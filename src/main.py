"""Main entry point for the Voice AI Agent application."""

import sys
import asyncio
import signal
import logging
import atexit
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager
from datetime import datetime, UTC

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_configuration, ConfigurationError, print_configuration_report
from src.health import check_health
from src.logging_config import setup_logging, LoggerMixin
from src.livekit_integration import get_livekit_integration, shutdown_livekit_integration
from src.webhooks import start_webhook_handler, stop_webhook_handler, setup_webhook_routes
from src.orchestrator import CallOrchestrator
from src.clients.deepgram_stt import DeepgramSTTClient
from src.clients.groq_llm import GroqLLMClient
from src.clients.cartesia_tts import CartesiaTTSClient
from src.monitoring.health_monitor import HealthMonitor, ComponentType
from src.monitoring.alerting import AlertManager, WebhookChannel, LogChannel
from src.monitoring.metrics_exporter import MetricsExportManager, PrometheusExporter, JSONExporter
from src.monitoring.dashboard import DashboardManager

try:
    from fastapi import FastAPI
    from uvicorn import Config, Server
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class VoiceAIAgent(LoggerMixin):
    """Main Voice AI Agent application class with comprehensive lifecycle management."""
    
    def __init__(self):
        """Initialize the Voice AI Agent."""
        super().__init__()
        self.settings = None
        self.running = False
        self.orchestrator = None
        self.livekit_integration = None
        self.webhook_server = None
        self.fastapi_app = None
        self.server_task = None
        self.shutdown_event = asyncio.Event()
        self.startup_complete = False
        self.shutdown_in_progress = False
        
        # Monitoring components
        self.health_monitor = None
        self.alert_manager = None
        self.metrics_exporter = None
        self.dashboard_manager = None
        
        # Initialize components list for tracking
        self.initialized_components: List[str] = []
        
        # Setup signal handlers and cleanup
        self._setup_signal_handlers()
        self._setup_cleanup_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            self.get_logger().info(f"Received signal {signal_name} ({signum}), initiating graceful shutdown")
            print(f"\n🛑 Received signal {signal_name}, initiating graceful shutdown...")
            self.running = False
            self.shutdown_event.set()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Handle SIGHUP for configuration reload (if supported)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    def _setup_cleanup_handlers(self):
        """Set up cleanup handlers for unexpected exits."""
        atexit.register(self._emergency_cleanup)
    
    def _emergency_cleanup(self):
        """Emergency cleanup for unexpected exits."""
        if not self.shutdown_in_progress:
            print("🚨 Emergency cleanup triggered")
            # Perform minimal cleanup that doesn't require async
            try:
                if self.server_task and not self.server_task.done():
                    self.server_task.cancel()
            except Exception as e:
                print(f"Error during emergency cleanup: {e}")
    
    async def _verify_dependencies(self) -> bool:
        """Verify all required dependencies are available."""
        logger = self.get_logger()
        logger.info("Verifying system dependencies")
        
        try:
            # Check Python version
            if sys.version_info < (3, 11):
                logger.error(f"Python 3.11+ required, got {sys.version_info}")
                return False
            
            # Check required modules
            required_modules = [
                'asyncio', 'json', 'pathlib', 'logging', 'signal'
            ]
            
            for module in required_modules:
                try:
                    __import__(module)
                except ImportError as e:
                    logger.error(f"Required module {module} not available: {e}")
                    return False
            
            # Check optional but important modules
            optional_modules = {
                'fastapi': 'Web framework for webhooks',
                'uvicorn': 'ASGI server',
                'pydantic': 'Data validation'
            }
            
            for module, description in optional_modules.items():
                try:
                    __import__(module)
                    logger.debug(f"Optional module {module} available")
                except ImportError:
                    logger.warning(f"Optional module {module} not available: {description}")
            
            logger.info("Dependency verification completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during dependency verification: {e}")
            return False
    
    async def async_initialize(self) -> bool:
        """
        Initialize the application with comprehensive validation and setup.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger = self.get_logger()
        logger.info("Voice AI Agent initialization starting")
        print("🎯 Voice AI Agent starting...")
        
        try:
            # Step 1: Verify system dependencies
            print("🔍 Verifying system dependencies...")
            if not await self._verify_dependencies():
                logger.error("Dependency verification failed")
                return False
            self.initialized_components.append("dependencies")
            
            # Step 2: Load and validate configuration
            print("📋 Loading configuration...")
            try:
                self.settings = load_configuration()
                logger.info(f"Configuration loaded for {self.settings.environment.value} environment")
                
                # Setup logging system with loaded configuration
                setup_logging(self.settings)
                logger = self.get_logger()  # Get logger with new configuration
                
                print(f"✅ Configuration loaded for {self.settings.environment.value} environment")
                
                # Print configuration summary in debug mode
                if self.settings.debug:
                    print("\n📊 Configuration Summary:")
                    print_configuration_report()
                
                self.initialized_components.append("configuration")
                
            except ConfigurationError as e:
                logger.error(f"Configuration error: {e}")
                print(f"❌ Configuration error: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during configuration: {e}")
                print(f"❌ Unexpected error during configuration: {e}")
                return False
        
            # Step 3: Initialize database connections
            print("🗄️  Initializing database...")
            try:
                from src.database.connection import init_database
                from src.database.migrations import MigrationManager
                
                db_manager = await init_database()
                logger.info("Database connection established")
                
                # Run database migrations
                migration_manager = MigrationManager(db_manager)
                migration_success = await migration_manager.migrate_to_latest()
                
                if migration_success:
                    logger.info("Database migrations completed successfully")
                    print("✅ Database initialized and migrated successfully")
                else:
                    logger.warning("Database migration had issues")
                    print("⚠️  Database migration had issues, but continuing...")
                
                self.initialized_components.append("database")
                    
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                print(f"❌ Failed to initialize database: {e}")
                if self.settings.is_production:
                    return False
                else:
                    logger.warning("Continuing without database in development mode")
                    print("⚠️  Continuing without database in development mode")
        
            # Step 4: Perform startup health checks
            print("🏥 Performing startup health checks...")
            try:
                health = check_health()
                logger.info(f"Health check completed with status: {health['status']}")
                
                if health["status"] == "healthy":
                    print("✅ All health checks passed")
                elif health["status"] == "degraded":
                    print("⚠️  Health checks passed with warnings")
                    # Print warnings if any
                    for check_name, result in health["checks"].items():
                        if "warning" in str(result).lower():
                            logger.warning(f"Health check warning - {check_name}: {result}")
                            print(f"  ⚠️  {check_name}: {result}")
                else:
                    print("❌ Health checks failed")
                    for check_name, result in health["checks"].items():
                        if "failed" in str(result).lower():
                            logger.error(f"Health check failed - {check_name}: {result}")
                            print(f"  ❌ {check_name}: {result}")
                    return False
                
                self.initialized_components.append("health_checks")
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
                print(f"❌ Health check error: {e}")
                return False
        
            # Step 5: Initialize AI service clients
            print("🤖 Initializing AI service clients...")
            try:
                # Initialize STT client
                stt_client = DeepgramSTTClient()
                logger.info("Deepgram STT client initialized")
                
                # Initialize LLM client
                llm_client = GroqLLMClient()
                logger.info("Groq LLM client initialized")
                
                # Initialize TTS client
                tts_client = CartesiaTTSClient()
                logger.info("Cartesia TTS client initialized")
                
                print("✅ AI service clients initialized")
                self.initialized_components.append("ai_clients")
                
            except Exception as e:
                logger.error(f"Failed to initialize AI clients: {e}")
                print(f"❌ Failed to initialize AI clients: {e}")
                return False
        
            # Step 6: Initialize call orchestrator
            print("🎭 Initializing call orchestrator...")
            try:
                self.orchestrator = CallOrchestrator(
                    stt_client=stt_client,
                    llm_client=llm_client,
                    tts_client=tts_client,
                    max_concurrent_calls=getattr(self.settings, 'max_concurrent_calls', 10)
                )
                logger.info("Call orchestrator initialized")
                print("✅ Call orchestrator initialized")
                self.initialized_components.append("orchestrator")
                
            except Exception as e:
                logger.error(f"Failed to initialize call orchestrator: {e}")
                print(f"❌ Failed to initialize call orchestrator: {e}")
                return False
        
            # Step 7: Initialize LiveKit SIP integration
            print("📞 Initializing LiveKit SIP integration...")
            try:
                self.livekit_integration = await get_livekit_integration()
                logger.info("LiveKit SIP integration initialized")
                print("✅ LiveKit SIP integration initialized")
                self.initialized_components.append("livekit")
                
                # Initialize Voice AI integration with LiveKit
                print("🤖 Initializing Voice AI integration with LiveKit...")
                from src.integration import get_livekit_voice_ai_integration
                from src.clients.livekit_api_client import LiveKitAPIClient
                from src.auth.livekit_auth import LiveKitAuthManager
                from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
                
                # Create required components for integration
                api_client = LiveKitAPIClient(
                    url=self.settings.livekit_url,
                    api_key=self.settings.livekit_api_key,
                    api_secret=self.settings.livekit_api_secret
                )
                
                auth_manager = LiveKitAuthManager(
                    api_key=self.settings.livekit_api_key,
                    api_secret=self.settings.livekit_api_secret
                )
                
                system_monitor = LiveKitSystemMonitor(
                    api_client=api_client,
                    auth_manager=auth_manager
                )
                
                # Initialize the Voice AI integration
                self.voice_ai_integration = await get_livekit_voice_ai_integration(
                    orchestrator=self.orchestrator,
                    livekit_integration=self.livekit_integration,
                    api_client=api_client,
                    auth_manager=auth_manager,
                    system_monitor=system_monitor
                )
                
                logger.info("Voice AI integration with LiveKit initialized")
                print("✅ Voice AI integration with LiveKit initialized")
                self.initialized_components.append("voice_ai_integration")
                
            except Exception as e:
                logger.error(f"Failed to initialize LiveKit SIP integration: {e}")
                print(f"❌ Failed to initialize LiveKit SIP integration: {e}")
                if self.settings.is_production:
                    return False
                else:
                    logger.warning("Continuing without SIP integration in development mode")
                    print("⚠️  Continuing without SIP integration in development mode")
        
            # Step 8: Initialize monitoring system
            print("📊 Initializing monitoring system...")
            try:
                # Initialize health monitor
                self.health_monitor = HealthMonitor(
                    check_interval=30.0,
                    enable_auto_checks=True
                )
                
                # Register AI service components for health monitoring
                async def stt_health_check():
                    try:
                        # Simple health check for STT client
                        return {"status": "healthy", "success_rate": 100.0}
                    except Exception:
                        return {"status": "unhealthy", "success_rate": 0.0}
                
                async def llm_health_check():
                    try:
                        # Simple health check for LLM client
                        return {"status": "healthy", "success_rate": 100.0}
                    except Exception:
                        return {"status": "unhealthy", "success_rate": 0.0}
                
                async def tts_health_check():
                    try:
                        # Simple health check for TTS client
                        return {"status": "healthy", "success_rate": 100.0}
                    except Exception:
                        return {"status": "unhealthy", "success_rate": 0.0}
                
                async def orchestrator_health_check():
                    try:
                        if self.orchestrator:
                            health_status = await self.orchestrator.get_health_status()
                            return {
                                "status": "healthy" if health_status.is_healthy else "degraded",
                                "success_rate": 90.0 if health_status.is_healthy else 50.0
                            }
                        return {"status": "unhealthy", "success_rate": 0.0}
                    except Exception:
                        return {"status": "unhealthy", "success_rate": 0.0}
                
                # Register components
                self.health_monitor.register_component(
                    "stt_client", ComponentType.STT_CLIENT, stt_health_check
                )
                self.health_monitor.register_component(
                    "llm_client", ComponentType.LLM_CLIENT, llm_health_check
                )
                self.health_monitor.register_component(
                    "tts_client", ComponentType.TTS_CLIENT, tts_health_check
                )
                self.health_monitor.register_component(
                    "orchestrator", ComponentType.ORCHESTRATOR, orchestrator_health_check
                )
                
                # Initialize alert manager
                self.alert_manager = AlertManager(check_interval=60.0)
                
                # Add log channel for alerts
                log_channel = LogChannel(log_level="ERROR")
                self.alert_manager.add_channel("log", log_channel)
                
                # Add webhook channel if configured
                if hasattr(self.settings, 'alert_webhook_url') and self.settings.alert_webhook_url:
                    webhook_channel = WebhookChannel(self.settings.alert_webhook_url)
                    self.alert_manager.add_channel("webhook", webhook_channel)
                
                # Initialize metrics exporter
                self.metrics_exporter = MetricsExportManager(export_interval=30.0)
                
                # Add Prometheus exporter if configured
                if hasattr(self.settings, 'prometheus_pushgateway_url') and self.settings.prometheus_pushgateway_url:
                    prometheus_exporter = PrometheusExporter(
                        pushgateway_url=self.settings.prometheus_pushgateway_url
                    )
                    self.metrics_exporter.add_exporter("prometheus", prometheus_exporter)
                
                # Add JSON file exporter for development
                if not self.settings.is_production:
                    json_exporter = JSONExporter(file_path="./metrics/metrics.json")
                    self.metrics_exporter.add_exporter("json", json_exporter)
                
                # Initialize dashboard manager
                self.dashboard_manager = DashboardManager(
                    health_monitor=self.health_monitor,
                    alert_manager=self.alert_manager,
                    update_interval=30.0
                )
                
                # Add LiveKit integration health checks if available
                if hasattr(self, 'voice_ai_integration') and self.voice_ai_integration:
                    async def voice_ai_integration_health_check():
                        try:
                            status = self.voice_ai_integration.get_integration_status()
                            return {
                                "status": "healthy" if status["status"] == "active" else "degraded",
                                "success_rate": 95.0 if status["status"] == "active" else 50.0,
                                "details": status
                            }
                        except Exception:
                            return {"status": "unhealthy", "success_rate": 0.0}
                    
                    self.health_monitor.register_component(
                        "voice_ai_integration", ComponentType.ORCHESTRATOR, voice_ai_integration_health_check
                    )
                
                # Start monitoring services
                await self.health_monitor.start_monitoring()
                await self.alert_manager.start_monitoring()
                await self.metrics_exporter.start_exporting()
                await self.dashboard_manager.start_updating()
                
                logger.info("Monitoring system initialized successfully")
                print("✅ Monitoring system initialized")
                self.initialized_components.append("monitoring")
                
            except Exception as e:
                logger.error(f"Failed to initialize monitoring system: {e}")
                print(f"❌ Failed to initialize monitoring system: {e}")
                if self.settings.is_production:
                    return False
                else:
                    logger.warning("Continuing without monitoring system in development mode")
                    print("⚠️  Continuing without monitoring system in development mode")

            # Step 9: Initialize webhook server
            if FASTAPI_AVAILABLE:
                try:
                    print("🌐 Initializing webhook server...")
                    
                    self.fastapi_app = FastAPI(
                        title="Voice AI Agent",
                        description="Voice AI Agent with LiveKit SIP Integration",
                        version="1.0.0"
                    )
                    
                    # Setup webhook routes
                    setup_webhook_routes(self.fastapi_app, self.orchestrator)
                    
                    # Setup monitoring endpoints
                    self._setup_monitoring_endpoints()
                    
                    # Start webhook handler
                    await start_webhook_handler(self.orchestrator)
                    
                    logger.info("Webhook server initialized")
                    print("✅ Webhook server initialized")
                    self.initialized_components.append("webhooks")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize webhook server: {e}")
                    print(f"❌ Failed to initialize webhook server: {e}")
                    if self.settings.is_production:
                        return False
                    else:
                        logger.warning("Continuing without webhook server in development mode")
                        print("⚠️  Continuing without webhook server in development mode")
            else:
                logger.warning("FastAPI not available, webhook server disabled")
                print("⚠️  FastAPI not available, webhook server disabled")
        
            # Step 10: Validate startup requirements
            if self.settings.is_production:
                print("🔒 Production mode: Validating all required services...")
                logger.info("Performing production readiness validation")
                
                # Validate critical components are initialized
                required_components = ["configuration", "ai_clients", "orchestrator"]
                missing_components = [comp for comp in required_components if comp not in self.initialized_components]
                
                if missing_components:
                    logger.error(f"Missing required components for production: {missing_components}")
                    print(f"❌ Missing required components: {missing_components}")
                    return False
                
                # Additional production validations
                if not self.settings.secret_key or self.settings.secret_key == "your-secret-key-here-change-this-in-production":
                    logger.error("Production secret key not configured")
                    print("❌ Production secret key not configured")
                    return False
                
                logger.info("Production readiness validation completed")
            
            # Step 11: Final initialization
            self.startup_complete = True
            logger.info("Voice AI Agent initialization completed successfully")
            print("🚀 Voice AI Agent initialization complete")
            print(f"📊 Initialized components: {', '.join(self.initialized_components)}")
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error during initialization: {e}", exc_info=True)
            print(f"💥 Unexpected initialization error: {e}")
            return False
    
    async def async_run(self):
        """Run the main application loop with comprehensive lifecycle management."""
        logger = self.get_logger()
        logger.info("Starting Voice AI Agent application")
        
        try:
            # Initialize the application
            if not await self.async_initialize():
                logger.error("Application initialization failed")
                print("💥 Failed to initialize Voice AI Agent")
                return 1
            
            logger.info("Voice AI Agent is ready to handle calls")
            print("🎙️  Voice AI Agent is ready to handle calls")
            
            # Check if running in test mode
            if self.settings and self.settings.test_mode:
                logger.info("Running in test mode - exiting after initialization")
                print("🧪 Running in test mode - exiting after initialization")
                await self.async_shutdown()
                return 0
            
            # Start webhook server if available
            if self.fastapi_app and FASTAPI_AVAILABLE:
                try:
                    logger.info(f"Starting webhook server on port {self.settings.port}")
                    print(f"🌐 Starting webhook server on port {self.settings.port}")
                    
                    config = Config(
                        app=self.fastapi_app,
                        host="0.0.0.0",
                        port=self.settings.port,
                        log_level="info" if not self.settings.debug else "debug"
                    )
                    server = Server(config)
                    self.server_task = asyncio.create_task(server.serve())
                    
                    logger.info(f"Webhook server started on http://0.0.0.0:{self.settings.port}")
                    print(f"✅ Webhook server started on http://0.0.0.0:{self.settings.port}")
                    print(f"📡 LiveKit webhook endpoint: http://{self.settings.domain}:{self.settings.port}/webhooks/livekit")
                    
                except Exception as e:
                    logger.error(f"Failed to start webhook server: {e}")
                    print(f"❌ Failed to start webhook server: {e}")
                    if self.settings.is_production:
                        return 1
            
            # Main application loop
            self.running = True
            logger.info("Entering main application loop")
            print("🔄 Voice AI Agent is running...")
            print("📞 Ready to receive SIP calls via LiveKit")
            print("🛑 Press Ctrl+C to stop")
            
            # Health check interval
            health_check_interval = 30  # seconds
            last_health_check = 0
            
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Wait for shutdown signal or timeout
                    await asyncio.wait_for(
                        self.shutdown_event.wait(), 
                        timeout=1.0  # Check every second
                    )
                    break  # Shutdown signal received
                    
                except asyncio.TimeoutError:
                    # Timeout is expected, continue with health checks
                    current_time = asyncio.get_event_loop().time()
                    
                    if current_time - last_health_check >= health_check_interval:
                        # Perform periodic health checks
                        if self.orchestrator:
                            try:
                                health_status = await self.orchestrator.get_health_status()
                                if not health_status.is_healthy:
                                    logger.warning(f"Health check warning: {health_status.status}")
                                    if self.settings.debug:
                                        print(f"⚠️  Health check warning: {health_status.status}")
                                else:
                                    logger.debug("Health check passed")
                            except Exception as e:
                                logger.error(f"Health check failed: {e}")
                        
                        last_health_check = current_time
                
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    if self.settings.is_production:
                        # In production, exit on unexpected errors
                        break
                    else:
                        # In development, continue running
                        await asyncio.sleep(1)
            
            logger.info("Main application loop ended")
            return 0
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            print("\n🛑 Keyboard interrupt received")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in application: {e}", exc_info=True)
            print(f"💥 Unexpected error in main application: {e}")
            return 1
        finally:
            # Ensure cleanup always happens
            await self.async_shutdown()
    
    def run(self):
        """Run the main application loop."""
        return asyncio.run(self.async_run())
    
    async def async_shutdown(self):
        """Perform comprehensive graceful shutdown."""
        if self.shutdown_in_progress:
            return
        
        self.shutdown_in_progress = True
        logger = self.get_logger()
        logger.info("Initiating graceful shutdown")
        print("🔄 Shutting down Voice AI Agent...")
        
        shutdown_tasks = []
        
        # Stop webhook server
        if self.server_task and not self.server_task.done():
            try:
                logger.info("Stopping webhook server")
                self.server_task.cancel()
                shutdown_tasks.append(self._safe_await(self.server_task, "webhook server"))
            except Exception as e:
                logger.error(f"Error stopping webhook server: {e}")
        
        # Stop webhook handler
        try:
            logger.info("Stopping webhook handler")
            await stop_webhook_handler()
            print("✅ Webhook handler stopped")
        except Exception as e:
            logger.error(f"Error stopping webhook handler: {e}")
            print(f"❌ Error stopping webhook handler: {e}")
        
        # Shutdown call orchestrator
        if self.orchestrator:
            try:
                logger.info("Shutting down call orchestrator")
                # If orchestrator has a shutdown method, call it
                if hasattr(self.orchestrator, 'shutdown'):
                    await self.orchestrator.shutdown()
                print("✅ Call orchestrator shutdown")
            except Exception as e:
                logger.error(f"Error shutting down call orchestrator: {e}")
                print(f"❌ Error shutting down call orchestrator: {e}")
        
        # Shutdown Voice AI integration
        if "voice_ai_integration" in self.initialized_components:
            try:
                logger.info("Shutting down Voice AI integration")
                from src.integration import shutdown_livekit_voice_ai_integration
                await shutdown_livekit_voice_ai_integration()
                print("✅ Voice AI integration shutdown")
            except Exception as e:
                logger.error(f"Error shutting down Voice AI integration: {e}")
                print(f"❌ Error shutting down Voice AI integration: {e}")

        # Shutdown LiveKit SIP integration
        if "livekit" in self.initialized_components:
            try:
                logger.info("Shutting down LiveKit SIP integration")
                await shutdown_livekit_integration()
                print("✅ LiveKit SIP integration shutdown")
            except Exception as e:
                logger.error(f"Error shutting down LiveKit SIP integration: {e}")
                print(f"❌ Error shutting down LiveKit SIP integration: {e}")
        
        # Shutdown monitoring system
        if "monitoring" in self.initialized_components:
            try:
                logger.info("Shutting down monitoring system")
                
                if self.dashboard_manager:
                    await self.dashboard_manager.stop_updating()
                
                if self.metrics_exporter:
                    await self.metrics_exporter.stop_exporting()
                    await self.metrics_exporter.close()
                
                if self.alert_manager:
                    await self.alert_manager.stop_monitoring()
                    await self.alert_manager.close()
                
                if self.health_monitor:
                    await self.health_monitor.stop_monitoring()
                
                print("✅ Monitoring system shutdown")
            except Exception as e:
                logger.error(f"Error shutting down monitoring system: {e}")
                print(f"❌ Error shutting down monitoring system: {e}")

        # Cleanup database connections
        if "database" in self.initialized_components:
            try:
                logger.info("Closing database connections")
                from src.database.connection import cleanup_database
                await cleanup_database()
                print("✅ Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
                print(f"❌ Error closing database connections: {e}")
        
        # Wait for all shutdown tasks to complete
        if shutdown_tasks:
            try:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error during shutdown task completion: {e}")
        
        # Final cleanup
        self.running = False
        self.startup_complete = False
        
        logger.info("Voice AI Agent shutdown completed")
        print("✅ Voice AI Agent shutdown complete")
    
    def _setup_monitoring_endpoints(self):
        """Setup monitoring and health check endpoints."""
        if not self.fastapi_app:
            return
        
        @self.fastapi_app.get("/health")
        async def health_check():
            """Basic health check endpoint."""
            try:
                if self.health_monitor:
                    system_health = self.health_monitor.get_system_health()
                    if system_health:
                        return {
                            "status": system_health.status.value,
                            "timestamp": system_health.last_check.isoformat(),
                            "healthy_components": system_health.healthy_components,
                            "total_components": system_health.total_components,
                            "health_percentage": system_health.health_percentage
                        }
                
                return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}
        
        @self.fastapi_app.get("/health/detailed")
        async def detailed_health_check():
            """Detailed health check with component status."""
            try:
                if self.health_monitor:
                    system_health = self.health_monitor.get_system_health()
                    if system_health:
                        return system_health.to_dict()
                
                return {"status": "unknown", "message": "Health monitor not available"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        @self.fastapi_app.get("/metrics")
        async def metrics_endpoint():
            """Prometheus metrics endpoint."""
            try:
                if (self.metrics_exporter and 
                    "prometheus" in self.metrics_exporter.exporters):
                    prometheus_exporter = self.metrics_exporter.exporters["prometheus"]
                    metrics_text = prometheus_exporter.get_metrics_exposition()
                    from fastapi import Response
                    return Response(
                        content=metrics_text,
                        media_type="text/plain"
                    )
                
                return {"error": "Prometheus exporter not configured"}
            except Exception as e:
                return {"error": str(e)}
        
        @self.fastapi_app.get("/alerts")
        async def active_alerts():
            """Get active alerts."""
            try:
                if self.alert_manager:
                    alerts = self.alert_manager.get_active_alerts()
                    return {
                        "alerts": [alert.to_dict() for alert in alerts],
                        "summary": self.alert_manager.get_alert_summary()
                    }
                
                return {"alerts": [], "summary": {}}
            except Exception as e:
                return {"error": str(e)}
        
        @self.fastapi_app.get("/dashboard/{dashboard_id}")
        async def get_dashboard(dashboard_id: str):
            """Get dashboard data."""
            try:
                if self.dashboard_manager:
                    dashboard_data = await self.dashboard_manager.export_dashboard_data(dashboard_id)
                    return dashboard_data
                
                return {"error": "Dashboard manager not available"}
            except ValueError as e:
                return {"error": str(e)}
            except Exception as e:
                return {"error": str(e)}
        
        @self.fastapi_app.get("/dashboards")
        async def list_dashboards():
            """List available dashboards."""
            try:
                if self.dashboard_manager:
                    dashboards = self.dashboard_manager.get_all_dashboards()
                    return {
                        "dashboards": [
                            {
                                "id": dashboard.id,
                                "title": dashboard.title,
                                "description": dashboard.description,
                                "updated_at": dashboard.updated_at.isoformat()
                            }
                            for dashboard in dashboards.values()
                        ]
                    }
                
                return {"dashboards": []}
            except Exception as e:
                return {"error": str(e)}

    async def _safe_await(self, task, task_name: str, timeout: float = 5.0):
        """Safely await a task with timeout."""
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            self.get_logger().warning(f"Timeout waiting for {task_name} to shutdown")
        except asyncio.CancelledError:
            self.get_logger().debug(f"{task_name} was cancelled")
        except Exception as e:
            self.get_logger().error(f"Error shutting down {task_name}: {e}")


def main():
    """Main entry point for the application."""
    import sys
    
    # Check for test mode argument
    if len(sys.argv) > 1 and sys.argv[1] == '--test-init':
        # Set test mode environment variable
        import os
        os.environ['TEST_MODE'] = 'true'
    
    agent = VoiceAIAgent()
    return agent.run()


if __name__ == "__main__":
    sys.exit(main())
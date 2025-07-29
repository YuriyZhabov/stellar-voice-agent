"""Main entry point for the Voice AI Agent application."""

import sys
import asyncio
import signal
from pathlib import Path
from typing import Optional

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_configuration, ConfigurationError, print_configuration_report
from src.health import check_health
from src.logging_config import setup_logging


class VoiceAIAgent:
    """Main Voice AI Agent application class."""
    
    def __init__(self):
        """Initialize the Voice AI Agent."""
        self.settings = None
        self.running = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def initialize(self) -> bool:
        """
        Initialize the application with configuration validation.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        print("🎯 Voice AI Agent starting...")
        
        # Load and validate configuration
        try:
            print("📋 Loading configuration...")
            self.settings = load_configuration()
            
            # Setup logging system
            setup_logging(self.settings)
            
            print(f"✅ Configuration loaded for {self.settings.environment.value} environment")
            
            # Print configuration summary in debug mode
            if self.settings.debug:
                print("\n📊 Configuration Summary:")
                print_configuration_report()
            
        except ConfigurationError as e:
            print(f"❌ Configuration error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during configuration: {e}")
            return False
        
        # Perform health checks
        try:
            print("🏥 Performing health checks...")
            health = check_health()
            
            if health["status"] == "healthy":
                print("✅ All health checks passed")
            elif health["status"] == "degraded":
                print("⚠️  Health checks passed with warnings")
                # Print warnings if any
                for check_name, result in health["checks"].items():
                    if "warning" in str(result).lower():
                        print(f"  ⚠️  {check_name}: {result}")
            else:
                print("❌ Health checks failed")
                for check_name, result in health["checks"].items():
                    if "failed" in str(result).lower():
                        print(f"  ❌ {check_name}: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
        
        # Validate startup requirements
        if self.settings.is_production:
            print("🔒 Production mode: Validating all required services...")
            # Additional production validations would go here
        
        print("🚀 Voice AI Agent initialization complete")
        return True
    
    def run(self):
        """Run the main application loop."""
        if not self.initialize():
            print("💥 Failed to initialize Voice AI Agent")
            return 1
        
        print("🎙️  Voice AI Agent is ready to handle calls")
        print("⚠️  This is a placeholder main loop")
        print("🔧 Actual call handling logic will be implemented in future tasks")
        
        # Check if running in test mode
        if self.settings and self.settings.test_mode:
            print("🧪 Running in test mode - exiting after initialization")
            self.shutdown()
            return 0
        
        # Main application loop placeholder
        self.running = True
        try:
            import time
            while self.running:
                # Placeholder for main application logic
                # In future tasks, this will handle:
                # - LiveKit connections
                # - SIP call management
                # - AI service orchestration
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received")
        except Exception as e:
            print(f"💥 Unexpected error in main loop: {e}")
            return 1
        finally:
            self.shutdown()
        
        return 0
    
    def shutdown(self):
        """Perform graceful shutdown."""
        print("🔄 Shutting down Voice AI Agent...")
        
        # Placeholder for cleanup tasks
        # In future tasks, this will:
        # - Close database connections
        # - Disconnect from LiveKit
        # - Clean up audio resources
        # - Save any pending data
        
        print("✅ Voice AI Agent shutdown complete")


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
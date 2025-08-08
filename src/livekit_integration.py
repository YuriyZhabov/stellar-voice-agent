"""
LiveKit SIP Integration Module

This module provides integration with LiveKit SIP services, including:
- SIP trunk configuration and management
- Call metadata transmission
- Connection monitoring and automatic reconnection
- Audio quality optimization
- Webhook handling for LiveKit events
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from uuid import uuid4

import yaml
from livekit import api, rtc
from livekit.api import AccessToken, VideoGrants

from src.config import get_settings
from src.metrics import get_metrics_collector, timer
from src.orchestrator import CallContext, CallOrchestrator
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager


logger = logging.getLogger(__name__)


class SIPTrunkStatus(str, Enum):
    """SIP trunk status enumeration."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    FAILED = "failed"
    UNKNOWN = "unknown"


class LiveKitEventType(str, Enum):
    """LiveKit event types."""
    ROOM_STARTED = "room_started"
    ROOM_FINISHED = "room_finished"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    TRACK_PUBLISHED = "track_published"
    TRACK_UNPUBLISHED = "track_unpublished"
    RECORDING_STARTED = "recording_started"
    RECORDING_FINISHED = "recording_finished"


@dataclass
class SIPTrunkConfig:
    """SIP trunk configuration."""
    name: str
    host: str
    port: int
    transport: str
    username: str
    password: str
    register: bool = True
    register_interval: int = 300
    keep_alive_interval: int = 30
    health_check_enabled: bool = True
    health_check_interval: int = 60
    health_check_timeout: int = 10
    max_failures: int = 3
    retry_enabled: bool = True
    retry_initial_delay: int = 1000
    retry_max_delay: int = 30000
    retry_multiplier: float = 2.0
    retry_max_attempts: int = 5


@dataclass
class AudioCodecConfig:
    """Audio codec configuration."""
    name: str
    payload_type: int
    sample_rate: int
    channels: int
    priority: int
    enabled: bool = True


@dataclass
class CallMetadata:
    """Call metadata for transmission."""
    call_id: str
    caller_number: str
    called_number: str
    start_time: datetime
    trunk_name: str
    codec_used: str
    caller_ip: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "call_id": self.call_id,
            "caller_number": self.caller_number,
            "called_number": self.called_number,
            "start_time": self.start_time.isoformat(),
            "trunk_name": self.trunk_name,
            "codec_used": self.codec_used,
            "caller_ip": self.caller_ip,
            "custom_headers": self.custom_headers
        }


@dataclass
class SIPTrunkHealth:
    """SIP trunk health status."""
    trunk_name: str
    status: SIPTrunkStatus
    last_check: datetime
    response_time: float
    failure_count: int
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trunk_name": self.trunk_name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "response_time": self.response_time,
            "failure_count": self.failure_count,
            "last_error": self.last_error
        }


class LiveKitSIPIntegration:
    """
    LiveKit SIP Integration manager.
    
    Handles SIP trunk configuration, call routing, metadata transmission,
    and connection monitoring with automatic reconnection.
    """
    
    def __init__(self, config_path: str = "livekit-sip.yaml"):
        """
        Initialize LiveKit SIP integration.
        
        Args:
            config_path: Path to the LiveKit SIP configuration file
        """
        self.config_path = config_path
        self.settings = get_settings()
        self.metrics_collector = get_metrics_collector()
        
        # Configuration
        self.sip_config: Dict[str, Any] = {}
        self.sip_trunks: Dict[str, SIPTrunkConfig] = {}
        self.audio_codecs: List[AudioCodecConfig] = []
        
        # Connection management
        self.livekit_client: Optional[api.LiveKitAPI] = None
        self.api_client: Optional[LiveKitAPIClient] = None
        self.auth_manager: Optional[LiveKitAuthManager] = None
        self.trunk_health: Dict[str, SIPTrunkHealth] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        
        # Event handling
        self.event_handlers: Dict[LiveKitEventType, List[Callable]] = {
            event_type: [] for event_type in LiveKitEventType
        }
        
        # Monitoring
        self.health_check_task: Optional[asyncio.Task] = None
        self.reconnection_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.total_calls = 0
        self.active_calls = 0
        self.failed_calls = 0
        self.reconnection_attempts = 0
        
        logger.info("LiveKit SIP Integration initialized")
    
    async def initialize(self) -> None:
        """Initialize the SIP integration."""
        try:
            # Load configuration
            await self._load_configuration()
            
            # Initialize LiveKit client
            await self._initialize_livekit_client()
            
            # Initialize enhanced API client and auth manager
            await self._initialize_enhanced_clients()
            
            # Configure SIP trunks
            await self._configure_sip_trunks()
            
            # Start health monitoring
            await self._start_health_monitoring()
            
            logger.info("LiveKit SIP Integration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize LiveKit SIP Integration: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the SIP integration."""
        try:
            logger.info("Shutting down LiveKit SIP Integration")
            
            # Stop health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Stop reconnection tasks
            for task in self.reconnection_tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Stop connection tasks
            for task in self.connection_tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close LiveKit client
            if self.livekit_client:
                # LiveKit client doesn't have explicit close method
                self.livekit_client = None
            
            logger.info("LiveKit SIP Integration shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during SIP integration shutdown: {e}")
    
    async def _load_configuration(self) -> None:
        """Load SIP configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                config_content = file.read()
            
            # Replace environment variables in configuration
            config_content = self._substitute_env_variables(config_content)
            
            # Parse YAML configuration
            self.sip_config = yaml.safe_load(config_content)
            
            # Parse SIP trunks
            for trunk_config in self.sip_config.get('sip_trunks', []):
                trunk = SIPTrunkConfig(
                    name=trunk_config['name'],
                    host=trunk_config['host'],
                    port=trunk_config['port'],
                    transport=trunk_config['transport'],
                    username=trunk_config['username'],
                    password=trunk_config['password'],
                    register=trunk_config.get('register', True),
                    register_interval=trunk_config.get('register_interval', 300),
                    keep_alive_interval=trunk_config.get('keep_alive_interval', 30),
                    health_check_enabled=trunk_config.get('health_check', {}).get('enabled', True),
                    health_check_interval=trunk_config.get('health_check', {}).get('interval', 60),
                    health_check_timeout=trunk_config.get('health_check', {}).get('timeout', 10),
                    max_failures=trunk_config.get('health_check', {}).get('max_failures', 3),
                    retry_enabled=trunk_config.get('retry', {}).get('enabled', True),
                    retry_initial_delay=trunk_config.get('retry', {}).get('initial_delay', 1000),
                    retry_max_delay=trunk_config.get('retry', {}).get('max_delay', 30000),
                    retry_multiplier=trunk_config.get('retry', {}).get('multiplier', 2.0),
                    retry_max_attempts=trunk_config.get('retry', {}).get('max_attempts', 5)
                )
                self.sip_trunks[trunk.name] = trunk
            
            # Parse audio codecs
            for codec_config in self.sip_config.get('audio_codecs', []):
                codec = AudioCodecConfig(
                    name=codec_config['name'],
                    payload_type=codec_config['payload_type'],
                    sample_rate=codec_config['sample_rate'],
                    channels=codec_config['channels'],
                    priority=codec_config['priority'],
                    enabled=codec_config.get('enabled', True)
                )
                self.audio_codecs.append(codec)
            
            # Sort codecs by priority
            self.audio_codecs.sort(key=lambda x: x.priority)
            
            logger.info(
                f"Loaded SIP configuration with {len(self.sip_trunks)} trunks and {len(self.audio_codecs)} codecs"
            )
            
        except Exception as e:
            logger.error(f"Failed to load SIP configuration: {e}")
            raise
    
    def _substitute_env_variables(self, content: str) -> str:
        """Substitute environment variables in configuration content."""
        import os
        import re
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_expr = match.group(1)
            
            # Check for default value syntax
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_expr, '')
        
        return re.sub(pattern, replace_var, content)
    
    async def _initialize_livekit_client(self) -> None:
        """Initialize LiveKit API client."""
        try:
            if not self.settings.livekit_url or not self.settings.livekit_api_key:
                raise ValueError("LiveKit URL and API key are required")
            
            self.livekit_client = api.LiveKitAPI(
                url=self.settings.livekit_url,
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret
            )
            
            # Test connection
            from livekit.api import ListRoomsRequest
            rooms = await self.livekit_client.room.list_rooms(ListRoomsRequest())
            logger.info(f"LiveKit client initialized successfully, found {len(rooms.rooms)} rooms")
            
        except Exception as e:
            logger.error(f"Failed to initialize LiveKit client: {e}")
            raise
    
    async def _initialize_enhanced_clients(self) -> None:
        """Initialize enhanced API client and auth manager."""
        try:
            # Initialize enhanced API client
            self.api_client = LiveKitAPIClient(
                url=self.settings.livekit_url,
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret
            )
            
            # Initialize auth manager
            self.auth_manager = LiveKitAuthManager(
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret
            )
            
            # Test enhanced client functionality
            health_result = await self.api_client.health_check()
            if not health_result.get('healthy', False):
                raise Exception(f"LiveKit API health check failed: {health_result.get('error', 'Unknown error')}")
            
            logger.info("Enhanced LiveKit clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced LiveKit clients: {e}")
            raise
    
    async def _configure_sip_trunks(self) -> None:
        """Configure SIP trunks."""
        try:
            for trunk_name, trunk_config in self.sip_trunks.items():
                # Initialize trunk health status
                self.trunk_health[trunk_name] = SIPTrunkHealth(
                    trunk_name=trunk_name,
                    status=SIPTrunkStatus.UNKNOWN,
                    last_check=datetime.now(UTC),
                    response_time=0.0,
                    failure_count=0
                )
                
                # Start connection monitoring task
                if trunk_config.health_check_enabled:
                    task = asyncio.create_task(
                        self._monitor_trunk_connection(trunk_name, trunk_config)
                    )
                    self.connection_tasks[trunk_name] = task
                
                logger.info(f"Configured SIP trunk: {trunk_name}")
            
        except Exception as e:
            logger.error(f"Failed to configure SIP trunks: {e}")
            raise
    
    async def _start_health_monitoring(self) -> None:
        """Start health monitoring task."""
        self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
    
    async def _health_monitoring_loop(self) -> None:
        """Main health monitoring loop."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all components."""
        try:
            # Check LiveKit connection
            if self.livekit_client:
                try:
                    from livekit.api import ListRoomsRequest
                    await self.livekit_client.room.list_rooms(ListRoomsRequest())
                    self.metrics_collector.set_gauge("livekit_connection_status", 1)
                except Exception as e:
                    logger.warning(f"LiveKit health check failed: {e}")
                    self.metrics_collector.set_gauge("livekit_connection_status", 0)
            
            # Update metrics
            self.metrics_collector.set_gauge("sip_trunks_total", len(self.sip_trunks))
            self.metrics_collector.set_gauge("active_calls_current", self.active_calls)
            self.metrics_collector.set_gauge("total_calls_handled", self.total_calls)
            
        except Exception as e:
            logger.error(f"Error performing health checks: {e}")
    
    async def _monitor_trunk_connection(self, trunk_name: str, trunk_config: SIPTrunkConfig) -> None:
        """Monitor SIP trunk connection."""
        while True:
            try:
                start_time = time.time()
                
                # Perform health check (simplified - in real implementation would use SIP OPTIONS)
                health_status = await self._check_trunk_health(trunk_config)
                
                response_time = time.time() - start_time
                
                # Update health status
                trunk_health = self.trunk_health[trunk_name]
                trunk_health.last_check = datetime.now(UTC)
                trunk_health.response_time = response_time
                
                if health_status:
                    trunk_health.status = SIPTrunkStatus.CONNECTED
                    trunk_health.failure_count = 0
                    trunk_health.last_error = None
                else:
                    trunk_health.failure_count += 1
                    trunk_health.status = SIPTrunkStatus.FAILED
                    trunk_health.last_error = "Health check failed"
                    
                    # Trigger reconnection if needed
                    if (trunk_health.failure_count >= trunk_config.max_failures and
                        trunk_config.retry_enabled):
                        await self._trigger_trunk_reconnection(trunk_name, trunk_config)
                
                # Update metrics
                self.metrics_collector.set_gauge(
                    "sip_trunk_status",
                    1 if health_status else 0,
                    labels={"trunk": trunk_name}
                )
                self.metrics_collector.record_histogram(
                    "sip_trunk_response_time",
                    response_time,
                    labels={"trunk": trunk_name}
                )
                
                await asyncio.sleep(trunk_config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring trunk {trunk_name}: {e}")
                await asyncio.sleep(trunk_config.health_check_interval)
    
    async def _check_trunk_health(self, trunk_config: SIPTrunkConfig) -> bool:
        """
        Check SIP trunk health.
        
        Args:
            trunk_config: SIP trunk configuration
            
        Returns:
            True if trunk is healthy, False otherwise
        """
        try:
            # In a real implementation, this would send a SIP OPTIONS request
            # For now, we'll simulate a basic connectivity check
            
            # Simulate network connectivity check
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(trunk_config.health_check_timeout)
            
            try:
                # Try to connect to the SIP server
                sock.connect((trunk_config.host, trunk_config.port))
                return True
            except (socket.timeout, socket.error):
                return False
            finally:
                sock.close()
                
        except Exception as e:
            logger.error(f"Error checking trunk health: {e}")
            return False
    
    async def _trigger_trunk_reconnection(self, trunk_name: str, trunk_config: SIPTrunkConfig) -> None:
        """Trigger SIP trunk reconnection."""
        if trunk_name in self.reconnection_tasks:
            return  # Reconnection already in progress
        
        logger.info(f"Triggering reconnection for trunk {trunk_name}")
        
        task = asyncio.create_task(
            self._reconnect_trunk(trunk_name, trunk_config)
        )
        self.reconnection_tasks[trunk_name] = task
    
    async def _reconnect_trunk(self, trunk_name: str, trunk_config: SIPTrunkConfig) -> None:
        """Reconnect to SIP trunk with exponential backoff."""
        try:
            delay = trunk_config.retry_initial_delay / 1000.0  # Convert to seconds
            
            for attempt in range(trunk_config.retry_max_attempts):
                logger.info(f"Reconnection attempt {attempt + 1} for trunk {trunk_name}")
                
                # Update status
                self.trunk_health[trunk_name].status = SIPTrunkStatus.CONNECTING
                
                # Attempt reconnection (simplified)
                success = await self._attempt_trunk_connection(trunk_config)
                
                if success:
                    logger.info(f"Successfully reconnected trunk {trunk_name}")
                    self.trunk_health[trunk_name].status = SIPTrunkStatus.CONNECTED
                    self.trunk_health[trunk_name].failure_count = 0
                    break
                else:
                    logger.warning(f"Reconnection attempt {attempt + 1} failed for trunk {trunk_name}")
                    
                    if attempt < trunk_config.retry_max_attempts - 1:
                        await asyncio.sleep(delay)
                        delay = min(delay * trunk_config.retry_multiplier, 
                                  trunk_config.retry_max_delay / 1000.0)
            else:
                logger.error(f"All reconnection attempts failed for trunk {trunk_name}")
                self.trunk_health[trunk_name].status = SIPTrunkStatus.FAILED
            
            self.reconnection_attempts += 1
            self.metrics_collector.increment_counter(
                "sip_trunk_reconnection_attempts",
                labels={"trunk": trunk_name}
            )
            
        except Exception as e:
            logger.error(f"Error during trunk reconnection: {e}")
        finally:
            # Clean up reconnection task
            self.reconnection_tasks.pop(trunk_name, None)
    
    async def _attempt_trunk_connection(self, trunk_config: SIPTrunkConfig) -> bool:
        """
        Attempt to connect to SIP trunk.
        
        Args:
            trunk_config: SIP trunk configuration
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # In a real implementation, this would establish SIP registration
            # For now, we'll simulate the connection attempt
            return await self._check_trunk_health(trunk_config)
            
        except Exception as e:
            logger.error(f"Error attempting trunk connection: {e}")
            return False
    
    async def handle_inbound_call(
        self, 
        caller_number: str, 
        called_number: str, 
        trunk_name: str,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> CallContext:
        """
        Handle inbound call and create LiveKit room with Voice AI integration.
        
        Args:
            caller_number: Caller's phone number
            called_number: Called phone number
            trunk_name: SIP trunk name
            custom_headers: Custom SIP headers
            
        Returns:
            CallContext for the new call
        """
        try:
            call_id = str(uuid4())
            room_name = f"voice-ai-call-{call_id}"
            
            # Create call metadata
            call_metadata = CallMetadata(
                call_id=call_id,
                caller_number=caller_number,
                called_number=called_number,
                start_time=datetime.now(UTC),
                trunk_name=trunk_name,
                codec_used=self._get_preferred_codec(),
                custom_headers=custom_headers or {}
            )
            
            # Create LiveKit room with Voice AI optimized settings using enhanced API client
            if self.api_client:
                room = await self.api_client.create_room(
                    name=room_name,
                    empty_timeout=300,  # 5 minutes
                    departure_timeout=20,  # 20 seconds
                    max_participants=2,  # Caller + AI Agent
                    metadata=call_metadata.to_dict()
                )
                logger.info(f"Room created using enhanced API client: {room_name}")
            else:
                # Fallback to original client
                room_options = api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=300,  # 5 minutes
                    departure_timeout=20,  # 20 seconds
                    max_participants=2,  # Caller + AI Agent
                    metadata=json.dumps(call_metadata.to_dict())
                )
                
                room = await self.livekit_client.room.create_room(room_options)
                logger.info(f"Room created using fallback client: {room_name}")
            
            # Create call context with enhanced metadata for Voice AI
            call_context = CallContext(
                call_id=call_id,
                caller_number=caller_number,
                start_time=call_metadata.start_time,
                livekit_room=room_name,
                metadata={
                    "called_number": called_number,
                    "trunk_name": trunk_name,
                    "codec_used": call_metadata.codec_used,
                    "custom_headers": call_metadata.custom_headers,
                    "room_sid": room.sid,
                    "voice_ai_enabled": True,
                    "audio_config": {
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "pcm"
                    }
                }
            )
            
            # Update statistics
            self.total_calls += 1
            self.active_calls += 1
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "inbound_calls_total",
                labels={"trunk": trunk_name, "voice_ai": "enabled"}
            )
            
            logger.info(
                f"Created Voice AI call {call_id} in room {room_name}",
                extra={
                    "call_id": call_id,
                    "caller_number": caller_number,
                    "called_number": called_number,
                    "trunk_name": trunk_name,
                    "room_sid": room.sid,
                    "voice_ai_enabled": True
                }
            )
            
            return call_context
            
        except Exception as e:
            logger.error(f"Error handling inbound call: {e}")
            self.failed_calls += 1
            self.metrics_collector.increment_counter("inbound_call_errors_total")
            raise
    
    async def handle_call_end(self, call_context: CallContext) -> None:
        """
        Handle call end and cleanup.
        
        Args:
            call_context: Call context
        """
        try:
            # Delete LiveKit room using enhanced API client
            if self.api_client:
                await self.api_client.delete_room(call_context.livekit_room)
                logger.info(f"Room deleted using enhanced API client: {call_context.livekit_room}")
            elif self.livekit_client:
                await self.livekit_client.room.delete_room(
                    api.DeleteRoomRequest(room=call_context.livekit_room)
                )
                logger.info(f"Room deleted using fallback client: {call_context.livekit_room}")
            
            # Update statistics
            self.active_calls = max(0, self.active_calls - 1)
            
            # Update metrics
            self.metrics_collector.set_gauge("active_calls_current", self.active_calls)
            
            logger.info(
                f"Cleaned up call {call_context.call_id}",
                extra={"call_id": call_context.call_id}
            )
            
        except Exception as e:
            logger.error(f"Error handling call end: {e}")
    
    def _get_preferred_codec(self) -> str:
        """Get the preferred audio codec."""
        for codec in self.audio_codecs:
            if codec.enabled:
                return codec.name
        return "PCMU"  # Default fallback
    
    def add_event_handler(self, event_type: LiveKitEventType, handler: Callable) -> None:
        """Add event handler for LiveKit events."""
        self.event_handlers[event_type].append(handler)
    
    async def handle_webhook_event(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming webhook event from LiveKit."""
        try:
            event_type = event_data.get('event')
            
            if event_type in [e.value for e in LiveKitEventType]:
                event_enum = LiveKitEventType(event_type)
                
                # Execute registered handlers
                for handler in self.event_handlers[event_enum]:
                    try:
                        await handler(event_data)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
                
                logger.debug(f"Processed webhook event: {event_type}")
            else:
                logger.warning(f"Unknown webhook event type: {event_type}")
                
        except Exception as e:
            logger.error(f"Error handling webhook event: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        return {
            "livekit_connected": self.livekit_client is not None,
            "sip_trunks": {
                name: health.to_dict() 
                for name, health in self.trunk_health.items()
            },
            "statistics": {
                "total_calls": self.total_calls,
                "active_calls": self.active_calls,
                "failed_calls": self.failed_calls,
                "reconnection_attempts": self.reconnection_attempts
            },
            "audio_codecs": [
                {
                    "name": codec.name,
                    "enabled": codec.enabled,
                    "priority": codec.priority
                }
                for codec in self.audio_codecs
            ]
        }


# Global instance
_livekit_integration: Optional[LiveKitSIPIntegration] = None


async def get_livekit_integration() -> LiveKitSIPIntegration:
    """Get the global LiveKit SIP integration instance."""
    global _livekit_integration
    
    if _livekit_integration is None:
        _livekit_integration = LiveKitSIPIntegration()
        await _livekit_integration.initialize()
    
    return _livekit_integration


async def shutdown_livekit_integration() -> None:
    """Shutdown the global LiveKit SIP integration instance."""
    global _livekit_integration
    
    if _livekit_integration:
        await _livekit_integration.shutdown()
        _livekit_integration = None
"""
LiveKit Voice AI Integration Module

This module provides enhanced integration between LiveKit and the Voice AI Agent system,
implementing the requirements for task 9: Integration with existing Voice AI Agent system.

Requirements addressed:
- 10.1: Webhook handler integration with LiveKit events
- 10.2: STT/TTS pipeline adaptation for LiveKit tracks
- 10.3: Room creation integration with existing call logic
- 10.4: Error handling compatibility with new system
- 10.5: Monitoring integration with existing systems
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from uuid import uuid4

from src.orchestrator import CallOrchestrator, CallContext
from src.livekit_integration import LiveKitSIPIntegration, LiveKitEventType
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class IntegrationStatus(Enum):
    """Integration status enumeration."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


@dataclass
class IntegrationMetrics:
    """Metrics for LiveKit Voice AI integration."""
    webhook_events_processed: int = 0
    audio_tracks_processed: int = 0
    stt_sessions_started: int = 0
    tts_responses_generated: int = 0
    integration_errors: int = 0
    room_creations: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "webhook_events_processed": self.webhook_events_processed,
            "audio_tracks_processed": self.audio_tracks_processed,
            "stt_sessions_started": self.stt_sessions_started,
            "tts_responses_generated": self.tts_responses_generated,
            "integration_errors": self.integration_errors,
            "room_creations": self.room_creations,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls
        }


class LiveKitVoiceAIIntegration:
    """
    Enhanced integration between LiveKit and Voice AI Agent system.
    
    This class provides:
    - Seamless webhook event handling integration
    - STT/TTS pipeline adaptation for LiveKit audio tracks
    - Room creation integration with existing call logic
    - Enhanced error handling with fallback mechanisms
    - Comprehensive monitoring and metrics integration
    """
    
    def __init__(
        self,
        orchestrator: CallOrchestrator,
        livekit_integration: LiveKitSIPIntegration,
        api_client: LiveKitAPIClient,
        auth_manager: LiveKitAuthManager,
        system_monitor: Optional[LiveKitSystemMonitor] = None
    ):
        """
        Initialize the LiveKit Voice AI integration.
        
        Args:
            orchestrator: Call orchestrator instance
            livekit_integration: LiveKit SIP integration instance
            api_client: LiveKit API client
            auth_manager: LiveKit authentication manager
            system_monitor: Optional system monitor instance
        """
        self.orchestrator = orchestrator
        self.livekit_integration = livekit_integration
        self.api_client = api_client
        self.auth_manager = auth_manager
        self.system_monitor = system_monitor
        
        # Integration state
        self.status = IntegrationStatus.INITIALIZING
        self.metrics = IntegrationMetrics()
        self.metrics_collector = get_metrics_collector()
        
        # Event handlers mapping
        self.event_handlers: Dict[LiveKitEventType, List[Callable]] = {
            LiveKitEventType.ROOM_STARTED: [self._handle_room_started_integration],
            LiveKitEventType.ROOM_FINISHED: [self._handle_room_finished_integration],
            LiveKitEventType.PARTICIPANT_JOINED: [self._handle_participant_joined_integration],
            LiveKitEventType.PARTICIPANT_LEFT: [self._handle_participant_left_integration],
            LiveKitEventType.TRACK_PUBLISHED: [self._handle_track_published_integration],
            LiveKitEventType.TRACK_UNPUBLISHED: [self._handle_track_unpublished_integration]
        }
        
        # Active call tracking for integration
        self.active_integrations: Dict[str, Dict[str, Any]] = {}  # call_id -> integration_data
        
        # Error handling and fallback
        self.error_handlers: List[Callable] = []
        self.fallback_enabled = True
        
        logger.info("LiveKit Voice AI Integration initialized")
    
    async def initialize(self) -> None:
        """Initialize the integration system."""
        try:
            logger.info("Initializing LiveKit Voice AI Integration")
            
            # Register event handlers with LiveKit integration
            for event_type, handlers in self.event_handlers.items():
                for handler in handlers:
                    self.livekit_integration.add_event_handler(event_type, handler)
            
            # Initialize monitoring integration if available
            if self.system_monitor:
                await self._initialize_monitoring_integration()
            
            self.status = IntegrationStatus.ACTIVE
            logger.info("LiveKit Voice AI Integration initialized successfully")
            
        except Exception as e:
            self.status = IntegrationStatus.FAILED
            logger.error(f"Failed to initialize LiveKit Voice AI Integration: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the integration system."""
        try:
            logger.info("Shutting down LiveKit Voice AI Integration")
            self.status = IntegrationStatus.SHUTDOWN
            
            # Clean up active integrations
            for call_id in list(self.active_integrations.keys()):
                await self._cleanup_call_integration(call_id)
            
            logger.info("LiveKit Voice AI Integration shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during integration shutdown: {e}")
    
    # Event Handler Integration Methods
    
    async def _handle_room_started_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle room started event with Voice AI integration."""
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return  # Not a Voice AI call
            
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Create integration data
            integration_data = {
                "call_id": call_id,
                "room_name": room_name,
                "room_sid": room_data.get('sid'),
                "started_at": datetime.now(UTC).isoformat(),
                "participants": {},
                "audio_tracks": {},
                "stt_sessions": {},
                "tts_active": False
            }
            
            self.active_integrations[call_id] = integration_data
            
            # Create call context for orchestrator
            call_context = CallContext(
                call_id=call_id,
                caller_number=event_data.get('metadata', {}).get('caller_number', 'unknown'),
                start_time=datetime.now(UTC),
                livekit_room=room_name,
                metadata={
                    "room_sid": room_data.get('sid'),
                    "integration_active": True,
                    "voice_ai_enabled": True
                }
            )
            
            # Notify orchestrator about room creation
            await self.orchestrator.handle_livekit_room_created(call_context)
            
            # Update metrics
            self.metrics.room_creations += 1
            self.metrics_collector.increment_counter(
                "livekit_voice_ai_rooms_started_total",
                labels={"call_id": call_id}
            )
            
            logger.info(
                f"Voice AI integration started for room {room_name}",
                extra={"call_id": call_id, "room_name": room_name}
            )
            
        except Exception as e:
            await self._handle_integration_error("room_started", event_data, e)
    
    async def _handle_participant_joined_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle participant joined event with Voice AI integration."""
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            room_name = room.get('name')
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return
            
            call_id = room_name.replace('voice-ai-call-', '')
            participant_identity = participant.get('identity')
            participant_sid = participant.get('sid')
            
            # Update integration data
            if call_id in self.active_integrations:
                self.active_integrations[call_id]["participants"][participant_identity] = {
                    "sid": participant_sid,
                    "joined_at": datetime.now(UTC).isoformat(),
                    "identity": participant_identity
                }
            
            # Get call context and notify orchestrator
            call_context = await self._get_call_context(call_id)
            if call_context:
                await self.orchestrator.handle_participant_joined(
                    call_context, participant_identity, participant_sid
                )
            
            logger.info(
                f"Participant {participant_identity} joined Voice AI call {call_id}",
                extra={"call_id": call_id, "participant_identity": participant_identity}
            )
            
        except Exception as e:
            await self._handle_integration_error("participant_joined", event_data, e)
    
    async def _handle_track_published_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle track published event with STT/TTS pipeline integration."""
        try:
            track = event_data.get('track', {})
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            room_name = room.get('name')
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return
            
            call_id = room_name.replace('voice-ai-call-', '')
            track_sid = track.get('sid')
            track_type = track.get('type')
            track_source = track.get('source')
            participant_identity = participant.get('identity')
            
            # Only process audio tracks from microphone
            if track_type != 'audio' or track_source != 'microphone':
                return
            
            # Update integration data
            if call_id in self.active_integrations:
                self.active_integrations[call_id]["audio_tracks"][track_sid] = {
                    "participant_identity": participant_identity,
                    "track_type": track_type,
                    "track_source": track_source,
                    "published_at": datetime.now(UTC).isoformat(),
                    "stt_active": False
                }
            
            # Get call context and start audio processing
            call_context = await self._get_call_context(call_id)
            if call_context:
                await self.orchestrator.start_audio_processing(
                    call_context, track_sid, participant_identity
                )
                
                # Mark STT as active
                if call_id in self.active_integrations:
                    self.active_integrations[call_id]["audio_tracks"][track_sid]["stt_active"] = True
                    self.active_integrations[call_id]["stt_sessions"][track_sid] = {
                        "started_at": datetime.now(UTC).isoformat(),
                        "participant_identity": participant_identity
                    }
            
            # Update metrics
            self.metrics.audio_tracks_processed += 1
            self.metrics.stt_sessions_started += 1
            
            self.metrics_collector.increment_counter(
                "livekit_voice_ai_audio_tracks_processed_total",
                labels={"call_id": call_id, "participant": participant_identity}
            )
            
            logger.info(
                f"STT pipeline started for audio track {track_sid} in Voice AI call {call_id}",
                extra={
                    "call_id": call_id,
                    "track_sid": track_sid,
                    "participant_identity": participant_identity
                }
            )
            
        except Exception as e:
            await self._handle_integration_error("track_published", event_data, e)
    
    async def _handle_room_finished_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle room finished event with Voice AI integration cleanup."""
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return
            
            call_id = room_name.replace('voice-ai-call-', '')
            
            # Get integration data before cleanup
            integration_data = self.active_integrations.get(call_id, {})
            
            # Update metrics based on integration success
            if integration_data:
                if integration_data.get("stt_sessions"):
                    self.metrics.successful_calls += 1
                else:
                    self.metrics.failed_calls += 1
            
            # Clean up integration
            await self._cleanup_call_integration(call_id)
            
            logger.info(
                f"Voice AI integration completed for call {call_id}",
                extra={"call_id": call_id, "room_name": room_name}
            )
            
        except Exception as e:
            await self._handle_integration_error("room_finished", event_data, e)
    
    async def _handle_participant_left_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle participant left event with Voice AI integration."""
        try:
            participant = event_data.get('participant', {})
            room = event_data.get('room', {})
            
            room_name = room.get('name')
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return
            
            call_id = room_name.replace('voice-ai-call-', '')
            participant_identity = participant.get('identity')
            
            # Update integration data
            if call_id in self.active_integrations:
                participants = self.active_integrations[call_id].get("participants", {})
                if participant_identity in participants:
                    participants[participant_identity]["left_at"] = datetime.now(UTC).isoformat()
            
            logger.info(
                f"Participant {participant_identity} left Voice AI call {call_id}",
                extra={"call_id": call_id, "participant_identity": participant_identity}
            )
            
        except Exception as e:
            await self._handle_integration_error("participant_left", event_data, e)
    
    async def _handle_track_unpublished_integration(self, event_data: Dict[str, Any]) -> None:
        """Handle track unpublished event with Voice AI integration."""
        try:
            track = event_data.get('track', {})
            room = event_data.get('room', {})
            
            room_name = room.get('name')
            if not room_name or not room_name.startswith('voice-ai-call-'):
                return
            
            call_id = room_name.replace('voice-ai-call-', '')
            track_sid = track.get('sid')
            
            # Update integration data
            if call_id in self.active_integrations:
                audio_tracks = self.active_integrations[call_id].get("audio_tracks", {})
                if track_sid in audio_tracks:
                    audio_tracks[track_sid]["unpublished_at"] = datetime.now(UTC).isoformat()
                    audio_tracks[track_sid]["stt_active"] = False
                
                # Remove STT session
                stt_sessions = self.active_integrations[call_id].get("stt_sessions", {})
                if track_sid in stt_sessions:
                    stt_sessions[track_sid]["ended_at"] = datetime.now(UTC).isoformat()
            
            logger.info(
                f"Audio track {track_sid} unpublished in Voice AI call {call_id}",
                extra={"call_id": call_id, "track_sid": track_sid}
            )
            
        except Exception as e:
            await self._handle_integration_error("track_unpublished", event_data, e)
    
    # Helper Methods
    
    async def _get_call_context(self, call_id: str) -> Optional[CallContext]:
        """Get call context for a call ID."""
        try:
            # Try to get from orchestrator's active calls
            if hasattr(self.orchestrator, 'active_calls'):
                return self.orchestrator.active_calls.get(call_id)
            
            # Create minimal call context from integration data
            integration_data = self.active_integrations.get(call_id)
            if integration_data:
                return CallContext(
                    call_id=call_id,
                    caller_number="unknown",
                    start_time=datetime.now(UTC),
                    livekit_room=integration_data.get("room_name", f"voice-ai-call-{call_id}"),
                    metadata={"integration_active": True}
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting call context for {call_id}: {e}")
            return None
    
    async def _cleanup_call_integration(self, call_id: str) -> None:
        """Clean up integration data for a call."""
        try:
            integration_data = self.active_integrations.pop(call_id, None)
            if integration_data:
                logger.debug(f"Cleaned up integration data for call {call_id}")
                
                # Update final metrics
                self.metrics_collector.set_gauge(
                    "livekit_voice_ai_active_integrations_current",
                    len(self.active_integrations)
                )
            
        except Exception as e:
            logger.error(f"Error cleaning up integration for call {call_id}: {e}")
    
    async def _handle_integration_error(
        self, 
        event_type: str, 
        event_data: Dict[str, Any], 
        error: Exception
    ) -> None:
        """Handle integration errors with fallback mechanisms."""
        try:
            self.metrics.integration_errors += 1
            
            error_info = {
                "event_type": event_type,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "event_id": event_data.get('event_id', 'unknown'),
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            logger.error(
                f"Integration error in {event_type}: {error}",
                extra=error_info
            )
            
            # Update error metrics
            self.metrics_collector.increment_counter(
                "livekit_voice_ai_integration_errors_total",
                labels={
                    "event_type": event_type,
                    "error_type": type(error).__name__
                }
            )
            
            # Execute error handlers
            for handler in self.error_handlers:
                try:
                    await handler(error_info)
                except Exception as handler_error:
                    logger.error(f"Error in integration error handler: {handler_error}")
            
            # Apply fallback mechanisms if enabled
            if self.fallback_enabled:
                await self._apply_fallback_mechanism(event_type, event_data, error)
            
        except Exception as e:
            logger.error(f"Error handling integration error: {e}")
    
    async def _apply_fallback_mechanism(
        self, 
        event_type: str, 
        event_data: Dict[str, Any], 
        original_error: Exception
    ) -> None:
        """Apply fallback mechanisms for integration errors."""
        try:
            logger.info(f"Applying fallback mechanism for {event_type} error")
            
            # Implement specific fallback strategies based on event type
            if event_type == "track_published":
                # Fallback: Try to restart audio processing after delay
                await asyncio.sleep(1)
                await self._retry_track_processing(event_data)
            
            elif event_type == "room_started":
                # Fallback: Ensure room is properly tracked
                await self._ensure_room_tracking(event_data)
            
            # Update fallback metrics
            self.metrics_collector.increment_counter(
                "livekit_voice_ai_fallback_applied_total",
                labels={"event_type": event_type}
            )
            
        except Exception as e:
            logger.error(f"Error applying fallback mechanism: {e}")
    
    async def _retry_track_processing(self, event_data: Dict[str, Any]) -> None:
        """Retry track processing as fallback."""
        try:
            # Disable fallback to prevent infinite loop
            original_fallback = self.fallback_enabled
            self.fallback_enabled = False
            
            # Re-attempt track processing with simplified approach
            await self._handle_track_published_integration(event_data)
            logger.info("Successfully retried track processing")
            
            # Restore fallback setting
            self.fallback_enabled = original_fallback
            
        except Exception as e:
            logger.error(f"Fallback track processing also failed: {e}")
            # Restore fallback setting even on error
            self.fallback_enabled = original_fallback
    
    async def _ensure_room_tracking(self, event_data: Dict[str, Any]) -> None:
        """Ensure room is properly tracked as fallback."""
        try:
            room_data = event_data.get('room', {})
            room_name = room_data.get('name')
            
            if room_name and room_name.startswith('voice-ai-call-'):
                call_id = room_name.replace('voice-ai-call-', '')
                
                # Ensure integration data exists
                if call_id not in self.active_integrations:
                    self.active_integrations[call_id] = {
                        "call_id": call_id,
                        "room_name": room_name,
                        "started_at": datetime.now(UTC).isoformat(),
                        "fallback_created": True
                    }
                    logger.info(f"Created fallback integration tracking for call {call_id}")
            
        except Exception as e:
            logger.error(f"Error ensuring room tracking: {e}")
    
    async def _initialize_monitoring_integration(self) -> None:
        """Initialize monitoring system integration."""
        try:
            if self.system_monitor:
                # Add integration-specific health checks
                async def integration_health_check():
                    return {
                        "status": self.status.value,
                        "active_integrations": len(self.active_integrations),
                        "metrics": self.metrics.to_dict()
                    }
                
                # Register health check if monitor supports it
                if hasattr(self.system_monitor, 'add_health_check'):
                    self.system_monitor.add_health_check(
                        "voice_ai_integration", 
                        integration_health_check
                    )
            
            logger.info("Monitoring integration initialized")
            
        except Exception as e:
            logger.error(f"Error initializing monitoring integration: {e}")
    
    # Public API Methods
    
    def add_error_handler(self, handler: Callable) -> None:
        """Add an error handler for integration errors."""
        self.error_handlers.append(handler)
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get comprehensive integration status."""
        return {
            "status": self.status.value,
            "active_integrations": len(self.active_integrations),
            "metrics": self.metrics.to_dict(),
            "integration_details": {
                call_id: {
                    "room_name": data.get("room_name"),
                    "participants": len(data.get("participants", {})),
                    "audio_tracks": len(data.get("audio_tracks", {})),
                    "stt_sessions": len(data.get("stt_sessions", {})),
                    "started_at": data.get("started_at")
                }
                for call_id, data in self.active_integrations.items()
            }
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get integration metrics."""
        return self.metrics.to_dict()


# Global instance management
_integration_instance: Optional[LiveKitVoiceAIIntegration] = None


async def get_livekit_voice_ai_integration(
    orchestrator: CallOrchestrator,
    livekit_integration: LiveKitSIPIntegration,
    api_client: LiveKitAPIClient,
    auth_manager: LiveKitAuthManager,
    system_monitor: Optional[LiveKitSystemMonitor] = None
) -> LiveKitVoiceAIIntegration:
    """Get or create the global LiveKit Voice AI integration instance."""
    global _integration_instance
    
    if _integration_instance is None:
        _integration_instance = LiveKitVoiceAIIntegration(
            orchestrator=orchestrator,
            livekit_integration=livekit_integration,
            api_client=api_client,
            auth_manager=auth_manager,
            system_monitor=system_monitor
        )
        await _integration_instance.initialize()
    
    return _integration_instance


async def shutdown_livekit_voice_ai_integration() -> None:
    """Shutdown the global LiveKit Voice AI integration instance."""
    global _integration_instance
    
    if _integration_instance:
        await _integration_instance.shutdown()
        _integration_instance = None
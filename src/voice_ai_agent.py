"""
Voice AI Agent for LiveKit Room Integration

This module provides the Voice AI Agent implementation that integrates with LiveKit rooms
for real-time voice conversation processing. It handles audio streaming, STT/TTS processing,
and conversation management within LiveKit rooms.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from uuid import uuid4

from livekit import rtc

from src.orchestrator import CallOrchestrator, CallContext, CallStatus
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager
from src.config import get_settings
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Voice AI Agent status enumeration."""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PROCESSING = "processing"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class AudioStreamConfig:
    """Configuration for audio streaming."""
    sample_rate: int = 16000
    channels: int = 1
    format: str = "pcm"
    buffer_size: int = 1024
    enable_echo_cancellation: bool = True
    enable_noise_suppression: bool = True
    enable_auto_gain_control: bool = True


@dataclass
class AgentMetrics:
    """Metrics for Voice AI Agent performance."""
    rooms_joined: int = 0
    audio_frames_processed: int = 0
    stt_requests: int = 0
    llm_requests: int = 0
    tts_requests: int = 0
    connection_errors: int = 0
    processing_errors: int = 0
    total_processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rooms_joined": self.rooms_joined,
            "audio_frames_processed": self.audio_frames_processed,
            "stt_requests": self.stt_requests,
            "llm_requests": self.llm_requests,
            "tts_requests": self.tts_requests,
            "connection_errors": self.connection_errors,
            "processing_errors": self.processing_errors,
            "total_processing_time": self.total_processing_time
        }


class VoiceAIAgent:
    """
    Voice AI Agent for LiveKit room integration.
    
    This agent connects to LiveKit rooms and provides real-time voice AI capabilities
    including speech-to-text, language model processing, and text-to-speech.
    """
    
    def __init__(
        self,
        orchestrator: CallOrchestrator,
        api_client: LiveKitAPIClient,
        auth_manager: LiveKitAuthManager,
        audio_config: Optional[AudioStreamConfig] = None
    ):
        """
        Initialize Voice AI Agent.
        
        Args:
            orchestrator: Call orchestrator for processing
            api_client: LiveKit API client
            auth_manager: LiveKit authentication manager
            audio_config: Audio streaming configuration
        """
        self.orchestrator = orchestrator
        self.api_client = api_client
        self.auth_manager = auth_manager
        self.audio_config = audio_config or AudioStreamConfig()
        
        self.settings = get_settings()
        self.metrics_collector = get_metrics_collector()
        
        # Agent state
        self.status = AgentStatus.INITIALIZING
        self.agent_id = str(uuid4())
        self.current_room: Optional[rtc.Room] = None
        self.current_call_context: Optional[CallContext] = None
        
        # Audio processing
        self.audio_source: Optional[rtc.AudioSource] = None
        self.audio_track: Optional[rtc.LocalAudioTrack] = None
        self.audio_buffer: List[bytes] = []
        self.processing_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.metrics = AgentMetrics()
        
        # Event handlers
        self.room_event_handlers: Dict[str, List[Callable]] = {
            'participant_connected': [],
            'participant_disconnected': [],
            'track_subscribed': [],
            'track_unsubscribed': [],
            'data_received': []
        }
        
        logger.info(f"Voice AI Agent {self.agent_id} initialized")
    
    async def join_room(self, room_name: str, call_context: CallContext) -> bool:
        """
        Join a LiveKit room for voice AI processing.
        
        Args:
            room_name: Name of the room to join
            call_context: Call context for the session
            
        Returns:
            True if successfully joined, False otherwise
        """
        try:
            self.status = AgentStatus.CONNECTING
            self.current_call_context = call_context
            
            logger.info(f"Agent {self.agent_id} joining room {room_name}")
            
            # Create access token for the agent using enhanced auth manager
            token = self.auth_manager.create_participant_token(
                identity=f"voice-ai-agent-{self.agent_id}",
                room_name=room_name,
                name=f"Voice AI Agent {self.agent_id}",
                role="agent",
                auto_renew=True  # Enable auto-renewal for long-running agents
            )
            
            # Verify room exists using API client
            try:
                rooms = await self.api_client.list_rooms(names=[room_name])
                if not rooms:
                    logger.error(f"Room {room_name} does not exist")
                    return False
                
                room_info = rooms[0]
                logger.info(f"Joining existing room {room_name} with {len(room_info.participants)} participants")
            except Exception as e:
                logger.warning(f"Could not verify room existence: {e}")
            
            # Create room instance
            self.current_room = rtc.Room()
            
            # Set up event handlers
            self._setup_room_event_handlers()
            
            # Connect to room
            await self.current_room.connect(
                url=self.settings.livekit_url,
                token=token
            )
            
            # Set up audio processing
            await self._setup_audio_processing()
            
            self.status = AgentStatus.CONNECTED
            self.metrics.rooms_joined += 1
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "voice_ai_agent_rooms_joined_total",
                labels={"agent_id": self.agent_id}
            )
            
            logger.info(f"Agent {self.agent_id} successfully joined room {room_name}")
            return True
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.metrics.connection_errors += 1
            
            logger.error(f"Failed to join room {room_name}: {e}")
            self.metrics_collector.increment_counter(
                "voice_ai_agent_connection_errors_total",
                labels={"agent_id": self.agent_id, "error_type": type(e).__name__}
            )
            return False
    
    async def leave_room(self) -> None:
        """Leave the current LiveKit room."""
        try:
            self.status = AgentStatus.DISCONNECTING
            
            logger.info(f"Agent {self.agent_id} leaving room")
            
            # Stop audio processing
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            
            # Clean up audio resources
            if self.audio_track:
                await self.current_room.local_participant.unpublish_track(self.audio_track)
                self.audio_track = None
            
            if self.audio_source:
                self.audio_source = None
            
            # Disconnect from room
            if self.current_room:
                await self.current_room.disconnect()
                self.current_room = None
            
            self.status = AgentStatus.DISCONNECTED
            self.current_call_context = None
            
            logger.info(f"Agent {self.agent_id} successfully left room")
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"Error leaving room: {e}")
    
    def _setup_room_event_handlers(self) -> None:
        """Set up LiveKit room event handlers."""
        if not self.current_room:
            return
        
        @self.current_room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant connected: {participant.identity}")
            asyncio.create_task(self._handle_participant_connected(participant))
        
        @self.current_room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant disconnected: {participant.identity}")
            asyncio.create_task(self._handle_participant_disconnected(participant))
        
        @self.current_room.on("track_subscribed")
        def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(f"Track subscribed: {track.sid} from {participant.identity}")
            asyncio.create_task(self._handle_track_subscribed(track, publication, participant))
        
        @self.current_room.on("track_unsubscribed")
        def on_track_unsubscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(f"Track unsubscribed: {track.sid} from {participant.identity}")
            asyncio.create_task(self._handle_track_unsubscribed(track, publication, participant))
        
        @self.current_room.on("data_received")
        def on_data_received(data: bytes, participant: rtc.RemoteParticipant):
            logger.debug(f"Data received from {participant.identity}: {len(data)} bytes")
            asyncio.create_task(self._handle_data_received(data, participant))
    
    async def _setup_audio_processing(self) -> None:
        """Set up audio source and track for processing."""
        try:
            # Create audio source
            self.audio_source = rtc.AudioSource(
                sample_rate=self.audio_config.sample_rate,
                num_channels=self.audio_config.channels
            )
            
            # Create audio track
            self.audio_track = rtc.LocalAudioTrack.create_audio_track(
                "voice-ai-response",
                self.audio_source
            )
            
            # Publish audio track
            await self.current_room.local_participant.publish_track(
                self.audio_track,
                rtc.TrackPublishOptions(
                    name="voice-ai-response",
                    source=rtc.TrackSource.SOURCE_MICROPHONE
                )
            )
            
            # Start audio processing task
            self.processing_task = asyncio.create_task(self._audio_processing_loop())
            
            logger.info("Audio processing setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup audio processing: {e}")
            raise
    
    async def _audio_processing_loop(self) -> None:
        """Main audio processing loop."""
        while self.status in [AgentStatus.CONNECTED, AgentStatus.PROCESSING]:
            try:
                # Process audio buffer if available
                if self.audio_buffer:
                    await self._process_audio_buffer()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")
                self.metrics.processing_errors += 1
                await asyncio.sleep(0.1)  # Brief pause on error
    
    async def _process_audio_buffer(self) -> None:
        """Process accumulated audio data."""
        try:
            if not self.audio_buffer or not self.current_call_context:
                return
            
            self.status = AgentStatus.PROCESSING
            
            # Combine audio buffer
            audio_data = b''.join(self.audio_buffer)
            self.audio_buffer.clear()
            
            # Process through orchestrator
            if self.orchestrator and self.current_call_context:
                try:
                    # Integrate with orchestrator's audio processing pipeline
                    await self.orchestrator.process_audio_data(
                        self.current_call_context,
                        audio_data,
                        source="voice_ai_agent",
                        agent_id=self.agent_id
                    )
                    
                    self.metrics.audio_frames_processed += 1
                    self.metrics_collector.increment_counter(
                        "voice_ai_agent_audio_frames_processed_total",
                        labels={"agent_id": self.agent_id}
                    )
                    
                    logger.debug(f"Processed {len(audio_data)} bytes of audio data through orchestrator")
                    
                except Exception as e:
                    logger.error(f"Error processing audio through orchestrator: {e}")
                    self.metrics.processing_errors += 1
            else:
                # Fallback processing
                logger.debug(f"Processing {len(audio_data)} bytes of audio data (fallback)")
                self.metrics.audio_frames_processed += 1
            
            self.status = AgentStatus.CONNECTED
            
        except Exception as e:
            logger.error(f"Error processing audio buffer: {e}")
            self.metrics.processing_errors += 1
    
    async def _handle_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        """Handle participant connected event."""
        try:
            logger.info(f"Handling participant connected: {participant.identity}")
            
            # Execute registered handlers
            for handler in self.room_event_handlers['participant_connected']:
                try:
                    await handler(participant)
                except Exception as e:
                    logger.error(f"Error in participant connected handler: {e}")
            
        except Exception as e:
            logger.error(f"Error handling participant connected: {e}")
    
    async def _handle_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        """Handle participant disconnected event."""
        try:
            logger.info(f"Handling participant disconnected: {participant.identity}")
            
            # Execute registered handlers
            for handler in self.room_event_handlers['participant_disconnected']:
                try:
                    await handler(participant)
                except Exception as e:
                    logger.error(f"Error in participant disconnected handler: {e}")
            
        except Exception as e:
            logger.error(f"Error handling participant disconnected: {e}")
    
    async def _handle_track_subscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant) -> None:
        """Handle track subscribed event."""
        try:
            logger.info(f"Handling track subscribed: {track.sid} from {participant.identity}")
            
            # If it's an audio track, start processing
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                await self._start_audio_track_processing(track, participant)
            
            # Execute registered handlers
            for handler in self.room_event_handlers['track_subscribed']:
                try:
                    await handler(track, publication, participant)
                except Exception as e:
                    logger.error(f"Error in track subscribed handler: {e}")
            
        except Exception as e:
            logger.error(f"Error handling track subscribed: {e}")
    
    async def _handle_track_unsubscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant) -> None:
        """Handle track unsubscribed event."""
        try:
            logger.info(f"Handling track unsubscribed: {track.sid} from {participant.identity}")
            
            # Execute registered handlers
            for handler in self.room_event_handlers['track_unsubscribed']:
                try:
                    await handler(track, publication, participant)
                except Exception as e:
                    logger.error(f"Error in track unsubscribed handler: {e}")
            
        except Exception as e:
            logger.error(f"Error handling track unsubscribed: {e}")
    
    async def _handle_data_received(self, data: bytes, participant: rtc.RemoteParticipant) -> None:
        """Handle data received event."""
        try:
            logger.debug(f"Handling data received from {participant.identity}: {len(data)} bytes")
            
            # Execute registered handlers
            for handler in self.room_event_handlers['data_received']:
                try:
                    await handler(data, participant)
                except Exception as e:
                    logger.error(f"Error in data received handler: {e}")
            
        except Exception as e:
            logger.error(f"Error handling data received: {e}")
    
    async def _start_audio_track_processing(self, track: rtc.AudioTrack, participant: rtc.RemoteParticipant) -> None:
        """Start processing audio from a subscribed track."""
        try:
            logger.info(f"Starting audio processing for track {track.sid} from {participant.identity}")
            
            # Create audio frame receiver
            audio_stream = rtc.AudioStream(track)
            
            async def process_audio_frames():
                async for frame in audio_stream:
                    try:
                        # Add frame data to buffer for processing
                        self.audio_buffer.append(frame.data)
                        
                        # Limit buffer size to prevent memory issues
                        if len(self.audio_buffer) > 100:
                            self.audio_buffer.pop(0)
                        
                    except Exception as e:
                        logger.error(f"Error processing audio frame: {e}")
            
            # Start processing task
            asyncio.create_task(process_audio_frames())
            
        except Exception as e:
            logger.error(f"Error starting audio track processing: {e}")
    
    async def send_audio_response(self, audio_data: bytes) -> None:
        """Send audio response through the agent's audio track."""
        try:
            if not self.audio_source or not self.current_room:
                logger.warning("Cannot send audio response: no audio source or room")
                return
            
            # Create audio frame
            frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=self.audio_config.sample_rate,
                num_channels=self.audio_config.channels,
                samples_per_channel=len(audio_data) // (self.audio_config.channels * 2)  # 16-bit samples
            )
            
            # Send frame through audio source
            await self.audio_source.capture_frame(frame)
            
            logger.debug(f"Sent audio response: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"Error sending audio response: {e}")
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add event handler for room events."""
        if event_type in self.room_event_handlers:
            self.room_event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status and metrics."""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "current_room": self.current_room.name if self.current_room else None,
            "current_call": self.current_call_context.call_id if self.current_call_context else None,
            "metrics": self.metrics.to_dict(),
            "audio_config": {
                "sample_rate": self.audio_config.sample_rate,
                "channels": self.audio_config.channels,
                "format": self.audio_config.format
            }
        }


# Global agent registry for managing multiple agents
_agent_registry: Dict[str, VoiceAIAgent] = {}


async def create_voice_ai_agent(
    orchestrator: CallOrchestrator,
    api_client: LiveKitAPIClient,
    auth_manager: LiveKitAuthManager,
    audio_config: Optional[AudioStreamConfig] = None
) -> VoiceAIAgent:
    """
    Create a new Voice AI Agent instance.
    
    Args:
        orchestrator: Call orchestrator
        api_client: LiveKit API client
        auth_manager: LiveKit auth manager
        audio_config: Audio configuration
        
    Returns:
        VoiceAIAgent instance
    """
    agent = VoiceAIAgent(orchestrator, api_client, auth_manager, audio_config)
    _agent_registry[agent.agent_id] = agent
    return agent


async def get_agent(agent_id: str) -> Optional[VoiceAIAgent]:
    """Get agent by ID."""
    return _agent_registry.get(agent_id)


async def cleanup_agent(agent_id: str) -> None:
    """Clean up and remove agent."""
    agent = _agent_registry.pop(agent_id, None)
    if agent:
        await agent.leave_room()


async def get_all_agents() -> List[VoiceAIAgent]:
    """Get all active agents."""
    return list(_agent_registry.values())
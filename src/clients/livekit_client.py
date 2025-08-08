"""
LiveKit Client with Enhanced Connection Management

This module provides a robust LiveKit client with:
- Automatic retry logic with exponential backoff
- Comprehensive error handling
- Connection monitoring and health checks
- Proper authentication handling

Requirements addressed:
- 1.1: Successful authentication with LiveKit server
- 1.2: Room creation with proper naming
- 1.4: Retry logic and error handling for connection
- 1.5: Detailed error logging
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from uuid import uuid4

from livekit import api, rtc
from livekit.api import AccessToken, VideoGrants, CreateRoomRequest, ListRoomsRequest, DeleteRoomRequest

from src.config import get_settings
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class RetryPolicy(str, Enum):
    """Retry policy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Retry configuration."""
    enabled: bool = True
    max_attempts: int = 5
    initial_delay: float = 1.0  # seconds
    max_delay: float = 30.0     # seconds
    multiplier: float = 2.0
    jitter: bool = True
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL_BACKOFF


@dataclass
class ConnectionConfig:
    """Connection configuration."""
    timeout: float = 30.0       # seconds
    keep_alive: float = 25.0    # seconds
    reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 1.0  # seconds
    health_check_interval: float = 60.0  # seconds


@dataclass
class LiveKitRoom:
    """LiveKit room information."""
    name: str
    sid: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    participants: List[str] = None
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []


@dataclass
class RoomParticipant:
    """LiveKit room participant."""
    room: Optional[rtc.Room]
    identity: str
    room_name: str
    auto_subscribe: bool = True
    audio_track: Optional[rtc.LocalAudioTrack] = None
    audio_publication: Optional[rtc.LocalTrackPublication] = None
    audio_callback: Optional[Callable[[bytes, int], None]] = None
    audio_streams: Optional[Dict[str, rtc.AudioStream]] = None
    
    def __post_init__(self):
        if self.audio_streams is None:
            self.audio_streams = {}


class LiveKitConnectionError(Exception):
    """LiveKit connection error."""
    pass


class LiveKitAuthenticationError(LiveKitConnectionError):
    """LiveKit authentication error."""
    pass


class LiveKitTimeoutError(LiveKitConnectionError):
    """LiveKit timeout error."""
    pass


class LiveKitClient:
    """
    Enhanced LiveKit client with robust connection management.
    
    Features:
    - Automatic retry logic with configurable policies
    - Connection health monitoring
    - Comprehensive error handling
    - Authentication validation
    - Room management with proper cleanup
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        connection_config: Optional[ConnectionConfig] = None
    ):
        """
        Initialize LiveKit client.
        
        Args:
            url: LiveKit server URL
            api_key: LiveKit API key
            api_secret: LiveKit API secret
            retry_config: Retry configuration
            connection_config: Connection configuration
        """
        # Load settings if not provided
        settings = get_settings()
        
        self.url = url or settings.livekit_url
        self.api_key = api_key or settings.livekit_api_key
        self.api_secret = api_secret or settings.livekit_api_secret
        
        # Validate required parameters
        if not all([self.url, self.api_key, self.api_secret]):
            raise ValueError("LiveKit URL, API key, and API secret are required")
        
        # Configuration
        self.retry_config = retry_config or RetryConfig()
        self.connection_config = connection_config or ConnectionConfig()
        
        # Client state
        self.client: Optional[api.LiveKitAPI] = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.last_error: Optional[Exception] = None
        self.connection_attempts = 0
        self.last_health_check = None
        
        # Monitoring
        self.metrics_collector = get_metrics_collector()
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retry_attempts = 0
        
        logger.info(f"LiveKit client initialized for {self.url}")
    
    async def connect(self) -> bool:
        """
        Connect to LiveKit server with retry logic.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.connection_state == ConnectionState.CONNECTED:
            return True
        
        self.connection_state = ConnectionState.CONNECTING
        self.connection_attempts += 1
        
        logger.info(f"Connecting to LiveKit server: {self.url}")
        
        try:
            # Initialize client
            self.client = api.LiveKitAPI(
                url=self.url,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Test connection with authentication
            await self._test_connection()
            
            self.connection_state = ConnectionState.CONNECTED
            self.last_error = None
            
            # Start health monitoring
            if not self.health_check_task:
                self.health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info("Successfully connected to LiveKit server")
            self.metrics_collector.set_gauge("livekit_connection_status", 1)
            
            return True
            
        except Exception as e:
            self.connection_state = ConnectionState.FAILED
            self.last_error = e
            
            logger.error(f"Failed to connect to LiveKit server: {e}")
            self.metrics_collector.set_gauge("livekit_connection_status", 0)
            
            # Determine error type for better handling
            if "auth" in str(e).lower() or "unauthorized" in str(e).lower():
                raise LiveKitAuthenticationError(f"Authentication failed: {e}")
            elif "timeout" in str(e).lower():
                raise LiveKitTimeoutError(f"Connection timeout: {e}")
            else:
                raise LiveKitConnectionError(f"Connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from LiveKit server."""
        logger.info("Disconnecting from LiveKit server")
        
        # Stop health monitoring
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None
        
        # Reset client state
        self.client = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.metrics_collector.set_gauge("livekit_connection_status", 0)
        
        logger.info("Disconnected from LiveKit server")
    
    async def _test_connection(self) -> None:
        """Test connection by listing rooms."""
        if not self.client:
            raise LiveKitConnectionError("Client not initialized")
        
        try:
            # Test with a simple API call
            start_time = time.time()
            rooms_response = await self.client.room.list_rooms(ListRoomsRequest())
            response_time = time.time() - start_time
            
            logger.debug(f"Connection test successful: {len(rooms_response.rooms)} rooms found ({response_time:.2f}s)")
            
            # Update metrics
            self.metrics_collector.record_histogram("livekit_api_response_time", response_time)
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    async def _health_check_loop(self) -> None:
        """Health check monitoring loop."""
        while self.connection_state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self.connection_config.health_check_interval)
                
                if self.connection_state != ConnectionState.CONNECTED:
                    break
                
                # Perform health check
                await self._perform_health_check()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Health check failed: {e}")
                
                # Trigger reconnection if enabled
                if self.connection_config.reconnect:
                    asyncio.create_task(self._reconnect())
                
                await asyncio.sleep(self.connection_config.health_check_interval)
    
    async def _perform_health_check(self) -> None:
        """Perform health check."""
        try:
            start_time = time.time()
            await self._test_connection()
            response_time = time.time() - start_time
            
            self.last_health_check = datetime.now(UTC)
            
            logger.debug(f"Health check passed ({response_time:.2f}s)")
            self.metrics_collector.set_gauge("livekit_health_check_status", 1)
            
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self.metrics_collector.set_gauge("livekit_health_check_status", 0)
            raise
    
    async def _reconnect(self) -> None:
        """Reconnect to LiveKit server."""
        if self.connection_state == ConnectionState.RECONNECTING:
            return  # Already reconnecting
        
        self.connection_state = ConnectionState.RECONNECTING
        logger.info("Attempting to reconnect to LiveKit server")
        
        for attempt in range(self.connection_config.max_reconnect_attempts):
            try:
                await asyncio.sleep(self.connection_config.reconnect_delay * (attempt + 1))
                
                # Attempt reconnection
                await self.connect()
                
                logger.info(f"Reconnection successful after {attempt + 1} attempts")
                return
                
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                
                if attempt == self.connection_config.max_reconnect_attempts - 1:
                    logger.error("All reconnection attempts failed")
                    self.connection_state = ConnectionState.FAILED
                    break
    
    async def _execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute operation with retry logic.
        
        Args:
            operation: Operation to execute
            operation_name: Name of operation for logging
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Operation result
        """
        if not self.retry_config.enabled:
            return await operation(*args, **kwargs)
        
        last_exception = None
        delay = self.retry_config.initial_delay
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                self.total_requests += 1
                
                # Ensure we're connected
                if self.connection_state != ConnectionState.CONNECTED:
                    await self.connect()
                
                # Execute operation
                start_time = time.time()
                result = await operation(*args, **kwargs)
                response_time = time.time() - start_time
                
                # Update metrics
                self.successful_requests += 1
                self.metrics_collector.record_histogram(
                    "livekit_operation_duration",
                    response_time,
                    labels={"operation": operation_name}
                )
                
                logger.debug(f"Operation {operation_name} succeeded on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                
                self.failed_requests += 1
                self.retry_attempts += 1
                
                logger.warning(f"Operation {operation_name} failed on attempt {attempt + 1}: {e}")
                
                # Update metrics
                self.metrics_collector.increment_counter(
                    "livekit_operation_failures",
                    labels={"operation": operation_name, "attempt": str(attempt + 1)}
                )
                
                # Check if we should retry
                if attempt == self.retry_config.max_attempts - 1:
                    break
                
                # Calculate delay for next attempt
                if self.retry_config.policy == RetryPolicy.EXPONENTIAL_BACKOFF:
                    delay = min(delay * self.retry_config.multiplier, self.retry_config.max_delay)
                elif self.retry_config.policy == RetryPolicy.LINEAR_BACKOFF:
                    delay = min(self.retry_config.initial_delay * (attempt + 2), self.retry_config.max_delay)
                # FIXED_DELAY uses the same delay each time
                
                # Add jitter if enabled
                if self.retry_config.jitter:
                    import random
                    jitter = random.uniform(0.1, 0.3) * delay
                    delay += jitter
                
                logger.debug(f"Retrying {operation_name} in {delay:.2f} seconds")
                await asyncio.sleep(delay)
        
        # All attempts failed
        logger.error(f"Operation {operation_name} failed after {self.retry_config.max_attempts} attempts")
        self.metrics_collector.increment_counter(
            "livekit_operation_total_failures",
            labels={"operation": operation_name}
        )
        
        if last_exception:
            raise last_exception
        else:
            raise LiveKitConnectionError(f"Operation {operation_name} failed after {self.retry_config.max_attempts} attempts")
    
    async def join_room(
        self,
        room_name: str,
        participant_name: str,
        auto_subscribe: bool = True
    ) -> 'RoomParticipant':
        """
        Join a LiveKit room as a participant.
        
        Args:
            room_name: Name of room to join
            participant_name: Name of participant
            auto_subscribe: Whether to auto-subscribe to tracks
            
        Returns:
            RoomParticipant object
        """
        logger.info(f"Joining LiveKit room: {room_name} as {participant_name}")
        
        async def _join_room():
            # Note: We don't check self.client here as we're creating a direct room connection
            
            # Generate access token for participant
            token = await self.generate_access_token(participant_name, room_name)
            
            # Create room connection
            room = rtc.Room()
            
            # Connect to room
            await room.connect(self.url, token)
            
            return RoomParticipant(
                room=room,
                identity=participant_name,
                room_name=room_name,
                auto_subscribe=auto_subscribe
            )
        
        try:
            participant = await self._execute_with_retry(_join_room, "join_room")
            
            logger.info(f"Successfully joined room: {room_name} as {participant_name}")
            self.metrics_collector.increment_counter("livekit_room_joins")
            
            return participant
            
        except Exception as e:
            logger.error(f"Failed to join room {room_name} as {participant_name}: {e}")
            self.metrics_collector.increment_counter("livekit_room_join_failures")
            raise
    
    async def publish_audio_track(
        self,
        participant: 'RoomParticipant',
        audio_source: Optional[rtc.AudioSource] = None
    ) -> rtc.LocalAudioTrack:
        """
        Publish an audio track for a participant.
        
        Args:
            participant: Room participant
            audio_source: Audio source (optional, creates default if None)
            
        Returns:
            LocalAudioTrack object
        """
        logger.info(f"Publishing audio track for participant: {participant.identity}")
        
        async def _publish_audio_track():
            if not participant.room:
                raise LiveKitConnectionError("Participant not connected to room")
            
            # Create audio source if not provided
            nonlocal audio_source
            if audio_source is None:
                audio_source = rtc.AudioSource(
                    sample_rate=48000,
                    num_channels=1
                )
            
            # Create local audio track
            track = rtc.LocalAudioTrack.create_audio_track(
                "voice-ai-audio",
                audio_source
            )
            
            # Publish track
            publication = await participant.room.local_participant.publish_track(
                track,
                rtc.TrackPublishOptions(
                    source=rtc.TrackSource.SOURCE_MICROPHONE
                )
            )
            
            # Store track reference in participant
            participant.audio_track = track
            participant.audio_publication = publication
            
            return track
        
        try:
            track = await self._execute_with_retry(_publish_audio_track, "publish_audio_track")
            
            logger.info(f"Successfully published audio track for: {participant.identity}")
            self.metrics_collector.increment_counter("livekit_audio_tracks_published")
            
            return track
            
        except Exception as e:
            logger.error(f"Failed to publish audio track for {participant.identity}: {e}")
            self.metrics_collector.increment_counter("livekit_audio_track_publish_failures")
            raise
    
    async def subscribe_to_audio(
        self,
        participant: 'RoomParticipant',
        callback: Callable[[bytes, int], None]
    ) -> None:
        """
        Subscribe to audio tracks from other participants.
        
        Args:
            participant: Room participant
            callback: Callback function for audio data (data, sample_rate)
        """
        logger.info(f"Setting up audio subscription for participant: {participant.identity}")
        
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            remote_participant: rtc.RemoteParticipant
        ):
            """Handle track subscription."""
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Subscribed to audio track from {remote_participant.identity}")
                
                # Create audio stream
                audio_stream = rtc.AudioStream(track)
                
                # Set up frame callback
                async def on_audio_frame(frame: rtc.AudioFrame):
                    """Handle audio frame."""
                    try:
                        # Convert frame to bytes
                        audio_data = frame.data.tobytes()
                        sample_rate = frame.sample_rate
                        
                        # Call user callback
                        if callback:
                            callback(audio_data, sample_rate)
                            
                    except Exception as e:
                        logger.error(f"Error processing audio frame: {e}")
                
                # Start receiving frames
                audio_stream.on("frame_received", on_audio_frame)
                
                # Store stream reference
                if not hasattr(participant, 'audio_streams'):
                    participant.audio_streams = {}
                participant.audio_streams[remote_participant.identity] = audio_stream
        
        def on_track_unsubscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            remote_participant: rtc.RemoteParticipant
        ):
            """Handle track unsubscription."""
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Unsubscribed from audio track from {remote_participant.identity}")
                
                # Clean up stream reference
                if hasattr(participant, 'audio_streams'):
                    participant.audio_streams.pop(remote_participant.identity, None)
        
        # Set up event handlers
        participant.room.on("track_subscribed", on_track_subscribed)
        participant.room.on("track_unsubscribed", on_track_unsubscribed)
        
        # Store callback reference
        participant.audio_callback = callback
        
        logger.info(f"Audio subscription set up for participant: {participant.identity}")
        self.metrics_collector.increment_counter("livekit_audio_subscriptions")
    
    async def leave_room(self, participant: 'RoomParticipant') -> None:
        """
        Leave a LiveKit room.
        
        Args:
            participant: Room participant to disconnect
        """
        logger.info(f"Leaving room: {participant.room_name} as {participant.identity}")
        
        try:
            if participant.room:
                # Unpublish tracks
                if hasattr(participant, 'audio_publication') and participant.audio_publication:
                    await participant.room.local_participant.unpublish_track(
                        participant.audio_publication.sid
                    )
                
                # Disconnect from room
                await participant.room.disconnect()
                
                # Clean up references
                participant.room = None
                participant.audio_track = None
                participant.audio_publication = None
                
                if hasattr(participant, 'audio_streams'):
                    participant.audio_streams.clear()
            
            logger.info(f"Successfully left room: {participant.room_name}")
            self.metrics_collector.increment_counter("livekit_room_leaves")
            
        except Exception as e:
            logger.error(f"Error leaving room {participant.room_name}: {e}")
            self.metrics_collector.increment_counter("livekit_room_leave_failures")
            raise
    
    async def send_audio_data(
        self,
        participant: 'RoomParticipant',
        audio_data: bytes,
        sample_rate: int = 48000,
        num_channels: int = 1
    ) -> None:
        """
        Send audio data through the participant's audio track.
        
        Args:
            participant: Room participant
            audio_data: Raw audio data
            sample_rate: Audio sample rate
            num_channels: Number of audio channels
        """
        if not participant.audio_track:
            raise LiveKitConnectionError("No audio track available for participant")
        
        try:
            # Create audio frame
            frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=sample_rate,
                num_channels=num_channels,
                samples_per_channel=len(audio_data) // (num_channels * 2)  # 16-bit samples
            )
            
            # Send frame through audio source
            if hasattr(participant.audio_track, 'source'):
                await participant.audio_track.source.capture_frame(frame)
            
            self.metrics_collector.increment_counter("livekit_audio_frames_sent")
            
        except Exception as e:
            logger.error(f"Failed to send audio data: {e}")
            self.metrics_collector.increment_counter("livekit_audio_send_failures")
            raise

    async def create_room(
        self,
        name: Optional[str] = None,
        empty_timeout: int = 300,
        max_participants: int = 2,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LiveKitRoom:
        """
        Create a LiveKit room with retry logic.
        
        Args:
            name: Room name (auto-generated if not provided)
            empty_timeout: Room timeout in seconds
            max_participants: Maximum number of participants
            metadata: Room metadata
            
        Returns:
            LiveKitRoom object
        """
        if not name:
            name = f"voice-ai-call-{uuid4()}"
        
        logger.info(f"Creating LiveKit room: {name}")
        
        async def _create_room():
            if not self.client:
                raise LiveKitConnectionError("Client not connected")
            
            room_request = CreateRoomRequest(
                name=name,
                empty_timeout=empty_timeout,
                max_participants=max_participants,
                metadata=json.dumps(metadata) if metadata else None
            )
            
            room = await self.client.room.create_room(room_request)
            
            return LiveKitRoom(
                name=room.name,
                sid=room.sid,
                created_at=datetime.now(UTC),
                metadata=metadata,
                participants=[]
            )
        
        try:
            room = await self._execute_with_retry(_create_room, "create_room")
            
            logger.info(f"Successfully created room: {room.name} (SID: {room.sid})")
            self.metrics_collector.increment_counter("livekit_rooms_created")
            
            return room
            
        except Exception as e:
            logger.error(f"Failed to create room {name}: {e}")
            self.metrics_collector.increment_counter("livekit_room_creation_failures")
            raise
    
    async def delete_room(self, room_name: str) -> bool:
        """
        Delete a LiveKit room with retry logic.
        
        Args:
            room_name: Name of room to delete
            
        Returns:
            True if deletion successful
        """
        logger.info(f"Deleting LiveKit room: {room_name}")
        
        async def _delete_room():
            if not self.client:
                raise LiveKitConnectionError("Client not connected")
            
            await self.client.room.delete_room(DeleteRoomRequest(room=room_name))
            return True
        
        try:
            result = await self._execute_with_retry(_delete_room, "delete_room")
            
            logger.info(f"Successfully deleted room: {room_name}")
            self.metrics_collector.increment_counter("livekit_rooms_deleted")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete room {room_name}: {e}")
            self.metrics_collector.increment_counter("livekit_room_deletion_failures")
            raise
    
    async def list_rooms(self) -> List[LiveKitRoom]:
        """
        List all LiveKit rooms with retry logic.
        
        Returns:
            List of LiveKitRoom objects
        """
        logger.debug("Listing LiveKit rooms")
        
        async def _list_rooms():
            if not self.client:
                raise LiveKitConnectionError("Client not connected")
            
            rooms_response = await self.client.room.list_rooms(ListRoomsRequest())
            
            rooms = []
            for room in rooms_response.rooms:
                metadata = None
                if room.metadata:
                    try:
                        metadata = json.loads(room.metadata)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON metadata in room {room.name}")
                
                rooms.append(LiveKitRoom(
                    name=room.name,
                    sid=room.sid,
                    created_at=datetime.fromtimestamp(room.creation_time, UTC),
                    metadata=metadata,
                    participants=[p.identity for p in room.participants]
                ))
            
            return rooms
        
        try:
            rooms = await self._execute_with_retry(_list_rooms, "list_rooms")
            
            logger.debug(f"Found {len(rooms)} rooms")
            self.metrics_collector.set_gauge("livekit_rooms_total", len(rooms))
            
            return rooms
            
        except Exception as e:
            logger.error(f"Failed to list rooms: {e}")
            self.metrics_collector.increment_counter("livekit_list_rooms_failures")
            raise
    
    async def generate_access_token(
        self,
        identity: str,
        room_name: str,
        grants: Optional[VideoGrants] = None
    ) -> str:
        """
        Generate access token for participant.
        
        Args:
            identity: Participant identity
            room_name: Room name
            grants: Video grants (optional)
            
        Returns:
            JWT access token
        """
        logger.debug(f"Generating access token for {identity} in room {room_name}")
        
        try:
            token = AccessToken(
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            token.with_identity(identity)
            
            if grants:
                token.with_grants(grants)
            else:
                # Default grants for voice calls
                token.with_grants(VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True
                ))
            
            jwt_token = token.to_jwt()
            
            logger.debug(f"Generated access token for {identity}")
            self.metrics_collector.increment_counter("livekit_tokens_generated")
            
            return jwt_token
            
        except Exception as e:
            logger.error(f"Failed to generate access token for {identity}: {e}")
            self.metrics_collector.increment_counter("livekit_token_generation_failures")
            raise
    
    async def get_room_info(self, room_name: str) -> Optional[LiveKitRoom]:
        """
        Get information about a specific room.
        
        Args:
            room_name: Room name
            
        Returns:
            LiveKitRoom object or None if not found
        """
        try:
            rooms = await self.list_rooms()
            
            for room in rooms:
                if room.name == room_name:
                    return room
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get room info for {room_name}: {e}")
            raise
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status and statistics.
        
        Returns:
            Connection status dictionary
        """
        return {
            "state": self.connection_state.value,
            "url": self.url,
            "api_key_prefix": f"{self.api_key[:8]}***" if self.api_key else None,
            "connection_attempts": self.connection_attempts,
            "last_error": str(self.last_error) if self.last_error else None,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "statistics": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "retry_attempts": self.retry_attempts,
                "success_rate": (
                    self.successful_requests / self.total_requests * 100
                    if self.total_requests > 0 else 0
                )
            },
            "configuration": {
                "retry_enabled": self.retry_config.enabled,
                "max_retry_attempts": self.retry_config.max_attempts,
                "reconnect_enabled": self.connection_config.reconnect,
                "health_check_interval": self.connection_config.health_check_interval
            }
        }
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the LiveKit connection.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._perform_health_check()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection and return detailed results.
        
        Returns:
            Test results dictionary
        """
        test_results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tests": {},
            "overall_status": "UNKNOWN"
        }
        
        # Test basic connectivity
        try:
            start_time = time.time()
            await self.connect()
            connect_time = time.time() - start_time
            
            test_results["tests"]["connection"] = {
                "status": "PASS",
                "response_time": connect_time,
                "message": "Connection successful"
            }
            
        except Exception as e:
            test_results["tests"]["connection"] = {
                "status": "FAIL",
                "error": str(e),
                "message": "Connection failed"
            }
        
        # Test room operations
        if self.connection_state == ConnectionState.CONNECTED:
            try:
                # Test room creation
                test_room_name = f"test-room-{int(time.time())}"
                
                start_time = time.time()
                room = await self.create_room(
                    name=test_room_name,
                    empty_timeout=60,
                    metadata={"test": True}
                )
                create_time = time.time() - start_time
                
                # Test room listing
                start_time = time.time()
                rooms = await self.list_rooms()
                list_time = time.time() - start_time
                
                room_found = any(r.name == test_room_name for r in rooms)
                
                # Test room deletion
                start_time = time.time()
                await self.delete_room(test_room_name)
                delete_time = time.time() - start_time
                
                test_results["tests"]["room_operations"] = {
                    "status": "PASS",
                    "create_time": create_time,
                    "list_time": list_time,
                    "delete_time": delete_time,
                    "room_found": room_found,
                    "message": "Room operations successful"
                }
                
            except Exception as e:
                test_results["tests"]["room_operations"] = {
                    "status": "FAIL",
                    "error": str(e),
                    "message": "Room operations failed"
                }
        
        # Test token generation
        try:
            start_time = time.time()
            token = await self.generate_access_token("test-user", "test-room")
            token_time = time.time() - start_time
            
            test_results["tests"]["token_generation"] = {
                "status": "PASS",
                "response_time": token_time,
                "token_length": len(token),
                "message": "Token generation successful"
            }
            
        except Exception as e:
            test_results["tests"]["token_generation"] = {
                "status": "FAIL",
                "error": str(e),
                "message": "Token generation failed"
            }
        
        # Determine overall status
        failed_tests = [t for t in test_results["tests"].values() if t["status"] == "FAIL"]
        if not failed_tests:
            test_results["overall_status"] = "HEALTHY"
        else:
            test_results["overall_status"] = "UNHEALTHY"
        
        return test_results


# Global client instance
_livekit_client: Optional[LiveKitClient] = None


async def get_livekit_client() -> LiveKitClient:
    """Get the global LiveKit client instance."""
    global _livekit_client
    
    if _livekit_client is None:
        _livekit_client = LiveKitClient()
        await _livekit_client.connect()
    
    return _livekit_client


async def shutdown_livekit_client() -> None:
    """Shutdown the global LiveKit client instance."""
    global _livekit_client
    
    if _livekit_client:
        await _livekit_client.disconnect()
        _livekit_client = None
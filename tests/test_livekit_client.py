#!/usr/bin/env python3
"""
Tests for LiveKit Client

This module tests the enhanced LiveKit client with retry logic and error handling.
"""

import asyncio
import pytest
import sys
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clients.livekit_client import (
    LiveKitClient,
    ConnectionState,
    RetryConfig,
    ConnectionConfig,
    LiveKitConnectionError,
    LiveKitAuthenticationError,
    LiveKitTimeoutError,
    RetryPolicy
)


class TestLiveKitClient:
    """Test cases for LiveKit client."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings fixture."""
        with patch('clients.livekit_client.get_settings') as mock:
            mock.return_value = MagicMock(
                livekit_url="wss://test.livekit.cloud",
                livekit_api_key="API_test_key",
                livekit_api_secret="test_secret"
            )
            yield mock.return_value
    
    @pytest.fixture
    def mock_metrics(self):
        """Mock metrics collector fixture."""
        with patch('clients.livekit_client.get_metrics_collector') as mock:
            mock.return_value = MagicMock()
            yield mock.return_value
    
    @pytest.fixture
    def client(self, mock_settings, mock_metrics):
        """LiveKit client fixture."""
        return LiveKitClient(
            url="wss://test.livekit.cloud",
            api_key="API_test_key",
            api_secret="test_secret"
        )
    
    def test_client_initialization(self, client):
        """Test client initialization."""
        assert client.url == "wss://test.livekit.cloud"
        assert client.api_key == "API_test_key"
        assert client.api_secret == "test_secret"
        assert client.connection_state == ConnectionState.DISCONNECTED
        assert client.retry_config.enabled is True
        assert client.connection_config.reconnect is True
    
    def test_client_initialization_missing_params(self):
        """Test client initialization with missing parameters."""
        with patch('clients.livekit_client.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                livekit_url=None,
                livekit_api_key=None,
                livekit_api_secret=None
            )
            
            with pytest.raises(ValueError, match="LiveKit URL, API key, and API secret are required"):
                LiveKitClient()
    
    @pytest.mark.asyncio
    async def test_successful_connection(self, client):
        """Test successful connection."""
        with patch('livekit.api.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_api.return_value = mock_client
            
            # Mock successful room listing
            mock_client.room.list_rooms.return_value = MagicMock(rooms=[])
            
            result = await client.connect()
            
            assert result is True
            assert client.connection_state == ConnectionState.CONNECTED
            assert client.client is not None
            mock_api.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_authentication_error(self, client):
        """Test connection with authentication error."""
        with patch('livekit.api.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_api.return_value = mock_client
            
            # Mock authentication failure
            mock_client.room.list_rooms.side_effect = Exception("auth check failed")
            
            with pytest.raises(LiveKitAuthenticationError):
                await client.connect()
            
            assert client.connection_state == ConnectionState.FAILED
    
    @pytest.mark.asyncio
    async def test_connection_timeout_error(self, client):
        """Test connection with timeout error."""
        with patch('livekit.api.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_api.return_value = mock_client
            
            # Mock timeout
            mock_client.room.list_rooms.side_effect = Exception("timeout")
            
            with pytest.raises(LiveKitTimeoutError):
                await client.connect()
            
            assert client.connection_state == ConnectionState.FAILED
    
    @pytest.mark.asyncio
    async def test_retry_logic_exponential_backoff(self, client):
        """Test retry logic with exponential backoff."""
        client.retry_config = RetryConfig(
            enabled=True,
            max_attempts=3,
            initial_delay=0.1,
            multiplier=2.0,
            policy=RetryPolicy.EXPONENTIAL_BACKOFF
        )
        
        # Mock the connection state to avoid real connection attempts
        client.connection_state = ConnectionState.CONNECTED
        
        # Mock operation that fails twice then succeeds
        mock_operation = AsyncMock()
        mock_operation.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            "Success"
        ]
        
        with patch('asyncio.sleep') as mock_sleep:
            with patch.object(client, 'connect') as mock_connect:
                mock_connect.return_value = True
                
                result = await client._execute_with_retry(
                    mock_operation,
                    "test_operation"
                )
                
                assert result == "Success"
                assert mock_operation.call_count == 3
                assert mock_sleep.call_count == 2  # Two retries
    
    @pytest.mark.asyncio
    async def test_retry_logic_max_attempts_exceeded(self, client):
        """Test retry logic when max attempts exceeded."""
        client.retry_config = RetryConfig(
            enabled=True,
            max_attempts=2,
            initial_delay=0.1
        )
        
        # Mock the connection state to avoid real connection attempts
        client.connection_state = ConnectionState.CONNECTED
        
        # Mock operation that always fails
        mock_operation = AsyncMock()
        mock_operation.side_effect = Exception("Always fails")
        
        with patch('asyncio.sleep'):
            with patch.object(client, 'connect') as mock_connect:
                mock_connect.return_value = True
                
                with pytest.raises(Exception, match="Always fails"):
                    await client._execute_with_retry(
                        mock_operation,
                        "test_operation"
                    )
                
                assert mock_operation.call_count == 2
    
    @pytest.mark.asyncio
    async def test_create_room_success(self, client):
        """Test successful room creation."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Mock room creation response
        mock_room = MagicMock()
        mock_room.name = "test-room"
        mock_room.sid = "test-sid"
        client.client.room.create_room.return_value = mock_room
        
        room = await client.create_room(
            name="test-room",
            metadata={"test": True}
        )
        
        assert room.name == "test-room"
        assert room.sid == "test-sid"
        assert room.metadata == {"test": True}
        client.client.room.create_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_room_auto_name(self, client):
        """Test room creation with auto-generated name."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Mock room creation response
        mock_room = MagicMock()
        mock_room.name = "voice-ai-call-12345"
        mock_room.sid = "test-sid"
        client.client.room.create_room.return_value = mock_room
        
        room = await client.create_room()
        
        assert room.name.startswith("voice-ai-call-")
        assert room.sid == "test-sid"
        client.client.room.create_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_room_success(self, client):
        """Test successful room deletion."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        result = await client.delete_room("test-room")
        
        assert result is True
        client.client.room.delete_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_rooms_success(self, client):
        """Test successful room listing."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Mock rooms response
        mock_room1 = MagicMock()
        mock_room1.name = "room1"
        mock_room1.sid = "sid1"
        mock_room1.creation_time = 1234567890
        mock_room1.metadata = '{"test": true}'
        mock_room1.participants = []
        
        mock_room2 = MagicMock()
        mock_room2.name = "room2"
        mock_room2.sid = "sid2"
        mock_room2.creation_time = 1234567891
        mock_room2.metadata = None
        mock_room2.participants = []
        
        mock_response = MagicMock()
        mock_response.rooms = [mock_room1, mock_room2]
        client.client.room.list_rooms.return_value = mock_response
        
        rooms = await client.list_rooms()
        
        assert len(rooms) == 2
        assert rooms[0].name == "room1"
        assert rooms[0].metadata == {"test": True}
        assert rooms[1].name == "room2"
        assert rooms[1].metadata is None
    
    @pytest.mark.asyncio
    async def test_generate_access_token(self, client):
        """Test access token generation."""
        token = await client.generate_access_token(
            identity="test-user",
            room_name="test-room"
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @pytest.mark.asyncio
    async def test_get_room_info_found(self, client):
        """Test getting room info when room exists."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Mock rooms response
        mock_room = MagicMock()
        mock_room.name = "target-room"
        mock_room.sid = "target-sid"
        mock_room.creation_time = 1234567890
        mock_room.metadata = None
        mock_room.participants = []
        
        mock_response = MagicMock()
        mock_response.rooms = [mock_room]
        client.client.room.list_rooms.return_value = mock_response
        
        room = await client.get_room_info("target-room")
        
        assert room is not None
        assert room.name == "target-room"
        assert room.sid == "target-sid"
    
    @pytest.mark.asyncio
    async def test_get_room_info_not_found(self, client):
        """Test getting room info when room doesn't exist."""
        # Setup connected client
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Mock empty rooms response
        mock_response = MagicMock()
        mock_response.rooms = []
        client.client.room.list_rooms.return_value = mock_response
        
        room = await client.get_room_info("nonexistent-room")
        
        assert room is None
    
    def test_get_connection_status(self, client):
        """Test getting connection status."""
        client.connection_state = ConnectionState.CONNECTED
        client.total_requests = 10
        client.successful_requests = 8
        client.failed_requests = 2
        
        status = client.get_connection_status()
        
        assert status["state"] == "connected"
        assert status["url"] == "wss://test.livekit.cloud"
        assert status["api_key_prefix"] == "API_test***"
        assert status["statistics"]["total_requests"] == 10
        assert status["statistics"]["successful_requests"] == 8
        assert status["statistics"]["failed_requests"] == 2
        assert status["statistics"]["success_rate"] == 80.0
    
    @pytest.mark.asyncio
    async def test_connection_test(self, client):
        """Test connection testing functionality."""
        with patch.object(client, 'connect') as mock_connect:
            with patch.object(client, 'create_room') as mock_create:
                with patch.object(client, 'list_rooms') as mock_list:
                    with patch.object(client, 'delete_room') as mock_delete:
                        with patch.object(client, 'generate_access_token') as mock_token:
                            
                            # Setup mocks
                            mock_connect.return_value = None
                            client.connection_state = ConnectionState.CONNECTED
                            
                            mock_room = MagicMock()
                            mock_room.name = "test-room"
                            mock_create.return_value = mock_room
                            
                            mock_list.return_value = [mock_room]
                            mock_delete.return_value = True
                            mock_token.return_value = "test-token"
                            
                            results = await client.test_connection()
                            
                            assert results["overall_status"] == "HEALTHY"
                            assert results["tests"]["connection"]["status"] == "PASS"
                            assert results["tests"]["room_operations"]["status"] == "PASS"
                            assert results["tests"]["token_generation"]["status"] == "PASS"
    
    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test client disconnection."""
        # Setup connected client with health check task
        client.connection_state = ConnectionState.CONNECTED
        client.client = AsyncMock()
        
        # Create a real asyncio task that we can cancel
        async def dummy_task():
            await asyncio.sleep(10)  # Long running task
        
        task = asyncio.create_task(dummy_task())
        client.health_check_task = task
        
        await client.disconnect()
        
        assert client.connection_state == ConnectionState.DISCONNECTED
        assert client.client is None
        assert task.cancelled()
    
    @pytest.mark.asyncio
    async def test_join_room_success(self, client):
        """Test successful room joining."""
        # Mock token generation
        with patch.object(client, 'generate_access_token') as mock_token:
            mock_token.return_value = "test-token"
            
            # Mock room connection
            with patch('livekit.rtc.Room') as mock_room_class:
                mock_room = AsyncMock()
                mock_room_class.return_value = mock_room
                
                # Mock the retry mechanism to directly call the operation
                async def mock_execute_with_retry(operation, operation_name, *args, **kwargs):
                    return await operation(*args, **kwargs)
                
                with patch.object(client, '_execute_with_retry', side_effect=mock_execute_with_retry):
                    participant = await client.join_room("test-room", "test-user")
                    
                    assert participant.identity == "test-user"
                    assert participant.room_name == "test-room"
                    assert participant.room == mock_room
                    mock_room.connect.assert_called_once_with(client.url, "test-token")
    
    @pytest.mark.asyncio
    async def test_publish_audio_track_success(self, client):
        """Test successful audio track publishing."""
        # Create mock participant
        mock_room = AsyncMock()
        mock_local_participant = AsyncMock()
        mock_room.local_participant = mock_local_participant
        
        from clients.livekit_client import RoomParticipant
        participant = RoomParticipant(
            room=mock_room,
            identity="test-user",
            room_name="test-room"
        )
        
        # Mock track creation and publishing
        with patch('livekit.rtc.AudioSource') as mock_audio_source:
            with patch('livekit.rtc.LocalAudioTrack') as mock_track_class:
                mock_track = AsyncMock()
                mock_track_class.create_audio_track.return_value = mock_track
                
                mock_publication = AsyncMock()
                mock_local_participant.publish_track.return_value = mock_publication
                
                # Mock the retry mechanism to directly call the operation
                async def mock_execute_with_retry(operation, operation_name, *args, **kwargs):
                    return await operation(*args, **kwargs)
                
                with patch.object(client, '_execute_with_retry', side_effect=mock_execute_with_retry):
                    track = await client.publish_audio_track(participant)
                    
                    assert track == mock_track
                    assert participant.audio_track == mock_track
                    assert participant.audio_publication == mock_publication
                    mock_local_participant.publish_track.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_subscribe_to_audio_success(self, client):
        """Test successful audio subscription setup."""
        # Create mock participant
        mock_room = AsyncMock()
        
        from clients.livekit_client import RoomParticipant
        participant = RoomParticipant(
            room=mock_room,
            identity="test-user",
            room_name="test-room"
        )
        
        # Mock callback
        callback = MagicMock()
        
        await client.subscribe_to_audio(participant, callback)
        
        assert participant.audio_callback == callback
        # Verify event handlers were set up
        mock_room.on.assert_any_call("track_subscribed", unittest.mock.ANY)
        mock_room.on.assert_any_call("track_unsubscribed", unittest.mock.ANY)
    
    @pytest.mark.asyncio
    async def test_leave_room_success(self, client):
        """Test successful room leaving."""
        # Create mock participant with audio track
        mock_room = AsyncMock()
        mock_local_participant = AsyncMock()
        mock_room.local_participant = mock_local_participant
        
        mock_publication = AsyncMock()
        mock_publication.sid = "test-sid"
        
        from clients.livekit_client import RoomParticipant
        participant = RoomParticipant(
            room=mock_room,
            identity="test-user",
            room_name="test-room"
        )
        participant.audio_publication = mock_publication
        
        await client.leave_room(participant)
        
        assert participant.room is None
        assert participant.audio_track is None
        assert participant.audio_publication is None
        mock_local_participant.unpublish_track.assert_called_once_with("test-sid")
        mock_room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_audio_data_success(self, client):
        """Test successful audio data sending."""
        # Create mock participant with audio track
        mock_audio_source = AsyncMock()
        mock_track = AsyncMock()
        mock_track.source = mock_audio_source
        
        from clients.livekit_client import RoomParticipant
        participant = RoomParticipant(
            room=AsyncMock(),
            identity="test-user",
            room_name="test-room"
        )
        participant.audio_track = mock_track
        
        audio_data = b"test audio data"
        
        with patch('livekit.rtc.AudioFrame') as mock_frame_class:
            mock_frame = AsyncMock()
            mock_frame_class.return_value = mock_frame
            
            await client.send_audio_data(participant, audio_data)
            
            mock_audio_source.capture_frame.assert_called_once_with(mock_frame)
    
    @pytest.mark.asyncio
    async def test_send_audio_data_no_track(self, client):
        """Test audio data sending without audio track."""
        from clients.livekit_client import RoomParticipant, LiveKitConnectionError
        participant = RoomParticipant(
            room=AsyncMock(),
            identity="test-user",
            room_name="test-room"
        )
        # No audio track set
        
        audio_data = b"test audio data"
        
        with pytest.raises(LiveKitConnectionError, match="No audio track available"):
            await client.send_audio_data(participant, audio_data)
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        with patch.object(client, '_perform_health_check') as mock_health:
            mock_health.return_value = None  # No exception means success
            
            result = await client.health_check()
            
            assert result is True
            mock_health.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch.object(client, '_perform_health_check') as mock_health:
            mock_health.side_effect = Exception("Health check failed")
            
            result = await client.health_check()
            
            assert result is False
            mock_health.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
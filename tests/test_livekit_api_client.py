"""
Tests for LiveKit API Client

This module tests the LiveKit API client implementation including:
- Proper Twirp endpoint usage
- Authorization header handling
- Error handling and mapping
- Retry logic with exponential backoff
- All RoomService API methods
"""

import asyncio
import json
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import aiohttp
from livekit.api import Room, ParticipantInfo

from src.clients.livekit_api_client import (
    LiveKitAPIClient,
    LiveKitAPIError,
    LiveKitAuthenticationError,
    LiveKitNotFoundError,
    LiveKitValidationError,
    LiveKitRateLimitError,
    LiveKitServerError,
    LiveKitConnectionError,
    RetryConfig,
    APIMetrics
)
from src.auth.livekit_auth import LiveKitAuthManager


class TestLiveKitAPIClient:
    """Test cases for LiveKit API Client."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Mock authentication manager."""
        auth_manager = MagicMock(spec=LiveKitAuthManager)
        auth_manager.create_admin_token.return_value = "mock-admin-token"
        return auth_manager
    
    @pytest.fixture
    def client(self, mock_auth_manager):
        """Create test client."""
        return LiveKitAPIClient(
            url="https://test.livekit.io",
            api_key="test-key",
            api_secret="test-secret",
            auth_manager=mock_auth_manager,
            timeout=5.0
        )
    
    @pytest.fixture
    def mock_response(self):
        """Mock HTTP response."""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='{"success": true}')
        return response
    
    def test_client_initialization(self, mock_auth_manager):
        """Test client initialization."""
        client = LiveKitAPIClient(
            url="https://test.livekit.io/",  # Test URL normalization
            api_key="test-key",
            api_secret="test-secret",
            auth_manager=mock_auth_manager
        )
        
        assert client.url == "https://test.livekit.io"
        assert client.api_key == "test-key"
        assert client.api_secret == "test-secret"
        assert client.auth_manager == mock_auth_manager
        assert isinstance(client.retry_config, RetryConfig)
        assert isinstance(client.metrics, APIMetrics)
    
    def test_client_initialization_missing_credentials(self):
        """Test client initialization with missing credentials."""
        with patch('src.clients.livekit_api_client.get_settings') as mock_settings:
            mock_settings.return_value.livekit_api_key = None
            mock_settings.return_value.livekit_api_secret = None
            
            with pytest.raises(ValueError, match="LiveKit API key and secret are required"):
                LiveKitAPIClient(url="https://test.livekit.io")
    
    def test_twirp_endpoints(self, client):
        """Test that all required Twirp endpoints are defined."""
        expected_endpoints = [
            "create_room",
            "list_rooms", 
            "delete_room",
            "list_participants",
            "get_participant",
            "remove_participant",
            "update_participant",
            "mute_published_track",
            "update_subscriptions",
            "send_data",
            "update_room_metadata"
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in client.TWIRP_ENDPOINTS
            assert client.TWIRP_ENDPOINTS[endpoint].startswith("/twirp/livekit.RoomService/")
    
    def test_error_mapping(self, client):
        """Test HTTP error code mapping."""
        test_cases = [
            (400, "Bad request", LiveKitValidationError),
            (401, "Unauthorized", LiveKitAuthenticationError),
            (403, "Forbidden", LiveKitAuthenticationError),
            (404, "Not found", LiveKitNotFoundError),
            (429, "Rate limited", LiveKitRateLimitError),
            (500, "Server error", LiveKitServerError),
            (502, "Bad gateway", LiveKitServerError),
            (418, "I'm a teapot", LiveKitAPIError)  # Generic error
        ]
        
        for status_code, message, expected_exception in test_cases:
            error = client._map_http_error(status_code, message)
            assert isinstance(error, expected_exception)
            assert error.status_code == status_code
            assert message in str(error)
    
    def test_retry_delay_calculation(self, client):
        """Test retry delay calculation with exponential backoff."""
        # Test without jitter
        client.retry_config.jitter = False
        
        delay_0 = client._calculate_retry_delay(0)
        delay_1 = client._calculate_retry_delay(1)
        delay_2 = client._calculate_retry_delay(2)
        
        assert delay_0 == 1.0  # base_delay
        assert delay_1 == 2.0  # base_delay * 2^1
        assert delay_2 == 4.0  # base_delay * 2^2
        
        # Test max delay
        delay_large = client._calculate_retry_delay(10)
        assert delay_large == client.retry_config.max_delay
        
        # Test with jitter
        client.retry_config.jitter = True
        delay_with_jitter = client._calculate_retry_delay(1)
        assert 1.5 <= delay_with_jitter <= 2.5  # 2.0 ± 25%
    
    @pytest.mark.asyncio
    async def test_admin_token_management(self, client, mock_auth_manager):
        """Test admin token creation and caching."""
        # First call should create token
        token1 = await client._get_admin_token()
        assert token1 == "mock-admin-token"
        mock_auth_manager.create_admin_token.assert_called_once()
        
        # Second call should use cached token
        token2 = await client._get_admin_token()
        assert token2 == "mock-admin-token"
        assert mock_auth_manager.create_admin_token.call_count == 1
        
        # Simulate token expiration
        client._admin_token_expires = datetime.now(UTC) - timedelta(minutes=1)
        token3 = await client._get_admin_token()
        assert token3 == "mock-admin-token"
        assert mock_auth_manager.create_admin_token.call_count == 2
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, client, mock_response):
        """Test successful HTTP request."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await client._make_request_with_retry(
                "POST",
                "/test/endpoint",
                {"test": "data"}
            )
            
            assert result == {"success": True}
            
            # Verify request was made with correct parameters
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            
            assert args[0] == "POST"
            assert args[1] == "https://test.livekit.io/test/endpoint"
            assert kwargs["json"] == {"test": "data"}
            assert "Authorization" in kwargs["headers"]
            assert kwargs["headers"]["Authorization"] == "Bearer mock-admin-token"
            assert kwargs["headers"]["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_make_request_retry_on_server_error(self, client):
        """Test retry logic on server errors."""
        client.retry_config.max_attempts = 3
        client.retry_config.base_delay = 0.01  # Fast retry for testing
        
        responses = [
            MagicMock(status=500, text=AsyncMock(return_value="Server error")),
            MagicMock(status=502, text=AsyncMock(return_value="Bad gateway")),
            MagicMock(status=200, text=AsyncMock(return_value='{"success": true}'))
        ]
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.side_effect = responses
            
            result = await client._make_request_with_retry(
                "POST",
                "/test/endpoint"
            )
            
            assert result == {"success": True}
            assert mock_request.call_count == 3
            assert client.metrics.retry_attempts == 2
    
    @pytest.mark.asyncio
    async def test_make_request_retry_exhausted(self, client):
        """Test retry exhaustion."""
        client.retry_config.max_attempts = 2
        client.retry_config.base_delay = 0.01
        
        error_response = MagicMock(status=500, text=AsyncMock(return_value="Server error"))
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = error_response
            
            with pytest.raises(LiveKitServerError):
                await client._make_request_with_retry(
                    "POST",
                    "/test/endpoint"
                )
            
            assert mock_request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_make_request_non_retryable_error(self, client):
        """Test non-retryable errors."""
        error_response = MagicMock(status=400, text=AsyncMock(return_value="Bad request"))
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = error_response
            
            with pytest.raises(LiveKitValidationError):
                await client._make_request_with_retry(
                    "POST",
                    "/test/endpoint"
                )
            
            # Should not retry on 400 error
            assert mock_request.call_count == 1
    
    @pytest.mark.asyncio
    async def test_make_request_connection_error_retry(self, client):
        """Test retry on connection errors."""
        client.retry_config.max_attempts = 3
        client.retry_config.base_delay = 0.01
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            # Create a successful response mock
            success_response = MagicMock(status=200, text=AsyncMock(return_value='{"success": true}'))
            
            mock_request.side_effect = [
                aiohttp.ClientConnectionError("Connection failed"),
                asyncio.TimeoutError("Timeout"),
                success_response
            ]
            mock_request.return_value.__aenter__.return_value = success_response
            
            # Need to handle the side_effect properly
            def side_effect_handler(*args, **kwargs):
                if mock_request.call_count <= 2:
                    if mock_request.call_count == 1:
                        raise aiohttp.ClientConnectionError("Connection failed")
                    else:
                        raise asyncio.TimeoutError("Timeout")
                else:
                    response = MagicMock(status=200, text=AsyncMock(return_value='{"success": true}'))
                    return response
            
            mock_request.side_effect = None
            mock_request.return_value.__aenter__.side_effect = side_effect_handler
            
            result = await client._make_request_with_retry(
                "POST",
                "/test/endpoint"
            )
            
            assert result == {"success": True}
            assert mock_request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_create_room(self, client):
        """Test create room API call."""
        expected_response = {
            "name": "test-room",
            "empty_timeout": 300,
            "departure_timeout": 20,
            "max_participants": 10,
            "creation_time": int(datetime.now(UTC).timestamp()),
            "metadata": '{"test": "data"}'
        }
        
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = expected_response
            
            room = await client.create_room(
                name="test-room",
                max_participants=10,
                metadata={"test": "data"}
            )
            
            assert isinstance(room, Room)
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[0] == "POST"
            assert args[1] == "/twirp/livekit.RoomService/CreateRoom"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["name"] == "test-room"
            assert request_data["max_participants"] == 10
            assert json.loads(request_data["metadata"]) == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_list_rooms(self, client):
        """Test list rooms API call."""
        expected_response = {
            "rooms": [
                {"name": "room1", "creation_time": int(datetime.now(UTC).timestamp())},
                {"name": "room2", "creation_time": int(datetime.now(UTC).timestamp())}
            ]
        }
        
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = expected_response
            
            rooms = await client.list_rooms(names=["room1", "room2"])
            
            assert len(rooms) == 2
            assert all(isinstance(room, Room) for room in rooms)
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/ListRooms"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["names"] == ["room1", "room2"]
    
    @pytest.mark.asyncio
    async def test_delete_room(self, client):
        """Test delete room API call."""
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = {}
            
            await client.delete_room("test-room")
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/DeleteRoom"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["room"] == "test-room"
    
    @pytest.mark.asyncio
    async def test_list_participants(self, client):
        """Test list participants API call."""
        expected_response = {
            "participants": [
                {
                    "sid": "participant1",
                    "identity": "user1",
                    "name": "User 1",
                    "state": 0,
                    "joined_at": int(datetime.now(UTC).timestamp())
                }
            ]
        }
        
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = expected_response
            
            participants = await client.list_participants("test-room")
            
            assert len(participants) == 1
            assert all(isinstance(p, ParticipantInfo) for p in participants)
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/ListParticipants"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["room"] == "test-room"
    
    @pytest.mark.asyncio
    async def test_remove_participant(self, client):
        """Test remove participant API call."""
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = {}
            
            await client.remove_participant("test-room", "user1")
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/RemoveParticipant"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["room"] == "test-room"
            assert request_data["identity"] == "user1"
    
    @pytest.mark.asyncio
    async def test_mute_published_track(self, client):
        """Test mute published track API call."""
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = {}
            
            await client.mute_published_track(
                "test-room", 
                "user1", 
                "track123", 
                True
            )
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/MutePublishedTrack"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["room"] == "test-room"
            assert request_data["identity"] == "user1"
            assert request_data["track_sid"] == "track123"
            assert request_data["muted"] is True
    
    @pytest.mark.asyncio
    async def test_send_data(self, client):
        """Test send data API call."""
        test_data = b"Hello, World!"
        
        with patch.object(client, '_make_request_with_retry') as mock_request:
            mock_request.return_value = {}
            
            await client.send_data(
                "test-room",
                test_data,
                kind=1,
                destination_sids=["participant1"],
                topic="chat"
            )
            
            # Verify request parameters
            mock_request.assert_called_once()
            args = mock_request.call_args[0]
            assert args[1] == "/twirp/livekit.RoomService/SendData"
            
            request_data = mock_request.call_args[0][2]
            assert request_data["room"] == "test-room"
            assert request_data["kind"] == 1
            assert request_data["destination_sids"] == ["participant1"]
            assert request_data["topic"] == "chat"
            
            # Verify data is base64 encoded
            import base64
            decoded_data = base64.b64decode(request_data["data"])
            assert decoded_data == test_data
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        with patch.object(client, 'list_rooms') as mock_list_rooms:
            mock_list_rooms.return_value = [MagicMock(), MagicMock()]
            
            result = await client.health_check()
            
            assert result["healthy"] is True
            assert result["rooms_count"] == 2
            assert "latency_ms" in result
            assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test failed health check."""
        with patch.object(client, 'list_rooms') as mock_list_rooms:
            mock_list_rooms.side_effect = LiveKitServerError("Server error")
            
            result = await client.health_check()
            
            assert result["healthy"] is False
            assert "error" in result
            assert "timestamp" in result
    
    def test_metrics_recording(self, client):
        """Test metrics recording."""
        # Record successful request
        client.metrics.record_request(True, 100.0, 0)
        
        assert client.metrics.total_requests == 1
        assert client.metrics.successful_requests == 1
        assert client.metrics.failed_requests == 0
        assert client.metrics.retry_attempts == 0
        assert client.metrics.average_latency_ms == 100.0
        
        # Record failed request with retries
        client.metrics.record_request(False, 200.0, 2)
        
        assert client.metrics.total_requests == 2
        assert client.metrics.successful_requests == 1
        assert client.metrics.failed_requests == 1
        assert client.metrics.retry_attempts == 2
        assert client.metrics.average_latency_ms == 150.0  # (100 + 200) / 2
    
    def test_get_metrics(self, client):
        """Test get metrics method."""
        client.metrics.record_request(True, 100.0, 1)
        client.metrics.record_request(False, 200.0, 0)
        
        metrics = client.get_metrics()
        
        assert metrics["total_requests"] == 2
        assert metrics["successful_requests"] == 1
        assert metrics["failed_requests"] == 1
        assert metrics["success_rate"] == 0.5
        assert metrics["retry_attempts"] == 1
        assert metrics["average_latency_ms"] == 150.0
        assert "last_request_time" in metrics
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_auth_manager):
        """Test async context manager usage."""
        async with LiveKitAPIClient(
            url="https://test.livekit.io",
            api_key="test-key",
            api_secret="test-secret",
            auth_manager=mock_auth_manager
        ) as client:
            assert client._session is not None
            assert not client._session.closed
        
        # Session should be closed after context exit
        assert client._session.closed
    
    @pytest.mark.asyncio
    async def test_session_management(self, client):
        """Test HTTP session management."""
        # Session should be None initially
        assert client._session is None
        
        # Ensure session creates one
        await client._ensure_session()
        assert client._session is not None
        assert not client._session.closed
        
        # Close session
        await client.close()
        assert client._session.closed
        
        # Ensure session should create a new one
        await client._ensure_session()
        assert not client._session.closed


class TestRetryConfig:
    """Test cases for RetryConfig."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert 429 in config.retryable_status_codes
        assert 500 in config.retryable_status_codes
        assert aiohttp.ClientConnectionError in config.retryable_exceptions
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.jitter is False


class TestAPIMetrics:
    """Test cases for APIMetrics."""
    
    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = APIMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.retry_attempts == 0
        assert metrics.average_latency_ms == 0.0
        assert metrics.last_request_time is None
    
    def test_record_single_request(self):
        """Test recording a single request."""
        metrics = APIMetrics()
        
        metrics.record_request(True, 100.0, 2)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.retry_attempts == 2
        assert metrics.average_latency_ms == 100.0
        assert metrics.last_request_time is not None
    
    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        metrics = APIMetrics()
        
        metrics.record_request(True, 100.0, 0)
        metrics.record_request(False, 200.0, 1)
        metrics.record_request(True, 150.0, 0)
        
        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert metrics.retry_attempts == 1
        assert metrics.average_latency_ms == 150.0  # (100 + 200 + 150) / 3


if __name__ == "__main__":
    pytest.main([__file__])
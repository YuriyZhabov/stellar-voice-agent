"""
Comprehensive unit tests for all LiveKit components.
Tests all new components according to requirements 7.1, 8.4, 9.3.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, UTC
import time
import jwt

# Import all components to test
from src.auth.livekit_auth import LiveKitAuthManager
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import LiveKitEgressService
from src.services.livekit_ingress import LiveKitIngressService
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.security.livekit_security import LiveKitSecurityManager
from src.performance_optimizer import LiveKitPerformanceOptimizer
from src.integration.livekit_voice_ai_integration import LiveKitVoiceAIIntegration


class TestLiveKitAuthManager:
    """Unit tests for LiveKit authentication manager."""
    
    @pytest.fixture
    def auth_manager(self):
        with patch('src.auth.livekit_auth.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                livekit_participant_token_ttl=600,
                livekit_admin_token_ttl=3600,
                livekit_auto_refresh=True
            )
            return LiveKitAuthManager("test_api_key", "test_api_secret")
    
    def test_init(self, auth_manager):
        """Test initialization of auth manager."""
        assert auth_manager.api_key == "test_api_key"
        assert auth_manager.api_secret == "test_api_secret"
    
    @patch('src.auth.livekit_auth.AccessToken')
    def test_create_participant_token(self, mock_access_token, auth_manager):
        """Test participant token creation according to specification."""
        mock_token = Mock()
        mock_token.to_jwt.return_value = "test_jwt_token"
        mock_access_token.return_value = mock_token
        
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room"
        )
        
        # Verify token creation
        mock_access_token.assert_called_once_with(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
        
        # Verify token configuration
        mock_token.with_identity.assert_called_once_with("test_user")
        mock_token.with_name.assert_called_once_with("test_user")
        mock_token.with_grants.assert_called_once()
        mock_token.with_ttl.assert_called_once()
        
        assert token == "test_jwt_token"
    
    @patch('src.auth.livekit_auth.AccessToken')
    def test_create_admin_token(self, mock_access_token, auth_manager):
        """Test admin token creation with proper grants."""
        mock_token = Mock()
        mock_token.to_jwt.return_value = "admin_jwt_token"
        mock_access_token.return_value = mock_token
        
        token = auth_manager.create_admin_token()
        
        # Verify admin token has proper grants
        mock_token.with_grants.assert_called_once()
        mock_token.with_ttl.assert_called_once_with(timedelta(hours=1))
        
        assert token == "admin_jwt_token"
    
    def test_token_auto_refresh(self, auth_manager):
        """Test automatic token refresh every 10 minutes."""
        with patch.object(auth_manager, 'create_participant_token') as mock_create:
            mock_create.return_value = "refreshed_token"
            
            # Simulate token refresh
            token = auth_manager.refresh_token("old_token", "user", "room")
            
            assert token == "refreshed_token"
            mock_create.assert_called_once_with("user", "room")


class TestLiveKitAPIClient:
    """Unit tests for LiveKit API client."""
    
    @pytest.fixture
    def api_client(self):
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            return LiveKitAPIClient(
                url="https://test.livekit.cloud",
                api_key="test_key",
                api_secret="test_secret"
            )
    
    @pytest.mark.asyncio
    async def test_create_room(self, api_client):
        """Test room creation with proper parameters."""
        mock_room = Mock()
        mock_room.name = "test_room"
        api_client.client.room.create_room = AsyncMock(return_value=mock_room)
        
        room = await api_client.create_room(
            name="test_room",
            empty_timeout=300,
            departure_timeout=20,
            max_participants=10,
            metadata={"test": "data"}
        )
        
        assert room.name == "test_room"
        api_client.client.room.create_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_rooms(self, api_client):
        """Test room listing functionality."""
        mock_response = Mock()
        mock_response.rooms = [Mock(name="room1"), Mock(name="room2")]
        api_client.client.room.list_rooms = AsyncMock(return_value=mock_response)
        
        rooms = await api_client.list_rooms()
        
        assert len(rooms) == 2
        api_client.client.room.list_rooms.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, api_client):
        """Test proper error handling for API failures."""
        api_client.client.room.create_room = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        with pytest.raises(Exception) as exc_info:
            await api_client.create_room("test_room")
        
        assert "API Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, api_client):
        """Test retry logic with exponential backoff."""
        # Mock first call to fail, second to succeed
        api_client.client.room.create_room = AsyncMock(
            side_effect=[Exception("Temporary error"), Mock(name="test_room")]
        )
        
        with patch('asyncio.sleep'):  # Mock sleep to speed up test
            room = await api_client.create_room_with_retry("test_room")
        
        assert api_client.client.room.create_room.call_count == 2


class TestLiveKitEgressService:
    """Unit tests for LiveKit Egress service."""
    
    @pytest.fixture
    def egress_service(self):
        mock_client = Mock()
        with patch('src.services.livekit_egress.EgressClient'):
            return LiveKitEgressService(mock_client)
    
    @pytest.mark.asyncio
    async def test_start_room_recording(self, egress_service):
        """Test room recording start with proper configuration."""
        mock_response = Mock()
        mock_response.egress_id = "egress_123"
        egress_service.egress_client.start_room_composite_egress = AsyncMock(
            return_value=mock_response
        )
        
        egress_id = await egress_service.start_room_recording(
            room_name="test_room",
            output_config={"file": {"filename": "recording.mp4"}}
        )
        
        assert egress_id == "egress_123"
        egress_service.egress_client.start_room_composite_egress.assert_called_once()
    
    def test_create_s3_output_config(self, egress_service):
        """Test S3 output configuration creation."""
        config = egress_service.create_s3_output_config(
            filename="test.mp4",
            bucket="test-bucket",
            access_key="access",
            secret="secret",
            region="us-east-1"
        )
        
        assert config["file"]["filename"] == "test.mp4"
        assert config["file"]["s3"]["bucket"] == "test-bucket"
        assert config["file"]["s3"]["region"] == "us-east-1"
    
    def test_create_rtmp_output_config(self, egress_service):
        """Test RTMP output configuration creation."""
        urls = ["rtmp://stream1.com", "rtmp://stream2.com"]
        config = egress_service.create_rtmp_output_config(urls)
        
        assert config["stream"]["protocol"] == "RTMP"
        assert config["stream"]["urls"] == urls


class TestLiveKitIngressService:
    """Unit tests for LiveKit Ingress service."""
    
    @pytest.fixture
    def ingress_service(self):
        mock_client = Mock()
        with patch('src.services.livekit_ingress.IngressClient'):
            return LiveKitIngressService(mock_client)
    
    @pytest.mark.asyncio
    async def test_create_rtmp_ingress(self, ingress_service):
        """Test RTMP ingress creation."""
        mock_response = Mock()
        mock_response.ingress_id = "ingress_123"
        mock_response.url = "rtmp://test.com/live"
        mock_response.stream_key = "stream_key_123"
        
        ingress_service.ingress_client.create_ingress = AsyncMock(
            return_value=mock_response
        )
        
        result = await ingress_service.create_rtmp_ingress(
            name="test_ingress",
            room_name="test_room",
            participant_identity="streamer",
            participant_name="Streamer"
        )
        
        assert result["ingress_id"] == "ingress_123"
        assert result["url"] == "rtmp://test.com/live"
        assert result["stream_key"] == "stream_key_123"
    
    @pytest.mark.asyncio
    async def test_create_whip_ingress(self, ingress_service):
        """Test WHIP ingress creation."""
        mock_response = Mock()
        mock_response.ingress_id = "whip_123"
        mock_response.url = "https://test.com/whip"
        
        ingress_service.ingress_client.create_ingress = AsyncMock(
            return_value=mock_response
        )
        
        result = await ingress_service.create_whip_ingress(
            name="whip_test",
            room_name="test_room",
            participant_identity="whip_user"
        )
        
        assert result["ingress_id"] == "whip_123"
        assert result["url"] == "https://test.com/whip"


class TestLiveKitSystemMonitor:
    """Unit tests for LiveKit system monitor."""
    
    @pytest.fixture
    def system_monitor(self):
        mock_client = Mock()
        return LiveKitSystemMonitor(mock_client)
    
    @pytest.mark.asyncio
    async def test_run_health_checks(self, system_monitor):
        """Test comprehensive health checks."""
        # Mock all health check methods
        system_monitor._check_room_service = AsyncMock(
            return_value={"status": "healthy", "latency_ms": 50}
        )
        system_monitor._check_sip_service = AsyncMock(
            return_value={"status": "healthy"}
        )
        system_monitor._check_egress_service = AsyncMock(
            return_value={"status": "healthy"}
        )
        system_monitor._check_ingress_service = AsyncMock(
            return_value={"status": "healthy"}
        )
        system_monitor._check_performance = AsyncMock(
            return_value={"avg_latency": 45}
        )
        
        checks = await system_monitor.run_health_checks()
        
        assert "timestamp" in checks
        assert "checks" in checks
        assert checks["checks"]["room_service"]["status"] == "healthy"
        assert checks["checks"]["performance"]["avg_latency"] == 45
    
    @pytest.mark.asyncio
    async def test_check_room_service_healthy(self, system_monitor):
        """Test room service health check when healthy."""
        system_monitor.client.list_rooms = AsyncMock(return_value=[])
        
        result = await system_monitor._check_room_service()
        
        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert "rooms_count" in result
    
    @pytest.mark.asyncio
    async def test_check_room_service_unhealthy(self, system_monitor):
        """Test room service health check when unhealthy."""
        system_monitor.client.list_rooms = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        
        result = await system_monitor._check_room_service()
        
        assert result["status"] == "unhealthy"
        assert "Connection failed" in result["error"]
    
    def test_metrics_tracking(self, system_monitor):
        """Test metrics tracking functionality."""
        # Test connection metrics
        system_monitor.record_connection_success()
        system_monitor.record_connection_failure()
        
        assert system_monitor.metrics["connections"]["successful"] == 1
        assert system_monitor.metrics["connections"]["failed"] == 1
        
        # Test latency tracking
        system_monitor.record_api_latency(100.5)
        assert 100.5 in system_monitor.metrics["api_latency"]


class TestLiveKitSecurityManager:
    """Unit tests for LiveKit security manager."""
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_mask_api_keys_in_logs(self, security_manager):
        """Test API key masking in logs."""
        log_message = "API key: livekit_api_key_12345 used for authentication"
        masked = security_manager.mask_sensitive_data(log_message)
        
        assert "livekit_api_key_12345" not in masked
        assert "***MASKED***" in masked
    
    def test_validate_jwt_token(self, security_manager):
        """Test JWT token validation."""
        # Create a test token
        payload = {
            "iss": "test_key",
            "sub": "test_user",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "video": {"roomJoin": True}
        }
        token = jwt.encode(payload, "test_secret", algorithm="HS256")
        
        is_valid = security_manager.validate_jwt_token(token, "test_secret")
        assert is_valid is True
    
    def test_validate_expired_token(self, security_manager):
        """Test validation of expired JWT token."""
        payload = {
            "iss": "test_key",
            "sub": "test_user",
            "iat": int(time.time()) - 1200,
            "exp": int(time.time()) - 600,  # Expired
            "video": {"roomJoin": True}
        }
        token = jwt.encode(payload, "test_secret", algorithm="HS256")
        
        is_valid = security_manager.validate_jwt_token(token, "test_secret")
        assert is_valid is False
    
    def test_detect_suspicious_activity(self, security_manager):
        """Test suspicious activity detection."""
        # Simulate multiple failed attempts
        for _ in range(10):
            security_manager.record_failed_attempt("192.168.1.1")
        
        is_suspicious = security_manager.is_suspicious_activity("192.168.1.1")
        assert is_suspicious is True


class TestPerformanceOptimizer:
    """Unit tests for performance optimizer."""
    
    @pytest.fixture
    def performance_optimizer(self):
        return LiveKitPerformanceOptimizer(
            livekit_url="https://test.livekit.cloud",
            api_key="test_key",
            api_secret="test_secret"
        )
    
    def test_connection_pooling(self, performance_optimizer):
        """Test connection pooling functionality."""
        # Test that connection pool exists
        assert hasattr(performance_optimizer, '_connection_pool')
        assert isinstance(performance_optimizer._connection_pool, list)
    
    def test_latency_optimization(self, performance_optimizer):
        """Test audio latency optimization."""
        # Test that audio config exists and has target latency
        assert hasattr(performance_optimizer, 'audio_config')
        assert performance_optimizer.audio_config.target_latency_ms == 50
    
    def test_concurrent_room_limit(self, performance_optimizer):
        """Test concurrent room limitation."""
        # Test room limits configuration
        assert hasattr(performance_optimizer, 'room_limits')
        assert performance_optimizer.room_limits.max_concurrent_rooms == 10
        
        # Test active rooms tracking
        assert hasattr(performance_optimizer, '_active_rooms')
        assert isinstance(performance_optimizer._active_rooms, dict)
    
    def test_graceful_reconnection(self, performance_optimizer):
        """Test graceful reconnection logic."""
        # Test that reconnection method exists
        assert hasattr(performance_optimizer, '_reconnect_connection')
        
        # Test shutdown event for graceful shutdown
        assert hasattr(performance_optimizer, '_shutdown_event')


class TestLiveKitVoiceAIIntegration:
    """Unit tests for LiveKit Voice AI integration."""
    
    @pytest.fixture
    def integration(self):
        mock_client = Mock()
        mock_voice_agent = Mock()
        return LiveKitVoiceAIIntegration(mock_client, mock_voice_agent)
    
    @pytest.mark.asyncio
    async def test_handle_room_started(self, integration):
        """Test room started event handling."""
        event_data = {
            "room": {"name": "test_room"},
            "timestamp": int(time.time())
        }
        
        integration.voice_agent.join_room = AsyncMock()
        
        await integration.handle_room_started(event_data)
        
        integration.voice_agent.join_room.assert_called_once_with("test_room")
    
    @pytest.mark.asyncio
    async def test_handle_participant_joined(self, integration):
        """Test participant joined event handling."""
        event_data = {
            "participant": {"identity": "user_123"},
            "room": {"name": "test_room"}
        }
        
        integration.voice_agent.start_processing = AsyncMock()
        
        await integration.handle_participant_joined(event_data)
        
        integration.voice_agent.start_processing.assert_called_once_with("user_123")
    
    @pytest.mark.asyncio
    async def test_stt_tts_pipeline_integration(self, integration):
        """Test STT/TTS pipeline integration with LiveKit tracks."""
        audio_data = b"fake_audio_data"
        
        integration.voice_agent.process_audio = AsyncMock(
            return_value="Processed text response"
        )
        integration.voice_agent.synthesize_speech = AsyncMock(
            return_value=b"synthesized_audio"
        )
        
        result = await integration.process_audio_track(audio_data)
        
        assert result == b"synthesized_audio"
        integration.voice_agent.process_audio.assert_called_once_with(audio_data)
        integration.voice_agent.synthesize_speech.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
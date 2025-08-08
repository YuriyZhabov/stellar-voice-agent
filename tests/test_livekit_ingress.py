"""
Tests for LiveKit Ingress Service

This module tests the comprehensive Ingress functionality:
- RTMP/RTMPS Ingress for OBS, XSplit
- WHIP Ingress for WebRTC-HTTP protocol
- URL Input for HLS, MP4, MOV files
- Support for all audio formats
- Error handling and monitoring
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, UTC

from src.services.livekit_ingress import (
    LiveKitIngressService,
    IngressType,
    IngressState,
    RTMPIngressOptions,
    WHIPIngressOptions,
    URLIngressOptions,
    IngressConfig,
    create_ingress_service
)
from src.clients.livekit_api_client import LiveKitAPIClient


@pytest.fixture
def mock_client():
    """Create mock LiveKit API client."""
    client = Mock(spec=LiveKitAPIClient)
    client.url = "https://test.livekit.cloud"
    client.api_key = "test_api_key"
    client.api_secret = "test_api_secret"
    return client


@pytest.fixture
def mock_livekit_api():
    """Create mock LiveKit API."""
    with patch('src.services.livekit_ingress.LiveKitAPI') as mock_api:
        api_instance = Mock()
        api_instance.ingress = Mock()
        mock_api.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_metrics():
    """Create mock metrics collector."""
    with patch('src.services.livekit_ingress.get_metrics_collector') as mock_get_metrics:
        metrics = Mock()
        metrics.increment_counter = Mock()
        mock_get_metrics.return_value = metrics
        yield metrics


@pytest.fixture
def ingress_service(mock_client, mock_livekit_api, mock_metrics):
    """Create LiveKit Ingress Service instance."""
    return LiveKitIngressService(mock_client)


class TestLiveKitIngressService:
    """Test LiveKit Ingress Service functionality."""
    
    def test_init(self, mock_client, mock_livekit_api, mock_metrics):
        """Test service initialization."""
        service = LiveKitIngressService(mock_client)
        
        assert service.client == mock_client
        assert service.livekit_api is not None
        assert service.active_ingress == {}
    
    @pytest.mark.asyncio
    async def test_create_rtmp_ingress_success(self, ingress_service, mock_livekit_api, mock_metrics):
        """Test successful RTMP ingress creation."""
        # Mock response
        mock_response = Mock()
        mock_response.ingress_id = "test_ingress_id"
        mock_response.url = "rtmp://test.livekit.cloud/live"
        mock_response.stream_key = "test_stream_key"
        
        mock_livekit_api.ingress.create_ingress = AsyncMock(return_value=mock_response)
        
        # Test RTMP ingress creation
        result = await ingress_service.create_rtmp_ingress(
            name="test_rtmp",
            room_name="test_room",
            participant_identity="rtmp_user",
            participant_name="RTMP User"
        )
        
        # Verify result
        assert result["ingress_id"] == "test_ingress_id"
        assert result["url"] == "rtmp://test.livekit.cloud/live"
        assert result["stream_key"] == "test_stream_key"
        assert result["name"] == "test_rtmp"
        assert result["room_name"] == "test_room"
        assert result["participant_identity"] == "rtmp_user"
        
        # Verify tracking
        assert "test_ingress_id" in ingress_service.active_ingress
        config = ingress_service.active_ingress["test_ingress_id"]
        assert config.input_type == IngressType.RTMP_INPUT
        assert config.state == IngressState.ENDPOINT_INACTIVE
        
        # Verify metrics
        mock_metrics.increment_counter.assert_called_with(
            "ingress_created_total",
            labels={"type": "rtmp", "room": "test_room"}
        )
    
    @pytest.mark.asyncio
    async def test_create_rtmp_ingress_with_options(self, ingress_service, mock_livekit_api):
        """Test RTMP ingress creation with custom options."""
        from livekit.api import IngressVideoEncodingPreset, IngressAudioEncodingPreset
        
        mock_response = Mock()
        mock_response.ingress_id = "test_ingress_id"
        mock_response.url = "rtmp://test.livekit.cloud/live"
        mock_response.stream_key = "test_stream_key"
        
        mock_livekit_api.ingress.create_ingress = AsyncMock(return_value=mock_response)
        
        # Test with custom options
        options = RTMPIngressOptions(
            enable_transcoding=True,
            bypass_transcoding=False,
            video_preset=IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS,
            audio_preset=IngressAudioEncodingPreset.OPUS_STEREO_96KBPS
        )
        
        result = await ingress_service.create_rtmp_ingress(
            name="test_rtmp_custom",
            room_name="test_room",
            participant_identity="rtmp_user",
            options=options
        )
        
        assert result["ingress_id"] == "test_ingress_id"
        
        # Verify API call was made with correct parameters
        mock_livekit_api.ingress.create_ingress.assert_called_once()
        call_args = mock_livekit_api.ingress.create_ingress.call_args[0][0]
        assert call_args.enable_transcoding == True
        assert call_args.bypass_transcoding == False
    
    @pytest.mark.asyncio
    async def test_create_whip_ingress_success(self, ingress_service, mock_livekit_api, mock_metrics):
        """Test successful WHIP ingress creation."""
        # Mock response
        mock_response = Mock()
        mock_response.ingress_id = "whip_ingress_id"
        mock_response.url = "https://test.livekit.cloud/whip/endpoint"
        
        mock_livekit_api.ingress.create_ingress = AsyncMock(return_value=mock_response)
        
        # Test WHIP ingress creation
        result = await ingress_service.create_whip_ingress(
            name="test_whip",
            room_name="test_room",
            participant_identity="whip_user"
        )
        
        # Verify result
        assert result["ingress_id"] == "whip_ingress_id"
        assert result["url"] == "https://test.livekit.cloud/whip/endpoint"
        assert result["name"] == "test_whip"
        assert result["room_name"] == "test_room"
        assert result["participant_identity"] == "whip_user"
        
        # Verify tracking
        assert "whip_ingress_id" in ingress_service.active_ingress
        config = ingress_service.active_ingress["whip_ingress_id"]
        assert config.input_type == IngressType.WHIP_INPUT
        
        # Verify metrics
        mock_metrics.increment_counter.assert_called_with(
            "ingress_created_total",
            labels={"type": "whip", "room": "test_room"}
        )
    
    @pytest.mark.asyncio
    async def test_create_url_ingress_success(self, ingress_service, mock_livekit_api, mock_metrics):
        """Test successful URL ingress creation."""
        # Mock response
        mock_response = Mock()
        mock_response.ingress_id = "url_ingress_id"
        
        mock_livekit_api.ingress.create_ingress = AsyncMock(return_value=mock_response)
        
        # Test URL ingress creation with MP4 file
        result = await ingress_service.create_url_ingress(
            name="test_url",
            room_name="test_room",
            participant_identity="url_user",
            url="https://example.com/video.mp4"
        )
        
        # Verify result
        assert result["ingress_id"] == "url_ingress_id"
        assert result["name"] == "test_url"
        assert result["room_name"] == "test_room"
        assert result["participant_identity"] == "url_user"
        assert result["source_url"] == "https://example.com/video.mp4"
        
        # Verify tracking
        assert "url_ingress_id" in ingress_service.active_ingress
        config = ingress_service.active_ingress["url_ingress_id"]
        assert config.input_type == IngressType.URL_INPUT
        
        # Verify metrics
        mock_metrics.increment_counter.assert_called_with(
            "ingress_created_total",
            labels={"type": "url", "room": "test_room"}
        )
    
    @pytest.mark.asyncio
    async def test_create_url_ingress_supported_formats(self, ingress_service, mock_livekit_api):
        """Test URL ingress with various supported formats."""
        mock_response = Mock()
        mock_response.ingress_id = "url_ingress_id"
        mock_livekit_api.ingress.create_ingress = AsyncMock(return_value=mock_response)
        
        # Test supported video formats
        video_urls = [
            "https://example.com/video.mp4",
            "https://example.com/video.mov",
            "https://example.com/video.mkv",
            "https://example.com/video.webm",
            "https://example.com/playlist.m3u8"  # HLS
        ]
        
        for url in video_urls:
            result = await ingress_service.create_url_ingress(
                name=f"test_{url.split('.')[-1]}",
                room_name="test_room",
                participant_identity="url_user",
                url=url
            )
            assert result["ingress_id"] == "url_ingress_id"
        
        # Test supported audio formats
        audio_urls = [
            "https://example.com/audio.mp3",
            "https://example.com/audio.ogg",
            "https://example.com/audio.m4a",
            "https://example.com/audio.aac"
        ]
        
        for url in audio_urls:
            result = await ingress_service.create_url_ingress(
                name=f"test_{url.split('.')[-1]}",
                room_name="test_room",
                participant_identity="url_user",
                url=url
            )
            assert result["ingress_id"] == "url_ingress_id"
    
    @pytest.mark.asyncio
    async def test_create_url_ingress_unsupported_format(self, ingress_service, mock_livekit_api):
        """Test URL ingress with unsupported format."""
        # Mock the API call to avoid the actual call
        mock_livekit_api.ingress.create_ingress = AsyncMock()
        
        with pytest.raises(ValueError, match="Unsupported URL format"):
            await ingress_service.create_url_ingress(
                name="test_unsupported",
                room_name="test_room",
                participant_identity="url_user",
                url="ftp://example.com/video.xyz"
            )
    
    @pytest.mark.asyncio
    async def test_update_ingress_success(self, ingress_service, mock_livekit_api):
        """Test successful ingress update."""
        # Mock response
        mock_response = Mock()
        mock_response.ingress_id = "test_ingress_id"
        mock_response.name = "updated_name"
        mock_response.room_name = "updated_room"
        mock_response.participant_identity = "updated_user"
        mock_response.participant_name = "Updated User"
        mock_response.state = IngressState.ENDPOINT_INACTIVE
        mock_response.url = "rtmp://test.livekit.cloud/live"
        mock_response.stream_key = "test_stream_key"
        
        mock_livekit_api.ingress.update_ingress = AsyncMock(return_value=mock_response)
        
        # Add ingress to tracking
        ingress_service.active_ingress["test_ingress_id"] = IngressConfig(
            ingress_id="test_ingress_id",
            name="old_name",
            room_name="old_room",
            participant_identity="old_user",
            participant_name="Old User",
            input_type=IngressType.RTMP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE
        )
        
        # Test update
        result = await ingress_service.update_ingress(
            ingress_id="test_ingress_id",
            name="updated_name",
            room_name="updated_room",
            participant_identity="updated_user"
        )
        
        # Verify result
        assert result["ingress_id"] == "test_ingress_id"
        assert result["name"] == "updated_name"
        assert result["room_name"] == "updated_room"
        assert result["participant_identity"] == "updated_user"
        
        # Verify tracking was updated
        config = ingress_service.active_ingress["test_ingress_id"]
        assert config.name == "updated_name"
        assert config.room_name == "updated_room"
        assert config.participant_identity == "updated_user"
    
    @pytest.mark.asyncio
    async def test_list_ingress_success(self, ingress_service, mock_livekit_api):
        """Test successful ingress listing."""
        # Mock response
        mock_ingress_info = Mock()
        mock_ingress_info.ingress_id = "test_ingress_id"
        mock_ingress_info.name = "test_ingress"
        mock_ingress_info.stream_key = "test_stream_key"
        mock_ingress_info.url = "rtmp://test.livekit.cloud/live"
        mock_ingress_info.input_type = IngressType.RTMP_INPUT
        mock_ingress_info.bypass_transcoding = False
        mock_ingress_info.enable_transcoding = True
        mock_ingress_info.room_name = "test_room"
        mock_ingress_info.participant_identity = "test_user"
        mock_ingress_info.participant_name = "Test User"
        mock_ingress_info.reusable = False
        mock_ingress_info.state = IngressState.ENDPOINT_INACTIVE
        
        mock_response = Mock()
        mock_response.items = [mock_ingress_info]
        
        mock_livekit_api.ingress.list_ingress = AsyncMock(return_value=mock_response)
        
        # Test list
        result = await ingress_service.list_ingress()
        
        # Verify result
        assert len(result) == 1
        ingress_data = result[0]
        assert ingress_data["ingress_id"] == "test_ingress_id"
        assert ingress_data["name"] == "test_ingress"
        assert ingress_data["room_name"] == "test_room"
        assert ingress_data["participant_identity"] == "test_user"
    
    @pytest.mark.asyncio
    async def test_delete_ingress_success(self, ingress_service, mock_livekit_api, mock_metrics):
        """Test successful ingress deletion."""
        mock_livekit_api.ingress.delete_ingress = AsyncMock()
        
        # Add ingress to tracking
        ingress_service.active_ingress["test_ingress_id"] = IngressConfig(
            ingress_id="test_ingress_id",
            name="test_ingress",
            room_name="test_room",
            participant_identity="test_user",
            participant_name="Test User",
            input_type=IngressType.RTMP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE
        )
        
        # Test delete
        await ingress_service.delete_ingress("test_ingress_id")
        
        # Verify API call
        mock_livekit_api.ingress.delete_ingress.assert_called_once()
        
        # Verify removal from tracking
        assert "test_ingress_id" not in ingress_service.active_ingress
        
        # Verify metrics
        mock_metrics.increment_counter.assert_called_with(
            "ingress_deleted_total",
            labels={"ingress_id": "test_ingress_id"}
        )
    
    def test_get_ingress_status(self, ingress_service):
        """Test getting ingress status."""
        # Add ingress to tracking
        created_at = datetime.now(UTC)
        ingress_service.active_ingress["test_ingress_id"] = IngressConfig(
            ingress_id="test_ingress_id",
            name="test_ingress",
            room_name="test_room",
            participant_identity="test_user",
            participant_name="Test User",
            input_type=IngressType.RTMP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE,
            url="rtmp://test.livekit.cloud/live",
            stream_key="test_stream_key",
            created_at=created_at
        )
        
        # Test get status
        status = ingress_service.get_ingress_status("test_ingress_id")
        
        assert status is not None
        assert status["ingress_id"] == "test_ingress_id"
        assert status["name"] == "test_ingress"
        assert status["room_name"] == "test_room"
        assert status["input_type"] == IngressType.RTMP_INPUT
        assert status["state"] == IngressState.ENDPOINT_INACTIVE
        assert status["url"] == "rtmp://test.livekit.cloud/live"
        assert status["stream_key"] == "test_stream_key"
        assert status["created_at"] == created_at.isoformat()
        
        # Test non-existent ingress
        status = ingress_service.get_ingress_status("non_existent")
        assert status is None
    
    def test_get_active_ingress_count(self, ingress_service):
        """Test getting active ingress count."""
        assert ingress_service.get_active_ingress_count() == 0
        
        # Add some ingress
        ingress_service.active_ingress["ingress1"] = IngressConfig(
            ingress_id="ingress1",
            name="test1",
            room_name="room1",
            participant_identity="user1",
            participant_name="User 1",
            input_type=IngressType.RTMP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE
        )
        
        ingress_service.active_ingress["ingress2"] = IngressConfig(
            ingress_id="ingress2",
            name="test2",
            room_name="room2",
            participant_identity="user2",
            participant_name="User 2",
            input_type=IngressType.WHIP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE
        )
        
        assert ingress_service.get_active_ingress_count() == 2
    
    def test_get_ingress_by_room(self, ingress_service):
        """Test getting ingress by room."""
        created_at = datetime.now(UTC)
        
        # Add ingress for different rooms
        ingress_service.active_ingress["ingress1"] = IngressConfig(
            ingress_id="ingress1",
            name="test1",
            room_name="room1",
            participant_identity="user1",
            participant_name="User 1",
            input_type=IngressType.RTMP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE,
            created_at=created_at
        )
        
        ingress_service.active_ingress["ingress2"] = IngressConfig(
            ingress_id="ingress2",
            name="test2",
            room_name="room1",
            participant_identity="user2",
            participant_name="User 2",
            input_type=IngressType.WHIP_INPUT,
            state=IngressState.ENDPOINT_INACTIVE,
            created_at=created_at
        )
        
        ingress_service.active_ingress["ingress3"] = IngressConfig(
            ingress_id="ingress3",
            name="test3",
            room_name="room2",
            participant_identity="user3",
            participant_name="User 3",
            input_type=IngressType.URL_INPUT,
            state=IngressState.ENDPOINT_INACTIVE,
            created_at=created_at
        )
        
        # Test get by room
        room1_ingress = ingress_service.get_ingress_by_room("room1")
        assert len(room1_ingress) == 2
        
        room2_ingress = ingress_service.get_ingress_by_room("room2")
        assert len(room2_ingress) == 1
        
        non_existent_room = ingress_service.get_ingress_by_room("room3")
        assert len(non_existent_room) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, ingress_service, mock_livekit_api):
        """Test health check when service is healthy."""
        mock_response = Mock()
        mock_response.items = []
        mock_livekit_api.ingress.list_ingress = AsyncMock(return_value=mock_response)
        
        result = await ingress_service.health_check()
        
        assert result["status"] == "healthy"
        assert result["service"] == "ingress"
        assert "latency_ms" in result
        assert result["active_ingress_count"] == 0
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, ingress_service, mock_livekit_api):
        """Test health check when service is unhealthy."""
        mock_livekit_api.ingress.list_ingress = AsyncMock(side_effect=Exception("API Error"))
        
        result = await ingress_service.health_check()
        
        assert result["status"] == "unhealthy"
        assert result["service"] == "ingress"
        assert result["error"] == "API Error"
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_create_ingress_error_handling(self, ingress_service, mock_livekit_api, mock_metrics):
        """Test error handling during ingress creation."""
        mock_livekit_api.ingress.create_ingress = AsyncMock(side_effect=Exception("API Error"))
        
        with pytest.raises(Exception, match="API Error"):
            await ingress_service.create_rtmp_ingress(
                name="test_error",
                room_name="test_room",
                participant_identity="test_user"
            )
        
        # Verify error metrics
        mock_metrics.increment_counter.assert_called_with(
            "ingress_errors_total",
            labels={"type": "rtmp", "error": "create_failed"}
        )
    
    def test_supported_url_formats(self, ingress_service):
        """Test supported URL format detection."""
        supported_formats = ingress_service._get_supported_url_formats()
        
        # Check video formats
        assert ".mp4" in supported_formats
        assert ".mov" in supported_formats
        assert ".mkv" in supported_formats
        assert ".webm" in supported_formats
        
        # Check audio formats
        assert ".mp3" in supported_formats
        assert ".ogg" in supported_formats
        assert ".m4a" in supported_formats
        
        # Check streaming protocols
        assert ".m3u8" in supported_formats
        assert "rtmp://" in supported_formats
        assert "https://" in supported_formats
        
        # Test format checking
        assert ingress_service._is_supported_url_format("https://example.com/video.mp4", supported_formats)
        assert ingress_service._is_supported_url_format("rtmp://example.com/live", supported_formats)
        # Note: https:// is in supported formats, so we need a truly unsupported format
        assert not ingress_service._is_supported_url_format("ftp://example.com/video.xyz", supported_formats)


class TestIngressServiceFactory:
    """Test ingress service factory function."""
    
    def test_create_ingress_service(self, mock_client):
        """Test factory function."""
        with patch('src.services.livekit_ingress.LiveKitAPI'):
            with patch('src.services.livekit_ingress.get_metrics_collector'):
                service = create_ingress_service(mock_client)
                assert isinstance(service, LiveKitIngressService)
                assert service.client == mock_client


class TestIngressOptions:
    """Test ingress option classes."""
    
    def test_rtmp_ingress_options(self):
        """Test RTMP ingress options."""
        options = RTMPIngressOptions()
        assert options.enable_transcoding == True
        assert options.bypass_transcoding == False
        assert options.video_preset is None
        assert options.audio_preset is None
        
        # Test with custom values
        from livekit.api import IngressVideoEncodingPreset, IngressAudioEncodingPreset
        custom_options = RTMPIngressOptions(
            enable_transcoding=False,
            bypass_transcoding=True,
            video_preset=IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS,
            audio_preset=IngressAudioEncodingPreset.OPUS_STEREO_96KBPS
        )
        assert custom_options.enable_transcoding == False
        assert custom_options.bypass_transcoding == True
        assert custom_options.video_preset == IngressVideoEncodingPreset.H264_720P_30FPS_3_LAYERS
        assert custom_options.audio_preset == IngressAudioEncodingPreset.OPUS_STEREO_96KBPS
    
    def test_whip_ingress_options(self):
        """Test WHIP ingress options."""
        options = WHIPIngressOptions()
        assert options.bypass_transcoding == False
        assert options.enable_transcoding == True
        assert options.video_preset is None
        assert options.audio_preset is None
    
    def test_url_ingress_options(self):
        """Test URL ingress options."""
        options = URLIngressOptions()
        assert options.enable_transcoding == True
        assert options.bypass_transcoding == False
        assert options.video_preset is None
        assert options.audio_preset is None
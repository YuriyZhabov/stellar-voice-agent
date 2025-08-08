"""
Tests for LiveKit Egress Service

This module contains comprehensive tests for the LiveKit Egress Service,
covering all functionality according to the API specification.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

from src.services.livekit_egress import (
    LiveKitEgressService,
    EgressStatus,
    OutputFormat,
    StorageProvider,
    S3Config,
    GCPConfig,
    AzureConfig,
    AliOSSConfig,
    start_room_recording_to_s3,
    start_room_streaming_to_rtmp,
    start_room_hls_streaming
)
from src.clients.livekit_api_client import LiveKitAPIClient


@pytest.fixture
def mock_livekit_client():
    """Create mock LiveKit API client."""
    client = Mock(spec=LiveKitAPIClient)
    client.url = "wss://test.livekit.cloud"
    client.api_key = "test_api_key"
    client.api_secret = "test_api_secret"
    return client


@pytest.fixture
def mock_egress_client():
    """Create mock egress client."""
    client = AsyncMock()
    
    # Mock response for start operations
    mock_response = Mock()
    mock_response.egress_id = "test_egress_id"
    
    client.start_room_composite_egress.return_value = mock_response
    client.start_track_composite_egress.return_value = mock_response
    client.start_track_egress.return_value = mock_response
    
    # Mock response for list operation
    mock_list_response = Mock()
    mock_list_response.items = []
    client.list_egress.return_value = mock_list_response
    
    return client


@pytest.fixture
def egress_service(mock_livekit_client):
    """Create LiveKit Egress Service instance."""
    with patch('src.services.livekit_egress.LiveKitAPI') as mock_livekit_api_class:
        mock_livekit_api = AsyncMock()
        mock_egress = AsyncMock()
        mock_livekit_api.egress = mock_egress
        mock_livekit_api_class.return_value = mock_livekit_api
        
        service = LiveKitEgressService(mock_livekit_client)
        service.livekit_api = mock_livekit_api
        
        return service


@pytest.fixture
def s3_config():
    """Create S3 configuration."""
    return S3Config(
        access_key="test_access_key",
        secret="test_secret",
        region="us-east-1",
        bucket="test-bucket"
    )


@pytest.fixture
def gcp_config():
    """Create GCP configuration."""
    return GCPConfig(
        credentials='{"type": "service_account"}',
        bucket="test-bucket"
    )


@pytest.fixture
def azure_config():
    """Create Azure configuration."""
    return AzureConfig(
        account_name="testaccount",
        account_key="test_key",
        container_name="test-container"
    )


class TestLiveKitEgressService:
    """Test LiveKit Egress Service functionality."""
    
    @pytest.mark.asyncio
    async def test_start_room_composite_egress_basic(self, egress_service):
        """Test basic room composite egress start."""
        # Mock response
        mock_response = Mock()
        mock_response.egress_id = "test_egress_123"
        egress_service.livekit_api.egress.start_room_composite_egress.return_value = mock_response
        
        # Start egress
        egress_id = await egress_service.start_room_composite_egress(
            room_name="test_room",
            audio_only=False,
            video_only=False
        )
        
        # Verify
        assert egress_id == "test_egress_123"
        assert egress_id in egress_service.active_egress
        assert egress_service.active_egress[egress_id].room_name == "test_room"
        assert egress_service.active_egress[egress_id].status == EgressStatus.EGRESS_STARTING
        
        # Verify client was called
        egress_service.livekit_api.egress.start_room_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_room_composite_egress_with_file_output(self, egress_service, s3_config):
        """Test room composite egress with file output."""
        # Create file output
        file_output = egress_service.create_s3_file_output(
            filename="test_recording.mp4",
            s3_config=s3_config,
            output_format=OutputFormat.MP4
        )
        
        # Mock response
        mock_response = Mock()
        mock_response.egress_id = "test_egress_456"
        egress_service.livekit_api.egress.start_room_composite_egress.return_value = mock_response
        
        # Start egress
        egress_id = await egress_service.start_room_composite_egress(
            room_name="test_room",
            file_outputs=[file_output]
        )
        
        # Verify
        assert egress_id == "test_egress_456"
        assert egress_id in egress_service.active_egress
    
    @pytest.mark.asyncio
    async def test_start_track_composite_egress(self, egress_service):
        """Test track composite egress start."""
        # Mock response
        mock_response = Mock()
        mock_response.egress_id = "track_egress_123"
        egress_service.livekit_api.egress.start_track_composite_egress.return_value = mock_response
        
        # Start egress
        egress_id = await egress_service.start_track_composite_egress(
            room_name="test_room",
            audio_track_id="audio_track_1",
            video_track_id="video_track_1"
        )
        
        # Verify
        assert egress_id == "track_egress_123"
        assert egress_id in egress_service.active_egress
        assert egress_service.active_egress[egress_id].room_name == "test_room"
        
        # Verify client was called
        egress_service.livekit_api.egress.start_track_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_track_egress(self, egress_service):
        """Test individual track egress start."""
        # Mock response
        mock_response = Mock()
        mock_response.egress_id = "single_track_123"
        egress_service.livekit_api.egress.start_track_egress.return_value = mock_response
        
        # Start egress
        egress_id = await egress_service.start_track_egress(
            room_name="test_room",
            track_id="track_123"
        )
        
        # Verify
        assert egress_id == "single_track_123"
        assert egress_id in egress_service.active_egress
        
        # Verify client was called
        egress_service.livekit_api.egress.start_track_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_egress(self, egress_service):
        """Test stopping egress."""
        # Add active egress
        egress_id = "test_egress_stop"
        egress_service.active_egress[egress_id] = Mock()
        egress_service.active_egress[egress_id].status = EgressStatus.EGRESS_ACTIVE
        
        # Stop egress
        await egress_service.stop_egress(egress_id)
        
        # Verify
        assert egress_service.active_egress[egress_id].status == EgressStatus.EGRESS_ENDING
        assert egress_service.active_egress[egress_id].ended_at is not None
        
        # Verify client was called
        egress_service.livekit_api.egress.stop_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_egress(self, egress_service):
        """Test listing egress instances."""
        # Mock response
        mock_egress_info = Mock()
        mock_egress_info.egress_id = "list_test_123"
        mock_egress_info.room_id = "room_123"
        mock_egress_info.room_name = "test_room"
        mock_egress_info.status = EgressStatus.EGRESS_ACTIVE
        mock_egress_info.started_at = 1234567890
        mock_egress_info.ended_at = 0
        mock_egress_info.error = ""
        mock_egress_info.file_results = []
        mock_egress_info.stream_results = []
        
        mock_response = Mock()
        mock_response.items = [mock_egress_info]
        egress_service.livekit_api.egress.list_egress.return_value = mock_response
        
        # List egress
        egress_list = await egress_service.list_egress(room_name="test_room")
        
        # Verify
        assert len(egress_list) == 1
        assert egress_list[0]["egress_id"] == "list_test_123"
        assert egress_list[0]["room_name"] == "test_room"
        
        # Verify client was called
        egress_service.livekit_api.egress.list_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_layout(self, egress_service):
        """Test updating layout."""
        egress_id = "layout_test_123"
        new_layout = "https://example.com/new_layout"
        
        # Update layout
        await egress_service.update_layout(egress_id, new_layout)
        
        # Verify client was called
        egress_service.livekit_api.egress.update_layout.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_stream(self, egress_service):
        """Test updating stream outputs."""
        egress_id = "stream_test_123"
        add_urls = ["rtmp://new.example.com/stream"]
        remove_urls = ["rtmp://old.example.com/stream"]
        
        # Update stream
        await egress_service.update_stream(
            egress_id,
            add_output_urls=add_urls,
            remove_output_urls=remove_urls
        )
        
        # Verify client was called
        egress_service.livekit_api.egress.update_stream.assert_called_once()


class TestOutputConfigurations:
    """Test output configuration methods."""
    
    def test_create_s3_file_output(self, egress_service, s3_config):
        """Test S3 file output creation."""
        output = egress_service.create_s3_file_output(
            filename="test.mp4",
            s3_config=s3_config,
            output_format=OutputFormat.MP4
        )
        
        assert output is not None
        assert output.filepath == "test.mp4"
        assert output.s3.bucket == "test-bucket"
        assert output.s3.region == "us-east-1"
    
    def test_create_gcp_file_output(self, egress_service, gcp_config):
        """Test GCP file output creation."""
        output = egress_service.create_gcp_file_output(
            filename="test.mp4",
            gcp_config=gcp_config,
            output_format=OutputFormat.MP4
        )
        
        assert output is not None
        assert output.filepath == "test.mp4"
        assert output.gcp.bucket == "test-bucket"
    
    def test_create_azure_file_output(self, egress_service, azure_config):
        """Test Azure file output creation."""
        output = egress_service.create_azure_file_output(
            filename="test.mp4",
            azure_config=azure_config,
            output_format=OutputFormat.MP4
        )
        
        assert output is not None
        assert output.filepath == "test.mp4"
        assert output.azure.account_name == "testaccount"
        assert output.azure.container_name == "test-container"
    
    def test_create_rtmp_stream_output(self, egress_service):
        """Test RTMP stream output creation."""
        urls = ["rtmp://example.com/stream1", "rtmp://example.com/stream2"]
        
        output = egress_service.create_rtmp_stream_output(urls)
        
        assert output is not None
        assert output.urls == urls
    
    def test_create_srt_stream_output(self, egress_service):
        """Test SRT stream output creation."""
        urls = ["srt://example.com:1234", "srt://example.com:1235"]
        
        output = egress_service.create_srt_stream_output(urls)
        
        assert output is not None
        assert output.urls == urls
    
    def test_create_hls_segment_output(self, egress_service, s3_config):
        """Test HLS segment output creation."""
        output = egress_service.create_hls_segment_output(
            filename_prefix="stream",
            playlist_name="playlist.m3u8",
            segment_duration=6,
            s3_config=s3_config
        )
        
        assert output is not None
        assert output.filename_prefix == "stream"
        assert output.playlist_name == "playlist.m3u8"
        assert output.segment_duration == 6
        assert output.s3.bucket == "test-bucket"
    
    def test_create_encoding_options(self, egress_service):
        """Test encoding options creation."""
        options = egress_service.create_encoding_options(
            width=1280,
            height=720,
            framerate=30,
            video_bitrate=2500,
            audio_bitrate=128
        )
        
        assert options is not None
        assert options.width == 1280
        assert options.height == 720
        assert options.framerate == 30
        assert options.video_bitrate == 2500
        assert options.audio_bitrate == 128


class TestUtilityMethods:
    """Test utility methods."""
    
    @pytest.mark.asyncio
    async def test_get_egress_status(self, egress_service):
        """Test getting egress status."""
        # Add test egress
        egress_id = "status_test_123"
        from src.services.livekit_egress import EgressConfig
        
        config = EgressConfig(
            egress_id=egress_id,
            room_name="test_room",
            status=EgressStatus.EGRESS_ACTIVE,
            started_at=datetime.now(UTC)
        )
        egress_service.active_egress[egress_id] = config
        
        # Get status
        status = await egress_service.get_egress_status(egress_id)
        
        assert status is not None
        assert status.egress_id == egress_id
        assert status.room_name == "test_room"
        assert status.status == EgressStatus.EGRESS_ACTIVE
    
    @pytest.mark.asyncio
    async def test_get_active_egress_count(self, egress_service):
        """Test getting active egress count."""
        from src.services.livekit_egress import EgressConfig
        
        # Add active egress
        config1 = EgressConfig(
            egress_id="active_1",
            room_name="room1",
            status=EgressStatus.EGRESS_ACTIVE
        )
        config2 = EgressConfig(
            egress_id="active_2",
            room_name="room2",
            status=EgressStatus.EGRESS_STARTING
        )
        config3 = EgressConfig(
            egress_id="completed_1",
            room_name="room3",
            status=EgressStatus.EGRESS_COMPLETE
        )
        
        egress_service.active_egress["active_1"] = config1
        egress_service.active_egress["active_2"] = config2
        egress_service.active_egress["completed_1"] = config3
        
        # Get count
        count = await egress_service.get_active_egress_count()
        
        assert count == 2  # Only active and starting count
    
    @pytest.mark.asyncio
    async def test_cleanup_completed_egress(self, egress_service):
        """Test cleanup of completed egress instances."""
        from src.services.livekit_egress import EgressConfig
        
        # Add various status egress
        configs = {
            "active_1": EgressConfig("active_1", "room1", EgressStatus.EGRESS_ACTIVE),
            "complete_1": EgressConfig("complete_1", "room2", EgressStatus.EGRESS_COMPLETE),
            "failed_1": EgressConfig("failed_1", "room3", EgressStatus.EGRESS_FAILED),
            "starting_1": EgressConfig("starting_1", "room4", EgressStatus.EGRESS_STARTING)
        }
        
        egress_service.active_egress.update(configs)
        
        # Cleanup
        cleaned_count = await egress_service.cleanup_completed_egress()
        
        assert cleaned_count == 2  # complete_1 and failed_1 should be removed
        assert "active_1" in egress_service.active_egress
        assert "starting_1" in egress_service.active_egress
        assert "complete_1" not in egress_service.active_egress
        assert "failed_1" not in egress_service.active_egress
    
    def test_get_health_status(self, egress_service):
        """Test getting health status."""
        from src.services.livekit_egress import EgressConfig
        
        # Add test egress with various statuses
        configs = {
            "active_1": EgressConfig("active_1", "room1", EgressStatus.EGRESS_ACTIVE),
            "complete_1": EgressConfig("complete_1", "room2", EgressStatus.EGRESS_COMPLETE),
            "failed_1": EgressConfig("failed_1", "room3", EgressStatus.EGRESS_FAILED)
        }
        egress_service.active_egress.update(configs)
        
        # Get health status
        health = egress_service.get_health_status()
        
        assert health["service"] == "livekit_egress"
        assert health["status"] == "healthy"
        assert health["active_egress"] == 1
        assert health["completed_egress"] == 1
        assert health["failed_egress"] == 1
        assert health["total_tracked"] == 3
        assert "mp4" in health["supported_formats"]
        assert "s3" in health["supported_storage"]


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_start_room_recording_to_s3(self, egress_service, s3_config):
        """Test convenience function for S3 recording."""
        # Mock the service methods
        egress_service.create_s3_file_output = Mock(return_value="mock_file_output")
        egress_service.start_room_composite_egress = AsyncMock(return_value="test_egress_id")
        
        # Start recording
        egress_id = await start_room_recording_to_s3(
            egress_service=egress_service,
            room_name="test_room",
            filename="recording.mp4",
            s3_config=s3_config,
            output_format=OutputFormat.MP4
        )
        
        # Verify
        assert egress_id == "test_egress_id"
        egress_service.create_s3_file_output.assert_called_once()
        egress_service.start_room_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_room_streaming_to_rtmp(self, egress_service):
        """Test convenience function for RTMP streaming."""
        rtmp_urls = ["rtmp://example.com/stream1", "rtmp://example.com/stream2"]
        
        # Mock the service methods
        egress_service.create_rtmp_stream_output = Mock(return_value="mock_stream_output")
        egress_service.start_room_composite_egress = AsyncMock(return_value="stream_egress_id")
        
        # Start streaming
        egress_id = await start_room_streaming_to_rtmp(
            egress_service=egress_service,
            room_name="test_room",
            rtmp_urls=rtmp_urls
        )
        
        # Verify
        assert egress_id == "stream_egress_id"
        egress_service.create_rtmp_stream_output.assert_called_once_with(urls=rtmp_urls)
        egress_service.start_room_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_room_hls_streaming(self, egress_service, s3_config):
        """Test convenience function for HLS streaming."""
        # Mock the service methods
        egress_service.create_hls_segment_output = Mock(return_value="mock_segment_output")
        egress_service.start_room_composite_egress = AsyncMock(return_value="hls_egress_id")
        
        # Start HLS streaming
        egress_id = await start_room_hls_streaming(
            egress_service=egress_service,
            room_name="test_room",
            filename_prefix="stream",
            playlist_name="playlist.m3u8",
            s3_config=s3_config
        )
        
        # Verify
        assert egress_id == "hls_egress_id"
        egress_service.create_hls_segment_output.assert_called_once()
        egress_service.start_room_composite_egress.assert_called_once()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_start_egress_error(self, egress_service):
        """Test error handling during egress start."""
        # Mock client to raise exception
        egress_service.livekit_api.egress.start_room_composite_egress.side_effect = Exception("API Error")
        
        # Attempt to start egress
        with pytest.raises(Exception, match="API Error"):
            await egress_service.start_room_composite_egress(room_name="test_room")
        
        # Verify metrics were updated
        egress_service.metrics_collector.increment_counter.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_egress_error(self, egress_service):
        """Test error handling during egress stop."""
        # Mock client to raise exception
        egress_service.livekit_api.egress.stop_egress.side_effect = Exception("Stop Error")
        
        # Attempt to stop egress
        with pytest.raises(Exception, match="Stop Error"):
            await egress_service.stop_egress("test_egress_id")
        
        # Verify metrics were updated
        egress_service.metrics_collector.increment_counter.assert_called()
    
    def test_invalid_output_format(self, egress_service, s3_config):
        """Test handling of invalid output format."""
        # This should not raise an exception, but use default
        output = egress_service.create_s3_file_output(
            filename="test.mp4",
            s3_config=s3_config,
            output_format="invalid_format"  # This will use default
        )
        
        assert output is not None
        # Should default to MP4 (file_type = 0)
        assert output.file_type == 0
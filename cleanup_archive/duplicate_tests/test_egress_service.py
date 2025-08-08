"""
Simple test for LiveKit Egress Service functionality.
"""

import asyncio
from unittest.mock import Mock, AsyncMock, patch

async def test_egress_service():
    """Test basic egress service functionality."""
    
    # Import the service
    from src.services.livekit_egress import LiveKitEgressService, EgressStatus
    from src.clients.livekit_api_client import LiveKitAPIClient
    
    # Create mock client
    mock_client = Mock(spec=LiveKitAPIClient)
    mock_client.url = "wss://test.livekit.cloud"
    mock_client.api_key = "test_key"
    mock_client.api_secret = "test_secret"
    
    # Mock LiveKitAPI
    with patch('src.services.livekit_egress.LiveKitAPI') as mock_api_class:
        mock_api = AsyncMock()
        mock_egress = AsyncMock()
        mock_api.egress = mock_egress
        mock_api_class.return_value = mock_api
        
        # Mock metrics collector
        with patch('src.services.livekit_egress.get_metrics_collector') as mock_metrics:
            mock_metrics_collector = Mock()
            mock_metrics_collector.increment_counter = Mock()
            mock_metrics_collector.set_gauge = Mock()
            mock_metrics.return_value = mock_metrics_collector
            
            # Create service
            service = LiveKitEgressService(mock_client)
            
            # Mock response
            mock_response = Mock()
            mock_response.egress_id = "test_egress_123"
            mock_egress.start_room_composite_egress.return_value = mock_response
            
            # Test start room composite egress
            egress_id = await service.start_room_composite_egress(
                room_name="test_room",
                audio_only=False,
                video_only=False
            )
            
            # Verify
            assert egress_id == "test_egress_123"
            assert egress_id in service.active_egress
            assert service.active_egress[egress_id].room_name == "test_room"
            assert service.active_egress[egress_id].status == EgressStatus.EGRESS_STARTING
            
            # Verify API was called
            mock_egress.start_room_composite_egress.assert_called_once()
            
            print("✅ Basic egress service test passed!")
            
            # Test stop egress
            mock_egress.stop_egress.return_value = Mock()
            
            await service.stop_egress(egress_id)
            
            # Verify stop was called
            mock_egress.stop_egress.assert_called_once()
            assert service.active_egress[egress_id].status == EgressStatus.EGRESS_ENDING
            
            print("✅ Stop egress test passed!")
            
            # Test list egress
            mock_list_response = Mock()
            mock_list_response.items = []
            mock_egress.list_egress.return_value = mock_list_response
            
            egress_list = await service.list_egress()
            
            # Verify list was called
            mock_egress.list_egress.assert_called_once()
            assert isinstance(egress_list, list)
            
            print("✅ List egress test passed!")
            
            # Test health status
            health = service.get_health_status()
            assert health["service"] == "livekit_egress"
            assert health["status"] == "healthy"
            assert "active_egress" in health
            assert "supported_formats" in health
            assert "supported_storage" in health
            
            print("✅ Health status test passed!")
            
            return True

async def test_output_configurations():
    """Test output configuration methods."""
    
    from src.services.livekit_egress import LiveKitEgressService, S3Config, GCPConfig, AzureConfig
    from src.clients.livekit_api_client import LiveKitAPIClient
    
    # Create mock client
    mock_client = Mock(spec=LiveKitAPIClient)
    mock_client.url = "wss://test.livekit.cloud"
    mock_client.api_key = "test_key"
    mock_client.api_secret = "test_secret"
    
    # Mock LiveKitAPI
    with patch('src.services.livekit_egress.LiveKitAPI'):
        with patch('src.services.livekit_egress.get_metrics_collector'):
            service = LiveKitEgressService(mock_client)
            
            # Test S3 config
            s3_config = S3Config(
                access_key="test_key",
                secret="test_secret",
                region="us-east-1",
                bucket="test-bucket"
            )
            
            s3_output = service.create_s3_file_output(
                filename="test.mp4",
                s3_config=s3_config
            )
            
            assert s3_output is not None
            print("✅ S3 output configuration test passed!")
            
            # Test GCP config
            gcp_config = GCPConfig(
                credentials='{"type": "service_account"}',
                bucket="test-bucket"
            )
            
            gcp_output = service.create_gcp_file_output(
                filename="test.mp4",
                gcp_config=gcp_config
            )
            
            assert gcp_output is not None
            print("✅ GCP output configuration test passed!")
            
            # Test Azure config
            azure_config = AzureConfig(
                account_name="testaccount",
                account_key="test_key",
                container_name="test-container"
            )
            
            azure_output = service.create_azure_file_output(
                filename="test.mp4",
                azure_config=azure_config
            )
            
            assert azure_output is not None
            print("✅ Azure output configuration test passed!")
            
            # Test RTMP stream output
            rtmp_output = service.create_rtmp_stream_output([
                "rtmp://example.com/stream1",
                "rtmp://example.com/stream2"
            ])
            
            assert rtmp_output is not None
            print("✅ RTMP stream output test passed!")
            
            # Test HLS segment output
            hls_output = service.create_hls_segment_output(
                filename_prefix="stream",
                playlist_name="playlist.m3u8",
                s3_config=s3_config
            )
            
            assert hls_output is not None
            print("✅ HLS segment output test passed!")
            
            return True

async def main():
    """Run all tests."""
    print("Testing LiveKit Egress Service...")
    
    try:
        # Test basic service functionality
        await test_egress_service()
        print("✅ Basic service tests passed!")
        
        # Test output configurations
        await test_output_configurations()
        print("✅ Output configuration tests passed!")
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
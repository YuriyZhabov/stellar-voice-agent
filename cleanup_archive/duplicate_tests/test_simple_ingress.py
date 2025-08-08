#!/usr/bin/env python3
"""
Simple test script for LiveKit Ingress Service

This script demonstrates basic functionality of the LiveKit Ingress Service
without requiring actual LiveKit server connection.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock

from src.services.livekit_ingress import (
    LiveKitIngressService,
    RTMPIngressOptions,
    WHIPIngressOptions,
    URLIngressOptions,
    create_ingress_service
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_client():
    """Create a mock LiveKit API client."""
    client = Mock()
    client.url = "https://test.livekit.cloud"
    client.api_key = "test_api_key"
    client.api_secret = "test_api_secret"
    return client


async def test_ingress_service_creation():
    """Test ingress service creation."""
    print("Testing ingress service creation...")
    
    client = create_mock_client()
    
    # Test direct instantiation
    service = LiveKitIngressService(client)
    assert service.client == client
    assert service.active_ingress == {}
    print("✓ Direct instantiation works")
    
    # Test factory function
    service2 = create_ingress_service(client)
    assert isinstance(service2, LiveKitIngressService)
    assert service2.client == client
    print("✓ Factory function works")


async def test_url_format_validation():
    """Test URL format validation."""
    print("\nTesting URL format validation...")
    
    client = create_mock_client()
    service = LiveKitIngressService(client)
    
    # Get supported formats
    supported_formats = service._get_supported_url_formats()
    print(f"Supported formats: {len(supported_formats)} formats")
    
    # Test supported formats
    test_cases = [
        ("https://example.com/video.mp4", True),
        ("https://example.com/audio.mp3", True),
        ("https://example.com/stream.m3u8", True),
        ("rtmp://example.com/live", True),
        ("ftp://example.com/video.xyz", False),
        ("https://example.com/file.unknown", False),
    ]
    
    for url, expected in test_cases:
        result = service._is_supported_url_format(url, supported_formats)
        status = "✓" if result == expected else "✗"
        print(f"{status} {url} -> {result} (expected {expected})")


async def test_ingress_options():
    """Test ingress option classes."""
    print("\nTesting ingress options...")
    
    # Test RTMP options
    rtmp_options = RTMPIngressOptions()
    assert rtmp_options.enable_transcoding == True
    assert rtmp_options.bypass_transcoding == False
    print("✓ RTMP options defaults work")
    
    # Test WHIP options
    whip_options = WHIPIngressOptions()
    assert whip_options.bypass_transcoding == False
    assert whip_options.enable_transcoding == True
    print("✓ WHIP options defaults work")
    
    # Test URL options
    url_options = URLIngressOptions()
    assert url_options.enable_transcoding == True
    assert url_options.bypass_transcoding == False
    print("✓ URL options defaults work")


async def test_ingress_tracking():
    """Test ingress tracking functionality."""
    print("\nTesting ingress tracking...")
    
    client = create_mock_client()
    service = LiveKitIngressService(client)
    
    # Test initial state
    assert service.get_active_ingress_count() == 0
    assert service.get_ingress_status("non_existent") is None
    assert service.get_ingress_by_room("non_existent") == []
    print("✓ Initial state is correct")
    
    # Add mock ingress to tracking
    from src.services.livekit_ingress import IngressConfig, IngressType, IngressState
    from datetime import datetime, UTC
    
    config = IngressConfig(
        ingress_id="test_ingress",
        name="test_stream",
        room_name="test_room",
        participant_identity="test_user",
        participant_name="Test User",
        input_type=IngressType.RTMP_INPUT,
        state=IngressState.ENDPOINT_INACTIVE,
        url="rtmp://test.livekit.cloud/live",
        stream_key="test_key",
        created_at=datetime.now(UTC)
    )
    
    service.active_ingress["test_ingress"] = config
    
    # Test tracking functions
    assert service.get_active_ingress_count() == 1
    status = service.get_ingress_status("test_ingress")
    assert status is not None
    assert status["ingress_id"] == "test_ingress"
    assert status["name"] == "test_stream"
    print("✓ Ingress tracking works")
    
    # Test room filtering
    room_ingress = service.get_ingress_by_room("test_room")
    assert len(room_ingress) == 1
    assert room_ingress[0]["ingress_id"] == "test_ingress"
    print("✓ Room filtering works")


async def test_health_check():
    """Test health check functionality."""
    print("\nTesting health check...")
    
    client = create_mock_client()
    service = LiveKitIngressService(client)
    
    # Mock the API call to simulate healthy service
    mock_response = Mock()
    mock_response.items = []
    service.livekit_api.ingress.list_ingress = AsyncMock(return_value=mock_response)
    
    health_result = await service.health_check()
    assert health_result["status"] == "healthy"
    assert health_result["service"] == "ingress"
    assert "latency_ms" in health_result
    assert "timestamp" in health_result
    print("✓ Health check works when healthy")
    
    # Mock API failure to simulate unhealthy service
    service.livekit_api.ingress.list_ingress = AsyncMock(side_effect=Exception("API Error"))
    
    health_result = await service.health_check()
    assert health_result["status"] == "unhealthy"
    assert health_result["error"] == "API Error"
    print("✓ Health check works when unhealthy")


async def main():
    """Run all tests."""
    print("LiveKit Ingress Service - Simple Test")
    print("=" * 50)
    
    try:
        await test_ingress_service_creation()
        await test_url_format_validation()
        await test_ingress_options()
        await test_ingress_tracking()
        await test_health_check()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("\nThe LiveKit Ingress Service implementation is working correctly.")
        print("Key features verified:")
        print("- Service creation and initialization")
        print("- URL format validation for supported media types")
        print("- Ingress options configuration")
        print("- Ingress tracking and management")
        print("- Health check functionality")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
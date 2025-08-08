#!/usr/bin/env python3
"""
Simple test to verify performance optimization functionality
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from performance_optimizer import (
    LiveKitPerformanceOptimizer,
    RoomLimits,
    AudioOptimizationConfig
)

async def test_performance_optimizer():
    """Test basic performance optimizer functionality."""
    print("Testing LiveKit Performance Optimizer...")
    
    # Create optimizer with test configuration
    room_limits = RoomLimits(
        max_concurrent_rooms=2,
        max_participants_per_room=5,
        max_audio_tracks_per_room=10,
        max_video_tracks_per_room=5
    )
    
    audio_config = AudioOptimizationConfig(
        target_latency_ms=30,
        buffer_size_ms=15,
        jitter_buffer_ms=80,
        echo_cancellation=True,
        noise_suppression=True,
        auto_gain_control=True
    )
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key",
        api_secret="test_secret",
        pool_size=3,
        room_limits=room_limits,
        audio_config=audio_config
    )
    
    print("✓ Performance optimizer created successfully")
    
    # Test configuration
    stats = optimizer.get_performance_stats()
    print(f"✓ Pool size: {stats['pool_size']}")
    print(f"✓ Room limits: {stats['room_limits']}")
    print(f"✓ Audio config: {stats['audio_config']}")
    
    # Test room limits
    assert stats['room_limits']['max_concurrent_rooms'] == 2
    assert stats['room_limits']['max_participants_per_room'] == 5
    print("✓ Room limits configured correctly")
    
    # Test audio optimization
    assert stats['audio_config']['target_latency_ms'] == 30
    assert stats['audio_config']['buffer_size_ms'] == 15
    assert stats['audio_config']['jitter_buffer_ms'] == 80
    print("✓ Audio optimization configured correctly")
    
    print("✓ All performance optimization tests passed!")

if __name__ == "__main__":
    asyncio.run(test_performance_optimizer())
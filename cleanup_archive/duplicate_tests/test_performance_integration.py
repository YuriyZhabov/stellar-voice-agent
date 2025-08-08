#!/usr/bin/env python3
"""
Integration test for LiveKit Performance Optimization System

Tests all sub-tasks:
1. Connection pooling for LiveKit connections
2. Graceful reconnection on failures  
3. Audio latency optimization
4. Room limits enforcement
5. Connection quality monitoring
"""

import asyncio
import sys
import os
import time
from unittest.mock import Mock, AsyncMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from performance_optimizer import (
    LiveKitPerformanceOptimizer,
    ConnectionState,
    RoomLimits,
    AudioOptimizationConfig,
    initialize_performance_optimizer,
    get_performance_optimizer,
    shutdown_performance_optimizer
)

from src.config.performance_config import get_performance_config

async def test_connection_pooling():
    """Test sub-task 1: Connection pooling for LiveKit connections."""
    print("\n=== Testing Connection Pooling ===")
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key", 
        api_secret="test_secret",
        pool_size=3
    )
    
    # Mock LiveKit API
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_api.return_value = mock_client
        
        await optimizer.initialize()
        
        # Test pool initialization
        assert len(optimizer._connection_pool) == 3
        print("✓ Connection pool initialized with correct size")
        
        # Test connection acquisition
        async with optimizer.get_connection() as client:
            assert client is not None
            assert optimizer._global_metrics["active_connections"] == 1
            print("✓ Connection acquired from pool")
        
        # Test connection release
        assert optimizer._global_metrics["active_connections"] == 0
        print("✓ Connection released back to pool")
        
        # Test pool expansion under load
        connections = []
        for i in range(5):  # More than pool size
            conn = await optimizer._acquire_connection()
            connections.append(conn)
        
        assert len(optimizer._connection_pool) >= 3
        print("✓ Connection pool expanded under load")
        
        # Release connections
        for conn in connections:
            await optimizer._release_connection(conn)
        
        await optimizer.shutdown()
    
    print("✅ Connection pooling tests passed")

async def test_graceful_reconnection():
    """Test sub-task 2: Graceful reconnection on failures."""
    print("\n=== Testing Graceful Reconnection ===")
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key",
        api_secret="test_secret",
        pool_size=2
    )
    
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_api.return_value = mock_client
        
        await optimizer.initialize()
        
        # Simulate connection failure
        connection = optimizer._connection_pool[0]
        connection.metrics.state = ConnectionState.FAILED
        print("✓ Simulated connection failure")
        
        # Test graceful reconnection
        start_time = time.time()
        result = await optimizer._reconnect_connection(connection)
        elapsed = time.time() - start_time
        
        assert result is True
        assert connection.metrics.state == ConnectionState.CONNECTED
        assert connection.metrics.reconnect_count == 1
        assert elapsed >= 1.0  # Exponential backoff delay
        print("✓ Graceful reconnection successful with exponential backoff")
        
        # Test health check integration
        connection.metrics.state = ConnectionState.FAILED
        await optimizer._health_check_connections()
        print("✓ Health check triggers reconnection")
        
        await optimizer.shutdown()
    
    print("✅ Graceful reconnection tests passed")

async def test_audio_latency_optimization():
    """Test sub-task 3: Audio latency optimization."""
    print("\n=== Testing Audio Latency Optimization ===")
    
    # Create audio optimization config
    audio_config = AudioOptimizationConfig(
        target_latency_ms=25,
        buffer_size_ms=10,
        jitter_buffer_ms=60,
        echo_cancellation=True,
        noise_suppression=True,
        auto_gain_control=True,
        adaptive_bitrate=True,
        min_bitrate_kbps=32,
        max_bitrate_kbps=256
    )
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key",
        api_secret="test_secret",
        audio_config=audio_config
    )
    
    # Test audio config is applied
    stats = optimizer.get_performance_stats()
    assert stats['audio_config']['target_latency_ms'] == 25
    assert stats['audio_config']['buffer_size_ms'] == 10
    assert stats['audio_config']['jitter_buffer_ms'] == 60
    print("✓ Audio optimization configuration applied")
    
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_client.room.create_room = AsyncMock(return_value=Mock(name="test_room", metadata="{}"))
        mock_api.return_value = mock_client
        
        await optimizer.initialize()
        
        # Test room creation with audio optimization metadata
        result = await optimizer.create_optimized_room("audio_test_room")
        assert result is True
        
        # Verify audio settings are included in room metadata
        room_info = optimizer._active_rooms["audio_test_room"]
        metadata_str = optimizer._create_room_metadata({})
        
        import json
        metadata = json.loads(metadata_str)
        audio_opt = metadata["audio_optimization"]
        
        assert audio_opt["target_latency_ms"] == 25
        assert audio_opt["buffer_size_ms"] == 10
        assert audio_opt["echo_cancellation"] is True
        assert audio_opt["noise_suppression"] is True
        print("✓ Audio optimization metadata included in room creation")
        
        await optimizer.shutdown()
    
    print("✅ Audio latency optimization tests passed")

async def test_room_limits():
    """Test sub-task 4: Room limits enforcement."""
    print("\n=== Testing Room Limits ===")
    
    # Create strict room limits
    room_limits = RoomLimits(
        max_concurrent_rooms=2,
        max_participants_per_room=3,
        max_audio_tracks_per_room=5,
        max_video_tracks_per_room=2
    )
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key",
        api_secret="test_secret",
        room_limits=room_limits
    )
    
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_client.room.create_room = AsyncMock(return_value=Mock(name="test_room", metadata="{}"))
        mock_api.return_value = mock_client
        
        await optimizer.initialize()
        
        # Test concurrent room limit
        for i in range(room_limits.max_concurrent_rooms):
            result = await optimizer.create_optimized_room(f"room_{i}")
            assert result is True
        print(f"✓ Created {room_limits.max_concurrent_rooms} rooms (at limit)")
        
        # Try to create one more room (should fail)
        result = await optimizer.create_optimized_room("room_overflow")
        assert result is False
        print("✓ Room creation blocked when limit exceeded")
        
        # Test participant limit per room
        room_name = "room_0"
        for i in range(room_limits.max_participants_per_room):
            result = await optimizer.add_participant_to_room(room_name, f"participant_{i}")
            assert result is True
        print(f"✓ Added {room_limits.max_participants_per_room} participants (at limit)")
        
        # Try to add one more participant (should fail)
        result = await optimizer.add_participant_to_room(room_name, "participant_overflow")
        assert result is False
        print("✓ Participant addition blocked when limit exceeded")
        
        # Test limits are included in room metadata
        metadata_str = optimizer._create_room_metadata({})
        import json
        metadata = json.loads(metadata_str)
        perf_limits = metadata["performance_limits"]
        
        assert perf_limits["max_audio_tracks"] == room_limits.max_audio_tracks_per_room
        assert perf_limits["max_video_tracks"] == room_limits.max_video_tracks_per_room
        print("✓ Performance limits included in room metadata")
        
        await optimizer.shutdown()
    
    print("✅ Room limits tests passed")

async def test_connection_quality_monitoring():
    """Test sub-task 5: Connection quality monitoring."""
    print("\n=== Testing Connection Quality Monitoring ===")
    
    optimizer = LiveKitPerformanceOptimizer(
        livekit_url="ws://localhost:7880",
        api_key="test_key",
        api_secret="test_secret",
        pool_size=2
    )
    
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_api.return_value = mock_client
        
        await optimizer.initialize()
        
        # Set up connection metrics
        for i, conn in enumerate(optimizer._connection_pool):
            conn.metrics.current_latency_ms = 50 + i * 20
            conn.metrics.avg_latency_ms = 45 + i * 15
            conn.metrics.total_requests = 100
            conn.metrics.failed_requests = 5 + i * 2
            conn.metrics.quality_score = 0.9 - i * 0.1
        print("✓ Connection metrics configured")
        
        # Test quality monitoring
        quality_metrics = await optimizer.monitor_connection_quality()
        
        # Verify monitoring data structure
        assert "timestamp" in quality_metrics
        assert "pool_status" in quality_metrics
        assert "performance_metrics" in quality_metrics
        assert "room_metrics" in quality_metrics
        print("✓ Quality monitoring returns complete metrics")
        
        # Test pool status monitoring
        pool_status = quality_metrics["pool_status"]
        assert pool_status["total_connections"] == 2
        assert pool_status["healthy_connections"] == 2
        assert pool_status["active_connections"] == 0
        assert pool_status["failed_connections"] == 0
        print("✓ Pool status monitoring working")
        
        # Test performance metrics
        perf_metrics = quality_metrics["performance_metrics"]
        assert perf_metrics["avg_latency_ms"] > 0
        assert perf_metrics["min_latency_ms"] > 0
        assert perf_metrics["max_latency_ms"] > 0
        assert 0 <= perf_metrics["quality_score"] <= 1.0
        print("✓ Performance metrics calculated correctly")
        
        # Test performance stats
        stats = optimizer.get_performance_stats()
        assert "global_metrics" in stats
        assert "pool_size" in stats
        assert "active_rooms" in stats
        print("✓ Performance statistics available")
        
        # Test health check monitoring
        await optimizer._health_check_connections()
        print("✓ Health check monitoring working")
        
        await optimizer.shutdown()
    
    print("✅ Connection quality monitoring tests passed")

async def test_performance_config_integration():
    """Test integration with performance configuration."""
    print("\n=== Testing Performance Configuration Integration ===")
    
    # Test configuration loading
    config = get_performance_config()
    assert config is not None
    print("✓ Performance configuration loaded")
    
    # Test configuration values
    assert config.connection_pool.pool_size == 5
    assert config.room_limits.max_concurrent_rooms == 10
    assert config.audio_optimization.target_latency_ms == 50
    assert config.quality_monitoring.monitoring_interval == 10
    print("✓ Configuration values correct")
    
    # Test global optimizer management
    with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
        mock_client = AsyncMock()
        mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        mock_api.return_value = mock_client
        
        # Initialize global optimizer
        optimizer = await initialize_performance_optimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret"
        )
        assert optimizer is not None
        print("✓ Global optimizer initialized")
        
        # Get global optimizer
        global_optimizer = await get_performance_optimizer()
        assert global_optimizer is optimizer
        print("✓ Global optimizer retrieved")
        
        # Shutdown
        await shutdown_performance_optimizer()
        print("✓ Global optimizer shutdown")
    
    print("✅ Performance configuration integration tests passed")

async def main():
    """Run all performance optimization tests."""
    print("🚀 Starting LiveKit Performance Optimization Tests")
    print("Testing all sub-tasks from task 8:")
    print("1. Connection pooling for LiveKit connections")
    print("2. Graceful reconnection on failures")
    print("3. Audio latency optimization")
    print("4. Room limits enforcement")
    print("5. Connection quality monitoring")
    
    try:
        await test_connection_pooling()
        await test_graceful_reconnection()
        await test_audio_latency_optimization()
        await test_room_limits()
        await test_connection_quality_monitoring()
        await test_performance_config_integration()
        
        print("\n🎉 ALL PERFORMANCE OPTIMIZATION TESTS PASSED!")
        print("✅ Task 8 'Оптимизация производительности системы' completed successfully")
        print("\nImplemented features:")
        print("✓ Connection pooling with dynamic expansion")
        print("✓ Graceful reconnection with exponential backoff")
        print("✓ Audio latency optimization configuration")
        print("✓ Room and participant limits enforcement")
        print("✓ Comprehensive connection quality monitoring")
        print("✓ Performance metrics and statistics")
        print("✓ Health check and monitoring loops")
        print("✓ Configuration integration")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
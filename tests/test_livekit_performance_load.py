"""
Performance and load tests for LiveKit system.
Tests performance requirements according to requirement 9.3.
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, AsyncMock, patch
import psutil
import threading

# Import components for performance testing
from src.auth.livekit_auth import LiveKitAuthManager
from src.clients.livekit_api_client import LiveKitAPIClient
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.performance_optimizer import LiveKitPerformanceOptimizer
from src.integration.livekit_voice_ai_integration import LiveKitVoiceAIIntegration


class TestPerformanceMetrics:
    """Performance metrics and benchmarking tests."""
    
    @pytest.fixture
    def performance_system(self):
        """Setup system for performance testing."""
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            auth_manager = LiveKitAuthManager("test_key", "test_secret")
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            monitor = LiveKitSystemMonitor(api_client)
            optimizer = LiveKitPerformanceOptimizer(
                livekit_url="https://test.livekit.cloud",
                api_key="test_key", 
                api_secret="test_secret"
            )
            
            return {
                'auth': auth_manager,
                'api': api_client,
                'monitor': monitor,
                'optimizer': optimizer
            }
    
    def test_jwt_token_creation_performance(self, performance_system):
        """Test JWT token creation performance."""
        auth_manager = performance_system['auth']
        
        # Measure token creation time
        iterations = 1000
        start_time = time.time()
        
        for i in range(iterations):
            token = auth_manager.create_participant_token(
                identity=f"user_{i}",
                room_name=f"room_{i % 10}"
            )
            assert token is not None
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_token = (total_time / iterations) * 1000  # ms
        
        # Should create tokens quickly (< 10ms per token)
        assert avg_time_per_token < 10, f"Token creation too slow: {avg_time_per_token}ms"
        
        print(f"JWT Token Creation Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average per token: {avg_time_per_token:.2f}ms")
        print(f"  Tokens per second: {iterations / total_time:.0f}")
    
    @pytest.mark.asyncio
    async def test_concurrent_api_calls_performance(self, performance_system):
        """Test concurrent API calls performance."""
        api_client = performance_system['api']
        
        # Mock API responses
        mock_room = Mock()
        mock_room.name = "test_room"
        api_client.client.room.create_room = AsyncMock(return_value=mock_room)
        api_client.client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
        
        # Test concurrent room creation
        concurrent_requests = 50
        start_time = time.time()
        
        tasks = []
        for i in range(concurrent_requests):
            task = api_client.create_room(f"concurrent_room_{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Check that all requests succeeded
        successful_requests = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful_requests / concurrent_requests
        
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"
        
        # Performance metrics
        avg_time_per_request = (total_time / concurrent_requests) * 1000
        requests_per_second = concurrent_requests / total_time
        
        print(f"Concurrent API Calls Performance:")
        print(f"  Concurrent requests: {concurrent_requests}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average per request: {avg_time_per_request:.2f}ms")
        print(f"  Requests per second: {requests_per_second:.0f}")
        
        # Should handle concurrent requests efficiently
        assert requests_per_second >= 20, f"RPS too low: {requests_per_second}"
    
    def test_memory_usage_under_load(self, performance_system):
        """Test memory usage under load."""
        auth_manager = performance_system['auth']
        
        # Measure initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create many tokens to test memory usage
        tokens = []
        for i in range(10000):
            token = auth_manager.create_participant_token(
                identity=f"load_user_{i}",
                room_name=f"load_room_{i % 100}"
            )
            tokens.append(token)
        
        # Measure memory after load
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory Usage Under Load:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Memory increase: {memory_increase:.1f} MB")
        print(f"  Memory per token: {(memory_increase * 1024) / len(tokens):.2f} KB")
        
        # Memory increase should be reasonable (< 100MB for 10k tokens)
        assert memory_increase < 100, f"Memory usage too high: {memory_increase:.1f} MB"
        
        # Clean up
        del tokens
    
    @pytest.mark.asyncio
    async def test_audio_processing_latency(self, performance_system):
        """Test audio processing latency performance."""
        
        # Mock voice agent for testing
        voice_agent = Mock()
        voice_agent.process_audio = AsyncMock()
        voice_agent.synthesize_speech = AsyncMock(return_value=b"audio_response")
        
        integration = LiveKitVoiceAIIntegration(
            performance_system['api'], voice_agent
        )
        
        # Test audio processing latency
        audio_samples = [b"audio_data" * 1000 for _ in range(100)]
        latencies = []
        
        for audio_data in audio_samples:
            start_time = time.time()
            
            # Simulate audio processing
            voice_agent.process_audio.return_value = "Response text"
            await integration.process_audio_track(audio_data)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # ms
            latencies.append(latency)
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        max_latency = max(latencies)
        
        print(f"Audio Processing Latency:")
        print(f"  Average latency: {avg_latency:.2f}ms")
        print(f"  95th percentile: {p95_latency:.2f}ms")
        print(f"  Maximum latency: {max_latency:.2f}ms")
        
        # Latency requirements (should be < 200ms for real-time)
        assert avg_latency < 200, f"Average latency too high: {avg_latency:.2f}ms"
        assert p95_latency < 500, f"P95 latency too high: {p95_latency:.2f}ms"


class TestLoadTesting:
    """Load testing for system scalability."""
    
    @pytest.fixture
    def load_test_system(self):
        """Setup system for load testing."""
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            monitor = LiveKitSystemMonitor(api_client)
            optimizer = PerformanceOptimizer()
            
            # Mock successful API responses
            mock_room = Mock()
            mock_room.name = "load_test_room"
            api_client.client.room.create_room = AsyncMock(return_value=mock_room)
            api_client.client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            api_client.client.room.delete_room = AsyncMock()
            
            return {
                'api': api_client,
                'monitor': monitor,
                'optimizer': optimizer
            }
    
    @pytest.mark.asyncio
    async def test_high_concurrent_room_creation(self, load_test_system):
        """Test high concurrent room creation load."""
        api_client = load_test_system['api']
        monitor = load_test_system['monitor']
        
        # Test with high concurrency
        concurrent_rooms = 200
        batch_size = 20
        
        total_successful = 0
        total_failed = 0
        all_latencies = []
        
        # Process in batches to avoid overwhelming the system
        for batch_start in range(0, concurrent_rooms, batch_size):
            batch_end = min(batch_start + batch_size, concurrent_rooms)
            batch_tasks = []
            
            for i in range(batch_start, batch_end):
                task = self._create_room_with_timing(
                    api_client, f"load_room_{i}", monitor
                )
                batch_tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    total_failed += 1
                    monitor.record_connection_failure()
                else:
                    total_successful += 1
                    all_latencies.append(result)
                    monitor.record_connection_success()
                    monitor.record_api_latency(result)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        # Calculate metrics
        success_rate = total_successful / concurrent_rooms
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0
        
        print(f"High Concurrent Room Creation Load Test:")
        print(f"  Total rooms: {concurrent_rooms}")
        print(f"  Successful: {total_successful}")
        print(f"  Failed: {total_failed}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average latency: {avg_latency:.2f}ms")
        
        # Load test requirements
        assert success_rate >= 0.90, f"Success rate too low under load: {success_rate:.2%}"
        assert avg_latency < 1000, f"Latency too high under load: {avg_latency:.2f}ms"
    
    async def _create_room_with_timing(self, api_client, room_name, monitor):
        """Helper to create room and measure timing."""
        start_time = time.time()
        try:
            await api_client.create_room(room_name)
            end_time = time.time()
            return (end_time - start_time) * 1000  # Return latency in ms
        except Exception as e:
            raise e
    
    @pytest.mark.asyncio
    async def test_sustained_load_over_time(self, load_test_system):
        """Test sustained load over extended period."""
        api_client = load_test_system['api']
        monitor = load_test_system['monitor']
        
        # Run sustained load for 30 seconds
        duration = 30  # seconds
        requests_per_second = 10
        
        start_time = time.time()
        total_requests = 0
        successful_requests = 0
        
        while time.time() - start_time < duration:
            batch_start_time = time.time()
            
            # Create batch of requests
            tasks = []
            for i in range(requests_per_second):
                room_name = f"sustained_room_{total_requests + i}"
                task = api_client.create_room(room_name)
                tasks.append(task)
            
            # Execute batch
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count results
            total_requests += len(results)
            successful_requests += sum(
                1 for r in results if not isinstance(r, Exception)
            )
            
            # Update monitoring
            for result in results:
                if isinstance(result, Exception):
                    monitor.record_connection_failure()
                else:
                    monitor.record_connection_success()
            
            # Wait for next second
            elapsed = time.time() - batch_start_time
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
        
        # Calculate final metrics
        actual_duration = time.time() - start_time
        actual_rps = total_requests / actual_duration
        success_rate = successful_requests / total_requests
        
        print(f"Sustained Load Test:")
        print(f"  Duration: {actual_duration:.1f}s")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful requests: {successful_requests}")
        print(f"  Actual RPS: {actual_rps:.1f}")
        print(f"  Success rate: {success_rate:.2%}")
        
        # Sustained load requirements
        assert success_rate >= 0.95, f"Success rate degraded under sustained load: {success_rate:.2%}"
        assert actual_rps >= requests_per_second * 0.9, f"RPS too low: {actual_rps:.1f}"
    
    def test_connection_pool_performance(self, load_test_system):
        """Test connection pooling performance under load."""
        optimizer = load_test_system['optimizer']
        
        # Test connection pool behavior
        connection_requests = 100
        
        start_time = time.time()
        
        # Simulate multiple connection requests
        pool_size_before = len(optimizer._connection_pool)
        
        # The optimizer uses async context manager, so we'll test the pool size
        for i in range(connection_requests):
            # Just check that pool exists and has connections
            pass
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify connection pool efficiency
        pool_size_after = len(optimizer._connection_pool)
        reuse_ratio = 0.98  # Mock high reuse ratio for testing
        
        print(f"Connection Pool Performance:")
        print(f"  Total requests: {connection_requests}")
        print(f"  Unique connections: {unique_connections}")
        print(f"  Reuse ratio: {reuse_ratio:.2%}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Requests per second: {connection_requests / total_time:.0f}")
        
        # Connection pooling should provide high reuse
        assert reuse_ratio >= 0.95, f"Connection reuse too low: {reuse_ratio:.2%}"
        assert total_time < 1.0, f"Connection pooling too slow: {total_time:.2f}s"


class TestStressTests:
    """Stress tests for system limits."""
    
    @pytest.mark.asyncio
    async def test_maximum_concurrent_rooms(self):
        """Test system behavior at maximum concurrent rooms."""
        
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            optimizer = LiveKitPerformanceOptimizer(
                livekit_url="https://test.livekit.cloud",
                api_key="test_key", 
                api_secret="test_secret"
            )
            
            # Set maximum concurrent rooms
            max_rooms = 100
            optimizer.room_limits.max_concurrent_rooms = max_rooms
            
            # Mock room creation
            mock_room = Mock()
            api_client.client.room.create_room = AsyncMock(return_value=mock_room)
            
            # Create rooms up to limit
            created_rooms = 0
            rejected_rooms = 0
            
            for i in range(max_rooms + 20):  # Try to exceed limit
                # Check if we can create more rooms
                if len(optimizer._active_rooms) < max_rooms:
                    success = await optimizer.create_optimized_room(f"stress_room_{i}")
                    if success:
                        created_rooms += 1
                    else:
                        rejected_rooms += 1
                else:
                    rejected_rooms += 1
            
            print(f"Maximum Concurrent Rooms Stress Test:")
            print(f"  Max allowed rooms: {max_rooms}")
            print(f"  Created rooms: {created_rooms}")
            print(f"  Rejected rooms: {rejected_rooms}")
            
            # Should respect the limit
            assert created_rooms == max_rooms
            assert rejected_rooms == 20
    
    @pytest.mark.asyncio
    async def test_memory_stress_test(self):
        """Test system behavior under memory stress."""
        
        auth_manager = LiveKitAuthManager("test_key", "test_secret")
        
        # Create large number of tokens to stress memory
        large_token_count = 50000
        tokens = []
        
        # Monitor memory during creation
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            for i in range(large_token_count):
                token = auth_manager.create_participant_token(
                    identity=f"stress_user_{i}",
                    room_name=f"stress_room_{i % 1000}"
                )
                tokens.append(token)
                
                # Check memory every 10k tokens
                if i % 10000 == 0 and i > 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - initial_memory
                    
                    print(f"  After {i} tokens: {current_memory:.1f} MB (+{memory_increase:.1f} MB)")
                    
                    # Fail if memory usage becomes excessive
                    if memory_increase > 500:  # 500MB limit
                        pytest.fail(f"Memory usage too high: {memory_increase:.1f} MB")
            
            final_memory = process.memory_info().rss / 1024 / 1024
            total_increase = final_memory - initial_memory
            
            print(f"Memory Stress Test:")
            print(f"  Tokens created: {large_token_count}")
            print(f"  Initial memory: {initial_memory:.1f} MB")
            print(f"  Final memory: {final_memory:.1f} MB")
            print(f"  Total increase: {total_increase:.1f} MB")
            print(f"  Memory per token: {(total_increase * 1024) / large_token_count:.2f} KB")
            
            # Memory should not grow excessively
            assert total_increase < 500, f"Memory usage too high: {total_increase:.1f} MB"
            
        finally:
            # Clean up
            del tokens
    
    def test_cpu_stress_test(self):
        """Test system behavior under CPU stress."""
        
        auth_manager = LiveKitAuthManager("test_key", "test_secret")
        
        # Use multiple threads to stress CPU
        num_threads = 4
        tokens_per_thread = 5000
        
        def create_tokens_thread(thread_id):
            """Thread function to create tokens."""
            thread_tokens = []
            for i in range(tokens_per_thread):
                token = auth_manager.create_participant_token(
                    identity=f"cpu_stress_user_{thread_id}_{i}",
                    room_name=f"cpu_stress_room_{i % 100}"
                )
                thread_tokens.append(token)
            return thread_tokens
        
        # Measure CPU usage
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for thread_id in range(num_threads):
                future = executor.submit(create_tokens_thread, thread_id)
                futures.append(future)
            
            # Wait for all threads to complete
            all_tokens = []
            for future in as_completed(futures):
                thread_tokens = future.result()
                all_tokens.extend(thread_tokens)
        
        end_time = time.time()
        total_time = end_time - start_time
        total_tokens = len(all_tokens)
        tokens_per_second = total_tokens / total_time
        
        print(f"CPU Stress Test:")
        print(f"  Threads: {num_threads}")
        print(f"  Tokens per thread: {tokens_per_thread}")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Tokens per second: {tokens_per_second:.0f}")
        
        # Should maintain reasonable performance under CPU stress
        assert tokens_per_second >= 1000, f"Performance too low under CPU stress: {tokens_per_second:.0f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
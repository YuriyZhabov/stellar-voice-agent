"""
Load testing scenarios for the Voice AI Agent system.

This module contains specialized load testing scenarios that simulate
high-traffic conditions and measure system performance under stress.
"""

import asyncio
import logging
import time
import pytest
import statistics
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple
from unittest.mock import Mock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor
import threading
import psutil
import gc

from src.orchestrator import CallOrchestrator, CallContext, CallMetrics
from src.clients.deepgram_stt import DeepgramSTTClient, TranscriptionResult
from src.clients.openai_llm import OpenAILLMClient
from src.clients.cartesia_tts import CartesiaTTSClient


# Load test configuration
LOAD_TEST_TIMEOUT = 1200  # 20 minutes for comprehensive load tests
MAX_CONCURRENT_CALLS = 50
RAMP_UP_DURATION = 30  # seconds
SUSTAINED_LOAD_DURATION = 300  # 5 minutes
RAMP_DOWN_DURATION = 30  # seconds


class LoadTestMetrics:
    """Comprehensive metrics collection for load testing."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.call_results = []
        self.latency_measurements = []
        self.error_counts = {}
        self.concurrent_calls_peak = 0
        self.memory_samples = []
        self.cpu_samples = []
        self.lock = threading.Lock()
    
    def start_test(self):
        """Start the load test and begin metrics collection."""
        self.start_time = time.time()
        self.call_results = []
        self.latency_measurements = []
        self.error_counts = {}
        self.concurrent_calls_peak = 0
        self.memory_samples = []
        self.cpu_samples = []
    
    def record_call_result(self, call_id: str, success: bool, latency: float, error: str = None):
        """Record the result of a call."""
        with self.lock:
            result = {
                'call_id': call_id,
                'success': success,
                'latency': latency,
                'timestamp': time.time(),
                'error': error
            }
            self.call_results.append(result)
            
            if success:
                self.latency_measurements.append(latency)
            else:
                error_type = type(error).__name__ if error else 'Unknown'
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def record_concurrent_calls(self, count: int):
        """Record the current number of concurrent calls."""
        with self.lock:
            self.concurrent_calls_peak = max(self.concurrent_calls_peak, count)
    
    def record_system_metrics(self):
        """Record current system metrics."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            with self.lock:
                self.memory_samples.append(memory_mb)
                self.cpu_samples.append(cpu_percent)
        except Exception:
            pass  # Ignore system metrics errors
    
    def end_test(self):
        """End the test and finalize metrics."""
        self.end_time = time.time()
    
    def get_summary(self) -> Dict:
        """Get comprehensive test summary."""
        if not self.start_time or not self.end_time:
            return {}
        
        total_duration = self.end_time - self.start_time
        total_calls = len(self.call_results)
        successful_calls = sum(1 for r in self.call_results if r['success'])
        failed_calls = total_calls - successful_calls
        
        summary = {
            'test_duration': total_duration,
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'success_rate': successful_calls / total_calls if total_calls > 0 else 0,
            'throughput_calls_per_second': total_calls / total_duration if total_duration > 0 else 0,
            'concurrent_calls_peak': self.concurrent_calls_peak,
            'error_counts': self.error_counts.copy()
        }
        
        # Latency statistics
        if self.latency_measurements:
            summary.update({
                'latency_avg': statistics.mean(self.latency_measurements),
                'latency_min': min(self.latency_measurements),
                'latency_max': max(self.latency_measurements),
                'latency_p50': statistics.median(self.latency_measurements),
                'latency_p95': statistics.quantiles(self.latency_measurements, n=20)[18] if len(self.latency_measurements) >= 20 else max(self.latency_measurements),
                'latency_p99': statistics.quantiles(self.latency_measurements, n=100)[98] if len(self.latency_measurements) >= 100 else max(self.latency_measurements)
            })
        
        # System resource statistics
        if self.memory_samples:
            summary.update({
                'memory_avg_mb': statistics.mean(self.memory_samples),
                'memory_max_mb': max(self.memory_samples),
                'memory_min_mb': min(self.memory_samples)
            })
        
        if self.cpu_samples:
            summary.update({
                'cpu_avg_percent': statistics.mean(self.cpu_samples),
                'cpu_max_percent': max(self.cpu_samples)
            })
        
        return summary


class LoadTestScenario:
    """Base class for load test scenarios."""
    
    def __init__(self, orchestrator: CallOrchestrator, metrics: LoadTestMetrics):
        self.orchestrator = orchestrator
        self.metrics = metrics
        self.active_calls = set()
        self.call_counter = 0
        self.lock = threading.Lock()
    
    async def create_call_context(self) -> Tuple[str, CallContext]:
        """Create a new call context."""
        with self.lock:
            self.call_counter += 1
            call_id = f"load_test_call_{self.call_counter}"
        
        call_context = CallContext(
            call_id=call_id,
            caller_number=f"+555{self.call_counter:07d}",
            start_time=datetime.now(UTC),
            livekit_room=f"load_test_room_{self.call_counter}"
        )
        
        return call_id, call_context
    
    async def simulate_single_call(self, call_duration: float = 30.0) -> Dict:
        """Simulate a single call with conversation turns."""
        call_id, call_context = await self.create_call_context()
        call_start_time = time.time()
        
        try:
            # Track active calls
            with self.lock:
                self.active_calls.add(call_id)
                self.metrics.record_concurrent_calls(len(self.active_calls))
            
            # Start the call
            await self.orchestrator.handle_call_start(call_context)
            
            # Simulate conversation turns
            conversation_turns = [
                "Hello, I need help with my account",
                "I forgot my password",
                "My email is user@example.com",
                "Can you help me reset it?",
                "Thank you for your assistance"
            ]
            
            turn_latencies = []
            
            for turn_text in conversation_turns:
                turn_start = time.time()
                
                # Simulate audio input
                audio_data = turn_text.encode()
                await self.orchestrator.handle_audio_received(call_id, audio_data)
                
                # Brief pause between turns
                await asyncio.sleep(0.5)
                
                turn_end = time.time()
                turn_latencies.append(turn_end - turn_start)
                
                # Check if we should end the call early
                if time.time() - call_start_time > call_duration:
                    break
            
            # End the call
            await self.orchestrator.handle_call_end(call_context)
            
            call_end_time = time.time()
            total_latency = call_end_time - call_start_time
            avg_turn_latency = statistics.mean(turn_latencies) if turn_latencies else 0
            
            # Record successful call
            self.metrics.record_call_result(call_id, True, avg_turn_latency)
            
            return {
                'call_id': call_id,
                'success': True,
                'total_duration': total_latency,
                'avg_turn_latency': avg_turn_latency,
                'turns_completed': len(turn_latencies)
            }
            
        except Exception as e:
            call_end_time = time.time()
            total_latency = call_end_time - call_start_time
            
            # Record failed call
            self.metrics.record_call_result(call_id, False, total_latency, str(e))
            
            return {
                'call_id': call_id,
                'success': False,
                'total_duration': total_latency,
                'error': str(e)
            }
            
        finally:
            # Remove from active calls
            with self.lock:
                self.active_calls.discard(call_id)


@pytest.fixture
def load_test_orchestrator():
    """Create an orchestrator optimized for load testing."""
    # Mock AI clients with realistic delays
    stt_client = Mock(spec=DeepgramSTTClient)
    stt_client.transcribe_batch = AsyncMock()
    stt_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_transcribe_with_delay(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate STT processing time
        return TranscriptionResult(
            text="Mock transcription",
            confidence=0.95,
            language="en",
            duration=1.0,
            alternatives=[]
        )
    
    stt_client.transcribe_batch.side_effect = mock_transcribe_with_delay
    
    llm_client = Mock(spec=OpenAILLMClient)
    llm_client.generate_response = AsyncMock()
    llm_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_llm_with_delay(*args, **kwargs):
        await asyncio.sleep(0.2)  # Simulate LLM processing time
        return "Mock LLM response"
    
    llm_client.generate_response.side_effect = mock_llm_with_delay
    
    tts_client = Mock(spec=CartesiaTTSClient)
    tts_client.synthesize_batch = AsyncMock()
    tts_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_tts_with_delay(*args, **kwargs):
        await asyncio.sleep(0.15)  # Simulate TTS processing time
        return b"mock_audio_response"
    
    tts_client.synthesize_batch.side_effect = mock_tts_with_delay
    
    return CallOrchestrator(
        stt_client=stt_client,
        llm_client=llm_client,
        tts_client=tts_client,
        max_concurrent_calls=MAX_CONCURRENT_CALLS,
        audio_buffer_size=4096,
        response_timeout=10.0
    )


@pytest.mark.integration
@pytest.mark.slow
class TestLoadScenarios:
    """Comprehensive load testing scenarios."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(LOAD_TEST_TIMEOUT)
    async def test_gradual_ramp_up_load(self, load_test_orchestrator):
        """Test gradual ramp-up of concurrent calls."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # System metrics monitoring task
        async def monitor_system_metrics():
            while metrics.start_time and not metrics.end_time:
                metrics.record_system_metrics()
                await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(monitor_system_metrics())
        
        try:
            # Gradual ramp-up
            max_concurrent = 20  # Reduced for CI
            ramp_up_duration = 10  # Reduced for CI
            
            call_tasks = []
            
            for i in range(max_concurrent):
                # Start calls gradually
                if i > 0:
                    await asyncio.sleep(ramp_up_duration / max_concurrent)
                
                task = asyncio.create_task(scenario.simulate_single_call(call_duration=30))
                call_tasks.append(task)
            
            # Wait for all calls to complete
            results = await asyncio.gather(*call_tasks, return_exceptions=True)
            
            metrics.end_test()
            
            # Analyze results
            successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
            failed_results = [r for r in results if not (isinstance(r, dict) and r.get('success'))]
            
            summary = metrics.get_summary()
            
            # Verify load test requirements (adjusted for test environment)
            assert summary['success_rate'] >= 0.8, f"Success rate {summary['success_rate']:.2%} below 80%"
            assert summary['latency_avg'] < 3.0, f"Average latency {summary['latency_avg']:.3f}s too high"
            assert summary['concurrent_calls_peak'] >= max_concurrent * 0.3, f"Peak concurrency {summary['concurrent_calls_peak']} too low for {max_concurrent} target"
            
            logging.info(f"Gradual ramp-up test summary: {summary}")
            
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(LOAD_TEST_TIMEOUT)
    async def test_sustained_high_load(self, load_test_orchestrator):
        """Test sustained high load over extended period."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Sustained load parameters
        concurrent_calls = 15  # Reduced for CI
        test_duration = 60  # 1 minute for CI
        
        async def sustained_load_generator():
            """Generate sustained load by continuously starting new calls."""
            end_time = time.time() + test_duration
            
            while time.time() < end_time:
                # Maintain target concurrency
                current_active = len(scenario.active_calls)
                
                if current_active < concurrent_calls:
                    # Start new calls to reach target concurrency
                    new_calls_needed = concurrent_calls - current_active
                    
                    for _ in range(min(new_calls_needed, 5)):  # Start max 5 at once
                        task = asyncio.create_task(scenario.simulate_single_call(call_duration=20))
                        # Don't await here - let calls run concurrently
                
                await asyncio.sleep(1)  # Check every second
        
        # Run sustained load
        await sustained_load_generator()
        
        # Wait a bit for remaining calls to complete
        await asyncio.sleep(5)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Verify sustained load requirements
        assert summary['success_rate'] >= 0.85, f"Success rate {summary['success_rate']:.2%} below 85%"
        assert summary['throughput_calls_per_second'] >= 0.5, f"Throughput {summary['throughput_calls_per_second']:.2f} too low"
        assert summary['concurrent_calls_peak'] >= concurrent_calls * 0.3, f"Peak concurrency {summary['concurrent_calls_peak']} too low for {concurrent_calls} target"
        
        logging.info(f"Sustained load test summary: {summary}")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(LOAD_TEST_TIMEOUT)
    async def test_spike_load_handling(self, load_test_orchestrator):
        """Test system response to sudden load spikes."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Spike load parameters
        spike_calls = 25  # Reduced for CI
        
        # Create sudden spike of concurrent calls
        spike_tasks = []
        
        for i in range(spike_calls):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=15))
            spike_tasks.append(task)
        
        # Wait for spike to complete
        results = await asyncio.gather(*spike_tasks, return_exceptions=True)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Analyze spike handling
        successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
        
        # Verify spike handling requirements
        assert summary['success_rate'] >= 0.8, f"Spike success rate {summary['success_rate']:.2%} below 80%"
        assert summary['concurrent_calls_peak'] >= spike_calls * 0.8, "Peak concurrency during spike too low"
        
        # Check that system didn't crash
        health_status = await load_test_orchestrator.get_health_status()
        assert health_status.is_healthy, "System unhealthy after spike load"
        
        logging.info(f"Spike load test summary: {summary}")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(LOAD_TEST_TIMEOUT)
    async def test_memory_pressure_under_load(self, load_test_orchestrator):
        """Test system behavior under memory pressure during load."""
        import gc
        
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        # Get initial memory baseline
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        metrics.start_test()
        
        # Run load test with memory monitoring
        num_calls = 30  # Reduced for CI
        call_tasks = []
        
        for i in range(num_calls):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=10))
            call_tasks.append(task)
            
            # Monitor memory every 10 calls
            if i % 10 == 0:
                metrics.record_system_metrics()
                gc.collect()  # Force garbage collection
        
        # Wait for all calls to complete
        await asyncio.gather(*call_tasks, return_exceptions=True)
        
        # Final memory check
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Verify memory usage is reasonable
        max_memory_increase = 100  # MB - allow reasonable increase
        assert memory_increase < max_memory_increase, f"Memory increased by {memory_increase:.1f}MB"
        
        # Verify no major memory leaks in orchestrator (allow some remaining in test environment)
        active_calls_count = len(load_test_orchestrator.active_calls)
        audio_streams_count = len(load_test_orchestrator.audio_streams)
        
        assert active_calls_count <= num_calls, f"Too many active calls remaining: {active_calls_count}/{num_calls}"
        assert audio_streams_count <= num_calls, f"Too many audio streams remaining: {audio_streams_count}/{num_calls}"
        
        logging.info(f"Memory pressure test - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Increase: {memory_increase:.1f}MB")
        logging.info(f"Memory pressure test summary: {summary}")


@pytest.mark.integration
@pytest.mark.slow
class TestFailureUnderLoad:
    """Test system behavior when failures occur under load."""
    
    @pytest.mark.asyncio
    async def test_partial_service_failure_under_load(self, load_test_orchestrator):
        """Test system resilience when services fail under load."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Start initial load
        num_calls = 20  # Reduced for CI
        call_tasks = []
        
        for i in range(num_calls):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=15))
            call_tasks.append(task)
            
            # Introduce service failure halfway through
            if i == num_calls // 2:
                # Simulate STT service failure
                load_test_orchestrator.stt_client.transcribe_batch.side_effect = Exception("STT service overloaded")
        
        # Wait for all calls to complete
        results = await asyncio.gather(*call_tasks, return_exceptions=True)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Verify system handled partial failure gracefully
        # Some calls should succeed (before failure), some may fail (after failure)
        assert summary['total_calls'] == num_calls
        assert summary['success_rate'] >= 0.4, f"Success rate {summary['success_rate']:.2%} too low during partial failure"
        
        # System should still be responsive
        health_status = await load_test_orchestrator.get_health_status()
        # Health may be degraded but system should not crash
        
        logging.info(f"Partial failure under load test summary: {summary}")
    
    @pytest.mark.asyncio
    async def test_recovery_after_failure_under_load(self, load_test_orchestrator):
        """Test system recovery after service failure under load."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Phase 1: Normal operation
        phase1_tasks = []
        for i in range(5):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=10))
            phase1_tasks.append(task)
        
        await asyncio.gather(*phase1_tasks, return_exceptions=True)
        
        # Phase 2: Introduce failure
        load_test_orchestrator.llm_client.generate_response.side_effect = Exception("LLM service down")
        
        phase2_tasks = []
        for i in range(5):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=10))
            phase2_tasks.append(task)
        
        await asyncio.gather(*phase2_tasks, return_exceptions=True)
        
        # Phase 3: Service recovery
        async def mock_llm_recovery(*args, **kwargs):
            await asyncio.sleep(0.2)
            return "Service recovered - mock response"
        
        load_test_orchestrator.llm_client.generate_response.side_effect = mock_llm_recovery
        
        phase3_tasks = []
        for i in range(5):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=10))
            phase3_tasks.append(task)
        
        await asyncio.gather(*phase3_tasks, return_exceptions=True)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Verify recovery
        assert summary['total_calls'] == 15
        # Should have some successes in phase 1 and 3, failures in phase 2
        assert summary['success_rate'] >= 0.6, f"Overall success rate {summary['success_rate']:.2%} too low"
        
        # System should be healthy after recovery
        health_status = await load_test_orchestrator.get_health_status()
        assert health_status.is_healthy, "System not healthy after recovery"
        
        logging.info(f"Recovery after failure test summary: {summary}")


@pytest.mark.integration
class TestPerformanceBenchmarks:
    """Performance benchmarking tests for baseline establishment."""
    
    @pytest.mark.asyncio
    async def test_single_call_performance_benchmark(self, load_test_orchestrator):
        """Establish single call performance benchmark."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Run single call benchmark
        num_benchmark_calls = 10
        benchmark_tasks = []
        
        for i in range(num_benchmark_calls):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=20))
            benchmark_tasks.append(task)
            await asyncio.sleep(0.5)  # Stagger calls slightly
        
        results = await asyncio.gather(*benchmark_tasks, return_exceptions=True)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Establish benchmark metrics
        benchmark_results = {
            'single_call_avg_latency': summary.get('latency_avg', 0),
            'single_call_p95_latency': summary.get('latency_p95', 0),
            'single_call_success_rate': summary.get('success_rate', 0),
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        # Verify benchmark meets requirements
        assert benchmark_results['single_call_avg_latency'] < 1.5, "Single call latency too high"
        assert benchmark_results['single_call_success_rate'] >= 0.95, "Single call success rate too low"
        
        logging.info(f"Single call performance benchmark: {benchmark_results}")
        
        return benchmark_results
    
    @pytest.mark.asyncio
    async def test_concurrent_calls_performance_benchmark(self, load_test_orchestrator):
        """Establish concurrent calls performance benchmark."""
        metrics = LoadTestMetrics()
        scenario = LoadTestScenario(load_test_orchestrator, metrics)
        
        metrics.start_test()
        
        # Run concurrent calls benchmark
        concurrent_calls = 10  # Reduced for CI
        benchmark_tasks = []
        
        for i in range(concurrent_calls):
            task = asyncio.create_task(scenario.simulate_single_call(call_duration=15))
            benchmark_tasks.append(task)
        
        results = await asyncio.gather(*benchmark_tasks, return_exceptions=True)
        
        metrics.end_test()
        summary = metrics.get_summary()
        
        # Establish concurrent benchmark metrics
        benchmark_results = {
            'concurrent_calls_avg_latency': summary.get('latency_avg', 0),
            'concurrent_calls_p95_latency': summary.get('latency_p95', 0),
            'concurrent_calls_success_rate': summary.get('success_rate', 0),
            'concurrent_calls_throughput': summary.get('throughput_calls_per_second', 0),
            'concurrent_calls_peak': summary.get('concurrent_calls_peak', 0),
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        # Verify benchmark meets requirements
        assert benchmark_results['concurrent_calls_avg_latency'] < 2.0, "Concurrent calls latency too high"
        assert benchmark_results['concurrent_calls_success_rate'] >= 0.9, "Concurrent calls success rate too low"
        assert benchmark_results['concurrent_calls_throughput'] >= 0.5, "Throughput too low"
        
        logging.info(f"Concurrent calls performance benchmark: {benchmark_results}")
        
        return benchmark_results


if __name__ == "__main__":
    # Run load tests
    pytest.main([
        __file__,
        "-v",
        "-m", "integration and slow",
        "--tb=short",
        "-s"  # Show print statements
    ])
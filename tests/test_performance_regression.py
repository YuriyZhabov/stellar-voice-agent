"""
Performance regression testing for deployment validation.

This module contains tests that establish performance baselines and detect
regressions in system performance across deployments.
"""

import asyncio
import json
import logging
import os
import time
import pytest
import statistics
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, AsyncMock

from src.orchestrator import CallOrchestrator, CallContext
from src.clients.deepgram_stt import DeepgramSTTClient, TranscriptionResult
from src.clients.openai_llm import OpenAILLMClient
from src.clients.cartesia_tts import CartesiaTTSClient


# Performance regression configuration
BASELINE_FILE = "performance_baseline.json"
REGRESSION_THRESHOLD = 1.2  # 20% performance degradation threshold
IMPROVEMENT_THRESHOLD = 0.9  # 10% performance improvement threshold


class PerformanceBaseline:
    """Manages performance baseline data."""
    
    def __init__(self, baseline_file: str = BASELINE_FILE):
        self.baseline_file = Path(baseline_file)
        self.baseline_data = self._load_baseline()
    
    def _load_baseline(self) -> Dict[str, Any]:
        """Load existing baseline data."""
        if self.baseline_file.exists():
            try:
                with open(self.baseline_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load baseline file: {e}")
        
        return {}
    
    def save_baseline(self, metrics: Dict[str, Any]):
        """Save new baseline metrics."""
        baseline_entry = {
            'timestamp': datetime.now(UTC).isoformat(),
            'metrics': metrics,
            'version': os.environ.get('APP_VERSION', 'unknown'),
            'environment': os.environ.get('ENVIRONMENT', 'test')
        }
        
        # Keep history of baselines
        if 'history' not in self.baseline_data:
            self.baseline_data['history'] = []
        
        self.baseline_data['history'].append(baseline_entry)
        self.baseline_data['current'] = baseline_entry
        
        # Keep only last 10 baselines
        if len(self.baseline_data['history']) > 10:
            self.baseline_data['history'] = self.baseline_data['history'][-10:]
        
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(self.baseline_data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save baseline file: {e}")
    
    def get_current_baseline(self) -> Optional[Dict[str, Any]]:
        """Get current baseline metrics."""
        return self.baseline_data.get('current', {}).get('metrics')
    
    def compare_metrics(self, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current metrics against baseline."""
        baseline_metrics = self.get_current_baseline()
        if not baseline_metrics:
            return {'status': 'no_baseline', 'message': 'No baseline available for comparison'}
        
        comparison = {
            'status': 'pass',
            'regressions': [],
            'improvements': [],
            'details': {}
        }
        
        # Compare key metrics
        key_metrics = [
            'avg_latency',
            'p95_latency',
            'p99_latency',
            'success_rate',
            'throughput',
            'memory_usage_mb',
            'cpu_usage_percent'
        ]
        
        for metric in key_metrics:
            if metric in current_metrics and metric in baseline_metrics:
                current_value = current_metrics[metric]
                baseline_value = baseline_metrics[metric]
                
                if baseline_value > 0:  # Avoid division by zero
                    ratio = current_value / baseline_value
                    
                    comparison['details'][metric] = {
                        'current': current_value,
                        'baseline': baseline_value,
                        'ratio': ratio,
                        'change_percent': (ratio - 1) * 100
                    }
                    
                    # Check for regressions (higher is worse for latency, lower is worse for success_rate/throughput)
                    if metric in ['avg_latency', 'p95_latency', 'p99_latency', 'memory_usage_mb', 'cpu_usage_percent']:
                        if ratio > REGRESSION_THRESHOLD:
                            comparison['regressions'].append({
                                'metric': metric,
                                'current': current_value,
                                'baseline': baseline_value,
                                'degradation_percent': (ratio - 1) * 100
                            })
                        elif ratio < IMPROVEMENT_THRESHOLD:
                            comparison['improvements'].append({
                                'metric': metric,
                                'current': current_value,
                                'baseline': baseline_value,
                                'improvement_percent': (1 - ratio) * 100
                            })
                    else:  # success_rate, throughput - higher is better
                        if ratio < (1 / REGRESSION_THRESHOLD):
                            comparison['regressions'].append({
                                'metric': metric,
                                'current': current_value,
                                'baseline': baseline_value,
                                'degradation_percent': (1 - ratio) * 100
                            })
                        elif ratio > (1 / IMPROVEMENT_THRESHOLD):
                            comparison['improvements'].append({
                                'metric': metric,
                                'current': current_value,
                                'baseline': baseline_value,
                                'improvement_percent': (ratio - 1) * 100
                            })
        
        # Set overall status
        if comparison['regressions']:
            comparison['status'] = 'regression_detected'
        elif comparison['improvements']:
            comparison['status'] = 'improvement_detected'
        
        return comparison


class PerformanceTester:
    """Comprehensive performance testing utility."""
    
    def __init__(self, orchestrator: CallOrchestrator):
        self.orchestrator = orchestrator
        self.test_results = {}
    
    async def run_latency_test(self, num_calls: int = 20) -> Dict[str, float]:
        """Run latency performance test."""
        latency_measurements = []
        
        for i in range(num_calls):
            call_id = f"perf_test_call_{i}"
            call_context = CallContext(
                call_id=call_id,
                caller_number=f"+555{i:07d}",
                start_time=datetime.now(UTC),
                livekit_room=f"perf_test_room_{i}"
            )
            
            start_time = time.time()
            
            try:
                # Full call lifecycle
                await self.orchestrator.handle_call_start(call_context)
                
                # Simulate conversation turn
                audio_data = f"Performance test message {i}".encode()
                await self.orchestrator.handle_audio_received(call_id, audio_data)
                
                await self.orchestrator.handle_call_end(call_context)
                
                end_time = time.time()
                latency = end_time - start_time
                latency_measurements.append(latency)
                
            except Exception as e:
                logging.warning(f"Performance test call {i} failed: {e}")
                # Still record the time for failed calls
                end_time = time.time()
                latency_measurements.append(end_time - start_time)
            
            # Brief pause between calls
            await asyncio.sleep(0.1)
        
        # Calculate latency statistics
        if latency_measurements:
            return {
                'avg_latency': statistics.mean(latency_measurements),
                'min_latency': min(latency_measurements),
                'max_latency': max(latency_measurements),
                'p50_latency': statistics.median(latency_measurements),
                'p95_latency': statistics.quantiles(latency_measurements, n=20)[18] if len(latency_measurements) >= 20 else max(latency_measurements),
                'p99_latency': statistics.quantiles(latency_measurements, n=100)[98] if len(latency_measurements) >= 100 else max(latency_measurements),
                'latency_std': statistics.stdev(latency_measurements) if len(latency_measurements) > 1 else 0
            }
        
        return {}
    
    async def run_throughput_test(self, duration_seconds: int = 60) -> Dict[str, float]:
        """Run throughput performance test."""
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        completed_calls = 0
        successful_calls = 0
        failed_calls = 0
        
        call_counter = 0
        
        while time.time() < end_time:
            call_counter += 1
            call_id = f"throughput_test_call_{call_counter}"
            call_context = CallContext(
                call_id=call_id,
                caller_number=f"+555{call_counter:07d}",
                start_time=datetime.now(UTC),
                livekit_room=f"throughput_test_room_{call_counter}"
            )
            
            try:
                await self.orchestrator.handle_call_start(call_context)
                
                # Quick conversation turn
                audio_data = f"Throughput test {call_counter}".encode()
                await self.orchestrator.handle_audio_received(call_id, audio_data)
                
                await self.orchestrator.handle_call_end(call_context)
                
                successful_calls += 1
                
            except Exception as e:
                failed_calls += 1
                logging.warning(f"Throughput test call {call_counter} failed: {e}")
            
            completed_calls += 1
            
            # Brief pause to avoid overwhelming the system
            await asyncio.sleep(0.05)
        
        actual_duration = time.time() - start_time
        
        return {
            'throughput': completed_calls / actual_duration,
            'successful_throughput': successful_calls / actual_duration,
            'success_rate': successful_calls / completed_calls if completed_calls > 0 else 0,
            'total_calls': completed_calls,
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'test_duration': actual_duration
        }
    
    async def run_concurrent_load_test(self, concurrent_calls: int = 10) -> Dict[str, float]:
        """Run concurrent load performance test."""
        async def single_concurrent_call(call_index: int):
            call_id = f"concurrent_test_call_{call_index}"
            call_context = CallContext(
                call_id=call_id,
                caller_number=f"+555{call_index:07d}",
                start_time=datetime.now(UTC),
                livekit_room=f"concurrent_test_room_{call_index}"
            )
            
            start_time = time.time()
            
            try:
                await self.orchestrator.handle_call_start(call_context)
                
                # Multiple conversation turns
                for turn in range(3):
                    audio_data = f"Concurrent test {call_index} turn {turn}".encode()
                    await self.orchestrator.handle_audio_received(call_id, audio_data)
                    await asyncio.sleep(0.1)
                
                await self.orchestrator.handle_call_end(call_context)
                
                end_time = time.time()
                return {
                    'success': True,
                    'duration': end_time - start_time,
                    'call_id': call_id
                }
                
            except Exception as e:
                end_time = time.time()
                return {
                    'success': False,
                    'duration': end_time - start_time,
                    'call_id': call_id,
                    'error': str(e)
                }
        
        # Run all calls concurrently
        start_time = time.time()
        tasks = [asyncio.create_task(single_concurrent_call(i)) for i in range(concurrent_calls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
        failed_results = [r for r in results if not (isinstance(r, dict) and r.get('success'))]
        
        durations = [r['duration'] for r in successful_results]
        
        return {
            'concurrent_success_rate': len(successful_results) / len(results),
            'concurrent_avg_duration': statistics.mean(durations) if durations else 0,
            'concurrent_max_duration': max(durations) if durations else 0,
            'concurrent_total_time': end_time - start_time,
            'concurrent_calls_completed': len(results),
            'concurrent_calls_successful': len(successful_results),
            'concurrent_calls_failed': len(failed_results)
        }
    
    async def run_memory_test(self, num_calls: int = 50) -> Dict[str, float]:
        """Run memory usage performance test."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get initial memory
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = [initial_memory]
        
        # Run calls and monitor memory
        for i in range(num_calls):
            call_id = f"memory_test_call_{i}"
            call_context = CallContext(
                call_id=call_id,
                caller_number=f"+555{i:07d}",
                start_time=datetime.now(UTC),
                livekit_room=f"memory_test_room_{i}"
            )
            
            try:
                await self.orchestrator.handle_call_start(call_context)
                
                audio_data = f"Memory test {i}".encode()
                await self.orchestrator.handle_audio_received(call_id, audio_data)
                
                await self.orchestrator.handle_call_end(call_context)
                
            except Exception as e:
                logging.warning(f"Memory test call {i} failed: {e}")
            
            # Sample memory every 10 calls
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
        
        # Final memory measurement
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_samples.append(final_memory)
        
        return {
            'memory_usage_mb': final_memory,
            'memory_initial_mb': initial_memory,
            'memory_increase_mb': final_memory - initial_memory,
            'memory_peak_mb': max(memory_samples),
            'memory_avg_mb': statistics.mean(memory_samples)
        }
    
    async def run_comprehensive_performance_test(self) -> Dict[str, Any]:
        """Run comprehensive performance test suite."""
        logging.info("Starting comprehensive performance test...")
        
        results = {
            'timestamp': datetime.now(UTC).isoformat(),
            'test_environment': os.environ.get('ENVIRONMENT', 'test'),
            'app_version': os.environ.get('APP_VERSION', 'unknown')
        }
        
        # Run latency test
        logging.info("Running latency test...")
        latency_results = await self.run_latency_test(num_calls=15)  # Reduced for CI
        results.update(latency_results)
        
        # Run throughput test
        logging.info("Running throughput test...")
        throughput_results = await self.run_throughput_test(duration_seconds=30)  # Reduced for CI
        results.update(throughput_results)
        
        # Run concurrent load test
        logging.info("Running concurrent load test...")
        concurrent_results = await self.run_concurrent_load_test(concurrent_calls=8)  # Reduced for CI
        results.update(concurrent_results)
        
        # Run memory test
        logging.info("Running memory test...")
        memory_results = await self.run_memory_test(num_calls=25)  # Reduced for CI
        results.update(memory_results)
        
        # Add CPU usage (basic measurement)
        import psutil
        results['cpu_usage_percent'] = psutil.Process().cpu_percent()
        
        logging.info("Comprehensive performance test completed")
        return results


@pytest.fixture
def performance_orchestrator():
    """Create an orchestrator for performance testing."""
    # Mock AI clients with realistic performance characteristics
    stt_client = Mock(spec=DeepgramSTTClient)
    stt_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_stt_realistic(*args, **kwargs):
        # Simulate realistic STT processing time
        await asyncio.sleep(0.08)  # 80ms average
        return TranscriptionResult(
            text="Performance test transcription",
            confidence=0.95,
            language="en",
            duration=1.0,
            alternatives=[]
        )
    
    stt_client.transcribe_batch.side_effect = mock_stt_realistic
    
    llm_client = Mock(spec=OpenAILLMClient)
    llm_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_llm_realistic(*args, **kwargs):
        # Simulate realistic LLM processing time
        await asyncio.sleep(0.15)  # 150ms average
        return "Performance test response from LLM"
    
    llm_client.generate_response.side_effect = mock_llm_realistic
    
    tts_client = Mock(spec=CartesiaTTSClient)
    tts_client.health_check = AsyncMock(return_value=Mock(is_healthy=True))
    
    async def mock_tts_realistic(*args, **kwargs):
        # Simulate realistic TTS processing time
        await asyncio.sleep(0.12)  # 120ms average
        return b"performance_test_audio_response"
    
    tts_client.synthesize_batch.side_effect = mock_tts_realistic
    
    return CallOrchestrator(
        stt_client=stt_client,
        llm_client=llm_client,
        tts_client=tts_client,
        max_concurrent_calls=50,
        audio_buffer_size=4096,
        response_timeout=10.0
    )


@pytest.mark.integration
class TestPerformanceRegression:
    """Performance regression testing suite."""
    
    @pytest.mark.asyncio
    async def test_establish_performance_baseline(self, performance_orchestrator):
        """Establish performance baseline for future comparisons."""
        tester = PerformanceTester(performance_orchestrator)
        baseline_manager = PerformanceBaseline()
        
        # Run comprehensive performance test
        performance_metrics = await tester.run_comprehensive_performance_test()
        
        # Verify metrics meet minimum requirements
        assert performance_metrics['avg_latency'] < 1.5, f"Baseline latency {performance_metrics['avg_latency']:.3f}s too high"
        assert performance_metrics['success_rate'] >= 0.95, f"Baseline success rate {performance_metrics['success_rate']:.2%} too low"
        assert performance_metrics['throughput'] >= 1.0, f"Baseline throughput {performance_metrics['throughput']:.2f} too low"
        
        # Save as new baseline
        baseline_manager.save_baseline(performance_metrics)
        
        logging.info(f"Performance baseline established: {performance_metrics}")
        
        return performance_metrics
    
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self, performance_orchestrator):
        """Test detection of performance regressions."""
        tester = PerformanceTester(performance_orchestrator)
        baseline_manager = PerformanceBaseline()
        
        # Run current performance test
        current_metrics = await tester.run_comprehensive_performance_test()
        
        # Compare against baseline
        comparison = baseline_manager.compare_metrics(current_metrics)
        
        # Log comparison results
        logging.info(f"Performance comparison status: {comparison['status']}")
        
        if comparison['regressions']:
            logging.warning(f"Performance regressions detected: {comparison['regressions']}")
        
        if comparison['improvements']:
            logging.info(f"Performance improvements detected: {comparison['improvements']}")
        
        # Assert no significant regressions
        if comparison['status'] == 'regression_detected':
            # Allow test to pass but log warnings for minor regressions
            major_regressions = [r for r in comparison['regressions'] if r['degradation_percent'] > 50]
            assert len(major_regressions) == 0, f"Major performance regressions detected: {major_regressions}"
        
        return comparison
    
    @pytest.mark.asyncio
    async def test_latency_regression_specific(self, performance_orchestrator):
        """Test specifically for latency regressions."""
        tester = PerformanceTester(performance_orchestrator)
        
        # Run focused latency test
        latency_metrics = await tester.run_latency_test(num_calls=25)
        
        # Verify latency requirements
        assert latency_metrics['avg_latency'] < 1.5, f"Average latency {latency_metrics['avg_latency']:.3f}s exceeds threshold"
        assert latency_metrics['p95_latency'] < 2.0, f"P95 latency {latency_metrics['p95_latency']:.3f}s exceeds threshold"
        assert latency_metrics['p99_latency'] < 3.0, f"P99 latency {latency_metrics['p99_latency']:.3f}s exceeds threshold"
        
        # Check latency consistency (low standard deviation)
        latency_cv = latency_metrics['latency_std'] / latency_metrics['avg_latency'] if latency_metrics['avg_latency'] > 0 else 0
        assert latency_cv < 0.5, f"Latency coefficient of variation {latency_cv:.3f} too high (inconsistent performance)"
        
        logging.info(f"Latency regression test passed: {latency_metrics}")
    
    @pytest.mark.asyncio
    async def test_throughput_regression_specific(self, performance_orchestrator):
        """Test specifically for throughput regressions."""
        tester = PerformanceTester(performance_orchestrator)
        
        # Run focused throughput test
        throughput_metrics = await tester.run_throughput_test(duration_seconds=45)
        
        # Verify throughput requirements
        assert throughput_metrics['throughput'] >= 1.0, f"Throughput {throughput_metrics['throughput']:.2f} calls/sec too low"
        assert throughput_metrics['success_rate'] >= 0.95, f"Success rate {throughput_metrics['success_rate']:.2%} too low"
        assert throughput_metrics['successful_throughput'] >= 0.95, f"Successful throughput {throughput_metrics['successful_throughput']:.2f} too low"
        
        logging.info(f"Throughput regression test passed: {throughput_metrics}")
    
    @pytest.mark.asyncio
    async def test_memory_regression_specific(self, performance_orchestrator):
        """Test specifically for memory usage regressions."""
        tester = PerformanceTester(performance_orchestrator)
        
        # Run focused memory test
        memory_metrics = await tester.run_memory_test(num_calls=40)
        
        # Verify memory usage requirements
        assert memory_metrics['memory_increase_mb'] < 50, f"Memory increase {memory_metrics['memory_increase_mb']:.1f}MB too high"
        assert memory_metrics['memory_usage_mb'] < 500, f"Total memory usage {memory_metrics['memory_usage_mb']:.1f}MB too high"
        
        # Check for memory leaks (memory should not increase significantly)
        memory_increase_ratio = memory_metrics['memory_increase_mb'] / memory_metrics['memory_initial_mb'] if memory_metrics['memory_initial_mb'] > 0 else 0
        assert memory_increase_ratio < 0.5, f"Memory increase ratio {memory_increase_ratio:.2f} suggests memory leak"
        
        logging.info(f"Memory regression test passed: {memory_metrics}")
    
    @pytest.mark.asyncio
    async def test_concurrent_performance_regression(self, performance_orchestrator):
        """Test for performance regressions under concurrent load."""
        tester = PerformanceTester(performance_orchestrator)
        
        # Run concurrent load test
        concurrent_metrics = await tester.run_concurrent_load_test(concurrent_calls=12)
        
        # Verify concurrent performance requirements
        assert concurrent_metrics['concurrent_success_rate'] >= 0.9, f"Concurrent success rate {concurrent_metrics['concurrent_success_rate']:.2%} too low"
        assert concurrent_metrics['concurrent_avg_duration'] < 2.0, f"Concurrent average duration {concurrent_metrics['concurrent_avg_duration']:.3f}s too high"
        assert concurrent_metrics['concurrent_max_duration'] < 5.0, f"Concurrent max duration {concurrent_metrics['concurrent_max_duration']:.3f}s too high"
        
        logging.info(f"Concurrent performance regression test passed: {concurrent_metrics}")


@pytest.mark.integration
class TestDeploymentValidation:
    """Deployment validation tests using performance metrics."""
    
    @pytest.mark.asyncio
    async def test_pre_deployment_validation(self, performance_orchestrator):
        """Validate performance before deployment."""
        tester = PerformanceTester(performance_orchestrator)
        
        # Run comprehensive validation
        validation_metrics = await tester.run_comprehensive_performance_test()
        
        # Define deployment readiness criteria
        deployment_criteria = {
            'avg_latency': 1.5,  # seconds
            'p95_latency': 2.0,  # seconds
            'success_rate': 0.95,  # 95%
            'throughput': 1.0,  # calls per second
            'memory_increase_mb': 50,  # MB
            'concurrent_success_rate': 0.9  # 90%
        }
        
        validation_results = {
            'deployment_ready': True,
            'failed_criteria': [],
            'warnings': [],
            'metrics': validation_metrics
        }
        
        # Check each criterion
        for criterion, threshold in deployment_criteria.items():
            if criterion in validation_metrics:
                value = validation_metrics[criterion]
                
                if criterion in ['avg_latency', 'p95_latency', 'memory_increase_mb']:
                    # Lower is better
                    if value > threshold:
                        validation_results['deployment_ready'] = False
                        validation_results['failed_criteria'].append({
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold,
                            'status': 'FAIL'
                        })
                    elif value > threshold * 0.8:  # Warning at 80% of threshold
                        validation_results['warnings'].append({
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold,
                            'status': 'WARNING'
                        })
                else:
                    # Higher is better
                    if value < threshold:
                        validation_results['deployment_ready'] = False
                        validation_results['failed_criteria'].append({
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold,
                            'status': 'FAIL'
                        })
                    elif value < threshold * 1.1:  # Warning at 110% of threshold
                        validation_results['warnings'].append({
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold,
                            'status': 'WARNING'
                        })
        
        # Log validation results
        if validation_results['deployment_ready']:
            logging.info("✅ Deployment validation PASSED")
        else:
            logging.error("❌ Deployment validation FAILED")
            logging.error(f"Failed criteria: {validation_results['failed_criteria']}")
        
        if validation_results['warnings']:
            logging.warning(f"⚠️ Deployment warnings: {validation_results['warnings']}")
        
        # Assert deployment readiness
        assert validation_results['deployment_ready'], f"Deployment validation failed: {validation_results['failed_criteria']}"
        
        return validation_results
    
    @pytest.mark.asyncio
    async def test_post_deployment_validation(self, performance_orchestrator):
        """Validate performance after deployment."""
        tester = PerformanceTester(performance_orchestrator)
        baseline_manager = PerformanceBaseline()
        
        # Run post-deployment performance test
        post_deployment_metrics = await tester.run_comprehensive_performance_test()
        
        # Compare against baseline
        comparison = baseline_manager.compare_metrics(post_deployment_metrics)
        
        # Post-deployment validation criteria (more lenient than pre-deployment)
        validation_results = {
            'deployment_healthy': True,
            'performance_status': comparison['status'],
            'issues': [],
            'metrics': post_deployment_metrics
        }
        
        # Check for major regressions
        if comparison['regressions']:
            major_regressions = [r for r in comparison['regressions'] if r['degradation_percent'] > 30]
            if major_regressions:
                validation_results['deployment_healthy'] = False
                validation_results['issues'].extend(major_regressions)
        
        # Check basic health criteria
        health_criteria = {
            'avg_latency': 2.0,  # More lenient for post-deployment
            'success_rate': 0.9,  # 90% minimum
            'throughput': 0.8  # 0.8 calls per second minimum
        }
        
        for criterion, threshold in health_criteria.items():
            if criterion in post_deployment_metrics:
                value = post_deployment_metrics[criterion]
                
                if criterion == 'avg_latency':
                    if value > threshold:
                        validation_results['deployment_healthy'] = False
                        validation_results['issues'].append({
                            'type': 'health_check_failure',
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold
                        })
                else:
                    if value < threshold:
                        validation_results['deployment_healthy'] = False
                        validation_results['issues'].append({
                            'type': 'health_check_failure',
                            'criterion': criterion,
                            'value': value,
                            'threshold': threshold
                        })
        
        # Log post-deployment results
        if validation_results['deployment_healthy']:
            logging.info("✅ Post-deployment validation PASSED")
        else:
            logging.error("❌ Post-deployment validation FAILED")
            logging.error(f"Issues detected: {validation_results['issues']}")
        
        # Assert deployment health
        assert validation_results['deployment_healthy'], f"Post-deployment validation failed: {validation_results['issues']}"
        
        return validation_results


if __name__ == "__main__":
    # Run performance regression tests
    pytest.main([
        __file__,
        "-v",
        "-m", "integration",
        "--tb=short"
    ])
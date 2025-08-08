#!/usr/bin/env python3
"""
End-to-End Integration Test Runner

This script runs comprehensive end-to-end integration tests for the Voice AI Agent system.
It includes all test categories specified in task 16:
- Complete conversation flow tests with all AI services
- Load testing scenarios for multiple concurrent calls
- Latency measurement tests to verify sub-1.5 second response requirements
- Failure scenario tests for partial service outages
- Long-running stability tests for 8+ hour continuous operation
- Performance regression tests for deployment validation
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional

import pytest


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('e2e_test_results.log')
    ]
)

logger = logging.getLogger(__name__)


class E2ETestRunner:
    """Comprehensive end-to-end test runner."""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def setup_test_environment(self):
        """Set up the test environment."""
        logger.info("Setting up test environment...")
        
        # Set test environment variables
        test_env = {
            'ENVIRONMENT': 'testing',
            'TEST_MODE': 'true',
            'DEBUG': 'true',
            'SECRET_KEY': 'test-secret-key-for-e2e-testing-32-chars',
            'DATABASE_URL': 'sqlite:///:memory:',
            'LOG_LEVEL': 'INFO',
            # Mock API keys for testing
            'DEEPGRAM_API_KEY': 'test-deepgram-key',
            'OPENAI_API_KEY': 'sk-test-openai-key',
            'CARTESIA_API_KEY': 'test-cartesia-key',
            'LIVEKIT_URL': 'wss://test.livekit.cloud',
            'LIVEKIT_API_KEY': 'test-livekit-key',
            'LIVEKIT_API_SECRET': 'test-livekit-secret'
        }
        
        for key, value in test_env.items():
            os.environ[key] = value
        
        logger.info("Test environment configured")
    
    def run_conversation_flow_tests(self) -> Dict:
        """Run complete conversation flow tests."""
        logger.info("🗣️ Running conversation flow tests...")
        
        test_args = [
            'tests/test_e2e_integration.py::TestCompleteConversationFlow',
            '-v',
            '--tb=short',
            '--junit-xml=conversation_flow_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'conversation_flow',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_load_tests(self) -> Dict:
        """Run load testing scenarios."""
        logger.info("⚡ Running load testing scenarios...")
        
        test_args = [
            'tests/test_load_testing.py::TestLoadScenarios',
            'tests/test_e2e_integration.py::TestLoadTesting',
            '-v',
            '--tb=short',
            '-m', 'integration',
            '--junit-xml=load_test_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'load_testing',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_latency_tests(self) -> Dict:
        """Run latency measurement tests."""
        logger.info("⏱️ Running latency measurement tests...")
        
        test_args = [
            'tests/test_e2e_integration.py::TestLatencyMeasurement',
            'tests/test_performance_regression.py::TestPerformanceRegression::test_latency_regression_specific',
            '-v',
            '--tb=short',
            '--junit-xml=latency_test_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'latency_measurement',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_failure_scenario_tests(self) -> Dict:
        """Run failure scenario tests."""
        logger.info("💥 Running failure scenario tests...")
        
        test_args = [
            'tests/test_e2e_integration.py::TestFailureScenarios',
            'tests/test_load_testing.py::TestFailureUnderLoad',
            '-v',
            '--tb=short',
            '--junit-xml=failure_scenario_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'failure_scenarios',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_stability_tests(self, duration_minutes: int = 5) -> Dict:
        """Run long-running stability tests."""
        logger.info(f"🔄 Running stability tests (duration: {duration_minutes} minutes)...")
        
        # Set stability test duration
        os.environ['STABILITY_TEST_DURATION'] = str(duration_minutes * 60)
        
        test_args = [
            'tests/test_e2e_integration.py::TestStabilityAndLongRunning',
            '-v',
            '--tb=short',
            '-m', 'slow',
            f'--timeout={duration_minutes * 60 + 120}',  # Add 2 minutes buffer
            '--junit-xml=stability_test_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'stability_testing',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'duration_minutes': duration_minutes,
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_performance_regression_tests(self) -> Dict:
        """Run performance regression tests."""
        logger.info("📊 Running performance regression tests...")
        
        test_args = [
            'tests/test_performance_regression.py',
            'tests/test_e2e_integration.py::TestPerformanceRegression',
            '-v',
            '--tb=short',
            '--junit-xml=performance_regression_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'performance_regression',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_system_integration_tests(self) -> Dict:
        """Run full system integration tests."""
        logger.info("🔧 Running system integration tests...")
        
        test_args = [
            'tests/test_e2e_integration.py::TestSystemIntegration',
            '-v',
            '--tb=short',
            '--junit-xml=system_integration_results.xml'
        ]
        
        result = pytest.main(test_args)
        
        return {
            'test_category': 'system_integration',
            'exit_code': result,
            'status': 'PASSED' if result == 0 else 'FAILED',
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def run_all_tests(self, stability_duration: int = 5, skip_slow: bool = False) -> Dict:
        """Run all end-to-end integration tests."""
        logger.info("🚀 Starting comprehensive end-to-end integration tests...")
        self.start_time = time.time()
        
        # Setup test environment
        self.setup_test_environment()
        
        # Run all test categories
        test_categories = [
            ('conversation_flow', self.run_conversation_flow_tests),
            ('latency_measurement', self.run_latency_tests),
            ('failure_scenarios', self.run_failure_scenario_tests),
            ('system_integration', self.run_system_integration_tests),
            ('load_testing', self.run_load_tests),
            ('performance_regression', self.run_performance_regression_tests),
        ]
        
        # Add stability tests if not skipping slow tests
        if not skip_slow:
            test_categories.append(('stability_testing', lambda: self.run_stability_tests(stability_duration)))
        
        results = {}
        overall_status = 'PASSED'
        
        for category_name, test_function in test_categories:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running {category_name} tests...")
            logger.info(f"{'='*60}")
            
            try:
                category_result = test_function()
                results[category_name] = category_result
                
                if category_result['status'] == 'FAILED':
                    overall_status = 'FAILED'
                    logger.error(f"❌ {category_name} tests FAILED")
                else:
                    logger.info(f"✅ {category_name} tests PASSED")
                    
            except Exception as e:
                logger.error(f"❌ {category_name} tests encountered an error: {e}")
                results[category_name] = {
                    'test_category': category_name,
                    'exit_code': -1,
                    'status': 'ERROR',
                    'error': str(e),
                    'timestamp': datetime.now(UTC).isoformat()
                }
                overall_status = 'FAILED'
        
        self.end_time = time.time()
        total_duration = self.end_time - self.start_time
        
        # Compile final results
        final_results = {
            'overall_status': overall_status,
            'total_duration_seconds': total_duration,
            'total_duration_minutes': total_duration / 60,
            'start_time': datetime.fromtimestamp(self.start_time, UTC).isoformat(),
            'end_time': datetime.fromtimestamp(self.end_time, UTC).isoformat(),
            'test_categories': results,
            'summary': self.generate_summary(results)
        }
        
        # Save results to file
        self.save_results(final_results)
        
        # Print summary
        self.print_summary(final_results)
        
        return final_results
    
    def generate_summary(self, results: Dict) -> Dict:
        """Generate test summary statistics."""
        total_categories = len(results)
        passed_categories = sum(1 for r in results.values() if r['status'] == 'PASSED')
        failed_categories = sum(1 for r in results.values() if r['status'] == 'FAILED')
        error_categories = sum(1 for r in results.values() if r['status'] == 'ERROR')
        
        return {
            'total_categories': total_categories,
            'passed_categories': passed_categories,
            'failed_categories': failed_categories,
            'error_categories': error_categories,
            'success_rate': passed_categories / total_categories if total_categories > 0 else 0
        }
    
    def save_results(self, results: Dict):
        """Save test results to file."""
        results_file = f"e2e_test_results_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"📄 Test results saved to {results_file}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")
    
    def print_summary(self, results: Dict):
        """Print test summary to console."""
        logger.info("\n" + "="*80)
        logger.info("🏁 END-TO-END INTEGRATION TEST SUMMARY")
        logger.info("="*80)
        
        logger.info(f"Overall Status: {results['overall_status']}")
        logger.info(f"Total Duration: {results['total_duration_minutes']:.1f} minutes")
        logger.info(f"Start Time: {results['start_time']}")
        logger.info(f"End Time: {results['end_time']}")
        
        logger.info("\nTest Category Results:")
        logger.info("-" * 40)
        
        for category, result in results['test_categories'].items():
            status_emoji = "✅" if result['status'] == 'PASSED' else "❌" if result['status'] == 'FAILED' else "⚠️"
            logger.info(f"{status_emoji} {category}: {result['status']}")
        
        summary = results['summary']
        logger.info(f"\nSummary Statistics:")
        logger.info(f"- Total Categories: {summary['total_categories']}")
        logger.info(f"- Passed: {summary['passed_categories']}")
        logger.info(f"- Failed: {summary['failed_categories']}")
        logger.info(f"- Errors: {summary['error_categories']}")
        logger.info(f"- Success Rate: {summary['success_rate']:.1%}")
        
        if results['overall_status'] == 'PASSED':
            logger.info("\n🎉 ALL END-TO-END INTEGRATION TESTS PASSED!")
        else:
            logger.error("\n💥 SOME END-TO-END INTEGRATION TESTS FAILED!")
        
        logger.info("="*80)


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description='Run end-to-end integration tests for Voice AI Agent')
    
    parser.add_argument(
        '--category',
        choices=[
            'all', 'conversation_flow', 'load_testing', 'latency_measurement',
            'failure_scenarios', 'stability_testing', 'performance_regression',
            'system_integration'
        ],
        default='all',
        help='Test category to run (default: all)'
    )
    
    parser.add_argument(
        '--stability-duration',
        type=int,
        default=5,
        help='Duration for stability tests in minutes (default: 5)'
    )
    
    parser.add_argument(
        '--skip-slow',
        action='store_true',
        help='Skip slow tests (stability tests)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = E2ETestRunner()
    
    try:
        if args.category == 'all':
            results = runner.run_all_tests(
                stability_duration=args.stability_duration,
                skip_slow=args.skip_slow
            )
        else:
            # Run specific category
            runner.setup_test_environment()
            
            category_methods = {
                'conversation_flow': runner.run_conversation_flow_tests,
                'load_testing': runner.run_load_tests,
                'latency_measurement': runner.run_latency_tests,
                'failure_scenarios': runner.run_failure_scenario_tests,
                'stability_testing': lambda: runner.run_stability_tests(args.stability_duration),
                'performance_regression': runner.run_performance_regression_tests,
                'system_integration': runner.run_system_integration_tests
            }
            
            if args.category in category_methods:
                result = category_methods[args.category]()
                logger.info(f"Test category '{args.category}' completed with status: {result['status']}")
                results = {'overall_status': result['status']}
            else:
                logger.error(f"Unknown test category: {args.category}")
                return 1
        
        # Return appropriate exit code
        return 0 if results['overall_status'] == 'PASSED' else 1
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Test execution interrupted by user")
        return 130
    
    except Exception as e:
        logger.error(f"❌ Test execution failed with error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
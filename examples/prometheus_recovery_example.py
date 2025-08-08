#!/usr/bin/env python3
"""
Prometheus Recovery System Example

This example demonstrates how to use the Prometheus auto-recovery system
to automatically detect and fix Prometheus service failures.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.monitoring.prometheus_recovery import (
    PrometheusRecovery,
    recover_prometheus,
    create_fallback_prometheus_config
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def basic_recovery_example():
    """Basic example of Prometheus recovery."""
    logger.info("=== Basic Recovery Example ===")
    
    # Simple recovery using convenience function
    result = await recover_prometheus(
        prometheus_url="http://localhost:9091",
        config_path="monitoring/prometheus/prometheus.yml"
    )
    
    logger.info(f"Recovery result: {result.success}")
    logger.info(f"Final status: {result.final_status}")
    
    if result.error_message:
        logger.error(f"Error: {result.error_message}")
    
    logger.info("Actions taken:")
    for action in result.actions_taken:
        logger.info(f"  - {action.action_type}: {action.details} "
                   f"(success: {action.success}, duration: {action.duration_seconds:.2f}s)")


async def advanced_recovery_example():
    """Advanced example with custom configuration."""
    logger.info("=== Advanced Recovery Example ===")
    
    # Create recovery instance with custom settings
    recovery = PrometheusRecovery(
        prometheus_url="http://localhost:9091",
        config_path="monitoring/prometheus/prometheus.yml",
        docker_compose_path="docker-compose.yml",
        max_retries=5,
        base_delay=2.0
    )
    
    # Attempt recovery
    result = await recovery.attempt_recovery()
    
    logger.info(f"Recovery completed: {result.success}")
    logger.info(f"Final status: {result.final_status}")
    
    # Show detailed action history
    logger.info("Detailed recovery actions:")
    for i, action in enumerate(result.actions_taken, 1):
        logger.info(f"  {i}. {action.action_type.upper()}")
        logger.info(f"     Time: {action.timestamp}")
        logger.info(f"     Success: {action.success}")
        logger.info(f"     Details: {action.details}")
        logger.info(f"     Duration: {action.duration_seconds:.2f}s")
        logger.info("")


async def retry_mechanism_example():
    """Example of using the retry mechanism."""
    logger.info("=== Retry Mechanism Example ===")
    
    recovery = PrometheusRecovery()
    
    # Example operation that might fail
    attempt_count = 0
    
    async def flaky_operation():
        nonlocal attempt_count
        attempt_count += 1
        logger.info(f"Attempting operation (attempt {attempt_count})")
        
        # Simulate failure on first two attempts
        if attempt_count < 3:
            raise Exception(f"Simulated failure on attempt {attempt_count}")
        
        return True
    
    # Use retry mechanism
    success, details = await recovery.retry_with_exponential_backoff(
        flaky_operation,
        max_attempts=5,
        base_delay=0.5
    )
    
    logger.info(f"Retry result: {success}")
    logger.info(f"Details: {details}")
    logger.info(f"Total attempts made: {attempt_count}")


def fallback_config_example():
    """Example of creating fallback configuration."""
    logger.info("=== Fallback Configuration Example ===")
    
    # Create fallback configuration
    config_path = "examples/fallback_prometheus.yml"
    create_fallback_prometheus_config(config_path)
    
    logger.info(f"Fallback configuration created at: {config_path}")
    
    # Read and display the configuration
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    logger.info("Generated configuration:")
    logger.info(config_content)


async def periodic_monitoring_example():
    """Example of periodic monitoring and recovery."""
    logger.info("=== Periodic Monitoring Example ===")
    
    recovery = PrometheusRecovery()
    
    # This would run indefinitely in a real application
    # For demo purposes, we'll just show how to set it up
    logger.info("Setting up periodic monitoring (would run indefinitely)")
    logger.info("In a real application, this would:")
    logger.info("  1. Check Prometheus health every 5 minutes")
    logger.info("  2. Automatically attempt recovery if issues are detected")
    logger.info("  3. Log all recovery attempts and results")
    
    # Example of what the periodic check would do
    logger.info("Performing one-time health check...")
    
    # Check current status
    status_action = await recovery._check_service_status()
    
    if status_action.success:
        logger.info("✓ Prometheus is healthy - no action needed")
    else:
        logger.warning("✗ Prometheus health check failed - would trigger recovery")
        logger.info(f"Failure details: {status_action.details}")


async def comprehensive_example():
    """Comprehensive example showing all features."""
    logger.info("=== Comprehensive Recovery Example ===")
    
    try:
        # 1. Create fallback configuration first
        logger.info("1. Creating fallback configuration...")
        create_fallback_prometheus_config("examples/comprehensive_prometheus.yml")
        
        # 2. Initialize recovery system
        logger.info("2. Initializing recovery system...")
        recovery = PrometheusRecovery(
            prometheus_url="http://localhost:9091",
            config_path="examples/comprehensive_prometheus.yml",
            max_retries=3,
            base_delay=1.0
        )
        
        # 3. Check current status
        logger.info("3. Checking current Prometheus status...")
        status_action = await recovery._check_service_status()
        logger.info(f"   Status: {'✓ Healthy' if status_action.success else '✗ Unhealthy'}")
        logger.info(f"   Details: {status_action.details}")
        
        # 4. Validate configuration
        logger.info("4. Validating Prometheus configuration...")
        config_action = await recovery._validate_and_fix_config()
        logger.info(f"   Config: {'✓ Valid' if config_action.success else '✗ Invalid'}")
        logger.info(f"   Details: {config_action.details}")
        
        # 5. Attempt full recovery if needed
        if not status_action.success:
            logger.info("5. Attempting full recovery...")
            result = await recovery.attempt_recovery()
            
            logger.info(f"   Recovery: {'✓ Success' if result.success else '✗ Failed'}")
            logger.info(f"   Final status: {result.final_status}")
            
            if result.error_message:
                logger.error(f"   Error: {result.error_message}")
        else:
            logger.info("5. No recovery needed - service is healthy")
        
        # 6. Show recovery history
        logger.info("6. Recovery history:")
        history = recovery.get_recovery_history()
        if history:
            for action in history:
                logger.info(f"   - {action.timestamp}: {action.action_type} "
                           f"({'✓' if action.success else '✗'})")
        else:
            logger.info("   No recovery actions in history")
        
    except Exception as e:
        logger.error(f"Comprehensive example failed: {str(e)}")


async def main():
    """Run all examples."""
    logger.info("Starting Prometheus Recovery Examples")
    logger.info("=" * 50)
    
    try:
        # Run examples
        await basic_recovery_example()
        print()
        
        await advanced_recovery_example()
        print()
        
        await retry_mechanism_example()
        print()
        
        fallback_config_example()
        print()
        
        await periodic_monitoring_example()
        print()
        
        await comprehensive_example()
        
    except KeyboardInterrupt:
        logger.info("Examples interrupted by user")
    except Exception as e:
        logger.error(f"Examples failed with error: {str(e)}")
    
    logger.info("=" * 50)
    logger.info("Prometheus Recovery Examples completed")


if __name__ == "__main__":
    asyncio.run(main())
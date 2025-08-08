"""
Example usage of the Metrics Endpoint Verification System

This example demonstrates how to use the MetricsEndpointVerifier to:
1. Test endpoint accessibility
2. Validate Prometheus metrics format
3. Verify health endpoints
4. Perform comprehensive scrape target verification
"""

import asyncio
import json
import logging
from pathlib import Path

from src.monitoring.metrics_endpoint_verifier import (
    MetricsEndpointVerifier,
    verify_endpoint,
    validate_metrics,
    verify_health,
    verify_all_targets
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_endpoint_verification():
    """Example of basic endpoint verification."""
    print("🔍 Example 1: Basic Endpoint Verification")
    print("-" * 50)
    
    # Test various endpoints
    endpoints = [
        "http://localhost:8000/metrics",
        "http://localhost:8000/health",
        "http://localhost:9091/metrics",  # Prometheus
        "http://httpbin.org/status/200",  # External test endpoint
        "http://nonexistent.example.com/metrics"  # Should fail
    ]
    
    for endpoint in endpoints:
        try:
            result = await verify_endpoint(endpoint)
            status = "✅ ACCESSIBLE" if result.accessible else "❌ FAILED"
            print(f"{status} {endpoint}")
            print(f"  Status: {result.status_code}")
            print(f"  Response time: {result.response_time_ms}ms")
            if result.error_message:
                print(f"  Error: {result.error_message}")
            print()
        except Exception as e:
            print(f"❌ ERROR {endpoint}: {e}")
            print()


async def example_metrics_validation():
    """Example of metrics format validation."""
    print("📊 Example 2: Metrics Format Validation")
    print("-" * 50)
    
    # Test metrics endpoints
    metrics_endpoints = [
        "http://localhost:8000/metrics",
        "http://localhost:9091/metrics",  # Prometheus self-metrics
    ]
    
    for endpoint in metrics_endpoints:
        try:
            result = await validate_metrics(endpoint)
            status = "✅ VALID" if result.prometheus_compliant else "❌ INVALID"
            print(f"{status} {endpoint}")
            print(f"  Format valid: {result.valid_format}")
            print(f"  Prometheus compliant: {result.prometheus_compliant}")
            print(f"  Metrics count: {result.metrics_count}")
            print(f"  Valid metrics: {result.valid_metrics[:5]}")  # Show first 5
            
            if result.format_errors:
                print(f"  Format errors: {result.format_errors[:3]}")  # Show first 3
            
            if result.sample_metrics:
                print(f"  Sample metrics:")
                for sample in result.sample_metrics[:3]:
                    print(f"    {sample}")
            print()
        except Exception as e:
            print(f"❌ ERROR {endpoint}: {e}")
            print()


async def example_health_verification():
    """Example of health endpoint verification."""
    print("🏥 Example 3: Health Endpoint Verification")
    print("-" * 50)
    
    # Test health endpoints
    health_endpoints = [
        "http://localhost:8000/health",
        "http://localhost:9091/-/healthy",  # Prometheus health
        "http://httpbin.org/json",  # Returns JSON (for testing)
    ]
    
    for endpoint in health_endpoints:
        try:
            result = await verify_health(endpoint)
            status = "✅ HEALTHY" if result.healthy else "❌ UNHEALTHY"
            print(f"{status} {endpoint}")
            print(f"  Status code: {result.status_code}")
            print(f"  Response time: {result.response_time_ms}ms")
            print(f"  Health checks: {result.health_checks}")
            
            if result.error_message:
                print(f"  Error: {result.error_message}")
            print()
        except Exception as e:
            print(f"❌ ERROR {endpoint}: {e}")
            print()


async def example_comprehensive_verification():
    """Example of comprehensive scrape target verification."""
    print("🎯 Example 4: Comprehensive Scrape Target Verification")
    print("-" * 50)
    
    verifier = MetricsEndpointVerifier(timeout=10)
    
    try:
        # Test individual scrape targets
        targets = [
            {
                "job_name": "voice-ai-agent",
                "target": "localhost:8000",
                "metrics_path": "/metrics",
                "health_path": "/health"
            },
            {
                "job_name": "prometheus",
                "target": "localhost:9091",
                "metrics_path": "/metrics",
                "health_path": "/-/healthy"
            }
        ]
        
        for target_config in targets:
            try:
                result = await verifier.verify_scrape_target(
                    job_name=target_config["job_name"],
                    target=target_config["target"],
                    metrics_path=target_config["metrics_path"],
                    health_path=target_config["health_path"]
                )
                
                status_icon = {
                    "healthy": "✅",
                    "degraded": "⚠️",
                    "failed": "❌"
                }.get(result.overall_status, "❓")
                
                print(f"{status_icon} {result.job_name} ({result.target})")
                print(f"  Overall status: {result.overall_status.upper()}")
                print(f"  Endpoint accessible: {result.endpoint_result.accessible}")
                
                if result.metrics_validation:
                    print(f"  Metrics compliant: {result.metrics_validation.prometheus_compliant}")
                    print(f"  Metrics count: {result.metrics_validation.metrics_count}")
                
                if result.health_result:
                    print(f"  Health status: {'healthy' if result.health_result.healthy else 'unhealthy'}")
                
                if result.recommendations:
                    print(f"  Recommendations:")
                    for rec in result.recommendations[:3]:  # Show first 3
                        print(f"    • {rec}")
                print()
                
            except Exception as e:
                print(f"❌ ERROR verifying {target_config['job_name']}: {e}")
                print()
    
    finally:
        verifier.close()


async def example_config_based_verification():
    """Example of verifying all targets from Prometheus configuration."""
    print("⚙️ Example 5: Configuration-Based Verification")
    print("-" * 50)
    
    config_path = "monitoring/prometheus/prometheus.yml"
    
    if not Path(config_path).exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("Creating example configuration for demonstration...")
        
        # Create example config for demonstration
        example_config = """
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'voice-ai-agent'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
    
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9091']
    metrics_path: /metrics
"""
        
        # For demo purposes, we'll use a temporary config
        import tempfile
        import yaml
        
        config_data = yaml.safe_load(example_config)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        print(f"✅ Created temporary config: {config_path}")
    
    try:
        result = await verify_all_targets(config_path)
        
        summary = result["summary"]
        print(f"📊 Verification Summary:")
        print(f"  Total targets: {summary['total_targets']}")
        print(f"  Healthy: {summary['healthy_targets']}")
        print(f"  Degraded: {summary['degraded_targets']}")
        print(f"  Failed: {summary['failed_targets']}")
        print(f"  Health percentage: {summary['health_percentage']:.1f}%")
        print(f"  Overall status: {summary['overall_status'].upper()}")
        print()
        
        print("🎯 Individual Target Results:")
        for target_result in result["verification_results"]:
            status_icon = {
                "healthy": "✅",
                "degraded": "⚠️",
                "failed": "❌"
            }.get(target_result["overall_status"], "❓")
            
            print(f"{status_icon} {target_result['job_name']} -> {target_result['target']}")
            print(f"  Status: {target_result['overall_status']}")
            
            if target_result["endpoint_result"]:
                ep = target_result["endpoint_result"]
                print(f"  Endpoint: {'accessible' if ep['accessible'] else 'failed'} ({ep['response_time_ms']}ms)")
            
            if target_result["metrics_validation"]:
                mv = target_result["metrics_validation"]
                print(f"  Metrics: {'compliant' if mv['prometheus_compliant'] else 'non-compliant'} ({mv['metrics_count']} metrics)")
            
            if target_result["health_result"]:
                hr = target_result["health_result"]
                print(f"  Health: {'healthy' if hr['healthy'] else 'unhealthy'}")
            
            print()
        
        print("💡 Overall Recommendations:")
        for rec in result["recommendations"][:5]:  # Show first 5
            print(f"  • {rec}")
        print()
        
    except Exception as e:
        print(f"❌ ERROR during configuration-based verification: {e}")
    
    finally:
        # Clean up temporary file if created
        if config_path.startswith('/tmp'):
            try:
                Path(config_path).unlink()
                print(f"🧹 Cleaned up temporary config: {config_path}")
            except Exception:
                pass


async def example_custom_verifier():
    """Example of using custom verifier with specific settings."""
    print("🔧 Example 6: Custom Verifier Configuration")
    print("-" * 50)
    
    # Create verifier with custom settings
    verifier = MetricsEndpointVerifier(
        timeout=5,  # Shorter timeout
        max_retries=1  # Fewer retries
    )
    
    try:
        print("Testing with custom timeout and retry settings...")
        
        # Test a slow endpoint (httpbin delay)
        slow_endpoint = "http://httpbin.org/delay/3"  # 3 second delay
        
        result = await verifier.verify_endpoint_accessibility(slow_endpoint)
        
        print(f"Slow endpoint test: {slow_endpoint}")
        print(f"  Accessible: {result.accessible}")
        print(f"  Response time: {result.response_time_ms}ms")
        if result.error_message:
            print(f"  Error: {result.error_message}")
        print()
        
        # Test metrics validation with custom settings
        print("Testing metrics validation with custom settings...")
        
        # This should be fast
        fast_endpoint = "http://httpbin.org/status/200"
        result = await verifier.verify_endpoint_accessibility(fast_endpoint)
        
        print(f"Fast endpoint test: {fast_endpoint}")
        print(f"  Accessible: {result.accessible}")
        print(f"  Response time: {result.response_time_ms}ms")
        print()
        
    finally:
        verifier.close()


async def example_error_handling():
    """Example of error handling in verification."""
    print("⚠️ Example 7: Error Handling")
    print("-" * 50)
    
    # Test various error conditions
    error_cases = [
        ("Connection refused", "http://localhost:99999/metrics"),
        ("DNS resolution failure", "http://nonexistent-domain-12345.com/metrics"),
        ("Timeout", "http://httpbin.org/delay/30"),  # Very long delay
        ("HTTP 404", "http://httpbin.org/status/404"),
        ("HTTP 500", "http://httpbin.org/status/500"),
    ]
    
    for error_type, endpoint in error_cases:
        print(f"Testing {error_type}: {endpoint}")
        
        try:
            result = await verify_endpoint(endpoint)
            
            print(f"  Accessible: {result.accessible}")
            print(f"  Status code: {result.status_code}")
            print(f"  Response time: {result.response_time_ms}ms")
            if result.error_message:
                print(f"  Error: {result.error_message}")
            print()
            
        except Exception as e:
            print(f"  Exception caught: {e}")
            print()


async def main():
    """Run all examples."""
    print("🚀 Metrics Endpoint Verification System Examples")
    print("=" * 60)
    print()
    
    examples = [
        example_endpoint_verification,
        example_metrics_validation,
        example_health_verification,
        example_comprehensive_verification,
        example_config_based_verification,
        example_custom_verifier,
        example_error_handling
    ]
    
    for i, example_func in enumerate(examples, 1):
        try:
            await example_func()
        except Exception as e:
            print(f"❌ Error in example {i}: {e}")
            print()
        
        if i < len(examples):
            print("⏳ Waiting 2 seconds before next example...")
            await asyncio.sleep(2)
            print()
    
    print("✅ All examples completed!")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
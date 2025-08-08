#!/usr/bin/env python3
"""
Example usage of Prometheus Health Check and Diagnostic System.

This example demonstrates how to use the Prometheus health checking
and diagnostic capabilities in your applications.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.prometheus_health import (
    PrometheusHealthChecker,
    check_prometheus_health,
    diagnose_prometheus_issues,
    generate_prometheus_report
)


async def basic_health_check_example():
    """Example of basic Prometheus health check."""
    print("=" * 60)
    print("🔍 BASIC PROMETHEUS HEALTH CHECK EXAMPLE")
    print("=" * 60)
    
    try:
        # Use convenience function for quick health check
        health_result = await check_prometheus_health()
        
        print(f"📊 Status: {health_result.status}")
        print(f"🔧 Service Running: {health_result.service_running}")
        print(f"📝 Config Valid: {health_result.config_valid}")
        print(f"⏱️  Response Time: {health_result.response_time_ms}ms")
        
        if health_result.error_messages:
            print("\n❌ Issues Found:")
            for error in health_result.error_messages:
                print(f"  • {error}")
        
        if health_result.recovery_actions:
            print("\n🔧 Recovery Actions:")
            for action in health_result.recovery_actions:
                print(f"  • {action}")
        
        return health_result.status == "healthy"
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def detailed_health_check_example():
    """Example of detailed Prometheus health check with custom configuration."""
    print("\n" + "=" * 60)
    print("🔍 DETAILED PROMETHEUS HEALTH CHECK EXAMPLE")
    print("=" * 60)
    
    # Create health checker with custom settings
    checker = PrometheusHealthChecker(
        prometheus_url="http://localhost:9091",
        config_path="monitoring/prometheus/prometheus.yml",
        timeout=15
    )
    
    try:
        # Perform comprehensive health check
        health_result = await checker.comprehensive_health_check()
        
        print(f"📊 Overall Status: {health_result.status.upper()}")
        print(f"🕐 Timestamp: {health_result.timestamp}")
        print(f"⏱️  Response Time: {health_result.response_time_ms}ms")
        
        if health_result.version:
            print(f"📦 Prometheus Version: {health_result.version}")
        
        if health_result.uptime_seconds:
            uptime_hours = health_result.uptime_seconds / 3600
            print(f"⏰ Uptime: {uptime_hours:.1f} hours")
        
        # Show endpoint accessibility
        print("\n🌐 Endpoint Accessibility:")
        for endpoint, accessible in health_result.endpoints_accessible.items():
            status = "✅" if accessible else "❌"
            print(f"  {status} {endpoint}")
        
        # Show configuration validation
        config_status = await checker._validate_configuration()
        print(f"\n📝 Configuration Status:")
        print(f"  YAML Valid: {'✅' if config_status.yaml_valid else '❌'}")
        print(f"  Scrape Configs: {len(config_status.scrape_configs)}")
        
        if config_status.validation_errors:
            print("  Validation Errors:")
            for error in config_status.validation_errors:
                print(f"    • {error}")
        
        return health_result.status == "healthy"
        
    except Exception as e:
        print(f"❌ Detailed health check failed: {e}")
        return False
    finally:
        checker.close()


async def diagnostic_example():
    """Example of Prometheus diagnostic and troubleshooting."""
    print("\n" + "=" * 60)
    print("🔍 PROMETHEUS DIAGNOSTIC EXAMPLE")
    print("=" * 60)
    
    try:
        # Run diagnostic analysis
        diagnosis = await diagnose_prometheus_issues()
        
        print(f"📊 Overall Status: {diagnosis.get('overall_status', 'unknown').upper()}")
        print(f"🕐 Diagnosis Time: {diagnosis.get('timestamp', 'unknown')}")
        
        # Show issues found
        issues = diagnosis.get('issues_found', [])
        if issues:
            print(f"\n❌ Issues Found ({len(issues)}):")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("\n✅ No issues detected")
        
        # Show root causes
        root_causes = diagnosis.get('root_causes', [])
        if root_causes:
            print(f"\n🔍 Potential Root Causes:")
            for cause in root_causes[:5]:  # Show top 5
                print(f"  • {cause}")
        
        # Show troubleshooting steps
        steps = diagnosis.get('troubleshooting_steps', [])
        if steps:
            print(f"\n🔧 Troubleshooting Steps:")
            for i, step in enumerate(steps[:5], 1):  # Show top 5
                print(f"  {i}. {step}")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        return False


async def comprehensive_report_example():
    """Example of generating comprehensive Prometheus health report."""
    print("\n" + "=" * 60)
    print("📋 COMPREHENSIVE PROMETHEUS REPORT EXAMPLE")
    print("=" * 60)
    
    try:
        # Generate comprehensive report
        report = await generate_prometheus_report()
        
        print(f"📊 Report Generated: {report['report_timestamp']}")
        print(f"🌐 Prometheus URL: {report['prometheus_url']}")
        print(f"📝 Config Path: {report['config_path']}")
        
        # Show health check summary
        health = report['health_check']
        print(f"\n🏥 Health Check Summary:")
        print(f"  Status: {health['status'].upper()}")
        print(f"  Service Running: {'✅' if health['service_running'] else '❌'}")
        print(f"  Config Valid: {'✅' if health['config_valid'] else '❌'}")
        print(f"  Response Time: {health['response_time_ms']}ms")
        
        # Show configuration summary
        config = report['configuration_status']
        print(f"\n📝 Configuration Summary:")
        print(f"  YAML Valid: {'✅' if config['yaml_valid'] else '❌'}")
        print(f"  Scrape Configs: {len(config['scrape_configs'])}")
        print(f"  Validation Errors: {len(config['validation_errors'])}")
        
        # Show recommendations
        recommendations = report.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Recommendations ({len(recommendations)}):")
            for rec in recommendations[:5]:  # Show top 5
                print(f"  • {rec}")
        
        # Save report to file
        report_file = "prometheus_health_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Full report saved to: {report_file}")
        
        return health['status'] == 'healthy'
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return False


async def monitoring_integration_example():
    """Example of integrating Prometheus health checks into monitoring."""
    print("\n" + "=" * 60)
    print("📊 MONITORING INTEGRATION EXAMPLE")
    print("=" * 60)
    
    # Simulate a monitoring loop
    print("🔄 Starting monitoring loop (3 iterations)...")
    
    healthy_count = 0
    total_checks = 3
    
    for i in range(total_checks):
        print(f"\n--- Check {i+1}/{total_checks} ---")
        
        try:
            # Quick health check
            health_result = await check_prometheus_health()
            
            status_icon = {
                'healthy': '✅',
                'degraded': '⚠️',
                'failed': '❌'
            }.get(health_result.status, '❓')
            
            print(f"{status_icon} Status: {health_result.status}")
            print(f"⏱️  Response: {health_result.response_time_ms}ms")
            
            if health_result.status == 'healthy':
                healthy_count += 1
            elif health_result.status == 'failed':
                print("🚨 Alert: Prometheus service is down!")
                # In real monitoring, you would send alerts here
            
            # Simulate monitoring interval
            if i < total_checks - 1:
                print("⏳ Waiting 2 seconds...")
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"❌ Monitoring check failed: {e}")
    
    # Summary
    health_percentage = (healthy_count / total_checks) * 100
    print(f"\n📊 Monitoring Summary:")
    print(f"  Total Checks: {total_checks}")
    print(f"  Healthy Checks: {healthy_count}")
    print(f"  Health Percentage: {health_percentage:.1f}%")
    
    if health_percentage >= 100:
        print("🎉 Prometheus is consistently healthy!")
    elif health_percentage >= 66:
        print("⚠️  Prometheus has intermittent issues")
    else:
        print("🚨 Prometheus has serious health issues")
    
    return health_percentage >= 66


async def main():
    """Run all examples."""
    print("🔍 PROMETHEUS HEALTH CHECK EXAMPLES")
    print("=" * 80)
    print("This script demonstrates various ways to use the Prometheus")
    print("health checking and diagnostic system.")
    print("=" * 80)
    
    examples = [
        ("Basic Health Check", basic_health_check_example),
        ("Detailed Health Check", detailed_health_check_example),
        ("Diagnostic Analysis", diagnostic_example),
        ("Comprehensive Report", comprehensive_report_example),
        ("Monitoring Integration", monitoring_integration_example)
    ]
    
    results = {}
    
    for name, example_func in examples:
        try:
            print(f"\n🚀 Running: {name}")
            success = await example_func()
            results[name] = success
            
            if success:
                print(f"✅ {name} completed successfully")
            else:
                print(f"⚠️  {name} completed with issues")
                
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = False
    
    # Final summary
    print("\n" + "=" * 80)
    print("📊 EXAMPLES SUMMARY")
    print("=" * 80)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    print(f"\n📈 Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
    
    if successful == total:
        print("🎉 All examples completed successfully!")
    elif successful > 0:
        print("⚠️  Some examples had issues - check Prometheus setup")
    else:
        print("🚨 All examples failed - Prometheus may not be running")
    
    return successful > 0


if __name__ == "__main__":
    # Run examples
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
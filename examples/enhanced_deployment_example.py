#!/usr/bin/env python3
"""
Enhanced Deployment Example

This example demonstrates the enhanced deployment script capabilities
with comprehensive Prometheus monitoring, validation, and recovery.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_prometheus_deployment import PrometheusDeploymentValidator


async def demonstrate_enhanced_deployment():
    """Demonstrate enhanced deployment capabilities."""
    print("🚀 Enhanced Deployment with Prometheus Monitoring Demo")
    print("=" * 60)
    
    # Initialize validator
    validator = PrometheusDeploymentValidator()
    
    try:
        # 1. Pre-deployment validation
        print("\n📋 Step 1: Pre-deployment Validation")
        print("-" * 40)
        
        pre_results = await validator.run_pre_deployment_validation()
        
        print(f"Status: {pre_results['overall_status'].upper()}")
        print(f"Issues Found: {len(pre_results['issues'])}")
        
        if pre_results['issues']:
            print("Issues:")
            for issue in pre_results['issues']:
                print(f"  • {issue}")
        
        if pre_results['recommendations']:
            print("Recommendations:")
            for rec in pre_results['recommendations'][:3]:
                print(f"  • {rec}")
        
        # 2. Simulate deployment (in real scenario, this would be the actual deployment)
        print("\n🔧 Step 2: Deployment Simulation")
        print("-" * 40)
        print("In a real deployment, this would:")
        print("  • Start Docker containers")
        print("  • Configure services")
        print("  • Set up monitoring stack")
        print("  • Wait for services to be ready")
        
        # 3. Post-deployment verification
        print("\n✅ Step 3: Post-deployment Verification")
        print("-" * 40)
        
        post_results = await validator.run_post_deployment_verification()
        
        print(f"Status: {post_results['overall_status'].upper()}")
        print(f"Issues Found: {len(post_results['issues'])}")
        
        # Show detailed check results
        for check_name, check_data in post_results['checks'].items():
            if isinstance(check_data, dict):
                if 'status' in check_data:
                    status_emoji = "✅" if check_data['status'] == 'healthy' else "⚠️" if check_data['status'] == 'degraded' else "❌"
                    print(f"  {status_emoji} {check_name.replace('_', ' ').title()}: {check_data['status']}")
                elif 'all_accessible' in check_data:
                    status_emoji = "✅" if check_data['all_accessible'] else "❌"
                    print(f"  {status_emoji} {check_name.replace('_', ' ').title()}: {'All accessible' if check_data['all_accessible'] else 'Some issues'}")
                elif 'collecting_data' in check_data:
                    status_emoji = "✅" if check_data['collecting_data'] else "❌"
                    print(f"  {status_emoji} {check_name.replace('_', ' ').title()}: {'Collecting data' if check_data['collecting_data'] else 'Not collecting'}")
        
        # 4. Recovery demonstration (if needed)
        if post_results['overall_status'] == 'failed':
            print("\n🔧 Step 4: Automatic Recovery")
            print("-" * 40)
            
            recovery_results = await validator.attempt_deployment_recovery()
            
            print(f"Recovery Status: {recovery_results['overall_status'].upper()}")
            print("Recovery Actions:")
            for action in recovery_results['recovery_actions']:
                status_emoji = "✅" if action['success'] else "❌"
                print(f"  {status_emoji} {action['action_type']}: {action['details']}")
        
        # 5. Generate comprehensive report
        print("\n📊 Step 5: Comprehensive Report")
        print("-" * 40)
        
        report = validator.generate_validation_report(
            pre_deployment=pre_results,
            post_deployment=post_results
        )
        
        print(f"Overall Assessment: {report['overall_assessment'].replace('_', ' ').title()}")
        print(f"Total Issues: {report['summary']['total_issues']}")
        
        if report['summary']['recommendations']:
            print("Key Recommendations:")
            for rec in report['summary']['recommendations'][:3]:
                print(f"  • {rec}")
        
        # 6. Demonstrate rollback capabilities
        print("\n🔄 Step 6: Rollback Capabilities")
        print("-" * 40)
        print("Enhanced deployment script provides:")
        print("  • Automatic backup creation before deployment")
        print("  • Configuration rollback on failure")
        print("  • Service state restoration")
        print("  • Comprehensive failure logging")
        
        # 7. Show monitoring integration
        print("\n📈 Step 7: Monitoring Integration")
        print("-" * 40)
        print("Enhanced monitoring includes:")
        print("  • Real-time Prometheus health checks")
        print("  • Scrape target verification")
        print("  • API endpoint validation")
        print("  • Data collection verification")
        print("  • Grafana integration checks")
        
        print("\n🎉 Enhanced Deployment Demo Complete!")
        print("=" * 60)
        
        return report
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        return None
    finally:
        validator.close()


async def demonstrate_validation_commands():
    """Demonstrate various validation commands."""
    print("\n🔍 Validation Commands Demo")
    print("=" * 40)
    
    commands = [
        ("Pre-deployment validation", "python scripts/validate_prometheus_deployment.py --phase pre"),
        ("Post-deployment verification", "python scripts/validate_prometheus_deployment.py --phase post"),
        ("Recovery attempt", "python scripts/validate_prometheus_deployment.py --phase recovery"),
        ("Full validation", "python scripts/validate_prometheus_deployment.py --phase all"),
        ("JSON output", "python scripts/validate_prometheus_deployment.py --json"),
        ("Verbose output", "python scripts/validate_prometheus_deployment.py --verbose")
    ]
    
    print("Available validation commands:")
    for description, command in commands:
        print(f"  • {description}:")
        print(f"    {command}")
    
    print("\nDeployment script commands:")
    deployment_commands = [
        ("Validate configuration", "./scripts/deploy_production.sh validate-config"),
        ("Prometheus health check", "./scripts/deploy_production.sh prometheus-health"),
        ("Prometheus recovery", "./scripts/deploy_production.sh prometheus-recover"),
        ("Deployment rollback", "./scripts/deploy_production.sh rollback"),
        ("Full deployment", "./scripts/deploy_production.sh start")
    ]
    
    for description, command in deployment_commands:
        print(f"  • {description}:")
        print(f"    {command}")


async def main():
    """Main demonstration function."""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Run main demo
        report = await demonstrate_enhanced_deployment()
        
        # Show command examples
        await demonstrate_validation_commands()
        
        # Show example usage scenarios
        print("\n📚 Usage Scenarios")
        print("=" * 40)
        
        scenarios = [
            {
                "name": "Development Deployment",
                "description": "Quick deployment with basic validation",
                "commands": [
                    "./scripts/deploy_production.sh validate-config",
                    "./scripts/deploy_production.sh start"
                ]
            },
            {
                "name": "Production Deployment",
                "description": "Full validation and monitoring setup",
                "commands": [
                    "python scripts/validate_prometheus_deployment.py --phase pre",
                    "./scripts/deploy_production.sh start",
                    "python scripts/validate_prometheus_deployment.py --phase post"
                ]
            },
            {
                "name": "Troubleshooting",
                "description": "Diagnose and recover from issues",
                "commands": [
                    "./scripts/deploy_production.sh prometheus-health",
                    "./scripts/deploy_production.sh prometheus-recover",
                    "python scripts/validate_prometheus_deployment.py --phase recovery"
                ]
            },
            {
                "name": "Rollback",
                "description": "Rollback failed deployment",
                "commands": [
                    "./scripts/deploy_production.sh rollback",
                    "./scripts/deploy_production.sh status"
                ]
            }
        ]
        
        for scenario in scenarios:
            print(f"\n{scenario['name']}:")
            print(f"  {scenario['description']}")
            for cmd in scenario['commands']:
                print(f"    {cmd}")
        
        print("\n✨ Enhanced deployment provides comprehensive monitoring,")
        print("   validation, and recovery capabilities for production deployments!")
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
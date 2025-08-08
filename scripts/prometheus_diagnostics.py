#!/usr/bin/env python3
"""
Prometheus Diagnostic Script

This script provides comprehensive diagnostics for Prometheus monitoring issues,
including automated root cause analysis and recovery recommendations.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.prometheus_health import PrometheusHealthChecker, generate_prometheus_report


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('prometheus_diagnostics.log')
        ]
    )


def print_banner():
    """Print diagnostic script banner."""
    print("=" * 80)
    print("🔍 PROMETHEUS DIAGNOSTIC SYSTEM")
    print("=" * 80)
    print("This script will perform comprehensive diagnostics of your Prometheus")
    print("monitoring system and provide detailed troubleshooting information.")
    print("=" * 80)
    print()


def print_section(title: str):
    """Print section header."""
    print(f"\n{'=' * 60}")
    print(f"📋 {title.upper()}")
    print("=" * 60)


async def run_basic_diagnostics(prometheus_url: str, config_path: str) -> dict:
    """Run basic diagnostic checks."""
    print_section("Basic System Checks")
    
    diagnostics = {
        "timestamp": datetime.now().isoformat(),
        "prometheus_url": prometheus_url,
        "config_path": config_path,
        "checks": {}
    }
    
    # Check if configuration file exists
    config_file = Path(config_path)
    if config_file.exists():
        print("✅ Configuration file exists")
        diagnostics["checks"]["config_file_exists"] = True
        
        # Check file permissions
        if os.access(config_file, os.R_OK):
            print("✅ Configuration file is readable")
            diagnostics["checks"]["config_file_readable"] = True
        else:
            print("❌ Configuration file is not readable")
            diagnostics["checks"]["config_file_readable"] = False
    else:
        print("❌ Configuration file not found")
        diagnostics["checks"]["config_file_exists"] = False
        diagnostics["checks"]["config_file_readable"] = False
    
    # Check Docker environment
    try:
        import subprocess
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker is available")
            diagnostics["checks"]["docker_available"] = True
        else:
            print("❌ Docker is not available")
            diagnostics["checks"]["docker_available"] = False
    except FileNotFoundError:
        print("❌ Docker command not found")
        diagnostics["checks"]["docker_available"] = False
    
    # Check Docker Compose
    try:
        result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker Compose is available")
            diagnostics["checks"]["docker_compose_available"] = True
        else:
            print("❌ Docker Compose is not available")
            diagnostics["checks"]["docker_compose_available"] = False
    except FileNotFoundError:
        print("❌ Docker Compose command not found")
        diagnostics["checks"]["docker_compose_available"] = False
    
    return diagnostics


async def check_docker_containers():
    """Check Docker container status."""
    print_section("Docker Container Status")
    
    try:
        import subprocess
        
        # Check if Prometheus container is running
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=voice-ai-prometheus', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and len(output.split('\n')) > 1:
                print("📊 Prometheus Container Status:")
                print(output)
                return True
            else:
                print("❌ Prometheus container is not running")
                
                # Check if container exists but is stopped
                result = subprocess.run(
                    ['docker', 'ps', '-a', '--filter', 'name=voice-ai-prometheus', '--format', 'table {{.Names}}\t{{.Status}}'],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    print("📊 Stopped Prometheus Container:")
                    print(result.stdout.strip())
                    print("\n💡 Container exists but is stopped. Try: docker-compose up -d prometheus")
                else:
                    print("❌ Prometheus container does not exist")
                    print("💡 Try: docker-compose up -d to create and start containers")
                
                return False
        else:
            print(f"❌ Error checking Docker containers: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking Docker containers: {e}")
        return False


async def check_network_connectivity(prometheus_url: str):
    """Check network connectivity to Prometheus."""
    print_section("Network Connectivity")
    
    try:
        import requests
        from urllib.parse import urlparse
        
        parsed_url = urlparse(prometheus_url)
        host = parsed_url.hostname
        port = parsed_url.port or 80
        
        print(f"🌐 Testing connectivity to {host}:{port}")
        
        # Test basic TCP connectivity
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print("✅ TCP connection successful")
                
                # Test HTTP connectivity
                try:
                    response = requests.get(f"{prometheus_url}/-/healthy", timeout=10)
                    if response.status_code == 200:
                        print("✅ HTTP health check successful")
                        return True
                    else:
                        print(f"⚠️  HTTP health check returned status {response.status_code}")
                        return False
                except requests.exceptions.RequestException as e:
                    print(f"❌ HTTP request failed: {e}")
                    return False
            else:
                print(f"❌ TCP connection failed (error code: {result})")
                return False
        finally:
            sock.close()
            
    except Exception as e:
        print(f"❌ Network connectivity check failed: {e}")
        return False


async def analyze_logs():
    """Analyze Docker container logs for issues."""
    print_section("Log Analysis")
    
    try:
        import subprocess
        
        # Get Prometheus container logs
        result = subprocess.run(
            ['docker', 'logs', '--tail', '50', 'voice-ai-prometheus'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            logs = result.stdout
            if logs:
                print("📋 Recent Prometheus Logs:")
                print("-" * 40)
                print(logs[-1000:])  # Show last 1000 characters
                print("-" * 40)
                
                # Analyze logs for common issues
                error_patterns = [
                    ("configuration", ["config", "yaml", "syntax"]),
                    ("network", ["connection", "refused", "timeout"]),
                    ("permission", ["permission", "denied", "access"]),
                    ("resource", ["memory", "disk", "space"]),
                    ("startup", ["failed", "error", "panic"])
                ]
                
                found_issues = []
                logs_lower = logs.lower()
                
                for issue_type, patterns in error_patterns:
                    if any(pattern in logs_lower for pattern in patterns):
                        found_issues.append(issue_type)
                
                if found_issues:
                    print(f"\n🔍 Potential Issues Detected: {', '.join(found_issues)}")
                else:
                    print("\n✅ No obvious issues found in logs")
                
                return logs
            else:
                print("📋 No logs available")
                return ""
        else:
            print(f"❌ Could not retrieve logs: {result.stderr}")
            return ""
            
    except Exception as e:
        print(f"❌ Log analysis failed: {e}")
        return ""


async def generate_recovery_plan(health_result: dict, diagnostics: dict) -> list:
    """Generate step-by-step recovery plan."""
    print_section("Recovery Plan")
    
    recovery_steps = []
    
    # Basic checks first
    if not diagnostics["checks"].get("docker_available", True):
        recovery_steps.append({
            "step": 1,
            "action": "Install Docker",
            "command": "curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh",
            "description": "Docker is required to run Prometheus containers"
        })
    
    if not diagnostics["checks"].get("docker_compose_available", True):
        recovery_steps.append({
            "step": len(recovery_steps) + 1,
            "action": "Install Docker Compose",
            "command": "pip install docker-compose",
            "description": "Docker Compose is required for orchestrating services"
        })
    
    # Configuration issues
    if not diagnostics["checks"].get("config_file_exists", True):
        recovery_steps.append({
            "step": len(recovery_steps) + 1,
            "action": "Create Prometheus configuration",
            "command": "cp monitoring/prometheus/prometheus.yml.example monitoring/prometheus/prometheus.yml",
            "description": "Create a basic Prometheus configuration file"
        })
    
    # Service issues
    if health_result and not health_result.get("service_running", False):
        recovery_steps.append({
            "step": len(recovery_steps) + 1,
            "action": "Start Prometheus service",
            "command": "docker-compose up -d prometheus",
            "description": "Start the Prometheus container"
        })
    
    # Network issues
    recovery_steps.append({
        "step": len(recovery_steps) + 1,
        "action": "Verify network connectivity",
        "command": "docker network ls && docker network inspect voice-ai-network",
        "description": "Check Docker network configuration"
    })
    
    # Final verification
    recovery_steps.append({
        "step": len(recovery_steps) + 1,
        "action": "Verify Prometheus health",
        "command": "python scripts/prometheus_diagnostics.py --verify",
        "description": "Run this script again to verify the fix"
    })
    
    print("🔧 Recommended Recovery Steps:")
    print()
    
    for step in recovery_steps:
        print(f"Step {step['step']}: {step['action']}")
        print(f"  Command: {step['command']}")
        print(f"  Description: {step['description']}")
        print()
    
    return recovery_steps


async def run_comprehensive_diagnostics(prometheus_url: str, config_path: str, output_file: str = None):
    """Run comprehensive diagnostics and generate report."""
    print_banner()
    
    # Run basic diagnostics
    basic_diagnostics = await run_basic_diagnostics(prometheus_url, config_path)
    
    # Check Docker containers
    container_running = await check_docker_containers()
    
    # Check network connectivity
    network_ok = await check_network_connectivity(prometheus_url)
    
    # Analyze logs
    logs = await analyze_logs()
    
    # Run Prometheus health check if service is accessible
    health_result = None
    if container_running and network_ok:
        try:
            print_section("Prometheus Health Check")
            report = await generate_prometheus_report(prometheus_url, config_path)
            health_result = report["health_check"]
            
            print(f"📊 Overall Status: {health_result['status'].upper()}")
            print(f"⏱️  Response Time: {health_result['response_time_ms']}ms")
            print(f"🔧 Service Running: {'✅' if health_result['service_running'] else '❌'}")
            print(f"📝 Config Valid: {'✅' if health_result['config_valid'] else '❌'}")
            
            if health_result['error_messages']:
                print("\n❌ Issues Found:")
                for error in health_result['error_messages']:
                    print(f"  • {error}")
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
    
    # Generate recovery plan
    recovery_steps = await generate_recovery_plan(health_result, basic_diagnostics)
    
    # Compile comprehensive report
    comprehensive_report = {
        "diagnostic_timestamp": datetime.now().isoformat(),
        "prometheus_url": prometheus_url,
        "config_path": config_path,
        "basic_diagnostics": basic_diagnostics,
        "container_running": container_running,
        "network_connectivity": network_ok,
        "logs_sample": logs[-500:] if logs else "",  # Last 500 chars
        "health_check": health_result,
        "recovery_steps": recovery_steps,
        "summary": {
            "total_issues": len([k for k, v in basic_diagnostics["checks"].items() if not v]),
            "critical_issues": not container_running or not network_ok,
            "recommended_action": "Follow recovery steps" if recovery_steps else "System appears healthy"
        }
    }
    
    # Save report if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(comprehensive_report, f, indent=2)
        print(f"\n📄 Comprehensive report saved to: {output_file}")
    
    # Print summary
    print_section("Diagnostic Summary")
    
    total_issues = comprehensive_report["summary"]["total_issues"]
    if total_issues == 0 and container_running and network_ok:
        print("🎉 No issues detected! Prometheus appears to be healthy.")
    else:
        print(f"⚠️  Found {total_issues} configuration issues")
        if not container_running:
            print("❌ Prometheus container is not running")
        if not network_ok:
            print("❌ Network connectivity issues detected")
        
        print(f"\n💡 Recommendation: {comprehensive_report['summary']['recommended_action']}")
    
    return comprehensive_report


async def verify_fix(prometheus_url: str, config_path: str):
    """Verify that Prometheus issues have been resolved."""
    print_banner()
    print("🔍 Verifying Prometheus Fix...")
    print()
    
    try:
        report = await generate_prometheus_report(prometheus_url, config_path)
        health = report["health_check"]
        
        print(f"📊 Status: {health['status'].upper()}")
        
        if health['status'] == 'healthy':
            print("🎉 SUCCESS: Prometheus is now healthy!")
            print(f"✅ Service running: {health['service_running']}")
            print(f"✅ Configuration valid: {health['config_valid']}")
            print(f"✅ All endpoints accessible")
            return True
        else:
            print("⚠️  Issues still remain:")
            for error in health['error_messages']:
                print(f"  • {error}")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Prometheus Diagnostic System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/prometheus_diagnostics.py
  python scripts/prometheus_diagnostics.py --url http://localhost:9091
  python scripts/prometheus_diagnostics.py --config monitoring/prometheus/prometheus.yml
  python scripts/prometheus_diagnostics.py --output diagnostics_report.json
  python scripts/prometheus_diagnostics.py --verify
        """
    )
    
    parser.add_argument(
        '--url', 
        default='http://localhost:9091',
        help='Prometheus URL (default: http://localhost:9091)'
    )
    
    parser.add_argument(
        '--config',
        default='monitoring/prometheus/prometheus.yml',
        help='Path to Prometheus configuration file'
    )
    
    parser.add_argument(
        '--output',
        help='Output file for comprehensive diagnostic report (JSON format)'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify that Prometheus issues have been resolved'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        if args.verify:
            # Run verification
            success = asyncio.run(verify_fix(args.url, args.config))
            sys.exit(0 if success else 1)
        else:
            # Run comprehensive diagnostics
            report = asyncio.run(run_comprehensive_diagnostics(args.url, args.config, args.output))
            
            # Exit with appropriate code
            if report["summary"]["total_issues"] == 0 and not report["summary"]["critical_issues"]:
                sys.exit(0)  # Success
            else:
                sys.exit(1)  # Issues found
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnostic interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Diagnostic failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
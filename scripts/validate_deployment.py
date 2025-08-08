#!/usr/bin/env python3
"""
Comprehensive deployment validation script for Voice AI Agent.

This script validates the complete production deployment including:
- Configuration validation
- Service health checks
- API connectivity tests
- Performance benchmarks
- Security checks
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import subprocess
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings, validate_settings
from src.health import comprehensive_health_check


class DeploymentValidator:
    """Comprehensive deployment validation."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "validation_results": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": []
        }
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for validation."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def log_info(self, message: str):
        """Log info message."""
        self.logger.info(message)
        print(f"ℹ️  {message}")
    
    def log_success(self, message: str):
        """Log success message."""
        self.logger.info(f"SUCCESS: {message}")
        print(f"✅ {message}")
    
    def log_warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
        self.results["warnings"].append(message)
        print(f"⚠️  {message}")
    
    def log_error(self, message: str):
        """Log error message."""
        self.logger.error(message)
        self.results["errors"].append(message)
        print(f"❌ {message}")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate application configuration."""
        self.log_info("Validating configuration...")
        
        try:
            # Test configuration loading
            settings = get_settings()
            config_validation = validate_settings()
            
            result = {
                "status": "passed" if config_validation["valid"] else "failed",
                "environment": config_validation.get("environment", "unknown"),
                "required_services": config_validation.get("required_services", {}),
                "warnings": config_validation.get("warnings", [])
            }
            
            if result["status"] == "passed":
                self.log_success("Configuration validation passed")
            else:
                self.log_error(f"Configuration validation failed: {config_validation.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Configuration validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_docker_services(self) -> Dict[str, Any]:
        """Validate Docker services are running."""
        self.log_info("Validating Docker services...")
        
        try:
            # Check if docker-compose is running
            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.prod.yml", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if result.returncode != 0:
                self.log_error(f"Failed to get Docker services status: {result.stderr}")
                return {"status": "failed", "error": result.stderr}
            
            # Parse service status
            services = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        service = json.loads(line)
                        services.append(service)
                    except json.JSONDecodeError:
                        continue
            
            service_status = {}
            for service in services:
                name = service.get("Service", "unknown")
                state = service.get("State", "unknown")
                health = service.get("Health", "unknown")
                
                service_status[name] = {
                    "state": state,
                    "health": health,
                    "running": state == "running"
                }
            
            # Check required services
            required_services = ["voice-ai-agent", "redis", "prometheus", "grafana"]
            missing_services = []
            unhealthy_services = []
            
            for service_name in required_services:
                if service_name not in service_status:
                    missing_services.append(service_name)
                elif not service_status[service_name]["running"]:
                    unhealthy_services.append(service_name)
            
            if missing_services:
                self.log_error(f"Missing services: {missing_services}")
            
            if unhealthy_services:
                self.log_error(f"Unhealthy services: {unhealthy_services}")
            
            if not missing_services and not unhealthy_services:
                self.log_success("All Docker services are running")
            
            return {
                "status": "passed" if not missing_services and not unhealthy_services else "failed",
                "services": service_status,
                "missing_services": missing_services,
                "unhealthy_services": unhealthy_services
            }
            
        except Exception as e:
            self.log_error(f"Docker services validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_health_endpoints(self) -> Dict[str, Any]:
        """Validate health endpoints are responding."""
        self.log_info("Validating health endpoints...")
        
        endpoints = {
            "application": "http://localhost:8000/health",
            "prometheus": "http://localhost:9091/-/healthy",
            "grafana": "http://localhost:3000/api/health",
            "loki": "http://localhost:3100/ready"
        }
        
        results = {}
        
        for name, url in endpoints.items():
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    results[name] = {
                        "status": "healthy",
                        "response_time": response.elapsed.total_seconds(),
                        "status_code": response.status_code
                    }
                    self.log_success(f"{name} health check passed")
                else:
                    results[name] = {
                        "status": "unhealthy",
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}"
                    }
                    self.log_error(f"{name} health check failed: HTTP {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                results[name] = {
                    "status": "unreachable",
                    "error": str(e)
                }
                self.log_error(f"{name} health check failed: {e}")
        
        healthy_count = sum(1 for r in results.values() if r["status"] == "healthy")
        total_count = len(results)
        
        return {
            "status": "passed" if healthy_count == total_count else "failed",
            "healthy_services": healthy_count,
            "total_services": total_count,
            "endpoints": results
        }
    
    def validate_application_health(self) -> Dict[str, Any]:
        """Validate comprehensive application health."""
        self.log_info("Validating application health...")
        
        try:
            health_data = comprehensive_health_check()
            
            if health_data["status"] == "healthy":
                self.log_success("Application health check passed")
            elif health_data["status"] == "degraded":
                self.log_warning("Application health check shows warnings")
            else:
                self.log_error("Application health check failed")
            
            return {
                "status": "passed" if health_data["status"] in ["healthy", "degraded"] else "failed",
                "health_data": health_data
            }
            
        except Exception as e:
            self.log_error(f"Application health validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_api_connectivity(self) -> Dict[str, Any]:
        """Validate API connectivity to external services."""
        self.log_info("Validating API connectivity...")
        
        try:
            settings = get_settings()
            
            # Test basic API key presence (not actual connectivity to avoid costs)
            api_tests = {
                "deepgram": bool(settings.deepgram_api_key),
                "openai": bool(settings.openai_api_key),
                "cartesia": bool(settings.cartesia_api_key),
                "livekit": bool(settings.livekit_api_key and settings.livekit_api_secret)
            }
            
            configured_apis = sum(api_tests.values())
            total_apis = len(api_tests)
            
            if configured_apis == total_apis:
                self.log_success("All API keys are configured")
            else:
                missing_apis = [name for name, configured in api_tests.items() if not configured]
                self.log_warning(f"Missing API keys: {missing_apis}")
            
            return {
                "status": "passed" if configured_apis == total_apis else "warning",
                "configured_apis": configured_apis,
                "total_apis": total_apis,
                "api_status": api_tests
            }
            
        except Exception as e:
            self.log_error(f"API connectivity validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_security_configuration(self) -> Dict[str, Any]:
        """Validate security configuration."""
        self.log_info("Validating security configuration...")
        
        try:
            settings = get_settings()
            
            security_checks = {
                "secret_key_changed": settings.secret_key != "your-secret-key-here-change-this-in-production",
                "secret_key_length": len(settings.secret_key) >= 32,
                "production_environment": settings.environment.value == "production",
                "cors_configured": bool(settings.cors_origins),
                "rate_limiting_enabled": settings.enable_rate_limiting
            }
            
            passed_checks = sum(security_checks.values())
            total_checks = len(security_checks)
            
            if passed_checks == total_checks:
                self.log_success("Security configuration validation passed")
            else:
                failed_checks = [name for name, passed in security_checks.items() if not passed]
                self.log_warning(f"Security configuration issues: {failed_checks}")
            
            return {
                "status": "passed" if passed_checks == total_checks else "warning",
                "passed_checks": passed_checks,
                "total_checks": total_checks,
                "security_checks": security_checks
            }
            
        except Exception as e:
            self.log_error(f"Security validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_monitoring_stack(self) -> Dict[str, Any]:
        """Validate monitoring stack configuration."""
        self.log_info("Validating monitoring stack...")
        
        try:
            # Check Prometheus metrics endpoint
            prometheus_metrics = None
            try:
                response = requests.get("http://localhost:9090/metrics", timeout=10)
                if response.status_code == 200:
                    prometheus_metrics = "available"
                else:
                    prometheus_metrics = f"error: HTTP {response.status_code}"
            except Exception as e:
                prometheus_metrics = f"error: {e}"
            
            # Check Grafana API
            grafana_api = None
            try:
                response = requests.get("http://localhost:3000/api/health", timeout=10)
                if response.status_code == 200:
                    grafana_api = "available"
                else:
                    grafana_api = f"error: HTTP {response.status_code}"
            except Exception as e:
                grafana_api = f"error: {e}"
            
            # Check application metrics endpoint
            app_metrics = None
            try:
                response = requests.get("http://localhost:8000/metrics", timeout=10)
                if response.status_code == 200:
                    app_metrics = "available"
                else:
                    app_metrics = f"error: HTTP {response.status_code}"
            except Exception as e:
                app_metrics = f"error: {e}"
            
            monitoring_status = {
                "prometheus_metrics": prometheus_metrics,
                "grafana_api": grafana_api,
                "application_metrics": app_metrics
            }
            
            available_services = sum(1 for status in monitoring_status.values() if status == "available")
            total_services = len(monitoring_status)
            
            if available_services == total_services:
                self.log_success("Monitoring stack validation passed")
            else:
                self.log_warning(f"Monitoring stack issues detected: {monitoring_status}")
            
            return {
                "status": "passed" if available_services == total_services else "warning",
                "available_services": available_services,
                "total_services": total_services,
                "monitoring_status": monitoring_status
            }
            
        except Exception as e:
            self.log_error(f"Monitoring stack validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    def validate_file_permissions(self) -> Dict[str, Any]:
        """Validate file permissions and directory structure."""
        self.log_info("Validating file permissions...")
        
        try:
            required_dirs = ["logs", "data", "backups", "metrics"]
            permission_issues = []
            
            for dir_name in required_dirs:
                dir_path = project_root / dir_name
                
                if not dir_path.exists():
                    permission_issues.append(f"Missing directory: {dir_name}")
                    continue
                
                if not os.access(dir_path, os.R_OK | os.W_OK):
                    permission_issues.append(f"Insufficient permissions: {dir_name}")
            
            if not permission_issues:
                self.log_success("File permissions validation passed")
            else:
                self.log_warning(f"Permission issues: {permission_issues}")
            
            return {
                "status": "passed" if not permission_issues else "warning",
                "permission_issues": permission_issues
            }
            
        except Exception as e:
            self.log_error(f"File permissions validation error: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def run_validation(self) -> Dict[str, Any]:
        """Run complete deployment validation."""
        print("🔍 Starting comprehensive deployment validation...")
        print("=" * 80)
        
        # Run all validation checks
        validations = {
            "configuration": self.validate_configuration(),
            "docker_services": self.validate_docker_services(),
            "health_endpoints": self.validate_health_endpoints(),
            "application_health": self.validate_application_health(),
            "api_connectivity": self.validate_api_connectivity(),
            "security_configuration": self.validate_security_configuration(),
            "monitoring_stack": self.validate_monitoring_stack(),
            "file_permissions": self.validate_file_permissions()
        }
        
        self.results["validation_results"] = validations
        
        # Determine overall status
        failed_validations = [name for name, result in validations.items() if result["status"] == "failed"]
        warning_validations = [name for name, result in validations.items() if result["status"] == "warning"]
        
        if failed_validations:
            self.results["overall_status"] = "failed"
            self.log_error(f"Validation failed. Failed checks: {failed_validations}")
        elif warning_validations:
            self.results["overall_status"] = "warning"
            self.log_warning(f"Validation passed with warnings: {warning_validations}")
        else:
            self.results["overall_status"] = "passed"
            self.log_success("All validation checks passed!")
        
        return self.results
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate validation report."""
        report = f"""
# Deployment Validation Report

**Timestamp:** {self.results['timestamp']}
**Overall Status:** {self.results['overall_status'].upper()}

## Summary

"""
        
        # Add summary statistics
        validations = self.results["validation_results"]
        passed_count = sum(1 for v in validations.values() if v["status"] == "passed")
        warning_count = sum(1 for v in validations.values() if v["status"] == "warning")
        failed_count = sum(1 for v in validations.values() if v["status"] == "failed")
        total_count = len(validations)
        
        report += f"- **Total Checks:** {total_count}\n"
        report += f"- **Passed:** {passed_count}\n"
        report += f"- **Warnings:** {warning_count}\n"
        report += f"- **Failed:** {failed_count}\n\n"
        
        # Add detailed results
        report += "## Detailed Results\n\n"
        
        for name, result in validations.items():
            status_emoji = "✅" if result["status"] == "passed" else "⚠️" if result["status"] == "warning" else "❌"
            report += f"### {status_emoji} {name.replace('_', ' ').title()}\n\n"
            report += f"**Status:** {result['status'].upper()}\n\n"
            
            if "error" in result:
                report += f"**Error:** {result['error']}\n\n"
            
            # Add specific details based on validation type
            if name == "docker_services" and "services" in result:
                report += "**Services:**\n"
                for service, status in result["services"].items():
                    report += f"- {service}: {status['state']} ({status['health']})\n"
                report += "\n"
            
            elif name == "health_endpoints" and "endpoints" in result:
                report += "**Endpoints:**\n"
                for endpoint, status in result["endpoints"].items():
                    report += f"- {endpoint}: {status['status']}\n"
                report += "\n"
        
        # Add errors and warnings
        if self.results["errors"]:
            report += "## Errors\n\n"
            for error in self.results["errors"]:
                report += f"- {error}\n"
            report += "\n"
        
        if self.results["warnings"]:
            report += "## Warnings\n\n"
            for warning in self.results["warnings"]:
                report += f"- {warning}\n"
            report += "\n"
        
        # Add recommendations
        report += "## Recommendations\n\n"
        
        if failed_count > 0:
            report += "### Critical Issues\n"
            report += "- Fix all failed validation checks before proceeding to production\n"
            report += "- Review error messages and take corrective action\n"
            report += "- Re-run validation after fixes\n\n"
        
        if warning_count > 0:
            report += "### Improvements\n"
            report += "- Address warning issues for optimal performance\n"
            report += "- Review security configuration\n"
            report += "- Ensure all monitoring services are properly configured\n\n"
        
        if failed_count == 0 and warning_count == 0:
            report += "- System is ready for production deployment! 🚀\n"
            report += "- Continue with regular monitoring and maintenance\n"
            report += "- Set up alerting for critical metrics\n\n"
        
        # Save report if output file specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"📄 Validation report saved to: {output_file}")
        
        return report


async def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Voice AI Agent deployment")
    parser.add_argument("--output", "-o", help="Output file for validation report")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    validator = DeploymentValidator()
    results = await validator.run_validation()
    
    print("\n" + "=" * 80)
    print("🏁 Validation Complete!")
    print("=" * 80)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        report = validator.generate_report(args.output)
        if not args.output:
            print(report)
    
    # Exit with appropriate code
    if results["overall_status"] == "failed":
        sys.exit(1)
    elif results["overall_status"] == "warning":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
"""
Prometheus Health Check and Diagnostic System

This module provides comprehensive health checking and diagnostic capabilities
for Prometheus monitoring service, including service status validation,
configuration validation, and connectivity testing.
"""

import asyncio
import json
import logging
import time
import yaml
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PrometheusHealthResult:
    """Data class for Prometheus health check results."""
    status: str  # "healthy", "degraded", "failed"
    timestamp: datetime
    service_running: bool
    config_valid: bool
    endpoints_accessible: Dict[str, bool]
    error_messages: List[str]
    recovery_actions: List[str]
    response_time_ms: float
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class PrometheusConfigStatus:
    """Data class for Prometheus configuration status."""
    yaml_valid: bool
    scrape_configs: List[Dict]
    target_accessibility: Dict[str, bool]
    validation_errors: List[str]
    recommendations: List[str]
    config_file_path: Optional[str] = None
    last_modified: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        if self.last_modified:
            result['last_modified'] = self.last_modified.isoformat()
        return result


class PrometheusHealthChecker:
    """Comprehensive Prometheus health checker and diagnostic system."""
    
    def __init__(self, 
                 prometheus_url: str = "http://localhost:9091",
                 config_path: str = "monitoring/prometheus/prometheus.yml",
                 timeout: int = 10):
        """
        Initialize Prometheus health checker.
        
        Args:
            prometheus_url: URL of Prometheus service
            config_path: Path to Prometheus configuration file
            timeout: Request timeout in seconds
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.config_path = Path(config_path)
        self.timeout = timeout
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"Initialized Prometheus health checker for {prometheus_url}")
    
    async def comprehensive_health_check(self) -> PrometheusHealthResult:
        """
        Perform comprehensive health check of Prometheus service.
        
        Returns:
            PrometheusHealthResult with detailed health information
        """
        start_time = time.time()
        logger.info("Starting comprehensive Prometheus health check")
        
        error_messages = []
        recovery_actions = []
        endpoints_accessible = {}
        
        # Check if service is running
        service_running = await self._check_service_running()
        if not service_running:
            error_messages.append("Prometheus service is not running or not accessible")
            recovery_actions.append("Start Prometheus service using Docker Compose")
            recovery_actions.append("Check Docker container logs for startup errors")
        
        # Check configuration validity
        config_status = await self._validate_configuration()
        config_valid = config_status.yaml_valid and len(config_status.validation_errors) == 0
        
        if not config_valid:
            error_messages.extend(config_status.validation_errors)
            recovery_actions.extend(config_status.recommendations)
        
        # Check endpoint accessibility
        if service_running:
            endpoints_accessible = await self._check_endpoints_accessibility()
            failed_endpoints = [ep for ep, accessible in endpoints_accessible.items() if not accessible]
            
            if failed_endpoints:
                error_messages.append(f"Failed to access endpoints: {failed_endpoints}")
                recovery_actions.append("Check network connectivity to failed endpoints")
                recovery_actions.append("Verify target services are running and healthy")
        
        # Get Prometheus version and uptime if service is running
        version = None
        uptime_seconds = None
        if service_running:
            try:
                version = await self._get_prometheus_version()
                uptime_seconds = await self._get_prometheus_uptime()
            except Exception as e:
                logger.warning(f"Could not get Prometheus version/uptime: {e}")
        
        # Determine overall status
        if not service_running:
            status = "failed"
        elif not config_valid or len([ep for ep in endpoints_accessible.values() if not ep]) > 0:
            status = "degraded"
        else:
            status = "healthy"
        
        response_time = (time.time() - start_time) * 1000
        
        result = PrometheusHealthResult(
            status=status,
            timestamp=datetime.now(),
            service_running=service_running,
            config_valid=config_valid,
            endpoints_accessible=endpoints_accessible,
            error_messages=error_messages,
            recovery_actions=recovery_actions,
            response_time_ms=round(response_time, 2),
            version=version,
            uptime_seconds=uptime_seconds
        )
        
        logger.info(f"Prometheus health check completed: {status} (took {response_time:.2f}ms)")
        return result
    
    async def _check_service_running(self) -> bool:
        """Check if Prometheus service is running and accessible."""
        try:
            # Check health endpoint
            health_url = f"{self.prometheus_url}/-/healthy"
            response = self.session.get(health_url, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.debug("Prometheus health endpoint accessible")
                return True
            else:
                logger.warning(f"Prometheus health endpoint returned {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Prometheus service")
            return False
        except requests.exceptions.Timeout:
            logger.error("Timeout connecting to Prometheus service")
            return False
        except Exception as e:
            logger.error(f"Error checking Prometheus service: {e}")
            return False
    
    async def _validate_configuration(self) -> PrometheusConfigStatus:
        """Validate Prometheus configuration file."""
        validation_errors = []
        recommendations = []
        scrape_configs = []
        target_accessibility = {}
        yaml_valid = False
        last_modified = None
        
        try:
            # Check if config file exists
            if not self.config_path.exists():
                validation_errors.append(f"Configuration file not found: {self.config_path}")
                recommendations.append("Create Prometheus configuration file")
                return PrometheusConfigStatus(
                    yaml_valid=False,
                    scrape_configs=[],
                    target_accessibility={},
                    validation_errors=validation_errors,
                    recommendations=recommendations,
                    config_file_path=str(self.config_path)
                )
            
            last_modified = datetime.fromtimestamp(self.config_path.stat().st_mtime)
            
            # Parse YAML configuration
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            yaml_valid = True
            logger.debug("Prometheus configuration YAML is valid")
            
            # Validate configuration structure
            if 'scrape_configs' not in config:
                validation_errors.append("Missing 'scrape_configs' section in configuration")
                recommendations.append("Add scrape_configs section to Prometheus configuration")
            else:
                scrape_configs = config['scrape_configs']
                
                # Validate each scrape config
                for i, scrape_config in enumerate(scrape_configs):
                    job_name = scrape_config.get('job_name', f'job_{i}')
                    
                    if 'static_configs' not in scrape_config:
                        validation_errors.append(f"Job '{job_name}' missing static_configs")
                        continue
                    
                    # Check target accessibility
                    for static_config in scrape_config['static_configs']:
                        targets = static_config.get('targets', [])
                        for target in targets:
                            target_accessibility[target] = await self._check_target_accessibility(target)
            
            # Check global configuration
            if 'global' not in config:
                recommendations.append("Consider adding global configuration section")
            
            # Check rule files
            if 'rule_files' in config:
                for rule_file in config['rule_files']:
                    rule_path = self.config_path.parent / rule_file
                    if not rule_path.exists():
                        validation_errors.append(f"Rule file not found: {rule_file}")
                        recommendations.append(f"Create rule file: {rule_file}")
            
        except yaml.YAMLError as e:
            validation_errors.append(f"Invalid YAML syntax: {e}")
            recommendations.append("Fix YAML syntax errors in configuration file")
            yaml_valid = False
        except Exception as e:
            validation_errors.append(f"Error validating configuration: {e}")
            recommendations.append("Check configuration file permissions and format")
            yaml_valid = False
        
        return PrometheusConfigStatus(
            yaml_valid=yaml_valid,
            scrape_configs=scrape_configs,
            target_accessibility=target_accessibility,
            validation_errors=validation_errors,
            recommendations=recommendations,
            config_file_path=str(self.config_path),
            last_modified=last_modified
        )
    
    async def _check_target_accessibility(self, target: str) -> bool:
        """Check if a scrape target is accessible."""
        try:
            # Parse target (format: host:port)
            if ':' not in target:
                logger.warning(f"Invalid target format: {target}")
                return False
            
            host, port = target.split(':', 1)
            
            # For Docker services, we need to check from within the network
            # For now, we'll do a basic HTTP check
            url = f"http://{target}"
            
            response = self.session.get(url, timeout=5)
            return response.status_code < 500
            
        except Exception as e:
            logger.debug(f"Target {target} not accessible: {e}")
            return False
    
    async def _check_endpoints_accessibility(self) -> Dict[str, bool]:
        """Check accessibility of key Prometheus endpoints."""
        endpoints = {
            'health': '/-/healthy',
            'ready': '/-/ready',
            'config': '/api/v1/status/config',
            'targets': '/api/v1/targets',
            'metrics': '/metrics'
        }
        
        accessibility = {}
        
        for name, endpoint in endpoints.items():
            try:
                url = f"{self.prometheus_url}{endpoint}"
                response = self.session.get(url, timeout=self.timeout)
                accessibility[name] = response.status_code == 200
                
                if response.status_code == 200:
                    logger.debug(f"Prometheus {name} endpoint accessible")
                else:
                    logger.warning(f"Prometheus {name} endpoint returned {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error checking {name} endpoint: {e}")
                accessibility[name] = False
        
        return accessibility
    
    async def _get_prometheus_version(self) -> Optional[str]:
        """Get Prometheus version information."""
        try:
            url = f"{self.prometheus_url}/api/v1/status/buildinfo"
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('version')
        except Exception as e:
            logger.debug(f"Could not get Prometheus version: {e}")
        
        return None
    
    async def _get_prometheus_uptime(self) -> Optional[float]:
        """Get Prometheus uptime in seconds."""
        try:
            url = f"{self.prometheus_url}/api/v1/query"
            params = {'query': 'prometheus_build_info'}
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                # This is a simplified uptime calculation
                # In reality, we'd need to query process_start_time_seconds
                return time.time() - 3600  # Placeholder
        except Exception as e:
            logger.debug(f"Could not get Prometheus uptime: {e}")
        
        return None
    
    def diagnose_failures(self, health_result: PrometheusHealthResult) -> Dict[str, Any]:
        """
        Diagnose Prometheus failures and provide detailed troubleshooting information.
        
        Args:
            health_result: Result from comprehensive health check
            
        Returns:
            Dict with diagnostic information and troubleshooting steps
        """
        logger.info("Starting Prometheus failure diagnosis")
        
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": health_result.status,
            "issues_found": [],
            "root_causes": [],
            "troubleshooting_steps": [],
            "recovery_actions": health_result.recovery_actions.copy(),
            "system_info": self._get_system_info()
        }
        
        # Diagnose service issues
        if not health_result.service_running:
            diagnosis["issues_found"].append("Prometheus service not running")
            diagnosis["root_causes"].extend([
                "Docker container failed to start",
                "Port conflict (9091 already in use)",
                "Configuration file errors preventing startup",
                "Insufficient system resources",
                "Network connectivity issues"
            ])
            diagnosis["troubleshooting_steps"].extend([
                "Check Docker container status: docker ps -a",
                "Check container logs: docker logs voice-ai-prometheus",
                "Verify port availability: netstat -tulpn | grep 9091",
                "Check system resources: docker stats",
                "Restart Docker Compose stack: docker-compose restart prometheus"
            ])
        
        # Diagnose configuration issues
        if not health_result.config_valid:
            diagnosis["issues_found"].append("Invalid Prometheus configuration")
            diagnosis["root_causes"].extend([
                "YAML syntax errors in prometheus.yml",
                "Invalid scrape target configurations",
                "Missing required configuration sections",
                "File permission issues"
            ])
            diagnosis["troubleshooting_steps"].extend([
                "Validate YAML syntax: yamllint monitoring/prometheus/prometheus.yml",
                "Check file permissions: ls -la monitoring/prometheus/prometheus.yml",
                "Test configuration: docker exec voice-ai-prometheus promtool check config /etc/prometheus/prometheus.yml",
                "Review configuration against Prometheus documentation"
            ])
        
        # Diagnose endpoint accessibility issues
        failed_endpoints = [ep for ep, accessible in health_result.endpoints_accessible.items() if not accessible]
        if failed_endpoints:
            diagnosis["issues_found"].append(f"Inaccessible endpoints: {failed_endpoints}")
            diagnosis["root_causes"].extend([
                "Network connectivity issues between containers",
                "Target services not running or unhealthy",
                "Firewall or security group restrictions",
                "DNS resolution problems"
            ])
            diagnosis["troubleshooting_steps"].extend([
                "Test network connectivity: docker exec voice-ai-prometheus wget -O- http://voice-ai-agent:8000/health",
                "Check target service health: docker exec voice-ai-agent python -c 'from src.health import check_health; print(check_health())'",
                "Verify Docker network: docker network ls && docker network inspect voice-ai-network",
                "Check service discovery: docker exec voice-ai-prometheus nslookup voice-ai-agent"
            ])
        
        # Add general troubleshooting steps
        diagnosis["troubleshooting_steps"].extend([
            "Check overall system health: docker-compose ps",
            "Review all container logs: docker-compose logs",
            "Verify environment variables: docker exec voice-ai-prometheus env | grep PROMETHEUS",
            "Check disk space: df -h",
            "Monitor resource usage: top or htop"
        ])
        
        logger.info(f"Diagnosis completed. Found {len(diagnosis['issues_found'])} issues")
        return diagnosis
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for diagnostics."""
        import platform
        import psutil
        
        try:
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            logger.warning(f"Could not get system info: {e}")
            return {"error": str(e)}
    
    async def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        logger.info("Generating comprehensive Prometheus health report")
        
        # Perform health check
        health_result = await self.comprehensive_health_check()
        
        # Perform diagnosis if there are issues
        diagnosis = None
        if health_result.status != "healthy":
            diagnosis = self.diagnose_failures(health_result)
        
        # Validate configuration
        config_status = await self._validate_configuration()
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "prometheus_url": self.prometheus_url,
            "config_path": str(self.config_path),
            "health_check": health_result.to_dict(),
            "configuration_status": config_status.to_dict(),
            "diagnosis": diagnosis,
            "recommendations": self._generate_recommendations(health_result, config_status)
        }
        
        logger.info(f"Health report generated. Status: {health_result.status}")
        return report
    
    def _generate_recommendations(self, 
                                health_result: PrometheusHealthResult, 
                                config_status: PrometheusConfigStatus) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []
        
        if health_result.status == "healthy":
            recommendations.append("✅ Prometheus is healthy and functioning correctly")
            recommendations.append("Consider setting up alerting rules for proactive monitoring")
            recommendations.append("Review and optimize scrape intervals for better performance")
        else:
            recommendations.extend(health_result.recovery_actions)
            recommendations.extend(config_status.recommendations)
        
        # Add general recommendations
        recommendations.extend([
            "Regularly backup Prometheus configuration and data",
            "Monitor Prometheus resource usage and scale as needed",
            "Keep Prometheus updated to the latest stable version",
            "Implement proper security measures for Prometheus access"
        ])
        
        return list(set(recommendations))  # Remove duplicates
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("Prometheus health checker closed")


# Convenience functions for easy usage
async def check_prometheus_health(prometheus_url: str = "http://localhost:9091",
                                config_path: str = "monitoring/prometheus/prometheus.yml") -> PrometheusHealthResult:
    """
    Convenience function to perform Prometheus health check.
    
    Args:
        prometheus_url: URL of Prometheus service
        config_path: Path to Prometheus configuration file
        
    Returns:
        PrometheusHealthResult with health information
    """
    checker = PrometheusHealthChecker(prometheus_url, config_path)
    try:
        return await checker.comprehensive_health_check()
    finally:
        checker.close()


async def diagnose_prometheus_issues(prometheus_url: str = "http://localhost:9091",
                                   config_path: str = "monitoring/prometheus/prometheus.yml") -> Dict[str, Any]:
    """
    Convenience function to diagnose Prometheus issues.
    
    Args:
        prometheus_url: URL of Prometheus service
        config_path: Path to Prometheus configuration file
        
    Returns:
        Dict with diagnostic information
    """
    checker = PrometheusHealthChecker(prometheus_url, config_path)
    try:
        health_result = await checker.comprehensive_health_check()
        return checker.diagnose_failures(health_result)
    finally:
        checker.close()


async def generate_prometheus_report(prometheus_url: str = "http://localhost:9091",
                                   config_path: str = "monitoring/prometheus/prometheus.yml") -> Dict[str, Any]:
    """
    Convenience function to generate comprehensive Prometheus health report.
    
    Args:
        prometheus_url: URL of Prometheus service
        config_path: Path to Prometheus configuration file
        
    Returns:
        Dict with comprehensive health report
    """
    checker = PrometheusHealthChecker(prometheus_url, config_path)
    try:
        return await checker.generate_health_report()
    finally:
        checker.close()


if __name__ == "__main__":
    import sys
    
    async def main():
        """Main function for command-line usage."""
        # Parse command line arguments
        prometheus_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9091"
        config_path = sys.argv[2] if len(sys.argv) > 2 else "monitoring/prometheus/prometheus.yml"
        
        print("🔍 Prometheus Health Check and Diagnostic System")
        print(f"Checking Prometheus at: {prometheus_url}")
        print(f"Configuration file: {config_path}")
        print("-" * 60)
        
        # Generate comprehensive report
        report = await generate_prometheus_report(prometheus_url, config_path)
        
        # Display results
        health = report['health_check']
        print(f"📊 Overall Status: {health['status'].upper()}")
        print(f"⏱️  Response Time: {health['response_time_ms']}ms")
        print(f"🔧 Service Running: {'✅' if health['service_running'] else '❌'}")
        print(f"📝 Config Valid: {'✅' if health['config_valid'] else '❌'}")
        
        if health['version']:
            print(f"📦 Version: {health['version']}")
        
        # Show endpoint accessibility
        print("\n🌐 Endpoint Accessibility:")
        for endpoint, accessible in health['endpoints_accessible'].items():
            status = "✅" if accessible else "❌"
            print(f"  {status} {endpoint}")
        
        # Show errors and recovery actions
        if health['error_messages']:
            print("\n❌ Issues Found:")
            for error in health['error_messages']:
                print(f"  • {error}")
        
        if health['recovery_actions']:
            print("\n🔧 Recovery Actions:")
            for action in health['recovery_actions']:
                print(f"  • {action}")
        
        # Show diagnosis if available
        if report['diagnosis']:
            diagnosis = report['diagnosis']
            print(f"\n🔍 Root Cause Analysis:")
            for cause in diagnosis['root_causes'][:3]:  # Show top 3
                print(f"  • {cause}")
        
        # Show recommendations
        print(f"\n💡 Recommendations:")
        for rec in report['recommendations'][:5]:  # Show top 5
            print(f"  • {rec}")
        
        # Exit with appropriate code
        if health['status'] == 'healthy':
            print("\n🎉 Prometheus is healthy!")
            sys.exit(0)
        elif health['status'] == 'degraded':
            print("\n⚠️  Prometheus has issues but is partially functional")
            sys.exit(1)
        else:
            print("\n💥 Prometheus is not functioning correctly")
            sys.exit(2)
    
    # Run the main function
    asyncio.run(main())
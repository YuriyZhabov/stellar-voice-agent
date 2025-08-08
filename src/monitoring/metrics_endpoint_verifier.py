"""
Metrics Endpoint Verification System

This module provides comprehensive verification capabilities for Prometheus
scrape targets, including endpoint accessibility testing, metrics format
validation, and health endpoint response verification.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from urllib.parse import urlparse, urljoin
import yaml

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EndpointVerificationResult:
    """Data class for endpoint verification results."""
    endpoint: str
    accessible: bool
    response_time_ms: float
    status_code: Optional[int]
    content_type: Optional[str]
    content_length: Optional[int]
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class MetricsFormatValidationResult:
    """Data class for metrics format validation results."""
    endpoint: str
    valid_format: bool
    metrics_count: int
    valid_metrics: List[str]
    invalid_metrics: List[str]
    format_errors: List[str]
    prometheus_compliant: bool
    sample_metrics: List[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class HealthEndpointResult:
    """Data class for health endpoint verification results."""
    endpoint: str
    healthy: bool
    response_data: Optional[Dict[str, Any]]
    response_time_ms: float
    status_code: Optional[int]
    health_checks: Dict[str, str]
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class ScrapeTargetVerificationResult:
    """Data class for complete scrape target verification results."""
    job_name: str
    target: str
    metrics_path: str
    endpoint_result: EndpointVerificationResult
    metrics_validation: Optional[MetricsFormatValidationResult]
    health_result: Optional[HealthEndpointResult]
    overall_status: str  # "healthy", "degraded", "failed"
    recommendations: List[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        if result['endpoint_result']:
            result['endpoint_result'] = self.endpoint_result.to_dict()
        if result['metrics_validation']:
            result['metrics_validation'] = self.metrics_validation.to_dict()
        if result['health_result']:
            result['health_result'] = self.health_result.to_dict()
        return result


class MetricsEndpointVerifier:
    """Comprehensive metrics endpoint verification system."""
    
    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        Initialize metrics endpoint verifier.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Prometheus metrics format patterns
        self.prometheus_metric_pattern = re.compile(
            r'^([a-zA-Z_:][a-zA-Z0-9_:]*)'  # Metric name
            r'(\{[^}]*\})?'                  # Optional labels
            r'\s+'                           # Whitespace
            r'([+-]?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?)'  # Value
            r'(\s+[0-9]+)?$'                 # Optional timestamp
        )
        
        # Common Prometheus metric types
        self.prometheus_types = {
            'counter', 'gauge', 'histogram', 'summary', 'untyped'
        }
        
        logger.info("Initialized metrics endpoint verifier")
    
    async def verify_endpoint_accessibility(self, endpoint: str) -> EndpointVerificationResult:
        """
        Verify if an endpoint is accessible.
        
        Args:
            endpoint: URL of the endpoint to verify
            
        Returns:
            EndpointVerificationResult with accessibility information
        """
        start_time = time.time()
        logger.debug(f"Verifying endpoint accessibility: {endpoint}")
        
        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000
            
            result = EndpointVerificationResult(
                endpoint=endpoint,
                accessible=response.status_code < 500,
                response_time_ms=round(response_time, 2),
                status_code=response.status_code,
                content_type=response.headers.get('content-type'),
                content_length=len(response.content) if response.content else 0
            )
            
            if response.status_code >= 400:
                result.error_message = f"HTTP {response.status_code}: {response.reason}"
            
            logger.debug(f"Endpoint {endpoint} accessibility check completed: {result.accessible}")
            return result
            
        except requests.exceptions.ConnectionError as e:
            response_time = (time.time() - start_time) * 1000
            logger.warning(f"Connection error for endpoint {endpoint}: {e}")
            return EndpointVerificationResult(
                endpoint=endpoint,
                accessible=False,
                response_time_ms=round(response_time, 2),
                status_code=None,
                content_type=None,
                content_length=None,
                error_message=f"Connection error: {str(e)}"
            )
        except requests.exceptions.Timeout as e:
            response_time = (time.time() - start_time) * 1000
            logger.warning(f"Timeout for endpoint {endpoint}: {e}")
            return EndpointVerificationResult(
                endpoint=endpoint,
                accessible=False,
                response_time_ms=round(response_time, 2),
                status_code=None,
                content_type=None,
                content_length=None,
                error_message=f"Timeout: {str(e)}"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error for endpoint {endpoint}: {e}")
            return EndpointVerificationResult(
                endpoint=endpoint,
                accessible=False,
                response_time_ms=round(response_time, 2),
                status_code=None,
                content_type=None,
                content_length=None,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    async def validate_metrics_format(self, endpoint: str) -> MetricsFormatValidationResult:
        """
        Validate that an endpoint returns properly formatted Prometheus metrics.
        
        Args:
            endpoint: URL of the metrics endpoint
            
        Returns:
            MetricsFormatValidationResult with validation information
        """
        logger.debug(f"Validating metrics format for endpoint: {endpoint}")
        
        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            
            if response.status_code != 200:
                return MetricsFormatValidationResult(
                    endpoint=endpoint,
                    valid_format=False,
                    metrics_count=0,
                    valid_metrics=[],
                    invalid_metrics=[],
                    format_errors=[f"HTTP {response.status_code}: {response.reason}"],
                    prometheus_compliant=False,
                    sample_metrics=[]
                )
            
            content = response.text
            lines = content.strip().split('\n')
            
            valid_metrics = []
            invalid_metrics = []
            format_errors = []
            metric_names = set()
            help_lines = []
            type_lines = []
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Handle HELP lines
                if line.startswith('# HELP '):
                    help_lines.append(line)
                    continue
                
                # Handle TYPE lines
                if line.startswith('# TYPE '):
                    type_lines.append(line)
                    # Validate TYPE line format
                    parts = line.split()
                    if len(parts) >= 4:
                        metric_name = parts[2]
                        metric_type = parts[3]
                        if metric_type not in self.prometheus_types:
                            format_errors.append(f"Line {line_num}: Invalid metric type '{metric_type}'")
                    else:
                        format_errors.append(f"Line {line_num}: Invalid TYPE line format")
                    continue
                
                # Skip other comment lines
                if line.startswith('#'):
                    continue
                
                # Validate metric line
                if self.prometheus_metric_pattern.match(line):
                    valid_metrics.append(line)
                    # Extract metric name
                    metric_name = line.split('{')[0].split()[0]
                    metric_names.add(metric_name)
                else:
                    invalid_metrics.append(line)
                    format_errors.append(f"Line {line_num}: Invalid metric format: {line[:100]}")
            
            # Check for required content type
            content_type = response.headers.get('content-type', '')
            if 'text/plain' not in content_type and 'application/openmetrics-text' not in content_type:
                format_errors.append(f"Invalid content type: {content_type}. Expected text/plain or application/openmetrics-text")
            
            # Determine if format is valid and Prometheus compliant
            valid_format = len(invalid_metrics) == 0 and len(format_errors) == 0
            prometheus_compliant = valid_format and len(valid_metrics) > 0
            
            # Get sample metrics (first 5)
            sample_metrics = valid_metrics[:5]
            
            result = MetricsFormatValidationResult(
                endpoint=endpoint,
                valid_format=valid_format,
                metrics_count=len(valid_metrics),
                valid_metrics=list(metric_names),
                invalid_metrics=invalid_metrics[:10],  # Limit to first 10 invalid metrics
                format_errors=format_errors[:10],  # Limit to first 10 errors
                prometheus_compliant=prometheus_compliant,
                sample_metrics=sample_metrics
            )
            
            logger.debug(f"Metrics format validation completed for {endpoint}: valid={valid_format}, count={len(valid_metrics)}")
            return result
            
        except Exception as e:
            logger.error(f"Error validating metrics format for {endpoint}: {e}")
            return MetricsFormatValidationResult(
                endpoint=endpoint,
                valid_format=False,
                metrics_count=0,
                valid_metrics=[],
                invalid_metrics=[],
                format_errors=[f"Validation error: {str(e)}"],
                prometheus_compliant=False,
                sample_metrics=[]
            )
    
    async def verify_health_endpoint(self, endpoint: str) -> HealthEndpointResult:
        """
        Verify health endpoint response and format.
        
        Args:
            endpoint: URL of the health endpoint
            
        Returns:
            HealthEndpointResult with health verification information
        """
        start_time = time.time()
        logger.debug(f"Verifying health endpoint: {endpoint}")
        
        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                return HealthEndpointResult(
                    endpoint=endpoint,
                    healthy=False,
                    response_data=None,
                    response_time_ms=round(response_time, 2),
                    status_code=response.status_code,
                    health_checks={},
                    error_message=f"HTTP {response.status_code}: {response.reason}"
                )
            
            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                # If not JSON, treat as plain text
                response_data = {"status": response.text.strip()}
            
            # Extract health information
            health_checks = {}
            healthy = False
            
            if isinstance(response_data, dict):
                # Check for common health status fields
                status = response_data.get('status', '').lower()
                healthy = status in ['healthy', 'ok', 'up', 'ready']
                
                # Extract individual health checks
                checks = response_data.get('checks', {})
                if isinstance(checks, dict):
                    health_checks = checks
                else:
                    # Look for other common patterns
                    for key, value in response_data.items():
                        if key != 'status' and key != 'timestamp':
                            health_checks[key] = str(value)
            else:
                # Simple string response
                status = str(response_data).lower()
                healthy = status in ['healthy', 'ok', 'up', 'ready']
                health_checks['status'] = str(response_data)
            
            result = HealthEndpointResult(
                endpoint=endpoint,
                healthy=healthy,
                response_data=response_data,
                response_time_ms=round(response_time, 2),
                status_code=response.status_code,
                health_checks=health_checks
            )
            
            logger.debug(f"Health endpoint verification completed for {endpoint}: healthy={healthy}")
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Error verifying health endpoint {endpoint}: {e}")
            return HealthEndpointResult(
                endpoint=endpoint,
                healthy=False,
                response_data=None,
                response_time_ms=round(response_time, 2),
                status_code=None,
                health_checks={},
                error_message=f"Verification error: {str(e)}"
            )
    
    async def verify_scrape_target(self, job_name: str, target: str, 
                                 metrics_path: str = "/metrics",
                                 health_path: str = "/health") -> ScrapeTargetVerificationResult:
        """
        Perform comprehensive verification of a Prometheus scrape target.
        
        Args:
            job_name: Name of the Prometheus job
            target: Target host:port
            metrics_path: Path to metrics endpoint
            health_path: Path to health endpoint
            
        Returns:
            ScrapeTargetVerificationResult with comprehensive verification results
        """
        logger.info(f"Verifying scrape target: {job_name} -> {target}")
        
        # Construct full URLs
        base_url = f"http://{target}"
        metrics_url = urljoin(base_url, metrics_path)
        health_url = urljoin(base_url, health_path)
        
        recommendations = []
        
        # Verify endpoint accessibility
        endpoint_result = await self.verify_endpoint_accessibility(metrics_url)
        
        # Verify metrics format if endpoint is accessible
        metrics_validation = None
        if endpoint_result.accessible and endpoint_result.status_code == 200:
            metrics_validation = await self.validate_metrics_format(metrics_url)
            
            if not metrics_validation.prometheus_compliant:
                recommendations.append("Fix metrics format to be Prometheus compliant")
            if metrics_validation.metrics_count == 0:
                recommendations.append("Endpoint should expose at least one metric")
        else:
            recommendations.append("Fix endpoint accessibility issues")
            if endpoint_result.status_code and endpoint_result.status_code >= 400:
                recommendations.append(f"Resolve HTTP {endpoint_result.status_code} error")
        
        # Verify health endpoint if it exists
        health_result = None
        try:
            health_result = await self.verify_health_endpoint(health_url)
            if not health_result.healthy:
                recommendations.append("Fix health endpoint to return healthy status")
        except Exception as e:
            logger.debug(f"Health endpoint verification failed for {target}: {e}")
            # Health endpoint is optional, so we don't fail the overall check
        
        # Determine overall status
        if not endpoint_result.accessible:
            overall_status = "failed"
            recommendations.append("Ensure target service is running and accessible")
        elif metrics_validation and not metrics_validation.prometheus_compliant:
            overall_status = "degraded"
            recommendations.append("Improve metrics format compliance")
        elif health_result and not health_result.healthy:
            overall_status = "degraded"
            recommendations.append("Address health check issues")
        else:
            overall_status = "healthy"
        
        # Add general recommendations
        if overall_status == "healthy":
            recommendations.append("Consider adding more detailed metrics")
            recommendations.append("Implement proper metric labeling")
        
        result = ScrapeTargetVerificationResult(
            job_name=job_name,
            target=target,
            metrics_path=metrics_path,
            endpoint_result=endpoint_result,
            metrics_validation=metrics_validation,
            health_result=health_result,
            overall_status=overall_status,
            recommendations=recommendations
        )
        
        logger.info(f"Scrape target verification completed: {job_name} -> {overall_status}")
        return result
    
    async def verify_all_scrape_targets(self, config_path: str = "monitoring/prometheus/prometheus.yml") -> Dict[str, Any]:
        """
        Verify all scrape targets from Prometheus configuration.
        
        Args:
            config_path: Path to Prometheus configuration file
            
        Returns:
            Dict with verification results for all targets
        """
        logger.info(f"Verifying all scrape targets from config: {config_path}")
        
        try:
            # Load Prometheus configuration
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            scrape_configs = config.get('scrape_configs', [])
            verification_results = []
            
            # Verify each scrape target
            for scrape_config in scrape_configs:
                job_name = scrape_config.get('job_name', 'unknown')
                metrics_path = scrape_config.get('metrics_path', '/metrics')
                
                static_configs = scrape_config.get('static_configs', [])
                for static_config in static_configs:
                    targets = static_config.get('targets', [])
                    for target in targets:
                        try:
                            result = await self.verify_scrape_target(
                                job_name=job_name,
                                target=target,
                                metrics_path=metrics_path
                            )
                            verification_results.append(result)
                        except Exception as e:
                            logger.error(f"Error verifying target {target}: {e}")
                            # Create a failed result
                            verification_results.append(ScrapeTargetVerificationResult(
                                job_name=job_name,
                                target=target,
                                metrics_path=metrics_path,
                                endpoint_result=EndpointVerificationResult(
                                    endpoint=f"http://{target}{metrics_path}",
                                    accessible=False,
                                    response_time_ms=0,
                                    status_code=None,
                                    content_type=None,
                                    content_length=None,
                                    error_message=f"Verification error: {str(e)}"
                                ),
                                metrics_validation=None,
                                health_result=None,
                                overall_status="failed",
                                recommendations=[f"Fix verification error: {str(e)}"]
                            ))
            
            # Generate summary
            total_targets = len(verification_results)
            healthy_targets = len([r for r in verification_results if r.overall_status == "healthy"])
            degraded_targets = len([r for r in verification_results if r.overall_status == "degraded"])
            failed_targets = len([r for r in verification_results if r.overall_status == "failed"])
            
            summary = {
                "timestamp": datetime.now().isoformat(),
                "config_path": config_path,
                "total_targets": total_targets,
                "healthy_targets": healthy_targets,
                "degraded_targets": degraded_targets,
                "failed_targets": failed_targets,
                "health_percentage": (healthy_targets / total_targets * 100) if total_targets > 0 else 0,
                "overall_status": "healthy" if failed_targets == 0 and degraded_targets == 0 else 
                                "degraded" if failed_targets == 0 else "failed"
            }
            
            report = {
                "summary": summary,
                "verification_results": [result.to_dict() for result in verification_results],
                "recommendations": self._generate_overall_recommendations(verification_results)
            }
            
            logger.info(f"All scrape targets verified: {healthy_targets}/{total_targets} healthy")
            return report
            
        except Exception as e:
            logger.error(f"Error verifying scrape targets: {e}")
            return {
                "summary": {
                    "timestamp": datetime.now().isoformat(),
                    "config_path": config_path,
                    "error": str(e),
                    "overall_status": "failed"
                },
                "verification_results": [],
                "recommendations": [f"Fix configuration loading error: {str(e)}"]
            }
    
    def _generate_overall_recommendations(self, results: List[ScrapeTargetVerificationResult]) -> List[str]:
        """Generate overall recommendations based on verification results."""
        recommendations = []
        
        failed_count = len([r for r in results if r.overall_status == "failed"])
        degraded_count = len([r for r in results if r.overall_status == "degraded"])
        
        if failed_count > 0:
            recommendations.append(f"Fix {failed_count} failed scrape targets")
            recommendations.append("Check service availability and network connectivity")
        
        if degraded_count > 0:
            recommendations.append(f"Improve {degraded_count} degraded scrape targets")
            recommendations.append("Review metrics format and health endpoint implementations")
        
        if failed_count == 0 and degraded_count == 0:
            recommendations.append("✅ All scrape targets are healthy")
            recommendations.append("Consider adding more comprehensive metrics")
            recommendations.append("Implement metric alerting rules")
        
        # Add specific recommendations based on common issues
        common_issues = {}
        for result in results:
            for rec in result.recommendations:
                common_issues[rec] = common_issues.get(rec, 0) + 1
        
        # Add most common issues as overall recommendations
        for issue, count in sorted(common_issues.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count > 1:
                recommendations.append(f"Common issue ({count} targets): {issue}")
        
        return recommendations
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("Metrics endpoint verifier closed")


# Convenience functions for easy usage
async def verify_endpoint(endpoint: str, timeout: int = 10) -> EndpointVerificationResult:
    """
    Convenience function to verify a single endpoint.
    
    Args:
        endpoint: URL of the endpoint to verify
        timeout: Request timeout in seconds
        
    Returns:
        EndpointVerificationResult with verification information
    """
    verifier = MetricsEndpointVerifier(timeout=timeout)
    try:
        return await verifier.verify_endpoint_accessibility(endpoint)
    finally:
        verifier.close()


async def validate_metrics(endpoint: str, timeout: int = 10) -> MetricsFormatValidationResult:
    """
    Convenience function to validate metrics format.
    
    Args:
        endpoint: URL of the metrics endpoint
        timeout: Request timeout in seconds
        
    Returns:
        MetricsFormatValidationResult with validation information
    """
    verifier = MetricsEndpointVerifier(timeout=timeout)
    try:
        return await verifier.validate_metrics_format(endpoint)
    finally:
        verifier.close()


async def verify_health(endpoint: str, timeout: int = 10) -> HealthEndpointResult:
    """
    Convenience function to verify health endpoint.
    
    Args:
        endpoint: URL of the health endpoint
        timeout: Request timeout in seconds
        
    Returns:
        HealthEndpointResult with health verification information
    """
    verifier = MetricsEndpointVerifier(timeout=timeout)
    try:
        return await verifier.verify_health_endpoint(endpoint)
    finally:
        verifier.close()


async def verify_all_targets(config_path: str = "monitoring/prometheus/prometheus.yml") -> Dict[str, Any]:
    """
    Convenience function to verify all scrape targets.
    
    Args:
        config_path: Path to Prometheus configuration file
        
    Returns:
        Dict with verification results for all targets
    """
    verifier = MetricsEndpointVerifier()
    try:
        return await verifier.verify_all_scrape_targets(config_path)
    finally:
        verifier.close()


if __name__ == "__main__":
    import sys
    
    async def main():
        """Main function for command-line usage."""
        if len(sys.argv) < 2:
            print("Usage: python metrics_endpoint_verifier.py <command> [args...]")
            print("Commands:")
            print("  verify-endpoint <url>")
            print("  validate-metrics <url>")
            print("  verify-health <url>")
            print("  verify-all [config_path]")
            sys.exit(1)
        
        command = sys.argv[1]
        
        if command == "verify-endpoint" and len(sys.argv) >= 3:
            endpoint = sys.argv[2]
            result = await verify_endpoint(endpoint)
            print(json.dumps(result.to_dict(), indent=2))
        
        elif command == "validate-metrics" and len(sys.argv) >= 3:
            endpoint = sys.argv[2]
            result = await validate_metrics(endpoint)
            print(json.dumps(result.to_dict(), indent=2))
        
        elif command == "verify-health" and len(sys.argv) >= 3:
            endpoint = sys.argv[2]
            result = await verify_health(endpoint)
            print(json.dumps(result.to_dict(), indent=2))
        
        elif command == "verify-all":
            config_path = sys.argv[2] if len(sys.argv) >= 3 else "monitoring/prometheus/prometheus.yml"
            result = await verify_all_targets(config_path)
            print(json.dumps(result, indent=2))
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    # Run the main function
    asyncio.run(main())
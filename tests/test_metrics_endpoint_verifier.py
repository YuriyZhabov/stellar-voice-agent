"""
Integration tests for the metrics endpoint verification system.

These tests verify the functionality of the MetricsEndpointVerifier class
and its ability to test endpoint accessibility, validate metrics format,
and verify health endpoints.
"""

import asyncio
import json
import pytest
import tempfile
import yaml
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from src.monitoring.metrics_endpoint_verifier import (
    MetricsEndpointVerifier,
    EndpointVerificationResult,
    MetricsFormatValidationResult,
    HealthEndpointResult,
    ScrapeTargetVerificationResult,
    verify_endpoint,
    validate_metrics,
    verify_health,
    verify_all_targets
)


class TestEndpointVerificationResult:
    """Test EndpointVerificationResult data class."""
    
    def test_endpoint_verification_result_creation(self):
        """Test creating EndpointVerificationResult."""
        result = EndpointVerificationResult(
            endpoint="http://localhost:8000/metrics",
            accessible=True,
            response_time_ms=150.5,
            status_code=200,
            content_type="text/plain",
            content_length=1024
        )
        
        assert result.endpoint == "http://localhost:8000/metrics"
        assert result.accessible is True
        assert result.response_time_ms == 150.5
        assert result.status_code == 200
        assert result.content_type == "text/plain"
        assert result.content_length == 1024
        assert result.error_message is None
        assert isinstance(result.timestamp, datetime)
    
    def test_endpoint_verification_result_to_dict(self):
        """Test converting EndpointVerificationResult to dictionary."""
        result = EndpointVerificationResult(
            endpoint="http://localhost:8000/metrics",
            accessible=True,
            response_time_ms=150.5,
            status_code=200,
            content_type="text/plain",
            content_length=1024
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["endpoint"] == "http://localhost:8000/metrics"
        assert result_dict["accessible"] is True
        assert result_dict["response_time_ms"] == 150.5
        assert result_dict["status_code"] == 200
        assert "timestamp" in result_dict
        assert isinstance(result_dict["timestamp"], str)


class TestMetricsFormatValidationResult:
    """Test MetricsFormatValidationResult data class."""
    
    def test_metrics_format_validation_result_creation(self):
        """Test creating MetricsFormatValidationResult."""
        result = MetricsFormatValidationResult(
            endpoint="http://localhost:8000/metrics",
            valid_format=True,
            metrics_count=5,
            valid_metrics=["http_requests_total", "cpu_usage"],
            invalid_metrics=[],
            format_errors=[],
            prometheus_compliant=True,
            sample_metrics=["http_requests_total 100", "cpu_usage 0.5"]
        )
        
        assert result.endpoint == "http://localhost:8000/metrics"
        assert result.valid_format is True
        assert result.metrics_count == 5
        assert len(result.valid_metrics) == 2
        assert len(result.invalid_metrics) == 0
        assert result.prometheus_compliant is True
        assert len(result.sample_metrics) == 2


class TestHealthEndpointResult:
    """Test HealthEndpointResult data class."""
    
    def test_health_endpoint_result_creation(self):
        """Test creating HealthEndpointResult."""
        response_data = {"status": "healthy", "checks": {"database": "ok"}}
        result = HealthEndpointResult(
            endpoint="http://localhost:8000/health",
            healthy=True,
            response_data=response_data,
            response_time_ms=50.0,
            status_code=200,
            health_checks={"database": "ok"}
        )
        
        assert result.endpoint == "http://localhost:8000/health"
        assert result.healthy is True
        assert result.response_data == response_data
        assert result.response_time_ms == 50.0
        assert result.status_code == 200
        assert result.health_checks == {"database": "ok"}


class TestMetricsEndpointVerifier:
    """Test MetricsEndpointVerifier class."""
    
    @pytest.fixture
    def verifier(self):
        """Create a MetricsEndpointVerifier instance for testing."""
        return MetricsEndpointVerifier(timeout=5, max_retries=1)
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        mock = Mock()
        mock.status_code = 200
        mock.reason = "OK"
        mock.headers = {"content-type": "text/plain"}
        mock.content = b"test content"
        mock.text = "test content"
        return mock
    
    def test_verifier_initialization(self, verifier):
        """Test MetricsEndpointVerifier initialization."""
        assert verifier.timeout == 5
        assert verifier.max_retries == 1
        assert hasattr(verifier, 'session')
        assert hasattr(verifier, 'prometheus_metric_pattern')
        assert hasattr(verifier, 'prometheus_types')
    
    @pytest.mark.asyncio
    async def test_verify_endpoint_accessibility_success(self, verifier, mock_response):
        """Test successful endpoint accessibility verification."""
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.verify_endpoint_accessibility("http://localhost:8000/metrics")
            
            assert isinstance(result, EndpointVerificationResult)
            assert result.endpoint == "http://localhost:8000/metrics"
            assert result.accessible is True
            assert result.status_code == 200
            assert result.content_type == "text/plain"
            assert result.content_length == len(b"test content")
            assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_verify_endpoint_accessibility_failure(self, verifier):
        """Test endpoint accessibility verification with connection error."""
        import requests
        
        with patch.object(verifier.session, 'get', side_effect=requests.exceptions.ConnectionError("Connection refused")):
            result = await verifier.verify_endpoint_accessibility("http://localhost:8000/metrics")
            
            assert isinstance(result, EndpointVerificationResult)
            assert result.endpoint == "http://localhost:8000/metrics"
            assert result.accessible is False
            assert result.status_code is None
            assert "Connection error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_verify_endpoint_accessibility_timeout(self, verifier):
        """Test endpoint accessibility verification with timeout."""
        import requests
        
        with patch.object(verifier.session, 'get', side_effect=requests.exceptions.Timeout("Request timeout")):
            result = await verifier.verify_endpoint_accessibility("http://localhost:8000/metrics")
            
            assert isinstance(result, EndpointVerificationResult)
            assert result.accessible is False
            assert "Timeout" in result.error_message
    
    @pytest.mark.asyncio
    async def test_validate_metrics_format_valid(self, verifier):
        """Test metrics format validation with valid Prometheus metrics."""
        valid_metrics = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 1234
http_requests_total{method="POST",status="200"} 567

# HELP cpu_usage Current CPU usage
# TYPE cpu_usage gauge
cpu_usage 0.75
"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = valid_metrics
        mock_response.headers = {"content-type": "text/plain"}
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.validate_metrics_format("http://localhost:8000/metrics")
            
            assert isinstance(result, MetricsFormatValidationResult)
            assert result.endpoint == "http://localhost:8000/metrics"
            assert result.valid_format is True
            assert result.prometheus_compliant is True
            assert result.metrics_count == 3
            assert "http_requests_total" in result.valid_metrics
            assert "cpu_usage" in result.valid_metrics
            assert len(result.invalid_metrics) == 0
            assert len(result.format_errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_metrics_format_invalid(self, verifier):
        """Test metrics format validation with invalid metrics."""
        invalid_metrics = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} invalid_value
invalid_metric_line
cpu_usage 0.75
"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = invalid_metrics
        mock_response.headers = {"content-type": "text/plain"}
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.validate_metrics_format("http://localhost:8000/metrics")
            
            assert isinstance(result, MetricsFormatValidationResult)
            assert result.valid_format is False
            assert result.prometheus_compliant is False
            assert len(result.invalid_metrics) > 0
            assert len(result.format_errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_metrics_format_http_error(self, verifier):
        """Test metrics format validation with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.validate_metrics_format("http://localhost:8000/metrics")
            
            assert isinstance(result, MetricsFormatValidationResult)
            assert result.valid_format is False
            assert result.prometheus_compliant is False
            assert result.metrics_count == 0
            assert "HTTP 404" in result.format_errors[0]
    
    @pytest.mark.asyncio
    async def test_verify_health_endpoint_healthy(self, verifier):
        """Test health endpoint verification with healthy response."""
        health_response = {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "redis": "ok"
            }
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = health_response
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.verify_health_endpoint("http://localhost:8000/health")
            
            assert isinstance(result, HealthEndpointResult)
            assert result.endpoint == "http://localhost:8000/health"
            assert result.healthy is True
            assert result.status_code == 200
            assert result.response_data == health_response
            assert result.health_checks == {"database": "ok", "redis": "ok"}
            assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_verify_health_endpoint_unhealthy(self, verifier):
        """Test health endpoint verification with unhealthy response."""
        health_response = {
            "status": "unhealthy",
            "checks": {
                "database": "failed",
                "redis": "ok"
            }
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = health_response
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.verify_health_endpoint("http://localhost:8000/health")
            
            assert isinstance(result, HealthEndpointResult)
            assert result.healthy is False
            assert result.health_checks == {"database": "failed", "redis": "ok"}
    
    @pytest.mark.asyncio
    async def test_verify_health_endpoint_plain_text(self, verifier):
        """Test health endpoint verification with plain text response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "OK"
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.verify_health_endpoint("http://localhost:8000/health")
            
            assert isinstance(result, HealthEndpointResult)
            assert result.healthy is True  # "OK" should be considered healthy
            assert result.response_data == {"status": "OK"}
    
    @pytest.mark.asyncio
    async def test_verify_scrape_target_healthy(self, verifier):
        """Test comprehensive scrape target verification with healthy target."""
        # Mock metrics endpoint
        metrics_response = Mock()
        metrics_response.status_code = 200
        metrics_response.headers = {"content-type": "text/plain"}
        metrics_response.content = b"http_requests_total 100"
        metrics_response.text = "http_requests_total 100"
        
        # Mock health endpoint
        health_response = Mock()
        health_response.status_code = 200
        health_response.json.return_value = {"status": "healthy"}
        
        def mock_get(url, **kwargs):
            if "/metrics" in url:
                return metrics_response
            elif "/health" in url:
                return health_response
            else:
                raise ValueError(f"Unexpected URL: {url}")
        
        with patch.object(verifier.session, 'get', side_effect=mock_get):
            result = await verifier.verify_scrape_target(
                job_name="test-job",
                target="localhost:8000",
                metrics_path="/metrics",
                health_path="/health"
            )
            
            assert isinstance(result, ScrapeTargetVerificationResult)
            assert result.job_name == "test-job"
            assert result.target == "localhost:8000"
            assert result.overall_status == "healthy"
            assert result.endpoint_result.accessible is True
            assert result.metrics_validation.prometheus_compliant is True
            assert result.health_result.healthy is True
    
    @pytest.mark.asyncio
    async def test_verify_scrape_target_failed(self, verifier):
        """Test scrape target verification with failed target."""
        import requests
        
        with patch.object(verifier.session, 'get', side_effect=requests.exceptions.ConnectionError("Connection refused")):
            result = await verifier.verify_scrape_target(
                job_name="test-job",
                target="localhost:8000"
            )
            
            assert isinstance(result, ScrapeTargetVerificationResult)
            assert result.overall_status == "failed"
            assert result.endpoint_result.accessible is False
            assert result.metrics_validation is None
            assert "Ensure target service is running and accessible" in result.recommendations
    
    @pytest.mark.asyncio
    async def test_verify_all_scrape_targets(self, verifier):
        """Test verification of all scrape targets from configuration."""
        # Create temporary config file
        config_data = {
            "scrape_configs": [
                {
                    "job_name": "test-app",
                    "static_configs": [
                        {"targets": ["localhost:8000", "localhost:8001"]}
                    ],
                    "metrics_path": "/metrics"
                },
                {
                    "job_name": "test-db",
                    "static_configs": [
                        {"targets": ["localhost:9090"]}
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            # Mock successful responses for all targets
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.content = b"test_metric 1"
            mock_response.text = "test_metric 1"
            mock_response.json.return_value = {"status": "healthy"}
            
            with patch.object(verifier.session, 'get', return_value=mock_response):
                result = await verifier.verify_all_scrape_targets(config_path)
                
                assert "summary" in result
                assert "verification_results" in result
                assert "recommendations" in result
                
                summary = result["summary"]
                assert summary["total_targets"] == 3  # 2 + 1 targets
                assert summary["overall_status"] in ["healthy", "degraded", "failed"]
                
                verification_results = result["verification_results"]
                assert len(verification_results) == 3
                
                # Check that all results have required fields
                for vr in verification_results:
                    assert "job_name" in vr
                    assert "target" in vr
                    assert "overall_status" in vr
                    assert "endpoint_result" in vr
        
        finally:
            # Clean up temporary file
            Path(config_path).unlink()
    
    @pytest.mark.asyncio
    async def test_verify_all_scrape_targets_config_error(self, verifier):
        """Test verification with invalid configuration file."""
        result = await verifier.verify_all_scrape_targets("nonexistent_config.yml")
        
        assert "summary" in result
        assert result["summary"]["overall_status"] == "failed"
        assert "error" in result["summary"]
        assert len(result["verification_results"]) == 0
    
    def test_generate_overall_recommendations(self, verifier):
        """Test generation of overall recommendations."""
        # Create mock results
        healthy_result = Mock()
        healthy_result.overall_status = "healthy"
        healthy_result.recommendations = ["Add more metrics"]
        
        degraded_result = Mock()
        degraded_result.overall_status = "degraded"
        degraded_result.recommendations = ["Fix metrics format"]
        
        failed_result = Mock()
        failed_result.overall_status = "failed"
        failed_result.recommendations = ["Fix connectivity"]
        
        results = [healthy_result, degraded_result, failed_result]
        
        recommendations = verifier._generate_overall_recommendations(results)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("1 failed scrape targets" in rec for rec in recommendations)
        assert any("1 degraded scrape targets" in rec for rec in recommendations)
    
    def test_close(self, verifier):
        """Test closing the verifier."""
        # Should not raise any exceptions
        verifier.close()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_verify_endpoint_function(self):
        """Test verify_endpoint convenience function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.content = b"test"
        
        with patch('src.monitoring.metrics_endpoint_verifier.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            result = await verify_endpoint("http://localhost:8000/metrics")
            
            assert isinstance(result, EndpointVerificationResult)
            assert result.accessible is True
            assert result.status_code == 200
    
    @pytest.mark.asyncio
    async def test_validate_metrics_function(self):
        """Test validate_metrics convenience function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "test_metric 1"
        mock_response.headers = {"content-type": "text/plain"}
        
        with patch('src.monitoring.metrics_endpoint_verifier.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            result = await validate_metrics("http://localhost:8000/metrics")
            
            assert isinstance(result, MetricsFormatValidationResult)
            assert result.endpoint == "http://localhost:8000/metrics"
    
    @pytest.mark.asyncio
    async def test_verify_health_function(self):
        """Test verify_health convenience function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        
        with patch('src.monitoring.metrics_endpoint_verifier.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            result = await verify_health("http://localhost:8000/health")
            
            assert isinstance(result, HealthEndpointResult)
            assert result.healthy is True
    
    @pytest.mark.asyncio
    async def test_verify_all_targets_function(self):
        """Test verify_all_targets convenience function."""
        # Create temporary config file
        config_data = {
            "scrape_configs": [
                {
                    "job_name": "test-app",
                    "static_configs": [{"targets": ["localhost:8000"]}]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.content = b"test_metric 1"
            mock_response.text = "test_metric 1"
            mock_response.json.return_value = {"status": "healthy"}
            
            with patch('src.monitoring.metrics_endpoint_verifier.requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session
                
                result = await verify_all_targets(config_path)
                
                assert "summary" in result
                assert "verification_results" in result
                assert result["summary"]["total_targets"] == 1
        
        finally:
            Path(config_path).unlink()


class TestPrometheusMetricsValidation:
    """Test Prometheus metrics format validation specifically."""
    
    @pytest.fixture
    def verifier(self):
        return MetricsEndpointVerifier()
    
    def test_prometheus_metric_pattern(self, verifier):
        """Test Prometheus metric pattern matching."""
        valid_metrics = [
            "http_requests_total 100",
            "http_requests_total{method=\"GET\"} 100",
            "http_requests_total{method=\"GET\",status=\"200\"} 100",
            "cpu_usage 0.75",
            "memory_usage_bytes 1024000000",
            "response_time_seconds 0.123",
            "metric_with_timestamp 100 1234567890"
        ]
        
        invalid_metrics = [
            "123invalid_start 100",
            "metric-with-dashes 100",
            "metric without_value",
            "metric 100 extra_stuff",
            ""
        ]
        
        for metric in valid_metrics:
            assert verifier.prometheus_metric_pattern.match(metric), f"Should match: {metric}"
        
        for metric in invalid_metrics:
            assert not verifier.prometheus_metric_pattern.match(metric), f"Should not match: {metric}"
    
    @pytest.mark.asyncio
    async def test_complex_metrics_validation(self, verifier):
        """Test validation of complex Prometheus metrics."""
        complex_metrics = """# HELP http_requests_total The total number of HTTP requests.
# TYPE http_requests_total counter
http_requests_total{method="post",code="200"} 1027 1395066363000
http_requests_total{method="post",code="400"}    3 1395066363000

# HELP http_request_duration_seconds A histogram of the request duration.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.05"} 24054
http_request_duration_seconds_bucket{le="0.1"} 33444
http_request_duration_seconds_bucket{le="0.2"} 100392
http_request_duration_seconds_bucket{le="+Inf"} 144320
http_request_duration_seconds_sum 53423
http_request_duration_seconds_count 144320

# HELP rpc_duration_seconds A summary of the RPC duration in seconds.
# TYPE rpc_duration_seconds summary
rpc_duration_seconds{quantile="0.01"} 3102
rpc_duration_seconds{quantile="0.05"} 3272
rpc_duration_seconds{quantile="0.5"} 4773
rpc_duration_seconds{quantile="0.9"} 9001
rpc_duration_seconds{quantile="0.99"} 76656
rpc_duration_seconds_sum 1.7560473e+07
rpc_duration_seconds_count 2693
"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = complex_metrics
        mock_response.headers = {"content-type": "text/plain"}
        
        with patch.object(verifier.session, 'get', return_value=mock_response):
            result = await verifier.validate_metrics_format("http://localhost:8000/metrics")
            
            assert result.valid_format is True
            assert result.prometheus_compliant is True
            assert result.metrics_count > 10
            assert "http_requests_total" in result.valid_metrics
            assert "http_request_duration_seconds_bucket" in result.valid_metrics
            assert "rpc_duration_seconds" in result.valid_metrics
            assert len(result.format_errors) == 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
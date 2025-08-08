"""
Tests for Prometheus health check and diagnostic system.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.prometheus_health import (
    PrometheusHealthChecker,
    PrometheusHealthResult,
    PrometheusConfigStatus,
    check_prometheus_health,
    diagnose_prometheus_issues,
    generate_prometheus_report
)


class TestPrometheusHealthChecker:
    """Test cases for PrometheusHealthChecker class."""
    
    def test_initialization(self):
        """Test PrometheusHealthChecker initialization."""
        checker = PrometheusHealthChecker()
        assert checker.prometheus_url == "http://localhost:9091"
        assert checker.config_path == Path("monitoring/prometheus/prometheus.yml")
        assert checker.timeout == 10
        checker.close()
    
    def test_custom_initialization(self):
        """Test PrometheusHealthChecker with custom parameters."""
        checker = PrometheusHealthChecker(
            prometheus_url="http://custom:9090",
            config_path="custom/prometheus.yml",
            timeout=5
        )
        assert checker.prometheus_url == "http://custom:9090"
        assert checker.config_path == Path("custom/prometheus.yml")
        assert checker.timeout == 5
        checker.close()
    
    @pytest.mark.asyncio
    async def test_check_service_running_success(self):
        """Test successful service running check."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await checker._check_service_running()
            assert result is True
            mock_get.assert_called_once_with(
                "http://localhost:9091/-/healthy",
                timeout=10
            )
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_check_service_running_failure(self):
        """Test failed service running check."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            
            result = await checker._check_service_running()
            assert result is False
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_check_service_running_connection_error(self):
        """Test service running check with connection error."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker.session, 'get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            result = await checker._check_service_running()
            assert result is False
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_validate_configuration_missing_file(self):
        """Test configuration validation with missing file."""
        checker = PrometheusHealthChecker(config_path="nonexistent.yml")
        
        result = await checker._validate_configuration()
        
        assert result.yaml_valid is False
        assert len(result.validation_errors) > 0
        assert "Configuration file not found" in result.validation_errors[0]
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_validate_configuration_valid_yaml(self):
        """Test configuration validation with valid YAML."""
        # Create a temporary config file
        import tempfile
        import yaml
        
        config_data = {
            'global': {'scrape_interval': '15s'},
            'scrape_configs': [
                {
                    'job_name': 'test',
                    'static_configs': [{'targets': ['localhost:8000']}]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            checker = PrometheusHealthChecker(config_path=temp_path)
            
            with patch.object(checker, '_check_target_accessibility', return_value=True):
                result = await checker._validate_configuration()
            
            assert result.yaml_valid is True
            assert len(result.scrape_configs) == 1
            assert result.scrape_configs[0]['job_name'] == 'test'
            
            checker.close()
        finally:
            Path(temp_path).unlink()
    
    @pytest.mark.asyncio
    async def test_check_endpoints_accessibility(self):
        """Test endpoint accessibility checking."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await checker._check_endpoints_accessibility()
            
            expected_endpoints = ['health', 'ready', 'config', 'targets', 'metrics']
            assert all(endpoint in result for endpoint in expected_endpoints)
            assert all(result[endpoint] is True for endpoint in expected_endpoints)
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_healthy(self):
        """Test comprehensive health check with healthy service."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker, '_check_service_running', return_value=True), \
             patch.object(checker, '_validate_configuration') as mock_validate, \
             patch.object(checker, '_check_endpoints_accessibility', return_value={'health': True}), \
             patch.object(checker, '_get_prometheus_version', return_value='2.40.0'), \
             patch.object(checker, '_get_prometheus_uptime', return_value=3600.0):
            
            mock_config = PrometheusConfigStatus(
                yaml_valid=True,
                scrape_configs=[],
                target_accessibility={},
                validation_errors=[],
                recommendations=[]
            )
            mock_validate.return_value = mock_config
            
            result = await checker.comprehensive_health_check()
            
            assert result.status == "healthy"
            assert result.service_running is True
            assert result.config_valid is True
            assert result.version == "2.40.0"
            assert result.uptime_seconds == 3600.0
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_failed(self):
        """Test comprehensive health check with failed service."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker, '_check_service_running', return_value=False), \
             patch.object(checker, '_validate_configuration') as mock_validate:
            
            mock_config = PrometheusConfigStatus(
                yaml_valid=True,
                scrape_configs=[],
                target_accessibility={},
                validation_errors=[],
                recommendations=[]
            )
            mock_validate.return_value = mock_config
            
            result = await checker.comprehensive_health_check()
            
            assert result.status == "failed"
            assert result.service_running is False
            assert len(result.error_messages) > 0
            assert len(result.recovery_actions) > 0
        
        checker.close()
    
    def test_diagnose_failures(self):
        """Test failure diagnosis."""
        checker = PrometheusHealthChecker()
        
        # Create a failed health result
        health_result = PrometheusHealthResult(
            status="failed",
            timestamp=None,
            service_running=False,
            config_valid=True,
            endpoints_accessible={},
            error_messages=["Service not running"],
            recovery_actions=["Start service"],
            response_time_ms=100.0
        )
        
        with patch.object(checker, '_get_system_info', return_value={"platform": "test"}):
            diagnosis = checker.diagnose_failures(health_result)
        
        assert "issues_found" in diagnosis
        assert "root_causes" in diagnosis
        assert "troubleshooting_steps" in diagnosis
        assert len(diagnosis["issues_found"]) > 0
        
        checker.close()
    
    @pytest.mark.asyncio
    async def test_generate_health_report(self):
        """Test health report generation."""
        checker = PrometheusHealthChecker()
        
        with patch.object(checker, 'comprehensive_health_check') as mock_health, \
             patch.object(checker, '_validate_configuration') as mock_config, \
             patch.object(checker, 'diagnose_failures', return_value={"test": "diagnosis"}):
            
            mock_health_result = PrometheusHealthResult(
                status="degraded",
                timestamp=None,
                service_running=True,
                config_valid=False,
                endpoints_accessible={},
                error_messages=["Config issue"],
                recovery_actions=["Fix config"],
                response_time_ms=150.0
            )
            mock_health.return_value = mock_health_result
            
            mock_config_result = PrometheusConfigStatus(
                yaml_valid=False,
                scrape_configs=[],
                target_accessibility={},
                validation_errors=["YAML error"],
                recommendations=["Fix YAML"]
            )
            mock_config.return_value = mock_config_result
            
            report = await checker.generate_health_report()
            
            assert "report_timestamp" in report
            assert "health_check" in report
            assert "configuration_status" in report
            assert "diagnosis" in report
            assert "recommendations" in report
        
        checker.close()


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    @pytest.mark.asyncio
    async def test_check_prometheus_health(self):
        """Test check_prometheus_health convenience function."""
        with patch('monitoring.prometheus_health.PrometheusHealthChecker') as mock_checker_class:
            mock_checker = Mock()
            mock_result = PrometheusHealthResult(
                status="healthy",
                timestamp=None,
                service_running=True,
                config_valid=True,
                endpoints_accessible={},
                error_messages=[],
                recovery_actions=[],
                response_time_ms=50.0
            )
            mock_checker.comprehensive_health_check = AsyncMock(return_value=mock_result)
            mock_checker_class.return_value = mock_checker
            
            result = await check_prometheus_health()
            
            assert result.status == "healthy"
            mock_checker.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_diagnose_prometheus_issues(self):
        """Test diagnose_prometheus_issues convenience function."""
        with patch('monitoring.prometheus_health.PrometheusHealthChecker') as mock_checker_class:
            mock_checker = Mock()
            mock_health_result = PrometheusHealthResult(
                status="failed",
                timestamp=None,
                service_running=False,
                config_valid=True,
                endpoints_accessible={},
                error_messages=["Service down"],
                recovery_actions=["Start service"],
                response_time_ms=0.0
            )
            mock_checker.comprehensive_health_check = AsyncMock(return_value=mock_health_result)
            mock_checker.diagnose_failures.return_value = {"diagnosis": "test"}
            mock_checker_class.return_value = mock_checker
            
            result = await diagnose_prometheus_issues()
            
            assert result == {"diagnosis": "test"}
            mock_checker.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_prometheus_report(self):
        """Test generate_prometheus_report convenience function."""
        with patch('monitoring.prometheus_health.PrometheusHealthChecker') as mock_checker_class:
            mock_checker = Mock()
            mock_checker.generate_health_report = AsyncMock(return_value={"report": "test"})
            mock_checker_class.return_value = mock_checker
            
            result = await generate_prometheus_report()
            
            assert result == {"report": "test"}
            mock_checker.close.assert_called_once()


class TestDataClasses:
    """Test cases for data classes."""
    
    def test_prometheus_health_result_to_dict(self):
        """Test PrometheusHealthResult to_dict method."""
        from datetime import datetime
        
        result = PrometheusHealthResult(
            status="healthy",
            timestamp=datetime(2023, 1, 1, 12, 0, 0),
            service_running=True,
            config_valid=True,
            endpoints_accessible={"health": True},
            error_messages=[],
            recovery_actions=[],
            response_time_ms=100.0,
            version="2.40.0"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["status"] == "healthy"
        assert result_dict["timestamp"] == "2023-01-01T12:00:00"
        assert result_dict["service_running"] is True
        assert result_dict["version"] == "2.40.0"
    
    def test_prometheus_config_status_to_dict(self):
        """Test PrometheusConfigStatus to_dict method."""
        from datetime import datetime
        
        config_status = PrometheusConfigStatus(
            yaml_valid=True,
            scrape_configs=[{"job_name": "test"}],
            target_accessibility={"localhost:8000": True},
            validation_errors=[],
            recommendations=[],
            last_modified=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        config_dict = config_status.to_dict()
        
        assert config_dict["yaml_valid"] is True
        assert config_dict["last_modified"] == "2023-01-01T12:00:00"
        assert len(config_dict["scrape_configs"]) == 1


if __name__ == "__main__":
    # Run basic tests
    print("Running basic Prometheus health check tests...")
    
    # Test initialization
    checker = PrometheusHealthChecker()
    print("✅ PrometheusHealthChecker initialized")
    checker.close()
    print("✅ PrometheusHealthChecker closed")
    
    # Test data classes
    from datetime import datetime
    result = PrometheusHealthResult(
        status="test",
        timestamp=datetime.now(),
        service_running=False,
        config_valid=False,
        endpoints_accessible={},
        error_messages=["test error"],
        recovery_actions=["test action"],
        response_time_ms=0.0
    )
    result_dict = result.to_dict()
    print("✅ PrometheusHealthResult serialization works")
    
    print("✅ All basic tests passed!")
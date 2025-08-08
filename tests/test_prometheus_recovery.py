"""
Tests for Prometheus Auto-Recovery System
"""

import pytest
import asyncio
import tempfile
import yaml
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime

from src.monitoring.prometheus_recovery import (
    PrometheusRecovery,
    RecoveryAction,
    RecoveryResult,
    recover_prometheus,
    create_fallback_prometheus_config
)


class TestPrometheusRecovery:
    """Test cases for PrometheusRecovery class."""
    
    @pytest.fixture
    def recovery_instance(self):
        """Create a PrometheusRecovery instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "prometheus.yml"
            docker_compose_path = Path(temp_dir) / "docker-compose.yml"
            
            return PrometheusRecovery(
                prometheus_url="http://localhost:9091",
                config_path=str(config_path),
                docker_compose_path=str(docker_compose_path),
                max_retries=3,
                base_delay=0.1  # Faster for testing
            )
    
    @pytest.mark.asyncio
    async def test_check_service_status_healthy(self, recovery_instance):
        """Test service status check when Prometheus is healthy."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            action = await recovery_instance._check_service_status()
            
            assert action.action_type == "status_check"
            assert action.success is True
            assert "Service healthy" in action.details
            assert action.duration_seconds > 0
    
    @pytest.mark.asyncio
    async def test_check_service_status_unhealthy(self, recovery_instance):
        """Test service status check when Prometheus is unhealthy."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_get.return_value = mock_response
            
            action = await recovery_instance._check_service_status()
            
            assert action.action_type == "status_check"
            assert action.success is False
            assert "HTTP 503" in action.details
    
    @pytest.mark.asyncio
    async def test_check_service_status_connection_error(self, recovery_instance):
        """Test service status check when connection fails."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
            
            action = await recovery_instance._check_service_status()
            
            assert action.action_type == "status_check"
            assert action.success is False
            assert "Connection failed" in action.details
    
    @pytest.mark.asyncio
    async def test_validate_and_fix_config_missing_file(self, recovery_instance):
        """Test configuration validation when config file is missing."""
        action = await recovery_instance._validate_and_fix_config()
        
        assert action.action_type == "config_validation"
        assert action.success is True
        assert "Created fallback configuration" in action.details
        assert recovery_instance.config_path.exists()
        
        # Verify the created config is valid YAML
        with open(recovery_instance.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        assert 'global' in config
        assert 'scrape_configs' in config
        assert len(config['scrape_configs']) > 0
    
    @pytest.mark.asyncio
    async def test_validate_and_fix_config_existing_valid(self, recovery_instance):
        """Test configuration validation with existing valid config."""
        # Create a valid config file
        config = {
            'global': {'scrape_interval': '15s'},
            'scrape_configs': [
                {'job_name': 'test', 'static_configs': [{'targets': ['localhost:8000']}]}
            ]
        }
        
        recovery_instance.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(recovery_instance.config_path, 'w') as f:
            yaml.dump(config, f)
        
        action = await recovery_instance._validate_and_fix_config()
        
        assert action.action_type == "config_validation"
        assert action.success is True
        assert "Configuration is valid" in action.details
    
    @pytest.mark.asyncio
    async def test_validate_and_fix_config_missing_scrape_configs(self, recovery_instance):
        """Test configuration validation with missing scrape_configs."""
        # Create config without scrape_configs
        config = {'global': {'scrape_interval': '15s'}}
        
        recovery_instance.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(recovery_instance.config_path, 'w') as f:
            yaml.dump(config, f)
        
        action = await recovery_instance._validate_and_fix_config()
        
        assert action.action_type == "config_validation"
        assert action.success is True
        assert "Fixed missing scrape_configs" in action.details
        
        # Verify scrape_configs were added
        with open(recovery_instance.config_path, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        assert 'scrape_configs' in updated_config
        assert len(updated_config['scrape_configs']) > 0
    
    @pytest.mark.asyncio
    async def test_restart_service_with_dependencies_success(self, recovery_instance):
        """Test successful service restart with dependencies."""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess calls
            mock_run.return_value = Mock(returncode=0, stderr="")
            
            action = await recovery_instance._restart_service_with_dependencies()
            
            assert action.action_type == "service_restart"
            assert action.success is True
            assert "Service restarted successfully" in action.details
            
            # Verify the correct sequence of docker-compose calls
            assert mock_run.call_count == 3  # stop, start deps, start prometheus
    
    @pytest.mark.asyncio
    async def test_restart_service_with_dependencies_failure(self, recovery_instance):
        """Test service restart failure."""
        with patch('subprocess.run') as mock_run:
            # Mock failed subprocess call
            mock_run.return_value = Mock(returncode=1, stderr="Container not found")
            
            action = await recovery_instance._restart_service_with_dependencies()
            
            assert action.action_type == "service_restart"
            assert action.success is False
            assert "Restart failed" in action.details
    
    @pytest.mark.asyncio
    async def test_wait_for_service_ready_success(self, recovery_instance):
        """Test waiting for service readiness - success case."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            action = await recovery_instance._wait_for_service_ready()
            
            assert action.action_type == "readiness_wait"
            assert action.success is True
            assert "Service ready after 1 attempts" in action.details
    
    @pytest.mark.asyncio
    async def test_wait_for_service_ready_failure(self, recovery_instance):
        """Test waiting for service readiness - failure case."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
            
            action = await recovery_instance._wait_for_service_ready()
            
            assert action.action_type == "readiness_wait"
            assert action.success is False
            assert f"Service not ready after {recovery_instance.max_retries} attempts" in action.details
    
    @pytest.mark.asyncio
    async def test_verify_recovery_success(self, recovery_instance):
        """Test recovery verification - success case."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            action = await recovery_instance._verify_recovery()
            
            assert action.action_type == "recovery_verification"
            assert action.success is True
            assert "All checks passed" in action.details
    
    @pytest.mark.asyncio
    async def test_verify_recovery_partial_failure(self, recovery_instance):
        """Test recovery verification - partial failure case."""
        with patch('requests.get') as mock_get:
            def side_effect(url, **kwargs):
                mock_response = Mock()
                if "healthy" in url:
                    mock_response.status_code = 200
                elif "query" in url:
                    mock_response.status_code = 503
                else:
                    mock_response.status_code = 200
                return mock_response
            
            mock_get.side_effect = side_effect
            
            action = await recovery_instance._verify_recovery()
            
            assert action.action_type == "recovery_verification"
            assert action.success is False
            assert "Query failed: 503" in action.details
    
    def test_generate_fallback_config(self, recovery_instance):
        """Test fallback configuration generation."""
        config = recovery_instance._generate_fallback_config()
        
        assert 'global' in config
        assert 'scrape_configs' in config
        assert config['global']['scrape_interval'] == '15s'
        assert len(config['scrape_configs']) > 0
        
        # Check that essential jobs are included
        job_names = [job['job_name'] for job in config['scrape_configs']]
        assert 'voice-ai-agent' in job_names
        assert 'prometheus' in job_names
    
    def test_get_default_scrape_configs(self, recovery_instance):
        """Test default scrape configurations."""
        configs = recovery_instance._get_default_scrape_configs()
        
        assert len(configs) >= 3
        
        # Verify structure of configs
        for config in configs:
            assert 'job_name' in config
            assert 'static_configs' in config
            assert 'metrics_path' in config
            assert 'scrape_interval' in config
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff_success(self, recovery_instance):
        """Test exponential backoff retry - success case."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:  # Succeed on second attempt
                return True
            return False
        
        success, details = await recovery_instance.retry_with_exponential_backoff(
            mock_operation, max_attempts=3, base_delay=0.01
        )
        
        assert success is True
        assert "Operation succeeded on attempt 2" in details
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff_failure(self, recovery_instance):
        """Test exponential backoff retry - failure case."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            return False
        
        success, details = await recovery_instance.retry_with_exponential_backoff(
            mock_operation, max_attempts=3, base_delay=0.01
        )
        
        assert success is False
        assert "Operation failed after 3 attempts" in details
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_already_healthy(self, recovery_instance):
        """Test recovery attempt when service is already healthy."""
        with patch.object(recovery_instance, '_check_service_status') as mock_status:
            mock_status.return_value = RecoveryAction(
                action_type="status_check",
                timestamp=datetime.now(),
                success=True,
                details="Service healthy",
                duration_seconds=0.1
            )
            
            result = await recovery_instance.attempt_recovery()
            
            assert result.success is True
            assert result.final_status == "healthy"
            assert len(result.actions_taken) == 1
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_full_process(self, recovery_instance):
        """Test full recovery process."""
        # Mock all the recovery steps
        with patch.object(recovery_instance, '_check_service_status') as mock_status, \
             patch.object(recovery_instance, '_validate_and_fix_config') as mock_config, \
             patch.object(recovery_instance, '_restart_service_with_dependencies') as mock_restart, \
             patch.object(recovery_instance, '_wait_for_service_ready') as mock_ready, \
             patch.object(recovery_instance, '_verify_recovery') as mock_verify:
            
            # First status check fails (needs recovery)
            mock_status.return_value = RecoveryAction(
                action_type="status_check", timestamp=datetime.now(),
                success=False, details="Service down", duration_seconds=0.1
            )
            
            mock_config.return_value = RecoveryAction(
                action_type="config_validation", timestamp=datetime.now(),
                success=True, details="Config fixed", duration_seconds=0.1
            )
            
            mock_restart.return_value = RecoveryAction(
                action_type="service_restart", timestamp=datetime.now(),
                success=True, details="Service restarted", duration_seconds=1.0
            )
            
            mock_ready.return_value = RecoveryAction(
                action_type="readiness_wait", timestamp=datetime.now(),
                success=True, details="Service ready", duration_seconds=2.0
            )
            
            mock_verify.return_value = RecoveryAction(
                action_type="recovery_verification", timestamp=datetime.now(),
                success=True, details="All checks passed", duration_seconds=0.5
            )
            
            result = await recovery_instance.attempt_recovery()
            
            assert result.success is True
            assert result.final_status == "healthy"
            assert len(result.actions_taken) == 5
            
            # Verify all steps were called
            mock_status.assert_called_once()
            mock_config.assert_called_once()
            mock_restart.assert_called_once()
            mock_ready.assert_called_once()
            mock_verify.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_recover_prometheus(self):
        """Test the recover_prometheus convenience function."""
        with patch('src.monitoring.prometheus_recovery.PrometheusRecovery') as mock_class:
            mock_instance = Mock()
            mock_result = RecoveryResult(
                success=True,
                actions_taken=[],
                final_status="healthy"
            )
            mock_instance.attempt_recovery = AsyncMock(return_value=mock_result)
            mock_class.return_value = mock_instance
            
            result = await recover_prometheus()
            
            assert result.success is True
            assert result.final_status == "healthy"
            mock_class.assert_called_once()
            mock_instance.attempt_recovery.assert_called_once()
    
    def test_create_fallback_prometheus_config(self):
        """Test the create_fallback_prometheus_config function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "prometheus.yml"
            
            create_fallback_prometheus_config(str(config_path))
            
            assert config_path.exists()
            
            # Verify the config is valid YAML
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            assert 'global' in config
            assert 'scrape_configs' in config


if __name__ == "__main__":
    pytest.main([__file__])
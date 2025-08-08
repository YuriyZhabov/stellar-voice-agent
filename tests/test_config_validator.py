"""
Unit tests for Prometheus Configuration Validator

Tests cover YAML syntax validation, configuration structure validation,
scrape target accessibility checking, and auto-correction functionality.
"""

import asyncio
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.monitoring.config_validator import (
    PrometheusConfigValidator,
    ValidationResult,
    TargetAccessibilityResult,
    validate_prometheus_config_syntax,
    check_prometheus_targets,
    validate_prometheus_config_comprehensive,
    auto_correct_prometheus_config
)


class TestPrometheusConfigValidator:
    """Test cases for PrometheusConfigValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return PrometheusConfigValidator(timeout=5)
    
    @pytest.fixture
    def valid_config(self):
        """Valid Prometheus configuration for testing."""
        return {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s',
                'external_labels': {
                    'monitor': 'test'
                }
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'static_configs': [
                        {'targets': ['localhost:9090']}
                    ]
                },
                {
                    'job_name': 'test-app',
                    'static_configs': [
                        {'targets': ['app:8000']}
                    ],
                    'metrics_path': '/metrics',
                    'scrape_interval': '10s'
                }
            ]
        }
    
    @pytest.fixture
    def invalid_config(self):
        """Invalid Prometheus configuration for testing."""
        return {
            'scrape_configs': [
                {
                    # Missing job_name
                    'static_configs': [
                        {'targets': ['invalid-target']}  # Missing port
                    ]
                }
            ]
            # Missing global section
        }
    
    def test_init(self, validator):
        """Test validator initialization."""
        assert validator.timeout == 5
        assert validator.session is not None
        assert validator.default_config is not None
        assert 'global' in validator.default_config
        assert 'scrape_configs' in validator.default_config
    
    def test_validate_yaml_syntax_valid_file(self, validator, valid_config):
        """Test YAML syntax validation with valid file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            result = validator.validate_yaml_syntax(temp_path)
            
            assert result.is_valid is True
            assert len(result.errors) == 0
            assert result.corrected_config is None
        finally:
            Path(temp_path).unlink()
    
    def test_validate_yaml_syntax_missing_file(self, validator):
        """Test YAML syntax validation with missing file."""
        result = validator.validate_yaml_syntax('/nonexistent/file.yml')
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert 'not found' in result.errors[0]
        assert result.corrected_config == validator.default_config
    
    def test_validate_yaml_syntax_empty_file(self, validator):
        """Test YAML syntax validation with empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            temp_path = f.name
        
        try:
            result = validator.validate_yaml_syntax(temp_path)
            
            assert result.is_valid is False
            assert len(result.errors) == 1
            assert 'empty' in result.errors[0]
            assert result.corrected_config == validator.default_config
        finally:
            Path(temp_path).unlink()
    
    def test_validate_yaml_syntax_invalid_yaml(self, validator):
        """Test YAML syntax validation with invalid YAML."""
        invalid_yaml = """
        global:
          scrape_interval: 15s
        scrape_configs:
          - job_name: test
            static_configs:
              - targets: [localhost:9090
        """  # Missing closing bracket
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(invalid_yaml)
            temp_path = f.name
        
        try:
            result = validator.validate_yaml_syntax(temp_path)
            
            assert result.is_valid is False
            assert len(result.errors) == 1
            assert 'YAML syntax error' in result.errors[0]
            assert result.corrected_config == validator.default_config
        finally:
            Path(temp_path).unlink()
    
    def test_validate_yaml_syntax_with_tabs(self, validator, valid_config):
        """Test YAML syntax validation with tabs (should fail)."""
        yaml_with_tabs = yaml.dump(valid_config).replace('  ', '\t')
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_with_tabs)
            temp_path = f.name
        
        try:
            result = validator.validate_yaml_syntax(temp_path)
            
            # YAML with tabs should fail validation
            assert result.is_valid is False
            assert len(result.errors) >= 1
            assert any('YAML syntax error' in error for error in result.errors)
            # Should still warn about tabs
            assert len(result.warnings) >= 1
            assert any('tabs' in warning for warning in result.warnings)
        finally:
            Path(temp_path).unlink()
    
    def test_validate_configuration_structure_valid(self, validator, valid_config):
        """Test configuration structure validation with valid config."""
        result = validator.validate_configuration_structure(valid_config)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.corrected_config is None
    
    def test_validate_configuration_structure_missing_global(self, validator):
        """Test configuration structure validation with missing global section."""
        config = {
            'scrape_configs': [
                {
                    'job_name': 'test',
                    'static_configs': [{'targets': ['localhost:9090']}]
                }
            ]
        }
        
        result = validator.validate_configuration_structure(config)
        
        assert result.is_valid is True  # Missing global is warning, not error
        assert len(result.warnings) >= 1
        assert any('global' in warning for warning in result.warnings)
        assert 'global' in result.corrected_config
    
    def test_validate_configuration_structure_missing_scrape_configs(self, validator):
        """Test configuration structure validation with missing scrape_configs."""
        config = {
            'global': {
                'scrape_interval': '15s'
            }
        }
        
        result = validator.validate_configuration_structure(config)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any('scrape_configs' in error for error in result.errors)
        assert 'scrape_configs' in result.corrected_config
    
    def test_validate_configuration_structure_invalid_scrape_config(self, validator, invalid_config):
        """Test configuration structure validation with invalid scrape config."""
        result = validator.validate_configuration_structure(invalid_config)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        # Should have errors for missing job_name and invalid target format
        error_text = ' '.join(result.errors)
        assert 'job_name' in error_text
    
    def test_validate_scrape_config_missing_job_name(self, validator):
        """Test scrape config validation with missing job_name."""
        errors, warnings, suggestions = [], [], []
        scrape_config = {
            'static_configs': [{'targets': ['localhost:9090']}]
        }
        
        corrected = validator._validate_scrape_config(scrape_config, 0, errors, warnings, suggestions)
        
        assert len(errors) >= 1
        assert any('job_name' in error for error in errors)
        assert 'job_name' in corrected
        assert corrected['job_name'] == 'job_0'
    
    def test_validate_scrape_config_missing_static_configs(self, validator):
        """Test scrape config validation with missing static_configs."""
        errors, warnings, suggestions = [], [], []
        scrape_config = {
            'job_name': 'test'
        }
        
        corrected = validator._validate_scrape_config(scrape_config, 0, errors, warnings, suggestions)
        
        assert len(errors) >= 1
        assert any('static_configs' in error for error in errors)
        assert 'static_configs' in corrected
    
    def test_validate_scrape_config_invalid_target_format(self, validator):
        """Test scrape config validation with invalid target format."""
        errors, warnings, suggestions = [], [], []
        scrape_config = {
            'job_name': 'test',
            'static_configs': [
                {'targets': ['localhost']}  # Missing port
            ]
        }
        
        corrected = validator._validate_scrape_config(scrape_config, 0, errors, warnings, suggestions)
        
        assert len(warnings) >= 1
        assert any('port' in warning for warning in warnings)
        # Should auto-correct by adding default port
        assert corrected['static_configs'][0]['targets'][0] == 'localhost:9090'
    
    @pytest.mark.asyncio
    async def test_check_single_target_accessibility_invalid_format(self, validator):
        """Test single target accessibility check with invalid format."""
        result = await validator._check_single_target_accessibility('invalid-target', 'test')
        
        assert result.accessible is False
        assert result.target == 'invalid-target'
        assert 'missing port' in result.error_message
    
    @pytest.mark.asyncio
    async def test_check_single_target_accessibility_invalid_port(self, validator):
        """Test single target accessibility check with invalid port."""
        result = await validator._check_single_target_accessibility('localhost:invalid', 'test')
        
        assert result.accessible is False
        assert result.target == 'localhost:invalid'
        assert 'Invalid port' in result.error_message
    
    @pytest.mark.asyncio
    @patch('socket.socket')
    async def test_check_single_target_accessibility_tcp_failure(self, mock_socket, validator):
        """Test single target accessibility check with TCP connection failure."""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Connection failed
        mock_socket.return_value = mock_sock
        
        result = await validator._check_single_target_accessibility('localhost:9090', 'test')
        
        assert result.accessible is False
        assert result.target == 'localhost:9090'
        assert 'TCP connection failed' in result.error_message
    
    @pytest.mark.asyncio
    @patch('socket.socket')
    @patch('requests.Session.get')
    async def test_check_single_target_accessibility_http_success(self, mock_get, mock_socket, validator):
        """Test single target accessibility check with successful HTTP response."""
        # Mock successful TCP connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0  # Connection successful
        mock_socket.return_value = mock_sock
        
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = await validator._check_single_target_accessibility('localhost:9090', 'test')
        
        assert result.accessible is True
        assert result.target == 'localhost:9090'
        assert result.status_code == 200
        assert result.error_message is None
    
    @pytest.mark.asyncio
    @patch('socket.socket')
    @patch('requests.Session.get')
    async def test_check_single_target_accessibility_http_error(self, mock_get, mock_socket, validator):
        """Test single target accessibility check with HTTP error response."""
        # Mock successful TCP connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = await validator._check_single_target_accessibility('localhost:9090', 'test')
        
        assert result.accessible is False
        assert result.target == 'localhost:9090'
        assert result.status_code == 500
        assert 'HTTP 500' in result.error_message
    
    @pytest.mark.asyncio
    async def test_check_scrape_targets_accessibility_no_configs(self, validator):
        """Test scrape targets accessibility check with no scrape configs."""
        config = {'global': {'scrape_interval': '15s'}}
        
        results = await validator.check_scrape_targets_accessibility(config)
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    @patch.object(PrometheusConfigValidator, '_check_single_target_accessibility')
    async def test_check_scrape_targets_accessibility_multiple_targets(self, mock_check, validator, valid_config):
        """Test scrape targets accessibility check with multiple targets."""
        # Mock the single target check
        mock_check.side_effect = [
            TargetAccessibilityResult('localhost:9090', True, 10.0, 200, None),
            TargetAccessibilityResult('app:8000', False, 5000.0, None, 'Connection failed')
        ]
        
        results = await validator.check_scrape_targets_accessibility(valid_config)
        
        assert len(results) == 2
        assert results[0].accessible is True
        assert results[1].accessible is False
        assert mock_check.call_count == 2
    
    def test_auto_correct_configuration_missing_file(self, validator):
        """Test auto-correction with missing configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_file = Path(temp_dir) / 'missing.yml'
            result = validator.auto_correct_configuration(missing_file, backup=False)
            
            # Should create the file with default config
            assert result.is_valid is True
            assert missing_file.exists()
            assert result.corrected_config is not None
            assert 'created' in ' '.join(result.suggestions).lower()
    
    def test_auto_correct_configuration_valid_file(self, validator, valid_config):
        """Test auto-correction with valid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            result = validator.auto_correct_configuration(temp_path, backup=False)
            
            # Valid config should not need correction
            assert result.is_valid is True
            assert len(result.errors) == 0
        finally:
            Path(temp_path).unlink()
    
    def test_auto_correct_configuration_invalid_file(self, validator, invalid_config):
        """Test auto-correction with invalid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            result = validator.auto_correct_configuration(temp_path, backup=False)
            
            assert result.is_valid is True  # Should be corrected
            assert result.corrected_config is not None
            
            # Check that file was actually corrected
            with open(temp_path, 'r') as corrected_file:
                corrected_data = yaml.safe_load(corrected_file)
                assert 'global' in corrected_data
                assert corrected_data['scrape_configs'][0]['job_name'] == 'job_0'
        finally:
            Path(temp_path).unlink()
    
    def test_auto_correct_configuration_with_backup(self, validator, invalid_config):
        """Test auto-correction with backup creation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(invalid_config, f)
            temp_path = Path(f.name)
        
        try:
            result = validator.auto_correct_configuration(temp_path, backup=True)
            
            assert result.is_valid is True
            
            # Check that backup was created
            backup_files = list(temp_path.parent.glob(f"{temp_path.stem}.backup.*.yml"))
            assert len(backup_files) == 1
            
            # Clean up backup
            backup_files[0].unlink()
        finally:
            temp_path.unlink()
    
    @pytest.mark.asyncio
    @patch.object(PrometheusConfigValidator, 'check_scrape_targets_accessibility')
    async def test_comprehensive_validation_success(self, mock_check_targets, validator, valid_config):
        """Test comprehensive validation with successful results."""
        # Mock target accessibility check
        mock_check_targets.return_value = [
            TargetAccessibilityResult('localhost:9090', True, 10.0, 200, None),
            TargetAccessibilityResult('app:8000', True, 15.0, 200, None)
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            results = await validator.comprehensive_validation(temp_path)
            
            assert results['overall_status'] == 'healthy'
            assert results['syntax_validation']['is_valid'] is True
            assert results['structure_validation']['is_valid'] is True
            assert results['summary']['total_errors'] == 0
            assert results['summary']['accessible_targets'] == 2
            assert results['summary']['total_targets'] == 2
        finally:
            Path(temp_path).unlink()
    
    @pytest.mark.asyncio
    async def test_comprehensive_validation_syntax_error(self, validator):
        """Test comprehensive validation with syntax errors."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(invalid_yaml)
            temp_path = f.name
        
        try:
            results = await validator.comprehensive_validation(temp_path)
            
            assert results['overall_status'] == 'failed'
            assert results['syntax_validation']['is_valid'] is False
            assert results['summary']['total_errors'] > 0
        finally:
            Path(temp_path).unlink()
    
    @pytest.mark.asyncio
    @patch.object(PrometheusConfigValidator, 'check_scrape_targets_accessibility')
    async def test_comprehensive_validation_degraded(self, mock_check_targets, validator, valid_config):
        """Test comprehensive validation with degraded status."""
        # Mock mixed target accessibility results
        mock_check_targets.return_value = [
            TargetAccessibilityResult('localhost:9090', True, 10.0, 200, None),
            TargetAccessibilityResult('app:8000', False, 5000.0, None, 'Connection failed')
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            results = await validator.comprehensive_validation(temp_path)
            
            assert results['overall_status'] == 'degraded'
            assert results['syntax_validation']['is_valid'] is True
            assert results['structure_validation']['is_valid'] is True
            assert results['summary']['accessible_targets'] == 1
            assert results['summary']['total_targets'] == 2
        finally:
            Path(temp_path).unlink()
    
    def test_close(self, validator):
        """Test validator cleanup."""
        validator.close()
        # Should not raise any exceptions


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_validate_prometheus_config_syntax(self):
        """Test syntax validation convenience function."""
        valid_config = {
            'global': {'scrape_interval': '15s'},
            'scrape_configs': [
                {'job_name': 'test', 'static_configs': [{'targets': ['localhost:9090']}]}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            result = validate_prometheus_config_syntax(temp_path)
            assert result.is_valid is True
        finally:
            Path(temp_path).unlink()
    
    @pytest.mark.asyncio
    @patch.object(PrometheusConfigValidator, 'check_scrape_targets_accessibility')
    async def test_check_prometheus_targets(self, mock_check):
        """Test target checking convenience function."""
        mock_check.return_value = [
            TargetAccessibilityResult('localhost:9090', True, 10.0, 200, None)
        ]
        
        valid_config = {
            'scrape_configs': [
                {'job_name': 'test', 'static_configs': [{'targets': ['localhost:9090']}]}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            results = await check_prometheus_targets(temp_path)
            assert len(results) == 1
            assert results[0].accessible is True
        finally:
            Path(temp_path).unlink()
    
    @pytest.mark.asyncio
    @patch.object(PrometheusConfigValidator, 'comprehensive_validation')
    async def test_validate_prometheus_config_comprehensive(self, mock_validation):
        """Test comprehensive validation convenience function."""
        mock_validation.return_value = {'overall_status': 'healthy'}
        
        result = await validate_prometheus_config_comprehensive('/test/path.yml')
        assert result['overall_status'] == 'healthy'
        mock_validation.assert_called_once_with('/test/path.yml')
    
    def test_auto_correct_prometheus_config(self):
        """Test auto-correction convenience function."""
        valid_config = {
            'global': {'scrape_interval': '15s'},
            'scrape_configs': [
                {'job_name': 'test', 'static_configs': [{'targets': ['localhost:9090']}]}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name
        
        try:
            result = auto_correct_prometheus_config(temp_path, backup=False)
            assert result.is_valid is True
        finally:
            Path(temp_path).unlink()


if __name__ == '__main__':
    pytest.main([__file__])
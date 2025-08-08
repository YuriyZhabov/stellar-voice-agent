"""
Tests for LiveKit Security Configuration

Tests all security features including:
- API key protection
- WSS enforcement
- Key rotation
- Access validation
- Suspicious activity monitoring
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, patch, AsyncMock

from src.security.livekit_security import (
    LiveKitSecurityManager, 
    SecureLogger, 
    SecurityEventType,
    get_security_manager,
    initialize_security
)
from src.security.security_integration import (
    SecurityIntegratedAuthManager,
    SecurityIntegratedAPIClient,
    security_required,
    SecureWebhookHandler,
    SecurityHealthChecker
)


class TestSecureLogger:
    """Test secure logging functionality."""
    
    def test_mask_api_keys(self):
        """Test that API keys are masked in logs."""
        logger = SecureLogger("test")
        
        test_message = 'api_key="sk-test123456789" and api_secret="secret123"'
        masked = logger._mask_sensitive_data(test_message)
        
        assert "sk-test123456" not in masked
        assert "secret123" not in masked
        assert "***MASKED***" in masked
    
    def test_mask_jwt_tokens(self):
        """Test that JWT tokens are masked in logs."""
        logger = SecureLogger("test")
        
        test_message = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature'
        masked = logger._mask_sensitive_data(test_message)
        
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature" not in masked
        assert "***MASKED***" in masked
    
    def test_mask_passwords(self):
        """Test that passwords are masked in logs."""
        logger = SecureLogger("test")
        
        test_message = 'password="mypassword123" token="abc123"'
        masked = logger._mask_sensitive_data(test_message)
        
        assert "mypassword123" not in masked
        assert "abc123" not in masked
        assert "***MASKED***" in masked


class TestLiveKitSecurityManager:
    """Test LiveKit security manager functionality."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
wss_enforcement:
  enabled: true
  allowed_protocols: ["wss", "https"]
  redirect_http_to_https: true

key_rotation:
  enabled: true
  rotation_interval_hours: 24
  overlap_period_minutes: 30
  auto_rotation: false

access_validation:
  strict_mode: true
  validate_all_grants: true
  log_access_attempts: true

suspicious_activity:
  max_failed_attempts: 3
  lockout_duration_minutes: 15
  rate_limit_per_minute: 100
  unusual_usage_threshold: 1000

logging:
  mask_sensitive_data: true
  log_level: "INFO"
  audit_log_retention_days: 90
""")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_security_manager_initialization(self, temp_config_file):
        """Test security manager initialization."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        assert manager.config is not None
        assert manager.config["wss_enforcement"]["enabled"] is True
        assert manager.config["key_rotation"]["enabled"] is True
    
    def test_api_key_validation(self, temp_config_file):
        """Test API key format validation."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Valid API key
        assert manager.validate_api_key_format("sk-test123456789012345678901234567890")
        
        # Invalid API keys
        assert not manager.validate_api_key_format("short")
        assert not manager.validate_api_key_format("")
        assert not manager.validate_api_key_format(None)
    
    def test_wss_enforcement(self, temp_config_file):
        """Test WSS connection enforcement."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # HTTP should be converted to HTTPS
        assert manager.enforce_wss_connections("http://example.com") == "https://example.com"
        
        # WS should be converted to WSS
        assert manager.enforce_wss_connections("ws://example.com") == "wss://example.com"
        
        # HTTPS should remain unchanged
        assert manager.enforce_wss_connections("https://example.com") == "https://example.com"
        
        # WSS should remain unchanged
        assert manager.enforce_wss_connections("wss://example.com") == "wss://example.com"
    
    def test_connection_protocol_validation(self, temp_config_file):
        """Test connection protocol validation."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Secure protocols should be valid
        assert manager.validate_connection_protocol("https://example.com")
        assert manager.validate_connection_protocol("wss://example.com")
        
        # Insecure protocols should be invalid
        assert not manager.validate_connection_protocol("http://example.com")
        assert not manager.validate_connection_protocol("ws://example.com")
    
    @pytest.mark.asyncio
    async def test_key_rotation(self, temp_config_file):
        """Test API key rotation functionality."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Test key rotation
        new_keys = await manager.rotate_api_keys(force=True)
        
        assert "api_key" in new_keys
        assert "api_secret" in new_keys
        assert len(new_keys["api_key"]) >= 32
        assert len(new_keys["api_secret"]) >= 64
        
        # Check that rotation was recorded
        assert len(manager.key_rotation_history) > 0
        assert manager.key_rotation_history[-1]["rotation_type"] == "manual"
    
    def test_access_rights_validation(self, temp_config_file):
        """Test access rights validation."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Valid grants
        valid_grants = {
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True
        }
        assert manager.validate_access_rights(valid_grants, ["roomJoin", "canPublish"])
        
        # Missing required permission
        assert not manager.validate_access_rights(valid_grants, ["roomJoin", "roomAdmin"])
        
        # Invalid grant name (when validate_all_grants is True)
        invalid_grants = {
            "roomJoin": True,
            "invalidGrant": True
        }
        assert not manager.validate_access_rights(invalid_grants, ["roomJoin"])
    
    def test_jwt_token_validation(self, temp_config_file):
        """Test JWT token structure validation."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Mock a valid JWT token structure
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "iss": "api_key",
                "sub": "participant_id",
                "iat": 1234567890,
                "exp": 1234567890 + 600,
                "video": {"roomJoin": True}
            }
            
            assert manager.validate_jwt_token_structure("valid.jwt.token")
        
        # Mock an invalid JWT token structure (missing required fields)
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "iss": "api_key",
                "sub": "participant_id"
                # Missing iat, exp, video
            }
            
            assert not manager.validate_jwt_token_structure("invalid.jwt.token")
    
    def test_auth_attempt_recording(self, temp_config_file):
        """Test authentication attempt recording."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Record failed attempts
        for i in range(5):
            manager.record_auth_attempt("192.168.1.100", False, "test_user")
        
        # Check that IP is blocked after max attempts
        assert manager.is_ip_blocked("192.168.1.100")
        
        # Check that different IP is not blocked
        assert not manager.is_ip_blocked("192.168.1.101")
    
    def test_api_usage_recording(self, temp_config_file):
        """Test API usage recording."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Record API usage
        manager.record_api_usage("create_room", "192.168.1.100", 0.5)
        manager.record_api_usage("list_rooms", "192.168.1.100", 0.3)
        
        # Check that usage was recorded
        assert "create_room" in manager.api_usage_stats
        assert "list_rooms" in manager.api_usage_stats
        assert "192.168.1.100" in manager.api_usage_stats
    
    def test_security_status(self, temp_config_file):
        """Test security status reporting."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Record some test data
        manager.record_auth_attempt("192.168.1.100", False)
        manager.record_api_usage("test_endpoint", "192.168.1.100", 0.1)
        
        status = manager.get_security_status()
        
        assert "timestamp" in status
        assert "configuration" in status
        assert "metrics" in status
        assert "recent_events" in status
        
        assert status["configuration"]["wss_enforcement_enabled"] is True
        assert status["configuration"]["key_rotation_enabled"] is True


class TestSecurityIntegration:
    """Test security integration with other components."""
    
    @pytest.fixture
    def mock_security_manager(self):
        """Mock security manager for testing."""
        with patch('src.security.security_integration.get_security_manager') as mock:
            manager = Mock()
            manager.validate_api_key_format.return_value = True
            manager.validate_jwt_token_structure.return_value = True
            manager.validate_access_rights.return_value = True
            manager.enforce_wss_connections.return_value = "wss://example.com"
            manager.validate_connection_protocol.return_value = True
            manager.is_key_rotation_due.return_value = False
            manager.record_api_usage = Mock()
            manager.record_auth_attempt = Mock()
            manager.logger = Mock()
            mock.return_value = manager
            yield manager
    
    def test_security_integrated_auth_manager(self, mock_security_manager):
        """Test security-integrated auth manager."""
        auth_manager = SecurityIntegratedAuthManager("test_key", "test_secret")
        
        # Verify that API key validation was called
        mock_security_manager.validate_api_key_format.assert_called_with("test_key")
    
    def test_security_integrated_api_client(self, mock_security_manager):
        """Test security-integrated API client."""
        # Test WSS enforcement
        client = SecurityIntegratedAPIClient("ws://example.com", "test_key", "test_secret")
        
        # Verify that WSS enforcement was applied
        mock_security_manager.enforce_wss_connections.assert_called_with("ws://example.com")
        mock_security_manager.validate_connection_protocol.assert_called()
    
    @pytest.mark.asyncio
    async def test_security_required_decorator(self, mock_security_manager):
        """Test security required decorator."""
        
        @security_required(["roomJoin", "canPublish"])
        async def test_function(token, source_ip="127.0.0.1"):
            return "success"
        
        # Mock JWT decode
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test_user",
                "video": {"roomJoin": True, "canPublish": True}
            }
            
            result = await test_function("valid.jwt.token")
            assert result == "success"
            
            # Verify security checks were called
            mock_security_manager.validate_jwt_token_structure.assert_called()
            mock_security_manager.validate_access_rights.assert_called()
            mock_security_manager.record_auth_attempt.assert_called_with("127.0.0.1", True, "test_user")
    
    @pytest.mark.asyncio
    async def test_secure_webhook_handler(self, mock_security_manager):
        """Test secure webhook handler."""
        handler = SecureWebhookHandler()
        
        # Test room started webhook
        webhook_data = {
            "event": "room_started",
            "room": {"name": "test_room"}
        }
        
        with patch.object(handler, '_validate_webhook_signature', return_value=True):
            result = await handler.handle_webhook(webhook_data, "192.168.1.100")
            assert result["status"] == "processed"
            
            # Verify API usage was recorded
            mock_security_manager.record_api_usage.assert_called_with("webhook", "192.168.1.100", 0)
    
    @pytest.mark.asyncio
    async def test_security_health_checker(self, mock_security_manager):
        """Test security health checker."""
        # Mock security manager config and state
        mock_security_manager.config = {
            'wss_enforcement': {'enabled': True},
            'key_rotation': {'enabled': True}
        }
        mock_security_manager.is_key_rotation_due.return_value = False
        mock_security_manager.failed_auth_attempts = {}
        mock_security_manager.is_ip_blocked.return_value = False
        mock_security_manager.security_events = []
        
        health_checker = SecurityHealthChecker()
        health_status = await health_checker.check_security_health()
        
        assert health_status["overall_status"] == "healthy"
        assert "checks" in health_status
        assert "wss_enforcement" in health_status["checks"]
        assert "key_rotation" in health_status["checks"]


class TestSecurityConfiguration:
    """Test security configuration management."""
    
    def test_security_config_validation(self, temp_config_file):
        """Test security configuration validation."""
        manager = LiveKitSecurityManager(temp_config_file)
        
        # Valid configuration update
        valid_config = {
            "suspicious_activity": {
                "max_failed_attempts": 10,
                "lockout_duration_minutes": 30,
                "rate_limit_per_minute": 200,
                "unusual_usage_threshold": 2000
            }
        }
        
        manager.update_security_config(valid_config)
        assert manager.config["suspicious_activity"]["max_failed_attempts"] == 10
        
        # Invalid configuration should raise error
        invalid_config = {
            "suspicious_activity": {
                "max_failed_attempts": 0  # Invalid: must be at least 1
            }
        }
        
        with pytest.raises(ValueError):
            manager.update_security_config(invalid_config)


@pytest.mark.asyncio
async def test_security_monitoring_background_tasks():
    """Test security monitoring background tasks."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
wss_enforcement:
  enabled: true
  allowed_protocols: ["wss", "https"]

key_rotation:
  enabled: true
  rotation_interval_hours: 1  # Short interval for testing

access_validation:
  strict_mode: true

suspicious_activity:
  max_failed_attempts: 2
  lockout_duration_minutes: 1

logging:
  audit_log_retention_days: 1
""")
        temp_path = f.name
    
    try:
        manager = LiveKitSecurityManager(temp_path)
        
        # Add some test data
        manager.record_auth_attempt("192.168.1.100", False)
        manager.record_auth_attempt("192.168.1.100", False)
        manager.record_auth_attempt("192.168.1.100", False)  # Should trigger alert
        
        # Run security analysis
        await manager._analyze_security_patterns()
        
        # Check that security events were recorded
        assert len(manager.security_events) > 0
        
        # Check that failed auth pattern was detected
        failed_auth_events = [
            event for event in manager.security_events 
            if event.event_type == SecurityEventType.MULTIPLE_FAILED_AUTH
        ]
        assert len(failed_auth_events) > 0
        
    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
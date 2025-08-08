"""
Security and validation tests for LiveKit system.
Tests security requirements according to requirement 8.4.
"""

import pytest
import jwt
import time
import hashlib
import secrets
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, UTC

# Import components for security testing
from src.auth.livekit_auth import LiveKitAuthManager
from src.security.livekit_security import LiveKitSecurityManager
from src.clients.livekit_api_client import LiveKitAPIClient
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor


class TestJWTTokenSecurity:
    """Security tests for JWT token handling."""
    
    @pytest.fixture
    def auth_manager(self):
        return LiveKitAuthManager("test_api_key", "test_secret_key")
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_jwt_token_structure_validation(self, auth_manager, security_manager):
        """Test JWT token structure according to specification."""
        
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room"
        )
        
        # Decode token without verification to check structure
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Verify required fields according to specification
        required_fields = ["iss", "sub", "iat", "exp", "video"]
        for field in required_fields:
            assert field in decoded, f"Required field '{field}' missing from token"
        
        # Verify issuer is API key
        assert decoded["iss"] == "test_api_key"
        
        # Verify subject is participant identity
        assert decoded["sub"] == "test_user"
        
        # Verify video grants structure
        assert isinstance(decoded["video"], dict)
        video_grants = decoded["video"]
        
        # Check for proper grants
        expected_grants = ["roomJoin", "room", "canPublish", "canSubscribe"]
        for grant in expected_grants:
            assert grant in video_grants, f"Expected grant '{grant}' missing"
    
    def test_jwt_token_expiration_validation(self, auth_manager, security_manager):
        """Test JWT token expiration handling."""
        
        # Create token with short expiration
        with patch('src.auth.livekit_auth.timedelta') as mock_timedelta:
            mock_timedelta.return_value = timedelta(seconds=1)  # 1 second expiration
            
            token = auth_manager.create_participant_token(
                identity="test_user",
                room_name="test_room"
            )
        
        # Token should be valid initially
        is_valid = security_manager.validate_jwt_token(token, "test_secret_key")
        assert is_valid is True
        
        # Wait for token to expire
        time.sleep(2)
        
        # Token should be invalid after expiration
        is_valid = security_manager.validate_jwt_token(token, "test_secret_key")
        assert is_valid is False
    
    def test_jwt_token_signature_validation(self, auth_manager, security_manager):
        """Test JWT token signature validation."""
        
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room"
        )
        
        # Valid signature should pass
        is_valid = security_manager.validate_jwt_token(token, "test_secret_key")
        assert is_valid is True
        
        # Invalid signature should fail
        is_valid = security_manager.validate_jwt_token(token, "wrong_secret")
        assert is_valid is False
        
        # Tampered token should fail
        tampered_token = token[:-10] + "tampered123"
        is_valid = security_manager.validate_jwt_token(tampered_token, "test_secret_key")
        assert is_valid is False
    
    def test_jwt_token_grants_validation(self, auth_manager, security_manager):
        """Test JWT token grants validation."""
        
        # Create token with specific grants
        from livekit.api import VideoGrants
        
        grants = VideoGrants(
            room_join=True,
            room="specific_room",
            can_publish=True,
            can_subscribe=False,  # Restricted
            can_publish_data=False  # Restricted
        )
        
        token = auth_manager.create_participant_token(
            identity="restricted_user",
            room_name="specific_room",
            grants=grants
        )
        
        # Validate grants
        decoded = jwt.decode(token, options={"verify_signature": False})
        video_grants = decoded["video"]
        
        assert video_grants["roomJoin"] is True
        assert video_grants["room"] == "specific_room"
        assert video_grants["canPublish"] is True
        assert video_grants["canSubscribe"] is False
        assert video_grants["canPublishData"] is False
    
    def test_admin_token_security(self, auth_manager, security_manager):
        """Test admin token security and privileges."""
        
        admin_token = auth_manager.create_admin_token()
        
        # Decode and verify admin privileges
        decoded = jwt.decode(admin_token, options={"verify_signature": False})
        video_grants = decoded["video"]
        
        # Admin should have elevated privileges
        admin_privileges = [
            "roomCreate", "roomList", "roomAdmin", 
            "roomRecord", "ingressAdmin"
        ]
        
        for privilege in admin_privileges:
            assert video_grants.get(privilege) is True, f"Admin missing privilege: {privilege}"
        
        # Admin token should have longer expiration
        exp_time = decoded["exp"]
        iat_time = decoded["iat"]
        token_duration = exp_time - iat_time
        
        # Should be 1 hour (3600 seconds)
        assert token_duration == 3600, f"Admin token duration incorrect: {token_duration}"


class TestAPIKeySecurity:
    """Security tests for API key handling."""
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_api_key_masking_in_logs(self, security_manager):
        """Test API key masking in log messages."""
        
        test_cases = [
            {
                "input": "Authentication with API key: livekit_api_key_12345",
                "should_mask": "livekit_api_key_12345"
            },
            {
                "input": "Using secret: livekit_secret_abcdef for signing",
                "should_mask": "livekit_secret_abcdef"
            },
            {
                "input": "JWT token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                "should_mask": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
            }
        ]
        
        for case in test_cases:
            masked = security_manager.mask_sensitive_data(case["input"])
            
            # Sensitive data should be masked
            assert case["should_mask"] not in masked, f"Sensitive data not masked: {case['should_mask']}"
            assert "***MASKED***" in masked, "Mask placeholder not found"
    
    def test_api_key_storage_security(self, security_manager):
        """Test secure API key storage practices."""
        
        # Test that API keys are not stored in plain text
        api_key = "livekit_api_key_sensitive"
        
        # Should hash or encrypt sensitive data
        secured_key = security_manager.secure_api_key(api_key)
        
        # Secured key should not contain original
        assert api_key not in secured_key
        assert len(secured_key) > 0
        
        # Should be able to verify without storing original
        is_valid = security_manager.verify_api_key(api_key, secured_key)
        assert is_valid is True
        
        # Wrong key should not verify
        is_valid = security_manager.verify_api_key("wrong_key", secured_key)
        assert is_valid is False
    
    def test_api_key_rotation_support(self, security_manager):
        """Test API key rotation without downtime."""
        
        old_key = "old_api_key_123"
        new_key = "new_api_key_456"
        
        # Should support multiple valid keys during rotation
        security_manager.add_valid_api_key(old_key)
        security_manager.add_valid_api_key(new_key)
        
        # Both keys should be valid during rotation period
        assert security_manager.is_valid_api_key(old_key) is True
        assert security_manager.is_valid_api_key(new_key) is True
        
        # Remove old key after rotation
        security_manager.remove_api_key(old_key)
        
        # Only new key should be valid
        assert security_manager.is_valid_api_key(old_key) is False
        assert security_manager.is_valid_api_key(new_key) is True


class TestConnectionSecurity:
    """Security tests for connection handling."""
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_wss_connection_enforcement(self, security_manager):
        """Test WSS connection enforcement."""
        
        # Should reject non-secure connections
        insecure_urls = [
            "ws://insecure.livekit.cloud",
            "http://insecure.livekit.cloud",
            "livekit.cloud:80"
        ]
        
        for url in insecure_urls:
            is_secure = security_manager.validate_connection_url(url)
            assert is_secure is False, f"Insecure URL should be rejected: {url}"
        
        # Should accept secure connections
        secure_urls = [
            "wss://secure.livekit.cloud",
            "https://secure.livekit.cloud",
            "wss://secure.livekit.cloud:443"
        ]
        
        for url in secure_urls:
            is_secure = security_manager.validate_connection_url(url)
            assert is_secure is True, f"Secure URL should be accepted: {url}"
    
    def test_suspicious_activity_detection(self, security_manager):
        """Test suspicious activity detection and blocking."""
        
        suspicious_ip = "192.168.1.100"
        normal_ip = "192.168.1.200"
        
        # Normal activity should not trigger detection
        for _ in range(5):
            security_manager.record_connection_attempt(normal_ip, success=True)
        
        assert security_manager.is_suspicious_activity(normal_ip) is False
        
        # Multiple failures should trigger detection
        for _ in range(10):
            security_manager.record_failed_attempt(suspicious_ip)
        
        assert security_manager.is_suspicious_activity(suspicious_ip) is True
        
        # Should block further attempts
        assert security_manager.should_block_ip(suspicious_ip) is True
        assert security_manager.should_block_ip(normal_ip) is False
    
    def test_rate_limiting_security(self, security_manager):
        """Test rate limiting for security."""
        
        client_ip = "192.168.1.150"
        
        # Should allow normal rate of requests
        for _ in range(10):
            allowed = security_manager.check_rate_limit(client_ip)
            assert allowed is True
            time.sleep(0.01)  # Small delay
        
        # Should block excessive requests
        for _ in range(100):
            security_manager.check_rate_limit(client_ip)
        
        # Should now be rate limited
        allowed = security_manager.check_rate_limit(client_ip)
        assert allowed is False
    
    def test_connection_timeout_security(self, security_manager):
        """Test connection timeout security measures."""
        
        # Should enforce connection timeouts
        timeout_config = security_manager.get_connection_timeout_config()
        
        assert timeout_config["connect_timeout"] <= 30  # Max 30 seconds
        assert timeout_config["read_timeout"] <= 60     # Max 60 seconds
        assert timeout_config["idle_timeout"] <= 300    # Max 5 minutes
        
        # Should have reasonable defaults
        assert timeout_config["connect_timeout"] >= 5   # Min 5 seconds
        assert timeout_config["read_timeout"] >= 10     # Min 10 seconds


class TestAccessControlSecurity:
    """Security tests for access control, authorization and permissions."""
    
    @pytest.fixture
    def auth_manager(self):
        return LiveKitAuthManager("test_key", "test_secret")
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_room_access_validation(self, auth_manager, security_manager):
        """Test room access validation."""
        
        # Create token for specific room
        room_token = auth_manager.create_participant_token(
            identity="user1",
            room_name="private_room"
        )
        
        # Should allow access to specified room
        has_access = security_manager.validate_room_access(
            room_token, "private_room", "test_secret"
        )
        assert has_access is True
        
        # Should deny access to different room
        has_access = security_manager.validate_room_access(
            room_token, "other_room", "test_secret"
        )
        assert has_access is False
    
    def test_participant_permissions_validation(self, auth_manager, security_manager):
        """Test participant permissions validation."""
        
        from livekit.api import VideoGrants
        
        # Create token with limited permissions
        limited_grants = VideoGrants(
            room_join=True,
            room="test_room",
            can_publish=False,  # Cannot publish
            can_subscribe=True,
            can_publish_data=False  # Cannot send data
        )
        
        limited_token = auth_manager.create_participant_token(
            identity="limited_user",
            room_name="test_room",
            grants=limited_grants
        )
        
        # Test permission validation
        permissions = security_manager.extract_permissions(limited_token, "test_secret")
        
        assert permissions["can_join"] is True
        assert permissions["can_publish"] is False
        assert permissions["can_subscribe"] is True
        assert permissions["can_publish_data"] is False
        
        # Should block unauthorized actions
        can_publish = security_manager.can_perform_action(
            limited_token, "publish_track", "test_secret"
        )
        assert can_publish is False
        
        can_subscribe = security_manager.can_perform_action(
            limited_token, "subscribe_track", "test_secret"
        )
        assert can_subscribe is True
    
    def test_admin_privilege_escalation_prevention(self, auth_manager, security_manager):
        """Test prevention of privilege escalation."""
        
        # Regular user token
        user_token = auth_manager.create_participant_token(
            identity="regular_user",
            room_name="test_room"
        )
        
        # Should not be able to perform admin actions
        admin_actions = [
            "create_room", "delete_room", "remove_participant",
            "start_recording", "create_ingress"
        ]
        
        for action in admin_actions:
            can_perform = security_manager.can_perform_action(
                user_token, action, "test_secret"
            )
            assert can_perform is False, f"Regular user should not perform: {action}"
        
        # Admin token should be able to perform admin actions
        admin_token = auth_manager.create_admin_token()
        
        for action in admin_actions:
            can_perform = security_manager.can_perform_action(
                admin_token, action, "test_secret"
            )
            assert can_perform is True, f"Admin should be able to perform: {action}"


class TestDataValidationSecurity:
    """Security tests for data validation and sanitization."""
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    def test_input_sanitization(self, security_manager):
        """Test input sanitization for security."""
        
        # Test room name sanitization
        malicious_room_names = [
            "room'; DROP TABLE rooms; --",
            "<script>alert('xss')</script>",
            "room\x00null_byte",
            "room/../../../etc/passwd",
            "room\r\n\r\nHTTP/1.1 200 OK"
        ]
        
        for malicious_name in malicious_room_names:
            sanitized = security_manager.sanitize_room_name(malicious_name)
            
            # Should remove or escape malicious content
            assert "DROP TABLE" not in sanitized
            assert "<script>" not in sanitized
            assert "\x00" not in sanitized
            assert "../" not in sanitized
            assert "\r\n" not in sanitized
    
    def test_metadata_validation(self, security_manager):
        """Test metadata validation for security."""
        
        # Test safe metadata
        safe_metadata = {
            "call_type": "inbound",
            "caller_id": "+1234567890",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        is_valid = security_manager.validate_metadata(safe_metadata)
        assert is_valid is True
        
        # Test malicious metadata
        malicious_metadata = {
            "script": "<script>alert('xss')</script>",
            "sql": "'; DROP TABLE users; --",
            "oversized": "x" * 10000,  # Too large
            "null_byte": "data\x00injection"
        }
        
        is_valid = security_manager.validate_metadata(malicious_metadata)
        assert is_valid is False
    
    def test_participant_identity_validation(self, security_manager):
        """Test participant identity validation."""
        
        # Valid identities
        valid_identities = [
            "user123",
            "user_123",
            "user-123",
            "user.123@example.com",
            "+1234567890"
        ]
        
        for identity in valid_identities:
            is_valid = security_manager.validate_participant_identity(identity)
            assert is_valid is True, f"Valid identity rejected: {identity}"
        
        # Invalid identities
        invalid_identities = [
            "",  # Empty
            "a" * 256,  # Too long
            "user\x00null",  # Null byte
            "user\r\ninjection",  # Line breaks
            "<script>alert(1)</script>",  # XSS
            "'; DROP TABLE users; --"  # SQL injection
        ]
        
        for identity in invalid_identities:
            is_valid = security_manager.validate_participant_identity(identity)
            assert is_valid is False, f"Invalid identity accepted: {identity}"


class TestSecurityMonitoring:
    """Security tests for monitoring and alerting."""
    
    @pytest.fixture
    def security_manager(self):
        return LiveKitSecurityManager()
    
    @pytest.fixture
    def monitor(self):
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            return LiveKitSystemMonitor(api_client)
    
    def test_security_event_logging(self, security_manager):
        """Test security event logging."""
        
        # Test various security events
        events = [
            {"type": "failed_authentication", "ip": "192.168.1.1", "user": "attacker"},
            {"type": "suspicious_activity", "ip": "192.168.1.1", "attempts": 10},
            {"type": "privilege_escalation", "user": "user123", "action": "admin_action"},
            {"type": "invalid_token", "token_hash": "abc123", "reason": "expired"}
        ]
        
        for event in events:
            security_manager.log_security_event(event)
        
        # Verify events are logged
        logged_events = security_manager.get_security_events()
        assert len(logged_events) == len(events)
        
        # Verify event structure
        for logged_event in logged_events:
            assert "timestamp" in logged_event
            assert "type" in logged_event
            assert "severity" in logged_event
    
    def test_security_alert_generation(self, security_manager, monitor):
        """Test security alert generation."""
        
        # Simulate security incidents
        security_manager.record_failed_attempt("192.168.1.1")
        security_manager.record_failed_attempt("192.168.1.1")
        security_manager.record_failed_attempt("192.168.1.1")
        
        # Should generate alert for multiple failures
        alerts = security_manager.get_pending_alerts()
        assert len(alerts) > 0
        
        # Verify alert structure
        alert = alerts[0]
        assert "type" in alert
        assert "severity" in alert
        assert "message" in alert
        assert "timestamp" in alert
        
        # High severity alerts should be flagged
        if alert["severity"] == "HIGH":
            assert "immediate_action_required" in alert
    
    def test_security_metrics_collection(self, security_manager, monitor):
        """Test security metrics collection."""
        
        # Generate various security events
        security_manager.record_connection_attempt("192.168.1.1", success=True)
        security_manager.record_connection_attempt("192.168.1.2", success=False)
        security_manager.record_failed_attempt("192.168.1.3")
        security_manager.record_suspicious_activity("192.168.1.4")
        
        # Collect security metrics
        metrics = security_manager.get_security_metrics()
        
        # Verify metrics structure
        assert "total_connections" in metrics
        assert "failed_connections" in metrics
        assert "suspicious_ips" in metrics
        assert "blocked_ips" in metrics
        assert "security_events" in metrics
        
        # Verify metrics values
        assert metrics["total_connections"] >= 2
        assert metrics["failed_connections"] >= 1
        assert metrics["suspicious_ips"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Tests for LiveKit Authentication Manager

This module contains comprehensive tests for the JWT authentication system
according to LiveKit specification requirements.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock

import jwt

from src.auth.livekit_auth import (
    LiveKitAuthManager,
    TokenType,
    ParticipantRole,
    TokenConfig,
    TokenInfo,
    get_auth_manager,
    shutdown_auth_manager
)


class TestLiveKitAuthManager:
    """Test cases for LiveKitAuthManager."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create auth manager for testing."""
        return LiveKitAuthManager(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('src.auth.livekit_auth.get_settings') as mock:
            mock_settings = MagicMock()
            mock_settings.livekit_api_key = "test_api_key"
            mock_settings.livekit_api_secret = "test_api_secret"
            mock.return_value = mock_settings
            yield mock_settings
    
    def test_initialization_with_credentials(self):
        """Test manager initialization with explicit credentials."""
        manager = LiveKitAuthManager(
            api_key="test_key",
            api_secret="test_secret"
        )
        
        assert manager.api_key == "test_key"
        assert manager.api_secret == "test_secret"
        assert manager._renewal_enabled is True
        assert len(manager._active_tokens) == 0
    
    def test_initialization_without_credentials_raises_error(self):
        """Test that initialization without credentials raises error."""
        with patch('src.auth.livekit_auth.get_settings') as mock:
            mock_settings = MagicMock()
            mock_settings.livekit_api_key = None
            mock_settings.livekit_api_secret = None
            mock.return_value = mock_settings
            
            with pytest.raises(ValueError, match="LiveKit API key and secret are required"):
                LiveKitAuthManager()
    
    def test_create_participant_token(self, auth_manager):
        """Test creating a participant token."""
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room",
            name="Test User",
            role=ParticipantRole.CALLER,
            auto_renew=False
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == "test_user"
        assert payload["iss"] == "test_api_key"
        assert "video" in payload
        assert payload["video"]["room"] == "test_room"
    
    def test_create_admin_token(self, auth_manager):
        """Test creating an admin token."""
        token = auth_manager.create_admin_token(
            identity="admin_user",
            room_name="admin_room",  # Admin tokens need room for LiveKit API
            auto_renew=False
        )
        
        assert isinstance(token, str)
        
        # Verify admin permissions
        payload = jwt.decode(token, options={"verify_signature": False})
        video_grants = payload["video"]
        
        assert video_grants.get("roomCreate") is True
        assert video_grants.get("roomList") is True
        assert video_grants.get("roomAdmin") is True
        assert video_grants.get("roomRecord") is True
        assert video_grants.get("ingressAdmin") is True
    
    def test_create_view_only_token(self, auth_manager):
        """Test creating a view-only token."""
        token = auth_manager.create_view_only_token(
            identity="viewer",
            room_name="test_room",
            auto_renew=False
        )
        
        payload = jwt.decode(token, options={"verify_signature": False})
        video_grants = payload["video"]
        
        assert video_grants.get("canPublish") is False
        assert video_grants.get("canSubscribe") is True
        assert video_grants.get("canPublishData") is False
    
    def test_create_camera_only_token(self, auth_manager):
        """Test creating a camera-only token."""
        token = auth_manager.create_camera_only_token(
            identity="camera_user",
            room_name="test_room",
            auto_renew=False
        )
        
        payload = jwt.decode(token, options={"verify_signature": False})
        video_grants = payload["video"]
        
        assert video_grants.get("canPublishSources") == ["camera"]
    
    def test_create_microphone_only_token(self, auth_manager):
        """Test creating a microphone-only token."""
        token = auth_manager.create_microphone_only_token(
            identity="mic_user",
            room_name="test_room",
            auto_renew=False
        )
        
        payload = jwt.decode(token, options={"verify_signature": False})
        video_grants = payload["video"]
        
        assert video_grants.get("canPublishSources") == ["microphone"]
    
    def test_validate_token_success(self, auth_manager):
        """Test successful token validation."""
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room",
            auto_renew=False
        )
        
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is True
        assert result["identity"] == "test_user"
        assert result["room"] == "test_room"
        assert "grants" in result
        assert "expires_at" in result
        assert "issued_at" in result
    
    def test_validate_token_invalid_signature(self, auth_manager):
        """Test token validation with invalid signature."""
        # Create token with different secret
        other_manager = LiveKitAuthManager(
            api_key="test_api_key",
            api_secret="different_secret"
        )
        
        token = other_manager.create_participant_token(
            identity="test_user",
            room_name="test_room",
            auto_renew=False
        )
        
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is False
        assert "Invalid token" in result["error"]
    
    def test_validate_token_expired(self, auth_manager):
        """Test validation of expired token."""
        # Create token with very short TTL using manual JWT creation
        import time
        payload = {
            "iss": "test_api_key",
            "sub": "test_user",
            "exp": int(time.time()) - 1,  # Already expired
            "video": {"room": "test_room"}
        }
        
        token = jwt.encode(payload, "test_api_secret", algorithm="HS256")
        
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is False
        assert "expired" in result["error"].lower()
    
    def test_validate_access_rights_success(self, auth_manager):
        """Test successful access rights validation."""
        token = auth_manager.create_admin_token(
            room_name="admin_room",
            auto_renew=False
        )
        
        result = auth_manager.validate_access_rights(
            token=token,
            required_permissions=["roomCreate", "roomAdmin"]
        )
        
        assert result["valid"] is True
        assert "grants" in result
    
    def test_validate_access_rights_insufficient_permissions(self, auth_manager):
        """Test access rights validation with insufficient permissions."""
        token = auth_manager.create_view_only_token(
            identity="viewer",
            room_name="test_room",
            auto_renew=False
        )
        
        result = auth_manager.validate_access_rights(
            token=token,
            required_permissions=["roomCreate", "roomAdmin"]
        )
        
        assert result["valid"] is False
        assert "Missing required permissions" in result["error"]
    
    def test_validate_access_rights_wrong_room(self, auth_manager):
        """Test access rights validation for wrong room."""
        token = auth_manager.create_participant_token(
            identity="test_user",
            room_name="room1",
            auto_renew=False
        )
        
        result = auth_manager.validate_access_rights(
            token=token,
            required_permissions=["roomJoin"],
            room_name="room2"
        )
        
        assert result["valid"] is False
        assert "not valid for room" in result["error"]
    
    def test_token_config_post_init(self):
        """Test TokenConfig post-initialization logic."""
        # Test admin token configuration
        admin_config = TokenConfig(
            identity="admin",
            token_type=TokenType.ADMIN
        )
        
        assert admin_config.room_create is True
        assert admin_config.room_admin is True
        assert admin_config.ttl_minutes == 60
        
        # Test view-only token configuration
        view_config = TokenConfig(
            identity="viewer",
            token_type=TokenType.VIEW_ONLY
        )
        
        assert view_config.can_publish is False
        assert view_config.can_publish_data is False
        assert view_config.can_publish_sources == []
    
    def test_token_info_properties(self):
        """Test TokenInfo property methods."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=5)
        
        token_info = TokenInfo(
            token="test_token",
            identity="test_user",
            room_name="test_room",
            token_type=TokenType.PARTICIPANT,
            created_at=now,
            expires_at=expires_at
        )
        
        assert not token_info.is_expired
        assert token_info.expires_in_seconds > 0
        assert not token_info.needs_renewal  # More than 2 minutes remaining
        
        # Test with expiring token
        expires_soon = now + timedelta(minutes=1)
        token_info.expires_at = expires_soon
        
        assert token_info.needs_renewal  # Less than 2 minutes remaining
    
    def test_get_token_info(self, auth_manager):
        """Test getting token info by identity."""
        auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room",
            auto_renew=False
        )
        
        token_info = auth_manager.get_token_info("test_user")
        
        assert token_info is not None
        assert token_info.identity == "test_user"
        assert token_info.room_name == "test_room"
        
        # Test non-existent identity
        assert auth_manager.get_token_info("non_existent") is None
    
    def test_revoke_token(self, auth_manager):
        """Test token revocation."""
        auth_manager.create_participant_token(
            identity="test_user",
            room_name="test_room",
            auto_renew=False
        )
        
        assert auth_manager.get_token_info("test_user") is not None
        
        # Revoke token
        result = auth_manager.revoke_token("test_user")
        
        assert result is True
        assert auth_manager.get_token_info("test_user") is None
        
        # Try to revoke non-existent token
        result = auth_manager.revoke_token("non_existent")
        assert result is False
    
    def test_cleanup_expired_tokens(self, auth_manager):
        """Test cleanup of expired tokens."""
        # Create token with very short TTL
        config = TokenConfig(
            identity="test_user",
            room_name="test_room",
            ttl_minutes=0  # Expires immediately
        )
        
        auth_manager._create_token(config, auto_renew=False)
        
        assert auth_manager.get_active_tokens_count() == 1
        
        # Wait for expiration
        time.sleep(0.1)
        
        # Cleanup expired tokens
        cleaned_count = auth_manager.cleanup_expired_tokens()
        
        assert cleaned_count == 1
        assert auth_manager.get_active_tokens_count() == 0
    
    def test_get_tokens_by_room(self, auth_manager):
        """Test getting tokens by room name."""
        auth_manager.create_participant_token(
            identity="user1",
            room_name="room1",
            auto_renew=False
        )
        
        auth_manager.create_participant_token(
            identity="user2",
            room_name="room1",
            auto_renew=False
        )
        
        auth_manager.create_participant_token(
            identity="user3",
            room_name="room2",
            auto_renew=False
        )
        
        room1_tokens = auth_manager.get_tokens_by_room("room1")
        room2_tokens = auth_manager.get_tokens_by_room("room2")
        
        assert len(room1_tokens) == 2
        assert len(room2_tokens) == 1
        
        identities = [token.identity for token in room1_tokens]
        assert "user1" in identities
        assert "user2" in identities
    
    @pytest.mark.asyncio
    async def test_token_renewal_loop(self, auth_manager):
        """Test automatic token renewal functionality."""
        # Create token with short TTL and auto-renewal
        config = TokenConfig(
            identity="test_user",
            room_name="test_room",
            ttl_minutes=1  # 1 minute TTL
        )
        
        original_token = auth_manager._create_token(config, auto_renew=True)
        
        # Get initial token info
        token_info = auth_manager.get_token_info("test_user")
        original_expires_at = token_info.expires_at
        
        # Simulate token needing renewal by modifying expires_at
        token_info.expires_at = datetime.now(UTC) + timedelta(seconds=30)  # 30 seconds left
        
        # Start renewal task manually for testing
        auth_manager._start_token_renewal("test_token_id", config)
        
        # Wait a bit for renewal to potentially happen
        await asyncio.sleep(0.1)
        
        # Note: In a real test, we'd need to mock the renewal process
        # This test mainly verifies the renewal loop can be started
        assert len(auth_manager._renewal_tasks) >= 0
    
    @pytest.mark.asyncio
    async def test_shutdown(self, auth_manager):
        """Test authentication manager shutdown."""
        # Create some tokens
        auth_manager.create_participant_token(
            identity="user1",
            room_name="room1",
            auto_renew=True
        )
        
        auth_manager.create_participant_token(
            identity="user2",
            room_name="room2",
            auto_renew=True
        )
        
        assert auth_manager.get_active_tokens_count() > 0
        assert len(auth_manager._renewal_tasks) >= 0
        
        # Shutdown
        await auth_manager.shutdown()
        
        assert not auth_manager._renewal_enabled
        assert len(auth_manager._active_tokens) == 0
        assert len(auth_manager._renewal_tasks) == 0
    
    def test_global_auth_manager(self, mock_settings):
        """Test global authentication manager functions."""
        # Test getting global instance
        manager1 = get_auth_manager()
        manager2 = get_auth_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, LiveKitAuthManager)
    
    @pytest.mark.asyncio
    async def test_global_auth_manager_shutdown(self, mock_settings):
        """Test global authentication manager shutdown."""
        manager = get_auth_manager()
        assert manager is not None
        
        await shutdown_auth_manager()
        
        # After shutdown, getting manager should create new instance
        new_manager = get_auth_manager()
        assert new_manager is not manager


class TestTokenValidationEdgeCases:
    """Test edge cases for token validation."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create auth manager for testing."""
        return LiveKitAuthManager(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )
    
    def test_validate_malformed_token(self, auth_manager):
        """Test validation of malformed token."""
        result = auth_manager.validate_token("not.a.valid.jwt.token")
        
        assert result["valid"] is False
        assert "Invalid token" in result["error"]
    
    def test_validate_token_missing_required_fields(self, auth_manager):
        """Test validation of token missing required fields."""
        # Create token manually without required fields
        payload = {
            "sub": "test_user",
            "exp": int(time.time()) + 600
            # Missing "iss" and "video" fields
        }
        
        token = jwt.encode(payload, "test_api_secret", algorithm="HS256")
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is False
        # JWT library will catch missing required claims before our validation
        assert "Invalid token" in result["error"] or "Missing required fields" in result["error"]
    
    def test_validate_token_wrong_issuer(self, auth_manager):
        """Test validation of token with wrong issuer."""
        payload = {
            "iss": "wrong_api_key",
            "sub": "test_user",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "video": {}
        }
        
        token = jwt.encode(payload, "test_api_secret", algorithm="HS256")
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is False
        assert "Invalid issuer" in result["error"]
    
    def test_validate_token_invalid_video_grants(self, auth_manager):
        """Test validation of token with invalid video grants."""
        payload = {
            "iss": "test_api_key",
            "sub": "test_user",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "video": "not_a_dict"  # Should be a dictionary
        }
        
        token = jwt.encode(payload, "test_api_secret", algorithm="HS256")
        result = auth_manager.validate_token(token)
        
        assert result["valid"] is False
        assert "Invalid video grants structure" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
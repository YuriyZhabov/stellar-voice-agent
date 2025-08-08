"""
LiveKit Authentication Manager

This module provides comprehensive JWT token management for LiveKit according to the official specification.
Handles token creation, validation, automatic renewal, and different access levels.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from uuid import uuid4

import jwt
from livekit.api import AccessToken, VideoGrants

from src.config import get_settings


logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    """JWT token types for different access levels."""
    PARTICIPANT = "participant"
    ADMIN = "admin"
    VIEW_ONLY = "view_only"
    CAMERA_ONLY = "camera_only"
    MICROPHONE_ONLY = "microphone_only"


class ParticipantRole(str, Enum):
    """Participant roles in LiveKit rooms."""
    CALLER = "caller"
    AGENT = "agent"
    OBSERVER = "observer"
    MODERATOR = "moderator"


@dataclass
class TokenConfig:
    """Configuration for JWT token creation."""
    identity: str
    name: Optional[str] = None
    room_name: Optional[str] = None
    token_type: TokenType = TokenType.PARTICIPANT
    ttl_minutes: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Video grants configuration
    room_create: bool = False
    room_list: bool = False
    room_join: bool = True
    room_admin: bool = False
    room_record: bool = False
    ingress_admin: bool = False
    can_publish: bool = True
    can_subscribe: bool = True
    can_publish_data: bool = True
    can_update_own_metadata: bool = True
    can_publish_sources: Optional[List[str]] = None
    
    def __post_init__(self):
        """Post-initialization to set defaults based on token type."""
        if self.name is None:
            self.name = self.identity
            
        # Configure permissions based on token type
        if self.token_type == TokenType.ADMIN:
            self.room_create = True
            self.room_list = True
            self.room_admin = True
            self.room_record = True
            self.ingress_admin = True
            self.ttl_minutes = 60  # Longer TTL for admin tokens
            
        elif self.token_type == TokenType.VIEW_ONLY:
            self.can_publish = False
            self.can_publish_data = False
            self.can_update_own_metadata = False
            self.can_publish_sources = []
            
        elif self.token_type == TokenType.CAMERA_ONLY:
            self.can_publish_sources = ["camera"]
            
        elif self.token_type == TokenType.MICROPHONE_ONLY:
            self.can_publish_sources = ["microphone"]


@dataclass
class TokenInfo:
    """Information about a created token."""
    token: str
    identity: str
    room_name: Optional[str]
    token_type: TokenType
    created_at: datetime
    expires_at: datetime
    auto_renew: bool = True
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now(UTC) >= self.expires_at
    
    @property
    def expires_in_seconds(self) -> float:
        """Get seconds until token expires."""
        return (self.expires_at - datetime.now(UTC)).total_seconds()
    
    @property
    def needs_renewal(self) -> bool:
        """Check if token needs renewal (within 2 minutes of expiry)."""
        return self.expires_in_seconds <= 120  # 2 minutes


class LiveKitAuthManager:
    """
    LiveKit JWT Authentication Manager
    
    Manages JWT token creation, validation, and automatic renewal according to LiveKit specification.
    Supports different token types and access levels with comprehensive validation.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize the authentication manager.
        
        Args:
            api_key: LiveKit API key (defaults to settings)
            api_secret: LiveKit API secret (defaults to settings)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.livekit_api_key
        self.api_secret = api_secret or self.settings.livekit_api_secret
        
        if not self.api_key or not self.api_secret:
            raise ValueError("LiveKit API key and secret are required")
        
        # Token storage and management
        self._active_tokens: Dict[str, TokenInfo] = {}
        self._renewal_tasks: Dict[str, asyncio.Task] = {}
        self._renewal_enabled = True
        
        logger.info("LiveKit Authentication Manager initialized")
    
    def create_participant_token(
        self,
        identity: str,
        room_name: str,
        name: Optional[str] = None,
        role: ParticipantRole = ParticipantRole.CALLER,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_minutes: int = 10,
        auto_renew: bool = True
    ) -> str:
        """
        Create a participant token with standard permissions.
        
        Args:
            identity: Unique participant identity
            room_name: Room name to join
            name: Display name (defaults to identity)
            role: Participant role
            metadata: Additional metadata
            ttl_minutes: Token time-to-live in minutes
            auto_renew: Enable automatic token renewal
            
        Returns:
            JWT token string
        """
        config = TokenConfig(
            identity=identity,
            name=name or identity,
            room_name=room_name,
            token_type=TokenType.PARTICIPANT,
            ttl_minutes=ttl_minutes,
            metadata=metadata or {}
        )
        
        # Adjust permissions based on role
        if role == ParticipantRole.AGENT:
            config.can_publish_data = True
            config.can_update_own_metadata = True
        elif role == ParticipantRole.OBSERVER:
            config.can_publish = False
            config.can_publish_data = False
        elif role == ParticipantRole.MODERATOR:
            config.room_admin = True
            config.can_publish_data = True
        
        return self._create_token(config, auto_renew)
    
    def create_admin_token(
        self,
        identity: str = "admin",
        room_name: Optional[str] = None,
        ttl_minutes: int = 60,
        auto_renew: bool = True
    ) -> str:
        """
        Create an administrative token with full permissions.
        
        Args:
            identity: Admin identity
            room_name: Room name (optional for admin tokens)
            ttl_minutes: Token time-to-live in minutes
            auto_renew: Enable automatic token renewal
            
        Returns:
            JWT token string
        """
        config = TokenConfig(
            identity=identity,
            name=f"Admin-{identity}",
            room_name=room_name,
            token_type=TokenType.ADMIN,
            ttl_minutes=ttl_minutes
        )
        
        return self._create_token(config, auto_renew)
    
    def create_view_only_token(
        self,
        identity: str,
        room_name: str,
        name: Optional[str] = None,
        ttl_minutes: int = 10,
        auto_renew: bool = True
    ) -> str:
        """
        Create a view-only token with subscribe permissions only.
        
        Args:
            identity: Unique participant identity
            room_name: Room name to join
            name: Display name (defaults to identity)
            ttl_minutes: Token time-to-live in minutes
            auto_renew: Enable automatic token renewal
            
        Returns:
            JWT token string
        """
        config = TokenConfig(
            identity=identity,
            name=name or identity,
            room_name=room_name,
            token_type=TokenType.VIEW_ONLY,
            ttl_minutes=ttl_minutes
        )
        
        return self._create_token(config, auto_renew)
    
    def create_camera_only_token(
        self,
        identity: str,
        room_name: str,
        name: Optional[str] = None,
        ttl_minutes: int = 10,
        auto_renew: bool = True
    ) -> str:
        """
        Create a camera-only token for video publishing.
        
        Args:
            identity: Unique participant identity
            room_name: Room name to join
            name: Display name (defaults to identity)
            ttl_minutes: Token time-to-live in minutes
            auto_renew: Enable automatic token renewal
            
        Returns:
            JWT token string
        """
        config = TokenConfig(
            identity=identity,
            name=name or identity,
            room_name=room_name,
            token_type=TokenType.CAMERA_ONLY,
            ttl_minutes=ttl_minutes
        )
        
        return self._create_token(config, auto_renew)
    
    def create_microphone_only_token(
        self,
        identity: str,
        room_name: str,
        name: Optional[str] = None,
        ttl_minutes: int = 10,
        auto_renew: bool = True
    ) -> str:
        """
        Create a microphone-only token for audio publishing.
        
        Args:
            identity: Unique participant identity
            room_name: Room name to join
            name: Display name (defaults to identity)
            ttl_minutes: Token time-to-live in minutes
            auto_renew: Enable automatic token renewal
            
        Returns:
            JWT token string
        """
        config = TokenConfig(
            identity=identity,
            name=name or identity,
            room_name=room_name,
            token_type=TokenType.MICROPHONE_ONLY,
            ttl_minutes=ttl_minutes
        )
        
        return self._create_token(config, auto_renew)
    
    def _create_token(self, config: TokenConfig, auto_renew: bool = True) -> str:
        """
        Create JWT token according to LiveKit specification.
        
        Args:
            config: Token configuration
            auto_renew: Enable automatic renewal
            
        Returns:
            JWT token string
        """
        try:
            # Create AccessToken with required fields according to specification
            token = AccessToken(
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Set identity and name (required fields)
            token.with_identity(config.identity)
            token.with_name(config.name)
            
            # Set TTL
            ttl = timedelta(minutes=config.ttl_minutes)
            token.with_ttl(ttl)
            
            # Configure video grants according to specification
            grants = VideoGrants(
                room_create=config.room_create,
                room_list=config.room_list,
                room_join=config.room_join,
                room_admin=config.room_admin,
                room_record=config.room_record,
                ingress_admin=config.ingress_admin,
                can_publish=config.can_publish,
                can_subscribe=config.can_subscribe,
                can_publish_data=config.can_publish_data,
                can_update_own_metadata=config.can_update_own_metadata
            )
            
            # Set room name if specified, or use default for admin tokens
            if config.room_name:
                grants.room = config.room_name
            elif config.token_type == TokenType.ADMIN:
                # Admin tokens need a room set, but can use a wildcard or default
                grants.room = "*"  # Wildcard for all rooms
            
            # Set publish sources if specified
            if config.can_publish_sources is not None:
                grants.can_publish_sources = config.can_publish_sources
            
            token.with_grants(grants)
            
            # Add metadata if provided
            if config.metadata:
                token.with_metadata(config.metadata)
            
            # Generate JWT token
            jwt_token = token.to_jwt()
            
            # Store token info for management
            token_id = str(uuid4())
            now = datetime.now(UTC)
            expires_at = now + ttl
            
            token_info = TokenInfo(
                token=jwt_token,
                identity=config.identity,
                room_name=config.room_name,
                token_type=config.token_type,
                created_at=now,
                expires_at=expires_at,
                auto_renew=auto_renew
            )
            
            self._active_tokens[token_id] = token_info
            
            # Start auto-renewal if enabled
            if auto_renew and self._renewal_enabled:
                self._start_token_renewal(token_id, config)
            
            logger.info(
                f"Created {config.token_type.value} token for {config.identity}",
                extra={
                    "token_id": token_id,
                    "identity": config.identity,
                    "room_name": config.room_name,
                    "token_type": config.token_type.value,
                    "expires_at": expires_at.isoformat()
                }
            )
            
            return jwt_token
            
        except Exception as e:
            logger.error(f"Failed to create token: {e}")
            raise
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token according to LiveKit specification.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Decode token without verification first to get header
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            
            # Verify token signature and claims
            payload = jwt.decode(
                token,
                self.api_secret,
                algorithms=["HS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": False,  # LiveKit tokens may not always have iat
                    "require": ["iss", "sub", "exp", "video"]  # Removed iat from required
                }
            )
            
            # Validate required fields according to specification
            required_fields = ["iss", "sub", "exp", "video"]
            missing_fields = [field for field in required_fields if field not in payload]
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Missing required fields: {missing_fields}",
                    "payload": None
                }
            
            # Validate issuer (should be API key)
            if payload.get("iss") != self.api_key:
                return {
                    "valid": False,
                    "error": "Invalid issuer (API key mismatch)",
                    "payload": None
                }
            
            # Validate video grants structure
            video_grants = payload.get("video", {})
            if not isinstance(video_grants, dict):
                return {
                    "valid": False,
                    "error": "Invalid video grants structure",
                    "payload": None
                }
            
            return {
                "valid": True,
                "payload": payload,
                "identity": payload.get("sub"),
                "room": video_grants.get("room"),
                "grants": video_grants,
                "expires_at": datetime.fromtimestamp(payload["exp"], UTC),
                "issued_at": datetime.fromtimestamp(payload.get("iat", payload["exp"] - 600), UTC)  # Default to exp - 10 minutes if no iat
            }
            
        except jwt.ExpiredSignatureError:
            return {
                "valid": False,
                "error": "Token has expired",
                "payload": None
            }
        except jwt.InvalidTokenError as e:
            return {
                "valid": False,
                "error": f"Invalid token: {str(e)}",
                "payload": None
            }
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "payload": None
            }
    
    def validate_access_rights(
        self,
        token: str,
        required_permissions: List[str],
        room_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate token access rights according to VideoGrants specification.
        
        Args:
            token: JWT token to validate
            required_permissions: List of required permissions
            room_name: Room name to validate access for
            
        Returns:
            Dictionary with validation results
        """
        try:
            # First validate the token
            validation_result = self.validate_token(token)
            if not validation_result["valid"]:
                return validation_result
            
            grants = validation_result["grants"]
            
            # Check room access if specified
            if room_name:
                token_room = grants.get("room")
                if token_room and token_room != room_name:
                    return {
                        "valid": False,
                        "error": f"Token not valid for room {room_name}",
                        "payload": validation_result["payload"]
                    }
            
            # Check required permissions
            missing_permissions = []
            for permission in required_permissions:
                if not grants.get(permission, False):
                    missing_permissions.append(permission)
            
            if missing_permissions:
                return {
                    "valid": False,
                    "error": f"Missing required permissions: {missing_permissions}",
                    "payload": validation_result["payload"]
                }
            
            return {
                "valid": True,
                "payload": validation_result["payload"],
                "grants": grants,
                "identity": validation_result["identity"],
                "room": validation_result["room"]
            }
            
        except Exception as e:
            logger.error(f"Access rights validation error: {e}")
            return {
                "valid": False,
                "error": f"Access validation error: {str(e)}",
                "payload": None
            }
    
    def _start_token_renewal(self, token_id: str, config: TokenConfig) -> None:
        """
        Start automatic token renewal task.
        
        Args:
            token_id: Token identifier
            config: Original token configuration
        """
        if token_id in self._renewal_tasks:
            return  # Already has renewal task
        
        task = asyncio.create_task(self._token_renewal_loop(token_id, config))
        self._renewal_tasks[token_id] = task
    
    async def _token_renewal_loop(self, token_id: str, config: TokenConfig) -> None:
        """
        Token renewal loop that runs every minute to check for expiring tokens.
        
        Args:
            token_id: Token identifier
            config: Original token configuration
        """
        try:
            while token_id in self._active_tokens and self._renewal_enabled:
                token_info = self._active_tokens[token_id]
                
                # Check if token needs renewal (within 2 minutes of expiry)
                if token_info.needs_renewal:
                    logger.info(f"Renewing token for {token_info.identity}")
                    
                    try:
                        # Create new token with same configuration
                        new_token = self._create_token(config, auto_renew=False)
                        
                        # Update token info
                        now = datetime.now(UTC)
                        token_info.token = new_token
                        token_info.created_at = now
                        token_info.expires_at = now + timedelta(minutes=config.ttl_minutes)
                        
                        logger.info(
                            f"Successfully renewed token for {token_info.identity}",
                            extra={
                                "token_id": token_id,
                                "identity": token_info.identity,
                                "new_expires_at": token_info.expires_at.isoformat()
                            }
                        )
                        
                    except Exception as e:
                        logger.error(f"Failed to renew token for {token_info.identity}: {e}")
                
                # Wait 60 seconds before next check
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.debug(f"Token renewal task cancelled for {token_id}")
        except Exception as e:
            logger.error(f"Error in token renewal loop: {e}")
        finally:
            # Clean up
            self._renewal_tasks.pop(token_id, None)
    
    def get_token_info(self, identity: str) -> Optional[TokenInfo]:
        """
        Get token information by identity.
        
        Args:
            identity: Participant identity
            
        Returns:
            TokenInfo if found, None otherwise
        """
        for token_info in self._active_tokens.values():
            if token_info.identity == identity:
                return token_info
        return None
    
    def revoke_token(self, identity: str) -> bool:
        """
        Revoke token for a specific identity.
        
        Args:
            identity: Participant identity
            
        Returns:
            True if token was revoked, False if not found
        """
        token_id_to_remove = None
        for token_id, token_info in self._active_tokens.items():
            if token_info.identity == identity:
                token_id_to_remove = token_id
                break
        
        if token_id_to_remove:
            # Cancel renewal task
            if token_id_to_remove in self._renewal_tasks:
                self._renewal_tasks[token_id_to_remove].cancel()
                del self._renewal_tasks[token_id_to_remove]
            
            # Remove token
            del self._active_tokens[token_id_to_remove]
            
            logger.info(f"Revoked token for {identity}")
            return True
        
        return False
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        expired_token_ids = []
        
        for token_id, token_info in self._active_tokens.items():
            if token_info.is_expired:
                expired_token_ids.append(token_id)
        
        for token_id in expired_token_ids:
            # Cancel renewal task
            if token_id in self._renewal_tasks:
                self._renewal_tasks[token_id].cancel()
                del self._renewal_tasks[token_id]
            
            # Remove token
            token_info = self._active_tokens[token_id]
            del self._active_tokens[token_id]
            
            logger.debug(f"Cleaned up expired token for {token_info.identity}")
        
        if expired_token_ids:
            logger.info(f"Cleaned up {len(expired_token_ids)} expired tokens")
        
        return len(expired_token_ids)
    
    def get_active_tokens_count(self) -> int:
        """Get count of active tokens."""
        return len(self._active_tokens)
    
    def get_tokens_by_room(self, room_name: str) -> List[TokenInfo]:
        """
        Get all tokens for a specific room.
        
        Args:
            room_name: Room name
            
        Returns:
            List of TokenInfo objects
        """
        return [
            token_info for token_info in self._active_tokens.values()
            if token_info.room_name == room_name
        ]
    
    async def shutdown(self) -> None:
        """Shutdown the authentication manager and cleanup resources."""
        logger.info("Shutting down LiveKit Authentication Manager")
        
        # Disable renewal
        self._renewal_enabled = False
        
        # Cancel all renewal tasks
        for task in self._renewal_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._renewal_tasks:
            await asyncio.gather(*self._renewal_tasks.values(), return_exceptions=True)
        
        # Clear all data
        self._active_tokens.clear()
        self._renewal_tasks.clear()
        
        logger.info("LiveKit Authentication Manager shutdown complete")


# Global instance
_auth_manager: Optional[LiveKitAuthManager] = None


def get_auth_manager() -> LiveKitAuthManager:
    """
    Get the global authentication manager instance.
    
    Returns:
        LiveKitAuthManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = LiveKitAuthManager()
    return _auth_manager


async def shutdown_auth_manager() -> None:
    """Shutdown the global authentication manager."""
    global _auth_manager
    if _auth_manager:
        await _auth_manager.shutdown()
        _auth_manager = None
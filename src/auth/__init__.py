"""
Authentication module for LiveKit integration.

This module provides comprehensive JWT token management for LiveKit according to the official specification.
"""

from .livekit_auth import (
    LiveKitAuthManager,
    TokenType,
    ParticipantRole,
    TokenConfig,
    TokenInfo,
    get_auth_manager,
    shutdown_auth_manager
)

__all__ = [
    "LiveKitAuthManager",
    "TokenType", 
    "ParticipantRole",
    "TokenConfig",
    "TokenInfo",
    "get_auth_manager",
    "shutdown_auth_manager"
]
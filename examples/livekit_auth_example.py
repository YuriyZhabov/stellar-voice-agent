#!/usr/bin/env python3
"""
LiveKit Authentication Manager Example

This example demonstrates how to use the LiveKit Authentication Manager
to create and manage JWT tokens for different types of participants.
"""

import asyncio
import logging
from datetime import datetime, UTC

from src.auth.livekit_auth import (
    LiveKitAuthManager,
    TokenType,
    ParticipantRole,
    get_auth_manager
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main example function."""
    logger.info("Starting LiveKit Authentication Manager Example")
    
    # Initialize authentication manager
    auth_manager = LiveKitAuthManager(
        api_key="your_livekit_api_key",
        api_secret="your_livekit_api_secret"
    )
    
    try:
        # Example 1: Create participant token for a caller
        logger.info("\n=== Example 1: Creating Participant Token ===")
        
        caller_token = auth_manager.create_participant_token(
            identity="caller_123",
            room_name="voice_call_room_456",
            name="John Doe",
            role=ParticipantRole.CALLER,
            metadata={"phone_number": "+1234567890"},
            ttl_minutes=15,
            auto_renew=True
        )
        
        logger.info(f"Created caller token: {caller_token[:50]}...")
        
        # Validate the token
        validation_result = auth_manager.validate_token(caller_token)
        if validation_result["valid"]:
            logger.info(f"Token valid for identity: {validation_result['identity']}")
            logger.info(f"Token expires at: {validation_result['expires_at']}")
        else:
            logger.error(f"Token validation failed: {validation_result['error']}")
        
        # Example 2: Create AI agent token
        logger.info("\n=== Example 2: Creating AI Agent Token ===")
        
        agent_token = auth_manager.create_participant_token(
            identity="ai_agent_voice_assistant",
            room_name="voice_call_room_456",
            name="Voice AI Assistant",
            role=ParticipantRole.AGENT,
            metadata={"type": "voice_ai", "model": "gpt-4"},
            ttl_minutes=30,
            auto_renew=True
        )
        
        logger.info(f"Created agent token: {agent_token[:50]}...")
        
        # Example 3: Create admin token for room management
        logger.info("\n=== Example 3: Creating Admin Token ===")
        
        admin_token = auth_manager.create_admin_token(
            identity="admin_user",
            room_name="voice_call_room_456",
            ttl_minutes=60,
            auto_renew=True
        )
        
        logger.info(f"Created admin token: {admin_token[:50]}...")
        
        # Validate admin permissions
        admin_validation = auth_manager.validate_access_rights(
            token=admin_token,
            required_permissions=["roomCreate", "roomAdmin", "roomRecord"]
        )
        
        if admin_validation["valid"]:
            logger.info("Admin token has required permissions")
        else:
            logger.error(f"Admin validation failed: {admin_validation['error']}")
        
        # Example 4: Create view-only token for monitoring
        logger.info("\n=== Example 4: Creating View-Only Token ===")
        
        observer_token = auth_manager.create_view_only_token(
            identity="observer_monitoring",
            room_name="voice_call_room_456",
            name="Call Monitor",
            ttl_minutes=10,
            auto_renew=True
        )
        
        logger.info(f"Created observer token: {observer_token[:50]}...")
        
        # Example 5: Create specialized tokens
        logger.info("\n=== Example 5: Creating Specialized Tokens ===")
        
        # Camera-only token
        camera_token = auth_manager.create_camera_only_token(
            identity="camera_user",
            room_name="video_call_room",
            name="Camera User",
            ttl_minutes=10
        )
        logger.info(f"Created camera-only token: {camera_token[:50]}...")
        
        # Microphone-only token
        mic_token = auth_manager.create_microphone_only_token(
            identity="mic_user",
            room_name="audio_call_room",
            name="Microphone User",
            ttl_minutes=10
        )
        logger.info(f"Created microphone-only token: {mic_token[:50]}...")
        
        # Example 6: Token management operations
        logger.info("\n=== Example 6: Token Management ===")
        
        # Get token information
        caller_info = auth_manager.get_token_info("caller_123")
        if caller_info:
            logger.info(f"Caller token expires in {caller_info.expires_in_seconds:.0f} seconds")
            logger.info(f"Token needs renewal: {caller_info.needs_renewal}")
        
        # Get all tokens for a room
        room_tokens = auth_manager.get_tokens_by_room("voice_call_room_456")
        logger.info(f"Found {len(room_tokens)} tokens for room 'voice_call_room_456'")
        
        for token_info in room_tokens:
            logger.info(f"  - {token_info.identity} ({token_info.token_type.value})")
        
        # Get active tokens count
        active_count = auth_manager.get_active_tokens_count()
        logger.info(f"Total active tokens: {active_count}")
        
        # Example 7: Access rights validation
        logger.info("\n=== Example 7: Access Rights Validation ===")
        
        # Test caller permissions
        caller_rights = auth_manager.validate_access_rights(
            token=caller_token,
            required_permissions=["roomJoin", "canPublish", "canSubscribe"],
            room_name="voice_call_room_456"
        )
        
        if caller_rights["valid"]:
            logger.info("Caller has required permissions for the room")
        else:
            logger.error(f"Caller access denied: {caller_rights['error']}")
        
        # Test observer permissions (should fail for publish)
        observer_rights = auth_manager.validate_access_rights(
            token=observer_token,
            required_permissions=["canPublish"],  # Observer shouldn't have this
            room_name="voice_call_room_456"
        )
        
        if not observer_rights["valid"]:
            logger.info(f"Observer correctly denied publish permission: {observer_rights['error']}")
        
        # Example 8: Token revocation
        logger.info("\n=== Example 8: Token Revocation ===")
        
        # Revoke a token
        revoked = auth_manager.revoke_token("observer_monitoring")
        if revoked:
            logger.info("Successfully revoked observer token")
        
        # Try to validate revoked token
        revoked_info = auth_manager.get_token_info("observer_monitoring")
        if revoked_info is None:
            logger.info("Confirmed: revoked token no longer exists")
        
        # Example 9: Cleanup expired tokens
        logger.info("\n=== Example 9: Token Cleanup ===")
        
        cleaned_count = auth_manager.cleanup_expired_tokens()
        logger.info(f"Cleaned up {cleaned_count} expired tokens")
        
        # Wait a bit to demonstrate auto-renewal (in a real scenario)
        logger.info("\n=== Example 10: Auto-Renewal Demonstration ===")
        logger.info("In a real application, tokens would auto-renew every 10 minutes")
        logger.info("The renewal process runs in the background automatically")
        
        # Show final statistics
        final_count = auth_manager.get_active_tokens_count()
        logger.info(f"Final active tokens count: {final_count}")
        
    except Exception as e:
        logger.error(f"Example failed with error: {e}")
        raise
    
    finally:
        # Shutdown the authentication manager
        logger.info("\n=== Shutting Down ===")
        await auth_manager.shutdown()
        logger.info("Authentication manager shutdown complete")


async def integration_example():
    """Example of integrating with existing LiveKit SIP integration."""
    logger.info("\n=== Integration Example ===")
    
    # Get global auth manager instance
    auth_manager = get_auth_manager()
    
    try:
        # Simulate incoming call scenario
        caller_number = "+1234567890"
        called_number = "+0987654321"
        call_id = "call_123456"
        room_name = f"voice-ai-call-{call_id}"
        
        # Create tokens for the call participants
        caller_token = auth_manager.create_participant_token(
            identity=f"caller_{caller_number.replace('+', '')}",
            room_name=room_name,
            name=f"Caller {caller_number}",
            role=ParticipantRole.CALLER,
            metadata={
                "phone_number": caller_number,
                "call_id": call_id,
                "call_type": "inbound"
            }
        )
        
        agent_token = auth_manager.create_participant_token(
            identity=f"agent_{call_id}",
            room_name=room_name,
            name="Voice AI Assistant",
            role=ParticipantRole.AGENT,
            metadata={
                "call_id": call_id,
                "agent_type": "voice_ai",
                "capabilities": ["speech_to_text", "text_to_speech", "conversation"]
            }
        )
        
        logger.info(f"Created tokens for call {call_id}")
        logger.info(f"Room: {room_name}")
        logger.info(f"Caller token: {caller_token[:50]}...")
        logger.info(f"Agent token: {agent_token[:50]}...")
        
        # In a real integration, you would:
        # 1. Pass these tokens to the LiveKit room creation
        # 2. Use them for participant authentication
        # 3. Monitor token expiration and renewal
        # 4. Clean up tokens when call ends
        
        return {
            "call_id": call_id,
            "room_name": room_name,
            "caller_token": caller_token,
            "agent_token": agent_token
        }
        
    except Exception as e:
        logger.error(f"Integration example failed: {e}")
        raise


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
    
    # Run the integration example
    # asyncio.run(integration_example())
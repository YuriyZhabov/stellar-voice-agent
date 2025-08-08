# LiveKit Authentication Manager Usage Guide

## Overview

The LiveKit Authentication Manager provides comprehensive JWT token management for LiveKit according to the official specification. It handles token creation, validation, automatic renewal, and different access levels.

## Features

- ✅ **JWT Token Creation** - Create tokens with proper LiveKit specification compliance
- ✅ **Multiple Token Types** - Support for participant, admin, view-only, camera-only, and microphone-only tokens
- ✅ **Automatic Token Renewal** - Tokens are automatically renewed every 10 minutes
- ✅ **Access Rights Validation** - Validate permissions according to VideoGrants specification
- ✅ **Token Management** - Track, revoke, and cleanup tokens
- ✅ **Different Participant Roles** - Support for caller, agent, observer, and moderator roles

## Quick Start

### Basic Usage

```python
from src.auth.livekit_auth import LiveKitAuthManager

# Initialize the manager
auth_manager = LiveKitAuthManager(
    api_key="your_livekit_api_key",
    api_secret="your_livekit_api_secret"
)

# Create a participant token
token = auth_manager.create_participant_token(
    identity="user_123",
    room_name="my_room",
    name="John Doe",
    ttl_minutes=15,
    auto_renew=True
)

# Validate the token
result = auth_manager.validate_token(token)
if result["valid"]:
    print(f"Token valid for: {result['identity']}")
else:
    print(f"Invalid token: {result['error']}")
```

### Using Global Instance

```python
from src.auth.livekit_auth import get_auth_manager

# Get global instance (recommended for most use cases)
auth_manager = get_auth_manager()

# Use as normal
token = auth_manager.create_participant_token(...)
```

## Token Types

### 1. Participant Token

Standard token for regular participants with full audio/video capabilities.

```python
token = auth_manager.create_participant_token(
    identity="caller_123",
    room_name="voice_call_room",
    name="John Doe",
    role=ParticipantRole.CALLER,
    metadata={"phone_number": "+1234567890"},
    ttl_minutes=15,
    auto_renew=True
)
```

### 2. Admin Token

Administrative token with full permissions for room management.

```python
token = auth_manager.create_admin_token(
    identity="admin_user",
    room_name="management_room",
    ttl_minutes=60,
    auto_renew=True
)
```

### 3. View-Only Token

Token for participants who can only subscribe to streams.

```python
token = auth_manager.create_view_only_token(
    identity="observer_123",
    room_name="monitored_room",
    name="Call Monitor",
    ttl_minutes=10,
    auto_renew=True
)
```

### 4. Camera-Only Token

Token that allows only camera publishing.

```python
token = auth_manager.create_camera_only_token(
    identity="camera_user",
    room_name="video_room",
    name="Camera User",
    ttl_minutes=10
)
```

### 5. Microphone-Only Token

Token that allows only microphone publishing.

```python
token = auth_manager.create_microphone_only_token(
    identity="mic_user",
    room_name="audio_room",
    name="Microphone User",
    ttl_minutes=10
)
```

## Participant Roles

Different roles have different default permissions:

- **CALLER**: Standard caller with full audio/video capabilities
- **AGENT**: AI agent with data publishing capabilities
- **OBSERVER**: View-only access, cannot publish
- **MODERATOR**: Enhanced permissions including room admin rights

```python
from src.auth.livekit_auth import ParticipantRole

# Create agent token
agent_token = auth_manager.create_participant_token(
    identity="ai_assistant",
    room_name="voice_call",
    role=ParticipantRole.AGENT,
    metadata={"type": "voice_ai"}
)
```

## Token Validation

### Basic Validation

```python
result = auth_manager.validate_token(token)

if result["valid"]:
    print(f"Identity: {result['identity']}")
    print(f"Room: {result['room']}")
    print(f"Expires: {result['expires_at']}")
    print(f"Grants: {result['grants']}")
else:
    print(f"Error: {result['error']}")
```

### Access Rights Validation

```python
result = auth_manager.validate_access_rights(
    token=token,
    required_permissions=["roomJoin", "canPublish"],
    room_name="specific_room"
)

if result["valid"]:
    print("Access granted")
else:
    print(f"Access denied: {result['error']}")
```

## Token Management

### Get Token Information

```python
token_info = auth_manager.get_token_info("user_identity")
if token_info:
    print(f"Expires in: {token_info.expires_in_seconds} seconds")
    print(f"Needs renewal: {token_info.needs_renewal}")
```

### Revoke Token

```python
success = auth_manager.revoke_token("user_identity")
if success:
    print("Token revoked successfully")
```

### Get Tokens by Room

```python
room_tokens = auth_manager.get_tokens_by_room("my_room")
for token_info in room_tokens:
    print(f"{token_info.identity} - {token_info.token_type}")
```

### Cleanup Expired Tokens

```python
cleaned_count = auth_manager.cleanup_expired_tokens()
print(f"Cleaned up {cleaned_count} expired tokens")
```

## Automatic Token Renewal

Tokens are automatically renewed when they have less than 2 minutes remaining:

```python
# Enable auto-renewal (default)
token = auth_manager.create_participant_token(
    identity="user_123",
    room_name="my_room",
    auto_renew=True  # This is the default
)

# Disable auto-renewal
token = auth_manager.create_participant_token(
    identity="user_123",
    room_room="my_room",
    auto_renew=False
)
```

## Integration with LiveKit SIP

```python
async def handle_inbound_call(caller_number, called_number, call_id):
    """Example integration with LiveKit SIP calls."""
    
    room_name = f"voice-ai-call-{call_id}"
    
    # Create caller token
    caller_token = auth_manager.create_participant_token(
        identity=f"caller_{caller_number.replace('+', '')}",
        room_name=room_name,
        name=f"Caller {caller_number}",
        role=ParticipantRole.CALLER,
        metadata={
            "phone_number": caller_number,
            "call_id": call_id
        }
    )
    
    # Create AI agent token
    agent_token = auth_manager.create_participant_token(
        identity=f"agent_{call_id}",
        room_name=room_name,
        name="Voice AI Assistant",
        role=ParticipantRole.AGENT,
        metadata={
            "call_id": call_id,
            "agent_type": "voice_ai"
        }
    )
    
    return {
        "room_name": room_name,
        "caller_token": caller_token,
        "agent_token": agent_token
    }
```

## Configuration

### Environment Variables

The authentication manager uses these environment variables from your settings:

```bash
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_api_secret_here
```

### Custom Configuration

```python
# Initialize with custom settings
auth_manager = LiveKitAuthManager(
    api_key="custom_api_key",
    api_secret="custom_api_secret"
)
```

## Error Handling

```python
try:
    token = auth_manager.create_participant_token(
        identity="user_123",
        room_name="my_room"
    )
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Token creation failed: {e}")

# Validation errors
result = auth_manager.validate_token(token)
if not result["valid"]:
    if "expired" in result["error"].lower():
        print("Token has expired")
    elif "invalid signature" in result["error"].lower():
        print("Token signature is invalid")
    else:
        print(f"Validation error: {result['error']}")
```

## Best Practices

1. **Use Global Instance**: Use `get_auth_manager()` for consistent instance management
2. **Enable Auto-Renewal**: Keep auto-renewal enabled for long-running sessions
3. **Validate Permissions**: Always validate access rights for sensitive operations
4. **Clean Up Tokens**: Regularly clean up expired tokens to prevent memory leaks
5. **Handle Errors**: Implement proper error handling for token operations
6. **Secure Storage**: Never log or expose JWT tokens in plain text
7. **Monitor Expiration**: Monitor token expiration in your application logic

## Shutdown

Always properly shutdown the authentication manager:

```python
# Shutdown individual instance
await auth_manager.shutdown()

# Shutdown global instance
from src.auth.livekit_auth import shutdown_auth_manager
await shutdown_auth_manager()
```

## Troubleshooting

### Common Issues

1. **"LiveKit API key and secret are required"**
   - Ensure environment variables are set correctly
   - Check that settings are loaded properly

2. **"Token has expired"**
   - Enable auto-renewal or create new token
   - Check system clock synchronization

3. **"Invalid issuer (API key mismatch)"**
   - Verify API key matches the one used to create token
   - Check for typos in configuration

4. **"Missing required permissions"**
   - Check token type and role permissions
   - Verify required permissions list

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('src.auth.livekit_auth').setLevel(logging.DEBUG)
```

## Examples

See `examples/livekit_auth_example.py` for comprehensive usage examples.

## Testing

Run the test suite to verify functionality:

```bash
python3 -m pytest tests/test_livekit_auth.py -v
```
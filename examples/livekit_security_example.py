#!/usr/bin/env python3
"""
LiveKit Security Configuration Example

Demonstrates how to use the security features including:
- API key protection
- WSS enforcement
- Key rotation
- Access validation
- Suspicious activity monitoring
"""

import asyncio
import os
import sys
from datetime import datetime, UTC

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.security.livekit_security import initialize_security, get_security_manager
from src.security.security_integration import (
    SecurityIntegratedAuthManager,
    SecurityIntegratedAPIClient,
    security_required,
    get_webhook_handler,
    get_health_checker
)


async def demonstrate_api_key_protection():
    """Demonstrate API key protection features."""
    print("\n=== API Key Protection Demo ===")
    
    security_manager = get_security_manager()
    
    # Test API key validation
    test_keys = [
        "sk-valid123456789012345678901234567890",  # Valid
        "short",  # Invalid - too short
        "",  # Invalid - empty
        "sk-test!@#$%^&*()",  # Invalid - special characters
    ]
    
    for key in test_keys:
        is_valid = security_manager.validate_api_key_format(key)
        masked_key = security_manager.protect_api_keys_in_logs(f"Testing key: {key}")
        print(f"Key validation: {is_valid}, Masked log: {masked_key}")
    
    # Demonstrate log masking
    sensitive_log = 'api_key="sk-secret123" password="mypass" token="jwt.token.here"'
    masked_log = security_manager.protect_api_keys_in_logs(sensitive_log)
    print(f"\nOriginal log: {sensitive_log}")
    print(f"Masked log: {masked_log}")


async def demonstrate_wss_enforcement():
    """Demonstrate WSS connection enforcement."""
    print("\n=== WSS Enforcement Demo ===")
    
    security_manager = get_security_manager()
    
    test_urls = [
        "http://livekit.example.com",
        "ws://livekit.example.com",
        "https://livekit.example.com",
        "wss://livekit.example.com"
    ]
    
    for url in test_urls:
        secure_url = security_manager.enforce_wss_connections(url)
        is_valid = security_manager.validate_connection_protocol(secure_url)
        print(f"Original: {url} -> Secure: {secure_url} (Valid: {is_valid})")


async def demonstrate_key_rotation():
    """Demonstrate API key rotation."""
    print("\n=== Key Rotation Demo ===")
    
    security_manager = get_security_manager()
    
    # Check if rotation is due
    rotation_due = security_manager.is_key_rotation_due()
    print(f"Key rotation due: {rotation_due}")
    
    # Force key rotation for demo
    try:
        new_keys = await security_manager.rotate_api_keys(force=True)
        print(f"New API key generated: {new_keys['api_key'][:10]}...")
        print(f"New API secret generated: {new_keys['api_secret'][:10]}...")
        print(f"Rotation history entries: {len(security_manager.key_rotation_history)}")
    except Exception as e:
        print(f"Key rotation failed: {e}")


async def demonstrate_access_validation():
    """Demonstrate access rights validation."""
    print("\n=== Access Validation Demo ===")
    
    security_manager = get_security_manager()
    
    # Test different permission scenarios
    test_scenarios = [
        {
            "name": "Valid participant permissions",
            "grants": {"roomJoin": True, "canPublish": True, "canSubscribe": True},
            "required": ["roomJoin", "canPublish"]
        },
        {
            "name": "Missing admin permission",
            "grants": {"roomJoin": True, "canPublish": True},
            "required": ["roomJoin", "roomAdmin"]
        },
        {
            "name": "Invalid grant name",
            "grants": {"roomJoin": True, "invalidGrant": True},
            "required": ["roomJoin"]
        }
    ]
    
    for scenario in test_scenarios:
        is_valid = security_manager.validate_access_rights(
            scenario["grants"], 
            scenario["required"]
        )
        print(f"{scenario['name']}: {'✓ Valid' if is_valid else '✗ Invalid'}")


async def demonstrate_suspicious_activity_monitoring():
    """Demonstrate suspicious activity monitoring."""
    print("\n=== Suspicious Activity Monitoring Demo ===")
    
    security_manager = get_security_manager()
    
    # Simulate failed authentication attempts
    test_ip = "192.168.1.100"
    print(f"Simulating failed auth attempts from {test_ip}")
    
    for i in range(6):  # Exceed the limit
        security_manager.record_auth_attempt(test_ip, False, f"user_{i}")
        is_blocked = security_manager.is_ip_blocked(test_ip)
        print(f"Attempt {i+1}: IP blocked = {is_blocked}")
    
    # Simulate API usage
    print(f"\nSimulating API usage from {test_ip}")
    for i in range(10):
        security_manager.record_api_usage("create_room", test_ip, 0.1)
    
    # Run security analysis
    await security_manager._analyze_security_patterns()
    
    # Show security events
    print(f"\nSecurity events recorded: {len(security_manager.security_events)}")
    for event in security_manager.security_events[-3:]:  # Show last 3 events
        print(f"- {event.event_type.value} from {event.source_ip} (severity: {event.severity})")


@security_required(["roomJoin", "canPublish"])
async def secure_room_operation(token: str, source_ip: str = "127.0.0.1"):
    """Example of a secured function using the security decorator."""
    return f"Room operation completed successfully for token: {token[:10]}..."


async def demonstrate_security_decorator():
    """Demonstrate the security decorator."""
    print("\n=== Security Decorator Demo ===")
    
    # This would normally be a real JWT token
    # For demo purposes, we'll mock the JWT validation
    import jwt
    from unittest.mock import patch
    
    mock_token_data = {
        "iss": "api_key",
        "sub": "test_user",
        "iat": 1234567890,
        "exp": 1234567890 + 600,
        "video": {"roomJoin": True, "canPublish": True, "canSubscribe": True}
    }
    
    with patch('jwt.decode', return_value=mock_token_data):
        try:
            result = await secure_room_operation("mock.jwt.token", "192.168.1.200")
            print(f"✓ Secured function result: {result}")
        except Exception as e:
            print(f"✗ Secured function failed: {e}")


async def demonstrate_webhook_security():
    """Demonstrate secure webhook handling."""
    print("\n=== Webhook Security Demo ===")
    
    webhook_handler = get_webhook_handler()
    
    # Test webhook data
    webhook_data = {
        "event": "room_started",
        "room": {
            "name": "demo_room",
            "sid": "RM_demo123"
        },
        "timestamp": datetime.now(UTC).isoformat()
    }
    
    try:
        result = await webhook_handler.handle_webhook(webhook_data, "192.168.1.300")
        print(f"✓ Webhook processed: {result}")
    except Exception as e:
        print(f"✗ Webhook processing failed: {e}")


async def demonstrate_health_check():
    """Demonstrate security health checking."""
    print("\n=== Security Health Check Demo ===")
    
    health_checker = get_health_checker()
    
    try:
        health_status = await health_checker.check_security_health()
        print(f"Overall status: {health_status['overall_status']}")
        print("Individual checks:")
        for check_name, check_result in health_status['checks'].items():
            status_icon = "✓" if check_result['status'] == 'healthy' else "⚠" if check_result['status'] == 'warning' else "✗"
            print(f"  {status_icon} {check_name}: {check_result['status']}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")


async def demonstrate_security_status():
    """Demonstrate security status reporting."""
    print("\n=== Security Status Demo ===")
    
    security_manager = get_security_manager()
    
    status = security_manager.get_security_status()
    
    print(f"Security Status Report ({status['timestamp']})")
    print("Configuration:")
    for key, value in status['configuration'].items():
        print(f"  - {key}: {value}")
    
    print("Metrics:")
    for key, value in status['metrics'].items():
        print(f"  - {key}: {value}")
    
    if status['recent_events']:
        print("Recent Events:")
        for event in status['recent_events']:
            print(f"  - {event['type']} from {event['source_ip']} ({event['severity']})")


async def main():
    """Run all security demonstrations."""
    print("LiveKit Security Configuration Demo")
    print("=" * 50)
    
    # Initialize security with custom config
    config_path = "config/security.yaml"
    if not os.path.exists(config_path):
        print(f"Warning: Security config not found at {config_path}")
        print("Using default configuration...")
    
    security_manager = initialize_security(config_path)
    print(f"Security manager initialized with config: {config_path}")
    
    # Run all demonstrations
    await demonstrate_api_key_protection()
    await demonstrate_wss_enforcement()
    await demonstrate_key_rotation()
    await demonstrate_access_validation()
    await demonstrate_suspicious_activity_monitoring()
    await demonstrate_security_decorator()
    await demonstrate_webhook_security()
    await demonstrate_health_check()
    await demonstrate_security_status()
    
    print("\n" + "=" * 50)
    print("Security demonstration completed!")
    print("\nKey Security Features Demonstrated:")
    print("✓ API key protection and masking in logs")
    print("✓ WSS connection enforcement")
    print("✓ Zero-downtime key rotation")
    print("✓ Comprehensive access rights validation")
    print("✓ Suspicious activity monitoring and alerting")
    print("✓ Security decorator for method protection")
    print("✓ Secure webhook handling")
    print("✓ Health checking and status reporting")


if __name__ == "__main__":
    asyncio.run(main())
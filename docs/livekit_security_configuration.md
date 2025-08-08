# LiveKit Security Configuration

This document describes the comprehensive security configuration system for LiveKit, implementing all security requirements from the specification.

## Overview

The LiveKit security system provides:

- **API Key Protection**: Prevents sensitive keys from appearing in logs
- **WSS Connection Enforcement**: Ensures all connections use secure protocols
- **Key Rotation Support**: Zero-downtime API key rotation
- **Access Rights Validation**: Comprehensive JWT token and permission validation
- **Suspicious Activity Monitoring**: Real-time detection and alerting

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Application       │───▶│  Security Manager    │───▶│  Security Events    │
│   Components        │    │  (Core Security)     │    │  & Monitoring       │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│  Security           │    │  Secure Logger       │    │  Health Checker     │
│  Integration        │    │  (Log Masking)       │    │  & Status           │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

## Components

### 1. LiveKitSecurityManager

The core security manager that handles all security operations.

```python
from src.security.livekit_security import get_security_manager

# Get the global security manager instance
security_manager = get_security_manager()

# Check security status
status = security_manager.get_security_status()
print(f"Security status: {status['overall_status']}")
```

### 2. SecureLogger

Automatically masks sensitive information in logs.

```python
from src.security.livekit_security import SecureLogger

logger = SecureLogger(__name__)

# This will automatically mask the API key
logger.info('Connecting with api_key="sk-secret123456789"')
# Output: Connecting with api_key="***MASKED***"
```

### 3. Security Integration

Provides security-enhanced versions of existing components.

```python
from src.security.security_integration import (
    SecurityIntegratedAuthManager,
    SecurityIntegratedAPIClient
)

# Use security-enhanced auth manager
auth_manager = SecurityIntegratedAuthManager(api_key, api_secret)

# Use security-enhanced API client (automatically enforces WSS)
client = SecurityIntegratedAPIClient("ws://livekit.example.com", api_key, api_secret)
```

## Configuration

### Security Configuration File

Create `config/security.yaml`:

```yaml
# WSS Connection Enforcement
wss_enforcement:
  enabled: true
  allowed_protocols: ["wss", "https"]
  redirect_http_to_https: true

# API Key Rotation
key_rotation:
  enabled: true
  rotation_interval_hours: 24
  overlap_period_minutes: 30
  auto_rotation: false

# Access Rights Validation
access_validation:
  strict_mode: true
  validate_all_grants: true
  log_access_attempts: true

# Suspicious Activity Monitoring
suspicious_activity:
  max_failed_attempts: 5
  lockout_duration_minutes: 15
  rate_limit_per_minute: 100
  unusual_usage_threshold: 1000

# Logging Configuration
logging:
  mask_sensitive_data: true
  log_level: "INFO"
  audit_log_retention_days: 90
```

### Environment Variables

Set these environment variables for enhanced security:

```bash
# Security webhook for alerts
export SECURITY_WEBHOOK_URL="https://your-alerting-system.com/webhook"

# Custom security config path
export LIVEKIT_SECURITY_CONFIG="config/security.yaml"
```

## Features

### 1. API Key Protection

Prevents API keys from appearing in logs and provides secure storage.

```python
# API key validation
is_valid = security_manager.validate_api_key_format("sk-test123456789")

# Secure hashing for storage
key_hash = security_manager.hash_api_key_for_storage("sk-secret123")

# Log masking
safe_log = security_manager.protect_api_keys_in_logs(
    'Using api_key="sk-secret123" for connection'
)
```

### 2. WSS Connection Enforcement

Automatically converts insecure connections to secure ones.

```python
# Automatically converts ws:// to wss://
secure_url = security_manager.enforce_wss_connections("ws://livekit.example.com")
# Result: "wss://livekit.example.com"

# Validates connection protocol
is_secure = security_manager.validate_connection_protocol("https://livekit.example.com")
# Result: True
```

### 3. Key Rotation Support

Zero-downtime API key rotation with overlap period.

```python
# Check if rotation is due
if security_manager.is_key_rotation_due():
    # Rotate keys with 30-minute overlap
    new_keys = await security_manager.rotate_api_keys()
    print(f"New API key: {new_keys['api_key']}")
    print(f"New API secret: {new_keys['api_secret']}")

# Force immediate rotation
new_keys = await security_manager.rotate_api_keys(force=True)
```

### 4. Access Rights Validation

Comprehensive JWT token and permission validation.

```python
# Validate JWT token structure
is_valid_token = security_manager.validate_jwt_token_structure(jwt_token)

# Validate access rights
token_grants = {"roomJoin": True, "canPublish": True}
required_permissions = ["roomJoin", "canPublish"]
has_access = security_manager.validate_access_rights(token_grants, required_permissions)

# Use security decorator for method protection
@security_required(["roomAdmin", "roomCreate"])
async def create_secure_room(token: str, room_name: str):
    # This method requires roomAdmin and roomCreate permissions
    pass
```

### 5. Suspicious Activity Monitoring

Real-time monitoring and alerting for security threats.

```python
# Record authentication attempts
security_manager.record_auth_attempt("192.168.1.100", success=False, user_identity="user123")

# Record API usage
security_manager.record_api_usage("create_room", "192.168.1.100", response_time=0.5)

# Check if IP is blocked
if security_manager.is_ip_blocked("192.168.1.100"):
    print("IP is blocked due to suspicious activity")

# Get security events
status = security_manager.get_security_status()
for event in status['recent_events']:
    print(f"Security event: {event['type']} from {event['source_ip']}")
```

## Security Decorators

Use decorators to protect sensitive methods:

```python
from src.security.security_integration import security_required

@security_required(["roomCreate", "roomAdmin"])
async def create_admin_room(token: str, room_config: dict):
    """This method requires both roomCreate and roomAdmin permissions."""
    # Implementation here
    pass

@security_required(["canPublish", "canSubscribe"])
async def join_room_as_participant(token: str, room_name: str):
    """This method requires participant permissions."""
    # Implementation here
    pass
```

## Webhook Security

Secure webhook handling with validation and monitoring:

```python
from src.security.security_integration import get_webhook_handler

webhook_handler = get_webhook_handler()

# Handle webhook with security validation
async def handle_livekit_webhook(request_data: dict, source_ip: str):
    try:
        result = await webhook_handler.handle_webhook(request_data, source_ip)
        return result
    except ValueError as e:
        # Security validation failed
        logger.error(f"Webhook security validation failed: {e}")
        raise
```

## Health Monitoring

Monitor security system health:

```python
from src.security.security_integration import get_health_checker

health_checker = get_health_checker()

# Perform security health check
health_status = await health_checker.check_security_health()

print(f"Overall security status: {health_status['overall_status']}")

# Check individual components
for check_name, check_result in health_status['checks'].items():
    print(f"{check_name}: {check_result['status']}")
```

## Security Events

The system generates various security events:

- **SUSPICIOUS_LOGIN**: Multiple failed login attempts from same IP
- **MULTIPLE_FAILED_AUTH**: Pattern of authentication failures
- **UNUSUAL_API_USAGE**: API usage exceeding normal thresholds
- **KEY_ROTATION**: API key rotation events
- **UNAUTHORIZED_ACCESS**: Access attempts without proper permissions
- **RATE_LIMIT_EXCEEDED**: Rate limiting violations

## Best Practices

### 1. Configuration

- Always enable WSS enforcement in production
- Set appropriate rate limits based on your usage patterns
- Configure key rotation intervals based on your security requirements
- Enable strict access validation mode

### 2. Monitoring

- Regularly review security events and metrics
- Set up alerting for high-severity security events
- Monitor blocked IPs and investigate patterns
- Track key rotation history

### 3. Integration

- Use security-integrated components instead of base components
- Apply security decorators to sensitive methods
- Validate all incoming webhooks
- Implement proper error handling for security failures

### 4. Maintenance

- Regularly update security configuration
- Review and rotate API keys according to schedule
- Clean up old security events and logs
- Test security features in staging environment

## Troubleshooting

### Common Issues

1. **WSS Connection Failures**
   - Check that WSS enforcement is properly configured
   - Verify SSL certificates are valid
   - Ensure firewall allows WSS connections

2. **Key Rotation Issues**
   - Verify overlap period is sufficient for all services to update
   - Check that key rotation is enabled in configuration
   - Monitor logs for rotation events

3. **Access Validation Failures**
   - Verify JWT token structure and required fields
   - Check that all required permissions are present
   - Ensure token hasn't expired

4. **False Positive Security Alerts**
   - Adjust rate limiting thresholds
   - Review IP whitelist/blacklist configuration
   - Fine-tune suspicious activity detection parameters

### Debugging

Enable debug logging to troubleshoot security issues:

```python
import logging
logging.getLogger('src.security').setLevel(logging.DEBUG)
```

Check security status for detailed information:

```python
status = security_manager.get_security_status()
print(json.dumps(status, indent=2))
```

## Integration Examples

See `examples/livekit_security_example.py` for comprehensive usage examples.

Run the example:

```bash
python examples/livekit_security_example.py
```

## Testing

Run security tests:

```bash
python -m pytest tests/test_livekit_security.py -v
```

The test suite covers:
- API key protection and validation
- WSS connection enforcement
- Key rotation functionality
- Access rights validation
- Suspicious activity monitoring
- Security integration components
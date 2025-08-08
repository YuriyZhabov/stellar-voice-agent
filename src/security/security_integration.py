"""
Security Integration Module

Integrates security features with existing LiveKit components including:
- Auth system integration
- API client security wrapper
- Monitoring integration
- Webhook security
"""

import asyncio
import time
from datetime import datetime, UTC
from typing import Dict, Any, Optional, List
from functools import wraps
import inspect

from .livekit_security import get_security_manager, SecurityEventType


class SecurityIntegratedAuthManager:
    """Auth manager with integrated security features."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.security_manager = get_security_manager()
        
        # Validate API keys on initialization
        if not self.security_manager.validate_api_key_format(api_key):
            raise ValueError("Invalid API key format")
    
    def create_participant_token(self, identity: str, room_name: str, **kwargs) -> str:
        """Create participant token with security validation."""
        try:
            # For demo purposes, create a mock token structure
            # In real implementation, this would use the actual LiveKit auth
            import jwt
            import time
            from datetime import datetime, timedelta, UTC
            
            payload = {
                "iss": self.api_key,
                "sub": identity,
                "iat": int(time.time()),
                "exp": int(time.time()) + 600,  # 10 minutes
                "video": {
                    "roomJoin": True,
                    "room": room_name,
                    "canPublish": kwargs.get("can_publish", True),
                    "canSubscribe": kwargs.get("can_subscribe", True),
                    "canPublishData": kwargs.get("can_publish_data", True)
                }
            }
            
            token = jwt.encode(payload, self.api_secret, algorithm="HS256")
            
            # Validate token structure
            if not self.security_manager.validate_jwt_token_structure(token):
                raise ValueError("Generated token failed security validation")
            
            # Log token creation (without exposing the token)
            self.security_manager.logger.info(
                f"Participant token created for identity: {identity}"
            )
            
            return token
            
        except Exception as e:
            self.security_manager.logger.error(f"Failed to create secure participant token: {e}")
            raise
    
    def create_admin_token(self) -> str:
        """Create admin token with security validation."""
        try:
            import jwt
            import time
            
            payload = {
                "iss": self.api_key,
                "sub": "admin",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,  # 1 hour
                "video": {
                    "roomCreate": True,
                    "roomList": True,
                    "roomAdmin": True,
                    "roomRecord": True,
                    "ingressAdmin": True
                }
            }
            
            token = jwt.encode(payload, self.api_secret, algorithm="HS256")
            
            # Validate admin token
            if not self.security_manager.validate_jwt_token_structure(token):
                raise ValueError("Generated admin token failed security validation")
            
            # Log admin token creation
            self.security_manager.logger.warning("Admin token created - high privilege access granted")
            
            return token
            
        except Exception as e:
            self.security_manager.logger.error(f"Failed to create secure admin token: {e}")
            raise


class SecurityIntegratedAPIClient:
    """API client with integrated security features."""
    
    def __init__(self, url: str, api_key: str, api_secret: str):
        # Enforce WSS connections
        security_manager = get_security_manager()
        secure_url = security_manager.enforce_wss_connections(url)
        
        if not security_manager.validate_connection_protocol(secure_url):
            raise ValueError(f"Insecure connection protocol not allowed: {url}")
        
        self.url = secure_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.security_manager = security_manager
        
        # Create security-integrated auth manager
        self.auth_manager = SecurityIntegratedAuthManager(api_key, api_secret)
    
    async def _make_secure_request(self, method_name: str, *args, **kwargs):
        """Make API request with security monitoring."""
        start_time = time.time()
        source_ip = kwargs.pop('source_ip', 'unknown')
        
        try:
            # Check if key rotation is due
            if self.security_manager.is_key_rotation_due():
                self.security_manager.logger.warning("API key rotation is due")
            
            # Simulate API request (in real implementation, this would call actual LiveKit API)
            await asyncio.sleep(0.1)  # Simulate network delay
            result = {"status": "success", "method": method_name, "args": args}
            
            # Record successful API usage
            response_time = time.time() - start_time
            self.security_manager.record_api_usage(method_name, source_ip, response_time)
            
            return result
            
        except Exception as e:
            # Record failed API usage
            response_time = time.time() - start_time
            self.security_manager.record_api_usage(f"{method_name}_failed", source_ip, response_time)
            
            # Log security-relevant errors
            self.security_manager.logger.error(
                f"API request failed: {method_name} - {str(e)}"
            )
            
            raise
    
    # API methods with security monitoring
    async def create_room(self, *args, **kwargs):
        return await self._make_secure_request('create_room', *args, **kwargs)
    
    async def list_rooms(self, *args, **kwargs):
        return await self._make_secure_request('list_rooms', *args, **kwargs)
    
    async def delete_room(self, *args, **kwargs):
        return await self._make_secure_request('delete_room', *args, **kwargs)
    
    async def list_participants(self, *args, **kwargs):
        return await self._make_secure_request('list_participants', *args, **kwargs)
    
    async def remove_participant(self, *args, **kwargs):
        return await self._make_secure_request('remove_participant', *args, **kwargs)
    
    async def mute_track(self, *args, **kwargs):
        return await self._make_secure_request('mute_track', *args, **kwargs)


def security_required(permissions: List[str]):
    """Decorator to enforce security permissions on methods."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            security_manager = get_security_manager()
            
            # Extract token from kwargs or args
            token = kwargs.get('token') or (args[1] if len(args) > 1 else None)
            source_ip = kwargs.get('source_ip', 'unknown')
            
            if not token:
                security_manager.logger.error("No token provided for secured method")
                raise ValueError("Authentication token required")
            
            try:
                # Validate token structure
                if not security_manager.validate_jwt_token_structure(token):
                    security_manager.record_auth_attempt(source_ip, False)
                    raise ValueError("Invalid token structure")
                
                # Decode token to get grants (simplified - in real implementation use proper JWT validation)
                import jwt
                decoded = jwt.decode(token, options={"verify_signature": False})
                token_grants = decoded.get('video', {})
                
                # Validate permissions
                if not security_manager.validate_access_rights(token_grants, permissions):
                    await security_manager._record_security_event(
                        SecurityEventType.UNAUTHORIZED_ACCESS,
                        source_ip,
                        decoded.get('sub'),
                        {'required_permissions': permissions, 'token_grants': list(token_grants.keys())},
                        'high'
                    )
                    raise ValueError("Insufficient permissions")
                
                # Record successful auth
                security_manager.record_auth_attempt(source_ip, True, decoded.get('sub'))
                
                # Call the original function
                return await func(*args, **kwargs)
                
            except Exception as e:
                security_manager.record_auth_attempt(source_ip, False)
                raise
        
        return wrapper
    return decorator


class SecureWebhookHandler:
    """Secure webhook handler with validation and monitoring."""
    
    def __init__(self):
        self.security_manager = get_security_manager()
    
    async def handle_webhook(self, request_data: Dict[str, Any], source_ip: str) -> Dict[str, Any]:
        """Handle webhook with security validation."""
        try:
            # Validate webhook signature (implement based on your webhook secret)
            if not self._validate_webhook_signature(request_data):
                await self.security_manager._record_security_event(
                    SecurityEventType.UNAUTHORIZED_ACCESS,
                    source_ip,
                    details={'webhook_validation_failed': True},
                    severity='high'
                )
                raise ValueError("Invalid webhook signature")
            
            # Record webhook activity
            self.security_manager.record_api_usage('webhook', source_ip, 0)
            
            # Process webhook
            event_type = request_data.get('event')
            
            if event_type == 'room_started':
                return await self._handle_room_started(request_data, source_ip)
            elif event_type == 'participant_joined':
                return await self._handle_participant_joined(request_data, source_ip)
            elif event_type == 'participant_left':
                return await self._handle_participant_left(request_data, source_ip)
            else:
                self.security_manager.logger.warning(f"Unknown webhook event type: {event_type}")
                return {'status': 'unknown_event'}
            
        except Exception as e:
            self.security_manager.logger.error(f"Webhook handling failed: {e}")
            raise
    
    def _validate_webhook_signature(self, request_data: Dict[str, Any]) -> bool:
        """Validate webhook signature."""
        # Implement webhook signature validation based on your setup
        # This is a placeholder implementation
        return True
    
    async def _handle_room_started(self, data: Dict[str, Any], source_ip: str) -> Dict[str, Any]:
        """Handle room started webhook."""
        room_name = data.get('room', {}).get('name')
        self.security_manager.logger.info(f"Room started: {room_name}")
        return {'status': 'processed'}
    
    async def _handle_participant_joined(self, data: Dict[str, Any], source_ip: str) -> Dict[str, Any]:
        """Handle participant joined webhook."""
        participant_identity = data.get('participant', {}).get('identity')
        room_name = data.get('room', {}).get('name')
        
        self.security_manager.logger.info(
            f"Participant joined: {participant_identity} in room {room_name}"
        )
        
        # Monitor for suspicious joining patterns
        self.security_manager.record_api_usage('participant_join', source_ip, 0)
        
        return {'status': 'processed'}
    
    async def _handle_participant_left(self, data: Dict[str, Any], source_ip: str) -> Dict[str, Any]:
        """Handle participant left webhook."""
        participant_identity = data.get('participant', {}).get('identity')
        room_name = data.get('room', {}).get('name')
        
        self.security_manager.logger.info(
            f"Participant left: {participant_identity} from room {room_name}"
        )
        
        return {'status': 'processed'}


class SecurityHealthChecker:
    """Health checker for security components."""
    
    def __init__(self):
        self.security_manager = get_security_manager()
    
    async def check_security_health(self) -> Dict[str, Any]:
        """Perform comprehensive security health check."""
        health_status = {
            'timestamp': datetime.now(UTC).isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        try:
            # Check WSS enforcement
            health_status['checks']['wss_enforcement'] = {
                'status': 'healthy' if self.security_manager.config['wss_enforcement']['enabled'] else 'warning',
                'enabled': self.security_manager.config['wss_enforcement']['enabled']
            }
            
            # Check key rotation status
            rotation_due = self.security_manager.is_key_rotation_due()
            health_status['checks']['key_rotation'] = {
                'status': 'warning' if rotation_due else 'healthy',
                'rotation_due': rotation_due,
                'enabled': self.security_manager.config['key_rotation']['enabled']
            }
            
            # Check for blocked IPs
            blocked_ips = len([ip for ip in self.security_manager.failed_auth_attempts 
                             if self.security_manager.is_ip_blocked(ip)])
            health_status['checks']['blocked_ips'] = {
                'status': 'warning' if blocked_ips > 0 else 'healthy',
                'count': blocked_ips
            }
            
            # Check recent security events
            recent_critical_events = [
                event for event in self.security_manager.security_events[-10:]
                if event.severity in ['high', 'critical']
            ]
            health_status['checks']['recent_security_events'] = {
                'status': 'critical' if recent_critical_events else 'healthy',
                'critical_events_count': len(recent_critical_events)
            }
            
            # Determine overall status
            statuses = [check['status'] for check in health_status['checks'].values()]
            if 'critical' in statuses:
                health_status['overall_status'] = 'critical'
            elif 'warning' in statuses:
                health_status['overall_status'] = 'warning'
            
            return health_status
            
        except Exception as e:
            self.security_manager.logger.error(f"Security health check failed: {e}")
            return {
                'timestamp': datetime.now(UTC).isoformat(),
                'overall_status': 'critical',
                'error': str(e)
            }


# Global instances
_webhook_handler: Optional[SecureWebhookHandler] = None
_health_checker: Optional[SecurityHealthChecker] = None

def get_webhook_handler() -> SecureWebhookHandler:
    """Get global webhook handler instance."""
    global _webhook_handler
    if _webhook_handler is None:
        _webhook_handler = SecureWebhookHandler()
    return _webhook_handler

def get_health_checker() -> SecurityHealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = SecurityHealthChecker()
    return _health_checker
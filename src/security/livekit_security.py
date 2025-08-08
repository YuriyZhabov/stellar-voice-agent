"""
LiveKit Security Configuration Module

Implements comprehensive security measures for LiveKit system including:
- API key protection from log leakage
- WSS connection enforcement
- Key rotation support
- Access rights validation
- Suspicious activity monitoring
"""

import os
import re
import logging
import hashlib
import time
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from pathlib import Path

# Security event types
class SecurityEventType(Enum):
    SUSPICIOUS_LOGIN = "suspicious_login"
    MULTIPLE_FAILED_AUTH = "multiple_failed_auth"
    UNUSUAL_API_USAGE = "unusual_api_usage"
    KEY_ROTATION = "key_rotation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_type: SecurityEventType
    timestamp: datetime
    source_ip: str
    user_identity: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "medium"  # low, medium, high, critical

class SecureLogger:
    """Logger that automatically masks sensitive information."""
    
    # Patterns to mask in logs
    SENSITIVE_PATTERNS = [
        (r'api_key["\s]*[:=]["\s]*([^"\s,}]+)', r'api_key="***MASKED***"'),
        (r'api_secret["\s]*[:=]["\s]*([^"\s,}]+)', r'api_secret="***MASKED***"'),
        (r'password["\s]*[:=]["\s]*([^"\s,}]+)', r'password="***MASKED***"'),
        (r'token["\s]*[:=]["\s]*([^"\s,}]+)', r'token="***MASKED***"'),
        (r'Bearer\s+([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)', r'Bearer ***MASKED_JWT***'),
        (r'Authorization:\s*Bearer\s+([^\s]+)', r'Authorization: Bearer ***MASKED***'),
    ]
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def _mask_sensitive_data(self, message: str) -> str:
        """Mask sensitive information in log messages."""
        masked_message = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            masked_message = re.sub(pattern, replacement, masked_message, flags=re.IGNORECASE)
        return masked_message
    
    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(self._mask_sensitive_data(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self.logger.info(self._mask_sensitive_data(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(self._mask_sensitive_data(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self.logger.error(self._mask_sensitive_data(message), *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        self.logger.critical(self._mask_sensitive_data(message), *args, **kwargs)

class LiveKitSecurityManager:
    """Comprehensive security manager for LiveKit system."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = SecureLogger(__name__)
        self.config_path = config_path or "config/security.yaml"
        self.security_events: List[SecurityEvent] = []
        self.failed_auth_attempts: Dict[str, List[datetime]] = {}
        self.api_usage_stats: Dict[str, Dict[str, int]] = {}
        self.active_keys: Dict[str, Dict[str, Any]] = {}
        self.key_rotation_history: List[Dict[str, Any]] = []
        
        # Load security configuration
        self._load_security_config()
        
        # Initialize monitoring
        self._init_monitoring()
    
    def _load_security_config(self):
        """Load security configuration from file."""
        try:
            if os.path.exists(self.config_path):
                import yaml
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
            else:
                # Default security configuration
                self.config = {
                    "wss_enforcement": {
                        "enabled": True,
                        "allowed_protocols": ["wss", "https"],
                        "redirect_http_to_https": True
                    },
                    "key_rotation": {
                        "enabled": True,
                        "rotation_interval_hours": 24,
                        "overlap_period_minutes": 30,
                        "auto_rotation": False
                    },
                    "access_validation": {
                        "strict_mode": True,
                        "validate_all_grants": True,
                        "log_access_attempts": True
                    },
                    "suspicious_activity": {
                        "max_failed_attempts": 5,
                        "lockout_duration_minutes": 15,
                        "rate_limit_per_minute": 100,
                        "unusual_usage_threshold": 1000
                    },
                    "logging": {
                        "mask_sensitive_data": True,
                        "log_level": "INFO",
                        "audit_log_retention_days": 90
                    }
                }
                self._save_security_config()
        except Exception as e:
            self.logger.error(f"Failed to load security config: {e}")
            raise
    
    def _save_security_config(self):
        """Save security configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            import yaml
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"Failed to save security config: {e}")
    
    def _init_monitoring(self):
        """Initialize security monitoring."""
        self.logger.info("Initializing LiveKit security monitoring")
        
        # Start background monitoring tasks only if event loop is running
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._monitor_security_events())
            asyncio.create_task(self._cleanup_old_events())
        except RuntimeError:
            # No event loop running, monitoring will be started when needed
            self.logger.info("No event loop running, monitoring tasks will start when event loop is available")
    
    async def _monitor_security_events(self):
        """Background task to monitor security events."""
        while True:
            try:
                await self._analyze_security_patterns()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Error in security monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_old_events(self):
        """Clean up old security events."""
        while True:
            try:
                retention_days = self.config["logging"]["audit_log_retention_days"]
                cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
                
                # Remove old events
                self.security_events = [
                    event for event in self.security_events 
                    if event.timestamp > cutoff_date
                ]
                
                # Clean up failed auth attempts
                for ip in list(self.failed_auth_attempts.keys()):
                    self.failed_auth_attempts[ip] = [
                        attempt for attempt in self.failed_auth_attempts[ip]
                        if attempt > cutoff_date
                    ]
                    if not self.failed_auth_attempts[ip]:
                        del self.failed_auth_attempts[ip]
                
                await asyncio.sleep(3600)  # Clean up every hour
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(3600)
    
    async def _analyze_security_patterns(self):
        """Analyze security events for patterns."""
        try:
            # Check for multiple failed auth attempts
            await self._check_failed_auth_patterns()
            
            # Check for unusual API usage
            await self._check_api_usage_patterns()
            
            # Check for suspicious activity
            await self._check_suspicious_activity()
            
        except Exception as e:
            self.logger.error(f"Error analyzing security patterns: {e}")
    
    async def _check_failed_auth_patterns(self):
        """Check for patterns in failed authentication attempts."""
        max_attempts = self.config["suspicious_activity"]["max_failed_attempts"]
        lockout_duration = self.config["suspicious_activity"]["lockout_duration_minutes"]
        
        for ip, attempts in self.failed_auth_attempts.items():
            cutoff_time = datetime.now(UTC) - timedelta(minutes=lockout_duration)
            recent_attempts = [
                attempt for attempt in attempts
                if attempt > cutoff_time
            ]
            
            if len(recent_attempts) >= max_attempts:
                await self._record_security_event(
                    SecurityEventType.MULTIPLE_FAILED_AUTH,
                    ip,
                    details={
                        "attempts_count": len(recent_attempts),
                        "time_window_minutes": lockout_duration
                    },
                    severity="high"
                )
    
    async def _check_api_usage_patterns(self):
        """Check for unusual API usage patterns."""
        threshold = self.config["suspicious_activity"]["unusual_usage_threshold"]
        
        for endpoint, stats in self.api_usage_stats.items():
            total_requests = sum(stats.values())
            if total_requests > threshold:
                await self._record_security_event(
                    SecurityEventType.UNUSUAL_API_USAGE,
                    "system",
                    details={
                        "endpoint": endpoint,
                        "request_count": total_requests,
                        "threshold": threshold
                    },
                    severity="medium"
                )
    
    async def _check_suspicious_activity(self):
        """Check for other suspicious activities."""
        # Check for rate limit violations
        rate_limit = self.config["suspicious_activity"]["rate_limit_per_minute"]
        
        for ip, stats in self.api_usage_stats.items():
            if isinstance(stats, dict) and "requests_per_minute" in stats:
                if stats["requests_per_minute"] > rate_limit:
                    await self._record_security_event(
                        SecurityEventType.RATE_LIMIT_EXCEEDED,
                        ip,
                        details={
                            "requests_per_minute": stats["requests_per_minute"],
                            "rate_limit": rate_limit
                        },
                        severity="medium"
                    )
    
    async def _record_security_event(
        self, 
        event_type: SecurityEventType, 
        source_ip: str,
        user_identity: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "medium"
    ):
        """Record a security event."""
        event = SecurityEvent(
            event_type=event_type,
            timestamp=datetime.now(UTC),
            source_ip=source_ip,
            user_identity=user_identity,
            details=details or {},
            severity=severity
        )
        
        self.security_events.append(event)
        
        # Log the event
        self.logger.warning(
            f"Security event: {event_type.value} from {source_ip} "
            f"(severity: {severity}) - {details}"
        )
        
        # Send alert for high/critical events
        if severity in ["high", "critical"]:
            await self._send_security_alert(event)
    
    async def _send_security_alert(self, event: SecurityEvent):
        """Send security alert for critical events."""
        try:
            # This would integrate with your alerting system
            alert_message = (
                f"SECURITY ALERT: {event.event_type.value}\n"
                f"Source: {event.source_ip}\n"
                f"Severity: {event.severity}\n"
                f"Time: {event.timestamp}\n"
                f"Details: {event.details}"
            )
            
            self.logger.critical(f"Security Alert: {alert_message}")
            
            # Here you would send to your alerting system
            # await self.alerting_service.send_alert(alert_message)
            
        except Exception as e:
            self.logger.error(f"Failed to send security alert: {e}")
    
    # API Key Protection Methods
    
    def protect_api_keys_in_logs(self, log_message: str) -> str:
        """Protect API keys from appearing in logs."""
        return self.logger._mask_sensitive_data(log_message)
    
    def validate_api_key_format(self, api_key: str) -> bool:
        """Validate API key format."""
        if not api_key or len(api_key) < 32:
            return False
        
        # Check for common patterns that indicate a real API key
        if re.match(r'^[A-Za-z0-9_-]+$', api_key):
            return True
        
        return False
    
    def hash_api_key_for_storage(self, api_key: str) -> str:
        """Hash API key for secure storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    # WSS Connection Enforcement
    
    def enforce_wss_connections(self, url: str) -> str:
        """Enforce WSS connections by converting HTTP/WS to HTTPS/WSS."""
        if not self.config["wss_enforcement"]["enabled"]:
            return url
        
        # Convert insecure protocols to secure ones
        if url.startswith("http://"):
            if self.config["wss_enforcement"]["redirect_http_to_https"]:
                url = url.replace("http://", "https://", 1)
                self.logger.info(f"Redirected HTTP to HTTPS: {url}")
        
        if url.startswith("ws://"):
            url = url.replace("ws://", "wss://", 1)
            self.logger.info(f"Upgraded WS to WSS: {url}")
        
        return url
    
    def validate_connection_protocol(self, url: str) -> bool:
        """Validate that connection uses secure protocol."""
        allowed_protocols = self.config["wss_enforcement"]["allowed_protocols"]
        
        for protocol in allowed_protocols:
            if url.startswith(f"{protocol}://"):
                return True
        
        self.logger.warning(f"Insecure protocol detected in URL: {url}")
        return False
    
    # Key Rotation Support
    
    async def rotate_api_keys(self, force: bool = False) -> Dict[str, str]:
        """Rotate API keys with zero downtime."""
        if not self.config["key_rotation"]["enabled"] and not force:
            raise ValueError("Key rotation is disabled")
        
        try:
            # Generate new keys
            new_api_key = self._generate_new_api_key()
            new_api_secret = self._generate_new_api_secret()
            
            # Store old keys for overlap period
            overlap_period = self.config["key_rotation"]["overlap_period_minutes"]
            old_keys = self.active_keys.copy()
            
            # Activate new keys
            self.active_keys = {
                "api_key": new_api_key,
                "api_secret": new_api_secret,
                "created_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(hours=self.config["key_rotation"]["rotation_interval_hours"])).isoformat()
            }
            
            # Schedule old key deactivation
            asyncio.create_task(self._deactivate_old_keys(old_keys, overlap_period))
            
            # Record rotation event
            await self._record_security_event(
                SecurityEventType.KEY_ROTATION,
                "system",
                details={
                    "rotation_type": "manual" if force else "automatic",
                    "overlap_period_minutes": overlap_period
                },
                severity="low"
            )
            
            # Add to rotation history
            self.key_rotation_history.append({
                "timestamp": datetime.now(UTC).isoformat(),
                "old_key_hash": self.hash_api_key_for_storage(old_keys.get("api_key", "")),
                "new_key_hash": self.hash_api_key_for_storage(new_api_key),
                "rotation_type": "manual" if force else "automatic"
            })
            
            self.logger.info("API keys rotated successfully")
            
            return {
                "api_key": new_api_key,
                "api_secret": new_api_secret
            }
            
        except Exception as e:
            self.logger.error(f"Failed to rotate API keys: {e}")
            raise
    
    def _generate_new_api_key(self) -> str:
        """Generate a new API key."""
        import secrets
        return secrets.token_urlsafe(32)
    
    def _generate_new_api_secret(self) -> str:
        """Generate a new API secret."""
        import secrets
        return secrets.token_urlsafe(64)
    
    async def _deactivate_old_keys(self, old_keys: Dict[str, Any], delay_minutes: int):
        """Deactivate old keys after overlap period."""
        await asyncio.sleep(delay_minutes * 60)
        
        self.logger.info(f"Deactivating old API keys after {delay_minutes} minute overlap")
        
        # In a real implementation, you would notify all services to stop using old keys
        # For now, we just log the deactivation
        
    def is_key_rotation_due(self) -> bool:
        """Check if key rotation is due."""
        if not self.config["key_rotation"]["enabled"]:
            return False
        
        if not self.active_keys:
            return True
        
        created_at = datetime.fromisoformat(self.active_keys["created_at"].replace('Z', '+00:00'))
        rotation_interval = timedelta(hours=self.config["key_rotation"]["rotation_interval_hours"])
        
        return datetime.now(UTC) > created_at + rotation_interval
    
    # Access Rights Validation
    
    def validate_access_rights(self, token_grants: Dict[str, Any], required_permissions: List[str]) -> bool:
        """Validate that token has required access rights."""
        if not self.config["access_validation"]["strict_mode"]:
            return True
        
        try:
            # Log access attempt if configured
            if self.config["access_validation"]["log_access_attempts"]:
                self.logger.info(f"Validating access rights: {required_permissions}")
            
            # Check each required permission
            for permission in required_permissions:
                if permission not in token_grants or not token_grants[permission]:
                    self.logger.warning(f"Access denied: missing permission '{permission}'")
                    return False
            
            # Validate all grants if strict mode is enabled
            if self.config["access_validation"]["validate_all_grants"]:
                valid_grants = {
                    "roomCreate", "roomList", "roomJoin", "roomAdmin", "roomRecord",
                    "ingressAdmin", "canPublish", "canSubscribe", "canPublishData",
                    "canUpdateOwnMetadata", "canPublishSources"
                }
                
                for grant_name in token_grants:
                    if grant_name not in valid_grants:
                        self.logger.warning(f"Invalid grant detected: {grant_name}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating access rights: {e}")
            return False
    
    def validate_jwt_token_structure(self, token: str) -> bool:
        """Validate JWT token structure and required fields."""
        try:
            import jwt
            
            # Decode without verification to check structure
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Check required fields
            required_fields = ["iss", "sub", "iat", "exp", "video"]
            for field in required_fields:
                if field not in decoded:
                    self.logger.warning(f"JWT token missing required field: {field}")
                    return False
            
            # Validate video grants structure
            video_grants = decoded.get("video", {})
            if not isinstance(video_grants, dict):
                self.logger.warning("JWT token 'video' field must be an object")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating JWT token structure: {e}")
            return False
    
    # Suspicious Activity Monitoring
    
    def record_auth_attempt(self, source_ip: str, success: bool, user_identity: Optional[str] = None):
        """Record authentication attempt for monitoring."""
        if not success:
            if source_ip not in self.failed_auth_attempts:
                self.failed_auth_attempts[source_ip] = []
            
            self.failed_auth_attempts[source_ip].append(datetime.now(UTC))
            
            # Check if this IP should be flagged
            max_attempts = self.config["suspicious_activity"]["max_failed_attempts"]
            recent_attempts = [
                attempt for attempt in self.failed_auth_attempts[source_ip]
                if attempt > datetime.now(UTC) - timedelta(minutes=15)
            ]
            
            if len(recent_attempts) >= max_attempts:
                asyncio.create_task(self._record_security_event(
                    SecurityEventType.SUSPICIOUS_LOGIN,
                    source_ip,
                    user_identity,
                    {"failed_attempts": len(recent_attempts)},
                    "high"
                ))
    
    def record_api_usage(self, endpoint: str, source_ip: str, response_time: float):
        """Record API usage for monitoring."""
        current_minute = datetime.now(UTC).replace(second=0, microsecond=0)
        
        # Initialize tracking structures
        if endpoint not in self.api_usage_stats:
            self.api_usage_stats[endpoint] = {}
        
        if source_ip not in self.api_usage_stats:
            self.api_usage_stats[source_ip] = {"requests_per_minute": 0, "last_minute": current_minute}
        
        # Update per-minute counters
        if self.api_usage_stats[source_ip]["last_minute"] != current_minute:
            self.api_usage_stats[source_ip]["requests_per_minute"] = 1
            self.api_usage_stats[source_ip]["last_minute"] = current_minute
        else:
            self.api_usage_stats[source_ip]["requests_per_minute"] += 1
        
        # Update endpoint stats
        minute_key = current_minute.isoformat()
        if minute_key not in self.api_usage_stats[endpoint]:
            self.api_usage_stats[endpoint][minute_key] = 0
        self.api_usage_stats[endpoint][minute_key] += 1
    
    def is_ip_blocked(self, source_ip: str) -> bool:
        """Check if IP is blocked due to suspicious activity."""
        if source_ip not in self.failed_auth_attempts:
            return False
        
        max_attempts = self.config["suspicious_activity"]["max_failed_attempts"]
        lockout_duration = self.config["suspicious_activity"]["lockout_duration_minutes"]
        
        recent_attempts = [
            attempt for attempt in self.failed_auth_attempts[source_ip]
            if attempt > datetime.now(UTC) - timedelta(minutes=lockout_duration)
        ]
        
        return len(recent_attempts) >= max_attempts
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status and metrics."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "configuration": {
                "wss_enforcement_enabled": self.config["wss_enforcement"]["enabled"],
                "key_rotation_enabled": self.config["key_rotation"]["enabled"],
                "strict_access_validation": self.config["access_validation"]["strict_mode"],
                "suspicious_activity_monitoring": True
            },
            "metrics": {
                "total_security_events": len(self.security_events),
                "failed_auth_attempts": sum(len(attempts) for attempts in self.failed_auth_attempts.values()),
                "blocked_ips": len([ip for ip in self.failed_auth_attempts if self.is_ip_blocked(ip)]),
                "key_rotations": len(self.key_rotation_history),
                "last_key_rotation": self.key_rotation_history[-1]["timestamp"] if self.key_rotation_history else None
            },
            "recent_events": [
                {
                    "type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "source_ip": event.source_ip,
                    "severity": event.severity
                }
                for event in self.security_events[-10:]  # Last 10 events
            ]
        }
    
    # Configuration Management
    
    def update_security_config(self, new_config: Dict[str, Any]):
        """Update security configuration."""
        try:
            # Validate configuration
            self._validate_security_config(new_config)
            
            # Update configuration
            self.config.update(new_config)
            
            # Save to file
            self._save_security_config()
            
            self.logger.info("Security configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update security configuration: {e}")
            raise
    
    def _validate_security_config(self, config: Dict[str, Any]):
        """Validate security configuration."""
        required_sections = ["wss_enforcement", "key_rotation", "access_validation", "suspicious_activity", "logging"]
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate specific settings
        if config["suspicious_activity"]["max_failed_attempts"] < 1:
            raise ValueError("max_failed_attempts must be at least 1")
        
        if config["key_rotation"]["rotation_interval_hours"] < 1:
            raise ValueError("rotation_interval_hours must be at least 1")
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get current security configuration."""
        return self.config.copy()

# Global security manager instance
_security_manager: Optional[LiveKitSecurityManager] = None

def get_security_manager() -> LiveKitSecurityManager:
    """Get global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = LiveKitSecurityManager()
    return _security_manager

def initialize_security(config_path: Optional[str] = None) -> LiveKitSecurityManager:
    """Initialize security manager with custom config path."""
    global _security_manager
    _security_manager = LiveKitSecurityManager(config_path)
    return _security_manager
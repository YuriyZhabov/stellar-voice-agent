"""
LiveKit Security Package

Provides comprehensive security features for LiveKit system including:
- API key protection from log leakage
- WSS connection enforcement  
- Key rotation support
- Access rights validation
- Suspicious activity monitoring
"""

from .livekit_security import (
    LiveKitSecurityManager,
    SecureLogger,
    SecurityEventType,
    SecurityEvent,
    get_security_manager,
    initialize_security
)

from .security_integration import (
    SecurityIntegratedAuthManager,
    SecurityIntegratedAPIClient,
    security_required,
    SecureWebhookHandler,
    SecurityHealthChecker,
    get_webhook_handler,
    get_health_checker
)

# Import from parent security module for backward compatibility
import sys
import os
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

# Import directly from security.py
import importlib.util
security_path = os.path.join(parent_dir, 'security.py')
spec = importlib.util.spec_from_file_location("security_utils", security_path)
security_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security_utils)

generate_secret_key = security_utils.generate_secret_key
validate_secret_key = security_utils.validate_secret_key
mask_sensitive_data = security_utils.mask_sensitive_data
validate_api_key = security_utils.validate_api_key
validate_audio_data = security_utils.validate_audio_data
APIKeyType = security_utils.APIKeyType
SensitiveDataFilter = security_utils.SensitiveDataFilter
SecurityConfig = security_utils.SecurityConfig

__all__ = [
    # Core security
    'LiveKitSecurityManager',
    'SecureLogger', 
    'SecurityEventType',
    'SecurityEvent',
    'get_security_manager',
    'initialize_security',
    
    # Security integration
    'SecurityIntegratedAuthManager',
    'SecurityIntegratedAPIClient',
    'security_required',
    'SecureWebhookHandler',
    'SecurityHealthChecker',
    'get_webhook_handler',
    'get_health_checker',
    
    # Utility functions
    'generate_secret_key',
    'validate_secret_key',
    'mask_sensitive_data',
    'validate_api_key',
    'validate_audio_data',
    'APIKeyType',
    'SensitiveDataFilter',
    'SecurityConfig'
]
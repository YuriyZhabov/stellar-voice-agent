"""Security utilities for Voice AI Agent."""

import hashlib
import logging
import re
import secrets
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass
from enum import Enum


class APIKeyType(Enum):
    """Supported API key types with their validation patterns."""
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    CARTESIA = "cartesia"
    LIVEKIT = "livekit"


@dataclass
class APIKeyValidationResult:
    """Result of API key validation."""
    is_valid: bool
    key_type: Optional[APIKeyType] = None
    error_message: Optional[str] = None
    masked_key: Optional[str] = None


@dataclass
class AudioValidationResult:
    """Result of audio data validation."""
    is_valid: bool
    file_size: int
    detected_format: Optional[str] = None
    duration_estimate: Optional[float] = None
    error_message: Optional[str] = None


class SecurityConfig:
    """Security configuration constants."""
    
    # Secret key requirements
    MIN_SECRET_KEY_LENGTH = 32
    SECRET_KEY_ENTROPY_THRESHOLD = 4.0  # bits per character
    
    # API key patterns (more flexible)
    API_KEY_PATTERNS = {
        APIKeyType.OPENAI: re.compile(r'^sk-[A-Za-z0-9_-]{20,}$'),
        APIKeyType.DEEPGRAM: re.compile(r'^[a-f0-9A-F]{20,}$'),
        APIKeyType.CARTESIA: re.compile(r'^[A-Za-z0-9_-]{20,}$'),
        APIKeyType.LIVEKIT: re.compile(r'^API[A-Za-z0-9_-]{8,}$'),  # Reduced minimum length for LiveKit
    }
    
    # Audio validation limits
    MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    MIN_AUDIO_SIZE_BYTES = 100  # 100 bytes
    MAX_AUDIO_DURATION_SECONDS = 300  # 5 minutes
    
    # Supported audio formats (magic bytes)
    AUDIO_MAGIC_BYTES = {
        b'RIFF': 'wav',
        b'ID3': 'mp3',
        b'\xff\xfb': 'mp3',
        b'\xff\xf3': 'mp3',
        b'\xff\xf2': 'mp3',
        b'OggS': 'ogg',
        b'fLaC': 'flac',
        b'FORM': 'aiff',
    }
    
    # Sensitive data patterns for log filtering
    SENSITIVE_PATTERNS = [
        re.compile(r'(api[_\s-]?key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_-]{20,})', re.IGNORECASE),
        re.compile(r'(secret[_\s-]?key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_-]{20,})', re.IGNORECASE),
        re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']{8,})', re.IGNORECASE),
        re.compile(r'(token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_-]{20,})', re.IGNORECASE),
        re.compile(r'(authorization["\']?\s*[:=]\s*["\']?bearer\s+)([A-Za-z0-9_-]{20,})', re.IGNORECASE),
        re.compile(r'(sk-[A-Za-z0-9_-]{20,})', re.IGNORECASE),  # OpenAI keys
        re.compile(r'([a-f0-9A-F]{40})', re.IGNORECASE),  # Deepgram keys
    ]


def generate_secret_key(length: int = 64) -> str:
    """
    Generate a cryptographically strong secret key.
    
    Args:
        length: Length of the secret key in characters
        
    Returns:
        str: Base64-encoded secret key
        
    Raises:
        ValueError: If length is too short
    """
    if length < SecurityConfig.MIN_SECRET_KEY_LENGTH:
        raise ValueError(f"Secret key length must be at least {SecurityConfig.MIN_SECRET_KEY_LENGTH} characters")
    
    # Generate random bytes and encode as URL-safe base64
    random_bytes = secrets.token_bytes(length * 3 // 4)  # Adjust for base64 encoding
    secret_key = secrets.token_urlsafe(len(random_bytes))
    
    # Ensure we have the exact length requested
    return secret_key[:length]


def validate_secret_key(secret_key: str) -> bool:
    """
    Validate secret key strength.
    
    Args:
        secret_key: Secret key to validate
        
    Returns:
        bool: True if secret key meets security requirements
    """
    if len(secret_key) < SecurityConfig.MIN_SECRET_KEY_LENGTH:
        return False
    
    # Check for default/weak keys
    weak_patterns = [
        "your-secret-key-here",
        "change-this-in-production",
        "default",
        "secret",
        "password",
        "123456",
    ]
    
    secret_lower = secret_key.lower()
    for pattern in weak_patterns:
        if pattern in secret_lower:
            return False
    
    # Calculate entropy (simplified)
    entropy = calculate_entropy(secret_key)
    return entropy >= SecurityConfig.SECRET_KEY_ENTROPY_THRESHOLD


def calculate_entropy(text: str) -> float:
    """
    Calculate Shannon entropy of text.
    
    Args:
        text: Text to analyze
        
    Returns:
        float: Entropy in bits per character
    """
    if not text:
        return 0.0
    
    # Count character frequencies
    char_counts = {}
    for char in text:
        char_counts[char] = char_counts.get(char, 0) + 1
    
    # Calculate entropy
    import math
    entropy = 0.0
    text_length = len(text)
    
    for count in char_counts.values():
        probability = count / text_length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def validate_api_key(api_key: str, key_type: Optional[APIKeyType] = None) -> APIKeyValidationResult:
    """
    Validate API key format and strength.
    
    Args:
        api_key: API key to validate
        key_type: Expected key type (auto-detect if None)
        
    Returns:
        APIKeyValidationResult: Validation result
    """
    if not api_key or not api_key.strip():
        return APIKeyValidationResult(
            is_valid=False,
            error_message="API key cannot be empty"
        )
    
    api_key = api_key.strip()
    
    # Check minimum length (special case for LiveKit)
    min_length = 12 if (key_type == APIKeyType.LIVEKIT or api_key.startswith('API')) else 20
    if len(api_key) < min_length:
        return APIKeyValidationResult(
            is_valid=False,
            error_message=f"API key is too short (minimum {min_length} characters)"
        )
    
    # If key type is specified, validate against specific pattern
    if key_type:
        pattern = SecurityConfig.API_KEY_PATTERNS.get(key_type)
        if pattern and not pattern.match(api_key):
            return APIKeyValidationResult(
                is_valid=False,
                key_type=key_type,
                error_message=f"API key does not match expected format for {key_type.value}",
                masked_key=mask_sensitive_data(api_key)
            )
        
        return APIKeyValidationResult(
            is_valid=True,
            key_type=key_type,
            masked_key=mask_sensitive_data(api_key)
        )
    
    # Auto-detect key type
    for detected_type, pattern in SecurityConfig.API_KEY_PATTERNS.items():
        if pattern.match(api_key):
            return APIKeyValidationResult(
                is_valid=True,
                key_type=detected_type,
                masked_key=mask_sensitive_data(api_key)
            )
    
    # Generic validation for unknown key types
    if len(api_key) >= 20 and api_key.isalnum() or set(api_key) & set('_-'):
        return APIKeyValidationResult(
            is_valid=True,
            masked_key=mask_sensitive_data(api_key)
        )
    
    return APIKeyValidationResult(
        is_valid=False,
        error_message="API key format is not recognized",
        masked_key=mask_sensitive_data(api_key)
    )


def validate_audio_data(audio_data: bytes, max_size: Optional[int] = None) -> AudioValidationResult:
    """
    Validate and sanitize audio data.
    
    Args:
        audio_data: Audio data bytes to validate
        max_size: Maximum allowed size in bytes
        
    Returns:
        AudioValidationResult: Validation result
    """
    if not audio_data:
        return AudioValidationResult(
            is_valid=False,
            file_size=0,
            error_message="Audio data cannot be empty"
        )
    
    file_size = len(audio_data)
    max_allowed_size = max_size or SecurityConfig.MAX_AUDIO_SIZE_BYTES
    
    # Check size limits
    if file_size < SecurityConfig.MIN_AUDIO_SIZE_BYTES:
        return AudioValidationResult(
            is_valid=False,
            file_size=file_size,
            error_message=f"Audio data too small (minimum {SecurityConfig.MIN_AUDIO_SIZE_BYTES} bytes)"
        )
    
    if file_size > max_allowed_size:
        return AudioValidationResult(
            is_valid=False,
            file_size=file_size,
            error_message=f"Audio data too large (maximum {max_allowed_size} bytes)"
        )
    
    # Detect audio format by magic bytes
    detected_format = None
    for magic_bytes, format_name in SecurityConfig.AUDIO_MAGIC_BYTES.items():
        if audio_data.startswith(magic_bytes):
            detected_format = format_name
            break
    
    # Estimate duration for WAV files (simplified)
    duration_estimate = None
    if detected_format == 'wav' and len(audio_data) > 44:  # WAV header is 44 bytes
        try:
            # Extract sample rate from WAV header (bytes 24-27)
            sample_rate = int.from_bytes(audio_data[24:28], byteorder='little')
            # Extract bits per sample (bytes 34-35)
            bits_per_sample = int.from_bytes(audio_data[34:36], byteorder='little')
            # Extract number of channels (bytes 22-23)
            channels = int.from_bytes(audio_data[22:24], byteorder='little')
            
            if sample_rate > 0 and bits_per_sample > 0 and channels > 0:
                bytes_per_second = sample_rate * (bits_per_sample // 8) * channels
                audio_data_size = file_size - 44  # Subtract header size
                duration_estimate = audio_data_size / bytes_per_second
        except Exception:
            pass  # Ignore errors in duration estimation
    
    # Check duration limits
    if duration_estimate and duration_estimate > SecurityConfig.MAX_AUDIO_DURATION_SECONDS:
        return AudioValidationResult(
            is_valid=False,
            file_size=file_size,
            detected_format=detected_format,
            duration_estimate=duration_estimate,
            error_message=f"Audio duration too long (maximum {SecurityConfig.MAX_AUDIO_DURATION_SECONDS} seconds)"
        )
    
    return AudioValidationResult(
        is_valid=True,
        file_size=file_size,
        detected_format=detected_format,
        duration_estimate=duration_estimate
    )


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging.
    
    Args:
        data: Sensitive data to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to show at the end
        
    Returns:
        str: Masked data
    """
    if not data or len(data) <= visible_chars:
        return mask_char * len(data) if data else ""
    
    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]


def sanitize_log_data(data: Union[str, Dict[str, Any], List[Any]]) -> Union[str, Dict[str, Any], List[Any]]:
    """
    Sanitize data for logging by removing or masking sensitive information.
    
    Args:
        data: Data to sanitize
        
    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        return _sanitize_string(data)
    elif isinstance(data, dict):
        return {key: sanitize_log_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    else:
        return data


def _sanitize_string(text: str) -> str:
    """
    Sanitize string by masking sensitive patterns.
    
    Args:
        text: Text to sanitize
        
    Returns:
        str: Sanitized text
    """
    sanitized = text
    
    for pattern in SecurityConfig.SENSITIVE_PATTERNS:
        def replace_match(match):
            prefix = match.group(1) if match.lastindex >= 1 else ""
            sensitive_part = match.group(2) if match.lastindex >= 2 else match.group(0)
            return prefix + mask_sensitive_data(sensitive_part)
        
        sanitized = pattern.sub(replace_match, sanitized)
    
    return sanitized


class SensitiveDataFilter(logging.Filter):
    """Logging filter to remove sensitive data from log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record to remove sensitive data.
        
        Args:
            record: Log record to filter
            
        Returns:
            bool: Always True (record is modified in place)
        """
        # Sanitize the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = sanitize_log_data(record.msg)
        
        # Sanitize arguments
        if hasattr(record, 'args') and record.args:
            record.args = tuple(sanitize_log_data(arg) for arg in record.args)
        
        # Sanitize extra fields
        for key, value in list(record.__dict__.items()):
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info'
            }:
                setattr(record, key, sanitize_log_data(value))
        
        return True


def get_security_headers() -> Dict[str, str]:
    """
    Get security headers for HTTP responses.
    
    Returns:
        Dict[str, str]: Security headers
    """
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    }


def hash_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hash data using SHA-256 with optional salt.
    
    Args:
        data: Data to hash
        salt: Optional salt for hashing
        
    Returns:
        str: Hexadecimal hash
    """
    if salt:
        data = salt + data
    
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_hash(data: str, hash_value: str, salt: Optional[str] = None) -> bool:
    """
    Verify data against hash.
    
    Args:
        data: Original data
        hash_value: Hash to verify against
        salt: Optional salt used in hashing
        
    Returns:
        bool: True if hash matches
    """
    return hash_data(data, salt) == hash_value
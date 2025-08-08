"""Tests for security utilities."""

import pytest
import logging
from unittest.mock import patch

from src.security import (
    generate_secret_key,
    validate_secret_key,
    calculate_entropy,
    validate_api_key,
    validate_audio_data,
    mask_sensitive_data,
    sanitize_log_data,
    SensitiveDataFilter,
    get_security_headers,
    hash_data,
    verify_hash,
    APIKeyType,
    APIKeyValidationResult,
    AudioValidationResult,
    SecurityConfig
)


class TestSecretKeyGeneration:
    """Test secret key generation and validation."""
    
    def test_generate_secret_key_default_length(self):
        """Test generating secret key with default length."""
        key = generate_secret_key()
        assert len(key) == 64
        assert isinstance(key, str)
    
    def test_generate_secret_key_custom_length(self):
        """Test generating secret key with custom length."""
        key = generate_secret_key(48)
        assert len(key) == 48
    
    def test_generate_secret_key_minimum_length(self):
        """Test generating secret key with minimum length."""
        key = generate_secret_key(32)
        assert len(key) == 32
    
    def test_generate_secret_key_too_short_raises_error(self):
        """Test that generating too short key raises error."""
        with pytest.raises(ValueError, match="Secret key length must be at least"):
            generate_secret_key(16)
    
    def test_generated_keys_are_unique(self):
        """Test that generated keys are unique."""
        key1 = generate_secret_key()
        key2 = generate_secret_key()
        assert key1 != key2


class TestSecretKeyValidation:
    """Test secret key validation."""
    
    def test_validate_strong_secret_key(self):
        """Test validating a strong secret key."""
        strong_key = generate_secret_key()
        assert validate_secret_key(strong_key) is True
    
    def test_validate_weak_secret_key(self):
        """Test validating weak secret keys."""
        weak_keys = [
            "your-secret-key-here",
            "change-this-in-production",
            "default",
            "secret",
            "password",
            "123456",
            "short"
        ]
        
        for weak_key in weak_keys:
            assert validate_secret_key(weak_key) is False
    
    def test_validate_short_secret_key(self):
        """Test validating short secret key."""
        short_key = "a" * 16
        assert validate_secret_key(short_key) is False


class TestEntropyCalculation:
    """Test entropy calculation."""
    
    def test_calculate_entropy_empty_string(self):
        """Test entropy calculation for empty string."""
        assert calculate_entropy("") == 0.0
    
    def test_calculate_entropy_single_character(self):
        """Test entropy calculation for single character."""
        assert calculate_entropy("a") == 0.0
    
    def test_calculate_entropy_repeated_characters(self):
        """Test entropy calculation for repeated characters."""
        entropy = calculate_entropy("aaaa")
        assert entropy == 0.0
    
    def test_calculate_entropy_mixed_characters(self):
        """Test entropy calculation for mixed characters."""
        entropy = calculate_entropy("abcd")
        assert entropy > 0.0
    
    def test_calculate_entropy_complex_string(self):
        """Test entropy calculation for complex string."""
        complex_string = "Th1s!sAC0mpl3xStr1ng"
        entropy = calculate_entropy(complex_string)
        assert entropy > 3.0  # Should have good entropy


class TestAPIKeyValidation:
    """Test API key validation."""
    
    def test_validate_openai_api_key_valid(self):
        """Test validating valid OpenAI API key."""
        valid_key = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
        result = validate_api_key(valid_key, APIKeyType.OPENAI)
        assert result.is_valid is True
        assert result.key_type == APIKeyType.OPENAI
    
    def test_validate_deepgram_api_key_valid(self):
        """Test validating valid Deepgram API key."""
        valid_key = "abcdef1234567890abcdef1234567890abcdef12"
        result = validate_api_key(valid_key, APIKeyType.DEEPGRAM)
        assert result.is_valid is True
        assert result.key_type == APIKeyType.DEEPGRAM
    
    def test_validate_cartesia_api_key_valid(self):
        """Test validating valid Cartesia API key."""
        valid_key = "cartesia_key_1234567890abcdef"
        result = validate_api_key(valid_key, APIKeyType.CARTESIA)
        assert result.is_valid is True
        assert result.key_type == APIKeyType.CARTESIA
    
    def test_validate_livekit_api_key_valid(self):
        """Test validating valid LiveKit API key."""
        valid_key = "APIabcdef1234567890abcdef1234567890"
        result = validate_api_key(valid_key, APIKeyType.LIVEKIT)
        assert result.is_valid is True
        assert result.key_type == APIKeyType.LIVEKIT
    
    def test_validate_empty_api_key(self):
        """Test validating empty API key."""
        result = validate_api_key("", APIKeyType.OPENAI)
        assert result.is_valid is False
        assert "cannot be empty" in result.error_message
    
    def test_validate_short_api_key(self):
        """Test validating short API key."""
        result = validate_api_key("short", APIKeyType.OPENAI)
        assert result.is_valid is False
        assert "too short" in result.error_message
    
    def test_auto_detect_api_key_type(self):
        """Test auto-detecting API key type."""
        openai_key = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
        result = validate_api_key(openai_key)
        assert result.is_valid is True
        assert result.key_type == APIKeyType.OPENAI


class TestAudioDataValidation:
    """Test audio data validation."""
    
    def test_validate_empty_audio_data(self):
        """Test validating empty audio data."""
        result = validate_audio_data(b"")
        assert result.is_valid is False
        assert "cannot be empty" in result.error_message
    
    def test_validate_too_small_audio_data(self):
        """Test validating too small audio data."""
        small_data = b"x" * 5  # Less than minimum (10 bytes in test mode)
        result = validate_audio_data(small_data)
        assert result.is_valid is False
        assert "too small" in result.error_message
    
    def test_validate_too_large_audio_data(self):
        """Test validating too large audio data."""
        large_data = b"x" * (60 * 1024 * 1024)  # Larger than default max
        result = validate_audio_data(large_data)
        assert result.is_valid is False
        assert "too large" in result.error_message
    
    def test_validate_valid_audio_data(self):
        """Test validating valid audio data."""
        valid_data = b"x" * 1000  # Valid size
        result = validate_audio_data(valid_data)
        assert result.is_valid is True
        assert result.file_size == 1000
    
    def test_validate_wav_audio_data(self):
        """Test validating WAV audio data."""
        # Create minimal WAV header
        wav_header = b"RIFF" + b"\x00" * 40  # Minimal WAV header
        wav_data = wav_header + b"x" * 1000
        result = validate_audio_data(wav_data)
        assert result.is_valid is True
        assert result.detected_format == "wav"
    
    def test_validate_custom_max_size(self):
        """Test validating with custom max size."""
        data = b"x" * 2000
        result = validate_audio_data(data, max_size=1000)
        assert result.is_valid is False
        assert "too large" in result.error_message


class TestSensitiveDataMasking:
    """Test sensitive data masking."""
    
    def test_mask_sensitive_data_default(self):
        """Test masking sensitive data with defaults."""
        sensitive = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_sensitive_data(sensitive)
        assert masked.endswith("7890")
        assert "*" in masked
        assert len(masked) == len(sensitive)
    
    def test_mask_sensitive_data_custom_params(self):
        """Test masking with custom parameters."""
        sensitive = "secret123456"
        masked = mask_sensitive_data(sensitive, mask_char="#", visible_chars=2)
        assert masked.endswith("56")
        assert "#" in masked
    
    def test_mask_short_data(self):
        """Test masking short data."""
        short_data = "abc"
        masked = mask_sensitive_data(short_data)
        assert masked == "***"
    
    def test_mask_empty_data(self):
        """Test masking empty data."""
        masked = mask_sensitive_data("")
        assert masked == ""


class TestLogDataSanitization:
    """Test log data sanitization."""
    
    def test_sanitize_string_with_api_key(self):
        """Test sanitizing string containing API key."""
        log_message = "Using API key: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
        sanitized = sanitize_log_data(log_message)
        assert "sk-proj-" not in sanitized or "*" in sanitized
    
    def test_sanitize_dict_with_sensitive_data(self):
        """Test sanitizing dictionary with sensitive data."""
        log_data = {
            "api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
            "message": "Processing request",
            "secret": "my-secret-password"
        }
        sanitized = sanitize_log_data(log_data)
        assert isinstance(sanitized, dict)
        assert "message" in sanitized
        assert sanitized["message"] == "Processing request"
    
    def test_sanitize_list_with_sensitive_data(self):
        """Test sanitizing list with sensitive data."""
        log_data = [
            "Normal message",
            "API key: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
            {"secret": "password123"}
        ]
        sanitized = sanitize_log_data(log_data)
        assert isinstance(sanitized, list)
        assert len(sanitized) == 3
        assert sanitized[0] == "Normal message"
    
    def test_sanitize_non_string_data(self):
        """Test sanitizing non-string data."""
        data = 12345
        sanitized = sanitize_log_data(data)
        assert sanitized == 12345


class TestSensitiveDataFilter:
    """Test sensitive data logging filter."""
    
    def test_filter_log_record_with_sensitive_data(self):
        """Test filtering log record with sensitive data."""
        # Create a log record
        logger = logging.getLogger("test")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="API key: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
            args=(),
            exc_info=None
        )
        
        # Apply filter
        filter_obj = SensitiveDataFilter()
        result = filter_obj.filter(record)
        
        assert result is True  # Filter should not block the record
        # The message should be sanitized
        assert "sk-proj-" not in record.msg or "*" in record.msg
    
    def test_filter_log_record_with_args(self):
        """Test filtering log record with sensitive args."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: %s",
            args=("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",),
            exc_info=None
        )
        
        filter_obj = SensitiveDataFilter()
        result = filter_obj.filter(record)
        
        assert result is True
        # Args should be sanitized
        assert len(record.args) == 1


class TestSecurityHeaders:
    """Test security headers."""
    
    def test_get_security_headers(self):
        """Test getting security headers."""
        headers = get_security_headers()
        
        assert isinstance(headers, dict)
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
        assert "Content-Security-Policy" in headers
        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers
        
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"


class TestHashingUtilities:
    """Test hashing utilities."""
    
    def test_hash_data_without_salt(self):
        """Test hashing data without salt."""
        data = "test data"
        hash_value = hash_data(data)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex length
    
    def test_hash_data_with_salt(self):
        """Test hashing data with salt."""
        data = "test data"
        salt = "test_salt"
        hash_value = hash_data(data, salt)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
    
    def test_hash_data_consistency(self):
        """Test that hashing is consistent."""
        data = "test data"
        hash1 = hash_data(data)
        hash2 = hash_data(data)
        
        assert hash1 == hash2
    
    def test_hash_data_with_salt_consistency(self):
        """Test that hashing with salt is consistent."""
        data = "test data"
        salt = "test_salt"
        hash1 = hash_data(data, salt)
        hash2 = hash_data(data, salt)
        
        assert hash1 == hash2
    
    def test_verify_hash_correct(self):
        """Test verifying correct hash."""
        data = "test data"
        hash_value = hash_data(data)
        
        assert verify_hash(data, hash_value) is True
    
    def test_verify_hash_incorrect(self):
        """Test verifying incorrect hash."""
        data = "test data"
        wrong_data = "wrong data"
        hash_value = hash_data(data)
        
        assert verify_hash(wrong_data, hash_value) is False
    
    def test_verify_hash_with_salt(self):
        """Test verifying hash with salt."""
        data = "test data"
        salt = "test_salt"
        hash_value = hash_data(data, salt)
        
        assert verify_hash(data, hash_value, salt) is True
        assert verify_hash(data, hash_value) is False  # Without salt should fail


class TestSecurityConfig:
    """Test security configuration constants."""
    
    def test_security_config_constants(self):
        """Test that security config has required constants."""
        assert hasattr(SecurityConfig, 'MIN_SECRET_KEY_LENGTH')
        assert hasattr(SecurityConfig, 'SECRET_KEY_ENTROPY_THRESHOLD')
        assert hasattr(SecurityConfig, 'API_KEY_PATTERNS')
        assert hasattr(SecurityConfig, 'MAX_AUDIO_SIZE_BYTES')
        assert hasattr(SecurityConfig, 'MIN_AUDIO_SIZE_BYTES')
        assert hasattr(SecurityConfig, 'AUDIO_MAGIC_BYTES')
        assert hasattr(SecurityConfig, 'SENSITIVE_PATTERNS')
        
        assert SecurityConfig.MIN_SECRET_KEY_LENGTH >= 32
        assert SecurityConfig.MAX_AUDIO_SIZE_BYTES > SecurityConfig.MIN_AUDIO_SIZE_BYTES
    
    def test_api_key_patterns_exist(self):
        """Test that API key patterns exist for all types."""
        for api_type in APIKeyType:
            assert api_type in SecurityConfig.API_KEY_PATTERNS
    
    def test_audio_magic_bytes_not_empty(self):
        """Test that audio magic bytes are defined."""
        assert len(SecurityConfig.AUDIO_MAGIC_BYTES) > 0
        assert b'RIFF' in SecurityConfig.AUDIO_MAGIC_BYTES  # WAV format
    
    def test_sensitive_patterns_not_empty(self):
        """Test that sensitive patterns are defined."""
        assert len(SecurityConfig.SENSITIVE_PATTERNS) > 0


class TestAPIKeyValidationResult:
    """Test API key validation result dataclass."""
    
    def test_create_valid_result(self):
        """Test creating valid API key result."""
        result = APIKeyValidationResult(
            is_valid=True,
            key_type=APIKeyType.OPENAI,
            masked_key="sk-***7890"
        )
        
        assert result.is_valid is True
        assert result.key_type == APIKeyType.OPENAI
        assert result.masked_key == "sk-***7890"
        assert result.error_message is None
    
    def test_create_invalid_result(self):
        """Test creating invalid API key result."""
        result = APIKeyValidationResult(
            is_valid=False,
            error_message="Invalid format"
        )
        
        assert result.is_valid is False
        assert result.error_message == "Invalid format"
        assert result.key_type is None
        assert result.masked_key is None


class TestAudioValidationResult:
    """Test audio validation result dataclass."""
    
    def test_create_valid_audio_result(self):
        """Test creating valid audio validation result."""
        result = AudioValidationResult(
            is_valid=True,
            file_size=1024,
            detected_format="wav",
            duration_estimate=10.5
        )
        
        assert result.is_valid is True
        assert result.file_size == 1024
        assert result.detected_format == "wav"
        assert result.duration_estimate == 10.5
        assert result.error_message is None
    
    def test_create_invalid_audio_result(self):
        """Test creating invalid audio validation result."""
        result = AudioValidationResult(
            is_valid=False,
            file_size=0,
            error_message="File too small"
        )
        
        assert result.is_valid is False
        assert result.file_size == 0
        assert result.error_message == "File too small"
        assert result.detected_format is None
        assert result.duration_estimate is None
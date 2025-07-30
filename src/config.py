"""Centralized configuration management for Voice AI Agent."""

import os
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from src.security import (
    generate_secret_key, 
    validate_secret_key, 
    validate_api_key, 
    APIKeyType,
    SecurityConfig
)


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SIPTransport(str, Enum):
    """SIP transport protocols."""
    UDP = "UDP"
    TCP = "TCP"
    TLS = "TLS"


class Settings(BaseSettings):
    """
    Centralized configuration management with Pydantic validation.
    
    All configuration values are loaded from environment variables
    with comprehensive validation and fallback mechanisms.
    """
    
    # =============================================================================
    # ENVIRONMENT CONFIGURATION
    # =============================================================================
    
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # =============================================================================
    # DOMAIN AND NETWORK CONFIGURATION
    # =============================================================================
    
    domain: str = Field(
        default="localhost",
        description="Domain name for the voice AI agent"
    )
    
    public_ip: str = Field(
        default="127.0.0.1",
        description="Public IP address of the server"
    )
    
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the web server"
    )
    
    # =============================================================================
    # SIP CONFIGURATION
    # =============================================================================
    
    sip_number: Optional[str] = Field(
        default=None,
        description="Phone number assigned to SIP trunk"
    )
    
    sip_server: Optional[str] = Field(
        default=None,
        description="SIP server hostname or IP address"
    )
    
    sip_username: Optional[str] = Field(
        default=None,
        description="SIP authentication username"
    )
    
    sip_password: Optional[str] = Field(
        default=None,
        description="SIP authentication password"
    )
    
    sip_transport: SIPTransport = Field(
        default=SIPTransport.UDP,
        description="SIP transport protocol"
    )
    
    sip_port: int = Field(
        default=5060,
        ge=1,
        le=65535,
        description="SIP port"
    )
    
    # =============================================================================
    # LIVEKIT CONFIGURATION
    # =============================================================================
    
    livekit_url: Optional[str] = Field(
        default=None,
        description="LiveKit server URL"
    )
    
    livekit_api_key: Optional[str] = Field(
        default=None,
        description="LiveKit API key"
    )
    
    livekit_api_secret: Optional[str] = Field(
        default=None,
        description="LiveKit API secret"
    )
    
    livekit_sip_uri: Optional[str] = Field(
        default=None,
        description="LiveKit SIP URI for incoming calls"
    )
    
    # =============================================================================
    # AI SERVICES CONFIGURATION
    # =============================================================================
    
    deepgram_api_key: Optional[str] = Field(
        default=None,
        description="Deepgram API key for speech-to-text"
    )
    
    deepgram_model: str = Field(
        default="nova-2",
        description="Deepgram model to use"
    )
    
    deepgram_language: str = Field(
        default="en-US",
        description="Deepgram language code"
    )
    
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for language model"
    )
    
    openai_model: str = Field(
        default="gpt-4",
        description="OpenAI model to use"
    )
    
    openai_org_id: Optional[str] = Field(
        default=None,
        description="OpenAI organization ID"
    )
    
    cartesia_api_key: Optional[str] = Field(
        default=None,
        description="Cartesia API key for text-to-speech"
    )
    
    cartesia_voice_id: str = Field(
        default="default",
        description="Cartesia voice ID to use"
    )
    
    # =============================================================================
    # PERFORMANCE CONFIGURATION
    # =============================================================================
    
    max_response_latency: float = Field(
        default=1.5,
        gt=0,
        description="Maximum response latency in seconds"
    )
    
    context_window_size: int = Field(
        default=4000,
        gt=0,
        description="Context window size for conversation history"
    )
    
    max_conversation_duration: int = Field(
        default=30,
        gt=0,
        description="Maximum conversation duration in minutes"
    )
    
    retry_attempts: int = Field(
        default=3,
        ge=0,
        description="Number of retry attempts for failed API calls"
    )
    
    retry_backoff_multiplier: float = Field(
        default=2.0,
        gt=0,
        description="Retry backoff multiplier"
    )
    
    max_retry_delay: float = Field(
        default=60.0,
        gt=0,
        description="Maximum retry delay in seconds"
    )
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    
    database_url: str = Field(
        default="sqlite:///./data/voice_ai.db",
        description="Database URL"
    )
    
    db_pool_size: int = Field(
        default=10,
        gt=0,
        description="Database connection pool size"
    )
    
    db_pool_overflow: int = Field(
        default=20,
        ge=0,
        description="Database connection pool overflow"
    )
    
    # =============================================================================
    # REDIS CONFIGURATION
    # =============================================================================
    
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and session storage"
    )
    
    redis_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Redis connection timeout in seconds"
    )
    
    # =============================================================================
    # MONITORING AND OBSERVABILITY
    # =============================================================================
    
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )
    
    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Prometheus metrics port"
    )
    
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    
    sentry_environment: str = Field(
        default="development",
        description="Sentry environment name"
    )
    
    structured_logging: bool = Field(
        default=True,
        description="Enable structured logging"
    )
    
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    
    log_file_path: Optional[str] = Field(
        default=None,
        description="Log file path"
    )
    
    # =============================================================================
    # SECURITY CONFIGURATION
    # =============================================================================
    
    secret_key: str = Field(
        default="your-secret-key-here-change-this-in-production",
        min_length=32,
        description="Secret key for session management and cryptographic operations"
    )
    
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS"
    )
    
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )
    
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable API rate limiting"
    )
    
    rate_limit_per_minute: int = Field(
        default=60,
        gt=0,
        description="Rate limit: requests per minute per IP"
    )
    
    # =============================================================================
    # AUDIO PROCESSING CONFIGURATION
    # =============================================================================
    
    audio_sample_rate: int = Field(
        default=16000,
        gt=0,
        description="Audio sample rate in Hz"
    )
    
    audio_channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Audio channels (1 for mono, 2 for stereo)"
    )
    
    audio_bit_depth: int = Field(
        default=16,
        ge=8,
        le=32,
        description="Audio bit depth"
    )
    
    audio_buffer_ms: int = Field(
        default=100,
        gt=0,
        description="Audio buffer size in milliseconds"
    )
    
    vad_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Voice Activity Detection threshold"
    )
    
    # =============================================================================
    # CONVERSATION CONFIGURATION
    # =============================================================================
    
    system_prompt: str = Field(
        default="You are a helpful AI assistant speaking over the phone. Keep responses concise and natural for voice conversation.",
        description="Default system prompt for the AI assistant"
    )
    
    max_response_tokens: int = Field(
        default=150,
        gt=0,
        description="Maximum tokens per response"
    )
    
    ai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for AI responses"
    )
    
    enable_conversation_logging: bool = Field(
        default=True,
        description="Enable conversation logging"
    )
    
    conversation_log_retention_days: int = Field(
        default=30,
        gt=0,
        description="Conversation log retention days"
    )
    
    # =============================================================================
    # DEVELOPMENT AND TESTING
    # =============================================================================
    
    test_mode: bool = Field(
        default=False,
        description="Enable test mode"
    )
    
    mock_api_responses: bool = Field(
        default=False,
        description="Mock API responses for development"
    )
    
    debug_api_calls: bool = Field(
        default=False,
        description="Enable request/response logging for debugging"
    )
    
    test_webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for testing notifications"
    )
    
    # =============================================================================
    # BACKUP AND RECOVERY
    # =============================================================================
    
    enable_auto_backup: bool = Field(
        default=True,
        description="Enable automatic database backups"
    )
    
    backup_interval_hours: int = Field(
        default=24,
        gt=0,
        description="Backup interval in hours"
    )
    
    backup_retention_count: int = Field(
        default=7,
        gt=0,
        description="Number of backup files to retain"
    )
    
    backup_path: str = Field(
        default="./backups/",
        description="Backup storage path"
    )
    
    # =============================================================================
    # VALIDATORS
    # =============================================================================
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key_strength(cls, v, info):
        """Validate secret key strength and security."""
        # Skip validation in test mode
        if hasattr(info, 'data') and info.data and info.data.get('environment') == Environment.TESTING:
            return v
        
        if not validate_secret_key(v):
            raise ValueError(
                f"Secret key does not meet security requirements. "
                f"Must be at least {SecurityConfig.MIN_SECRET_KEY_LENGTH} characters long "
                f"and cryptographically strong."
            )
        return v
    
    @field_validator('deepgram_api_key')
    @classmethod
    def validate_deepgram_key(cls, v, info):
        """Validate Deepgram API key format."""
        if v is not None and v.strip():
            # Skip validation in test mode
            if hasattr(info, 'data') and info.data and info.data.get('environment') == Environment.TESTING:
                return v
            result = validate_api_key(v, APIKeyType.DEEPGRAM)
            if not result.is_valid:
                raise ValueError(f"Invalid Deepgram API key: {result.error_message}")
        return v
    
    @field_validator('openai_api_key')
    @classmethod
    def validate_openai_key(cls, v, info):
        """Validate OpenAI API key format."""
        if v is not None and v.strip():
            # Skip validation in test mode
            if hasattr(info, 'data') and info.data and info.data.get('environment') == Environment.TESTING:
                return v
            result = validate_api_key(v, APIKeyType.OPENAI)
            if not result.is_valid:
                raise ValueError(f"Invalid OpenAI API key: {result.error_message}")
        return v
    
    @field_validator('cartesia_api_key')
    @classmethod
    def validate_cartesia_key(cls, v, info):
        """Validate Cartesia API key format."""
        if v is not None and v.strip():
            # Skip validation in test mode
            if hasattr(info, 'data') and info.data and info.data.get('environment') == Environment.TESTING:
                return v
            result = validate_api_key(v, APIKeyType.CARTESIA)
            if not result.is_valid:
                raise ValueError(f"Invalid Cartesia API key: {result.error_message}")
        return v
    
    @field_validator('livekit_api_key')
    @classmethod
    def validate_livekit_key(cls, v, info):
        """Validate LiveKit API key format."""
        if v is not None and v.strip():
            # Skip validation in test mode
            if hasattr(info, 'data') and info.data and info.data.get('environment') == Environment.TESTING:
                return v
            result = validate_api_key(v, APIKeyType.LIVEKIT)
            if not result.is_valid:
                raise ValueError(f"Invalid LiveKit API key: {result.error_message}")
        return v
    
    @field_validator('public_ip')
    @classmethod
    def validate_ip_address(cls, v):
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
    
    @model_validator(mode='after')
    def validate_production_requirements(self):
        """Validate required fields for production environment."""
        if self.environment == Environment.PRODUCTION:
            required_fields = {
                'sip_number': self.sip_number,
                'sip_server': self.sip_server,
                'sip_username': self.sip_username,
                'sip_password': self.sip_password,
                'livekit_url': self.livekit_url,
                'livekit_api_key': self.livekit_api_key,
                'livekit_api_secret': self.livekit_api_secret,
                'deepgram_api_key': self.deepgram_api_key,
                'openai_api_key': self.openai_api_key,
                'cartesia_api_key': self.cartesia_api_key
            }
            
            missing_fields = []
            for field_name, field_value in required_fields.items():
                if not field_value:
                    missing_fields.append(field_name)
            
            if missing_fields:
                raise ValueError(f"Missing required fields for production: {missing_fields}")
        
        return self
    
    # =============================================================================
    # PROPERTIES
    # =============================================================================
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == Environment.TESTING
    
    @property
    def database_is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith('sqlite')
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return {
            'level': self.log_level.value,
            'structured': self.structured_logging,
            'format': self.log_format,
            'file_path': self.log_file_path,
            'debug': self.debug
        }
    
    @property
    def sip_config(self) -> Dict[str, Any]:
        """Get SIP configuration."""
        return {
            'number': self.sip_number,
            'server': self.sip_server,
            'username': self.sip_username,
            'password': self.sip_password,
            'transport': self.sip_transport.value,
            'port': self.sip_port
        }
    
    @property
    def livekit_config(self) -> Dict[str, Any]:
        """Get LiveKit configuration."""
        return {
            'url': self.livekit_url,
            'api_key': self.livekit_api_key,
            'api_secret': self.livekit_api_secret,
            'sip_uri': self.livekit_sip_uri
        }
    
    @property
    def ai_services_config(self) -> Dict[str, Any]:
        """Get AI services configuration."""
        return {
            'deepgram': {
                'api_key': self.deepgram_api_key,
                'model': self.deepgram_model,
                'language': self.deepgram_language
            },
            'openai': {
                'api_key': self.openai_api_key,
                'model': self.openai_model,
                'org_id': self.openai_org_id,
                'temperature': self.ai_temperature,
                'max_tokens': self.max_response_tokens
            },
            'cartesia': {
                'api_key': self.cartesia_api_key,
                'voice_id': self.cartesia_voice_id
            }
        }
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': False,
        'validate_assignment': True,
        'extra': 'forbid',  # Forbid extra fields
        'env_prefix': '',
    }


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.
    
    Returns:
        Settings: The global settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.
    
    Returns:
        Settings: The reloaded settings instance
    """
    global _settings
    _settings = Settings()
    return _settings


def validate_settings() -> Dict[str, Any]:
    """
    Validate current settings and return validation report.
    
    Returns:
        Dict containing validation results
    """
    try:
        settings = get_settings()
        return {
            'valid': True,
            'environment': settings.environment.value,
            'production_ready': settings.is_production,
            'required_services': {
                'sip': bool(settings.sip_server and settings.sip_username),
                'livekit': bool(settings.livekit_url and settings.livekit_api_key),
                'deepgram': bool(settings.deepgram_api_key),
                'openai': bool(settings.openai_api_key),
                'cartesia': bool(settings.cartesia_api_key)
            },
            'warnings': []
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'environment': 'unknown'
        }
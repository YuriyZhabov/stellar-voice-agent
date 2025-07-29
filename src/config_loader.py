"""Configuration loading utilities with fallback mechanisms."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

from .config import Settings, Environment, get_settings, validate_settings


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """
    Configuration loader with fallback mechanisms and validation.
    """
    
    def __init__(self, config_paths: Optional[List[Union[str, Path]]] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_paths: List of paths to search for configuration files
        """
        self.config_paths = config_paths or [
            Path.cwd() / '.env',
            Path.cwd() / 'config' / '.env',
            Path.home() / '.voice-ai-agent' / '.env',
            Path('/etc/voice-ai-agent/.env')
        ]
        self._loaded_from: Optional[Path] = None
    
    def load_with_fallbacks(self) -> Settings:
        """
        Load configuration with fallback mechanisms.
        
        Returns:
            Settings: Loaded and validated settings
            
        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        # Try to load from each path in order
        for config_path in self.config_paths:
            config_path = Path(config_path)
            if config_path.exists() and config_path.is_file():
                try:
                    # Set environment variable to point to this config file
                    os.environ['ENV_FILE'] = str(config_path)
                    settings = Settings(_env_file=str(config_path))
                    self._loaded_from = config_path
                    
                    # Validate the loaded settings
                    validation_result = validate_settings()
                    if not validation_result['valid']:
                        raise ConfigurationError(f"Invalid configuration: {validation_result['error']}")
                    
                    return settings
                    
                except Exception as e:
                    print(f"Warning: Failed to load config from {config_path}: {e}", file=sys.stderr)
                    continue
        
        # If no config file found, try to load from environment variables only
        try:
            settings = Settings()
            validation_result = validate_settings()
            
            if not validation_result['valid']:
                raise ConfigurationError(f"Invalid configuration: {validation_result['error']}")
            
            self._loaded_from = None
            return settings
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def get_config_source(self) -> Optional[str]:
        """
        Get the source of the loaded configuration.
        
        Returns:
            Optional[str]: Path to config file or 'environment' if loaded from env vars
        """
        if self._loaded_from:
            return str(self._loaded_from)
        return 'environment_variables'
    
    def validate_required_for_environment(self, environment: Environment) -> List[str]:
        """
        Validate required configuration for specific environment.
        
        Args:
            environment: Target environment
            
        Returns:
            List[str]: List of missing required fields
        """
        settings = get_settings()
        missing_fields = []
        
        if environment == Environment.PRODUCTION:
            required_fields = {
                'sip_number': settings.sip_number,
                'sip_server': settings.sip_server,
                'sip_username': settings.sip_username,
                'sip_password': settings.sip_password,
                'livekit_url': settings.livekit_url,
                'livekit_api_key': settings.livekit_api_key,
                'livekit_api_secret': settings.livekit_api_secret,
                'deepgram_api_key': settings.deepgram_api_key,
                'openai_api_key': settings.openai_api_key,
                'cartesia_api_key': settings.cartesia_api_key,
            }
            
            for field_name, field_value in required_fields.items():
                if not field_value:
                    missing_fields.append(field_name)
        
        elif environment == Environment.STAGING:
            # Staging requires most production fields but can have some defaults
            required_fields = {
                'livekit_url': settings.livekit_url,
                'livekit_api_key': settings.livekit_api_key,
                'deepgram_api_key': settings.deepgram_api_key,
                'openai_api_key': settings.openai_api_key,
            }
            
            for field_name, field_value in required_fields.items():
                if not field_value:
                    missing_fields.append(field_name)
        
        return missing_fields


def load_configuration() -> Settings:
    """
    Load configuration with comprehensive error handling.
    
    Returns:
        Settings: Loaded and validated settings
        
    Raises:
        ConfigurationError: If configuration cannot be loaded
    """
    loader = ConfigLoader()
    
    try:
        settings = loader.load_with_fallbacks()
        
        # Log configuration source
        source = loader.get_config_source()
        print(f"✅ Configuration loaded from: {source}")
        
        # Validate for current environment
        missing_fields = loader.validate_required_for_environment(settings.environment)
        if missing_fields:
            if settings.environment == Environment.PRODUCTION:
                raise ConfigurationError(f"Missing required fields for production: {missing_fields}")
            else:
                print(f"⚠️  Warning: Missing optional fields for {settings.environment.value}: {missing_fields}")
        
        return settings
        
    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(f"Unexpected error loading configuration: {e}")


@contextmanager
def temporary_environment(**env_vars):
    """
    Temporarily set environment variables for testing.
    
    Args:
        **env_vars: Environment variables to set temporarily
    """
    old_environ = dict(os.environ)
    os.environ.update(env_vars)
    
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def create_default_config_file(path: Union[str, Path], environment: Environment = Environment.DEVELOPMENT) -> None:
    """
    Create a default configuration file.
    
    Args:
        path: Path where to create the config file
        environment: Target environment for the config
    """
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read the template
    template_path = Path(__file__).parent.parent / '.env.template'
    if not template_path.exists():
        raise ConfigurationError(f"Template file not found: {template_path}")
    
    # Copy template to target location
    with open(template_path, 'r') as template_file:
        template_content = template_file.read()
    
    # Modify for specific environment
    if environment == Environment.PRODUCTION:
        template_content = template_content.replace(
            'ENVIRONMENT=development',
            'ENVIRONMENT=production'
        )
        template_content = template_content.replace(
            'DEBUG=false',
            'DEBUG=false'
        )
    elif environment == Environment.STAGING:
        template_content = template_content.replace(
            'ENVIRONMENT=development',
            'ENVIRONMENT=staging'
        )
    
    with open(config_path, 'w') as config_file:
        config_file.write(template_content)
    
    print(f"✅ Created default config file: {config_path}")


def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of current configuration.
    
    Returns:
        Dict containing configuration summary
    """
    try:
        settings = get_settings()
        validation_result = validate_settings()
        
        return {
            'environment': settings.environment.value,
            'debug': settings.debug,
            'production_ready': settings.is_production,
            'services_configured': validation_result.get('required_services', {}),
            'database_type': 'sqlite' if settings.database_is_sqlite else 'postgresql',
            'logging': {
                'level': settings.log_level.value,
                'structured': settings.structured_logging,
                'file_enabled': bool(settings.log_file_path)
            },
            'security': {
                'cors_enabled': settings.enable_cors,
                'rate_limiting': settings.enable_rate_limiting,
                'secret_key_set': settings.secret_key != "your-secret-key-here-change-this-in-production"
            },
            'monitoring': {
                'metrics_enabled': settings.enable_metrics,
                'sentry_enabled': bool(settings.sentry_dsn)
            },
            'validation': validation_result
        }
    except Exception as e:
        return {
            'error': str(e),
            'valid': False
        }


def check_configuration_health() -> Dict[str, Any]:
    """
    Perform comprehensive configuration health check.
    
    Returns:
        Dict containing health check results
    """
    health_status = {
        'status': 'healthy',
        'checks': {},
        'warnings': [],
        'errors': []
    }
    
    try:
        settings = get_settings()
        
        # Check environment configuration
        if settings.environment == Environment.PRODUCTION:
            if settings.debug:
                health_status['warnings'].append("Debug mode enabled in production")
            
            if settings.secret_key == "your-secret-key-here-change-this-in-production":
                health_status['errors'].append("Default secret key used in production")
                health_status['status'] = 'unhealthy'
        
        # Check required services
        validation_result = validate_settings()
        services = validation_result.get('required_services', {})
        
        for service, configured in services.items():
            if configured:
                health_status['checks'][f'{service}_configured'] = 'ok'
            else:
                health_status['checks'][f'{service}_configured'] = 'missing'
                if settings.environment == Environment.PRODUCTION:
                    health_status['errors'].append(f"{service.upper()} not configured")
                    health_status['status'] = 'unhealthy'
                else:
                    health_status['warnings'].append(f"{service.upper()} not configured")
        
        # Check database configuration
        if settings.database_is_sqlite and settings.environment == Environment.PRODUCTION:
            health_status['warnings'].append("Using SQLite in production (consider PostgreSQL)")
        
        # Check performance settings
        if settings.max_response_latency > 2.0:
            health_status['warnings'].append(f"High response latency limit: {settings.max_response_latency}s")
        
        # Check security settings
        if not settings.enable_rate_limiting and settings.environment == Environment.PRODUCTION:
            health_status['warnings'].append("Rate limiting disabled in production")
        
        # Set final status
        if health_status['errors']:
            health_status['status'] = 'unhealthy'
        elif health_status['warnings']:
            health_status['status'] = 'degraded'
        
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['errors'].append(f"Configuration error: {e}")
    
    return health_status


def print_configuration_report():
    """Print a detailed configuration report."""
    print("\n🔧 Voice AI Agent Configuration Report")
    print("=" * 50)
    
    try:
        summary = get_config_summary()
        
        if 'error' in summary:
            print(f"❌ Configuration Error: {summary['error']}")
            return
        
        print(f"Environment: {summary['environment'].upper()}")
        print(f"Debug Mode: {'ON' if summary['debug'] else 'OFF'}")
        print(f"Production Ready: {'YES' if summary['production_ready'] else 'NO'}")
        
        print(f"\n📊 Services Configuration:")
        services = summary.get('services_configured', {})
        for service, configured in services.items():
            status = "✅" if configured else "❌"
            print(f"  {status} {service.upper()}: {'Configured' if configured else 'Missing'}")
        
        print(f"\n🗄️  Database: {summary['database_type'].upper()}")
        
        logging_info = summary.get('logging', {})
        print(f"\n📝 Logging:")
        print(f"  Level: {logging_info.get('level', 'Unknown')}")
        print(f"  Structured: {'ON' if logging_info.get('structured') else 'OFF'}")
        print(f"  File Logging: {'ON' if logging_info.get('file_enabled') else 'OFF'}")
        
        security_info = summary.get('security', {})
        print(f"\n🔒 Security:")
        print(f"  CORS: {'ON' if security_info.get('cors_enabled') else 'OFF'}")
        print(f"  Rate Limiting: {'ON' if security_info.get('rate_limiting') else 'OFF'}")
        print(f"  Secret Key: {'SET' if security_info.get('secret_key_set') else 'DEFAULT'}")
        
        monitoring_info = summary.get('monitoring', {})
        print(f"\n📈 Monitoring:")
        print(f"  Metrics: {'ON' if monitoring_info.get('metrics_enabled') else 'OFF'}")
        print(f"  Sentry: {'ON' if monitoring_info.get('sentry_enabled') else 'OFF'}")
        
        # Health check
        health = check_configuration_health()
        print(f"\n🏥 Configuration Health: {health['status'].upper()}")
        
        if health['warnings']:
            print("⚠️  Warnings:")
            for warning in health['warnings']:
                print(f"  - {warning}")
        
        if health['errors']:
            print("❌ Errors:")
            for error in health['errors']:
                print(f"  - {error}")
        
    except Exception as e:
        print(f"❌ Failed to generate configuration report: {e}")


if __name__ == "__main__":
    """CLI interface for configuration management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice AI Agent Configuration Manager")
    parser.add_argument('--report', action='store_true', help='Print configuration report')
    parser.add_argument('--validate', action='store_true', help='Validate configuration')
    parser.add_argument('--create-config', type=str, help='Create default config file at path')
    parser.add_argument('--environment', choices=['development', 'staging', 'production'], 
                       default='development', help='Target environment for config creation')
    
    args = parser.parse_args()
    
    if args.report:
        print_configuration_report()
    elif args.validate:
        try:
            settings = load_configuration()
            health = check_configuration_health()
            print(f"✅ Configuration is {health['status']}")
            if health['warnings']:
                for warning in health['warnings']:
                    print(f"⚠️  {warning}")
            if health['errors']:
                for error in health['errors']:
                    print(f"❌ {error}")
        except ConfigurationError as e:
            print(f"❌ Configuration validation failed: {e}")
            sys.exit(1)
    elif args.create_config:
        try:
            env = Environment(args.environment)
            create_default_config_file(args.create_config, env)
        except Exception as e:
            print(f"❌ Failed to create config file: {e}")
            sys.exit(1)
    else:
        parser.print_help()
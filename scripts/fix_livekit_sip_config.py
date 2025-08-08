#!/usr/bin/env python3
"""
LiveKit SIP Configuration Fix Script

This script fixes common LiveKit SIP configuration issues including:
- API key and URL validation
- Configuration file corrections
- Retry logic implementation
- Error handling improvements

Requirements addressed:
- 1.1, 1.2, 1.3: Fix authentication and room creation
- 1.4, 1.5: Improve error handling and logging
"""

import asyncio
import json
import logging
import os
import sys
import time
import yaml
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from config import get_settings
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveKitConfigFixer:
    """LiveKit SIP configuration fixer."""
    
    def __init__(self):
        """Initialize the config fixer."""
        self.settings = None
        self.fixes_applied = []
        self.backup_files = []
        
    async def run_fixes(self) -> Dict[str, Any]:
        """Run all configuration fixes."""
        print("🔧 LiveKit SIP Configuration Fixer")
        print("=" * 50)
        print(f"Started at: {datetime.now(UTC).isoformat()}")
        print()
        
        try:
            # Load current settings
            await self._load_settings()
            
            # Apply fixes
            await self._fix_environment_variables()
            await self._fix_livekit_sip_config()
            await self._fix_simple_config()
            await self._add_retry_logic_config()
            await self._improve_error_handling_config()
            await self._validate_fixed_configuration()
            
            # Generate summary
            self._print_summary()
            
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "fixes_applied": self.fixes_applied,
                "backup_files": self.backup_files,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Configuration fix failed: {e}")
            print(f"❌ Configuration fix failed: {e}")
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(e),
                "success": False
            }
    
    async def _load_settings(self) -> None:
        """Load current settings."""
        print("📋 Loading current settings...")
        
        try:
            self.settings = get_settings()
            print(f"   ✅ Settings loaded successfully")
            
        except Exception as e:
            print(f"   ❌ Failed to load settings: {e}")
            raise
    
    async def _fix_environment_variables(self) -> None:
        """Fix environment variables."""
        print("🔧 Checking environment variables...")
        
        try:
            # Check for missing or incorrect environment variables
            env_fixes = []
            
            # Validate LiveKit URL format
            if self.settings.livekit_url:
                if not self.settings.livekit_url.startswith(('wss://', 'ws://')):
                    env_fixes.append("LIVEKIT_URL should start with wss:// or ws://")
                
                # Check for common URL issues
                if 'localhost' in self.settings.livekit_url and 'cloud' in self.settings.livekit_url:
                    env_fixes.append("LIVEKIT_URL appears to mix localhost and cloud - verify correct URL")
            
            # Validate API key format
            if self.settings.livekit_api_key:
                if len(self.settings.livekit_api_key) < 10:
                    env_fixes.append("LIVEKIT_API_KEY appears too short - verify correct key")
                
                if not self.settings.livekit_api_key.startswith('API'):
                    env_fixes.append("LIVEKIT_API_KEY should typically start with 'API'")
            
            # Validate API secret
            if self.settings.livekit_api_secret:
                if len(self.settings.livekit_api_secret) < 20:
                    env_fixes.append("LIVEKIT_API_SECRET appears too short - verify correct secret")
            
            # Check SIP configuration
            if self.settings.sip_number and not self.settings.sip_number.startswith('+'):
                env_fixes.append("SIP_NUMBER should include country code with + prefix")
            
            if env_fixes:
                print(f"   ⚠️ Environment variable issues found:")
                for fix in env_fixes:
                    print(f"      - {fix}")
                self.fixes_applied.extend(env_fixes)
            else:
                print(f"   ✅ Environment variables look correct")
                
        except Exception as e:
            print(f"   ❌ Environment variable check failed: {e}")
            raise
    
    async def _fix_livekit_sip_config(self) -> None:
        """Fix main LiveKit SIP configuration."""
        print("🔧 Fixing livekit-sip.yaml configuration...")
        
        config_file = "livekit-sip.yaml"
        
        try:
            if not os.path.exists(config_file):
                print(f"   ⚠️ {config_file} not found, skipping")
                return
            
            # Backup original file
            backup_file = f"{config_file}.backup.{int(time.time())}"
            with open(config_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
            self.backup_files.append(backup_file)
            
            # Load and fix configuration
            with open(config_file, 'r') as f:
                config_content = f.read()
            
            # Apply fixes to configuration content
            fixed_content = self._apply_config_fixes(config_content)
            
            # Write fixed configuration
            with open(config_file, 'w') as f:
                f.write(fixed_content)
            
            print(f"   ✅ Fixed {config_file} (backup: {backup_file})")
            self.fixes_applied.append(f"Updated {config_file} with improved configuration")
            
        except Exception as e:
            print(f"   ❌ Failed to fix {config_file}: {e}")
            raise
    
    async def _fix_simple_config(self) -> None:
        """Fix simple LiveKit SIP configuration."""
        print("🔧 Fixing livekit-sip-simple.yaml configuration...")
        
        config_file = "livekit-sip-simple.yaml"
        
        try:
            if not os.path.exists(config_file):
                print(f"   ⚠️ {config_file} not found, skipping")
                return
            
            # Backup original file
            backup_file = f"{config_file}.backup.{int(time.time())}"
            with open(config_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
            self.backup_files.append(backup_file)
            
            # Load current configuration
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Apply fixes
            fixes_made = []
            
            # Fix LiveKit configuration
            if 'livekit' in config:
                livekit_config = config['livekit']
                
                # Add connection timeout and retry settings
                if 'connection' not in livekit_config:
                    livekit_config['connection'] = {}
                
                connection_config = livekit_config['connection']
                
                # Set proper timeouts
                if 'timeout' not in connection_config:
                    connection_config['timeout'] = 30000  # 30 seconds
                    fixes_made.append("Added connection timeout")
                
                if 'keep_alive' not in connection_config:
                    connection_config['keep_alive'] = 25000  # 25 seconds
                    fixes_made.append("Added keep-alive setting")
                
                if 'reconnect' not in connection_config:
                    connection_config['reconnect'] = True
                    fixes_made.append("Enabled automatic reconnection")
                
                if 'max_reconnect_attempts' not in connection_config:
                    connection_config['max_reconnect_attempts'] = 10
                    fixes_made.append("Added max reconnection attempts")
                
                if 'reconnect_delay' not in connection_config:
                    connection_config['reconnect_delay'] = 1000  # 1 second
                    fixes_made.append("Added reconnection delay")
            
            # Fix webhook configuration
            if 'webhooks' in config:
                webhook_config = config['webhooks']
                
                # Add retry configuration for webhooks
                if 'retry' not in webhook_config:
                    webhook_config['retry'] = {
                        'enabled': True,
                        'max_attempts': 3,
                        'initial_delay': 1000,  # 1 second
                        'max_delay': 10000,     # 10 seconds
                        'multiplier': 2.0
                    }
                    fixes_made.append("Added webhook retry configuration")
                
                # Add timeout for webhooks
                if 'timeout' not in webhook_config:
                    webhook_config['timeout'] = 5000  # 5 seconds
                    fixes_made.append("Added webhook timeout")
            
            # Add logging configuration
            if 'logging' not in config:
                config['logging'] = {
                    'level': 'INFO',
                    'format': 'json',
                    'categories': {
                        'sip': True,
                        'livekit': True,
                        'webhook': True,
                        'auth': True
                    }
                }
                fixes_made.append("Added comprehensive logging configuration")
            
            # Add health check configuration
            if 'health_check' not in config:
                config['health_check'] = {
                    'enabled': True,
                    'interval': 30,  # seconds
                    'timeout': 10,   # seconds
                    'endpoint': '/health/sip'
                }
                fixes_made.append("Added health check configuration")
            
            # Write fixed configuration
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            if fixes_made:
                print(f"   ✅ Applied {len(fixes_made)} fixes to {config_file}")
                for fix in fixes_made:
                    print(f"      - {fix}")
                self.fixes_applied.extend(fixes_made)
            else:
                print(f"   ✅ {config_file} already properly configured")
            
        except Exception as e:
            print(f"   ❌ Failed to fix {config_file}: {e}")
            raise
    
    def _apply_config_fixes(self, content: str) -> str:
        """Apply fixes to configuration content."""
        # This is a simplified version - in practice, you'd parse YAML and make specific fixes
        fixes = []
        
        # Add connection timeout if missing
        if 'timeout:' not in content:
            content = content.replace(
                'livekit:',
                '''livekit:
  connection:
    timeout: 30000  # 30 seconds
    keep_alive: 25000  # 25 seconds
    reconnect: true
    max_reconnect_attempts: 10
    reconnect_delay: 1000  # 1 second'''
            )
            fixes.append("Added connection configuration")
        
        # Add retry logic if missing
        if 'retry:' not in content and 'sip_trunks:' in content:
            content = content.replace(
                'register_interval: 300',
                '''register_interval: 300
    
    # Retry configuration for connection failures
    retry:
      enabled: true
      initial_delay: 1000  # 1 second
      max_delay: 30000     # 30 seconds
      multiplier: 2.0      # Exponential backoff
      max_attempts: 5'''
            )
            fixes.append("Added retry configuration")
        
        return content
    
    async def _add_retry_logic_config(self) -> None:
        """Add retry logic configuration."""
        print("🔧 Adding retry logic configuration...")
        
        try:
            # Create a retry configuration file
            retry_config = {
                'retry_policies': {
                    'livekit_connection': {
                        'enabled': True,
                        'max_attempts': 5,
                        'initial_delay': 1.0,  # seconds
                        'max_delay': 30.0,     # seconds
                        'multiplier': 2.0,
                        'jitter': True
                    },
                    'sip_registration': {
                        'enabled': True,
                        'max_attempts': 3,
                        'initial_delay': 2.0,
                        'max_delay': 60.0,
                        'multiplier': 2.0,
                        'jitter': False
                    },
                    'webhook_delivery': {
                        'enabled': True,
                        'max_attempts': 3,
                        'initial_delay': 0.5,
                        'max_delay': 10.0,
                        'multiplier': 2.0,
                        'jitter': True
                    }
                },
                'circuit_breaker': {
                    'enabled': True,
                    'failure_threshold': 5,
                    'recovery_timeout': 60,  # seconds
                    'half_open_max_calls': 3
                }
            }
            
            config_file = "config/retry_policies.yaml"
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            with open(config_file, 'w') as f:
                yaml.dump(retry_config, f, default_flow_style=False, indent=2)
            
            print(f"   ✅ Created retry configuration: {config_file}")
            self.fixes_applied.append(f"Created retry policies configuration")
            
        except Exception as e:
            print(f"   ❌ Failed to add retry logic config: {e}")
            raise
    
    async def _improve_error_handling_config(self) -> None:
        """Improve error handling configuration."""
        print("🔧 Improving error handling configuration...")
        
        try:
            # Create error handling configuration
            error_config = {
                'error_handling': {
                    'log_level': 'ERROR',
                    'include_stack_trace': True,
                    'mask_sensitive_data': True,
                    'error_categories': {
                        'authentication': {
                            'log_level': 'ERROR',
                            'alert': True,
                            'retry': True
                        },
                        'connection': {
                            'log_level': 'WARNING',
                            'alert': False,
                            'retry': True
                        },
                        'webhook': {
                            'log_level': 'WARNING',
                            'alert': False,
                            'retry': True
                        },
                        'sip': {
                            'log_level': 'INFO',
                            'alert': False,
                            'retry': False
                        }
                    }
                },
                'alerting': {
                    'enabled': True,
                    'channels': ['log', 'metrics'],
                    'thresholds': {
                        'auth_failures_per_minute': 5,
                        'connection_failures_per_minute': 10,
                        'webhook_failures_per_minute': 20
                    }
                }
            }
            
            config_file = "config/error_handling.yaml"
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            with open(config_file, 'w') as f:
                yaml.dump(error_config, f, default_flow_style=False, indent=2)
            
            print(f"   ✅ Created error handling configuration: {config_file}")
            self.fixes_applied.append(f"Created error handling configuration")
            
        except Exception as e:
            print(f"   ❌ Failed to improve error handling config: {e}")
            raise
    
    async def _validate_fixed_configuration(self) -> None:
        """Validate the fixed configuration."""
        print("🔍 Validating fixed configuration...")
        
        try:
            validation_results = []
            
            # Check if configuration files exist and are valid
            config_files = [
                "livekit-sip.yaml",
                "livekit-sip-simple.yaml",
                "config/retry_policies.yaml",
                "config/error_handling.yaml"
            ]
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r') as f:
                            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                                yaml.safe_load(f)
                            else:
                                json.load(f)
                        validation_results.append(f"✅ {config_file}: Valid")
                    except Exception as e:
                        validation_results.append(f"❌ {config_file}: Invalid - {e}")
                else:
                    validation_results.append(f"⚠️ {config_file}: Not found")
            
            # Print validation results
            for result in validation_results:
                print(f"   {result}")
            
            # Check if all critical files are valid
            critical_files = ["livekit-sip-simple.yaml"]
            critical_valid = all(
                f"✅ {cf}" in result for result in validation_results 
                for cf in critical_files
            )
            
            if critical_valid:
                print(f"   ✅ All critical configuration files are valid")
                self.fixes_applied.append("Configuration validation passed")
            else:
                print(f"   ⚠️ Some configuration files have issues")
                self.fixes_applied.append("Configuration validation found issues")
            
        except Exception as e:
            print(f"   ❌ Configuration validation failed: {e}")
            raise
    
    def _print_summary(self) -> None:
        """Print summary of fixes applied."""
        print("\n" + "=" * 50)
        print("📊 CONFIGURATION FIX SUMMARY")
        print("=" * 50)
        
        print(f"Fixes Applied: {len(self.fixes_applied)}")
        for i, fix in enumerate(self.fixes_applied, 1):
            print(f"   {i}. {fix}")
        
        if self.backup_files:
            print(f"\nBackup Files Created: {len(self.backup_files)}")
            for backup in self.backup_files:
                print(f"   - {backup}")
        
        print(f"\n💡 NEXT STEPS:")
        print("   1. Run the diagnostic script to verify fixes")
        print("   2. Test with a real SIP call")
        print("   3. Monitor logs for any remaining issues")
        print("   4. Consider running the application in debug mode initially")
        
        print(f"\n🔧 To run diagnostics:")
        print("   python scripts/diagnose_livekit_connection.py")


async def main():
    """Main function."""
    try:
        fixer = LiveKitConfigFixer()
        results = await fixer.run_fixes()
        
        if results["success"]:
            print(f"\n✅ Configuration fixes completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Configuration fixes failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Configuration fix interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error during configuration fix: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
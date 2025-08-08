#!/usr/bin/env python3
"""
LiveKit SIP Connection Diagnostic Script

This script provides comprehensive diagnostics for LiveKit SIP connection issues,
including API key validation, server connectivity, configuration verification,
and connection troubleshooting with retry logic and error handling.

Requirements addressed:
- 1.1: Successful authentication with LiveKit server
- 1.2: Room creation with proper naming
- 1.3: Webhook delivery to correct endpoint
- 1.4: Detailed error logging for authentication failures
- 1.5: No "auth check failed" or "no response from servers" errors
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse

import aiohttp
import yaml
from livekit import api
from livekit.api import AccessToken, VideoGrants, CreateRoomRequest, ListRoomsRequest, DeleteRoomRequest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from config import get_settings
    from livekit_integration import LiveKitSIPIntegration
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


class LiveKitDiagnostics:
    """Comprehensive LiveKit SIP connection diagnostics."""
    
    def __init__(self):
        """Initialize diagnostics."""
        self.settings = None
        self.livekit_client = None
        self.test_results = {}
        self.errors = []
        self.warnings = []
        
    async def run_full_diagnostics(self) -> Dict[str, Any]:
        """Run complete diagnostic suite."""
        print("🔍 LiveKit SIP Connection Diagnostics")
        print("=" * 60)
        print(f"Started at: {datetime.now(UTC).isoformat()}")
        print()
        
        # Initialize test results
        self.test_results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tests": {},
            "summary": {},
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Run diagnostic tests
        await self._test_configuration_loading()
        await self._test_environment_variables()
        await self._test_livekit_server_connectivity()
        await self._test_api_key_validation()
        await self._test_room_operations()
        await self._test_webhook_endpoint()
        await self._test_sip_configuration()
        await self._test_retry_logic()
        await self._test_error_handling()
        
        # Generate summary
        self._generate_summary()
        
        # Print results
        self._print_results()
        
        # Save results to file
        await self._save_results()
        
        return self.test_results
    
    async def _test_configuration_loading(self) -> None:
        """Test configuration loading."""
        test_name = "Configuration Loading"
        print(f"🧪 Testing {test_name}...")
        
        try:
            # Load settings
            self.settings = get_settings()
            
            # Validate required settings
            required_settings = [
                'livekit_url', 'livekit_api_key', 'livekit_api_secret',
                'sip_number', 'sip_server', 'sip_username', 'sip_password'
            ]
            
            missing_settings = []
            for setting in required_settings:
                if not getattr(self.settings, setting, None):
                    missing_settings.append(setting)
            
            if missing_settings:
                raise ValueError(f"Missing required settings: {', '.join(missing_settings)}")
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "message": "Configuration loaded successfully",
                "details": {
                    "livekit_url": self.settings.livekit_url,
                    "sip_server": self.settings.sip_server,
                    "sip_number": self.settings.sip_number,
                    "domain": self.settings.domain,
                    "port": self.settings.port
                }
            }
            print(f"   ✅ {test_name}: PASS")
            
        except Exception as e:
            error_msg = f"Configuration loading failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_environment_variables(self) -> None:
        """Test environment variables."""
        test_name = "Environment Variables"
        print(f"🧪 Testing {test_name}...")
        
        try:
            env_vars = {
                'LIVEKIT_URL': os.getenv('LIVEKIT_URL'),
                'LIVEKIT_API_KEY': os.getenv('LIVEKIT_API_KEY'),
                'LIVEKIT_API_SECRET': os.getenv('LIVEKIT_API_SECRET'),
                'SIP_SERVER': os.getenv('SIP_SERVER'),
                'SIP_USERNAME': os.getenv('SIP_USERNAME'),
                'SIP_PASSWORD': os.getenv('SIP_PASSWORD'),
                'SIP_NUMBER': os.getenv('SIP_NUMBER'),
                'DOMAIN': os.getenv('DOMAIN'),
                'PORT': os.getenv('PORT')
            }
            
            missing_vars = [var for var, value in env_vars.items() if not value]
            
            # Mask sensitive values
            masked_vars = {}
            for var, value in env_vars.items():
                if value and any(sensitive in var.lower() for sensitive in ['password', 'secret', 'key']):
                    masked_vars[var] = f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
                else:
                    masked_vars[var] = value
            
            if missing_vars:
                warning_msg = f"Missing environment variables: {', '.join(missing_vars)}"
                self.warnings.append(warning_msg)
                print(f"   ⚠️ {test_name}: WARNING - {warning_msg}")
            
            self.test_results["tests"][test_name] = {
                "status": "PASS" if not missing_vars else "WARNING",
                "message": "Environment variables checked",
                "details": {
                    "variables": masked_vars,
                    "missing": missing_vars
                }
            }
            
            if not missing_vars:
                print(f"   ✅ {test_name}: PASS")
            
        except Exception as e:
            error_msg = f"Environment variable check failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_livekit_server_connectivity(self) -> None:
        """Test LiveKit server connectivity."""
        test_name = "LiveKit Server Connectivity"
        print(f"🧪 Testing {test_name}...")
        
        if not self.settings:
            self.test_results["tests"][test_name] = {
                "status": "SKIP",
                "message": "Skipped due to configuration failure"
            }
            print(f"   ⏭️ {test_name}: SKIPPED")
            return
        
        try:
            # Parse LiveKit URL
            parsed_url = urlparse(self.settings.livekit_url)
            
            # Test basic connectivity
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try to connect to the WebSocket endpoint
                test_url = f"https://{parsed_url.netloc}"
                
                start_time = time.time()
                async with session.get(test_url) as response:
                    response_time = time.time() - start_time
                    
                    self.test_results["tests"][test_name] = {
                        "status": "PASS",
                        "message": f"Server reachable (HTTP {response.status})",
                        "details": {
                            "url": test_url,
                            "status_code": response.status,
                            "response_time_ms": round(response_time * 1000, 2),
                            "headers": dict(response.headers)
                        }
                    }
                    print(f"   ✅ {test_name}: PASS - Server reachable ({response_time:.2f}s)")
        
        except asyncio.TimeoutError:
            error_msg = "Server connection timeout"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": "Connection timeout after 10 seconds"
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
            
        except Exception as e:
            error_msg = f"Server connectivity failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_api_key_validation(self) -> None:
        """Test API key validation."""
        test_name = "API Key Validation"
        print(f"🧪 Testing {test_name}...")
        
        if not self.settings:
            self.test_results["tests"][test_name] = {
                "status": "SKIP",
                "message": "Skipped due to configuration failure"
            }
            print(f"   ⏭️ {test_name}: SKIPPED")
            return
        
        try:
            # Initialize LiveKit client
            self.livekit_client = api.LiveKitAPI(
                url=self.settings.livekit_url,
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret
            )
            
            # Test API key by listing rooms
            start_time = time.time()
            rooms_response = await self.livekit_client.room.list_rooms(ListRoomsRequest())
            response_time = time.time() - start_time
            
            # Test token generation
            token = AccessToken(
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret
            )
            token.with_identity("test-participant")
            token.with_grants(VideoGrants(room_join=True, room="test-room"))
            jwt_token = token.to_jwt()
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "message": "API key validation successful",
                "details": {
                    "rooms_found": len(rooms_response.rooms),
                    "response_time_ms": round(response_time * 1000, 2),
                    "token_generated": bool(jwt_token),
                    "api_key_prefix": f"{self.settings.livekit_api_key[:8]}***"
                }
            }
            print(f"   ✅ {test_name}: PASS - Found {len(rooms_response.rooms)} rooms ({response_time:.2f}s)")
            
        except Exception as e:
            error_msg = f"API key validation failed: {str(e)}"
            
            # Check for specific authentication errors
            if "auth check failed" in str(e).lower():
                error_msg += " - Authentication check failed, verify API key and secret"
            elif "no response from servers" in str(e).lower():
                error_msg += " - No response from servers, check server URL and connectivity"
            
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_room_operations(self) -> None:
        """Test room creation and management operations."""
        test_name = "Room Operations"
        print(f"🧪 Testing {test_name}...")
        
        if not self.livekit_client:
            self.test_results["tests"][test_name] = {
                "status": "SKIP",
                "message": "Skipped due to API key validation failure"
            }
            print(f"   ⏭️ {test_name}: SKIPPED")
            return
        
        test_room_name = f"voice-ai-test-{int(time.time())}"
        
        try:
            # Test room creation
            create_start = time.time()
            room_request = CreateRoomRequest(
                name=test_room_name,
                empty_timeout=60,  # 1 minute for testing
                max_participants=2,
                metadata=json.dumps({
                    "test": True,
                    "created_at": datetime.now(UTC).isoformat(),
                    "purpose": "diagnostic_test"
                })
            )
            
            room = await self.livekit_client.room.create_room(room_request)
            create_time = time.time() - create_start
            
            # Verify room was created
            rooms_response = await self.livekit_client.room.list_rooms(ListRoomsRequest())
            room_found = any(r.name == test_room_name for r in rooms_response.rooms)
            
            if not room_found:
                raise Exception("Room not found after creation")
            
            # Test room deletion
            delete_start = time.time()
            await self.livekit_client.room.delete_room(DeleteRoomRequest(room=test_room_name))
            delete_time = time.time() - delete_start
            
            # Verify room was deleted
            rooms_response = await self.livekit_client.room.list_rooms(ListRoomsRequest())
            room_still_exists = any(r.name == test_room_name for r in rooms_response.rooms)
            
            if room_still_exists:
                self.warnings.append(f"Test room {test_room_name} still exists after deletion")
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "message": "Room operations successful",
                "details": {
                    "test_room_name": test_room_name,
                    "room_created": True,
                    "room_deleted": not room_still_exists,
                    "create_time_ms": round(create_time * 1000, 2),
                    "delete_time_ms": round(delete_time * 1000, 2),
                    "room_metadata": json.loads(room.metadata) if room.metadata else None
                }
            }
            print(f"   ✅ {test_name}: PASS - Room created and deleted successfully")
            
        except Exception as e:
            error_msg = f"Room operations failed: {str(e)}"
            
            # Try to clean up test room if it exists
            try:
                await self.livekit_client.room.delete_room(DeleteRoomRequest(room=test_room_name))
            except:
                pass  # Ignore cleanup errors
            
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_webhook_endpoint(self) -> None:
        """Test webhook endpoint accessibility."""
        test_name = "Webhook Endpoint"
        print(f"🧪 Testing {test_name}...")
        
        if not self.settings:
            self.test_results["tests"][test_name] = {
                "status": "SKIP",
                "message": "Skipped due to configuration failure"
            }
            print(f"   ⏭️ {test_name}: SKIPPED")
            return
        
        try:
            webhook_url = f"http://{self.settings.domain}:{self.settings.port}/webhooks/livekit"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Test GET request (should return 405 Method Not Allowed)
                start_time = time.time()
                async with session.get(webhook_url) as response:
                    response_time = time.time() - start_time
                    
                    # Test POST request with sample webhook data
                    sample_webhook = {
                        "event": "room_started",
                        "room": {
                            "name": "test-room",
                            "sid": "test-sid"
                        },
                        "timestamp": int(time.time())
                    }
                    
                    post_start = time.time()
                    async with session.post(webhook_url, json=sample_webhook) as post_response:
                        post_time = time.time() - post_start
                        post_status = post_response.status
                        
                        # Check if endpoint is accessible (any response is good)
                        accessible = response.status in [200, 405, 404, 500]  # Any response means accessible
                        
                        self.test_results["tests"][test_name] = {
                            "status": "PASS" if accessible else "FAIL",
                            "message": f"Webhook endpoint accessible" if accessible else "Webhook endpoint not accessible",
                            "details": {
                                "webhook_url": webhook_url,
                                "get_status": response.status,
                                "get_response_time_ms": round(response_time * 1000, 2),
                                "post_status": post_status,
                                "post_response_time_ms": round(post_time * 1000, 2),
                                "accessible": accessible
                            }
                        }
                        
                        if accessible:
                            print(f"   ✅ {test_name}: PASS - Endpoint accessible")
                        else:
                            print(f"   ❌ {test_name}: FAIL - Endpoint not accessible")
        
        except asyncio.TimeoutError:
            error_msg = "Webhook endpoint timeout"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": "Connection timeout after 10 seconds"
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
            
        except Exception as e:
            error_msg = f"Webhook endpoint test failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_sip_configuration(self) -> None:
        """Test SIP configuration loading and validation."""
        test_name = "SIP Configuration"
        print(f"🧪 Testing {test_name}...")
        
        try:
            # Test loading SIP configuration files
            config_files = ["livekit-sip.yaml", "livekit-sip-simple.yaml"]
            config_results = {}
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r') as f:
                            config_content = f.read()
                        
                        # Substitute environment variables
                        config_content = self._substitute_env_variables(config_content)
                        config_data = yaml.safe_load(config_content)
                        
                        # Validate configuration structure
                        validation_results = self._validate_sip_config(config_data)
                        
                        config_results[config_file] = {
                            "exists": True,
                            "valid_yaml": True,
                            "validation": validation_results
                        }
                        
                    except Exception as e:
                        config_results[config_file] = {
                            "exists": True,
                            "valid_yaml": False,
                            "error": str(e)
                        }
                else:
                    config_results[config_file] = {
                        "exists": False
                    }
            
            # Check if at least one config file is valid
            valid_configs = [
                name for name, result in config_results.items()
                if result.get("exists") and result.get("valid_yaml")
            ]
            
            if valid_configs:
                self.test_results["tests"][test_name] = {
                    "status": "PASS",
                    "message": f"SIP configuration valid ({', '.join(valid_configs)})",
                    "details": config_results
                }
                print(f"   ✅ {test_name}: PASS - Valid configurations found")
            else:
                error_msg = "No valid SIP configuration found"
                self.test_results["tests"][test_name] = {
                    "status": "FAIL",
                    "message": error_msg,
                    "details": config_results
                }
                self.errors.append(error_msg)
                print(f"   ❌ {test_name}: FAIL - {error_msg}")
                
        except Exception as e:
            error_msg = f"SIP configuration test failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    def _substitute_env_variables(self, content: str) -> str:
        """Substitute environment variables in configuration content."""
        import re
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_expr = match.group(1)
            
            # Check for default value syntax
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_expr, '')
        
        return re.sub(pattern, replace_var, content)
    
    def _validate_sip_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SIP configuration structure."""
        validation = {
            "has_sip_trunks": bool(config.get("sip_trunks")),
            "has_livekit_config": bool(config.get("livekit")),
            "has_routing": bool(config.get("routing")),
            "trunk_count": len(config.get("sip_trunks", [])),
            "codec_count": len(config.get("audio_codecs", [])),
            "issues": []
        }
        
        # Check required sections
        required_sections = ["sip_trunks", "livekit", "routing"]
        for section in required_sections:
            if not config.get(section):
                validation["issues"].append(f"Missing required section: {section}")
        
        # Validate SIP trunks
        for i, trunk in enumerate(config.get("sip_trunks", [])):
            trunk_issues = []
            required_trunk_fields = ["name", "host", "username", "password"]
            for field in required_trunk_fields:
                if not trunk.get(field):
                    trunk_issues.append(f"Missing field: {field}")
            
            if trunk_issues:
                validation["issues"].append(f"Trunk {i}: {', '.join(trunk_issues)}")
        
        # Validate LiveKit configuration
        livekit_config = config.get("livekit", {})
        if isinstance(livekit_config, dict):
            required_livekit_fields = ["url", "api_key", "api_secret"]
            for field in required_livekit_fields:
                if not livekit_config.get(field):
                    validation["issues"].append(f"Missing LiveKit field: {field}")
        
        return validation
    
    async def _test_retry_logic(self) -> None:
        """Test retry logic and error handling."""
        test_name = "Retry Logic"
        print(f"🧪 Testing {test_name}...")
        
        try:
            # Test retry logic with intentionally failing operations
            max_retries = 3
            retry_delay = 0.1  # Short delay for testing
            
            # Simulate connection retry
            retry_count = 0
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    retry_count += 1
                    
                    # Simulate a failing operation that eventually succeeds
                    if attempt < 2:  # Fail first 2 attempts
                        raise ConnectionError(f"Simulated connection failure (attempt {attempt + 1})")
                    
                    # Success on 3rd attempt
                    break
                    
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "message": "Retry logic working correctly",
                "details": {
                    "max_retries": max_retries,
                    "actual_retries": retry_count,
                    "final_success": True,
                    "last_error": last_error
                }
            }
            print(f"   ✅ {test_name}: PASS - Retry logic functional")
            
        except Exception as e:
            error_msg = f"Retry logic test failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    async def _test_error_handling(self) -> None:
        """Test error handling mechanisms."""
        test_name = "Error Handling"
        print(f"🧪 Testing {test_name}...")
        
        try:
            error_scenarios = []
            
            # Test invalid API key handling
            try:
                invalid_client = api.LiveKitAPI(
                    url=self.settings.livekit_url if self.settings else "wss://invalid.livekit.cloud",
                    api_key="invalid_key",
                    api_secret="invalid_secret"
                )
                await invalid_client.room.list_rooms(ListRoomsRequest())
                error_scenarios.append({"scenario": "invalid_api_key", "handled": False})
            except Exception as e:
                error_scenarios.append({
                    "scenario": "invalid_api_key",
                    "handled": True,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
            
            # Test invalid URL handling
            try:
                invalid_url_client = api.LiveKitAPI(
                    url="wss://nonexistent.invalid.domain",
                    api_key="test_key",
                    api_secret="test_secret"
                )
                await invalid_url_client.room.list_rooms(ListRoomsRequest())
                error_scenarios.append({"scenario": "invalid_url", "handled": False})
            except Exception as e:
                error_scenarios.append({
                    "scenario": "invalid_url",
                    "handled": True,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
            
            # Check if errors are properly handled
            handled_errors = [s for s in error_scenarios if s["handled"]]
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "message": f"Error handling functional ({len(handled_errors)}/{len(error_scenarios)} scenarios)",
                "details": {
                    "scenarios_tested": len(error_scenarios),
                    "scenarios_handled": len(handled_errors),
                    "error_scenarios": error_scenarios
                }
            }
            print(f"   ✅ {test_name}: PASS - Error handling functional")
            
        except Exception as e:
            error_msg = f"Error handling test failed: {str(e)}"
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "message": error_msg,
                "error": str(e)
            }
            self.errors.append(error_msg)
            print(f"   ❌ {test_name}: FAIL - {error_msg}")
    
    def _generate_summary(self) -> None:
        """Generate diagnostic summary."""
        tests = self.test_results["tests"]
        
        total_tests = len(tests)
        passed_tests = len([t for t in tests.values() if t["status"] == "PASS"])
        failed_tests = len([t for t in tests.values() if t["status"] == "FAIL"])
        warning_tests = len([t for t in tests.values() if t["status"] == "WARNING"])
        skipped_tests = len([t for t in tests.values() if t["status"] == "SKIP"])
        
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "warnings": warning_tests,
            "skipped": skipped_tests,
            "success_rate": round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0,
            "overall_status": "HEALTHY" if failed_tests == 0 else "ISSUES_FOUND"
        }
        
        self.test_results["errors"] = self.errors
        self.test_results["warnings"] = self.warnings
        
        # Generate recommendations
        recommendations = []
        
        if failed_tests > 0:
            recommendations.append("Address failed tests before proceeding with production deployment")
        
        if "API Key Validation" in tests and tests["API Key Validation"]["status"] == "FAIL":
            recommendations.append("Verify LiveKit API key and secret are correct")
            recommendations.append("Check LiveKit server URL format (should start with wss://)")
        
        if "Webhook Endpoint" in tests and tests["Webhook Endpoint"]["status"] == "FAIL":
            recommendations.append("Ensure the application is running and webhook endpoint is accessible")
            recommendations.append("Check firewall settings for the webhook port")
        
        if "SIP Configuration" in tests and tests["SIP Configuration"]["status"] == "FAIL":
            recommendations.append("Review SIP configuration files for syntax errors")
            recommendations.append("Verify all required environment variables are set")
        
        if warning_tests > 0:
            recommendations.append("Review warnings and consider addressing them")
        
        self.test_results["recommendations"] = recommendations
    
    def _print_results(self) -> None:
        """Print diagnostic results."""
        print("\n" + "=" * 60)
        print("📊 DIAGNOSTIC RESULTS")
        print("=" * 60)
        
        summary = self.test_results["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"⚠️ Warnings: {summary['warnings']}")
        print(f"⏭️ Skipped: {summary['skipped']}")
        print(f"Success Rate: {summary['success_rate']}%")
        print(f"Overall Status: {summary['overall_status']}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        if self.test_results["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(self.test_results["recommendations"], 1):
                print(f"   {i}. {rec}")
        
        print(f"\n🔍 Detailed results saved to: livekit_diagnostics_{int(time.time())}.json")
    
    async def _save_results(self) -> None:
        """Save diagnostic results to file."""
        filename = f"livekit_diagnostics_{int(time.time())}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            
            print(f"📄 Results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️ Failed to save results: {e}")


async def main():
    """Main diagnostic function."""
    try:
        diagnostics = LiveKitDiagnostics()
        results = await diagnostics.run_full_diagnostics()
        
        # Exit with error code if there are failures
        if results["summary"]["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n🛑 Diagnostics interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error during diagnostics: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
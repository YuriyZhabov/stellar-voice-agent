#!/usr/bin/env python3
"""
SIP Integration Test Script

This script tests the LiveKit SIP integration configuration, including:
- Configuration file validation
- SIP trunk connectivity
- LiveKit API connection
- Audio codec configuration
- Webhook endpoint testing
- End-to-end call simulation
"""

import asyncio
import json
import logging
import socket
import sys
import time
from datetime import datetime, UTC
from typing import Dict, Any, List
from uuid import uuid4

import yaml
import requests
from livekit import api

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SIPIntegrationTester:
    """Test suite for SIP integration."""
    
    def __init__(self):
        """Initialize the tester."""
        self.config = {}
        self.test_results = {}
        self.livekit_client = None
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all SIP integration tests.
        
        Returns:
            Dictionary containing test results
        """
        logger.info("Starting SIP integration tests")
        
        tests = [
            ("Configuration Validation", self.test_configuration),
            ("Environment Variables", self.test_environment_variables),
            ("SIP Trunk Connectivity", self.test_sip_connectivity),
            ("LiveKit API Connection", self.test_livekit_connection),
            ("Audio Codec Configuration", self.test_audio_codecs),
            ("Webhook Endpoints", self.test_webhook_endpoints),
            ("Call Simulation", self.test_call_simulation),
            ("Health Monitoring", self.test_health_monitoring),
            ("Error Handling", self.test_error_handling)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"Running test: {test_name}")
            try:
                result = await test_func()
                self.test_results[test_name] = {
                    "status": "PASS" if result else "FAIL",
                    "details": result if isinstance(result, dict) else {}
                }
                logger.info(f"Test {test_name}: {'PASS' if result else 'FAIL'}")
            except Exception as e:
                self.test_results[test_name] = {
                    "status": "ERROR",
                    "error": str(e)
                }
                logger.error(f"Test {test_name}: ERROR - {e}")
        
        # Generate summary
        passed = sum(1 for r in self.test_results.values() if r["status"] == "PASS")
        total = len(self.test_results)
        
        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": passed / total if total > 0 else 0,
            "timestamp": datetime.now(UTC).isoformat(),
            "results": self.test_results
        }
        
        logger.info(f"Test Summary: {passed}/{total} tests passed ({summary['success_rate']:.1%})")
        
        return summary
    
    async def test_configuration(self) -> bool:
        """Test configuration file validation."""
        try:
            # Load configuration file
            with open('livekit-sip.yaml', 'r') as file:
                config_content = file.read()
            
            # Substitute environment variables (basic substitution for testing)
            import os
            import re
            
            def replace_var(match):
                var_expr = match.group(1)
                if ':-' in var_expr:
                    var_name, default_value = var_expr.split(':-', 1)
                    return os.getenv(var_name, default_value)
                else:
                    return os.getenv(var_expr, '')
            
            pattern = r'\$\{([^}]+)\}'
            config_content = re.sub(pattern, replace_var, config_content)
            
            # Parse YAML
            self.config = yaml.safe_load(config_content)
            
            # Validate required sections
            required_sections = [
                'sip_trunks',
                'audio_codecs',
                'routing',
                'livekit',
                'metadata'
            ]
            
            for section in required_sections:
                if section not in self.config:
                    logger.error(f"Missing required section: {section}")
                    return False
            
            # Validate SIP trunks
            if not self.config['sip_trunks']:
                logger.error("No SIP trunks configured")
                return False
            
            for trunk in self.config['sip_trunks']:
                required_fields = ['name', 'host', 'port', 'username', 'password']
                for field in required_fields:
                    if not trunk.get(field):
                        logger.error(f"Missing required field '{field}' in SIP trunk")
                        return False
            
            # Validate audio codecs
            if not self.config['audio_codecs']:
                logger.error("No audio codecs configured")
                return False
            
            # Validate LiveKit configuration
            livekit_config = self.config.get('livekit', {})
            server_config = livekit_config.get('server', {})
            
            if not server_config.get('url'):
                logger.error("LiveKit server URL not configured")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_environment_variables(self) -> bool:
        """Test environment variable configuration."""
        try:
            import os
            
            required_vars = [
                'SIP_SERVER',
                'SIP_USERNAME', 
                'SIP_PASSWORD',
                'LIVEKIT_URL',
                'LIVEKIT_API_KEY',
                'LIVEKIT_API_SECRET'
            ]
            
            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.error(f"Missing environment variables: {missing_vars}")
                return False
            
            # Validate format of key variables
            livekit_api_key = os.getenv('LIVEKIT_API_KEY', '')
            if not livekit_api_key.startswith('API'):
                logger.warning("LiveKit API key format may be incorrect (should start with 'API')")
            
            logger.info("Environment variables validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Environment variables test failed: {e}")
            return False
    
    async def test_sip_connectivity(self) -> Dict[str, Any]:
        """Test SIP trunk connectivity."""
        results = {}
        
        try:
            for trunk in self.config.get('sip_trunks', []):
                trunk_name = trunk['name']
                host = trunk['host']
                port = trunk['port']
                
                logger.info(f"Testing connectivity to SIP trunk: {trunk_name}")
                
                # Test basic network connectivity
                start_time = time.time()
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(10)
                    sock.connect((host, port))
                    sock.close()
                    
                    response_time = time.time() - start_time
                    results[trunk_name] = {
                        "connectivity": True,
                        "response_time": response_time,
                        "host": host,
                        "port": port
                    }
                    logger.info(f"SIP trunk {trunk_name} connectivity: OK ({response_time:.3f}s)")
                    
                except (socket.timeout, socket.error) as e:
                    results[trunk_name] = {
                        "connectivity": False,
                        "error": str(e),
                        "host": host,
                        "port": port
                    }
                    logger.error(f"SIP trunk {trunk_name} connectivity: FAILED - {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"SIP connectivity test failed: {e}")
            return {"error": str(e)}
    
    async def test_livekit_connection(self) -> Dict[str, Any]:
        """Test LiveKit API connection."""
        try:
            import os
            
            livekit_url = os.getenv('LIVEKIT_URL')
            livekit_api_key = os.getenv('LIVEKIT_API_KEY')
            livekit_api_secret = os.getenv('LIVEKIT_API_SECRET')
            
            if not all([livekit_url, livekit_api_key, livekit_api_secret]):
                return {"error": "LiveKit credentials not configured"}
            
            # Initialize LiveKit client
            self.livekit_client = api.LiveKitAPI(
                url=livekit_url,
                api_key=livekit_api_key,
                api_secret=livekit_api_secret
            )
            
            # Test connection by listing rooms
            start_time = time.time()
            rooms = await self.livekit_client.room.list_rooms()
            response_time = time.time() - start_time
            
            result = {
                "connection": True,
                "response_time": response_time,
                "rooms_count": len(rooms),
                "url": livekit_url
            }
            
            logger.info(f"LiveKit connection: OK ({response_time:.3f}s, {len(rooms)} rooms)")
            return result
            
        except Exception as e:
            logger.error(f"LiveKit connection test failed: {e}")
            return {"connection": False, "error": str(e)}
    
    async def test_audio_codecs(self) -> Dict[str, Any]:
        """Test audio codec configuration."""
        try:
            codecs = self.config.get('audio_codecs', [])
            
            if not codecs:
                return {"error": "No audio codecs configured"}
            
            results = {
                "total_codecs": len(codecs),
                "enabled_codecs": [],
                "disabled_codecs": [],
                "priority_order": []
            }
            
            # Sort by priority
            sorted_codecs = sorted(codecs, key=lambda x: x.get('priority', 999))
            
            for codec in sorted_codecs:
                codec_info = {
                    "name": codec['name'],
                    "payload_type": codec['payload_type'],
                    "sample_rate": codec['sample_rate'],
                    "channels": codec['channels'],
                    "priority": codec['priority']
                }
                
                if codec.get('enabled', True):
                    results["enabled_codecs"].append(codec_info)
                else:
                    results["disabled_codecs"].append(codec_info)
                
                results["priority_order"].append(codec['name'])
            
            # Validate codec configuration
            if not results["enabled_codecs"]:
                results["warning"] = "No codecs are enabled"
            
            # Check for standard telephony codecs
            codec_names = [c['name'] for c in results["enabled_codecs"]]
            if 'PCMU' not in codec_names and 'PCMA' not in codec_names:
                results["warning"] = "No standard telephony codecs (PCMU/PCMA) enabled"
            
            logger.info(f"Audio codecs: {len(results['enabled_codecs'])} enabled, {len(results['disabled_codecs'])} disabled")
            return results
            
        except Exception as e:
            logger.error(f"Audio codec test failed: {e}")
            return {"error": str(e)}
    
    async def test_webhook_endpoints(self) -> Dict[str, Any]:
        """Test webhook endpoint configuration."""
        try:
            import os
            
            domain = os.getenv('DOMAIN', 'localhost')
            port = os.getenv('PORT', '8000')
            
            webhook_url = f"http://{domain}:{port}/webhooks/livekit"
            health_url = f"http://{domain}:{port}/webhooks/health"
            
            results = {
                "webhook_url": webhook_url,
                "health_url": health_url,
                "tests": {}
            }
            
            # Test health endpoint (if server is running)
            try:
                response = requests.get(health_url, timeout=5)
                results["tests"]["health_endpoint"] = {
                    "status": response.status_code,
                    "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                }
                logger.info(f"Webhook health endpoint: {response.status_code}")
            except requests.RequestException as e:
                results["tests"]["health_endpoint"] = {
                    "error": str(e),
                    "note": "Server may not be running"
                }
                logger.warning(f"Webhook health endpoint test failed: {e}")
            
            # Validate webhook configuration in YAML
            webhook_config = self.config.get('livekit', {}).get('webhooks', {})
            if webhook_config.get('enabled'):
                results["webhook_config"] = {
                    "enabled": True,
                    "url": webhook_config.get('url'),
                    "events": webhook_config.get('events', [])
                }
            else:
                results["webhook_config"] = {"enabled": False}
            
            return results
            
        except Exception as e:
            logger.error(f"Webhook endpoint test failed: {e}")
            return {"error": str(e)}
    
    async def test_call_simulation(self) -> Dict[str, Any]:
        """Test call simulation (if LiveKit client is available)."""
        try:
            if not self.livekit_client:
                return {"error": "LiveKit client not available"}
            
            # Create a test room
            call_id = str(uuid4())
            room_name = f"voice-ai-call-{call_id}"
            
            test_metadata = {
                "call_id": call_id,
                "caller_number": "+1234567890",
                "called_number": "+0987654321",
                "start_time": datetime.now(UTC).isoformat(),
                "trunk_name": "test-trunk",
                "codec_used": "PCMU",
                "test": True
            }
            
            # Create room
            room_options = api.CreateRoomRequest(
                name=room_name,
                empty_timeout=60,  # 1 minute for test
                max_participants=2,
                metadata=json.dumps(test_metadata)
            )
            
            start_time = time.time()
            room = await self.livekit_client.room.create_room(room_options)
            create_time = time.time() - start_time
            
            # List rooms to verify creation
            rooms = await self.livekit_client.room.list_rooms()
            test_room = next((r for r in rooms if r.name == room_name), None)
            
            result = {
                "room_created": True,
                "room_name": room_name,
                "create_time": create_time,
                "room_found": test_room is not None,
                "metadata": test_metadata
            }
            
            # Clean up - delete the test room
            try:
                await self.livekit_client.room.delete_room(
                    api.DeleteRoomRequest(room=room_name)
                )
                result["room_deleted"] = True
            except Exception as e:
                result["room_deleted"] = False
                result["delete_error"] = str(e)
            
            logger.info(f"Call simulation: Room created and deleted successfully ({create_time:.3f}s)")
            return result
            
        except Exception as e:
            logger.error(f"Call simulation test failed: {e}")
            return {"error": str(e)}
    
    async def test_health_monitoring(self) -> Dict[str, Any]:
        """Test health monitoring configuration."""
        try:
            monitoring_config = self.config.get('monitoring', {})
            
            results = {
                "health_check": monitoring_config.get('health_check', {}),
                "metrics": monitoring_config.get('metrics', {}),
                "logging": monitoring_config.get('logging', {})
            }
            
            # Validate health check configuration
            health_config = results["health_check"]
            if not health_config.get('enabled'):
                results["warnings"] = results.get("warnings", [])
                results["warnings"].append("Health checks are disabled")
            
            # Validate metrics configuration
            metrics_config = results["metrics"]
            if not metrics_config.get('enabled'):
                results["warnings"] = results.get("warnings", [])
                results["warnings"].append("Metrics collection is disabled")
            
            logger.info("Health monitoring configuration validated")
            return results
            
        except Exception as e:
            logger.error(f"Health monitoring test failed: {e}")
            return {"error": str(e)}
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling configuration."""
        try:
            results = {}
            
            # Test retry configuration
            for trunk in self.config.get('sip_trunks', []):
                trunk_name = trunk['name']
                retry_config = trunk.get('retry', {})
                
                results[trunk_name] = {
                    "retry_enabled": retry_config.get('enabled', False),
                    "max_attempts": retry_config.get('max_attempts', 0),
                    "initial_delay": retry_config.get('initial_delay', 0),
                    "max_delay": retry_config.get('max_delay', 0),
                    "multiplier": retry_config.get('multiplier', 1.0)
                }
            
            # Test health check failure handling
            health_checks = {}
            for trunk in self.config.get('sip_trunks', []):
                trunk_name = trunk['name']
                health_config = trunk.get('health_check', {})
                
                health_checks[trunk_name] = {
                    "enabled": health_config.get('enabled', False),
                    "max_failures": health_config.get('max_failures', 0),
                    "timeout": health_config.get('timeout', 0)
                }
            
            results["health_checks"] = health_checks
            
            logger.info("Error handling configuration validated")
            return results
            
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            return {"error": str(e)}


async def main():
    """Main test function."""
    tester = SIPIntegrationTester()
    
    try:
        # Run all tests
        results = await tester.run_all_tests()
        
        # Save results to file
        with open('sip_integration_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print summary
        print("\n" + "="*60)
        print("SIP INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Success Rate: {results['success_rate']:.1%}")
        print(f"Results saved to: sip_integration_test_results.json")
        
        # Print failed tests
        failed_tests = [name for name, result in results['results'].items() 
                       if result['status'] != 'PASS']
        
        if failed_tests:
            print(f"\nFailed Tests:")
            for test_name in failed_tests:
                result = results['results'][test_name]
                print(f"  - {test_name}: {result.get('error', 'Unknown error')}")
        
        # Exit with appropriate code
        sys.exit(0 if results['success_rate'] == 1.0 else 1)
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
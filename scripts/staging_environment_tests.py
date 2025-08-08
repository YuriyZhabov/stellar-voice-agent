#!/usr/bin/env python3
"""
Staging Environment Testing for LiveKit System
Проведение тестирования в staging environment
Requirements: 1.1, 2.1, 3.1
"""

import os
import json
import yaml
import time
import requests
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StagingEnvironmentTester:
    """Тестирование staging среды LiveKit системы."""
    
    def __init__(self, config_file: str = "config/staging_tests.yaml"):
        self.config_file = config_file
        self.config = self._load_test_config()
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.test_results = []
        
    def _load_test_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации тестирования."""
        default_config = {
            "staging_environment": {
                "base_url": "http://staging.localhost:8000",
                "livekit_url": "ws://staging.localhost:7880",
                "api_key": os.getenv("LIVEKIT_API_KEY_STAGING"),
                "api_secret": os.getenv("LIVEKIT_API_SECRET_STAGING"),
                "sip_number": os.getenv("SIP_NUMBER_STAGING"),
                "health_check_url": "http://staging.localhost:8000/health"
            },
            "test_suites": {
                "infrastructure": {
                    "enabled": True,
                    "tests": ["service_health", "database_connectivity", "redis_connectivity", "disk_space"]
                },
                "api_endpoints": {
                    "enabled": True,
                    "tests": ["health_endpoint", "metrics_endpoint", "webhook_endpoint", "livekit_api"]
                },
                "authentication": {
                    "enabled": True,
                    "tests": ["jwt_generation", "token_validation", "api_authentication"]
                },
                "sip_integration": {
                    "enabled": True,
                    "tests": ["sip_trunk_connectivity", "sip_registration", "call_routing"]
                },
                "livekit_integration": {
                    "enabled": True,
                    "tests": ["room_creation", "participant_join", "track_publishing", "webhook_delivery"]
                },
                "performance": {
                    "enabled": True,
                    "tests": ["response_time", "concurrent_connections", "memory_usage", "cpu_usage"]
                },
                "security": {
                    "enabled": True,
                    "tests": ["ssl_certificates", "api_security", "data_encryption"]
                },
                "monitoring": {
                    "enabled": True,
                    "tests": ["prometheus_metrics", "log_aggregation", "alerting_system"]
                }
            },
            "test_parameters": {
                "timeout": 30,
                "retry_count": 3,
                "concurrent_users": 10,
                "test_duration": 300,
                "performance_thresholds": {
                    "response_time_ms": 1000,
                    "memory_usage_mb": 512,
                    "cpu_usage_percent": 80
                }
            }
        }
        
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # Create default config
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            return default_config
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов staging среды."""
        logger.info("Starting comprehensive staging environment tests...")
        
        test_report = {
            "timestamp": self.timestamp,
            "environment": "staging",
            "test_suites": {},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
        
        # Запуск тестовых наборов
        for suite_name, suite_config in self.config["test_suites"].items():
            if not suite_config.get("enabled", True):
                logger.info(f"Skipping disabled test suite: {suite_name}")
                continue
            
            logger.info(f"Running test suite: {suite_name}")
            suite_results = await self._run_test_suite(suite_name, suite_config)
            test_report["test_suites"][suite_name] = suite_results
            
            # Обновление сводки
            test_report["summary"]["total_tests"] += suite_results["total_tests"]
            test_report["summary"]["passed"] += suite_results["passed"]
            test_report["summary"]["failed"] += suite_results["failed"]
            test_report["summary"]["skipped"] += suite_results["skipped"]
        
        # Сохранение отчета
        report_file = f"staging_test_report_{self.timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(test_report, f, indent=2)
        
        logger.info(f"Test report saved: {report_file}")
        logger.info(f"Test summary: {test_report['summary']['passed']}/{test_report['summary']['total_tests']} passed")
        
        return test_report
    
    async def _run_test_suite(self, suite_name: str, suite_config: Dict[str, Any]) -> Dict[str, Any]:
        """Запуск набора тестов."""
        suite_results = {
            "suite_name": suite_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "tests": {},
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
        
        tests = suite_config.get("tests", [])
        
        for test_name in tests:
            logger.info(f"Running test: {suite_name}.{test_name}")
            
            try:
                test_method = getattr(self, f"_test_{suite_name}_{test_name}", None)
                if test_method:
                    result = await test_method()
                    suite_results["tests"][test_name] = result
                    
                    if result["status"] == "passed":
                        suite_results["passed"] += 1
                    elif result["status"] == "failed":
                        suite_results["failed"] += 1
                    else:
                        suite_results["skipped"] += 1
                        
                    suite_results["total_tests"] += 1
                else:
                    logger.warning(f"Test method not found: _test_{suite_name}_{test_name}")
                    suite_results["tests"][test_name] = {
                        "status": "skipped",
                        "message": "Test method not implemented"
                    }
                    suite_results["skipped"] += 1
                    suite_results["total_tests"] += 1
                    
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                suite_results["tests"][test_name] = {
                    "status": "failed",
                    "message": f"Exception: {str(e)}"
                }
                suite_results["failed"] += 1
                suite_results["total_tests"] += 1
        
        return suite_results
    
    # Infrastructure Tests
    async def _test_infrastructure_service_health(self) -> Dict[str, Any]:
        """Тест здоровья сервисов."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "status=running", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            
            running_services = [s for s in result.stdout.strip().split('\n') if s]
            expected_services = ["livekit-server", "voice-ai-agent", "redis"]
            
            missing_services = [s for s in expected_services if not any(s in rs for rs in running_services)]
            
            if not missing_services:
                return {
                    "status": "passed",
                    "message": f"All services running: {len(running_services)}",
                    "details": {"running_services": running_services}
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Missing services: {missing_services}",
                    "details": {"missing_services": missing_services}
                }
                
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"Could not check service health: {e}"
            }
    
    async def _test_infrastructure_database_connectivity(self) -> Dict[str, Any]:
        """Тест подключения к базе данных."""
        db_files = ["data/voice_ai.db", "voice_ai.db"]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    result = subprocess.run(
                        ["sqlite3", db_file, "SELECT COUNT(*) FROM sqlite_master;"],
                        capture_output=True, text=True, check=True
                    )
                    
                    return {
                        "status": "passed",
                        "message": f"Database connectivity verified: {db_file}",
                        "details": {"database_file": db_file}
                    }
                    
                except subprocess.CalledProcessError as e:
                    return {
                        "status": "failed",
                        "message": f"Database connectivity failed: {e}"
                    }
        
        return {
            "status": "failed",
            "message": "No database file found"
        }
    
    async def _test_infrastructure_redis_connectivity(self) -> Dict[str, Any]:
        """Тест подключения к Redis."""
        try:
            result = subprocess.run(
                ["docker", "exec", "redis", "redis-cli", "ping"],
                capture_output=True, text=True, check=True
            )
            
            if "PONG" in result.stdout:
                return {
                    "status": "passed",
                    "message": "Redis connectivity verified"
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Redis ping failed: {result.stdout}"
                }
                
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"Redis connectivity test failed: {e}"
            }
    
    async def _test_infrastructure_disk_space(self) -> Dict[str, Any]:
        """Тест свободного места на диске."""
        try:
            result = subprocess.run(
                ["df", "-h", "."],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                disk_info = lines[1].split()
                usage_percent = int(disk_info[4].rstrip('%'))
                
                if usage_percent < 90:
                    return {
                        "status": "passed",
                        "message": f"Disk usage: {usage_percent}%",
                        "details": {"usage_percent": usage_percent}
                    }
                else:
                    return {
                        "status": "failed",
                        "message": f"Disk usage too high: {usage_percent}%",
                        "details": {"usage_percent": usage_percent}
                    }
            else:
                return {
                    "status": "failed",
                    "message": "Could not parse disk usage"
                }
                
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"Disk space check failed: {e}"
            }
    
    # API Endpoint Tests
    async def _test_api_endpoints_health_endpoint(self) -> Dict[str, Any]:
        """Тест health endpoint."""
        health_url = self.config["staging_environment"]["health_check_url"]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": "passed",
                            "message": "Health endpoint responding",
                            "details": {"response_data": data}
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": f"Health endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Health endpoint test failed: {e}"
            }
    
    async def _test_api_endpoints_metrics_endpoint(self) -> Dict[str, Any]:
        """Тест metrics endpoint."""
        base_url = self.config["staging_environment"]["base_url"]
        metrics_url = f"{base_url}/metrics"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(metrics_url, timeout=10) as response:
                    if response.status == 200:
                        text = await response.text()
                        return {
                            "status": "passed",
                            "message": "Metrics endpoint responding",
                            "details": {"metrics_length": len(text)}
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": f"Metrics endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Metrics endpoint test failed: {e}"
            }
    
    async def _test_api_endpoints_webhook_endpoint(self) -> Dict[str, Any]:
        """Тест webhook endpoint."""
        base_url = self.config["staging_environment"]["base_url"]
        webhook_url = f"{base_url}/webhooks/livekit"
        
        test_payload = {
            "event": "test_event",
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=test_payload, timeout=10) as response:
                    if response.status in [200, 202]:
                        return {
                            "status": "passed",
                            "message": "Webhook endpoint accepting requests"
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": f"Webhook endpoint returned {response.status}"
                        }
                        
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Webhook endpoint test failed: {e}"
            }
    
    async def _test_api_endpoints_livekit_api(self) -> Dict[str, Any]:
        """Тест LiveKit API."""
        try:
            # Import LiveKit client
            from livekit import api
            
            livekit_url = self.config["staging_environment"]["livekit_url"]
            api_key = self.config["staging_environment"]["api_key"]
            api_secret = self.config["staging_environment"]["api_secret"]
            
            if not api_key or not api_secret:
                return {
                    "status": "skipped",
                    "message": "LiveKit API credentials not configured"
                }
            
            client = api.LiveKitAPI(
                url=livekit_url,
                api_key=api_key,
                api_secret=api_secret
            )
            
            # Test room listing
            rooms = await client.room.list_rooms(api.ListRoomsRequest())
            
            return {
                "status": "passed",
                "message": "LiveKit API responding",
                "details": {"rooms_count": len(rooms.rooms)}
            }
            
        except ImportError:
            return {
                "status": "skipped",
                "message": "LiveKit client not available"
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"LiveKit API test failed: {e}"
            }
    
    # Authentication Tests
    async def _test_authentication_jwt_generation(self) -> Dict[str, Any]:
        """Тест генерации JWT токенов."""
        try:
            api_key = self.config["staging_environment"]["api_key"]
            api_secret = self.config["staging_environment"]["api_secret"]
            
            if not api_key or not api_secret:
                return {
                    "status": "skipped",
                    "message": "API credentials not configured"
                }
            
            # Import auth manager
            import sys
            sys.path.append('src')
            from auth.livekit_auth import LiveKitAuthManager
            
            auth_manager = LiveKitAuthManager(api_key, api_secret)
            token = auth_manager.create_participant_token("test_user", "test_room")
            
            if token and len(token) > 0:
                return {
                    "status": "passed",
                    "message": "JWT token generated successfully",
                    "details": {"token_length": len(token)}
                }
            else:
                return {
                    "status": "failed",
                    "message": "JWT token generation failed"
                }
                
        except ImportError as e:
            return {
                "status": "skipped",
                "message": f"Auth module not available: {e}"
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"JWT generation test failed: {e}"
            }
    
    async def _test_authentication_token_validation(self) -> Dict[str, Any]:
        """Тест валидации токенов."""
        try:
            import jwt
            
            api_key = self.config["staging_environment"]["api_key"]
            api_secret = self.config["staging_environment"]["api_secret"]
            
            if not api_key or not api_secret:
                return {
                    "status": "skipped",
                    "message": "API credentials not configured"
                }
            
            # Create test token
            payload = {
                "iss": api_key,
                "sub": "test_user",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600
            }
            
            token = jwt.encode(payload, api_secret, algorithm="HS256")
            
            # Validate token
            decoded = jwt.decode(token, api_secret, algorithms=["HS256"])
            
            if decoded["sub"] == "test_user":
                return {
                    "status": "passed",
                    "message": "Token validation successful"
                }
            else:
                return {
                    "status": "failed",
                    "message": "Token validation failed"
                }
                
        except ImportError:
            return {
                "status": "skipped",
                "message": "JWT library not available"
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Token validation test failed: {e}"
            }
    
    async def _test_authentication_api_authentication(self) -> Dict[str, Any]:
        """Тест API аутентификации."""
        # This would test actual API authentication with LiveKit server
        return {
            "status": "skipped",
            "message": "API authentication test not implemented"
        }
    
    # Performance Tests
    async def _test_performance_response_time(self) -> Dict[str, Any]:
        """Тест времени отклика."""
        health_url = self.config["staging_environment"]["health_check_url"]
        threshold_ms = self.config["test_parameters"]["performance_thresholds"]["response_time_ms"]
        
        response_times = []
        
        try:
            for i in range(5):  # 5 измерений
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, timeout=10) as response:
                        if response.status == 200:
                            response_time_ms = (time.time() - start_time) * 1000
                            response_times.append(response_time_ms)
                        else:
                            return {
                                "status": "failed",
                                "message": f"Health check failed with status {response.status}"
                            }
            
            avg_response_time = sum(response_times) / len(response_times)
            
            if avg_response_time <= threshold_ms:
                return {
                    "status": "passed",
                    "message": f"Average response time: {avg_response_time:.2f}ms",
                    "details": {
                        "avg_response_time_ms": avg_response_time,
                        "threshold_ms": threshold_ms,
                        "measurements": response_times
                    }
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Response time too high: {avg_response_time:.2f}ms > {threshold_ms}ms",
                    "details": {
                        "avg_response_time_ms": avg_response_time,
                        "threshold_ms": threshold_ms
                    }
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Response time test failed: {e}"
            }
    
    async def _test_performance_concurrent_connections(self) -> Dict[str, Any]:
        """Тест одновременных подключений."""
        health_url = self.config["staging_environment"]["health_check_url"]
        concurrent_users = self.config["test_parameters"]["concurrent_users"]
        
        async def make_request(session):
            try:
                async with session.get(health_url, timeout=10) as response:
                    return response.status == 200
            except:
                return False
        
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [make_request(session) for _ in range(concurrent_users)]
                results = await asyncio.gather(*tasks)
                
                successful_requests = sum(results)
                success_rate = successful_requests / concurrent_users
                
                if success_rate >= 0.95:  # 95% success rate
                    return {
                        "status": "passed",
                        "message": f"Concurrent connections test passed: {successful_requests}/{concurrent_users}",
                        "details": {
                            "success_rate": success_rate,
                            "successful_requests": successful_requests,
                            "total_requests": concurrent_users
                        }
                    }
                else:
                    return {
                        "status": "failed",
                        "message": f"Concurrent connections test failed: {successful_requests}/{concurrent_users}",
                        "details": {
                            "success_rate": success_rate,
                            "successful_requests": successful_requests,
                            "total_requests": concurrent_users
                        }
                    }
                    
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Concurrent connections test failed: {e}"
            }
    
    async def _test_performance_memory_usage(self) -> Dict[str, Any]:
        """Тест использования памяти."""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\t{{.MemUsage}}"],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            memory_usage = {}
            
            for line in lines:
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        container = parts[0]
                        mem_usage = parts[1].split(' / ')[0]  # Get used memory
                        
                        # Parse memory usage (e.g., "123.4MiB" -> 123.4)
                        if 'MiB' in mem_usage:
                            mem_mb = float(mem_usage.replace('MiB', ''))
                        elif 'GiB' in mem_usage:
                            mem_mb = float(mem_usage.replace('GiB', '')) * 1024
                        else:
                            mem_mb = 0
                        
                        memory_usage[container] = mem_mb
            
            threshold_mb = self.config["test_parameters"]["performance_thresholds"]["memory_usage_mb"]
            high_memory_containers = {k: v for k, v in memory_usage.items() if v > threshold_mb}
            
            if not high_memory_containers:
                return {
                    "status": "passed",
                    "message": "Memory usage within limits",
                    "details": {"memory_usage_mb": memory_usage}
                }
            else:
                return {
                    "status": "failed",
                    "message": f"High memory usage detected: {high_memory_containers}",
                    "details": {
                        "memory_usage_mb": memory_usage,
                        "threshold_mb": threshold_mb,
                        "high_memory_containers": high_memory_containers
                    }
                }
                
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"Memory usage test failed: {e}"
            }
    
    async def _test_performance_cpu_usage(self) -> Dict[str, Any]:
        """Тест использования CPU."""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\t{{.CPUPerc}}"],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            cpu_usage = {}
            
            for line in lines:
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        container = parts[0]
                        cpu_percent = float(parts[1].replace('%', ''))
                        cpu_usage[container] = cpu_percent
            
            threshold_percent = self.config["test_parameters"]["performance_thresholds"]["cpu_usage_percent"]
            high_cpu_containers = {k: v for k, v in cpu_usage.items() if v > threshold_percent}
            
            if not high_cpu_containers:
                return {
                    "status": "passed",
                    "message": "CPU usage within limits",
                    "details": {"cpu_usage_percent": cpu_usage}
                }
            else:
                return {
                    "status": "failed",
                    "message": f"High CPU usage detected: {high_cpu_containers}",
                    "details": {
                        "cpu_usage_percent": cpu_usage,
                        "threshold_percent": threshold_percent,
                        "high_cpu_containers": high_cpu_containers
                    }
                }
                
        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "message": f"CPU usage test failed: {e}"
            }
    
    # Placeholder methods for other test categories
    async def _test_sip_integration_sip_trunk_connectivity(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "SIP trunk connectivity test not implemented"}
    
    async def _test_sip_integration_sip_registration(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "SIP registration test not implemented"}
    
    async def _test_sip_integration_call_routing(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Call routing test not implemented"}
    
    async def _test_livekit_integration_room_creation(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Room creation test not implemented"}
    
    async def _test_livekit_integration_participant_join(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Participant join test not implemented"}
    
    async def _test_livekit_integration_track_publishing(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Track publishing test not implemented"}
    
    async def _test_livekit_integration_webhook_delivery(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Webhook delivery test not implemented"}
    
    async def _test_security_ssl_certificates(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "SSL certificates test not implemented"}
    
    async def _test_security_api_security(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "API security test not implemented"}
    
    async def _test_security_data_encryption(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Data encryption test not implemented"}
    
    async def _test_monitoring_prometheus_metrics(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Prometheus metrics test not implemented"}
    
    async def _test_monitoring_log_aggregation(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Log aggregation test not implemented"}
    
    async def _test_monitoring_alerting_system(self) -> Dict[str, Any]:
        return {"status": "skipped", "message": "Alerting system test not implemented"}

def main():
    """Основная функция для тестирования staging среды."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Staging Environment Testing for LiveKit System")
    parser.add_argument("--run-all", action="store_true", help="Run all staging tests")
    parser.add_argument("--suite", help="Run specific test suite")
    parser.add_argument("--test", help="Run specific test")
    parser.add_argument("--config", help="Path to test configuration file")
    
    args = parser.parse_args()
    
    config_file = args.config or "config/staging_tests.yaml"
    tester = StagingEnvironmentTester(config_file)
    
    async def run_tests():
        if args.run_all:
            report = await tester.run_all_tests()
            print(f"Test Results: {report['summary']['passed']}/{report['summary']['total_tests']} passed")
            return report['summary']['failed'] == 0
        
        elif args.suite:
            if args.suite in tester.config["test_suites"]:
                suite_config = tester.config["test_suites"][args.suite]
                results = await tester._run_test_suite(args.suite, suite_config)
                print(f"Suite Results: {results['passed']}/{results['total_tests']} passed")
                return results['failed'] == 0
            else:
                print(f"Unknown test suite: {args.suite}")
                return False
        
        elif args.test:
            # Run specific test
            parts = args.test.split('.')
            if len(parts) == 2:
                suite_name, test_name = parts
                test_method = getattr(tester, f"_test_{suite_name}_{test_name}", None)
                if test_method:
                    result = await test_method()
                    print(f"Test Result: {result}")
                    return result['status'] == 'passed'
                else:
                    print(f"Test method not found: {args.test}")
                    return False
            else:
                print("Test format should be: suite_name.test_name")
                return False
        
        else:
            print("Use --help for available options")
            return False
    
    # Run async tests
    success = asyncio.run(run_tests())
    exit(0 if success else 1)

if __name__ == "__main__":
    main()
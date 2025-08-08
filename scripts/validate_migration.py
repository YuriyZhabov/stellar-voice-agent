#!/usr/bin/env python3
"""
Migration Validation Script
Валидация миграции LiveKit системы
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationValidator:
    """Валидация миграции LiveKit системы."""
    
    def __init__(self):
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.validation_results = []
        
    def validate_migration(self) -> Dict[str, Any]:
        """Полная валидация миграции."""
        logger.info("Starting migration validation...")
        
        validation_report = {
            "timestamp": self.timestamp,
            "validation_type": "migration",
            "categories": {},
            "summary": {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
        }
        
        # Категории валидации
        validation_categories = [
            ("configuration", self._validate_configuration),
            ("services", self._validate_services),
            ("api_endpoints", self._validate_api_endpoints),
            ("authentication", self._validate_authentication),
            ("sip_integration", self._validate_sip_integration),
            ("database", self._validate_database),
            ("monitoring", self._validate_monitoring),
            ("performance", self._validate_performance)
        ]
        
        for category_name, validation_func in validation_categories:
            logger.info(f"Validating category: {category_name}")
            
            try:
                category_results = validation_func()
                validation_report["categories"][category_name] = category_results
                
                # Обновление сводки
                validation_report["summary"]["total_checks"] += category_results["total_checks"]
                validation_report["summary"]["passed"] += category_results["passed"]
                validation_report["summary"]["failed"] += category_results["failed"]
                validation_report["summary"]["warnings"] += category_results["warnings"]
                
            except Exception as e:
                logger.error(f"Validation category {category_name} failed: {e}")
                validation_report["categories"][category_name] = {
                    "status": "error",
                    "message": str(e),
                    "total_checks": 1,
                    "passed": 0,
                    "failed": 1,
                    "warnings": 0
                }
                validation_report["summary"]["total_checks"] += 1
                validation_report["summary"]["failed"] += 1
        
        # Сохранение отчета
        report_file = f"migration_validation_report_{self.timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(validation_report, f, indent=2)
        
        logger.info(f"Migration validation completed. Report saved: {report_file}")
        logger.info(f"Summary: {validation_report['summary']['passed']}/{validation_report['summary']['total_checks']} checks passed")
        
        return validation_report
    
    def _validate_configuration(self) -> Dict[str, Any]:
        """Валидация конфигурационных файлов."""
        results = {
            "category": "configuration",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка существования конфигурационных файлов
        config_files = [
            "livekit-sip-correct.yaml",
            "config/livekit_config.py",
            "config/livekit_auth.yaml",
            "config/deployment.yaml",
            ".env"
        ]
        
        for config_file in config_files:
            check_name = f"config_file_{config_file.replace('/', '_').replace('.', '_')}"
            
            if os.path.exists(config_file):
                results["checks"][check_name] = {
                    "status": "passed",
                    "message": f"Configuration file exists: {config_file}"
                }
                results["passed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Configuration file missing: {config_file}"
                }
                results["failed"] += 1
            
            results["total_checks"] += 1
        
        # Валидация YAML файлов
        yaml_files = ["livekit-sip-correct.yaml", "config/deployment.yaml"]
        
        for yaml_file in yaml_files:
            check_name = f"yaml_syntax_{yaml_file.replace('/', '_').replace('.', '_')}"
            
            if os.path.exists(yaml_file):
                try:
                    with open(yaml_file, 'r') as f:
                        yaml.safe_load(f)
                    
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": f"YAML syntax valid: {yaml_file}"
                    }
                    results["passed"] += 1
                    
                except yaml.YAMLError as e:
                    results["checks"][check_name] = {
                        "status": "failed",
                        "message": f"YAML syntax error in {yaml_file}: {e}"
                    }
                    results["failed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"YAML file not found: {yaml_file}"
                }
                results["failed"] += 1
            
            results["total_checks"] += 1
        
        # Валидация переменных окружения
        check_name = "environment_variables"
        
        try:
            from .update_env_vars import EnvironmentUpdater
            
            updater = EnvironmentUpdater()
            validation = updater.validate_environment_variables()
            
            if validation["valid"]:
                results["checks"][check_name] = {
                    "status": "passed",
                    "message": f"Environment variables valid ({validation['total_variables']} variables)"
                }
                results["passed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Environment variables invalid: {validation['errors']}"
                }
                results["failed"] += 1
                
            if validation["warnings"]:
                results["warnings"] += len(validation["warnings"])
                
        except ImportError:
            results["checks"][check_name] = {
                "status": "warning",
                "message": "Environment updater not available"
            }
            results["warnings"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_services(self) -> Dict[str, Any]:
        """Валидация сервисов."""
        results = {
            "category": "services",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка запущенных контейнеров
        check_name = "docker_containers"
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True, check=True
            )
            
            containers = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        containers[parts[0]] = parts[1]
            
            expected_services = ["livekit-server", "voice-ai-agent", "redis"]
            running_services = []
            missing_services = []
            
            for service in expected_services:
                found = False
                for container_name in containers.keys():
                    if service in container_name and "Up" in containers[container_name]:
                        running_services.append(container_name)
                        found = True
                        break
                
                if not found:
                    missing_services.append(service)
            
            if not missing_services:
                results["checks"][check_name] = {
                    "status": "passed",
                    "message": f"All services running: {running_services}"
                }
                results["passed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Missing services: {missing_services}"
                }
                results["failed"] += 1
                
        except subprocess.CalledProcessError as e:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"Could not check Docker containers: {e}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        # Проверка health checks
        check_name = "service_health"
        
        try:
            health_url = "http://localhost:8000/health"
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                results["checks"][check_name] = {
                    "status": "passed",
                    "message": "Service health check passed",
                    "details": health_data
                }
                results["passed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Health check failed with status {response.status_code}"
                }
                results["failed"] += 1
                
        except requests.RequestException as e:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"Health check request failed: {e}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_api_endpoints(self) -> Dict[str, Any]:
        """Валидация API эндпоинтов."""
        results = {
            "category": "api_endpoints",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Список эндпоинтов для проверки
        endpoints = [
            ("health", "http://localhost:8000/health"),
            ("metrics", "http://localhost:8000/metrics"),
            ("webhooks", "http://localhost:8000/webhooks/livekit")
        ]
        
        for endpoint_name, endpoint_url in endpoints:
            check_name = f"endpoint_{endpoint_name}"
            
            try:
                if endpoint_name == "webhooks":
                    # POST запрос для webhook
                    response = requests.post(
                        endpoint_url, 
                        json={"test": "validation"}, 
                        timeout=10
                    )
                else:
                    # GET запрос для остальных
                    response = requests.get(endpoint_url, timeout=10)
                
                if response.status_code in [200, 202, 405]:  # 405 для webhook без правильных данных
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": f"Endpoint {endpoint_name} responding (status: {response.status_code})"
                    }
                    results["passed"] += 1
                else:
                    results["checks"][check_name] = {
                        "status": "failed",
                        "message": f"Endpoint {endpoint_name} returned status {response.status_code}"
                    }
                    results["failed"] += 1
                    
            except requests.RequestException as e:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Endpoint {endpoint_name} request failed: {e}"
                }
                results["failed"] += 1
            
            results["total_checks"] += 1
        
        return results
    
    def _validate_authentication(self) -> Dict[str, Any]:
        """Валидация аутентификации."""
        results = {
            "category": "authentication",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка JWT токенов
        check_name = "jwt_token_generation"
        
        try:
            # Попытка импорта и использования auth manager
            import sys
            sys.path.append('src')
            from auth.livekit_auth import LiveKitAuthManager
            
            # Получение API ключей из переменных окружения
            api_key = os.getenv("LIVEKIT_API_KEY")
            api_secret = os.getenv("LIVEKIT_API_SECRET")
            
            if api_key and api_secret and not api_key.startswith("${"):
                auth_manager = LiveKitAuthManager(api_key, api_secret)
                token = auth_manager.create_participant_token("test_user", "test_room")
                
                if token and len(token) > 0:
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": "JWT token generation successful"
                    }
                    results["passed"] += 1
                else:
                    results["checks"][check_name] = {
                        "status": "failed",
                        "message": "JWT token generation returned empty token"
                    }
                    results["failed"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "warning",
                    "message": "API credentials not configured for JWT testing"
                }
                results["warnings"] += 1
                
        except ImportError as e:
            results["checks"][check_name] = {
                "status": "warning",
                "message": f"Auth module not available: {e}"
            }
            results["warnings"] += 1
        except Exception as e:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"JWT token generation failed: {e}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_sip_integration(self) -> Dict[str, Any]:
        """Валидация SIP интеграции."""
        results = {
            "category": "sip_integration",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка SIP конфигурации
        check_name = "sip_configuration"
        
        sip_config_file = "livekit-sip-correct.yaml"
        
        if os.path.exists(sip_config_file):
            try:
                with open(sip_config_file, 'r') as f:
                    sip_config = yaml.safe_load(f)
                
                # Проверка обязательных секций
                required_sections = ["livekit", "sip_trunks", "routing"]
                missing_sections = []
                
                for section in required_sections:
                    if section not in sip_config:
                        missing_sections.append(section)
                
                if not missing_sections:
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": "SIP configuration structure valid"
                    }
                    results["passed"] += 1
                else:
                    results["checks"][check_name] = {
                        "status": "failed",
                        "message": f"SIP configuration missing sections: {missing_sections}"
                    }
                    results["failed"] += 1
                    
            except yaml.YAMLError as e:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"SIP configuration YAML error: {e}"
                }
                results["failed"] += 1
        else:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"SIP configuration file not found: {sip_config_file}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_database(self) -> Dict[str, Any]:
        """Валидация базы данных."""
        results = {
            "category": "database",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка подключения к базе данных
        check_name = "database_connectivity"
        
        db_files = ["data/voice_ai.db", "voice_ai.db"]
        db_found = False
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    result = subprocess.run(
                        ["sqlite3", db_file, "SELECT COUNT(*) FROM sqlite_master;"],
                        capture_output=True, text=True, check=True
                    )
                    
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": f"Database connectivity verified: {db_file}"
                    }
                    results["passed"] += 1
                    db_found = True
                    break
                    
                except subprocess.CalledProcessError as e:
                    results["checks"][check_name] = {
                        "status": "failed",
                        "message": f"Database connectivity failed for {db_file}: {e}"
                    }
                    results["failed"] += 1
                    db_found = True
                    break
        
        if not db_found:
            results["checks"][check_name] = {
                "status": "warning",
                "message": "No database file found"
            }
            results["warnings"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_monitoring(self) -> Dict[str, Any]:
        """Валидация мониторинга."""
        results = {
            "category": "monitoring",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка метрик Prometheus
        check_name = "prometheus_metrics"
        
        try:
            metrics_url = "http://localhost:8000/metrics"
            response = requests.get(metrics_url, timeout=10)
            
            if response.status_code == 200:
                metrics_text = response.text
                
                # Проверка наличия базовых метрик
                expected_metrics = ["http_requests_total", "process_cpu_seconds_total"]
                found_metrics = []
                
                for metric in expected_metrics:
                    if metric in metrics_text:
                        found_metrics.append(metric)
                
                if found_metrics:
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": f"Prometheus metrics available: {found_metrics}"
                    }
                    results["passed"] += 1
                else:
                    results["checks"][check_name] = {
                        "status": "warning",
                        "message": "Prometheus metrics endpoint available but no expected metrics found"
                    }
                    results["warnings"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": f"Prometheus metrics endpoint returned status {response.status_code}"
                }
                results["failed"] += 1
                
        except requests.RequestException as e:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"Prometheus metrics check failed: {e}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        return results
    
    def _validate_performance(self) -> Dict[str, Any]:
        """Валидация производительности."""
        results = {
            "category": "performance",
            "checks": {},
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        # Проверка времени отклика
        check_name = "response_time"
        
        try:
            health_url = "http://localhost:8000/health"
            
            # Измерение времени отклика
            response_times = []
            for _ in range(3):
                start_time = time.time()
                response = requests.get(health_url, timeout=10)
                response_time = (time.time() - start_time) * 1000  # в миллисекундах
                
                if response.status_code == 200:
                    response_times.append(response_time)
                else:
                    break
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                
                if avg_response_time < 1000:  # менее 1 секунды
                    results["checks"][check_name] = {
                        "status": "passed",
                        "message": f"Average response time: {avg_response_time:.2f}ms"
                    }
                    results["passed"] += 1
                else:
                    results["checks"][check_name] = {
                        "status": "warning",
                        "message": f"High response time: {avg_response_time:.2f}ms"
                    }
                    results["warnings"] += 1
            else:
                results["checks"][check_name] = {
                    "status": "failed",
                    "message": "Could not measure response time"
                }
                results["failed"] += 1
                
        except requests.RequestException as e:
            results["checks"][check_name] = {
                "status": "failed",
                "message": f"Response time check failed: {e}"
            }
            results["failed"] += 1
        
        results["total_checks"] += 1
        
        return results

def main():
    """Основная функция для валидации миграции."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migration Validation Script")
    parser.add_argument("--full", action="store_true", help="Run full migration validation")
    parser.add_argument("--category", help="Validate specific category")
    parser.add_argument("--output", help="Output file for validation report")
    
    args = parser.parse_args()
    
    validator = MigrationValidator()
    
    if args.full or not args.category:
        # Полная валидация
        report = validator.validate_migration()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Validation report saved to: {args.output}")
        
        # Вывод сводки
        summary = report["summary"]
        print(f"Migration Validation Summary:")
        print(f"  Total checks: {summary['total_checks']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Warnings: {summary['warnings']}")
        
        # Возврат кода ошибки если есть неудачные проверки
        exit(0 if summary['failed'] == 0 else 1)
    
    elif args.category:
        # Валидация конкретной категории
        validation_method = getattr(validator, f"_validate_{args.category}", None)
        
        if validation_method:
            results = validation_method()
            print(json.dumps(results, indent=2))
            exit(0 if results['failed'] == 0 else 1)
        else:
            print(f"Unknown validation category: {args.category}")
            exit(1)

if __name__ == "__main__":
    main()
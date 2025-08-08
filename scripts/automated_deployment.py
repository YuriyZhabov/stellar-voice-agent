#!/usr/bin/env python3
"""
Automated Deployment Scripts for LiveKit System
Создание скриптов для автоматического развертывания
Requirements: 1.1, 2.1, 3.1
"""

import os
import json
import yaml
import subprocess
import time
import requests
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomatedDeployment:
    """Автоматизированное развертывание LiveKit системы."""
    
    def __init__(self, config_file: str = "config/deployment.yaml"):
        self.config_file = config_file
        self.config = self._load_deployment_config()
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.deployment_log = []
        
    def _load_deployment_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации развертывания."""
        default_config = {
            "environments": {
                "development": {
                    "compose_file": "docker-compose.yml",
                    "env_file": ".env",
                    "health_check_url": "http://localhost:8000/health",
                    "pre_deployment_checks": ["lint", "unit_tests"],
                    "post_deployment_checks": ["health_check", "integration_tests"]
                },
                "staging": {
                    "compose_file": "docker-compose.staging.yml",
                    "env_file": ".env.staging",
                    "health_check_url": "http://staging.example.com/health",
                    "pre_deployment_checks": ["lint", "unit_tests", "security_scan"],
                    "post_deployment_checks": ["health_check", "integration_tests", "smoke_tests"]
                },
                "production": {
                    "compose_file": "docker-compose.prod.yml",
                    "env_file": ".env.production",
                    "health_check_url": "http://production.example.com/health",
                    "pre_deployment_checks": ["lint", "unit_tests", "security_scan", "performance_tests"],
                    "post_deployment_checks": ["health_check", "integration_tests", "smoke_tests", "monitoring_check"],
                    "blue_green": True,
                    "rollback_on_failure": True
                }
            },
            "checks": {
                "lint": {
                    "command": ["python", "-m", "flake8", "src/"],
                    "timeout": 60
                },
                "unit_tests": {
                    "command": ["python", "-m", "pytest", "tests/", "-v"],
                    "timeout": 300
                },
                "security_scan": {
                    "command": ["python", "-m", "bandit", "-r", "src/"],
                    "timeout": 120
                },
                "performance_tests": {
                    "command": ["python", "test_performance_final.py"],
                    "timeout": 600
                },
                "integration_tests": {
                    "command": ["python", "test_integration_simple.py"],
                    "timeout": 300
                },
                "smoke_tests": {
                    "command": ["python", "scripts/smoke_tests.py"],
                    "timeout": 180
                }
            },
            "notifications": {
                "enabled": True,
                "webhook_url": os.getenv("DEPLOYMENT_WEBHOOK_URL"),
                "channels": ["slack", "email"]
            },
            "rollback": {
                "auto_rollback": True,
                "rollback_timeout": 300,
                "health_check_retries": 3
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
    
    def deploy_to_environment(self, environment: str, version: Optional[str] = None) -> bool:
        """Развертывание в указанную среду."""
        if environment not in self.config["environments"]:
            logger.error(f"Unknown environment: {environment}")
            return False
        
        env_config = self.config["environments"][environment]
        
        logger.info(f"Starting deployment to {environment} environment")
        self._log_deployment_step("started", environment, version)
        
        try:
            # Pre-deployment checks
            if not self._run_pre_deployment_checks(env_config):
                logger.error("Pre-deployment checks failed")
                self._log_deployment_step("failed", environment, version, "pre_checks_failed")
                return False
            
            # Create rollback point
            rollback_point = self._create_deployment_rollback_point(environment)
            
            # Perform deployment
            if env_config.get("blue_green", False):
                success = self._perform_blue_green_deployment(environment, env_config)
            else:
                success = self._perform_standard_deployment(environment, env_config)
            
            if not success:
                logger.error("Deployment failed")
                if env_config.get("rollback_on_failure", False):
                    self._perform_automatic_rollback(rollback_point)
                self._log_deployment_step("failed", environment, version, "deployment_failed")
                return False
            
            # Post-deployment checks
            if not self._run_post_deployment_checks(env_config):
                logger.error("Post-deployment checks failed")
                if env_config.get("rollback_on_failure", False):
                    self._perform_automatic_rollback(rollback_point)
                self._log_deployment_step("failed", environment, version, "post_checks_failed")
                return False
            
            # Send success notification
            self._send_deployment_notification("success", environment, version)
            self._log_deployment_step("completed", environment, version)
            
            logger.info(f"Deployment to {environment} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed with exception: {e}")
            self._send_deployment_notification("failed", environment, version, str(e))
            self._log_deployment_step("failed", environment, version, f"exception: {e}")
            return False
    
    def _run_pre_deployment_checks(self, env_config: Dict[str, Any]) -> bool:
        """Выполнение проверок перед развертыванием."""
        checks = env_config.get("pre_deployment_checks", [])
        
        logger.info(f"Running {len(checks)} pre-deployment checks...")
        
        for check_name in checks:
            if not self._run_check(check_name):
                return False
        
        logger.info("All pre-deployment checks passed")
        return True
    
    def _run_post_deployment_checks(self, env_config: Dict[str, Any]) -> bool:
        """Выполнение проверок после развертывания."""
        checks = env_config.get("post_deployment_checks", [])
        
        logger.info(f"Running {len(checks)} post-deployment checks...")
        
        # Ожидание стабилизации сервисов
        time.sleep(30)
        
        for check_name in checks:
            if not self._run_check(check_name):
                return False
        
        logger.info("All post-deployment checks passed")
        return True
    
    def _run_check(self, check_name: str) -> bool:
        """Выполнение конкретной проверки."""
        if check_name not in self.config["checks"]:
            logger.warning(f"Unknown check: {check_name}")
            return True
        
        check_config = self.config["checks"][check_name]
        command = check_config["command"]
        timeout = check_config.get("timeout", 60)
        
        logger.info(f"Running check: {check_name}")
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            
            logger.info(f"Check {check_name} passed")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Check {check_name} timed out after {timeout} seconds")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Check {check_name} failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
    
    def _perform_standard_deployment(self, environment: str, env_config: Dict[str, Any]) -> bool:
        """Выполнение стандартного развертывания."""
        logger.info("Performing standard deployment...")
        
        compose_file = env_config["compose_file"]
        env_file = env_config.get("env_file", ".env")
        
        try:
            # Stop existing services
            if os.path.exists(compose_file):
                subprocess.run(
                    ["docker-compose", "-f", compose_file, "down"],
                    capture_output=True, text=True, check=True
                )
            
            # Pull latest images
            subprocess.run(
                ["docker-compose", "-f", compose_file, "pull"],
                capture_output=True, text=True, check=True
            )
            
            # Start services
            env = os.environ.copy()
            if os.path.exists(env_file):
                # Load environment variables from file
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            env[key] = value
            
            subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                capture_output=True, text=True, check=True, env=env
            )
            
            logger.info("Standard deployment completed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Standard deployment failed: {e}")
            return False
    
    def _perform_blue_green_deployment(self, environment: str, env_config: Dict[str, Any]) -> bool:
        """Выполнение blue-green развертывания."""
        logger.info("Performing blue-green deployment...")
        
        try:
            from .blue_green_deployment import BlueGreenDeployment
            
            bg_deployment = BlueGreenDeployment()
            return bg_deployment.perform_blue_green_deployment()
            
        except ImportError:
            logger.error("Blue-green deployment module not available")
            return False
        except Exception as e:
            logger.error(f"Blue-green deployment failed: {e}")
            return False
    
    def _create_deployment_rollback_point(self, environment: str) -> str:
        """Создание точки отката для развертывания."""
        try:
            from .rollback_procedures import RollbackManager
            
            rollback_manager = RollbackManager()
            rollback_point = rollback_manager.create_rollback_point(
                f"deployment_{environment}_{self.timestamp}",
                f"Pre-deployment backup for {environment}"
            )
            
            logger.info(f"Created rollback point: {rollback_point}")
            return rollback_point
            
        except ImportError:
            logger.warning("Rollback manager not available")
            return ""
        except Exception as e:
            logger.warning(f"Could not create rollback point: {e}")
            return ""
    
    def _perform_automatic_rollback(self, rollback_point: str):
        """Выполнение автоматического отката."""
        if not rollback_point:
            logger.error("No rollback point available")
            return
        
        logger.info("Performing automatic rollback...")
        
        try:
            from .rollback_procedures import RollbackManager
            
            rollback_manager = RollbackManager()
            success = rollback_manager.perform_rollback(rollback_point)
            
            if success:
                logger.info("Automatic rollback completed successfully")
            else:
                logger.error("Automatic rollback failed")
                
        except ImportError:
            logger.error("Rollback manager not available for automatic rollback")
        except Exception as e:
            logger.error(f"Automatic rollback failed: {e}")
    
    def _send_deployment_notification(self, status: str, environment: str, version: Optional[str], error: Optional[str] = None):
        """Отправка уведомления о развертывании."""
        if not self.config["notifications"]["enabled"]:
            return
        
        webhook_url = self.config["notifications"]["webhook_url"]
        if not webhook_url:
            return
        
        message = {
            "timestamp": datetime.now(UTC).isoformat(),
            "status": status,
            "environment": environment,
            "version": version or "latest",
            "deployment_id": self.timestamp
        }
        
        if error:
            message["error"] = error
        
        try:
            response = requests.post(
                webhook_url,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Deployment notification sent")
            else:
                logger.warning(f"Notification failed with status {response.status_code}")
                
        except requests.RequestException as e:
            logger.warning(f"Could not send notification: {e}")
    
    def _log_deployment_step(self, status: str, environment: str, version: Optional[str], details: Optional[str] = None):
        """Логирование шага развертывания."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "deployment_id": self.timestamp,
            "status": status,
            "environment": environment,
            "version": version or "latest",
            "details": details
        }
        
        self.deployment_log.append(log_entry)
        
        # Сохранение лога в файл
        log_file = f"deployment_log_{datetime.now(UTC).strftime('%Y%m%d')}.json"
        
        existing_log = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    existing_log = json.load(f)
            except:
                pass
        
        existing_log.append(log_entry)
        
        with open(log_file, 'w') as f:
            json.dump(existing_log, f, indent=2)
    
    def create_deployment_pipeline(self, environments: List[str]) -> bool:
        """Создание pipeline развертывания через несколько сред."""
        logger.info(f"Starting deployment pipeline: {' -> '.join(environments)}")
        
        for i, environment in enumerate(environments):
            logger.info(f"Pipeline step {i+1}/{len(environments)}: {environment}")
            
            if not self.deploy_to_environment(environment):
                logger.error(f"Pipeline failed at {environment}")
                return False
            
            # Пауза между развертываниями
            if i < len(environments) - 1:
                pause_time = 60  # 1 минута
                logger.info(f"Pausing {pause_time} seconds before next deployment...")
                time.sleep(pause_time)
        
        logger.info("Deployment pipeline completed successfully")
        return True
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Получение статуса развертывания."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "current_deployment_id": self.timestamp,
            "recent_deployments": self.deployment_log[-10:],  # Последние 10 развертываний
            "environments": list(self.config["environments"].keys()),
            "available_checks": list(self.config["checks"].keys())
        }
    
    def validate_deployment_config(self) -> Dict[str, Any]:
        """Валидация конфигурации развертывания."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Проверка существования compose файлов
        for env_name, env_config in self.config["environments"].items():
            compose_file = env_config.get("compose_file")
            if compose_file and not os.path.exists(compose_file):
                validation_results["errors"].append(f"Compose file not found for {env_name}: {compose_file}")
                validation_results["valid"] = False
            
            env_file = env_config.get("env_file")
            if env_file and not os.path.exists(env_file):
                validation_results["warnings"].append(f"Environment file not found for {env_name}: {env_file}")
        
        # Проверка команд проверок
        for check_name, check_config in self.config["checks"].items():
            command = check_config.get("command", [])
            if not command:
                validation_results["errors"].append(f"No command specified for check: {check_name}")
                validation_results["valid"] = False
        
        return validation_results

def main():
    """Основная функция для автоматического развертывания."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automated Deployment for LiveKit System")
    parser.add_argument("--deploy", metavar="ENV", help="Deploy to environment")
    parser.add_argument("--version", help="Version to deploy")
    parser.add_argument("--pipeline", nargs="+", help="Deploy through pipeline of environments")
    parser.add_argument("--status", action="store_true", help="Show deployment status")
    parser.add_argument("--validate", action="store_true", help="Validate deployment configuration")
    parser.add_argument("--check", metavar="CHECK_NAME", help="Run specific check")
    
    args = parser.parse_args()
    
    deployment = AutomatedDeployment()
    
    if args.deploy:
        success = deployment.deploy_to_environment(args.deploy, args.version)
        exit(0 if success else 1)
    
    elif args.pipeline:
        success = deployment.create_deployment_pipeline(args.pipeline)
        exit(0 if success else 1)
    
    elif args.status:
        status = deployment.get_deployment_status()
        print(json.dumps(status, indent=2))
    
    elif args.validate:
        validation = deployment.validate_deployment_config()
        print(json.dumps(validation, indent=2))
        exit(0 if validation["valid"] else 1)
    
    elif args.check:
        success = deployment._run_check(args.check)
        exit(0 if success else 1)
    
    else:
        print("Use --help for available options")

if __name__ == "__main__":
    main()
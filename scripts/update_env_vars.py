#!/usr/bin/env python3
"""
Environment Variables Update Script
Обновление переменных окружения для миграции
Requirements: 1.1, 2.1, 3.1
"""

import os
import shutil
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnvironmentUpdater:
    """Обновление переменных окружения для миграции LiveKit."""
    
    def __init__(self):
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        
    def update_environment_variables(self, env_file: str = ".env") -> bool:
        """Обновление переменных окружения."""
        logger.info(f"Updating environment variables in {env_file}")
        
        # Создание резервной копии
        if os.path.exists(env_file):
            backup_file = f"{env_file}.backup.{self.timestamp}"
            shutil.copy2(env_file, backup_file)
            logger.info(f"Created backup: {backup_file}")
        
        # Новые переменные для LiveKit системы
        new_variables = {
            # LiveKit Core Configuration
            "LIVEKIT_URL": "ws://localhost:7880",
            "LIVEKIT_API_KEY": "${LIVEKIT_API_KEY}",
            "LIVEKIT_API_SECRET": "${LIVEKIT_API_SECRET}",
            
            # JWT Configuration
            "JWT_TOKEN_EXPIRY_MINUTES": "10",
            "JWT_AUTO_REFRESH": "true",
            
            # SIP Configuration
            "SIP_SERVER": "${SIP_SERVER}",
            "SIP_PORT": "5060",
            "SIP_TRANSPORT": "UDP",
            "SIP_USERNAME": "${SIP_USERNAME}",
            "SIP_PASSWORD": "${SIP_PASSWORD}",
            "SIP_NUMBER": "${SIP_NUMBER}",
            
            # API Endpoints Configuration
            "LIVEKIT_ROOM_SERVICE_URL": "http://localhost:7880/twirp/livekit.RoomService",
            "LIVEKIT_EGRESS_SERVICE_URL": "http://localhost:7880/twirp/livekit.EgressService",
            "LIVEKIT_INGRESS_SERVICE_URL": "http://localhost:7880/twirp/livekit.IngressService",
            "LIVEKIT_SIP_SERVICE_URL": "http://localhost:7880/twirp/livekit.SIPService",
            
            # Webhook Configuration
            "WEBHOOK_SECRET": "${SECRET_KEY}",
            "WEBHOOK_TIMEOUT": "5",
            "WEBHOOK_MAX_RETRIES": "3",
            
            # Performance Configuration
            "CONNECTION_POOL_SIZE": "10",
            "CONNECTION_TIMEOUT": "30",
            "KEEP_ALIVE_INTERVAL": "25",
            "MAX_RECONNECT_ATTEMPTS": "10",
            "RECONNECT_DELAY": "1",
            
            # Monitoring Configuration
            "PROMETHEUS_ENABLED": "true",
            "PROMETHEUS_PORT": "9090",
            "METRICS_ENABLED": "true",
            "HEALTH_CHECK_INTERVAL": "60",
            
            # Security Configuration
            "SSL_VERIFY": "true",
            "API_KEY_ROTATION_ENABLED": "false",
            "LOG_SENSITIVE_DATA": "false",
            
            # Database Configuration
            "DATABASE_URL": "sqlite:///data/voice_ai.db",
            "DATABASE_POOL_SIZE": "5",
            "DATABASE_TIMEOUT": "30",
            
            # Redis Configuration
            "REDIS_URL": "redis://localhost:6379",
            "REDIS_TIMEOUT": "5",
            
            # Deployment Configuration
            "DEPLOYMENT_ENVIRONMENT": "development",
            "BLUE_GREEN_ENABLED": "false",
            "AUTO_ROLLBACK_ENABLED": "true",
            
            # Logging Configuration
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "json",
            "LOG_FILE": "logs/livekit_system.log",
            
            # Feature Flags
            "EGRESS_ENABLED": "true",
            "INGRESS_ENABLED": "true",
            "SIP_INTEGRATION_ENABLED": "true",
            "MONITORING_ENABLED": "true",
            "PERFORMANCE_OPTIMIZATION_ENABLED": "true"
        }
        
        # Чтение существующих переменных
        existing_vars = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_vars[key] = value
        
        # Объединение существующих и новых переменных
        updated_vars = existing_vars.copy()
        
        # Добавление новых переменных (не перезаписывая существующие)
        for key, value in new_variables.items():
            if key not in updated_vars:
                updated_vars[key] = value
                logger.info(f"Added new variable: {key}")
            else:
                logger.info(f"Keeping existing variable: {key}")
        
        # Обновление специфических переменных для миграции
        migration_updates = {
            "LIVEKIT_INTEGRATION_VERSION": "2.0",
            "MIGRATION_TIMESTAMP": self.timestamp,
            "SYSTEM_VERSION": "livekit-correct-config"
        }
        
        for key, value in migration_updates.items():
            updated_vars[key] = value
            logger.info(f"Updated migration variable: {key} = {value}")
        
        # Запись обновленных переменных
        with open(env_file, 'w') as f:
            f.write(f"# LiveKit System Environment Variables\n")
            f.write(f"# Updated: {datetime.now(UTC).isoformat()}\n")
            f.write(f"# Migration timestamp: {self.timestamp}\n\n")
            
            # Группировка переменных по категориям
            categories = {
                "Core LiveKit Configuration": [
                    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"
                ],
                "JWT Configuration": [
                    "JWT_TOKEN_EXPIRY_MINUTES", "JWT_AUTO_REFRESH"
                ],
                "SIP Configuration": [
                    "SIP_SERVER", "SIP_PORT", "SIP_TRANSPORT", "SIP_USERNAME", 
                    "SIP_PASSWORD", "SIP_NUMBER"
                ],
                "API Endpoints": [
                    "LIVEKIT_ROOM_SERVICE_URL", "LIVEKIT_EGRESS_SERVICE_URL",
                    "LIVEKIT_INGRESS_SERVICE_URL", "LIVEKIT_SIP_SERVICE_URL"
                ],
                "Performance Configuration": [
                    "CONNECTION_POOL_SIZE", "CONNECTION_TIMEOUT", "KEEP_ALIVE_INTERVAL",
                    "MAX_RECONNECT_ATTEMPTS", "RECONNECT_DELAY"
                ],
                "Monitoring Configuration": [
                    "PROMETHEUS_ENABLED", "PROMETHEUS_PORT", "METRICS_ENABLED",
                    "HEALTH_CHECK_INTERVAL"
                ],
                "Security Configuration": [
                    "SSL_VERIFY", "API_KEY_ROTATION_ENABLED", "LOG_SENSITIVE_DATA"
                ],
                "Database Configuration": [
                    "DATABASE_URL", "DATABASE_POOL_SIZE", "DATABASE_TIMEOUT"
                ],
                "Deployment Configuration": [
                    "DEPLOYMENT_ENVIRONMENT", "BLUE_GREEN_ENABLED", "AUTO_ROLLBACK_ENABLED"
                ]
            }
            
            # Запись переменных по категориям
            written_vars = set()
            
            for category, var_names in categories.items():
                f.write(f"# {category}\n")
                for var_name in var_names:
                    if var_name in updated_vars:
                        f.write(f"{var_name}={updated_vars[var_name]}\n")
                        written_vars.add(var_name)
                f.write("\n")
            
            # Запись остальных переменных
            f.write("# Other Configuration\n")
            for key, value in sorted(updated_vars.items()):
                if key not in written_vars:
                    f.write(f"{key}={value}\n")
        
        logger.info(f"Environment variables updated: {len(updated_vars)} total variables")
        return True
    
    def create_environment_files(self) -> bool:
        """Создание файлов окружения для разных сред."""
        environments = {
            ".env.staging": {
                "DEPLOYMENT_ENVIRONMENT": "staging",
                "LOG_LEVEL": "DEBUG",
                "PROMETHEUS_ENABLED": "true",
                "BLUE_GREEN_ENABLED": "true",
                "LIVEKIT_URL": "ws://staging.localhost:7880",
                "HEALTH_CHECK_INTERVAL": "30"
            },
            ".env.production": {
                "DEPLOYMENT_ENVIRONMENT": "production",
                "LOG_LEVEL": "INFO",
                "PROMETHEUS_ENABLED": "true",
                "BLUE_GREEN_ENABLED": "true",
                "AUTO_ROLLBACK_ENABLED": "true",
                "LIVEKIT_URL": "ws://production.localhost:7880",
                "SSL_VERIFY": "true",
                "LOG_SENSITIVE_DATA": "false",
                "HEALTH_CHECK_INTERVAL": "60"
            }
        }
        
        for env_file, overrides in environments.items():
            logger.info(f"Creating environment file: {env_file}")
            
            # Копирование базового .env файла
            if os.path.exists(".env"):
                shutil.copy2(".env", env_file)
            
            # Применение переопределений
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                # Обновление существующих переменных
                updated_lines = []
                updated_vars = set()
                
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        key = line.split('=')[0]
                        if key in overrides:
                            updated_lines.append(f"{key}={overrides[key]}\n")
                            updated_vars.add(key)
                        else:
                            updated_lines.append(line)
                    else:
                        updated_lines.append(line)
                
                # Добавление новых переменных
                for key, value in overrides.items():
                    if key not in updated_vars:
                        updated_lines.append(f"{key}={value}\n")
                
                # Запись обновленного файла
                with open(env_file, 'w') as f:
                    f.writelines(updated_lines)
            
            logger.info(f"Created {env_file} with {len(overrides)} overrides")
        
        return True
    
    def validate_environment_variables(self, env_file: str = ".env") -> Dict[str, Any]:
        """Валидация переменных окружения."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "missing_required": [],
            "total_variables": 0
        }
        
        # Обязательные переменные
        required_variables = [
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY", 
            "LIVEKIT_API_SECRET",
            "SIP_SERVER",
            "SIP_USERNAME",
            "SIP_PASSWORD",
            "SIP_NUMBER"
        ]
        
        # Чтение переменных из файла
        env_vars = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        
        validation_results["total_variables"] = len(env_vars)
        
        # Проверка обязательных переменных
        for var in required_variables:
            if var not in env_vars:
                validation_results["missing_required"].append(var)
                validation_results["errors"].append(f"Missing required variable: {var}")
                validation_results["valid"] = False
            elif not env_vars[var] or env_vars[var].startswith("${"):
                validation_results["warnings"].append(f"Variable {var} is not set or uses placeholder")
        
        # Проверка URL форматов
        url_variables = ["LIVEKIT_URL", "DATABASE_URL", "REDIS_URL"]
        for var in url_variables:
            if var in env_vars:
                value = env_vars[var]
                if not value.startswith(("http://", "https://", "ws://", "wss://", "sqlite://", "redis://")):
                    validation_results["warnings"].append(f"Variable {var} may have invalid URL format: {value}")
        
        # Проверка числовых значений
        numeric_variables = ["SIP_PORT", "CONNECTION_POOL_SIZE", "CONNECTION_TIMEOUT"]
        for var in numeric_variables:
            if var in env_vars:
                try:
                    int(env_vars[var])
                except ValueError:
                    validation_results["errors"].append(f"Variable {var} should be numeric: {env_vars[var]}")
                    validation_results["valid"] = False
        
        # Проверка булевых значений
        boolean_variables = ["PROMETHEUS_ENABLED", "SSL_VERIFY", "AUTO_ROLLBACK_ENABLED"]
        for var in boolean_variables:
            if var in env_vars:
                value = env_vars[var].lower()
                if value not in ["true", "false", "1", "0", "yes", "no"]:
                    validation_results["warnings"].append(f"Variable {var} should be boolean: {env_vars[var]}")
        
        return validation_results

def main():
    """Основная функция для обновления переменных окружения."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Environment Variables Update Script")
    parser.add_argument("--update", metavar="ENV_FILE", default=".env", help="Update environment file")
    parser.add_argument("--create-all", action="store_true", help="Create all environment files")
    parser.add_argument("--validate", metavar="ENV_FILE", default=".env", help="Validate environment file")
    
    args = parser.parse_args()
    
    updater = EnvironmentUpdater()
    
    if args.create_all:
        # Обновление основного файла
        success = updater.update_environment_variables(args.update)
        if success:
            # Создание файлов для других сред
            success = updater.create_environment_files()
        
        if success:
            print("All environment files created successfully")
        else:
            print("Failed to create environment files")
            exit(1)
    
    elif args.validate:
        validation = updater.validate_environment_variables(args.validate)
        
        print(f"Validation Results for {args.validate}:")
        print(f"Total variables: {validation['total_variables']}")
        print(f"Valid: {validation['valid']}")
        
        if validation['errors']:
            print(f"Errors ({len(validation['errors'])}):")
            for error in validation['errors']:
                print(f"  - {error}")
        
        if validation['warnings']:
            print(f"Warnings ({len(validation['warnings'])}):")
            for warning in validation['warnings']:
                print(f"  - {warning}")
        
        if validation['missing_required']:
            print(f"Missing required variables: {validation['missing_required']}")
        
        exit(0 if validation['valid'] else 1)
    
    else:
        # Обновление указанного файла
        success = updater.update_environment_variables(args.update)
        if success:
            print(f"Environment file {args.update} updated successfully")
        else:
            print(f"Failed to update environment file {args.update}")
            exit(1)

if __name__ == "__main__":
    main()
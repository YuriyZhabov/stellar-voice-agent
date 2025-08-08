#!/usr/bin/env python3
"""
Blue-Green Deployment Strategy for LiveKit System
Реализация blue-green deployment стратегии
Requirements: 1.1, 2.1, 3.1
"""

import os
import json
import yaml
import time
import subprocess
import requests
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlueGreenDeployment:
    """Blue-Green deployment стратегия для LiveKit системы."""
    
    def __init__(self, config_file: str = "config/deployment.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
        self.current_environment = self._detect_current_environment()
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации развертывания."""
        default_config = {
            "environments": {
                "blue": {
                    "compose_file": "docker-compose.blue.yml",
                    "port_offset": 0,
                    "health_check_url": "http://localhost:8000/health",
                    "services": ["livekit-server", "voice-ai-agent", "redis"]
                },
                "green": {
                    "compose_file": "docker-compose.green.yml", 
                    "port_offset": 1000,
                    "health_check_url": "http://localhost:9000/health",
                    "services": ["livekit-server", "voice-ai-agent", "redis"]
                }
            },
            "load_balancer": {
                "config_file": "nginx.conf",
                "upstream_template": "upstream_template.conf"
            },
            "health_check": {
                "timeout": 30,
                "interval": 5,
                "max_retries": 6
            },
            "rollback": {
                "auto_rollback": True,
                "rollback_timeout": 300
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
    
    def _detect_current_environment(self) -> str:
        """Определение текущей активной среды."""
        # Проверяем какие контейнеры запущены
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            running_containers = result.stdout.strip().split('\n')
            
            if any('blue' in container for container in running_containers):
                return 'blue'
            elif any('green' in container for container in running_containers):
                return 'green'
            else:
                return 'blue'  # Default to blue
                
        except subprocess.CalledProcessError:
            logger.warning("Could not detect current environment, defaulting to blue")
            return 'blue'
    
    def get_target_environment(self) -> str:
        """Получение целевой среды для развертывания."""
        return 'green' if self.current_environment == 'blue' else 'blue'
    
    def create_environment_configs(self):
        """Создание конфигурационных файлов для blue/green сред."""
        logger.info("Creating blue-green environment configurations...")
        
        # Создание docker-compose файлов для каждой среды
        for env_name, env_config in self.config["environments"].items():
            self._create_compose_file(env_name, env_config)
        
        # Создание nginx конфигурации
        self._create_nginx_config()
    
    def _create_compose_file(self, env_name: str, env_config: Dict[str, Any]):
        """Создание docker-compose файла для среды."""
        base_compose_file = "docker-compose.yml"
        
        if not os.path.exists(base_compose_file):
            logger.error(f"Base compose file {base_compose_file} not found")
            return
        
        with open(base_compose_file, 'r') as f:
            base_config = yaml.safe_load(f)
        
        # Модификация портов для среды
        port_offset = env_config.get("port_offset", 0)
        
        for service_name, service_config in base_config.get("services", {}).items():
            # Добавление префикса к имени контейнера
            service_config["container_name"] = f"{env_name}-{service_name}"
            
            # Модификация портов
            if "ports" in service_config:
                new_ports = []
                for port_mapping in service_config["ports"]:
                    if isinstance(port_mapping, str) and ":" in port_mapping:
                        host_port, container_port = port_mapping.split(":")
                        new_host_port = str(int(host_port) + port_offset)
                        new_ports.append(f"{new_host_port}:{container_port}")
                    else:
                        new_ports.append(port_mapping)
                service_config["ports"] = new_ports
            
            # Добавление меток для идентификации среды
            if "labels" not in service_config:
                service_config["labels"] = {}
            service_config["labels"]["deployment.environment"] = env_name
            service_config["labels"]["deployment.timestamp"] = self.timestamp
        
        # Сохранение модифицированного файла
        compose_file = env_config["compose_file"]
        with open(compose_file, 'w') as f:
            yaml.dump(base_config, f, default_flow_style=False)
        
        logger.info(f"Created compose file for {env_name}: {compose_file}")
    
    def _create_nginx_config(self):
        """Создание nginx конфигурации для load balancing."""
        nginx_config = """
upstream livekit_backend {
    server localhost:8000 weight=1 max_fails=3 fail_timeout=30s;
}

upstream livekit_backend_standby {
    server localhost:9000 weight=1 max_fails=3 fail_timeout=30s backup;
}

server {
    listen 80;
    server_name localhost;
    
    location /health {
        proxy_pass http://livekit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }
    
    location / {
        proxy_pass http://livekit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Health check and failover
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 2;
        proxy_next_upstream_timeout 10s;
    }
}
"""
        
        with open("nginx.conf", 'w') as f:
            f.write(nginx_config)
        
        logger.info("Created nginx configuration for load balancing")
    
    def deploy_to_environment(self, target_env: str) -> bool:
        """Развертывание в целевую среду."""
        logger.info(f"Starting deployment to {target_env} environment...")
        
        env_config = self.config["environments"][target_env]
        compose_file = env_config["compose_file"]
        
        try:
            # Остановка существующих контейнеров целевой среды
            self._stop_environment(target_env)
            
            # Запуск новых контейнеров
            logger.info(f"Starting {target_env} environment...")
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                capture_output=True, text=True, check=True
            )
            
            logger.info(f"Services started in {target_env} environment")
            
            # Ожидание готовности сервисов
            if self._wait_for_health_check(target_env):
                logger.info(f"Deployment to {target_env} successful")
                return True
            else:
                logger.error(f"Health check failed for {target_env}")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return False
    
    def _stop_environment(self, env_name: str):
        """Остановка среды."""
        env_config = self.config["environments"][env_name]
        compose_file = env_config["compose_file"]
        
        if os.path.exists(compose_file):
            try:
                subprocess.run(
                    ["docker-compose", "-f", compose_file, "down"],
                    capture_output=True, text=True, check=True
                )
                logger.info(f"Stopped {env_name} environment")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Could not stop {env_name} environment: {e}")
    
    def _wait_for_health_check(self, env_name: str) -> bool:
        """Ожидание прохождения health check."""
        env_config = self.config["environments"][env_name]
        health_url = env_config["health_check_url"]
        
        timeout = self.config["health_check"]["timeout"]
        interval = self.config["health_check"]["interval"]
        max_retries = self.config["health_check"]["max_retries"]
        
        logger.info(f"Waiting for health check: {health_url}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Health check passed for {env_name}")
                    return True
                else:
                    logger.warning(f"Health check returned {response.status_code}")
            except requests.RequestException as e:
                logger.warning(f"Health check attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(interval)
        
        logger.error(f"Health check failed after {max_retries} attempts")
        return False
    
    def switch_traffic(self, target_env: str) -> bool:
        """Переключение трафика на целевую среду."""
        logger.info(f"Switching traffic to {target_env} environment...")
        
        # Обновление nginx конфигурации
        self._update_nginx_upstream(target_env)
        
        # Перезагрузка nginx
        try:
            subprocess.run(["nginx", "-s", "reload"], check=True)
            logger.info("Nginx configuration reloaded")
            
            # Обновление текущей среды
            self.current_environment = target_env
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload nginx: {e}")
            return False
    
    def _update_nginx_upstream(self, active_env: str):
        """Обновление nginx upstream конфигурации."""
        env_config = self.config["environments"][active_env]
        port_offset = env_config.get("port_offset", 0)
        active_port = 8000 + port_offset
        
        standby_env = 'green' if active_env == 'blue' else 'blue'
        standby_config = self.config["environments"][standby_env]
        standby_port_offset = standby_config.get("port_offset", 0)
        standby_port = 8000 + standby_port_offset
        
        nginx_config = f"""
upstream livekit_backend {{
    server localhost:{active_port} weight=1 max_fails=3 fail_timeout=30s;
}}

upstream livekit_backend_standby {{
    server localhost:{standby_port} weight=1 max_fails=3 fail_timeout=30s backup;
}}

server {{
    listen 80;
    server_name localhost;
    
    location /health {{
        proxy_pass http://livekit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }}
    
    location / {{
        proxy_pass http://livekit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 2;
        proxy_next_upstream_timeout 10s;
    }}
}}
"""
        
        with open("nginx.conf", 'w') as f:
            f.write(nginx_config)
        
        logger.info(f"Updated nginx config - active: {active_env}:{active_port}")
    
    def cleanup_old_environment(self, env_name: str):
        """Очистка старой среды после успешного переключения."""
        logger.info(f"Cleaning up {env_name} environment...")
        
        # Ожидание перед очисткой (для возможности быстрого отката)
        cleanup_delay = self.config.get("cleanup_delay", 300)  # 5 минут
        logger.info(f"Waiting {cleanup_delay} seconds before cleanup...")
        time.sleep(cleanup_delay)
        
        self._stop_environment(env_name)
        logger.info(f"Cleanup completed for {env_name}")
    
    def perform_blue_green_deployment(self) -> bool:
        """Выполнение полного blue-green развертывания."""
        logger.info("Starting blue-green deployment process...")
        
        current_env = self.current_environment
        target_env = self.get_target_environment()
        
        logger.info(f"Current environment: {current_env}")
        logger.info(f"Target environment: {target_env}")
        
        # Создание конфигураций сред
        self.create_environment_configs()
        
        # Развертывание в целевую среду
        if not self.deploy_to_environment(target_env):
            logger.error("Deployment failed")
            return False
        
        # Переключение трафика
        if not self.switch_traffic(target_env):
            logger.error("Traffic switch failed")
            # Откат
            self._stop_environment(target_env)
            return False
        
        # Очистка старой среды (в фоне)
        import threading
        cleanup_thread = threading.Thread(
            target=self.cleanup_old_environment,
            args=(current_env,)
        )
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        logger.info("Blue-green deployment completed successfully")
        return True
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Получение статуса развертывания."""
        status = {
            "timestamp": datetime.now(UTC).isoformat(),
            "current_environment": self.current_environment,
            "environments": {}
        }
        
        for env_name, env_config in self.config["environments"].items():
            env_status = {
                "active": env_name == self.current_environment,
                "health_check_url": env_config["health_check_url"],
                "services": []
            }
            
            # Проверка статуса сервисов
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"label=deployment.environment={env_name}", 
                     "--format", "{{.Names}}\t{{.Status}}"],
                    capture_output=True, text=True, check=True
                )
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        name, status_text = line.split('\t', 1)
                        env_status["services"].append({
                            "name": name,
                            "status": status_text
                        })
                        
            except subprocess.CalledProcessError:
                env_status["services"] = []
            
            status["environments"][env_name] = env_status
        
        return status

def main():
    """Основная функция для выполнения blue-green развертывания."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Blue-Green Deployment for LiveKit")
    parser.add_argument("--deploy", action="store_true", help="Perform blue-green deployment")
    parser.add_argument("--status", action="store_true", help="Show deployment status")
    parser.add_argument("--create-configs", action="store_true", help="Create environment configs")
    parser.add_argument("--switch", choices=["blue", "green"], help="Switch traffic to environment")
    
    args = parser.parse_args()
    
    deployment = BlueGreenDeployment()
    
    if args.deploy:
        success = deployment.perform_blue_green_deployment()
        exit(0 if success else 1)
    
    elif args.status:
        status = deployment.get_deployment_status()
        print(json.dumps(status, indent=2))
    
    elif args.create_configs:
        deployment.create_environment_configs()
        print("Environment configurations created")
    
    elif args.switch:
        success = deployment.switch_traffic(args.switch)
        exit(0 if success else 1)
    
    else:
        print("Use --help for available options")

if __name__ == "__main__":
    main()
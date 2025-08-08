#!/usr/bin/env python3
"""
Rollback Procedures for LiveKit System
Добавление rollback процедур при проблемах
Requirements: 1.1, 2.1, 3.1
"""

import os
import json
import yaml
import shutil
import subprocess
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RollbackManager:
    """Менеджер процедур отката для LiveKit системы."""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.rollback_log = []
        
    def create_rollback_point(self, name: str, description: str = "") -> str:
        """Создание точки отката."""
        rollback_point = {
            "name": name,
            "description": description,
            "timestamp": self.timestamp,
            "files": [],
            "services": [],
            "environment_vars": {},
            "database_state": None
        }
        
        logger.info(f"Creating rollback point: {name}")
        
        # Создание директории для точки отката
        rollback_dir = self.backup_dir / f"rollback_{name}_{self.timestamp}"
        rollback_dir.mkdir(parents=True, exist_ok=True)
        
        # Резервное копирование критических файлов
        critical_files = [
            ".env",
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "livekit-sip.yaml",
            "livekit-sip-correct.yaml",
            "nginx.conf"
        ]
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                dest_path = rollback_dir / file_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
                rollback_point["files"].append(file_path)
                logger.info(f"Backed up: {file_path}")
        
        # Резервное копирование директорий с кодом
        code_dirs = ["src", "config", "scripts"]
        for dir_path in code_dirs:
            if os.path.exists(dir_path):
                dest_path = rollback_dir / dir_path
                shutil.copytree(dir_path, dest_path, dirs_exist_ok=True)
                rollback_point["files"].append(dir_path)
                logger.info(f"Backed up directory: {dir_path}")
        
        # Сохранение состояния сервисов
        rollback_point["services"] = self._capture_service_state()
        
        # Сохранение переменных окружения
        rollback_point["environment_vars"] = dict(os.environ)
        
        # Сохранение состояния базы данных
        rollback_point["database_state"] = self._capture_database_state()
        
        # Сохранение метаданных точки отката
        with open(rollback_dir / "rollback_metadata.json", "w") as f:
            json.dump(rollback_point, f, indent=2, default=str)
        
        logger.info(f"Rollback point created: {rollback_dir}")
        return str(rollback_dir)
    
    def _capture_service_state(self) -> List[Dict[str, Any]]:
        """Захват состояния сервисов."""
        services = []
        
        try:
            # Получение списка запущенных контейнеров
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        services.append({
                            "name": parts[0],
                            "image": parts[1],
                            "status": parts[2],
                            "ports": parts[3] if len(parts) > 3 else ""
                        })
        
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not capture service state: {e}")
        
        return services
    
    def _capture_database_state(self) -> Optional[Dict[str, Any]]:
        """Захват состояния базы данных."""
        db_state = None
        
        # Проверка наличия SQLite базы данных
        db_files = ["data/voice_ai.db", "voice_ai.db"]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    # Создание дампа базы данных
                    dump_file = f"database_dump_{self.timestamp}.sql"
                    subprocess.run(
                        ["sqlite3", db_file, ".dump"],
                        stdout=open(dump_file, 'w'),
                        check=True
                    )
                    
                    db_state = {
                        "type": "sqlite",
                        "file": db_file,
                        "dump_file": dump_file,
                        "size": os.path.getsize(db_file)
                    }
                    
                    logger.info(f"Database state captured: {db_file}")
                    break
                    
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Could not dump database {db_file}: {e}")
        
        return db_state
    
    def list_rollback_points(self) -> List[Dict[str, Any]]:
        """Список доступных точек отката."""
        rollback_points = []
        
        for rollback_dir in self.backup_dir.glob("rollback_*"):
            metadata_file = rollback_dir / "rollback_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        metadata["path"] = str(rollback_dir)
                        rollback_points.append(metadata)
                except Exception as e:
                    logger.warning(f"Could not read metadata from {metadata_file}: {e}")
        
        # Сортировка по времени создания (новые первыми)
        rollback_points.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return rollback_points
    
    def perform_rollback(self, rollback_point_path: str, components: Optional[List[str]] = None) -> bool:
        """Выполнение отката к указанной точке."""
        rollback_dir = Path(rollback_point_path)
        metadata_file = rollback_dir / "rollback_metadata.json"
        
        if not metadata_file.exists():
            logger.error(f"Rollback metadata not found: {metadata_file}")
            return False
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"Could not read rollback metadata: {e}")
            return False
        
        logger.info(f"Starting rollback to: {metadata['name']} ({metadata['timestamp']})")
        
        # Создание точки отката перед откатом (на случай проблем)
        pre_rollback_point = self.create_rollback_point(
            f"pre_rollback_{metadata['name']}", 
            "Automatic backup before rollback"
        )
        
        rollback_success = True
        
        try:
            # Остановка сервисов
            if not components or "services" in components:
                if not self._stop_all_services():
                    logger.warning("Could not stop all services cleanly")
            
            # Восстановление файлов
            if not components or "files" in components:
                if not self._restore_files(rollback_dir, metadata):
                    rollback_success = False
            
            # Восстановление базы данных
            if not components or "database" in components:
                if not self._restore_database(metadata):
                    rollback_success = False
            
            # Запуск сервисов
            if not components or "services" in components:
                if not self._start_services(metadata):
                    rollback_success = False
            
            # Проверка здоровья системы после отката
            if rollback_success:
                if self._verify_rollback_health():
                    logger.info("Rollback completed successfully")
                    self._log_rollback_action("success", metadata, components)
                else:
                    logger.error("Rollback health check failed")
                    rollback_success = False
            
            if not rollback_success:
                logger.error("Rollback failed, attempting to restore pre-rollback state")
                self._emergency_restore(pre_rollback_point)
                self._log_rollback_action("failed", metadata, components)
        
        except Exception as e:
            logger.error(f"Rollback failed with exception: {e}")
            self._emergency_restore(pre_rollback_point)
            rollback_success = False
        
        return rollback_success
    
    def _stop_all_services(self) -> bool:
        """Остановка всех сервисов."""
        logger.info("Stopping all services...")
        
        compose_files = ["docker-compose.yml", "docker-compose.prod.yml", 
                        "docker-compose.blue.yml", "docker-compose.green.yml"]
        
        for compose_file in compose_files:
            if os.path.exists(compose_file):
                try:
                    subprocess.run(
                        ["docker-compose", "-f", compose_file, "down"],
                        capture_output=True, text=True, check=True
                    )
                    logger.info(f"Stopped services from {compose_file}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Could not stop services from {compose_file}: {e}")
        
        return True
    
    def _restore_files(self, rollback_dir: Path, metadata: Dict[str, Any]) -> bool:
        """Восстановление файлов из точки отката."""
        logger.info("Restoring files...")
        
        success = True
        
        for file_path in metadata.get("files", []):
            source_path = rollback_dir / file_path
            
            if source_path.exists():
                try:
                    if source_path.is_dir():
                        if os.path.exists(file_path):
                            shutil.rmtree(file_path)
                        shutil.copytree(source_path, file_path)
                    else:
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        shutil.copy2(source_path, file_path)
                    
                    logger.info(f"Restored: {file_path}")
                    
                except Exception as e:
                    logger.error(f"Could not restore {file_path}: {e}")
                    success = False
            else:
                logger.warning(f"Backup file not found: {source_path}")
        
        return success
    
    def _restore_database(self, metadata: Dict[str, Any]) -> bool:
        """Восстановление базы данных."""
        db_state = metadata.get("database_state")
        
        if not db_state:
            logger.info("No database state to restore")
            return True
        
        logger.info("Restoring database...")
        
        try:
            db_file = db_state["file"]
            dump_file = db_state["dump_file"]
            
            if os.path.exists(dump_file):
                # Удаление текущей базы данных
                if os.path.exists(db_file):
                    os.remove(db_file)
                
                # Восстановление из дампа
                with open(dump_file, 'r') as f:
                    subprocess.run(
                        ["sqlite3", db_file],
                        stdin=f,
                        check=True
                    )
                
                logger.info(f"Database restored: {db_file}")
                return True
            else:
                logger.warning(f"Database dump not found: {dump_file}")
                return False
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def _start_services(self, metadata: Dict[str, Any]) -> bool:
        """Запуск сервисов."""
        logger.info("Starting services...")
        
        # Определение основного compose файла
        compose_file = "docker-compose.yml"
        if os.path.exists("docker-compose.prod.yml"):
            compose_file = "docker-compose.prod.yml"
        
        try:
            subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                capture_output=True, text=True, check=True
            )
            
            logger.info("Services started")
            
            # Ожидание готовности сервисов
            time.sleep(30)
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Could not start services: {e}")
            return False
    
    def _verify_rollback_health(self) -> bool:
        """Проверка здоровья системы после отката."""
        logger.info("Verifying system health after rollback...")
        
        health_checks = [
            self._check_service_health,
            self._check_api_endpoints,
            self._check_database_connectivity
        ]
        
        for check in health_checks:
            if not check():
                return False
        
        logger.info("System health verification passed")
        return True
    
    def _check_service_health(self) -> bool:
        """Проверка здоровья сервисов."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "status=running", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            
            running_services = result.stdout.strip().split('\n')
            if len(running_services) > 0 and running_services[0]:
                logger.info(f"Running services: {len(running_services)}")
                return True
            else:
                logger.error("No services are running")
                return False
                
        except subprocess.CalledProcessError:
            logger.error("Could not check service health")
            return False
    
    def _check_api_endpoints(self) -> bool:
        """Проверка API эндпоинтов."""
        import requests
        
        endpoints = [
            "http://localhost:8000/health",
            "http://localhost:8000/metrics"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                if response.status_code == 200:
                    logger.info(f"API endpoint healthy: {endpoint}")
                else:
                    logger.warning(f"API endpoint returned {response.status_code}: {endpoint}")
            except requests.RequestException as e:
                logger.warning(f"API endpoint check failed {endpoint}: {e}")
        
        return True  # Non-critical for rollback success
    
    def _check_database_connectivity(self) -> bool:
        """Проверка подключения к базе данных."""
        db_files = ["data/voice_ai.db", "voice_ai.db"]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                try:
                    subprocess.run(
                        ["sqlite3", db_file, "SELECT 1;"],
                        capture_output=True, text=True, check=True
                    )
                    logger.info(f"Database connectivity verified: {db_file}")
                    return True
                except subprocess.CalledProcessError:
                    logger.warning(f"Database connectivity check failed: {db_file}")
        
        return True  # Non-critical for rollback success
    
    def _emergency_restore(self, pre_rollback_point: str):
        """Экстренное восстановление состояния перед откатом."""
        logger.info("Performing emergency restore...")
        
        try:
            # Простое восстановление критических файлов
            rollback_dir = Path(pre_rollback_point)
            metadata_file = rollback_dir / "rollback_metadata.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                self._restore_files(rollback_dir, metadata)
                logger.info("Emergency restore completed")
            
        except Exception as e:
            logger.error(f"Emergency restore failed: {e}")
    
    def _log_rollback_action(self, status: str, metadata: Dict[str, Any], components: Optional[List[str]]):
        """Логирование действий отката."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": "rollback",
            "status": status,
            "rollback_point": metadata.get("name"),
            "rollback_timestamp": metadata.get("timestamp"),
            "components": components or ["all"]
        }
        
        self.rollback_log.append(log_entry)
        
        # Сохранение лога в файл
        log_file = f"rollback_log_{datetime.now(UTC).strftime('%Y%m%d')}.json"
        
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
    
    def get_rollback_status(self) -> Dict[str, Any]:
        """Получение статуса системы отката."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "available_rollback_points": len(self.list_rollback_points()),
            "recent_rollbacks": self.rollback_log[-5:],  # Последние 5 откатов
            "backup_directory": str(self.backup_dir),
            "disk_usage": self._get_backup_disk_usage()
        }
    
    def _get_backup_disk_usage(self) -> Dict[str, Any]:
        """Получение информации об использовании диска для резервных копий."""
        try:
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(self.backup_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
            
            return {
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "directory_count": len(list(self.backup_dir.glob("rollback_*")))
            }
            
        except Exception as e:
            logger.warning(f"Could not calculate disk usage: {e}")
            return {"error": str(e)}

def main():
    """Основная функция для управления откатами."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Rollback Manager for LiveKit System")
    parser.add_argument("--create", metavar="NAME", help="Create rollback point")
    parser.add_argument("--list", action="store_true", help="List available rollback points")
    parser.add_argument("--rollback", metavar="PATH", help="Perform rollback to specified point")
    parser.add_argument("--components", nargs="+", choices=["files", "services", "database"], 
                       help="Specify components to rollback")
    parser.add_argument("--status", action="store_true", help="Show rollback system status")
    parser.add_argument("--description", help="Description for rollback point")
    
    args = parser.parse_args()
    
    rollback_manager = RollbackManager()
    
    if args.create:
        rollback_point = rollback_manager.create_rollback_point(
            args.create, 
            args.description or ""
        )
        print(f"Rollback point created: {rollback_point}")
    
    elif args.list:
        points = rollback_manager.list_rollback_points()
        print(f"Available rollback points ({len(points)}):")
        for point in points:
            print(f"  {point['name']} - {point['timestamp']} - {point.get('description', '')}")
            print(f"    Path: {point['path']}")
    
    elif args.rollback:
        success = rollback_manager.perform_rollback(args.rollback, args.components)
        exit(0 if success else 1)
    
    elif args.status:
        status = rollback_manager.get_rollback_status()
        print(json.dumps(status, indent=2))
    
    else:
        print("Use --help for available options")

if __name__ == "__main__":
    main()
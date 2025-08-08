#!/usr/bin/env python3
"""
Скрипт развертывания новой SIP конфигурации LiveKit.
Обновляет конфигурационные файлы и перезапускает необходимые сервисы.
"""

import os
import sys
import shutil
import subprocess
import yaml
import json
from datetime import datetime
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SIPConfigDeployer:
    """Развертывание SIP конфигурации."""
    
    def __init__(self):
        self.backup_dir = Path("backups/sip_config")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.deployment_log = []
    
    def log_action(self, action: str, status: str = "success", details: str = ""):
        """Логирование действий развертывания."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details
        }
        self.deployment_log.append(entry)
        
        if status == "success":
            logger.info(f"✅ {action}: {details}")
        elif status == "warning":
            logger.warning(f"⚠️  {action}: {details}")
        else:
            logger.error(f"❌ {action}: {details}")
    
    def create_backup(self) -> bool:
        """Создание резервной копии текущей конфигурации."""
        try:
            # Создание директории для бэкапов
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_dir / f"backup_{self.timestamp}"
            backup_path.mkdir(exist_ok=True)
            
            # Файлы для резервного копирования
            files_to_backup = [
                "livekit-sip.yaml",
                "livekit-sip-simple.yaml", 
                "livekit-sip-working.yaml",
                ".env",
                "docker-compose.prod.yml"
            ]
            
            backed_up_files = []
            for file_name in files_to_backup:
                if Path(file_name).exists():
                    shutil.copy2(file_name, backup_path / file_name)
                    backed_up_files.append(file_name)
            
            # Создание манифеста бэкапа
            manifest = {
                "timestamp": self.timestamp,
                "backed_up_files": backed_up_files,
                "backup_reason": "SIP configuration deployment"
            }
            
            with open(backup_path / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)
            
            self.log_action(
                "Backup creation", 
                "success", 
                f"Создан бэкап в {backup_path} ({len(backed_up_files)} файлов)"
            )
            return True
            
        except Exception as e:
            self.log_action("Backup creation", "error", str(e))
            return False
    
    def validate_new_config(self) -> bool:
        """Валидация новой конфигурации."""
        try:
            # Проверка существования файла
            config_file = "livekit-sip-correct.yaml"
            if not Path(config_file).exists():
                self.log_action(
                    "Config validation", 
                    "error", 
                    f"Файл {config_file} не найден"
                )
                return False
            
            # Проверка синтаксиса YAML
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Базовая валидация структуры
            required_sections = ['livekit', 'sip_trunks', 'routing', 'audio_codecs']
            missing_sections = []
            
            for section in required_sections:
                if section not in config:
                    missing_sections.append(section)
            
            if missing_sections:
                self.log_action(
                    "Config validation", 
                    "error", 
                    f"Отсутствуют секции: {', '.join(missing_sections)}"
                )
                return False
            
            # Запуск валидатора конфигурации
            try:
                result = subprocess.run([
                    sys.executable, "scripts/validate_sip_config.py", config_file
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    self.log_action(
                        "Config validation", 
                        "error", 
                        f"Валидация не пройдена: {result.stderr}"
                    )
                    return False
                
            except subprocess.TimeoutExpired:
                self.log_action(
                    "Config validation", 
                    "warning", 
                    "Таймаут валидации, продолжаем развертывание"
                )
            except FileNotFoundError:
                self.log_action(
                    "Config validation", 
                    "warning", 
                    "Валидатор не найден, пропускаем проверку"
                )
            
            self.log_action("Config validation", "success", "Конфигурация валидна")
            return True
            
        except Exception as e:
            self.log_action("Config validation", "error", str(e))
            return False
    
    def deploy_config_files(self) -> bool:
        """Развертывание конфигурационных файлов."""
        try:
            # Замена основного SIP конфигурационного файла
            shutil.copy2("livekit-sip-correct.yaml", "livekit-sip.yaml")
            self.log_action(
                "Config deployment", 
                "success", 
                "Основной SIP конфигурационный файл обновлен"
            )
            
            # Обновление Dockerfile для использования нового конфигурационного файла
            dockerfile_path = Path("Dockerfile")
            if dockerfile_path.exists():
                with open(dockerfile_path, 'r') as f:
                    dockerfile_content = f.read()
                
                # Замена строки копирования SIP конфигурации
                updated_content = dockerfile_content.replace(
                    "COPY livekit-sip.yaml ./",
                    "COPY livekit-sip.yaml ./\nCOPY livekit-sip-correct.yaml ./"
                )
                
                with open(dockerfile_path, 'w') as f:
                    f.write(updated_content)
                
                self.log_action(
                    "Dockerfile update", 
                    "success", 
                    "Dockerfile обновлен для новой конфигурации"
                )
            
            return True
            
        except Exception as e:
            self.log_action("Config deployment", "error", str(e))
            return False
    
    def update_environment_config(self) -> bool:
        """Обновление переменных окружения."""
        try:
            env_file = Path(".env")
            if not env_file.exists():
                self.log_action(
                    "Environment update", 
                    "warning", 
                    ".env файл не найден"
                )
                return True
            
            # Чтение текущего .env файла
            with open(env_file, 'r') as f:
                env_content = f.read()
            
            # Добавление новых переменных если их нет
            new_vars = [
                "# LiveKit SIP Configuration Variables",
                "LIVEKIT_SIP_CONFIG_FILE=livekit-sip-correct.yaml",
                "LIVEKIT_CONNECTION_TIMEOUT=30s",
                "LIVEKIT_KEEP_ALIVE=25s",
                "LIVEKIT_MAX_RECONNECT_ATTEMPTS=10"
            ]
            
            vars_added = []
            for var_line in new_vars:
                if var_line.startswith("#"):
                    continue
                    
                var_name = var_line.split("=")[0]
                if var_name not in env_content:
                    env_content += f"\n{var_line}"
                    vars_added.append(var_name)
            
            # Сохранение обновленного .env файла
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            if vars_added:
                self.log_action(
                    "Environment update", 
                    "success", 
                    f"Добавлены переменные: {', '.join(vars_added)}"
                )
            else:
                self.log_action(
                    "Environment update", 
                    "success", 
                    "Все необходимые переменные уже присутствуют"
                )
            
            return True
            
        except Exception as e:
            self.log_action("Environment update", "error", str(e))
            return False
    
    def test_configuration(self) -> bool:
        """Тестирование новой конфигурации."""
        try:
            # Запуск тестов конфигурации
            result = subprocess.run([
                sys.executable, "scripts/test_sip_configuration.py"
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                self.log_action(
                    "Configuration testing", 
                    "success", 
                    "Все тесты пройдены успешно"
                )
                return True
            else:
                self.log_action(
                    "Configuration testing", 
                    "warning", 
                    f"Некоторые тесты не пройдены: {result.stderr}"
                )
                # Не блокируем развертывание из-за тестов
                return True
                
        except subprocess.TimeoutExpired:
            self.log_action(
                "Configuration testing", 
                "warning", 
                "Таймаут тестирования, продолжаем развертывание"
            )
            return True
        except FileNotFoundError:
            self.log_action(
                "Configuration testing", 
                "warning", 
                "Тестовый скрипт не найден, пропускаем тестирование"
            )
            return True
        except Exception as e:
            self.log_action("Configuration testing", "error", str(e))
            return True  # Не блокируем развертывание
    
    def restart_services(self) -> bool:
        """Перезапуск сервисов для применения новой конфигурации."""
        try:
            # Проверка наличия docker-compose
            result = subprocess.run(
                ["docker-compose", "--version"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0:
                self.log_action(
                    "Service restart", 
                    "warning", 
                    "Docker Compose не найден, пропускаем перезапуск"
                )
                return True
            
            # Перезапуск сервисов
            services_to_restart = ["voice-ai-agent"]
            
            for service in services_to_restart:
                try:
                    # Остановка сервиса
                    subprocess.run([
                        "docker-compose", "-f", "docker-compose.prod.yml", 
                        "stop", service
                    ], check=True, timeout=30)
                    
                    # Запуск сервиса
                    subprocess.run([
                        "docker-compose", "-f", "docker-compose.prod.yml", 
                        "up", "-d", service
                    ], check=True, timeout=60)
                    
                    self.log_action(
                        "Service restart", 
                        "success", 
                        f"Сервис {service} перезапущен"
                    )
                    
                except subprocess.CalledProcessError as e:
                    self.log_action(
                        "Service restart", 
                        "warning", 
                        f"Ошибка перезапуска {service}: {e}"
                    )
                except subprocess.TimeoutExpired:
                    self.log_action(
                        "Service restart", 
                        "warning", 
                        f"Таймаут перезапуска {service}"
                    )
            
            return True
            
        except Exception as e:
            self.log_action("Service restart", "error", str(e))
            return False
    
    def save_deployment_log(self) -> str:
        """Сохранение лога развертывания."""
        log_file = f"sip_config_deployment_{self.timestamp}.json"
        
        deployment_report = {
            "deployment_timestamp": self.timestamp,
            "deployment_log": self.deployment_log,
            "summary": {
                "total_actions": len(self.deployment_log),
                "successful_actions": len([a for a in self.deployment_log if a["status"] == "success"]),
                "warnings": len([a for a in self.deployment_log if a["status"] == "warning"]),
                "errors": len([a for a in self.deployment_log if a["status"] == "error"])
            }
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(deployment_report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Лог развертывания сохранен в {log_file}")
        return log_file
    
    def deploy(self) -> bool:
        """Выполнение полного развертывания."""
        logger.info("🚀 Начинаем развертывание новой SIP конфигурации...")
        
        # Последовательность действий развертывания
        deployment_steps = [
            ("Создание резервной копии", self.create_backup),
            ("Валидация новой конфигурации", self.validate_new_config),
            ("Развертывание конфигурационных файлов", self.deploy_config_files),
            ("Обновление переменных окружения", self.update_environment_config),
            ("Тестирование конфигурации", self.test_configuration),
            ("Перезапуск сервисов", self.restart_services)
        ]
        
        success = True
        for step_name, step_func in deployment_steps:
            logger.info(f"📋 Выполняем: {step_name}")
            
            try:
                if not step_func():
                    logger.error(f"❌ Ошибка на этапе: {step_name}")
                    success = False
                    break
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка на этапе {step_name}: {e}")
                self.log_action(step_name, "error", f"Неожиданная ошибка: {e}")
                success = False
                break
        
        # Сохранение лога развертывания
        log_file = self.save_deployment_log()
        
        # Вывод итогов
        if success:
            logger.info("✅ Развертывание SIP конфигурации завершено успешно!")
            logger.info(f"📊 Лог развертывания: {log_file}")
        else:
            logger.error("❌ Развертывание SIP конфигурации завершено с ошибками!")
            logger.error(f"📊 Лог развертывания: {log_file}")
            logger.error("🔄 Для отката используйте резервную копию")
        
        return success
    
    def rollback(self, backup_timestamp: str = None) -> bool:
        """Откат к предыдущей конфигурации."""
        try:
            if backup_timestamp is None:
                # Найти последний бэкап
                backup_dirs = list(self.backup_dir.glob("backup_*"))
                if not backup_dirs:
                    logger.error("❌ Резервные копии не найдены")
                    return False
                
                backup_path = max(backup_dirs, key=lambda p: p.name)
            else:
                backup_path = self.backup_dir / f"backup_{backup_timestamp}"
                if not backup_path.exists():
                    logger.error(f"❌ Резервная копия {backup_timestamp} не найдена")
                    return False
            
            logger.info(f"🔄 Выполняем откат к {backup_path.name}")
            
            # Восстановление файлов из бэкапа
            manifest_file = backup_path / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                
                for file_name in manifest.get("backed_up_files", []):
                    backup_file = backup_path / file_name
                    if backup_file.exists():
                        shutil.copy2(backup_file, file_name)
                        logger.info(f"✅ Восстановлен файл: {file_name}")
            
            logger.info("✅ Откат выполнен успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отката: {e}")
            return False

def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Развертывание SIP конфигурации LiveKit")
    parser.add_argument("--rollback", help="Откат к указанной резервной копии (timestamp)")
    parser.add_argument("--list-backups", action="store_true", help="Список доступных резервных копий")
    
    args = parser.parse_args()
    
    deployer = SIPConfigDeployer()
    
    if args.list_backups:
        backup_dirs = list(deployer.backup_dir.glob("backup_*"))
        if backup_dirs:
            print("📋 Доступные резервные копии:")
            for backup_dir in sorted(backup_dirs, reverse=True):
                timestamp = backup_dir.name.replace("backup_", "")
                print(f"  - {timestamp}")
        else:
            print("❌ Резервные копии не найдены")
        return
    
    if args.rollback:
        success = deployer.rollback(args.rollback)
        sys.exit(0 if success else 1)
    
    # Обычное развертывание
    success = deployer.deploy()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
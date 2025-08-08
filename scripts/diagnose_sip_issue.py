#!/usr/bin/env python3
"""
Диагностика проблем с SIP интеграцией.
"""

import asyncio
import json
import logging
import socket
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SIPDiagnostic:
    """Диагностика SIP проблем."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.sip_config = self._load_sip_config()
    
    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        return logging.getLogger(__name__)
    
    def _load_sip_config(self):
        try:
            from src.config import get_settings
            settings = get_settings()
            
            return {
                "sip_number": settings.sip_number,
                "sip_server": settings.sip_server,
                "sip_username": settings.sip_username,
                "sip_password": settings.sip_password,
                "public_ip": settings.public_ip,
                "domain": settings.domain,
                "livekit_url": settings.livekit_url,
                "livekit_sip_uri": settings.livekit_sip_uri
            }
        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации: {e}")
            return {}
    
    def check_sip_configuration(self):
        self.logger.info("🔍 Проверка SIP конфигурации...")
        
        required_fields = ["sip_number", "sip_server", "sip_username", "sip_password", "public_ip"]
        missing_fields = []
        
        for field in required_fields:
            value = self.sip_config.get(field)
            if not value:
                missing_fields.append(field)
            else:
                self.logger.info(f"✅ {field}: {value}")
        
        if missing_fields:
            self.logger.error(f"❌ Отсутствуют поля: {missing_fields}")
            return False
        
        return True
    
    def check_network_connectivity(self):
        self.logger.info("🌐 Проверка сетевой связности...")
        
        sip_server = self.sip_config.get("sip_server")
        if not sip_server:
            self.logger.error("❌ SIP сервер не указан")
            return False
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((sip_server, 5060))
            sock.close()
            
            if result == 0:
                self.logger.info(f"✅ TCP подключение к {sip_server}:5060 успешно")
                return True
            else:
                self.logger.error(f"❌ Не удается подключиться к {sip_server}:5060")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка проверки связности: {e}")
            return False
    
    def check_docker_logs(self):
        self.logger.info("📋 Проверка логов Docker...")
        
        try:
            import subprocess
            
            result = subprocess.run(
                ["docker", "logs", "--tail", "50", "voice-ai-agent-prod"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                self.logger.error("❌ Не удается получить логи")
                return False
            
            logs = result.stdout + result.stderr
            
            # Поиск SIP ошибок
            sip_errors = []
            for line in logs.split('\n'):
                if 'sip' in line.lower() and ('error' in line.lower() or 'failed' in line.lower()):
                    sip_errors.append(line.strip())
            
            if sip_errors:
                self.logger.error(f"❌ Найдено {len(sip_errors)} SIP ошибок:")
                for error in sip_errors[-3:]:
                    self.logger.error(f"   {error}")
                return False
            else:
                self.logger.info("✅ SIP ошибок в логах не найдено")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка анализа логов: {e}")
            return False
    
    def generate_fix_recommendations(self):
        print("\n" + "=" * 80)
        print("🔧 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
        print("=" * 80)
        print()
        print("1. 📞 ПРОВЕРЬТЕ СТАТУС НОМЕРА В NOVOFON:")
        print("   - Войдите в панель управления Novofon")
        print("   - Проверьте что номер +79952227978 активен")
        print("   - Убедитесь что нет блокировок")
        print()
        print("2. 🌐 ПРОВЕРЬТЕ WEBHOOK URL:")
        print(f"   - URL должен быть доступен: http://{self.sip_config.get('domain', 'agentio.ru')}:8000/webhooks/livekit")
        print("   - Проверьте что порт 8000 открыт извне")
        print("   - Убедитесь что домен резолвится правильно")
        print()
        print("3. 🔧 ПРОВЕРЬТЕ LIVEKIT SIP НАСТРОЙКИ:")
        print("   - Убедитесь что LiveKit SIP правильно настроен")
        print("   - Проверьте что SIP URI корректный")
        print("   - Убедитесь что есть маршрутизация входящих звонков")
        print()
        print("4. 📋 ПРОВЕРЬТЕ ЛОГИ ПРИЛОЖЕНИЯ:")
        print("   docker logs -f voice-ai-agent-prod")
        print()
        print("5. 🆘 СВЯЖИТЕСЬ С ПОДДЕРЖКОЙ:")
        print("   - Novofon: поддержка по настройке SIP")
        print("   - Проверьте настройки маршрутизации звонков")
        print()
        print("=" * 80)
    
    async def run_diagnostic(self):
        print("🔍 ДИАГНОСТИКА SIP ПРОБЛЕМ")
        print("=" * 50)
        
        results = {}
        results["config"] = self.check_sip_configuration()
        results["network"] = self.check_network_connectivity()
        results["logs"] = self.check_docker_logs()
        
        print(f"\n📊 РЕЗУЛЬТАТЫ:")
        for check, passed in results.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}: {'OK' if passed else 'ОШИБКА'}")
        
        self.generate_fix_recommendations()
        
        return all(results.values())


async def main():
    diagnostic = SIPDiagnostic()
    success = await diagnostic.run_diagnostic()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
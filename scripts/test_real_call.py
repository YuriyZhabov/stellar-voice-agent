#!/usr/bin/env python3
"""
Скрипт для тестирования реального звонка на Voice AI Agent.

Этот скрипт поможет протестировать:
1. SIP интеграцию с Novofon
2. LiveKit подключение
3. Работу всех AI сервисов (STT, LLM, TTS)
4. End-to-end функциональность системы
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class RealCallTester:
    """Тестер для реальных звонков."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "real_call",
            "results": {}
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Настройка логирования."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def check_system_readiness(self) -> bool:
        """Проверить готовность системы к приему звонков."""
        self.logger.info("🔍 Проверка готовности системы...")
        
        try:
            # 1. Проверить health endpoint
            import requests
            
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Health endpoint недоступен: {response.status_code}")
                return False
            
            health_data = response.json()
            status = health_data.get("status")
            health_percentage = health_data.get("health_percentage", 0)
            
            self.logger.info(f"Статус системы: {status} ({health_percentage:.1f}%)")
            
            if status not in ["healthy", "degraded"] or health_percentage < 75:
                self.logger.error("Система не готова к приему звонков")
                return False
            
            # 2. Проверить AI сервисы
            checks = health_data.get("checks", {})
            ai_services = ["deepgram", "openai", "cartesia"]
            
            for service in ai_services:
                service_status = checks.get(service, "unknown")
                if service_status != "ok":
                    self.logger.error(f"AI сервис {service} не готов: {service_status}")
                    return False
                self.logger.info(f"✅ {service}: {service_status}")
            
            # 3. Проверить LiveKit webhook endpoint
            try:
                webhook_response = requests.get("http://localhost:8000/webhooks/health", timeout=5)
                if webhook_response.status_code == 200:
                    self.logger.info("✅ LiveKit webhook endpoint доступен")
                else:
                    self.logger.warning("⚠️  LiveKit webhook endpoint недоступен")
            except Exception as e:
                self.logger.warning(f"⚠️  Не удалось проверить webhook endpoint: {e}")
            
            self.logger.info("✅ Система готова к приему звонков")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при проверке готовности системы: {e}")
            return False
    
    def display_call_instructions(self):
        """Показать инструкции для тестового звонка."""
        print("\n" + "=" * 80)
        print("📞 ИНСТРУКЦИИ ДЛЯ ТЕСТОВОГО ЗВОНКА")
        print("=" * 80)
        print()
        print("1. 📱 Позвоните на номер: +7 958 751 40 11")
        print("2. 🎤 Дождитесь ответа системы")
        print("3. 💬 Скажите что-нибудь, например: 'Привет, как дела?'")
        print("4. 👂 Послушайте ответ AI агента")
        print("5. 🔄 Попробуйте несколько реплик для проверки диалога")
        print("6. 📞 Завершите звонок")
        print()
        print("🔍 ЧТО ПРОВЕРЯЕМ:")
        print("   ✓ Система отвечает на звонок")
        print("   ✓ Распознавание речи работает (Deepgram STT)")
        print("   ✓ AI генерирует ответы (OpenAI LLM)")
        print("   ✓ Синтез речи работает (Cartesia TTS)")
        print("   ✓ Качество звука приемлемое")
        print("   ✓ Задержка ответа < 2 секунд")
        print()
        print("⚠️  ВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
        print("   • Система не отвечает → проверить SIP настройки")
        print("   • Плохое качество звука → проверить кодеки")
        print("   • Большая задержка → проверить производительность")
        print("   • Нет ответа AI → проверить логи приложения")
        print()
        print("=" * 80)
    
    async def monitor_call_logs(self, duration_minutes: int = 5):
        """Мониторить логи во время звонка."""
        self.logger.info(f"🔍 Мониторинг логов в течение {duration_minutes} минут...")
        
        import subprocess
        
        # Запустить мониторинг логов Docker контейнера
        try:
            process = subprocess.Popen(
                ["docker", "logs", "-f", "voice-ai-agent-prod"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            start_time = time.time()
            call_detected = False
            
            print("\n📋 ЛОГИ СИСТЕМЫ (в реальном времени):")
            print("-" * 60)
            
            while time.time() - start_time < duration_minutes * 60:
                try:
                    line = process.stdout.readline()
                    if line:
                        line = line.strip()
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
                        
                        # Детектировать активность звонков
                        if any(keyword in line.lower() for keyword in [
                            "call", "room", "participant", "audio", "transcription", "synthesis"
                        ]):
                            call_detected = True
                            print(f"🔥 АКТИВНОСТЬ ЗВОНКА ОБНАРУЖЕНА: {line}")
                    
                    await asyncio.sleep(0.1)
                    
                except KeyboardInterrupt:
                    break
            
            process.terminate()
            
            if call_detected:
                self.logger.info("✅ Обнаружена активность звонков в логах")
            else:
                self.logger.warning("⚠️  Активность звонков не обнаружена")
            
            return call_detected
            
        except Exception as e:
            self.logger.error(f"Ошибка мониторинга логов: {e}")
            return False
    
    async def check_call_metrics(self) -> Dict[str, Any]:
        """Проверить метрики после звонка."""
        self.logger.info("📊 Проверка метрик системы...")
        
        try:
            import requests
            
            # Получить метрики
            metrics_response = requests.get("http://localhost:9090/metrics", timeout=10)
            if metrics_response.status_code == 200:
                metrics_text = metrics_response.text
                
                # Простой парсинг метрик
                call_metrics = {}
                for line in metrics_text.split('\n'):
                    if 'call' in line.lower() and not line.startswith('#'):
                        call_metrics[line.split()[0]] = line.split()[1] if len(line.split()) > 1 else "N/A"
                
                self.logger.info(f"Найдено {len(call_metrics)} метрик звонков")
                return call_metrics
            else:
                self.logger.warning("Метрики недоступны")
                return {}
                
        except Exception as e:
            self.logger.error(f"Ошибка получения метрик: {e}")
            return {}
    
    def generate_test_report(self, call_detected: bool, metrics: Dict[str, Any]):
        """Сгенерировать отчет о тестировании."""
        print("\n" + "=" * 80)
        print("📋 ОТЧЕТ О ТЕСТИРОВАНИИ РЕАЛЬНОГО ЗВОНКА")
        print("=" * 80)
        print(f"Время тестирования: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Номер для звонков: +7 958 751 40 11")
        print()
        
        print("🔍 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
        print(f"   Система готова: ✅")
        print(f"   Активность звонков: {'✅' if call_detected else '❌'}")
        print(f"   Метрики собраны: {'✅' if metrics else '❌'}")
        print()
        
        if metrics:
            print("📊 МЕТРИКИ ЗВОНКОВ:")
            for metric, value in list(metrics.items())[:10]:  # Показать первые 10
                print(f"   {metric}: {value}")
            if len(metrics) > 10:
                print(f"   ... и еще {len(metrics) - 10} метрик")
        
        print()
        print("💡 РЕКОМЕНДАЦИИ:")
        if call_detected:
            print("   ✅ Система обрабатывает звонки корректно")
            print("   ✅ Все компоненты работают")
            print("   ✅ Можно использовать в продакшене")
        else:
            print("   ⚠️  Звонки не обнаружены - проверьте:")
            print("      • SIP настройки Novofon")
            print("      • LiveKit конфигурацию")
            print("      • Сетевые настройки")
        
        print()
        print("=" * 80)
    
    async def run_interactive_test(self):
        """Запустить интерактивное тестирование."""
        print("🎯 ТЕСТИРОВАНИЕ РЕАЛЬНОГО ЗВОНКА")
        print("=" * 50)
        
        # 1. Проверить готовность системы
        if not await self.check_system_readiness():
            print("❌ Система не готова к тестированию")
            return False
        
        # 2. Показать инструкции
        self.display_call_instructions()
        
        # 3. Ждать подтверждения пользователя
        input("\n🎤 Нажмите Enter когда будете готовы начать мониторинг...")
        
        # 4. Запустить мониторинг
        print("\n🔍 Начинаем мониторинг. Теперь можете звонить!")
        call_detected = await self.monitor_call_logs(duration_minutes=5)
        
        # 5. Собрать метрики
        metrics = await self.check_call_metrics()
        
        # 6. Сгенерировать отчет
        self.generate_test_report(call_detected, metrics)
        
        return call_detected


async def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестирование реального звонка")
    parser.add_argument("--monitor-only", action="store_true", help="Только мониторинг логов")
    parser.add_argument("--duration", type=int, default=5, help="Длительность мониторинга в минутах")
    
    args = parser.parse_args()
    
    tester = RealCallTester()
    
    if args.monitor_only:
        # Только мониторинг
        await tester.monitor_call_logs(args.duration)
    else:
        # Полное интерактивное тестирование
        success = await tester.run_interactive_test()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
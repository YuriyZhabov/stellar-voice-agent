#!/usr/bin/env python3
"""
Скрипт для мониторинга входящих звонков в реальном времени.
Отслеживает логи LiveKit SIP и webhook события.
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime, UTC

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CallMonitor:
    """Монитор входящих звонков."""
    
    def __init__(self):
        self.running = False
        self.last_log_time = time.time()
        
    async def monitor_livekit_logs(self):
        """Мониторит логи LiveKit SIP."""
        print("📞 Мониторинг логов LiveKit SIP...")
        
        while self.running:
            try:
                # Получаем новые логи
                result = subprocess.run(
                    ["docker", "logs", "voice-ai-livekit-sip-fixed", "--since", "10s"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    logs = result.stdout.strip()
                    for line in logs.split('\n'):
                        if line.strip():
                            await self.process_sip_log(line)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка мониторинга логов: {e}")
                await asyncio.sleep(5)
    
    async def process_sip_log(self, log_line):
        """Обрабатывает строку лога SIP."""
        try:
            # Ищем важные события
            if "processing invite" in log_line.lower():
                print(f"📞 ВХОДЯЩИЙ ЗВОНОК: {log_line}")
                
                # Извлекаем информацию о звонке
                if "fromUser" in log_line and "toUser" in log_line:
                    # Парсим информацию о звонке
                    parts = log_line.split('"')
                    call_info = {}
                    for i, part in enumerate(parts):
                        if "fromUser" in part:
                            call_info["from"] = parts[i+1] if i+1 < len(parts) else "unknown"
                        elif "toUser" in part:
                            call_info["to"] = parts[i+1] if i+1 < len(parts) else "unknown"
                        elif "callID" in part:
                            call_info["call_id"] = parts[i+1] if i+1 < len(parts) else "unknown"
                    
                    print(f"   📋 От: {call_info.get('from', 'unknown')}")
                    print(f"   📋 К: {call_info.get('to', 'unknown')}")
                    print(f"   📋 ID: {call_info.get('call_id', 'unknown')}")
                    
            elif "rejecting inbound" in log_line.lower():
                print(f"❌ ЗВОНОК ОТКЛОНЕН: {log_line}")
                
            elif "auth check failed" in log_line.lower():
                print(f"🔐 ОШИБКА АУТЕНТИФИКАЦИИ: {log_line}")
                
            elif "room created" in log_line.lower():
                print(f"🏠 КОМНАТА СОЗДАНА: {log_line}")
                
            elif "participant joined" in log_line.lower():
                print(f"👤 УЧАСТНИК ПРИСОЕДИНИЛСЯ: {log_line}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки лога: {e}")
    
    async def monitor_webhook_events(self):
        """Мониторит webhook события через логи приложения."""
        print("🌐 Мониторинг webhook событий...")
        
        # Здесь можно добавить мониторинг логов приложения
        # Пока просто ждем
        while self.running:
            await asyncio.sleep(5)
    
    async def show_status(self):
        """Показывает текущий статус системы."""
        while self.running:
            try:
                # Проверяем статус контейнеров
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=voice-ai", "--format", "table {{.Names}}\t{{.Status}}"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"\n📊 СТАТУС СИСТЕМЫ ({datetime.now().strftime('%H:%M:%S')})")
                    print("=" * 50)
                    print(result.stdout)
                    print("=" * 50)
                
                await asyncio.sleep(30)  # Показываем статус каждые 30 секунд
                
            except Exception as e:
                logger.error(f"Ошибка получения статуса: {e}")
                await asyncio.sleep(30)
    
    async def start_monitoring(self):
        """Запускает мониторинг."""
        print("🚀 ЗАПУСК МОНИТОРИНГА ЗВОНКОВ")
        print("=" * 60)
        print("📞 Ожидание входящих звонков на номер +79952227978")
        print("🛑 Нажмите Ctrl+C для остановки")
        print("=" * 60)
        
        self.running = True
        
        # Запускаем все мониторы параллельно
        tasks = [
            asyncio.create_task(self.monitor_livekit_logs()),
            asyncio.create_task(self.monitor_webhook_events()),
            asyncio.create_task(self.show_status())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n🛑 Остановка мониторинга...")
            self.running = False
            
            # Отменяем все задачи
            for task in tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            print("✅ Мониторинг остановлен")


async def main():
    """Основная функция."""
    monitor = CallMonitor()
    await monitor.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
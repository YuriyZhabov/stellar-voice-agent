#!/usr/bin/env python3
"""
Простой мониторинг входящих звонков в реальном времени.
"""

import subprocess
import sys
import time

def monitor_calls():
    """Мониторит входящие звонки."""
    print("📞 МОНИТОРИНГ ВХОДЯЩИХ ЗВОНКОВ")
    print("=" * 50)
    print("📱 Позвоните на номер: +79952227978")
    print("🛑 Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    try:
        # Запускаем мониторинг логов
        process = subprocess.Popen(
            ["docker", "logs", "-f", "voice-ai-livekit-sip-correct"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            # Показываем важные события
            if any(keyword in line.lower() for keyword in [
                "processing invite", "rejecting inbound", "auth check", 
                "room created", "participant joined", "error", "warn"
            ]):
                timestamp = time.strftime("%H:%M:%S")
                
                if "processing invite" in line.lower():
                    print(f"[{timestamp}] 📞 ВХОДЯЩИЙ ЗВОНОК: {line}")
                elif "rejecting inbound" in line.lower():
                    print(f"[{timestamp}] ❌ ЗВОНОК ОТКЛОНЕН: {line}")
                elif "auth check failed" in line.lower():
                    print(f"[{timestamp}] 🔐 ОШИБКА АУТЕНТИФИКАЦИИ: {line}")
                elif "room created" in line.lower():
                    print(f"[{timestamp}] 🏠 КОМНАТА СОЗДАНА: {line}")
                elif "participant joined" in line.lower():
                    print(f"[{timestamp}] 👤 УЧАСТНИК ПРИСОЕДИНИЛСЯ: {line}")
                elif "error" in line.lower():
                    print(f"[{timestamp}] 🚨 ОШИБКА: {line}")
                elif "warn" in line.lower():
                    print(f"[{timestamp}] ⚠️ ПРЕДУПРЕЖДЕНИЕ: {line}")
                else:
                    print(f"[{timestamp}] ℹ️ СОБЫТИЕ: {line}")
                    
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен")
        process.terminate()
    except Exception as e:
        print(f"❌ Ошибка мониторинга: {e}")

if __name__ == "__main__":
    monitor_calls()
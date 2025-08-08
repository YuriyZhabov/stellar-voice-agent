#!/usr/bin/env python3
"""
Скрипт для диагностики и исправления проблемы "занято" при звонках.
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


def check_livekit_sip_status():
    """Проверяет статус LiveKit SIP."""
    print("📞 Проверка статуса LiveKit SIP...")
    
    try:
        # Проверяем, что контейнер запущен
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=voice-ai-livekit-sip", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"✅ Контейнер запущен: {result.stdout.strip()}")
            
            # Проверяем логи на ошибки
            log_result = subprocess.run(
                ["docker", "logs", "voice-ai-livekit-sip-correct", "--tail", "10"],
                capture_output=True,
                text=True
            )
            
            if "service ready" in log_result.stdout:
                print("✅ LiveKit SIP сервис готов")
                return True
            else:
                print("⚠️ LiveKit SIP может быть не готов")
                print(f"Логи: {log_result.stdout}")
                return False
        else:
            print("❌ LiveKit SIP контейнер не запущен")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки LiveKit SIP: {e}")
        return False


def check_sip_port():
    """Проверяет доступность SIP порта."""
    print("🌐 Проверка SIP порта 5060...")
    
    try:
        result = subprocess.run(
            ["netstat", "-ulnp", "|", "grep", ":5060"],
            shell=True,
            capture_output=True,
            text=True
        )
        
        if "5060" in result.stdout:
            print("✅ Порт 5060 слушается")
            return True
        else:
            print("❌ Порт 5060 не слушается")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки порта: {e}")
        return False


def check_webhook_endpoint():
    """Проверяет webhook endpoint."""
    print("🌐 Проверка webhook endpoint...")
    
    try:
        import requests
        response = requests.post(
            "http://localhost:8000/webhooks/livekit",
            json={"event": "test", "room": {"name": "test"}},
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Webhook endpoint работает")
            return True
        else:
            print(f"⚠️ Webhook endpoint вернул статус {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook endpoint недоступен: {e}")
        return False


def monitor_incoming_calls():
    """Мониторит входящие звонки в реальном времени."""
    print("👁️ Мониторинг входящих звонков (нажмите Ctrl+C для остановки)...")
    print("📞 Попробуйте позвонить на +79952227978")
    
    try:
        # Запускаем мониторинг логов в реальном времени
        process = subprocess.Popen(
            ["docker", "logs", "-f", "voice-ai-livekit-sip-correct"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
                
            # Фильтруем важные события
            if "processing invite" in line.lower():
                print(f"📞 ВХОДЯЩИЙ ЗВОНОК: {line}")
            elif "rejecting inbound" in line.lower():
                print(f"❌ ЗВОНОК ОТКЛОНЕН: {line}")
            elif "auth check failed" in line.lower():
                print(f"🔐 ОШИБКА АУТЕНТИФИКАЦИИ: {line}")
            elif "room created" in line.lower():
                print(f"🏠 КОМНАТА СОЗДАНА: {line}")
            elif "participant joined" in line.lower():
                print(f"👤 УЧАСТНИК ПРИСОЕДИНИЛСЯ: {line}")
            elif "error" in line.lower() or "warn" in line.lower():
                print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ/ОШИБКА: {line}")
                
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен")
        process.terminate()
    except Exception as e:
        print(f"❌ Ошибка мониторинга: {e}")


def suggest_fixes():
    """Предлагает возможные исправления."""
    print("\n🔧 ВОЗМОЖНЫЕ ИСПРАВЛЕНИЯ:")
    print("=" * 50)
    
    print("1. 📞 ПРОВЕРЬТЕ НАСТРОЙКИ NOVOFON:")
    print("   - Убедитесь, что номер +79952227978 активен")
    print("   - Проверьте настройки переадресации на 94.131.122.253:5060")
    print("   - Убедитесь, что нет блокировок или ограничений")
    
    print("\n2. 🌐 ПРОВЕРЬТЕ СЕТЕВЫЕ НАСТРОЙКИ:")
    print("   - Убедитесь, что порт 5060/UDP открыт в firewall")
    print("   - Проверьте, что нет NAT проблем")
    print("   - Убедитесь, что IP 94.131.122.253 доступен извне")
    
    print("\n3. 🔧 ПРОВЕРЬТЕ КОНФИГУРАЦИЮ LIVEKIT SIP:")
    print("   - Убедитесь, что используется правильная конфигурация")
    print("   - Проверьте, что auth_required: false")
    print("   - Убедитесь, что inbound_only: true")
    
    print("\n4. 📋 ПРОВЕРЬТЕ ЛОГИ:")
    print("   - docker logs voice-ai-livekit-sip-correct")
    print("   - Ищите сообщения об ошибках аутентификации")
    
    print("\n5. 🆘 ЭКСТРЕННЫЕ МЕРЫ:")
    print("   - Перезапустите LiveKit SIP контейнер")
    print("   - Проверьте, что Redis доступен")
    print("   - Убедитесь, что LiveKit сервер доступен")


async def main():
    """Основная функция диагностики."""
    print("🚨 ДИАГНОСТИКА ПРОБЛЕМЫ 'ЗАНЯТО'")
    print("=" * 60)
    
    # Проверяем основные компоненты
    checks = [
        ("LiveKit SIP статус", check_livekit_sip_status()),
        ("SIP порт 5060", check_sip_port()),
        ("Webhook endpoint", check_webhook_endpoint())
    ]
    
    all_good = True
    for check_name, result in checks:
        if not result:
            all_good = False
    
    if all_good:
        print("\n✅ Все основные компоненты работают")
        print("🔍 Запускаем мониторинг входящих звонков...")
        monitor_incoming_calls()
    else:
        print("\n❌ Обнаружены проблемы с компонентами")
        suggest_fixes()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Диагностика прервана пользователем")
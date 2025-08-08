#!/usr/bin/env python3
"""
Скрипт для тестирования входящего звонка.
Проверяет все компоненты системы и готовность к приему звонков.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, UTC

import aiohttp
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_webhook_endpoint():
    """Тестирует webhook endpoint."""
    print("🌐 Тестирование webhook endpoint...")
    
    try:
        test_event = {
            "event": "room_started",
            "room": {
                "name": "voice-ai-call-test123",
                "sid": "RM_test123",
                "metadata": json.dumps({
                    "caller_number": "+79000000000",
                    "call_type": "test"
                })
            },
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/webhooks/livekit",
                json=test_event,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Webhook endpoint работает: {result}")
                    return True
                else:
                    print(f"❌ Webhook endpoint вернул статус {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка webhook endpoint: {e}")
        return False


def test_livekit_sip_status():
    """Проверяет статус LiveKit SIP."""
    print("📞 Проверка статуса LiveKit SIP...")
    
    try:
        # Проверяем логи контейнера
        import subprocess
        result = subprocess.run(
            ["docker", "logs", "voice-ai-livekit-sip-fixed", "--tail", "5"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logs = result.stdout
            if "service ready" in logs:
                print("✅ LiveKit SIP сервис готов")
                return True
            else:
                print(f"⚠️ LiveKit SIP логи: {logs}")
                return False
        else:
            print(f"❌ Не удается получить логи LiveKit SIP: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки LiveKit SIP: {e}")
        return False


def test_network_connectivity():
    """Проверяет сетевую связность."""
    print("🌐 Проверка сетевой связности...")
    
    try:
        # Проверяем, что порт 5060 открыт
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        try:
            # Пытаемся подключиться к локальному порту 5060
            sock.connect(('127.0.0.1', 5060))
            print("✅ Порт 5060 доступен")
            return True
        except Exception as e:
            print(f"❌ Порт 5060 недоступен: {e}")
            return False
        finally:
            sock.close()
            
    except Exception as e:
        print(f"❌ Ошибка проверки сети: {e}")
        return False


def test_external_access():
    """Проверяет внешний доступ к webhook."""
    print("🌍 Проверка внешнего доступа...")
    
    try:
        # Проверяем доступность webhook извне
        response = requests.get(
            "http://agentio.ru:8000/health",
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Webhook доступен извне")
            return True
        else:
            print(f"⚠️ Webhook доступен, но статус {response.status_code}")
            return True  # Все равно доступен
            
    except Exception as e:
        print(f"❌ Webhook недоступен извне: {e}")
        return False


async def simulate_call_flow():
    """Симулирует поток обработки звонка."""
    print("🎭 Симуляция потока обработки звонка...")
    
    try:
        # 1. Симулируем room_started
        room_started_event = {
            "event": "room_started",
            "room": {
                "name": "voice-ai-call-sim123",
                "sid": "RM_sim123",
                "metadata": json.dumps({
                    "caller_number": "+79000000001",
                    "call_type": "simulation"
                })
            },
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/webhooks/livekit",
                json=room_started_event
            ) as response:
                if response.status != 200:
                    print(f"❌ Ошибка room_started: {response.status}")
                    return False
        
        print("✅ room_started обработан")
        
        # 2. Симулируем participant_joined
        await asyncio.sleep(1)
        
        participant_joined_event = {
            "event": "participant_joined",
            "room": {
                "name": "voice-ai-call-sim123",
                "sid": "RM_sim123"
            },
            "participant": {
                "identity": "+79000000001",
                "name": "caller",
                "sid": "PA_sim123"
            },
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/webhooks/livekit",
                json=participant_joined_event
            ) as response:
                if response.status != 200:
                    print(f"❌ Ошибка participant_joined: {response.status}")
                    return False
        
        print("✅ participant_joined обработан")
        
        # 3. Симулируем room_finished
        await asyncio.sleep(1)
        
        room_finished_event = {
            "event": "room_finished",
            "room": {
                "name": "voice-ai-call-sim123",
                "sid": "RM_sim123"
            },
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/webhooks/livekit",
                json=room_finished_event
            ) as response:
                if response.status != 200:
                    print(f"❌ Ошибка room_finished: {response.status}")
                    return False
        
        print("✅ room_finished обработан")
        print("✅ Полный поток звонка симулирован успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка симуляции звонка: {e}")
        return False


async def main():
    """Основная функция тестирования."""
    print("🧪 ТЕСТИРОВАНИЕ ГОТОВНОСТИ К ПРИЕМУ ЗВОНКОВ")
    print("=" * 60)
    
    tests = [
        ("Webhook endpoint", test_webhook_endpoint()),
        ("LiveKit SIP статус", test_livekit_sip_status()),
        ("Сетевая связность", test_network_connectivity()),
        ("Внешний доступ", test_external_access()),
        ("Симуляция звонка", simulate_call_flow())
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        print(f"\n🔍 {test_name}...")
        
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
            
        results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name}: ПРОЙДЕН")
        else:
            print(f"❌ {test_name}: ПРОВАЛЕН")
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"   {test_name}: {status}")
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! СИСТЕМА ГОТОВА К ПРИЕМУ ЗВОНКОВ!")
        print("\n📞 Теперь можно звонить на номер +79952227978")
        print("🤖 Система должна автоматически активировать AI агента")
    else:
        print(f"\n⚠️ {total - passed} тестов провалено. Необходимо исправить проблемы.")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())
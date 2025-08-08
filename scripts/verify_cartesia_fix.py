#!/usr/bin/env python3
"""
Скрипт для проверки что исправления Cartesia TTS работают корректно
БЕЗ изменения существующих рабочих файлов.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def verify_cartesia_fix():
    """Проверить что исправления Cartesia TTS работают."""
    print("🔍 Проверка исправлений Cartesia TTS...")
    
    try:
        # 1. Проверить что Cartesia TTS health check работает
        print("1. Тестирование Cartesia TTS health check...")
        from src.clients.cartesia_tts import CartesiaTTSClient
        
        client = CartesiaTTSClient()
        is_healthy = await client.health_check()
        await client.close()
        
        if is_healthy:
            print("   ✅ Cartesia TTS health check работает")
        else:
            print("   ❌ Cartesia TTS health check не работает")
            return False
        
        # 2. Проверить comprehensive health check
        print("2. Тестирование comprehensive health check...")
        from src.health import comprehensive_health_check_async
        
        health_data = await comprehensive_health_check_async()
        cartesia_status = health_data.get("checks", {}).get("cartesia", "unknown")
        
        if cartesia_status == "ok":
            print("   ✅ Comprehensive health check показывает Cartesia как OK")
        else:
            print(f"   ❌ Comprehensive health check показывает Cartesia как: {cartesia_status}")
            return False
        
        # 3. Проверить общее здоровье системы
        health_percentage = health_data.get("health_percentage", 0)
        print(f"3. Общее здоровье системы: {health_percentage:.1f}%")
        
        if health_percentage >= 90:
            print("   ✅ Система здорова")
        else:
            print("   ⚠️  Система работает с предупреждениями")
        
        print("\n🎉 Все исправления Cartesia TTS работают корректно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        return False


async def main():
    """Основная функция."""
    success = await verify_cartesia_fix()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
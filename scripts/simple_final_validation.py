#!/usr/bin/env python3
"""
Простая финальная валидация системы LiveKit.
Загружает переменные окружения из .env файла и выполняет базовые проверки.
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# Загрузка переменных окружения из .env файла
def load_env_file():
    """Загрузка переменных окружения из .env файла."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print(f"✅ Загружены переменные окружения из {env_file}")
    else:
        print(f"❌ Файл .env не найден: {env_file}")

async def validate_environment():
    """Валидация переменных окружения."""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = [
        'LIVEKIT_URL',
        'LIVEKIT_API_KEY',
        'LIVEKIT_API_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print(f"   ✅ {var}: настроена")
    
    if missing_vars:
        print(f"   ❌ Отсутствуют переменные: {missing_vars}")
        return False
    
    return True

async def validate_config_files():
    """Валидация конфигурационных файлов."""
    print("📁 Проверка конфигурационных файлов...")
    
    project_root = Path(__file__).parent.parent
    config_files = [
        "livekit-sip-correct.yaml",
        ".env",
        "config/livekit_config.py",
        "config/security.yaml",
        "config/performance.yaml"
    ]
    
    missing_files = []
    for file_path in config_files:
        full_path = project_root / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"   ✅ {file_path}: существует ({size} байт)")
        else:
            missing_files.append(file_path)
            print(f"   ❌ {file_path}: отсутствует")
    
    return len(missing_files) == 0

async def validate_basic_imports():
    """Валидация базовых импортов."""
    print("📦 Проверка импортов модулей...")
    
    # Добавляем путь к src
    sys.path.append(str(Path(__file__).parent.parent / "src"))
    
    modules_to_test = [
        ("auth.livekit_auth", "LiveKitAuthManager"),
        ("clients.livekit_api_client", "LiveKitAPIClient"),
        ("monitoring.livekit_system_monitor", "LiveKitSystemMonitor"),
        ("security.livekit_security", "LiveKitSecurityValidator"),
        ("performance_optimizer", "PerformanceOptimizer"),
        ("integration.livekit_voice_ai_integration", "LiveKitVoiceAIIntegration")
    ]
    
    successful_imports = 0
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"   ✅ {module_name}.{class_name}: импорт успешен")
            successful_imports += 1
        except Exception as e:
            print(f"   ❌ {module_name}.{class_name}: ошибка импорта - {e}")
    
    return successful_imports == len(modules_to_test)

async def test_basic_authentication():
    """Тест базовой аутентификации."""
    print("🔐 Тест базовой аутентификации...")
    
    try:
        from auth.livekit_auth import LiveKitAuthManager
        
        api_key = os.getenv('LIVEKIT_API_KEY')
        api_secret = os.getenv('LIVEKIT_API_SECRET')
        
        if not api_key or not api_secret:
            print("   ❌ API ключи не настроены")
            return False
        
        auth_manager = LiveKitAuthManager(api_key, api_secret)
        
        # Создание тестового токена
        token = auth_manager.create_participant_token("test-user", "test-room")
        
        if token and len(token) > 50:  # JWT токены обычно длинные
            print("   ✅ JWT токен создан успешно")
            
            # Проверка структуры токена
            import jwt
            payload = jwt.decode(token, options={"verify_signature": False})
            required_fields = ['iss', 'sub', 'iat', 'exp']
            
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                print(f"   ⚠️  Отсутствуют поля в JWT: {missing_fields}")
                return False
            else:
                print("   ✅ Структура JWT токена корректна")
                return True
        else:
            print("   ❌ Некорректный JWT токен")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка аутентификации: {e}")
        return False

async def test_api_client_initialization():
    """Тест инициализации API клиента."""
    print("🌐 Тест инициализации API клиента...")
    
    try:
        from clients.livekit_api_client import LiveKitAPIClient
        
        livekit_url = os.getenv('LIVEKIT_URL')
        api_key = os.getenv('LIVEKIT_API_KEY')
        api_secret = os.getenv('LIVEKIT_API_SECRET')
        
        client = LiveKitAPIClient(livekit_url, api_key, api_secret)
        
        if client:
            print("   ✅ API клиент инициализирован успешно")
            return True
        else:
            print("   ❌ Ошибка инициализации API клиента")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка инициализации API клиента: {e}")
        return False

async def run_simple_validation():
    """Запуск простой валидации."""
    print("🚀 Запуск простой финальной валидации системы LiveKit")
    print("=" * 70)
    
    # Загрузка переменных окружения
    load_env_file()
    
    # Выполнение проверок
    checks = [
        ("Переменные окружения", validate_environment()),
        ("Конфигурационные файлы", validate_config_files()),
        ("Импорты модулей", validate_basic_imports()),
        ("Базовая аутентификация", test_basic_authentication()),
        ("Инициализация API клиента", test_api_client_initialization())
    ]
    
    results = []
    for check_name, check_coro in checks:
        print(f"\n--- {check_name} ---")
        try:
            result = await check_coro
            results.append((check_name, result))
        except Exception as e:
            print(f"   ❌ Критическая ошибка: {e}")
            results.append((check_name, False))
    
    # Итоговый отчет
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЕТ ПРОСТОЙ ВАЛИДАЦИИ")
    print("=" * 70)
    
    passed_checks = sum(1 for _, result in results if result)
    total_checks = len(results)
    
    print(f"Пройдено проверок: {passed_checks}/{total_checks}")
    
    for check_name, result in results:
        status = "✅ ПРОЙДЕНО" if result else "❌ ПРОВАЛЕНО"
        print(f"   {status}: {check_name}")
    
    if passed_checks == total_checks:
        print("\n🎉 Все базовые проверки пройдены успешно!")
        print("Система готова для более детального тестирования.")
        return 0
    elif passed_checks >= total_checks * 0.8:  # 80% проверок пройдено
        print("\n⚠️  Большинство проверок пройдено, но есть проблемы.")
        print("Рекомендуется исправить выявленные проблемы.")
        return 2
    else:
        print("\n❌ Критические проблемы с системой!")
        print("Необходимо исправить проблемы перед использованием.")
        return 1

async def main():
    """Главная функция."""
    try:
        exit_code = await run_simple_validation()
        sys.exit(exit_code)
    except Exception as e:
        print(f"💥 Критическая ошибка валидации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
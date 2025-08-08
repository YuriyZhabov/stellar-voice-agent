#!/usr/bin/env python3
"""
Финальный тест системы приема звонков.
Проверяет все компоненты и готовность к работе.
"""

import subprocess
import time
import requests

def check_system_status():
    """Проверяет статус всех компонентов системы."""
    print("🔍 ПРОВЕРКА СТАТУСА СИСТЕМЫ")
    print("=" * 50)
    
    # 1. Проверяем LiveKit SIP
    try:
        result = subprocess.run(
            ["docker", "logs", "voice-ai-livekit-sip-correct", "--tail", "5"],
            capture_output=True,
            text=True
        )
        
        if "service ready" in result.stdout:
            print("✅ LiveKit SIP: ГОТОВ")
        else:
            print("❌ LiveKit SIP: НЕ ГОТОВ")
            return False
    except:
        print("❌ LiveKit SIP: ОШИБКА")
        return False
    
    # 2. Проверяем webhook
    try:
        response = requests.post(
            "http://localhost:8000/webhooks/livekit",
            json={"event": "test"},
            timeout=5
        )
        if response.status_code == 200:
            print("✅ Webhook: РАБОТАЕТ")
        else:
            print("❌ Webhook: НЕ РАБОТАЕТ")
            return False
    except:
        print("❌ Webhook: НЕДОСТУПЕН")
        return False
    
    # 3. Проверяем порт 5060
    try:
        result = subprocess.run(
            ["netstat", "-ulnp"],
            capture_output=True,
            text=True
        )
        if ":5060" in result.stdout:
            print("✅ Порт 5060: СЛУШАЕТСЯ")
        else:
            print("❌ Порт 5060: НЕ СЛУШАЕТСЯ")
            return False
    except:
        print("❌ Порт 5060: ОШИБКА ПРОВЕРКИ")
        return False
    
    # 4. Проверяем Redis
    try:
        result = subprocess.run(
            ["docker", "exec", "voice-ai-redis-simple", "redis-cli", "ping"],
            capture_output=True,
            text=True
        )
        if "PONG" in result.stdout:
            print("✅ Redis: РАБОТАЕТ")
        else:
            print("❌ Redis: НЕ ОТВЕЧАЕТ")
            return False
    except:
        print("❌ Redis: ОШИБКА")
        return False
    
    return True

def show_call_instructions():
    """Показывает инструкции для тестирования звонка."""
    print("\n📞 ИНСТРУКЦИИ ДЛЯ ТЕСТИРОВАНИЯ")
    print("=" * 50)
    print("1. Позвоните на номер: +7 995 222 79 78")
    print("2. Ожидайте соединения (не должно быть 'занято')")
    print("3. Если звонок проходит - система работает!")
    print("4. Если 'занято' - проверьте логи ниже")
    
def monitor_next_call():
    """Мониторит следующий входящий звонок."""
    print("\n👁️ МОНИТОРИНГ СЛЕДУЮЩЕГО ЗВОНКА")
    print("=" * 50)
    print("📱 Позвоните СЕЙЧАС на +79952227978")
    print("⏱️ Ожидание звонка в течение 60 секунд...")
    
    start_time = time.time()
    timeout = 60  # 60 секунд
    
    try:
        process = subprocess.Popen(
            ["docker", "logs", "-f", "voice-ai-livekit-sip-correct"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        while time.time() - start_time < timeout:
            line = process.stdout.readline()
            if not line:
                continue
                
            line = line.strip()
            current_time = time.strftime("%H:%M:%S")
            
            if "processing invite" in line.lower():
                print(f"[{current_time}] 📞 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН!")
                print(f"[{current_time}] 📋 Детали: {line}")
                
                # Ждем результат обработки
                for _ in range(10):  # Ждем до 10 секунд
                    result_line = process.stdout.readline()
                    if not result_line:
                        continue
                        
                    result_line = result_line.strip()
                    
                    if "rejecting inbound" in result_line.lower():
                        print(f"[{current_time}] ❌ ЗВОНОК ОТКЛОНЕН: {result_line}")
                        print("\n🚨 ПРОБЛЕМА: Звонок отклоняется системой")
                        print("💡 Возможные причины:")
                        print("   - Проблемы с аутентификацией")
                        print("   - Неправильная конфигурация")
                        print("   - Проблемы с LiveKit сервером")
                        process.terminate()
                        return False
                        
                    elif "room created" in result_line.lower():
                        print(f"[{current_time}] ✅ КОМНАТА СОЗДАНА: {result_line}")
                        print("\n🎉 УСПЕХ! Звонок принят системой!")
                        process.terminate()
                        return True
                        
                    elif "participant joined" in result_line.lower():
                        print(f"[{current_time}] 👤 УЧАСТНИК ПРИСОЕДИНИЛСЯ: {result_line}")
                        
                    time.sleep(1)
                
                print(f"[{current_time}] ⏱️ Ожидание результата обработки...")
                
        print(f"\n⏰ Время ожидания истекло ({timeout} сек)")
        print("📞 Звонок не был обнаружен")
        process.terminate()
        return None
        
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг прерван пользователем")
        process.terminate()
        return None
    except Exception as e:
        print(f"\n❌ Ошибка мониторинга: {e}")
        return None

def main():
    """Основная функция."""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ СИСТЕМЫ ПРИЕМА ЗВОНКОВ")
    print("=" * 60)
    
    # Проверяем статус системы
    if not check_system_status():
        print("\n❌ СИСТЕМА НЕ ГОТОВА!")
        print("🔧 Исправьте ошибки перед тестированием звонков")
        return
    
    print("\n✅ ВСЕ КОМПОНЕНТЫ ГОТОВЫ!")
    
    # Показываем инструкции
    show_call_instructions()
    
    # Запрашиваем подтверждение
    try:
        input("\n⏳ Нажмите Enter когда будете готовы начать мониторинг...")
    except KeyboardInterrupt:
        print("\n👋 Тест отменен")
        return
    
    # Мониторим звонок
    result = monitor_next_call()
    
    if result is True:
        print("\n🎉 ТЕСТ ПРОЙДЕН УСПЕШНО!")
        print("✅ Система готова к приему звонков")
        print("🤖 AI агент должен активироваться при звонках")
    elif result is False:
        print("\n❌ ТЕСТ ПРОВАЛЕН!")
        print("🔧 Требуется дополнительная настройка")
    else:
        print("\n⚠️ ТЕСТ НЕ ЗАВЕРШЕН")
        print("📞 Попробуйте позвонить еще раз")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Тест прерван пользователем")
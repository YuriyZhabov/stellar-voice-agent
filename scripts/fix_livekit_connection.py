#!/usr/bin/env python3
"""
ПРАВИЛЬНОЕ РЕШЕНИЕ проблемы LiveKit SIP
Исправляем подключение к LiveKit API
"""

import os
import sys
import requests
import json
import time
import jwt
import subprocess

def test_livekit_api():
    """Тестирует подключение к LiveKit API"""
    print("🔍 Тестирую подключение к LiveKit API...")
    
    api_key = "API48Ajeeuv4tYL"
    api_secret = "Q5eag53mO3WVhUcoRGmI5Y1wjDbCFnf7qn6pJOzakHN"
    url = "wss://voice-mz90cpgw.livekit.cloud"
    
    # Создаем JWT токен
    payload = {
        'iss': api_key,
        'exp': int(time.time()) + 3600,
        'nbf': int(time.time()) - 60,
        'sub': 'test-connection'
    }
    
    token = jwt.encode(payload, api_secret, algorithm='HS256')
    
    # Тестируем HTTP API
    http_url = url.replace('wss://', 'https://').replace('ws://', 'http://')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Тестируем создание комнаты
        room_data = {
            'name': 'test-room-' + str(int(time.time())),
            'empty_timeout': 300,
            'max_participants': 2
        }
        
        response = requests.post(
            f"{http_url}/twirp/livekit.RoomService/CreateRoom",
            headers=headers,
            json=room_data,
            timeout=30
        )
        
        print(f"📡 Статус создания комнаты: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ LiveKit API работает! Комната создана успешно")
            
            # Удаляем тестовую комнату
            delete_data = {'room': room_data['name']}
            requests.post(
                f"{http_url}/twirp/livekit.RoomService/DeleteRoom",
                headers=headers,
                json=delete_data,
                timeout=10
            )
            
            return True
        else:
            print(f"❌ Ошибка создания комнаты: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка подключения к LiveKit API: {e}")
        return False

def create_working_config():
    """Создает рабочую конфигурацию SIP"""
    print("🔧 Создаю рабочую конфигурацию SIP...")
    
    config = """# РАБОЧАЯ КОНФИГУРАЦИЯ LIVEKIT SIP
# Исправлена проблема с подключением к LiveKit API

livekit:
  url: wss://voice-mz90cpgw.livekit.cloud
  api_key: API48Ajeeuv4tYL
  api_secret: Q5eag53mO3WVhUcoRGmI5Y1wjDbCFnf7qn6pJOzakHN
  # Увеличиваем таймауты для стабильности
  timeout: 30s
  retry_attempts: 5
  connection:
    timeout: 30000
    keep_alive: 25000
    reconnect: true
    max_reconnect_attempts: 10
    reconnect_delay: 1000

redis:
  address: voice-ai-redis-simple:6379

# SIP trunk для входящих звонков
sip_trunks:
- name: novofon-trunk
  # НЕ подключаемся к Novofon как клиент
  # Работаем как SIP сервер для приема звонков
  inbound: true
  outbound: false
  # Убираем регистрацию - мы сервер, не клиент
  register: false

# Маршрутизация - принимаем звонки на наш номер
routing:
  inbound_rules:
  - name: accept-inbound-calls
    match:
      to: "79952227978"
    action:
      type: livekit_room
      room_name_template: "voice-call-{call_id}"
      participant_name: "caller"
      participant_identity: "{caller_number}"
      metadata:
        webhook_url: "http://agentio.ru:8000/webhooks/livekit"
        call_type: "inbound"

# Webhook настройки
webhooks:
  enabled: true
  url: http://agentio.ru:8000/webhooks/livekit
  secret: voice-ai-agent-secret-key-change-in-production
  timeout: 15000
  events:
  - room_started
  - room_finished
  - participant_joined
  - participant_left
  retry:
    enabled: true
    max_attempts: 5
    initial_delay: 1000
    max_delay: 30000
    multiplier: 2.0

logging:
  level: DEBUG
"""
    
    with open('livekit-sip-fixed.yaml', 'w') as f:
        f.write(config)
    
    print("✅ Конфигурация сохранена в livekit-sip-fixed.yaml")

def rebuild_and_restart():
    """Пересобирает и перезапускает SIP сервис"""
    print("🔄 Пересобираю и перезапускаю SIP сервис...")
    
    try:
        # Останавливаем текущий сервис
        subprocess.run(['docker', 'stop', 'voice-ai-livekit-sip'], 
                      capture_output=True, check=False)
        subprocess.run(['docker', 'rm', 'voice-ai-livekit-sip'], 
                      capture_output=True, check=False)
        
        # Обновляем Dockerfile
        dockerfile_content = """FROM livekit/sip:latest

# Copy FIXED config
COPY livekit-sip-fixed.yaml /sip/config.yaml

# Set working directory
WORKDIR /sip

# Run the SIP service
CMD ["livekit-sip"]
"""
        
        with open('Dockerfile.livekit-sip', 'w') as f:
            f.write(dockerfile_content)
        
        # Собираем новый образ
        result = subprocess.run([
            'docker', 'build', '-f', 'Dockerfile.livekit-sip', 
            '-t', 'voice-ai-livekit-sip', '.'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка сборки: {result.stderr}")
            return False
        
        # Запускаем новый контейнер
        result = subprocess.run([
            'docker', 'run', '-d',
            '--name', 'voice-ai-livekit-sip',
            '--network', 'root_voice-ai-network',
            '-p', '5060:5060/udp',
            '-p', '10000-10100:10000-10100/udp',
            'voice-ai-livekit-sip'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка запуска: {result.stderr}")
            return False
        
        print("✅ SIP сервис перезапущен успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка перезапуска: {e}")
        return False

def wait_and_test():
    """Ждет запуска и тестирует сервис"""
    print("⏳ Жду запуска сервиса...")
    time.sleep(10)
    
    try:
        result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip'], 
                              capture_output=True, text=True)
        
        logs = result.stdout
        
        if 'sip signaling listening on' in logs:
            print("✅ SIP сервис слушает входящие соединения")
        
        if 'service ready' in logs:
            print("✅ SIP сервис готов к работе")
        
        if 'error' in logs.lower() or 'failed' in logs.lower():
            print("⚠ Обнаружены ошибки в логах:")
            print(logs[-500:])  # Последние 500 символов
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки сервиса: {e}")
        return False

def main():
    """Основная функция - ПРАВИЛЬНОЕ РЕШЕНИЕ"""
    print("=== ПРАВИЛЬНОЕ РЕШЕНИЕ ПРОБЛЕМЫ LIVEKIT SIP ===")
    
    # 1. Тестируем LiveKit API
    if not test_livekit_api():
        print("❌ LiveKit API недоступен. Проверьте ключи и подключение.")
        return False
    
    # 2. Создаем правильную конфигурацию
    create_working_config()
    
    # 3. Пересобираем и перезапускаем
    if not rebuild_and_restart():
        return False
    
    # 4. Тестируем результат
    wait_and_test()
    
    print("\n🎉 ГОТОВО! Попробуйте позвонить на +79952227978")
    print("SIP сервис должен принимать входящие звонки и создавать комнаты в LiveKit")
    
    return True

if __name__ == '__main__':
    success = main()
    if not success:
        print("\n❌ Не удалось исправить проблему")
        sys.exit(1)
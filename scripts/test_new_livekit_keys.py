#!/usr/bin/env python3
"""
Тестирование новых ключей LiveKit
"""

import requests
import json
import time
import jwt

def test_new_livekit_keys():
    """Тестирует новые ключи LiveKit"""
    print("🔍 Тестирую новые ключи LiveKit...")
    
    # Новые ключи
    api_key = "APIJrnqBwqxL2N6"
    api_secret = "vd2Kjxdilq1lDpJw8lG6NjHpXDyRUjaywJEzt4akZ0P"
    url = "wss://voice-mz90cpgw.livekit.cloud"
    
    print(f"🔑 API Key: {api_key}")
    print(f"🔑 API Secret: {api_secret[:20]}...")
    print(f"🌐 URL: {url}")
    
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
        print(f"📄 Ответ: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ НОВЫЕ КЛЮЧИ РАБОТАЮТ! Комната создана успешно")
            
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

if __name__ == '__main__':
    if test_new_livekit_keys():
        print("\n🎉 КЛЮЧИ РАБОТАЮТ! Можно обновлять конфигурацию")
    else:
        print("\n❌ Ключи не работают")
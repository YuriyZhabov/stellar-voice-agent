#!/usr/bin/env python3
"""
Тестирование нового ключа Groq API
"""

import requests
import json

def test_groq_key(api_key):
    """Тестирует ключ Groq API"""
    
    if not api_key or api_key.strip() == "":
        print("❌ API ключ пустой")
        return False
    
    print(f"🔑 Тестирую ключ: {api_key[:20]}...")
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "messages": [
            {
                "role": "user", 
                "content": "Привет! Это тест API."
            }
        ],
        "model": "llama3-8b-8192",
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"📡 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ API работает! Ответ: {message[:100]}...")
            return True
        else:
            print(f"❌ Ошибка API: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

def main():
    print("=== ТЕСТ GROQ API КЛЮЧА ===")
    
    # Введите новый ключ здесь для тестирования
    new_key = input("Введите новый Groq API ключ: ").strip()
    
    if test_groq_key(new_key):
        print("\n✅ Ключ работает! Можно заменить в .env файле")
        
        # Предложить автоматическую замену
        replace = input("Заменить ключ в .env файле? (y/n): ").strip().lower()
        
        if replace == 'y':
            try:
                # Читаем .env файл
                with open('.env', 'r') as f:
                    content = f.read()
                
                # Заменяем ключ
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('GROQ_API_KEY='):
                        lines[i] = f'GROQ_API_KEY={new_key}'
                    elif line.startswith('GROQ_MODEL='):
                        lines[i] = 'GROQ_MODEL=llama3-8b-8192'
                
                # Записываем обратно
                with open('.env', 'w') as f:
                    f.write('\n'.join(lines))
                
                print("✅ Ключ обновлен в .env файле!")
                print("🔄 Перезапустите агент для применения изменений")
                
            except Exception as e:
                print(f"❌ Ошибка обновления файла: {e}")
    else:
        print("\n❌ Ключ не работает")

if __name__ == '__main__':
    main()
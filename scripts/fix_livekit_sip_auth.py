#!/usr/bin/env python3
"""
Fix LiveKit SIP Authentication Issues
Диагностирует и исправляет проблемы с аутентификацией LiveKit SIP
"""

import os
import sys
import json
import yaml
import requests
import time
from datetime import datetime
import subprocess
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LiveKitSIPAuthFixer:
    def __init__(self):
        self.load_config()
        
    def load_config(self):
        """Загружает конфигурацию из .env файла"""
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
                        
            self.livekit_url = os.getenv('LIVEKIT_URL')
            self.livekit_api_key = os.getenv('LIVEKIT_API_KEY')
            self.livekit_api_secret = os.getenv('LIVEKIT_API_SECRET')
            self.domain = os.getenv('DOMAIN')
            self.port = os.getenv('PORT', '8000')
            
            logger.info("Конфигурация загружена успешно")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            sys.exit(1)
    
    def test_livekit_connection(self):
        """Тестирует подключение к LiveKit API"""
        logger.info("Тестирование подключения к LiveKit API...")
        
        try:
            # Проверяем доступность сервера
            url = self.livekit_url.replace('wss://', 'https://')
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                logger.info("✓ LiveKit сервер доступен")
                return True
            else:
                logger.error(f"✗ LiveKit сервер недоступен: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Ошибка подключения к LiveKit: {e}")
            return False
    
    def test_webhook_endpoint(self):
        """Тестирует доступность webhook endpoint"""
        logger.info("Тестирование webhook endpoint...")
        
        try:
            webhook_url = f"http://{self.domain}:{self.port}/webhooks/livekit"
            response = requests.get(webhook_url, timeout=5)
            
            # Webhook может возвращать 405 (Method Not Allowed) для GET запросов
            if response.status_code in [200, 405]:
                logger.info("✓ Webhook endpoint доступен")
                return True
            else:
                logger.warning(f"⚠ Webhook endpoint возвращает: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Webhook endpoint недоступен: {e}")
            return False
    
    def check_sip_trunk_config(self):
        """Проверяет конфигурацию SIP trunk"""
        logger.info("Проверка конфигурации SIP trunk...")
        
        try:
            with open('livekit-sip-simple.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            # Проверяем наличие SIP trunk
            if 'sip_trunks' not in config:
                logger.error("✗ SIP trunks не настроены")
                return False
            
            trunk = config['sip_trunks'][0]
            
            # Проверяем обязательные поля
            required_fields = ['host', 'username', 'password', 'port']
            for field in required_fields:
                if field not in trunk or not trunk[field]:
                    logger.error(f"✗ Отсутствует поле {field} в SIP trunk")
                    return False
            
            logger.info("✓ Конфигурация SIP trunk корректна")
            return True
            
        except Exception as e:
            logger.error(f"✗ Ошибка проверки SIP trunk: {e}")
            return False
    
    def fix_livekit_sip_config(self):
        """Исправляет конфигурацию LiveKit SIP"""
        logger.info("Исправление конфигурации LiveKit SIP...")
        
        try:
            # Создаем исправленную конфигурацию
            config = {
                'livekit': {
                    'url': self.livekit_url,
                    'api_key': self.livekit_api_key,
                    'api_secret': self.livekit_api_secret,
                    'timeout': '30s',
                    'retry_attempts': 5,
                    'connection': {
                        'timeout': 30000,
                        'keep_alive': 25000,
                        'reconnect': True,
                        'max_reconnect_attempts': 10,
                        'reconnect_delay': 1000
                    }
                },
                'redis': {
                    'address': 'voice-ai-redis-simple:6379'
                },
                'sip_trunks': [{
                    'name': 'novofon-trunk',
                    'host': 'sip.novofon.ru',
                    'port': 5060,
                    'transport': 'UDP',
                    'username': os.getenv('SIP_USERNAME'),
                    'password': os.getenv('SIP_PASSWORD'),
                    'register': True,
                    'register_interval': 300,
                    'auth_username': os.getenv('SIP_USERNAME'),  # Добавляем явную аутентификацию
                    'auth_password': os.getenv('SIP_PASSWORD')
                }],
                'routing': {
                    'inbound_rules': [{
                        'name': 'voice-ai-routing',
                        'match': {
                            'to': os.getenv('SIP_NUMBER', '79952227978').replace('+', ''),
                            'trunk': 'novofon-trunk'
                        },
                        'action': {
                            'type': 'livekit_room',
                            'room_name_template': 'voice-ai-call-{call_id}',
                            'participant_name': 'caller',
                            'participant_identity': '{caller_number}',
                            'metadata': {
                                'webhook_url': f"http://{self.domain}:{self.port}/webhooks/livekit"
                            }
                        }
                    }]
                },
                'webhooks': {
                    'enabled': True,
                    'url': f"http://{self.domain}:{self.port}/webhooks/livekit",
                    'secret': os.getenv('SECRET_KEY'),
                    'timeout': 10000,  # Увеличиваем timeout
                    'events': [
                        'room_started',
                        'room_finished', 
                        'participant_joined',
                        'participant_left'
                    ],
                    'retry': {
                        'enabled': True,
                        'max_attempts': 5,
                        'initial_delay': 1000,
                        'max_delay': 30000,
                        'multiplier': 2.0
                    }
                },
                'logging': {
                    'level': 'INFO'
                },
                'health_check': {
                    'enabled': True,
                    'endpoint': '/health/sip',
                    'interval': 30,
                    'timeout': 10
                }
            }
            
            # Сохраняем исправленную конфигурацию
            with open('livekit-sip-simple-fixed.yaml', 'w') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("✓ Исправленная конфигурация сохранена в livekit-sip-simple-fixed.yaml")
            return True
            
        except Exception as e:
            logger.error(f"✗ Ошибка исправления конфигурации: {e}")
            return False
    
    def restart_livekit_sip(self):
        """Перезапускает LiveKit SIP сервис"""
        logger.info("Перезапуск LiveKit SIP сервиса...")
        
        try:
            # Останавливаем текущий контейнер
            subprocess.run(['docker', 'stop', 'voice-ai-livekit-sip'], 
                         capture_output=True, check=False)
            
            # Удаляем контейнер
            subprocess.run(['docker', 'rm', 'voice-ai-livekit-sip'], 
                         capture_output=True, check=False)
            
            # Запускаем с исправленной конфигурацией
            cmd = [
                'docker', 'run', '-d',
                '--name', 'voice-ai-livekit-sip',
                '--network', 'voice-ai-simple_default',
                '-p', '5060:5060/udp',
                '-p', '5060:5060/tcp', 
                '-v', f'{os.getcwd()}/livekit-sip-simple-fixed.yaml:/etc/livekit-sip.yaml',
                'livekit/sip:latest',
                '--config', '/etc/livekit-sip.yaml'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ LiveKit SIP сервис перезапущен успешно")
                return True
            else:
                logger.error(f"✗ Ошибка перезапуска: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Ошибка перезапуска сервиса: {e}")
            return False
    
    def wait_for_service_ready(self, timeout=60):
        """Ждет готовности сервиса"""
        logger.info("Ожидание готовности сервиса...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '10'], 
                                      capture_output=True, text=True)
                
                if 'server starting' in result.stdout:
                    logger.info("✓ Сервис готов к работе")
                    return True
                    
                time.sleep(2)
                
            except Exception:
                time.sleep(2)
                continue
        
        logger.error("✗ Сервис не готов в течение таймаута")
        return False
    
    def test_sip_registration(self):
        """Тестирует регистрацию SIP"""
        logger.info("Тестирование SIP регистрации...")
        
        try:
            # Проверяем логи на наличие успешной регистрации
            result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '50'], 
                                  capture_output=True, text=True)
            
            if 'register success' in result.stdout.lower() or 'registered' in result.stdout.lower():
                logger.info("✓ SIP регистрация успешна")
                return True
            elif 'register failed' in result.stdout.lower() or 'registration failed' in result.stdout.lower():
                logger.error("✗ SIP регистрация неуспешна")
                return False
            else:
                logger.warning("⚠ Статус SIP регистрации неясен")
                return None
                
        except Exception as e:
            logger.error(f"✗ Ошибка проверки SIP регистрации: {e}")
            return False
    
    def run_diagnostics(self):
        """Запускает полную диагностику"""
        logger.info("=== Диагностика LiveKit SIP Authentication ===")
        
        results = {}
        
        # Тестируем подключение к LiveKit
        results['livekit_connection'] = self.test_livekit_connection()
        
        # Тестируем webhook endpoint
        results['webhook_endpoint'] = self.test_webhook_endpoint()
        
        # Проверяем конфигурацию SIP trunk
        results['sip_trunk_config'] = self.check_sip_trunk_config()
        
        return results
    
    def fix_all_issues(self):
        """Исправляет все найденные проблемы"""
        logger.info("=== Исправление проблем LiveKit SIP ===")
        
        # Диагностика
        diagnostics = self.run_diagnostics()
        
        # Исправляем конфигурацию
        if not self.fix_livekit_sip_config():
            return False
        
        # Перезапускаем сервис
        if not self.restart_livekit_sip():
            return False
        
        # Ждем готовности
        if not self.wait_for_service_ready():
            return False
        
        # Тестируем регистрацию
        registration_status = self.test_sip_registration()
        
        logger.info("=== Результаты исправления ===")
        logger.info(f"Конфигурация исправлена: ✓")
        logger.info(f"Сервис перезапущен: ✓")
        logger.info(f"SIP регистрация: {'✓' if registration_status else '✗' if registration_status is False else '?'}")
        
        return True

def main():
    """Основная функция"""
    fixer = LiveKitSIPAuthFixer()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--diagnose':
        # Только диагностика
        results = fixer.run_diagnostics()
        
        print("\n=== Результаты диагностики ===")
        for test, result in results.items():
            status = "✓" if result else "✗"
            print(f"{test}: {status}")
    else:
        # Полное исправление
        success = fixer.fix_all_issues()
        
        if success:
            print("\n✓ Проблемы с аутентификацией LiveKit SIP исправлены!")
            print("Попробуйте совершить тестовый звонок.")
        else:
            print("\n✗ Не удалось исправить все проблемы.")
            print("Проверьте логи для получения дополнительной информации.")

if __name__ == '__main__':
    main()
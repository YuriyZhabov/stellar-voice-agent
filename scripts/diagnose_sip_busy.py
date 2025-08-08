#!/usr/bin/env python3
"""
Диагностика проблемы "занято" при SIP звонках
Проверяет все возможные причины отклонения звонков
"""

import os
import sys
import json
import yaml
import requests
import time
import subprocess
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SIPBusyDiagnostic:
    def __init__(self):
        self.load_config()
        
    def load_config(self):
        """Загружает конфигурацию"""
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
            self.sip_number = os.getenv('SIP_NUMBER', '+79952227978')
            
            logger.info("Конфигурация загружена")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            sys.exit(1)
    
    def check_docker_containers(self):
        """Проверяет статус Docker контейнеров"""
        logger.info("=== Проверка Docker контейнеров ===")
        
        containers = [
            'voice-ai-livekit-sip',
            'voice-ai-agent-simple', 
            'voice-ai-redis-simple'
        ]
        
        results = {}
        
        for container in containers:
            try:
                result = subprocess.run(['docker', 'ps', '--filter', f'name={container}'], 
                                      capture_output=True, text=True)
                
                if container in result.stdout and 'Up' in result.stdout:
                    logger.info(f"✓ {container}: Запущен")
                    results[container] = True
                else:
                    logger.error(f"✗ {container}: Не запущен")
                    results[container] = False
                    
            except Exception as e:
                logger.error(f"✗ Ошибка проверки {container}: {e}")
                results[container] = False
        
        return results
    
    def check_network_connectivity(self):
        """Проверяет сетевое подключение"""
        logger.info("=== Проверка сетевого подключения ===")
        
        tests = {}
        
        # Проверка LiveKit сервера
        try:
            url = self.livekit_url.replace('wss://', 'https://')
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                logger.info("✓ LiveKit сервер доступен")
                tests['livekit_server'] = True
            else:
                logger.error(f"✗ LiveKit сервер недоступен: {response.status_code}")
                tests['livekit_server'] = False
                
        except Exception as e:
            logger.error(f"✗ Ошибка подключения к LiveKit: {e}")
            tests['livekit_server'] = False
        
        # Проверка webhook endpoint
        try:
            webhook_url = f"http://{self.domain}:{self.port}/webhooks/livekit"
            response = requests.get(webhook_url, timeout=5)
            
            if response.status_code in [200, 405]:
                logger.info("✓ Webhook endpoint доступен")
                tests['webhook_endpoint'] = True
            else:
                logger.warning(f"⚠ Webhook endpoint: {response.status_code}")
                tests['webhook_endpoint'] = False
                
        except Exception as e:
            logger.error(f"✗ Webhook endpoint недоступен: {e}")
            tests['webhook_endpoint'] = False
        
        # Проверка SIP сервера Novofon
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            result = sock.connect_ex(('sip.novofon.ru', 5060))
            sock.close()
            
            if result == 0:
                logger.info("✓ SIP сервер Novofon доступен")
                tests['novofon_sip'] = True
            else:
                logger.error("✗ SIP сервер Novofon недоступен")
                tests['novofon_sip'] = False
                
        except Exception as e:
            logger.error(f"✗ Ошибка подключения к Novofon: {e}")
            tests['novofon_sip'] = False
        
        return tests
    
    def check_livekit_api_auth(self):
        """Проверяет аутентификацию с LiveKit API"""
        logger.info("=== Проверка аутентификации LiveKit API ===")
        
        try:
            import jwt
            import time
            
            # Создаем JWT токен для тестирования
            payload = {
                'iss': self.livekit_api_key,
                'exp': int(time.time()) + 3600,  # 1 час
                'nbf': int(time.time()) - 60,    # 1 минута назад
                'sub': 'test-auth'
            }
            
            token = jwt.encode(payload, self.livekit_api_secret, algorithm='HS256')
            
            # Тестируем API
            api_url = self.livekit_url.replace('wss://', 'https://').replace('ws://', 'http://')
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(f"{api_url}/", headers=headers, timeout=10)
            
            if response.status_code in [200, 404]:  # 404 тоже OK для API endpoint
                logger.info("✓ LiveKit API аутентификация работает")
                return True
            else:
                logger.error(f"✗ LiveKit API аутентификация неуспешна: {response.status_code}")
                return False
                
        except ImportError:
            logger.warning("⚠ PyJWT не установлен, пропускаем тест API")
            return None
        except Exception as e:
            logger.error(f"✗ Ошибка тестирования LiveKit API: {e}")
            return False
    
    def check_sip_configuration(self):
        """Проверяет конфигурацию SIP"""
        logger.info("=== Проверка конфигурации SIP ===")
        
        try:
            with open('livekit-sip-simple.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            issues = []
            
            # Проверяем SIP trunk
            if 'sip_trunks' not in config:
                issues.append("Отсутствует секция sip_trunks")
            else:
                trunk = config['sip_trunks'][0]
                
                required_fields = ['host', 'username', 'password', 'port']
                for field in required_fields:
                    if field not in trunk or not trunk[field]:
                        issues.append(f"Отсутствует поле {field} в SIP trunk")
            
            # Проверяем routing
            if 'routing' not in config:
                issues.append("Отсутствует секция routing")
            elif 'inbound_rules' not in config['routing']:
                issues.append("Отсутствуют inbound_rules")
            else:
                rule = config['routing']['inbound_rules'][0]
                if 'match' not in rule or 'to' not in rule['match']:
                    issues.append("Неправильная конфигурация routing rule")
            
            # Проверяем LiveKit конфигурацию
            if 'livekit' not in config:
                issues.append("Отсутствует секция livekit")
            else:
                lk = config['livekit']
                required_lk_fields = ['url', 'api_key', 'api_secret']
                for field in required_lk_fields:
                    if field not in lk or not lk[field]:
                        issues.append(f"Отсутствует поле {field} в livekit")
            
            if issues:
                for issue in issues:
                    logger.error(f"✗ {issue}")
                return False
            else:
                logger.info("✓ Конфигурация SIP корректна")
                return True
                
        except Exception as e:
            logger.error(f"✗ Ошибка проверки конфигурации: {e}")
            return False
    
    def check_port_availability(self):
        """Проверяет доступность портов"""
        logger.info("=== Проверка портов ===")
        
        import socket
        
        ports_to_check = [
            (5060, 'SIP UDP'),
            (8000, 'Webhook HTTP'),
            (6379, 'Redis')
        ]
        
        results = {}
        
        for port, description in ports_to_check:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    logger.info(f"✓ Порт {port} ({description}): Доступен")
                    results[port] = True
                else:
                    logger.warning(f"⚠ Порт {port} ({description}): Недоступен")
                    results[port] = False
                    
            except Exception as e:
                logger.error(f"✗ Ошибка проверки порта {port}: {e}")
                results[port] = False
        
        return results
    
    def analyze_recent_logs(self):
        """Анализирует последние логи"""
        logger.info("=== Анализ логов ===")
        
        try:
            result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '100'], 
                                  capture_output=True, text=True)
            
            logs = result.stdout
            
            # Ищем ключевые события
            events = {
                'auth_failures': logs.count('auth check failed'),
                'processing_invites': logs.count('processing invite'),
                'server_starting': logs.count('server starting'),
                'connection_errors': logs.count('connection failed') + logs.count('failed to connect'),
                'registration_attempts': logs.count('register') + logs.count('registration')
            }
            
            logger.info(f"Ошибки аутентификации: {events['auth_failures']}")
            logger.info(f"Обработка звонков: {events['processing_invites']}")
            logger.info(f"Запуски сервера: {events['server_starting']}")
            logger.info(f"Ошибки подключения: {events['connection_errors']}")
            logger.info(f"Попытки регистрации: {events['registration_attempts']}")
            
            return events
            
        except Exception as e:
            logger.error(f"✗ Ошибка анализа логов: {e}")
            return {}
    
    def generate_fix_recommendations(self, diagnostics):
        """Генерирует рекомендации по исправлению"""
        logger.info("=== Рекомендации по исправлению ===")
        
        recommendations = []
        
        # Проверяем контейнеры
        if not all(diagnostics.get('containers', {}).values()):
            recommendations.append("Перезапустить неработающие контейнеры")
        
        # Проверяем сеть
        if not diagnostics.get('network', {}).get('livekit_server'):
            recommendations.append("Проверить подключение к LiveKit серверу")
        
        if not diagnostics.get('network', {}).get('webhook_endpoint'):
            recommendations.append("Проверить работу webhook endpoint")
        
        # Проверяем аутентификацию
        if diagnostics.get('livekit_auth') is False:
            recommendations.append("Проверить API ключи LiveKit")
        
        # Проверяем логи
        logs = diagnostics.get('logs', {})
        if logs.get('auth_failures', 0) > 0:
            recommendations.append("Исправить проблемы аутентификации LiveKit")
        
        if logs.get('connection_errors', 0) > 0:
            recommendations.append("Исправить проблемы подключения")
        
        if not recommendations:
            recommendations.append("Все основные компоненты работают корректно")
        
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. {rec}")
        
        return recommendations
    
    def run_full_diagnostic(self):
        """Запускает полную диагностику"""
        logger.info("=== ДИАГНОСТИКА ПРОБЛЕМЫ 'ЗАНЯТО' ===")
        
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'containers': self.check_docker_containers(),
            'network': self.check_network_connectivity(),
            'livekit_auth': self.check_livekit_api_auth(),
            'sip_config': self.check_sip_configuration(),
            'ports': self.check_port_availability(),
            'logs': self.analyze_recent_logs()
        }
        
        # Генерируем рекомендации
        recommendations = self.generate_fix_recommendations(diagnostics)
        diagnostics['recommendations'] = recommendations
        
        # Сохраняем отчет
        report_filename = f"sip_busy_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(diagnostics, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Отчет сохранен в {report_filename}")
        
        return diagnostics

def main():
    """Основная функция"""
    diagnostic = SIPBusyDiagnostic()
    results = diagnostic.run_full_diagnostic()
    
    # Выводим краткое резюме
    print("\n=== РЕЗЮМЕ ===")
    
    all_containers_ok = all(results['containers'].values())
    network_ok = all(results['network'].values())
    config_ok = results['sip_config']
    
    print(f"Контейнеры: {'✓' if all_containers_ok else '✗'}")
    print(f"Сеть: {'✓' if network_ok else '✗'}")
    print(f"Конфигурация: {'✓' if config_ok else '✗'}")
    print(f"Ошибки аутентификации: {results['logs'].get('auth_failures', 0)}")
    
    if results['logs'].get('auth_failures', 0) > 0:
        print("\n⚠ ОСНОВНАЯ ПРОБЛЕМА: Ошибки аутентификации LiveKit")
        print("Рекомендуется проверить API ключи и подключение к LiveKit")

if __name__ == '__main__':
    main()
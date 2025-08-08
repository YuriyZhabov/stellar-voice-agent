#!/usr/bin/env python3
"""
Тестирование исправления аутентификации SIP
Проверяет, что проблема с "auth check failed" решена
"""

import os
import sys
import time
import subprocess
import logging
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SIPAuthTester:
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
                        
            self.sip_number = os.getenv('SIP_NUMBER', '+79952227978')
            logger.info("Конфигурация загружена успешно")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            sys.exit(1)
    
    def check_service_status(self):
        """Проверяет статус LiveKit SIP сервиса"""
        logger.info("Проверка статуса LiveKit SIP сервиса...")
        
        try:
            result = subprocess.run(['docker', 'ps', '--filter', 'name=voice-ai-livekit-sip'], 
                                  capture_output=True, text=True)
            
            if 'voice-ai-livekit-sip' in result.stdout and 'Up' in result.stdout:
                logger.info("✓ LiveKit SIP сервис запущен")
                return True
            else:
                logger.error("✗ LiveKit SIP сервис не запущен")
                return False
                
        except Exception as e:
            logger.error(f"✗ Ошибка проверки статуса сервиса: {e}")
            return False
    
    def monitor_logs_for_auth_errors(self, duration=30):
        """Мониторит логи на предмет ошибок аутентификации"""
        logger.info(f"Мониторинг логов в течение {duration} секунд...")
        
        start_time = time.time()
        auth_errors = []
        successful_calls = []
        
        while time.time() - start_time < duration:
            try:
                result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '10'], 
                                      capture_output=True, text=True)
                
                lines = result.stdout.split('\n')
                
                for line in lines:
                    if 'auth check failed' in line.lower():
                        auth_errors.append({
                            'timestamp': datetime.now().isoformat(),
                            'message': line.strip()
                        })
                    elif 'processing invite' in line.lower():
                        successful_calls.append({
                            'timestamp': datetime.now().isoformat(),
                            'message': line.strip()
                        })
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка мониторинга логов: {e}")
                time.sleep(2)
                continue
        
        return {
            'auth_errors': auth_errors,
            'successful_calls': successful_calls,
            'monitoring_duration': duration
        }
    
    def check_livekit_connectivity(self):
        """Проверяет подключение к LiveKit"""
        logger.info("Проверка подключения к LiveKit...")
        
        try:
            result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '50'], 
                                  capture_output=True, text=True)
            
            if 'connecting to livekit' in result.stdout.lower():
                logger.info("✓ Попытка подключения к LiveKit обнаружена")
                
                if 'connected to livekit' in result.stdout.lower():
                    logger.info("✓ Успешное подключение к LiveKit")
                    return True
                elif 'failed to connect' in result.stdout.lower():
                    logger.error("✗ Ошибка подключения к LiveKit")
                    return False
                else:
                    logger.warning("⚠ Статус подключения к LiveKit неясен")
                    return None
            else:
                logger.warning("⚠ Попытки подключения к LiveKit не обнаружены")
                return None
                
        except Exception as e:
            logger.error(f"✗ Ошибка проверки подключения к LiveKit: {e}")
            return False
    
    def check_sip_registration(self):
        """Проверяет SIP регистрацию"""
        logger.info("Проверка SIP регистрации...")
        
        try:
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
    
    def generate_test_report(self, monitoring_results):
        """Генерирует отчет о тестировании"""
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'sip_number': self.sip_number,
            'service_status': self.check_service_status(),
            'livekit_connectivity': self.check_livekit_connectivity(),
            'sip_registration': self.check_sip_registration(),
            'monitoring_results': monitoring_results,
            'summary': {
                'auth_errors_count': len(monitoring_results['auth_errors']),
                'successful_calls_count': len(monitoring_results['successful_calls']),
                'auth_fix_successful': len(monitoring_results['auth_errors']) == 0
            }
        }
        
        return report
    
    def run_test(self, monitoring_duration=30):
        """Запускает полный тест"""
        logger.info("=== Тестирование исправления аутентификации SIP ===")
        
        # Проверяем статус сервиса
        if not self.check_service_status():
            logger.error("Сервис не запущен. Завершение теста.")
            return False
        
        # Мониторим логи
        logger.info("Начинаем мониторинг логов...")
        logger.info(f"Попробуйте позвонить на номер {self.sip_number} в течение следующих {monitoring_duration} секунд")
        
        monitoring_results = self.monitor_logs_for_auth_errors(monitoring_duration)
        
        # Генерируем отчет
        report = self.generate_test_report(monitoring_results)
        
        # Сохраняем отчет
        report_filename = f"sip_auth_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Выводим результаты
        logger.info("=== Результаты тестирования ===")
        logger.info(f"Статус сервиса: {'✓' if report['service_status'] else '✗'}")
        logger.info(f"Подключение к LiveKit: {'✓' if report['livekit_connectivity'] else '✗' if report['livekit_connectivity'] is False else '?'}")
        logger.info(f"SIP регистрация: {'✓' if report['sip_registration'] else '✗' if report['sip_registration'] is False else '?'}")
        logger.info(f"Ошибки аутентификации: {report['summary']['auth_errors_count']}")
        logger.info(f"Успешные звонки: {report['summary']['successful_calls_count']}")
        logger.info(f"Исправление успешно: {'✓' if report['summary']['auth_fix_successful'] else '✗'}")
        
        logger.info(f"Подробный отчет сохранен в {report_filename}")
        
        return report['summary']['auth_fix_successful']

def main():
    """Основная функция"""
    tester = SIPAuthTester()
    
    # Получаем длительность мониторинга из аргументов
    monitoring_duration = 30
    if len(sys.argv) > 1:
        try:
            monitoring_duration = int(sys.argv[1])
        except ValueError:
            logger.warning("Неверный формат длительности мониторинга. Используется значение по умолчанию: 30 секунд")
    
    # Запускаем тест
    success = tester.run_test(monitoring_duration)
    
    if success:
        print("\n✓ Тест пройден! Проблема с аутентификацией SIP исправлена.")
    else:
        print("\n✗ Тест не пройден. Проблемы с аутентификацией все еще присутствуют.")
        print("Проверьте отчет для получения дополнительной информации.")

if __name__ == '__main__':
    main()
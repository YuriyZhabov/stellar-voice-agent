#!/usr/bin/env python3
"""
Скрипт тестирования SIP конфигурации LiveKit.
Проверяет подключение к LiveKit API и корректность SIP настроек.
"""

import asyncio
import os
import sys
import yaml
import json
import time
from datetime import datetime, UTC
from typing import Dict, Any, Optional
import logging
import aiohttp

# Добавляем путь к src для импорта модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth.livekit_auth import LiveKitAuthManager
from clients.livekit_api_client import LiveKitAPIClient

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SIPConfigurationTester:
    """Тестер SIP конфигурации LiveKit."""
    
    def __init__(self, config_path: str = 'livekit-sip-correct.yaml'):
        self.config_path = config_path
        self.config = None
        self.auth_manager = None
        self.api_client = None
        self.test_results = {
            'timestamp': datetime.now(UTC).isoformat(),
            'tests': {},
            'overall_status': 'unknown'
        }
    
    async def load_configuration(self) -> bool:
        """Загрузка конфигурации и инициализация клиентов."""
        try:
            # Загрузка YAML конфигурации
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # Получение настроек из переменных окружения
            livekit_url = os.getenv('LIVEKIT_URL')
            api_key = os.getenv('LIVEKIT_API_KEY')
            api_secret = os.getenv('LIVEKIT_API_SECRET')
            
            if not all([livekit_url, api_key, api_secret]):
                logger.error("Отсутствуют обязательные переменные окружения LiveKit")
                return False
            
            # Инициализация менеджера аутентификации
            self.auth_manager = LiveKitAuthManager(api_key, api_secret)
            
            # Инициализация API клиента
            self.api_client = LiveKitAPIClient(livekit_url, api_key, api_secret)
            
            logger.info("Конфигурация загружена и клиенты инициализированы")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return False
    
    async def test_livekit_connection(self) -> Dict[str, Any]:
        """Тест подключения к LiveKit API."""
        test_name = "livekit_connection"
        logger.info("Тестирование подключения к LiveKit...")
        
        try:
            start_time = time.time()
            
            # Попытка получить список комнат
            rooms = await self.api_client.list_rooms()
            
            latency = time.time() - start_time
            
            result = {
                'status': 'success',
                'latency_ms': round(latency * 1000, 2),
                'rooms_count': len(rooms),
                'message': f'Подключение успешно, найдено {len(rooms)} комнат'
            }
            
            logger.info(f"✅ Подключение к LiveKit успешно (латентность: {result['latency_ms']}ms)")
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка подключения к LiveKit: {e}'
            }
            logger.error(f"❌ Ошибка подключения к LiveKit: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def test_jwt_token_creation(self) -> Dict[str, Any]:
        """Тест создания JWT токенов."""
        test_name = "jwt_token_creation"
        logger.info("Тестирование создания JWT токенов...")
        
        try:
            # Тест создания токена участника
            participant_token = self.auth_manager.create_participant_token(
                identity="test_participant",
                room_name="test_room"
            )
            
            # Тест создания административного токена
            admin_token = self.auth_manager.create_admin_token()
            
            # Проверка, что токены не пустые
            if not participant_token or not admin_token:
                raise ValueError("Созданные токены пусты")
            
            result = {
                'status': 'success',
                'participant_token_length': len(participant_token),
                'admin_token_length': len(admin_token),
                'message': 'JWT токены созданы успешно'
            }
            
            logger.info("✅ JWT токены созданы успешно")
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка создания JWT токенов: {e}'
            }
            logger.error(f"❌ Ошибка создания JWT токенов: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def test_room_operations(self) -> Dict[str, Any]:
        """Тест операций с комнатами."""
        test_name = "room_operations"
        logger.info("Тестирование операций с комнатами...")
        
        test_room_name = f"test_room_{int(time.time())}"
        
        try:
            # Создание тестовой комнаты
            room = await self.api_client.create_room(
                name=test_room_name,
                empty_timeout=300,
                departure_timeout=20,
                max_participants=2,
                metadata={"test": True, "created_by": "sip_config_test"}
            )
            
            logger.info(f"Создана тестовая комната: {room.name}")
            
            # Получение списка комнат
            rooms = await self.api_client.list_rooms()
            room_found = any(r.name == test_room_name for r in rooms)
            
            if not room_found:
                raise ValueError("Созданная комната не найдена в списке")
            
            # Получение списка участников (должен быть пустым)
            participants = await self.api_client.list_participants(test_room_name)
            
            # Удаление тестовой комнаты
            await self.api_client.delete_room(test_room_name)
            
            result = {
                'status': 'success',
                'room_name': test_room_name,
                'participants_count': len(participants),
                'message': 'Операции с комнатами выполнены успешно'
            }
            
            logger.info("✅ Операции с комнатами выполнены успешно")
            
        except Exception as e:
            # Попытка очистки в случае ошибки
            try:
                await self.api_client.delete_room(test_room_name)
            except:
                pass
            
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка операций с комнатами: {e}'
            }
            logger.error(f"❌ Ошибка операций с комнатами: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def test_sip_configuration_validity(self) -> Dict[str, Any]:
        """Тест валидности SIP конфигурации."""
        test_name = "sip_configuration"
        logger.info("Тестирование SIP конфигурации...")
        
        try:
            config_issues = []
            
            # Проверка SIP транков
            sip_trunks = self.config.get('sip_trunks', [])
            if not sip_trunks:
                config_issues.append("Отсутствуют SIP транки")
            
            # Проверка правил маршрутизации
            routing = self.config.get('routing', {})
            inbound_rules = routing.get('inbound_rules', [])
            if not inbound_rules:
                config_issues.append("Отсутствуют правила входящей маршрутизации")
            
            # Проверка аудио кодеков
            audio_codecs = self.config.get('audio_codecs', [])
            if not audio_codecs:
                config_issues.append("Отсутствуют аудио кодеки")
            
            # Проверка webhook конфигурации
            webhooks = self.config.get('webhooks', {})
            if not webhooks.get('enabled'):
                config_issues.append("Webhooks отключены")
            
            if config_issues:
                result = {
                    'status': 'warning',
                    'issues': config_issues,
                    'message': f'Найдены проблемы в конфигурации: {len(config_issues)}'
                }
                logger.warning(f"⚠️  Найдены проблемы в SIP конфигурации: {config_issues}")
            else:
                result = {
                    'status': 'success',
                    'message': 'SIP конфигурация корректна'
                }
                logger.info("✅ SIP конфигурация корректна")
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка проверки SIP конфигурации: {e}'
            }
            logger.error(f"❌ Ошибка проверки SIP конфигурации: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def test_webhook_endpoint(self) -> Dict[str, Any]:
        """Тест доступности webhook endpoint."""
        test_name = "webhook_endpoint"
        logger.info("Тестирование webhook endpoint...")
        
        try:
            webhooks_config = self.config.get('webhooks', {})
            webhook_url = webhooks_config.get('url', '')
            
            if not webhook_url:
                result = {
                    'status': 'skipped',
                    'message': 'Webhook URL не настроен'
                }
                logger.info("⏭️  Webhook URL не настроен, пропускаем тест")
            else:
                # Заменяем переменные окружения в URL
                webhook_url = webhook_url.replace('${DOMAIN}', os.getenv('DOMAIN', 'localhost'))
                webhook_url = webhook_url.replace('${PORT}', os.getenv('PORT', '8000'))
                
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(webhook_url, timeout=5) as response:
                            latency = time.time() - start_time
                            
                            result = {
                                'status': 'success',
                                'url': webhook_url,
                                'status_code': response.status,
                                'latency_ms': round(latency * 1000, 2),
                                'message': f'Webhook endpoint доступен (код: {response.status})'
                            }
                            logger.info(f"✅ Webhook endpoint доступен: {webhook_url}")
                    
                    except aiohttp.ClientError as e:
                        result = {
                            'status': 'error',
                            'url': webhook_url,
                            'error': str(e),
                            'message': f'Webhook endpoint недоступен: {e}'
                        }
                        logger.error(f"❌ Webhook endpoint недоступен: {e}")
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка тестирования webhook endpoint: {e}'
            }
            logger.error(f"❌ Ошибка тестирования webhook endpoint: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def test_environment_variables(self) -> Dict[str, Any]:
        """Тест наличия необходимых переменных окружения."""
        test_name = "environment_variables"
        logger.info("Проверка переменных окружения...")
        
        try:
            required_vars = [
                'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET',
                'SIP_NUMBER', 'SIP_SERVER', 'SIP_USERNAME', 'SIP_PASSWORD',
                'DOMAIN', 'PORT', 'SECRET_KEY', 'REDIS_URL'
            ]
            
            missing_vars = []
            present_vars = []
            
            for var in required_vars:
                value = os.getenv(var)
                if value:
                    present_vars.append(var)
                else:
                    missing_vars.append(var)
            
            if missing_vars:
                result = {
                    'status': 'error',
                    'missing_variables': missing_vars,
                    'present_variables': present_vars,
                    'message': f'Отсутствуют переменные окружения: {", ".join(missing_vars)}'
                }
                logger.error(f"❌ Отсутствуют переменные окружения: {missing_vars}")
            else:
                result = {
                    'status': 'success',
                    'present_variables': present_vars,
                    'message': 'Все необходимые переменные окружения присутствуют'
                }
                logger.info("✅ Все необходимые переменные окружения присутствуют")
            
        except Exception as e:
            result = {
                'status': 'error',
                'error': str(e),
                'message': f'Ошибка проверки переменных окружения: {e}'
            }
            logger.error(f"❌ Ошибка проверки переменных окружения: {e}")
        
        self.test_results['tests'][test_name] = result
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов."""
        logger.info("🚀 Начинаем комплексное тестирование SIP конфигурации...")
        
        if not await self.load_configuration():
            self.test_results['overall_status'] = 'configuration_error'
            return self.test_results
        
        # Список тестов для выполнения
        tests = [
            self.test_environment_variables,
            self.test_livekit_connection,
            self.test_jwt_token_creation,
            self.test_room_operations,
            self.test_sip_configuration_validity,
            self.test_webhook_endpoint
        ]
        
        # Выполнение тестов
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                test_name = test_func.__name__.replace('test_', '')
                self.test_results['tests'][test_name] = {
                    'status': 'error',
                    'error': str(e),
                    'message': f'Неожиданная ошибка в тесте: {e}'
                }
                logger.error(f"❌ Неожиданная ошибка в тесте {test_name}: {e}")
        
        # Определение общего статуса
        test_statuses = [test['status'] for test in self.test_results['tests'].values()]
        
        if 'error' in test_statuses:
            self.test_results['overall_status'] = 'failed'
        elif 'warning' in test_statuses:
            self.test_results['overall_status'] = 'passed_with_warnings'
        else:
            self.test_results['overall_status'] = 'passed'
        
        return self.test_results
    
    def print_summary(self) -> None:
        """Вывод сводки результатов тестирования."""
        print("\n" + "="*80)
        print("📊 СВОДКА РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ SIP КОНФИГУРАЦИИ")
        print("="*80)
        
        overall_status = self.test_results['overall_status']
        status_icons = {
            'passed': '✅',
            'passed_with_warnings': '⚠️',
            'failed': '❌',
            'configuration_error': '🔧'
        }
        
        status_messages = {
            'passed': 'ВСЕ ТЕСТЫ ПРОЙДЕНЫ',
            'passed_with_warnings': 'ТЕСТЫ ПРОЙДЕНЫ С ПРЕДУПРЕЖДЕНИЯМИ',
            'failed': 'ТЕСТЫ НЕ ПРОЙДЕНЫ',
            'configuration_error': 'ОШИБКА КОНФИГУРАЦИИ'
        }
        
        icon = status_icons.get(overall_status, '❓')
        message = status_messages.get(overall_status, 'НЕИЗВЕСТНЫЙ СТАТУС')
        
        print(f"\n{icon} ОБЩИЙ СТАТУС: {message}")
        print(f"🕐 Время тестирования: {self.test_results['timestamp']}")
        print(f"📁 Файл конфигурации: {self.config_path}")
        
        print(f"\n📋 ДЕТАЛИ ТЕСТОВ:")
        for test_name, test_result in self.test_results['tests'].items():
            status = test_result['status']
            message = test_result.get('message', 'Нет сообщения')
            
            status_icon = {
                'success': '✅',
                'warning': '⚠️',
                'error': '❌',
                'skipped': '⏭️'
            }.get(status, '❓')
            
            print(f"  {status_icon} {test_name}: {message}")
            
            if 'error' in test_result:
                print(f"     Ошибка: {test_result['error']}")
        
        print("\n" + "="*80)
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Сохранение отчета в файл."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sip_config_test_report_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Отчет сохранен в файл: {filename}")
        return filename

async def main():
    """Основная функция."""
    config_file = 'livekit-sip-correct.yaml'
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    tester = SIPConfigurationTester(config_file)
    results = await tester.run_all_tests()
    
    # Вывод сводки
    tester.print_summary()
    
    # Сохранение отчета
    report_file = tester.save_report()
    
    # Возврат кода выхода
    exit_code = 0 if results['overall_status'] in ['passed', 'passed_with_warnings'] else 1
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())
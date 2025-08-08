#!/usr/bin/env python3
"""
Скрипт валидации SIP конфигурации LiveKit согласно спецификации API.
Проверяет корректность настроек в livekit-sip-correct.yaml.
"""

import yaml
import os
import sys
import re
from typing import Dict, Any, List, Optional
import logging
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SIPConfigValidator:
    """Валидатор конфигурации SIP согласно LiveKit API спецификации."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.errors = []
        self.warnings = []
    
    def load_config(self) -> bool:
        """Загрузка конфигурационного файла."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Замена переменных окружения для валидации
            import re
            def replace_env_var(match):
                var_name = match.group(1)
                default_value = match.group(2) if match.group(2) else ""
                return os.getenv(var_name, default_value)
            
            # Замена ${VAR} и ${VAR:-default}
            content = re.sub(r'\$\{([^}:]+)(?::-([^}]*))?\}', replace_env_var, content)
            
            self.config = yaml.safe_load(content)
            logger.info(f"Конфигурация загружена из {self.config_path}")
            return True
        except FileNotFoundError:
            self.errors.append(f"Файл конфигурации не найден: {self.config_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"Ошибка парсинга YAML: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Ошибка загрузки конфигурации: {e}")
            return False
    
    def validate_livekit_config(self) -> None:
        """Валидация основной конфигурации LiveKit."""
        livekit_config = self.config.get('livekit', {})
        
        # Проверка обязательных полей
        required_fields = ['url', 'api_key', 'api_secret']
        for field in required_fields:
            if not livekit_config.get(field):
                self.errors.append(f"Отсутствует обязательное поле livekit.{field}")
        
        # Проверка формата URL
        url = livekit_config.get('url', '')
        if url and not (url.startswith('wss://') or url.startswith('ws://')):
            self.errors.append("livekit.url должен начинаться с wss:// или ws://")
        
        # Проверка настроек подключения
        connection_settings = {
            'connection_timeout': r'^\d+s$',
            'keep_alive': r'^\d+s$',
            'reconnect_delay': r'^\d+s$'
        }
        
        for setting, pattern in connection_settings.items():
            value = livekit_config.get(setting)
            if value and not re.match(pattern, str(value)):
                self.errors.append(f"livekit.{setting} должен быть в формате '30s'")
        
        # Проверка числовых значений
        numeric_settings = ['max_reconnect_attempts']
        for setting in numeric_settings:
            value = livekit_config.get(setting)
            if value is not None and not isinstance(value, int):
                self.errors.append(f"livekit.{setting} должен быть числом")
    
    def validate_sip_trunks(self) -> None:
        """Валидация конфигурации SIP транков согласно API."""
        sip_trunks = self.config.get('sip_trunks', [])
        
        if not sip_trunks:
            self.errors.append("Не настроены SIP транки")
            return
        
        trunk_names = set()
        has_inbound = False
        has_outbound = False
        
        for i, trunk in enumerate(sip_trunks):
            trunk_name = trunk.get('name', f'trunk_{i}')
            
            # Проверка уникальности имен
            if trunk_name in trunk_names:
                self.errors.append(f"Дублирующееся имя транка: {trunk_name}")
            trunk_names.add(trunk_name)
            
            # Проверка типа транка
            is_inbound = trunk.get('inbound_only', False)
            is_outbound = trunk.get('outbound_only', False)
            
            if is_inbound and is_outbound:
                self.errors.append(f"Транк {trunk_name} не может быть одновременно inbound_only и outbound_only")
            
            if is_inbound:
                has_inbound = True
                self._validate_inbound_trunk(trunk, trunk_name)
            elif is_outbound:
                has_outbound = True
                self._validate_outbound_trunk(trunk, trunk_name)
            else:
                self.warnings.append(f"Транк {trunk_name} не имеет явного типа (inbound/outbound)")
        
        if not has_inbound:
            self.warnings.append("Не настроены входящие SIP транки")
        if not has_outbound:
            self.warnings.append("Не настроены исходящие SIP транки")
    
    def _validate_inbound_trunk(self, trunk: Dict[str, Any], name: str) -> None:
        """Валидация входящего транка согласно CreateSIPInboundTrunk API."""
        
        # Проверка номеров
        numbers = trunk.get('numbers', [])
        if not numbers:
            self.errors.append(f"Входящий транк {name} должен содержать номера")
        
        for number in numbers:
            if not isinstance(number, str):
                self.errors.append(f"Номер в транке {name} должен быть строкой: {number}")
        
        # Проверка разрешенных адресов
        allowed_addresses = trunk.get('allowed_addresses', [])
        if not allowed_addresses:
            self.warnings.append(f"Входящий транк {name} не имеет ограничений по IP")
        
        # Проверка настроек аутентификации
        auth_required = trunk.get('auth_required', False)
        if auth_required:
            if not trunk.get('auth_username') or not trunk.get('auth_password'):
                self.errors.append(f"Транк {name} требует аутентификацию, но не указаны учетные данные")
    
    def _validate_outbound_trunk(self, trunk: Dict[str, Any], name: str) -> None:
        """Валидация исходящего транка согласно CreateSIPOutboundTrunk API."""
        
        # Проверка обязательных полей
        required_fields = ['host', 'auth_username', 'auth_password']
        for field in required_fields:
            if not trunk.get(field):
                self.errors.append(f"Исходящий транк {name} должен содержать {field}")
        
        # Проверка порта
        port = trunk.get('port', 5060)
        if not isinstance(port, int) or port < 1 or port > 65535:
            self.errors.append(f"Некорректный порт в транке {name}: {port}")
        
        # Проверка транспорта
        transport = trunk.get('transport', 'UDP')
        if transport not in ['UDP', 'TCP', 'TLS']:
            self.errors.append(f"Неподдерживаемый транспорт в транке {name}: {transport}")
    
    def validate_routing_rules(self) -> None:
        """Валидация правил маршрутизации согласно CreateSIPDispatchRule API."""
        routing = self.config.get('routing', {})
        
        # Проверка входящих правил
        inbound_rules = routing.get('inbound_rules', [])
        if not inbound_rules:
            self.warnings.append("Не настроены правила маршрутизации входящих звонков")
        
        for i, rule in enumerate(inbound_rules):
            rule_name = rule.get('name', f'rule_{i}')
            
            # Проверка условий маршрутизации
            match = rule.get('match', {})
            if not match:
                self.errors.append(f"Правило {rule_name} не содержит условий маршрутизации")
            
            # Проверка действий
            action = rule.get('action', {})
            if not action:
                self.errors.append(f"Правило {rule_name} не содержит действий")
            
            action_type = action.get('type')
            if action_type == 'livekit_room':
                self._validate_room_action(action, rule_name)
            elif action_type == 'sip_trunk':
                self._validate_trunk_action(action, rule_name)
            else:
                self.errors.append(f"Неизвестный тип действия в правиле {rule_name}: {action_type}")
    
    def _validate_room_action(self, action: Dict[str, Any], rule_name: str) -> None:
        """Валидация действия создания комнаты."""
        
        # Проверка шаблона имени комнаты
        room_template = action.get('room_name_template')
        if not room_template:
            self.errors.append(f"Правило {rule_name} должно содержать room_name_template")
        
        # Проверка настроек участника
        if not action.get('participant_name'):
            self.errors.append(f"Правило {rule_name} должно содержать participant_name")
        
        if not action.get('participant_identity'):
            self.errors.append(f"Правило {rule_name} должно содержать participant_identity")
        
        # Проверка конфигурации комнаты
        room_config = action.get('room_config', {})
        if room_config:
            # Проверка таймаутов
            empty_timeout = room_config.get('empty_timeout')
            if empty_timeout is not None and not isinstance(empty_timeout, int):
                self.errors.append(f"room_config.empty_timeout должен быть числом в правиле {rule_name}")
            
            departure_timeout = room_config.get('departure_timeout')
            if departure_timeout is not None and not isinstance(departure_timeout, int):
                self.errors.append(f"room_config.departure_timeout должен быть числом в правиле {rule_name}")
            
            max_participants = room_config.get('max_participants')
            if max_participants is not None and not isinstance(max_participants, int):
                self.errors.append(f"room_config.max_participants должен быть числом в правиле {rule_name}")
    
    def validate_audio_codecs(self) -> None:
        """Валидация конфигурации аудио кодеков."""
        codecs = self.config.get('audio_codecs', [])
        
        if not codecs:
            self.warnings.append("Не настроены аудио кодеки")
            return
        
        supported_codecs = ['PCMU', 'PCMA', 'G722', 'opus', 'G729']
        codec_names = set()
        priorities = set()
        
        for codec in codecs:
            name = codec.get('name')
            priority = codec.get('priority')
            
            if not name:
                self.errors.append("Кодек должен содержать имя")
                continue
            
            if name in codec_names:
                self.errors.append(f"Дублирующийся кодек: {name}")
            codec_names.add(name)
            
            if name not in supported_codecs:
                self.warnings.append(f"Неизвестный кодек: {name}")
            
            if priority is not None:
                if not isinstance(priority, int) or priority < 1:
                    self.errors.append(f"Некорректный приоритет кодека {name}: {priority}")
                
                if priority in priorities:
                    self.errors.append(f"Дублирующийся приоритет кодека: {priority}")
                priorities.add(priority)
    
    def validate_webhooks(self) -> None:
        """Валидация конфигурации webhooks."""
        webhooks = self.config.get('webhooks', {})
        
        if not webhooks.get('enabled', False):
            self.warnings.append("Webhooks отключены")
            return
        
        # Проверка URL
        url = webhooks.get('url')
        if not url:
            self.errors.append("Не указан URL для webhooks")
        elif not (url.startswith('http://') or url.startswith('https://')):
            self.errors.append("URL webhooks должен начинаться с http:// или https://")
        
        # Проверка секрета
        if not webhooks.get('secret'):
            self.warnings.append("Не указан секрет для webhooks")
        
        # Проверка событий
        events = webhooks.get('events', [])
        if not events:
            self.warnings.append("Не указаны события для webhooks")
        
        supported_events = [
            'room_started', 'room_finished', 'participant_joined', 'participant_left',
            'track_published', 'track_unpublished', 'recording_started', 'recording_finished'
        ]
        
        for event in events:
            if event not in supported_events:
                self.warnings.append(f"Неизвестное событие webhook: {event}")
    
    def validate_environment_variables(self) -> None:
        """Проверка наличия необходимых переменных окружения."""
        required_env_vars = [
            'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET',
            'SIP_NUMBER', 'SIP_SERVER', 'SIP_USERNAME', 'SIP_PASSWORD',
            'DOMAIN', 'PORT', 'SECRET_KEY'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.errors.append(f"Отсутствуют переменные окружения: {', '.join(missing_vars)}")
    
    def validate(self) -> bool:
        """Выполнение полной валидации конфигурации."""
        logger.info("Начинаем валидацию SIP конфигурации...")
        
        if not self.load_config():
            return False
        
        # Выполнение всех проверок
        self.validate_livekit_config()
        self.validate_sip_trunks()
        self.validate_routing_rules()
        self.validate_audio_codecs()
        self.validate_webhooks()
        self.validate_environment_variables()
        
        # Вывод результатов
        if self.errors:
            logger.error("Найдены ошибки в конфигурации:")
            for error in self.errors:
                logger.error(f"  ❌ {error}")
        
        if self.warnings:
            logger.warning("Найдены предупреждения:")
            for warning in self.warnings:
                logger.warning(f"  ⚠️  {warning}")
        
        if not self.errors and not self.warnings:
            logger.info("✅ Конфигурация прошла валидацию без ошибок и предупреждений")
        elif not self.errors:
            logger.info("✅ Конфигурация прошла валидацию (есть предупреждения)")
        else:
            logger.error("❌ Конфигурация содержит ошибки")
        
        return len(self.errors) == 0
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Получение отчета о валидации."""
        return {
            'config_file': self.config_path,
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }

def main():
    """Основная функция скрипта."""
    config_file = 'livekit-sip-correct.yaml'
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    validator = SIPConfigValidator(config_file)
    is_valid = validator.validate()
    
    # Вывод отчета
    report = validator.get_validation_report()
    print(f"\n📊 Отчет о валидации:")
    print(f"   Файл: {report['config_file']}")
    print(f"   Статус: {'✅ Валидна' if report['valid'] else '❌ Невалидна'}")
    print(f"   Ошибки: {report['error_count']}")
    print(f"   Предупреждения: {report['warning_count']}")
    
    sys.exit(0 if is_valid else 1)

if __name__ == '__main__':
    main()
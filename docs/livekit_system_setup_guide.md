# Руководство по настройке системы LiveKit

## Обзор

Данное руководство описывает пошаговую настройку системы LiveKit для интеграции с Voice AI Agent. Система включает правильную аутентификацию, SIP интеграцию, мониторинг и все необходимые компоненты согласно официальной спецификации LiveKit API.

## Предварительные требования

### Системные требования
- Python 3.8+
- Redis сервер
- LiveKit сервер (cloud или self-hosted)
- SIP провайдер (например, Novofon)

### Необходимые учетные данные
- LiveKit API ключи (API_KEY, API_SECRET)
- LiveKit сервер URL
- SIP учетные данные провайдера
- Redis connection string

## Пошаговая настройка

### Шаг 1: Настройка переменных окружения

Создайте или обновите файл `.env`:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# SIP Configuration
SIP_SERVER=sip.novofon.ru
SIP_PORT=5060
SIP_TRANSPORT=UDP
SIP_USERNAME=your_sip_username
SIP_PASSWORD=your_sip_password
SIP_NUMBER=your_phone_number

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Application Configuration
DOMAIN=your-domain.com
PORT=8000
SECRET_KEY=your_secret_key
LOG_LEVEL=INFO
```

### Шаг 2: Установка зависимостей

```bash
# Установка основных зависимостей
pip install -r requirements.txt

# Проверка установки LiveKit SDK
python -c "import livekit; print('LiveKit SDK installed successfully')"
```

### Шаг 3: Настройка конфигурационных файлов

#### 3.1 Конфигурация аутентификации

Файл `config/livekit_auth.yaml`:
```yaml
livekit_auth:
  token_ttl_minutes: 10
  auto_refresh: true
  default_grants:
    room_join: true
    can_publish: true
    can_subscribe: true
    can_publish_data: true
    can_update_own_metadata: true
  
  admin_grants:
    room_create: true
    room_list: true
    room_admin: true
    room_record: true
    ingress_admin: true
```

#### 3.2 Конфигурация SIP

Файл `livekit-sip-correct.yaml` уже настроен согласно спецификации.

#### 3.3 Конфигурация мониторинга

Файл `config/monitoring.yaml`:
```yaml
monitoring:
  health_check:
    enabled: true
    interval_seconds: 60
    timeout_seconds: 10
  
  metrics:
    enabled: true
    export_interval_seconds: 30
  
  alerts:
    enabled: true
    webhook_url: "http://localhost:8000/alerts"
```

### Шаг 4: Инициализация системы

```bash
# Запуск скрипта инициализации
python scripts/init_system.py

# Проверка конфигурации
python scripts/validate_sip_config.py
```

### Шаг 5: Запуск системы

#### 5.1 Запуск в режиме разработки

```bash
# Запуск основного приложения
python src/main.py

# В отдельном терминале - запуск мониторинга
python scripts/monitor_system.py
```

#### 5.2 Запуск в production режиме

```bash
# Использование Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Или использование скрипта развертывания
./scripts/deploy_production.sh
```

### Шаг 6: Проверка работоспособности

#### 6.1 Проверка API подключения

```bash
# Тест подключения к LiveKit API
python -c "
from src.clients.livekit_api_client import LiveKitAPIClient
import asyncio
import os

async def test():
    client = LiveKitAPIClient(
        url=os.getenv('LIVEKIT_URL'),
        api_key=os.getenv('LIVEKIT_API_KEY'),
        api_secret=os.getenv('LIVEKIT_API_SECRET')
    )
    rooms = await client.list_rooms()
    print(f'Connected successfully. Found {len(rooms)} rooms.')

asyncio.run(test())
"
```

#### 6.2 Проверка SIP конфигурации

```bash
# Запуск диагностики SIP
python scripts/test_sip_configuration.py
```

#### 6.3 Проверка мониторинга

```bash
# Проверка health endpoints
curl http://localhost:8000/health

# Проверка метрик
curl http://localhost:8000/metrics
```

## Конфигурация компонентов

### Аутентификация

Система использует JWT токены с автоматическим обновлением:

```python
from src.auth.livekit_auth import LiveKitAuthManager

# Создание менеджера аутентификации
auth_manager = LiveKitAuthManager(api_key, api_secret)

# Создание токена участника
token = auth_manager.create_participant_token(
    identity="user123",
    room_name="voice-ai-call-123"
)
```

### SIP интеграция

Конфигурация поддерживает входящие и исходящие звонки:

```yaml
# Входящие звонки автоматически создают LiveKit комнаты
routing:
  inbound_rules:
    - name: "voice-ai-dispatch"
      match:
        to: "${SIP_NUMBER}"
      action:
        type: livekit_room
        room_name_template: "voice-ai-call-{call_id}"
```

### Мониторинг

Система включает комплексный мониторинг:

```python
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor

# Запуск мониторинга
monitor = LiveKitSystemMonitor(api_client)
health_status = await monitor.run_health_checks()
```

## Безопасность

### Защита API ключей

1. Никогда не храните ключи в коде
2. Используйте переменные окружения
3. Настройте маскирование в логах

### WSS соединения

Все соединения должны использовать WSS:

```python
# Правильно
LIVEKIT_URL=wss://your-server.com

# Неправильно
LIVEKIT_URL=ws://your-server.com
```

### Ротация ключей

Система поддерживает ротацию ключей без downtime:

```bash
# Обновление ключей
python scripts/rotate_api_keys.py --new-key=NEW_KEY --new-secret=NEW_SECRET
```

## Производительность

### Connection Pooling

Система автоматически управляет пулом соединений:

```python
# Настройка в config/performance.yaml
connection_pool:
  max_connections: 100
  timeout_seconds: 30
  keep_alive: true
```

### Оптимизация латентности

Рекомендуемые настройки для минимальной латентности:

```yaml
audio:
  buffer_size: 20ms
  sample_rate: 48000
  channels: 1
```

## Troubleshooting

### Частые проблемы

1. **Ошибка аутентификации**: Проверьте API ключи и их права
2. **SIP не подключается**: Проверьте настройки провайдера
3. **Высокая латентность**: Оптимизируйте настройки аудио

### Логи и диагностика

```bash
# Просмотр логов
tail -f logs/livekit_system.log

# Запуск полной диагностики
python scripts/diagnose_livekit_connection.py
```

## Поддержка и обслуживание

### Регулярные задачи

1. Мониторинг метрик производительности
2. Проверка логов на ошибки
3. Обновление зависимостей
4. Резервное копирование конфигураций

### Контакты поддержки

- Документация LiveKit: https://docs.livekit.io/
- GitHub Issues: https://github.com/livekit/livekit
- Community Forum: https://livekit.io/community

## Заключение

После выполнения всех шагов система LiveKit будет полностью настроена и готова к работе с Voice AI Agent. Регулярно проверяйте мониторинг и обновляйте конфигурации по мере необходимости.
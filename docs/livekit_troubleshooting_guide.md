# Руководство по устранению неполадок LiveKit

## Обзор

Данное руководство содержит решения для наиболее распространенных проблем при работе с системой LiveKit, включая диагностику, методы устранения неполадок и профилактические меры.

## Диагностические инструменты

### Встроенные скрипты диагностики

```bash
# Полная диагностика системы
python scripts/diagnose_livekit_connection.py

# Диагностика SIP подключения
python scripts/diagnose_sip_issue.py

# Проверка конфигурации
python scripts/validate_sip_config.py

# Мониторинг системы в реальном времени
python scripts/monitor_system.py
```

### Health Check эндпоинты

```bash
# Проверка общего состояния системы
curl http://localhost:8000/health

# Детальная проверка компонентов
curl http://localhost:8000/health/detailed

# Проверка LiveKit API
curl http://localhost:8000/health/livekit

# Проверка SIP статуса
curl http://localhost:8000/health/sip
```

## Категории проблем

### 1. Проблемы аутентификации

#### Симптомы
- Ошибки "Unauthorized" или "Invalid token"
- Невозможность создать комнаты
- Отказ в доступе к API

#### Диагностика

```python
# Проверка токена
from src.auth.livekit_auth import LiveKitAuthManager
import os

auth_manager = LiveKitAuthManager(
    os.getenv('LIVEKIT_API_KEY'),
    os.getenv('LIVEKIT_API_SECRET')
)

# Создание тестового токена
token = auth_manager.create_participant_token("test", "test-room")
print(f"Token created: {token[:50]}...")

# Проверка прав токена
import jwt
decoded = jwt.decode(token, options={"verify_signature": False})
print(f"Token grants: {decoded.get('video', {})}")
```

#### Решения

1. **Неправильные API ключи**
   ```bash
   # Проверьте переменные окружения
   echo $LIVEKIT_API_KEY
   echo $LIVEKIT_API_SECRET
   
   # Убедитесь, что ключи активны в LiveKit Cloud
   ```

2. **Истекший токен**
   ```python
   # Система автоматически обновляет токены каждые 10 минут
   # Проверьте настройки в config/livekit_auth.yaml
   token_ttl_minutes: 10
   auto_refresh: true
   ```

3. **Неправильные права доступа**
   ```python
   # Убедитесь, что токен содержит необходимые права
   grants = VideoGrants(
       room_join=True,
       room_create=True,  # Для создания комнат
       room_admin=True    # Для административных операций
   )
   ```

### 2. Проблемы SIP подключения

#### Симптомы
- Входящие звонки не поступают
- Ошибки регистрации SIP
- Проблемы с аудио качеством

#### Диагностика

```bash
# Проверка SIP конфигурации
python scripts/test_sip_configuration.py

# Мониторинг SIP трафика
python scripts/monitor_calls.py

# Проверка сетевого подключения
ping sip.novofon.ru
telnet sip.novofon.ru 5060
```

#### Решения

1. **Неправильная конфигурация транка**
   ```yaml
   # Проверьте livekit-sip-correct.yaml
   sip_trunks:
     - name: "novofon-inbound"
       numbers:
         - "${SIP_NUMBER}"  # Убедитесь, что номер правильный
       allowed_addresses:
         - "0.0.0.0/0"      # Или конкретные IP провайдера
   ```

2. **Проблемы с аутентификацией SIP**
   ```yaml
   # Для исходящих звонков
   - name: "novofon-outbound"
     auth_username: "${SIP_USERNAME}"  # Проверьте учетные данные
     auth_password: "${SIP_PASSWORD}"
   ```

3. **Проблемы с маршрутизацией**
   ```yaml
   # Убедитесь, что правила маршрутизации настроены
   routing:
     inbound_rules:
       - name: "voice-ai-dispatch"
         match:
           to: "${SIP_NUMBER}"
         action:
           type: livekit_room
   ```

### 3. Проблемы с API подключением

#### Симптомы
- Таймауты при вызове API
- Ошибки сети
- Медленные ответы

#### Диагностика

```python
# Тест подключения к API
import asyncio
from src.clients.livekit_api_client import LiveKitAPIClient

async def test_api():
    client = LiveKitAPIClient(url, api_key, api_secret)
    
    try:
        # Тест базового подключения
        rooms = await client.list_rooms()
        print(f"API working. Found {len(rooms)} rooms")
        
        # Тест создания комнаты
        room = await client.create_room("test-room")
        print(f"Room created: {room.name}")
        
        # Тест удаления комнаты
        await client.delete_room("test-room")
        print("Room deleted successfully")
        
    except Exception as e:
        print(f"API Error: {e}")

asyncio.run(test_api())
```

#### Решения

1. **Неправильный URL сервера**
   ```bash
   # Убедитесь, что URL правильный и доступный
   LIVEKIT_URL=wss://your-livekit-server.com
   
   # Проверьте доступность
   curl -I https://your-livekit-server.com
   ```

2. **Проблемы с сетью**
   ```python
   # Настройте таймауты и retry логику
   # В config/retry_policies.yaml
   api_client:
     timeout_seconds: 30
     max_retries: 3
     retry_delay_seconds: 1
   ```

3. **Проблемы с SSL/TLS**
   ```python
   # Убедитесь, что используется WSS, а не WS
   # Проверьте сертификаты
   import ssl
   import socket
   
   context = ssl.create_default_context()
   with socket.create_connection(('your-server.com', 443)) as sock:
       with context.wrap_socket(sock, server_hostname='your-server.com') as ssock:
           print(f"SSL version: {ssock.version()}")
   ```

### 4. Проблемы производительности

#### Симптомы
- Высокая латентность аудио
- Прерывания звука
- Медленная обработка

#### Диагностика

```python
# Мониторинг производительности
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor

monitor = LiveKitSystemMonitor(api_client)
performance = await monitor._check_performance()
print(f"Average API latency: {performance['avg_api_latency_ms']}ms")
print(f"Active rooms: {performance['active_rooms']}")
print(f"Error rate: {performance['error_rate']}")
```

#### Решения

1. **Оптимизация аудио настроек**
   ```yaml
   # В livekit-sip-correct.yaml
   audio_codecs:
     - name: "opus"     # Лучший кодек для качества
       priority: 1
     - name: "PCMU"     # Fallback
       priority: 2
   ```

2. **Настройка connection pooling**
   ```python
   # В config/performance.yaml
   connection_pool:
     max_connections: 100
     timeout_seconds: 30
     keep_alive: true
   ```

3. **Оптимизация буферизации**
   ```yaml
   audio:
     buffer_size: 20ms    # Минимальная латентность
     sample_rate: 48000   # Высокое качество
     channels: 1          # Моно для экономии ресурсов
   ```

### 5. Проблемы с мониторингом

#### Симптомы
- Отсутствие метрик
- Неработающие алерты
- Недоступные health checks

#### Диагностика

```bash
# Проверка мониторинга
curl http://localhost:8000/metrics
curl http://localhost:8000/health

# Проверка логов мониторинга
tail -f logs/monitoring.log

# Тест алертов
python -c "
from src.monitoring.livekit_alerting import LiveKitAlerting
alerting = LiveKitAlerting()
alerting.send_test_alert()
"
```

#### Решения

1. **Настройка endpoints**
   ```python
   # Убедитесь, что health endpoints зарегистрированы
   from src.monitoring.health_endpoints import setup_health_endpoints
   setup_health_endpoints(app)
   ```

2. **Конфигурация алертов**
   ```yaml
   # В config/monitoring.yaml
   alerts:
     enabled: true
     webhook_url: "http://localhost:8000/alerts"
     thresholds:
       error_rate: 0.05
       latency_ms: 1000
   ```

## Логи и отладка

### Уровни логирования

```python
# Настройка в .env
LOG_LEVEL=DEBUG  # Для детальной отладки
LOG_LEVEL=INFO   # Для production
LOG_LEVEL=ERROR  # Только ошибки
```

### Важные лог файлы

```bash
# Основные логи системы
tail -f logs/livekit_system.log

# Логи SIP
tail -f logs/sip_handler.log

# Логи мониторинга
tail -f logs/monitoring.log

# Логи производительности
tail -f logs/performance.log
```

### Структурированное логирование

```python
# Поиск конкретных ошибок
grep "ERROR" logs/livekit_system.log | tail -20

# Поиск проблем с аутентификацией
grep "auth" logs/livekit_system.log | grep -i error

# Поиск проблем с SIP
grep "sip" logs/livekit_system.log | grep -i "failed\|error"
```

## Профилактические меры

### Регулярные проверки

```bash
# Ежедневные проверки (добавить в cron)
0 9 * * * /path/to/scripts/daily_health_check.sh

# Еженедельные проверки
0 9 * * 1 /path/to/scripts/weekly_system_check.sh
```

### Мониторинг ключевых метрик

1. **API латентность** - должна быть < 100ms
2. **Успешность подключений** - должна быть > 99%
3. **Качество аудио** - без прерываний
4. **Использование ресурсов** - CPU < 80%, Memory < 80%

### Резервное копирование

```bash
# Резервное копирование конфигураций
./scripts/backup.sh

# Восстановление из резервной копии
./scripts/restore.sh backup_20240101_120000
```

## Контакты поддержки

### Внутренняя поддержка
- Логи системы: `logs/`
- Диагностические скрипты: `scripts/`
- Конфигурационные файлы: `config/`

### Внешняя поддержка
- LiveKit Documentation: https://docs.livekit.io/
- LiveKit GitHub: https://github.com/livekit/livekit
- Community Forum: https://livekit.io/community

### Экстренные процедуры

1. **Полный сбой системы**
   ```bash
   # Быстрое восстановление
   ./scripts/emergency_restore.sh
   ```

2. **Проблемы с SIP**
   ```bash
   # Переключение на резервную конфигурацию
   cp livekit-sip-backup.yaml livekit-sip-correct.yaml
   systemctl restart livekit-sip
   ```

3. **Проблемы с производительностью**
   ```bash
   # Временное увеличение ресурсов
   ./scripts/scale_up.sh
   ```

## Заключение

Данное руководство покрывает основные проблемы, которые могут возникнуть при работе с системой LiveKit. Регулярно обновляйте документацию на основе новых проблем и их решений.
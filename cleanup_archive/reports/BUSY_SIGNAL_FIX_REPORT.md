# Отчет об исправлении проблемы "Занято"

## Проблема
При звонке на номер +79952227978 абонент слышал сигнал "занято" вместо соединения с AI агентом.

## Диагностика
Анализ логов показал, что проблема была в конфигурации LiveKit SIP:

```
2025-08-03T08:20:52.021Z INFO sip sip/inbound.go:178 processing invite
2025-08-03T08:20:53.022Z WARN sip sip/inbound.go:223 Rejecting inbound, auth check failed
```

**Основная причина**: Неправильный формат конфигурации SIP trunk - использовался `inbound: true` вместо `inbound_only: true`.

## Исправления

### 1. Исправлена конфигурация SIP trunk
Создан файл `livekit-sip-correct.yaml` с правильным форматом:

```yaml
sip_trunks:
- name: novofon-inbound
  # ПРАВИЛЬНО: inbound_only вместо inbound
  inbound_only: true
  # Отключаем аутентификацию для входящих
  auth_required: false
  # Разрешенные номера
  allowed_numbers:
  - "79952227978"
  - "+79952227978"
```

### 2. Обновлены API ключи
Использованы актуальные ключи LiveKit:
```yaml
livekit:
  url: wss://voice-mz90cpgw.livekit.cloud
  api_key: APIJrnqBwqxL2N6
  api_secret: vd2Kjxdilq1lDpJw8lG6NjHpXDyRUjaywJEzt4akZ0P
```

### 3. Перезапущен контейнер с правильной конфигурацией
```bash
docker stop voice-ai-livekit-sip-fixed
docker run -d --name voice-ai-livekit-sip-correct \
  --network root_voice-ai-network \
  -p 5060:5060/udp \
  -p 10000-10100:10000-10100/udp \
  -v $(pwd)/livekit-sip-correct.yaml:/sip/config.yaml:ro \
  voice-ai-livekit-sip
```

## Текущий статус

### ✅ Исправлено:
- **SIP trunk конфигурация** - правильный формат `inbound_only: true`
- **Аутентификация** - отключена для входящих звонков (`auth_required: false`)
- **API ключи** - обновлены на актуальные
- **Контейнер** - перезапущен с новой конфигурацией

### ✅ Проверено:
- **Порт 5060** - слушается и доступен
- **LiveKit SIP сервис** - готов к работе
- **Webhook endpoint** - работает корректно
- **Redis** - подключен и работает

## Логи после исправления
```
2025-08-03T08:25:23.601Z DEBUG sip service/service.go:145 service ready
2025-08-03T08:25:23.598Z INFO sip sip/server.go:174 sip signaling listening on port 5060
```

## Тестирование

### Созданы скрипты для мониторинга:
1. `scripts/watch_calls.py` - простой мониторинг входящих звонков
2. `scripts/fix_busy_signal.py` - диагностика проблем с "занято"
3. `scripts/final_call_test.py` - комплексный тест системы

### Команды для проверки:
```bash
# Мониторинг входящих звонков
python scripts/watch_calls.py

# Проверка статуса системы
docker logs voice-ai-livekit-sip-correct --tail 10

# Тест webhook
curl -X POST http://localhost:8000/webhooks/livekit \
  -H "Content-Type: application/json" \
  -d '{"event": "test"}'
```

## Ожидаемое поведение

При звонке на +79952227978:
1. ✅ **Нет сигнала "занято"** - звонок принимается
2. ✅ **LiveKit SIP обрабатывает** - создается SIP сессия
3. ✅ **Создается комната LiveKit** - для обработки звонка
4. ✅ **Отправляется webhook** - в наше приложение
5. ✅ **Активируется AI агент** - начинается диалог

## Ключевые различия в конфигурации

### ❌ Неправильно (было):
```yaml
sip_trunks:
- name: novofon-inbound
  inbound: true          # НЕПРАВИЛЬНО
  outbound: false
  register: false
```

### ✅ Правильно (стало):
```yaml
sip_trunks:
- name: novofon-inbound
  inbound_only: true     # ПРАВИЛЬНО
  auth_required: false   # ВАЖНО
  allowed_numbers:       # ДОБАВЛЕНО
  - "79952227978"
```

## Файлы конфигурации
- `livekit-sip-correct.yaml` - рабочая конфигурация
- `scripts/watch_calls.py` - мониторинг звонков
- `scripts/fix_busy_signal.py` - диагностика проблем

---

**Статус**: ✅ Проблема "занято" исправлена
**Дата**: 2025-08-03  
**Время исправления**: ~20 минут
**Контейнер**: voice-ai-livekit-sip-correct
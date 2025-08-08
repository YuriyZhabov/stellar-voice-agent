# Design Document

## Overview

Данный документ описывает техническое решение для исправления проблемы подключения LiveKit SIP к LiveKit серверу и обеспечения корректной работы Voice AI Agent. Основная проблема заключается в том, что LiveKit SIP не может аутентифицироваться с LiveKit сервером, что приводит к отклонению входящих звонков.

## Architecture

### Текущая архитектура
```
Звонок → Novofon SIP → LiveKit SIP → [ОШИБКА AUTH] ❌ LiveKit Server
                                                    ↓
                                              Voice AI Agent (не получает события)
```

### Целевая архитектура
```
Звонок → Novofon SIP → LiveKit SIP → ✅ LiveKit Server → Webhook → Voice AI Agent
                                           ↓
                                    LiveKit Room ← подключается ← Voice AI Agent
```

## Components and Interfaces

### 1. LiveKit SIP Configuration Fix

**Проблема:** Неправильная конфигурация подключения к LiveKit серверу

**Решение:**
- Проверить и исправить URL LiveKit сервера
- Валидировать API ключи и секреты
- Настроить правильные параметры подключения
- Добавить retry логику для подключения

**Конфигурация:**
```yaml
livekit:
  url: "wss://voice-mz90cpgw.livekit.cloud"
  api_key: "API48Ajeeuv4tYL" 
  api_secret: "Q5eag53mO3WVhUcoRGmI5Y1wjDbCFnf7qn6pJOzakHN"
  timeout: 30s
  retry_attempts: 3
  health_check_interval: 60s
```

### 2. LiveKit API Client Integration

**Компонент:** `src/clients/livekit_client.py`

**Интерфейс:**
```python
class LiveKitClient:
    async def connect(self) -> bool
    async def create_room(self, room_name: str) -> Room
    async def join_room(self, room_name: str, participant_name: str) -> RoomParticipant
    async def publish_audio_track(self, audio_data: bytes) -> AudioTrack
    async def subscribe_to_audio(self, callback: Callable) -> None
    async def leave_room(self) -> None
    async def health_check() -> bool
```

### 3. Voice AI Agent LiveKit Integration

**Компонент:** `src/livekit_agent.py`

**Функциональность:**
- Подключение к LiveKit комнате при получении webhook
- Публикация аудио трека для воспроизведения ответов
- Подписка на входящие аудио треки от участников
- Интеграция с существующим AI pipeline (STT → LLM → TTS)

**Интерфейс:**
```python
class LiveKitVoiceAgent:
    async def handle_room_started(self, room_name: str) -> None
    async def handle_participant_joined(self, participant_id: str) -> None
    async def handle_audio_received(self, audio_data: bytes) -> None
    async def send_audio_response(self, audio_data: bytes) -> None
    async def cleanup_room(self) -> None
```

### 4. Webhook Handler Enhancement

**Компонент:** `src/webhooks.py` (расширение)

**Новые обработчики:**
```python
async def handle_livekit_room_started(self, event_data: dict) -> None
async def handle_livekit_participant_joined(self, event_data: dict) -> None  
async def handle_livekit_track_published(self, event_data: dict) -> None
async def handle_livekit_track_unpublished(self, event_data: dict) -> None
```

### 5. Diagnostic Tools

**Компонент:** `scripts/diagnose_livekit_connection.py`

**Функциональность:**
- Проверка доступности LiveKit сервера
- Валидация API ключей
- Тестирование создания комнаты
- Проверка webhook доступности
- Мониторинг подключений

## Data Models

### LiveKit Room Metadata
```python
@dataclass
class LiveKitRoomMetadata:
    call_id: str
    caller_number: str
    start_time: datetime
    webhook_url: str
    ai_agent_participant_id: Optional[str] = None
```

### Audio Processing Pipeline
```python
@dataclass
class AudioProcessingContext:
    room_name: str
    participant_id: str
    audio_track_id: str
    conversation_context: ConversationContext
    processing_state: AudioProcessingState
```

## Error Handling

### 1. LiveKit Connection Errors
- **ConnectionError**: Retry с экспоненциальным backoff
- **AuthenticationError**: Логирование и уведомление администратора
- **TimeoutError**: Увеличение timeout и retry
- **RateLimitError**: Ожидание и повторная попытка

### 2. Audio Processing Errors
- **STT Error**: Запрос повторения от пользователя
- **LLM Error**: Fallback на предустановленные ответы
- **TTS Error**: Текстовый ответ через альтернативный канал
- **Audio Streaming Error**: Переподключение к треку

### 3. Room Management Errors
- **Room Creation Failed**: Создание fallback комнаты
- **Participant Join Failed**: Retry подключения
- **Track Publishing Failed**: Альтернативные методы доставки аудио

## Testing Strategy

### 1. Unit Tests
- Тестирование LiveKit API клиента
- Тестирование webhook обработчиков
- Тестирование аудио pipeline
- Мокирование LiveKit сервера для изоляции

### 2. Integration Tests
- Тестирование полного flow от SIP звонка до AI ответа
- Тестирование webhook доставки
- Тестирование аудио качества
- Тестирование error recovery

### 3. Load Tests
- Тестирование множественных одновременных звонков
- Тестирование производительности аудио обработки
- Тестирование стабильности подключений
- Мониторинг использования ресурсов

## Security Considerations

### 1. API Key Management
- Хранение ключей в переменных окружения
- Ротация ключей без downtime
- Логирование без раскрытия секретов
- Валидация прав доступа

### 2. Audio Data Security
- Шифрование аудио потоков
- Временное хранение аудио данных
- Очистка буферов после обработки
- Соблюдение GDPR для голосовых данных

### 3. Network Security
- WSS подключения для LiveKit
- Валидация webhook подписей
- Rate limiting для API вызовов
- Мониторинг подозрительной активности

## Performance Optimization

### 1. Audio Latency
- Минимизация буферизации аудио
- Оптимизация STT/TTS pipeline
- Параллельная обработка аудио чанков
- Предзагрузка AI моделей

### 2. Connection Management
- Connection pooling для LiveKit
- Keep-alive для WebSocket соединений
- Graceful reconnection при сбоях
- Мониторинг качества соединения

### 3. Resource Usage
- Ограничение количества одновременных комнат
- Автоматическая очистка неактивных комнат
- Оптимизация использования памяти
- CPU profiling для аудио обработки

## Monitoring and Observability

### 1. Metrics
- Количество успешных/неуспешных подключений к LiveKit
- Латентность аудио обработки
- Качество распознавания речи
- Время ответа AI агента

### 2. Logging
- Структурированные логи для всех LiveKit операций
- Корреляция логов по call_id
- Логирование аудио метрик (без содержимого)
- Error tracking и alerting

### 3. Health Checks
- Периодическая проверка LiveKit подключения
- Мониторинг качества аудио треков
- Проверка доступности webhook endpoint
- Валидация AI сервисов

## Deployment Strategy

### 1. Staging Environment
- Тестирование с реальными SIP звонками
- Валидация всех компонентов интеграции
- Performance testing под нагрузкой
- Security audit

### 2. Production Rollout
- Blue-green deployment для минимизации downtime
- Постепенное переключение трафика
- Мониторинг ключевых метрик
- Rollback план при проблемах

### 3. Configuration Management
- Версионирование конфигураций
- Автоматическое применение изменений
- Валидация конфигураций перед применением
- Backup и restore процедуры
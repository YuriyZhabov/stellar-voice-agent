# API сервера LiveKit: Исчерпывающий справочник разработчика

Данное руководство представляет максимально полную документацию по всем аспектам серверных API LiveKit, включая детальные спецификации каждого метода, параметров, структур данных и практических примеров использования.

## Архитектура и базовые принципы

### Протокол Twirp: Техническая спецификация

LiveKit использует **Twirp** — RPC-фреймворк от Twitch, работающий поверх HTTP/1.1[1]. Ключевые технические характеристики:

**Структура эндпоинтов:**
- Базовый формат: `/twirp/livekit./`
- Все запросы выполняются через HTTP POST
- Content-Type: `application/json`
- Поддержка как `snake_case`, так и `camelCase` в параметрах[1]

**Четыре основных сервиса:**
- **RoomService**: `/twirp/livekit.RoomService/`
- **Egress**: `/twirp/livekit.Egress/`
- **Ingress**: `/twirp/livekit.Ingress/`
- **SIP**: `/twirp/livekit.SIP/`

**Авторизация:**
Все запросы требуют заголовок: `Authorization: Bearer `[1]

### Распределенная архитектура

API LiveKit полностью распределены — любой экземпляр сервера способен обрабатывать запросы о любой комнате, участнике или треке в кластере[1]. Это обеспечивает горизонтальную масштабируемость и отказоустойчивость.

## Система аутентификации и авторизации

### JWT токены: Полная спецификация

Токены LiveKit основаны на стандарте JWT (RFC 7519) и содержат следующие обязательные поля[2]:

**Заголовок токена:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload структура:**
```json
{
  "iss": "api_key",
  "sub": "participant_identity", 
  "iat": 1234567890,
  "exp": 1234567890,
  "video": {
    "room": "room_name",
    "roomJoin": true,
    "canPublish": true,
    "canSubscribe": true,
    "canPublishData": true,
    "canUpdateOwnMetadata": true
  }
}
```

### Полный перечень прав доступа (Video Grant)

| Поле | Тип | Описание | Примечания |
|------|-----|----------|------------|
| `roomCreate` | bool | Создание/удаление комнат | Административная функция |
| `roomList` | bool | Просмотр списка комнат | Для дашбордов и мониторинга |
| `roomJoin` | bool | Вход в комнату | Обязательно для участников |
| `roomAdmin` | bool | Модерация комнаты | Управление участниками и треками |
| `roomRecord` | bool | Использование Egress API | Для записи и экспорта |
| `ingressAdmin` | bool | Использование Ingress API | Для импорта медиа |
| `room` | string | Имя комнаты | Обязательно при `roomJoin` или `roomAdmin` |
| `canPublish` | bool | Публикация треков | По умолчанию `true` |
| `canPublishData` | bool | Отправка данных | По умолчанию `true` |
| `canPublishSources` | string[] | Разрешенные источники | `["camera", "microphone", "screen_share", "screen_share_audio"]` |
| `canSubscribe` | bool | Подписка на треки | По умолчанию `true` |
| `canUpdateOwnMetadata` | bool | Обновление собственных метаданных | По умолчанию `true` |
| `hidden` | bool | Скрытие от других участников | Для невидимых наблюдателей |
| `kind` | string | Тип участника | `"standard"`, `"ingress"`, `"egress"`, `"sip"`, `"agent"` |

### Примеры токенов для различных сценариев

**Токен только для просмотра:**[2]
```json
{
  "video": {
    "room": "myroom",
    "roomJoin": true,
    "canSubscribe": true,
    "canPublish": false,
    "canPublishData": false
  }
}
```

**Токен только для камеры:**[2]
```json
{
  "video": {
    "room": "myroom", 
    "roomJoin": true,
    "canSubscribe": true,
    "canPublish": true,
    "canPublishSources": ["camera"]
  }
}
```

### Автоматическое обновление токенов

LiveKit автоматически выдает обновленные токены подключенным клиентам с временем жизни 10 минут[2]. Токены также обновляются при изменении имени, прав или метаданных участника.

## RoomService API: Исчерпывающая документация

### Методы управления комнатами

#### CreateRoom
**Эндпоинт:** `/twirp/livekit.RoomService/CreateRoom`  
**Права:** `roomCreate`

**Полный набор параметров:**

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|--------------|--------------|----------|
| `name` | string | Да | - | Уникальное имя комнаты |
| `empty_timeout` | uint32 | Нет | 300 | Время в секундах до закрытия пустой комнаты |
| `departure_timeout` | uint32 | Нет | 20 | Время до закрытия после ухода последнего участника |
| `max_participants` | uint32 | Нет | 0 | Максимальное количество участников (0 = без ограничений) |
| `metadata` | string | Нет | "" | JSON-строка с пользовательскими данными |
| `node_id` | string | Нет | "" | Принудительное размещение на конкретном узле |
| `min_playout_delay` | uint32 | Нет | 0 | Минимальная задержка воспроизведения (мс) |
| `max_playout_delay` | uint32 | Нет | 0 | Максимальная задержка воспроизведения (мс) |
| `sync_streams` | bool | Нет | false | Синхронизация потоков |
| `egress` | RoomEgress | Нет | null | Настройки автоматической записи |

**Пример запроса:**[3]
```bash
curl -X POST https://your-host/twirp/livekit.RoomService/CreateRoom \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{
    "name": "conference-2024",
    "max_participants": 100,
    "empty_timeout": 600,
    "departure_timeout": 60,
    "metadata": "{\"meeting_id\": \"12345\", \"organizer\": \"user123\"}"
  }'
```

#### ListRooms
**Эндпоинт:** `/twirp/livekit.RoomService/ListRooms`  
**Права:** `roomList`

**Параметры:**
- `names` (string[]): Фильтр по именам комнат

**Пример ответа:**
```json
{
  "rooms": [
    {
      "sid": "RM_1234567890",
      "name": "conference-2024",
      "num_participants": 5,
      "num_publishers": 3,
      "creation_time": 1703097600,
      "metadata": "{\"meeting_id\": \"12345\"}"
    }
  ]
}
```

#### DeleteRoom
**Эндпоинт:** `/twirp/livekit.RoomService/DeleteRoom`  
**Права:** `roomCreate`

**Параметры:**
- `room` (string): Имя комнаты для удаления

### Методы управления участниками

#### ListParticipants
**Эндпоинт:** `/twirp/livekit.RoomService/ListParticipants`  
**Права:** `roomAdmin`

**Полная структура ответа ParticipantInfo:**

| Поле | Тип | Описание |
|------|-----|----------|
| `sid` | string | Серверный идентификатор |
| `identity` | string | Пользовательский идентификатор |
| `state` | enum | `JOINING`, `JOINED`, `ACTIVE`, `DISCONNECTED` |
| `tracks` | TrackInfo[] | Список опубликованных треков |
| `metadata` | string | Пользовательские метаданные |
| `joined_at` | int64 | Unix timestamp входа |
| `name` | string | Отображаемое имя |
| `version` | uint32 | Версия клиентского SDK |
| `permission` | ParticipantPermission | Права участника |
| `region` | string | Географический регион |
| `is_publisher` | bool | Публикует ли треки |

#### GetParticipant
**Эндпоинт:** `/twirp/livekit.RoomService/GetParticipant`  
**Права:** `roomAdmin`

**Параметры:**
- `room` (string): Имя комнаты
- `identity` (string): Идентификатор участника

#### RemoveParticipant
**Эндпоинт:** `/twirp/livekit.RoomService/RemoveParticipant`  
**Права:** `roomAdmin`

**Параметры:**
- `room` (string): Имя комнаты
- `identity` (string): Идентификатор участника

#### UpdateParticipant
**Эндпоинт:** `/twirp/livekit.RoomService/UpdateParticipant`  
**Права:** `roomAdmin`

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `room` | string | Имя комнаты |
| `identity` | string | Идентификатор участника |
| `metadata` | string | Новые метаданные |
| `permission` | ParticipantPermission | Новые права |
| `name` | string | Новое отображаемое имя |

### Управление треками

#### MutePublishedTrack
**Эндпоинт:** `/twirp/livekit.RoomService/MutePublishedTrack`  
**Права:** `roomAdmin`

**Параметры:**
- `room` (string): Имя комнаты
- `identity` (string): Идентификатор участника
- `track_sid` (string): SID трека
- `muted` (bool): Заглушить (true) или включить (false)

**Важное примечание:** По умолчанию LiveKit запрещает удаленное включение треков из соображений приватности. Для разрешения установите `enable_remote_unmute: true` в конфигурации сервера[1].

#### UpdateSubscriptions
**Эндпоинт:** `/twirp/livekit.RoomService/UpdateSubscriptions`  
**Права:** `roomAdmin`

**Параметры:**
- `room` (string): Имя комнаты
- `identity` (string): Идентификатор участника
- `track_sids` (string[]): Список SID треков для подписки
- `subscribe` (bool): Подписаться (true) или отписаться (false)

#### SendData
**Эндпоинт:** `/twirp/livekit.RoomService/SendData`  
**Права:** `roomAdmin`

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `room` | string | Имя комнаты |
| `data` | bytes | Бинарные данные для отправки |
| `kind` | enum | `RELIABLE` или `LOSSY` |
| `destination_sids` | string[] | SID получателей (пусто = всем) |
| `destination_identities` | string[] | Identity получателей |
| `topic` | string | Тема сообщения |

## Egress API: Полная документация экспорта

### Типы экспорта с детальными возможностями

#### 1. Room Composite Egress
Экспорт всей комнаты с использованием веб-шаблона, отрендеренного в Chrome[4].

**Поддерживаемые выходные форматы:**[5]
- MP4 файлы ✅
- OGG файлы ✅  
- RTMP(S) стримы ✅
- HLS сегменты ✅

**Метод:** `StartRoomCompositeEgress`

**Основные параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `room_name` | string | Имя комнаты для записи |
| `layout` | string | URL веб-шаблона (по умолчанию встроенный) |
| `audio_only` | bool | Только аудио запись |
| `video_only` | bool | Только видео запись |
| `custom_base_url` | string | Базовый URL для кастомных шаблонов |

#### 2. Track Composite Egress
Синхронизированный экспорт одного аудио и одного видео трека[4].

**Поддерживаемые форматы:**[5]
- MP4 файлы ✅
- OGG файлы ✅
- RTMP(S) стримы ✅

**Метод:** `StartTrackCompositeEgress`

#### 3. Track Egress
Экспорт отдельных треков без перекодирования видео[4].

**Поддерживаемые форматы:**[5]
- MP4 файлы ✅
- OGG файлы ✅  
- IVF файлы ✅
- WebSocket стримы ✅

**Метод:** `StartTrackEgress`

#### 4. Participant Egress
Новый API для экспорта видео и аудио участника вместе[4].

**Метод:** `StartParticipantEgress`

#### 5. Web Egress
Запись любой веб-страницы, не привязанной к LiveKit комнатам[4].

**Метод:** `StartWebEgress`

### Выходные конфигурации

#### Файловый вывод

**S3-совместимые хранилища:**
```json
{
  "file": {
    "filename": "recording.mp4",
    "s3": {
      "access_key": "your-key",
      "secret": "your-secret", 
      "bucket": "recordings-bucket",
      "region": "us-east-1",
      "endpoint": "custom-endpoint.com"
    }
  }
}
```

**Azure Blob Storage:**
```json
{
  "file": {
    "filename": "recording.mp4",
    "azure": {
      "account_name": "account",
      "account_key": "key",
      "container_name": "recordings"
    }
  }
}
```

**Google Cloud Storage:**
```json
{
  "file": {
    "filename": "recording.mp4", 
    "gcp": {
      "credentials": "base64-encoded-service-account",
      "bucket": "recordings-bucket"
    }
  }
}
```

#### Потоковый вывод (RTMP)

```json
{
  "stream": {
    "protocol": "RTMP",
    "urls": [
      "rtmp://live.twitch.tv/live/YOUR_STREAM_KEY",
      "rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY"
    ]
  }
}
```

### Управление активными записями

#### ListEgress
**Эндпоинт:** `/twirp/livekit.Egress/ListEgress`  
**Права:** `roomRecord`

**Параметры фильтрации:**
- `room_name` (string): Фильтр по комнате
- `egress_id` (string): Конкретный ID записи
- `active` (bool): Только активные записи

#### UpdateLayout
**Эндпоинт:** `/twirp/livekit.Egress/UpdateLayout`  
**Права:** `roomRecord`

Позволяет изменить веб-шаблон во время активной записи комнаты.

#### StopEgress
**Эндпоинт:** `/twirp/livekit.Egress/StopEgress`  
**Права:** `roomRecord`

**Параметры:**
- `egress_id` (string): ID записи для остановки

## Ingress API: Полная документация импорта

### Поддерживаемые типы входных данных

#### 1. RTMP/RTMPS (input_type: 0)
Прием потоков от OBS, XSplit и других стриминговых программ[6].

#### 2. WHIP (input_type: 1) 
WebRTC-HTTP Ingestion Protocol для браузерных источников[6].

#### 3. URL Input (input_type: 2)
Импорт файлов и потоков по HTTP(S) или SRT URL[6].

**Поддерживаемые форматы:**
- HLS потоки
- MP4, MOV файлы
- MKV/WEBM контейнеры
- OGG, MP3, M4A аудио
- SRT потоки

### Методы Ingress API

#### CreateIngress
**Эндпоинт:** `/twirp/livekit.Ingress/CreateIngress`  
**Права:** `ingressAdmin`

**RTMP/WHIP параметры:**[6]
```json
{
  "input_type": 0,
  "name": "OBS Stream",
  "room_name": "streaming-room",
  "participant_identity": "streamer-1", 
  "participant_name": "Main Streamer",
  "enable_transcoding": true
}
```

**URL Input параметры:**[6]
```json
{
  "input_type": 2,
  "name": "HLS Stream Import",
  "room_name": "imported-content",
  "participant_identity": "hls-source",
  "participant_name": "External Stream",
  "url": "https://example.com/stream.m3u8"
}
```

**Дополнительные параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `audio` | IngressAudioOptions | Настройки аудио |
| `video` | IngressVideoOptions | Настройки видео |
| `bypass_transcoding` | bool | Отключение перекодирования (только WHIP) |

#### UpdateIngress  
**Эндпоинт:** `/twirp/livekit.Ingress/UpdateIngress`  
**Права:** `ingressAdmin`

Позволяет изменить конфигурацию для повторного использования того же URL для публикации в разные комнаты[1].

#### ListIngress
**Эндпоинт:** `/twirp/livekit.Ingress/ListIngress`  
**Права:** `ingressAdmin`

**Параметры фильтрации:**
- `room_name` (string): Фильтр по комнате
- `ingress_id` (string): Конкретный ID ingress

#### DeleteIngress
**Эндпоинт:** `/twirp/livekit.Ingress/DeleteIngress`  
**Права:** `ingressAdmin`

### Производительность и ресурсы

Один Ingress worker может обрабатывать несколько заданий одновременно, в зависимости от их ресурсных требований. Например, WHIP сессия с отключенным перекодированием потребляет значительно меньше ресурсов[7].

## SIP API: Исчерпывающая документация телефонии

### Архитектурные концепции

#### SIP Участники
Каждый звонящий, принимающий и AI агент является участником LiveKit с дополнительными SIP-атрибутами[8]:

**Дополнительные поля SIP участника:**
- `sip_call_id`: Уникальный идентификатор SIP вызова
- `phone_number`: Номер телефона участника  
- `dtmf_digits`: Последовательность нажатых цифр
- `call_direction`: `INBOUND` или `OUTBOUND`

#### Транки (Trunks)
Соединяют SIP-провайдера с LiveKit[8]:

**Входящие транки:**
- Обрабатывают входящие вызовы
- Могут быть ограничены по IP-адресам
- Могут быть ограничены по номерам

**Исходящие транки:**  
- Используются для исходящих вызовов
- Поддерживают аутентификацию
- Могут быть привязаны к региону

#### Правила маршрутизации (Dispatch Rules)
Контролируют направление входящих вызовов в комнаты LiveKit[8].

### Методы SIP API

#### CreateSIPInboundTrunk
**Эндпоинт:** `/twirp/livekit.SIP/CreateSIPInboundTrunk`

**Полные параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `trunk` | SIPInboundTrunkInfo | Конфигурация транка |
| `trunk.name` | string | Имя транка |
| `trunk.numbers` | string[] | Список телефонных номеров |
| `trunk.allowed_addresses` | string[] | Разрешенные IP-адреса |
| `trunk.allowed_numbers` | string[] | Разрешенные номера звонящих |
| `trunk.auth_username` | string | Имя пользователя для аутентификации |
| `trunk.auth_password` | string | Пароль для аутентификации |

**Пример создания:[9]**
```json
{
  "trunk": {
    "name": "Telnyx Inbound",
    "numbers": ["+15551234567"],
    "allowed_addresses": ["192.168.1.0/24"]
  }
}
```

#### CreateSIPOutboundTrunk
**Эндпоинт:** `/twirp/livekit.SIP/CreateSIPOutboundTrunk`

**Параметры:**
- `trunk`: Конфигурация исходящего транка с аутентификацией

#### CreateSIPDispatchRule
**Эндпоинт:** `/twirp/livekit.SIP/CreateSIPDispatchRule`

**Параметры:[9]**
```json
{
  "name": "Main Dispatch Rule",
  "trunk_ids": ["trunk-id-123"],
  "rule": {
    "dispatchRuleDirect": {
      "roomName": "sip-conference",
      "pin": "1234"
    }
  }
}
```

#### CreateSIPParticipant
**Эндпоинт:** `/twirp/livekit.SIP/CreateSIPParticipant`

Инициирует исходящий SIP-вызов[8].

**Параметры:**
- `sip_trunk_id`: ID исходящего транка
- `sip_call_to`: Номер для вызова
- `room_name`: Комната для подключения
- `participant_identity`: Идентификатор участника

## SDK и практические примеры

### Серверные SDK: Полная экосистема

#### Python SDK
**Пакеты:**
- `livekit-api`: Управление комнатами и токены[10]
- `livekit`: Подключение как участник в реальном времени
- `livekit-agents`: Создание AI агентов

**Пример инициализации:**[10]
```python
from livekit import api

lkapi = api.LiveKitAPI(
    url="https://your-livekit-host",
    api_key="your-api-key", 
    api_secret="your-api-secret"
)

# Список комнат
rooms = await lkapi.room.list_rooms(
    api.proto_room.ListRoomsRequest(names=['test-room'])
)
```

#### Go SDK
**Пакет:** `github.com/livekit/server-sdk-go/v2`[3]

**Пример использования:**[3]
```go
import (
    lksdk "github.com/livekit/server-sdk-go/v2"
    livekit "github.com/livekit/protocol/livekit"
)

roomClient := lksdk.NewRoomServiceClient(hostURL, apiKey, apiSecret)

// Создание комнаты
room, err := roomClient.CreateRoom(context.Background(), &livekit.CreateRoomRequest{
    Name: "my-room",
    MaxParticipants: 50,
})
```

#### Ruby SDK
**Пакет:** `livekit`[11]

**Пример создания токена:**[11]
```ruby
require 'livekit'

token = LiveKit::AccessToken.new(api_key: 'yourkey', api_secret: 'yoursecret')
token.identity = 'participant-identity'
token.name = 'participant-name'
token.video_grant = LiveKit::VideoGrant.new(roomJoin: true, room: 'room-name')
puts token.to_jwt
```

#### Node.js SDK
**Пакеты:**
- `livekit-server-sdk`: Основной серверный SDK[12]
- `@livekit/agents`: AI агенты (beta)

### Коды ошибок и обработка

#### Стандартные HTTP коды
- `200`: Успешный запрос
- `400`: Неверные параметры запроса
- `401`: Неверный или отсутствующий токен авторизации
- `403`: Недостаточно прав для выполнения операции
- `404`: Комната или участник не найдены
- `409`: Конфликт (например, комната уже существует)
- `500`: Внутренняя ошибка сервера

#### Twirp-специфичные ошибки
```json
{
  "code": "invalid_argument",
  "msg": "room name is required",
  "meta": {
    "argument": "name"
  }
}
```

### Мониторинг и отладка

#### Логирование
LiveKit поддерживает структурированное логирование в форматах JSON и текстовом. Уровни логирования: `debug`, `info`, `warn`, `error`.

#### Метрики
Сервер экспортирует метрики в формате Prometheus для мониторинга производительности и состояния системы.

#### Веб-хуки
LiveKit может отправлять веб-хуки о событиях комнат и участников для интеграции с внешними системами.

## Расширенные возможности

### Форвардинг участников
Метод `ForwardParticipant` позволяет перенаправлять участников и их треки из одной комнаты в другую. Эта функция доступна только в LiveKit Cloud/Private Cloud[13].

### Региональное развертывание
LiveKit поддерживает географическое распределение для снижения задержек и соответствия местным требованиям.

### Интеграция с AI агентами
Agents Framework позволяет добавлять программы Python или Node.js в комнаты как полноценных участников реального времени с возможностями обработки потокового ввода и генерации AI-ответов.

Данное руководство охватывает все аспекты API сервера LiveKit с максимальной детализацией для исключения любых разночтений в использовании платформы.
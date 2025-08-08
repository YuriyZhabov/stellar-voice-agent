# Дизайн правильной настройки системы LiveKit

## Обзор

Данный документ описывает техническое решение для правильной настройки системы LiveKit на основе исчерпывающего справочника API. Цель - устранить текущие проблемы с подключением и создать надежную, масштабируемую систему согласно официальной спецификации.

## Архитектура системы

### Текущие проблемы
```
❌ Неправильная аутентификация JWT
❌ Некорректные эндпоинты API  
❌ Неправильная конфигурация SIP
❌ Отсутствие proper error handling
❌ Неоптимальные настройки производительности
```

### Целевая архитектура
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SIP Provider  │───▶│   LiveKit SIP    │───▶│  LiveKit Server │
│   (Novofon)     │    │   (правильно     │    │  (с правильной  │
│                 │    │   настроенный)   │    │   аутентиф.)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Voice AI Agent │◀───│    Webhooks      │◀───│   LiveKit Room  │
│  (интегрирован  │    │  (правильные     │    │  (с метаданными │
│   с LiveKit)    │    │   обработчики)   │    │   и правами)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Компоненты и интерфейсы

### 1. Правильная конфигурация аутентификации

**Компонент:** `src/config/livekit_auth.py`

```python
from livekit.api import AccessToken, VideoGrants
from datetime import datetime, timedelta, UTC
import jwt

class LiveKitAuthManager:
    """Управление аутентификацией LiveKit согласно спецификации."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def create_participant_token(
        self, 
        identity: str, 
        room_name: str,
        grants: VideoGrants = None
    ) -> str:
        """Создание JWT токена участника согласно спецификации."""
        token = AccessToken(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # Обязательные поля согласно спецификации
        token.with_identity(identity)
        token.with_name(identity)  # Отображаемое имя
        
        # Права доступа согласно спецификации
        if grants is None:
            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=True
            )
        
        token.with_grants(grants)
        
        # Время жизни токена - 10 минут (автообновление)
        token.with_ttl(timedelta(minutes=10))
        
        return token.to_jwt()
    
    def create_admin_token(self) -> str:
        """Создание административного токена."""
        token = AccessToken(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # Административные права
        grants = VideoGrants(
            room_create=True,
            room_list=True,
            room_admin=True,
            room_record=True,
            ingress_admin=True
        )
        
        token.with_grants(grants)
        token.with_ttl(timedelta(hours=1))
        
        return token.to_jwt()
```

### 2. Правильная конфигурация API клиента

**Компонент:** `src/clients/livekit_api_client.py`

```python
from livekit import api
from livekit.api import (
    CreateRoomRequest, ListRoomsRequest, DeleteRoomRequest,
    ListParticipantsRequest, RemoveParticipantRequest,
    UpdateParticipantRequest, MutePublishedTrackRequest
)
import aiohttp
import json
from typing import Dict, Any, Optional, List

class LiveKitAPIClient:
    """Клиент для работы с LiveKit API согласно Twirp спецификации."""
    
    def __init__(self, url: str, api_key: str, api_secret: str):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = api.LiveKitAPI(
            url=url,
            api_key=api_key,
            api_secret=api_secret
        )
        self.auth_manager = LiveKitAuthManager(api_key, api_secret)
    
    # RoomService API методы согласно спецификации
    
    async def create_room(
        self,
        name: str,
        empty_timeout: int = 300,
        departure_timeout: int = 20,
        max_participants: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> api.Room:
        """Создание комнаты через /twirp/livekit.RoomService/CreateRoom"""
        
        request = CreateRoomRequest(
            name=name,
            empty_timeout=empty_timeout,
            departure_timeout=departure_timeout,
            max_participants=max_participants,
            metadata=json.dumps(metadata) if metadata else ""
        )
        
        return await self.client.room.create_room(request)
    
    async def list_rooms(self, names: Optional[List[str]] = None) -> List[api.Room]:
        """Список комнат через /twirp/livekit.RoomService/ListRooms"""
        request = ListRoomsRequest(names=names or [])
        response = await self.client.room.list_rooms(request)
        return list(response.rooms)
    
    async def delete_room(self, room_name: str) -> None:
        """Удаление комнаты через /twirp/livekit.RoomService/DeleteRoom"""
        request = DeleteRoomRequest(room=room_name)
        await self.client.room.delete_room(request)
    
    async def list_participants(self, room_name: str) -> List[api.ParticipantInfo]:
        """Список участников через /twirp/livekit.RoomService/ListParticipants"""
        request = ListParticipantsRequest(room=room_name)
        response = await self.client.room.list_participants(request)
        return list(response.participants)
    
    async def remove_participant(self, room_name: str, identity: str) -> None:
        """Удаление участника через /twirp/livekit.RoomService/RemoveParticipant"""
        request = RemoveParticipantRequest(room=room_name, identity=identity)
        await self.client.room.remove_participant(request)
    
    async def mute_track(
        self, 
        room_name: str, 
        identity: str, 
        track_sid: str, 
        muted: bool
    ) -> None:
        """Управление треком через /twirp/livekit.RoomService/MutePublishedTrack"""
        request = MutePublishedTrackRequest(
            room=room_name,
            identity=identity,
            track_sid=track_sid,
            muted=muted
        )
        await self.client.room.mute_published_track(request)
```

### 3. Правильная конфигурация SIP

**Компонент:** `config/livekit-sip-correct.yaml`

```yaml
# Правильная конфигурация SIP согласно спецификации
livekit:
  url: ${LIVEKIT_URL}
  api_key: ${LIVEKIT_API_KEY}
  api_secret: ${LIVEKIT_API_SECRET}
  # Настройки подключения согласно спецификации
  connection_timeout: 30s
  keep_alive: 25s
  auto_reconnect: true
  max_reconnect_attempts: 10
  reconnect_delay: 1s

redis:
  address: ${REDIS_URL:-redis://localhost:6379}
  timeout: 5s

# SIP транки согласно SIP API спецификации
sip_trunks:
  - name: "novofon-inbound"
    # Входящий транк для приема звонков
    inbound_only: true
    # Настройки согласно CreateSIPInboundTrunk
    numbers:
      - "${SIP_NUMBER}"
      - "+${SIP_NUMBER}"
    allowed_addresses:
      - "0.0.0.0/0"  # Разрешить все IP (настроить по необходимости)
    auth_required: false  # Для входящих звонков от провайдера
    
  - name: "novofon-outbound"
    # Исходящий транк для совершения звонков
    outbound_only: true
    host: "${SIP_SERVER}"
    port: ${SIP_PORT:-5060}
    transport: ${SIP_TRANSPORT:-UDP}
    # Аутентификация согласно CreateSIPOutboundTrunk
    auth_username: "${SIP_USERNAME}"
    auth_password: "${SIP_PASSWORD}"

# Правила маршрутизации согласно CreateSIPDispatchRule
routing:
  inbound_rules:
    - name: "voice-ai-dispatch"
      # Маршрутизация входящих звонков
      match:
        to: "${SIP_NUMBER}"
      action:
        type: livekit_room
        room_name_template: "voice-ai-call-{call_id}"
        participant_name: "caller"
        participant_identity: "{caller_number}"
        # Метаданные комнаты согласно спецификации
        room_metadata:
          call_type: "inbound"
          sip_number: "${SIP_NUMBER}"
          created_at: "{timestamp}"

# Webhook конфигурация согласно спецификации
webhooks:
  enabled: true
  url: "http://${DOMAIN}:${PORT}/webhooks/livekit"
  secret: "${SECRET_KEY}"
  # Retry конфигурация для webhooks
  timeout: 5s
  max_retries: 3
  retry_delay: 1s

# Аудио кодеки согласно спецификации
audio_codecs:
  - name: "PCMU"
    priority: 1
  - name: "PCMA"
    priority: 2
  - name: "G722"
    priority: 3
  - name: "opus"
    priority: 4

# Логирование согласно рекомендациям
logging:
  level: ${LOG_LEVEL:-INFO}
  structured: true
  format: json

# Health check конфигурация
health_check:
  enabled: true
  interval: 60s
  timeout: 10s
```

### 4. Конфигурация Egress для записи

**Компонент:** `src/services/livekit_egress.py`

```python
from livekit.api import EgressClient, StartRoomCompositeEgressRequest
from typing import Dict, Any, Optional, List

class LiveKitEgressService:
    """Сервис для работы с Egress API согласно спецификации."""
    
    def __init__(self, client: LiveKitAPIClient):
        self.client = client
        self.egress_client = EgressClient(
            url=client.url,
            api_key=client.api_key,
            api_secret=client.api_secret
        )
    
    async def start_room_recording(
        self,
        room_name: str,
        output_config: Dict[str, Any]
    ) -> str:
        """Запуск записи комнаты согласно Room Composite Egress спецификации."""
        
        # Поддерживаемые форматы: MP4, OGG, RTMP, HLS
        request = StartRoomCompositeEgressRequest(
            room_name=room_name,
            layout="",  # Использовать встроенный шаблон
            audio_only=False,
            video_only=False,
            **output_config
        )
        
        response = await self.egress_client.start_room_composite_egress(request)
        return response.egress_id
    
    def create_s3_output_config(
        self,
        filename: str,
        bucket: str,
        access_key: str,
        secret: str,
        region: str = "us-east-1"
    ) -> Dict[str, Any]:
        """Создание конфигурации S3 вывода согласно спецификации."""
        return {
            "file": {
                "filename": filename,
                "s3": {
                    "access_key": access_key,
                    "secret": secret,
                    "bucket": bucket,
                    "region": region
                }
            }
        }
    
    def create_rtmp_output_config(self, urls: List[str]) -> Dict[str, Any]:
        """Создание конфигурации RTMP вывода согласно спецификации."""
        return {
            "stream": {
                "protocol": "RTMP",
                "urls": urls
            }
        }
```

### 5. Конфигурация Ingress для импорта

**Компонент:** `src/services/livekit_ingress.py`

```python
from livekit.api import IngressClient, CreateIngressRequest
from typing import Dict, Any, Optional

class LiveKitIngressService:
    """Сервис для работы с Ingress API согласно спецификации."""
    
    def __init__(self, client: LiveKitAPIClient):
        self.client = client
        self.ingress_client = IngressClient(
            url=client.url,
            api_key=client.api_key,
            api_secret=client.api_secret
        )
    
    async def create_rtmp_ingress(
        self,
        name: str,
        room_name: str,
        participant_identity: str,
        participant_name: str
    ) -> Dict[str, Any]:
        """Создание RTMP Ingress согласно спецификации."""
        
        request = CreateIngressRequest(
            input_type=0,  # RTMP/RTMPS
            name=name,
            room_name=room_name,
            participant_identity=participant_identity,
            participant_name=participant_name,
            enable_transcoding=True
        )
        
        response = await self.ingress_client.create_ingress(request)
        return {
            "ingress_id": response.ingress_id,
            "url": response.url,
            "stream_key": response.stream_key
        }
    
    async def create_whip_ingress(
        self,
        name: str,
        room_name: str,
        participant_identity: str,
        bypass_transcoding: bool = False
    ) -> Dict[str, Any]:
        """Создание WHIP Ingress согласно спецификации."""
        
        request = CreateIngressRequest(
            input_type=1,  # WHIP
            name=name,
            room_name=room_name,
            participant_identity=participant_identity,
            bypass_transcoding=bypass_transcoding
        )
        
        response = await self.ingress_client.create_ingress(request)
        return {
            "ingress_id": response.ingress_id,
            "url": response.url
        }
```

### 6. Система мониторинга и диагностики

**Компонент:** `src/monitoring/livekit_monitor.py`

```python
import asyncio
import time
from datetime import datetime, UTC
from typing import Dict, Any, List
import logging

class LiveKitSystemMonitor:
    """Мониторинг системы LiveKit согласно спецификации."""
    
    def __init__(self, client: LiveKitAPIClient):
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.metrics = {
            "connections": {"successful": 0, "failed": 0},
            "rooms": {"created": 0, "deleted": 0, "active": 0},
            "participants": {"joined": 0, "left": 0, "active": 0},
            "api_latency": [],
            "errors": []
        }
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Запуск health checks согласно спецификации."""
        
        checks = {
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {}
        }
        
        # Проверка RoomService API
        checks["checks"]["room_service"] = await self._check_room_service()
        
        # Проверка SIP API (если доступен)
        checks["checks"]["sip_service"] = await self._check_sip_service()
        
        # Проверка Egress API
        checks["checks"]["egress_service"] = await self._check_egress_service()
        
        # Проверка Ingress API
        checks["checks"]["ingress_service"] = await self._check_ingress_service()
        
        # Проверка производительности
        checks["checks"]["performance"] = await self._check_performance()
        
        return checks
    
    async def _check_room_service(self) -> Dict[str, Any]:
        """Проверка RoomService API."""
        try:
            start_time = time.time()
            rooms = await self.client.list_rooms()
            latency = time.time() - start_time
            
            return {
                "status": "healthy",
                "latency_ms": round(latency * 1000, 2),
                "rooms_count": len(rooms)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_performance(self) -> Dict[str, Any]:
        """Проверка производительности системы."""
        return {
            "avg_api_latency_ms": sum(self.metrics["api_latency"]) / len(self.metrics["api_latency"]) if self.metrics["api_latency"] else 0,
            "active_rooms": self.metrics["rooms"]["active"],
            "active_participants": self.metrics["participants"]["active"],
            "error_rate": len(self.metrics["errors"]) / max(1, sum(self.metrics["connections"].values()))
        }
```

## Безопасность и производительность

### Безопасность
1. **API ключи**: Хранение в переменных окружения, маскирование в логах
2. **JWT токены**: Автоматическое обновление каждые 10 минут
3. **WSS соединения**: Обязательное использование для всех подключений
4. **Валидация прав**: Проверка всех разрешений перед операциями

### Производительность
1. **Connection pooling**: Переиспользование соединений
2. **Retry логика**: Экспоненциальный backoff для повторных попыток
3. **Graceful reconnection**: Автоматическое переподключение при сбоях
4. **Мониторинг латентности**: Отслеживание времени ответа API

## Интеграция с существующей системой

### Webhook обработчики
```python
# Расширение существующих webhook обработчиков
async def handle_livekit_room_started(self, event_data: dict):
    """Обработка события создания комнаты."""
    room_name = event_data["room"]["name"]
    
    # Интеграция с Voice AI Agent
    await self.voice_agent.join_room(room_name)

async def handle_livekit_participant_joined(self, event_data: dict):
    """Обработка подключения участника."""
    participant_id = event_data["participant"]["identity"]
    
    # Запуск AI обработки
    await self.voice_agent.start_processing(participant_id)
```

### Миграция конфигурации
1. Обновление существующих конфигурационных файлов
2. Миграция API вызовов на новые эндпоинты
3. Обновление системы мониторинга
4. Тестирование интеграции с существующими компонентами

Данный дизайн обеспечивает полное соответствие спецификации LiveKit API и решает все выявленные проблемы с подключением и конфигурацией системы.
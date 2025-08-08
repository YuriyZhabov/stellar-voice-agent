# LiveKit Egress Service Documentation

## Обзор

LiveKit Egress Service предоставляет полную функциональность для записи и экспорта контента из LiveKit комнат согласно официальной спецификации API. Сервис поддерживает все типы экспорта, включая файловые записи, потоковую передачу и сегментированные выходы.

## Основные возможности

### Поддерживаемые типы Egress

1. **Room Composite Egress** - Запись всей комнаты
2. **Track Composite Egress** - Синхронизированная запись аудио/видео треков
3. **Track Egress** - Запись отдельных треков

### Поддерживаемые форматы вывода

- **Файловые форматы**: MP4, OGG, WebM, TS
- **Потоковые протоколы**: RTMP, SRT
- **Сегментированные форматы**: HLS

### Поддерживаемые облачные хранилища

- **Amazon S3** (и S3-совместимые)
- **Google Cloud Storage**
- **Azure Blob Storage**
- **Alibaba Cloud OSS**

## Быстрый старт

### Инициализация сервиса

```python
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import LiveKitEgressService

# Создание клиента
livekit_client = LiveKitAPIClient(
    url="wss://your-livekit-server.com",
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Создание Egress сервиса
egress_service = LiveKitEgressService(livekit_client)
```

### Простая запись комнаты в S3

```python
from src.services.livekit_egress import S3Config, OutputFormat, start_room_recording_to_s3

# Конфигурация S3
s3_config = S3Config(
    access_key="your_access_key",
    secret="your_secret",
    region="us-east-1",
    bucket="recordings-bucket"
)

# Запуск записи
egress_id = await start_room_recording_to_s3(
    egress_service=egress_service,
    room_name="my-room",
    filename="recording.mp4",
    s3_config=s3_config,
    output_format=OutputFormat.MP4
)
```

## Детальное руководство

### Room Composite Egress

Room Composite Egress записывает всю комнату как единое видео, включая всех участников и их контент.

#### Базовая запись комнаты

```python
# Создание файлового вывода
file_output = egress_service.create_s3_file_output(
    filename="room_recording.mp4",
    s3_config=s3_config,
    output_format=OutputFormat.MP4
)

# Запуск записи
egress_id = await egress_service.start_room_composite_egress(
    room_name="conference-room",
    file_outputs=[file_output]
)
```

#### Запись только аудио

```python
egress_id = await egress_service.start_room_composite_egress(
    room_name="audio-conference",
    audio_only=True,
    file_outputs=[file_output]
)
```

#### Запись с пользовательским макетом

```python
egress_id = await egress_service.start_room_composite_egress(
    room_name="presentation-room",
    layout="https://your-domain.com/layouts/presentation.html",
    file_outputs=[file_output]
)
```

### Track Composite Egress

Track Composite Egress записывает конкретные аудио и видео треки с синхронизацией.

```python
# Создание нескольких выводов
mp4_output = egress_service.create_s3_file_output(
    filename="tracks.mp4",
    s3_config=s3_config,
    output_format=OutputFormat.MP4
)

webm_output = egress_service.create_gcp_file_output(
    filename="tracks.webm",
    gcp_config=gcp_config,
    output_format=OutputFormat.WEBM
)

# Запуск записи треков
egress_id = await egress_service.start_track_composite_egress(
    room_name="interview-room",
    audio_track_id="interviewer_audio",
    video_track_id="interviewer_video",
    file_outputs=[mp4_output, webm_output]
)
```

### Потоковая передача RTMP

```python
from src.services.livekit_egress import start_room_streaming_to_rtmp

# RTMP эндпоинты
rtmp_urls = [
    "rtmp://live.twitch.tv/live/your_stream_key",
    "rtmp://a.rtmp.youtube.com/live2/your_youtube_key"
]

# Запуск стриминга
egress_id = await start_room_streaming_to_rtmp(
    egress_service=egress_service,
    room_name="live-event",
    rtmp_urls=rtmp_urls,
    layout="https://your-domain.com/layouts/live.html"
)
```

### HLS стриминг

```python
from src.services.livekit_egress import start_room_hls_streaming

# Запуск HLS стриминга
egress_id = await start_room_hls_streaming(
    egress_service=egress_service,
    room_name="live-stream",
    filename_prefix="hls/stream/segment",
    playlist_name="hls/stream/playlist.m3u8",
    s3_config=s3_config,
    segment_duration=6
)
```

## Конфигурации облачных хранилищ

### Amazon S3

```python
from src.services.livekit_egress import S3Config

s3_config = S3Config(
    access_key="AKIA...",
    secret="your_secret_key",
    region="us-east-1",
    bucket="your-bucket",
    endpoint="https://s3.amazonaws.com",  # Опционально
    force_path_style=False,  # Для S3-совместимых хранилищ
    metadata={
        "project": "voice-ai-agent",
        "environment": "production"
    },
    tagging="project=voice-ai&env=prod"  # Опционально
)
```

### Google Cloud Storage

```python
from src.services.livekit_egress import GCPConfig

gcp_config = GCPConfig(
    credentials='{"type": "service_account", "project_id": "your-project", ...}',
    bucket="your-gcp-bucket"
)
```

### Azure Blob Storage

```python
from src.services.livekit_egress import AzureConfig

azure_config = AzureConfig(
    account_name="yourstorageaccount",
    account_key="your_account_key",
    container_name="recordings"
)
```

### Alibaba Cloud OSS

```python
from src.services.livekit_egress import AliOSSConfig

alioss_config = AliOSSConfig(
    access_key="your_access_key",
    secret="your_secret",
    region="oss-cn-hangzhou",
    bucket="your-bucket",
    endpoint="https://oss-cn-hangzhou.aliyuncs.com"
)
```

## Пользовательские настройки кодирования

```python
# Создание пользовательских настроек кодирования
encoding_options = egress_service.create_encoding_options(
    width=1920,
    height=1080,
    depth=24,
    framerate=30,
    audio_codec="opus",
    audio_bitrate=128,
    audio_frequency=48000,
    video_codec="h264_baseline",
    video_bitrate=4500,
    key_frame_interval=4.0
)

# Использование в записи
egress_id = await egress_service.start_room_composite_egress(
    room_name="high-quality-room",
    file_outputs=[file_output],
    options=encoding_options
)
```

## Управление активными Egress

### Остановка записи

```python
await egress_service.stop_egress(egress_id)
```

### Список активных записей

```python
# Все активные записи
active_egress = await egress_service.list_egress(active=True)

# Записи для конкретной комнаты
room_egress = await egress_service.list_egress(room_name="specific-room")

# Конкретная запись
specific_egress = await egress_service.list_egress(egress_id="egress_123")
```

### Обновление макета во время записи

```python
await egress_service.update_layout(
    egress_id="egress_123",
    layout="https://your-domain.com/layouts/new_layout.html"
)
```

### Динамическое управление потоками

```python
# Добавление новых RTMP потоков
await egress_service.update_stream(
    egress_id="stream_egress_123",
    add_output_urls=["rtmp://new-stream.example.com/live/key"]
)

# Удаление потоков
await egress_service.update_stream(
    egress_id="stream_egress_123",
    remove_output_urls=["rtmp://old-stream.example.com/live/key"]
)
```

## Мониторинг и диагностика

### Получение статуса записи

```python
status = await egress_service.get_egress_status(egress_id)
if status:
    print(f"Status: {status.status}")
    print(f"Started: {status.started_at}")
    print(f"Room: {status.room_name}")
```

### Статистика сервиса

```python
# Количество активных записей
active_count = await egress_service.get_active_egress_count()

# Очистка завершенных записей
cleaned_count = await egress_service.cleanup_completed_egress()

# Общий статус здоровья
health_status = egress_service.get_health_status()
print(f"Service status: {health_status['status']}")
print(f"Active egress: {health_status['active_egress']}")
print(f"Supported formats: {health_status['supported_formats']}")
```

## Обработка ошибок

```python
try:
    egress_id = await egress_service.start_room_composite_egress(
        room_name="test-room",
        file_outputs=[file_output]
    )
    print(f"Started egress: {egress_id}")
    
except Exception as e:
    logger.error(f"Failed to start egress: {e}")
    
    # Проверка статуса сервиса
    health = egress_service.get_health_status()
    if health['status'] != 'healthy':
        logger.error("Egress service is not healthy")
```

## Лучшие практики

### 1. Управление ресурсами

```python
# Регулярная очистка завершенных записей
async def cleanup_task():
    while True:
        try:
            cleaned = await egress_service.cleanup_completed_egress()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} completed egress instances")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
        
        await asyncio.sleep(300)  # Каждые 5 минут

# Запуск задачи очистки
asyncio.create_task(cleanup_task())
```

### 2. Мониторинг записей

```python
async def monitor_egress(egress_id: str):
    """Мониторинг статуса записи до завершения."""
    while True:
        status = await egress_service.get_egress_status(egress_id)
        if not status:
            break
            
        logger.info(f"Egress {egress_id} status: {status.status}")
        
        if status.status in ["EGRESS_COMPLETE", "EGRESS_FAILED", "EGRESS_ABORTED"]:
            if status.status == "EGRESS_COMPLETE":
                logger.info(f"Recording completed: {status.file_results}")
            else:
                logger.error(f"Recording failed: {status.error}")
            break
        
        await asyncio.sleep(10)
```

### 3. Обработка сбоев

```python
async def robust_start_recording(room_name: str, max_retries: int = 3):
    """Надежный запуск записи с повторными попытками."""
    for attempt in range(max_retries):
        try:
            egress_id = await egress_service.start_room_composite_egress(
                room_name=room_name,
                file_outputs=[file_output]
            )
            logger.info(f"Recording started successfully: {egress_id}")
            return egress_id
            
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                logger.error("All recording attempts failed")
                raise
```

### 4. Конфигурация для разных сценариев

```python
# Конфигурация для высокого качества
HIGH_QUALITY_OPTIONS = egress_service.create_encoding_options(
    width=1920,
    height=1080,
    framerate=60,
    video_bitrate=8000,
    audio_bitrate=320
)

# Конфигурация для экономии трафика
LOW_BANDWIDTH_OPTIONS = egress_service.create_encoding_options(
    width=1280,
    height=720,
    framerate=30,
    video_bitrate=2000,
    audio_bitrate=128
)

# Конфигурация только для аудио
AUDIO_ONLY_OPTIONS = egress_service.create_encoding_options(
    width=0,
    height=0,
    video_bitrate=0,
    audio_bitrate=128
)
```

## Интеграция с Voice AI Agent

```python
from src.livekit_integration import get_livekit_integration

async def start_call_recording(call_context):
    """Запуск записи звонка Voice AI Agent."""
    livekit_integration = await get_livekit_integration()
    egress_service = LiveKitEgressService(livekit_integration.livekit_client)
    
    # Конфигурация записи для звонков
    s3_config = S3Config(
        access_key=settings.s3_access_key,
        secret=settings.s3_secret,
        region=settings.s3_region,
        bucket=settings.recordings_bucket,
        metadata={
            "call_id": call_context.call_id,
            "caller_number": call_context.caller_number,
            "start_time": call_context.start_time.isoformat()
        }
    )
    
    # Имя файла с метаданными звонка
    filename = f"calls/{call_context.call_id}_{call_context.start_time.strftime('%Y%m%d_%H%M%S')}.mp4"
    
    # Запуск записи
    egress_id = await start_room_recording_to_s3(
        egress_service=egress_service,
        room_name=call_context.livekit_room,
        filename=filename,
        s3_config=s3_config,
        output_format=OutputFormat.MP4,
        audio_only=True  # Для голосовых звонков
    )
    
    # Сохранение egress_id в контексте звонка
    call_context.metadata["egress_id"] = egress_id
    
    return egress_id
```

## Заключение

LiveKit Egress Service предоставляет мощные возможности для записи и экспорта контента из LiveKit комнат. Сервис полностью соответствует официальной спецификации API и поддерживает все современные форматы и облачные хранилища.

Для получения дополнительной информации обратитесь к:
- [Примерам использования](../examples/livekit_egress_example.py)
- [Тестам](../tests/test_livekit_egress.py)
- [Официальной документации LiveKit](https://docs.livekit.io/)
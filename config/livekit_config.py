"""
LiveKit Configuration Module

Правильная конфигурация LiveKit согласно спецификации API.
Содержит все необходимые настройки для аутентификации, подключения и интеграции.
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import timedelta


@dataclass
class LiveKitConnectionConfig:
    """Конфигурация подключения к LiveKit серверу."""
    
    url: str
    api_key: str
    api_secret: str
    connection_timeout: int = 30  # секунды
    keep_alive: int = 25  # секунды
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: int = 1  # секунды
    use_wss: bool = True  # Обязательное использование WSS


@dataclass
class LiveKitJWTConfig:
    """Конфигурация JWT токенов согласно спецификации."""
    
    participant_token_ttl: int = 600  # 10 минут в секундах
    admin_token_ttl: int = 3600  # 1 час в секундах
    auto_refresh_enabled: bool = True
    refresh_threshold: int = 60  # Обновлять за 60 секунд до истечения


@dataclass
class LiveKitRoomConfig:
    """Конфигурация комнат согласно RoomService API."""
    
    empty_timeout: int = 300  # 5 минут по умолчанию
    departure_timeout: int = 20  # 20 секунд по умолчанию
    max_participants: int = 10  # Ограничение участников
    enable_recording: bool = True
    enable_transcription: bool = False


@dataclass
class LiveKitSIPConfig:
    """Конфигурация SIP интеграции согласно SIP API."""
    
    enabled: bool = True
    server: str = ""
    port: int = 5060
    transport: str = "UDP"  # UDP, TCP, TLS
    username: str = ""
    password: str = ""
    number: str = ""
    auth_required: bool = False  # Для входящих звонков
    allowed_addresses: List[str] = None
    
    def __post_init__(self):
        if self.allowed_addresses is None:
            self.allowed_addresses = ["0.0.0.0/0"]


@dataclass
class LiveKitWebhookConfig:
    """Конфигурация webhooks согласно спецификации."""
    
    enabled: bool = True
    url: str = ""
    secret: str = ""
    timeout: int = 5  # секунды
    max_retries: int = 3
    retry_delay: int = 1  # секунды


@dataclass
class LiveKitAudioConfig:
    """Конфигурация аудио кодеков согласно спецификации."""
    
    codecs: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.codecs is None:
            self.codecs = [
                {"name": "PCMU", "priority": 1},
                {"name": "PCMA", "priority": 2},
                {"name": "G722", "priority": 3},
                {"name": "opus", "priority": 4}
            ]


@dataclass
class LiveKitConfig:
    """Основная конфигурация LiveKit системы."""
    
    connection: LiveKitConnectionConfig
    jwt: LiveKitJWTConfig
    room: LiveKitRoomConfig
    sip: LiveKitSIPConfig
    webhook: LiveKitWebhookConfig
    audio: LiveKitAudioConfig
    
    # Дополнительные настройки
    debug_mode: bool = False
    log_level: str = "INFO"
    metrics_enabled: bool = True
    health_check_enabled: bool = True
    health_check_interval: int = 60  # секунды


def load_livekit_config() -> LiveKitConfig:
    """
    Загрузка конфигурации LiveKit из переменных окружения.
    
    Returns:
        LiveKitConfig: Полная конфигурация системы
        
    Raises:
        ValueError: Если обязательные переменные не установлены
    """
    
    # Проверка обязательных переменных
    required_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY", 
        "LIVEKIT_API_SECRET"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {missing_vars}")
    
    # Конфигурация подключения
    connection = LiveKitConnectionConfig(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
        connection_timeout=int(os.getenv("LIVEKIT_CONNECTION_TIMEOUT", "30")),
        keep_alive=int(os.getenv("LIVEKIT_KEEP_ALIVE", "25")),
        auto_reconnect=os.getenv("LIVEKIT_AUTO_RECONNECT", "true").lower() == "true",
        max_reconnect_attempts=int(os.getenv("LIVEKIT_MAX_RECONNECT_ATTEMPTS", "10")),
        reconnect_delay=int(os.getenv("LIVEKIT_RECONNECT_DELAY", "1")),
        use_wss=os.getenv("LIVEKIT_USE_WSS", "true").lower() == "true"
    )
    
    # Конфигурация JWT
    jwt = LiveKitJWTConfig(
        participant_token_ttl=int(os.getenv("LIVEKIT_PARTICIPANT_TOKEN_TTL", "600")),
        admin_token_ttl=int(os.getenv("LIVEKIT_ADMIN_TOKEN_TTL", "3600")),
        auto_refresh_enabled=os.getenv("LIVEKIT_AUTO_REFRESH", "true").lower() == "true",
        refresh_threshold=int(os.getenv("LIVEKIT_REFRESH_THRESHOLD", "60"))
    )
    
    # Конфигурация комнат
    room = LiveKitRoomConfig(
        empty_timeout=int(os.getenv("LIVEKIT_ROOM_EMPTY_TIMEOUT", "300")),
        departure_timeout=int(os.getenv("LIVEKIT_ROOM_DEPARTURE_TIMEOUT", "20")),
        max_participants=int(os.getenv("LIVEKIT_ROOM_MAX_PARTICIPANTS", "10")),
        enable_recording=os.getenv("LIVEKIT_ROOM_ENABLE_RECORDING", "true").lower() == "true",
        enable_transcription=os.getenv("LIVEKIT_ROOM_ENABLE_TRANSCRIPTION", "false").lower() == "true"
    )
    
    # Конфигурация SIP
    sip = LiveKitSIPConfig(
        enabled=os.getenv("LIVEKIT_SIP_ENABLED", "true").lower() == "true",
        server=os.getenv("SIP_SERVER", ""),
        port=int(os.getenv("SIP_PORT", "5060")),
        transport=os.getenv("SIP_TRANSPORT", "UDP"),
        username=os.getenv("SIP_USERNAME", ""),
        password=os.getenv("SIP_PASSWORD", ""),
        number=os.getenv("SIP_NUMBER", ""),
        auth_required=os.getenv("SIP_AUTH_REQUIRED", "false").lower() == "true"
    )
    
    # Конфигурация webhooks
    webhook = LiveKitWebhookConfig(
        enabled=os.getenv("LIVEKIT_WEBHOOK_ENABLED", "true").lower() == "true",
        url=os.getenv("LIVEKIT_WEBHOOK_URL", f"http://{os.getenv('DOMAIN', 'localhost')}:{os.getenv('PORT', '8000')}/webhooks/livekit"),
        secret=os.getenv("LIVEKIT_WEBHOOK_SECRET", os.getenv("SECRET_KEY", "")),
        timeout=int(os.getenv("LIVEKIT_WEBHOOK_TIMEOUT", "5")),
        max_retries=int(os.getenv("LIVEKIT_WEBHOOK_MAX_RETRIES", "3")),
        retry_delay=int(os.getenv("LIVEKIT_WEBHOOK_RETRY_DELAY", "1"))
    )
    
    # Конфигурация аудио
    audio = LiveKitAudioConfig()
    
    return LiveKitConfig(
        connection=connection,
        jwt=jwt,
        room=room,
        sip=sip,
        webhook=webhook,
        audio=audio,
        debug_mode=os.getenv("LIVEKIT_DEBUG", "false").lower() == "true",
        log_level=os.getenv("LIVEKIT_LOG_LEVEL", "INFO"),
        metrics_enabled=os.getenv("LIVEKIT_METRICS_ENABLED", "true").lower() == "true",
        health_check_enabled=os.getenv("LIVEKIT_HEALTH_CHECK_ENABLED", "true").lower() == "true",
        health_check_interval=int(os.getenv("LIVEKIT_HEALTH_CHECK_INTERVAL", "60"))
    )


def validate_livekit_config(config: LiveKitConfig) -> List[str]:
    """
    Валидация конфигурации LiveKit.
    
    Args:
        config: Конфигурация для валидации
        
    Returns:
        List[str]: Список ошибок валидации (пустой если все корректно)
    """
    errors = []
    
    # Валидация подключения
    if not config.connection.url:
        errors.append("LIVEKIT_URL не может быть пустым")
    elif not config.connection.url.startswith(("ws://", "wss://")):
        errors.append("LIVEKIT_URL должен начинаться с ws:// или wss://")
    
    if not config.connection.api_key:
        errors.append("LIVEKIT_API_KEY не может быть пустым")
    
    if not config.connection.api_secret:
        errors.append("LIVEKIT_API_SECRET не может быть пустым")
    
    # Валидация JWT настроек
    if config.jwt.participant_token_ttl < 60:
        errors.append("Время жизни токена участника должно быть не менее 60 секунд")
    
    if config.jwt.admin_token_ttl < 300:
        errors.append("Время жизни административного токена должно быть не менее 300 секунд")
    
    # Валидация комнат
    if config.room.max_participants < 1:
        errors.append("Максимальное количество участников должно быть больше 0")
    
    # Валидация SIP (если включен)
    if config.sip.enabled:
        if not config.sip.server:
            errors.append("SIP_SERVER обязателен когда SIP включен")
        
        if not config.sip.number:
            errors.append("SIP_NUMBER обязателен когда SIP включен")
    
    # Валидация webhooks (если включены)
    if config.webhook.enabled:
        if not config.webhook.url:
            errors.append("LIVEKIT_WEBHOOK_URL обязателен когда webhooks включены")
        
        if not config.webhook.secret:
            errors.append("LIVEKIT_WEBHOOK_SECRET обязателен когда webhooks включены")
    
    return errors


# Глобальная конфигурация (ленивая загрузка)
_config: Optional[LiveKitConfig] = None


def get_livekit_config() -> LiveKitConfig:
    """
    Получение глобальной конфигурации LiveKit.
    
    Returns:
        LiveKitConfig: Конфигурация системы
    """
    global _config
    if _config is None:
        _config = load_livekit_config()
        
        # Валидация конфигурации
        errors = validate_livekit_config(_config)
        if errors:
            raise ValueError(f"Ошибки конфигурации LiveKit: {'; '.join(errors)}")
    
    return _config


def reload_livekit_config() -> LiveKitConfig:
    """
    Принудительная перезагрузка конфигурации.
    
    Returns:
        LiveKitConfig: Новая конфигурация системы
    """
    global _config
    _config = None
    return get_livekit_config()
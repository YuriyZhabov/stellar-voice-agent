"""
LiveKit Performance Optimizer

Модуль для оптимизации производительности системы LiveKit согласно требованиям 9.1-9.5:
- Connection pooling для LiveKit соединений
- Graceful reconnection при сбоях
- Оптимизация латентности аудио обработки
- Ограничение одновременных комнат
- Мониторинг качества соединений
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
import weakref
from contextlib import asynccontextmanager
import statistics

from livekit import api
from livekit.api import LiveKitAPI


class ConnectionState(Enum):
    """Состояния соединения."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class ConnectionMetrics:
    """Метрики соединения."""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    current_latency_ms: float = 0.0
    reconnect_count: int = 0
    state: ConnectionState = ConnectionState.DISCONNECTED
    quality_score: float = 1.0  # 0.0 - 1.0


@dataclass
class PooledConnection:
    """Пулированное соединение к LiveKit."""
    client: LiveKitAPI
    metrics: ConnectionMetrics
    in_use: bool = False
    last_health_check: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RoomLimits:
    """Ограничения для комнат."""
    max_concurrent_rooms: int = 10
    max_participants_per_room: int = 50
    max_audio_tracks_per_room: int = 20
    max_video_tracks_per_room: int = 10


@dataclass
class AudioOptimizationConfig:
    """Конфигурация оптимизации аудио."""
    target_latency_ms: int = 50
    buffer_size_ms: int = 20
    jitter_buffer_ms: int = 100
    echo_cancellation: bool = True
    noise_suppression: bool = True
    auto_gain_control: bool = True


class LiveKitPerformanceOptimizer:
    """Оптимизатор производительности LiveKit системы."""
    
    def __init__(
        self,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        pool_size: int = 5,
        room_limits: Optional[RoomLimits] = None,
        audio_config: Optional[AudioOptimizationConfig] = None
    ):
        self.livekit_url = livekit_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.pool_size = pool_size
        self.room_limits = room_limits or RoomLimits()
        self.audio_config = audio_config or AudioOptimizationConfig()
        
        # Connection pool
        self._connection_pool: List[PooledConnection] = []
        self._pool_lock = asyncio.Lock()
        
        # Room tracking
        self._active_rooms: Dict[str, Dict[str, Any]] = {}
        self._room_participants: Dict[str, Set[str]] = {}
        self._room_tracks: Dict[str, Dict[str, int]] = {}
        
        # Performance metrics
        self._global_metrics = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "avg_connection_latency": 0.0,
            "reconnection_rate": 0.0,
            "room_creation_rate": 0.0,
            "audio_latency_ms": [],
            "connection_quality_scores": []
        }
        
        # Monitoring
        self.logger = logging.getLogger(__name__)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30  # seconds
        
        # Graceful shutdown
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Инициализация оптимизатора производительности."""
        self.logger.info("Initializing LiveKit Performance Optimizer")
        
        # Создание начального пула соединений
        await self._initialize_connection_pool()
        
        # Запуск мониторинга
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(f"Performance optimizer initialized with pool size: {self.pool_size}")
    
    async def shutdown(self) -> None:
        """Graceful shutdown оптимизатора."""
        self.logger.info("Shutting down Performance Optimizer")
        
        self._shutdown_event.set()
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Закрытие всех соединений в пуле
        async with self._pool_lock:
            for conn in self._connection_pool:
                try:
                    # LiveKit API client не требует явного закрытия
                    pass
                except Exception as e:
                    self.logger.error(f"Error closing connection: {e}")
            
            self._connection_pool.clear()
        
        self.logger.info("Performance Optimizer shutdown complete")
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения из пула с автоматическим возвратом."""
        connection = await self._acquire_connection()
        try:
            yield connection.client
        finally:
            await self._release_connection(connection)
    
    async def _initialize_connection_pool(self) -> None:
        """Инициализация пула соединений."""
        async with self._pool_lock:
            for i in range(self.pool_size):
                try:
                    client = LiveKitAPI(
                        url=self.livekit_url,
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )
                    
                    metrics = ConnectionMetrics(state=ConnectionState.CONNECTED)
                    connection = PooledConnection(client=client, metrics=metrics)
                    
                    # Проверка соединения
                    await self._test_connection(connection)
                    
                    self._connection_pool.append(connection)
                    self._global_metrics["total_connections"] += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to create connection {i}: {e}")
                    self._global_metrics["failed_connections"] += 1
    
    async def _acquire_connection(self) -> PooledConnection:
        """Получение соединения из пула."""
        async with self._pool_lock:
            # Поиск свободного соединения
            for connection in self._connection_pool:
                if not connection.in_use and connection.metrics.state == ConnectionState.CONNECTED:
                    connection.in_use = True
                    connection.metrics.last_used = datetime.now(UTC)
                    self._global_metrics["active_connections"] += 1
                    return connection
            
            # Если нет свободных соединений, создаем новое
            if len(self._connection_pool) < self.pool_size * 2:  # Динамическое расширение
                try:
                    client = LiveKitAPI(
                        url=self.livekit_url,
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )
                    
                    metrics = ConnectionMetrics(state=ConnectionState.CONNECTED)
                    connection = PooledConnection(client=client, metrics=metrics, in_use=True)
                    
                    await self._test_connection(connection)
                    
                    self._connection_pool.append(connection)
                    self._global_metrics["total_connections"] += 1
                    self._global_metrics["active_connections"] += 1
                    
                    return connection
                    
                except Exception as e:
                    self.logger.error(f"Failed to create new connection: {e}")
                    self._global_metrics["failed_connections"] += 1
            
            # Ожидание освобождения соединения
            self.logger.warning("No available connections, waiting...")
            await asyncio.sleep(0.1)
            return await self._acquire_connection()
    
    async def _release_connection(self, connection: PooledConnection) -> None:
        """Возврат соединения в пул."""
        async with self._pool_lock:
            connection.in_use = False
            self._global_metrics["active_connections"] = max(0, self._global_metrics["active_connections"] - 1)
    
    async def _test_connection(self, connection: PooledConnection) -> bool:
        """Тестирование соединения."""
        try:
            start_time = time.time()
            
            # Простой тест - получение списка комнат
            await connection.client.room.list_rooms(api.ListRoomsRequest())
            
            latency = (time.time() - start_time) * 1000
            connection.metrics.current_latency_ms = latency
            connection.metrics.state = ConnectionState.CONNECTED
            
            # Обновление средней латентности
            if connection.metrics.avg_latency_ms == 0:
                connection.metrics.avg_latency_ms = latency
            else:
                connection.metrics.avg_latency_ms = (connection.metrics.avg_latency_ms + latency) / 2
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            connection.metrics.state = ConnectionState.FAILED
            connection.metrics.failed_requests += 1
            return False
    
    async def _reconnect_connection(self, connection: PooledConnection) -> bool:
        """Graceful переподключение."""
        self.logger.info("Attempting graceful reconnection")
        
        connection.metrics.state = ConnectionState.RECONNECTING
        connection.metrics.reconnect_count += 1
        
        max_attempts = 5
        base_delay = 1.0
        
        for attempt in range(max_attempts):
            try:
                # Экспоненциальный backoff
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                
                # Создание нового клиента
                connection.client = LiveKitAPI(
                    url=self.livekit_url,
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
                
                # Тестирование соединения
                if await self._test_connection(connection):
                    self.logger.info(f"Reconnection successful after {attempt + 1} attempts")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
        
        connection.metrics.state = ConnectionState.FAILED
        self.logger.error("All reconnection attempts failed")
        return False
    
    async def create_optimized_room(
        self,
        room_name: str,
        max_participants: Optional[int] = None,
        audio_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Создание оптимизированной комнаты с ограничениями."""
        
        # Проверка лимитов
        if len(self._active_rooms) >= self.room_limits.max_concurrent_rooms:
            self.logger.warning(f"Room limit reached: {self.room_limits.max_concurrent_rooms}")
            return False
        
        if room_name in self._active_rooms:
            self.logger.warning(f"Room {room_name} already exists")
            return False
        
        max_participants = max_participants or self.room_limits.max_participants_per_room
        
        try:
            async with self.get_connection() as client:
                # Создание комнаты с оптимизированными настройками
                request = api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=300,  # 5 минут
                    departure_timeout=20,  # 20 секунд
                    max_participants=max_participants,
                    metadata=self._create_room_metadata(audio_config)
                )
                
                room = await client.room.create_room(request)
                
                # Регистрация комнаты
                self._active_rooms[room_name] = {
                    "created_at": datetime.now(UTC),
                    "max_participants": max_participants,
                    "audio_config": audio_config or {},
                    "room_info": room
                }
                
                self._room_participants[room_name] = set()
                self._room_tracks[room_name] = {"audio": 0, "video": 0}
                
                self.logger.info(f"Created optimized room: {room_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to create room {room_name}: {e}")
            return False
    
    def _create_room_metadata(self, audio_config: Optional[Dict[str, Any]]) -> str:
        """Создание метаданных комнаты с настройками аудио."""
        metadata = {
            "audio_optimization": {
                "target_latency_ms": self.audio_config.target_latency_ms,
                "buffer_size_ms": self.audio_config.buffer_size_ms,
                "jitter_buffer_ms": self.audio_config.jitter_buffer_ms,
                "echo_cancellation": self.audio_config.echo_cancellation,
                "noise_suppression": self.audio_config.noise_suppression,
                "auto_gain_control": self.audio_config.auto_gain_control
            },
            "performance_limits": {
                "max_audio_tracks": self.room_limits.max_audio_tracks_per_room,
                "max_video_tracks": self.room_limits.max_video_tracks_per_room
            }
        }
        
        if audio_config:
            metadata["audio_optimization"].update(audio_config)
        
        import json
        return json.dumps(metadata)
    
    async def add_participant_to_room(
        self,
        room_name: str,
        participant_id: str
    ) -> bool:
        """Добавление участника в комнату с проверкой лимитов."""
        
        if room_name not in self._active_rooms:
            self.logger.error(f"Room {room_name} not found")
            return False
        
        room_info = self._active_rooms[room_name]
        current_participants = len(self._room_participants[room_name])
        
        if current_participants >= room_info["max_participants"]:
            self.logger.warning(f"Participant limit reached for room {room_name}")
            return False
        
        self._room_participants[room_name].add(participant_id)
        self.logger.info(f"Added participant {participant_id} to room {room_name}")
        return True
    
    async def monitor_connection_quality(self) -> Dict[str, Any]:
        """Мониторинг качества соединений."""
        quality_metrics = {
            "timestamp": datetime.now(UTC).isoformat(),
            "pool_status": {
                "total_connections": len(self._connection_pool),
                "active_connections": sum(1 for c in self._connection_pool if c.in_use),
                "healthy_connections": sum(1 for c in self._connection_pool if c.metrics.state == ConnectionState.CONNECTED),
                "failed_connections": sum(1 for c in self._connection_pool if c.metrics.state == ConnectionState.FAILED)
            },
            "performance_metrics": {
                "avg_latency_ms": 0.0,
                "min_latency_ms": float('inf'),
                "max_latency_ms": 0.0,
                "quality_score": 0.0
            },
            "room_metrics": {
                "active_rooms": len(self._active_rooms),
                "total_participants": sum(len(participants) for participants in self._room_participants.values()),
                "avg_participants_per_room": 0.0
            }
        }
        
        # Расчет метрик производительности
        latencies = [c.metrics.current_latency_ms for c in self._connection_pool if c.metrics.current_latency_ms > 0]
        if latencies:
            quality_metrics["performance_metrics"]["avg_latency_ms"] = statistics.mean(latencies)
            quality_metrics["performance_metrics"]["min_latency_ms"] = min(latencies)
            quality_metrics["performance_metrics"]["max_latency_ms"] = max(latencies)
        
        # Расчет качества соединений
        quality_scores = []
        for connection in self._connection_pool:
            if connection.metrics.total_requests > 0:
                success_rate = 1.0 - (connection.metrics.failed_requests / connection.metrics.total_requests)
                latency_score = max(0.0, 1.0 - (connection.metrics.avg_latency_ms / 1000.0))  # Нормализация
                quality_score = (success_rate + latency_score) / 2
                quality_scores.append(quality_score)
                connection.metrics.quality_score = quality_score
        
        if quality_scores:
            quality_metrics["performance_metrics"]["quality_score"] = statistics.mean(quality_scores)
        
        # Метрики комнат
        if self._active_rooms:
            total_participants = sum(len(participants) for participants in self._room_participants.values())
            quality_metrics["room_metrics"]["avg_participants_per_room"] = total_participants / len(self._active_rooms)
        
        return quality_metrics
    
    async def _monitoring_loop(self) -> None:
        """Основной цикл мониторинга."""
        while not self._shutdown_event.is_set():
            try:
                # Health check соединений
                await self._health_check_connections()
                
                # Мониторинг качества
                quality_metrics = await self.monitor_connection_quality()
                
                # Логирование метрик
                self.logger.info(f"Quality metrics: {quality_metrics['performance_metrics']}")
                
                # Очистка неактивных комнат
                await self._cleanup_inactive_rooms()
                
                await asyncio.sleep(self._health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _health_check_connections(self) -> None:
        """Health check всех соединений в пуле."""
        async with self._pool_lock:
            for connection in self._connection_pool:
                if not connection.in_use:
                    # Проверка только неиспользуемых соединений
                    time_since_check = datetime.now(UTC) - connection.last_health_check
                    
                    if time_since_check.total_seconds() > self._health_check_interval:
                        connection.last_health_check = datetime.now(UTC)
                        
                        if not await self._test_connection(connection):
                            # Попытка переподключения
                            await self._reconnect_connection(connection)
    
    async def _cleanup_inactive_rooms(self) -> None:
        """Очистка неактивных комнат."""
        current_time = datetime.now(UTC)
        rooms_to_remove = []
        
        for room_name, room_info in self._active_rooms.items():
            # Удаление комнат старше 1 часа без участников
            if (len(self._room_participants[room_name]) == 0 and 
                current_time - room_info["created_at"] > timedelta(hours=1)):
                rooms_to_remove.append(room_name)
        
        for room_name in rooms_to_remove:
            try:
                async with self.get_connection() as client:
                    await client.room.delete_room(api.DeleteRoomRequest(room=room_name))
                
                del self._active_rooms[room_name]
                del self._room_participants[room_name]
                del self._room_tracks[room_name]
                
                self.logger.info(f"Cleaned up inactive room: {room_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to cleanup room {room_name}: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получение статистики производительности."""
        return {
            "global_metrics": self._global_metrics.copy(),
            "pool_size": len(self._connection_pool),
            "active_rooms": len(self._active_rooms),
            "room_limits": {
                "max_concurrent_rooms": self.room_limits.max_concurrent_rooms,
                "max_participants_per_room": self.room_limits.max_participants_per_room,
                "max_audio_tracks_per_room": self.room_limits.max_audio_tracks_per_room,
                "max_video_tracks_per_room": self.room_limits.max_video_tracks_per_room
            },
            "audio_config": {
                "target_latency_ms": self.audio_config.target_latency_ms,
                "buffer_size_ms": self.audio_config.buffer_size_ms,
                "jitter_buffer_ms": self.audio_config.jitter_buffer_ms
            }
        }


# Глобальный экземпляр оптимизатора
_performance_optimizer: Optional[LiveKitPerformanceOptimizer] = None


async def get_performance_optimizer() -> LiveKitPerformanceOptimizer:
    """Получение глобального экземпляра оптимизатора производительности."""
    global _performance_optimizer
    
    if _performance_optimizer is None:
        raise RuntimeError("Performance optimizer not initialized. Call initialize_performance_optimizer() first.")
    
    return _performance_optimizer


async def initialize_performance_optimizer(
    livekit_url: str,
    api_key: str,
    api_secret: str,
    **kwargs
) -> LiveKitPerformanceOptimizer:
    """Инициализация глобального оптимизатора производительности."""
    global _performance_optimizer
    
    if _performance_optimizer is not None:
        await _performance_optimizer.shutdown()
    
    _performance_optimizer = LiveKitPerformanceOptimizer(
        livekit_url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        **kwargs
    )
    
    await _performance_optimizer.initialize()
    return _performance_optimizer


async def shutdown_performance_optimizer() -> None:
    """Shutdown глобального оптимизатора производительности."""
    global _performance_optimizer
    
    if _performance_optimizer is not None:
        await _performance_optimizer.shutdown()
        _performance_optimizer = None
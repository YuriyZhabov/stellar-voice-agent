"""
Tests for LiveKit Performance Optimization System

Тесты для проверки всех аспектов оптимизации производительности:
- Connection pooling
- Graceful reconnection
- Audio latency optimization
- Room limits
- Connection quality monitoring
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

from src.performance_optimizer import (
    LiveKitPerformanceOptimizer,
    ConnectionState,
    ConnectionMetrics,
    PooledConnection,
    RoomLimits,
    AudioOptimizationConfig,
    initialize_performance_optimizer,
    get_performance_optimizer,
    shutdown_performance_optimizer
)
from src.config.performance_config import (
    PerformanceConfig,
    ConnectionPoolConfig,
    RoomLimitsConfig,
    AudioOptimizationConfig as ConfigAudioOptimization,
    QualityMonitoringConfig,
    get_performance_config
)


class TestConnectionPooling:
    """Тесты для connection pooling."""
    
    @pytest.fixture
    async def optimizer(self):
        """Создание оптимизатора для тестов."""
        optimizer = LiveKitPerformanceOptimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret",
            pool_size=3
        )
        
        # Мокаем LiveKit API
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            await optimizer.initialize()
            yield optimizer
            await optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_connection_pool_initialization(self, optimizer):
        """Тест инициализации пула соединений."""
        assert len(optimizer._connection_pool) == 3
        assert optimizer._global_metrics["total_connections"] == 3
        
        # Проверка состояния соединений
        for conn in optimizer._connection_pool:
            assert conn.metrics.state == ConnectionState.CONNECTED
            assert not conn.in_use
    
    @pytest.mark.asyncio
    async def test_connection_acquisition_and_release(self, optimizer):
        """Тест получения и возврата соединений."""
        # Получение соединения
        async with optimizer.get_connection() as client:
            assert client is not None
            assert optimizer._global_metrics["active_connections"] == 1
            
            # Проверка что соединение помечено как используемое
            used_connections = [c for c in optimizer._connection_pool if c.in_use]
            assert len(used_connections) == 1
        
        # После выхода из контекста соединение должно быть освобождено
        assert optimizer._global_metrics["active_connections"] == 0
        used_connections = [c for c in optimizer._connection_pool if c.in_use]
        assert len(used_connections) == 0
    
    @pytest.mark.asyncio
    async def test_connection_pool_expansion(self, optimizer):
        """Тест динамического расширения пула."""
        # Занимаем все соединения в пуле
        connections = []
        for i in range(optimizer.pool_size + 2):  # Больше чем размер пула
            conn = await optimizer._acquire_connection()
            connections.append(conn)
        
        # Пул должен расшириться
        assert len(optimizer._connection_pool) > optimizer.pool_size
        
        # Освобождаем соединения
        for conn in connections:
            await optimizer._release_connection(conn)
    
    @pytest.mark.asyncio
    async def test_connection_health_check(self, optimizer):
        """Тест health check соединений."""
        # Симулируем неисправное соединение
        optimizer._connection_pool[0].metrics.state = ConnectionState.FAILED
        
        # Запускаем health check
        await optimizer._health_check_connections()
        
        # Соединение должно быть восстановлено или помечено для переподключения
        assert optimizer._connection_pool[0].metrics.reconnect_count > 0


class TestGracefulReconnection:
    """Тесты для graceful reconnection."""
    
    @pytest.fixture
    async def optimizer(self):
        """Создание оптимизатора для тестов."""
        optimizer = LiveKitPerformanceOptimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret",
            pool_size=2
        )
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            await optimizer.initialize()
            yield optimizer
            await optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_graceful_reconnection_success(self, optimizer):
        """Тест успешного graceful переподключения."""
        connection = optimizer._connection_pool[0]
        connection.metrics.state = ConnectionState.FAILED
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            # Тестируем переподключение
            result = await optimizer._reconnect_connection(connection)
            
            assert result is True
            assert connection.metrics.state == ConnectionState.CONNECTED
            assert connection.metrics.reconnect_count == 1
    
    @pytest.mark.asyncio
    async def test_graceful_reconnection_failure(self, optimizer):
        """Тест неудачного graceful переподключения."""
        connection = optimizer._connection_pool[0]
        connection.metrics.state = ConnectionState.FAILED
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            # Симулируем постоянные ошибки
            mock_api.side_effect = Exception("Connection failed")
            
            # Тестируем переподключение
            result = await optimizer._reconnect_connection(connection)
            
            assert result is False
            assert connection.metrics.state == ConnectionState.FAILED
            assert connection.metrics.reconnect_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, optimizer):
        """Тест экспоненциального backoff при переподключении."""
        connection = optimizer._connection_pool[0]
        connection.metrics.state = ConnectionState.FAILED
        
        start_time = time.time()
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            # Первые попытки неудачные, последняя успешная
            mock_api.side_effect = [
                Exception("Failed 1"),
                Exception("Failed 2"),
                AsyncMock()  # Успешное соединение
            ]
            
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            result = await optimizer._reconnect_connection(connection)
            
            # Проверяем что прошло достаточно времени для backoff
            elapsed = time.time() - start_time
            assert elapsed >= 1.0  # Минимальная задержка
            assert result is True


class TestAudioLatencyOptimization:
    """Тесты для оптимизации латентности аудио."""
    
    @pytest.fixture
    async def optimizer(self):
        """Создание оптимизатора с настройками аудио."""
        audio_config = AudioOptimizationConfig(
            target_latency_ms=30,
            buffer_size_ms=15,
            jitter_buffer_ms=80,
            echo_cancellation=True,
            noise_suppression=True,
            auto_gain_control=True
        )
        
        optimizer = LiveKitPerformanceOptimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret",
            audio_config=audio_config
        )
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_client.room.create_room = AsyncMock(return_value=Mock(name="test_room"))
            mock_api.return_value = mock_client
            
            await optimizer.initialize()
            yield optimizer
            await optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_audio_optimization_config_in_room_metadata(self, optimizer):
        """Тест включения настроек аудио в метаданные комнаты."""
        room_name = "test_audio_room"
        
        result = await optimizer.create_optimized_room(room_name)
        assert result is True
        
        # Проверяем что комната создана с правильными настройками
        room_info = optimizer._active_rooms[room_name]
        
        # Метаданные должны содержать настройки аудио
        import json
        metadata = json.loads(room_info["room_info"].metadata if hasattr(room_info["room_info"], 'metadata') else '{}')
        
        # Проверяем настройки аудио в метаданных
        audio_opt = metadata.get("audio_optimization", {})
        assert audio_opt.get("target_latency_ms") == 30
        assert audio_opt.get("buffer_size_ms") == 15
        assert audio_opt.get("jitter_buffer_ms") == 80
        assert audio_opt.get("echo_cancellation") is True
    
    def test_audio_config_creation(self):
        """Тест создания конфигурации аудио."""
        config = AudioOptimizationConfig(
            target_latency_ms=25,
            buffer_size_ms=10,
            adaptive_bitrate=True,
            min_bitrate_kbps=32,
            max_bitrate_kbps=256
        )
        
        assert config.target_latency_ms == 25
        assert config.buffer_size_ms == 10
        assert config.adaptive_bitrate is True
        assert config.min_bitrate_kbps == 32
        assert config.max_bitrate_kbps == 256


class TestRoomLimits:
    """Тесты для ограничений комнат."""
    
    @pytest.fixture
    async def optimizer(self):
        """Создание оптимизатора с ограничениями."""
        room_limits = RoomLimits(
            max_concurrent_rooms=2,
            max_participants_per_room=3,
            max_audio_tracks_per_room=5,
            max_video_tracks_per_room=2
        )
        
        optimizer = LiveKitPerformanceOptimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret",
            room_limits=room_limits
        )
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_client.room.create_room = AsyncMock(return_value=Mock(name="test_room"))
            mock_api.return_value = mock_client
            
            await optimizer.initialize()
            yield optimizer
            await optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_room_limit(self, optimizer):
        """Тест ограничения одновременных комнат."""
        # Создаем максимальное количество комнат
        for i in range(optimizer.room_limits.max_concurrent_rooms):
            result = await optimizer.create_optimized_room(f"room_{i}")
            assert result is True
        
        # Попытка создать еще одну комнату должна быть отклонена
        result = await optimizer.create_optimized_room("room_overflow")
        assert result is False
        
        assert len(optimizer._active_rooms) == optimizer.room_limits.max_concurrent_rooms
    
    @pytest.mark.asyncio
    async def test_participant_limit_per_room(self, optimizer):
        """Тест ограничения участников в комнате."""
        room_name = "test_room"
        
        # Создаем комнату
        await optimizer.create_optimized_room(room_name)
        
        # Добавляем максимальное количество участников
        for i in range(optimizer.room_limits.max_participants_per_room):
            result = await optimizer.add_participant_to_room(room_name, f"participant_{i}")
            assert result is True
        
        # Попытка добавить еще одного участника должна быть отклонена
        result = await optimizer.add_participant_to_room(room_name, "participant_overflow")
        assert result is False
        
        assert len(optimizer._room_participants[room_name]) == optimizer.room_limits.max_participants_per_room
    
    @pytest.mark.asyncio
    async def test_room_metadata_includes_limits(self, optimizer):
        """Тест включения ограничений в метаданные комнаты."""
        room_name = "test_room"
        
        result = await optimizer.create_optimized_room(room_name)
        assert result is True
        
        # Проверяем метаданные
        room_info = optimizer._active_rooms[room_name]
        
        import json
        metadata = json.loads(room_info["room_info"].metadata if hasattr(room_info["room_info"], 'metadata') else '{}')
        
        perf_limits = metadata.get("performance_limits", {})
        assert perf_limits.get("max_audio_tracks") == optimizer.room_limits.max_audio_tracks_per_room
        assert perf_limits.get("max_video_tracks") == optimizer.room_limits.max_video_tracks_per_room


class TestConnectionQualityMonitoring:
    """Тесты для мониторинга качества соединений."""
    
    @pytest.fixture
    async def optimizer(self):
        """Создание оптимизатора для тестов мониторинга."""
        optimizer = LiveKitPerformanceOptimizer(
            livekit_url="ws://localhost:7880",
            api_key="test_key",
            api_secret="test_secret",
            pool_size=2
        )
        
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            await optimizer.initialize()
            yield optimizer
            await optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_connection_quality_monitoring(self, optimizer):
        """Тест мониторинга качества соединений."""
        # Устанавливаем метрики для соединений
        for i, conn in enumerate(optimizer._connection_pool):
            conn.metrics.current_latency_ms = 50 + i * 10
            conn.metrics.avg_latency_ms = 45 + i * 10
            conn.metrics.total_requests = 100
            conn.metrics.failed_requests = 5
            conn.metrics.quality_score = 0.8 - i * 0.1
        
        # Получаем метрики качества
        quality_metrics = await optimizer.monitor_connection_quality()
        
        assert "timestamp" in quality_metrics
        assert "pool_status" in quality_metrics
        assert "performance_metrics" in quality_metrics
        assert "room_metrics" in quality_metrics
        
        # Проверяем статус пула
        pool_status = quality_metrics["pool_status"]
        assert pool_status["total_connections"] == 2
        assert pool_status["healthy_connections"] == 2
        
        # Проверяем метрики производительности
        perf_metrics = quality_metrics["performance_metrics"]
        assert perf_metrics["avg_latency_ms"] > 0
        assert perf_metrics["min_latency_ms"] > 0
        assert perf_metrics["max_latency_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_quality_score_calculation(self, optimizer):
        """Тест расчета оценки качества соединений."""
        # Настраиваем метрики соединения
        connection = optimizer._connection_pool[0]
        connection.metrics.total_requests = 100
        connection.metrics.failed_requests = 10  # 90% success rate
        connection.metrics.avg_latency_ms = 100  # Средняя латентность
        
        quality_metrics = await optimizer.monitor_connection_quality()
        
        # Проверяем что качество рассчитано
        assert quality_metrics["performance_metrics"]["quality_score"] > 0
        assert quality_metrics["performance_metrics"]["quality_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_performance_stats(self, optimizer):
        """Тест получения статистики производительности."""
        stats = optimizer.get_performance_stats()
        
        assert "global_metrics" in stats
        assert "pool_size" in stats
        assert "active_rooms" in stats
        assert "room_limits" in stats
        assert "audio_config" in stats
        
        # Проверяем структуру лимитов комнат
        room_limits = stats["room_limits"]
        assert "max_concurrent_rooms" in room_limits
        assert "max_participants_per_room" in room_limits
        assert "max_audio_tracks_per_room" in room_limits
        assert "max_video_tracks_per_room" in room_limits
        
        # Проверяем конфигурацию аудио
        audio_config = stats["audio_config"]
        assert "target_latency_ms" in audio_config
        assert "buffer_size_ms" in audio_config
        assert "jitter_buffer_ms" in audio_config


class TestPerformanceConfigIntegration:
    """Тесты интеграции с конфигурацией производительности."""
    
    def test_performance_config_loading(self):
        """Тест загрузки конфигурации производительности."""
        config = get_performance_config()
        
        assert isinstance(config, PerformanceConfig)
        assert isinstance(config.connection_pool, ConnectionPoolConfig)
        assert isinstance(config.room_limits, RoomLimitsConfig)
        assert isinstance(config.audio_optimization, ConfigAudioOptimization)
        assert isinstance(config.quality_monitoring, QualityMonitoringConfig)
    
    def test_config_values(self):
        """Тест значений конфигурации по умолчанию."""
        config = get_performance_config()
        
        # Connection pool
        assert config.connection_pool.pool_size == 5
        assert config.connection_pool.max_pool_size == 10
        assert config.connection_pool.health_check_interval == 30
        
        # Room limits
        assert config.room_limits.max_concurrent_rooms == 10
        assert config.room_limits.max_participants_per_room == 50
        
        # Audio optimization
        assert config.audio_optimization.target_latency_ms == 50
        assert config.audio_optimization.buffer_size_ms == 20
        assert config.audio_optimization.echo_cancellation is True
        
        # Quality monitoring
        assert config.quality_monitoring.monitoring_interval == 10
        assert config.quality_monitoring.min_success_rate == 0.95


class TestGlobalOptimizerManagement:
    """Тесты для глобального управления оптимизатором."""
    
    @pytest.mark.asyncio
    async def test_global_optimizer_initialization(self):
        """Тест инициализации глобального оптимизатора."""
        with patch('src.performance_optimizer.LiveKitAPI') as mock_api:
            mock_client = AsyncMock()
            mock_client.room.list_rooms = AsyncMock(return_value=Mock(rooms=[]))
            mock_api.return_value = mock_client
            
            # Инициализация
            optimizer = await initialize_performance_optimizer(
                livekit_url="ws://localhost:7880",
                api_key="test_key",
                api_secret="test_secret"
            )
            
            assert optimizer is not None
            
            # Получение глобального экземпляра
            global_optimizer = await get_performance_optimizer()
            assert global_optimizer is optimizer
            
            # Shutdown
            await shutdown_performance_optimizer()
    
    @pytest.mark.asyncio
    async def test_global_optimizer_error_handling(self):
        """Тест обработки ошибок глобального оптимизатора."""
        # Попытка получить неинициализированный оптимизатор
        with pytest.raises(RuntimeError):
            await get_performance_optimizer()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
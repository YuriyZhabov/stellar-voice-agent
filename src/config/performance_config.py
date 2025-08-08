"""
Performance Configuration Loader

Загрузчик конфигурации для оптимизации производительности LiveKit системы.
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConnectionPoolConfig:
    """Конфигурация пула соединений."""
    pool_size: int = 5
    max_pool_size: int = 10
    health_check_interval: int = 30
    connection_timeout: int = 10
    max_reconnect_attempts: int = 5
    reconnect_base_delay: float = 1.0


@dataclass
class RoomLimitsConfig:
    """Конфигурация ограничений комнат."""
    max_concurrent_rooms: int = 10
    max_participants_per_room: int = 50
    max_audio_tracks_per_room: int = 20
    max_video_tracks_per_room: int = 10
    empty_room_timeout: int = 300
    departure_timeout: int = 20


@dataclass
class AudioOptimizationConfig:
    """Конфигурация оптимизации аудио."""
    target_latency_ms: int = 50
    buffer_size_ms: int = 20
    jitter_buffer_ms: int = 100
    echo_cancellation: bool = True
    noise_suppression: bool = True
    auto_gain_control: bool = True
    adaptive_bitrate: bool = True
    min_bitrate_kbps: int = 16
    max_bitrate_kbps: int = 128


@dataclass
class QualityThresholds:
    """Пороговые значения качества."""
    excellent: float = 0.9
    good: float = 0.7
    fair: float = 0.5
    poor: float = 0.5


@dataclass
class LatencyThresholds:
    """Пороговые значения латентности."""
    excellent: int = 50
    good: int = 100
    fair: int = 200
    poor: int = 500


@dataclass
class QualityMonitoringConfig:
    """Конфигурация мониторинга качества."""
    monitoring_interval: int = 10
    quality_thresholds: QualityThresholds = None
    latency_thresholds: LatencyThresholds = None
    min_success_rate: float = 0.95
    
    def __post_init__(self):
        if self.quality_thresholds is None:
            self.quality_thresholds = QualityThresholds()
        if self.latency_thresholds is None:
            self.latency_thresholds = LatencyThresholds()


@dataclass
class MetricsConfig:
    """Конфигурация метрик."""
    detailed_metrics: bool = True
    metrics_buffer_size: int = 1000
    aggregation_interval: int = 60
    prometheus_export: bool = True
    prometheus_port: int = 9090


@dataclass
class ReconnectionConfig:
    """Конфигурация переподключения."""
    enabled: bool = True
    max_attempts: int = 5
    exponential_backoff: bool = True
    max_delay: int = 60
    jitter: bool = True
    jitter_percent: float = 0.1


@dataclass
class ResourceManagementConfig:
    """Конфигурация управления ресурсами."""
    auto_cleanup: bool = True
    cleanup_interval: int = 300
    inactive_room_ttl: int = 3600
    disconnected_participant_ttl: int = 120


@dataclass
class LoadBalancingConfig:
    """Конфигурация балансировки нагрузки."""
    enabled: bool = True
    algorithm: str = "least_connections"
    weights: Dict[str, float] = None
    health_check_enabled: bool = True
    
    def __post_init__(self):
        if self.weights is None:
            self.weights = {"primary": 1.0, "secondary": 0.8}


@dataclass
class CachingConfig:
    """Конфигурация кэширования."""
    enabled: bool = True
    room_cache_ttl: int = 300
    participant_cache_ttl: int = 60
    max_cache_size: int = 1000


@dataclass
class LoggingConfig:
    """Конфигурация логирования."""
    level: str = "INFO"
    structured: bool = True
    include_metrics: bool = True
    metrics_log_interval: int = 60


@dataclass
class PerformanceConfig:
    """Полная конфигурация производительности."""
    connection_pool: ConnectionPoolConfig = None
    room_limits: RoomLimitsConfig = None
    audio_optimization: AudioOptimizationConfig = None
    quality_monitoring: QualityMonitoringConfig = None
    metrics: MetricsConfig = None
    reconnection: ReconnectionConfig = None
    resource_management: ResourceManagementConfig = None
    load_balancing: LoadBalancingConfig = None
    caching: CachingConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        if self.connection_pool is None:
            self.connection_pool = ConnectionPoolConfig()
        if self.room_limits is None:
            self.room_limits = RoomLimitsConfig()
        if self.audio_optimization is None:
            self.audio_optimization = AudioOptimizationConfig()
        if self.quality_monitoring is None:
            self.quality_monitoring = QualityMonitoringConfig()
        if self.metrics is None:
            self.metrics = MetricsConfig()
        if self.reconnection is None:
            self.reconnection = ReconnectionConfig()
        if self.resource_management is None:
            self.resource_management = ResourceManagementConfig()
        if self.load_balancing is None:
            self.load_balancing = LoadBalancingConfig()
        if self.caching is None:
            self.caching = CachingConfig()
        if self.logging is None:
            self.logging = LoggingConfig()


class PerformanceConfigLoader:
    """Загрузчик конфигурации производительности."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
    
    def _get_default_config_path(self) -> str:
        """Получение пути к конфигурационному файлу по умолчанию."""
        # Поиск конфигурационного файла в нескольких местах
        possible_paths = [
            "config/performance.yaml",
            "config/performance.yml",
            "/etc/livekit/performance.yaml",
            os.path.expanduser("~/.livekit/performance.yaml")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Если файл не найден, используем первый путь как значение по умолчанию
        return possible_paths[0]
    
    def load_config(self) -> PerformanceConfig:
        """Загрузка конфигурации из файла."""
        try:
            if not os.path.exists(self.config_path):
                print(f"Config file not found: {self.config_path}, using defaults")
                return PerformanceConfig()
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
            
            if not config_data:
                return PerformanceConfig()
            
            return self._parse_config(config_data)
            
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            return PerformanceConfig()
    
    def _parse_config(self, config_data: Dict[str, Any]) -> PerformanceConfig:
        """Парсинг конфигурационных данных."""
        config = PerformanceConfig()
        
        # Connection Pool
        if 'connection_pool' in config_data:
            pool_data = config_data['connection_pool']
            config.connection_pool = ConnectionPoolConfig(
                pool_size=pool_data.get('pool_size', 5),
                max_pool_size=pool_data.get('max_pool_size', 10),
                health_check_interval=pool_data.get('health_check_interval', 30),
                connection_timeout=pool_data.get('connection_timeout', 10),
                max_reconnect_attempts=pool_data.get('max_reconnect_attempts', 5),
                reconnect_base_delay=pool_data.get('reconnect_base_delay', 1.0)
            )
        
        # Room Limits
        if 'room_limits' in config_data:
            limits_data = config_data['room_limits']
            config.room_limits = RoomLimitsConfig(
                max_concurrent_rooms=limits_data.get('max_concurrent_rooms', 10),
                max_participants_per_room=limits_data.get('max_participants_per_room', 50),
                max_audio_tracks_per_room=limits_data.get('max_audio_tracks_per_room', 20),
                max_video_tracks_per_room=limits_data.get('max_video_tracks_per_room', 10),
                empty_room_timeout=limits_data.get('empty_room_timeout', 300),
                departure_timeout=limits_data.get('departure_timeout', 20)
            )
        
        # Audio Optimization
        if 'audio_optimization' in config_data:
            audio_data = config_data['audio_optimization']
            config.audio_optimization = AudioOptimizationConfig(
                target_latency_ms=audio_data.get('target_latency_ms', 50),
                buffer_size_ms=audio_data.get('buffer_size_ms', 20),
                jitter_buffer_ms=audio_data.get('jitter_buffer_ms', 100),
                echo_cancellation=audio_data.get('echo_cancellation', True),
                noise_suppression=audio_data.get('noise_suppression', True),
                auto_gain_control=audio_data.get('auto_gain_control', True),
                adaptive_bitrate=audio_data.get('adaptive_bitrate', True),
                min_bitrate_kbps=audio_data.get('min_bitrate_kbps', 16),
                max_bitrate_kbps=audio_data.get('max_bitrate_kbps', 128)
            )
        
        # Quality Monitoring
        if 'quality_monitoring' in config_data:
            quality_data = config_data['quality_monitoring']
            
            quality_thresholds = QualityThresholds()
            if 'quality_thresholds' in quality_data:
                qt_data = quality_data['quality_thresholds']
                quality_thresholds = QualityThresholds(
                    excellent=qt_data.get('excellent', 0.9),
                    good=qt_data.get('good', 0.7),
                    fair=qt_data.get('fair', 0.5),
                    poor=qt_data.get('poor', 0.5)
                )
            
            latency_thresholds = LatencyThresholds()
            if 'latency_thresholds' in quality_data:
                lt_data = quality_data['latency_thresholds']
                latency_thresholds = LatencyThresholds(
                    excellent=lt_data.get('excellent', 50),
                    good=lt_data.get('good', 100),
                    fair=lt_data.get('fair', 200),
                    poor=lt_data.get('poor', 500)
                )
            
            config.quality_monitoring = QualityMonitoringConfig(
                monitoring_interval=quality_data.get('monitoring_interval', 10),
                quality_thresholds=quality_thresholds,
                latency_thresholds=latency_thresholds,
                min_success_rate=quality_data.get('min_success_rate', 0.95)
            )
        
        # Metrics
        if 'metrics' in config_data:
            metrics_data = config_data['metrics']
            config.metrics = MetricsConfig(
                detailed_metrics=metrics_data.get('detailed_metrics', True),
                metrics_buffer_size=metrics_data.get('metrics_buffer_size', 1000),
                aggregation_interval=metrics_data.get('aggregation_interval', 60),
                prometheus_export=metrics_data.get('prometheus_export', True),
                prometheus_port=metrics_data.get('prometheus_port', 9090)
            )
        
        # Reconnection
        if 'reconnection' in config_data:
            reconnect_data = config_data['reconnection']
            config.reconnection = ReconnectionConfig(
                enabled=reconnect_data.get('enabled', True),
                max_attempts=reconnect_data.get('max_attempts', 5),
                exponential_backoff=reconnect_data.get('exponential_backoff', True),
                max_delay=reconnect_data.get('max_delay', 60),
                jitter=reconnect_data.get('jitter', True),
                jitter_percent=reconnect_data.get('jitter_percent', 0.1)
            )
        
        # Resource Management
        if 'resource_management' in config_data:
            resource_data = config_data['resource_management']
            config.resource_management = ResourceManagementConfig(
                auto_cleanup=resource_data.get('auto_cleanup', True),
                cleanup_interval=resource_data.get('cleanup_interval', 300),
                inactive_room_ttl=resource_data.get('inactive_room_ttl', 3600),
                disconnected_participant_ttl=resource_data.get('disconnected_participant_ttl', 120)
            )
        
        # Load Balancing
        if 'load_balancing' in config_data:
            lb_data = config_data['load_balancing']
            weights = lb_data.get('weights', {"primary": 1.0, "secondary": 0.8})
            config.load_balancing = LoadBalancingConfig(
                enabled=lb_data.get('enabled', True),
                algorithm=lb_data.get('algorithm', "least_connections"),
                weights=weights,
                health_check_enabled=lb_data.get('health_check_enabled', True)
            )
        
        # Caching
        if 'caching' in config_data:
            cache_data = config_data['caching']
            config.caching = CachingConfig(
                enabled=cache_data.get('enabled', True),
                room_cache_ttl=cache_data.get('room_cache_ttl', 300),
                participant_cache_ttl=cache_data.get('participant_cache_ttl', 60),
                max_cache_size=cache_data.get('max_cache_size', 1000)
            )
        
        # Logging
        if 'logging' in config_data:
            log_data = config_data['logging']
            config.logging = LoggingConfig(
                level=log_data.get('level', "INFO"),
                structured=log_data.get('structured', True),
                include_metrics=log_data.get('include_metrics', True),
                metrics_log_interval=log_data.get('metrics_log_interval', 60)
            )
        
        return config
    
    def save_config(self, config: PerformanceConfig) -> bool:
        """Сохранение конфигурации в файл."""
        try:
            # Создание директории если не существует
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            config_dict = self._config_to_dict(config)
            
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config_dict, file, default_flow_style=False, allow_unicode=True)
            
            return True
            
        except Exception as e:
            print(f"Error saving config to {self.config_path}: {e}")
            return False
    
    def _config_to_dict(self, config: PerformanceConfig) -> Dict[str, Any]:
        """Преобразование конфигурации в словарь."""
        return {
            'connection_pool': {
                'pool_size': config.connection_pool.pool_size,
                'max_pool_size': config.connection_pool.max_pool_size,
                'health_check_interval': config.connection_pool.health_check_interval,
                'connection_timeout': config.connection_pool.connection_timeout,
                'max_reconnect_attempts': config.connection_pool.max_reconnect_attempts,
                'reconnect_base_delay': config.connection_pool.reconnect_base_delay
            },
            'room_limits': {
                'max_concurrent_rooms': config.room_limits.max_concurrent_rooms,
                'max_participants_per_room': config.room_limits.max_participants_per_room,
                'max_audio_tracks_per_room': config.room_limits.max_audio_tracks_per_room,
                'max_video_tracks_per_room': config.room_limits.max_video_tracks_per_room,
                'empty_room_timeout': config.room_limits.empty_room_timeout,
                'departure_timeout': config.room_limits.departure_timeout
            },
            'audio_optimization': {
                'target_latency_ms': config.audio_optimization.target_latency_ms,
                'buffer_size_ms': config.audio_optimization.buffer_size_ms,
                'jitter_buffer_ms': config.audio_optimization.jitter_buffer_ms,
                'echo_cancellation': config.audio_optimization.echo_cancellation,
                'noise_suppression': config.audio_optimization.noise_suppression,
                'auto_gain_control': config.audio_optimization.auto_gain_control,
                'adaptive_bitrate': config.audio_optimization.adaptive_bitrate,
                'min_bitrate_kbps': config.audio_optimization.min_bitrate_kbps,
                'max_bitrate_kbps': config.audio_optimization.max_bitrate_kbps
            },
            'quality_monitoring': {
                'monitoring_interval': config.quality_monitoring.monitoring_interval,
                'quality_thresholds': {
                    'excellent': config.quality_monitoring.quality_thresholds.excellent,
                    'good': config.quality_monitoring.quality_thresholds.good,
                    'fair': config.quality_monitoring.quality_thresholds.fair,
                    'poor': config.quality_monitoring.quality_thresholds.poor
                },
                'latency_thresholds': {
                    'excellent': config.quality_monitoring.latency_thresholds.excellent,
                    'good': config.quality_monitoring.latency_thresholds.good,
                    'fair': config.quality_monitoring.latency_thresholds.fair,
                    'poor': config.quality_monitoring.latency_thresholds.poor
                },
                'min_success_rate': config.quality_monitoring.min_success_rate
            },
            'metrics': {
                'detailed_metrics': config.metrics.detailed_metrics,
                'metrics_buffer_size': config.metrics.metrics_buffer_size,
                'aggregation_interval': config.metrics.aggregation_interval,
                'prometheus_export': config.metrics.prometheus_export,
                'prometheus_port': config.metrics.prometheus_port
            },
            'reconnection': {
                'enabled': config.reconnection.enabled,
                'max_attempts': config.reconnection.max_attempts,
                'exponential_backoff': config.reconnection.exponential_backoff,
                'max_delay': config.reconnection.max_delay,
                'jitter': config.reconnection.jitter,
                'jitter_percent': config.reconnection.jitter_percent
            },
            'resource_management': {
                'auto_cleanup': config.resource_management.auto_cleanup,
                'cleanup_interval': config.resource_management.cleanup_interval,
                'inactive_room_ttl': config.resource_management.inactive_room_ttl,
                'disconnected_participant_ttl': config.resource_management.disconnected_participant_ttl
            },
            'load_balancing': {
                'enabled': config.load_balancing.enabled,
                'algorithm': config.load_balancing.algorithm,
                'weights': config.load_balancing.weights,
                'health_check_enabled': config.load_balancing.health_check_enabled
            },
            'caching': {
                'enabled': config.caching.enabled,
                'room_cache_ttl': config.caching.room_cache_ttl,
                'participant_cache_ttl': config.caching.participant_cache_ttl,
                'max_cache_size': config.caching.max_cache_size
            },
            'logging': {
                'level': config.logging.level,
                'structured': config.logging.structured,
                'include_metrics': config.logging.include_metrics,
                'metrics_log_interval': config.logging.metrics_log_interval
            }
        }


# Глобальный экземпляр загрузчика конфигурации
_config_loader: Optional[PerformanceConfigLoader] = None
_cached_config: Optional[PerformanceConfig] = None


def get_performance_config(config_path: Optional[str] = None) -> PerformanceConfig:
    """Получение конфигурации производительности."""
    global _config_loader, _cached_config
    
    if _config_loader is None or (config_path and _config_loader.config_path != config_path):
        _config_loader = PerformanceConfigLoader(config_path)
        _cached_config = None
    
    if _cached_config is None:
        _cached_config = _config_loader.load_config()
    
    return _cached_config


def reload_performance_config() -> PerformanceConfig:
    """Перезагрузка конфигурации производительности."""
    global _cached_config
    _cached_config = None
    return get_performance_config()
"""Production-ready centralized logging configuration for Voice AI Agent."""

import logging
import logging.config
import logging.handlers
import sys
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime, UTC
import traceback

from src.config import get_settings


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""
    
    def filter(self, record):
        # Add performance context
        record.timestamp_ms = int(time.time() * 1000)
        record.process_id = os.getpid()
        record.thread_id = record.thread
        return True


class SecurityFilter(logging.Filter):
    """Filter to sanitize sensitive information from logs."""
    
    SENSITIVE_PATTERNS = [
        'api_key', 'secret', 'password', 'token', 'auth',
        'deepgram_api_key', 'openai_api_key', 'cartesia_api_key',
        'livekit_api_secret', 'secret_key'
    ]
    
    def filter(self, record):
        # Sanitize message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern in record.msg.lower():
                    record.msg = record.msg.replace(
                        record.msg[record.msg.lower().find(pattern):],
                        f"{pattern}=***REDACTED***"
                    )
        
        # Sanitize args
        if hasattr(record, 'args') and record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, (str, dict)):
                    arg_str = str(arg).lower()
                    if any(pattern in arg_str for pattern in self.SENSITIVE_PATTERNS):
                        sanitized_args.append("***REDACTED***")
                    else:
                        sanitized_args.append(arg)
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
        
        return True


class StructuredFormatter(logging.Formatter):
    """Custom structured formatter for production logging."""
    
    def format(self, record):
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": getattr(record, 'process_id', os.getpid()),
            "thread_id": getattr(record, 'thread_id', record.thread),
            "timestamp_ms": getattr(record, 'timestamp_ms', int(time.time() * 1000))
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info', 'timestamp_ms', 'process_id', 'thread_id']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class AsyncFileHandler(logging.handlers.RotatingFileHandler):
    """Async-safe file handler for high-performance logging."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffer = []
        self._buffer_size = 100
        self._last_flush = time.time()
        self._flush_interval = 5.0  # 5 seconds
    
    def emit(self, record):
        try:
            # Buffer the record
            self._buffer.append(self.format(record))
            
            # Flush if buffer is full or interval exceeded
            current_time = time.time()
            if (len(self._buffer) >= self._buffer_size or 
                current_time - self._last_flush >= self._flush_interval):
                self._flush_buffer()
                
        except Exception:
            self.handleError(record)
    
    def _flush_buffer(self):
        """Flush buffered log entries to file."""
        if not self._buffer:
            return
        
        try:
            # Write all buffered entries
            for entry in self._buffer:
                if self.shouldRollover(None):
                    self.doRollover()
                
                self.stream.write(entry + self.terminator)
            
            self.stream.flush()
            self._buffer.clear()
            self._last_flush = time.time()
            
        except Exception as e:
            print(f"Error flushing log buffer: {e}", file=sys.stderr)
    
    def close(self):
        """Close handler and flush remaining buffer."""
        self._flush_buffer()
        super().close()


def setup_production_logging(settings=None) -> None:
    """
    Set up production-ready centralized logging configuration.
    
    Args:
        settings: Optional settings object, will use global settings if None
    """
    if settings is None:
        settings = get_settings()
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Determine log level based on environment
    if settings.is_production:
        default_level = "INFO"
        third_party_level = "WARNING"
    elif settings.environment.value == "staging":
        default_level = "INFO"
        third_party_level = "INFO"
    else:
        default_level = "DEBUG"
        third_party_level = "INFO"
    
    log_level = getattr(settings, 'log_level', default_level)
    if hasattr(log_level, 'value'):
        log_level = log_level.value
    
    # Production-optimized logging configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "structured": {
                "()": StructuredFormatter
            },
            "performance": {
                "format": "%(asctime)s - PERF - %(name)s - %(message)s - [%(process_id)d:%(thread_id)d] - %(timestamp_ms)dms",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "filters": {
            "performance": {
                "()": PerformanceFilter
            },
            "security": {
                "()": SecurityFilter
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "structured" if settings.structured_logging else "standard",
                "stream": sys.stdout,
                "filters": ["security", "performance"]
            },
            "file": {
                "()": AsyncFileHandler,
                "level": log_level,
                "formatter": "structured" if settings.structured_logging else "detailed",
                "filename": log_dir / "voice_ai_agent.log",
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 10,
                "encoding": "utf8",
                "filters": ["security", "performance"]
            },
            "error_file": {
                "()": AsyncFileHandler,
                "level": "ERROR",
                "formatter": "structured" if settings.structured_logging else "detailed",
                "filename": log_dir / "voice_ai_agent_errors.log",
                "maxBytes": 20 * 1024 * 1024,  # 20MB
                "backupCount": 5,
                "encoding": "utf8",
                "filters": ["security", "performance"]
            },
            "performance_file": {
                "()": AsyncFileHandler,
                "level": "INFO",
                "formatter": "performance",
                "filename": log_dir / "voice_ai_agent_performance.log",
                "maxBytes": 100 * 1024 * 1024,  # 100MB
                "backupCount": 3,
                "encoding": "utf8",
                "filters": ["performance"]
            },
            "audit_file": {
                "()": AsyncFileHandler,
                "level": "INFO",
                "formatter": "structured",
                "filename": log_dir / "voice_ai_agent_audit.log",
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 20,  # Keep more audit logs
                "encoding": "utf8",
                "filters": ["security", "performance"]
            }
        },
        "loggers": {
            "src": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "src.performance": {
                "level": "INFO",
                "handlers": ["performance_file"],
                "propagate": False
            },
            "src.audit": {
                "level": "INFO",
                "handlers": ["audit_file"],
                "propagate": False
            },
            "src.orchestrator": {
                "level": log_level,
                "handlers": ["console", "file", "error_file", "performance_file"],
                "propagate": False
            },
            "src.clients": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "src.monitoring": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO" if not settings.is_production else "WARNING",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO" if not settings.is_production else "WARNING",
                "handlers": ["file"],
                "propagate": False
            },
            "fastapi": {
                "level": "INFO" if not settings.is_production else "WARNING",
                "handlers": ["console", "file"],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"]
        }
    }
    
    # Add custom file handler if specified
    if hasattr(settings, 'log_file_path') and settings.log_file_path:
        config["handlers"]["custom_file"] = {
            "()": AsyncFileHandler,
            "level": log_level,
            "formatter": "structured" if settings.structured_logging else "detailed",
            "filename": settings.log_file_path,
            "maxBytes": 50 * 1024 * 1024,  # 50MB
            "backupCount": 5,
            "encoding": "utf8",
            "filters": ["security", "performance"]
        }
        config["loggers"]["src"]["handlers"].append("custom_file")
    
    # Production-specific optimizations
    if settings.is_production:
        # Disable console logging in production if not explicitly enabled
        if not os.environ.get('ENABLE_CONSOLE_LOGGING', '').lower() == 'true':
            config["loggers"]["src"]["handlers"] = ["file", "error_file"]
            config["loggers"]["uvicorn"]["handlers"] = ["file"]
            config["loggers"]["uvicorn.error"]["handlers"] = ["file", "error_file"]
        
        # Add syslog handler for production monitoring
        if hasattr(logging.handlers, 'SysLogHandler'):
            config["handlers"]["syslog"] = {
                "class": "logging.handlers.SysLogHandler",
                "level": "ERROR",
                "formatter": "structured",
                "address": "/dev/log" if os.path.exists("/dev/log") else ("localhost", 514),
                "filters": ["security"]
            }
            config["loggers"]["src"]["handlers"].append("syslog")
    
    # Configure logging
    logging.config.dictConfig(config)
    
    # Set up third-party library logging levels
    third_party_loggers = [
        "httpx", "urllib3", "asyncio", "websockets", "aiohttp",
        "deepgram", "openai", "cartesia", "livekit",
        "sqlalchemy", "alembic", "redis", "prometheus_client"
    ]
    
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(third_party_level)
    
    # Special handling for noisy loggers
    logging.getLogger("httpcore").setLevel("WARNING")
    logging.getLogger("httpx._client").setLevel("WARNING")
    logging.getLogger("asyncio.coroutines").setLevel("WARNING")
    
    # Log configuration completion
    logger = logging.getLogger(__name__)
    logger.info(
        "Production logging configuration completed",
        extra={
            "log_level": log_level,
            "structured_logging": getattr(settings, 'structured_logging', True),
            "log_format": getattr(settings, 'log_format', 'json'),
            "environment": settings.environment.value,
            "is_production": settings.is_production,
            "log_handlers": list(config["handlers"].keys())
        }
    )


class PerformanceLogger:
    """Specialized logger for performance metrics."""
    
    def __init__(self):
        self.logger = logging.getLogger("src.performance")
    
    def log_latency(self, operation: str, latency: float, **kwargs):
        """Log latency measurement."""
        self.logger.info(
            f"LATENCY: {operation}",
            extra={
                "operation": operation,
                "latency_ms": latency * 1000,
                "latency_seconds": latency,
                **kwargs
            }
        )
    
    def log_throughput(self, operation: str, count: int, duration: float, **kwargs):
        """Log throughput measurement."""
        throughput = count / duration if duration > 0 else 0
        self.logger.info(
            f"THROUGHPUT: {operation}",
            extra={
                "operation": operation,
                "count": count,
                "duration_seconds": duration,
                "throughput_per_second": throughput,
                **kwargs
            }
        )
    
    def log_resource_usage(self, **kwargs):
        """Log resource usage metrics."""
        self.logger.info(
            "RESOURCE_USAGE",
            extra=kwargs
        )


class AuditLogger:
    """Specialized logger for audit events."""
    
    def __init__(self):
        self.logger = logging.getLogger("src.audit")
    
    def log_call_start(self, call_id: str, caller_number: str, **kwargs):
        """Log call start event."""
        self.logger.info(
            f"CALL_START: {call_id}",
            extra={
                "event": "call_start",
                "call_id": call_id,
                "caller_number": caller_number,
                **kwargs
            }
        )
    
    def log_call_end(self, call_id: str, duration: float, **kwargs):
        """Log call end event."""
        self.logger.info(
            f"CALL_END: {call_id}",
            extra={
                "event": "call_end",
                "call_id": call_id,
                "duration_seconds": duration,
                **kwargs
            }
        )
    
    def log_error(self, error_type: str, error_message: str, **kwargs):
        """Log error event."""
        self.logger.error(
            f"ERROR: {error_type}",
            extra={
                "event": "error",
                "error_type": error_type,
                "error_message": error_message,
                **kwargs
            }
        )


def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance."""
    return PerformanceLogger()


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance."""
    return AuditLogger()
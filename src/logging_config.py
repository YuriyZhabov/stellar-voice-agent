"""Centralized logging configuration with structured JSON format."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.config import Settings
from src.security import SensitiveDataFilter


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id'):
            log_entry["correlation_id"] = record.correlation_id
        
        # Add service name if present
        if hasattr(record, 'service'):
            log_entry["service"] = record.service
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info', 'correlation_id', 'service'
            }:
                log_entry[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        super().__init__()
        self.correlation_id = correlation_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to record if not already present."""
        if not hasattr(record, 'correlation_id') and self.correlation_id:
            record.correlation_id = self.correlation_id
        return True


def setup_logging(settings: Settings) -> None:
    """Set up centralized logging configuration."""
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(formatter)
    
    # Add sensitive data filter to all handlers
    sensitive_filter = SensitiveDataFilter()
    console_handler.addFilter(sensitive_filter)
    
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging system initialized with security filtering",
        extra={
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "environment": settings.environment
        }
    )


def get_logger_with_correlation(name: str, correlation_id: Optional[str] = None) -> logging.Logger:
    """Get logger with correlation ID filter."""
    logger = logging.getLogger(name)
    
    if correlation_id:
        # Remove existing correlation filters
        for filter_obj in logger.filters[:]:
            if isinstance(filter_obj, CorrelationFilter):
                logger.removeFilter(filter_obj)
        
        # Add new correlation filter
        logger.addFilter(CorrelationFilter(correlation_id))
    
    return logger


class LoggerMixin:
    """Mixin class to add logging capabilities with correlation ID support."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)
    
    def get_logger(self, correlation_id: Optional[str] = None) -> logging.Logger:
        """Get logger with optional correlation ID."""
        if correlation_id:
            return get_logger_with_correlation(self._logger.name, correlation_id)
        return self._logger
    
    def log_with_context(
        self,
        level: int,
        message: str,
        correlation_id: Optional[str] = None,
        **extra_fields: Any
    ) -> None:
        """Log message with context and extra fields."""
        logger = self.get_logger(correlation_id)
        logger.log(level, message, extra=extra_fields)
    
    def debug_with_context(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **extra_fields: Any
    ) -> None:
        """Log debug message with context."""
        self.log_with_context(logging.DEBUG, message, correlation_id, **extra_fields)
    
    def info_with_context(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **extra_fields: Any
    ) -> None:
        """Log info message with context."""
        self.log_with_context(logging.INFO, message, correlation_id, **extra_fields)
    
    def warning_with_context(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **extra_fields: Any
    ) -> None:
        """Log warning message with context."""
        self.log_with_context(logging.WARNING, message, correlation_id, **extra_fields)
    
    def error_with_context(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **extra_fields: Any
    ) -> None:
        """Log error message with context."""
        self.log_with_context(logging.ERROR, message, correlation_id, **extra_fields)
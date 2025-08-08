"""
LiveKit Detailed Logging System

Comprehensive logging system for LiveKit operations with structured logging,
error codes, and detailed operation tracking.

Requirements addressed:
- 7.4: Detailed error logging with codes
"""

import json
import logging
import logging.handlers
import sys
import traceback
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4


class LiveKitLogLevel(Enum):
    """LiveKit-specific log levels."""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LiveKitErrorCode(Enum):
    """Standardized error codes for LiveKit operations."""
    
    # Authentication errors (1000-1099)
    AUTH_TOKEN_INVALID = "LK1001"
    AUTH_TOKEN_EXPIRED = "LK1002"
    AUTH_INSUFFICIENT_PERMISSIONS = "LK1003"
    AUTH_API_KEY_INVALID = "LK1004"
    
    # Connection errors (1100-1199)
    CONN_TIMEOUT = "LK1101"
    CONN_REFUSED = "LK1102"
    CONN_LOST = "LK1103"
    CONN_SSL_ERROR = "LK1104"
    
    # API errors (1200-1299)
    API_INVALID_REQUEST = "LK1201"
    API_RATE_LIMITED = "LK1202"
    API_SERVER_ERROR = "LK1203"
    API_NOT_FOUND = "LK1204"
    API_VALIDATION_ERROR = "LK1205"
    
    # Room errors (1300-1399)
    ROOM_NOT_FOUND = "LK1301"
    ROOM_CREATION_FAILED = "LK1302"
    ROOM_FULL = "LK1303"
    ROOM_CLOSED = "LK1304"
    
    # Participant errors (1400-1499)
    PARTICIPANT_NOT_FOUND = "LK1401"
    PARTICIPANT_DISCONNECTED = "LK1402"
    PARTICIPANT_PERMISSION_DENIED = "LK1403"
    
    # Media errors (1500-1599)
    MEDIA_TRACK_FAILED = "LK1501"
    MEDIA_CODEC_UNSUPPORTED = "LK1502"
    MEDIA_QUALITY_POOR = "LK1503"
    
    # SIP errors (1600-1699)
    SIP_TRUNK_UNAVAILABLE = "LK1601"
    SIP_CALL_FAILED = "LK1602"
    SIP_AUTH_FAILED = "LK1603"
    SIP_CODEC_MISMATCH = "LK1604"
    
    # Egress errors (1700-1799)
    EGRESS_START_FAILED = "LK1701"
    EGRESS_STORAGE_ERROR = "LK1702"
    EGRESS_ENCODING_ERROR = "LK1703"
    
    # Ingress errors (1800-1899)
    INGRESS_CREATE_FAILED = "LK1801"
    INGRESS_SOURCE_UNAVAILABLE = "LK1802"
    INGRESS_FORMAT_UNSUPPORTED = "LK1803"
    
    # System errors (1900-1999)
    SYSTEM_RESOURCE_EXHAUSTED = "LK1901"
    SYSTEM_CONFIG_ERROR = "LK1902"
    SYSTEM_HEALTH_CHECK_FAILED = "LK1903"


class LiveKitLogFormatter(logging.Formatter):
    """Custom formatter for LiveKit logs with structured output."""
    
    def __init__(self, include_trace: bool = True):
        super().__init__()
        self.include_trace = include_trace
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add thread/process info if available
        if hasattr(record, 'thread') and record.thread:
            log_data["thread_id"] = record.thread
        if hasattr(record, 'process') and record.process:
            log_data["process_id"] = record.process
        
        # Add LiveKit-specific fields
        if hasattr(record, 'operation_id'):
            log_data["operation_id"] = record.operation_id
        if hasattr(record, 'error_code'):
            log_data["error_code"] = record.error_code
        if hasattr(record, 'service'):
            log_data["service"] = record.service
        if hasattr(record, 'room_name'):
            log_data["room_name"] = record.room_name
        if hasattr(record, 'participant_id'):
            log_data["participant_id"] = record.participant_id
        if hasattr(record, 'latency_ms'):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, 'details'):
            log_data["details"] = record.details
        
        # Add exception info if present
        if record.exc_info and self.include_trace:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class LiveKitLogger:
    """
    Enhanced logger for LiveKit operations with structured logging and error codes.
    """
    
    def __init__(self, name: str, log_level: Union[str, int] = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.operation_stack = []  # Stack of operation IDs for nested operations
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up log handlers."""
        
        # Console handler with structured format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = LiveKitLogFormatter(include_trace=False)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with full details
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "livekit.log",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = LiveKitLogFormatter(include_trace=True)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "livekit_errors.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
    
    def start_operation(self, operation_name: str, **kwargs) -> str:
        """Start a new operation and return operation ID."""
        operation_id = str(uuid4())
        self.operation_stack.append(operation_id)
        
        self.info(
            f"Starting operation: {operation_name}",
            operation_id=operation_id,
            operation_name=operation_name,
            **kwargs
        )
        
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, **kwargs) -> None:
        """End an operation."""
        if operation_id in self.operation_stack:
            self.operation_stack.remove(operation_id)
        
        status = "completed" if success else "failed"
        level = self.info if success else self.error
        
        level(
            f"Operation {status}",
            operation_id=operation_id,
            success=success,
            **kwargs
        )
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        error_code: Optional[LiveKitErrorCode] = None,
        service: Optional[str] = None,
        room_name: Optional[str] = None,
        participant_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        operation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        exc_info: Optional[bool] = None,
        **kwargs
    ) -> None:
        """Log with LiveKit-specific context."""
        
        # Use current operation ID if not provided
        if operation_id is None and self.operation_stack:
            operation_id = self.operation_stack[-1]
        
        # Create extra context
        extra = {
            "operation_id": operation_id,
            "service": service,
            "room_name": room_name,
            "participant_id": participant_id,
            "latency_ms": latency_ms,
            "details": details or kwargs
        }
        
        if error_code:
            extra["error_code"] = error_code.value
        
        # Remove None values
        extra = {k: v for k, v in extra.items() if v is not None}
        
        self.logger.log(level, message, extra=extra, exc_info=exc_info)
    
    def trace(self, message: str, **kwargs) -> None:
        """Log trace message."""
        self._log_with_context(LiveKitLogLevel.TRACE.value, message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(
        self,
        message: str,
        error_code: Optional[LiveKitErrorCode] = None,
        exc_info: bool = True,
        **kwargs
    ) -> None:
        """Log error message with optional error code."""
        self._log_with_context(
            logging.ERROR,
            message,
            error_code=error_code,
            exc_info=exc_info,
            **kwargs
        )
    
    def critical(
        self,
        message: str,
        error_code: Optional[LiveKitErrorCode] = None,
        exc_info: bool = True,
        **kwargs
    ) -> None:
        """Log critical message with optional error code."""
        self._log_with_context(
            logging.CRITICAL,
            message,
            error_code=error_code,
            exc_info=exc_info,
            **kwargs
        )
    
    def log_api_call(
        self,
        method: str,
        endpoint: str,
        status_code: Optional[int] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log API call with standardized format."""
        
        if error:
            self.error(
                f"API call failed: {method} {endpoint}",
                error_code=self._get_api_error_code(status_code),
                details={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "error": error,
                    **kwargs
                },
                latency_ms=latency_ms
            )
        else:
            self.info(
                f"API call successful: {method} {endpoint}",
                details={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    **kwargs
                },
                latency_ms=latency_ms
            )
    
    def log_room_event(
        self,
        event: str,
        room_name: str,
        participant_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log room-related event."""
        self.info(
            f"Room event: {event}",
            service="room",
            room_name=room_name,
            participant_id=participant_id,
            details=kwargs
        )
    
    def log_sip_event(
        self,
        event: str,
        call_id: Optional[str] = None,
        trunk_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log SIP-related event."""
        self.info(
            f"SIP event: {event}",
            service="sip",
            details={
                "call_id": call_id,
                "trunk_name": trunk_name,
                **kwargs
            }
        )
    
    def log_media_event(
        self,
        event: str,
        track_id: Optional[str] = None,
        codec: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log media-related event."""
        self.info(
            f"Media event: {event}",
            service="media",
            details={
                "track_id": track_id,
                "codec": codec,
                **kwargs
            }
        )
    
    def _get_api_error_code(self, status_code: Optional[int]) -> Optional[LiveKitErrorCode]:
        """Map HTTP status code to LiveKit error code."""
        if not status_code:
            return None
        
        mapping = {
            400: LiveKitErrorCode.API_VALIDATION_ERROR,
            401: LiveKitErrorCode.AUTH_TOKEN_INVALID,
            403: LiveKitErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            404: LiveKitErrorCode.API_NOT_FOUND,
            429: LiveKitErrorCode.API_RATE_LIMITED,
            500: LiveKitErrorCode.API_SERVER_ERROR,
            502: LiveKitErrorCode.API_SERVER_ERROR,
            503: LiveKitErrorCode.API_SERVER_ERROR,
            504: LiveKitErrorCode.CONN_TIMEOUT
        }
        
        return mapping.get(status_code)


class LiveKitOperationContext:
    """Context manager for LiveKit operations with automatic logging."""
    
    def __init__(
        self,
        logger: LiveKitLogger,
        operation_name: str,
        service: Optional[str] = None,
        **kwargs
    ):
        self.logger = logger
        self.operation_name = operation_name
        self.service = service
        self.kwargs = kwargs
        self.operation_id = None
        self.start_time = None
    
    def __enter__(self):
        """Enter operation context."""
        self.start_time = datetime.now(UTC)
        self.operation_id = self.logger.start_operation(
            self.operation_name,
            service=self.service,
            **self.kwargs
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit operation context."""
        if self.start_time:
            duration_ms = (datetime.now(UTC) - self.start_time).total_seconds() * 1000
        else:
            duration_ms = None
        
        success = exc_type is None
        
        self.logger.end_operation(
            self.operation_id,
            success=success,
            duration_ms=duration_ms,
            service=self.service
        )
        
        if not success and exc_val:
            self.logger.error(
                f"Operation failed: {self.operation_name}",
                operation_id=self.operation_id,
                service=self.service,
                exc_info=True
            )


# Global logger instances
_loggers: Dict[str, LiveKitLogger] = {}


def get_logger(name: str, level: Union[str, int] = logging.INFO) -> LiveKitLogger:
    """Get or create a LiveKit logger instance."""
    if name not in _loggers:
        _loggers[name] = LiveKitLogger(name, level)
    return _loggers[name]


def setup_logging(
    level: Union[str, int] = logging.INFO,
    log_dir: Optional[str] = None
) -> None:
    """Set up global logging configuration."""
    
    # Set up log directory
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Add custom log level
    logging.addLevelName(LiveKitLogLevel.TRACE.value, "TRACE")
    
    print(f"LiveKit logging configured with level: {level}")


# Convenience function for operation context
def operation_context(
    operation_name: str,
    logger_name: str = "livekit",
    **kwargs
) -> LiveKitOperationContext:
    """Create an operation context."""
    logger = get_logger(logger_name)
    return LiveKitOperationContext(logger, operation_name, **kwargs)
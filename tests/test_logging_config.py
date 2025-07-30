"""Tests for logging configuration system."""

import json
import logging
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock

from src.config import Settings
from src.logging_config import (
    JSONFormatter,
    CorrelationFilter,
    setup_logging,
    get_logger_with_correlation,
    LoggerMixin
)


class TestJSONFormatter:
    """Test JSON formatter functionality."""
    
    def test_basic_formatting(self):
        """Test basic JSON log formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "path"
        assert log_data["function"] == "<module>"
        assert log_data["line"] == 42
        assert "timestamp" in log_data
    
    def test_correlation_id_formatting(self):
        """Test correlation ID inclusion in JSON format."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-123"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["correlation_id"] == "test-correlation-123"
    
    def test_service_name_formatting(self):
        """Test service name inclusion in JSON format."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.service = "test-service"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["service"] == "test-service"
    
    def test_extra_fields_formatting(self):
        """Test extra fields inclusion in JSON format."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.custom_field = "custom_value"
        record.request_id = "req-123"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["custom_field"] == "custom_value"
        assert log_data["request_id"] == "req-123"


class TestCorrelationFilter:
    """Test correlation filter functionality."""
    
    def test_filter_adds_correlation_id(self):
        """Test that filter adds correlation ID to records."""
        correlation_filter = CorrelationFilter("test-correlation-456")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = correlation_filter.filter(record)
        
        assert result is True
        assert record.correlation_id == "test-correlation-456"
    
    def test_filter_preserves_existing_correlation_id(self):
        """Test that filter doesn't override existing correlation ID."""
        correlation_filter = CorrelationFilter("new-correlation")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "existing-correlation"
        
        result = correlation_filter.filter(record)
        
        assert result is True
        assert record.correlation_id == "existing-correlation"
    
    def test_filter_without_correlation_id(self):
        """Test filter behavior without correlation ID."""
        correlation_filter = CorrelationFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = correlation_filter.filter(record)
        
        assert result is True
        assert not hasattr(record, 'correlation_id')
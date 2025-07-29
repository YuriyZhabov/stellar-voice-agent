"""Test health check functionality."""

import pytest
from src.health import check_health


def test_health_check():
    """Test that health check returns expected structure."""
    status = check_health()
    
    assert isinstance(status, dict)
    assert "status" in status
    assert "python_version" in status
    assert "checks" in status
    assert isinstance(status["checks"], dict)


def test_health_check_status():
    """Test that health check returns healthy status."""
    status = check_health()
    
    assert status["status"] == "healthy"
    assert status["checks"]["python"] == "ok"
    assert status["checks"]["imports"] == "ok"
"""
Integration tests for enhanced webhook endpoints.
"""

import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.webhooks import setup_webhook_routes
from src.orchestrator import CallOrchestrator


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orchestrator = AsyncMock(spec=CallOrchestrator)
    orchestrator.handle_call_start = AsyncMock()
    orchestrator.handle_call_end = AsyncMock()
    return orchestrator


@pytest.fixture
def app_with_webhooks(mock_orchestrator):
    """Create FastAPI app with webhook routes."""
    app = FastAPI()
    
    with patch('src.webhooks.get_settings') as mock_settings, \
         patch('src.webhooks.get_metrics_collector') as mock_metrics:
        
        mock_settings.return_value.livekit_webhook_secret = "test_secret"
        mock_settings.return_value.secret_key = "fallback_secret"
        mock_metrics.return_value = MagicMock()
        
        setup_webhook_routes(app, mock_orchestrator)
    
    return app


@pytest.fixture
def client(app_with_webhooks):
    """Create test client."""
    return TestClient(app_with_webhooks)


class TestWebhookEndpoints:
    """Test webhook endpoints."""
    
    def test_webhook_health_endpoint(self, client):
        """Test webhook health endpoint."""
        response = client.get("/webhooks/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "statistics" in data
        assert "event_processor_running" in data
    
    def test_active_calls_endpoint(self, client):
        """Test active calls endpoint."""
        response = client.get("/webhooks/calls")
        
        assert response.status_code == 200
        data = response.json()
        assert "active_calls" in data
        assert "total_count" in data
        assert "timestamp" in data
        assert isinstance(data["active_calls"], list)
    
    def test_call_info_endpoint(self, client):
        """Test call info endpoint."""
        response = client.get("/webhooks/calls/nonexistent_call")
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Call nonexistent_call not found" in data["error"]
    
    def test_cleanup_endpoint(self, client):
        """Test cleanup endpoint."""
        response = client.post("/webhooks/cleanup?max_age_hours=24")
        
        assert response.status_code == 200
        data = response.json()
        assert "cleaned_calls" in data
        assert "max_age_hours" in data
        assert "timestamp" in data
    
    def test_system_health_endpoint(self, client):
        """Test enhanced system health endpoint."""
        with patch('src.health.check_health') as mock_health:
            mock_health.return_value = {"status": "healthy", "components": {}}
            
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "webhook_handler" in data
            assert "status" in data["webhook_handler"]
    
    def test_livekit_webhook_endpoint_invalid_json(self, client):
        """Test LiveKit webhook endpoint with invalid JSON."""
        response = client.post(
            "/webhooks/livekit",
            content="invalid json",
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]
    
    def test_livekit_webhook_endpoint_valid_event(self, client):
        """Test LiveKit webhook endpoint with valid event."""
        event_data = {
            "event": "room_started",
            "room": {
                "name": "voice-ai-call-test123",
                "sid": "RM_test123",
                "metadata": json.dumps({
                    "caller_number": "+1234567890"
                })
            }
        }
        
        response = client.post(
            "/webhooks/livekit",
            json=event_data,
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "event_id" in data
        assert "timestamp" in data
        assert "processing_time" in data
    
    def test_livekit_webhook_with_signature(self, client):
        """Test LiveKit webhook with signature validation."""
        import hmac
        import hashlib
        
        event_data = {
            "event": "room_started",
            "room": {
                "name": "voice-ai-call-test123",
                "sid": "RM_test123"
            }
        }
        
        payload = json.dumps(event_data).encode()
        signature = hmac.new(
            "test_secret".encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        response = client.post(
            "/webhooks/livekit",
            json=event_data,
            headers={
                "content-type": "application/json",
                "x-livekit-signature": f"sha256={signature}"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
    
    def test_livekit_webhook_invalid_signature(self, client):
        """Test LiveKit webhook with invalid signature."""
        event_data = {
            "event": "room_started",
            "room": {
                "name": "voice-ai-call-test123",
                "sid": "RM_test123"
            }
        }
        
        response = client.post(
            "/webhooks/livekit",
            json=event_data,
            headers={
                "content-type": "application/json",
                "x-livekit-signature": "sha256=invalid_signature"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__])
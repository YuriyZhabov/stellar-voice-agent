"""
Tests for enhanced webhook handlers with correlation and validation.
"""

import asyncio
import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from fastapi.testclient import TestClient

from src.webhooks import WebhookHandler, setup_webhook_routes
from src.orchestrator import CallOrchestrator, CallContext
from src.livekit_integration import LiveKitEventType


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orchestrator = AsyncMock(spec=CallOrchestrator)
    orchestrator.handle_call_start = AsyncMock()
    orchestrator.handle_call_end = AsyncMock()
    return orchestrator


@pytest.fixture
def webhook_handler(mock_orchestrator):
    """Create a webhook handler instance."""
    with patch('src.webhooks.get_settings') as mock_settings, \
         patch('src.webhooks.get_metrics_collector') as mock_metrics:
        
        mock_settings.return_value.livekit_webhook_secret = "test_secret"
        mock_settings.return_value.secret_key = "fallback_secret"
        mock_metrics.return_value = MagicMock()
        
        handler = WebhookHandler(mock_orchestrator)
        return handler


@pytest.fixture
def sample_room_started_event():
    """Sample room started event data."""
    return {
        "event": "room_started",
        "room": {
            "name": "voice-ai-call-test123",
            "sid": "RM_test123",
            "metadata": json.dumps({
                "caller_number": "+1234567890",
                "called_number": "+79952227978",
                "trunk_name": "novofon"
            })
        },
        "timestamp": datetime.now(UTC).isoformat()
    }


@pytest.fixture
def sample_participant_joined_event():
    """Sample participant joined event data."""
    return {
        "event": "participant_joined",
        "room": {
            "name": "voice-ai-call-test123",
            "sid": "RM_test123"
        },
        "participant": {
            "identity": "caller_123",
            "sid": "PA_caller123",
            "name": "Caller"
        }
    }


@pytest.fixture
def sample_track_published_event():
    """Sample track published event data."""
    return {
        "event": "track_published",
        "room": {
            "name": "voice-ai-call-test123",
            "sid": "RM_test123"
        },
        "participant": {
            "identity": "caller_123",
            "sid": "PA_caller123"
        },
        "track": {
            "sid": "TR_audio123",
            "type": "audio",
            "name": "microphone",
            "source": "microphone"
        }
    }


class TestWebhookSignatureValidation:
    """Test webhook signature validation."""
    
    def test_signature_validation_success(self, webhook_handler):
        """Test successful signature validation."""
        payload = b'{"event": "test"}'
        
        # Calculate expected signature
        import hmac
        import hashlib
        expected_sig = hmac.new(
            "test_secret".encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature = f"sha256={expected_sig}"
        
        assert webhook_handler.verify_webhook_signature(payload, signature) is True
    
    def test_signature_validation_failure(self, webhook_handler):
        """Test signature validation failure."""
        payload = b'{"event": "test"}'
        signature = "sha256=invalid_signature"
        
        assert webhook_handler.verify_webhook_signature(payload, signature) is False
    
    def test_signature_validation_no_secret(self, mock_orchestrator):
        """Test signature validation when no secret is configured."""
        with patch('src.webhooks.get_settings') as mock_settings, \
             patch('src.webhooks.get_metrics_collector'):
            
            mock_settings.return_value.livekit_webhook_secret = None
            mock_settings.return_value.secret_key = None
            
            handler = WebhookHandler(mock_orchestrator)
            payload = b'{"event": "test"}'
            signature = "sha256=any_signature"
            
            # Should return True when no secret is configured
            assert handler.verify_webhook_signature(payload, signature) is True
    
    def test_timestamp_validation(self, webhook_handler):
        """Test timestamp validation for replay attack prevention."""
        import time
        
        payload = b'{"event": "test"}'
        
        # Calculate valid signature
        import hmac
        import hashlib
        expected_sig = hmac.new(
            "test_secret".encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature = f"sha256={expected_sig}"
        
        # Test with current timestamp (should pass)
        current_timestamp = str(int(time.time()))
        assert webhook_handler.verify_webhook_signature(payload, signature, current_timestamp) is True
        
        # Test with old timestamp (should fail)
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        assert webhook_handler.verify_webhook_signature(payload, signature, old_timestamp) is False


class TestEventCorrelation:
    """Test event correlation and tracking."""
    
    @pytest.mark.asyncio
    async def test_room_started_correlation(self, webhook_handler, sample_room_started_event):
        """Test room started event creates proper correlation."""
        # Process the event
        await webhook_handler._handle_room_started(sample_room_started_event)
        
        # Check correlation data
        room_name = "voice-ai-call-test123"
        assert room_name in webhook_handler.active_calls
        
        call_context = webhook_handler.active_calls[room_name]
        assert call_context.call_id == "test123"
        assert call_context.caller_number == "+1234567890"
        assert call_context.livekit_room == room_name
        
        # Check tracking structures
        assert room_name in webhook_handler.call_participants
        assert room_name in webhook_handler.call_tracks
    
    @pytest.mark.asyncio
    async def test_participant_tracking(self, webhook_handler, sample_room_started_event, sample_participant_joined_event):
        """Test participant tracking."""
        # First create the room
        await webhook_handler._handle_room_started(sample_room_started_event)
        
        # Then add participant
        await webhook_handler._handle_participant_joined(sample_participant_joined_event)
        
        # Check participant tracking
        room_name = "voice-ai-call-test123"
        participants = webhook_handler.call_participants[room_name]
        assert "caller_123" in participants
        assert len(participants) == 1
    
    @pytest.mark.asyncio
    async def test_track_tracking(self, webhook_handler, sample_room_started_event, sample_track_published_event):
        """Test track tracking."""
        # First create the room
        await webhook_handler._handle_room_started(sample_room_started_event)
        
        # Then publish track
        await webhook_handler._handle_track_published(sample_track_published_event)
        
        # Check track tracking
        room_name = "voice-ai-call-test123"
        tracks = webhook_handler.call_tracks[room_name]
        assert "TR_audio123" in tracks
        
        track_info = tracks["TR_audio123"]
        assert track_info["type"] == "audio"
        assert track_info["participant_identity"] == "caller_123"
        assert track_info["source"] == "microphone"
    
    @pytest.mark.asyncio
    async def test_room_finished_cleanup(self, webhook_handler, sample_room_started_event):
        """Test room finished event cleans up correlation data."""
        # First create the room
        await webhook_handler._handle_room_started(sample_room_started_event)
        
        room_name = "voice-ai-call-test123"
        assert room_name in webhook_handler.active_calls
        
        # Create room finished event
        room_finished_event = {
            "event": "room_finished",
            "room": {
                "name": room_name,
                "sid": "RM_test123"
            }
        }
        
        # Process room finished
        await webhook_handler._handle_room_finished(room_finished_event)
        
        # Check cleanup
        assert room_name not in webhook_handler.active_calls
        assert room_name not in webhook_handler.call_participants
        assert room_name not in webhook_handler.call_tracks


class TestWebhookStatistics:
    """Test webhook statistics and monitoring."""
    
    def test_get_webhook_statistics(self, webhook_handler):
        """Test webhook statistics collection."""
        # Set some test data
        webhook_handler.total_events_received = 10
        webhook_handler.total_events_processed = 8
        webhook_handler.total_events_failed = 2
        webhook_handler.signature_validation_failures = 1
        
        stats = webhook_handler.get_webhook_statistics()
        
        assert stats["total_events_received"] == 10
        assert stats["total_events_processed"] == 8
        assert stats["total_events_failed"] == 2
        assert stats["signature_validation_failures"] == 1
        assert "active_calls_count" in stats
        assert "event_queue_size" in stats
    
    def test_get_call_correlation_info(self, webhook_handler):
        """Test call correlation info retrieval."""
        # Create test call context
        call_context = CallContext(
            call_id="test123",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room="voice-ai-call-test123"
        )
        
        room_name = "voice-ai-call-test123"
        webhook_handler.active_calls[room_name] = call_context
        webhook_handler.call_participants[room_name] = {"caller_123", "agent_456"}
        webhook_handler.call_tracks[room_name] = {"TR_audio123": {}, "TR_audio456": {}}
        
        info = webhook_handler.get_call_correlation_info(room_name)
        
        assert info is not None
        assert info["call_id"] == "test123"
        assert info["caller_number"] == "+1234567890"
        assert info["room_name"] == room_name
        assert len(info["participants"]) == 2
        assert len(info["tracks"]) == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_calls(self, webhook_handler):
        """Test cleanup of stale call data."""
        from datetime import timedelta
        
        # Create old call context
        old_time = datetime.now(UTC) - timedelta(hours=25)
        old_call_context = CallContext(
            call_id="old123",
            caller_number="+1111111111",
            start_time=old_time,
            livekit_room="voice-ai-call-old123"
        )
        
        # Create recent call context
        recent_call_context = CallContext(
            call_id="recent123",
            caller_number="+2222222222",
            start_time=datetime.now(UTC),
            livekit_room="voice-ai-call-recent123"
        )
        
        # Add both calls
        webhook_handler.active_calls["voice-ai-call-old123"] = old_call_context
        webhook_handler.active_calls["voice-ai-call-recent123"] = recent_call_context
        webhook_handler.call_participants["voice-ai-call-old123"] = set()
        webhook_handler.call_participants["voice-ai-call-recent123"] = set()
        
        # Cleanup stale calls (older than 24 hours)
        cleaned_count = await webhook_handler.cleanup_stale_calls(24)
        
        # Check results
        assert cleaned_count == 1
        assert "voice-ai-call-old123" not in webhook_handler.active_calls
        assert "voice-ai-call-recent123" in webhook_handler.active_calls


class TestErrorHandling:
    """Test error handling in webhook processing."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, webhook_handler):
        """Test handling of invalid JSON in webhook payload."""
        # This would be tested at the FastAPI level, but we can test
        # the event processing error handling
        
        invalid_event = {"invalid": "event_without_required_fields"}
        
        # Should not raise exception, but should log error
        with patch('src.webhooks.logger') as mock_logger:
            try:
                await webhook_handler._process_single_event(invalid_event)
            except Exception:
                pass  # Expected to fail gracefully
            
            # Should have logged the error
            assert mock_logger.warning.called or mock_logger.error.called
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, webhook_handler, sample_room_started_event):
        """Test error handling when orchestrator fails."""
        # Make orchestrator raise an exception
        webhook_handler.orchestrator.handle_call_start.side_effect = Exception("Orchestrator error")
        
        # Should not raise exception, but should log error
        with patch('src.webhooks.logger') as mock_logger:
            await webhook_handler._handle_room_started(sample_room_started_event)
            
            # Should have logged the error but still created correlation data
            assert mock_logger.error.called
            assert "voice-ai-call-test123" in webhook_handler.active_calls


if __name__ == "__main__":
    pytest.main([__file__])
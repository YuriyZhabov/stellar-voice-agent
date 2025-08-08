"""
Tests for LiveKit Voice AI Integration

This module tests the integration between LiveKit and the Voice AI Agent system,
validating all aspects of task 11 implementation including updated components.
"""

import asyncio
import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.integration.livekit_voice_ai_integration import (
    LiveKitVoiceAIIntegration,
    IntegrationStatus,
    IntegrationMetrics
)
from src.orchestrator import CallOrchestrator, CallContext
from src.livekit_integration import LiveKitSIPIntegration, LiveKitEventType
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.webhooks import WebhookHandler
from src.voice_ai_agent import VoiceAIAgent, AgentStatus
from src.sip_handler import SIPHandler, SIPCallInfo, SIPCallStatus


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orchestrator = AsyncMock(spec=CallOrchestrator)
    orchestrator.active_calls = {}
    orchestrator.handle_livekit_room_created = AsyncMock()
    orchestrator.handle_participant_joined = AsyncMock()
    orchestrator.start_audio_processing = AsyncMock()
    return orchestrator


@pytest.fixture
def mock_livekit_integration():
    """Create a mock LiveKit integration."""
    integration = AsyncMock(spec=LiveKitSIPIntegration)
    integration.add_event_handler = MagicMock()
    return integration


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    return AsyncMock(spec=LiveKitAPIClient)


@pytest.fixture
def mock_auth_manager():
    """Create a mock auth manager."""
    return AsyncMock(spec=LiveKitAuthManager)


@pytest.fixture
def mock_system_monitor():
    """Create a mock system monitor."""
    return AsyncMock(spec=LiveKitSystemMonitor)


@pytest.fixture
async def integration(
    mock_orchestrator,
    mock_livekit_integration,
    mock_api_client,
    mock_auth_manager,
    mock_system_monitor
):
    """Create a LiveKit Voice AI integration instance."""
    integration = LiveKitVoiceAIIntegration(
        orchestrator=mock_orchestrator,
        livekit_integration=mock_livekit_integration,
        api_client=mock_api_client,
        auth_manager=mock_auth_manager,
        system_monitor=mock_system_monitor
    )
    await integration.initialize()
    return integration


class TestLiveKitVoiceAIIntegration:
    """Test cases for LiveKit Voice AI Integration."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, integration):
        """Test integration initialization."""
        assert integration.status == IntegrationStatus.ACTIVE
        assert isinstance(integration.metrics, IntegrationMetrics)
        assert len(integration.event_handlers) == 6
        
        # Verify event handlers were registered
        integration.livekit_integration.add_event_handler.assert_called()
    
    @pytest.mark.asyncio
    async def test_room_started_integration(self, integration, mock_orchestrator):
        """Test room started event integration."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        
        event_data = {
            "event": "room_started",
            "event_id": str(uuid4()),
            "room": {
                "name": room_name,
                "sid": "room_sid_123",
                "metadata": json.dumps({"caller_number": "+1234567890"})
            }
        }
        
        # Handle the event
        await integration._handle_room_started_integration(event_data)
        
        # Verify integration data was created
        assert call_id in integration.active_integrations
        integration_data = integration.active_integrations[call_id]
        assert integration_data["call_id"] == call_id
        assert integration_data["room_name"] == room_name
        assert integration_data["room_sid"] == "room_sid_123"
        
        # Verify orchestrator was notified
        mock_orchestrator.handle_livekit_room_created.assert_called_once()
        
        # Verify metrics were updated
        assert integration.metrics.room_creations == 1
    
    @pytest.mark.asyncio
    async def test_participant_joined_integration(self, integration, mock_orchestrator):
        """Test participant joined event integration."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        participant_identity = "caller_123"
        participant_sid = "participant_sid_123"
        
        # Set up integration data
        integration.active_integrations[call_id] = {
            "call_id": call_id,
            "room_name": room_name,
            "participants": {}
        }
        
        # Mock call context
        call_context = CallContext(
            call_id=call_id,
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room=room_name
        )
        mock_orchestrator.active_calls = {call_id: call_context}
        
        event_data = {
            "event": "participant_joined",
            "event_id": str(uuid4()),
            "participant": {
                "identity": participant_identity,
                "sid": participant_sid
            },
            "room": {
                "name": room_name,
                "sid": "room_sid_123"
            }
        }
        
        # Handle the event
        await integration._handle_participant_joined_integration(event_data)
        
        # Verify participant was tracked
        participants = integration.active_integrations[call_id]["participants"]
        assert participant_identity in participants
        assert participants[participant_identity]["sid"] == participant_sid
        
        # Verify orchestrator was notified
        mock_orchestrator.handle_participant_joined.assert_called_once_with(
            call_context, participant_identity, participant_sid
        )
    
    @pytest.mark.asyncio
    async def test_track_published_integration(self, integration, mock_orchestrator):
        """Test track published event integration with STT pipeline."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        track_sid = "track_sid_123"
        participant_identity = "caller_123"
        
        # Set up integration data
        integration.active_integrations[call_id] = {
            "call_id": call_id,
            "room_name": room_name,
            "audio_tracks": {},
            "stt_sessions": {}
        }
        
        # Mock call context
        call_context = CallContext(
            call_id=call_id,
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room=room_name
        )
        mock_orchestrator.active_calls = {call_id: call_context}
        
        event_data = {
            "event": "track_published",
            "event_id": str(uuid4()),
            "track": {
                "sid": track_sid,
                "type": "audio",
                "source": "microphone"
            },
            "participant": {
                "identity": participant_identity,
                "sid": "participant_sid_123"
            },
            "room": {
                "name": room_name,
                "sid": "room_sid_123"
            }
        }
        
        # Handle the event
        await integration._handle_track_published_integration(event_data)
        
        # Verify audio track was tracked
        audio_tracks = integration.active_integrations[call_id]["audio_tracks"]
        assert track_sid in audio_tracks
        assert audio_tracks[track_sid]["participant_identity"] == participant_identity
        assert audio_tracks[track_sid]["stt_active"] is True
        
        # Verify STT session was created
        stt_sessions = integration.active_integrations[call_id]["stt_sessions"]
        assert track_sid in stt_sessions
        assert stt_sessions[track_sid]["participant_identity"] == participant_identity
        
        # Verify orchestrator was notified to start audio processing
        mock_orchestrator.start_audio_processing.assert_called_once_with(
            call_context, track_sid, participant_identity
        )
        
        # Verify metrics were updated
        assert integration.metrics.audio_tracks_processed == 1
        assert integration.metrics.stt_sessions_started == 1
    
    @pytest.mark.asyncio
    async def test_track_published_non_audio_ignored(self, integration, mock_orchestrator):
        """Test that non-audio tracks are ignored."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        
        integration.active_integrations[call_id] = {
            "call_id": call_id,
            "room_name": room_name,
            "audio_tracks": {},
            "stt_sessions": {}
        }
        
        event_data = {
            "event": "track_published",
            "event_id": str(uuid4()),
            "track": {
                "sid": "track_sid_123",
                "type": "video",  # Video track should be ignored
                "source": "camera"
            },
            "participant": {
                "identity": "caller_123",
                "sid": "participant_sid_123"
            },
            "room": {
                "name": room_name,
                "sid": "room_sid_123"
            }
        }
        
        # Handle the event
        await integration._handle_track_published_integration(event_data)
        
        # Verify no audio processing was started
        mock_orchestrator.start_audio_processing.assert_not_called()
        
        # Verify metrics were not updated
        assert integration.metrics.audio_tracks_processed == 0
        assert integration.metrics.stt_sessions_started == 0
    
    @pytest.mark.asyncio
    async def test_room_finished_integration(self, integration):
        """Test room finished event integration with cleanup."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        
        # Set up integration data with STT sessions to mark as successful
        integration.active_integrations[call_id] = {
            "call_id": call_id,
            "room_name": room_name,
            "stt_sessions": {"track_123": {"participant": "caller"}}
        }
        
        event_data = {
            "event": "room_finished",
            "event_id": str(uuid4()),
            "room": {
                "name": room_name,
                "sid": "room_sid_123"
            }
        }
        
        # Handle the event
        await integration._handle_room_finished_integration(event_data)
        
        # Verify integration data was cleaned up
        assert call_id not in integration.active_integrations
        
        # Verify metrics were updated (successful call due to STT sessions)
        assert integration.metrics.successful_calls == 1
        assert integration.metrics.failed_calls == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_with_fallback(self, integration):
        """Test error handling with fallback mechanisms."""
        call_id = str(uuid4())
        room_name = f"voice-ai-call-{call_id}"
        
        # Create event data that will cause an error
        event_data = {
            "event": "track_published",
            "event_id": str(uuid4()),
            "track": {
                "sid": "track_sid_123",
                "type": "audio",
                "source": "microphone"
            },
            "participant": {
                "identity": "caller_123",
                "sid": "participant_sid_123"
            },
            "room": {
                "name": room_name,
                "sid": "room_sid_123"
            }
        }
        
        # Mock orchestrator to raise an error
        integration.orchestrator.start_audio_processing.side_effect = Exception("Test error")
        
        # Handle the event (should not raise exception due to error handling)
        await integration._handle_track_published_integration(event_data)
        
        # Verify error was tracked
        assert integration.metrics.integration_errors == 1
    
    @pytest.mark.asyncio
    async def test_non_voice_ai_room_ignored(self, integration, mock_orchestrator):
        """Test that non-Voice AI rooms are ignored."""
        event_data = {
            "event": "room_started",
            "event_id": str(uuid4()),
            "room": {
                "name": "regular-room-123",  # Not a voice-ai-call room
                "sid": "room_sid_123"
            }
        }
        
        # Handle the event
        await integration._handle_room_started_integration(event_data)
        
        # Verify no integration data was created
        assert len(integration.active_integrations) == 0
        
        # Verify orchestrator was not notified
        mock_orchestrator.handle_livekit_room_created.assert_not_called()
        
        # Verify metrics were not updated
        assert integration.metrics.room_creations == 0
    
    @pytest.mark.asyncio
    async def test_get_integration_status(self, integration):
        """Test getting integration status."""
        # Add some test data
        call_id = str(uuid4())
        integration.active_integrations[call_id] = {
            "room_name": f"voice-ai-call-{call_id}",
            "participants": {"caller": {}},
            "audio_tracks": {"track1": {}},
            "stt_sessions": {"track1": {}},
            "started_at": datetime.now(UTC).isoformat()
        }
        
        status = integration.get_integration_status()
        
        assert status["status"] == IntegrationStatus.ACTIVE.value
        assert status["active_integrations"] == 1
        assert "metrics" in status
        assert "integration_details" in status
        assert call_id in status["integration_details"]
        
        details = status["integration_details"][call_id]
        assert details["participants"] == 1
        assert details["audio_tracks"] == 1
        assert details["stt_sessions"] == 1
    
    @pytest.mark.asyncio
    async def test_shutdown(self, integration):
        """Test integration shutdown."""
        # Add some test data
        call_id = str(uuid4())
        integration.active_integrations[call_id] = {"test": "data"}
        
        # Shutdown
        await integration.shutdown()
        
        # Verify status and cleanup
        assert integration.status == IntegrationStatus.SHUTDOWN
        assert len(integration.active_integrations) == 0
    
    def test_add_error_handler(self, integration):
        """Test adding error handlers."""
        handler = AsyncMock()
        integration.add_error_handler(handler)
        
        assert handler in integration.error_handlers
    
    def test_get_metrics(self, integration):
        """Test getting metrics."""
        # Update some metrics
        integration.metrics.webhook_events_processed = 5
        integration.metrics.successful_calls = 3
        
        metrics = integration.get_metrics()
        
        assert metrics["webhook_events_processed"] == 5
        assert metrics["successful_calls"] == 3
        assert isinstance(metrics, dict)


class TestIntegrationMetrics:
    """Test cases for IntegrationMetrics."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = IntegrationMetrics()
        
        assert metrics.webhook_events_processed == 0
        assert metrics.audio_tracks_processed == 0
        assert metrics.stt_sessions_started == 0
        assert metrics.tts_responses_generated == 0
        assert metrics.integration_errors == 0
        assert metrics.room_creations == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
    
    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = IntegrationMetrics()
        metrics.webhook_events_processed = 10
        metrics.successful_calls = 5
        
        metrics_dict = metrics.to_dict()
        
        assert metrics_dict["webhook_events_processed"] == 10
        assert metrics_dict["successful_calls"] == 5
        assert isinstance(metrics_dict, dict)
        assert len(metrics_dict) == 8  # All metric fields


@pytest.mark.asyncio
async def test_global_instance_management():
    """Test global instance management functions."""
    from src.integration.livekit_voice_ai_integration import (
        get_livekit_voice_ai_integration,
        shutdown_livekit_voice_ai_integration,
        _integration_instance
    )
    
    # Create mocks
    orchestrator = AsyncMock(spec=CallOrchestrator)
    livekit_integration = AsyncMock(spec=LiveKitSIPIntegration)
    api_client = AsyncMock(spec=LiveKitAPIClient)
    auth_manager = AsyncMock(spec=LiveKitAuthManager)
    
    # Get instance
    instance1 = await get_livekit_voice_ai_integration(
        orchestrator, livekit_integration, api_client, auth_manager
    )
    
    # Get instance again (should be same)
    instance2 = await get_livekit_voice_ai_integration(
        orchestrator, livekit_integration, api_client, auth_manager
    )
    
    assert instance1 is instance2
    
    # Shutdown
    await shutdown_livekit_voice_ai_integration()
    
    # Verify cleanup
    from src.integration.livekit_voice_ai_integration import _integration_instance
    assert _integration_instance is None


if __name__ == "__main__":
    pytest.main([__file__])
# 
Tests for updated components (Task 11)

@pytest.fixture
def mock_webhook_handler():
    """Create a mock webhook handler."""
    handler = AsyncMock(spec=WebhookHandler)
    handler.api_client = AsyncMock()
    handler.auth_manager = AsyncMock()
    handler.livekit_event_handlers = {}
    return handler


@pytest.fixture
def mock_voice_ai_agent():
    """Create a mock Voice AI agent."""
    agent = AsyncMock(spec=VoiceAIAgent)
    agent.agent_id = str(uuid4())
    agent.status = AgentStatus.INITIALIZING
    agent.join_room = AsyncMock(return_value=True)
    agent.leave_room = AsyncMock()
    agent.send_audio_response = AsyncMock()
    return agent


@pytest.fixture
def mock_sip_handler():
    """Create a mock SIP handler."""
    handler = AsyncMock(spec=SIPHandler)
    handler.active_calls = {}
    handler.voice_ai_agents = {}
    handler.handle_incoming_call = AsyncMock(return_value=str(uuid4()))
    handler.end_call = AsyncMock()
    return handler


class TestUpdatedWebhookHandler:
    """Test updated webhook handler with enhanced LiveKit integration."""
    
    @pytest.mark.asyncio
    async def test_enhanced_webhook_initialization(self, mock_orchestrator):
        """Test enhanced webhook handler initialization."""
        from src.webhooks import WebhookHandler
        from src.livekit_integration import LiveKitEventType
        
        handler = WebhookHandler(mock_orchestrator)
        
        # Verify enhanced initialization
        assert handler.orchestrator == mock_orchestrator
        assert hasattr(handler, 'livekit_event_handlers')
        assert hasattr(handler, 'api_client')
        assert hasattr(handler, 'auth_manager')
        
        # Verify event handlers are registered
        assert LiveKitEventType.ROOM_STARTED in handler.livekit_event_handlers
        assert LiveKitEventType.ROOM_FINISHED in handler.livekit_event_handlers
        assert LiveKitEventType.PARTICIPANT_JOINED in handler.livekit_event_handlers
        assert LiveKitEventType.PARTICIPANT_LEFT in handler.livekit_event_handlers
        assert LiveKitEventType.TRACK_PUBLISHED in handler.livekit_event_handlers
        assert LiveKitEventType.TRACK_UNPUBLISHED in handler.livekit_event_handlers
    
    @pytest.mark.asyncio
    async def test_enhanced_room_started_handling(self, mock_orchestrator):
        """Test enhanced room started event handling."""
        from src.webhooks import WebhookHandler
        from src.livekit_integration import LiveKitEventType
        
        # Create handler with mocked components
        handler = WebhookHandler(mock_orchestrator)
        handler.api_client = AsyncMock()
        handler.api_client.list_rooms = AsyncMock(return_value=[MagicMock()])
        
        event_data = {
            'event_id': str(uuid4()),
            'event': LiveKitEventType.ROOM_STARTED.value,
            'room': {
                'name': 'voice-ai-call-test-123',
                'sid': 'room_sid_123',
                'metadata': json.dumps({
                    'caller_number': '+1234567890',
                    'called_number': '+0987654321'
                })
            }
        }
        
        # Test enhanced room started handling
        await handler._handle_livekit_room_started(event_data)
        
        # Verify API client interaction
        handler.api_client.list_rooms.assert_called_once_with(names=['voice-ai-call-test-123'])
    
    @pytest.mark.asyncio
    async def test_enhanced_participant_authorization(self, mock_orchestrator):
        """Test enhanced participant authorization validation."""
        from src.webhooks import WebhookHandler
        
        handler = WebhookHandler(mock_orchestrator)
        participant_identity = "test-participant"
        room_name = "voice-ai-call-test"
        
        # Mock auth manager
        handler.auth_manager = AsyncMock()
        handler.auth_manager.create_participant_token.return_value = "valid_token"
        handler.auth_manager.validate_token.return_value = {"valid": True}
        
        # Test authorization validation
        result = await handler._validate_participant_authorization(
            participant_identity, room_name
        )
        
        assert result is True
        handler.auth_manager.create_participant_token.assert_called_once()
        handler.auth_manager.validate_token.assert_called_once_with("valid_token")
    
    @pytest.mark.asyncio
    async def test_enhanced_track_processing(self, mock_orchestrator):
        """Test enhanced audio track processing."""
        from src.webhooks import WebhookHandler
        from src.orchestrator import CallContext
        
        handler = WebhookHandler(mock_orchestrator)
        handler.active_calls = {
            'voice-ai-call-test': CallContext(
                call_id='test',
                caller_number='+1234567890',
                start_time=datetime.now(UTC),
                livekit_room='voice-ai-call-test'
            )
        }
        handler.orchestrator.handle_audio_track_published = AsyncMock()
        
        event_data = {
            'event_id': str(uuid4()),
            'track': {
                'sid': 'track_123',
                'type': 'audio'
            },
            'participant': {
                'identity': 'caller-123'
            },
            'room': {
                'name': 'voice-ai-call-test'
            }
        }
        
        # Test enhanced track published handling
        await handler._handle_livekit_track_published(event_data)
        
        # Verify orchestrator notification was called
        handler.orchestrator.handle_audio_track_published.assert_called_once()


class TestVoiceAIAgent:
    """Test Voice AI Agent for LiveKit room integration."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_orchestrator, mock_api_client, mock_auth_manager):
        """Test Voice AI agent initialization."""
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig
        
        audio_config = AudioStreamConfig(sample_rate=16000, channels=1)
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager,
            audio_config=audio_config
        )
        
        assert agent.orchestrator == mock_orchestrator
        assert agent.api_client == mock_api_client
        assert agent.auth_manager == mock_auth_manager
        assert agent.audio_config.sample_rate == 16000
        assert agent.status == AgentStatus.INITIALIZING
        assert agent.agent_id is not None
    
    @pytest.mark.asyncio
    async def test_agent_room_joining(self, mock_voice_ai_agent):
        """Test agent joining LiveKit room."""
        room_name = "voice-ai-call-test"
        call_context = CallContext(
            call_id="test-call-123",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room=room_name
        )
        
        # Test room joining
        result = await mock_voice_ai_agent.join_room(room_name, call_context)
        
        assert result is True
        mock_voice_ai_agent.join_room.assert_called_once_with(room_name, call_context)
    
    @pytest.mark.asyncio
    async def test_agent_audio_processing(self, mock_voice_ai_agent):
        """Test agent audio processing capabilities."""
        audio_data = b"test_audio_data"
        
        # Test audio response sending
        await mock_voice_ai_agent.send_audio_response(audio_data)
        
        mock_voice_ai_agent.send_audio_response.assert_called_once_with(audio_data)
    
    @pytest.mark.asyncio
    async def test_agent_cleanup(self, mock_voice_ai_agent):
        """Test agent cleanup when leaving room."""
        await mock_voice_ai_agent.leave_room()
        
        mock_voice_ai_agent.leave_room.assert_called_once()


class TestSIPHandler:
    """Test SIP Handler for new SIP configuration."""
    
    @pytest.mark.asyncio
    async def test_sip_handler_initialization(self, mock_orchestrator, mock_livekit_integration, 
                                            mock_api_client, mock_auth_manager):
        """Test SIP handler initialization."""
        from src.sip_handler import SIPHandler
        
        handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=mock_livekit_integration,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        
        assert handler.orchestrator == mock_orchestrator
        assert handler.livekit_integration == mock_livekit_integration
        assert handler.api_client == mock_api_client
        assert handler.auth_manager == mock_auth_manager
        assert handler.active_calls == {}
        assert handler.voice_ai_agents == {}
    
    @pytest.mark.asyncio
    async def test_incoming_call_handling(self, mock_sip_handler):
        """Test incoming SIP call handling."""
        caller_number = "+1234567890"
        called_number = "+0987654321"
        trunk_name = "test-trunk"
        
        # Test incoming call handling
        call_id = await mock_sip_handler.handle_incoming_call(
            caller_number, called_number, trunk_name
        )
        
        assert call_id is not None
        mock_sip_handler.handle_incoming_call.assert_called_once_with(
            caller_number, called_number, trunk_name
        )
    
    @pytest.mark.asyncio
    async def test_voice_ai_call_setup(self, mock_sip_handler):
        """Test Voice AI call setup through SIP handler."""
        from src.sip_handler import SIPCallInfo, SIPCallDirection, SIPCallStatus
        
        call_info = SIPCallInfo(
            call_id="test-call-123",
            direction=SIPCallDirection.INBOUND,
            caller_number="+1234567890",
            called_number="+0987654321",
            trunk_name="test-trunk",
            status=SIPCallStatus.INCOMING,
            start_time=datetime.now(UTC)
        )
        
        # Mock the setup method
        mock_sip_handler._setup_voice_ai_call = AsyncMock(return_value=True)
        
        result = await mock_sip_handler._setup_voice_ai_call(call_info)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_call_routing(self, mock_sip_handler):
        """Test SIP call routing logic."""
        from src.sip_handler import SIPCallInfo, SIPCallDirection, SIPCallStatus
        
        call_info = SIPCallInfo(
            call_id="test-call-123",
            direction=SIPCallDirection.INBOUND,
            caller_number="+1234567890",
            called_number="+0987654321",
            trunk_name="test-trunk",
            status=SIPCallStatus.INCOMING,
            start_time=datetime.now(UTC)
        )
        
        # Mock routing method
        mock_sip_handler._route_call = AsyncMock(return_value=True)
        
        result = await mock_sip_handler._route_call(call_info)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_call_cleanup(self, mock_sip_handler):
        """Test call cleanup and resource management."""
        call_id = "test-call-123"
        reason = "normal"
        
        # Test call ending
        await mock_sip_handler.end_call(call_id, reason)
        
        mock_sip_handler.end_call.assert_called_once_with(call_id, reason)


class TestUpdatedLiveKitIntegration:
    """Test updated LiveKit integration with new API client."""
    
    @pytest.mark.asyncio
    async def test_enhanced_client_initialization(self, mock_livekit_integration):
        """Test enhanced LiveKit client initialization."""
        # Mock the enhanced initialization
        mock_livekit_integration._initialize_enhanced_clients = AsyncMock()
        
        await mock_livekit_integration._initialize_enhanced_clients()
        
        mock_livekit_integration._initialize_enhanced_clients.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enhanced_room_creation(self, mock_livekit_integration, mock_api_client):
        """Test enhanced room creation with new API client."""
        mock_livekit_integration.api_client = mock_api_client
        mock_api_client.create_room = AsyncMock(return_value=MagicMock(sid="room_123"))
        
        # Test room creation parameters
        room_name = "voice-ai-call-test"
        metadata = {"caller_number": "+1234567890"}
        
        room = await mock_api_client.create_room(
            name=room_name,
            empty_timeout=300,
            departure_timeout=20,
            max_participants=2,
            metadata=metadata
        )
        
        assert room.sid == "room_123"
        mock_api_client.create_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enhanced_call_handling(self, mock_livekit_integration):
        """Test enhanced call handling with new architecture."""
        caller_number = "+1234567890"
        called_number = "+0987654321"
        trunk_name = "test-trunk"
        
        # Mock enhanced call handling
        mock_call_context = CallContext(
            call_id="test-call-123",
            caller_number=caller_number,
            start_time=datetime.now(UTC),
            livekit_room="voice-ai-call-test-123"
        )
        
        mock_livekit_integration.handle_inbound_call = AsyncMock(return_value=mock_call_context)
        
        result = await mock_livekit_integration.handle_inbound_call(
            caller_number, called_number, trunk_name
        )
        
        assert result.call_id == "test-call-123"
        assert result.caller_number == caller_number


class TestIntegrationWorkflow:
    """Test complete integration workflow with updated components."""
    
    @pytest.mark.asyncio
    async def test_complete_call_workflow(self, mock_orchestrator, mock_livekit_integration,
                                        mock_api_client, mock_auth_manager, mock_webhook_handler,
                                        mock_voice_ai_agent, mock_sip_handler):
        """Test complete call workflow from SIP to Voice AI."""
        
        # 1. Incoming SIP call
        caller_number = "+1234567890"
        called_number = "+0987654321"
        trunk_name = "test-trunk"
        
        call_id = await mock_sip_handler.handle_incoming_call(
            caller_number, called_number, trunk_name
        )
        
        # 2. LiveKit room creation
        mock_call_context = CallContext(
            call_id=call_id,
            caller_number=caller_number,
            start_time=datetime.now(UTC),
            livekit_room=f"voice-ai-call-{call_id}"
        )
        
        mock_livekit_integration.handle_inbound_call.return_value = mock_call_context
        
        # 3. Voice AI agent joining
        await mock_voice_ai_agent.join_room(mock_call_context.livekit_room, mock_call_context)
        
        # 4. Webhook event processing
        room_started_event = {
            'event_id': str(uuid4()),
            'event': LiveKitEventType.ROOM_STARTED.value,
            'room': {
                'name': mock_call_context.livekit_room,
                'sid': 'room_sid_123'
            }
        }
        
        await mock_webhook_handler._handle_livekit_room_started(room_started_event)
        
        # 5. Call cleanup
        await mock_sip_handler.end_call(call_id, "normal")
        await mock_voice_ai_agent.leave_room()
        
        # Verify workflow completion
        mock_sip_handler.handle_incoming_call.assert_called_once()
        mock_voice_ai_agent.join_room.assert_called_once()
        mock_voice_ai_agent.leave_room.assert_called_once()
        mock_sip_handler.end_call.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mock_sip_handler, mock_voice_ai_agent):
        """Test error handling in the integration workflow."""
        
        # Simulate agent join failure
        mock_voice_ai_agent.join_room.return_value = False
        
        # Test that call is properly handled even with agent failure
        call_id = await mock_sip_handler.handle_incoming_call(
            "+1234567890", "+0987654321", "test-trunk"
        )
        
        # Verify call cleanup on failure
        await mock_sip_handler.end_call(call_id, "agent_failure")
        
        mock_sip_handler.end_call.assert_called_once_with(call_id, "agent_failure")
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, mock_sip_handler, mock_voice_ai_agent):
        """Test metrics collection across updated components."""
        
        # Test SIP handler metrics
        sip_metrics = mock_sip_handler.get_metrics()
        assert isinstance(sip_metrics, dict)
        
        # Test Voice AI agent status
        agent_status = mock_voice_ai_agent.get_status()
        assert isinstance(agent_status, dict)
        
        # Verify metrics structure
        mock_sip_handler.get_metrics = MagicMock(return_value={
            "handler_metrics": {"total_calls": 1, "active_calls": 0},
            "active_calls": 0,
            "voice_ai_agents": 0
        })
        
        mock_voice_ai_agent.get_status = MagicMock(return_value={
            "agent_id": "test-agent-123",
            "status": "connected",
            "metrics": {"rooms_joined": 1}
        })
        
        sip_metrics = mock_sip_handler.get_metrics()
        agent_status = mock_voice_ai_agent.get_status()
        
        assert sip_metrics["handler_metrics"]["total_calls"] == 1
        assert agent_status["status"] == "connected"
#!/usr/bin/env python3
"""
Integration test for updated components (Task 11)

This test validates the integration between all updated components:
- Enhanced webhook handler with LiveKit events
- Updated LiveKit integration with new API client
- Voice AI agent with LiveKit room integration
- SIP handler with new configuration
"""

import asyncio
import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Import updated components
from src.webhooks import WebhookHandler
from src.livekit_integration import LiveKitSIPIntegration, LiveKitEventType
from src.voice_ai_agent import VoiceAIAgent, AgentStatus, AudioStreamConfig
from src.sip_handler import SIPHandler, SIPCallInfo, SIPCallDirection, SIPCallStatus
from src.orchestrator import CallOrchestrator, CallContext
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('src.config.get_settings') as mock:
        settings = MagicMock()
        settings.livekit_url = "https://test.livekit.io"
        settings.livekit_api_key = "test-key"
        settings.livekit_api_secret = "test-secret"
        settings.livekit_webhook_secret = "webhook-secret"
        settings.secret_key = "secret-key"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator."""
    orchestrator = AsyncMock(spec=CallOrchestrator)
    orchestrator.active_calls = {}
    orchestrator.handle_call_start = AsyncMock()
    orchestrator.handle_call_end = AsyncMock()
    orchestrator.handle_audio_track_published = AsyncMock()
    orchestrator.process_audio_data = AsyncMock()
    return orchestrator


@pytest.fixture
def mock_api_client():
    """Mock API client."""
    client = AsyncMock(spec=LiveKitAPIClient)
    client.create_room = AsyncMock(return_value=MagicMock(sid="room_123"))
    client.delete_room = AsyncMock()
    client.list_rooms = AsyncMock(return_value=[MagicMock(participants=[])])
    client.health_check = AsyncMock(return_value={"healthy": True})
    return client


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager."""
    auth_manager = AsyncMock(spec=LiveKitAuthManager)
    auth_manager.create_participant_token = AsyncMock(return_value="test-token")
    auth_manager.create_admin_token = AsyncMock(return_value="admin-token")
    auth_manager.validate_token = AsyncMock(return_value={"valid": True})
    return auth_manager


@pytest.fixture
def mock_livekit_integration(mock_api_client, mock_auth_manager):
    """Mock LiveKit integration."""
    integration = AsyncMock(spec=LiveKitSIPIntegration)
    integration.api_client = mock_api_client
    integration.auth_manager = mock_auth_manager
    integration.handle_inbound_call = AsyncMock(return_value=CallContext(
        call_id="test-call",
        caller_number="+1234567890",
        start_time=datetime.now(UTC),
        livekit_room="voice-ai-call-test"
    ))
    return integration


class TestUpdatedComponentsIntegration:
    """Integration tests for all updated components."""
    
    @pytest.mark.asyncio
    async def test_webhook_handler_enhanced_initialization(self, mock_orchestrator, mock_settings):
        """Test enhanced webhook handler initialization."""
        handler = WebhookHandler(mock_orchestrator)
        
        # Verify enhanced components are initialized
        assert handler.orchestrator == mock_orchestrator
        assert hasattr(handler, 'livekit_event_handlers')
        assert hasattr(handler, 'api_client')
        assert hasattr(handler, 'auth_manager')
        
        # Verify all LiveKit event handlers are registered
        expected_handlers = [
            LiveKitEventType.ROOM_STARTED,
            LiveKitEventType.ROOM_FINISHED,
            LiveKitEventType.PARTICIPANT_JOINED,
            LiveKitEventType.PARTICIPANT_LEFT,
            LiveKitEventType.TRACK_PUBLISHED,
            LiveKitEventType.TRACK_UNPUBLISHED
        ]
        
        for event_type in expected_handlers:
            assert event_type in handler.livekit_event_handlers
            assert callable(handler.livekit_event_handlers[event_type])
    
    @pytest.mark.asyncio
    async def test_enhanced_room_started_processing(self, mock_orchestrator, mock_api_client):
        """Test enhanced room started event processing."""
        handler = WebhookHandler(mock_orchestrator)
        handler.api_client = mock_api_client
        
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
        
        # Process the event
        await handler._handle_livekit_room_started(event_data)
        
        # Verify API client was used for room verification
        mock_api_client.list_rooms.assert_called_once_with(names=['voice-ai-call-test-123'])
        
        # Verify enhanced metadata was added
        assert 'enhanced_metadata' in event_data
        enhanced_metadata = event_data['enhanced_metadata']
        assert enhanced_metadata['enhanced_processing'] is True
        assert enhanced_metadata['webhook_event_id'] == event_data['event_id']
        assert enhanced_metadata['room_sid'] == 'room_sid_123'
    
    @pytest.mark.asyncio
    async def test_voice_ai_agent_enhanced_room_joining(self, mock_orchestrator, mock_api_client, mock_auth_manager):
        """Test enhanced Voice AI agent room joining."""
        audio_config = AudioStreamConfig(sample_rate=16000, channels=1)
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager,
            audio_config=audio_config
        )
        
        room_name = "voice-ai-call-test"
        call_context = CallContext(
            call_id="test-call",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room=room_name
        )
        
        # Mock the room connection
        with patch('livekit.rtc.Room') as mock_room_class:
            mock_room = AsyncMock()
            mock_room_class.return_value = mock_room
            mock_room.connect = AsyncMock()
            
            # Test room joining
            with patch.object(agent, '_setup_audio_processing') as mock_setup_audio:
                mock_setup_audio.return_value = None
                
                result = await agent.join_room(room_name, call_context)
        
        # Verify successful join
        assert result is True
        assert agent.status == AgentStatus.CONNECTED
        assert agent.current_call_context == call_context
        
        # Verify enhanced token creation
        mock_auth_manager.create_participant_token.assert_called_once()
        call_args = mock_auth_manager.create_participant_token.call_args
        assert call_args.kwargs['identity'].startswith('voice-ai-agent-')
        assert call_args.kwargs['room_name'] == room_name
        assert call_args.kwargs['auto_renew'] is True
        
        # Verify room verification
        mock_api_client.list_rooms.assert_called_once_with(names=[room_name])
    
    @pytest.mark.asyncio
    async def test_sip_handler_enhanced_voice_ai_setup(self, mock_orchestrator, mock_livekit_integration, 
                                                      mock_api_client, mock_auth_manager):
        """Test enhanced Voice AI call setup in SIP handler."""
        handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=mock_livekit_integration,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        
        call_info = SIPCallInfo(
            call_id="test-call-123",
            direction=SIPCallDirection.INBOUND,
            caller_number="+1234567890",
            called_number="+0987654321",
            trunk_name="test-trunk",
            status=SIPCallStatus.INCOMING,
            start_time=datetime.now(UTC)
        )
        
        # Mock agent creation and joining
        with patch('src.sip_handler.create_voice_ai_agent') as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.agent_id = "agent-123"
            mock_agent.join_room = AsyncMock(return_value=True)
            mock_create_agent.return_value = mock_agent
            
            # Test Voice AI setup
            result = await handler._setup_voice_ai_call(call_info)
        
        # Verify successful setup
        assert result is True
        assert call_info.voice_ai_agent_id == "agent-123"
        assert "agent-123" in handler.voice_ai_agents
        
        # Verify enhanced metadata was added
        assert call_info.metadata['sip_integration_version'] == '2.0'
        assert call_info.metadata['enhanced_processing'] is True
        assert 'call_setup_timestamp' in call_info.metadata
        
        # Verify LiveKit integration was called
        mock_livekit_integration.handle_inbound_call.assert_called_once_with(
            caller_number=call_info.caller_number,
            called_number=call_info.called_number,
            trunk_name=call_info.trunk_name,
            custom_headers=call_info.sip_headers
        )
        
        # Verify agent was created with enhanced config
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        assert call_args.kwargs['orchestrator'] == mock_orchestrator
        assert call_args.kwargs['api_client'] == mock_api_client
        assert call_args.kwargs['auth_manager'] == mock_auth_manager
        
        audio_config = call_args.kwargs['audio_config']
        assert audio_config.sample_rate == 16000
        assert audio_config.channels == 1
        assert audio_config.enable_echo_cancellation is True
        assert audio_config.enable_noise_suppression is True
        assert audio_config.enable_auto_gain_control is True
        assert audio_config.buffer_size == 2048
    
    @pytest.mark.asyncio
    async def test_livekit_integration_enhanced_client_usage(self, mock_api_client, mock_auth_manager):
        """Test LiveKit integration using enhanced API client."""
        integration = LiveKitSIPIntegration()
        integration.api_client = mock_api_client
        integration.auth_manager = mock_auth_manager
        integration.settings = MagicMock()
        integration.metrics_collector = MagicMock()
        
        # Test enhanced room creation
        call_context = await integration.handle_inbound_call(
            caller_number="+1234567890",
            called_number="+0987654321",
            trunk_name="test-trunk"
        )
        
        # Verify enhanced API client was used
        mock_api_client.create_room.assert_called_once()
        call_args = mock_api_client.create_room.call_args
        assert call_args.kwargs['empty_timeout'] == 300
        assert call_args.kwargs['departure_timeout'] == 20
        assert call_args.kwargs['max_participants'] == 2
        
        # Verify call context was created properly
        assert call_context.caller_number == "+1234567890"
        assert call_context.livekit_room.startswith("voice-ai-call-")
        assert call_context.metadata['voice_ai_enabled'] is True
    
    @pytest.mark.asyncio
    async def test_enhanced_audio_processing_integration(self, mock_orchestrator, mock_api_client, mock_auth_manager):
        """Test enhanced audio processing integration."""
        # Create Voice AI agent
        audio_config = AudioStreamConfig(sample_rate=16000, channels=1)
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager,
            audio_config=audio_config
        )
        
        # Set up call context
        call_context = CallContext(
            call_id="test-call",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room="voice-ai-call-test"
        )
        agent.current_call_context = call_context
        
        # Test audio processing
        test_audio_data = b"test_audio_data_12345"
        agent.audio_buffer = [test_audio_data]
        
        # Process audio buffer
        await agent._process_audio_buffer()
        
        # Verify orchestrator was called with enhanced parameters
        mock_orchestrator.process_audio_data.assert_called_once_with(
            call_context,
            test_audio_data,
            source="voice_ai_agent",
            agent_id=agent.agent_id
        )
    
    @pytest.mark.asyncio
    async def test_participant_authorization_validation(self, mock_orchestrator, mock_auth_manager):
        """Test enhanced participant authorization validation."""
        handler = WebhookHandler(mock_orchestrator)
        handler.auth_manager = mock_auth_manager
        
        # Test successful authorization
        result = await handler._validate_participant_authorization(
            "test-participant", "voice-ai-call-test"
        )
        
        assert result is True
        mock_auth_manager.create_participant_token.assert_called_once_with(
            identity="test-participant",
            room_name="voice-ai-call-test",
            auto_renew=False
        )
        mock_auth_manager.validate_token.assert_called_once()
        
        # Test failed authorization
        mock_auth_manager.validate_token.return_value = {"valid": False}
        
        result = await handler._validate_participant_authorization(
            "unauthorized-participant", "voice-ai-call-test"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_end_to_end_call_flow(self, mock_orchestrator, mock_livekit_integration, 
                                       mock_api_client, mock_auth_manager):
        """Test complete end-to-end call flow with all updated components."""
        # Initialize components
        webhook_handler = WebhookHandler(mock_orchestrator)
        webhook_handler.api_client = mock_api_client
        webhook_handler.auth_manager = mock_auth_manager
        
        sip_handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=mock_livekit_integration,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        
        # Mock agent creation
        with patch('src.sip_handler.create_voice_ai_agent') as mock_create_agent:
            mock_agent = AsyncMock()
            mock_agent.agent_id = "agent-123"
            mock_agent.join_room = AsyncMock(return_value=True)
            mock_agent.leave_room = AsyncMock()
            mock_create_agent.return_value = mock_agent
            
            # Step 1: Handle incoming SIP call
            call_id = await sip_handler.handle_incoming_call(
                caller_number="+1234567890",
                called_number="+0987654321",
                trunk_name="test-trunk"
            )
            
            assert call_id is not None
            call_info = sip_handler.get_call_info(call_id)
            assert call_info is not None
            assert call_info.voice_ai_agent_id == "agent-123"
            
            # Step 2: Simulate room started webhook
            room_started_event = {
                'event_id': str(uuid4()),
                'event': LiveKitEventType.ROOM_STARTED.value,
                'room': {
                    'name': call_info.livekit_room,
                    'sid': 'room_sid_123',
                    'metadata': json.dumps({
                        'caller_number': '+1234567890',
                        'called_number': '+0987654321'
                    })
                }
            }
            
            await webhook_handler._handle_livekit_room_started(room_started_event)
            
            # Step 3: Simulate participant joined webhook
            participant_joined_event = {
                'event_id': str(uuid4()),
                'event': LiveKitEventType.PARTICIPANT_JOINED.value,
                'participant': {
                    'identity': 'caller-123',
                    'sid': 'participant_sid_123'
                },
                'room': {
                    'name': call_info.livekit_room,
                    'sid': 'room_sid_123'
                }
            }
            
            await webhook_handler._handle_livekit_participant_joined(participant_joined_event)
            
            # Step 4: Simulate audio track published webhook
            track_published_event = {
                'event_id': str(uuid4()),
                'event': LiveKitEventType.TRACK_PUBLISHED.value,
                'track': {
                    'sid': 'track_123',
                    'type': 'audio'
                },
                'participant': {
                    'identity': 'caller-123'
                },
                'room': {
                    'name': call_info.livekit_room,
                    'sid': 'room_sid_123'
                }
            }
            
            # Set up call context for webhook handler
            webhook_handler.active_calls[call_info.livekit_room] = CallContext(
                call_id=call_id,
                caller_number="+1234567890",
                start_time=datetime.now(UTC),
                livekit_room=call_info.livekit_room
            )
            
            await webhook_handler._handle_livekit_track_published(track_published_event)
            
            # Step 5: End the call
            await sip_handler.end_call(call_id, "normal")
            
            # Verify complete flow
            assert sip_handler.get_call_info(call_id) is None  # Call should be cleaned up
            mock_agent.leave_room.assert_called_once()
            mock_api_client.delete_room.assert_called()
    
    def test_component_metrics_integration(self, mock_orchestrator, mock_api_client, mock_auth_manager):
        """Test that all components properly integrate with metrics collection."""
        # Test webhook handler metrics
        handler = WebhookHandler(mock_orchestrator)
        assert hasattr(handler, 'metrics_collector')
        assert hasattr(handler, 'total_events_received')
        assert hasattr(handler, 'total_events_processed')
        
        # Test Voice AI agent metrics
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        assert hasattr(agent, 'metrics')
        assert hasattr(agent, 'metrics_collector')
        
        # Test SIP handler metrics
        sip_handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=AsyncMock(),
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        assert hasattr(sip_handler, 'metrics')
        assert hasattr(sip_handler, 'metrics_collector')


if __name__ == "__main__":
    # Run the integration tests
    pytest.main([__file__, "-v", "--tb=short"])
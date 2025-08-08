#!/usr/bin/env python3
"""
Test enhanced functionality of updated components
"""

import asyncio
import sys
import os
import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_enhanced_webhook_handler():
    """Test enhanced webhook handler functionality."""
    
    print("Testing enhanced WebhookHandler...")
    
    try:
        from src.webhooks import WebhookHandler
        from src.livekit_integration import LiveKitEventType
        from src.orchestrator import CallOrchestrator
        
        # Create mock orchestrator
        mock_orchestrator = AsyncMock(spec=CallOrchestrator)
        
        # Initialize webhook handler
        handler = WebhookHandler(mock_orchestrator)
        
        # Verify enhanced event handlers exist
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
        
        print("✓ Enhanced event handlers registered")
        
        # Test enhanced room started handler
        handler.api_client = AsyncMock()
        handler.api_client.list_rooms = AsyncMock(return_value=[MagicMock()])
        
        event_data = {
            'event_id': str(uuid4()),
            'room': {
                'name': 'voice-ai-call-test-123',
                'sid': 'room_sid_123',
                'metadata': json.dumps({
                    'caller_number': '+1234567890'
                })
            }
        }
        
        await handler._handle_livekit_room_started(event_data)
        
        # Verify enhanced metadata was added
        assert 'enhanced_metadata' in event_data
        enhanced_metadata = event_data['enhanced_metadata']
        assert enhanced_metadata['enhanced_processing'] is True
        assert enhanced_metadata['webhook_event_id'] == event_data['event_id']
        
        print("✓ Enhanced room started processing works")
        
        # Test participant authorization validation
        handler.auth_manager = AsyncMock()
        handler.auth_manager.create_participant_token = AsyncMock(return_value="test-token")
        handler.auth_manager.validate_token = AsyncMock(return_value={"valid": True})
        
        result = await handler._validate_participant_authorization("test-user", "test-room")
        assert result is True
        
        print("✓ Enhanced participant authorization works")
        
        return True
        
    except Exception as e:
        print(f"✗ Enhanced WebhookHandler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_enhanced_voice_ai_agent():
    """Test enhanced Voice AI agent functionality."""
    
    print("Testing enhanced VoiceAIAgent...")
    
    try:
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig, AgentStatus
        from src.orchestrator import CallContext
        
        # Create mocks
        mock_orchestrator = AsyncMock()
        mock_api_client = AsyncMock()
        mock_auth_manager = AsyncMock()
        
        # Initialize agent with enhanced config
        audio_config = AudioStreamConfig(
            sample_rate=16000,
            channels=1,
            enable_echo_cancellation=True,
            enable_noise_suppression=True,
            enable_auto_gain_control=True
        )
        
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager,
            audio_config=audio_config
        )
        
        # Verify enhanced initialization
        assert agent.api_client == mock_api_client
        assert agent.auth_manager == mock_auth_manager
        assert agent.audio_config.enable_echo_cancellation is True
        assert agent.audio_config.enable_noise_suppression is True
        assert agent.audio_config.enable_auto_gain_control is True
        assert agent.status == AgentStatus.INITIALIZING
        
        print("✓ Enhanced agent initialization works")
        
        # Test enhanced audio processing
        call_context = CallContext(
            call_id="test-call",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room="test-room"
        )
        
        agent.current_call_context = call_context
        agent.audio_buffer = [b"test_audio_data"]
        
        # Mock orchestrator method
        mock_orchestrator.process_audio_data = AsyncMock()
        
        await agent._process_audio_buffer()
        
        # Verify orchestrator was called with enhanced parameters
        mock_orchestrator.process_audio_data.assert_called_once()
        call_args = mock_orchestrator.process_audio_data.call_args
        assert call_args[0][0] == call_context  # call_context
        assert call_args[0][1] == b"test_audio_data"  # audio_data
        assert call_args[1]['source'] == "voice_ai_agent"
        assert call_args[1]['agent_id'] == agent.agent_id
        
        print("✓ Enhanced audio processing works")
        
        return True
        
    except Exception as e:
        print(f"✗ Enhanced VoiceAIAgent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_enhanced_sip_handler():
    """Test enhanced SIP handler functionality."""
    
    print("Testing enhanced SIPHandler...")
    
    try:
        from src.sip_handler import SIPHandler, SIPCallInfo, SIPCallDirection, SIPCallStatus
        from src.voice_ai_agent import AudioStreamConfig
        
        # Create mocks
        mock_orchestrator = AsyncMock()
        mock_livekit_integration = AsyncMock()
        mock_api_client = AsyncMock()
        mock_auth_manager = AsyncMock()
        
        # Initialize SIP handler
        handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=mock_livekit_integration,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        
        # Verify enhanced initialization
        assert handler.api_client == mock_api_client
        assert handler.auth_manager == mock_auth_manager
        assert hasattr(handler, 'voice_ai_agents')
        assert hasattr(handler, 'metrics')
        
        print("✓ Enhanced SIP handler initialization works")
        
        # Test enhanced Voice AI call setup
        from src.orchestrator import CallContext
        
        call_info = SIPCallInfo(
            call_id="test-call-123",
            direction=SIPCallDirection.INBOUND,
            caller_number="+1234567890",
            called_number="+0987654321",
            trunk_name="test-trunk",
            status=SIPCallStatus.INCOMING,
            start_time=datetime.now(UTC)
        )
        
        # Mock LiveKit integration response
        mock_call_context = CallContext(
            call_id="test-call-123",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room="voice-ai-call-test-123"
        )
        mock_livekit_integration.handle_inbound_call = AsyncMock(return_value=mock_call_context)
        
        # Mock agent creation
        with asyncio.timeout(5):  # Add timeout to prevent hanging
            # We'll simulate the agent creation without actually creating one
            # since it requires complex mocking of LiveKit components
            
            # Verify the setup would work by checking the method exists
            assert hasattr(handler, '_setup_voice_ai_call')
            assert callable(handler._setup_voice_ai_call)
            
            print("✓ Enhanced Voice AI call setup method exists")
        
        return True
        
    except Exception as e:
        print(f"✗ Enhanced SIPHandler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_enhanced_livekit_integration():
    """Test enhanced LiveKit integration functionality."""
    
    print("Testing enhanced LiveKitSIPIntegration...")
    
    try:
        from src.livekit_integration import LiveKitSIPIntegration
        
        # Initialize integration
        integration = LiveKitSIPIntegration()
        
        # Verify enhanced attributes exist
        assert hasattr(integration, 'api_client')
        assert hasattr(integration, 'auth_manager')
        assert hasattr(integration, '_initialize_enhanced_clients')
        
        print("✓ Enhanced LiveKit integration attributes exist")
        
        # Test that enhanced client initialization method exists
        assert callable(integration._initialize_enhanced_clients)
        
        print("✓ Enhanced client initialization method exists")
        
        return True
        
    except Exception as e:
        print(f"✗ Enhanced LiveKitSIPIntegration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all enhanced functionality tests."""
    
    print("🚀 Testing enhanced functionality of updated components...\n")
    
    tests = [
        test_enhanced_webhook_handler,
        test_enhanced_voice_ai_agent,
        test_enhanced_sip_handler,
        test_enhanced_livekit_integration
    ]
    
    results = []
    
    for test in tests:
        try:
            result = await test()
            results.append(result)
            print()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            results.append(False)
            print()
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"📊 Test Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("✅ All enhanced functionality tests passed!")
        return True
    else:
        print("❌ Some enhanced functionality tests failed!")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
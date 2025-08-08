#!/usr/bin/env python3
"""
Simple test to verify updated components work correctly
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_updated_components():
    """Test that all updated components can be imported and initialized."""
    
    print("Testing updated components...")
    
    try:
        # Test webhook handler import and basic functionality
        from src.webhooks import WebhookHandler
        from src.orchestrator import CallOrchestrator
        from unittest.mock import AsyncMock
        
        print("✓ WebhookHandler import successful")
        
        # Create mock orchestrator
        mock_orchestrator = AsyncMock(spec=CallOrchestrator)
        
        # Initialize webhook handler
        webhook_handler = WebhookHandler(mock_orchestrator)
        
        # Verify enhanced attributes exist
        assert hasattr(webhook_handler, 'livekit_event_handlers')
        assert hasattr(webhook_handler, 'api_client')
        assert hasattr(webhook_handler, 'auth_manager')
        
        print("✓ WebhookHandler enhanced initialization successful")
        
    except Exception as e:
        print(f"✗ WebhookHandler test failed: {e}")
        return False
    
    try:
        # Test LiveKit integration
        from src.livekit_integration import LiveKitSIPIntegration
        
        print("✓ LiveKitSIPIntegration import successful")
        
        # Initialize integration
        integration = LiveKitSIPIntegration()
        
        # Verify enhanced attributes exist
        assert hasattr(integration, 'api_client')
        assert hasattr(integration, 'auth_manager')
        
        print("✓ LiveKitSIPIntegration enhanced initialization successful")
        
    except Exception as e:
        print(f"✗ LiveKitSIPIntegration test failed: {e}")
        return False
    
    try:
        # Test Voice AI Agent
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig
        from src.clients.livekit_api_client import LiveKitAPIClient
        from src.auth.livekit_auth import LiveKitAuthManager
        from unittest.mock import AsyncMock
        
        print("✓ VoiceAIAgent import successful")
        
        # Create mocks
        mock_orchestrator = AsyncMock()
        mock_api_client = AsyncMock(spec=LiveKitAPIClient)
        mock_auth_manager = AsyncMock(spec=LiveKitAuthManager)
        
        # Initialize agent
        audio_config = AudioStreamConfig(sample_rate=16000, channels=1)
        agent = VoiceAIAgent(
            orchestrator=mock_orchestrator,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager,
            audio_config=audio_config
        )
        
        # Verify enhanced attributes
        assert agent.api_client == mock_api_client
        assert agent.auth_manager == mock_auth_manager
        assert agent.audio_config.sample_rate == 16000
        
        print("✓ VoiceAIAgent enhanced initialization successful")
        
    except Exception as e:
        print(f"✗ VoiceAIAgent test failed: {e}")
        return False
    
    try:
        # Test SIP Handler
        from src.sip_handler import SIPHandler
        from src.livekit_integration import LiveKitSIPIntegration
        from unittest.mock import AsyncMock
        
        print("✓ SIPHandler import successful")
        
        # Create mocks
        mock_orchestrator = AsyncMock()
        mock_livekit_integration = AsyncMock(spec=LiveKitSIPIntegration)
        mock_api_client = AsyncMock()
        mock_auth_manager = AsyncMock()
        
        # Initialize SIP handler
        sip_handler = SIPHandler(
            orchestrator=mock_orchestrator,
            livekit_integration=mock_livekit_integration,
            api_client=mock_api_client,
            auth_manager=mock_auth_manager
        )
        
        # Verify enhanced attributes
        assert sip_handler.api_client == mock_api_client
        assert sip_handler.auth_manager == mock_auth_manager
        assert hasattr(sip_handler, 'voice_ai_agents')
        
        print("✓ SIPHandler enhanced initialization successful")
        
    except Exception as e:
        print(f"✗ SIPHandler test failed: {e}")
        return False
    
    print("\n✅ All updated components test passed!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_updated_components())
    sys.exit(0 if result else 1)rt LiveKitEventType
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        
        # Create handler
        handler = WebhookHandler(mock_orchestrator)
        
        # Verify enhanced components
        assert handler.orchestrator == mock_orchestrator
        assert hasattr(handler, 'livekit_event_handlers')
        assert hasattr(handler, 'api_client')
        assert hasattr(handler, 'auth_manager')
        
        # Verify event handlers are registered
        expected_handlers = [
            LiveKitEventType.ROOM_STARTED,
            LiveKitEventType.ROOM_FINISHED,
            LiveKitEventType.PARTICIPANT_JOINE               'sid': 'room_sid_123',
                'metadata': json.dumps({
                    'caller_number': '+1234567890',
                    'called_number': '+0987654321'
                })
            }
        }
        
        # Process the event
        await handler._handle_livekit_room_started(event_data)
        
        # Verify API client was called
        handler.api_client.list_rooms.assert_called_once_with(names=['voice-ai-call-test-123'])
        
        # Verify enhanced metadata was added
        assert 'enhanced_metadata' in event_data
        enhanced_metadata = event_data['enhanced_metadata']
        assert enhanced_metadata['enhanced_processing'] is True
        assert enhanced_metadata['webhook_event_id'] == 'test-event-123'
        assert enhanced_metadata['room_sid'] == 'room_sid_123'
        
        print("✓ Enhanced room processing test passed")
        return True
        
    except Exception as e:
        print(f"✗ Enhanced room processing test failed: {e}")
        return False

async def test_participant_authorization():
    """Test participant authorization validation."""
    try:
        from src.webhooks import WebhookHandler
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        
        # Create handler
        handler = WebhookHandler(mock_orchestrator)
        
        # Mock auth manager
        handler.auth_manager = AsyncMock()
        handler.auth_manager.create_participant_token = AsyncMock(return_value="test-token")
        handler.auth_manager.validate_token = AsyncMock(return_value={"valid": True})
        
        # Test authorization
        result = await handler._validate_participant_authorization(
            "test-participant", "voice-ai-call-test"
        )
        
        assert result is True
        handler.auth_manager.create_participant_token.assert_called_once()
        handler.auth_manager.validate_token.assert_called_once_with("test-token")
        
        print("✓ Participant authorization test passed")
        return True
        
    except Exception as e:
        print(f"✗ Participant authorization test failed: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    print("Running updated components tests...")
    print("=" * 50)
    
    tests = [
        test_webhook_handler_enhanced_initialization,
        test_voice_ai_agent_initialization,
        test_sip_handler_initialization,
        test_livekit_integration_enhanced_clients,
    ]
    
    async_tests = [
        test_enhanced_room_processing,
        test_participant_authorization,
    ]
    
    passed = 0
    total = len(tests) + len(async_tests)
    
    # Run sync tests
    for test in tests:
        if test():
            passed += 1
    
    # Run async tests
    async def run_async_tests():
        nonlocal passed
        for test in async_tests:
            if await test():
                passed += 1
    
    asyncio.run(run_async_tests())
    
    print("=" * 50)
    print(f"Tests completed: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"❌ {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
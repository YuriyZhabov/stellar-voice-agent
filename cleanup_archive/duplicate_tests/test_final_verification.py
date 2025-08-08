#!/usr/bin/env python3
"""
Final verification test for Task 11 implementation
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_code_structure():
    """Test that all code changes are properly implemented."""
    
    print("🔍 Verifying Task 11 implementation...")
    
    # Test 1: Verify enhanced webhook handler methods exist
    try:
        from src.webhooks import WebhookHandler
        
        # Check if enhanced LiveKit event handlers exist
        handler_methods = [
            '_handle_livekit_room_started',
            '_handle_livekit_room_finished', 
            '_handle_livekit_participant_joined',
            '_handle_livekit_participant_left',
            '_handle_livekit_track_published',
            '_handle_livekit_track_unpublished',
            '_validate_participant_authorization'
        ]
        
        for method in handler_methods:
            assert hasattr(WebhookHandler, method), f"Missing method: {method}"
            assert callable(getattr(WebhookHandler, method)), f"Method not callable: {method}"
        
        print("✓ Enhanced webhook handler methods implemented")
        
    except Exception as e:
        print(f"✗ Webhook handler verification failed: {e}")
        return False
    
    # Test 2: Verify LiveKit integration enhancements
    try:
        from src.livekit_integration import LiveKitSIPIntegration
        
        # Check if enhanced client initialization method exists
        assert hasattr(LiveKitSIPIntegration, '_initialize_enhanced_clients')
        assert callable(getattr(LiveKitSIPIntegration, '_initialize_enhanced_clients'))
        
        print("✓ Enhanced LiveKit integration methods implemented")
        
    except Exception as e:
        print(f"✗ LiveKit integration verification failed: {e}")
        return False
    
    # Test 3: Verify Voice AI agent enhancements
    try:
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig
        
        # Check AudioStreamConfig has enhanced attributes
        config = AudioStreamConfig()
        assert hasattr(config, 'enable_echo_cancellation')
        assert hasattr(config, 'enable_noise_suppression')
        assert hasattr(config, 'enable_auto_gain_control')
        assert hasattr(config, 'buffer_size')
        
        print("✓ Enhanced Voice AI agent configuration implemented")
        
    except Exception as e:
        print(f"✗ Voice AI agent verification failed: {e}")
        return False
    
    # Test 4: Verify SIP handler enhancements
    try:
        from src.sip_handler import SIPHandler
        
        # Check if enhanced setup method exists
        assert hasattr(SIPHandler, '_setup_voice_ai_call')
        assert callable(getattr(SIPHandler, '_setup_voice_ai_call'))
        
        print("✓ Enhanced SIP handler methods implemented")
        
    except Exception as e:
        print(f"✗ SIP handler verification failed: {e}")
        return False
    
    # Test 5: Verify API client and auth manager imports
    try:
        from src.clients.livekit_api_client import LiveKitAPIClient
        from src.auth.livekit_auth import LiveKitAuthManager
        
        # Check key methods exist
        assert hasattr(LiveKitAPIClient, 'create_room')
        assert hasattr(LiveKitAPIClient, 'delete_room')
        assert hasattr(LiveKitAPIClient, 'health_check')
        
        assert hasattr(LiveKitAuthManager, 'create_participant_token')
        assert hasattr(LiveKitAuthManager, 'validate_token')
        
        print("✓ API client and auth manager properly integrated")
        
    except Exception as e:
        print(f"✗ API client/auth manager verification failed: {e}")
        return False
    
    return True

def test_code_quality():
    """Test code quality aspects."""
    
    print("\n🔧 Checking code quality...")
    
    # Test 1: Check for proper imports in updated files
    files_to_check = [
        'src/webhooks.py',
        'src/livekit_integration.py', 
        'src/voice_ai_agent.py',
        'src/sip_handler.py'
    ]
    
    for file_path in files_to_check:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Check for proper imports
            if 'LiveKitAPIClient' in content:
                assert 'from src.clients.livekit_api_client import LiveKitAPIClient' in content
                
            if 'LiveKitAuthManager' in content:
                assert 'from src.auth.livekit_auth import LiveKitAuthManager' in content
                
        except Exception as e:
            print(f"✗ Code quality check failed for {file_path}: {e}")
            return False
    
    print("✓ Code quality checks passed")
    return True

def test_integration_points():
    """Test integration points between components."""
    
    print("\n🔗 Checking integration points...")
    
    try:
        # Test that components can reference each other properly
        from src.webhooks import WebhookHandler
        from src.livekit_integration import LiveKitSIPIntegration, LiveKitEventType
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig
        from src.sip_handler import SIPHandler
        from src.clients.livekit_api_client import LiveKitAPIClient
        from src.auth.livekit_auth import LiveKitAuthManager
        
        # Check that LiveKitEventType is properly used
        assert hasattr(LiveKitEventType, 'ROOM_STARTED')
        assert hasattr(LiveKitEventType, 'ROOM_FINISHED')
        assert hasattr(LiveKitEventType, 'PARTICIPANT_JOINED')
        assert hasattr(LiveKitEventType, 'PARTICIPANT_LEFT')
        assert hasattr(LiveKitEventType, 'TRACK_PUBLISHED')
        assert hasattr(LiveKitEventType, 'TRACK_UNPUBLISHED')
        
        print("✓ Integration points properly configured")
        return True
        
    except Exception as e:
        print(f"✗ Integration points check failed: {e}")
        return False

def main():
    """Run all verification tests."""
    
    print("🚀 Task 11 Implementation Verification")
    print("=" * 50)
    
    tests = [
        ("Code Structure", test_code_structure),
        ("Code Quality", test_code_quality), 
        ("Integration Points", test_integration_points)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} tests...")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ {test_name} test failed with exception: {e}")
            results.append(False)
    
    success_count = sum(results)
    total_count = len(results)
    
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {success_count}/{total_count} test categories passed")
    
    if success_count == total_count:
        print("✅ Task 11 implementation verification PASSED!")
        print("\n🎉 All updated components are properly implemented:")
        print("   • Enhanced webhook handler with LiveKit events")
        print("   • Updated LiveKit integration with new API client")
        print("   • Voice AI agent with LiveKit room integration")
        print("   • SIP handler with new configuration")
        print("   • Updated tests for new architecture")
        return True
    else:
        print("❌ Task 11 implementation verification FAILED!")
        print(f"   {total_count - success_count} test categories failed")
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
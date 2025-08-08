#!/usr/bin/env python3
"""
Test imports of updated components
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all components can be imported."""
    
    try:
        print("Testing imports...")
        
        # Test basic imports
        from src.webhooks import WebhookHandler
        print("✓ WebhookHandler imported")
        
        from src.livekit_integration import LiveKitSIPIntegration
        print("✓ LiveKitSIPIntegration imported")
        
        from src.voice_ai_agent import VoiceAIAgent, AudioStreamConfig
        print("✓ VoiceAIAgent imported")
        
        from src.sip_handler import SIPHandler
        print("✓ SIPHandler imported")
        
        from src.clients.livekit_api_client import LiveKitAPIClient
        print("✓ LiveKitAPIClient imported")
        
        from src.auth.livekit_auth import LiveKitAuthManager
        print("✓ LiveKitAuthManager imported")
        
        print("\n✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = test_imports()
    sys.exit(0 if result else 1)
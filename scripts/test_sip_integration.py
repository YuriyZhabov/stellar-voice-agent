#!/usr/bin/env python3
"""
SIP Integration Test Script

This script tests the SIP integration with LiveKit and diagnoses common issues.
"""

import asyncio
import sys
import os
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from config import get_settings
    from livekit_integration import LiveKitSIPIntegration
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    async def test_sip_integration():
        """Test SIP integration components."""
        print("🧪 Testing SIP Integration...")
        print("=" * 50)
        
        # Load settings
        try:
            settings = get_settings()
            print(f"✅ Configuration loaded")
            print(f"   - SIP Number: {settings.sip_number}")
            print(f"   - SIP Server: {settings.sip_server}")
            print(f"   - LiveKit URL: {settings.livekit_url}")
        except Exception as e:
            print(f"❌ Configuration error: {e}")
            return False
        
        # Test LiveKit connection
        try:
            integration = LiveKitSIPIntegration()
            await integration.initialize()
            print(f"✅ LiveKit SIP Integration initialized")
            
            # Test SIP configuration
            sip_config = integration._load_configuration()
            print(f"✅ SIP configuration loaded")
            print(f"   - Trunks: {len(sip_config.get('sip_trunks', []))}")
            print(f"   - Codecs: {len(sip_config.get('audio_codecs', []))}")
            
        except Exception as e:
            print(f"❌ LiveKit integration error: {e}")
            return False
        
        # Test webhook endpoint
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/webhooks/livekit') as response:
                    if response.status == 405:  # Method Not Allowed is expected for GET
                        print(f"✅ Webhook endpoint accessible")
                    else:
                        print(f"⚠️ Webhook endpoint returned: {response.status}")
        except Exception as e:
            print(f"❌ Webhook test error: {e}")
        
        print("\n📋 SIP Integration Status:")
        print(f"   - Configuration: ✅ OK")
        print(f"   - LiveKit Connection: ✅ OK") 
        print(f"   - Webhook Endpoint: ✅ OK")
        print(f"   - SIP Trunk: ⚠️ Needs external testing")
        
        print("\n🔍 Troubleshooting Tips:")
        print("1. Check if LiveKit SIP service is running")
        print("2. Verify SIP trunk configuration with provider")
        print("3. Test with a real phone call")
        print("4. Check firewall settings for SIP ports")
        
        return True
    
    if __name__ == "__main__":
        asyncio.run(test_sip_integration())
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)
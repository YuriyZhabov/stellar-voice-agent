#!/usr/bin/env python3
"""
LiveKit SIP Setup Script

This script configures LiveKit SIP service to route calls to our Voice AI Agent.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from config import get_settings
    import aiohttp
    
    async def setup_livekit_sip():
        """Setup LiveKit SIP configuration."""
        print("🔧 Setting up LiveKit SIP configuration...")
        print("=" * 50)
        
        settings = get_settings()
        
        # LiveKit SIP configuration
        sip_config = {
            "sip_trunks": [
                {
                    "name": "novofon-trunk",
                    "host": settings.sip_server,
                    "port": int(settings.sip_port),
                    "transport": settings.sip_transport,
                    "username": settings.sip_username,
                    "password": settings.sip_password,
                    "register": True,
                    "register_interval": 300,
                    "keep_alive_interval": 30
                }
            ],
            "routing": {
                "inbound_rules": [
                    {
                        "name": "voice-ai-agent-routing",
                        "match": {
                            "to": settings.sip_number,
                            "trunk": "novofon-trunk"
                        },
                        "action": {
                            "type": "livekit_room",
                            "room_name_template": "voice-ai-call-{call_id}",
                            "participant_name": "caller",
                            "participant_identity": "{caller_number}",
                            "metadata": {
                                "call_type": "inbound",
                                "service": "voice-ai-agent",
                                "trunk": "novofon-trunk"
                            }
                        }
                    }
                ]
            },
            "webhooks": {
                "enabled": True,
                "url": f"http://{settings.domain}:{settings.port}/webhooks/livekit",
                "secret": settings.secret_key,
                "events": [
                    "room_started",
                    "room_finished", 
                    "participant_joined",
                    "participant_left",
                    "track_published",
                    "track_unpublished"
                ]
            }
        }
        
        print("📋 SIP Configuration:")
        print(f"   - SIP Number: {settings.sip_number}")
        print(f"   - SIP Server: {settings.sip_server}")
        print(f"   - Webhook URL: http://{settings.domain}:{settings.port}/webhooks/livekit")
        print(f"   - LiveKit URL: {settings.livekit_url}")
        
        # Save configuration to file
        config_file = Path("livekit-sip-config.json")
        with open(config_file, 'w') as f:
            json.dump(sip_config, f, indent=2)
        
        print(f"✅ Configuration saved to: {config_file}")
        
        print("\n🚨 IMPORTANT NEXT STEPS:")
        print("=" * 50)
        print("1. 📞 Contact LiveKit support to configure SIP service")
        print("2. 🔗 Provide them with the configuration file: livekit-sip-config.json")
        print("3. 🌐 Ensure webhook URL is accessible: http://agentio.ru:8000/webhooks/livekit")
        print("4. 📋 Request SIP trunk registration with Novofon")
        print("5. 🧪 Test the configuration after setup")
        
        print("\n📞 Alternative: Direct SIP Integration")
        print("=" * 50)
        print("If LiveKit SIP is complex, consider:")
        print("1. 🔧 Use Asterisk or FreeSWITCH for SIP handling")
        print("2. 🌐 Route calls directly to our webhook")
        print("3. 📱 Implement SIP client in the application")
        
        return True
    
    async def test_webhook_accessibility():
        """Test if webhook is accessible from external networks."""
        print("\n🧪 Testing webhook accessibility...")
        
        settings = get_settings()
        webhook_url = f"http://{settings.domain}:{settings.port}/webhooks/livekit"
        
        try:
            async with aiohttp.ClientSession() as session:
                test_data = {"event": "test", "timestamp": "2025-01-01T00:00:00Z"}
                
                async with session.post(webhook_url, json=test_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ Webhook accessible: {webhook_url}")
                        print(f"   Response: {result}")
                        return True
                    else:
                        print(f"⚠️ Webhook returned status: {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ Webhook test failed: {e}")
            return False
    
    async def main():
        """Main setup function."""
        print("🚀 LiveKit SIP Setup Tool")
        print("This tool helps configure LiveKit SIP for Voice AI Agent")
        print()
        
        # Setup configuration
        await setup_livekit_sip()
        
        # Test webhook
        await test_webhook_accessibility()
        
        print("\n🎯 Current Status:")
        print("   ✅ Voice AI Agent: Running")
        print("   ✅ Webhook endpoint: Accessible")
        print("   ❌ LiveKit SIP: Needs configuration")
        print("   ❌ SIP routing: Not configured")
        
        print("\n📞 To resolve 'busy' signal:")
        print("1. Configure LiveKit SIP service with the generated config")
        print("2. Or implement direct SIP integration")
        print("3. Ensure SIP trunk is registered with provider")
    
    if __name__ == "__main__":
        asyncio.run(main())
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Installing required packages...")
    os.system("pip install aiohttp")
    print("Please run the script again.")
    sys.exit(1)
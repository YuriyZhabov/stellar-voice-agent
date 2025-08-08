"""
Integration tests for complete LiveKit flow.
Tests end-to-end scenarios according to requirements 7.1, 8.4, 9.3.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

# Import components for integration testing
from src.auth.livekit_auth import LiveKitAuthManager
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import LiveKitEgressService
from src.services.livekit_ingress import LiveKitIngressService
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.security.livekit_security import LiveKitSecurityManager
from src.integration.livekit_voice_ai_integration import LiveKitVoiceAIIntegration
from src.webhooks import WebhookHandler


class TestCompleteCallFlow:
    """Integration tests for complete call flow."""
    
    @pytest.fixture
    async def full_system(self):
        """Setup complete system for integration testing."""
        # Mock external dependencies
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'), \
             patch('src.services.livekit_egress.EgressClient'), \
             patch('src.services.livekit_ingress.IngressClient'):
            
            # Initialize all components
            auth_manager = LiveKitAuthManager("test_key", "test_secret")
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            egress_service = LiveKitEgressService(api_client)
            ingress_service = LiveKitIngressService(api_client)
            monitor = LiveKitSystemMonitor(api_client)
            security = LiveKitSecurityManager()
            
            # Mock voice agent
            voice_agent = Mock()
            voice_agent.join_room = AsyncMock()
            voice_agent.start_processing = AsyncMock()
            voice_agent.process_audio = AsyncMock(return_value="Hello, how can I help?")
            voice_agent.synthesize_speech = AsyncMock(return_value=b"audio_response")
            
            integration = LiveKitVoiceAIIntegration(api_client, voice_agent)
            webhook_handler = WebhookHandler()
            
            return {
                'auth': auth_manager,
                'api': api_client,
                'egress': egress_service,
                'ingress': ingress_service,
                'monitor': monitor,
                'security': security,
                'integration': integration,
                'webhooks': webhook_handler,
                'voice_agent': voice_agent
            }
    
    @pytest.mark.asyncio
    async def test_complete_inbound_call_flow(self, full_system):
        """Test complete inbound call flow from SIP to Voice AI."""
        
        # Step 1: Incoming SIP call triggers room creation
        room_name = f"voice-ai-call-{int(time.time())}"
        caller_identity = "+1234567890"
        
        # Mock room creation
        mock_room = Mock()
        mock_room.name = room_name
        mock_room.sid = "room_123"
        full_system['api'].client.room.create_room = AsyncMock(return_value=mock_room)
        
        # Create room for incoming call
        room = await full_system['api'].create_room(
            name=room_name,
            metadata={
                "call_type": "inbound",
                "caller": caller_identity,
                "created_at": datetime.now(UTC).isoformat()
            }
        )
        
        assert room.name == room_name
        
        # Step 2: Generate participant token for caller
        token = full_system['auth'].create_participant_token(
            identity=caller_identity,
            room_name=room_name
        )
        
        assert token is not None
        
        # Step 3: Simulate room started webhook
        room_started_event = {
            "event": "room_started",
            "room": {
                "name": room_name,
                "sid": "room_123",
                "creation_time": int(time.time())
            }
        }
        
        await full_system['integration'].handle_room_started(room_started_event)
        full_system['voice_agent'].join_room.assert_called_once_with(room_name)
        
        # Step 4: Simulate participant joined webhook
        participant_joined_event = {
            "event": "participant_joined",
            "room": {"name": room_name},
            "participant": {
                "identity": caller_identity,
                "name": "Caller",
                "sid": "participant_123"
            }
        }
        
        await full_system['integration'].handle_participant_joined(participant_joined_event)
        full_system['voice_agent'].start_processing.assert_called_once_with(caller_identity)
        
        # Step 5: Simulate audio processing
        audio_data = b"incoming_audio_data"
        processed_audio = await full_system['integration'].process_audio_track(audio_data)
        
        assert processed_audio == b"audio_response"
        full_system['voice_agent'].process_audio.assert_called_once_with(audio_data)
        full_system['voice_agent'].synthesize_speech.assert_called_once()
        
        # Step 6: Verify system monitoring
        health_checks = await full_system['monitor'].run_health_checks()
        
        assert "timestamp" in health_checks
        assert "checks" in health_checks
    
    @pytest.mark.asyncio
    async def test_recording_integration_flow(self, full_system):
        """Test integration of call recording with egress service."""
        
        room_name = "recorded_call_room"
        
        # Step 1: Create room
        mock_room = Mock()
        mock_room.name = room_name
        full_system['api'].client.room.create_room = AsyncMock(return_value=mock_room)
        
        room = await full_system['api'].create_room(room_name)
        
        # Step 2: Start recording
        mock_egress_response = Mock()
        mock_egress_response.egress_id = "egress_123"
        full_system['egress'].egress_client.start_room_composite_egress = AsyncMock(
            return_value=mock_egress_response
        )
        
        output_config = full_system['egress'].create_s3_output_config(
            filename=f"{room_name}_recording.mp4",
            bucket="recordings-bucket",
            access_key="access_key",
            secret="secret_key"
        )
        
        egress_id = await full_system['egress'].start_room_recording(
            room_name=room_name,
            output_config=output_config
        )
        
        assert egress_id == "egress_123"
        
        # Step 3: Verify recording started webhook handling
        recording_started_event = {
            "event": "egress_started",
            "egress_info": {
                "egress_id": egress_id,
                "room_name": room_name,
                "status": "EGRESS_STARTING"
            }
        }
        
        # Process webhook
        await full_system['webhooks'].handle_egress_started(recording_started_event)
        
        # Verify recording is tracked
        assert egress_id in full_system['webhooks'].active_recordings
    
    @pytest.mark.asyncio
    async def test_streaming_integration_flow(self, full_system):
        """Test integration of streaming with ingress service."""
        
        room_name = "streaming_room"
        streamer_identity = "streamer_123"
        
        # Step 1: Create RTMP ingress
        mock_ingress_response = Mock()
        mock_ingress_response.ingress_id = "ingress_456"
        mock_ingress_response.url = "rtmp://test.com/live"
        mock_ingress_response.stream_key = "stream_key_456"
        
        full_system['ingress'].ingress_client.create_ingress = AsyncMock(
            return_value=mock_ingress_response
        )
        
        ingress_info = await full_system['ingress'].create_rtmp_ingress(
            name="test_stream",
            room_name=room_name,
            participant_identity=streamer_identity,
            participant_name="Test Streamer"
        )
        
        assert ingress_info["ingress_id"] == "ingress_456"
        assert ingress_info["url"] == "rtmp://test.com/live"
        
        # Step 2: Simulate ingress started webhook
        ingress_started_event = {
            "event": "ingress_started",
            "ingress_info": {
                "ingress_id": "ingress_456",
                "name": "test_stream",
                "room_name": room_name,
                "participant_identity": streamer_identity,
                "state": "INGRESS_STARTING"
            }
        }
        
        await full_system['webhooks'].handle_ingress_started(ingress_started_event)
        
        # Step 3: Simulate participant joined from ingress
        participant_joined_event = {
            "event": "participant_joined",
            "room": {"name": room_name},
            "participant": {
                "identity": streamer_identity,
                "name": "Test Streamer",
                "sid": "participant_456"
            }
        }
        
        await full_system['integration'].handle_participant_joined(participant_joined_event)
        full_system['voice_agent'].start_processing.assert_called_with(streamer_identity)
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, full_system):
        """Test error recovery and retry mechanisms."""
        
        room_name = "error_test_room"
        
        # Step 1: Simulate API failure
        full_system['api'].client.room.create_room = AsyncMock(
            side_effect=[
                Exception("Temporary API failure"),
                Exception("Another failure"),
                Mock(name=room_name)  # Success on third try
            ]
        )
        
        # Step 2: Test retry mechanism
        with patch('asyncio.sleep'):  # Mock sleep for faster testing
            room = await full_system['api'].create_room_with_retry(
                room_name, max_retries=3
            )
        
        # Should succeed after retries
        assert room.name == room_name
        assert full_system['api'].client.room.create_room.call_count == 3
        
        # Step 3: Test monitoring of failures
        full_system['monitor'].record_connection_failure()
        full_system['monitor'].record_connection_failure()
        full_system['monitor'].record_connection_success()
        
        metrics = full_system['monitor'].get_metrics()
        assert metrics["connections"]["failed"] == 2
        assert metrics["connections"]["successful"] == 1
    
    @pytest.mark.asyncio
    async def test_security_validation_flow(self, full_system):
        """Test security validation throughout the flow."""
        
        # Step 1: Test JWT token validation
        token = full_system['auth'].create_participant_token(
            identity="test_user",
            room_name="secure_room"
        )
        
        is_valid = full_system['security'].validate_jwt_token(token, "test_secret")
        assert is_valid is True
        
        # Step 2: Test suspicious activity detection
        suspicious_ip = "192.168.1.100"
        
        # Simulate multiple failed attempts
        for _ in range(10):
            full_system['security'].record_failed_attempt(suspicious_ip)
        
        is_suspicious = full_system['security'].is_suspicious_activity(suspicious_ip)
        assert is_suspicious is True
        
        # Step 3: Test sensitive data masking
        log_message = f"Authentication failed for token: {token}"
        masked_message = full_system['security'].mask_sensitive_data(log_message)
        
        assert token not in masked_message
        assert "***MASKED***" in masked_message
    
    @pytest.mark.asyncio
    async def test_performance_optimization_flow(self, full_system):
        """Test performance optimization throughout the flow."""
        
        # Step 1: Test connection pooling
        conn1 = full_system['api'].get_connection()
        conn2 = full_system['api'].get_connection()
        
        # Should reuse connection
        assert conn1 is conn2
        
        # Step 2: Test concurrent room limits
        max_rooms = 5
        full_system['monitor'].set_max_concurrent_rooms(max_rooms)
        
        # Create rooms up to limit
        for i in range(max_rooms):
            assert full_system['monitor'].can_create_room() is True
            full_system['monitor'].add_active_room(f"room_{i}")
        
        # Should reject additional rooms
        assert full_system['monitor'].can_create_room() is False
        
        # Step 3: Test latency tracking
        start_time = time.time()
        await asyncio.sleep(0.1)  # Simulate API call
        latency = (time.time() - start_time) * 1000
        
        full_system['monitor'].record_api_latency(latency)
        
        metrics = full_system['monitor'].get_metrics()
        assert latency in metrics["api_latency"]


class TestWebhookIntegrationFlow:
    """Integration tests for webhook handling flow."""
    
    @pytest.fixture
    def webhook_system(self):
        """Setup webhook system for testing."""
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            api_client = LiveKitAPIClient(
                "https://test.livekit.cloud", "test_key", "test_secret"
            )
            
            voice_agent = Mock()
            voice_agent.join_room = AsyncMock()
            voice_agent.start_processing = AsyncMock()
            voice_agent.stop_processing = AsyncMock()
            
            integration = LiveKitVoiceAIIntegration(api_client, voice_agent)
            webhook_handler = WebhookHandler()
            
            return {
                'api': api_client,
                'integration': integration,
                'webhooks': webhook_handler,
                'voice_agent': voice_agent
            }
    
    @pytest.mark.asyncio
    async def test_complete_webhook_flow(self, webhook_system):
        """Test complete webhook handling flow."""
        
        room_name = "webhook_test_room"
        participant_identity = "test_participant"
        
        # Step 1: Room started
        room_started_event = {
            "event": "room_started",
            "room": {"name": room_name, "sid": "room_123"}
        }
        
        await webhook_system['integration'].handle_room_started(room_started_event)
        webhook_system['voice_agent'].join_room.assert_called_once_with(room_name)
        
        # Step 2: Participant joined
        participant_joined_event = {
            "event": "participant_joined",
            "room": {"name": room_name},
            "participant": {"identity": participant_identity, "sid": "p_123"}
        }
        
        await webhook_system['integration'].handle_participant_joined(participant_joined_event)
        webhook_system['voice_agent'].start_processing.assert_called_once_with(participant_identity)
        
        # Step 3: Track published (audio)
        track_published_event = {
            "event": "track_published",
            "room": {"name": room_name},
            "participant": {"identity": participant_identity},
            "track": {"sid": "track_123", "type": "audio", "source": "microphone"}
        }
        
        await webhook_system['integration'].handle_track_published(track_published_event)
        
        # Step 4: Participant left
        participant_left_event = {
            "event": "participant_disconnected",
            "room": {"name": room_name},
            "participant": {"identity": participant_identity}
        }
        
        await webhook_system['integration'].handle_participant_left(participant_left_event)
        webhook_system['voice_agent'].stop_processing.assert_called_once_with(participant_identity)
        
        # Step 5: Room finished
        room_finished_event = {
            "event": "room_finished",
            "room": {"name": room_name, "sid": "room_123"}
        }
        
        await webhook_system['integration'].handle_room_finished(room_finished_event)


class TestSIPIntegrationFlow:
    """Integration tests for SIP integration flow."""
    
    @pytest.mark.asyncio
    async def test_sip_call_to_livekit_flow(self):
        """Test complete SIP call to LiveKit room flow."""
        
        # This would test the actual SIP configuration and call routing
        # For now, we'll test the configuration validation
        
        from scripts.validate_sip_config import validate_sip_configuration
        
        # Test SIP configuration validation
        config_path = "livekit-sip-correct.yaml"
        
        with patch('builtins.open'), \
             patch('yaml.safe_load') as mock_yaml:
            
            mock_yaml.return_value = {
                "livekit": {
                    "url": "wss://test.livekit.cloud",
                    "api_key": "test_key",
                    "api_secret": "test_secret"
                },
                "sip_trunks": [
                    {
                        "name": "test-trunk",
                        "inbound_only": True,
                        "numbers": ["+1234567890"]
                    }
                ],
                "routing": {
                    "inbound_rules": [
                        {
                            "name": "voice-ai-dispatch",
                            "match": {"to": "+1234567890"},
                            "action": {
                                "type": "livekit_room",
                                "room_name_template": "voice-ai-call-{call_id}"
                            }
                        }
                    ]
                }
            }
            
            is_valid = validate_sip_configuration(config_path)
            assert is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
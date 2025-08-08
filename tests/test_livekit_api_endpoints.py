"""
Automatic tests for all LiveKit API endpoints.
Tests all API endpoints according to requirements 7.1, 8.4, 9.3.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, UTC

# Import components for API testing
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import LiveKitEgressService
from src.services.livekit_ingress import LiveKitIngressService
from src.auth.livekit_auth import LiveKitAuthManager


class TestRoomServiceAPI:
    """Tests for RoomService API endpoints."""
    
    @pytest.fixture
    def api_client(self):
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            return LiveKitAPIClient(
                url="https://test.livekit.cloud",
                api_key="test_key",
                api_secret="test_secret"
            )
    
    @pytest.mark.asyncio
    async def test_create_room_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/CreateRoom endpoint."""
        
        # Mock successful response
        mock_room = Mock()
        mock_room.name = "test_room"
        mock_room.sid = "room_123"
        mock_room.creation_time = int(time.time())
        mock_room.empty_timeout = 300
        mock_room.departure_timeout = 20
        mock_room.max_participants = 10
        mock_room.metadata = '{"test": "data"}'
        
        api_client.client.room.create_room = AsyncMock(return_value=mock_room)
        
        # Test room creation
        room = await api_client.create_room(
            name="test_room",
            empty_timeout=300,
            departure_timeout=20,
            max_participants=10,
            metadata={"test": "data"}
        )
        
        # Verify response
        assert room.name == "test_room"
        assert room.sid == "room_123"
        assert room.max_participants == 10
        
        # Verify API call
        api_client.client.room.create_room.assert_called_once()
        call_args = api_client.client.room.create_room.call_args[0][0]
        assert call_args.name == "test_room"
        assert call_args.empty_timeout == 300
        assert call_args.departure_timeout == 20
        assert call_args.max_participants == 10
    
    @pytest.mark.asyncio
    async def test_list_rooms_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/ListRooms endpoint."""
        
        # Mock response with multiple rooms
        mock_rooms = [
            Mock(name="room1", sid="r1", num_participants=2),
            Mock(name="room2", sid="r2", num_participants=0),
            Mock(name="room3", sid="r3", num_participants=5)
        ]
        mock_response = Mock()
        mock_response.rooms = mock_rooms
        
        api_client.client.room.list_rooms = AsyncMock(return_value=mock_response)
        
        # Test listing all rooms
        rooms = await api_client.list_rooms()
        
        assert len(rooms) == 3
        assert rooms[0].name == "room1"
        assert rooms[1].name == "room2"
        assert rooms[2].name == "room3"
        
        # Test listing specific rooms
        rooms = await api_client.list_rooms(names=["room1", "room3"])
        
        api_client.client.room.list_rooms.assert_called()
        call_args = api_client.client.room.list_rooms.call_args[0][0]
        assert call_args.names == ["room1", "room3"]
    
    @pytest.mark.asyncio
    async def test_delete_room_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/DeleteRoom endpoint."""
        
        api_client.client.room.delete_room = AsyncMock()
        
        # Test room deletion
        await api_client.delete_room("test_room")
        
        # Verify API call
        api_client.client.room.delete_room.assert_called_once()
        call_args = api_client.client.room.delete_room.call_args[0][0]
        assert call_args.room == "test_room"
    
    @pytest.mark.asyncio
    async def test_get_room_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/GetRoom endpoint."""
        
        # Mock room response
        mock_room = Mock()
        mock_room.name = "specific_room"
        mock_room.sid = "room_456"
        mock_room.num_participants = 3
        
        api_client.client.room.get_room = AsyncMock(return_value=mock_room)
        
        # Test getting specific room
        room = await api_client.get_room("specific_room")
        
        assert room.name == "specific_room"
        assert room.sid == "room_456"
        assert room.num_participants == 3
        
        # Verify API call
        api_client.client.room.get_room.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_participants_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/ListParticipants endpoint."""
        
        # Mock participants response
        mock_participants = [
            Mock(identity="user1", sid="p1", state="ACTIVE"),
            Mock(identity="user2", sid="p2", state="ACTIVE"),
            Mock(identity="user3", sid="p3", state="DISCONNECTED")
        ]
        mock_response = Mock()
        mock_response.participants = mock_participants
        
        api_client.client.room.list_participants = AsyncMock(return_value=mock_response)
        
        # Test listing participants
        participants = await api_client.list_participants("test_room")
        
        assert len(participants) == 3
        assert participants[0].identity == "user1"
        assert participants[1].identity == "user2"
        assert participants[2].identity == "user3"
        
        # Verify API call
        api_client.client.room.list_participants.assert_called_once()
        call_args = api_client.client.room.list_participants.call_args[0][0]
        assert call_args.room == "test_room"
    
    @pytest.mark.asyncio
    async def test_get_participant_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/GetParticipant endpoint."""
        
        # Mock participant response
        mock_participant = Mock()
        mock_participant.identity = "specific_user"
        mock_participant.sid = "p_123"
        mock_participant.state = "ACTIVE"
        mock_participant.joined_at = int(time.time())
        
        api_client.client.room.get_participant = AsyncMock(return_value=mock_participant)
        
        # Test getting specific participant
        participant = await api_client.get_participant("test_room", "specific_user")
        
        assert participant.identity == "specific_user"
        assert participant.sid == "p_123"
        assert participant.state == "ACTIVE"
        
        # Verify API call
        api_client.client.room.get_participant.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_participant_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/RemoveParticipant endpoint."""
        
        api_client.client.room.remove_participant = AsyncMock()
        
        # Test participant removal
        await api_client.remove_participant("test_room", "user_to_remove")
        
        # Verify API call
        api_client.client.room.remove_participant.assert_called_once()
        call_args = api_client.client.room.remove_participant.call_args[0][0]
        assert call_args.room == "test_room"
        assert call_args.identity == "user_to_remove"
    
    @pytest.mark.asyncio
    async def test_mute_published_track_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/MutePublishedTrack endpoint."""
        
        api_client.client.room.mute_published_track = AsyncMock()
        
        # Test track muting
        await api_client.mute_track(
            room_name="test_room",
            identity="user123",
            track_sid="track_456",
            muted=True
        )
        
        # Verify API call
        api_client.client.room.mute_published_track.assert_called_once()
        call_args = api_client.client.room.mute_published_track.call_args[0][0]
        assert call_args.room == "test_room"
        assert call_args.identity == "user123"
        assert call_args.track_sid == "track_456"
        assert call_args.muted is True
    
    @pytest.mark.asyncio
    async def test_update_participant_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/UpdateParticipant endpoint."""
        
        mock_participant = Mock()
        mock_participant.identity = "updated_user"
        
        api_client.client.room.update_participant = AsyncMock(return_value=mock_participant)
        
        # Test participant update
        participant = await api_client.update_participant(
            room_name="test_room",
            identity="user123",
            metadata='{"updated": true}',
            permission={"canPublish": False}
        )
        
        assert participant.identity == "updated_user"
        
        # Verify API call
        api_client.client.room.update_participant.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_data_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/SendData endpoint."""
        
        api_client.client.room.send_data = AsyncMock()
        
        # Test data sending
        await api_client.send_data(
            room_name="test_room",
            data=b"test_data",
            kind="reliable",
            destination_sids=["p1", "p2"]
        )
        
        # Verify API call
        api_client.client.room.send_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_subscriptions_endpoint(self, api_client):
        """Test /twirp/livekit.RoomService/UpdateSubscriptions endpoint."""
        
        api_client.client.room.update_subscriptions = AsyncMock()
        
        # Test subscription update
        await api_client.update_subscriptions(
            room_name="test_room",
            identity="user123",
            track_sids=["track1", "track2"],
            subscribe=True
        )
        
        # Verify API call
        api_client.client.room.update_subscriptions.assert_called_once()


class TestEgressServiceAPI:
    """Tests for Egress Service API endpoints."""
    
    @pytest.fixture
    def egress_service(self):
        mock_client = Mock()
        with patch('src.services.livekit_egress.EgressClient'):
            return LiveKitEgressService(mock_client)
    
    @pytest.mark.asyncio
    async def test_start_room_composite_egress_endpoint(self, egress_service):
        """Test StartRoomCompositeEgress endpoint."""
        
        # Mock egress response
        mock_response = Mock()
        mock_response.egress_id = "egress_123"
        mock_response.status = "EGRESS_STARTING"
        
        egress_service.egress_client.start_room_composite_egress = AsyncMock(
            return_value=mock_response
        )
        
        # Test room recording start
        output_config = {
            "file": {
                "filename": "recording.mp4",
                "s3": {
                    "bucket": "recordings",
                    "access_key": "access",
                    "secret": "secret"
                }
            }
        }
        
        egress_id = await egress_service.start_room_recording(
            room_name="test_room",
            output_config=output_config
        )
        
        assert egress_id == "egress_123"
        
        # Verify API call
        egress_service.egress_client.start_room_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_track_composite_egress_endpoint(self, egress_service):
        """Test StartTrackCompositeEgress endpoint."""
        
        mock_response = Mock()
        mock_response.egress_id = "track_egress_456"
        
        egress_service.egress_client.start_track_composite_egress = AsyncMock(
            return_value=mock_response
        )
        
        # Test track composite egress
        egress_id = await egress_service.start_track_composite_egress(
            room_name="test_room",
            audio_track_id="audio_123",
            video_track_id="video_456",
            output_config={"file": {"filename": "track_recording.mp4"}}
        )
        
        assert egress_id == "track_egress_456"
        egress_service.egress_client.start_track_composite_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_track_egress_endpoint(self, egress_service):
        """Test StartTrackEgress endpoint."""
        
        mock_response = Mock()
        mock_response.egress_id = "single_track_789"
        
        egress_service.egress_client.start_track_egress = AsyncMock(
            return_value=mock_response
        )
        
        # Test single track egress
        egress_id = await egress_service.start_track_egress(
            room_name="test_room",
            track_id="track_123",
            output_config={"file": {"filename": "single_track.mp4"}}
        )
        
        assert egress_id == "single_track_789"
        egress_service.egress_client.start_track_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_egress_endpoint(self, egress_service):
        """Test ListEgress endpoint."""
        
        mock_egress_list = [
            Mock(egress_id="e1", status="EGRESS_ACTIVE"),
            Mock(egress_id="e2", status="EGRESS_COMPLETE"),
            Mock(egress_id="e3", status="EGRESS_FAILED")
        ]
        mock_response = Mock()
        mock_response.items = mock_egress_list
        
        egress_service.egress_client.list_egress = AsyncMock(return_value=mock_response)
        
        # Test egress listing
        egress_list = await egress_service.list_egress(room_name="test_room")
        
        assert len(egress_list) == 3
        assert egress_list[0].egress_id == "e1"
        assert egress_list[1].status == "EGRESS_COMPLETE"
        
        egress_service.egress_client.list_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_egress_endpoint(self, egress_service):
        """Test StopEgress endpoint."""
        
        mock_response = Mock()
        mock_response.egress_id = "egress_to_stop"
        mock_response.status = "EGRESS_ENDING"
        
        egress_service.egress_client.stop_egress = AsyncMock(return_value=mock_response)
        
        # Test egress stopping
        result = await egress_service.stop_egress("egress_to_stop")
        
        assert result.egress_id == "egress_to_stop"
        assert result.status == "EGRESS_ENDING"
        
        egress_service.egress_client.stop_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_layout_endpoint(self, egress_service):
        """Test UpdateLayout endpoint."""
        
        mock_response = Mock()
        mock_response.egress_id = "layout_egress"
        
        egress_service.egress_client.update_layout = AsyncMock(return_value=mock_response)
        
        # Test layout update
        result = await egress_service.update_layout(
            egress_id="layout_egress",
            layout="grid"
        )
        
        assert result.egress_id == "layout_egress"
        egress_service.egress_client.update_layout.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_stream_endpoint(self, egress_service):
        """Test UpdateStream endpoint."""
        
        mock_response = Mock()
        mock_response.egress_id = "stream_egress"
        
        egress_service.egress_client.update_stream = AsyncMock(return_value=mock_response)
        
        # Test stream update
        result = await egress_service.update_stream(
            egress_id="stream_egress",
            add_output_urls=["rtmp://new-stream.com/live"],
            remove_output_urls=["rtmp://old-stream.com/live"]
        )
        
        assert result.egress_id == "stream_egress"
        egress_service.egress_client.update_stream.assert_called_once()


class TestIngressServiceAPI:
    """Tests for Ingress Service API endpoints."""
    
    @pytest.fixture
    def ingress_service(self):
        mock_client = Mock()
        with patch('src.services.livekit_ingress.IngressClient'):
            return LiveKitIngressService(mock_client)
    
    @pytest.mark.asyncio
    async def test_create_ingress_endpoint(self, ingress_service):
        """Test CreateIngress endpoint."""
        
        # Mock ingress response
        mock_response = Mock()
        mock_response.ingress_id = "ingress_123"
        mock_response.name = "test_ingress"
        mock_response.url = "rtmp://test.com/live"
        mock_response.stream_key = "stream_key_123"
        mock_response.state = "INGRESS_STARTING"
        
        ingress_service.ingress_client.create_ingress = AsyncMock(
            return_value=mock_response
        )
        
        # Test RTMP ingress creation
        result = await ingress_service.create_rtmp_ingress(
            name="test_ingress",
            room_name="test_room",
            participant_identity="streamer",
            participant_name="Test Streamer"
        )
        
        assert result["ingress_id"] == "ingress_123"
        assert result["url"] == "rtmp://test.com/live"
        assert result["stream_key"] == "stream_key_123"
        
        # Verify API call
        ingress_service.ingress_client.create_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_whip_ingress_endpoint(self, ingress_service):
        """Test CreateIngress endpoint for WHIP."""
        
        mock_response = Mock()
        mock_response.ingress_id = "whip_456"
        mock_response.url = "https://test.com/whip"
        mock_response.state = "INGRESS_STARTING"
        
        ingress_service.ingress_client.create_ingress = AsyncMock(
            return_value=mock_response
        )
        
        # Test WHIP ingress creation
        result = await ingress_service.create_whip_ingress(
            name="whip_test",
            room_name="test_room",
            participant_identity="whip_user"
        )
        
        assert result["ingress_id"] == "whip_456"
        assert result["url"] == "https://test.com/whip"
        
        ingress_service.ingress_client.create_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_url_ingress_endpoint(self, ingress_service):
        """Test CreateIngress endpoint for URL input."""
        
        mock_response = Mock()
        mock_response.ingress_id = "url_789"
        mock_response.state = "INGRESS_STARTING"
        
        ingress_service.ingress_client.create_ingress = AsyncMock(
            return_value=mock_response
        )
        
        # Test URL ingress creation
        result = await ingress_service.create_url_ingress(
            name="url_test",
            room_name="test_room",
            participant_identity="url_user",
            url="https://example.com/video.mp4"
        )
        
        assert result["ingress_id"] == "url_789"
        ingress_service.ingress_client.create_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_ingress_endpoint(self, ingress_service):
        """Test ListIngress endpoint."""
        
        mock_ingress_list = [
            Mock(ingress_id="i1", name="ingress1", state="INGRESS_ACTIVE"),
            Mock(ingress_id="i2", name="ingress2", state="INGRESS_COMPLETE"),
            Mock(ingress_id="i3", name="ingress3", state="INGRESS_FAILED")
        ]
        mock_response = Mock()
        mock_response.items = mock_ingress_list
        
        ingress_service.ingress_client.list_ingress = AsyncMock(return_value=mock_response)
        
        # Test ingress listing
        ingress_list = await ingress_service.list_ingress(room_name="test_room")
        
        assert len(ingress_list) == 3
        assert ingress_list[0].ingress_id == "i1"
        assert ingress_list[1].state == "INGRESS_COMPLETE"
        
        ingress_service.ingress_client.list_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_ingress_endpoint(self, ingress_service):
        """Test DeleteIngress endpoint."""
        
        mock_response = Mock()
        mock_response.ingress_id = "ingress_to_delete"
        
        ingress_service.ingress_client.delete_ingress = AsyncMock(return_value=mock_response)
        
        # Test ingress deletion
        result = await ingress_service.delete_ingress("ingress_to_delete")
        
        assert result.ingress_id == "ingress_to_delete"
        ingress_service.ingress_client.delete_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_ingress_endpoint(self, ingress_service):
        """Test UpdateIngress endpoint."""
        
        mock_response = Mock()
        mock_response.ingress_id = "ingress_to_update"
        mock_response.name = "updated_ingress"
        
        ingress_service.ingress_client.update_ingress = AsyncMock(return_value=mock_response)
        
        # Test ingress update
        result = await ingress_service.update_ingress(
            ingress_id="ingress_to_update",
            name="updated_ingress",
            room_name="new_room",
            participant_name="Updated Participant"
        )
        
        assert result.ingress_id == "ingress_to_update"
        assert result.name == "updated_ingress"
        
        ingress_service.ingress_client.update_ingress.assert_called_once()


class TestSIPServiceAPI:
    """Tests for SIP Service API endpoints."""
    
    @pytest.fixture
    def api_client(self):
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            return LiveKitAPIClient(
                url="https://test.livekit.cloud",
                api_key="test_key",
                api_secret="test_secret"
            )
    
    @pytest.mark.asyncio
    async def test_create_sip_trunk_endpoint(self, api_client):
        """Test CreateSIPTrunk endpoint."""
        
        mock_trunk = Mock()
        mock_trunk.sip_trunk_id = "trunk_123"
        mock_trunk.name = "test_trunk"
        
        api_client.client.sip.create_sip_inbound_trunk = AsyncMock(return_value=mock_trunk)
        
        # Test SIP trunk creation
        trunk = await api_client.create_sip_inbound_trunk(
            name="test_trunk",
            numbers=["+1234567890"],
            allowed_addresses=["0.0.0.0/0"],
            auth_username="user",
            auth_password="pass"
        )
        
        assert trunk.sip_trunk_id == "trunk_123"
        assert trunk.name == "test_trunk"
        
        api_client.client.sip.create_sip_inbound_trunk.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_sip_dispatch_rule_endpoint(self, api_client):
        """Test CreateSIPDispatchRule endpoint."""
        
        mock_rule = Mock()
        mock_rule.sip_dispatch_rule_id = "rule_456"
        mock_rule.name = "voice_ai_rule"
        
        api_client.client.sip.create_sip_dispatch_rule = AsyncMock(return_value=mock_rule)
        
        # Test dispatch rule creation
        rule = await api_client.create_sip_dispatch_rule(
            name="voice_ai_rule",
            trunk_ids=["trunk_123"],
            rule={
                "dispatchRuleDirect": {
                    "roomName": "voice-ai-call-{call_id}",
                    "pin": ""
                }
            }
        )
        
        assert rule.sip_dispatch_rule_id == "rule_456"
        assert rule.name == "voice_ai_rule"
        
        api_client.client.sip.create_sip_dispatch_rule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_sip_participant_endpoint(self, api_client):
        """Test CreateSIPParticipant endpoint."""
        
        mock_participant = Mock()
        mock_participant.sip_call_id = "call_789"
        mock_participant.participant_identity = "sip_caller"
        
        api_client.client.sip.create_sip_participant = AsyncMock(return_value=mock_participant)
        
        # Test SIP participant creation
        participant = await api_client.create_sip_participant(
            sip_trunk_id="trunk_123",
            sip_call_to="+1234567890",
            room_name="test_room",
            participant_identity="sip_caller"
        )
        
        assert participant.sip_call_id == "call_789"
        assert participant.participant_identity == "sip_caller"
        
        api_client.client.sip.create_sip_participant.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_sip_trunks_endpoint(self, api_client):
        """Test ListSIPTrunk endpoint."""
        
        mock_trunks = [
            Mock(sip_trunk_id="t1", name="trunk1"),
            Mock(sip_trunk_id="t2", name="trunk2")
        ]
        mock_response = Mock()
        mock_response.items = mock_trunks
        
        api_client.client.sip.list_sip_trunk = AsyncMock(return_value=mock_response)
        
        # Test trunk listing
        trunks = await api_client.list_sip_trunks()
        
        assert len(trunks) == 2
        assert trunks[0].sip_trunk_id == "t1"
        assert trunks[1].name == "trunk2"
        
        api_client.client.sip.list_sip_trunk.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_sip_trunk_endpoint(self, api_client):
        """Test DeleteSIPTrunk endpoint."""
        
        api_client.client.sip.delete_sip_trunk = AsyncMock()
        
        # Test trunk deletion
        await api_client.delete_sip_trunk("trunk_to_delete")
        
        api_client.client.sip.delete_sip_trunk.assert_called_once()


class TestAPIErrorHandling:
    """Tests for API error handling across all endpoints."""
    
    @pytest.fixture
    def api_client(self):
        with patch('src.clients.livekit_api_client.api.LiveKitAPI'):
            return LiveKitAPIClient(
                url="https://test.livekit.cloud",
                api_key="test_key",
                api_secret="test_secret"
            )
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, api_client):
        """Test handling of HTTP errors."""
        
        from livekit.api import TwirpError
        
        # Test different HTTP error codes
        error_cases = [
            (400, "INVALID_ARGUMENT", "Invalid room name"),
            (401, "UNAUTHENTICATED", "Invalid API key"),
            (403, "PERMISSION_DENIED", "Insufficient permissions"),
            (404, "NOT_FOUND", "Room not found"),
            (429, "RESOURCE_EXHAUSTED", "Rate limit exceeded"),
            (500, "INTERNAL", "Internal server error")
        ]
        
        for status_code, error_code, message in error_cases:
            api_client.client.room.create_room = AsyncMock(
                side_effect=TwirpError(error_code, message)
            )
            
            with pytest.raises(TwirpError) as exc_info:
                await api_client.create_room("test_room")
            
            assert exc_info.value.code == error_code
            assert message in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, api_client):
        """Test handling of network errors."""
        
        import aiohttp
        
        # Test connection timeout
        api_client.client.room.create_room = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                connection_key=None, os_error=None
            )
        )
        
        with pytest.raises(aiohttp.ClientConnectorError):
            await api_client.create_room("test_room")
        
        # Test timeout error
        api_client.client.room.create_room = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        
        with pytest.raises(asyncio.TimeoutError):
            await api_client.create_room("test_room")
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, api_client):
        """Test retry mechanism for transient errors."""
        
        # Mock transient failure followed by success
        mock_room = Mock(name="test_room")
        api_client.client.room.create_room = AsyncMock(
            side_effect=[
                Exception("Temporary network error"),
                Exception("Another temporary error"),
                mock_room  # Success on third try
            ]
        )
        
        # Test with retry mechanism
        with patch('asyncio.sleep'):  # Mock sleep for faster testing
            room = await api_client.create_room_with_retry(
                "test_room", max_retries=3, backoff_factor=1.0
            )
        
        assert room.name == "test_room"
        assert api_client.client.room.create_room.call_count == 3
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, api_client):
        """Test rate limit handling."""
        
        from livekit.api import TwirpError
        
        # Mock rate limit error
        api_client.client.room.create_room = AsyncMock(
            side_effect=TwirpError("RESOURCE_EXHAUSTED", "Rate limit exceeded")
        )
        
        # Should handle rate limit gracefully
        with pytest.raises(TwirpError) as exc_info:
            await api_client.create_room("test_room")
        
        assert exc_info.value.code == "RESOURCE_EXHAUSTED"
        
        # Should implement exponential backoff for rate limits
        with patch('asyncio.sleep') as mock_sleep:
            try:
                await api_client.create_room_with_retry("test_room", max_retries=2)
            except TwirpError:
                pass
            
            # Should have called sleep for backoff
            assert mock_sleep.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
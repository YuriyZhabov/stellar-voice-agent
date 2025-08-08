"""Unit tests for CallOrchestrator."""

import asyncio
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.orchestrator import (
    CallOrchestrator,
    CallContext,
    CallMetrics,
    CallStatus,
    AudioStreamState,
    HealthStatus
)
from src.clients.deepgram_stt import DeepgramSTTClient, TranscriptionResult
from src.clients.openai_llm import OpenAILLMClient, LLMResponse, TokenUsage
from src.clients.cartesia_tts import CartesiaTTSClient, TTSResponse, AudioFormat
from src.conversation.state_machine import ConversationState
from src.conversation.dialogue_manager import ConversationTurn


@pytest.fixture
def mock_stt_client():
    """Mock STT client."""
    client = AsyncMock(spec=DeepgramSTTClient)
    client.health_check.return_value = True
    client.transcribe_batch.return_value = TranscriptionResult(
        text="Hello, how are you?",
        confidence=0.95,
        language="en-US",
        duration=1.5,
        alternatives=["Hello, how are you?"],
        is_final=True
    )
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = AsyncMock(spec=OpenAILLMClient)
    client.health_check.return_value = True
    client.create_conversation_context.return_value = MagicMock()
    return client


@pytest.fixture
def mock_tts_client():
    """Mock TTS client."""
    client = AsyncMock(spec=CartesiaTTSClient)
    client.health_check.return_value = True
    client.synthesize_batch.return_value = TTSResponse(
        audio_data=b"fake_audio_data",
        duration=2.0,
        format=AudioFormat.WAV,
        sample_rate=16000,
        characters_processed=20,
        synthesis_time=0.5
    )
    # Mock the AudioFormat enum
    client.AudioFormat = AudioFormat
    return client


@pytest.fixture
def call_context():
    """Sample call context."""
    return CallContext(
        call_id=str(uuid4()),
        caller_number="+1234567890",
        start_time=datetime.now(UTC),
        livekit_room="room_123",
        metadata={"test": True}
    )


@pytest.fixture
def orchestrator(mock_stt_client, mock_llm_client, mock_tts_client):
    """CallOrchestrator instance with mocked clients."""
    with patch('src.orchestrator.get_settings') as mock_settings:
        # Mock settings to avoid validation errors
        mock_settings.return_value.context_window_size = 4000
        mock_settings.return_value.cartesia_voice_id = "test_voice"
        mock_settings.return_value.audio_sample_rate = 16000
        
        return CallOrchestrator(
            stt_client=mock_stt_client,
            llm_client=mock_llm_client,
            tts_client=mock_tts_client,
            max_concurrent_calls=5,
            audio_buffer_size=1024,
            response_timeout=30.0
        )


class TestCallOrchestrator:
    """Test cases for CallOrchestrator."""
    
    def test_initialization(self, orchestrator, mock_stt_client, mock_llm_client, mock_tts_client):
        """Test orchestrator initialization."""
        assert orchestrator.stt_client == mock_stt_client
        assert orchestrator.llm_client == mock_llm_client
        assert orchestrator.tts_client == mock_tts_client
        assert orchestrator.max_concurrent_calls == 5
        assert orchestrator.audio_buffer_size == 1024
        assert orchestrator.response_timeout == 30.0
        assert len(orchestrator.active_calls) == 0
        assert orchestrator.total_calls_handled == 0
    
    @pytest.mark.asyncio
    async def test_handle_call_start_success(self, orchestrator, call_context):
        """Test successful call start handling."""
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            
            await orchestrator.handle_call_start(call_context)
            
            # Verify call is tracked
            assert call_context.call_id in orchestrator.active_calls
            assert call_context.call_id in orchestrator.call_metrics
            assert call_context.call_id in orchestrator.call_state_machines
            assert call_context.call_id in orchestrator.dialogue_managers
            
            # Verify metrics
            assert orchestrator.total_calls_handled == 1
            
            # Verify state machine is initialized
            state_machine = orchestrator.call_state_machines[call_context.call_id]
            assert state_machine.current_state == ConversationState.LISTENING
    
    @pytest.mark.asyncio
    async def test_handle_call_start_max_concurrent_limit(self, orchestrator):
        """Test call rejection when max concurrent limit is reached."""
        # Fill up to max concurrent calls
        for i in range(orchestrator.max_concurrent_calls):
            call_ctx = CallContext(
                call_id=f"call_{i}",
                caller_number=f"+123456789{i}",
                start_time=datetime.now(UTC),
                livekit_room=f"room_{i}"
            )
            with patch('src.orchestrator.get_settings') as mock_settings:
                mock_settings.return_value.context_window_size = 4000
                await orchestrator.handle_call_start(call_ctx)
        
        # Try to add one more call
        overflow_call = CallContext(
            call_id="overflow_call",
            caller_number="+9999999999",
            start_time=datetime.now(UTC),
            livekit_room="overflow_room"
        )
        
        with patch.object(orchestrator, '_handle_call_rejection') as mock_rejection:
            await orchestrator.handle_call_start(overflow_call)
            mock_rejection.assert_called_once_with(overflow_call, "max_concurrent_calls_reached")
    
    @pytest.mark.asyncio
    async def test_handle_audio_received(self, orchestrator, call_context):
        """Test audio data handling."""
        # Start a call first
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        # Mock the audio processing to prevent automatic buffer clearing
        with patch.object(orchestrator, '_process_audio_buffer') as mock_process:
            # Send audio data
            audio_data = b"fake_audio_data"
            await orchestrator.handle_audio_received(call_context.call_id, audio_data)
            
            # Verify audio is buffered
            assert len(orchestrator.audio_buffers[call_context.call_id]) == 1
            assert orchestrator.audio_buffers[call_context.call_id][0] == audio_data
            
            # Verify metrics updated
            metrics = orchestrator.call_metrics[call_context.call_id]
            assert metrics.bytes_received == len(audio_data)
    
    @pytest.mark.asyncio
    async def test_handle_audio_received_unknown_call(self, orchestrator):
        """Test handling audio for unknown call."""
        # Should not raise exception
        await orchestrator.handle_audio_received("unknown_call", b"audio_data")
    
    @pytest.mark.asyncio
    async def test_process_audio_buffer(self, orchestrator, call_context, mock_stt_client):
        """Test audio buffer processing."""
        # Start a call and add audio data
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        # Add audio to buffer
        orchestrator.audio_buffers[call_context.call_id] = [b"audio1", b"audio2"]
        
        # Mock dialogue manager response
        dialogue_manager = orchestrator.dialogue_managers[call_context.call_id]
        mock_turn = ConversationTurn(
            turn_id="turn_1",
            user_input="Hello",
            assistant_response="Hi there!",
            timestamp=datetime.now(UTC),
            processing_time=1.0
        )
        dialogue_manager.process_user_input = AsyncMock(return_value=("Hi there!", mock_turn))
        
        # Mock TTS response
        with patch.object(orchestrator, '_generate_audio_response') as mock_tts:
            await orchestrator._process_audio_buffer(call_context.call_id)
            
            # Verify STT was called
            mock_stt_client.transcribe_batch.assert_called_once()
            
            # Verify dialogue manager was called
            dialogue_manager.process_user_input.assert_called_once()
            
            # Verify TTS was called
            mock_tts.assert_called_once_with(call_context.call_id, "Hi there!")
            
            # Verify buffer was cleared
            assert len(orchestrator.audio_buffers[call_context.call_id]) == 0
    
    @pytest.mark.asyncio
    async def test_process_audio_buffer_low_confidence(self, orchestrator, call_context, mock_stt_client):
        """Test handling low confidence transcription."""
        # Mock low confidence transcription
        mock_stt_client.transcribe_batch.return_value = TranscriptionResult(
            text="unclear",
            confidence=0.3,  # Low confidence
            language="en-US",
            duration=1.0
        )
        
        # Start call and add audio
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        orchestrator.audio_buffers[call_context.call_id] = [b"unclear_audio"]
        
        # Process audio
        await orchestrator._process_audio_buffer(call_context.call_id)
        
        # Verify state machine returned to listening
        state_machine = orchestrator.call_state_machines[call_context.call_id]
        assert state_machine.current_state == ConversationState.LISTENING
    
    @pytest.mark.asyncio
    async def test_generate_audio_response(self, orchestrator, call_context, mock_tts_client):
        """Test audio response generation."""
        # Start call
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            mock_settings.return_value.cartesia_voice_id = "test_voice"
            mock_settings.return_value.audio_sample_rate = 16000
            await orchestrator.handle_call_start(call_context)
        
        # Generate response
        response_text = "Hello, how can I help you?"
        await orchestrator._generate_audio_response(call_context.call_id, response_text)
        
        # Verify TTS was called
        mock_tts_client.synthesize_batch.assert_called_once()
        
        # Verify metrics updated
        metrics = orchestrator.call_metrics[call_context.call_id]
        assert metrics.bytes_sent > 0
        assert metrics.tts_latency > 0
    
    @pytest.mark.asyncio
    async def test_handle_call_end(self, orchestrator, call_context):
        """Test call end handling."""
        # Start call first
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        # End call
        await orchestrator.handle_call_end(call_context)
        
        # Verify call is removed from active calls
        assert call_context.call_id not in orchestrator.active_calls
        
        # Verify metrics updated
        assert orchestrator.successful_calls == 1
        
        # Verify resources cleaned up
        assert call_context.call_id not in orchestrator.call_state_machines
        assert call_context.call_id not in orchestrator.dialogue_managers
        assert call_context.call_id not in orchestrator.audio_buffers
    
    @pytest.mark.asyncio
    async def test_cleanup_call_resources(self, orchestrator, call_context):
        """Test call resource cleanup."""
        # Start call and populate resources
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        call_id = call_context.call_id
        
        # Verify resources exist
        assert call_id in orchestrator.active_calls
        assert call_id in orchestrator.call_state_machines
        assert call_id in orchestrator.dialogue_managers
        
        # Clean up resources
        await orchestrator._cleanup_call_resources(call_id)
        
        # Verify resources removed
        assert call_id not in orchestrator.active_calls
        assert call_id not in orchestrator.call_state_machines
        assert call_id not in orchestrator.dialogue_managers
        assert call_id not in orchestrator.audio_streams
        assert call_id not in orchestrator.audio_stream_states
        assert call_id not in orchestrator.audio_buffers
        assert call_id not in orchestrator.processing_locks
    
    @pytest.mark.asyncio
    async def test_health_status(self, orchestrator):
        """Test health status reporting."""
        health_status = await orchestrator.get_health_status()
        
        assert isinstance(health_status, HealthStatus)
        assert health_status.is_healthy is True
        assert health_status.status == "healthy"
        assert "stt_client" in health_status.components
        assert "llm_client" in health_status.components
        assert "tts_client" in health_status.components
        assert "system" in health_status.components
        
        # Check details
        assert "active_calls" in health_status.details
        assert "total_calls_handled" in health_status.details
        assert "success_rate" in health_status.details
    
    @pytest.mark.asyncio
    async def test_health_status_unhealthy_component(self, orchestrator, mock_stt_client):
        """Test health status with unhealthy component."""
        # Make STT client unhealthy
        mock_stt_client.health_check.return_value = False
        
        health_status = await orchestrator.get_health_status()
        
        assert health_status.is_healthy is False
        assert health_status.status == "unhealthy"
        assert health_status.components["stt_client"] is False
    
    def test_get_call_metrics_all(self, orchestrator):
        """Test getting all call metrics."""
        metrics = orchestrator.get_call_metrics()
        
        assert "total_calls" in metrics
        assert "successful_calls" in metrics
        assert "failed_calls" in metrics
        assert "active_calls" in metrics
        assert "success_rate" in metrics
        assert "individual_calls" in metrics
        
        assert metrics["total_calls"] == 0
        assert metrics["successful_calls"] == 0
        assert metrics["active_calls"] == 0
    
    @pytest.mark.asyncio
    async def test_get_call_metrics_specific(self, orchestrator, call_context):
        """Test getting specific call metrics."""
        # Start call to create metrics
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        metrics = orchestrator.get_call_metrics(call_context.call_id)
        
        assert "call_id" in metrics
        assert metrics["call_id"] == call_context.call_id
        assert "start_time" in metrics
        assert "total_turns" in metrics
    
    def test_get_call_metrics_nonexistent(self, orchestrator):
        """Test getting metrics for nonexistent call."""
        metrics = orchestrator.get_call_metrics("nonexistent_call")
        assert metrics == {}
    
    @pytest.mark.asyncio
    async def test_get_active_calls(self, orchestrator, call_context):
        """Test getting active calls information."""
        # Initially no active calls
        active_calls = orchestrator.get_active_calls()
        assert len(active_calls) == 0
        
        # Start a call
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        # Check active calls
        active_calls = orchestrator.get_active_calls()
        assert len(active_calls) == 1
        
        call_info = active_calls[0]
        assert call_info["call_id"] == call_context.call_id
        assert call_info["caller_number"] == call_context.caller_number
        assert "state" in call_info
        assert "audio_state" in call_info
        assert "metrics" in call_info
    
    def test_event_handlers(self, orchestrator):
        """Test event handler registration."""
        start_handler = AsyncMock()
        end_handler = AsyncMock()
        error_handler = AsyncMock()
        
        orchestrator.add_call_start_handler(start_handler)
        orchestrator.add_call_end_handler(end_handler)
        orchestrator.add_error_handler(error_handler)
        
        assert start_handler in orchestrator.call_start_handlers
        assert end_handler in orchestrator.call_end_handlers
        assert error_handler in orchestrator.error_handlers
    
    @pytest.mark.asyncio
    async def test_call_start_handler_execution(self, orchestrator, call_context):
        """Test call start handler execution."""
        handler = AsyncMock()
        orchestrator.add_call_start_handler(handler)
        
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        handler.assert_called_once_with(call_context)
    
    @pytest.mark.asyncio
    async def test_call_end_handler_execution(self, orchestrator, call_context):
        """Test call end handler execution."""
        handler = AsyncMock()
        orchestrator.add_call_end_handler(handler)
        
        # Start and end call
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        await orchestrator.handle_call_end(call_context)
        
        handler.assert_called_once_with(call_context)
    
    @pytest.mark.asyncio
    async def test_error_handler_execution(self, orchestrator, call_context):
        """Test error handler execution."""
        handler = AsyncMock()
        orchestrator.add_error_handler(handler)
        
        test_error = Exception("Test error")
        await orchestrator._handle_call_error(call_context, test_error)
        
        handler.assert_called_once_with(call_context, test_error)
    
    @pytest.mark.asyncio
    async def test_concurrent_call_handling(self, orchestrator):
        """Test handling multiple concurrent calls."""
        call_contexts = []
        
        # Create multiple call contexts
        for i in range(3):
            call_ctx = CallContext(
                call_id=f"call_{i}",
                caller_number=f"+123456789{i}",
                start_time=datetime.now(UTC),
                livekit_room=f"room_{i}"
            )
            call_contexts.append(call_ctx)
        
        # Start all calls concurrently
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            
            tasks = [
                orchestrator.handle_call_start(call_ctx)
                for call_ctx in call_contexts
            ]
            await asyncio.gather(*tasks)
        
        # Verify all calls are active
        assert len(orchestrator.active_calls) == 3
        for call_ctx in call_contexts:
            assert call_ctx.call_id in orchestrator.active_calls
    
    @pytest.mark.asyncio
    async def test_audio_processing_error_handling(self, orchestrator, call_context, mock_stt_client):
        """Test error handling during audio processing."""
        # Make STT client raise an error
        mock_stt_client.transcribe_batch.side_effect = Exception("STT error")
        
        # Start call and add audio
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        orchestrator.audio_buffers[call_context.call_id] = [b"audio_data"]
        
        # Process audio - should handle error gracefully
        await orchestrator._process_audio_buffer(call_context.call_id)
        
        # Verify error metrics updated
        metrics = orchestrator.call_metrics[call_context.call_id]
        assert metrics.failed_turns == 1
        
        # Verify state machine recovered
        state_machine = orchestrator.call_state_machines[call_context.call_id]
        assert state_machine.current_state == ConversationState.LISTENING
    
    @pytest.mark.asyncio
    async def test_close_orchestrator(self, orchestrator, call_context):
        """Test orchestrator cleanup on close."""
        # Start a call
        with patch('src.orchestrator.get_settings') as mock_settings:
            mock_settings.return_value.context_window_size = 4000
            await orchestrator.handle_call_start(call_context)
        
        # Close orchestrator
        await orchestrator.close()
        
        # Verify all calls ended
        assert len(orchestrator.active_calls) == 0
        
        # Verify clients closed
        orchestrator.stt_client.close.assert_called_once()
        orchestrator.llm_client.close.assert_called_once()
        orchestrator.tts_client.close.assert_called_once()


class TestCallContext:
    """Test cases for CallContext."""
    
    def test_call_context_creation(self):
        """Test CallContext creation."""
        call_id = str(uuid4())
        caller_number = "+1234567890"
        start_time = datetime.now(UTC)
        livekit_room = "room_123"
        metadata = {"test": True}
        
        context = CallContext(
            call_id=call_id,
            caller_number=caller_number,
            start_time=start_time,
            livekit_room=livekit_room,
            metadata=metadata
        )
        
        assert context.call_id == call_id
        assert context.caller_number == caller_number
        assert context.start_time == start_time
        assert context.livekit_room == livekit_room
        assert context.metadata == metadata
    
    def test_call_context_to_dict(self):
        """Test CallContext serialization."""
        context = CallContext(
            call_id="test_call",
            caller_number="+1234567890",
            start_time=datetime.now(UTC),
            livekit_room="room_123",
            metadata={"test": True}
        )
        
        context_dict = context.to_dict()
        
        assert context_dict["call_id"] == "test_call"
        assert context_dict["caller_number"] == "+1234567890"
        assert "start_time" in context_dict
        assert context_dict["livekit_room"] == "room_123"
        assert context_dict["metadata"] == {"test": True}


class TestCallMetrics:
    """Test cases for CallMetrics."""
    
    def test_call_metrics_creation(self):
        """Test CallMetrics creation."""
        call_id = "test_call"
        start_time = datetime.now(UTC)
        
        metrics = CallMetrics(
            call_id=call_id,
            start_time=start_time
        )
        
        assert metrics.call_id == call_id
        assert metrics.start_time == start_time
        assert metrics.total_turns == 0
        assert metrics.successful_turns == 0
        assert metrics.failed_turns == 0
    
    def test_call_metrics_success_rate(self):
        """Test success rate calculation."""
        metrics = CallMetrics(
            call_id="test_call",
            start_time=datetime.now(UTC)
        )
        
        # No turns
        assert metrics.success_rate == 0.0
        
        # Some successful turns
        metrics.total_turns = 10
        metrics.successful_turns = 8
        assert metrics.success_rate == 0.8
    
    def test_call_metrics_average_response_time(self):
        """Test average response time calculation."""
        metrics = CallMetrics(
            call_id="test_call",
            start_time=datetime.now(UTC)
        )
        
        metrics.stt_latency = 0.5
        metrics.llm_latency = 1.0
        metrics.tts_latency = 0.3
        
        assert metrics.average_response_time == 1.8
    
    def test_call_metrics_to_dict(self):
        """Test CallMetrics serialization."""
        metrics = CallMetrics(
            call_id="test_call",
            start_time=datetime.now(UTC),
            total_turns=5,
            successful_turns=4
        )
        
        metrics_dict = metrics.to_dict()
        
        assert metrics_dict["call_id"] == "test_call"
        assert metrics_dict["total_turns"] == 5
        assert metrics_dict["successful_turns"] == 4
        assert metrics_dict["success_rate"] == 0.8
        assert "start_time" in metrics_dict


class TestHealthStatus:
    """Test cases for HealthStatus."""
    
    def test_health_status_creation(self):
        """Test HealthStatus creation."""
        components = {
            "stt_client": True,
            "llm_client": True,
            "tts_client": False
        }
        
        status = HealthStatus(
            is_healthy=False,
            status="unhealthy",
            components=components,
            last_check=datetime.now(UTC)
        )
        
        assert status.is_healthy is False
        assert status.status == "unhealthy"
        assert status.components == components
    
    def test_health_status_to_dict(self):
        """Test HealthStatus serialization."""
        status = HealthStatus(
            is_healthy=True,
            status="healthy",
            components={"test": True},
            last_check=datetime.now(UTC),
            details={"active_calls": 0}
        )
        
        status_dict = status.to_dict()
        
        assert status_dict["is_healthy"] is True
        assert status_dict["status"] == "healthy"
        assert status_dict["components"] == {"test": True}
        assert status_dict["details"] == {"active_calls": 0}
        assert "last_check" in status_dict
"""Tests for Deepgram STT client."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import AsyncIterator, List

from src.clients.deepgram_stt import (
    DeepgramSTTClient,
    TranscriptionResult,
    StreamingConfig,
    DeepgramMetrics,
    TranscriptionMode
)


class TestTranscriptionResult:
    """Test TranscriptionResult data class."""
    
    def test_transcription_result_creation(self):
        """Test creating a TranscriptionResult."""
        result = TranscriptionResult(
            text="Hello world",
            confidence=0.95,
            language="en-US",
            duration=1.5,
            alternatives=["Hello world", "Hello word"],
            is_final=True
        )
        
        assert result.text == "Hello world"
        assert result.confidence == 0.95
        assert result.language == "en-US"
        assert result.duration == 1.5
        assert result.alternatives == ["Hello world", "Hello word"]
        assert result.is_final is True
        assert result.channel == 0
        assert result.start_time == 0.0
        assert result.end_time == 0.0
        assert result.words == []
        assert result.metadata == {}


class TestStreamingConfig:
    """Test StreamingConfig data class."""
    
    def test_streaming_config_defaults(self):
        """Test StreamingConfig with default values."""
        config = StreamingConfig()
        
        assert config.model == "nova-2"
        assert config.language == "en-US"
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.encoding == "linear16"
        assert config.interim_results is True
        assert config.punctuate is True
        assert config.smart_format is True
        assert config.profanity_filter is False
        assert config.redact == []
        assert config.keywords == []
        assert config.utterance_end_ms == 1000
        assert config.vad_events is True
        assert config.endpointing == 300
    
    def test_streaming_config_custom(self):
        """Test StreamingConfig with custom values."""
        config = StreamingConfig(
            model="nova-2-general",
            language="es-ES",
            sample_rate=8000,
            channels=2,
            interim_results=False,
            punctuate=False,
            profanity_filter=True,
            redact=["ssn", "credit_card"],
            keywords=["hello", "world"]
        )
        
        assert config.model == "nova-2-general"
        assert config.language == "es-ES"
        assert config.sample_rate == 8000
        assert config.channels == 2
        assert config.interim_results is False
        assert config.punctuate is False
        assert config.profanity_filter is True
        assert config.redact == ["ssn", "credit_card"]
        assert config.keywords == ["hello", "world"]


class TestDeepgramMetrics:
    """Test DeepgramMetrics data class."""
    
    def test_deepgram_metrics_defaults(self):
        """Test DeepgramMetrics with default values."""
        metrics = DeepgramMetrics()
        
        assert metrics.streaming_connections == 0
        assert metrics.active_streams == 0
        assert metrics.total_audio_duration == 0.0
        assert metrics.total_transcription_time == 0.0
        assert metrics.average_confidence == 0.0
        assert metrics.reconnection_count == 0
        assert metrics.transcription_speed_ratio == 0.0
    
    def test_transcription_speed_ratio_calculation(self):
        """Test transcription speed ratio calculation."""
        metrics = DeepgramMetrics()
        metrics.total_audio_duration = 10.0
        metrics.total_transcription_time = 5.0
        
        assert metrics.transcription_speed_ratio == 0.5
        
        # Test zero division
        metrics.total_audio_duration = 0.0
        assert metrics.transcription_speed_ratio == 0.0


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('src.clients.deepgram_stt.get_settings') as mock:
        settings = MagicMock()
        settings.deepgram_api_key = "test_api_key"
        settings.deepgram_model = "nova-2"
        settings.deepgram_language = "en-US"
        settings.audio_sample_rate = 16000
        settings.audio_channels = 1
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_deepgram_client():
    """Mock Deepgram client."""
    with patch('src.clients.deepgram_stt.DeepgramClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


class TestDeepgramSTTClient:
    """Test DeepgramSTTClient class."""
    
    def test_init_with_api_key(self, mock_settings, mock_deepgram_client):
        """Test client initialization with API key."""
        client = DeepgramSTTClient(api_key="custom_key")
        
        assert client.api_key == "custom_key"
        assert client.service_name == "deepgram_stt"
        assert isinstance(client.streaming_config, StreamingConfig)
        assert isinstance(client.deepgram_metrics, DeepgramMetrics)
    
    def test_init_without_api_key(self, mock_settings, mock_deepgram_client):
        """Test client initialization without API key (uses settings)."""
        client = DeepgramSTTClient()
        
        assert client.api_key == "test_api_key"
        assert client.streaming_config.model == "nova-2"
        assert client.streaming_config.language == "en-US"
    
    def test_init_no_api_key_raises_error(self, mock_deepgram_client):
        """Test initialization raises error when no API key available."""
        with patch('src.clients.deepgram_stt.get_settings') as mock_get_settings:
            settings = MagicMock()
            settings.deepgram_api_key = None
            mock_get_settings.return_value = settings
            
            with pytest.raises(ValueError, match="Deepgram API key is required"):
                DeepgramSTTClient()
    
    def test_init_with_custom_config(self, mock_settings, mock_deepgram_client):
        """Test initialization with custom streaming config."""
        custom_config = StreamingConfig(
            model="nova-2-general",
            language="es-ES",
            sample_rate=8000
        )
        
        client = DeepgramSTTClient(streaming_config=custom_config)
        
        assert client.streaming_config.model == "nova-2-general"
        assert client.streaming_config.language == "es-ES"
        assert client.streaming_config.sample_rate == 8000
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_settings, mock_deepgram_client):
        """Test successful health check."""
        # Mock the transcribe_file response
        mock_response = MagicMock()
        mock_response.results.channels = [MagicMock()]
        mock_response.results.channels[0].alternatives = [MagicMock()]
        mock_response.results.channels[0].alternatives[0].transcript = "test"
        
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file = AsyncMock(
            return_value=mock_response
        )
        
        client = DeepgramSTTClient()
        result = await client.health_check()
        
        assert result is True
        mock_deepgram_client.listen.asyncrest.v.assert_called_with("1")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_settings, mock_deepgram_client):
        """Test health check failure."""
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        client = DeepgramSTTClient()
        result = await client.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_transcribe_batch_success(self, mock_settings, mock_deepgram_client):
        """Test successful batch transcription."""
        # Mock response
        mock_response = MagicMock()
        mock_response.results.channels = [MagicMock()]
        mock_response.results.channels[0].alternatives = [
            MagicMock(
                transcript="Hello world",
                confidence=0.95,
                words=[
                    MagicMock(word="Hello", start=0.0, end=0.5, confidence=0.9),
                    MagicMock(word="world", start=0.6, end=1.0, confidence=1.0)
                ]
            ),
            MagicMock(transcript="Hello word", confidence=0.85)
        ]
        mock_response.results.metadata = MagicMock()
        mock_response.results.metadata.duration = 1.0
        mock_response.results.metadata.model_info = MagicMock()
        mock_response.results.metadata.model_info.name = "nova-2"
        mock_response.results.metadata.model_info.version = "1.0"
        mock_response.results.metadata.request_id = "req_123"
        
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file = AsyncMock(
            return_value=mock_response
        )
        
        client = DeepgramSTTClient()
        # Use larger audio data to pass validation
        audio_data = b"fake_audio_data" * 20  # Make it larger than 100 bytes
        
        # Mock the audio validation to always pass
        with patch('src.clients.deepgram_stt.validate_audio_data') as mock_validate:
            mock_validate.return_value = MagicMock(
                is_valid=True,
                detected_format="wav",
                duration_estimate=1.0,
                file_size=len(audio_data)
            )
            
            result = await client.transcribe_batch(audio_data)
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Hello world"
        assert result.confidence == 0.95
        assert result.language == "en-US"
        assert result.is_final is True
        assert len(result.alternatives) == 1
        assert result.alternatives[0] == "Hello word"
        assert len(result.words) == 2
        assert result.words[0]["word"] == "Hello"
        assert result.metadata["model"] == "nova-2"
        assert result.metadata["request_id"] == "req_123"
        
        # Verify API call
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file.assert_called_once()
        call_args = mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file.call_args
        assert call_args[0][0]["buffer"] == audio_data
        assert call_args[0][0]["mimetype"] == "audio/wav"
        assert call_args[0][1]["model"] == "nova-2"
        assert call_args[0][1]["language"] == "en-US"
    
    @pytest.mark.asyncio
    async def test_transcribe_batch_with_options(self, mock_settings, mock_deepgram_client):
        """Test batch transcription with custom options."""
        mock_response = MagicMock()
        mock_response.results.channels = [MagicMock()]
        mock_response.results.channels[0].alternatives = [
            MagicMock(transcript="Test", confidence=0.9, words=[])
        ]
        mock_response.results.metadata = None
        
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file = AsyncMock(
            return_value=mock_response
        )
        
        client = DeepgramSTTClient()
        # Use larger audio data to pass validation
        audio_data = b"fake_audio_data" * 20  # Make it larger than 100 bytes
        custom_options = {
            "model": "nova-2-general",
            "language": "es-ES",
            "custom_param": "value"
        }
        
        # Mock the audio validation to always pass
        with patch('src.clients.deepgram_stt.validate_audio_data') as mock_validate:
            mock_validate.return_value = MagicMock(
                is_valid=True,
                detected_format="mp3",
                duration_estimate=1.0,
                file_size=len(audio_data)
            )
            
            result = await client.transcribe_batch(
                audio_data,
                mimetype="audio/mp3",
                options=custom_options
            )
        
        assert result.text == "Test"
        
        # Verify custom options were used
        call_args = mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file.call_args
        assert call_args[0][0]["mimetype"] == "audio/mp3"
        assert call_args[0][1]["model"] == "nova-2-general"
        assert call_args[0][1]["language"] == "es-ES"
        assert call_args[0][1]["custom_param"] == "value"
    
    @pytest.mark.asyncio
    async def test_transcribe_batch_failure(self, mock_settings, mock_deepgram_client):
        """Test batch transcription failure."""
        mock_deepgram_client.listen.asyncrest.v.return_value.transcribe_file = AsyncMock(
            side_effect=Exception("Transcription failed")
        )
        
        client = DeepgramSTTClient()
        # Use larger audio data to pass validation
        audio_data = b"fake_audio_data" * 20  # Make it larger than 100 bytes
        
        # Mock the audio validation to always pass
        with patch('src.clients.deepgram_stt.validate_audio_data') as mock_validate:
            mock_validate.return_value = MagicMock(
                is_valid=True,
                detected_format="wav",
                duration_estimate=1.0,
                file_size=len(audio_data)
            )
            
            with pytest.raises(Exception, match="Transcription failed"):
                await client.transcribe_batch(audio_data)
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_basic(self, mock_settings, mock_deepgram_client):
        """Test basic streaming transcription."""
        # Mock live connection
        mock_live_connection = MagicMock()
        mock_live_connection.start = AsyncMock(return_value=True)
        mock_live_connection.send = AsyncMock()
        mock_live_connection.finish = AsyncMock()
        
        mock_deepgram_client.listen.asynclive.v.return_value = mock_live_connection
        
        client = DeepgramSTTClient()
        
        # Create mock audio stream
        async def mock_audio_stream():
            yield b"audio_chunk_1"
            yield b"audio_chunk_2"
            yield b"audio_chunk_3"
        
        # Mock the streaming connection to immediately finish
        async def mock_create_streaming_connection(audio_stream, connection_id):
            # Consume the audio stream
            async for chunk in audio_stream:
                pass
            # Yield a test result
            yield TranscriptionResult(
                text="Streaming test",
                confidence=0.9,
                language="en-US",
                duration=1.0
            )
        
        with patch.object(client, '_create_streaming_connection', mock_create_streaming_connection):
            results = []
            async for result in client.transcribe_stream(mock_audio_stream()):
                results.append(result)
        
        assert len(results) == 1
        assert results[0].text == "Streaming test"
        assert results[0].confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_with_reconnection(self, mock_settings, mock_deepgram_client):
        """Test streaming transcription with reconnection."""
        client = DeepgramSTTClient()
        
        # Create mock audio stream
        async def mock_audio_stream():
            yield b"audio_chunk_1"
            yield b"audio_chunk_2"
        
        # Mock connection that fails first time, succeeds second time
        call_count = 0
        
        async def mock_create_streaming_connection(audio_stream, connection_id):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call fails
                raise Exception("Connection failed")
            else:
                # Second call succeeds
                async for chunk in audio_stream:
                    pass
                yield TranscriptionResult(
                    text="Reconnection success",
                    confidence=0.95,
                    language="en-US",
                    duration=1.0
                )
        
        with patch.object(client, '_create_streaming_connection', mock_create_streaming_connection):
            with patch('asyncio.sleep', AsyncMock()):  # Speed up test
                results = []
                async for result in client.transcribe_stream(mock_audio_stream()):
                    results.append(result)
        
        assert len(results) == 1
        assert results[0].text == "Reconnection success"
        assert call_count == 2  # Should have been called twice
        assert client.deepgram_metrics.reconnection_count == 1
    
    @pytest.mark.asyncio
    async def test_transcribe_stream_max_reconnections_exceeded(self, mock_settings, mock_deepgram_client):
        """Test streaming transcription when max reconnections exceeded."""
        client = DeepgramSTTClient()
        
        async def mock_audio_stream():
            yield b"audio_chunk_1"
        
        # Mock connection that always fails
        async def mock_create_streaming_connection(audio_stream, connection_id):
            raise Exception("Connection always fails")
            yield  # This makes it an async generator (unreachable but needed for type)
        
        with patch.object(client, '_create_streaming_connection', mock_create_streaming_connection):
            with patch('asyncio.sleep', AsyncMock()):  # Speed up test
                with pytest.raises(Exception, match="Connection always fails"):
                    async for result in client.transcribe_stream(mock_audio_stream()):
                        pass
    
    @pytest.mark.asyncio
    async def test_close_connection(self, mock_settings, mock_deepgram_client):
        """Test closing a specific connection."""
        client = DeepgramSTTClient()
        
        # Add a mock connection
        mock_connection = MagicMock()
        mock_connection.finish = AsyncMock()
        
        connection_id = "test_connection"
        client._active_connections[connection_id] = mock_connection
        client.deepgram_metrics.active_streams = 1
        
        await client.close_connection(connection_id)
        
        assert connection_id not in client._active_connections
        assert client.deepgram_metrics.active_streams == 0
        mock_connection.finish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_connection_with_error(self, mock_settings, mock_deepgram_client):
        """Test closing connection handles errors gracefully."""
        client = DeepgramSTTClient()
        
        # Add a mock connection that raises error on finish
        mock_connection = MagicMock()
        mock_connection.finish = AsyncMock(side_effect=Exception("Close error"))
        
        connection_id = "test_connection"
        client._active_connections[connection_id] = mock_connection
        client.deepgram_metrics.active_streams = 1
        
        # Should not raise exception
        await client.close_connection(connection_id)
        
        assert connection_id not in client._active_connections
        assert client.deepgram_metrics.active_streams == 0
    
    @pytest.mark.asyncio
    async def test_close_all_connections(self, mock_settings, mock_deepgram_client):
        """Test closing all connections."""
        client = DeepgramSTTClient()
        
        # Add multiple mock connections
        mock_connections = {}
        for i in range(3):
            connection_id = f"connection_{i}"
            mock_connection = MagicMock()
            mock_connection.finish = AsyncMock()
            mock_connections[connection_id] = mock_connection
            client._active_connections[connection_id] = mock_connection
        
        client.deepgram_metrics.active_streams = 3
        
        await client.close_all_connections()
        
        assert len(client._active_connections) == 0
        assert client.deepgram_metrics.active_streams == 0
        
        # Verify all connections were closed
        for mock_connection in mock_connections.values():
            mock_connection.finish.assert_called_once()
    
    def test_get_deepgram_metrics(self, mock_settings, mock_deepgram_client):
        """Test getting Deepgram-specific metrics."""
        client = DeepgramSTTClient()
        
        # Update some metrics
        client.deepgram_metrics.streaming_connections = 5
        client.deepgram_metrics.active_streams = 2
        client.deepgram_metrics.total_audio_duration = 10.0
        client.deepgram_metrics.total_transcription_time = 8.0
        client.deepgram_metrics.average_confidence = 0.92
        client.deepgram_metrics.reconnection_count = 1
        
        metrics = client.get_deepgram_metrics()
        
        assert isinstance(metrics, DeepgramMetrics)
        assert metrics.streaming_connections == 5
        assert metrics.active_streams == 2
        assert metrics.total_audio_duration == 10.0
        assert metrics.total_transcription_time == 8.0
        assert metrics.average_confidence == 0.92
        assert metrics.reconnection_count == 1
        assert metrics.transcription_speed_ratio == 0.8
    
    def test_get_health_status(self, mock_settings, mock_deepgram_client):
        """Test getting extended health status."""
        client = DeepgramSTTClient()
        
        # Update some metrics
        client.deepgram_metrics.streaming_connections = 3
        client.deepgram_metrics.active_streams = 1
        client.deepgram_metrics.average_confidence = 0.88
        
        status = client.get_health_status()
        
        assert "service" in status
        assert "circuit_breaker_state" in status
        assert "metrics" in status
        assert "healthy" in status
        assert "deepgram_metrics" in status
        assert "streaming_config" in status
        
        deepgram_metrics = status["deepgram_metrics"]
        assert deepgram_metrics["streaming_connections"] == 3
        assert deepgram_metrics["active_streams"] == 1
        assert deepgram_metrics["average_confidence"] == 0.88
        
        streaming_config = status["streaming_config"]
        assert streaming_config["model"] == "nova-2"
        assert streaming_config["language"] == "en-US"
        assert streaming_config["sample_rate"] == 16000
        assert streaming_config["interim_results"] is True
    
    @pytest.mark.asyncio
    async def test_close_client(self, mock_settings, mock_deepgram_client):
        """Test closing the client."""
        client = DeepgramSTTClient()
        
        # Add a mock connection
        mock_connection = MagicMock()
        mock_connection.finish = AsyncMock()
        client._active_connections["test"] = mock_connection
        
        with patch.object(client, 'close_all_connections', AsyncMock()) as mock_close_all:
            with patch.object(client.http_client, 'aclose', AsyncMock()) as mock_http_close:
                await client.close()
        
        mock_close_all.assert_called_once()
        mock_http_close.assert_called_once()


@pytest.mark.asyncio
async def test_integration_batch_transcription():
    """Integration test for batch transcription (requires API key)."""
    # Skip if no API key available
    try:
        from src.config import get_settings
        settings = get_settings()
        if not settings.deepgram_api_key:
            pytest.skip("No Deepgram API key available")
    except Exception:
        pytest.skip("Settings not available")
    
    # This would be a real integration test
    # For now, we'll skip it in unit tests
    pytest.skip("Integration test - run separately with real API key")


@pytest.mark.asyncio
async def test_integration_streaming_transcription():
    """Integration test for streaming transcription (requires API key)."""
    # Skip if no API key available
    try:
        from src.config import get_settings
        settings = get_settings()
        if not settings.deepgram_api_key:
            pytest.skip("No Deepgram API key available")
    except Exception:
        pytest.skip("Settings not available")
    
    # This would be a real integration test
    # For now, we'll skip it in unit tests
    pytest.skip("Integration test - run separately with real API key")
"""Unit tests for Cartesia TTS client."""

import asyncio
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any

from src.clients.cartesia_tts import (
    CartesiaTTSClient,
    VoiceConfig,
    AudioConfig,
    AudioFormat,
    AudioEncoding,
    TTSResponse,
    TTSUsageStats
)
from src.clients.base import RetryConfig, CircuitBreakerConfig


@dataclass
class MockWebSocketResponse:
    """Mock WebSocket response for testing."""
    audio: str
    context_id: str = "test-context"


@dataclass
class MockBatchResponse:
    """Mock batch response for testing."""
    audio: str
    context_id: str = "test-context"


class MockCartesiaWebSocket:
    """Mock Cartesia WebSocket for testing."""
    
    def __init__(self, should_fail: bool = False, fail_after: int = 0):
        self.should_fail = should_fail
        self.fail_after = fail_after
        self.call_count = 0
        self.closed = False
    
    async def send(self, **kwargs) -> AsyncIterator[MockWebSocketResponse]:
        """Mock send method for streaming."""
        self.call_count += 1
        
        if self.should_fail and self.call_count > self.fail_after:
            raise Exception("Mock WebSocket error")
        
        if kwargs.get('stream', True):
            # Return async generator for streaming
            return self._stream_generator()
        else:
            # Return single response for batch with enough data for health check
            test_audio = base64.b64encode(b"mock audio data" * 100).decode()  # 1500 bytes
            return MockBatchResponse(audio=test_audio)
    
    async def _stream_generator(self):
        """Generate mock streaming responses."""
        for i in range(3):
            if self.should_fail and i >= self.fail_after:
                raise Exception("Mock streaming error")
            
            test_audio = base64.b64encode(f"chunk_{i}".encode()).decode()
            yield MockWebSocketResponse(audio=test_audio)
    
    async def close(self):
        """Mock close method."""
        self.closed = True


class MockCartesiaTTS:
    """Mock Cartesia TTS client."""
    
    def __init__(self, should_fail: bool = False, fail_after: int = 0):
        self.should_fail = should_fail
        self.fail_after = fail_after
    
    async def websocket(self):
        """Return mock websocket."""
        return MockCartesiaWebSocket(self.should_fail, self.fail_after)


class MockCartesiaClient:
    """Mock Cartesia client."""
    
    def __init__(self, should_fail: bool = False, fail_after: int = 0):
        self.tts = MockCartesiaTTS(should_fail, fail_after)
        self.voices = MockVoicesClient()
        self.closed = False
    
    async def close(self):
        """Mock close method."""
        self.closed = True


class MockVoicesClient:
    """Mock voices client."""
    
    async def list(self):
        """Return mock voice list."""
        # Create proper mock objects with attributes
        mock_voice1 = MagicMock()
        mock_voice1.id = "voice-1"
        mock_voice1.name = "Test Voice 1"
        mock_voice1.description = "A test voice"
        mock_voice1.language = "en"
        mock_voice1.gender = "female"
        
        mock_voice2 = MagicMock()
        mock_voice2.id = "voice-2"
        mock_voice2.name = "Test Voice 2"
        mock_voice2.description = "Another test voice"
        mock_voice2.language = "en"
        mock_voice2.gender = "male"
        
        return [mock_voice1, mock_voice2]


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('src.clients.cartesia_tts.get_settings') as mock:
        mock.return_value = MagicMock(
            cartesia_api_key="test-api-key",
            cartesia_voice_id="test-voice-id"
        )
        yield mock.return_value


@pytest.fixture
def tts_client(mock_settings):
    """Create TTS client for testing."""
    with patch('src.clients.cartesia_tts.AsyncCartesia') as mock_cartesia:
        mock_cartesia.return_value = MockCartesiaClient()
        
        client = CartesiaTTSClient(
            api_key="test-api-key",
            default_voice_id="test-voice-id"
        )
        yield client


@pytest.fixture
def failing_tts_client(mock_settings):
    """Create TTS client that fails for testing error scenarios."""
    with patch('src.clients.cartesia_tts.AsyncCartesia') as mock_cartesia:
        mock_cartesia.return_value = MockCartesiaClient(should_fail=True)
        
        # Create retry config with only 1 attempt to avoid multiple failed_requests
        from src.clients.base import RetryConfig
        retry_config = RetryConfig(max_attempts=1)
        
        client = CartesiaTTSClient(
            api_key="test-api-key",
            default_voice_id="test-voice-id",
            retry_config=retry_config
        )
        yield client


class TestCartesiaTTSClient:
    """Test cases for CartesiaTTSClient."""
    
    def test_initialization(self, mock_settings):
        """Test client initialization."""
        with patch('src.clients.cartesia_tts.AsyncCartesia') as mock_cartesia:
            mock_cartesia.return_value = MockCartesiaClient()
            
            client = CartesiaTTSClient(
                api_key="test-key",
                model_id="test-model",
                default_voice_id="test-voice"
            )
            
            assert client.api_key == "test-key"
            assert client.model_id == "test-model"
            assert client.default_voice_id == "test-voice"
            assert isinstance(client.usage_stats, TTSUsageStats)
    
    def test_initialization_without_api_key(self, mock_settings):
        """Test initialization fails without API key."""
        mock_settings.cartesia_api_key = None
        
        with pytest.raises(ValueError, match="Cartesia API key is required"):
            CartesiaTTSClient()
    
    def test_text_preprocessing(self, tts_client):
        """Test text preprocessing functionality."""
        # Test basic preprocessing
        result = tts_client.preprocess_text("  Hello   world  ")
        assert result == "Hello world."
        
        # Test abbreviation expansion
        result = tts_client.preprocess_text("Dr. Smith said hello")
        assert result == "Doctor Smith said hello."
        
        # Test currency handling
        result = tts_client.preprocess_text("It costs $50")
        assert result == "It costs 50 dollars."
        
        # Test percentage handling
        result = tts_client.preprocess_text("95% complete")
        assert result == "95 percent complete."
        
        # Test empty text
        result = tts_client.preprocess_text("")
        assert result == ""
        
        # Test whitespace only
        result = tts_client.preprocess_text("   ")
        assert result == ""
    
    def test_text_validation(self, tts_client):
        """Test text validation."""
        # Valid text
        assert tts_client.validate_text("Hello world") is True
        
        # Empty text
        assert tts_client.validate_text("") is False
        assert tts_client.validate_text("   ") is False
        
        # Too long text
        long_text = "a" * 1001
        assert tts_client.validate_text(long_text) is False
        
        # Text with problematic characters
        assert tts_client.validate_text("Hello <world>") is True  # Should warn but not fail
    
    @pytest.mark.asyncio
    async def test_synthesize_stream_success(self, tts_client):
        """Test successful streaming synthesis."""
        text = "Hello, this is a test."
        voice_config = VoiceConfig(voice_id="test-voice")
        audio_config = AudioConfig(format=AudioFormat.WAV)
        
        chunks = []
        async for chunk in tts_client.synthesize_stream(text, voice_config, audio_config):
            chunks.append(chunk)
        
        # Should receive 3 chunks from mock
        assert len(chunks) == 3
        assert all(isinstance(chunk, bytes) for chunk in chunks)
        
        # Check usage stats
        assert tts_client.usage_stats.total_requests == 1
        assert tts_client.usage_stats.streaming_requests == 1
        assert tts_client.usage_stats.total_characters > 0
    
    @pytest.mark.asyncio
    async def test_synthesize_stream_invalid_text(self, tts_client):
        """Test streaming synthesis with invalid text."""
        chunks = []
        async for chunk in tts_client.synthesize_stream(""):
            chunks.append(chunk)
        
        # Should not yield any chunks for invalid text
        assert len(chunks) == 0
        assert tts_client.usage_stats.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_synthesize_stream_error_fallback(self, failing_tts_client):
        """Test streaming synthesis error handling with fallback."""
        text = "Hello, this is a test."
        
        chunks = []
        async for chunk in failing_tts_client.synthesize_stream(text):
            chunks.append(chunk)
        
        # Should receive fallback silence
        assert len(chunks) == 1
        assert isinstance(chunks[0], bytes)
        assert len(chunks[0]) > 0  # Should have fallback audio
    
    @pytest.mark.asyncio
    async def test_synthesize_batch_success(self, tts_client):
        """Test successful batch synthesis."""
        text = "Hello, this is a test."
        voice_config = VoiceConfig(voice_id="test-voice")
        audio_config = AudioConfig(format=AudioFormat.WAV)
        
        response = await tts_client.synthesize_batch(text, voice_config, audio_config)
        
        assert isinstance(response, TTSResponse)
        assert len(response.audio_data) > 0
        assert response.format == AudioFormat.WAV
        assert response.characters_processed == len(tts_client.preprocess_text(text))
        assert response.synthesis_time > 0
        
        # Check usage stats
        assert tts_client.usage_stats.total_requests == 1
        assert tts_client.usage_stats.batch_requests == 1
    
    @pytest.mark.asyncio
    async def test_synthesize_batch_invalid_text(self, tts_client):
        """Test batch synthesis with invalid text."""
        with pytest.raises(ValueError, match="Invalid text for synthesis"):
            await tts_client.synthesize_batch("")
        
        assert tts_client.usage_stats.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_synthesize_batch_error(self, failing_tts_client):
        """Test batch synthesis error handling."""
        text = "Hello, this is a test."
        
        with pytest.raises(Exception):
            await failing_tts_client.synthesize_batch(text)
        
        assert failing_tts_client.usage_stats.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_get_available_voices(self, tts_client):
        """Test getting available voices."""
        voices = await tts_client.get_available_voices()
        
        assert len(voices) == 2
        assert voices[0]["id"] == "voice-1"
        assert voices[0]["name"] == "Test Voice 1"
        assert voices[1]["id"] == "voice-2"
        assert voices[1]["name"] == "Test Voice 2"
    
    @pytest.mark.asyncio
    async def test_get_available_voices_error(self, failing_tts_client):
        """Test getting available voices with error."""
        # Mock the voices client to fail
        failing_tts_client.client.voices.list = AsyncMock(side_effect=Exception("API error"))
        
        voices = await failing_tts_client.get_available_voices()
        assert voices == []
    
    def test_get_usage_statistics(self, tts_client):
        """Test getting usage statistics."""
        # Add some mock usage
        tts_client.usage_stats.add_request(
            characters=100,
            duration=5.0,
            latency=1.0,
            is_streaming=True
        )
        tts_client.usage_stats.add_failed_request()
        
        stats = tts_client.get_usage_statistics()
        
        assert stats["total_requests"] == 1
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["total_characters"] == 100
        assert stats["streaming_requests"] == 1
        assert stats["batch_requests"] == 0
    
    def test_create_voice_config(self, tts_client):
        """Test creating voice configuration."""
        # Test with defaults
        config = tts_client.create_voice_config()
        assert config.voice_id == "test-voice-id"
        assert config.speed == 1.0
        assert config.language == "en"
        
        # Test with custom values
        config = tts_client.create_voice_config(
            voice_id="custom-voice",
            speed=1.5,
            emotion="happy",
            language="es"
        )
        assert config.voice_id == "custom-voice"
        assert config.speed == 1.5
        assert config.emotion == "happy"
        assert config.language == "es"
        
        # Test speed clamping
        config = tts_client.create_voice_config(speed=3.0)
        assert config.speed == 2.0  # Should be clamped
        
        config = tts_client.create_voice_config(speed=0.1)
        assert config.speed == 0.5  # Should be clamped
    
    def test_create_telephony_audio_config(self, tts_client):
        """Test creating telephony-optimized audio configuration."""
        # Test WAV format
        config = tts_client.create_telephony_audio_config(AudioFormat.WAV)
        assert config.format == AudioFormat.WAV
        assert config.sample_rate == 8000
        
        # Test MP3 format
        config = tts_client.create_telephony_audio_config(AudioFormat.MP3)
        assert config.format == AudioFormat.MP3
        assert config.sample_rate == 8000
        assert config.bit_rate == 64
        
        # Test RAW format
        config = tts_client.create_telephony_audio_config(AudioFormat.RAW)
        assert config.format == AudioFormat.RAW
        assert config.sample_rate == 8000
        assert config.encoding == AudioEncoding.PCM_MULAW
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, tts_client):
        """Test successful health check."""
        result = await tts_client.health_check()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, failing_tts_client):
        """Test health check failure."""
        result = await failing_tts_client.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_close(self, tts_client):
        """Test client cleanup."""
        await tts_client.close()
        assert tts_client.client.closed is True


class TestVoiceConfig:
    """Test cases for VoiceConfig."""
    
    def test_to_cartesia_format(self):
        """Test conversion to Cartesia format."""
        config = VoiceConfig(voice_id="test-voice", speed=1.5, emotion="happy")
        cartesia_format = config.to_cartesia_format()
        
        assert cartesia_format == {
            "mode": "id",
            "id": "test-voice"
        }


class TestAudioConfig:
    """Test cases for AudioConfig."""
    
    def test_to_cartesia_format_wav(self):
        """Test WAV format conversion."""
        config = AudioConfig(format=AudioFormat.WAV, sample_rate=16000)
        cartesia_format = config.to_cartesia_format()
        
        assert cartesia_format == {
            "container": "wav",
            "sample_rate": 16000
        }
    
    def test_to_cartesia_format_mp3(self):
        """Test MP3 format conversion."""
        config = AudioConfig(
            format=AudioFormat.MP3,
            sample_rate=22050,
            bit_rate=128
        )
        cartesia_format = config.to_cartesia_format()
        
        assert cartesia_format == {
            "container": "mp3",
            "sample_rate": 22050,
            "bit_rate": 128
        }
    
    def test_to_cartesia_format_raw(self):
        """Test RAW format conversion."""
        config = AudioConfig(
            format=AudioFormat.RAW,
            sample_rate=8000,
            encoding=AudioEncoding.PCM_S16LE
        )
        cartesia_format = config.to_cartesia_format()
        
        assert cartesia_format == {
            "container": "raw",
            "sample_rate": 8000,
            "encoding": "pcm_s16le"
        }


class TestTTSUsageStats:
    """Test cases for TTSUsageStats."""
    
    def test_add_request(self):
        """Test adding request statistics."""
        stats = TTSUsageStats()
        
        stats.add_request(characters=100, duration=5.0, latency=1.0, is_streaming=True)
        
        assert stats.total_requests == 1
        assert stats.total_characters == 100
        assert stats.total_audio_duration == 5.0
        assert stats.streaming_requests == 1
        assert stats.batch_requests == 0
        assert stats.average_latency == 1.0
    
    def test_add_failed_request(self):
        """Test adding failed request statistics."""
        stats = TTSUsageStats()
        
        stats.add_failed_request()
        
        assert stats.failed_requests == 1
        assert stats.success_rate == 0.0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = TTSUsageStats()
        
        # No requests
        assert stats.success_rate == 0.0
        
        # Some successful requests
        stats.add_request(100, 5.0, 1.0)
        stats.add_request(100, 5.0, 1.0)
        assert stats.success_rate == 1.0
        
        # Some failed requests
        stats.add_failed_request()
        assert stats.success_rate == 2/3  # 2 successful out of 3 total
    
    def test_average_latency_calculation(self):
        """Test average latency calculation."""
        stats = TTSUsageStats()
        
        stats.add_request(100, 5.0, 1.0)
        stats.add_request(100, 5.0, 2.0)
        stats.add_request(100, 5.0, 3.0)
        
        assert stats.average_latency == 2.0  # (1.0 + 2.0 + 3.0) / 3


class TestResiliencePatterns:
    """Test resilience patterns in TTS client."""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_settings):
        """Test retry logic on failures."""
        with patch('src.clients.cartesia_tts.AsyncCartesia') as mock_cartesia:
            # Create client that fails first 2 attempts, then succeeds
            mock_cartesia.return_value = MockCartesiaClient(should_fail=True, fail_after=2)
            
            client = CartesiaTTSClient(
                api_key="test-key",
                retry_config=RetryConfig(max_attempts=3, base_delay=0.1)
            )
            
            # Should eventually succeed after retries
            response = await client.synthesize_batch("Hello world")
            assert isinstance(response, TTSResponse)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, mock_settings):
        """Test circuit breaker opens after failures."""
        with patch('src.clients.cartesia_tts.AsyncCartesia') as mock_cartesia:
            mock_cartesia.return_value = MockCartesiaClient(should_fail=True)
            
            client = CartesiaTTSClient(
                api_key="test-key",
                circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2),
                retry_config=RetryConfig(max_attempts=1)  # Fail fast
            )
            
            # First few requests should fail and open circuit breaker
            for _ in range(3):
                try:
                    await client.synthesize_batch("Hello world")
                except Exception:
                    pass
            
            # Circuit breaker should now be open
            health_status = client.get_health_status()
            assert health_status["circuit_breaker_state"] == "open"
    
    def test_get_health_status(self, tts_client):
        """Test health status reporting."""
        health_status = tts_client.get_health_status()
        
        assert "service" in health_status
        assert "circuit_breaker_state" in health_status
        assert "metrics" in health_status
        assert "healthy" in health_status
        assert health_status["service"] == "cartesia_tts"
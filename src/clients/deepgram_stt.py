"""Deepgram Speech-to-Text client with streaming support."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from uuid import uuid4

import websockets
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents
from deepgram.clients.live.v1 import LiveOptions

from src.clients.base import BaseResilientClient, ClientMetrics
from src.config import get_settings
from src.security import validate_audio_data


class TranscriptionMode(Enum):
    """Transcription modes."""
    STREAMING = "streaming"
    BATCH = "batch"


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    confidence: float
    language: str
    duration: float
    alternatives: List[str] = field(default_factory=list)
    is_final: bool = True
    channel: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription."""
    model: str = "nova-2"
    language: str = "en-US"
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "linear16"
    interim_results: bool = True
    punctuate: bool = True
    smart_format: bool = True
    profanity_filter: bool = False
    redact: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    utterance_end_ms: int = 1000
    vad_events: bool = True
    endpointing: int = 300


@dataclass
class DeepgramMetrics(ClientMetrics):
    """Extended metrics for Deepgram client."""
    streaming_connections: int = 0
    active_streams: int = 0
    total_audio_duration: float = 0.0
    total_transcription_time: float = 0.0
    average_confidence: float = 0.0
    reconnection_count: int = 0
    
    @property
    def transcription_speed_ratio(self) -> float:
        """Calculate transcription speed ratio (real-time factor)."""
        if self.total_audio_duration == 0:
            return 0.0
        return self.total_transcription_time / self.total_audio_duration


class DeepgramSTTClient(BaseResilientClient[TranscriptionResult]):
    """
    Deepgram Speech-to-Text client with streaming and batch support.
    
    Features:
    - Real-time streaming transcription with low latency
    - Batch transcription for pre-recorded audio
    - Automatic reconnection for streaming connections
    - Confidence scoring and quality metrics
    - Comprehensive error handling and fallbacks
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        streaming_config: Optional[StreamingConfig] = None
    ):
        """
        Initialize Deepgram STT client.
        
        Args:
            api_key: Deepgram API key (uses config if not provided)
            timeout: Request timeout in seconds
            streaming_config: Configuration for streaming transcription
        """
        super().__init__(
            service_name="deepgram_stt",
            timeout=timeout
        )
        
        # Get settings
        settings = get_settings()
        self.api_key = api_key or settings.deepgram_api_key
        
        if not self.api_key:
            raise ValueError("Deepgram API key is required")
        
        # Initialize Deepgram client
        config = DeepgramClientOptions(
            api_key=self.api_key,
            options={"keepalive": "true"}
        )
        self.deepgram_client = DeepgramClient(api_key=self.api_key, config=config)
        
        # Streaming configuration
        self.streaming_config = streaming_config or StreamingConfig(
            model=settings.deepgram_model,
            language=settings.deepgram_language,
            sample_rate=settings.audio_sample_rate,
            channels=settings.audio_channels
        )
        
        # Extended metrics
        self.deepgram_metrics = DeepgramMetrics()
        
        # Active streaming connections
        self._active_connections: Dict[str, Any] = {}
        self._connection_lock = asyncio.Lock()
        
        self.logger.info(
            "Deepgram STT client initialized",
            extra={
                "model": self.streaming_config.model,
                "language": self.streaming_config.language,
                "sample_rate": self.streaming_config.sample_rate
            }
        )
    
    async def health_check(self) -> bool:
        """
        Perform health check by testing API connectivity.
        
        Returns:
            bool: True if service is healthy
        """
        try:
            # Test with a small audio sample
            test_audio = b'\x00' * 1600  # 100ms of silence at 16kHz
            
            async def _health_check():
                response = await self.deepgram_client.listen.asyncrest.v("1").transcribe_file(
                    {"buffer": test_audio, "mimetype": "audio/wav"},
                    {"model": "nova-2", "language": "en-US"}
                )
                return response.results.channels[0].alternatives[0].transcript is not None
            
            result = await self.execute_with_resilience(_health_check)
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    async def transcribe_batch(
        self,
        audio_data: bytes,
        mimetype: str = "audio/wav",
        options: Optional[Dict[str, Any]] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio data in batch mode.
        
        Args:
            audio_data: Audio data bytes
            mimetype: MIME type of audio data
            options: Additional transcription options
            
        Returns:
            TranscriptionResult: Transcription result
            
        Raises:
            ValueError: If audio data is invalid or unsafe
        """
        correlation_id = self._generate_correlation_id()
        start_time = time.time()
        
        # Validate audio data for security
        validation_result = validate_audio_data(audio_data)
        if not validation_result.is_valid:
            self.logger.error(
                f"Audio validation failed: {validation_result.error_message}",
                extra={
                    "correlation_id": correlation_id,
                    "file_size": validation_result.file_size
                }
            )
            raise ValueError(f"Invalid audio data: {validation_result.error_message}")
        
        self.logger.debug(
            "Starting batch transcription",
            extra={
                "correlation_id": correlation_id,
                "audio_size": len(audio_data),
                "mimetype": mimetype,
                "detected_format": validation_result.detected_format,
                "duration_estimate": validation_result.duration_estimate
            }
        )
        
        # Prepare options
        transcription_options = {
            "model": self.streaming_config.model,
            "language": self.streaming_config.language,
            "punctuate": self.streaming_config.punctuate,
            "smart_format": self.streaming_config.smart_format,
            "profanity_filter": self.streaming_config.profanity_filter,
        }
        
        if options:
            transcription_options.update(options)
        
        async def _transcribe():
            response = await self.deepgram_client.listen.asyncrest.v("1").transcribe_file(
                {"buffer": audio_data, "mimetype": mimetype},
                transcription_options
            )
            return response
        
        try:
            response = await self.execute_with_resilience(_transcribe, correlation_id)
            
            # Extract transcription result
            channel = response.results.channels[0]
            alternative = channel.alternatives[0]
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Update metrics
            self.deepgram_metrics.total_transcription_time += duration
            if hasattr(response.results, 'metadata') and response.results.metadata:
                audio_duration = response.results.metadata.duration or 0
                self.deepgram_metrics.total_audio_duration += audio_duration
            
            result = TranscriptionResult(
                text=alternative.transcript,
                confidence=alternative.confidence,
                language=self.streaming_config.language,
                duration=duration,
                alternatives=[alt.transcript for alt in channel.alternatives[1:5]],
                is_final=True,
                words=[
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence
                    }
                    for word in alternative.words
                ] if hasattr(alternative, 'words') and alternative.words else [],
                metadata={
                    "model": response.results.metadata.model_info.name if response.results.metadata else None,
                    "model_version": response.results.metadata.model_info.version if response.results.metadata else None,
                    "request_id": response.results.metadata.request_id if response.results.metadata else None
                }
            )
            
            self.logger.info(
                "Batch transcription completed",
                extra={
                    "correlation_id": correlation_id,
                    "text_length": len(result.text),
                    "confidence": result.confidence,
                    "duration": duration
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Batch transcription failed: {str(e)}",
                extra={"correlation_id": correlation_id}
            )
            raise
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        connection_id: Optional[str] = None
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe audio stream in real-time.
        
        Args:
            audio_stream: Async iterator of audio data chunks
            connection_id: Optional connection identifier
            
        Yields:
            TranscriptionResult: Streaming transcription results
        """
        if connection_id is None:
            connection_id = self._generate_correlation_id()
        
        self.logger.info(
            "Starting streaming transcription",
            extra={"connection_id": connection_id}
        )
        
        async with self._connection_lock:
            self.deepgram_metrics.streaming_connections += 1
            self.deepgram_metrics.active_streams += 1
        
        try:
            async for result in self._stream_with_reconnection(audio_stream, connection_id):
                yield result
                
        finally:
            async with self._connection_lock:
                self.deepgram_metrics.active_streams -= 1
                if connection_id in self._active_connections:
                    del self._active_connections[connection_id]
    
    async def _stream_with_reconnection(
        self,
        audio_stream: AsyncIterator[bytes],
        connection_id: str,
        max_reconnections: int = 3
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Handle streaming with automatic reconnection.
        
        Args:
            audio_stream: Audio data stream
            connection_id: Connection identifier
            max_reconnections: Maximum reconnection attempts
            
        Yields:
            TranscriptionResult: Transcription results
        """
        reconnection_count = 0
        
        while reconnection_count <= max_reconnections:
            try:
                async for result in self._create_streaming_connection(audio_stream, connection_id):
                    yield result
                break  # Successful completion
                
            except Exception as e:
                reconnection_count += 1
                self.deepgram_metrics.reconnection_count += 1
                
                if reconnection_count > max_reconnections:
                    self.logger.error(
                        f"Max reconnections exceeded for streaming connection",
                        extra={
                            "connection_id": connection_id,
                            "attempts": reconnection_count,
                            "error": str(e)
                        }
                    )
                    raise
                
                self.logger.warning(
                    f"Streaming connection failed, attempting reconnection {reconnection_count}/{max_reconnections}",
                    extra={
                        "connection_id": connection_id,
                        "error": str(e)
                    }
                )
                
                # Exponential backoff
                await asyncio.sleep(min(2 ** reconnection_count, 10))
    
    async def _create_streaming_connection(
        self,
        audio_stream: AsyncIterator[bytes],
        connection_id: str
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Create a streaming connection to Deepgram.
        
        Args:
            audio_stream: Audio data stream
            connection_id: Connection identifier
            
        Yields:
            TranscriptionResult: Transcription results
        """
        # Configure live transcription options
        options = LiveOptions(
            model=self.streaming_config.model,
            language=self.streaming_config.language,
            sample_rate=self.streaming_config.sample_rate,
            channels=self.streaming_config.channels,
            encoding=self.streaming_config.encoding,
            interim_results=self.streaming_config.interim_results,
            punctuate=self.streaming_config.punctuate,
            smart_format=self.streaming_config.smart_format,
            profanity_filter=self.streaming_config.profanity_filter,
            redact=self.streaming_config.redact,
            keywords=self.streaming_config.keywords,
            utterance_end_ms=self.streaming_config.utterance_end_ms,
            vad_events=self.streaming_config.vad_events,
            endpointing=self.streaming_config.endpointing
        )
        
        # Create live transcription connection
        dg_connection = self.deepgram_client.listen.asynclive.v("1")
        
        # Result queue for handling async events
        result_queue: asyncio.Queue[TranscriptionResult] = asyncio.Queue()
        connection_active = True
        
        def on_message(self, result, **kwargs):
            """Handle transcription messages."""
            try:
                if result.channel and result.channel.alternatives:
                    alternative = result.channel.alternatives[0]
                    
                    transcription_result = TranscriptionResult(
                        text=alternative.transcript,
                        confidence=alternative.confidence,
                        language=self.streaming_config.language,
                        duration=result.duration if hasattr(result, 'duration') else 0.0,
                        is_final=result.is_final,
                        channel=result.channel_index[0] if result.channel_index else 0,
                        start_time=result.start if hasattr(result, 'start') else 0.0,
                        end_time=result.end if hasattr(result, 'end') else 0.0,
                        words=[
                            {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "confidence": word.confidence
                            }
                            for word in alternative.words
                        ] if hasattr(alternative, 'words') and alternative.words else [],
                        metadata={
                            "model_uuid": result.metadata.model_uuid if result.metadata else None,
                            "request_id": result.metadata.request_id if result.metadata else None
                        }
                    )
                    
                    # Update confidence metrics
                    if alternative.confidence > 0:
                        current_avg = self.deepgram_metrics.average_confidence
                        current_count = self.deepgram_metrics.success_count
                        self.deepgram_metrics.average_confidence = (
                            (current_avg * current_count + alternative.confidence) / (current_count + 1)
                        )
                    
                    asyncio.create_task(result_queue.put(transcription_result))
                    
            except Exception as e:
                self.logger.error(
                    f"Error processing transcription message: {str(e)}",
                    extra={"connection_id": connection_id}
                )
        
        def on_error(self, error, **kwargs):
            """Handle connection errors."""
            self.logger.error(
                f"Streaming transcription error: {str(error)}",
                extra={"connection_id": connection_id}
            )
            nonlocal connection_active
            connection_active = False
            asyncio.create_task(result_queue.put(None))  # Signal end
        
        def on_close(self, close, **kwargs):
            """Handle connection close."""
            self.logger.info(
                "Streaming transcription connection closed",
                extra={"connection_id": connection_id}
            )
            nonlocal connection_active
            connection_active = False
            asyncio.create_task(result_queue.put(None))  # Signal end
        
        # Register event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        
        try:
            # Start the connection
            if not await dg_connection.start(options):
                raise Exception("Failed to start Deepgram live transcription")
            
            # Store active connection
            async with self._connection_lock:
                self._active_connections[connection_id] = dg_connection
            
            # Start audio streaming task
            async def stream_audio():
                try:
                    async for audio_chunk in audio_stream:
                        if not connection_active:
                            break
                        await dg_connection.send(audio_chunk)
                except Exception as e:
                    self.logger.error(
                        f"Error streaming audio: {str(e)}",
                        extra={"connection_id": connection_id}
                    )
                finally:
                    if connection_active:
                        await dg_connection.finish()
            
            # Start audio streaming
            audio_task = asyncio.create_task(stream_audio())
            
            try:
                # Yield results as they come
                while connection_active:
                    try:
                        result = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                        if result is None:  # End signal
                            break
                        yield result
                    except asyncio.TimeoutError:
                        continue
                        
            finally:
                # Clean up
                audio_task.cancel()
                try:
                    await audio_task
                except asyncio.CancelledError:
                    pass
                
        finally:
            # Ensure connection is closed
            try:
                await dg_connection.finish()
            except Exception:
                pass
            
            async with self._connection_lock:
                if connection_id in self._active_connections:
                    del self._active_connections[connection_id]
    
    async def close_connection(self, connection_id: str) -> None:
        """
        Close a specific streaming connection.
        
        Args:
            connection_id: Connection identifier to close
        """
        async with self._connection_lock:
            if connection_id in self._active_connections:
                connection = self._active_connections[connection_id]
                try:
                    await connection.finish()
                except Exception as e:
                    self.logger.warning(
                        f"Error closing connection {connection_id}: {str(e)}"
                    )
                del self._active_connections[connection_id]
                self.deepgram_metrics.active_streams -= 1
    
    async def close_all_connections(self) -> None:
        """Close all active streaming connections."""
        async with self._connection_lock:
            connection_ids = list(self._active_connections.keys())
            
        for connection_id in connection_ids:
            await self.close_connection(connection_id)
    
    def get_deepgram_metrics(self) -> DeepgramMetrics:
        """
        Get Deepgram-specific metrics.
        
        Returns:
            DeepgramMetrics: Extended metrics
        """
        return self.deepgram_metrics
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get extended health status including Deepgram-specific metrics."""
        base_status = super().get_health_status()
        
        base_status.update({
            "deepgram_metrics": {
                "streaming_connections": self.deepgram_metrics.streaming_connections,
                "active_streams": self.deepgram_metrics.active_streams,
                "total_audio_duration": self.deepgram_metrics.total_audio_duration,
                "transcription_speed_ratio": self.deepgram_metrics.transcription_speed_ratio,
                "average_confidence": self.deepgram_metrics.average_confidence,
                "reconnection_count": self.deepgram_metrics.reconnection_count
            },
            "streaming_config": {
                "model": self.streaming_config.model,
                "language": self.streaming_config.language,
                "sample_rate": self.streaming_config.sample_rate,
                "interim_results": self.streaming_config.interim_results
            }
        })
        
        return base_status
    
    async def close(self) -> None:
        """Close the client and all connections."""
        await self.close_all_connections()
        await super().close()
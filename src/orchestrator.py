"""
Call Orchestrator for managing voice AI agent call lifecycle.

This module implements the CallOrchestrator class that serves as the central
coordinator for managing the entire call lifecycle and component interactions.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncIterator, Callable
from uuid import uuid4

from src.clients.deepgram_stt import DeepgramSTTClient, TranscriptionResult
from src.clients.openai_llm import OpenAILLMClient, ConversationContext
from src.clients.cartesia_tts import CartesiaTTSClient, VoiceConfig, AudioConfig
from src.conversation.state_machine import ConversationStateMachine, ConversationState
from src.conversation.dialogue_manager import DialogueManager
from src.config import get_settings
from src.metrics import get_metrics_collector, timer
from src.health import check_health


logger = logging.getLogger(__name__)


class CallStatus(str, Enum):
    """Call status enumeration."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PROCESSING = "processing"
    ENDING = "ending"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioStreamState(str, Enum):
    """Audio stream state enumeration."""
    IDLE = "idle"
    RECEIVING = "receiving"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"


@dataclass
class CallContext:
    """Context information for a call."""
    call_id: str
    caller_number: str
    start_time: datetime
    livekit_room: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "call_id": self.call_id,
            "caller_number": self.caller_number,
            "start_time": self.start_time.isoformat(),
            "livekit_room": self.livekit_room,
            "metadata": self.metadata
        }


@dataclass
class CallMetrics:
    """Metrics for call performance monitoring."""
    call_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0
    audio_processing_time: float = 0.0
    stt_latency: float = 0.0
    llm_latency: float = 0.0
    tts_latency: float = 0.0
    total_turns: int = 0
    successful_turns: int = 0
    failed_turns: int = 0
    interruptions: int = 0
    reconnections: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate turn success rate."""
        if self.total_turns == 0:
            return 0.0
        return self.successful_turns / self.total_turns
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        return self.stt_latency + self.llm_latency + self.tts_latency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "call_id": self.call_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "audio_processing_time": self.audio_processing_time,
            "stt_latency": self.stt_latency,
            "llm_latency": self.llm_latency,
            "tts_latency": self.tts_latency,
            "total_turns": self.total_turns,
            "successful_turns": self.successful_turns,
            "failed_turns": self.failed_turns,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "interruptions": self.interruptions,
            "reconnections": self.reconnections,
            "bytes_received": self.bytes_received,
            "bytes_sent": self.bytes_sent
        }


@dataclass
class HealthStatus:
    """Health status for the orchestrator."""
    is_healthy: bool
    status: str
    components: Dict[str, bool]
    last_check: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_healthy": self.is_healthy,
            "status": self.status,
            "components": self.components,
            "last_check": self.last_check.isoformat(),
            "details": self.details
        }


class CallOrchestrator:
    """
    Central coordinator for managing call lifecycle and component interactions.
    
    The CallOrchestrator manages:
    - LiveKit event handling and audio stream management
    - State machine coordination and transition management
    - Dialogue history maintenance and context management
    - Error handling and fallback response coordination
    - Metrics collection and performance monitoring
    """
    
    def __init__(
        self,
        stt_client: DeepgramSTTClient,
        llm_client: OpenAILLMClient,
        tts_client: CartesiaTTSClient,
        max_concurrent_calls: int = 10,
        audio_buffer_size: int = 1024,
        response_timeout: float = 30.0
    ):
        """
        Initialize the CallOrchestrator.
        
        Args:
            stt_client: Speech-to-text client
            llm_client: Language model client
            tts_client: Text-to-speech client
            max_concurrent_calls: Maximum concurrent calls to handle
            audio_buffer_size: Audio buffer size in bytes
            response_timeout: Response timeout in seconds
        """
        self.stt_client = stt_client
        self.llm_client = llm_client
        self.tts_client = tts_client
        self.max_concurrent_calls = max_concurrent_calls
        self.audio_buffer_size = audio_buffer_size
        self.response_timeout = response_timeout
        
        # Load settings
        self.settings = get_settings()
        
        # Active calls management
        self.active_calls: Dict[str, CallContext] = {}
        self.call_metrics: Dict[str, CallMetrics] = {}
        self.call_state_machines: Dict[str, ConversationStateMachine] = {}
        self.dialogue_managers: Dict[str, DialogueManager] = {}
        
        # Audio stream management
        self.audio_streams: Dict[str, AsyncIterator[bytes]] = {}
        self.audio_stream_states: Dict[str, AudioStreamState] = {}
        self.audio_buffers: Dict[str, List[bytes]] = {}
        
        # Metrics and monitoring
        self.metrics_collector = get_metrics_collector()
        self.total_calls_handled = 0
        self.successful_calls = 0
        self.failed_calls = 0
        
        # Event handlers
        self.call_start_handlers: List[Callable] = []
        self.call_end_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []
        
        # Concurrency control
        self.call_semaphore = asyncio.Semaphore(max_concurrent_calls)
        self.processing_locks: Dict[str, asyncio.Lock] = {}
        
        logger.info(
            "CallOrchestrator initialized",
            extra={
                "max_concurrent_calls": max_concurrent_calls,
                "audio_buffer_size": audio_buffer_size,
                "response_timeout": response_timeout
            }
        )
    
    async def handle_call_start(self, call_context: CallContext) -> None:
        """
        Handle incoming call start event.
        
        Args:
            call_context: Context information for the call
        """
        call_id = call_context.call_id
        
        # Check concurrent call limit
        if len(self.active_calls) >= self.max_concurrent_calls:
            logger.warning(
                f"Maximum concurrent calls reached, rejecting call {call_id}",
                extra={"call_id": call_id, "active_calls": len(self.active_calls)}
            )
            await self._handle_call_rejection(call_context, "max_concurrent_calls_reached")
            return
        
        async with self.call_semaphore:
            try:
                logger.info(
                    f"Starting call {call_id}",
                    extra={
                        "call_id": call_id,
                        "caller_number": call_context.caller_number,
                        "livekit_room": call_context.livekit_room
                    }
                )
                
                # Initialize call tracking
                self.active_calls[call_id] = call_context
                self.call_metrics[call_id] = CallMetrics(
                    call_id=call_id,
                    start_time=call_context.start_time
                )
                self.processing_locks[call_id] = asyncio.Lock()
                
                # Initialize conversation components
                state_machine = ConversationStateMachine(ConversationState.LISTENING)
                self.call_state_machines[call_id] = state_machine
                
                dialogue_manager = DialogueManager(
                    conversation_id=call_id,
                    llm_client=self.llm_client,
                    state_machine=state_machine,
                    max_context_turns=self.settings.context_window_size // 100,  # Rough estimate
                    max_context_tokens=self.settings.context_window_size
                )
                self.dialogue_managers[call_id] = dialogue_manager
                
                # Initialize audio stream management
                self.audio_stream_states[call_id] = AudioStreamState.IDLE
                self.audio_buffers[call_id] = []
                
                # Update metrics
                self.total_calls_handled += 1
                self.metrics_collector.increment_counter(
                    "calls_started_total",
                    labels={"caller_number": call_context.caller_number}
                )
                self.metrics_collector.set_gauge(
                    "active_calls_current",
                    len(self.active_calls)
                )
                
                # Execute call start handlers
                await self._execute_call_start_handlers(call_context)
                
                logger.info(
                    f"Call {call_id} started successfully",
                    extra={"call_id": call_id}
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to start call {call_id}: {e}",
                    extra={"call_id": call_id, "error": str(e)}
                )
                await self._handle_call_error(call_context, e)
    
    async def handle_audio_received(self, call_id: str, audio_data: bytes) -> None:
        """
        Handle incoming audio data from LiveKit.
        
        Args:
            call_id: Call identifier
            audio_data: Raw audio data bytes
        """
        if call_id not in self.active_calls:
            logger.warning(f"Received audio for unknown call {call_id}")
            return
        
        try:
            # Update metrics
            self.call_metrics[call_id].bytes_received += len(audio_data)
            self.metrics_collector.record_histogram(
                "audio_chunk_size_bytes",
                len(audio_data),
                labels={"call_id": call_id}
            )
            
            # Buffer audio data
            self.audio_buffers[call_id].append(audio_data)
            
            # Update audio stream state
            self.audio_stream_states[call_id] = AudioStreamState.RECEIVING
            
            # Process audio if we have enough buffered data or timeout
            if (len(self.audio_buffers[call_id]) >= 10 or  # Buffer threshold
                self.audio_stream_states[call_id] == AudioStreamState.RECEIVING):
                await self._process_audio_buffer(call_id)
                
        except Exception as e:
            logger.error(
                f"Error handling audio for call {call_id}: {e}",
                extra={"call_id": call_id, "error": str(e)}
            )
            await self._handle_audio_error(call_id, e)
    
    async def handle_call_end(self, call_context: CallContext) -> None:
        """
        Handle call end event.
        
        Args:
            call_context: Context information for the call
        """
        call_id = call_context.call_id
        
        try:
            logger.info(
                f"Ending call {call_id}",
                extra={"call_id": call_id}
            )
            
            # Update call metrics
            if call_id in self.call_metrics:
                metrics = self.call_metrics[call_id]
                metrics.end_time = datetime.now(UTC)
                metrics.total_duration = (metrics.end_time - metrics.start_time).total_seconds()
                
                # Record final metrics
                self.metrics_collector.record_timer(
                    "call_duration_seconds",
                    metrics.total_duration,
                    labels={"call_id": call_id}
                )
                self.metrics_collector.record_histogram(
                    "call_turns_total",
                    metrics.total_turns,
                    labels={"call_id": call_id}
                )
                self.metrics_collector.record_histogram(
                    "call_success_rate",
                    metrics.success_rate,
                    labels={"call_id": call_id}
                )
            
            # End conversation
            if call_id in self.dialogue_managers:
                dialogue_manager = self.dialogue_managers[call_id]
                conversation_summary = dialogue_manager.end_conversation()
                
                logger.info(
                    f"Call {call_id} conversation summary",
                    extra={
                        "call_id": call_id,
                        "turns": conversation_summary.total_turns,
                        "duration": conversation_summary.total_duration
                    }
                )
            
            # Clean up resources
            await self._cleanup_call_resources(call_id)
            
            # Update global metrics
            self.successful_calls += 1
            self.metrics_collector.increment_counter("calls_completed_total")
            self.metrics_collector.set_gauge(
                "active_calls_current",
                len(self.active_calls)
            )
            
            # Execute call end handlers
            await self._execute_call_end_handlers(call_context)
            
            logger.info(
                f"Call {call_id} ended successfully",
                extra={"call_id": call_id}
            )
            
        except Exception as e:
            logger.error(
                f"Error ending call {call_id}: {e}",
                extra={"call_id": call_id, "error": str(e)}
            )
            self.failed_calls += 1
            self.metrics_collector.increment_counter("calls_failed_total")
    
    async def _process_audio_buffer(self, call_id: str) -> None:
        """
        Process buffered audio data for a call.
        
        Args:
            call_id: Call identifier
        """
        if call_id not in self.active_calls:
            return
        
        async with self.processing_locks[call_id]:
            try:
                # Update state
                self.audio_stream_states[call_id] = AudioStreamState.PROCESSING
                state_machine = self.call_state_machines[call_id]
                dialogue_manager = self.dialogue_managers[call_id]
                
                # Transition to processing state
                await state_machine.transition_to(
                    ConversationState.PROCESSING,
                    trigger="audio_received"
                )
                
                # Combine buffered audio
                audio_buffer = self.audio_buffers[call_id]
                if not audio_buffer:
                    return
                
                combined_audio = b''.join(audio_buffer)
                self.audio_buffers[call_id] = []  # Clear buffer
                
                # Process audio through STT
                with timer("stt_processing_duration", {"call_id": call_id}):
                    stt_start = time.time()
                    transcription_result = await self.stt_client.transcribe_batch(
                        combined_audio,
                        mimetype="audio/wav"
                    )
                    stt_latency = time.time() - stt_start
                
                # Update metrics
                self.call_metrics[call_id].stt_latency = stt_latency
                dialogue_manager.update_service_latency('stt', stt_latency)
                
                # Skip processing if transcription is empty or low confidence
                if not transcription_result.text.strip() or transcription_result.confidence < 0.5:
                    logger.debug(
                        f"Skipping low-quality transcription for call {call_id}",
                        extra={
                            "call_id": call_id,
                            "confidence": transcription_result.confidence,
                            "text": transcription_result.text[:50]
                        }
                    )
                    await state_machine.transition_to(
                        ConversationState.LISTENING,
                        trigger="low_quality_transcription"
                    )
                    return
                
                logger.info(
                    f"Transcribed audio for call {call_id}",
                    extra={
                        "call_id": call_id,
                        "text": transcription_result.text[:100],
                        "confidence": transcription_result.confidence,
                        "stt_latency": stt_latency
                    }
                )
                
                # Process through dialogue manager
                with timer("dialogue_processing_duration", {"call_id": call_id}):
                    response_text, conversation_turn = await dialogue_manager.process_user_input(
                        transcription_result.text,
                        metadata={
                            "transcription_confidence": transcription_result.confidence,
                            "stt_latency": stt_latency
                        }
                    )
                
                # Update turn metrics
                self.call_metrics[call_id].total_turns += 1
                self.call_metrics[call_id].successful_turns += 1
                self.call_metrics[call_id].llm_latency = dialogue_manager.metrics.llm_latency
                
                # Transition to speaking state
                await state_machine.transition_to(
                    ConversationState.SPEAKING,
                    trigger="response_generated"
                )
                
                # Generate audio response
                await self._generate_audio_response(call_id, response_text)
                
                # Transition back to listening
                await state_machine.transition_to(
                    ConversationState.LISTENING,
                    trigger="response_completed"
                )
                
                self.audio_stream_states[call_id] = AudioStreamState.IDLE
                
            except Exception as e:
                logger.error(
                    f"Error processing audio buffer for call {call_id}: {e}",
                    extra={"call_id": call_id, "error": str(e)}
                )
                
                # Update error metrics
                self.call_metrics[call_id].failed_turns += 1
                self.metrics_collector.increment_counter(
                    "audio_processing_errors_total",
                    labels={"call_id": call_id}
                )
                
                # Force transition back to listening state
                await state_machine.force_transition(
                    ConversationState.LISTENING,
                    trigger="error_recovery"
                )
                
                self.audio_stream_states[call_id] = AudioStreamState.ERROR
    
    async def _generate_audio_response(self, call_id: str, response_text: str) -> None:
        """
        Generate and send audio response.
        
        Args:
            call_id: Call identifier
            response_text: Text to convert to speech
        """
        try:
            # Create voice and audio configurations
            voice_config = VoiceConfig(
                voice_id=self.settings.cartesia_voice_id,
                speed=1.0,
                language="en"
            )
            
            audio_config = AudioConfig(
                format=self.tts_client.AudioFormat.WAV,
                sample_rate=self.settings.audio_sample_rate
            )
            
            # Generate TTS audio
            with timer("tts_processing_duration", {"call_id": call_id}):
                tts_start = time.time()
                tts_response = await self.tts_client.synthesize_batch(
                    response_text,
                    voice_config=voice_config,
                    audio_config=audio_config
                )
                tts_latency = time.time() - tts_start
            
            # Update metrics
            self.call_metrics[call_id].tts_latency = tts_latency
            self.call_metrics[call_id].bytes_sent += len(tts_response.audio_data)
            
            dialogue_manager = self.dialogue_managers[call_id]
            dialogue_manager.update_service_latency('tts', tts_latency)
            
            logger.info(
                f"Generated TTS response for call {call_id}",
                extra={
                    "call_id": call_id,
                    "text_length": len(response_text),
                    "audio_size": len(tts_response.audio_data),
                    "tts_latency": tts_latency
                }
            )
            
            # TODO: Send audio to LiveKit (will be implemented in future tasks)
            # For now, we just log that we would send the audio
            logger.debug(
                f"Would send {len(tts_response.audio_data)} bytes of audio to LiveKit for call {call_id}"
            )
            
        except Exception as e:
            logger.error(
                f"Error generating audio response for call {call_id}: {e}",
                extra={"call_id": call_id, "error": str(e)}
            )
            raise
    
    async def _cleanup_call_resources(self, call_id: str) -> None:
        """
        Clean up resources for a completed call.
        
        Args:
            call_id: Call identifier
        """
        try:
            # Remove from active calls
            self.active_calls.pop(call_id, None)
            
            # Clean up state machine
            self.call_state_machines.pop(call_id, None)
            
            # Clean up dialogue manager
            self.dialogue_managers.pop(call_id, None)
            
            # Clean up audio resources
            self.audio_streams.pop(call_id, None)
            self.audio_stream_states.pop(call_id, None)
            self.audio_buffers.pop(call_id, None)
            
            # Clean up processing locks
            self.processing_locks.pop(call_id, None)
            
            logger.debug(f"Cleaned up resources for call {call_id}")
            
        except Exception as e:
            logger.error(
                f"Error cleaning up resources for call {call_id}: {e}",
                extra={"call_id": call_id, "error": str(e)}
            )
    
    async def _handle_call_rejection(self, call_context: CallContext, reason: str) -> None:
        """
        Handle call rejection.
        
        Args:
            call_context: Call context
            reason: Rejection reason
        """
        logger.warning(
            f"Rejecting call {call_context.call_id}: {reason}",
            extra={"call_id": call_context.call_id, "reason": reason}
        )
        
        self.metrics_collector.increment_counter(
            "calls_rejected_total",
            labels={"reason": reason}
        )
        
        # TODO: Send rejection response to LiveKit
    
    async def _handle_call_error(self, call_context: CallContext, error: Exception) -> None:
        """
        Handle call error.
        
        Args:
            call_context: Call context
            error: Error that occurred
        """
        call_id = call_context.call_id
        
        logger.error(
            f"Call error for {call_id}: {error}",
            extra={"call_id": call_id, "error": str(error)}
        )
        
        self.failed_calls += 1
        self.metrics_collector.increment_counter(
            "call_errors_total",
            labels={"error_type": type(error).__name__}
        )
        
        # Execute error handlers
        await self._execute_error_handlers(call_context, error)
        
        # Clean up resources
        await self._cleanup_call_resources(call_id)
    
    async def _handle_audio_error(self, call_id: str, error: Exception) -> None:
        """
        Handle audio processing error.
        
        Args:
            call_id: Call identifier
            error: Error that occurred
        """
        logger.error(
            f"Audio error for call {call_id}: {error}",
            extra={"call_id": call_id, "error": str(error)}
        )
        
        self.audio_stream_states[call_id] = AudioStreamState.ERROR
        self.metrics_collector.increment_counter(
            "audio_errors_total",
            labels={"call_id": call_id, "error_type": type(error).__name__}
        )
    
    async def _execute_call_start_handlers(self, call_context: CallContext) -> None:
        """Execute registered call start handlers."""
        for handler in self.call_start_handlers:
            try:
                await handler(call_context)
            except Exception as e:
                logger.error(f"Error in call start handler: {e}")
    
    async def _execute_call_end_handlers(self, call_context: CallContext) -> None:
        """Execute registered call end handlers."""
        for handler in self.call_end_handlers:
            try:
                await handler(call_context)
            except Exception as e:
                logger.error(f"Error in call end handler: {e}")
    
    async def _execute_error_handlers(self, call_context: CallContext, error: Exception) -> None:
        """Execute registered error handlers."""
        for handler in self.error_handlers:
            try:
                await handler(call_context, error)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")
    
    def add_call_start_handler(self, handler: Callable) -> None:
        """Add call start event handler."""
        self.call_start_handlers.append(handler)
    
    def add_call_end_handler(self, handler: Callable) -> None:
        """Add call end event handler."""
        self.call_end_handlers.append(handler)
    
    def add_error_handler(self, handler: Callable) -> None:
        """Add error event handler."""
        self.error_handlers.append(handler)
    
    async def get_health_status(self) -> HealthStatus:
        """
        Get comprehensive health status.
        
        Returns:
            HealthStatus with component health information
        """
        try:
            # Check component health
            components = {
                "stt_client": await self.stt_client.health_check(),
                "llm_client": await self.llm_client.health_check(),
                "tts_client": await self.tts_client.health_check(),
                "system": check_health()["status"] == "healthy"
            }
            
            # Overall health
            is_healthy = all(components.values())
            status = "healthy" if is_healthy else "unhealthy"
            
            # Additional details
            details = {
                "active_calls": len(self.active_calls),
                "total_calls_handled": self.total_calls_handled,
                "successful_calls": self.successful_calls,
                "failed_calls": self.failed_calls,
                "success_rate": (
                    self.successful_calls / max(1, self.total_calls_handled)
                ),
                "max_concurrent_calls": self.max_concurrent_calls,
                "audio_buffer_size": self.audio_buffer_size
            }
            
            return HealthStatus(
                is_healthy=is_healthy,
                status=status,
                components=components,
                last_check=datetime.now(UTC),
                details=details
            )
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return HealthStatus(
                is_healthy=False,
                status="error",
                components={},
                last_check=datetime.now(UTC),
                details={"error": str(e)}
            )
    
    def get_call_metrics(self, call_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get call metrics.
        
        Args:
            call_id: Specific call ID, or None for all calls
            
        Returns:
            Dictionary containing call metrics
        """
        if call_id:
            if call_id in self.call_metrics:
                return self.call_metrics[call_id].to_dict()
            else:
                return {}
        
        # Return all call metrics
        return {
            "total_calls": self.total_calls_handled,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "active_calls": len(self.active_calls),
            "success_rate": (
                self.successful_calls / max(1, self.total_calls_handled)
            ),
            "individual_calls": {
                call_id: metrics.to_dict()
                for call_id, metrics in self.call_metrics.items()
            }
        }
    
    def get_active_calls(self) -> List[Dict[str, Any]]:
        """
        Get information about active calls.
        
        Returns:
            List of active call information
        """
        return [
            {
                **call_context.to_dict(),
                "state": self.call_state_machines[call_id].current_state.value,
                "audio_state": self.audio_stream_states[call_id].value,
                "metrics": self.call_metrics[call_id].to_dict()
            }
            for call_id, call_context in self.active_calls.items()
        ]
    
    async def close(self) -> None:
        """Close the orchestrator and clean up resources."""
        try:
            logger.info("Closing CallOrchestrator")
            
            # End all active calls
            active_call_ids = list(self.active_calls.keys())
            for call_id in active_call_ids:
                call_context = self.active_calls[call_id]
                await self.handle_call_end(call_context)
            
            # Close client connections
            await self.stt_client.close()
            await self.llm_client.close()
            await self.tts_client.close()
            
            logger.info("CallOrchestrator closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing CallOrchestrator: {e}")
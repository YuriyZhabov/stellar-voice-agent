"""
Dialogue Manager for conversation context and AI service coordination.

This module implements the DialogueManager class that maintains conversation
history, manages context preservation, and coordinates between STT, LLM, and TTS services.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, AsyncIterator
from uuid import uuid4

from src.clients.base import BaseResilientClient
from src.clients.groq_llm import GroqLLMClient, ConversationContext, MessageRole, LLMResponse
from src.conversation.state_machine import ConversationStateMachine, ConversationState
from src.config import get_settings


logger = logging.getLogger(__name__)


class ConversationPhase(str, Enum):
    """Phases of conversation processing."""
    INITIALIZATION = "initialization"
    LISTENING = "listening"
    TRANSCRIPTION = "transcription"
    UNDERSTANDING = "understanding"
    GENERATION = "generation"
    SYNTHESIS = "synthesis"
    RESPONSE = "response"
    COMPLETION = "completion"


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""
    turn_id: str
    user_input: str
    assistant_response: str
    timestamp: datetime
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "turn_id": self.turn_id,
            "user_input": self.user_input,
            "assistant_response": self.assistant_response,
            "timestamp": self.timestamp.isoformat(),
            "processing_time": self.processing_time,
            "metadata": self.metadata
        }


@dataclass
class ConversationSummary:
    """Summary of conversation for analytics and context management."""
    conversation_id: str
    total_turns: int
    total_duration: float
    start_time: datetime
    end_time: Optional[datetime]
    participant_count: int
    topics_discussed: List[str]
    sentiment_analysis: Optional[Dict[str, Any]]
    quality_metrics: Dict[str, float]
    token_usage: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "conversation_id": self.conversation_id,
            "total_turns": self.total_turns,
            "total_duration": self.total_duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "participant_count": self.participant_count,
            "topics_discussed": self.topics_discussed,
            "sentiment_analysis": self.sentiment_analysis,
            "quality_metrics": self.quality_metrics,
            "token_usage": self.token_usage
        }


@dataclass
class ConversationMetrics:
    """Metrics for conversation quality and performance."""
    total_turns: int = 0
    average_response_time: float = 0.0
    total_processing_time: float = 0.0
    stt_latency: float = 0.0
    llm_latency: float = 0.0
    tts_latency: float = 0.0
    error_count: int = 0
    interruption_count: int = 0
    context_truncations: int = 0
    fallback_responses: int = 0
    
    def update_response_time(self, response_time: float) -> None:
        """Update average response time with new measurement."""
        if self.total_turns == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                (self.average_response_time * self.total_turns + response_time) / 
                (self.total_turns + 1)
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "total_turns": self.total_turns,
            "average_response_time": self.average_response_time,
            "total_processing_time": self.total_processing_time,
            "stt_latency": self.stt_latency,
            "llm_latency": self.llm_latency,
            "tts_latency": self.tts_latency,
            "error_count": self.error_count,
            "interruption_count": self.interruption_count,
            "context_truncations": self.context_truncations,
            "fallback_responses": self.fallback_responses
        }


class DialogueManager:
    """
    Manages conversation context and coordinates AI service interactions.
    
    The DialogueManager is responsible for:
    - Maintaining conversation history and context
    - Multi-turn dialogue context preservation with memory management
    - Conversation summarization for long conversations
    - Response generation coordination between STT, LLM, and TTS services
    - Conversation analytics and quality metrics collection
    """
    
    def __init__(
        self,
        conversation_id: str,
        llm_client: GroqLLMClient,
        state_machine: ConversationStateMachine,
        max_context_turns: int = 20,
        max_context_tokens: int = 4000,
        summarization_threshold: int = 15,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize the DialogueManager.
        
        Args:
            conversation_id: Unique identifier for the conversation
            llm_client: Groq LLM client for response generation
            state_machine: Conversation state machine
            max_context_turns: Maximum number of turns to keep in context
            max_context_tokens: Maximum tokens for context window
            summarization_threshold: Number of turns before summarization
            system_prompt: Custom system prompt for the conversation
        """
        self.conversation_id = conversation_id
        self.llm_client = llm_client
        self.state_machine = state_machine
        self.max_context_turns = max_context_turns
        self.max_context_tokens = max_context_tokens
        self.summarization_threshold = summarization_threshold
        
        # Load settings (with fallback for testing)
        try:
            settings = get_settings()
            default_system_prompt = settings.system_prompt
        except Exception:
            # Fallback for testing environment
            default_system_prompt = "You are a helpful AI assistant speaking over the phone. Keep responses concise and natural for voice conversation."
        
        self.system_prompt = system_prompt or default_system_prompt
        
        # Initialize conversation state
        self.start_time = datetime.now(UTC)
        self.end_time: Optional[datetime] = None
        self.current_phase = ConversationPhase.INITIALIZATION
        
        # Conversation history and context
        self.conversation_turns: List[ConversationTurn] = []
        self.conversation_context: Optional[ConversationContext] = None
        self.conversation_summary: Optional[str] = None
        
        # Metrics and analytics
        self.metrics = ConversationMetrics()
        self.quality_scores: Dict[str, float] = {}
        
        # Service coordination
        self.current_correlation_id: Optional[str] = None
        self.processing_lock = asyncio.Lock()
        
        # Initialize LLM conversation context
        self._initialize_conversation_context()
        
        logger.info(
            f"DialogueManager initialized for conversation {conversation_id}",
            extra={"conversation_id": conversation_id}
        )
    
    def _initialize_conversation_context(self) -> None:
        """Initialize the LLM conversation context."""
        self.conversation_context = self.llm_client.create_conversation_context(
            conversation_id=self.conversation_id,
            system_prompt=self.system_prompt,
            max_tokens=self.max_context_tokens
        )
    
    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for request tracking."""
        return f"{self.conversation_id}_{str(uuid4())[:8]}"
    
    async def process_user_input(
        self,
        user_input: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, ConversationTurn]:
        """
        Process user input and generate assistant response.
        
        Args:
            user_input: The user's input text
            metadata: Additional metadata for the turn
            
        Returns:
            Tuple of (assistant_response, conversation_turn)
        """
        async with self.processing_lock:
            start_time = time.time()
            turn_id = str(uuid4())
            self.current_correlation_id = self._generate_correlation_id()
            
            logger.info(
                f"Processing user input: {user_input[:100]}...",
                extra={
                    "conversation_id": self.conversation_id,
                    "turn_id": turn_id,
                    "correlation_id": self.current_correlation_id
                }
            )
            
            try:
                # Update conversation phase
                self.current_phase = ConversationPhase.UNDERSTANDING
                
                # Add user message to context
                if self.conversation_context:
                    self.conversation_context.add_message(
                        MessageRole.USER,
                        user_input,
                        metadata={"turn_id": turn_id, "timestamp": time.time()}
                    )
                
                # Check if context needs summarization
                await self._manage_context_size()
                
                # Generate response using LLM
                self.current_phase = ConversationPhase.GENERATION
                llm_start_time = time.time()
                
                llm_response = await self.llm_client.generate_response(
                    self.conversation_context,
                    correlation_id=self.current_correlation_id
                )
                
                llm_latency = time.time() - llm_start_time
                self.metrics.llm_latency = llm_latency
                
                # Add assistant response to context
                if self.conversation_context:
                    self.conversation_context.add_message(
                        MessageRole.ASSISTANT,
                        llm_response.content,
                        metadata={"turn_id": turn_id, "timestamp": time.time()}
                    )
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Create conversation turn
                conversation_turn = ConversationTurn(
                    turn_id=turn_id,
                    user_input=user_input,
                    assistant_response=llm_response.content,
                    timestamp=datetime.now(UTC),
                    processing_time=processing_time,
                    metadata={
                        **(metadata or {}),
                        "llm_latency": llm_latency,
                        "token_usage": llm_response.token_usage.__dict__,
                        "model": llm_response.model,
                        "finish_reason": llm_response.finish_reason,
                        "correlation_id": self.current_correlation_id
                    }
                )
                
                # Add to conversation history
                self.conversation_turns.append(conversation_turn)
                
                # Update metrics
                self.metrics.total_turns += 1
                self.metrics.update_response_time(processing_time)
                self.metrics.total_processing_time += processing_time
                
                # Update conversation phase
                self.current_phase = ConversationPhase.RESPONSE
                
                logger.info(
                    f"Generated response in {processing_time:.2f}s: {llm_response.content[:100]}...",
                    extra={
                        "conversation_id": self.conversation_id,
                        "turn_id": turn_id,
                        "processing_time": processing_time,
                        "correlation_id": self.current_correlation_id
                    }
                )
                
                return llm_response.content, conversation_turn
                
            except Exception as e:
                self.metrics.error_count += 1
                logger.error(
                    f"Error processing user input: {e}",
                    extra={
                        "conversation_id": self.conversation_id,
                        "turn_id": turn_id,
                        "error": str(e),
                        "correlation_id": self.current_correlation_id
                    }
                )
                
                # Generate fallback response
                fallback_response = self.llm_client.generate_fallback_response("general")
                self.metrics.fallback_responses += 1
                
                # Create error turn
                error_turn = ConversationTurn(
                    turn_id=turn_id,
                    user_input=user_input,
                    assistant_response=fallback_response.content,
                    timestamp=datetime.now(UTC),
                    processing_time=time.time() - start_time,
                    metadata={
                        **(metadata or {}),
                        "error": str(e),
                        "fallback": True,
                        "correlation_id": self.current_correlation_id
                    }
                )
                
                self.conversation_turns.append(error_turn)
                return fallback_response.content, error_turn
    
    async def _manage_context_size(self) -> None:
        """Manage conversation context size and perform summarization if needed."""
        if not self.conversation_context:
            return
        
        # Check if we need to summarize based on turn count
        if len(self.conversation_turns) >= self.summarization_threshold:
            await self._summarize_conversation()
        
        # Check if we need to optimize based on token count
        messages = self.conversation_context.get_messages_for_api()
        total_tokens = self.llm_client.calculate_context_tokens(messages)
        
        if total_tokens > self.max_context_tokens * 0.8:  # 80% threshold
            logger.info(
                f"Context approaching limit ({total_tokens} tokens), optimizing",
                extra={"conversation_id": self.conversation_id}
            )
            
            self.llm_client.optimize_conversation_history(self.conversation_context)
            self.metrics.context_truncations += 1
    
    async def _summarize_conversation(self) -> None:
        """Generate a summary of the conversation for context management."""
        if len(self.conversation_turns) < 3:  # Need minimum turns for meaningful summary
            return
        
        try:
            # Create summarization context
            summary_context = self.llm_client.create_conversation_context(
                conversation_id=f"{self.conversation_id}_summary",
                system_prompt="You are a helpful assistant that creates concise summaries of conversations. Summarize the key points, topics discussed, and important context from the conversation below."
            )
            
            # Add conversation history for summarization
            conversation_text = "\n".join([
                f"User: {turn.user_input}\nAssistant: {turn.assistant_response}"
                for turn in self.conversation_turns[-10:]  # Last 10 turns
            ])
            
            summary_context.add_message(
                MessageRole.USER,
                f"Please summarize this conversation:\n\n{conversation_text}"
            )
            
            # Generate summary
            summary_response = await self.llm_client.generate_response(summary_context)
            self.conversation_summary = summary_response.content
            
            # Update conversation context with summary
            if self.conversation_context:
                # Clear old messages and add summary
                self.conversation_context.messages = []
                self.conversation_context.add_message(
                    MessageRole.SYSTEM,
                    f"Previous conversation summary: {self.conversation_summary}"
                )
            
            logger.info(
                f"Generated conversation summary: {self.conversation_summary[:100]}...",
                extra={"conversation_id": self.conversation_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to generate conversation summary: {e}",
                extra={"conversation_id": self.conversation_id}
            )
    
    async def add_to_history(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to conversation history.
        
        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Additional metadata for the message
        """
        if not self.conversation_context:
            return
        
        try:
            message_role = MessageRole.USER if role.lower() == 'user' else MessageRole.ASSISTANT
            self.conversation_context.add_message(
                message_role,
                content,
                metadata=metadata
            )
            
            logger.debug(
                f"Added {role} message to history: {content[:50]}...",
                extra={"conversation_id": self.conversation_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to add message to history: {e}",
                extra={"conversation_id": self.conversation_id}
            )
    
    def get_conversation_summary(self) -> ConversationSummary:
        """
        Get comprehensive conversation summary with analytics.
        
        Returns:
            ConversationSummary with metrics and analysis
        """
        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics()
        
        # Extract topics (simplified - could use NLP for better topic extraction)
        topics = self._extract_topics()
        
        # Get token usage from LLM client
        token_usage = self.llm_client.get_token_usage_summary()["total_usage"]
        
        return ConversationSummary(
            conversation_id=self.conversation_id,
            total_turns=len(self.conversation_turns),
            total_duration=(datetime.now(UTC) - self.start_time).total_seconds(),
            start_time=self.start_time,
            end_time=self.end_time,
            participant_count=2,  # User and assistant
            topics_discussed=topics,
            sentiment_analysis=None,  # Could be implemented with sentiment analysis
            quality_metrics=quality_metrics,
            token_usage=token_usage
        )
    
    def _calculate_quality_metrics(self) -> Dict[str, float]:
        """Calculate conversation quality metrics."""
        if not self.conversation_turns:
            return {
                "response_time_score": 0.0,
                "error_score": 0.0,
                "context_efficiency": 0.0,
                "fallback_score": 0.0,
                "overall_score": 0.0
            }
        
        # Response time quality (lower is better, normalized to 0-1)
        avg_response_time = self.metrics.average_response_time
        response_time_score = max(0, 1 - (avg_response_time / 3.0))  # 3s as max acceptable
        
        # Error rate (lower is better)
        error_rate = self.metrics.error_count / max(1, self.metrics.total_turns)
        error_score = max(0, 1 - error_rate)
        
        # Context management efficiency
        context_efficiency = max(0, 1 - (self.metrics.context_truncations / max(1, self.metrics.total_turns)))
        
        # Fallback usage (lower is better)
        fallback_rate = self.metrics.fallback_responses / max(1, self.metrics.total_turns)
        fallback_score = max(0, 1 - fallback_rate)
        
        return {
            "response_time_score": response_time_score,
            "error_score": error_score,
            "context_efficiency": context_efficiency,
            "fallback_score": fallback_score,
            "overall_score": (response_time_score + error_score + context_efficiency + fallback_score) / 4
        }
    
    def _extract_topics(self) -> List[str]:
        """Extract topics from conversation (simplified implementation)."""
        # This is a simplified topic extraction - could be enhanced with NLP
        topics = set()
        
        for turn in self.conversation_turns:
            # Simple keyword extraction
            words = turn.user_input.lower().split()
            # Add words longer than 4 characters as potential topics
            topics.update([word for word in words if len(word) > 4 and word.isalpha()])
        
        return list(topics)[:10]  # Return top 10 topics
    
    def get_conversation_metrics(self) -> ConversationMetrics:
        """Get current conversation metrics."""
        return self.metrics
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """
        Get conversation history.
        
        Args:
            limit: Maximum number of turns to return
            
        Returns:
            List of conversation turns
        """
        if limit is None:
            return self.conversation_turns.copy()
        return self.conversation_turns[-limit:]
    
    def update_service_latency(
        self,
        service: str,
        latency: float
    ) -> None:
        """
        Update latency metrics for specific services.
        
        Args:
            service: Service name ('stt', 'llm', 'tts')
            latency: Latency in seconds
        """
        if service == 'stt':
            self.metrics.stt_latency = latency
        elif service == 'llm':
            self.metrics.llm_latency = latency
        elif service == 'tts':
            self.metrics.tts_latency = latency
        
        logger.debug(
            f"Updated {service} latency: {latency:.3f}s",
            extra={"conversation_id": self.conversation_id}
        )
    
    def record_interruption(self) -> None:
        """Record user interruption event."""
        self.metrics.interruption_count += 1
        logger.info(
            "User interruption recorded",
            extra={"conversation_id": self.conversation_id}
        )
    
    def end_conversation(self) -> ConversationSummary:
        """
        End the conversation and return final summary.
        
        Returns:
            Final conversation summary
        """
        self.end_time = datetime.now(UTC)
        self.current_phase = ConversationPhase.COMPLETION
        
        summary = self.get_conversation_summary()
        
        logger.info(
            f"Conversation ended. Duration: {summary.total_duration:.1f}s, Turns: {summary.total_turns}",
            extra={
                "conversation_id": self.conversation_id,
                "duration": summary.total_duration,
                "turns": summary.total_turns
            }
        )
        
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        """Get current dialogue manager status."""
        return {
            "conversation_id": self.conversation_id,
            "current_phase": self.current_phase.value,
            "total_turns": len(self.conversation_turns),
            "start_time": self.start_time.isoformat(),
            "duration": (datetime.now(UTC) - self.start_time).total_seconds(),
            "metrics": self.metrics.to_dict(),
            "context_size": len(self.conversation_context.messages) if self.conversation_context else 0,
            "has_summary": bool(self.conversation_summary)
        }
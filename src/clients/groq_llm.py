"""Groq LLM client with context management and intelligent truncation."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from openai import AsyncOpenAI  # Groq uses OpenAI-compatible API

from src.clients.base import BaseResilientClient, RetryConfig, CircuitBreakerConfig
from src.config import get_settings


class MessageRole(str, Enum):
    """Message roles for conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Conversation message."""
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_groq_format(self) -> Dict[str, str]:
        """Convert to Groq API format (OpenAI-compatible)."""
        return {
            "role": self.role.value,
            "content": self.content
        }


@dataclass
class TokenUsage:
    """Token usage tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost_estimate(self) -> float:
        """Estimate cost based on Groq pricing (approximate)."""
        # Groq pricing is typically much lower than OpenAI
        # Using approximate rates: $0.0001/1K prompt tokens, $0.0002/1K completion tokens
        prompt_cost = (self.prompt_tokens / 1000) * 0.0001
        completion_cost = (self.completion_tokens / 1000) * 0.0002
        return prompt_cost + completion_cost


@dataclass
class ConversationContext:
    """Context for conversation management."""
    conversation_id: str
    messages: List[Message] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add message to conversation."""
        message = Message(role=role, content=content, metadata=metadata)
        self.messages.append(message)
    
    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """Get messages formatted for Groq API."""
        api_messages = []
        
        # Add system prompt if provided
        if self.system_prompt:
            api_messages.append({
                "role": "system",
                "content": self.system_prompt
            })
        
        # Add conversation messages
        for message in self.messages:
            api_messages.append(message.to_groq_format())
        
        return api_messages


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    token_usage: TokenUsage
    model: str
    finish_reason: str
    response_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class GroqLLMClient(BaseResilientClient[LLMResponse]):
    """
    Groq LLM client with context management and intelligent truncation.
    
    Features:
    - Context window management with intelligent truncation
    - Token usage monitoring and cost calculation
    - Response streaming for reduced latency
    - Fallback response generation for API failures
    - Conversation history optimization
    - Fast inference with Groq's optimized infrastructure
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "moonshotai/kimi-k2-instruct",
        max_context_tokens: int = 4000,
        max_response_tokens: int = 150,
        temperature: float = 0.7,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        timeout: float = 30.0
    ):
        super().__init__(
            service_name="groq_llm",
            retry_config=retry_config,
            circuit_breaker_config=circuit_breaker_config,
            timeout=timeout
        )
        
        # Load settings
        settings = get_settings()
        
        # Initialize Groq client configuration
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.max_context_tokens = max_context_tokens or settings.context_window_size
        self.max_response_tokens = max_response_tokens or settings.max_response_tokens
        self.temperature = temperature or settings.ai_temperature
        
        if not self.api_key:
            raise ValueError("Groq API key is required")
        
        # Initialize async OpenAI client with Groq endpoint
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=timeout
        )
        
        # Fallback responses for different scenarios
        self.fallback_responses = {
            "api_error": "I'm experiencing some technical difficulties right now. Could you please repeat your question?",
            "rate_limit": "I'm processing a lot of requests right now. Please give me a moment and try again.",
            "timeout": "I'm taking longer than usual to respond. Could you please rephrase your question?",
            "context_overflow": "We've been talking for a while. Let me summarize what we've discussed so far.",
            "general": "I apologize, but I'm having trouble processing your request right now. How can I help you?"
        }
        
        # Token usage tracking
        self.total_token_usage = TokenUsage()
        self.conversation_contexts: Dict[str, ConversationContext] = {}
    
    async def close(self) -> None:
        """Close the Groq client."""
        await super().close()
        await self.client.close()
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        This is a rough approximation: ~4 characters per token for English.
        For production, consider using tiktoken library for accurate counting.
        """
        return len(text) // 4
    
    def calculate_context_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Calculate total tokens for message context."""
        total_tokens = 0
        for message in messages:
            # Add tokens for role and content
            total_tokens += self.estimate_tokens(message["role"])
            total_tokens += self.estimate_tokens(message["content"])
            # Add overhead for message formatting
            total_tokens += 4
        return total_tokens
    
    def truncate_context(self, messages: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
        """
        Intelligently truncate context to fit within token limits.
        
        Strategy:
        1. Always keep system message (if present)
        2. Keep most recent messages
        3. Summarize older messages if needed
        """
        if not messages:
            return messages
        
        # Separate system messages from conversation
        system_messages = [msg for msg in messages if msg["role"] == "system"]
        conversation_messages = [msg for msg in messages if msg["role"] != "system"]
        
        # Calculate tokens for system messages
        system_tokens = sum(self.estimate_tokens(msg["content"]) for msg in system_messages)
        available_tokens = max_tokens - system_tokens - self.max_response_tokens
        
        if available_tokens <= 0:
            self.logger.warning("System messages exceed token limit")
            return system_messages
        
        # Keep recent messages that fit within available tokens
        truncated_conversation = []
        current_tokens = 0
        
        # Process messages in reverse order (most recent first)
        for message in reversed(conversation_messages):
            message_tokens = self.estimate_tokens(message["content"]) + 4  # overhead
            
            if current_tokens + message_tokens <= available_tokens:
                truncated_conversation.insert(0, message)
                current_tokens += message_tokens
            else:
                # If we have space and this is important context, try to summarize
                if len(truncated_conversation) > 0 and current_tokens < available_tokens * 0.8:
                    # Add a summary message for truncated context
                    summary_msg = {
                        "role": "system",
                        "content": f"[Previous conversation context has been summarized due to length. {len(conversation_messages) - len(truncated_conversation)} earlier messages were condensed.]"
                    }
                    if self.estimate_tokens(summary_msg["content"]) + current_tokens <= available_tokens:
                        truncated_conversation.insert(0, summary_msg)
                break
        
        return system_messages + truncated_conversation
    
    async def generate_response(
        self,
        context: ConversationContext,
        correlation_id: Optional[str] = None
    ) -> LLMResponse:
        """Generate response using Groq API."""
        if correlation_id is None:
            correlation_id = self._generate_correlation_id()
        
        # Prepare messages for API
        messages = context.get_messages_for_api()
        
        # Calculate and manage context size
        context_tokens = self.calculate_context_tokens(messages)
        if context_tokens > self.max_context_tokens:
            self.logger.info(
                f"Context exceeds limit ({context_tokens} > {self.max_context_tokens}), truncating",
                extra={"correlation_id": correlation_id}
            )
            messages = self.truncate_context(messages, self.max_context_tokens)
        
        async def _make_request() -> LLMResponse:
            start_time = time.time()
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_response_tokens,
                    temperature=context.temperature,
                    stream=False
                )
                
                response_time = time.time() - start_time
                
                # Extract response data
                choice = response.choices[0]
                content = choice.message.content or ""
                finish_reason = choice.finish_reason or "unknown"
                
                # Track token usage
                usage = response.usage
                token_usage = TokenUsage(
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0
                )
                
                # Update total usage
                self.total_token_usage.prompt_tokens += token_usage.prompt_tokens
                self.total_token_usage.completion_tokens += token_usage.completion_tokens
                self.total_token_usage.total_tokens += token_usage.total_tokens
                
                return LLMResponse(
                    content=content,
                    token_usage=token_usage,
                    model=self.model,
                    finish_reason=finish_reason,
                    response_time=response_time,
                    metadata={
                        "correlation_id": correlation_id,
                        "context_tokens": context_tokens,
                        "truncated": context_tokens > self.max_context_tokens
                    }
                )
                
            except Exception as e:
                self.logger.error(f"Groq API error: {e}", extra={"correlation_id": correlation_id})
                raise
        
        return await self.execute_with_resilience(_make_request, correlation_id)
    
    async def stream_response(
        self,
        context: ConversationContext,
        correlation_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream response from Groq API for reduced latency."""
        if correlation_id is None:
            correlation_id = self._generate_correlation_id()
        
        # Prepare messages for API
        messages = context.get_messages_for_api()
        
        # Calculate and manage context size
        context_tokens = self.calculate_context_tokens(messages)
        if context_tokens > self.max_context_tokens:
            messages = self.truncate_context(messages, self.max_context_tokens)
        
        async def _stream_request() -> AsyncIterator[str]:
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_response_tokens,
                    temperature=context.temperature,
                    stream=True
                )
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                        
            except Exception as e:
                self.logger.error(f"Streaming error: {e}", extra={"correlation_id": correlation_id})
                raise
        
        # Execute streaming with resilience (note: streaming doesn't use circuit breaker)
        try:
            async for content_chunk in _stream_request():
                yield content_chunk
        except Exception as e:
            # Fallback to non-streaming response
            self.logger.warning(
                f"Streaming failed, falling back to regular response: {e}",
                extra={"correlation_id": correlation_id}
            )
            response = await self.generate_response(context, correlation_id)
            yield response.content
    
    def generate_fallback_response(self, error_type: str = "general") -> LLMResponse:
        """Generate fallback response for API failures."""
        fallback_content = self.fallback_responses.get(error_type, self.fallback_responses["general"])
        
        return LLMResponse(
            content=fallback_content,
            token_usage=TokenUsage(),  # No tokens used for fallback
            model="fallback",
            finish_reason="fallback",
            response_time=0.0,
            metadata={"fallback": True, "error_type": error_type}
        )
    
    def create_conversation_context(
        self,
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> ConversationContext:
        """Create new conversation context."""
        if conversation_id is None:
            conversation_id = str(uuid4())
        
        settings = get_settings()
        
        context = ConversationContext(
            conversation_id=conversation_id,
            system_prompt=system_prompt or settings.system_prompt,
            max_tokens=max_tokens or self.max_context_tokens,
            temperature=temperature or self.temperature
        )
        
        self.conversation_contexts[conversation_id] = context
        return context
    
    def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get existing conversation context."""
        return self.conversation_contexts.get(conversation_id)
    
    def optimize_conversation_history(self, context: ConversationContext) -> None:
        """
        Optimize conversation history to maintain context within token limits.
        
        This method can be called periodically to clean up old messages
        and maintain optimal context size.
        """
        messages = context.get_messages_for_api()
        total_tokens = self.calculate_context_tokens(messages)
        
        if total_tokens > self.max_context_tokens * 0.8:  # 80% threshold
            # Keep system prompt and recent important messages
            optimized_messages = self.truncate_context(messages, int(self.max_context_tokens * 0.6))
            
            # Update context with optimized messages
            context.messages = []
            for msg in optimized_messages:
                if msg["role"] != "system":  # Skip system messages as they're handled separately
                    context.add_message(
                        MessageRole(msg["role"]),
                        msg["content"]
                    )
            
            self.logger.info(
                f"Optimized conversation history: {total_tokens} -> {self.calculate_context_tokens(optimized_messages)} tokens",
                extra={"conversation_id": context.conversation_id}
            )
    
    def get_token_usage_summary(self) -> Dict[str, Any]:
        """Get comprehensive token usage summary."""
        return {
            "total_usage": {
                "prompt_tokens": self.total_token_usage.prompt_tokens,
                "completion_tokens": self.total_token_usage.completion_tokens,
                "total_tokens": self.total_token_usage.total_tokens,
                "estimated_cost": self.total_token_usage.cost_estimate
            },
            "active_conversations": len(self.conversation_contexts),
            "model": self.model,
            "max_context_tokens": self.max_context_tokens,
            "max_response_tokens": self.max_response_tokens
        }
    
    async def health_check(self) -> bool:
        """Perform health check by making a simple API call."""
        try:
            # Create a minimal test context
            test_context = ConversationContext(
                conversation_id="health_check",
                system_prompt="You are a helpful assistant.",
                max_tokens=100
            )
            test_context.add_message(MessageRole.USER, "Hello")
            
            # Make a simple API call
            response = await self.generate_response(test_context)
            return bool(response.content)
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
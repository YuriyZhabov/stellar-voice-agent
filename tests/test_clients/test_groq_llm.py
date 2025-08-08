"""Tests for Groq LLM client with context management."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from openai.types.chat import ChatCompletion
from openai.types.completion_usage import CompletionUsage

from src.clients.groq_llm import (
    GroqLLMClient,
    Message,
    MessageRole,
    TokenUsage,
    ConversationContext,
    LLMResponse
)
from src.clients.base import RetryConfig, CircuitBreakerConfig


class TestMessage:
    """Test Message class."""
    
    def test_message_creation(self):
        """Test message creation with all fields."""
        message = Message(
            role=MessageRole.USER,
            content="Hello, world!",
            metadata={"test": True}
        )
        
        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"
        assert message.metadata == {"test": True}
        assert message.timestamp > 0
    
    def test_message_to_groq_format(self):
        """Test conversion to Groq API format."""
        message = Message(role=MessageRole.ASSISTANT, content="Hi there!")
        
        groq_format = message.to_groq_format()
        
        assert groq_format == {
            "role": "assistant",
            "content": "Hi there!"
        }


class TestTokenUsage:
    """Test TokenUsage class."""
    
    def test_token_usage_creation(self):
        """Test token usage creation."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
    
    def test_cost_estimate(self):
        """Test cost estimation calculation for Groq pricing."""
        usage = TokenUsage(
            prompt_tokens=1000,  # $0.0001
            completion_tokens=1000,  # $0.0002
            total_tokens=2000
        )
        
        expected_cost = (1000 / 1000) * 0.0001 + (1000 / 1000) * 0.0002  # $0.0003
        assert abs(usage.cost_estimate - expected_cost) < 0.00001


class TestConversationContext:
    """Test ConversationContext class."""
    
    def test_context_creation(self):
        """Test conversation context creation."""
        context = ConversationContext(
            conversation_id="test-123",
            system_prompt="You are helpful.",
            max_tokens=2000,
            temperature=0.8
        )
        
        assert context.conversation_id == "test-123"
        assert context.system_prompt == "You are helpful."
        assert context.max_tokens == 2000
        assert context.temperature == 0.8
        assert len(context.messages) == 0
    
    def test_add_message(self):
        """Test adding messages to context."""
        context = ConversationContext(conversation_id="test")
        
        context.add_message(MessageRole.USER, "Hello")
        context.add_message(MessageRole.ASSISTANT, "Hi there!", {"confidence": 0.9})
        
        assert len(context.messages) == 2
        assert context.messages[0].role == MessageRole.USER
        assert context.messages[0].content == "Hello"
        assert context.messages[1].role == MessageRole.ASSISTANT
        assert context.messages[1].content == "Hi there!"
        assert context.messages[1].metadata == {"confidence": 0.9}
    
    def test_get_messages_for_api(self):
        """Test formatting messages for Groq API."""
        context = ConversationContext(
            conversation_id="test",
            system_prompt="You are helpful."
        )
        context.add_message(MessageRole.USER, "Hello")
        context.add_message(MessageRole.ASSISTANT, "Hi!")
        
        api_messages = context.get_messages_for_api()
        
        expected = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        assert api_messages == expected
    
    def test_get_messages_for_api_no_system_prompt(self):
        """Test formatting messages without system prompt."""
        context = ConversationContext(conversation_id="test")
        context.add_message(MessageRole.USER, "Hello")
        
        api_messages = context.get_messages_for_api()
        
        expected = [
            {"role": "user", "content": "Hello"}
        ]
        
        assert api_messages == expected


class TestGroqLLMClient:
    """Test Groq LLM client."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('src.clients.groq_llm.get_settings') as mock:
            mock.return_value = MagicMock(
                groq_api_key="gsk_test-api-key",
                groq_model="meta-llama/llama-3.1-70b-versatile",
                context_window_size=4000,
                max_response_tokens=150,
                ai_temperature=0.7,
                system_prompt="You are a helpful assistant."
            )
            yield mock.return_value
    
    @pytest.fixture
    def client(self, mock_settings):
        """Create Groq LLM client for testing."""
        with patch('src.clients.groq_llm.AsyncOpenAI'):
            client = GroqLLMClient(
                api_key="gsk_test-key",
                model="meta-llama/llama-3.1-70b-versatile",
                max_context_tokens=4000,
                max_response_tokens=150,
                temperature=0.7
            )
            yield client
    
    def test_client_initialization(self, mock_settings):
        """Test client initialization with settings."""
        with patch('src.clients.groq_llm.AsyncOpenAI') as mock_openai:
            client = GroqLLMClient()
            
            assert client.api_key == "gsk_test-api-key"
            assert client.model == "meta-llama/llama-3.1-70b-versatile"
            assert client.max_context_tokens == 4000
            assert client.max_response_tokens == 150
            assert client.temperature == 0.7
            
            mock_openai.assert_called_once_with(
                api_key="gsk_test-api-key",
                base_url="https://api.groq.com/openai/v1",
                timeout=30.0
            )
    
    def test_client_initialization_no_api_key(self, mock_settings):
        """Test client initialization fails without API key."""
        mock_settings.groq_api_key = None
        
        with patch('src.clients.groq_llm.AsyncOpenAI'):
            with pytest.raises(ValueError, match="Groq API key is required"):
                GroqLLMClient()
    
    def test_estimate_tokens(self, client):
        """Test token estimation."""
        # Test basic estimation (4 chars per token)
        assert client.estimate_tokens("hello") == 1  # 5 chars / 4 = 1.25 -> 1
        assert client.estimate_tokens("hello world") == 2  # 11 chars / 4 = 2.75 -> 2
        assert client.estimate_tokens("a" * 100) == 25  # 100 chars / 4 = 25
    
    def test_calculate_context_tokens(self, client):
        """Test context token calculation."""
        messages = [
            {"role": "system", "content": "You are helpful."},  # ~4 + 4 + 4 = 12
            {"role": "user", "content": "Hello"},  # ~1 + 1 + 4 = 6
            {"role": "assistant", "content": "Hi there!"}  # ~2 + 2 + 4 = 8
        ]
        
        tokens = client.calculate_context_tokens(messages)
        assert tokens > 0  # Should calculate some tokens
        assert tokens < 100  # Should be reasonable for short messages
    
    def test_truncate_context_no_truncation_needed(self, client):
        """Test context truncation when no truncation is needed."""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]
        
        truncated = client.truncate_context(messages, 1000)
        assert truncated == messages
    
    def test_truncate_context_with_truncation(self, client):
        """Test context truncation when truncation is needed."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
            {"role": "assistant", "content": "Second response"},
            {"role": "user", "content": "Third message"}
        ]
        
        # Set very low token limit to force truncation
        truncated = client.truncate_context(messages, 50)
        
        # Should keep system message and some recent messages
        assert len(truncated) <= len(messages)
        
        # Find system messages in truncated result
        system_messages = [msg for msg in truncated if msg["role"] == "system"]
        assert len(system_messages) >= 1  # At least one system message should be preserved
        
        # If there are conversation messages, the most recent should be preserved
        conversation_messages = [msg for msg in truncated if msg["role"] != "system"]
        if conversation_messages:
            # The last conversation message should be one of the more recent ones
            last_content = conversation_messages[-1]["content"]
            recent_contents = ["Second message", "Second response", "Third message"]
            assert last_content in recent_contents
    
    def test_truncate_context_empty_messages(self, client):
        """Test context truncation with empty messages."""
        messages = []
        truncated = client.truncate_context(messages, 1000)
        assert truncated == []
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, client):
        """Test successful response generation."""
        # Mock Groq response
        mock_response = MagicMock(spec=ChatCompletion)
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(spec=CompletionUsage)
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        mock_response.usage.total_tokens = 18
        
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Create test context
        context = ConversationContext(conversation_id="test")
        context.add_message(MessageRole.USER, "Hello")
        
        # Generate response
        response = await client.generate_response(context)
        
        assert isinstance(response, LLMResponse)
        assert response.content == "Hello! How can I help you?"
        assert response.model == "meta-llama/llama-3.1-70b-versatile"
        assert response.finish_reason == "stop"
        assert response.token_usage.prompt_tokens == 10
        assert response.token_usage.completion_tokens == 8
        assert response.token_usage.total_tokens == 18
        assert response.response_time > 0
    
    @pytest.mark.asyncio
    async def test_generate_response_with_context_truncation(self, client):
        """Test response generation with context truncation."""
        # Mock Groq response
        mock_response = MagicMock(spec=ChatCompletion)
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(spec=CompletionUsage)
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8
        
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Create context with many messages to trigger truncation
        context = ConversationContext(conversation_id="test")
        for i in range(100):  # Add many messages
            context.add_message(MessageRole.USER, f"Message {i}" * 50)  # Long messages
            context.add_message(MessageRole.ASSISTANT, f"Response {i}" * 50)
        
        # Generate response
        response = await client.generate_response(context)
        
        assert response.content == "Response"
        assert response.metadata["truncated"] is True
    
    @pytest.mark.asyncio
    async def test_generate_response_api_error(self, client):
        """Test handling of general API errors."""
        client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Groq API error")
        )
        
        context = ConversationContext(conversation_id="test")
        context.add_message(MessageRole.USER, "Hello")
        
        with pytest.raises(Exception, match="Groq API error"):
            await client.generate_response(context)
    
    @pytest.mark.asyncio
    async def test_stream_response_success(self, client):
        """Test successful streaming response."""
        # Mock streaming response
        async def mock_stream():
            chunks = ["Hello", " there", "!", ""]
            for chunk in chunks:
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock()]
                mock_chunk.choices[0].delta.content = chunk
                yield mock_chunk
        
        client.client.chat.completions.create = AsyncMock(return_value=mock_stream())
        
        context = ConversationContext(conversation_id="test")
        context.add_message(MessageRole.USER, "Hello")
        
        # Collect streamed content
        content_chunks = []
        async for chunk in client.stream_response(context):
            content_chunks.append(chunk)
        
        assert content_chunks == ["Hello", " there", "!"]
    
    @pytest.mark.asyncio
    async def test_stream_response_fallback_to_regular(self, client):
        """Test streaming fallback to regular response on error."""
        # Mock streaming to fail
        client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Streaming failed")
        )
        
        # Mock regular response generation
        with patch.object(client, 'generate_response') as mock_generate:
            mock_response = LLMResponse(
                content="Fallback response",
                token_usage=TokenUsage(),
                model="meta-llama/llama-3.1-70b-versatile",
                finish_reason="stop",
                response_time=0.1
            )
            mock_generate.return_value = mock_response
            
            context = ConversationContext(conversation_id="test")
            context.add_message(MessageRole.USER, "Hello")
            
            # Collect streamed content
            content_chunks = []
            async for chunk in client.stream_response(context):
                content_chunks.append(chunk)
            
            assert content_chunks == ["Fallback response"]
            mock_generate.assert_called_once()
    
    def test_generate_fallback_response(self, client):
        """Test fallback response generation."""
        # Test default fallback
        response = client.generate_fallback_response()
        assert response.content == client.fallback_responses["general"]
        assert response.model == "fallback"
        assert response.finish_reason == "fallback"
        assert response.metadata["fallback"] is True
        
        # Test specific error type
        response = client.generate_fallback_response("rate_limit")
        assert response.content == client.fallback_responses["rate_limit"]
        assert response.metadata["error_type"] == "rate_limit"
    
    def test_create_conversation_context(self, client, mock_settings):
        """Test conversation context creation."""
        context = client.create_conversation_context(
            conversation_id="test-123",
            system_prompt="Custom prompt",
            max_tokens=2000,
            temperature=0.8
        )
        
        assert context.conversation_id == "test-123"
        assert context.system_prompt == "Custom prompt"
        assert context.max_tokens == 2000
        assert context.temperature == 0.8
        assert client.conversation_contexts["test-123"] == context
    
    def test_create_conversation_context_with_defaults(self, client, mock_settings):
        """Test conversation context creation with default values."""
        context = client.create_conversation_context()
        
        assert context.conversation_id is not None
        assert context.system_prompt == "You are a helpful assistant."
        assert context.max_tokens == 4000
        assert context.temperature == 0.7
    
    def test_get_conversation_context(self, client):
        """Test retrieving conversation context."""
        # Create context
        context = client.create_conversation_context("test-123")
        
        # Retrieve context
        retrieved = client.get_conversation_context("test-123")
        assert retrieved == context
        
        # Test non-existent context
        assert client.get_conversation_context("non-existent") is None
    
    def test_optimize_conversation_history(self, client):
        """Test conversation history optimization."""
        context = ConversationContext(conversation_id="test")
        
        # Add many messages to trigger optimization
        for i in range(50):
            context.add_message(MessageRole.USER, f"Long message {i}" * 20)
            context.add_message(MessageRole.ASSISTANT, f"Long response {i}" * 20)
        
        original_count = len(context.messages)
        
        # Optimize history
        client.optimize_conversation_history(context)
        
        # Should have fewer messages after optimization
        assert len(context.messages) < original_count
    
    def test_get_token_usage_summary(self, client):
        """Test token usage summary."""
        # Simulate some token usage
        client.total_token_usage.prompt_tokens = 1000
        client.total_token_usage.completion_tokens = 500
        client.total_token_usage.total_tokens = 1500
        
        # Create some contexts
        client.create_conversation_context("test-1")
        client.create_conversation_context("test-2")
        
        summary = client.get_token_usage_summary()
        
        assert summary["total_usage"]["prompt_tokens"] == 1000
        assert summary["total_usage"]["completion_tokens"] == 500
        assert summary["total_usage"]["total_tokens"] == 1500
        assert summary["total_usage"]["estimated_cost"] > 0
        assert summary["active_conversations"] == 2
        assert summary["model"] == "meta-llama/llama-3.1-70b-versatile"
        assert summary["max_context_tokens"] == 4000
        assert summary["max_response_tokens"] == 150
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        # Mock successful response
        mock_response = MagicMock(spec=ChatCompletion)
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I'm healthy!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(spec=CompletionUsage)
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8
        
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await client.health_check()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check failure."""
        client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Health check failed")
        )
        
        result = await client.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client cleanup."""
        client.client.close = AsyncMock()
        
        await client.close()
        
        client.client.close.assert_called_once()


class TestIntegration:
    """Integration tests for Groq LLM client."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test complete conversation flow."""
        with patch('src.clients.groq_llm.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                groq_api_key="gsk_test-key",
                groq_model="meta-llama/llama-3.1-70b-versatile",
                context_window_size=4000,
                max_response_tokens=150,
                ai_temperature=0.7,
                system_prompt="You are helpful."
            )
            
            with patch('src.clients.groq_llm.AsyncOpenAI') as mock_openai:
                # Create client
                client = GroqLLMClient()
                
                # Mock responses
                mock_response1 = MagicMock(spec=ChatCompletion)
                mock_response1.choices = [MagicMock()]
                mock_response1.choices[0].message.content = "Hello! How can I help?"
                mock_response1.choices[0].finish_reason = "stop"
                mock_response1.usage = MagicMock(spec=CompletionUsage)
                mock_response1.usage.prompt_tokens = 10
                mock_response1.usage.completion_tokens = 8
                mock_response1.usage.total_tokens = 18
                
                mock_response2 = MagicMock(spec=ChatCompletion)
                mock_response2.choices = [MagicMock()]
                mock_response2.choices[0].message.content = "I can help with that!"
                mock_response2.choices[0].finish_reason = "stop"
                mock_response2.usage = MagicMock(spec=CompletionUsage)
                mock_response2.usage.prompt_tokens = 15
                mock_response2.usage.completion_tokens = 10
                mock_response2.usage.total_tokens = 25
                
                client.client.chat.completions.create = AsyncMock(
                    side_effect=[mock_response1, mock_response2]
                )
                
                # Create conversation
                context = client.create_conversation_context("test-conversation")
                
                # First exchange
                context.add_message(MessageRole.USER, "Hello")
                response1 = await client.generate_response(context)
                context.add_message(MessageRole.ASSISTANT, response1.content)
                
                # Second exchange
                context.add_message(MessageRole.USER, "Can you help me?")
                response2 = await client.generate_response(context)
                context.add_message(MessageRole.ASSISTANT, response2.content)
                
                # Verify conversation state
                assert len(context.messages) == 4
                assert response1.content == "Hello! How can I help?"
                assert response2.content == "I can help with that!"
                
                # Verify token tracking
                assert client.total_token_usage.total_tokens == 43  # 18 + 25
                
                # Verify conversation context
                retrieved_context = client.get_conversation_context("test-conversation")
                assert retrieved_context == context
                
                # Mock the close method to be async
                client.client.close = AsyncMock()
                await client.close()
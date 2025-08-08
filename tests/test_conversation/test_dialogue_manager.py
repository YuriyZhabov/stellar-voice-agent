"""Tests for DialogueManager conversation context management."""

import asyncio
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.conversation.dialogue_manager import (
    DialogueManager,
    ConversationTurn,
    ConversationSummary,
    ConversationMetrics,
    ConversationPhase
)
from src.conversation.state_machine import ConversationStateMachine, ConversationState
from src.clients.openai_llm import (
    OpenAILLMClient,
    ConversationContext,
    MessageRole,
    LLMResponse,
    TokenUsage
)


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock(spec=OpenAILLMClient)
    
    # Mock conversation context creation
    mock_context = MagicMock(spec=ConversationContext)
    mock_context.conversation_id = "test_conversation"
    mock_context.messages = []
    mock_context.add_message = MagicMock()
    mock_context.get_messages_for_api = MagicMock(return_value=[])
    
    client.create_conversation_context.return_value = mock_context
    client.calculate_context_tokens.return_value = 100
    client.optimize_conversation_history = MagicMock()
    
    # Mock token usage summary
    client.get_token_usage_summary.return_value = {
        "total_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost": 0.01
        }
    }
    
    return client


@pytest.fixture
def mock_state_machine():
    """Create mock state machine."""
    return MagicMock(spec=ConversationStateMachine)


@pytest.fixture
def dialogue_manager(mock_llm_client, mock_state_machine):
    """Create DialogueManager instance for testing."""
    return DialogueManager(
        conversation_id="test_conversation",
        llm_client=mock_llm_client,
        state_machine=mock_state_machine,
        max_context_turns=10,
        max_context_tokens=1000,
        summarization_threshold=5
    )


class TestDialogueManagerInitialization:
    """Test DialogueManager initialization."""
    
    def test_initialization_with_defaults(self, mock_llm_client, mock_state_machine):
        """Test DialogueManager initialization with default parameters."""
        manager = DialogueManager(
            conversation_id="test_conv",
            llm_client=mock_llm_client,
            state_machine=mock_state_machine
        )
        
        assert manager.conversation_id == "test_conv"
        assert manager.llm_client == mock_llm_client
        assert manager.state_machine == mock_state_machine
        assert manager.max_context_turns == 20  # default
        assert manager.max_context_tokens == 4000  # default
        assert manager.summarization_threshold == 15  # default
        assert manager.current_phase == ConversationPhase.INITIALIZATION
        assert len(manager.conversation_turns) == 0
        assert isinstance(manager.metrics, ConversationMetrics)
    
    def test_initialization_with_custom_parameters(self, mock_llm_client, mock_state_machine):
        """Test DialogueManager initialization with custom parameters."""
        custom_prompt = "You are a test assistant."
        
        manager = DialogueManager(
            conversation_id="custom_conv",
            llm_client=mock_llm_client,
            state_machine=mock_state_machine,
            max_context_turns=5,
            max_context_tokens=500,
            summarization_threshold=3,
            system_prompt=custom_prompt
        )
        
        assert manager.max_context_turns == 5
        assert manager.max_context_tokens == 500
        assert manager.summarization_threshold == 3
        assert manager.system_prompt == custom_prompt
        
        # Verify LLM client was called with correct parameters
        mock_llm_client.create_conversation_context.assert_called_once_with(
            conversation_id="custom_conv",
            system_prompt=custom_prompt,
            max_tokens=500
        )


class TestUserInputProcessing:
    """Test user input processing and response generation."""
    
    @pytest.mark.asyncio
    async def test_process_user_input_success(self, dialogue_manager, mock_llm_client):
        """Test successful user input processing."""
        # Mock LLM response
        mock_response = LLMResponse(
            content="Hello! How can I help you?",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.5
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Process user input
        user_input = "Hello, how are you?"
        response, turn = await dialogue_manager.process_user_input(user_input)
        
        # Verify response
        assert response == "Hello! How can I help you?"
        assert isinstance(turn, ConversationTurn)
        assert turn.user_input == user_input
        assert turn.assistant_response == "Hello! How can I help you?"
        assert turn.processing_time > 0
        
        # Verify conversation state
        assert len(dialogue_manager.conversation_turns) == 1
        assert dialogue_manager.metrics.total_turns == 1
        assert dialogue_manager.current_phase == ConversationPhase.RESPONSE
        
        # Verify LLM client interactions
        mock_llm_client.generate_response.assert_called_once()
        dialogue_manager.conversation_context.add_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_user_input_with_metadata(self, dialogue_manager, mock_llm_client):
        """Test user input processing with metadata."""
        mock_response = LLMResponse(
            content="Response with metadata",
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.3
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        metadata = {"source": "phone", "caller_id": "123456"}
        response, turn = await dialogue_manager.process_user_input(
            "Test input",
            metadata=metadata
        )
        
        # Verify metadata is preserved
        assert "source" in turn.metadata
        assert "caller_id" in turn.metadata
        assert turn.metadata["source"] == "phone"
        assert turn.metadata["caller_id"] == "123456"
    
    @pytest.mark.asyncio
    async def test_process_user_input_error_handling(self, dialogue_manager, mock_llm_client):
        """Test error handling during user input processing."""
        # Mock LLM client to raise exception
        mock_llm_client.generate_response.side_effect = Exception("API Error")
        
        # Mock fallback response
        fallback_response = LLMResponse(
            content="I apologize, but I'm having trouble processing your request right now.",
            token_usage=TokenUsage(),
            model="fallback",
            finish_reason="fallback",
            response_time=0.0
        )
        mock_llm_client.generate_fallback_response.return_value = fallback_response
        
        # Process user input
        response, turn = await dialogue_manager.process_user_input("Test input")
        
        # Verify fallback response
        assert response == fallback_response.content
        assert turn.metadata.get("fallback") is True
        assert turn.metadata.get("error") == "API Error"
        
        # Verify metrics
        assert dialogue_manager.metrics.error_count == 1
        assert dialogue_manager.metrics.fallback_responses == 1


class TestContextManagement:
    """Test conversation context management and summarization."""
    
    @pytest.mark.asyncio
    async def test_context_size_management(self, dialogue_manager, mock_llm_client):
        """Test context size management and optimization."""
        # Mock high token count to trigger optimization
        mock_llm_client.calculate_context_tokens.return_value = 850  # 85% of 1000
        
        mock_response = LLMResponse(
            content="Response",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.2
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Process input to trigger context management
        await dialogue_manager.process_user_input("Test input")
        
        # Verify optimization was called
        mock_llm_client.optimize_conversation_history.assert_called_once()
        assert dialogue_manager.metrics.context_truncations == 1
    
    @pytest.mark.asyncio
    async def test_conversation_summarization(self, dialogue_manager, mock_llm_client):
        """Test conversation summarization when threshold is reached."""
        # Add turns to reach summarization threshold
        for i in range(5):  # threshold is 5
            dialogue_manager.conversation_turns.append(
                ConversationTurn(
                    turn_id=str(uuid4()),
                    user_input=f"User input {i}",
                    assistant_response=f"Assistant response {i}",
                    timestamp=datetime.now(UTC),
                    processing_time=0.1
                )
            )
        
        # Mock summary response
        summary_response = LLMResponse(
            content="This conversation covered topics A, B, and C.",
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.8
        )
        
        # Mock LLM client for both regular response and summary
        mock_llm_client.generate_response.side_effect = [summary_response, summary_response]
        
        # Process input to trigger summarization
        await dialogue_manager.process_user_input("Trigger summarization")
        
        # Verify summarization occurred
        assert dialogue_manager.conversation_summary is not None
        assert "topics A, B, and C" in dialogue_manager.conversation_summary
    
    @pytest.mark.asyncio
    async def test_add_to_history(self, dialogue_manager):
        """Test adding messages to conversation history."""
        # Add user message
        await dialogue_manager.add_to_history("user", "Hello", {"test": True})
        
        # Add assistant message
        await dialogue_manager.add_to_history("assistant", "Hi there!", {"response": True})
        
        # Verify messages were added
        assert dialogue_manager.conversation_context.add_message.call_count == 2
        
        # Verify correct roles were used
        calls = dialogue_manager.conversation_context.add_message.call_args_list
        assert calls[0][0][0] == MessageRole.USER
        assert calls[0][0][1] == "Hello"
        assert calls[1][0][0] == MessageRole.ASSISTANT
        assert calls[1][0][1] == "Hi there!"


class TestConversationSummary:
    """Test conversation summary generation and analytics."""
    
    def test_get_conversation_summary(self, dialogue_manager):
        """Test conversation summary generation."""
        # Add some conversation turns
        for i in range(3):
            dialogue_manager.conversation_turns.append(
                ConversationTurn(
                    turn_id=str(uuid4()),
                    user_input=f"User input {i}",
                    assistant_response=f"Assistant response {i}",
                    timestamp=datetime.now(UTC),
                    processing_time=0.1 + i * 0.05
                )
            )
        
        # Update metrics
        dialogue_manager.metrics.total_turns = 3
        dialogue_manager.metrics.average_response_time = 0.125
        
        summary = dialogue_manager.get_conversation_summary()
        
        assert isinstance(summary, ConversationSummary)
        assert summary.conversation_id == "test_conversation"
        assert summary.total_turns == 3
        assert summary.participant_count == 2
        assert summary.total_duration > 0
        assert "overall_score" in summary.quality_metrics
    
    def test_quality_metrics_calculation(self, dialogue_manager):
        """Test quality metrics calculation."""
        # Set up metrics for testing
        dialogue_manager.metrics.total_turns = 10
        dialogue_manager.metrics.average_response_time = 1.0  # Good response time
        dialogue_manager.metrics.error_count = 1  # 10% error rate
        dialogue_manager.metrics.context_truncations = 0
        dialogue_manager.metrics.fallback_responses = 0
        
        quality_metrics = dialogue_manager._calculate_quality_metrics()
        
        assert "response_time_score" in quality_metrics
        assert "error_score" in quality_metrics
        assert "context_efficiency" in quality_metrics
        assert "fallback_score" in quality_metrics
        assert "overall_score" in quality_metrics
        
        # Verify scores are between 0 and 1
        for score in quality_metrics.values():
            assert 0 <= score <= 1
    
    def test_topic_extraction(self, dialogue_manager):
        """Test simple topic extraction from conversation."""
        # Add turns with identifiable topics
        dialogue_manager.conversation_turns = [
            ConversationTurn(
                turn_id="1",
                user_input="I want to discuss weather patterns and climate change",
                assistant_response="Sure, let's talk about weather",
                timestamp=datetime.now(UTC),
                processing_time=0.1
            ),
            ConversationTurn(
                turn_id="2",
                user_input="What about machine learning algorithms?",
                assistant_response="Machine learning is fascinating",
                timestamp=datetime.now(UTC),
                processing_time=0.1
            )
        ]
        
        topics = dialogue_manager._extract_topics()
        
        # Should extract words longer than 4 characters
        expected_topics = {"weather", "patterns", "climate", "change", "machine", "learning", "algorithms"}
        extracted_topics = set(topics)
        
        # Check that some expected topics are found
        assert len(extracted_topics.intersection(expected_topics)) > 0


class TestMetricsAndAnalytics:
    """Test metrics collection and analytics."""
    
    def test_metrics_initialization(self, dialogue_manager):
        """Test metrics are properly initialized."""
        metrics = dialogue_manager.metrics
        
        assert metrics.total_turns == 0
        assert metrics.average_response_time == 0.0
        assert metrics.error_count == 0
        assert metrics.interruption_count == 0
        assert metrics.context_truncations == 0
        assert metrics.fallback_responses == 0
    
    def test_update_service_latency(self, dialogue_manager):
        """Test updating service-specific latency metrics."""
        dialogue_manager.update_service_latency("stt", 0.1)
        dialogue_manager.update_service_latency("llm", 0.5)
        dialogue_manager.update_service_latency("tts", 0.2)
        
        assert dialogue_manager.metrics.stt_latency == 0.1
        assert dialogue_manager.metrics.llm_latency == 0.5
        assert dialogue_manager.metrics.tts_latency == 0.2
    
    def test_record_interruption(self, dialogue_manager):
        """Test recording user interruptions."""
        initial_count = dialogue_manager.metrics.interruption_count
        
        dialogue_manager.record_interruption()
        dialogue_manager.record_interruption()
        
        assert dialogue_manager.metrics.interruption_count == initial_count + 2
    
    def test_conversation_metrics_update(self, dialogue_manager):
        """Test conversation metrics update with response times."""
        metrics = dialogue_manager.metrics
        
        # Test first response time
        metrics.update_response_time(1.0)
        assert metrics.average_response_time == 1.0
        
        # Test second response time
        metrics.total_turns = 1  # Simulate first turn completed
        metrics.update_response_time(2.0)
        assert metrics.average_response_time == 1.5  # (1.0 + 2.0) / 2


class TestConversationLifecycle:
    """Test complete conversation lifecycle."""
    
    def test_get_conversation_history(self, dialogue_manager):
        """Test retrieving conversation history."""
        # Add some turns
        for i in range(5):
            dialogue_manager.conversation_turns.append(
                ConversationTurn(
                    turn_id=str(i),
                    user_input=f"Input {i}",
                    assistant_response=f"Response {i}",
                    timestamp=datetime.now(UTC),
                    processing_time=0.1
                )
            )
        
        # Test getting all history
        all_history = dialogue_manager.get_conversation_history()
        assert len(all_history) == 5
        
        # Test getting limited history
        limited_history = dialogue_manager.get_conversation_history(limit=3)
        assert len(limited_history) == 3
        assert limited_history[0].turn_id == "2"  # Last 3 turns
    
    def test_end_conversation(self, dialogue_manager):
        """Test ending conversation and getting final summary."""
        # Add a turn
        dialogue_manager.conversation_turns.append(
            ConversationTurn(
                turn_id="final",
                user_input="Goodbye",
                assistant_response="Goodbye!",
                timestamp=datetime.now(UTC),
                processing_time=0.1
            )
        )
        dialogue_manager.metrics.total_turns = 1
        
        summary = dialogue_manager.end_conversation()
        
        assert dialogue_manager.end_time is not None
        assert dialogue_manager.current_phase == ConversationPhase.COMPLETION
        assert isinstance(summary, ConversationSummary)
        assert summary.total_turns == 1
    
    def test_get_status(self, dialogue_manager):
        """Test getting dialogue manager status."""
        status = dialogue_manager.get_status()
        
        assert "conversation_id" in status
        assert "current_phase" in status
        assert "total_turns" in status
        assert "start_time" in status
        assert "duration" in status
        assert "metrics" in status
        assert "context_size" in status
        assert "has_summary" in status
        
        assert status["conversation_id"] == "test_conversation"
        assert status["current_phase"] == ConversationPhase.INITIALIZATION.value


class TestConcurrencyAndThreadSafety:
    """Test concurrency handling and thread safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_lock(self, dialogue_manager, mock_llm_client):
        """Test that concurrent processing is properly locked."""
        mock_response = LLMResponse(
            content="Response",
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.1
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Start two concurrent processing tasks
        task1 = asyncio.create_task(
            dialogue_manager.process_user_input("Input 1")
        )
        task2 = asyncio.create_task(
            dialogue_manager.process_user_input("Input 2")
        )
        
        # Wait for both to complete
        results = await asyncio.gather(task1, task2)
        
        # Verify both completed successfully
        assert len(results) == 2
        assert all(isinstance(result[1], ConversationTurn) for result in results)
        
        # Verify turns were processed sequentially (due to lock)
        assert len(dialogue_manager.conversation_turns) == 2


class TestErrorHandlingAndResilience:
    """Test error handling and system resilience."""
    
    @pytest.mark.asyncio
    async def test_llm_client_failure_recovery(self, dialogue_manager, mock_llm_client):
        """Test recovery from LLM client failures."""
        # First call fails, second succeeds
        mock_llm_client.generate_response.side_effect = [
            Exception("Network error"),
            LLMResponse(
                content="Recovery response",
                token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
                model="gpt-4",
                finish_reason="stop",
                response_time=0.2
            )
        ]
        
        # Mock fallback response for first failure
        fallback_response = LLMResponse(
            content="Fallback response",
            token_usage=TokenUsage(),
            model="fallback",
            finish_reason="fallback",
            response_time=0.0
        )
        mock_llm_client.generate_fallback_response.return_value = fallback_response
        
        # First call should use fallback
        response1, turn1 = await dialogue_manager.process_user_input("First input")
        assert response1 == "Fallback response"
        assert turn1.metadata.get("fallback") is True
        
        # Reset the side effect for second call
        mock_llm_client.generate_response.side_effect = None
        mock_llm_client.generate_response.return_value = LLMResponse(
            content="Recovery response",
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.2
        )
        
        # Second call should succeed
        response2, turn2 = await dialogue_manager.process_user_input("Second input")
        assert response2 == "Recovery response"
        assert turn2.metadata.get("fallback") is not True
    
    @pytest.mark.asyncio
    async def test_context_management_failure_handling(self, dialogue_manager, mock_llm_client):
        """Test handling of context management failures."""
        # Mock context optimization to fail
        mock_llm_client.optimize_conversation_history.side_effect = Exception("Context error")
        mock_llm_client.calculate_context_tokens.return_value = 900  # High token count
        
        # Mock the generate_response to fail first, then fallback should be used
        mock_llm_client.generate_response.side_effect = Exception("Context error")
        
        # Mock fallback response
        fallback_response = LLMResponse(
            content="I apologize, but I'm having trouble processing your request right now.",
            token_usage=TokenUsage(),
            model="fallback",
            finish_reason="fallback",
            response_time=0.0
        )
        mock_llm_client.generate_fallback_response.return_value = fallback_response
        
        # Should use fallback response when context management fails
        response, turn = await dialogue_manager.process_user_input("Test input")
        
        assert response == "I apologize, but I'm having trouble processing your request right now."
        assert isinstance(turn, ConversationTurn)
        assert turn.metadata.get("fallback") is True
        # Error should be logged and fallback used
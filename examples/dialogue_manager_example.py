#!/usr/bin/env python3
"""
Example demonstrating DialogueManager usage for conversation context management.

This example shows how to use the DialogueManager to maintain conversation
history, manage context, and coordinate AI service interactions.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from src.conversation.dialogue_manager import DialogueManager
from src.conversation.state_machine import ConversationStateMachine, ConversationState
from src.clients.openai_llm import (
    OpenAILLMClient,
    ConversationContext,
    MessageRole,
    LLMResponse,
    TokenUsage
)


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_llm_client():
    """Create a mock LLM client for demonstration."""
    client = AsyncMock(spec=OpenAILLMClient)
    
    # Mock conversation context
    mock_context = MagicMock(spec=ConversationContext)
    mock_context.conversation_id = "demo_conversation"
    mock_context.messages = []
    mock_context.add_message = MagicMock()
    mock_context.get_messages_for_api = MagicMock(return_value=[])
    
    client.create_conversation_context.return_value = mock_context
    client.calculate_context_tokens.return_value = 100
    client.optimize_conversation_history = MagicMock()
    
    # Mock responses for different inputs
    async def mock_generate_response(context, correlation_id=None):
        # Get the last user message to generate appropriate response
        if hasattr(context, 'messages') and context.messages:
            # This is a simplified response generation
            return LLMResponse(
                content="I understand. How can I help you further?",
                token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
                model="gpt-4",
                finish_reason="stop",
                response_time=0.5
            )
        else:
            return LLMResponse(
                content="Hello! How can I assist you today?",
                token_usage=TokenUsage(prompt_tokens=15, completion_tokens=8, total_tokens=23),
                model="gpt-4",
                finish_reason="stop",
                response_time=0.3
            )
    
    client.generate_response.side_effect = mock_generate_response
    
    # Mock fallback response
    client.generate_fallback_response.return_value = LLMResponse(
        content="I apologize, but I'm having trouble processing your request right now.",
        token_usage=TokenUsage(),
        model="fallback",
        finish_reason="fallback",
        response_time=0.0
    )
    
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


async def demonstrate_basic_conversation():
    """Demonstrate basic conversation flow."""
    logger.info("=== Basic Conversation Demo ===")
    
    # Create mock components
    llm_client = create_mock_llm_client()
    state_machine = MagicMock(spec=ConversationStateMachine)
    
    # Create DialogueManager
    dialogue_manager = DialogueManager(
        conversation_id="demo_basic",
        llm_client=llm_client,
        state_machine=state_machine,
        max_context_turns=10,
        system_prompt="You are a helpful assistant for demonstration purposes."
    )
    
    # Simulate conversation turns
    conversation_inputs = [
        "Hello, how are you?",
        "Can you help me with a question?",
        "What's the weather like?",
        "Thank you for your help!"
    ]
    
    for i, user_input in enumerate(conversation_inputs, 1):
        logger.info(f"\n--- Turn {i} ---")
        logger.info(f"User: {user_input}")
        
        # Process user input
        response, turn = await dialogue_manager.process_user_input(
            user_input,
            metadata={"turn_number": i, "demo": True}
        )
        
        logger.info(f"Assistant: {response}")
        logger.info(f"Processing time: {turn.processing_time:.3f}s")
        logger.info(f"Turn ID: {turn.turn_id}")
    
    # Get conversation summary
    summary = dialogue_manager.get_conversation_summary()
    logger.info(f"\n--- Conversation Summary ---")
    logger.info(f"Total turns: {summary.total_turns}")
    logger.info(f"Duration: {summary.total_duration:.2f}s")
    logger.info(f"Quality score: {summary.quality_metrics.get('overall_score', 0):.2f}")
    
    # Get metrics
    metrics = dialogue_manager.get_conversation_metrics()
    logger.info(f"\n--- Metrics ---")
    logger.info(f"Average response time: {metrics.average_response_time:.3f}s")
    logger.info(f"Error count: {metrics.error_count}")
    logger.info(f"Total processing time: {metrics.total_processing_time:.3f}s")


async def demonstrate_context_management():
    """Demonstrate context management and summarization."""
    logger.info("\n\n=== Context Management Demo ===")
    
    # Create mock components
    llm_client = create_mock_llm_client()
    state_machine = MagicMock(spec=ConversationStateMachine)
    
    # Create DialogueManager with small context limits for demo
    dialogue_manager = DialogueManager(
        conversation_id="demo_context",
        llm_client=llm_client,
        state_machine=state_machine,
        max_context_turns=3,  # Small limit to trigger summarization
        summarization_threshold=3,
        system_prompt="You are a helpful assistant demonstrating context management."
    )
    
    # Mock summarization response
    async def mock_summarization_response(context, correlation_id=None):
        if "summarize" in str(context.messages).lower():
            return LLMResponse(
                content="The conversation covered greetings, questions about assistance, and weather inquiries.",
                token_usage=TokenUsage(prompt_tokens=50, completion_tokens=15, total_tokens=65),
                model="gpt-4",
                finish_reason="stop",
                response_time=0.8
            )
        return LLMResponse(
            content="I understand your message.",
            token_usage=TokenUsage(prompt_tokens=20, completion_tokens=8, total_tokens=28),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.4
        )
    
    llm_client.generate_response.side_effect = mock_summarization_response
    
    # Simulate longer conversation to trigger summarization
    long_conversation = [
        "Hello there!",
        "I have a question about programming.",
        "Can you explain Python functions?",
        "What about classes and objects?",  # This should trigger summarization
        "How do I handle exceptions?",
        "Thank you for the explanations!"
    ]
    
    for i, user_input in enumerate(long_conversation, 1):
        logger.info(f"\n--- Turn {i} ---")
        logger.info(f"User: {user_input}")
        
        response, turn = await dialogue_manager.process_user_input(user_input)
        
        logger.info(f"Assistant: {response}")
        
        # Check if summarization occurred
        if dialogue_manager.conversation_summary:
            logger.info(f"📝 Conversation summarized: {dialogue_manager.conversation_summary}")
    
    # Show final status
    status = dialogue_manager.get_status()
    logger.info(f"\n--- Final Status ---")
    logger.info(f"Total turns: {status['total_turns']}")
    logger.info(f"Context size: {status['context_size']}")
    logger.info(f"Has summary: {status['has_summary']}")


async def demonstrate_error_handling():
    """Demonstrate error handling and fallback responses."""
    logger.info("\n\n=== Error Handling Demo ===")
    
    # Create mock components
    llm_client = create_mock_llm_client()
    state_machine = MagicMock(spec=ConversationStateMachine)
    
    # Create DialogueManager
    dialogue_manager = DialogueManager(
        conversation_id="demo_errors",
        llm_client=llm_client,
        state_machine=state_machine,
        system_prompt="You are a helpful assistant demonstrating error handling."
    )
    
    # Mock LLM client to fail on certain inputs
    async def mock_error_response(context, correlation_id=None):
        # Check if this should trigger an error
        if hasattr(context, 'messages') and any("error" in str(msg).lower() for msg in context.messages):
            raise Exception("Simulated API error")
        
        return LLMResponse(
            content="This response worked fine.",
            token_usage=TokenUsage(prompt_tokens=15, completion_tokens=8, total_tokens=23),
            model="gpt-4",
            finish_reason="stop",
            response_time=0.3
        )
    
    llm_client.generate_response.side_effect = mock_error_response
    
    # Test inputs including one that will cause an error
    test_inputs = [
        "Hello, this should work fine.",
        "Please trigger an error for testing.",  # This will cause an error
        "This should work again after the error."
    ]
    
    for i, user_input in enumerate(test_inputs, 1):
        logger.info(f"\n--- Turn {i} ---")
        logger.info(f"User: {user_input}")
        
        response, turn = await dialogue_manager.process_user_input(user_input)
        
        logger.info(f"Assistant: {response}")
        
        # Check if fallback was used
        if turn.metadata.get("fallback"):
            logger.info("⚠️  Fallback response used due to error")
            logger.info(f"Error: {turn.metadata.get('error', 'Unknown error')}")
    
    # Show error metrics
    metrics = dialogue_manager.get_conversation_metrics()
    logger.info(f"\n--- Error Metrics ---")
    logger.info(f"Total errors: {metrics.error_count}")
    logger.info(f"Fallback responses: {metrics.fallback_responses}")


async def demonstrate_service_coordination():
    """Demonstrate service latency tracking and coordination."""
    logger.info("\n\n=== Service Coordination Demo ===")
    
    # Create mock components
    llm_client = create_mock_llm_client()
    state_machine = MagicMock(spec=ConversationStateMachine)
    
    # Create DialogueManager
    dialogue_manager = DialogueManager(
        conversation_id="demo_services",
        llm_client=llm_client,
        state_machine=state_machine,
        system_prompt="You are demonstrating service coordination."
    )
    
    # Simulate service latencies
    dialogue_manager.update_service_latency("stt", 0.15)  # Speech-to-text
    dialogue_manager.update_service_latency("llm", 0.45)  # Language model
    dialogue_manager.update_service_latency("tts", 0.25)  # Text-to-speech
    
    # Process a message
    response, turn = await dialogue_manager.process_user_input(
        "How are the different services performing?"
    )
    
    logger.info(f"User: How are the different services performing?")
    logger.info(f"Assistant: {response}")
    
    # Show service metrics
    metrics = dialogue_manager.get_conversation_metrics()
    logger.info(f"\n--- Service Latencies ---")
    logger.info(f"STT latency: {metrics.stt_latency:.3f}s")
    logger.info(f"LLM latency: {metrics.llm_latency:.3f}s")
    logger.info(f"TTS latency: {metrics.tts_latency:.3f}s")
    
    # Simulate interruption
    dialogue_manager.record_interruption()
    dialogue_manager.record_interruption()
    
    logger.info(f"Interruptions recorded: {metrics.interruption_count}")


async def main():
    """Run all demonstration scenarios."""
    logger.info("🎯 DialogueManager Demonstration")
    logger.info("=" * 50)
    
    try:
        # Run all demonstrations
        await demonstrate_basic_conversation()
        await demonstrate_context_management()
        await demonstrate_error_handling()
        await demonstrate_service_coordination()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All demonstrations completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())
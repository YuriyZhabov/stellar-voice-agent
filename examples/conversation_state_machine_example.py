#!/usr/bin/env python3
"""
Example usage of the Conversation State Machine.

This example demonstrates how to use the ConversationStateMachine
for managing conversation states in a voice AI agent.
"""

import asyncio
import logging
from datetime import datetime, UTC

from src.conversation.state_machine import (
    ConversationState,
    ConversationStateMachine,
    StateTransition
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def conversation_handler(state: ConversationState, transition: StateTransition):
    """Example state handler that logs state changes."""
    logger.info(f"Entered {state.value} state from {transition.from_state.value}")
    
    if state == ConversationState.LISTENING:
        logger.info("🎤 Ready to listen for user input...")
    elif state == ConversationState.PROCESSING:
        logger.info("🧠 Processing user input and generating response...")
    elif state == ConversationState.SPEAKING:
        logger.info("🗣️  Speaking response to user...")


async def transition_logger(transition: StateTransition):
    """Example transition callback that logs all transitions."""
    logger.info(
        f"Transition: {transition.from_state.value} -> {transition.to_state.value} "
        f"(trigger: {transition.trigger})"
    )


async def simulate_conversation_flow():
    """Simulate a complete conversation flow."""
    logger.info("=== Starting Conversation Flow Simulation ===")
    
    # Create state machine
    fsm = ConversationStateMachine()
    
    # Add handlers and callbacks
    fsm.add_state_handler(ConversationState.LISTENING, conversation_handler)
    fsm.add_state_handler(ConversationState.PROCESSING, conversation_handler)
    fsm.add_state_handler(ConversationState.SPEAKING, conversation_handler)
    fsm.add_transition_callback(transition_logger)
    
    logger.info(f"Initial state: {fsm.current_state.value}")
    
    # Simulate conversation cycle
    logger.info("\n--- Simulating user speaking ---")
    await fsm.transition_to(ConversationState.PROCESSING, "user_speech_detected")
    await asyncio.sleep(0.5)  # Simulate processing time
    
    logger.info("\n--- Simulating response generation ---")
    await fsm.transition_to(ConversationState.SPEAKING, "llm_response_ready")
    await asyncio.sleep(1.0)  # Simulate speaking time
    
    logger.info("\n--- Returning to listening ---")
    await fsm.transition_to(ConversationState.LISTENING, "speech_complete")
    
    # Show metrics
    logger.info("\n=== Conversation Metrics ===")
    summary = fsm.get_state_summary()
    for key, value in summary.items():
        logger.info(f"{key}: {value}")
    
    return fsm


async def simulate_error_recovery():
    """Simulate error recovery scenarios."""
    logger.info("\n=== Error Recovery Simulation ===")
    
    fsm = ConversationStateMachine()
    fsm.add_transition_callback(transition_logger)
    
    # Simulate normal flow
    await fsm.transition_to(ConversationState.PROCESSING, "user_input")
    
    # Simulate error requiring force transition
    logger.info("\n--- Simulating error recovery ---")
    await fsm.force_transition(ConversationState.LISTENING, "error_recovery")
    
    logger.info(f"Recovered to state: {fsm.current_state.value}")
    
    return fsm


async def demonstrate_temporary_states():
    """Demonstrate temporary state transitions."""
    logger.info("\n=== Temporary State Demonstration ===")
    
    fsm = ConversationStateMachine()
    fsm.add_transition_callback(transition_logger)
    
    logger.info(f"Starting state: {fsm.current_state.value}")
    
    # Use temporary state context manager
    async with fsm.temporary_state(ConversationState.PROCESSING, "temporary_processing"):
        logger.info(f"Inside temporary state: {fsm.current_state.value}")
        await asyncio.sleep(0.1)
    
    logger.info(f"Returned to state: {fsm.current_state.value}")
    
    return fsm


async def demonstrate_concurrent_safety():
    """Demonstrate thread safety with concurrent transitions."""
    logger.info("\n=== Concurrent Safety Demonstration ===")
    
    fsm = ConversationStateMachine()
    fsm.add_transition_callback(transition_logger)
    
    # Create multiple concurrent transition attempts
    tasks = []
    for i in range(5):
        task = fsm.transition_to(ConversationState.PROCESSING, f"concurrent_attempt_{i}")
        tasks.append(task)
    
    # Wait for all attempts
    results = await asyncio.gather(*tasks)
    
    logger.info(f"All transition results: {results}")
    logger.info(f"Final state: {fsm.current_state.value}")
    logger.info(f"Total transitions: {fsm.metrics.total_transitions}")
    
    return fsm


async def demonstrate_conversation_analytics():
    """Demonstrate conversation analytics and metrics."""
    logger.info("\n=== Conversation Analytics Demonstration ===")
    
    fsm = ConversationStateMachine()
    
    # Simulate multiple conversation cycles
    for cycle in range(3):
        logger.info(f"\n--- Conversation Cycle {cycle + 1} ---")
        
        await fsm.transition_to(ConversationState.PROCESSING, f"cycle_{cycle}_input")
        await asyncio.sleep(0.2)  # Simulate processing
        
        await fsm.transition_to(ConversationState.SPEAKING, f"cycle_{cycle}_response")
        await asyncio.sleep(0.3)  # Simulate speaking
        
        await fsm.transition_to(ConversationState.LISTENING, f"cycle_{cycle}_complete")
        await asyncio.sleep(0.1)  # Brief pause
    
    # Show detailed analytics
    logger.info("\n=== Detailed Analytics ===")
    summary = fsm.get_state_summary()
    
    logger.info(f"Total transitions: {summary['total_transitions']}")
    logger.info(f"Invalid transitions: {summary['invalid_transitions']}")
    logger.info("State durations:")
    for state, duration in summary['state_durations'].items():
        logger.info(f"  {state}: {duration:.3f} seconds")
    
    # Show transition history
    logger.info("\nTransition History:")
    history = fsm.get_transition_history(limit=5)  # Last 5 transitions
    for i, transition in enumerate(history, 1):
        logger.info(
            f"  {i}. {transition.from_state.value} -> {transition.to_state.value} "
            f"({transition.trigger})"
        )
    
    return fsm


async def main():
    """Main example function."""
    logger.info("🤖 Conversation State Machine Examples")
    logger.info("=" * 50)
    
    try:
        # Run all demonstrations
        await simulate_conversation_flow()
        await simulate_error_recovery()
        await demonstrate_temporary_states()
        await demonstrate_concurrent_safety()
        await demonstrate_conversation_analytics()
        
        logger.info("\n✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
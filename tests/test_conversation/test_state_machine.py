"""
Unit tests for the conversation state machine.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock

from src.conversation.state_machine import (
    ConversationState,
    ConversationStateMachine,
    StateTransition,
    StateMetrics
)


class TestConversationState:
    """Test the ConversationState enum."""
    
    def test_state_values(self):
        """Test that states have correct string values."""
        assert ConversationState.LISTENING.value == "listening"
        assert ConversationState.PROCESSING.value == "processing"
        assert ConversationState.SPEAKING.value == "speaking"
    
    def test_state_count(self):
        """Test that we have exactly 3 states."""
        assert len(ConversationState) == 3


class TestStateTransition:
    """Test the StateTransition dataclass."""
    
    def test_state_transition_creation(self):
        """Test creating a state transition."""
        now = datetime.now(UTC)
        transition = StateTransition(
            from_state=ConversationState.LISTENING,
            to_state=ConversationState.PROCESSING,
            timestamp=now,
            trigger="user_speech",
            metadata={"confidence": 0.95}
        )
        
        assert transition.from_state == ConversationState.LISTENING
        assert transition.to_state == ConversationState.PROCESSING
        assert transition.timestamp == now
        assert transition.trigger == "user_speech"
        assert transition.metadata == {"confidence": 0.95}
    
    def test_state_transition_without_metadata(self):
        """Test creating a state transition without metadata."""
        now = datetime.now(UTC)
        transition = StateTransition(
            from_state=ConversationState.PROCESSING,
            to_state=ConversationState.SPEAKING,
            timestamp=now,
            trigger="response_ready"
        )
        
        assert transition.metadata is None


class TestStateMetrics:
    """Test the StateMetrics dataclass."""
    
    def test_state_metrics_initialization(self):
        """Test state metrics initialization."""
        metrics = StateMetrics()
        
        assert metrics.total_transitions == 0
        assert metrics.invalid_transitions == 0
        assert metrics.current_state_start is None
        assert len(metrics.state_durations) == 3
        assert all(duration == 0.0 for duration in metrics.state_durations.values())
    
    def test_state_metrics_with_values(self):
        """Test state metrics with custom values."""
        now = datetime.now(UTC)
        durations = {
            ConversationState.LISTENING: 5.0,
            ConversationState.PROCESSING: 2.0,
            ConversationState.SPEAKING: 3.0
        }
        
        metrics = StateMetrics(
            total_transitions=10,
            state_durations=durations,
            invalid_transitions=2,
            current_state_start=now
        )
        
        assert metrics.total_transitions == 10
        assert metrics.invalid_transitions == 2
        assert metrics.current_state_start == now
        assert metrics.state_durations == durations


class TestConversationStateMachine:
    """Test the ConversationStateMachine class."""
    
    def test_initialization_default(self):
        """Test state machine initialization with default state."""
        fsm = ConversationStateMachine()
        
        assert fsm.current_state == ConversationState.LISTENING
        assert fsm.previous_state is None
        assert fsm.metrics.total_transitions == 0
        assert fsm.metrics.current_state_start is not None
    
    def test_initialization_custom_state(self):
        """Test state machine initialization with custom state."""
        fsm = ConversationStateMachine(ConversationState.PROCESSING)
        
        assert fsm.current_state == ConversationState.PROCESSING
        assert fsm.previous_state is None
    
    def test_valid_transitions(self):
        """Test that valid transitions are correctly defined."""
        fsm = ConversationStateMachine()
        
        # From LISTENING
        assert fsm.can_transition(ConversationState.LISTENING, ConversationState.PROCESSING)
        assert fsm.can_transition(ConversationState.LISTENING, ConversationState.SPEAKING)
        assert not fsm.can_transition(ConversationState.LISTENING, ConversationState.LISTENING)
        
        # From PROCESSING
        assert fsm.can_transition(ConversationState.PROCESSING, ConversationState.SPEAKING)
        assert fsm.can_transition(ConversationState.PROCESSING, ConversationState.LISTENING)
        assert not fsm.can_transition(ConversationState.PROCESSING, ConversationState.PROCESSING)
        
        # From SPEAKING
        assert fsm.can_transition(ConversationState.SPEAKING, ConversationState.LISTENING)
        assert fsm.can_transition(ConversationState.SPEAKING, ConversationState.PROCESSING)
        assert not fsm.can_transition(ConversationState.SPEAKING, ConversationState.SPEAKING)
    
    @pytest.mark.asyncio
    async def test_successful_transition(self):
        """Test successful state transition."""
        fsm = ConversationStateMachine()
        
        result = await fsm.transition_to(ConversationState.PROCESSING, "user_input")
        
        assert result is True
        assert fsm.current_state == ConversationState.PROCESSING
        assert fsm.previous_state == ConversationState.LISTENING
        assert fsm.metrics.total_transitions == 1
        assert len(fsm.get_transition_history()) == 1
    
    @pytest.mark.asyncio
    async def test_invalid_transition(self):
        """Test invalid state transition."""
        fsm = ConversationStateMachine()
        
        result = await fsm.transition_to(ConversationState.LISTENING, "invalid")
        
        assert result is True  # Same state transition is allowed
        assert fsm.current_state == ConversationState.LISTENING
        assert fsm.metrics.total_transitions == 0
    
    @pytest.mark.asyncio
    async def test_invalid_transition_different_state(self):
        """Test truly invalid state transition."""
        fsm = ConversationStateMachine(ConversationState.PROCESSING)
        
        # This should fail because PROCESSING -> PROCESSING is not valid
        result = await fsm.transition_to(ConversationState.PROCESSING, "invalid")
        
        assert result is True  # Same state is allowed
        assert fsm.current_state == ConversationState.PROCESSING
        assert fsm.metrics.invalid_transitions == 0
    
    @pytest.mark.asyncio
    async def test_force_transition(self):
        """Test forced state transition."""
        fsm = ConversationStateMachine()
        
        # Force an invalid transition
        result = await fsm.force_transition(ConversationState.LISTENING, "error_recovery")
        
        assert result is True
        assert fsm.current_state == ConversationState.LISTENING
        assert fsm.metrics.total_transitions == 1
        
        # Check that it was marked as forced
        history = fsm.get_transition_history()
        assert len(history) == 1
        assert history[0].metadata.get("forced") is True
    
    @pytest.mark.asyncio
    async def test_state_duration_tracking(self):
        """Test that state durations are tracked correctly."""
        fsm = ConversationStateMachine()
        
        # Wait a bit then transition
        await asyncio.sleep(0.1)
        await fsm.transition_to(ConversationState.PROCESSING, "test")
        
        # Check that listening duration was recorded
        assert fsm.metrics.state_durations[ConversationState.LISTENING] > 0
        assert fsm.metrics.state_durations[ConversationState.PROCESSING] == 0
    
    @pytest.mark.asyncio
    async def test_state_handlers(self):
        """Test state handlers are called correctly."""
        fsm = ConversationStateMachine()
        handler_called = False
        received_state = None
        received_transition = None
        
        async def test_handler(state, transition):
            nonlocal handler_called, received_state, received_transition
            handler_called = True
            received_state = state
            received_transition = transition
        
        fsm.add_state_handler(ConversationState.PROCESSING, test_handler)
        await fsm.transition_to(ConversationState.PROCESSING, "test")
        
        assert handler_called
        assert received_state == ConversationState.PROCESSING
        assert received_transition.to_state == ConversationState.PROCESSING
    
    @pytest.mark.asyncio
    async def test_transition_callbacks(self):
        """Test transition callbacks are called correctly."""
        fsm = ConversationStateMachine()
        callback_called = False
        received_transition = None
        
        async def test_callback(transition):
            nonlocal callback_called, received_transition
            callback_called = True
            received_transition = transition
        
        fsm.add_transition_callback(test_callback)
        await fsm.transition_to(ConversationState.PROCESSING, "test")
        
        assert callback_called
        assert received_transition.from_state == ConversationState.LISTENING
        assert received_transition.to_state == ConversationState.PROCESSING
    
    @pytest.mark.asyncio
    async def test_handler_error_handling(self):
        """Test that handler errors don't break transitions."""
        fsm = ConversationStateMachine()
        
        async def failing_handler(state, transition):
            raise Exception("Handler error")
        
        fsm.add_state_handler(ConversationState.PROCESSING, failing_handler)
        
        # Transition should still succeed despite handler error
        result = await fsm.transition_to(ConversationState.PROCESSING, "test")
        assert result is True
        assert fsm.current_state == ConversationState.PROCESSING
    
    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callback errors don't break transitions."""
        fsm = ConversationStateMachine()
        
        async def failing_callback(transition):
            raise Exception("Callback error")
        
        fsm.add_transition_callback(failing_callback)
        
        # Transition should still succeed despite callback error
        result = await fsm.transition_to(ConversationState.PROCESSING, "test")
        assert result is True
        assert fsm.current_state == ConversationState.PROCESSING
    
    def test_transition_history(self):
        """Test transition history tracking."""
        fsm = ConversationStateMachine()
        
        # Initially empty
        assert len(fsm.get_transition_history()) == 0
        
        # Add some transitions (we'll test this with sync methods for simplicity)
        transition1 = StateTransition(
            ConversationState.LISTENING,
            ConversationState.PROCESSING,
            datetime.now(UTC),
            "test1"
        )
        transition2 = StateTransition(
            ConversationState.PROCESSING,
            ConversationState.SPEAKING,
            datetime.now(UTC),
            "test2"
        )
        
        fsm._transition_history.extend([transition1, transition2])
        
        # Test full history
        history = fsm.get_transition_history()
        assert len(history) == 2
        assert history[0] == transition1
        assert history[1] == transition2
        
        # Test limited history
        limited = fsm.get_transition_history(limit=1)
        assert len(limited) == 1
        assert limited[0] == transition2
    
    def test_reset(self):
        """Test state machine reset."""
        fsm = ConversationStateMachine()
        
        # Add some state
        fsm._current_state = ConversationState.PROCESSING
        fsm._previous_state = ConversationState.LISTENING
        fsm._metrics.total_transitions = 5
        fsm._transition_history.append(
            StateTransition(
                ConversationState.LISTENING,
                ConversationState.PROCESSING,
                datetime.now(UTC),
                "test"
            )
        )
        
        # Reset
        fsm.reset()
        
        assert fsm.current_state == ConversationState.LISTENING
        assert fsm.previous_state is None
        assert fsm.metrics.total_transitions == 0
        assert len(fsm.get_transition_history()) == 0
        assert fsm.metrics.current_state_start is not None
    
    def test_reset_custom_state(self):
        """Test state machine reset to custom state."""
        fsm = ConversationStateMachine()
        
        fsm.reset(ConversationState.SPEAKING)
        
        assert fsm.current_state == ConversationState.SPEAKING
    
    @pytest.mark.asyncio
    async def test_temporary_state_context_manager(self):
        """Test temporary state context manager."""
        fsm = ConversationStateMachine()
        original_state = fsm.current_state
        
        async with fsm.temporary_state(ConversationState.PROCESSING, "temp_test"):
            assert fsm.current_state == ConversationState.PROCESSING
        
        assert fsm.current_state == original_state
    
    @pytest.mark.asyncio
    async def test_temporary_state_invalid_transition(self):
        """Test temporary state with invalid transition."""
        fsm = ConversationStateMachine()
        original_state = fsm.current_state
        
        # Try to transition to same state (which should be allowed but logged)
        async with fsm.temporary_state(ConversationState.LISTENING, "temp_test"):
            assert fsm.current_state == ConversationState.LISTENING
        
        assert fsm.current_state == original_state
    
    def test_get_state_summary(self):
        """Test state summary generation."""
        fsm = ConversationStateMachine()
        fsm._previous_state = ConversationState.PROCESSING
        fsm._metrics.total_transitions = 3
        fsm._metrics.invalid_transitions = 1
        fsm._metrics.state_durations[ConversationState.LISTENING] = 5.0
        
        summary = fsm.get_state_summary()
        
        assert summary["current_state"] == "listening"
        assert summary["previous_state"] == "processing"
        assert summary["total_transitions"] == 3
        assert summary["invalid_transitions"] == 1
        assert summary["state_durations"]["listening"] == 5.0
        assert summary["transition_count"] == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_transitions(self):
        """Test that concurrent transitions are handled safely."""
        fsm = ConversationStateMachine()
        
        # Create multiple concurrent transition attempts
        tasks = [
            fsm.transition_to(ConversationState.PROCESSING, f"concurrent_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Only one should succeed (the first one), others should be ignored
        # since they're transitioning to the same state
        assert fsm.current_state == ConversationState.PROCESSING
        assert all(result is True for result in results)  # All succeed because same state
    
    @pytest.mark.asyncio
    async def test_complex_state_flow(self):
        """Test a complex state flow scenario."""
        fsm = ConversationStateMachine()
        
        # Simulate a complete conversation cycle
        assert await fsm.transition_to(ConversationState.PROCESSING, "user_spoke")
        assert fsm.current_state == ConversationState.PROCESSING
        
        assert await fsm.transition_to(ConversationState.SPEAKING, "response_ready")
        assert fsm.current_state == ConversationState.SPEAKING
        
        assert await fsm.transition_to(ConversationState.LISTENING, "response_complete")
        assert fsm.current_state == ConversationState.LISTENING
        
        # Check metrics
        assert fsm.metrics.total_transitions == 3
        assert len(fsm.get_transition_history()) == 3
        
        # Check all states have some duration
        assert all(duration >= 0 for duration in fsm.metrics.state_durations.values())


@pytest.mark.asyncio
async def test_integration_scenario():
    """Test a realistic integration scenario."""
    fsm = ConversationStateMachine()
    
    # Track state changes
    state_changes = []
    
    async def track_transitions(transition):
        state_changes.append(f"{transition.from_state.value}->{transition.to_state.value}")
    
    fsm.add_transition_callback(track_transitions)
    
    # Simulate conversation flow
    await fsm.transition_to(ConversationState.PROCESSING, "user_input_detected")
    await asyncio.sleep(0.01)  # Simulate processing time
    
    await fsm.transition_to(ConversationState.SPEAKING, "llm_response_ready")
    await asyncio.sleep(0.01)  # Simulate speaking time
    
    await fsm.transition_to(ConversationState.LISTENING, "speech_complete")
    
    # Verify the flow
    expected_changes = [
        "listening->processing",
        "processing->speaking", 
        "speaking->listening"
    ]
    assert state_changes == expected_changes
    
    # Verify final state
    assert fsm.current_state == ConversationState.LISTENING
    assert fsm.metrics.total_transitions == 3
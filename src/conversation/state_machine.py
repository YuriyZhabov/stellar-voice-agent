"""
Finite State Machine for conversation management.

This module implements a finite state machine that manages conversation states
and ensures proper state transitions during voice interactions.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, UTC
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Enumeration of possible conversation states."""
    
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class StateTransition:
    """Represents a state transition with metadata."""
    
    from_state: ConversationState
    to_state: ConversationState
    timestamp: datetime
    trigger: str
    metadata: Optional[Dict] = None


@dataclass
class StateMetrics:
    """Metrics for state machine monitoring."""
    
    total_transitions: int = 0
    state_durations: Dict[ConversationState, float] = None
    invalid_transitions: int = 0
    current_state_start: Optional[datetime] = None
    
    def __post_init__(self):
        if self.state_durations is None:
            self.state_durations = {state: 0.0 for state in ConversationState}


class ConversationStateMachine:
    """
    Finite state machine for managing conversation states.
    
    Manages transitions between LISTENING, PROCESSING, and SPEAKING states
    with validation, logging, and metrics collection.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS: Dict[ConversationState, Set[ConversationState]] = {
        ConversationState.LISTENING: {
            ConversationState.PROCESSING,
            ConversationState.SPEAKING  # Direct transition for interruptions
        },
        ConversationState.PROCESSING: {
            ConversationState.SPEAKING,
            ConversationState.LISTENING  # Error recovery
        },
        ConversationState.SPEAKING: {
            ConversationState.LISTENING,
            ConversationState.PROCESSING  # Interruption handling
        }
    }
    
    def __init__(self, initial_state: ConversationState = ConversationState.LISTENING):
        """
        Initialize the state machine.
        
        Args:
            initial_state: The initial state of the conversation
        """
        self._current_state = initial_state
        self._previous_state: Optional[ConversationState] = None
        self._transition_history: List[StateTransition] = []
        self._metrics = StateMetrics()
        self._state_handlers: Dict[ConversationState, List] = {
            state: [] for state in ConversationState
        }
        self._transition_callbacks: List = []
        self._lock = asyncio.Lock()
        
        # Initialize metrics
        self._metrics.current_state_start = datetime.now(UTC)
        
        logger.info(f"State machine initialized with state: {initial_state.value}")
    
    @property
    def current_state(self) -> ConversationState:
        """Get the current state."""
        return self._current_state
    
    @property
    def previous_state(self) -> Optional[ConversationState]:
        """Get the previous state."""
        return self._previous_state
    
    @property
    def metrics(self) -> StateMetrics:
        """Get state machine metrics."""
        return self._metrics
    
    def can_transition(self, from_state: ConversationState, to_state: ConversationState) -> bool:
        """
        Check if a state transition is valid.
        
        Args:
            from_state: The source state
            to_state: The target state
            
        Returns:
            True if the transition is valid, False otherwise
        """
        return to_state in self.VALID_TRANSITIONS.get(from_state, set())
    
    async def transition_to(self, new_state: ConversationState, trigger: str = "manual", 
                           metadata: Optional[Dict] = None) -> bool:
        """
        Transition to a new state with validation and logging.
        
        Args:
            new_state: The target state
            trigger: Description of what triggered the transition
            metadata: Additional metadata for the transition
            
        Returns:
            True if transition was successful, False otherwise
        """
        async with self._lock:
            if new_state == self._current_state:
                logger.debug(f"Already in state {new_state.value}, ignoring transition")
                return True
            
            if not self.can_transition(self._current_state, new_state):
                logger.warning(
                    f"Invalid transition from {self._current_state.value} to {new_state.value}"
                )
                self._metrics.invalid_transitions += 1
                return False
            
            # Record state duration
            now = datetime.now(UTC)
            if self._metrics.current_state_start:
                duration = (now - self._metrics.current_state_start).total_seconds()
                self._metrics.state_durations[self._current_state] += duration
            
            # Create transition record
            transition = StateTransition(
                from_state=self._current_state,
                to_state=new_state,
                timestamp=now,
                trigger=trigger,
                metadata=metadata or {}
            )
            
            # Update state
            self._previous_state = self._current_state
            self._current_state = new_state
            self._transition_history.append(transition)
            self._metrics.total_transitions += 1
            self._metrics.current_state_start = now
            
            logger.info(
                f"State transition: {self._previous_state.value} -> {new_state.value} "
                f"(trigger: {trigger})"
            )
            
            # Execute state handlers and callbacks
            await self._execute_state_handlers(new_state, transition)
            await self._execute_transition_callbacks(transition)
            
            return True
    
    async def force_transition(self, new_state: ConversationState, trigger: str = "forced",
                              metadata: Optional[Dict] = None) -> bool:
        """
        Force a transition to a new state, bypassing validation.
        
        This should only be used for error recovery scenarios.
        
        Args:
            new_state: The target state
            trigger: Description of what triggered the transition
            metadata: Additional metadata for the transition
            
        Returns:
            True if transition was successful
        """
        async with self._lock:
            logger.warning(
                f"Forcing transition from {self._current_state.value} to {new_state.value} "
                f"(trigger: {trigger})"
            )
            
            # Record state duration
            now = datetime.now(UTC)
            if self._metrics.current_state_start:
                duration = (now - self._metrics.current_state_start).total_seconds()
                self._metrics.state_durations[self._current_state] += duration
            
            # Create transition record
            transition = StateTransition(
                from_state=self._current_state,
                to_state=new_state,
                timestamp=now,
                trigger=trigger,
                metadata=(metadata or {}) | {"forced": True}
            )
            
            # Update state
            self._previous_state = self._current_state
            self._current_state = new_state
            self._transition_history.append(transition)
            self._metrics.total_transitions += 1
            self._metrics.current_state_start = now
            
            # Execute state handlers and callbacks
            await self._execute_state_handlers(new_state, transition)
            await self._execute_transition_callbacks(transition)
            
            return True
    
    def add_state_handler(self, state: ConversationState, handler):
        """
        Add a handler to be called when entering a specific state.
        
        Args:
            state: The state to handle
            handler: Async callable to execute when entering the state
        """
        self._state_handlers[state].append(handler)
        logger.debug(f"Added state handler for {state.value}")
    
    def add_transition_callback(self, callback):
        """
        Add a callback to be called on any state transition.
        
        Args:
            callback: Async callable to execute on transitions
        """
        self._transition_callbacks.append(callback)
        logger.debug("Added transition callback")
    
    async def _execute_state_handlers(self, state: ConversationState, transition: StateTransition):
        """Execute all handlers for the given state."""
        for handler in self._state_handlers[state]:
            try:
                await handler(state, transition)
            except Exception as e:
                logger.error(f"Error executing state handler for {state.value}: {e}")
    
    async def _execute_transition_callbacks(self, transition: StateTransition):
        """Execute all transition callbacks."""
        for callback in self._transition_callbacks:
            try:
                await callback(transition)
            except Exception as e:
                logger.error(f"Error executing transition callback: {e}")
    
    def get_transition_history(self, limit: Optional[int] = None) -> List[StateTransition]:
        """
        Get the transition history.
        
        Args:
            limit: Maximum number of transitions to return
            
        Returns:
            List of state transitions
        """
        if limit is None:
            return self._transition_history.copy()
        return self._transition_history[-limit:]
    
    def reset(self, initial_state: ConversationState = ConversationState.LISTENING):
        """
        Reset the state machine to initial state.
        
        Args:
            initial_state: The state to reset to
        """
        logger.info(f"Resetting state machine to {initial_state.value}")
        
        # Record final state duration
        if self._metrics.current_state_start:
            duration = (datetime.now(UTC) - self._metrics.current_state_start).total_seconds()
            self._metrics.state_durations[self._current_state] += duration
        
        self._current_state = initial_state
        self._previous_state = None
        self._transition_history.clear()
        self._metrics = StateMetrics()
        self._metrics.current_state_start = datetime.now(UTC)
    
    @asynccontextmanager
    async def temporary_state(self, temp_state: ConversationState, trigger: str = "temporary"):
        """
        Context manager for temporary state transitions.
        
        Args:
            temp_state: Temporary state to transition to
            trigger: Description of the temporary transition
        """
        original_state = self._current_state
        
        if await self.transition_to(temp_state, trigger):
            try:
                yield
            finally:
                await self.transition_to(original_state, f"return_from_{trigger}")
        else:
            # If transition failed, still yield but log the issue
            logger.warning(f"Failed to transition to temporary state {temp_state.value}")
            yield
    
    def get_state_summary(self) -> Dict:
        """
        Get a summary of the current state machine status.
        
        Returns:
            Dictionary with state machine summary
        """
        return {
            "current_state": self._current_state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "total_transitions": self._metrics.total_transitions,
            "invalid_transitions": self._metrics.invalid_transitions,
            "state_durations": {
                state.value: duration 
                for state, duration in self._metrics.state_durations.items()
            },
            "transition_count": len(self._transition_history)
        }
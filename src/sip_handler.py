"""
SIP Handler for LiveKit Integration

This module provides SIP call handling functionality that integrates with LiveKit
for voice AI processing. It manages SIP trunk connections, call routing, and
integration with the Voice AI Agent system.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
from uuid import uuid4

import yaml

from src.orchestrator import CallOrchestrator, CallContext
from src.livekit_integration import LiveKitSIPIntegration, SIPTrunkConfig
from src.voice_ai_agent import VoiceAIAgent, create_voice_ai_agent, AudioStreamConfig
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager
from src.config import get_settings
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class SIPCallStatus(Enum):
    """SIP call status enumeration."""
    INCOMING = "incoming"
    RINGING = "ringing"
    ANSWERED = "answered"
    ACTIVE = "active"
    TRANSFERRING = "transferring"
    HOLDING = "holding"
    ENDING = "ending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SIPCallDirection(Enum):
    """SIP call direction enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass
class SIPCallInfo:
    """Information about a SIP call."""
    call_id: str
    direction: SIPCallDirection
    caller_number: str
    called_number: str
    trunk_name: str
    status: SIPCallStatus
    start_time: datetime
    answer_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    livekit_room: Optional[str] = None
    voice_ai_agent_id: Optional[str] = None
    sip_headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "call_id": self.call_id,
            "direction": self.direction.value,
            "caller_number": self.caller_number,
            "called_number": self.called_number,
            "trunk_name": self.trunk_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "answer_time": self.answer_time.isoformat() if self.answer_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "livekit_room": self.livekit_room,
            "voice_ai_agent_id": self.voice_ai_agent_id,
            "sip_headers": self.sip_headers,
            "metadata": self.metadata
        }


@dataclass
class SIPHandlerMetrics:
    """Metrics for SIP handler performance."""
    total_calls: int = 0
    active_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    cancelled_calls: int = 0
    average_call_duration: float = 0.0
    voice_ai_calls: int = 0
    trunk_failures: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_calls": self.total_calls,
            "active_calls": self.active_calls,
            "completed_calls": self.completed_calls,
            "failed_calls": self.failed_calls,
            "cancelled_calls": self.cancelled_calls,
            "average_call_duration": self.average_call_duration,
            "voice_ai_calls": self.voice_ai_calls,
            "trunk_failures": self.trunk_failures
        }


class SIPHandler:
    """
    SIP Handler for LiveKit Voice AI integration.
    
    This handler manages SIP calls and integrates them with LiveKit rooms
    for voice AI processing. It handles call routing, trunk management,
    and Voice AI Agent coordination.
    """
    
    def __init__(
        self,
        orchestrator: CallOrchestrator,
        livekit_integration: LiveKitSIPIntegration,
        api_client: LiveKitAPIClient,
        auth_manager: LiveKitAuthManager,
        config_path: str = "livekit-sip-correct.yaml"
    ):
        """
        Initialize SIP Handler.
        
        Args:
            orchestrator: Call orchestrator instance
            livekit_integration: LiveKit SIP integration
            api_client: LiveKit API client
            auth_manager: LiveKit auth manager
            config_path: Path to SIP configuration file
        """
        self.orchestrator = orchestrator
        self.livekit_integration = livekit_integration
        self.api_client = api_client
        self.auth_manager = auth_manager
        self.config_path = config_path
        
        self.settings = get_settings()
        self.metrics_collector = get_metrics_collector()
        
        # SIP configuration
        self.sip_config: Dict[str, Any] = {}
        self.sip_trunks: Dict[str, SIPTrunkConfig] = {}
        self.routing_rules: List[Dict[str, Any]] = []
        
        # Call management
        self.active_calls: Dict[str, SIPCallInfo] = {}
        self.voice_ai_agents: Dict[str, VoiceAIAgent] = {}
        self.call_routing_handlers: List[Callable] = []
        
        # Metrics
        self.metrics = SIPHandlerMetrics()
        
        # Event handlers
        self.call_event_handlers: Dict[str, List[Callable]] = {
            'call_incoming': [],
            'call_answered': [],
            'call_ended': [],
            'call_failed': []
        }
        
        logger.info("SIP Handler initialized")
    
    async def initialize(self) -> None:
        """Initialize the SIP handler."""
        try:
            # Load SIP configuration
            await self._load_sip_configuration()
            
            # Initialize SIP trunks
            await self._initialize_sip_trunks()
            
            # Setup call routing
            await self._setup_call_routing()
            
            logger.info("SIP Handler initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize SIP Handler: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the SIP handler."""
        try:
            logger.info("Shutting down SIP Handler")
            
            # End all active calls
            for call_id in list(self.active_calls.keys()):
                await self.end_call(call_id, "shutdown")
            
            # Clean up Voice AI agents
            for agent_id, agent in self.voice_ai_agents.items():
                try:
                    await agent.leave_room()
                except Exception as e:
                    logger.error(f"Error cleaning up agent {agent_id}: {e}")
            
            self.voice_ai_agents.clear()
            
            logger.info("SIP Handler shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during SIP Handler shutdown: {e}")
    
    async def _load_sip_configuration(self) -> None:
        """Load SIP configuration from file."""
        try:
            with open(self.config_path, 'r') as file:
                config_content = file.read()
            
            # Replace environment variables
            config_content = self._substitute_env_variables(config_content)
            
            # Parse YAML
            self.sip_config = yaml.safe_load(config_content)
            
            # Extract routing rules
            self.routing_rules = self.sip_config.get('routing_rules', [])
            
            logger.info(f"Loaded SIP configuration with {len(self.routing_rules)} routing rules")
            
        except Exception as e:
            logger.error(f"Failed to load SIP configuration: {e}")
            raise
    
    def _substitute_env_variables(self, content: str) -> str:
        """Substitute environment variables in configuration."""
        import os
        import re
        
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                return os.getenv(var_expr, '')
        
        return re.sub(pattern, replace_var, content)
    
    async def _initialize_sip_trunks(self) -> None:
        """Initialize SIP trunks from configuration."""
        try:
            # Get trunks from LiveKit integration
            self.sip_trunks = self.livekit_integration.sip_trunks
            
            logger.info(f"Initialized {len(self.sip_trunks)} SIP trunks")
            
        except Exception as e:
            logger.error(f"Failed to initialize SIP trunks: {e}")
            raise
    
    async def _setup_call_routing(self) -> None:
        """Setup call routing rules."""
        try:
            # Add default Voice AI routing handler
            self.call_routing_handlers.append(self._default_voice_ai_routing)
            
            logger.info("Call routing setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup call routing: {e}")
            raise
    
    async def handle_incoming_call(
        self,
        caller_number: str,
        called_number: str,
        trunk_name: str,
        sip_headers: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Handle incoming SIP call.
        
        Args:
            caller_number: Caller's phone number
            called_number: Called phone number
            trunk_name: SIP trunk name
            sip_headers: SIP headers
            
        Returns:
            Call ID
        """
        try:
            call_id = str(uuid4())
            
            # Create call info
            call_info = SIPCallInfo(
                call_id=call_id,
                direction=SIPCallDirection.INBOUND,
                caller_number=caller_number,
                called_number=called_number,
                trunk_name=trunk_name,
                status=SIPCallStatus.INCOMING,
                start_time=datetime.now(UTC),
                sip_headers=sip_headers or {}
            )
            
            self.active_calls[call_id] = call_info
            self.metrics.total_calls += 1
            self.metrics.active_calls += 1
            
            logger.info(
                f"Incoming call {call_id}: {caller_number} -> {called_number} via {trunk_name}"
            )
            
            # Execute call routing
            routing_result = await self._route_call(call_info)
            
            if routing_result:
                # Answer the call
                await self._answer_call(call_info)
            else:
                # Reject the call
                await self._reject_call(call_info, "No routing available")
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "sip_incoming_calls_total",
                labels={"trunk": trunk_name, "routing": "voice_ai" if routing_result else "rejected"}
            )
            
            # Execute event handlers
            for handler in self.call_event_handlers['call_incoming']:
                try:
                    await handler(call_info)
                except Exception as e:
                    logger.error(f"Error in call incoming handler: {e}")
            
            return call_id
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {e}")
            self.metrics.failed_calls += 1
            raise
    
    async def _route_call(self, call_info: SIPCallInfo) -> bool:
        """
        Route call based on routing rules.
        
        Args:
            call_info: Call information
            
        Returns:
            True if call was routed, False otherwise
        """
        try:
            # Execute routing handlers
            for handler in self.call_routing_handlers:
                try:
                    result = await handler(call_info)
                    if result:
                        return True
                except Exception as e:
                    logger.error(f"Error in routing handler: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error routing call: {e}")
            return False
    
    async def _default_voice_ai_routing(self, call_info: SIPCallInfo) -> bool:
        """
        Default Voice AI routing handler.
        
        Args:
            call_info: Call information
            
        Returns:
            True if call should be routed to Voice AI
        """
        try:
            # Check routing rules
            for rule in self.routing_rules:
                if self._match_routing_rule(call_info, rule):
                    action = rule.get('action', 'voice_ai')
                    
                    if action == 'voice_ai':
                        # Route to Voice AI
                        return await self._setup_voice_ai_call(call_info)
                    elif action == 'reject':
                        return False
                    elif action == 'forward':
                        # Handle forwarding (not implemented in this version)
                        logger.warning(f"Call forwarding not implemented for call {call_info.call_id}")
                        return False
            
            # Default: route to Voice AI
            return await self._setup_voice_ai_call(call_info)
            
        except Exception as e:
            logger.error(f"Error in default Voice AI routing: {e}")
            return False
    
    def _match_routing_rule(self, call_info: SIPCallInfo, rule: Dict[str, Any]) -> bool:
        """Check if call matches routing rule."""
        try:
            # Check caller number pattern
            caller_pattern = rule.get('caller_pattern')
            if caller_pattern and not self._match_pattern(call_info.caller_number, caller_pattern):
                return False
            
            # Check called number pattern
            called_pattern = rule.get('called_pattern')
            if called_pattern and not self._match_pattern(call_info.called_number, called_pattern):
                return False
            
            # Check trunk
            trunk_pattern = rule.get('trunk_pattern')
            if trunk_pattern and not self._match_pattern(call_info.trunk_name, trunk_pattern):
                return False
            
            # Check SIP headers
            header_conditions = rule.get('header_conditions', {})
            for header_name, header_pattern in header_conditions.items():
                header_value = call_info.sip_headers.get(header_name, '')
                if not self._match_pattern(header_value, header_pattern):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching routing rule: {e}")
            return False
    
    def _match_pattern(self, value: str, pattern: str) -> bool:
        """Match value against pattern (supports wildcards)."""
        import re
        
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        return bool(re.match(f'^{regex_pattern}$', value))
    
    async def _setup_voice_ai_call(self, call_info: SIPCallInfo) -> bool:
        """
        Setup Voice AI processing for the call.
        
        Args:
            call_info: Call information
            
        Returns:
            True if setup successful
        """
        try:
            # Create LiveKit room through integration
            call_context = await self.livekit_integration.handle_inbound_call(
                caller_number=call_info.caller_number,
                called_number=call_info.called_number,
                trunk_name=call_info.trunk_name,
                custom_headers=call_info.sip_headers
            )
            
            # Update call info with enhanced metadata
            call_info.livekit_room = call_context.livekit_room
            call_info.metadata.update(call_context.metadata)
            call_info.metadata.update({
                'sip_integration_version': '2.0',
                'enhanced_processing': True,
                'call_setup_timestamp': datetime.now(UTC).isoformat()
            })
            
            # Create Voice AI agent with enhanced configuration
            audio_config = AudioStreamConfig(
                sample_rate=16000,
                channels=1,
                format="pcm",
                enable_echo_cancellation=True,
                enable_noise_suppression=True,
                enable_auto_gain_control=True,
                buffer_size=2048  # Larger buffer for better quality
            )
            
            agent = await create_voice_ai_agent(
                orchestrator=self.orchestrator,
                api_client=self.api_client,
                auth_manager=self.auth_manager,
                audio_config=audio_config
            )
            
            # Join agent to room with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    success = await agent.join_room(call_context.livekit_room, call_context)
                    if success:
                        break
                    else:
                        logger.warning(f"Agent join attempt {attempt + 1} failed for call {call_info.call_id}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)  # Wait before retry
                except Exception as e:
                    logger.warning(f"Agent join attempt {attempt + 1} error: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                    else:
                        raise
            else:
                logger.error(f"All agent join attempts failed for call {call_info.call_id}")
                return False
            
            # Store agent and update metrics
            call_info.voice_ai_agent_id = agent.agent_id
            self.voice_ai_agents[agent.agent_id] = agent
            self.metrics.voice_ai_calls += 1
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "sip_voice_ai_calls_setup_total",
                labels={"trunk": call_info.trunk_name, "success": "true"}
            )
            
            logger.info(
                f"Voice AI setup completed for call {call_info.call_id}",
                extra={
                    "call_id": call_info.call_id,
                    "agent_id": agent.agent_id,
                    "room_name": call_context.livekit_room,
                    "trunk_name": call_info.trunk_name
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Voice AI call: {e}")
            self.metrics_collector.increment_counter(
                "sip_voice_ai_calls_setup_total",
                labels={"trunk": call_info.trunk_name, "success": "false"}
            )
            return False
    
    async def _answer_call(self, call_info: SIPCallInfo) -> None:
        """Answer the SIP call."""
        try:
            call_info.status = SIPCallStatus.ANSWERED
            call_info.answer_time = datetime.now(UTC)
            
            logger.info(f"Call {call_info.call_id} answered")
            
            # Execute event handlers
            for handler in self.call_event_handlers['call_answered']:
                try:
                    await handler(call_info)
                except Exception as e:
                    logger.error(f"Error in call answered handler: {e}")
            
        except Exception as e:
            logger.error(f"Error answering call: {e}")
    
    async def _reject_call(self, call_info: SIPCallInfo, reason: str) -> None:
        """Reject the SIP call."""
        try:
            call_info.status = SIPCallStatus.FAILED
            call_info.end_time = datetime.now(UTC)
            call_info.metadata['rejection_reason'] = reason
            
            # Remove from active calls
            self.active_calls.pop(call_info.call_id, None)
            self.metrics.active_calls = max(0, self.metrics.active_calls - 1)
            self.metrics.failed_calls += 1
            
            logger.info(f"Call {call_info.call_id} rejected: {reason}")
            
            # Execute event handlers
            for handler in self.call_event_handlers['call_failed']:
                try:
                    await handler(call_info)
                except Exception as e:
                    logger.error(f"Error in call failed handler: {e}")
            
        except Exception as e:
            logger.error(f"Error rejecting call: {e}")
    
    async def end_call(self, call_id: str, reason: str = "normal") -> None:
        """
        End a SIP call.
        
        Args:
            call_id: Call ID
            reason: Reason for ending call
        """
        try:
            call_info = self.active_calls.get(call_id)
            if not call_info:
                logger.warning(f"Call {call_id} not found for ending")
                return
            
            call_info.status = SIPCallStatus.ENDING
            
            # Clean up Voice AI agent
            if call_info.voice_ai_agent_id:
                agent = self.voice_ai_agents.pop(call_info.voice_ai_agent_id, None)
                if agent:
                    await agent.leave_room()
            
            # Clean up LiveKit room
            if call_info.livekit_room:
                try:
                    await self.api_client.delete_room(call_info.livekit_room)
                except Exception as e:
                    logger.warning(f"Error cleaning up LiveKit room: {e}")
            
            # Update call info
            call_info.status = SIPCallStatus.COMPLETED
            call_info.end_time = datetime.now(UTC)
            call_info.metadata['end_reason'] = reason
            
            if call_info.answer_time:
                call_info.duration = (call_info.end_time - call_info.answer_time).total_seconds()
            
            # Remove from active calls
            self.active_calls.pop(call_id, None)
            self.metrics.active_calls = max(0, self.metrics.active_calls - 1)
            self.metrics.completed_calls += 1
            
            # Update average duration
            if self.metrics.completed_calls > 0:
                total_duration = self.metrics.average_call_duration * (self.metrics.completed_calls - 1) + call_info.duration
                self.metrics.average_call_duration = total_duration / self.metrics.completed_calls
            
            logger.info(f"Call {call_id} ended: {reason} (duration: {call_info.duration:.2f}s)")
            
            # Execute event handlers
            for handler in self.call_event_handlers['call_ended']:
                try:
                    await handler(call_info)
                except Exception as e:
                    logger.error(f"Error in call ended handler: {e}")
            
            # Update metrics
            self.metrics_collector.increment_counter(
                "sip_calls_completed_total",
                labels={"trunk": call_info.trunk_name, "reason": reason}
            )
            
            self.metrics_collector.record_histogram(
                "sip_call_duration_seconds",
                call_info.duration,
                labels={"trunk": call_info.trunk_name}
            )
            
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {e}")
    
    def add_call_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add event handler for call events."""
        if event_type in self.call_event_handlers:
            self.call_event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown call event type: {event_type}")
    
    def get_call_info(self, call_id: str) -> Optional[SIPCallInfo]:
        """Get call information by ID."""
        return self.active_calls.get(call_id)
    
    def get_active_calls(self) -> List[SIPCallInfo]:
        """Get all active calls."""
        return list(self.active_calls.values())
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get SIP handler metrics."""
        return {
            "handler_metrics": self.metrics.to_dict(),
            "active_calls": len(self.active_calls),
            "voice_ai_agents": len(self.voice_ai_agents),
            "sip_trunks": len(self.sip_trunks),
            "routing_rules": len(self.routing_rules)
        }


# Global SIP handler instance
_sip_handler: Optional[SIPHandler] = None


async def get_sip_handler() -> Optional[SIPHandler]:
    """Get the global SIP handler instance."""
    return _sip_handler


async def initialize_sip_handler(
    orchestrator: CallOrchestrator,
    livekit_integration: LiveKitSIPIntegration,
    api_client: LiveKitAPIClient,
    auth_manager: LiveKitAuthManager,
    config_path: str = "livekit-sip-correct.yaml"
) -> SIPHandler:
    """Initialize the global SIP handler instance."""
    global _sip_handler
    
    _sip_handler = SIPHandler(
        orchestrator=orchestrator,
        livekit_integration=livekit_integration,
        api_client=api_client,
        auth_manager=auth_manager,
        config_path=config_path
    )
    
    await _sip_handler.initialize()
    return _sip_handler


async def shutdown_sip_handler() -> None:
    """Shutdown the global SIP handler instance."""
    global _sip_handler
    
    if _sip_handler:
        await _sip_handler.shutdown()
        _sip_handler = None
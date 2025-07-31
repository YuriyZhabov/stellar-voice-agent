"""Data access layer for conversation logging."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Call, Conversation, Message, ConversationMetrics, SystemEvent
from .connection import DatabaseManager

logger = logging.getLogger(__name__)


class ConversationRepository:
    """
    Repository for managing conversation data with comprehensive logging capabilities.
    
    Provides high-level operations for storing and retrieving call data,
    conversation logs, and system metrics.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
    
    # =============================================================================
    # CALL MANAGEMENT
    # =============================================================================
    
    async def create_call(
        self,
        call_id: str,
        caller_number: Optional[str] = None,
        livekit_room: Optional[str] = None,
        livekit_participant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Call:
        """
        Create a new call record.
        
        Args:
            call_id: Unique call identifier
            caller_number: Phone number of the caller
            livekit_room: LiveKit room identifier
            livekit_participant_id: LiveKit participant identifier
            metadata: Additional call metadata
            
        Returns:
            Call: Created call record
        """
        async with self.db_manager.get_async_session() as session:
            call = Call(
                call_id=call_id,
                caller_number=caller_number,
                livekit_room=livekit_room,
                livekit_participant_id=livekit_participant_id,
                call_metadata=metadata or {},
                status="active"
            )
            
            session.add(call)
            await session.flush()
            await session.refresh(call)
            
            logger.info(f"Created call record: {call_id}")
            return call
    
    async def end_call(
        self,
        call_id: str,
        end_time: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> Optional[Call]:
        """
        End a call and update its status.
        
        Args:
            call_id: Call identifier
            end_time: Call end time (defaults to now)
            error_message: Optional error message if call ended due to error
            
        Returns:
            Call: Updated call record or None if not found
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        
        async with self.db_manager.get_async_session() as session:
            # Get the call
            result = await session.execute(
                select(Call).where(Call.call_id == call_id)
            )
            call = result.scalar_one_or_none()
            
            if not call:
                logger.warning(f"Call not found for ending: {call_id}")
                return None
            
            # Calculate duration
            duration_seconds = None
            if call.start_time:
                # Ensure both datetimes are timezone-aware
                if call.start_time.tzinfo is None:
                    call_start_time = call.start_time.replace(tzinfo=timezone.utc)
                else:
                    call_start_time = call.start_time
                
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                
                duration_seconds = (end_time - call_start_time).total_seconds()
            
            # Update call
            call.end_time = end_time
            call.duration_seconds = duration_seconds
            call.status = "error" if error_message else "completed"
            
            if error_message:
                call.error_message = error_message
                call.error_count += 1
            
            await session.flush()
            await session.refresh(call)
            
            logger.info(f"Ended call: {call_id}, duration: {duration_seconds}s")
            return call
    
    async def get_call(self, call_id: str) -> Optional[Call]:
        """
        Get a call by ID with all related data.
        
        Args:
            call_id: Call identifier
            
        Returns:
            Call: Call record with conversations or None if not found
        """
        async with self.db_manager.get_async_session() as session:
            result = await session.execute(
                select(Call)
                .options(selectinload(Call.conversations))
                .where(Call.call_id == call_id)
            )
            return result.scalar_one_or_none()
    
    # =============================================================================
    # CONVERSATION MANAGEMENT
    # =============================================================================
    
    async def create_conversation(
        self,
        call_id: str,
        conversation_id: Optional[str] = None,
        ai_model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Conversation:
        """
        Create a new conversation within a call.
        
        Args:
            call_id: Parent call identifier
            conversation_id: Unique conversation identifier (auto-generated if None)
            ai_model: AI model used for this conversation
            system_prompt: System prompt used
            
        Returns:
            Conversation: Created conversation record
        """
        if conversation_id is None:
            conversation_id = str(uuid4())
        
        async with self.db_manager.get_async_session() as session:
            # Get the call
            call_result = await session.execute(
                select(Call).where(Call.call_id == call_id)
            )
            call = call_result.scalar_one_or_none()
            
            if not call:
                raise ValueError(f"Call not found: {call_id}")
            
            conversation = Conversation(
                call_id=call.id,
                conversation_id=conversation_id,
                ai_model=ai_model,
                system_prompt=system_prompt,
                status="active"
            )
            
            session.add(conversation)
            await session.flush()
            await session.refresh(conversation)
            
            logger.info(f"Created conversation: {conversation_id} for call: {call_id}")
            return conversation
    
    async def end_conversation(
        self,
        conversation_id: str,
        end_time: Optional[datetime] = None,
        summary: Optional[str] = None,
        topic: Optional[str] = None
    ) -> Optional[Conversation]:
        """
        End a conversation and update its status.
        
        Args:
            conversation_id: Conversation identifier
            end_time: Conversation end time (defaults to now)
            summary: Conversation summary
            topic: Conversation topic
            
        Returns:
            Conversation: Updated conversation record or None if not found
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        
        async with self.db_manager.get_async_session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                logger.warning(f"Conversation not found for ending: {conversation_id}")
                return None
            
            # Calculate duration
            duration_seconds = None
            if conversation.start_time:
                # Ensure both datetimes are timezone-aware
                if conversation.start_time.tzinfo is None:
                    conv_start_time = conversation.start_time.replace(tzinfo=timezone.utc)
                else:
                    conv_start_time = conversation.start_time
                
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                
                duration_seconds = (end_time - conv_start_time).total_seconds()
            
            # Update conversation
            conversation.end_time = end_time
            conversation.duration_seconds = duration_seconds
            conversation.status = "completed"
            
            if summary:
                conversation.summary = summary
            if topic:
                conversation.topic = topic
            
            await session.flush()
            await session.refresh(conversation)
            
            logger.info(f"Ended conversation: {conversation_id}, duration: {duration_seconds}s")
            return conversation
    
    # =============================================================================
    # MESSAGE MANAGEMENT
    # =============================================================================
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        processing_duration_ms: Optional[float] = None,
        stt_metadata: Optional[Dict[str, Any]] = None,
        llm_metadata: Optional[Dict[str, Any]] = None,
        tts_metadata: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Parent conversation identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            message_id: Unique message identifier (auto-generated if None)
            processing_duration_ms: Processing time in milliseconds
            stt_metadata: Speech-to-text metadata
            llm_metadata: Language model metadata
            tts_metadata: Text-to-speech metadata
            metadata: Additional metadata
            
        Returns:
            Message: Created message record
        """
        if message_id is None:
            message_id = str(uuid4())
        
        async with self.db_manager.get_async_session() as session:
            # Get the conversation
            conv_result = await session.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            
            if not conversation:
                raise ValueError(f"Conversation not found: {conversation_id}")
            
            # Get next sequence number
            seq_result = await session.execute(
                select(func.coalesce(func.max(Message.sequence_number), 0) + 1)
                .where(Message.conversation_id == conversation.id)
            )
            sequence_number = seq_result.scalar()
            
            # Create message
            message = Message(
                conversation_id=conversation.id,
                message_id=message_id,
                sequence_number=sequence_number,
                role=role,
                content=content,
                processing_duration_ms=processing_duration_ms,
                message_metadata=metadata or {}
            )
            
            # Add STT metadata
            if stt_metadata:
                message.stt_confidence = stt_metadata.get('confidence')
                message.stt_language = stt_metadata.get('language')
                message.stt_alternatives = stt_metadata.get('alternatives')
                message.original_audio_duration = stt_metadata.get('audio_duration')
            
            # Add LLM metadata
            if llm_metadata:
                message.llm_model = llm_metadata.get('model')
                message.llm_tokens_input = llm_metadata.get('tokens_input')
                message.llm_tokens_output = llm_metadata.get('tokens_output')
                message.llm_cost_usd = llm_metadata.get('cost_usd')
            
            # Add TTS metadata
            if tts_metadata:
                message.tts_voice_id = tts_metadata.get('voice_id')
                message.tts_audio_duration = tts_metadata.get('audio_duration')
                message.tts_cost_usd = tts_metadata.get('cost_usd')
            
            session.add(message)
            await session.flush()
            await session.refresh(message)
            
            logger.debug(f"Added message: {role} message to conversation {conversation_id}")
            return message
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """
        Get messages for a conversation.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List[Message]: List of messages ordered by sequence number
        """
        async with self.db_manager.get_async_session() as session:
            # Get conversation
            conv_result = await session.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            
            if not conversation:
                return []
            
            # Build query
            query = (
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.sequence_number)
                .offset(offset)
            )
            
            if limit:
                query = query.limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    # =============================================================================
    # METRICS MANAGEMENT
    # =============================================================================
    
    async def update_conversation_metrics(self, conversation_id: str) -> Optional[ConversationMetrics]:
        """
        Calculate and update metrics for a conversation.
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            ConversationMetrics: Updated metrics record or None if conversation not found
        """
        async with self.db_manager.get_async_session() as session:
            # Get conversation
            conv_result = await session.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            
            if not conversation:
                logger.warning(f"Conversation not found for metrics update: {conversation_id}")
                return None
            
            # Get or create metrics record
            metrics_result = await session.execute(
                select(ConversationMetrics).where(ConversationMetrics.conversation_id == conversation.id)
            )
            metrics = metrics_result.scalar_one_or_none()
            
            if not metrics:
                metrics = ConversationMetrics(conversation_id=conversation.id)
                session.add(metrics)
            
            # Calculate metrics from messages
            messages_result = await session.execute(
                select(Message).where(Message.conversation_id == conversation.id)
            )
            messages = list(messages_result.scalars().all())
            
            if not messages:
                await session.flush()
                await session.refresh(metrics)
                return metrics
            
            # Message counts
            metrics.total_messages = len(messages)
            metrics.user_messages = len([m for m in messages if m.role == 'user'])
            metrics.assistant_messages = len([m for m in messages if m.role == 'assistant'])
            
            # Timing metrics
            processing_times = [m.processing_duration_ms for m in messages if m.processing_duration_ms]
            if processing_times:
                metrics.avg_response_time_ms = sum(processing_times) / len(processing_times)
                metrics.max_response_time_ms = max(processing_times)
                metrics.min_response_time_ms = min(processing_times)
                metrics.total_processing_time_ms = sum(processing_times)
                
                # Count SLA violations (> 1500ms)
                metrics.latency_sla_violations = len([t for t in processing_times if t > 1500])
            
            # Token usage and costs
            metrics.total_input_tokens = sum(m.llm_tokens_input or 0 for m in messages)
            metrics.total_output_tokens = sum(m.llm_tokens_output or 0 for m in messages)
            metrics.total_llm_cost_usd = sum(m.llm_cost_usd or 0 for m in messages)
            metrics.total_tts_cost_usd = sum(m.tts_cost_usd or 0 for m in messages)
            metrics.total_cost_usd = metrics.total_llm_cost_usd + metrics.total_tts_cost_usd
            
            # Quality metrics
            stt_confidences = [m.stt_confidence for m in messages if m.stt_confidence]
            if stt_confidences:
                metrics.avg_stt_confidence = sum(stt_confidences) / len(stt_confidences)
            
            # Audio metrics
            audio_durations = [m.original_audio_duration for m in messages if m.original_audio_duration]
            if audio_durations:
                metrics.total_audio_duration_seconds = sum(audio_durations)
            
            speech_durations = [m.tts_audio_duration for m in messages if m.tts_audio_duration]
            if speech_durations:
                metrics.total_speech_duration_seconds = sum(speech_durations)
            
            # Error tracking
            metrics.total_errors = len([m for m in messages if m.error_message])
            metrics.total_retries = sum(m.retry_count for m in messages)
            
            await session.flush()
            await session.refresh(metrics)
            
            logger.info(f"Updated metrics for conversation: {conversation_id}")
            return metrics
    
    # =============================================================================
    # SYSTEM EVENTS
    # =============================================================================
    
    async def log_system_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        component: Optional[str] = None,
        call_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ) -> SystemEvent:
        """
        Log a system event.
        
        Args:
            event_type: Type of event
            severity: Event severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Event message
            component: Component that generated the event
            call_id: Related call ID
            conversation_id: Related conversation ID
            metadata: Additional event metadata
            stack_trace: Stack trace for errors
            
        Returns:
            SystemEvent: Created event record
        """
        async with self.db_manager.get_async_session() as session:
            event = SystemEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                severity=severity.upper(),
                message=message,
                component=component,
                call_id=call_id,
                conversation_id=conversation_id,
                event_metadata=metadata or {},
                stack_trace=stack_trace
            )
            
            session.add(event)
            await session.flush()
            await session.refresh(event)
            
            return event
    
    # =============================================================================
    # DATA RETENTION AND CLEANUP
    # =============================================================================
    
    async def cleanup_old_data(self, retention_days: int = 30) -> Dict[str, int]:
        """
        Clean up old conversation data based on retention policy.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Dict with counts of deleted records
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted_counts = {"calls": 0, "conversations": 0, "messages": 0, "events": 0}
        
        async with self.db_manager.get_async_session() as session:
            # Delete old system events
            events_result = await session.execute(
                delete(SystemEvent).where(SystemEvent.timestamp < cutoff_date)
            )
            deleted_counts["events"] = events_result.rowcount
            
            # Delete old calls (cascades to conversations and messages)
            calls_result = await session.execute(
                delete(Call).where(Call.created_at < cutoff_date)
            )
            deleted_counts["calls"] = calls_result.rowcount
            
            logger.info(f"Cleaned up old data: {deleted_counts}")
            return deleted_counts
    
    # =============================================================================
    # ANALYTICS AND REPORTING
    # =============================================================================
    
    async def get_call_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get call statistics for a date range.
        
        Args:
            start_date: Start date for statistics (defaults to 24 hours ago)
            end_date: End date for statistics (defaults to now)
            
        Returns:
            Dict containing call statistics
        """
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(hours=24)
        
        async with self.db_manager.get_async_session() as session:
            # Basic call counts
            total_calls_result = await session.execute(
                select(func.count(Call.id))
                .where(and_(Call.start_time >= start_date, Call.start_time <= end_date))
            )
            total_calls = total_calls_result.scalar()
            
            # Completed calls
            completed_calls_result = await session.execute(
                select(func.count(Call.id))
                .where(and_(
                    Call.start_time >= start_date,
                    Call.start_time <= end_date,
                    Call.status == "completed"
                ))
            )
            completed_calls = completed_calls_result.scalar()
            
            # Average call duration
            avg_duration_result = await session.execute(
                select(func.avg(Call.duration_seconds))
                .where(and_(
                    Call.start_time >= start_date,
                    Call.start_time <= end_date,
                    Call.duration_seconds.isnot(None)
                ))
            )
            avg_duration = avg_duration_result.scalar() or 0
            
            # Total conversation metrics
            metrics_result = await session.execute(
                select(
                    func.sum(ConversationMetrics.total_cost_usd),
                    func.avg(ConversationMetrics.avg_response_time_ms),
                    func.sum(ConversationMetrics.latency_sla_violations),
                    func.sum(ConversationMetrics.total_messages)
                )
                .join(Conversation)
                .join(Call)
                .where(and_(Call.start_time >= start_date, Call.start_time <= end_date))
            )
            metrics_data = metrics_result.first()
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "calls": {
                    "total": total_calls,
                    "completed": completed_calls,
                    "success_rate": (completed_calls / total_calls * 100) if total_calls > 0 else 0,
                    "avg_duration_seconds": float(avg_duration)
                },
                "performance": {
                    "total_cost_usd": float(metrics_data[0] or 0),
                    "avg_response_time_ms": float(metrics_data[1] or 0),
                    "sla_violations": int(metrics_data[2] or 0),
                    "total_messages": int(metrics_data[3] or 0)
                }
            }
"""Integration between database logging and conversation system."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import uuid4

from .repository import ConversationRepository
from .connection import get_database_manager

logger = logging.getLogger(__name__)


class ConversationLogger:
    """
    High-level interface for logging conversation data.
    
    Provides a simplified API for the conversation system to log
    calls, messages, and events without dealing with database details.
    """
    
    def __init__(self):
        """Initialize the conversation logger."""
        self.db_manager = get_database_manager()
        self.repository = ConversationRepository(self.db_manager)
        self._active_calls: Dict[str, int] = {}  # call_id -> db_id mapping
        self._active_conversations: Dict[str, int] = {}  # conversation_id -> db_id mapping
    
    async def start_call(
        self,
        call_id: str,
        caller_number: Optional[str] = None,
        livekit_room: Optional[str] = None,
        livekit_participant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Start logging a new call.
        
        Args:
            call_id: Unique call identifier
            caller_number: Phone number of the caller
            livekit_room: LiveKit room identifier
            livekit_participant_id: LiveKit participant identifier
            metadata: Additional call metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            call = await self.repository.create_call(
                call_id=call_id,
                caller_number=caller_number,
                livekit_room=livekit_room,
                livekit_participant_id=livekit_participant_id,
                metadata=metadata
            )
            
            self._active_calls[call_id] = call.id
            logger.info(f"Started logging call: {call_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start call logging for {call_id}: {e}")
            await self._log_error("call_logging_error", f"Failed to start call logging: {e}", call_id=call_id)
            return False
    
    async def end_call(
        self,
        call_id: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        End call logging.
        
        Args:
            call_id: Call identifier
            error_message: Optional error message if call ended due to error
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            call = await self.repository.end_call(
                call_id=call_id,
                error_message=error_message
            )
            
            if call:
                # Remove from active calls
                self._active_calls.pop(call_id, None)
                logger.info(f"Ended call logging: {call_id}")
                return True
            else:
                logger.warning(f"Call not found for ending: {call_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to end call logging for {call_id}: {e}")
            await self._log_error("call_logging_error", f"Failed to end call logging: {e}", call_id=call_id)
            return False
    
    async def start_conversation(
        self,
        call_id: str,
        conversation_id: Optional[str] = None,
        ai_model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Start logging a new conversation within a call.
        
        Args:
            call_id: Parent call identifier
            conversation_id: Unique conversation identifier (auto-generated if None)
            ai_model: AI model used for this conversation
            system_prompt: System prompt used
            
        Returns:
            Optional[str]: Conversation ID if successful, None otherwise
        """
        try:
            if conversation_id is None:
                conversation_id = str(uuid4())
            
            conversation = await self.repository.create_conversation(
                call_id=call_id,
                conversation_id=conversation_id,
                ai_model=ai_model,
                system_prompt=system_prompt
            )
            
            self._active_conversations[conversation_id] = conversation.id
            logger.info(f"Started logging conversation: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Failed to start conversation logging for {conversation_id}: {e}")
            await self._log_error("conversation_logging_error", f"Failed to start conversation logging: {e}", 
                                call_id=call_id, conversation_id=conversation_id)
            return None
    
    async def end_conversation(
        self,
        conversation_id: str,
        summary: Optional[str] = None,
        topic: Optional[str] = None
    ) -> bool:
        """
        End conversation logging.
        
        Args:
            conversation_id: Conversation identifier
            summary: Conversation summary
            topic: Conversation topic
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conversation = await self.repository.end_conversation(
                conversation_id=conversation_id,
                summary=summary,
                topic=topic
            )
            
            if conversation:
                # Update metrics before removing from active conversations
                await self.repository.update_conversation_metrics(conversation_id)
                
                # Remove from active conversations
                self._active_conversations.pop(conversation_id, None)
                logger.info(f"Ended conversation logging: {conversation_id}")
                return True
            else:
                logger.warning(f"Conversation not found for ending: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to end conversation logging for {conversation_id}: {e}")
            await self._log_error("conversation_logging_error", f"Failed to end conversation logging: {e}", 
                                conversation_id=conversation_id)
            return False
    
    async def log_user_message(
        self,
        conversation_id: str,
        content: str,
        audio_duration: Optional[float] = None,
        stt_confidence: Optional[float] = None,
        stt_language: Optional[str] = None,
        processing_time_ms: Optional[float] = None,
        alternatives: Optional[List[str]] = None
    ) -> bool:
        """
        Log a user message (from speech-to-text).
        
        Args:
            conversation_id: Conversation identifier
            content: Transcribed message content
            audio_duration: Duration of original audio in seconds
            stt_confidence: Speech-to-text confidence score
            stt_language: Detected language
            processing_time_ms: Processing time in milliseconds
            alternatives: Alternative transcriptions
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            stt_metadata = {}
            if stt_confidence is not None:
                stt_metadata['confidence'] = stt_confidence
            if stt_language is not None:
                stt_metadata['language'] = stt_language
            if audio_duration is not None:
                stt_metadata['audio_duration'] = audio_duration
            if alternatives is not None:
                stt_metadata['alternatives'] = alternatives
            
            message = await self.repository.add_message(
                conversation_id=conversation_id,
                role="user",
                content=content,
                processing_duration_ms=processing_time_ms,
                stt_metadata=stt_metadata if stt_metadata else None
            )
            
            logger.debug(f"Logged user message in conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log user message for {conversation_id}: {e}")
            await self._log_error("message_logging_error", f"Failed to log user message: {e}", 
                                conversation_id=conversation_id)
            return False
    
    async def log_assistant_message(
        self,
        conversation_id: str,
        content: str,
        processing_time_ms: Optional[float] = None,
        llm_model: Optional[str] = None,
        llm_tokens_input: Optional[int] = None,
        llm_tokens_output: Optional[int] = None,
        llm_cost_usd: Optional[float] = None,
        tts_voice_id: Optional[str] = None,
        tts_audio_duration: Optional[float] = None,
        tts_cost_usd: Optional[float] = None
    ) -> bool:
        """
        Log an assistant message (AI response).
        
        Args:
            conversation_id: Conversation identifier
            content: AI response content
            processing_time_ms: Total processing time in milliseconds
            llm_model: Language model used
            llm_tokens_input: Input tokens used
            llm_tokens_output: Output tokens generated
            llm_cost_usd: LLM cost in USD
            tts_voice_id: Text-to-speech voice ID
            tts_audio_duration: Generated audio duration in seconds
            tts_cost_usd: TTS cost in USD
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            llm_metadata = {}
            if llm_model is not None:
                llm_metadata['model'] = llm_model
            if llm_tokens_input is not None:
                llm_metadata['tokens_input'] = llm_tokens_input
            if llm_tokens_output is not None:
                llm_metadata['tokens_output'] = llm_tokens_output
            if llm_cost_usd is not None:
                llm_metadata['cost_usd'] = llm_cost_usd
            
            tts_metadata = {}
            if tts_voice_id is not None:
                tts_metadata['voice_id'] = tts_voice_id
            if tts_audio_duration is not None:
                tts_metadata['audio_duration'] = tts_audio_duration
            if tts_cost_usd is not None:
                tts_metadata['cost_usd'] = tts_cost_usd
            
            message = await self.repository.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                processing_duration_ms=processing_time_ms,
                llm_metadata=llm_metadata if llm_metadata else None,
                tts_metadata=tts_metadata if tts_metadata else None
            )
            
            logger.debug(f"Logged assistant message in conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log assistant message for {conversation_id}: {e}")
            await self._log_error("message_logging_error", f"Failed to log assistant message: {e}", 
                                conversation_id=conversation_id)
            return False
    
    async def log_system_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log a system message.
        
        Args:
            conversation_id: Conversation identifier
            content: System message content
            metadata: Additional metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            message = await self.repository.add_message(
                conversation_id=conversation_id,
                role="system",
                content=content,
                metadata=metadata
            )
            
            logger.debug(f"Logged system message in conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log system message for {conversation_id}: {e}")
            await self._log_error("message_logging_error", f"Failed to log system message: {e}", 
                                conversation_id=conversation_id)
            return False
    
    async def log_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        component: Optional[str] = None,
        call_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ) -> bool:
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
            bool: True if successful, False otherwise
        """
        try:
            event = await self.repository.log_system_event(
                event_type=event_type,
                severity=severity,
                message=message,
                component=component,
                call_id=call_id,
                conversation_id=conversation_id,
                metadata=metadata,
                stack_trace=stack_trace
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            # Don't recursively log errors for event logging failures
            return False
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation message history.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            
        Returns:
            List[Dict]: List of message dictionaries
        """
        try:
            messages = await self.repository.get_conversation_messages(
                conversation_id=conversation_id,
                limit=limit
            )
            
            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "sequence_number": msg.sequence_number,
                    "created_at": msg.created_at.isoformat(),
                    "processing_duration_ms": msg.processing_duration_ms,
                    "stt_confidence": msg.stt_confidence,
                    "llm_tokens_input": msg.llm_tokens_input,
                    "llm_tokens_output": msg.llm_tokens_output,
                    "metadata": msg.message_metadata
                }
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Failed to get conversation history for {conversation_id}: {e}")
            return []
    
    async def get_call_statistics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get call statistics for the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dict: Statistics dictionary
        """
        try:
            from datetime import timedelta
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            stats = await self.repository.get_call_statistics(
                start_date=start_time,
                end_date=end_time
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get call statistics: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_data(self, retention_days: int = 30) -> Dict[str, int]:
        """
        Clean up old conversation data.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Dict: Counts of deleted records
        """
        try:
            return await self.repository.cleanup_old_data(retention_days)
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {"error": str(e)}
    
    async def _log_error(
        self,
        event_type: str,
        message: str,
        call_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> None:
        """Internal method to log errors without recursion."""
        try:
            await self.repository.log_system_event(
                event_type=event_type,
                severity="ERROR",
                message=message,
                component="conversation_logger",
                call_id=call_id,
                conversation_id=conversation_id
            )
        except Exception:
            # Don't log errors for error logging to avoid recursion
            pass


# Global conversation logger instance
_conversation_logger: Optional[ConversationLogger] = None


def get_conversation_logger() -> ConversationLogger:
    """
    Get the global conversation logger instance.
    
    Returns:
        ConversationLogger: The global conversation logger
    """
    global _conversation_logger
    if _conversation_logger is None:
        _conversation_logger = ConversationLogger()
    return _conversation_logger
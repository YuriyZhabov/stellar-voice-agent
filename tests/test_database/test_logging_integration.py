"""Tests for conversation logging integration."""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from src.database.connection import DatabaseManager
from src.database.logging_integration import ConversationLogger, get_conversation_logger
from src.config import Settings, Environment


@pytest.fixture
async def db_manager():
    """Create a test database manager with in-memory SQLite."""
    settings = Settings(
        environment=Environment.TESTING,
        database_url="sqlite:///:memory:",
        debug=True
    )
    
    with patch('src.database.connection.get_settings', return_value=settings):
        manager = DatabaseManager()
        await manager.initialize()
        await manager.create_tables()
        yield manager
        await manager.cleanup()


@pytest.fixture
async def conversation_logger(db_manager):
    """Create a conversation logger."""
    with patch('src.database.logging_integration.get_database_manager', return_value=db_manager):
        logger = ConversationLogger()
        yield logger


class TestConversationLogger:
    """Test the ConversationLogger class."""
    
    @pytest.mark.asyncio
    async def test_start_call(self, conversation_logger):
        """Test starting a call."""
        success = await conversation_logger.start_call(
            call_id="test-call-123",
            caller_number="+1234567890",
            livekit_room="room-123",
            metadata={"source": "test"}
        )
        
        assert success is True
        assert "test-call-123" in conversation_logger._active_calls
    
    @pytest.mark.asyncio
    async def test_end_call(self, conversation_logger):
        """Test ending a call."""
        # Start a call first
        await conversation_logger.start_call(call_id="test-call-end")
        
        # End the call
        success = await conversation_logger.end_call(call_id="test-call-end")
        
        assert success is True
        assert "test-call-end" not in conversation_logger._active_calls
    
    @pytest.mark.asyncio
    async def test_end_call_with_error(self, conversation_logger):
        """Test ending a call with error."""
        # Start a call first
        await conversation_logger.start_call(call_id="test-call-error")
        
        # End the call with error
        success = await conversation_logger.end_call(
            call_id="test-call-error",
            error_message="Connection lost"
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_start_conversation(self, conversation_logger):
        """Test starting a conversation."""
        # Start a call first
        await conversation_logger.start_call(call_id="test-call-conv")
        
        # Start conversation
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-conv",
            ai_model="gpt-4",
            system_prompt="You are helpful"
        )
        
        assert conversation_id is not None
        assert conversation_id in conversation_logger._active_conversations
    
    @pytest.mark.asyncio
    async def test_start_conversation_auto_id(self, conversation_logger):
        """Test starting a conversation with auto-generated ID."""
        # Start a call first
        await conversation_logger.start_call(call_id="test-call-auto")
        
        # Start conversation without specifying ID
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-auto"
        )
        
        assert conversation_id is not None
        assert len(conversation_id) > 0
    
    @pytest.mark.asyncio
    async def test_end_conversation(self, conversation_logger):
        """Test ending a conversation."""
        # Start call and conversation
        await conversation_logger.start_call(call_id="test-call-end-conv")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-end-conv"
        )
        
        # End conversation
        success = await conversation_logger.end_conversation(
            conversation_id=conversation_id,
            summary="Test conversation",
            topic="Testing"
        )
        
        assert success is True
        assert conversation_id not in conversation_logger._active_conversations
    
    @pytest.mark.asyncio
    async def test_log_user_message(self, conversation_logger):
        """Test logging a user message."""
        # Setup call and conversation
        await conversation_logger.start_call(call_id="test-call-user-msg")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-user-msg"
        )
        
        # Log user message
        success = await conversation_logger.log_user_message(
            conversation_id=conversation_id,
            content="Hello, how are you?",
            audio_duration=2.5,
            stt_confidence=0.95,
            stt_language="en-US",
            processing_time_ms=150.0,
            alternatives=["Hello how are you", "Hello, how are you"]
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_log_assistant_message(self, conversation_logger):
        """Test logging an assistant message."""
        # Setup call and conversation
        await conversation_logger.start_call(call_id="test-call-assistant-msg")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-assistant-msg"
        )
        
        # Log assistant message
        success = await conversation_logger.log_assistant_message(
            conversation_id=conversation_id,
            content="I'm doing well, thank you!",
            processing_time_ms=1200.0,
            llm_model="gpt-4",
            llm_tokens_input=10,
            llm_tokens_output=8,
            llm_cost_usd=0.0002,
            tts_voice_id="voice-123",
            tts_audio_duration=2.0,
            tts_cost_usd=0.0001
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_log_system_message(self, conversation_logger):
        """Test logging a system message."""
        # Setup call and conversation
        await conversation_logger.start_call(call_id="test-call-system-msg")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-system-msg"
        )
        
        # Log system message
        success = await conversation_logger.log_system_message(
            conversation_id=conversation_id,
            content="Conversation started",
            metadata={"event": "start"}
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_log_event(self, conversation_logger):
        """Test logging a system event."""
        success = await conversation_logger.log_event(
            event_type="api_error",
            severity="ERROR",
            message="OpenAI API request failed",
            component="openai_client",
            call_id="test-call-123",
            metadata={"error_code": 429}
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conversation_logger):
        """Test getting conversation history."""
        # Setup call and conversation
        await conversation_logger.start_call(call_id="test-call-history")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-history"
        )
        
        # Add some messages
        await conversation_logger.log_user_message(
            conversation_id=conversation_id,
            content="Hello"
        )
        await conversation_logger.log_assistant_message(
            conversation_id=conversation_id,
            content="Hi there!"
        )
        await conversation_logger.log_user_message(
            conversation_id=conversation_id,
            content="How are you?"
        )
        
        # Get history
        history = await conversation_logger.get_conversation_history(conversation_id)
        
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"
        assert history[2]["role"] == "user"
        assert history[2]["content"] == "How are you?"
    
    @pytest.mark.asyncio
    async def test_get_conversation_history_with_limit(self, conversation_logger):
        """Test getting conversation history with limit."""
        # Setup call and conversation
        await conversation_logger.start_call(call_id="test-call-history-limit")
        conversation_id = await conversation_logger.start_conversation(
            call_id="test-call-history-limit"
        )
        
        # Add multiple messages
        for i in range(5):
            await conversation_logger.log_user_message(
                conversation_id=conversation_id,
                content=f"Message {i + 1}"
            )
        
        # Get limited history
        history = await conversation_logger.get_conversation_history(
            conversation_id,
            limit=3
        )
        
        assert len(history) == 3
        assert history[0]["content"] == "Message 1"
        assert history[1]["content"] == "Message 2"
        assert history[2]["content"] == "Message 3"
    
    @pytest.mark.asyncio
    async def test_get_call_statistics(self, conversation_logger):
        """Test getting call statistics."""
        # Create some test data
        await conversation_logger.start_call(call_id="stats-call-1")
        await conversation_logger.end_call("stats-call-1")
        
        await conversation_logger.start_call(call_id="stats-call-2")
        await conversation_logger.end_call("stats-call-2", error_message="Test error")
        
        # Get statistics
        stats = await conversation_logger.get_call_statistics(hours=1)
        
        assert "calls" in stats
        assert "performance" in stats
        assert stats["calls"]["total"] >= 2
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, conversation_logger):
        """Test cleaning up old data."""
        # Create some test data
        await conversation_logger.start_call(call_id="cleanup-test-call")
        await conversation_logger.end_call("cleanup-test-call")
        
        # Cleanup (should not delete recent data)
        result = await conversation_logger.cleanup_old_data(retention_days=30)
        
        assert isinstance(result, dict)
        # Should not delete recent data
        assert result.get("calls", 0) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, conversation_logger):
        """Test error handling in logging operations."""
        # Try to start conversation with invalid call ID
        conversation_id = await conversation_logger.start_conversation(
            call_id="nonexistent-call"
        )
        
        assert conversation_id is None
        
        # Try to log message to nonexistent conversation
        success = await conversation_logger.log_user_message(
            conversation_id="nonexistent-conv",
            content="Test message"
        )
        
        assert success is False
        
        # Try to end nonexistent call
        success = await conversation_logger.end_call("nonexistent-call")
        
        assert success is False


class TestGlobalConversationLogger:
    """Test global conversation logger functions."""
    
    def test_get_conversation_logger_singleton(self):
        """Test that get_conversation_logger returns singleton."""
        # Clear any existing global instance
        import src.database.logging_integration
        src.database.logging_integration._conversation_logger = None
        
        logger1 = get_conversation_logger()
        logger2 = get_conversation_logger()
        
        assert logger1 is logger2
    
    @pytest.mark.asyncio
    async def test_conversation_logger_integration(self, db_manager):
        """Test conversation logger integration with database manager."""
        # Clear any existing global instance
        import src.database.logging_integration
        src.database.logging_integration._conversation_logger = None
        
        with patch('src.database.logging_integration.get_database_manager', return_value=db_manager):
            logger = get_conversation_logger()
            
            # Test basic functionality
            success = await logger.start_call(call_id="integration-test")
            assert success is True
            
            conversation_id = await logger.start_conversation(call_id="integration-test")
            assert conversation_id is not None
            
            success = await logger.log_user_message(
                conversation_id=conversation_id,
                content="Integration test message"
            )
            assert success is True


class TestFullConversationFlow:
    """Test complete conversation flow logging."""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, conversation_logger):
        """Test logging a complete conversation flow."""
        # Start call
        call_success = await conversation_logger.start_call(
            call_id="flow-test-call",
            caller_number="+1234567890",
            metadata={"test": "flow"}
        )
        assert call_success is True
        
        # Start conversation
        conversation_id = await conversation_logger.start_conversation(
            call_id="flow-test-call",
            ai_model="gpt-4",
            system_prompt="You are a helpful assistant"
        )
        assert conversation_id is not None
        
        # Log conversation messages
        messages = [
            ("user", "Hello, I need help with my account"),
            ("assistant", "I'd be happy to help you with your account. What specific issue are you experiencing?"),
            ("user", "I can't log in to my account"),
            ("assistant", "I understand you're having trouble logging in. Let me help you troubleshoot this issue."),
            ("user", "Thank you, that would be great"),
            ("assistant", "You're welcome! Let's start by checking if you're using the correct email address.")
        ]
        
        for role, content in messages:
            if role == "user":
                success = await conversation_logger.log_user_message(
                    conversation_id=conversation_id,
                    content=content,
                    stt_confidence=0.95,
                    processing_time_ms=100.0
                )
            else:
                success = await conversation_logger.log_assistant_message(
                    conversation_id=conversation_id,
                    content=content,
                    llm_model="gpt-4",
                    llm_tokens_input=20,
                    llm_tokens_output=15,
                    processing_time_ms=800.0
                )
            assert success is True
        
        # Log some events
        await conversation_logger.log_event(
            event_type="conversation_milestone",
            severity="INFO",
            message="User authentication issue identified",
            call_id="flow-test-call",
            conversation_id=conversation_id
        )
        
        # End conversation
        conv_success = await conversation_logger.end_conversation(
            conversation_id=conversation_id,
            summary="User needed help with account login issues. Provided troubleshooting steps.",
            topic="Account Support"
        )
        assert conv_success is True
        
        # End call
        call_end_success = await conversation_logger.end_call("flow-test-call")
        assert call_end_success is True
        
        # Verify conversation history
        history = await conversation_logger.get_conversation_history(conversation_id)
        assert len(history) == 6
        
        # Verify message sequence
        for i, (expected_role, expected_content) in enumerate(messages):
            assert history[i]["role"] == expected_role
            assert history[i]["content"] == expected_content
            assert history[i]["sequence_number"] == i + 1
        
        # Get statistics
        stats = await conversation_logger.get_call_statistics(hours=1)
        assert stats["calls"]["total"] >= 1
        assert stats["calls"]["completed"] >= 1
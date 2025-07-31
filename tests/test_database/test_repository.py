"""Tests for conversation repository."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.database.connection import DatabaseManager
from src.database.repository import ConversationRepository
from src.database.models import Call, Conversation, Message, ConversationMetrics, SystemEvent
from src.config import Settings, Environment


def normalize_datetime_for_comparison(dt: datetime) -> datetime:
    """
    Normalize datetime for comparison by ensuring it's timezone-aware in UTC.
    
    SQLite doesn't preserve timezone information, so we need to handle
    timezone-naive datetimes returned from the database by treating them as UTC.
    
    Args:
        dt: Datetime object to normalize
        
    Returns:
        Timezone-aware datetime in UTC
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Assume timezone-naive datetimes from database are UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Convert timezone-aware datetimes to UTC
        return dt.astimezone(timezone.utc)


def assert_datetime_equal(actual: datetime, expected: datetime, tolerance_seconds: float = 1.0):
    """
    Assert that two datetime objects are equal within a tolerance, handling timezone differences.
    
    Args:
        actual: Actual datetime value (typically from database)
        expected: Expected datetime value (typically from test)
        tolerance_seconds: Tolerance in seconds for comparison
    """
    actual_normalized = normalize_datetime_for_comparison(actual)
    expected_normalized = normalize_datetime_for_comparison(expected)
    
    if actual_normalized is None and expected_normalized is None:
        return
    
    if actual_normalized is None or expected_normalized is None:
        raise AssertionError(f"One datetime is None: actual={actual_normalized}, expected={expected_normalized}")
    
    time_diff = abs((actual_normalized - expected_normalized).total_seconds())
    if time_diff > tolerance_seconds:
        raise AssertionError(
            f"Datetime difference {time_diff}s exceeds tolerance {tolerance_seconds}s: "
            f"actual={actual_normalized}, expected={expected_normalized}"
        )


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
async def repository(db_manager):
    """Create a conversation repository."""
    return ConversationRepository(db_manager)


class TestCallManagement:
    """Test call management operations."""
    
    @pytest.mark.asyncio
    async def test_create_call(self, repository):
        """Test creating a call record."""
        call = await repository.create_call(
            call_id="test-call-123",
            caller_number="+1234567890",
            livekit_room="room-123",
            metadata={"source": "test"}
        )
        
        assert call.call_id == "test-call-123"
        assert call.caller_number == "+1234567890"
        assert call.livekit_room == "room-123"
        assert call.status == "active"
        assert call.call_metadata["source"] == "test"
        assert call.created_at is not None
    
    @pytest.mark.asyncio
    async def test_end_call(self, repository):
        """Test ending a call."""
        # Create a call first
        call = await repository.create_call(call_id="test-call-end")
        
        # End the call
        end_time = datetime.now(timezone.utc)
        ended_call = await repository.end_call(
            call_id="test-call-end",
            end_time=end_time
        )
        
        assert ended_call is not None
        assert ended_call.status == "completed"
        assert_datetime_equal(ended_call.end_time, end_time)
        assert ended_call.duration_seconds is not None
        assert ended_call.duration_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_end_call_with_error(self, repository):
        """Test ending a call with error."""
        # Create a call first
        call = await repository.create_call(call_id="test-call-error")
        
        # End the call with error
        ended_call = await repository.end_call(
            call_id="test-call-error",
            error_message="Connection lost"
        )
        
        assert ended_call.status == "error"
        assert ended_call.error_message == "Connection lost"
        assert ended_call.error_count == 1
    
    @pytest.mark.asyncio
    async def test_end_nonexistent_call(self, repository):
        """Test ending a call that doesn't exist."""
        result = await repository.end_call(call_id="nonexistent-call")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_call(self, repository):
        """Test retrieving a call with conversations."""
        # Create call and conversation
        call = await repository.create_call(call_id="test-call-get")
        conversation = await repository.create_conversation(
            call_id="test-call-get",
            conversation_id="test-conv-1"
        )
        
        # Retrieve the call
        retrieved_call = await repository.get_call("test-call-get")
        
        assert retrieved_call is not None
        assert retrieved_call.call_id == "test-call-get"
        assert len(retrieved_call.conversations) == 1
        assert retrieved_call.conversations[0].conversation_id == "test-conv-1"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_call(self, repository):
        """Test retrieving a call that doesn't exist."""
        result = await repository.get_call("nonexistent-call")
        assert result is None


class TestConversationManagement:
    """Test conversation management operations."""
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, repository):
        """Test creating a conversation."""
        # Create parent call first
        call = await repository.create_call(call_id="test-call-conv")
        
        conversation = await repository.create_conversation(
            call_id="test-call-conv",
            conversation_id="test-conv-123",
            ai_model="gpt-4",
            system_prompt="You are helpful"
        )
        
        assert conversation.conversation_id == "test-conv-123"
        assert conversation.ai_model == "gpt-4"
        assert conversation.system_prompt == "You are helpful"
        assert conversation.status == "active"
    
    @pytest.mark.asyncio
    async def test_create_conversation_auto_id(self, repository):
        """Test creating a conversation with auto-generated ID."""
        # Create parent call first
        call = await repository.create_call(call_id="test-call-auto")
        
        conversation = await repository.create_conversation(
            call_id="test-call-auto"
        )
        
        assert conversation.conversation_id is not None
        assert len(conversation.conversation_id) > 0
    
    @pytest.mark.asyncio
    async def test_create_conversation_invalid_call(self, repository):
        """Test creating a conversation with invalid call ID."""
        with pytest.raises(ValueError, match="Call not found"):
            await repository.create_conversation(call_id="nonexistent-call")
    
    @pytest.mark.asyncio
    async def test_end_conversation(self, repository):
        """Test ending a conversation."""
        # Create parent call and conversation
        call = await repository.create_call(call_id="test-call-end-conv")
        conversation = await repository.create_conversation(
            call_id="test-call-end-conv",
            conversation_id="test-conv-end"
        )
        
        # End the conversation
        end_time = datetime.now(timezone.utc)
        ended_conv = await repository.end_conversation(
            conversation_id="test-conv-end",
            end_time=end_time,
            summary="Test conversation summary",
            topic="Testing"
        )
        
        assert ended_conv is not None
        assert ended_conv.status == "completed"
        assert_datetime_equal(ended_conv.end_time, end_time)
        assert ended_conv.summary == "Test conversation summary"
        assert ended_conv.topic == "Testing"
        assert ended_conv.duration_seconds is not None
    
    @pytest.mark.asyncio
    async def test_end_nonexistent_conversation(self, repository):
        """Test ending a conversation that doesn't exist."""
        result = await repository.end_conversation("nonexistent-conv")
        assert result is None


class TestMessageManagement:
    """Test message management operations."""
    
    @pytest.mark.asyncio
    async def test_add_user_message(self, repository):
        """Test adding a user message."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-msg")
        conversation = await repository.create_conversation(
            call_id="test-call-msg",
            conversation_id="test-conv-msg"
        )
        
        # Add user message
        message = await repository.add_message(
            conversation_id="test-conv-msg",
            role="user",
            content="Hello, how are you?",
            processing_duration_ms=150.5,
            stt_metadata={
                "confidence": 0.95,
                "language": "en-US",
                "audio_duration": 2.5
            }
        )
        
        assert message.role == "user"
        assert message.content == "Hello, how are you?"
        assert message.sequence_number == 1
        assert message.processing_duration_ms == 150.5
        assert message.stt_confidence == 0.95
        assert message.stt_language == "en-US"
        assert message.original_audio_duration == 2.5
    
    @pytest.mark.asyncio
    async def test_add_assistant_message(self, repository):
        """Test adding an assistant message."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-assistant")
        conversation = await repository.create_conversation(
            call_id="test-call-assistant",
            conversation_id="test-conv-assistant"
        )
        
        # Add assistant message
        message = await repository.add_message(
            conversation_id="test-conv-assistant",
            role="assistant",
            content="I'm doing well, thank you!",
            llm_metadata={
                "model": "gpt-4",
                "tokens_input": 10,
                "tokens_output": 8,
                "cost_usd": 0.0002
            },
            tts_metadata={
                "voice_id": "voice-123",
                "audio_duration": 2.0,
                "cost_usd": 0.0001
            }
        )
        
        assert message.role == "assistant"
        assert message.content == "I'm doing well, thank you!"
        assert message.llm_model == "gpt-4"
        assert message.llm_tokens_input == 10
        assert message.llm_tokens_output == 8
        assert message.llm_cost_usd == 0.0002
        assert message.tts_voice_id == "voice-123"
        assert message.tts_audio_duration == 2.0
        assert message.tts_cost_usd == 0.0001
    
    @pytest.mark.asyncio
    async def test_add_message_sequence_numbers(self, repository):
        """Test that sequence numbers are assigned correctly."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-seq")
        conversation = await repository.create_conversation(
            call_id="test-call-seq",
            conversation_id="test-conv-seq"
        )
        
        # Add multiple messages
        msg1 = await repository.add_message(
            conversation_id="test-conv-seq",
            role="user",
            content="First message"
        )
        
        msg2 = await repository.add_message(
            conversation_id="test-conv-seq",
            role="assistant",
            content="Second message"
        )
        
        msg3 = await repository.add_message(
            conversation_id="test-conv-seq",
            role="user",
            content="Third message"
        )
        
        assert msg1.sequence_number == 1
        assert msg2.sequence_number == 2
        assert msg3.sequence_number == 3
    
    @pytest.mark.asyncio
    async def test_add_message_invalid_conversation(self, repository):
        """Test adding message to invalid conversation."""
        with pytest.raises(ValueError, match="Conversation not found"):
            await repository.add_message(
                conversation_id="nonexistent-conv",
                role="user",
                content="Test message"
            )
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, repository):
        """Test retrieving conversation messages."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-get-msgs")
        conversation = await repository.create_conversation(
            call_id="test-call-get-msgs",
            conversation_id="test-conv-get-msgs"
        )
        
        # Add messages
        await repository.add_message(
            conversation_id="test-conv-get-msgs",
            role="user",
            content="First message"
        )
        await repository.add_message(
            conversation_id="test-conv-get-msgs",
            role="assistant",
            content="Second message"
        )
        await repository.add_message(
            conversation_id="test-conv-get-msgs",
            role="user",
            content="Third message"
        )
        
        # Get all messages
        messages = await repository.get_conversation_messages("test-conv-get-msgs")
        
        assert len(messages) == 3
        assert messages[0].sequence_number == 1
        assert messages[0].content == "First message"
        assert messages[1].sequence_number == 2
        assert messages[1].content == "Second message"
        assert messages[2].sequence_number == 3
        assert messages[2].content == "Third message"
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_limit(self, repository):
        """Test retrieving conversation messages with limit."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-limit")
        conversation = await repository.create_conversation(
            call_id="test-call-limit",
            conversation_id="test-conv-limit"
        )
        
        # Add messages
        for i in range(5):
            await repository.add_message(
                conversation_id="test-conv-limit",
                role="user",
                content=f"Message {i + 1}"
            )
        
        # Get limited messages
        messages = await repository.get_conversation_messages(
            "test-conv-limit",
            limit=3,
            offset=1
        )
        
        assert len(messages) == 3
        assert messages[0].sequence_number == 2
        assert messages[1].sequence_number == 3
        assert messages[2].sequence_number == 4
    
    @pytest.mark.asyncio
    async def test_get_messages_nonexistent_conversation(self, repository):
        """Test getting messages for nonexistent conversation."""
        messages = await repository.get_conversation_messages("nonexistent-conv")
        assert messages == []


class TestMetricsManagement:
    """Test conversation metrics management."""
    
    @pytest.mark.asyncio
    async def test_update_conversation_metrics(self, repository):
        """Test updating conversation metrics."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-metrics")
        conversation = await repository.create_conversation(
            call_id="test-call-metrics",
            conversation_id="test-conv-metrics"
        )
        
        # Add messages with various metadata
        await repository.add_message(
            conversation_id="test-conv-metrics",
            role="user",
            content="Hello",
            processing_duration_ms=100.0,
            stt_metadata={"confidence": 0.95, "audio_duration": 1.0}
        )
        
        await repository.add_message(
            conversation_id="test-conv-metrics",
            role="assistant",
            content="Hi there!",
            processing_duration_ms=1200.0,
            llm_metadata={
                "tokens_input": 5,
                "tokens_output": 3,
                "cost_usd": 0.0001
            },
            tts_metadata={
                "audio_duration": 1.5,
                "cost_usd": 0.00005
            }
        )
        
        await repository.add_message(
            conversation_id="test-conv-metrics",
            role="user",
            content="How are you?",
            processing_duration_ms=2000.0,  # SLA violation
            stt_metadata={"confidence": 0.90, "audio_duration": 1.2}
        )
        
        # Update metrics
        metrics = await repository.update_conversation_metrics("test-conv-metrics")
        
        assert metrics is not None
        assert metrics.total_messages == 3
        assert metrics.user_messages == 2
        assert metrics.assistant_messages == 1
        assert metrics.avg_response_time_ms == pytest.approx((100.0 + 1200.0 + 2000.0) / 3)
        assert metrics.max_response_time_ms == pytest.approx(2000.0)
        assert metrics.min_response_time_ms == pytest.approx(100.0)
        assert metrics.latency_sla_violations == 1  # One message > 1500ms
        assert metrics.total_input_tokens == 5
        assert metrics.total_output_tokens == 3
        assert metrics.total_llm_cost_usd == pytest.approx(0.0001)
        assert metrics.total_tts_cost_usd == pytest.approx(0.00005)
        assert metrics.total_cost_usd == pytest.approx(0.00015)
        assert metrics.avg_stt_confidence == pytest.approx((0.95 + 0.90) / 2)
        assert metrics.total_audio_duration_seconds == pytest.approx(2.2)  # 1.0 + 1.2
        assert metrics.total_speech_duration_seconds == pytest.approx(1.5)
    
    @pytest.mark.asyncio
    async def test_update_metrics_nonexistent_conversation(self, repository):
        """Test updating metrics for nonexistent conversation."""
        result = await repository.update_conversation_metrics("nonexistent-conv")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_metrics_empty_conversation(self, repository):
        """Test updating metrics for conversation with no messages."""
        # Create parent records
        call = await repository.create_call(call_id="test-call-empty")
        conversation = await repository.create_conversation(
            call_id="test-call-empty",
            conversation_id="test-conv-empty"
        )
        
        # Update metrics (no messages)
        metrics = await repository.update_conversation_metrics("test-conv-empty")
        
        assert metrics is not None
        assert metrics.total_messages == 0
        assert metrics.user_messages == 0
        assert metrics.assistant_messages == 0
        assert metrics.total_cost_usd == 0.0


class TestSystemEvents:
    """Test system event logging."""
    
    @pytest.mark.asyncio
    async def test_log_system_event(self, repository):
        """Test logging a system event."""
        event = await repository.log_system_event(
            event_type="api_error",
            severity="ERROR",
            message="OpenAI API request failed",
            component="openai_client",
            call_id="test-call-123",
            conversation_id="test-conv-123",
            metadata={"error_code": 429, "retry_count": 3},
            stack_trace="Traceback..."
        )
        
        assert event.event_type == "api_error"
        assert event.severity == "ERROR"
        assert event.message == "OpenAI API request failed"
        assert event.component == "openai_client"
        assert event.call_id == "test-call-123"
        assert event.conversation_id == "test-conv-123"
        assert event.event_metadata["error_code"] == 429
        assert event.stack_trace == "Traceback..."
        assert event.event_id is not None
    
    @pytest.mark.asyncio
    async def test_log_system_event_minimal(self, repository):
        """Test logging a minimal system event."""
        event = await repository.log_system_event(
            event_type="info",
            severity="INFO",
            message="System started"
        )
        
        assert event.event_type == "info"
        assert event.severity == "INFO"
        assert event.message == "System started"
        assert event.component is None
        assert event.call_id is None


class TestDataRetention:
    """Test data retention and cleanup."""
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, repository):
        """Test cleaning up old data."""
        # Create old call (older than retention period)
        old_time = datetime.now(timezone.utc) - timedelta(days=35)
        
        # Mock the created_at time by directly inserting
        async with repository.db_manager.get_async_session() as session:
            old_call = Call(
                call_id="old-call",
                created_at=old_time,
                start_time=old_time
            )
            session.add(old_call)
            await session.flush()
            
            # Add conversation and message
            old_conversation = Conversation(
                call_id=old_call.id,
                conversation_id="old-conv",
                created_at=old_time
            )
            session.add(old_conversation)
            await session.flush()
            
            old_message = Message(
                conversation_id=old_conversation.id,
                message_id="old-msg",
                sequence_number=1,
                role="user",
                content="Old message",
                created_at=old_time
            )
            session.add(old_message)
            
            # Add old system event
            old_event = SystemEvent(
                event_id="old-event",
                event_type="test",
                severity="INFO",
                message="Old event",
                timestamp=old_time
            )
            session.add(old_event)
        
        # Create recent call (within retention period)
        recent_call = await repository.create_call(call_id="recent-call")
        
        # Cleanup old data (30 days retention)
        deleted_counts = await repository.cleanup_old_data(retention_days=30)
        
        assert deleted_counts["calls"] == 1  # Old call deleted
        assert deleted_counts["events"] == 1  # Old event deleted
        
        # Verify recent call still exists
        recent_call_check = await repository.get_call("recent-call")
        assert recent_call_check is not None
        
        # Verify old call is gone
        old_call_check = await repository.get_call("old-call")
        assert old_call_check is None


class TestAnalytics:
    """Test analytics and reporting."""
    
    @pytest.mark.asyncio
    async def test_get_call_statistics(self, repository):
        """Test getting call statistics."""
        # Create test data
        now = datetime.now(timezone.utc)
        
        # Create completed call
        call1 = await repository.create_call(call_id="stats-call-1")
        await repository.end_call("stats-call-1")
        
        # Create call with error
        call2 = await repository.create_call(call_id="stats-call-2")
        await repository.end_call("stats-call-2", error_message="Test error")
        
        # Create conversation with metrics
        conversation = await repository.create_conversation(
            call_id="stats-call-1",
            conversation_id="stats-conv-1"
        )
        
        # Add messages
        await repository.add_message(
            conversation_id="stats-conv-1",
            role="user",
            content="Test",
            processing_duration_ms=500.0
        )
        
        await repository.add_message(
            conversation_id="stats-conv-1",
            role="assistant",
            content="Response",
            processing_duration_ms=1200.0,
            llm_metadata={"cost_usd": 0.001}
        )
        
        # Update metrics
        await repository.update_conversation_metrics("stats-conv-1")
        
        # Get statistics
        stats = await repository.get_call_statistics(
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1)
        )
        
        assert stats["calls"]["total"] == 2
        assert stats["calls"]["completed"] == 1
        assert stats["calls"]["success_rate"] == 50.0  # 1 out of 2 completed
        assert stats["performance"]["total_cost_usd"] == 0.001
        assert stats["performance"]["total_messages"] == 2
    
    @pytest.mark.asyncio
    async def test_get_call_statistics_empty(self, repository):
        """Test getting statistics with no data."""
        now = datetime.now(timezone.utc)
        
        stats = await repository.get_call_statistics(
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1)
        )
        
        assert stats["calls"]["total"] == 0
        assert stats["calls"]["completed"] == 0
        assert stats["calls"]["success_rate"] == 0
        assert stats["performance"]["total_cost_usd"] == 0.0
        assert stats["performance"]["total_messages"] == 0
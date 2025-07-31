"""Tests for database models."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Call, Conversation, Message, ConversationMetrics, SystemEvent


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


class TestCallModel:
    """Test the Call model."""
    
    def test_call_creation(self, in_memory_db):
        """Test creating a call record."""
        call = Call(
            call_id="test-call-123",
            caller_number="+1234567890",
            livekit_room="room-123",
            status="active"
        )
        
        in_memory_db.add(call)
        in_memory_db.commit()
        
        # Verify the call was created
        retrieved_call = in_memory_db.query(Call).filter_by(call_id="test-call-123").first()
        assert retrieved_call is not None
        assert retrieved_call.caller_number == "+1234567890"
        assert retrieved_call.status == "active"
        assert retrieved_call.created_at is not None
    
    def test_call_with_metadata(self, in_memory_db):
        """Test call with JSON metadata."""
        call_metadata = {
            "source": "test",
            "priority": "high",
            "tags": ["urgent", "customer"]
        }
        
        call = Call(
            call_id="test-call-metadata",
            call_metadata=call_metadata
        )
        
        in_memory_db.add(call)
        in_memory_db.commit()
        
        retrieved_call = in_memory_db.query(Call).filter_by(call_id="test-call-metadata").first()
        assert retrieved_call.call_metadata == call_metadata
    
    def test_call_duration_calculation(self, in_memory_db):
        """Test call duration calculation."""
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        call = Call(
            call_id="test-call-duration",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration
        )
        
        in_memory_db.add(call)
        in_memory_db.commit()
        
        retrieved_call = in_memory_db.query(Call).filter_by(call_id="test-call-duration").first()
        assert retrieved_call.duration_seconds == duration
    
    def test_call_relationships(self, in_memory_db):
        """Test call relationships with conversations."""
        call = Call(call_id="test-call-rel")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-1"
        )
        in_memory_db.add(conversation)
        in_memory_db.commit()
        
        # Test relationship
        retrieved_call = in_memory_db.query(Call).filter_by(call_id="test-call-rel").first()
        assert len(retrieved_call.conversations) == 1
        assert retrieved_call.conversations[0].conversation_id == "test-conv-1"


class TestConversationModel:
    """Test the Conversation model."""
    
    def test_conversation_creation(self, in_memory_db):
        """Test creating a conversation record."""
        # Create parent call first
        call = Call(call_id="test-call-conv")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-123",
            ai_model="gpt-4",
            system_prompt="You are a helpful assistant"
        )
        
        in_memory_db.add(conversation)
        in_memory_db.commit()
        
        retrieved_conv = in_memory_db.query(Conversation).filter_by(
            conversation_id="test-conv-123"
        ).first()
        assert retrieved_conv is not None
        assert retrieved_conv.ai_model == "gpt-4"
        assert retrieved_conv.system_prompt == "You are a helpful assistant"
    
    def test_conversation_relationships(self, in_memory_db):
        """Test conversation relationships."""
        # Create call and conversation
        call = Call(call_id="test-call-conv-rel")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-rel"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        # Create message
        message = Message(
            conversation_id=conversation.id,
            message_id="test-msg-1",
            sequence_number=1,
            role="user",
            content="Hello"
        )
        in_memory_db.add(message)
        in_memory_db.commit()
        
        # Test relationships
        retrieved_conv = in_memory_db.query(Conversation).filter_by(
            conversation_id="test-conv-rel"
        ).first()
        assert retrieved_conv.call.call_id == "test-call-conv-rel"
        assert len(retrieved_conv.messages) == 1
        assert retrieved_conv.messages[0].content == "Hello"


class TestMessageModel:
    """Test the Message model."""
    
    def test_message_creation(self, in_memory_db):
        """Test creating a message record."""
        # Create parent records
        call = Call(call_id="test-call-msg")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-msg"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        message = Message(
            conversation_id=conversation.id,
            message_id="test-msg-123",
            sequence_number=1,
            role="user",
            content="Hello, how are you?",
            processing_duration_ms=150.5
        )
        
        in_memory_db.add(message)
        in_memory_db.commit()
        
        retrieved_msg = in_memory_db.query(Message).filter_by(
            message_id="test-msg-123"
        ).first()
        assert retrieved_msg is not None
        assert retrieved_msg.role == "user"
        assert retrieved_msg.content == "Hello, how are you?"
        assert retrieved_msg.processing_duration_ms == 150.5
    
    def test_message_with_ai_metadata(self, in_memory_db):
        """Test message with AI service metadata."""
        # Create parent records
        call = Call(call_id="test-call-ai")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-ai"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        message = Message(
            conversation_id=conversation.id,
            message_id="test-msg-ai",
            sequence_number=1,
            role="assistant",
            content="I'm doing well, thank you!",
            llm_model="gpt-4",
            llm_tokens_input=10,
            llm_tokens_output=8,
            llm_cost_usd=0.0002,
            tts_voice_id="voice-123",
            tts_audio_duration=2.5,
            tts_cost_usd=0.0001
        )
        
        in_memory_db.add(message)
        in_memory_db.commit()
        
        retrieved_msg = in_memory_db.query(Message).filter_by(
            message_id="test-msg-ai"
        ).first()
        assert retrieved_msg.llm_model == "gpt-4"
        assert retrieved_msg.llm_tokens_input == 10
        assert retrieved_msg.llm_tokens_output == 8
        assert retrieved_msg.llm_cost_usd == 0.0002
        assert retrieved_msg.tts_voice_id == "voice-123"
        assert retrieved_msg.tts_audio_duration == 2.5
        assert retrieved_msg.tts_cost_usd == 0.0001
    
    def test_message_sequence_constraint(self, in_memory_db):
        """Test unique constraint on conversation_id + sequence_number."""
        # Create parent records
        call = Call(call_id="test-call-seq")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-seq"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        # Create first message
        message1 = Message(
            conversation_id=conversation.id,
            message_id="test-msg-seq-1",
            sequence_number=1,
            role="user",
            content="First message"
        )
        in_memory_db.add(message1)
        in_memory_db.commit()
        
        # Try to create second message with same sequence number
        message2 = Message(
            conversation_id=conversation.id,
            message_id="test-msg-seq-2",
            sequence_number=1,  # Same sequence number
            role="user",
            content="Second message"
        )
        in_memory_db.add(message2)
        
        # This should raise an integrity error
        with pytest.raises(Exception):  # SQLite raises IntegrityError
            in_memory_db.commit()


class TestConversationMetricsModel:
    """Test the ConversationMetrics model."""
    
    def test_metrics_creation(self, in_memory_db):
        """Test creating conversation metrics."""
        # Create parent records
        call = Call(call_id="test-call-metrics")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-metrics"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        metrics = ConversationMetrics(
            conversation_id=conversation.id,
            total_messages=5,
            user_messages=3,
            assistant_messages=2,
            avg_response_time_ms=1200.5,
            total_cost_usd=0.0025,
            avg_stt_confidence=0.95
        )
        
        in_memory_db.add(metrics)
        in_memory_db.commit()
        
        retrieved_metrics = in_memory_db.query(ConversationMetrics).filter_by(
            conversation_id=conversation.id
        ).first()
        assert retrieved_metrics is not None
        assert retrieved_metrics.total_messages == 5
        assert retrieved_metrics.user_messages == 3
        assert retrieved_metrics.assistant_messages == 2
        assert retrieved_metrics.avg_response_time_ms == 1200.5
        assert retrieved_metrics.total_cost_usd == 0.0025
        assert retrieved_metrics.avg_stt_confidence == 0.95
    
    def test_metrics_relationship(self, in_memory_db):
        """Test metrics relationship with conversation."""
        # Create parent records
        call = Call(call_id="test-call-metrics-rel")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-metrics-rel"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        metrics = ConversationMetrics(
            conversation_id=conversation.id,
            total_messages=1
        )
        in_memory_db.add(metrics)
        in_memory_db.commit()
        
        # Test relationship
        retrieved_conv = in_memory_db.query(Conversation).filter_by(
            conversation_id="test-conv-metrics-rel"
        ).first()
        assert retrieved_conv.metrics is not None
        assert retrieved_conv.metrics.total_messages == 1


class TestSystemEventModel:
    """Test the SystemEvent model."""
    
    def test_system_event_creation(self, in_memory_db):
        """Test creating a system event."""
        event = SystemEvent(
            event_id="test-event-123",
            event_type="api_error",
            severity="ERROR",
            message="OpenAI API request failed",
            component="openai_client",
            call_id="test-call-123",
            event_metadata={"error_code": 429, "retry_count": 3}
        )
        
        in_memory_db.add(event)
        in_memory_db.commit()
        
        retrieved_event = in_memory_db.query(SystemEvent).filter_by(
            event_id="test-event-123"
        ).first()
        assert retrieved_event is not None
        assert retrieved_event.event_type == "api_error"
        assert retrieved_event.severity == "ERROR"
        assert retrieved_event.message == "OpenAI API request failed"
        assert retrieved_event.component == "openai_client"
        assert retrieved_event.call_id == "test-call-123"
        assert retrieved_event.event_metadata["error_code"] == 429
    
    def test_system_event_with_stack_trace(self, in_memory_db):
        """Test system event with stack trace."""
        stack_trace = """
        Traceback (most recent call last):
          File "test.py", line 1, in <module>
            raise Exception("Test error")
        Exception: Test error
        """
        
        event = SystemEvent(
            event_id="test-event-stack",
            event_type="exception",
            severity="CRITICAL",
            message="Unhandled exception occurred",
            stack_trace=stack_trace.strip()
        )
        
        in_memory_db.add(event)
        in_memory_db.commit()
        
        retrieved_event = in_memory_db.query(SystemEvent).filter_by(
            event_id="test-event-stack"
        ).first()
        assert retrieved_event.stack_trace is not None
        assert "Exception: Test error" in retrieved_event.stack_trace


class TestModelIndexes:
    """Test that database indexes are working correctly."""
    
    def test_call_indexes(self, in_memory_db):
        """Test that call indexes exist and work."""
        # Create test data
        for i in range(10):
            call = Call(
                call_id=f"test-call-{i}",
                caller_number=f"+123456789{i}",
                status="completed" if i % 2 == 0 else "active"
            )
            in_memory_db.add(call)
        
        in_memory_db.commit()
        
        # Test index on call_id
        result = in_memory_db.query(Call).filter_by(call_id="test-call-5").first()
        assert result is not None
        
        # Test index on status
        completed_calls = in_memory_db.query(Call).filter_by(status="completed").all()
        assert len(completed_calls) == 5
    
    def test_message_indexes(self, in_memory_db):
        """Test that message indexes exist and work."""
        # Create parent records
        call = Call(call_id="test-call-idx")
        in_memory_db.add(call)
        in_memory_db.flush()
        
        conversation = Conversation(
            call_id=call.id,
            conversation_id="test-conv-idx"
        )
        in_memory_db.add(conversation)
        in_memory_db.flush()
        
        # Create test messages
        for i in range(10):
            message = Message(
                conversation_id=conversation.id,
                message_id=f"test-msg-{i}",
                sequence_number=i + 1,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}"
            )
            in_memory_db.add(message)
        
        in_memory_db.commit()
        
        # Test index on role
        user_messages = in_memory_db.query(Message).filter_by(role="user").all()
        assert len(user_messages) == 5
        
        # Test index on sequence number
        messages_ordered = in_memory_db.query(Message).filter_by(
            conversation_id=conversation.id
        ).order_by(Message.sequence_number).all()
        assert len(messages_ordered) == 10
        assert messages_ordered[0].sequence_number == 1
        assert messages_ordered[-1].sequence_number == 10
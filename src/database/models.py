"""Database models for Voice AI Agent conversation logging."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean, 
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func

Base = declarative_base()


class Call(Base):
    """
    Represents a phone call session.
    
    Stores metadata about the entire call including duration,
    caller information, and call status.
    """
    __tablename__ = "calls"
    
    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Call identification
    call_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    caller_number: Mapped[Optional[str]] = Column(String(50), nullable=True, index=True)
    
    # LiveKit integration
    livekit_room: Mapped[Optional[str]] = Column(String(255), nullable=True)
    livekit_participant_id: Mapped[Optional[str]] = Column(String(255), nullable=True)
    
    # Call timing
    start_time: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_time: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Call status and metadata
    status: Mapped[str] = Column(String(50), nullable=False, default="active", index=True)
    call_metadata: Mapped[Optional[Dict[str, Any]]] = Column(JSON, nullable=True)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    error_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="call", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_calls_start_time', 'start_time'),
        Index('idx_calls_status_start_time', 'status', 'start_time'),
    )
    
    def __repr__(self) -> str:
        return f"<Call(id={self.id}, call_id='{self.call_id}', status='{self.status}')>"


class Conversation(Base):
    """
    Represents a conversation within a call.
    
    A call may have multiple conversations if the call is transferred
    or if there are multiple dialogue sessions.
    """
    __tablename__ = "conversations"
    
    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to call
    call_id: Mapped[int] = Column(Integer, ForeignKey("calls.id"), nullable=False, index=True)
    
    # Conversation identification
    conversation_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    
    # Conversation timing
    start_time: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_time: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Conversation status
    status: Mapped[str] = Column(String(50), nullable=False, default="active", index=True)
    
    # AI configuration used
    ai_model: Mapped[Optional[str]] = Column(String(100), nullable=True)
    system_prompt: Mapped[Optional[str]] = Column(Text, nullable=True)
    
    # Conversation summary
    summary: Mapped[Optional[str]] = Column(Text, nullable=True)
    topic: Mapped[Optional[str]] = Column(String(255), nullable=True)
    
    # Quality metrics
    user_satisfaction: Mapped[Optional[int]] = Column(Integer, nullable=True)  # 1-5 scale
    conversation_quality: Mapped[Optional[float]] = Column(Float, nullable=True)  # 0-1 scale
    
    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    call: Mapped["Call"] = relationship("Call", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    metrics: Mapped[Optional["ConversationMetrics"]] = relationship("ConversationMetrics", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_conversations_start_time', 'start_time'),
        Index('idx_conversations_status_start_time', 'status', 'start_time'),
    )
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, conversation_id='{self.conversation_id}', status='{self.status}')>"


class Message(Base):
    """
    Represents individual messages within a conversation.
    
    Stores both user input (transcribed speech) and AI responses,
    along with processing metadata and quality metrics.
    """
    __tablename__ = "messages"
    
    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to conversation
    conversation_id: Mapped[int] = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    
    # Message identification
    message_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    sequence_number: Mapped[int] = Column(Integer, nullable=False)
    
    # Message content
    role: Mapped[str] = Column(String(20), nullable=False, index=True)  # 'user', 'assistant', 'system'
    content: Mapped[str] = Column(Text, nullable=False)
    original_audio_duration: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Processing metadata
    processing_start_time: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    processing_end_time: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    processing_duration_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # STT metadata (for user messages)
    stt_confidence: Mapped[Optional[float]] = Column(Float, nullable=True)
    stt_language: Mapped[Optional[str]] = Column(String(10), nullable=True)
    stt_alternatives: Mapped[Optional[List[str]]] = Column(JSON, nullable=True)
    
    # LLM metadata (for assistant messages)
    llm_model: Mapped[Optional[str]] = Column(String(100), nullable=True)
    llm_tokens_input: Mapped[Optional[int]] = Column(Integer, nullable=True)
    llm_tokens_output: Mapped[Optional[int]] = Column(Integer, nullable=True)
    llm_cost_usd: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # TTS metadata (for assistant messages)
    tts_voice_id: Mapped[Optional[str]] = Column(String(100), nullable=True)
    tts_audio_duration: Mapped[Optional[float]] = Column(Float, nullable=True)
    tts_cost_usd: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Quality metrics
    response_relevance: Mapped[Optional[float]] = Column(Float, nullable=True)  # 0-1 scale
    response_helpfulness: Mapped[Optional[float]] = Column(Float, nullable=True)  # 0-1 scale
    
    # Error tracking
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    retry_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    
    # Additional metadata
    message_metadata: Mapped[Optional[Dict[str, Any]]] = Column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('idx_messages_created_at', 'created_at'),
        Index('idx_messages_role_created_at', 'role', 'created_at'),
        Index('idx_messages_sequence', 'conversation_id', 'sequence_number'),
        UniqueConstraint('conversation_id', 'sequence_number', name='uq_conversation_sequence'),
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role='{self.role}', sequence={self.sequence_number})>"


class ConversationMetrics(Base):
    """
    Aggregated metrics for a conversation.
    
    Stores performance metrics, costs, and quality indicators
    for analysis and monitoring purposes.
    """
    __tablename__ = "conversation_metrics"
    
    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to conversation (one-to-one)
    conversation_id: Mapped[int] = Column(Integer, ForeignKey("conversations.id"), nullable=False, unique=True, index=True)
    
    # Message counts
    total_messages: Mapped[int] = Column(Integer, nullable=False, default=0)
    user_messages: Mapped[int] = Column(Integer, nullable=False, default=0)
    assistant_messages: Mapped[int] = Column(Integer, nullable=False, default=0)
    
    # Timing metrics (in milliseconds)
    avg_response_time_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    max_response_time_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    min_response_time_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    total_processing_time_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Component timing breakdown
    avg_stt_latency_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    avg_llm_latency_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    avg_tts_latency_ms: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Token usage and costs
    total_input_tokens: Mapped[int] = Column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = Column(Integer, nullable=False, default=0)
    total_llm_cost_usd: Mapped[float] = Column(Float, nullable=False, default=0.0)
    total_tts_cost_usd: Mapped[float] = Column(Float, nullable=False, default=0.0)
    total_stt_cost_usd: Mapped[float] = Column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = Column(Float, nullable=False, default=0.0)
    
    # Quality metrics
    avg_stt_confidence: Mapped[Optional[float]] = Column(Float, nullable=True)
    avg_response_relevance: Mapped[Optional[float]] = Column(Float, nullable=True)
    avg_response_helpfulness: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Audio metrics
    total_audio_duration_seconds: Mapped[Optional[float]] = Column(Float, nullable=True)
    total_speech_duration_seconds: Mapped[Optional[float]] = Column(Float, nullable=True)
    
    # Error tracking
    total_errors: Mapped[int] = Column(Integer, nullable=False, default=0)
    total_retries: Mapped[int] = Column(Integer, nullable=False, default=0)
    
    # Performance indicators
    latency_sla_violations: Mapped[int] = Column(Integer, nullable=False, default=0)  # Responses > 1.5s
    quality_threshold_violations: Mapped[int] = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="metrics")
    
    def __repr__(self) -> str:
        return f"<ConversationMetrics(id={self.id}, conversation_id={self.conversation_id}, total_cost=${self.total_cost_usd:.4f})>"


class SystemEvent(Base):
    """
    System events and operational logs.
    
    Tracks system-level events, errors, and operational metrics
    for monitoring and debugging purposes.
    """
    __tablename__ = "system_events"
    
    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event identification
    event_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = Column(String(100), nullable=False, index=True)
    
    # Event details
    severity: Mapped[str] = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: Mapped[str] = Column(Text, nullable=False)
    component: Mapped[Optional[str]] = Column(String(100), nullable=True, index=True)
    
    # Context
    call_id: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    conversation_id: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    
    # Additional data
    event_metadata: Mapped[Optional[Dict[str, Any]]] = Column(JSON, nullable=True)
    stack_trace: Mapped[Optional[str]] = Column(Text, nullable=True)
    
    # Timestamps
    timestamp: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_system_events_timestamp', 'timestamp'),
        Index('idx_system_events_type_timestamp', 'event_type', 'timestamp'),
        Index('idx_system_events_severity_timestamp', 'severity', 'timestamp'),
        Index('idx_system_events_component_timestamp', 'component', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<SystemEvent(id={self.id}, type='{self.event_type}', severity='{self.severity}')>"
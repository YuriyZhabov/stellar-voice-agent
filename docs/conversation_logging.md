# Conversation Logging System

The Voice AI Agent includes a comprehensive conversation logging system that tracks all call data, conversation history, and system metrics in a SQLite database.

## Overview

The conversation logging system consists of several components:

- **Database Models**: Define the structure for calls, conversations, messages, and metrics
- **Repository Layer**: Provides data access methods for database operations
- **Logging Integration**: High-level API for logging conversation data
- **Migration System**: Manages database schema changes

## Database Schema

### Core Tables

1. **calls** - Stores call metadata and session information
2. **conversations** - Tracks individual conversations within calls
3. **messages** - Records all user and assistant messages
4. **conversation_metrics** - Aggregated performance and cost metrics
5. **system_events** - System-level events and operational logs

### Key Features

- **Automatic Metrics Calculation**: Response times, token usage, costs
- **Quality Tracking**: STT confidence, response relevance scores
- **Error Handling**: Comprehensive error logging and recovery
- **Data Retention**: Configurable cleanup policies
- **Performance Monitoring**: SLA violation tracking

## Usage

### Basic Usage

```python
from src.database.logging_integration import get_conversation_logger

# Get the global logger instance
logger = get_conversation_logger()

# Start a call
await logger.start_call(
    call_id="unique_call_id",
    caller_number="+1234567890",
    livekit_room="room_001"
)

# Start a conversation
conversation_id = await logger.start_conversation(
    call_id="unique_call_id",
    ai_model="gpt-4",
    system_prompt="You are a helpful assistant."
)

# Log user message (from STT)
await logger.log_user_message(
    conversation_id=conversation_id,
    content="Hello, can you help me?",
    stt_confidence=0.95,
    processing_time_ms=150.0
)

# Log assistant message (AI response)
await logger.log_assistant_message(
    conversation_id=conversation_id,
    content="Of course! How can I help you?",
    processing_time_ms=1200.0,
    llm_model="gpt-4",
    llm_tokens_input=25,
    llm_tokens_output=18,
    llm_cost_usd=0.0012
)

# End conversation
await logger.end_conversation(
    conversation_id=conversation_id,
    summary="User requested help, assistance provided"
)

# End call
await logger.end_call("unique_call_id")
```

### Advanced Features

#### System Event Logging

```python
await logger.log_event(
    event_type="balance_lookup",
    severity="INFO",
    message="User requested balance lookup",
    component="account_service",
    call_id="unique_call_id",
    conversation_id=conversation_id,
    metadata={"account_type": "checking"}
)
```

#### Conversation History Retrieval

```python
history = await logger.get_conversation_history(
    conversation_id=conversation_id,
    limit=10
)

for message in history:
    print(f"{message['role']}: {message['content']}")
```

#### Statistics and Analytics

```python
# Get call statistics for the last 24 hours
stats = await logger.get_call_statistics(hours=24)

print(f"Total calls: {stats['calls']['total']}")
print(f"Success rate: {stats['calls']['success_rate']:.1f}%")
print(f"Average response time: {stats['performance']['avg_response_time_ms']:.1f}ms")
print(f"Total cost: ${stats['performance']['total_cost_usd']:.4f}")
```

#### Data Cleanup

```python
# Clean up data older than 30 days
deleted_counts = await logger.cleanup_old_data(retention_days=30)
print(f"Deleted {deleted_counts['calls']} old calls")
```

## Database Initialization

The database is automatically initialized when the application starts:

```python
from src.database.connection import init_database
from src.database.migrations import MigrationManager

# Initialize database and run migrations
db_manager = await init_database()
migration_manager = MigrationManager(db_manager)
await migration_manager.migrate_to_latest()
```

## Configuration

Database configuration is managed through environment variables:

```bash
# Database URL (SQLite by default)
DATABASE_URL=sqlite:///./data/voice_ai.db

# Connection pool settings (for PostgreSQL)
DB_POOL_SIZE=10
DB_POOL_OVERFLOW=20

# Data retention
CONVERSATION_LOG_RETENTION_DAYS=30
```

## Metrics and Monitoring

The system automatically tracks:

### Performance Metrics
- Response times (STT, LLM, TTS)
- Processing latencies
- SLA violations (>1.5s responses)

### Cost Tracking
- Token usage (input/output)
- API costs (LLM, TTS, STT)
- Total conversation costs

### Quality Metrics
- STT confidence scores
- Response relevance ratings
- User satisfaction scores

### System Health
- Error rates and types
- Retry attempts
- Connection failures

## Error Handling

The logging system includes comprehensive error handling:

- **Graceful Degradation**: Continues operation even if logging fails
- **Automatic Retry**: Retries failed operations with exponential backoff
- **Error Logging**: All errors are logged to system_events table
- **Recovery**: Automatic recovery from temporary failures

## Best Practices

1. **Always End Sessions**: Ensure calls and conversations are properly ended
2. **Include Metadata**: Add relevant metadata for better analytics
3. **Monitor Costs**: Track token usage and API costs regularly
4. **Clean Up Data**: Implement regular data retention policies
5. **Handle Errors**: Check return values and handle failures gracefully

## Example Application

See `examples/conversation_logging_example.py` for a complete working example that demonstrates all features of the conversation logging system.

## Database Schema Migrations

The system includes a migration framework for schema updates:

```python
from src.database.migrations import MigrationManager

migration_manager = MigrationManager(db_manager)

# Check migration status
status = await migration_manager.get_migration_status()
print(f"Current version: {status['current_version']}")
print(f"Pending migrations: {status['pending_count']}")

# Apply all pending migrations
success = await migration_manager.migrate_to_latest()
```

## Testing

Run the database tests to verify functionality:

```bash
# Run all database tests
python -m pytest tests/test_database/ -v

# Run specific test categories
python -m pytest tests/test_database/test_repository.py -v
python -m pytest tests/test_database/test_logging_integration.py -v
```

## Troubleshooting

### Common Issues

1. **Database Lock Errors**: Ensure proper session management and cleanup
2. **Migration Failures**: Check database permissions and schema conflicts
3. **Performance Issues**: Monitor query performance and add indexes as needed
4. **Storage Space**: Implement data retention policies for large deployments

### Debug Mode

Enable debug logging to see all SQL queries:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

This will show all database operations in the logs for troubleshooting.
# Voice AI Agent - API Reference

## Table of Contents

1. [Core Components](#core-components)
2. [Client Layer](#client-layer)
3. [Configuration Management](#configuration-management)
4. [Health Monitoring](#health-monitoring)
5. [Database Layer](#database-layer)
6. [Conversation Management](#conversation-management)
7. [Monitoring & Metrics](#monitoring--metrics)
8. [Security](#security)

## Core Components

### CallOrchestrator

Central coordinator for managing call lifecycle and component interactions.

#### Class: `CallOrchestrator`

**Constructor:**
```python
CallOrchestrator(
    stt_client: DeepgramSTTClient,
    llm_client: GroqLLMClient,
    tts_client: CartesiaTTSClient,
    max_concurrent_calls: int = 10,
    audio_buffer_size: int = 1024,
    response_timeout: float = 30.0
)
```

**Key Methods:**

##### `async handle_call_start(call_context: CallContext) -> None`
Handle incoming call start event.

**Parameters:**
- `call_context`: Context information for the call

**Example:**
```python
call_context = CallContext(
    call_id="call_123",
    caller_number="+1234567890",
    start_time=datetime.now(UTC),
    livekit_room="room_abc"
)
await orchestrator.handle_call_start(call_context)
```

##### `async handle_audio_received(call_id: str, audio_data: bytes) -> None`
Handle incoming audio data from LiveKit.

**Parameters:**
- `call_id`: Call identifier
- `audio_data`: Raw audio data bytes

##### `async handle_call_end(call_context: CallContext) -> None`
Handle call end event and cleanup resources.

##### `async get_health_status() -> HealthStatus`
Get comprehensive health status of the orchestrator.

**Returns:**
- `HealthStatus`: Health status with component information

**Example:**
```python
health = await orchestrator.get_health_status()
print(f"Status: {health.status}")
print(f"Components: {health.components}")
```

#### Data Classes

##### `CallContext`
```python
@dataclass
class CallContext:
    call_id: str
    caller_number: str
    start_time: datetime
    livekit_room: str
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### `CallMetrics`
```python
@dataclass
class CallMetrics:
    call_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0
    stt_latency: float = 0.0
    llm_latency: float = 0.0
    tts_latency: float = 0.0
    total_turns: int = 0
    successful_turns: int = 0
    failed_turns: int = 0
```

### VoiceAIAgent

Main application class with comprehensive lifecycle management.

#### Class: `VoiceAIAgent`

**Key Methods:**

##### `async async_initialize() -> bool`
Initialize the application with comprehensive validation.

**Returns:**
- `bool`: True if initialization successful

##### `async async_run() -> int`
Run the main application loop.

**Returns:**
- `int`: Exit code (0 for success)

##### `async async_shutdown() -> None`
Perform comprehensive graceful shutdown.

## Client Layer

### BaseResilientClient

Base class for resilient API clients with retry logic and circuit breaker.

#### Class: `BaseResilientClient[T]`

**Constructor:**
```python
BaseResilientClient(
    service_name: str,
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    timeout: float = 30.0
)
```

**Key Methods:**

##### `async execute_with_resilience(operation: Callable, correlation_id: Optional[str] = None) -> T`
Execute operation with retry logic and circuit breaker.

##### `get_health_status() -> Dict[str, Any]`
Get health status of the client.

##### `async health_check() -> bool`
Perform health check for the specific service (abstract method).

#### Configuration Classes

##### `RetryConfig`
```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
```

##### `CircuitBreakerConfig`
```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
```

### DeepgramSTTClient

Deepgram Speech-to-Text client with streaming support.

#### Class: `DeepgramSTTClient(BaseResilientClient[TranscriptionResult])`

**Constructor:**
```python
DeepgramSTTClient(
    api_key: Optional[str] = None,
    timeout: float = 30.0,
    streaming_config: Optional[StreamingConfig] = None
)
```

**Key Methods:**

##### `async transcribe_batch(audio_data: bytes, mimetype: str = "audio/wav", options: Optional[Dict[str, Any]] = None) -> TranscriptionResult`
Transcribe audio data in batch mode.

**Parameters:**
- `audio_data`: Audio data bytes
- `mimetype`: MIME type of audio data
- `options`: Additional transcription options

**Returns:**
- `TranscriptionResult`: Transcription result

**Example:**
```python
client = DeepgramSTTClient()
result = await client.transcribe_batch(
    audio_data=wav_bytes,
    mimetype="audio/wav"
)
print(f"Transcription: {result.text}")
print(f"Confidence: {result.confidence}")
```

##### `async transcribe_stream(audio_stream: AsyncIterator[bytes], connection_id: Optional[str] = None) -> AsyncIterator[TranscriptionResult]`
Transcribe audio stream in real-time.

**Parameters:**
- `audio_stream`: Async iterator of audio data chunks
- `connection_id`: Optional connection identifier

**Yields:**
- `TranscriptionResult`: Streaming transcription results

**Example:**
```python
async def audio_generator():
    # Yield audio chunks
    for chunk in audio_chunks:
        yield chunk

async for result in client.transcribe_stream(audio_generator()):
    if result.is_final:
        print(f"Final: {result.text}")
    else:
        print(f"Interim: {result.text}")
```

#### Data Classes

##### `TranscriptionResult`
```python
@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    language: str
    duration: float
    alternatives: List[str] = field(default_factory=list)
    is_final: bool = True
    channel: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    words: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### `StreamingConfig`
```python
@dataclass
class StreamingConfig:
    model: str = "nova-2"
    language: str = "en-US"
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "linear16"
    interim_results: bool = True
    punctuate: bool = True
    smart_format: bool = True
```

### GroqLLMClient

Groq LLM client with context management and intelligent truncation.

#### Class: `GroqLLMClient(BaseResilientClient[LLMResponse])`

**Constructor:**
```python
GroqLLMClient(
    api_key: Optional[str] = None,
    model: str = "meta-llama/llama-3.1-70b-versatile",
    max_context_tokens: int = 4000,
    max_response_tokens: int = 150,
    temperature: float = 0.7,
    timeout: float = 30.0
)
```

**Key Methods:**

##### `async generate_response(context: ConversationContext, correlation_id: Optional[str] = None) -> LLMResponse`
Generate response using Groq API.

**Parameters:**
- `context`: Conversation context with messages
- `correlation_id`: Optional correlation ID

**Returns:**
- `LLMResponse`: Generated response with metadata

**Example:**
```python
client = GroqLLMClient()
context = client.create_conversation_context(
    system_prompt="You are a helpful assistant."
)
context.add_message(MessageRole.USER, "Hello, how are you?")

response = await client.generate_response(context)
print(f"Response: {response.content}")
print(f"Tokens used: {response.token_usage.total_tokens}")
```

##### `async stream_response(context: ConversationContext, correlation_id: Optional[str] = None) -> AsyncIterator[str]`
Stream response from Groq API for reduced latency.

**Example:**
```python
async for chunk in client.stream_response(context):
    print(chunk, end='', flush=True)
```

##### `create_conversation_context(conversation_id: Optional[str] = None, system_prompt: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> ConversationContext`
Create new conversation context.

##### `optimize_conversation_history(context: ConversationContext) -> None`
Optimize conversation history to maintain context within token limits.

#### Data Classes

##### `LLMResponse`
```python
@dataclass
class LLMResponse:
    content: str
    token_usage: TokenUsage
    model: str
    finish_reason: str
    response_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### `ConversationContext`
```python
@dataclass
class ConversationContext:
    conversation_id: str
    messages: List[Message] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### `TokenUsage`
```python
@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost_estimate(self) -> float:
        """Estimate cost based on Groq pricing."""
```

### CartesiaTTSClient

Cartesia TTS client with streaming audio synthesis capabilities.

#### Class: `CartesiaTTSClient(BaseResilientClient[TTSResponse])`

**Constructor:**
```python
CartesiaTTSClient(
    api_key: Optional[str] = None,
    model_id: str = "sonic-english",
    default_voice_id: Optional[str] = None,
    default_audio_config: Optional[AudioConfig] = None,
    timeout: float = 30.0
)
```

**Key Methods:**

##### `async synthesize_batch(text: str, voice_config: Optional[VoiceConfig] = None, audio_config: Optional[AudioConfig] = None, correlation_id: Optional[str] = None) -> TTSResponse`
Synthesize complete audio in batch mode.

**Parameters:**
- `text`: Text to synthesize
- `voice_config`: Voice configuration
- `audio_config`: Audio format configuration
- `correlation_id`: Request correlation ID

**Returns:**
- `TTSResponse`: Complete TTS response with audio data

**Example:**
```python
client = CartesiaTTSClient()
voice_config = VoiceConfig(
    voice_id="064b17af-d36b-4bfb-b003-be07dba1b649",
    speed=1.0,
    language="en"
)
audio_config = AudioConfig(
    format=AudioFormat.WAV,
    sample_rate=16000
)

response = await client.synthesize_batch(
    text="Hello, how can I help you today?",
    voice_config=voice_config,
    audio_config=audio_config
)

# Save audio to file
with open("output.wav", "wb") as f:
    f.write(response.audio_data)
```

##### `async synthesize_stream(text: str, voice_config: Optional[VoiceConfig] = None, audio_config: Optional[AudioConfig] = None, correlation_id: Optional[str] = None) -> AsyncIterator[bytes]`
Stream audio synthesis for real-time playback.

**Example:**
```python
async for audio_chunk in client.synthesize_stream(
    text="This is streaming audio synthesis.",
    voice_config=voice_config
):
    # Play or process audio chunk in real-time
    await play_audio_chunk(audio_chunk)
```

##### `preprocess_text(text: str) -> str`
Preprocess text for optimal speech synthesis.

##### `async get_available_voices() -> List[Dict[str, Any]]`
Get list of available voices.

#### Data Classes

##### `TTSResponse`
```python
@dataclass
class TTSResponse:
    audio_data: bytes
    duration: float
    format: AudioFormat
    sample_rate: int
    characters_processed: int
    synthesis_time: float
    context_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### `VoiceConfig`
```python
@dataclass
class VoiceConfig:
    voice_id: str
    speed: float = 1.0
    emotion: Optional[str] = None
    language: str = "en"
```

##### `AudioConfig`
```python
@dataclass
class AudioConfig:
    format: AudioFormat = AudioFormat.WAV
    sample_rate: int = 16000
    encoding: Optional[AudioEncoding] = None
    bit_rate: Optional[int] = None
```

## Configuration Management

### Settings

Centralized configuration management with Pydantic validation.

#### Class: `Settings(BaseSettings)`

**Key Properties:**

##### Environment Configuration
- `environment: Environment` - Application environment (development/staging/production/testing)
- `log_level: LogLevel` - Logging level
- `debug: bool` - Enable debug mode

##### Network Configuration
- `domain: str` - Domain name for the voice AI agent
- `public_ip: str` - Public IP address of the server
- `port: int` - Port for the web server

##### SIP Configuration
- `sip_number: Optional[str]` - Phone number assigned to SIP trunk
- `sip_server: Optional[str]` - SIP server hostname or IP address
- `sip_username: Optional[str]` - SIP authentication username
- `sip_password: Optional[str]` - SIP authentication password

##### AI Services Configuration
- `deepgram_api_key: Optional[str]` - Deepgram API key for speech-to-text
- `groq_api_key: Optional[str]` - Groq API key for language model
- `cartesia_api_key: Optional[str]` - Cartesia API key for text-to-speech
- `livekit_api_key: Optional[str]` - LiveKit API key

##### Performance Configuration
- `max_response_latency: float = 1.5` - Maximum response latency in seconds
- `context_window_size: int = 4000` - Context window size for conversation history
- `retry_attempts: int = 3` - Number of retry attempts for failed API calls

**Key Methods:**

##### `get_settings() -> Settings`
Get the global settings instance.

##### `reload_settings() -> Settings`
Reload settings from environment variables.

##### `validate_settings() -> Dict[str, Any]`
Validate current settings and return validation report.

**Example:**
```python
from src.config import get_settings

settings = get_settings()
print(f"Environment: {settings.environment}")
print(f"Debug mode: {settings.debug}")
print(f"Max latency: {settings.max_response_latency}s")

# Validate settings
validation = validate_settings()
if validation['valid']:
    print("Configuration is valid")
else:
    print(f"Configuration error: {validation['error']}")
```

## Health Monitoring

### Health Check Functions

#### `check_health() -> Dict[str, Any]`
Perform comprehensive health checks for the application.

**Returns:**
- `Dict[str, Any]`: Health status information

**Example:**
```python
from src.health import check_health

health = check_health()
print(f"Status: {health['status']}")
print(f"Response time: {health['response_time_ms']}ms")

for check_name, result in health['checks'].items():
    print(f"{check_name}: {result}")
```

#### `comprehensive_health_check() -> Dict[str, Any]`
Perform comprehensive health check including all subsystems.

#### `async comprehensive_health_check_async() -> Dict[str, Any]`
Async version with actual AI service testing.

**Example:**
```python
from src.health import comprehensive_health_check_async

health = await comprehensive_health_check_async()
print(f"Overall status: {health['status']}")
print(f"Health percentage: {health['health_percentage']}%")

if 'failed_checks' in health:
    print(f"Failed checks: {health['failed_checks']}")
```

## Database Layer

### Database Connection Management

#### `async init_database() -> DatabaseManager`
Initialize database connection and return manager.

#### `get_database_manager() -> DatabaseManager`
Get the global database manager instance.

### Models

Database models for conversation logging and system data.

#### `ConversationLog`
```python
class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    
    id: int
    call_id: str
    caller_number: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    transcript: Optional[str]
    ai_responses: Optional[str]
    metadata: Optional[Dict[str, Any]]
```

#### `CallMetrics`
```python
class CallMetrics(Base):
    __tablename__ = "call_metrics"
    
    id: int
    call_id: str
    stt_latency: float
    llm_latency: float
    tts_latency: float
    total_latency: float
    success_rate: float
    created_at: datetime
```

## Conversation Management

### ConversationStateMachine

Manages conversation states and transitions.

#### Class: `ConversationStateMachine`

**Constructor:**
```python
ConversationStateMachine(initial_state: ConversationState = ConversationState.LISTENING)
```

**Key Methods:**

##### `async transition_to(new_state: ConversationState, trigger: str) -> bool`
Transition to a new state with validation.

##### `get_current_state() -> ConversationState`
Get the current conversation state.

##### `can_transition(from_state: ConversationState, to_state: ConversationState) -> bool`
Check if transition is valid.

**Example:**
```python
from src.conversation.state_machine import ConversationStateMachine, ConversationState

state_machine = ConversationStateMachine()
print(f"Current state: {state_machine.get_current_state()}")

# Transition to processing
success = await state_machine.transition_to(
    ConversationState.PROCESSING,
    trigger="audio_received"
)
if success:
    print("Transitioned to PROCESSING state")
```

### DialogueManager

Maintains conversation context and coordinates AI service interactions.

#### Class: `DialogueManager`

**Constructor:**
```python
DialogueManager(
    conversation_id: str,
    llm_client: GroqLLMClient,
    state_machine: ConversationStateMachine,
    max_context_turns: int = 10,
    max_context_tokens: int = 4000
)
```

**Key Methods:**

##### `async process_user_input(text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, ConversationTurn]`
Process user input and generate AI response.

##### `add_to_history(role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None`
Add message to conversation history.

##### `end_conversation() -> ConversationSummary`
End conversation and return summary.

**Example:**
```python
dialogue_manager = DialogueManager(
    conversation_id="conv_123",
    llm_client=groq_client,
    state_machine=state_machine
)

response, turn = await dialogue_manager.process_user_input(
    "Hello, how are you?",
    metadata={"confidence": 0.95}
)
print(f"AI Response: {response}")
```

## Monitoring & Metrics

### Metrics Collection

#### `get_metrics_collector() -> MetricsCollector`
Get the global metrics collector instance.

#### `timer(metric_name: str, labels: Dict[str, str] = None)`
Context manager for timing operations.

**Example:**
```python
from src.metrics import get_metrics_collector, timer

collector = get_metrics_collector()

# Increment counter
collector.increment_counter("api_calls_total", labels={"service": "deepgram"})

# Record histogram
collector.record_histogram("response_time_seconds", 0.5)

# Use timer context manager
with timer("database_query_duration", {"table": "conversations"}):
    result = await db.query("SELECT * FROM conversations")
```

### Health Monitoring

#### `HealthMonitor`
Monitors component health with configurable checks.

#### `AlertManager`
Manages alerts and notifications for system issues.

#### `MetricsExportManager`
Exports metrics to various backends (Prometheus, JSON, etc.).

## Security

### Security Functions

#### `validate_api_key(api_key: str, key_type: APIKeyType) -> ValidationResult`
Validate API key format and structure.

#### `validate_audio_data(audio_data: bytes) -> AudioValidationResult`
Validate audio data for security and format compliance.

#### `generate_secret_key() -> str`
Generate cryptographically strong secret key.

**Example:**
```python
from src.security import validate_api_key, APIKeyType, validate_audio_data

# Validate API key
result = validate_api_key("sk-1234567890abcdef", APIKeyType.OPENAI)
if result.is_valid:
    print("API key is valid")
else:
    print(f"Invalid API key: {result.error_message}")

# Validate audio data
audio_result = validate_audio_data(audio_bytes)
if audio_result.is_valid:
    print(f"Audio format: {audio_result.detected_format}")
    print(f"Duration: {audio_result.duration_estimate}s")
```

### Security Configuration

#### `SecurityConfig`
Configuration class for security settings.

#### `APIKeyType`
Enumeration of supported API key types.

---

*This API reference provides comprehensive documentation for all public interfaces in the Voice AI Agent system. For implementation details and examples, refer to the source code and test files.*
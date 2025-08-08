# Voice AI Agent - Module Documentation

## Table of Contents

1. [Source Code Modules](#source-code-modules)
2. [Configuration Files](#configuration-files)
3. [Scripts and Utilities](#scripts-and-utilities)
4. [Test Modules](#test-modules)
5. [Docker and Deployment](#docker-and-deployment)
6. [Monitoring Configuration](#monitoring-configuration)

## Source Code Modules

### Core Application (`src/`)

#### `src/main.py`
**Purpose:** Main entry point for the Voice AI Agent application with comprehensive lifecycle management.

**Key Classes:**
- `VoiceAIAgent`: Main application class with initialization, running, and shutdown logic

**Key Functions:**
- `async_initialize()`: Comprehensive application initialization with validation
- `async_run()`: Main application loop with health monitoring
- `async_shutdown()`: Graceful shutdown with resource cleanup

**Dependencies:**
- FastAPI for web server
- Uvicorn for ASGI server
- All client modules and orchestrator

**Usage:**
```python
# Run the application
agent = VoiceAIAgent()
exit_code = agent.run()
```

#### `src/orchestrator.py`
**Purpose:** Central coordinator managing call lifecycle and component interactions.

**Key Classes:**
- `CallOrchestrator`: Main orchestration class
- `CallContext`: Call context information
- `CallMetrics`: Performance metrics tracking
- `HealthStatus`: Health status reporting

**Key Features:**
- LiveKit event handling
- Audio stream management
- State machine coordination
- Error handling and fallbacks
- Metrics collection

**Usage:**
```python
orchestrator = CallOrchestrator(
    stt_client=deepgram_client,
    llm_client=groq_client,
    tts_client=cartesia_client
)
await orchestrator.handle_call_start(call_context)
```

#### `src/config.py`
**Purpose:** Centralized configuration management with Pydantic validation.

**Key Classes:**
- `Settings`: Main configuration class with validation
- `Environment`: Environment enumeration
- `LogLevel`: Logging level enumeration
- `SIPTransport`: SIP transport protocol enumeration

**Key Features:**
- Environment variable loading
- Production requirement validation
- API key format validation
- Configuration property accessors

**Configuration Sections:**
- Environment and logging
- Network and domain settings
- SIP configuration
- LiveKit configuration
- AI services (Deepgram, Groq, Cartesia)
- Performance tuning
- Database settings
- Security settings

#### `src/health.py`
**Purpose:** Health check utilities for comprehensive system monitoring.

**Key Functions:**
- `check_health()`: Basic health checks
- `comprehensive_health_check()`: Full system health check
- `check_ai_services_health_async()`: AI service connectivity testing
- `check_database_health()`: Database connectivity check
- `check_redis_health()`: Redis connectivity check

**Health Check Categories:**
- Python version and imports
- Project structure
- Environment configuration
- Disk space and memory
- Database connectivity
- AI service availability

### Client Layer (`src/clients/`)

#### `src/clients/base.py`
**Purpose:** Base resilient client with retry logic and circuit breaker pattern.

**Key Classes:**
- `BaseResilientClient`: Abstract base class for all API clients
- `CircuitBreaker`: Circuit breaker implementation
- `RetryConfig`: Retry logic configuration
- `CircuitBreakerConfig`: Circuit breaker configuration
- `ClientMetrics`: Client performance metrics

**Key Features:**
- Exponential backoff retry logic
- Circuit breaker for service failures
- Request correlation tracking
- Comprehensive metrics collection
- Health status reporting

#### `src/clients/deepgram_stt.py`
**Purpose:** Deepgram Speech-to-Text client with streaming support.

**Key Classes:**
- `DeepgramSTTClient`: Main STT client
- `TranscriptionResult`: Transcription response data
- `StreamingConfig`: Streaming configuration
- `DeepgramMetrics`: Extended metrics

**Key Features:**
- Real-time streaming transcription
- Batch transcription mode
- Automatic reconnection logic
- Confidence scoring
- Audio validation and security

**Supported Features:**
- Multiple audio formats (WAV, MP3, etc.)
- Language detection
- Word-level timestamps
- Alternative transcriptions
- Voice activity detection

#### `src/clients/groq_llm.py`
**Purpose:** Groq LLM client with context management and intelligent truncation.

**Key Classes:**
- `GroqLLMClient`: Main LLM client
- `ConversationContext`: Conversation management
- `LLMResponse`: Response data structure
- `TokenUsage`: Token tracking and cost estimation

**Key Features:**
- Fast inference with Groq infrastructure
- Context window management
- Intelligent conversation truncation
- Token usage monitoring
- Response streaming
- Fallback response generation

**Conversation Management:**
- Multi-turn dialogue support
- Context optimization
- Token limit enforcement
- Conversation history summarization

#### `src/clients/cartesia_tts.py`
**Purpose:** Cartesia TTS client with streaming audio synthesis.

**Key Classes:**
- `CartesiaTTSClient`: Main TTS client
- `TTSResponse`: Synthesis response data
- `VoiceConfig`: Voice configuration
- `AudioConfig`: Audio format configuration
- `TTSUsageStats`: Usage statistics

**Key Features:**
- Streaming audio synthesis
- Multiple audio formats (WAV, MP3, RAW)
- Voice customization options
- Text preprocessing for optimal synthesis
- Telephony-optimized audio formats

**Audio Formats:**
- WAV (16kHz, 8kHz for telephony)
- MP3 with configurable bitrate
- Raw PCM with various encodings
- Telephony-specific formats (μ-law, A-law)

### Conversation Management (`src/conversation/`)

#### `src/conversation/state_machine.py`
**Purpose:** Finite state machine for conversation state management.

**Key Classes:**
- `ConversationStateMachine`: State machine implementation
- `ConversationState`: State enumeration (LISTENING, PROCESSING, SPEAKING)

**Key Features:**
- State transition validation
- Event-driven state changes
- State history tracking
- Error recovery mechanisms

**State Transitions:**
- LISTENING → PROCESSING (on audio received)
- PROCESSING → SPEAKING (on response generated)
- SPEAKING → LISTENING (on response completed)
- Error recovery transitions

#### `src/conversation/dialogue_manager.py`
**Purpose:** Dialogue management and conversation context maintenance.

**Key Classes:**
- `DialogueManager`: Main dialogue management
- `ConversationTurn`: Individual conversation turn
- `ConversationSummary`: Conversation summary data

**Key Features:**
- Conversation history management
- Context preservation across turns
- Response generation coordination
- Conversation analytics
- Turn-level metrics

### Database Layer (`src/database/`)

#### `src/database/connection.py`
**Purpose:** Database connection management and initialization.

**Key Classes:**
- `DatabaseManager`: Database connection manager
- `DatabaseConfig`: Database configuration

**Key Features:**
- SQLite database support
- Connection pooling
- Health monitoring
- Automatic initialization

#### `src/database/models.py`
**Purpose:** SQLAlchemy database models for data persistence.

**Key Models:**
- `ConversationLog`: Conversation logging
- `CallMetrics`: Call performance metrics
- `SystemMetrics`: System performance data

**Key Features:**
- Conversation transcription storage
- Performance metrics tracking
- System health history
- Data retention policies

#### `src/database/repository.py`
**Purpose:** Data access layer with repository pattern.

**Key Classes:**
- `ConversationRepository`: Conversation data access
- `MetricsRepository`: Metrics data access

**Key Features:**
- CRUD operations
- Query optimization
- Data validation
- Transaction management

#### `src/database/migrations.py`
**Purpose:** Database schema migration management.

**Key Classes:**
- `MigrationManager`: Migration execution
- `Migration`: Individual migration definition

**Key Features:**
- Schema versioning
- Automatic migration execution
- Rollback support
- Migration validation

### Monitoring (`src/monitoring/`)

#### `src/monitoring/health_monitor.py`
**Purpose:** Comprehensive health monitoring system.

**Key Classes:**
- `HealthMonitor`: Main health monitoring
- `ComponentType`: Component type enumeration
- `HealthCheck`: Individual health check

**Key Features:**
- Component health tracking
- Automated health checks
- Health status aggregation
- Historical health data

#### `src/monitoring/alerting.py`
**Purpose:** Alert management and notification system.

**Key Classes:**
- `AlertManager`: Alert coordination
- `AlertChannel`: Alert delivery channels
- `WebhookChannel`: Webhook notifications
- `LogChannel`: Log-based alerts

**Key Features:**
- Multi-channel alerting
- Alert throttling
- Severity-based routing
- Alert history tracking

#### `src/monitoring/metrics_exporter.py`
**Purpose:** Metrics export to external systems.

**Key Classes:**
- `MetricsExportManager`: Export coordination
- `PrometheusExporter`: Prometheus integration
- `JSONExporter`: JSON file export

**Key Features:**
- Multiple export formats
- Configurable export intervals
- Export validation
- Error handling

#### `src/monitoring/dashboard.py`
**Purpose:** Dashboard data aggregation and management.

**Key Classes:**
- `DashboardManager`: Dashboard coordination
- `DashboardData`: Dashboard data structure

**Key Features:**
- Real-time data aggregation
- Dashboard data caching
- Performance optimization
- Data visualization support

### Security (`src/middleware/security.py`)
**Purpose:** Security middleware and validation.

**Key Features:**
- Request validation
- Rate limiting
- CORS handling
- Security headers

### Utilities

#### `src/metrics.py`
**Purpose:** Metrics collection and aggregation utilities.

**Key Classes:**
- `MetricsCollector`: Main metrics collection
- `Timer`: Timing context manager

**Key Features:**
- Counter metrics
- Histogram metrics
- Gauge metrics
- Timer utilities

#### `src/logging_config.py`
**Purpose:** Logging configuration and setup.

**Key Features:**
- Structured logging (JSON format)
- Log level configuration
- Correlation ID support
- Production logging optimization

#### `src/security.py`
**Purpose:** Security utilities and validation.

**Key Functions:**
- `validate_api_key()`: API key validation
- `validate_audio_data()`: Audio data validation
- `generate_secret_key()`: Secure key generation

## Configuration Files

### Environment Configuration

#### `.env.template`
**Purpose:** Template for environment variables with documentation.

**Sections:**
- Domain and network settings
- SIP configuration
- LiveKit settings
- AI service API keys
- Performance tuning
- Security settings

#### `.env`, `.env.production`, `.env.test`
**Purpose:** Environment-specific configuration files.

**Usage:**
- `.env`: Development environment
- `.env.production`: Production deployment
- `.env.test`: Testing environment

### Application Configuration

#### `config/production.yaml`
**Purpose:** Production-specific configuration overrides.

**Features:**
- Production logging settings
- Performance optimizations
- Security configurations

#### `livekit-sip.yaml`
**Purpose:** LiveKit SIP integration configuration.

**Features:**
- SIP trunk configuration
- Call routing rules
- Audio codec settings
- Integration parameters

### Project Configuration

#### `pyproject.toml`
**Purpose:** Python project configuration and dependencies.

**Sections:**
- Project metadata
- Dependencies and versions
- Development dependencies
- Build system configuration
- Tool configurations (black, ruff, mypy)

#### `requirements.txt`
**Purpose:** Python dependencies for deployment.

**Features:**
- Production dependencies
- Version pinning
- Deployment optimization

## Scripts and Utilities

### Deployment Scripts (`scripts/`)

#### `scripts/deploy_production.sh`
**Purpose:** Production deployment automation.

**Features:**
- Environment setup
- Docker container deployment
- Health check validation
- Rollback procedures

#### `scripts/setup_production_env.sh`
**Purpose:** Production environment initialization.

**Features:**
- System dependencies
- Security configuration
- Service setup
- Monitoring initialization

#### `scripts/validate_deployment.py`
**Purpose:** Deployment validation and testing.

**Features:**
- Service connectivity testing
- Configuration validation
- Performance benchmarking
- Health check verification

### Monitoring Scripts

#### `scripts/health_monitor.py`
**Purpose:** Standalone health monitoring utility.

**Features:**
- System health checks
- Service status monitoring
- Alert generation
- Health reporting

#### `scripts/monitor_system.py`
**Purpose:** System monitoring and metrics collection.

**Features:**
- Resource utilization monitoring
- Performance metrics
- Log analysis
- Trend reporting

### Utility Scripts

#### `scripts/backup.sh`
**Purpose:** Database and configuration backup.

**Features:**
- Automated backups
- Retention management
- Compression and encryption
- Restore procedures

#### `scripts/cleanup_system.sh`
**Purpose:** System cleanup and maintenance.

**Features:**
- Log rotation
- Temporary file cleanup
- Cache management
- Resource optimization

## Test Modules

### Test Structure (`tests/`)

#### `tests/test_clients/`
**Purpose:** Client implementation testing.

**Test Files:**
- `test_deepgram_stt.py`: STT client testing
- `test_groq_llm.py`: LLM client testing
- `test_cartesia_tts.py`: TTS client testing

**Test Categories:**
- Unit tests with mocked APIs
- Integration tests with real services
- Error handling and resilience
- Performance and latency testing

#### `tests/test_conversation/`
**Purpose:** Conversation management testing.

**Test Files:**
- `test_state_machine.py`: State machine testing
- `test_dialogue_manager.py`: Dialogue management testing

**Test Categories:**
- State transition validation
- Conversation flow testing
- Context management
- Error recovery

#### `tests/test_database/`
**Purpose:** Database layer testing.

**Test Files:**
- `test_connection.py`: Connection management
- `test_models.py`: Model validation
- `test_repository.py`: Data access testing
- `test_migrations.py`: Migration testing

#### Core Tests

#### `tests/test_config.py`
**Purpose:** Configuration validation testing.

**Test Categories:**
- Environment variable loading
- Validation logic
- Production requirements
- Configuration properties

#### `tests/test_health.py`
**Purpose:** Health check system testing.

**Test Categories:**
- Health check functions
- Component health monitoring
- System status reporting
- Error condition handling

#### `tests/test_e2e_integration.py`
**Purpose:** End-to-end integration testing.

**Test Categories:**
- Complete conversation flows
- Multi-service integration
- Performance validation
- Error scenarios

#### `tests/test_load_testing.py`
**Purpose:** Performance and load testing.

**Test Categories:**
- Concurrent call handling
- Resource utilization
- Latency measurement
- Scalability testing

## Docker and Deployment

### Container Configuration

#### `Dockerfile`
**Purpose:** Container image definition for the application.

**Features:**
- Multi-stage build
- Security optimizations
- Health check integration
- Production-ready configuration

#### `docker-compose.yml`
**Purpose:** Development environment orchestration.

**Services:**
- voice-ai-agent: Main application
- redis: Caching and session storage
- Development utilities

#### `docker-compose.prod.yml`
**Purpose:** Production environment orchestration.

**Services:**
- voice-ai-agent: Main application
- prometheus: Metrics collection
- grafana: Visualization
- loki: Log aggregation
- redis: Caching

### Build and Automation

#### `Makefile`
**Purpose:** Development automation and build commands.

**Commands:**
- `make setup`: Environment setup
- `make test`: Test execution
- `make lint`: Code quality checks
- `make run`: Development server
- `make clean`: Cleanup operations

#### `.github/workflows/ci.yml`
**Purpose:** CI/CD pipeline configuration.

**Features:**
- Automated testing
- Code quality checks
- Security scanning
- Deployment automation

## Monitoring Configuration

### Prometheus (`monitoring/prometheus/`)

#### `monitoring/prometheus/prometheus.yml`
**Purpose:** Prometheus server configuration.

**Features:**
- Scrape configurations
- Service discovery
- Alerting rules
- Data retention

#### `monitoring/prometheus/rules/voice-ai-agent.yml`
**Purpose:** Alerting rules for the application.

**Alert Categories:**
- Service availability
- Performance degradation
- Error rate thresholds
- Resource utilization

### Grafana (`monitoring/grafana/`)

#### `monitoring/grafana/dashboards/voice-ai-agent.json`
**Purpose:** Grafana dashboard configuration.

**Dashboard Sections:**
- System overview
- Call metrics
- AI service performance
- Error tracking
- Resource utilization

#### `monitoring/grafana/datasources/prometheus.yml`
**Purpose:** Grafana data source configuration.

### Loki (`monitoring/loki/`)

#### `monitoring/loki/loki.yml`
**Purpose:** Loki log aggregation configuration.

**Features:**
- Log ingestion
- Retention policies
- Query optimization
- Storage configuration

---

*This module documentation provides comprehensive coverage of all components in the Voice AI Agent system. Each module is documented with its purpose, key classes/functions, features, and usage examples.*
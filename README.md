# Voice AI Agent

A production-ready Voice AI Agent system that enables natural voice conversations through telephone calls, integrating multiple AI services (speech-to-text, language processing, text-to-speech) with telephony infrastructure.

## Features

- 🎯 **Low Latency**: Sub-1.5 second response times
- 📞 **Telephony Integration**: SIP trunk support via LiveKit
- 🤖 **AI Services**: Deepgram STT, Groq LLM, Cartesia TTS
- 🔄 **Resilient Architecture**: Circuit breakers, retries, fallbacks
- 📊 **Production Ready**: Monitoring, logging, health checks
- 🐳 **Containerized**: Docker and Docker Compose support
- 🧪 **Well Tested**: Comprehensive test suite with CI/CD

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd voice-ai-agent
   make setup
   ```

2. **Configure Environment**
   ```bash
   cp .env.template .env
   # Edit .env with your API keys and configuration
   ```

3. **Run the Application**
   ```bash
   make run
   ```

## Development

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Make

### Development Setup

```bash
# Set up development environment
make setup

# Run tests
make test

# Format code
make format

# Run linting
make lint

# Start in development mode
make run-dev
```

### Available Commands

Run `make help` to see all available commands.

## Configuration

Copy `.env.template` to `.env` and configure the following:

- **SIP Configuration**: Phone number, SIP server, credentials
- **LiveKit**: Server URL, API keys
- **AI Services**: Deepgram, Groq, Cartesia API keys
- **Performance**: Latency limits, retry settings
- **Monitoring**: Metrics, logging, health checks

## Architecture

The system follows a microservices architecture with:

- **Call Orchestrator**: Central coordinator for call lifecycle
- **Finite State Machine**: Manages conversation states
- **Dialogue Manager**: Maintains conversation context
- **Resilient Clients**: Handle external service integration
- **Monitoring**: Health checks, metrics, logging

## Deployment

### Docker Deployment

```bash
# Build and start with Docker Compose
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

### Production Deployment

1. Configure environment variables for production
2. Set up monitoring and alerting
3. Configure backup and recovery
4. Deploy with Docker Compose or Kubernetes

## Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests
make test-integration

# Generate coverage report
make test-coverage
```

## Monitoring

The system includes comprehensive monitoring:

- **Health Checks**: Application and service health
- **Metrics**: Prometheus metrics for performance monitoring
- **Logging**: Structured logging with correlation IDs
- **Dashboards**: Grafana dashboards for visualization

## License

MIT License - see LICENSE file for details.
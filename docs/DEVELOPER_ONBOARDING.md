# Voice AI Agent - Developer Onboarding Guide

## Welcome to the Voice AI Agent Project! 🎉

This guide will help you get up and running with the Voice AI Agent development environment quickly and efficiently.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Development Environment Setup](#development-environment-setup)
4. [Project Structure Overview](#project-structure-overview)
5. [Development Workflow](#development-workflow)
6. [Testing Guide](#testing-guide)
7. [Debugging and Troubleshooting](#debugging-and-troubleshooting)
8. [Contributing Guidelines](#contributing-guidelines)
9. [Resources and Documentation](#resources-and-documentation)

## Prerequisites

### Required Software

1. **Python 3.12+**
   - Download from [python.org](https://python.org)
   - Verify installation: `python --version`

2. **Docker & Docker Compose**
   - Download from [docker.com](https://docker.com)
   - Verify installation: `docker --version` and `docker-compose --version`

3. **Git**
   - Download from [git-scm.com](https://git-scm.com)
   - Verify installation: `git --version`

### Recommended Tools

1. **IDE/Editor**
   - VS Code (recommended) with Python extension
   - PyCharm Professional/Community
   - Vim/Neovim with Python plugins

2. **Terminal**
   - iTerm2 (macOS)
   - Windows Terminal (Windows)
   - Any modern terminal (Linux)

### API Keys Required

You'll need API keys for the following services:

1. **Deepgram** (Speech-to-Text)
   - Sign up at [deepgram.com](https://deepgram.com)
   - Get API key from dashboard

2. **Groq** (Language Model)
   - Sign up at [groq.com](https://groq.com)
   - Get API key from console

3. **Cartesia** (Text-to-Speech)
   - Sign up at [cartesia.ai](https://cartesia.ai)
   - Get API key from dashboard

4. **LiveKit** (Real-time Communication)
   - Sign up at [livekit.io](https://livekit.io)
   - Get API key and secret from project settings

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd voice-ai-agent
```

### 2. Set Up Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make setup
```

### 3. Configure Environment Variables

```bash
# Copy template and edit with your API keys
cp .env.template .env
nano .env  # or use your preferred editor
```

**Required Environment Variables:**
```bash
# Domain and Network
DOMAIN=localhost
PUBLIC_IP=127.0.0.1
PORT=8000

# AI Services (REQUIRED)
DEEPGRAM_API_KEY=your_deepgram_api_key_here
GROQ_API_KEY=your_groq_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here

# LiveKit (REQUIRED for SIP integration)
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Optional: SIP Configuration (for production)
SIP_NUMBER=+1234567890
SIP_SERVER=sip.example.com
SIP_USERNAME=your_sip_username
SIP_PASSWORD=your_sip_password
```

### 4. Run the Application

```bash
# Start development server
make run

# Or run directly
python -m src.main
```

### 5. Verify Installation

```bash
# Run health check
make health

# Run tests
make test
```

## Development Environment Setup

### IDE Configuration (VS Code)

1. **Install Recommended Extensions:**
   - Python
   - Pylance
   - Black Formatter
   - Ruff
   - Docker
   - YAML

2. **Configure Settings:**
   The project includes `.vscode/settings.json` with optimal settings:
   ```json
   {
     "python.defaultInterpreterPath": "./venv/bin/python",
     "python.formatting.provider": "black",
     "python.linting.enabled": true,
     "python.linting.ruffEnabled": true,
     "python.testing.pytestEnabled": true
   }
   ```

3. **Debug Configuration:**
   Use `.vscode/launch.json` for debugging:
   ```json
   {
     "name": "Voice AI Agent",
     "type": "python",
     "request": "launch",
     "module": "src.main",
     "console": "integratedTerminal",
     "envFile": "${workspaceFolder}/.env"
   }
   ```

### Environment Management

#### Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Deactivate
deactivate
```

#### Dependency Management
```bash
# Install all dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"

# Update requirements
pip freeze > requirements.txt
```

### Docker Development

#### Development with Docker
```bash
# Build development image
docker-compose build

# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f voice-ai-agent

# Stop environment
docker-compose down
```

#### Production Testing
```bash
# Start production stack
docker-compose -f docker-compose.prod.yml up -d

# Monitor services
docker-compose -f docker-compose.prod.yml ps

# View metrics
open http://localhost:3000  # Grafana dashboard
```

## Project Structure Overview

```
voice-ai-agent/
├── src/                        # Main application source
│   ├── clients/               # AI service clients
│   │   ├── base.py           # Base resilient client
│   │   ├── deepgram_stt.py   # Speech-to-text client
│   │   ├── groq_llm.py       # Language model client
│   │   └── cartesia_tts.py   # Text-to-speech client
│   ├── conversation/         # Conversation management
│   │   ├── state_machine.py  # State machine
│   │   └── dialogue_manager.py # Dialogue management
│   ├── database/             # Database layer
│   ├── monitoring/           # Health and metrics
│   ├── main.py              # Application entry point
│   ├── orchestrator.py      # Call orchestration
│   ├── config.py            # Configuration management
│   └── health.py            # Health checks
├── tests/                    # Test suite
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── monitoring/              # Monitoring configs
├── security/                # Security utilities
├── docker-compose.yml       # Development environment
├── Dockerfile              # Container definition
├── Makefile                # Development commands
└── pyproject.toml          # Project configuration
```

### Key Directories

- **`src/`**: Main application code
- **`src/clients/`**: AI service integrations
- **`src/conversation/`**: Conversation logic
- **`tests/`**: Comprehensive test suite
- **`docs/`**: Project documentation
- **`scripts/`**: Deployment and utility scripts
- **`monitoring/`**: Prometheus, Grafana, Loki configs

## Development Workflow

### Daily Development

1. **Start Your Day**
   ```bash
   # Activate environment
   source venv/bin/activate
   
   # Pull latest changes
   git pull origin main
   
   # Update dependencies if needed
   make setup
   
   # Run health check
   make health
   ```

2. **Development Cycle**
   ```bash
   # Make your changes
   # ...
   
   # Format code
   make format
   
   # Run linting
   make lint
   
   # Run tests
   make test
   
   # Test specific module
   pytest tests/test_clients/test_groq_llm.py -v
   ```

3. **Before Committing**
   ```bash
   # Run full test suite
   make test
   
   # Check code quality
   make lint
   
   # Verify health checks pass
   make health
   ```

### Git Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes and Commit**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

3. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Code Style Guidelines

#### Python Code Style
- Use **Black** for formatting (configured in `pyproject.toml`)
- Use **Ruff** for linting
- Follow **PEP 8** conventions
- Use **type hints** for all functions
- Write **docstrings** for all public functions

#### Example Code Style
```python
"""Module docstring describing the purpose."""

import asyncio
import logging
from typing import Dict, List, Optional

from src.config import get_settings


class ExampleClass:
    """Class docstring describing the purpose."""
    
    def __init__(self, param: str, optional_param: Optional[int] = None):
        """Initialize the class.
        
        Args:
            param: Description of parameter
            optional_param: Optional parameter description
        """
        self.param = param
        self.optional_param = optional_param
        self.logger = logging.getLogger(__name__)
    
    async def async_method(self, data: Dict[str, str]) -> List[str]:
        """Async method with proper typing.
        
        Args:
            data: Input data dictionary
            
        Returns:
            List of processed strings
            
        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
        
        self.logger.info(f"Processing {len(data)} items")
        
        # Process data
        results = []
        for key, value in data.items():
            processed = await self._process_item(key, value)
            results.append(processed)
        
        return results
    
    async def _process_item(self, key: str, value: str) -> str:
        """Private method for processing individual items."""
        return f"{key}: {value.upper()}"
```

## Testing Guide

### Test Structure

```
tests/
├── test_clients/              # Client tests
│   ├── test_deepgram_stt.py
│   ├── test_groq_llm.py
│   └── test_cartesia_tts.py
├── test_conversation/         # Conversation tests
├── test_database/            # Database tests
├── test_config.py           # Configuration tests
├── test_health.py           # Health check tests
├── test_e2e_integration.py  # End-to-end tests
└── test_load_testing.py     # Performance tests
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_config.py -v

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run tests matching pattern
pytest -k "test_health" -v

# Run tests in parallel
pytest -n auto
```

### Writing Tests

#### Unit Test Example
```python
import pytest
from unittest.mock import AsyncMock, patch

from src.clients.groq_llm import GroqLLMClient, ConversationContext


class TestGroqLLMClient:
    """Test suite for GroqLLMClient."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return GroqLLMClient(api_key="test-key")
    
    @pytest.fixture
    def conversation_context(self, client):
        """Create test conversation context."""
        return client.create_conversation_context(
            conversation_id="test-conv",
            system_prompt="You are a test assistant."
        )
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, client, conversation_context):
        """Test successful response generation."""
        # Add user message
        conversation_context.add_message("user", "Hello")
        
        # Mock the API response
        with patch.object(client.client.chat.completions, 'create') as mock_create:
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = "Hello! How can I help?"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 8
            mock_response.usage.total_tokens = 18
            mock_create.return_value = mock_response
            
            # Test the method
            response = await client.generate_response(conversation_context)
            
            # Assertions
            assert response.content == "Hello! How can I help?"
            assert response.token_usage.total_tokens == 18
            assert response.finish_reason == "stop"
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check functionality."""
        with patch.object(client, 'generate_response') as mock_generate:
            mock_generate.return_value = AsyncMock(content="Test response")
            
            result = await client.health_check()
            assert result is True
```

#### Integration Test Example
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_conversation_flow():
    """Test complete conversation flow with real services."""
    # This test requires API keys to be configured
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not configured")
    
    # Initialize clients
    groq_client = GroqLLMClient()
    
    # Create conversation
    context = groq_client.create_conversation_context(
        system_prompt="You are a helpful assistant. Keep responses brief."
    )
    context.add_message("user", "Say hello")
    
    # Generate response
    response = await groq_client.generate_response(context)
    
    # Verify response
    assert response.content
    assert len(response.content) > 0
    assert response.token_usage.total_tokens > 0
```

### Test Categories

1. **Unit Tests**: Test individual functions/methods in isolation
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test complete workflows
4. **Performance Tests**: Test system performance and scalability
5. **Security Tests**: Test input validation and security measures

## Debugging and Troubleshooting

### Common Issues and Solutions

#### 1. API Key Issues
**Problem:** `ValueError: API key is required`

**Solution:**
```bash
# Check if API keys are set
echo $DEEPGRAM_API_KEY
echo $GROQ_API_KEY
echo $CARTESIA_API_KEY

# If not set, add to .env file
echo "DEEPGRAM_API_KEY=your_key_here" >> .env
```

#### 2. Import Errors
**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Ensure you're in the project root
pwd

# Install in development mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 3. Docker Issues
**Problem:** Container fails to start

**Solution:**
```bash
# Check container logs
docker-compose logs voice-ai-agent

# Rebuild containers
docker-compose build --no-cache

# Check port conflicts
netstat -tulpn | grep :8000
```

#### 4. Database Issues
**Problem:** Database connection errors

**Solution:**
```bash
# Check database file permissions
ls -la data/voice_ai.db

# Reset database
rm data/voice_ai.db
python -c "from src.database.migrations import MigrationManager; import asyncio; asyncio.run(MigrationManager().migrate_to_latest())"
```

### Debugging Tools

#### 1. Logging
```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Use structured logging
logger = logging.getLogger(__name__)
logger.info("Debug message", extra={"key": "value"})
```

#### 2. Python Debugger
```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint (Python 3.7+)
breakpoint()
```

#### 3. VS Code Debugging
- Set breakpoints in VS Code
- Use F5 to start debugging
- Use debug console for interactive debugging

#### 4. Health Checks
```bash
# Check system health
make health

# Check specific components
python -c "from src.health import check_ai_services_health; print(check_ai_services_health())"
```

### Performance Profiling

#### 1. Basic Profiling
```python
import cProfile
import pstats

# Profile a function
cProfile.run('your_function()', 'profile_stats')
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative').print_stats(10)
```

#### 2. Memory Profiling
```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler your_script.py
```

#### 3. Async Profiling
```python
import asyncio
import time

async def profile_async_function():
    start_time = time.time()
    result = await your_async_function()
    end_time = time.time()
    print(f"Function took {end_time - start_time:.3f} seconds")
    return result
```

## Contributing Guidelines

### Code Review Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/descriptive-name
   ```

2. **Make Changes**
   - Follow code style guidelines
   - Add tests for new functionality
   - Update documentation if needed

3. **Pre-commit Checks**
   ```bash
   make lint    # Check code style
   make test    # Run test suite
   make health  # Verify system health
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add descriptive commit message"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/descriptive-name
   # Create pull request on GitHub
   ```

### Commit Message Format

Use conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(clients): add Groq LLM client with streaming support

fix(orchestrator): handle audio buffer overflow correctly

docs(api): update API reference with new endpoints

test(integration): add end-to-end conversation tests
```

### Pull Request Guidelines

1. **PR Title**: Use conventional commit format
2. **Description**: Explain what and why
3. **Testing**: Describe how you tested the changes
4. **Documentation**: Update docs if needed
5. **Breaking Changes**: Clearly mark any breaking changes

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance impact considered
- [ ] Error handling is appropriate
- [ ] Logging is adequate

## Resources and Documentation

### Project Documentation

- **[API Reference](API_REFERENCE.md)**: Comprehensive API documentation
- **[Module Documentation](MODULE_DOCUMENTATION.md)**: Detailed module descriptions
- **[Project Documentation](PROJECT_DOCUMENTATION.md)**: High-level project overview
- **[Deployment Guide](deployment_guide.md)**: Production deployment instructions
- **[Monitoring Guide](monitoring_system.md)**: Monitoring and observability setup

### External Resources

#### AI Services Documentation
- **Deepgram**: [docs.deepgram.com](https://docs.deepgram.com)
- **Groq**: [console.groq.com/docs](https://console.groq.com/docs)
- **Cartesia**: [docs.cartesia.ai](https://docs.cartesia.ai)
- **LiveKit**: [docs.livekit.io](https://docs.livekit.io)

#### Python Resources
- **Python Documentation**: [docs.python.org](https://docs.python.org)
- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Pydantic**: [docs.pydantic.dev](https://docs.pydantic.dev)
- **SQLAlchemy**: [docs.sqlalchemy.org](https://docs.sqlalchemy.org)

#### Development Tools
- **Docker**: [docs.docker.com](https://docs.docker.com)
- **Pytest**: [docs.pytest.org](https://docs.pytest.org)
- **Black**: [black.readthedocs.io](https://black.readthedocs.io)
- **Ruff**: [docs.astral.sh/ruff](https://docs.astral.sh/ruff)

### Getting Help

1. **Check Documentation**: Start with project docs
2. **Search Issues**: Look for similar issues on GitHub
3. **Ask Questions**: Create a GitHub issue with the "question" label
4. **Join Discussions**: Participate in GitHub discussions
5. **Contact Team**: Reach out to project maintainers

### Development Tips

1. **Use Virtual Environments**: Always work in a virtual environment
2. **Write Tests First**: Consider test-driven development
3. **Keep PRs Small**: Smaller PRs are easier to review
4. **Document Your Code**: Write clear docstrings and comments
5. **Monitor Performance**: Use profiling tools to identify bottlenecks
6. **Security First**: Always validate inputs and handle secrets securely

---

**Welcome to the team! 🚀**

This guide should get you started with Voice AI Agent development. If you have questions or run into issues, don't hesitate to ask for help. Happy coding!
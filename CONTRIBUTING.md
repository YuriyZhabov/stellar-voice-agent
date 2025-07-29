# Contributing to Voice AI Agent

Thank you for your interest in contributing to the Voice AI Agent project! This document provides guidelines and information for contributors.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd voice-ai-agent
   ```

2. **Set up development environment**
   ```bash
   make setup
   ```

3. **Configure environment**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

4. **Verify setup**
   ```bash
   make health
   make test
   ```

## Development Workflow

### Code Quality

We maintain high code quality standards:

- **Formatting**: Code is formatted with Black (88 character line length)
- **Linting**: We use Ruff for fast Python linting
- **Type Checking**: MyPy is used for static type checking
- **Testing**: Comprehensive test coverage with pytest

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
pre-commit install
```

This will run formatting, linting, and type checking before each commit.

### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
make test-unit
make test-integration

# Run with coverage
make test-coverage
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Use meaningful variable and function names

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

Examples:
```
feat(stt): add Deepgram streaming support
fix(health): handle missing psutil dependency
docs(readme): update installation instructions
```

## Testing Guidelines

### Test Categories

- **Unit Tests**: Test individual functions/classes in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

### Test Structure

```python
def test_function_name():
    """Test description explaining what is being tested."""
    # Arrange
    setup_data = create_test_data()
    
    # Act
    result = function_under_test(setup_data)
    
    # Assert
    assert result == expected_value
```

### Mocking

Use pytest-mock for mocking external dependencies:

```python
def test_api_call(mocker):
    """Test API call with mocked response."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"status": "success"}
    
    mocker.patch("requests.get", return_value=mock_response)
    
    result = api_function()
    assert result["status"] == "success"
```

## Architecture Guidelines

### Project Structure

```
src/
├── __init__.py
├── main.py              # Application entry point
├── health.py            # Health check utilities
├── config/              # Configuration management
├── clients/             # External service clients
├── core/                # Core business logic
├── models/              # Data models
└── utils/               # Utility functions

tests/
├── __init__.py
├── unit/                # Unit tests
├── integration/         # Integration tests
└── fixtures/            # Test fixtures
```

### Design Principles

1. **Dependency Injection**: Use dependency injection for loose coupling
2. **Single Responsibility**: Each class/function should have one responsibility
3. **Error Handling**: Implement comprehensive error handling with proper logging
4. **Configuration**: Use environment variables for configuration
5. **Monitoring**: Include metrics and health checks for all components

## API Guidelines

### Error Handling

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def api_function() -> Optional[dict]:
    """Example API function with proper error handling."""
    try:
        result = await external_api_call()
        return result
    except ExternalAPIError as e:
        logger.error(f"External API error: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error in api_function: {e}")
        raise
```

### Logging

Use structured logging with correlation IDs:

```python
import structlog

logger = structlog.get_logger(__name__)

def process_call(call_id: str):
    """Process a call with structured logging."""
    logger.info("Processing call", call_id=call_id)
    
    try:
        # Process call
        logger.info("Call processed successfully", call_id=call_id)
    except Exception as e:
        logger.error("Call processing failed", call_id=call_id, error=str(e))
        raise
```

## Performance Guidelines

### Latency Requirements

- End-to-end response time: < 1.5 seconds
- Health check response: < 100ms
- Database queries: < 50ms average

### Memory Management

- Monitor memory usage in long-running processes
- Use connection pooling for database connections
- Implement proper cleanup in async contexts

## Security Guidelines

### API Keys and Secrets

- Never commit API keys or secrets to version control
- Use environment variables for all sensitive configuration
- Rotate API keys regularly
- Use least-privilege access principles

### Input Validation

- Validate all input data using Pydantic models
- Sanitize user input to prevent injection attacks
- Implement rate limiting for API endpoints

## Documentation

### Code Documentation

- Write clear docstrings for all public functions
- Include type hints for better IDE support
- Document complex algorithms and business logic

### API Documentation

- Use OpenAPI/Swagger for API documentation
- Include examples for all endpoints
- Document error responses and status codes

## Release Process

1. **Feature Development**
   - Create feature branch from `develop`
   - Implement feature with tests
   - Create pull request to `develop`

2. **Code Review**
   - All code must be reviewed by at least one other developer
   - Ensure tests pass and coverage is maintained
   - Check for security vulnerabilities

3. **Integration Testing**
   - Merge to `develop` branch
   - Run full integration test suite
   - Deploy to staging environment

4. **Release**
   - Create release branch from `develop`
   - Update version numbers and changelog
   - Merge to `main` and tag release
   - Deploy to production

## Getting Help

- Check existing issues and documentation first
- Create detailed issue reports with reproduction steps
- Join our development discussions
- Follow coding standards and contribution guidelines

Thank you for contributing to Voice AI Agent! 🎉
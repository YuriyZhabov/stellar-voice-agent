"""Test configuration management."""

import pytest
import os
from pathlib import Path


def test_env_template_format():
    """Test that .env.template has proper format."""
    project_root = Path(__file__).parent.parent
    env_template = project_root / ".env.template"
    
    content = env_template.read_text()
    lines = content.split('\n')
    
    # Check for proper sections
    sections = [
        "ENVIRONMENT CONFIGURATION",
        "DOMAIN AND NETWORK CONFIGURATION", 
        "SIP CONFIGURATION",
        "LIVEKIT CONFIGURATION",
        "AI SERVICES CONFIGURATION"
    ]
    
    for section in sections:
        assert any(section in line for line in lines), f"Section {section} not found"


def test_pyproject_toml_structure():
    """Test that pyproject.toml has required sections."""
    project_root = Path(__file__).parent.parent
    
    # This is a basic test - in real implementation we'd parse TOML
    pyproject_file = project_root / "pyproject.toml"
    content = pyproject_file.read_text()
    
    required_sections = [
        "[build-system]",
        "[project]", 
        "[project.optional-dependencies]",
        "[tool.black]",
        "[tool.ruff]",
        "[tool.mypy]",
        "[tool.pytest.ini_options]"
    ]
    
    for section in required_sections:
        assert section in content, f"Required section {section} not found in pyproject.toml"


def test_dependencies_present():
    """Test that required dependencies are listed."""
    project_root = Path(__file__).parent.parent
    pyproject_file = project_root / "pyproject.toml"
    content = pyproject_file.read_text()
    
    required_deps = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "openai",
        "deepgram-sdk",
        "cartesia",
        "livekit"
    ]
    
    for dep in required_deps:
        assert dep in content, f"Required dependency {dep} not found"


def test_dev_dependencies():
    """Test that development dependencies are present."""
    project_root = Path(__file__).parent.parent
    pyproject_file = project_root / "pyproject.toml"
    content = pyproject_file.read_text()
    
    dev_deps = [
        "pytest",
        "black", 
        "ruff",
        "mypy"
    ]
    
    for dep in dev_deps:
        assert dep in content, f"Required dev dependency {dep} not found"


@pytest.mark.unit
def test_environment_loading():
    """Test environment variable loading logic."""
    # This would test actual configuration loading
    # For now, just test that we can access environment
    
    # Test that we can set and get environment variables
    test_var = "TEST_VOICE_AI_VAR"
    test_value = "test_value_123"
    
    os.environ[test_var] = test_value
    assert os.getenv(test_var) == test_value
    
    # Clean up
    del os.environ[test_var]


def test_docker_compose_services():
    """Test that docker-compose.yml has required services."""
    project_root = Path(__file__).parent.parent
    compose_file = project_root / "docker-compose.yml"
    content = compose_file.read_text()
    
    required_services = [
        "voice-ai-agent:",
        "redis:",
        "prometheus:",
        "grafana:"
    ]
    
    for service in required_services:
        assert service in content, f"Required service {service} not found in docker-compose.yml"
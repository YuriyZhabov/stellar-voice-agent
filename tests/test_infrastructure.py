"""Test infrastructure and basic functionality."""

import pytest
import sys
import os
from pathlib import Path


def test_python_version():
    """Test that Python version is 3.11 or higher."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version_info}"


def test_project_structure():
    """Test that required project directories exist."""
    project_root = Path(__file__).parent.parent
    
    required_dirs = [
        "src",
        "tests", 
        "config",
        ".github/workflows"
    ]
    
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        assert dir_path.exists(), f"Required directory {dir_name} not found"
        assert dir_path.is_dir(), f"{dir_name} is not a directory"


def test_required_files():
    """Test that required configuration files exist."""
    project_root = Path(__file__).parent.parent
    
    required_files = [
        "pyproject.toml",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        ".env.template",
        "README.md",
        ".gitignore"
    ]
    
    for file_name in required_files:
        file_path = project_root / file_name
        assert file_path.exists(), f"Required file {file_name} not found"
        assert file_path.is_file(), f"{file_name} is not a file"


def test_environment_template():
    """Test that environment template contains required variables."""
    project_root = Path(__file__).parent.parent
    env_template = project_root / ".env.template"
    
    content = env_template.read_text()
    
    required_vars = [
        "DEEPGRAM_API_KEY",
        "OPENAI_API_KEY", 
        "CARTESIA_API_KEY",
        "LIVEKIT_URL",
        "SIP_NUMBER",
        "DEEPGRAM_LANGUAGE"
    ]
    
    for var in required_vars:
        assert var in content, f"Required environment variable {var} not found in template"


def test_imports():
    """Test that basic imports work."""
    try:
        import src
        import src.health
        import src.main
    except ImportError as e:
        pytest.fail(f"Failed to import basic modules: {e}")


def test_package_structure():
    """Test that packages have __init__.py files."""
    project_root = Path(__file__).parent.parent
    
    packages = ["src", "tests", "config"]
    
    for package in packages:
        init_file = project_root / package / "__init__.py"
        assert init_file.exists(), f"Package {package} missing __init__.py"


@pytest.mark.slow
def test_docker_build():
    """Test that Docker image can be built (slow test)."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "build", "-t", "voice-ai-agent-test", "."],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        pytest.fail("Docker build timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available")


def test_makefile_targets():
    """Test that Makefile has required targets."""
    project_root = Path(__file__).parent.parent
    makefile = project_root / "Makefile"
    
    content = makefile.read_text()
    
    required_targets = [
        "help:",
        "setup:",
        "test:",
        "lint:",
        "format:",
        "run:",
        "health:",
        "clean:"
    ]
    
    for target in required_targets:
        assert target in content, f"Required Makefile target {target} not found"
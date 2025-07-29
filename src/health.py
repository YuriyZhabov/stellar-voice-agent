"""Health check utilities for the Voice AI Agent."""

import sys
import os
import time
import platform
from typing import Dict, Any, Optional
from pathlib import Path


def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health checks for the application.
    
    Returns:
        Dict containing health status information
    """
    start_time = time.time()
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.1.0",
        "python_version": sys.version,
        "platform": platform.platform(),
        "checks": {}
    }
    
    # Check Python version
    try:
        if sys.version_info >= (3, 11):
            health_status["checks"]["python_version"] = "ok"
            health_status["checks"]["python"] = "ok"  # For backward compatibility
        else:
            health_status["checks"]["python_version"] = f"warning: {sys.version_info}"
            health_status["checks"]["python"] = f"warning: {sys.version_info}"
    except Exception as e:
        health_status["checks"]["python_version"] = f"failed: {e}"
        health_status["checks"]["python"] = f"failed: {e}"
        health_status["status"] = "unhealthy"
    
    # Check basic imports
    try:
        import asyncio
        import json
        import pathlib
        health_status["checks"]["basic_imports"] = "ok"
        health_status["checks"]["imports"] = "ok"  # For backward compatibility
    except ImportError as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["basic_imports"] = f"failed: {e}"
        health_status["checks"]["imports"] = f"failed: {e}"
    
    # Check project structure
    try:
        project_root = Path(__file__).parent.parent
        required_dirs = ["src", "tests", "config"]
        missing_dirs = []
        
        for dir_name in required_dirs:
            if not (project_root / dir_name).exists():
                missing_dirs.append(dir_name)
        
        if missing_dirs:
            health_status["checks"]["project_structure"] = f"missing: {missing_dirs}"
            health_status["status"] = "degraded"
        else:
            health_status["checks"]["project_structure"] = "ok"
    except Exception as e:
        health_status["checks"]["project_structure"] = f"failed: {e}"
        health_status["status"] = "unhealthy"
    
    # Check environment configuration
    try:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            health_status["checks"]["environment"] = "ok"
        else:
            health_status["checks"]["environment"] = "warning: .env file not found"
    except Exception as e:
        health_status["checks"]["environment"] = f"failed: {e}"
    
    # Check disk space
    try:
        disk_usage = os.statvfs('/')
        free_space_gb = (disk_usage.f_bavail * disk_usage.f_frsize) / (1024**3)
        
        if free_space_gb > 1.0:  # More than 1GB free
            health_status["checks"]["disk_space"] = f"ok: {free_space_gb:.1f}GB free"
        else:
            health_status["checks"]["disk_space"] = f"warning: {free_space_gb:.1f}GB free"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["disk_space"] = f"failed: {e}"
    
    # Check memory usage
    try:
        import psutil
        memory = psutil.virtual_memory()
        memory_usage_percent = memory.percent
        
        if memory_usage_percent < 80:
            health_status["checks"]["memory"] = f"ok: {memory_usage_percent:.1f}% used"
        else:
            health_status["checks"]["memory"] = f"warning: {memory_usage_percent:.1f}% used"
            health_status["status"] = "degraded"
    except ImportError:
        health_status["checks"]["memory"] = "skipped: psutil not available"
    except Exception as e:
        health_status["checks"]["memory"] = f"failed: {e}"
    
    # Calculate response time
    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    health_status["response_time_ms"] = round(response_time, 2)
    
    if response_time > 1000:  # More than 1 second
        health_status["status"] = "degraded"
    
    return health_status


def check_dependencies() -> Dict[str, str]:
    """
    Check if required dependencies are available.
    
    Returns:
        Dict mapping dependency names to their status
    """
    dependencies = {
        "fastapi": "optional",
        "uvicorn": "optional", 
        "pydantic": "optional",
        "openai": "optional",
        "deepgram": "optional",
        "cartesia": "optional",
        "livekit": "optional",
        "sqlalchemy": "optional",
        "redis": "optional"
    }
    
    status = {}
    
    for dep, importance in dependencies.items():
        try:
            __import__(dep.replace("-", "_"))
            status[dep] = "available"
        except ImportError:
            status[dep] = f"missing ({importance})"
    
    return status


def get_system_info() -> Dict[str, Any]:
    """
    Get detailed system information.
    
    Returns:
        Dict containing system information
    """
    info = {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform
        },
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture()
        },
        "environment": {
            "cwd": os.getcwd(),
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown")
        }
    }
    
    try:
        import psutil
        info["resources"] = {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2)
        }
    except ImportError:
        info["resources"] = "psutil not available"
    
    return info


if __name__ == "__main__":
    status = check_health()
    
    print(f"🏥 Voice AI Agent Health Check")
    print(f"Status: {status['status'].upper()}")
    print(f"Response time: {status['response_time_ms']}ms")
    print()
    
    for check_name, result in status["checks"].items():
        icon = "✅" if result == "ok" or result.startswith("ok:") else "⚠️" if "warning" in result else "❌"
        print(f"{icon} {check_name}: {result}")
    
    if status["status"] == "healthy":
        print("\n🎉 All systems operational!")
        sys.exit(0)
    elif status["status"] == "degraded":
        print("\n⚠️ System operational with warnings")
        sys.exit(0)
    else:
        print("\n💥 System unhealthy!")
        sys.exit(1)
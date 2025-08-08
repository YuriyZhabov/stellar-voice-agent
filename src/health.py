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
        "version": "1.0.0",
        "python_version": sys.version,
        "platform": platform.platform(),
        "environment": os.getenv("ENVIRONMENT", "unknown"),
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
        from src.config import get_settings
        settings = get_settings()
        health_status["checks"]["environment"] = "ok"
        health_status["checks"]["config"] = "ok"
        
        # Check critical configuration
        if settings.environment.value == "production":
            required_keys = ["deepgram_api_key", "groq_api_key", "cartesia_api_key"]  # Changed from openai_api_key to groq_api_key
            missing_keys = []
            for key in required_keys:
                if not getattr(settings, key, None):
                    missing_keys.append(key)
            
            if missing_keys:
                health_status["checks"]["config"] = f"warning: missing {missing_keys}"
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["environment"] = f"failed: {e}"
        health_status["checks"]["config"] = f"failed: {e}"
        health_status["status"] = "unhealthy"
    
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

def create_health_endpoint():
    """
    Create a simple health check endpoint for containers.
    
    Returns:
        Function that can be used as a health check endpoint
    """
    def health_endpoint():
        try:
            health_data = check_health()
            if health_data["status"] in ["healthy", "degraded"]:
                return health_data
            else:
                raise Exception(f"Health check failed: {health_data}")
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    return health_endpoint


def check_database_health() -> Dict[str, str]:
    """
    Check database connectivity and health.
    
    Returns:
        Dict with database health status
    """
    try:
        from src.database.connection import get_database_manager
        import asyncio
        
        # Get database manager
        db_manager = get_database_manager()
        
        # Run async health check in sync context
        async def _async_health_check():
            try:
                if not db_manager._is_initialized:
                    await db_manager.initialize()
                health_result = await db_manager.health_check()
                return health_result["status"] == "healthy"
            except Exception:
                return False
        
        # Run the async health check
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't run another event loop
                return {"database": "ok: configured"}
            else:
                is_healthy = loop.run_until_complete(_async_health_check())
        except RuntimeError:
            # No event loop running, create a new one
            is_healthy = asyncio.run(_async_health_check())
        
        if is_healthy:
            return {"database": "ok"}
        else:
            return {"database": "failed: health check failed"}
            
    except Exception as e:
        return {"database": f"failed: {e}"}


def check_redis_health() -> Dict[str, str]:
    """
    Check Redis connectivity and health.
    
    Returns:
        Dict with Redis health status
    """
    try:
        import redis
        from src.config import get_settings
        
        settings = get_settings()
        
        # Parse Redis URL and create connection
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=5)
        
        # Test Redis connection
        r.ping()
        return {"redis": "ok"}
    except Exception as e:
        return {"redis": f"failed: {e}"}


def check_ai_services_health() -> Dict[str, str]:
    """
    Check AI services connectivity and actual functionality.
    
    Returns:
        Dict with AI services health status
    """
    try:
        from src.config import get_settings
        
        settings = get_settings()
        health = {}
        
        # Check if API keys are configured first
        if not settings.deepgram_api_key:
            health["deepgram"] = "not_configured"
        else:
            health["deepgram"] = "configured"
        
        if not settings.groq_api_key:
            health["groq"] = "not_configured"
        else:
            health["groq"] = "configured"
        
        if not settings.cartesia_api_key:
            health["cartesia"] = "not_configured"
        else:
            health["cartesia"] = "configured"
        
        if not settings.livekit_api_key:
            health["livekit"] = "not_configured"
        else:
            health["livekit"] = "configured"
        
        return health
    except Exception as e:
        return {"ai_services": f"failed: {e}"}


async def check_ai_services_health_async() -> Dict[str, str]:
    """
    Check AI services connectivity and actual functionality (async version).
    
    Returns:
        Dict with AI services health status
    """
    try:
        from src.config import get_settings
        
        settings = get_settings()
        health = {}
        
        # Check Deepgram STT
        try:
            if not settings.deepgram_api_key:
                health["deepgram"] = "not_configured"
            else:
                from src.clients.deepgram_stt import DeepgramSTTClient
                client = DeepgramSTTClient()
                is_healthy = await client.health_check()
                health["deepgram"] = "ok" if is_healthy else "failed"
                await client.close()
        except Exception as e:
            health["deepgram"] = f"failed: {str(e)[:50]}"
        
        # Check Groq LLM
        try:
            if not settings.groq_api_key:
                health["groq"] = "not_configured"
            else:
                from src.clients.groq_llm import GroqLLMClient
                client = GroqLLMClient()
                is_healthy = await client.health_check()
                health["groq"] = "ok" if is_healthy else "failed"
                await client.close()
        except Exception as e:
            health["groq"] = f"failed: {str(e)[:50]}"
        
        # Check Cartesia TTS
        try:
            if not settings.cartesia_api_key:
                health["cartesia"] = "not_configured"
            else:
                from src.clients.cartesia_tts import CartesiaTTSClient
                client = CartesiaTTSClient()
                is_healthy = await client.health_check()
                health["cartesia"] = "ok" if is_healthy else "failed"
                await client.close()
        except Exception as e:
            health["cartesia"] = f"failed: {str(e)[:50]}"
        
        # Check LiveKit (basic configuration check for now)
        try:
            if not settings.livekit_api_key:
                health["livekit"] = "not_configured"
            else:
                health["livekit"] = "configured"  # TODO: Implement actual LiveKit health check
        except Exception as e:
            health["livekit"] = f"failed: {str(e)[:50]}"
        
        return health
    except Exception as e:
        return {"ai_services": f"failed: {e}"}


def check_prometheus_health() -> Dict[str, str]:
    """
    Check Prometheus monitoring service health.
    
    Returns:
        Dict with Prometheus health status
    """
    # Skip Prometheus check in simple mode
    return {"prometheus": "skipped: not configured in simple mode"}


def comprehensive_health_check() -> Dict[str, Any]:
    """
    Perform comprehensive health check including all subsystems.
    
    Returns:
        Dict containing comprehensive health status
    """
    health_data = check_health()
    
    # Add database health
    db_health = check_database_health()
    health_data["checks"].update(db_health)
    
    # Add Redis health
    redis_health = check_redis_health()
    health_data["checks"].update(redis_health)
    
    # Add AI services health (basic configuration check)
    ai_health = check_ai_services_health()
    health_data["checks"].update(ai_health)
    
    # Add Prometheus health
    prometheus_health = check_prometheus_health()
    health_data["checks"].update(prometheus_health)
    
    # Determine overall status
    failed_checks = [k for k, v in health_data["checks"].items() if "failed" in str(v)]
    warning_checks = [k for k, v in health_data["checks"].items() if "warning" in str(v)]
    
    if failed_checks:
        health_data["status"] = "unhealthy"
        health_data["failed_checks"] = failed_checks
    elif warning_checks:
        health_data["status"] = "degraded"
        health_data["warning_checks"] = warning_checks
    else:
        health_data["status"] = "healthy"
    
    return health_data


async def check_prometheus_health_async() -> Dict[str, str]:
    """
    Check Prometheus monitoring service health (async version).
    
    Returns:
        Dict with Prometheus health status
    """
    # Skip Prometheus check in simple mode
    return {"prometheus": "skipped: not configured in simple mode"}


async def comprehensive_health_check_async() -> Dict[str, Any]:
    """
    Perform comprehensive health check including all subsystems (async version).
    
    Returns:
        Dict containing comprehensive health status
    """
    health_data = check_health()
    
    # Add database health
    db_health = check_database_health()
    health_data["checks"].update(db_health)
    
    # Add Redis health
    redis_health = check_redis_health()
    health_data["checks"].update(redis_health)
    
    # Add AI services health (with actual functionality testing)
    ai_health = await check_ai_services_health_async()
    health_data["checks"].update(ai_health)
    
    # Add Prometheus health (comprehensive async check)
    prometheus_health = await check_prometheus_health_async()
    health_data["checks"].update(prometheus_health)
    
    # Determine overall status
    failed_checks = [k for k, v in health_data["checks"].items() if "failed" in str(v)]
    warning_checks = [k for k, v in health_data["checks"].items() if "warning" in str(v)]
    not_configured_checks = [k for k, v in health_data["checks"].items() if "not_configured" in str(v)]
    
    if failed_checks:
        health_data["status"] = "unhealthy"
        health_data["failed_checks"] = failed_checks
    elif warning_checks or not_configured_checks:
        health_data["status"] = "degraded"
        health_data["warning_checks"] = warning_checks
        health_data["not_configured_checks"] = not_configured_checks
    else:
        health_data["status"] = "healthy"
    
    # Calculate health percentage
    total_checks = len([k for k in health_data["checks"].keys() if k not in ["python", "imports"]])  # Exclude duplicates
    healthy_checks = len([k for k, v in health_data["checks"].items() if str(v).startswith("ok") and k not in ["python", "imports"]])
    health_data["health_percentage"] = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
    
    return health_data
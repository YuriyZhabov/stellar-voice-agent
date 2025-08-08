"""
Health Check Endpoints for LiveKit System

Provides HTTP endpoints for health checks and monitoring data.
Integrates with the LiveKit System Monitor to provide real-time status.

Requirements addressed:
- 7.5: Health check endpoints
"""

import json
import logging
from datetime import datetime, UTC
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from src.monitoring.livekit_system_monitor import get_monitor, LiveKitSystemMonitor


logger = logging.getLogger(__name__)

# Create router for health endpoints
health_router = APIRouter(prefix="/health", tags=["health"])


def get_system_monitor() -> LiveKitSystemMonitor:
    """Dependency to get the system monitor."""
    monitor = get_monitor()
    if not monitor:
        raise HTTPException(
            status_code=503,
            detail="System monitor not initialized"
        )
    return monitor


@health_router.get("/")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    
    Returns:
        JSON response with basic health status
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "livekit-voice-ai-agent"
        }
    )


@health_router.get("/livekit")
async def livekit_health_check(
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
) -> JSONResponse:
    """
    Comprehensive LiveKit health check.
    
    Returns:
        JSON response with detailed health status
    """
    try:
        # Run health checks
        health_results = await monitor.run_health_checks()
        health_summary = monitor.get_health_summary()
        
        # Determine HTTP status code based on health
        status_code = 200
        if health_summary["overall_status"] == "unhealthy":
            status_code = 503
        elif health_summary["overall_status"] == "degraded":
            status_code = 200  # Still operational but with issues
        
        response_data = {
            "overall_status": health_summary["overall_status"],
            "timestamp": datetime.now(UTC).isoformat(),
            "services": {
                service: {
                    "status": result.status.value,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                    "last_check": result.timestamp.isoformat()
                }
                for service, result in health_results.items()
            },
            "summary": health_summary
        }
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
        
    except Exception as e:
        logger.error(f"Error in LiveKit health check: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
        )


@health_router.get("/metrics")
async def get_metrics(
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
) -> JSONResponse:
    """
    Get performance metrics.
    
    Returns:
        JSON response with performance metrics
    """
    try:
        metrics = monitor.get_performance_summary()
        
        return JSONResponse(
            status_code=200,
            content={
                "timestamp": datetime.now(UTC).isoformat(),
                "metrics": metrics
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving metrics: {str(e)}"
        )


@health_router.get("/detailed")
async def get_detailed_status(
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
) -> JSONResponse:
    """
    Get detailed system status including metrics history.
    
    Returns:
        JSON response with comprehensive system status
    """
    try:
        detailed_metrics = monitor.get_detailed_metrics()
        
        return JSONResponse(
            status_code=200,
            content={
                "timestamp": datetime.now(UTC).isoformat(),
                **detailed_metrics
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting detailed status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving detailed status: {str(e)}"
        )


@health_router.get("/alerts")
async def get_alerts(
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor),
    resolved: Optional[bool] = None
) -> JSONResponse:
    """
    Get system alerts.
    
    Args:
        resolved: Filter by resolved status (None for all)
    
    Returns:
        JSON response with alerts
    """
    try:
        alerts = monitor.alerts
        
        # Filter by resolved status if specified
        if resolved is not None:
            alerts = [alert for alert in alerts if alert.resolved == resolved]
        
        alert_data = [
            {
                "id": alert.id,
                "level": alert.level.value,
                "service": alert.service,
                "message": alert.message,
                "details": alert.details,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved
            }
            for alert in sorted(alerts, key=lambda a: a.timestamp, reverse=True)
        ]
        
        return JSONResponse(
            status_code=200,
            content={
                "timestamp": datetime.now(UTC).isoformat(),
                "alerts": alert_data,
                "total_count": len(alert_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving alerts: {str(e)}"
        )


@health_router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
) -> JSONResponse:
    """
    Resolve an alert.
    
    Args:
        alert_id: ID of the alert to resolve
    
    Returns:
        JSON response confirming resolution
    """
    try:
        success = await monitor.resolve_alert(alert_id)
        
        if success:
            return JSONResponse(
                status_code=200,
                content={
                    "message": f"Alert {alert_id} resolved successfully",
                    "timestamp": datetime.now(UTC).isoformat()
                }
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Alert {alert_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error resolving alert: {str(e)}"
        )


@health_router.get("/readiness")
async def readiness_check(
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
) -> JSONResponse:
    """
    Kubernetes-style readiness check.
    
    Returns:
        200 if ready to serve traffic, 503 if not ready
    """
    try:
        health_summary = monitor.get_health_summary()
        
        # Consider ready if at least some services are healthy
        ready = health_summary["healthy_services"] > 0
        
        status_code = 200 if ready else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "ready": ready,
                "healthy_services": health_summary["healthy_services"],
                "total_services": health_summary["total_services"],
                "timestamp": datetime.now(UTC).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error in readiness check: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }
        )


@health_router.get("/liveness")
async def liveness_check() -> JSONResponse:
    """
    Kubernetes-style liveness check.
    
    Returns:
        200 if the application is alive
    """
    return JSONResponse(
        status_code=200,
        content={
            "alive": True,
            "timestamp": datetime.now(UTC).isoformat()
        }
    )
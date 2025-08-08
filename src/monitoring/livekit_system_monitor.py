"""
LiveKit System Monitor

Comprehensive monitoring and diagnostics system for LiveKit according to specification.
Provides health checks, performance metrics, alerting, and detailed logging.

Requirements addressed:
- 7.1: API endpoint diagnostics
- 7.2: Service availability testing (RoomService, Egress, Ingress, SIP)
- 7.3: Performance metrics monitoring
- 7.4: Detailed error logging with codes
- 7.5: Health check endpoints
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Deque
from uuid import uuid4

from src.clients.livekit_api_client import LiveKitAPIClient, LiveKitAPIError
from src.auth.livekit_auth import LiveKitAuthManager


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    api_latency: List[float] = field(default_factory=list)
    connection_success_rate: float = 0.0
    active_rooms: int = 0
    active_participants: int = 0
    error_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


@dataclass
class Alert:
    """System alert data structure."""
    id: str = field(default_factory=lambda: str(uuid4()))
    level: AlertLevel = AlertLevel.INFO
    service: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved: bool = False


class LiveKitSystemMonitor:
    """
    Comprehensive monitoring system for LiveKit according to specification.
    
    Provides:
    - Health checks for all API services
    - Performance metrics monitoring
    - Alert system for critical errors
    - Detailed logging of all operations
    """
    
    def __init__(
        self,
        api_client: LiveKitAPIClient,
        auth_manager: LiveKitAuthManager,
        check_interval: int = 60,
        metrics_retention_hours: int = 24
    ):
        self.api_client = api_client
        self.auth_manager = auth_manager
        self.check_interval = check_interval
        self.metrics_retention_hours = metrics_retention_hours
        
        # Metrics storage
        self.metrics = PerformanceMetrics()
        self.metrics_history: Deque[Dict[str, Any]] = deque(maxlen=1000)
        
        # Health check results
        self.health_results: Dict[str, HealthCheckResult] = {}
        
        # Alert system
        self.alerts: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Connection tracking
        self.connection_stats = {
            "successful": 0,
            "failed": 0,
            "total_attempts": 0
        }
        
        # Room and participant tracking
        self.room_stats = {
            "created": 0,
            "deleted": 0,
            "active": 0
        }
        
        self.participant_stats = {
            "joined": 0,
            "left": 0,
            "active": 0
        }
        
        # Error tracking
        self.error_log: Deque[Dict[str, Any]] = deque(maxlen=500)
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        logger.info("LiveKit System Monitor initialized")
    
    async def start_monitoring(self) -> None:
        """Start continuous monitoring."""
        if self._monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("LiveKit monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("LiveKit monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self.run_health_checks()
                await self._update_performance_metrics()
                await self._cleanup_old_data()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def run_health_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run comprehensive health checks for all LiveKit services.
        
        Returns:
            Dictionary of health check results by service name
        """
        logger.info("Running LiveKit health checks")
        
        checks = {}
        
        # Check RoomService API
        checks["room_service"] = await self._check_room_service()
        
        # Check Egress API
        checks["egress_service"] = await self._check_egress_service()
        
        # Check Ingress API
        checks["ingress_service"] = await self._check_ingress_service()
        
        # Check SIP API (if available)
        checks["sip_service"] = await self._check_sip_service()
        
        # Check authentication system
        checks["auth_system"] = await self._check_auth_system()
        
        # Update stored results
        self.health_results.update(checks)
        
        # Check for critical issues and generate alerts
        await self._evaluate_health_alerts(checks)
        
        logger.info(f"Health checks completed: {len(checks)} services checked")
        return checks
    
    async def _check_room_service(self) -> HealthCheckResult:
        """Check RoomService API health."""
        try:
            start_time = time.time()
            
            # Test basic room listing
            rooms = await self.api_client.list_rooms()
            
            latency = (time.time() - start_time) * 1000
            
            # Record successful connection
            self._record_connection_success()
            
            result = HealthCheckResult(
                service="room_service",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "rooms_count": len(rooms),
                    "endpoint": "/twirp/livekit.RoomService/ListRooms"
                }
            )
            
            logger.debug(f"RoomService health check passed: {latency:.2f}ms")
            return result
            
        except Exception as e:
            self._record_connection_failure()
            self._log_error("room_service", str(e), {"endpoint": "ListRooms"})
            
            return HealthCheckResult(
                service="room_service",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={"endpoint": "/twirp/livekit.RoomService/ListRooms"}
            )
    
    async def _check_egress_service(self) -> HealthCheckResult:
        """Check Egress API health."""
        try:
            start_time = time.time()
            
            # Test egress service availability
            # Note: We'll use a lightweight check that doesn't create actual egress
            egress_client = self.api_client.get_egress_client()
            
            # Try to list existing egress (this is a read-only operation)
            await egress_client.list_egress()
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="egress_service",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={"endpoint": "/twirp/livekit.Egress/ListEgress"}
            )
            
        except Exception as e:
            self._log_error("egress_service", str(e), {"endpoint": "ListEgress"})
            
            return HealthCheckResult(
                service="egress_service",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={"endpoint": "/twirp/livekit.Egress/ListEgress"}
            )
    
    async def _check_ingress_service(self) -> HealthCheckResult:
        """Check Ingress API health."""
        try:
            start_time = time.time()
            
            # Test ingress service availability
            ingress_client = self.api_client.get_ingress_client()
            
            # Try to list existing ingress (read-only operation)
            await ingress_client.list_ingress()
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="ingress_service",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={"endpoint": "/twirp/livekit.Ingress/ListIngress"}
            )
            
        except Exception as e:
            self._log_error("ingress_service", str(e), {"endpoint": "ListIngress"})
            
            return HealthCheckResult(
                service="ingress_service",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={"endpoint": "/twirp/livekit.Ingress/ListIngress"}
            )
    
    async def _check_sip_service(self) -> HealthCheckResult:
        """Check SIP API health."""
        try:
            start_time = time.time()
            
            # Test SIP service availability
            sip_client = self.api_client.get_sip_client()
            
            # Try to list SIP trunks (read-only operation)
            await sip_client.list_sip_inbound_trunk()
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="sip_service",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={"endpoint": "/twirp/livekit.SIP/ListSIPInboundTrunk"}
            )
            
        except Exception as e:
            self._log_error("sip_service", str(e), {"endpoint": "ListSIPInboundTrunk"})
            
            # SIP might not be available in all deployments
            status = HealthStatus.UNKNOWN if "not found" in str(e).lower() else HealthStatus.UNHEALTHY
            
            return HealthCheckResult(
                service="sip_service",
                status=status,
                error=str(e),
                details={"endpoint": "/twirp/livekit.SIP/ListSIPInboundTrunk"}
            )
    
    async def _check_auth_system(self) -> HealthCheckResult:
        """Check authentication system health."""
        try:
            start_time = time.time()
            
            # Test JWT token creation
            token = self.auth_manager.create_participant_token(
                identity="health-check",
                room_name="health-check-room"
            )
            
            # Validate token structure
            if not token or len(token.split('.')) != 3:
                raise ValueError("Invalid JWT token structure")
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service="auth_system",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={"token_length": len(token)}
            )
            
        except Exception as e:
            self._log_error("auth_system", str(e), {"operation": "create_token"})
            
            return HealthCheckResult(
                service="auth_system",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={"operation": "create_token"}
            )  
  
    async def _evaluate_health_alerts(self, checks: Dict[str, HealthCheckResult]) -> None:
        """Evaluate health check results and generate alerts."""
        for service, result in checks.items():
            if result.status == HealthStatus.UNHEALTHY:
                await self._create_alert(
                    AlertLevel.ERROR,
                    service,
                    f"Service {service} is unhealthy: {result.error}",
                    {"latency_ms": result.latency_ms, "details": result.details}
                )
            elif result.status == HealthStatus.DEGRADED:
                await self._create_alert(
                    AlertLevel.WARNING,
                    service,
                    f"Service {service} is degraded",
                    {"latency_ms": result.latency_ms, "details": result.details}
                )
            elif result.latency_ms and result.latency_ms > 5000:  # 5 second threshold
                await self._create_alert(
                    AlertLevel.WARNING,
                    service,
                    f"High latency detected for {service}: {result.latency_ms:.2f}ms",
                    {"latency_ms": result.latency_ms}
                )
    
    async def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        try:
            # Calculate connection success rate
            total_connections = self.connection_stats["total_attempts"]
            if total_connections > 0:
                self.metrics.connection_success_rate = (
                    self.connection_stats["successful"] / total_connections
                )
            
            # Calculate error rate
            total_operations = sum(self.connection_stats.values())
            if total_operations > 0:
                self.metrics.error_rate = len(self.error_log) / total_operations
            
            # Update room and participant counts
            self.metrics.active_rooms = self.room_stats["active"]
            self.metrics.active_participants = self.participant_stats["active"]
            
            # Calculate average API latency
            if self.metrics.api_latency:
                avg_latency = sum(self.metrics.api_latency) / len(self.metrics.api_latency)
                
                # Store metrics snapshot
                metrics_snapshot = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "connection_success_rate": self.metrics.connection_success_rate,
                    "avg_api_latency_ms": avg_latency,
                    "active_rooms": self.metrics.active_rooms,
                    "active_participants": self.metrics.active_participants,
                    "error_rate": self.metrics.error_rate,
                    "total_errors": len(self.error_log)
                }
                
                self.metrics_history.append(metrics_snapshot)
                
                # Clear old latency data to prevent memory growth
                if len(self.metrics.api_latency) > 1000:
                    self.metrics.api_latency = self.metrics.api_latency[-500:]
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data."""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(hours=self.metrics_retention_hours)
            
            # Clean up old alerts
            self.alerts = [
                alert for alert in self.alerts
                if alert.timestamp > cutoff_time or not alert.resolved
            ]
            
            # Clean up old error logs
            self.error_log = deque([
                error for error in self.error_log
                if datetime.fromisoformat(error["timestamp"].replace('Z', '+00:00')) > cutoff_time
            ], maxlen=500)
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    async def _create_alert(
        self,
        level: AlertLevel,
        service: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create and process a new alert."""
        alert = Alert(
            level=level,
            service=service,
            message=message,
            details=details or {}
        )
        
        self.alerts.append(alert)
        
        # Log the alert
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }.get(level, logging.INFO)
        
        logger.log(log_level, f"ALERT [{level.value.upper()}] {service}: {message}")
        
        # Notify alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        return alert
    
    def _record_connection_success(self) -> None:
        """Record a successful connection."""
        self.connection_stats["successful"] += 1
        self.connection_stats["total_attempts"] += 1
    
    def _record_connection_failure(self) -> None:
        """Record a failed connection."""
        self.connection_stats["failed"] += 1
        self.connection_stats["total_attempts"] += 1
    
    def _log_error(self, service: str, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an error with detailed information."""
        error_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "service": service,
            "error": error,
            "details": details or {}
        }
        
        self.error_log.append(error_entry)
        logger.error(f"Service error [{service}]: {error}", extra={"details": details})
    
    def record_api_latency(self, latency_ms: float) -> None:
        """Record API latency measurement."""
        self.metrics.api_latency.append(latency_ms)
    
    def record_room_created(self) -> None:
        """Record room creation."""
        self.room_stats["created"] += 1
        self.room_stats["active"] += 1
    
    def record_room_deleted(self) -> None:
        """Record room deletion."""
        self.room_stats["deleted"] += 1
        self.room_stats["active"] = max(0, self.room_stats["active"] - 1)
    
    def record_participant_joined(self) -> None:
        """Record participant joining."""
        self.participant_stats["joined"] += 1
        self.participant_stats["active"] += 1
    
    def record_participant_left(self) -> None:
        """Record participant leaving."""
        self.participant_stats["left"] += 1
        self.participant_stats["active"] = max(0, self.participant_stats["active"] - 1)
    
    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add a callback function for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Remove an alert callback function."""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary."""
        healthy_services = sum(
            1 for result in self.health_results.values()
            if result.status == HealthStatus.HEALTHY
        )
        
        total_services = len(self.health_results)
        
        return {
            "overall_status": (
                HealthStatus.HEALTHY.value if healthy_services == total_services
                else HealthStatus.DEGRADED.value if healthy_services > 0
                else HealthStatus.UNHEALTHY.value
            ),
            "healthy_services": healthy_services,
            "total_services": total_services,
            "last_check": max(
                (result.timestamp for result in self.health_results.values()),
                default=None
            ),
            "active_alerts": len([alert for alert in self.alerts if not alert.resolved])
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        avg_latency = (
            sum(self.metrics.api_latency) / len(self.metrics.api_latency)
            if self.metrics.api_latency else 0
        )
        
        return {
            "connection_success_rate": self.metrics.connection_success_rate,
            "avg_api_latency_ms": round(avg_latency, 2),
            "active_rooms": self.metrics.active_rooms,
            "active_participants": self.metrics.active_participants,
            "error_rate": self.metrics.error_rate,
            "total_connections": self.connection_stats["total_attempts"],
            "total_errors": len(self.error_log)
        }
    
    def get_detailed_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics including history."""
        return {
            "current_metrics": self.get_performance_summary(),
            "health_summary": self.get_health_summary(),
            "health_details": {
                service: {
                    "status": result.status.value,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                    "details": result.details,
                    "last_check": result.timestamp.isoformat()
                }
                for service, result in self.health_results.items()
            },
            "recent_alerts": [
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "service": alert.service,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved
                }
                for alert in sorted(self.alerts, key=lambda a: a.timestamp, reverse=True)[:10]
            ],
            "metrics_history": list(self.metrics_history)[-50:],  # Last 50 snapshots
            "connection_stats": self.connection_stats.copy(),
            "room_stats": self.room_stats.copy(),
            "participant_stats": self.participant_stats.copy()
        }


# Global monitor instance
_monitor_instance: Optional[LiveKitSystemMonitor] = None


def get_monitor() -> Optional[LiveKitSystemMonitor]:
    """Get the global monitor instance."""
    return _monitor_instance


def initialize_monitor(
    api_client: LiveKitAPIClient,
    auth_manager: LiveKitAuthManager,
    **kwargs
) -> LiveKitSystemMonitor:
    """Initialize the global monitor instance."""
    global _monitor_instance
    _monitor_instance = LiveKitSystemMonitor(api_client, auth_manager, **kwargs)
    return _monitor_instance


async def start_global_monitoring() -> None:
    """Start global monitoring if initialized."""
    if _monitor_instance:
        await _monitor_instance.start_monitoring()


async def stop_global_monitoring() -> None:
    """Stop global monitoring if active."""
    if _monitor_instance:
        await _monitor_instance.stop_monitoring()
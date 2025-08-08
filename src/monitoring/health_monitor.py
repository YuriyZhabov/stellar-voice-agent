"""Comprehensive health monitoring system for all critical components."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
from uuid import uuid4

from src.config import get_settings
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Types of system components."""
    STT_CLIENT = "stt_client"
    LLM_CLIENT = "llm_client"
    TTS_CLIENT = "tts_client"
    DATABASE = "database"
    REDIS = "redis"
    LIVEKIT = "livekit"
    SYSTEM = "system"
    ORCHESTRATOR = "orchestrator"


@dataclass
class HealthThreshold:
    """Health check thresholds for a component."""
    response_time_ms: float = 5000.0  # 5 seconds
    success_rate_percent: float = 80.0  # 80%
    error_rate_percent: float = 20.0   # 20%
    memory_usage_percent: float = 85.0  # 85%
    cpu_usage_percent: float = 80.0     # 80%
    disk_usage_percent: float = 90.0    # 90%


@dataclass
class ComponentHealth:
    """Health information for a single component."""
    component_type: ComponentType
    component_name: str
    status: HealthStatus
    last_check: datetime
    response_time_ms: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "component_type": self.component_type.value,
            "component_name": self.component_name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "response_time_ms": self.response_time_ms,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "details": self.details,
            "error_message": self.error_message
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    last_check: datetime
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def healthy_components(self) -> int:
        """Count of healthy components."""
        return sum(1 for comp in self.components.values() 
                  if comp.status == HealthStatus.HEALTHY)
    
    @property
    def total_components(self) -> int:
        """Total number of components."""
        return len(self.components)
    
    @property
    def health_percentage(self) -> float:
        """Overall health percentage."""
        if self.total_components == 0:
            return 0.0
        return (self.healthy_components / self.total_components) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "healthy_components": self.healthy_components,
            "total_components": self.total_components,
            "health_percentage": self.health_percentage,
            "components": {name: comp.to_dict() for name, comp in self.components.items()},
            "summary": self.summary
        }


class HealthMonitor:
    """
    Comprehensive health monitoring system for all critical components.
    
    Features:
    - Automated health checks for all system components
    - Configurable thresholds and check intervals
    - Health status aggregation and reporting
    - Integration with metrics collection
    - Support for custom health check functions
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        component_timeout: float = 10.0,
        enable_auto_checks: bool = True
    ):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Interval between health checks in seconds
            component_timeout: Timeout for individual component checks
            enable_auto_checks: Enable automatic periodic health checks
        """
        self.check_interval = check_interval
        self.component_timeout = component_timeout
        self.enable_auto_checks = enable_auto_checks
        
        # Component registry
        self.components: Dict[str, Dict[str, Any]] = {}
        self.health_checkers: Dict[str, Callable] = {}
        self.thresholds: Dict[str, HealthThreshold] = {}
        
        # Health status tracking
        self.component_health: Dict[str, ComponentHealth] = {}
        self.system_health: Optional[SystemHealth] = None
        self.last_system_check: Optional[datetime] = None
        
        # Monitoring state
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        self._stop_event = asyncio.Event()
        
        # Metrics integration
        self.metrics_collector = get_metrics_collector()
        
        # Health check history for trend analysis
        self.health_history: Dict[str, List[ComponentHealth]] = {}
        self.max_history_size = 100
        
        logger.info(
            "Health monitor initialized",
            extra={
                "check_interval": check_interval,
                "component_timeout": component_timeout,
                "auto_checks": enable_auto_checks
            }
        )
    
    def register_component(
        self,
        component_name: str,
        component_type: ComponentType,
        health_checker: Callable,
        threshold: Optional[HealthThreshold] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a component for health monitoring.
        
        Args:
            component_name: Unique name for the component
            component_type: Type of component
            health_checker: Async function that returns health status
            threshold: Custom health thresholds
            metadata: Additional component metadata
        """
        self.components[component_name] = {
            "type": component_type,
            "metadata": metadata or {}
        }
        self.health_checkers[component_name] = health_checker
        self.thresholds[component_name] = threshold or HealthThreshold()
        self.health_history[component_name] = []
        
        logger.info(
            f"Registered component for health monitoring: {component_name}",
            extra={
                "component_type": component_type.value,
                "has_custom_threshold": threshold is not None
            }
        )
    
    def unregister_component(self, component_name: str) -> None:
        """
        Unregister a component from health monitoring.
        
        Args:
            component_name: Name of component to unregister
        """
        self.components.pop(component_name, None)
        self.health_checkers.pop(component_name, None)
        self.thresholds.pop(component_name, None)
        self.component_health.pop(component_name, None)
        self.health_history.pop(component_name, None)
        
        logger.info(f"Unregistered component: {component_name}")
    
    async def check_component_health(self, component_name: str) -> ComponentHealth:
        """
        Check health of a specific component.
        
        Args:
            component_name: Name of component to check
            
        Returns:
            ComponentHealth with current status
        """
        if component_name not in self.components:
            raise ValueError(f"Component not registered: {component_name}")
        
        component_info = self.components[component_name]
        health_checker = self.health_checkers[component_name]
        threshold = self.thresholds[component_name]
        
        start_time = time.time()
        
        try:
            # Execute health check with timeout
            health_result = await asyncio.wait_for(
                health_checker(),
                timeout=self.component_timeout
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine health status based on result and thresholds
            if isinstance(health_result, bool):
                status = HealthStatus.HEALTHY if health_result else HealthStatus.UNHEALTHY
                details = {"check_passed": health_result}
                success_rate = 100.0 if health_result else 0.0
                error_rate = 0.0 if health_result else 100.0
                error_message = None if health_result else "Health check failed"
            elif isinstance(health_result, dict):
                # Extract detailed health information
                status = HealthStatus(health_result.get("status", HealthStatus.UNKNOWN))
                details = health_result.get("details", {})
                success_rate = health_result.get("success_rate", 0.0)
                error_rate = health_result.get("error_rate", 0.0)
                error_message = health_result.get("error_message")
            else:
                # Fallback for unexpected result types
                status = HealthStatus.UNKNOWN
                details = {"raw_result": str(health_result)}
                success_rate = 0.0
                error_rate = 100.0
                error_message = f"Unexpected health check result type: {type(health_result)}"
            
            # Apply threshold-based status adjustment
            if status == HealthStatus.HEALTHY:
                if response_time_ms > threshold.response_time_ms:
                    status = HealthStatus.DEGRADED
                    error_message = f"Response time {response_time_ms:.1f}ms exceeds threshold {threshold.response_time_ms}ms"
                elif success_rate < threshold.success_rate_percent:
                    status = HealthStatus.DEGRADED
                    error_message = f"Success rate {success_rate:.1f}% below threshold {threshold.success_rate_percent}%"
                elif error_rate > threshold.error_rate_percent:
                    status = HealthStatus.DEGRADED
                    error_message = f"Error rate {error_rate:.1f}% exceeds threshold {threshold.error_rate_percent}%"
            
            component_health = ComponentHealth(
                component_type=component_info["type"],
                component_name=component_name,
                status=status,
                last_check=datetime.now(UTC),
                response_time_ms=response_time_ms,
                success_rate=success_rate,
                error_rate=error_rate,
                details=details,
                error_message=error_message
            )
            
        except asyncio.TimeoutError:
            component_health = ComponentHealth(
                component_type=component_info["type"],
                component_name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(UTC),
                response_time_ms=self.component_timeout * 1000,
                success_rate=0.0,
                error_rate=100.0,
                details={"timeout": True},
                error_message=f"Health check timed out after {self.component_timeout}s"
            )
            
        except Exception as e:
            component_health = ComponentHealth(
                component_type=component_info["type"],
                component_name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(UTC),
                response_time_ms=(time.time() - start_time) * 1000,
                success_rate=0.0,
                error_rate=100.0,
                details={"exception": str(e)},
                error_message=f"Health check failed: {str(e)}"
            )
        
        # Update component health and history
        self.component_health[component_name] = component_health
        self._add_to_history(component_name, component_health)
        
        # Update metrics
        self.metrics_collector.set_gauge(
            f"component_health_status",
            1 if component_health.status == HealthStatus.HEALTHY else 0,
            labels={"component": component_name, "type": component_info["type"].value}
        )
        self.metrics_collector.record_histogram(
            f"component_health_response_time_ms",
            component_health.response_time_ms,
            labels={"component": component_name}
        )
        
        logger.debug(
            f"Health check completed for {component_name}",
            extra={
                "component": component_name,
                "status": component_health.status.value,
                "response_time_ms": component_health.response_time_ms
            }
        )
        
        return component_health
    
    async def check_all_components(self) -> SystemHealth:
        """
        Check health of all registered components.
        
        Returns:
            SystemHealth with overall system status
        """
        start_time = time.time()
        
        # Check all components concurrently
        health_tasks = {
            name: self.check_component_health(name)
            for name in self.components.keys()
        }
        
        component_results = {}
        for name, task in health_tasks.items():
            try:
                component_results[name] = await task
            except Exception as e:
                logger.error(f"Failed to check health for {name}: {e}")
                component_results[name] = ComponentHealth(
                    component_type=self.components[name]["type"],
                    component_name=name,
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(UTC),
                    error_message=f"Health check failed: {str(e)}"
                )
        
        # Determine overall system health
        healthy_count = sum(1 for comp in component_results.values() 
                          if comp.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for comp in component_results.values() 
                           if comp.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for comp in component_results.values() 
                            if comp.status == HealthStatus.UNHEALTHY)
        
        total_components = len(component_results)
        
        if total_components == 0:
            overall_status = HealthStatus.UNKNOWN
        elif unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Create system health summary
        check_duration = (time.time() - start_time) * 1000
        
        summary = {
            "total_components": total_components,
            "healthy_components": healthy_count,
            "degraded_components": degraded_count,
            "unhealthy_components": unhealthy_count,
            "health_percentage": (healthy_count / max(1, total_components)) * 100,
            "check_duration_ms": check_duration,
            "critical_issues": [
                comp.component_name for comp in component_results.values()
                if comp.status == HealthStatus.UNHEALTHY
            ],
            "performance_issues": [
                comp.component_name for comp in component_results.values()
                if comp.status == HealthStatus.DEGRADED
            ]
        }
        
        system_health = SystemHealth(
            status=overall_status,
            last_check=datetime.now(UTC),
            components=component_results,
            summary=summary
        )
        
        self.system_health = system_health
        self.last_system_check = system_health.last_check
        
        # Update system-level metrics
        self.metrics_collector.set_gauge("system_health_status", 
                                        1 if overall_status == HealthStatus.HEALTHY else 0)
        self.metrics_collector.set_gauge("system_health_percentage", summary["health_percentage"])
        self.metrics_collector.record_histogram("system_health_check_duration_ms", check_duration)
        
        logger.info(
            f"System health check completed",
            extra={
                "status": overall_status.value,
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
                "duration_ms": check_duration
            }
        )
        
        return system_health
    
    def _add_to_history(self, component_name: str, health: ComponentHealth) -> None:
        """Add health check result to history."""
        if component_name not in self.health_history:
            self.health_history[component_name] = []
        
        history = self.health_history[component_name]
        history.append(health)
        
        # Limit history size
        if len(history) > self.max_history_size:
            history.pop(0)
    
    def get_component_health_trend(self, component_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get health trend for a component over specified time period.
        
        Args:
            component_name: Name of component
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        if component_name not in self.health_history:
            return {"error": "Component not found"}
        
        history = self.health_history[component_name]
        if not history:
            return {"error": "No health history available"}
        
        # Filter history by time period
        cutoff_time = datetime.now(UTC).timestamp() - (hours * 3600)
        recent_history = [
            h for h in history 
            if h.last_check.timestamp() > cutoff_time
        ]
        
        if not recent_history:
            return {"error": "No recent health data"}
        
        # Calculate trend metrics
        total_checks = len(recent_history)
        healthy_checks = sum(1 for h in recent_history if h.status == HealthStatus.HEALTHY)
        degraded_checks = sum(1 for h in recent_history if h.status == HealthStatus.DEGRADED)
        unhealthy_checks = sum(1 for h in recent_history if h.status == HealthStatus.UNHEALTHY)
        
        avg_response_time = sum(h.response_time_ms for h in recent_history) / total_checks
        avg_success_rate = sum(h.success_rate for h in recent_history) / total_checks
        avg_error_rate = sum(h.error_rate for h in recent_history) / total_checks
        
        return {
            "component_name": component_name,
            "period_hours": hours,
            "total_checks": total_checks,
            "availability_percentage": (healthy_checks / total_checks) * 100,
            "degraded_percentage": (degraded_checks / total_checks) * 100,
            "unhealthy_percentage": (unhealthy_checks / total_checks) * 100,
            "average_response_time_ms": avg_response_time,
            "average_success_rate": avg_success_rate,
            "average_error_rate": avg_error_rate,
            "trend": "improving" if recent_history[-1].status == HealthStatus.HEALTHY else "degrading"
        }
    
    async def start_monitoring(self) -> None:
        """Start automatic health monitoring."""
        if self.is_monitoring:
            logger.warning("Health monitoring is already running")
            return
        
        if not self.enable_auto_checks:
            logger.info("Automatic health checks are disabled")
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(
            f"Started health monitoring with {self.check_interval}s interval",
            extra={"components": len(self.components)}
        )
    
    async def stop_monitoring(self) -> None:
        """Stop automatic health monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring and not self._stop_event.is_set():
            try:
                await self.check_all_components()
                
                # Wait for next check interval
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.check_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    continue  # Continue monitoring
                    
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                # Continue monitoring despite errors
                await asyncio.sleep(min(self.check_interval, 60))
    
    def get_system_health(self) -> Optional[SystemHealth]:
        """Get current system health status."""
        return self.system_health
    
    def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """Get current health status for a specific component."""
        return self.component_health.get(component_name)
    
    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get current health status for all components."""
        return self.component_health.copy()
    
    def is_system_healthy(self) -> bool:
        """Check if system is currently healthy."""
        return (self.system_health is not None and 
                self.system_health.status == HealthStatus.HEALTHY)
    
    def get_unhealthy_components(self) -> List[str]:
        """Get list of currently unhealthy components."""
        return [
            name for name, health in self.component_health.items()
            if health.status == HealthStatus.UNHEALTHY
        ]
    
    def get_degraded_components(self) -> List[str]:
        """Get list of currently degraded components."""
        return [
            name for name, health in self.component_health.items()
            if health.status == HealthStatus.DEGRADED
        ]
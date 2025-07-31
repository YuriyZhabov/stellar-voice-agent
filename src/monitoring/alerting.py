"""Alerting system for system failures and performance degradation."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
from uuid import uuid4

import httpx

from src.config import get_settings
from src.monitoring.health_monitor import HealthStatus, ComponentHealth, SystemHealth


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Individual alert instance."""
    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    component: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "component": self.component,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "metadata": self.metadata
        }
    
    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
    
    def acknowledge(self) -> None:
        """Mark alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
    
    def suppress(self) -> None:
        """Mark alert as suppressed."""
        self.status = AlertStatus.SUPPRESSED
        self.updated_at = datetime.now(UTC)


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: Callable[[Any], bool]
    severity: AlertSeverity
    message_template: str
    component_filter: Optional[str] = None
    cooldown_minutes: int = 5
    max_alerts_per_hour: int = 10
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertChannel:
    """Abstract base class for alert notification channels."""
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert notification."""
        raise NotImplementedError
    
    async def health_check(self) -> bool:
        """Check if channel is healthy."""
        raise NotImplementedError


class WebhookChannel(AlertChannel):
    """Webhook alert notification channel."""
    
    def __init__(
        self,
        webhook_url: str,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize webhook channel.
        
        Args:
            webhook_url: URL to send webhook notifications to
            timeout: HTTP timeout for webhook calls
            headers: Additional HTTP headers
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.headers = headers or {}
        
        self.http_client = httpx.AsyncClient(timeout=timeout)
        
        logger.info(f"Webhook alert channel initialized: {webhook_url}")
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.now(UTC).isoformat(),
                "source": "voice_ai_agent"
            }
            
            response = await self.http_client.post(
                self.webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    **self.headers
                }
            )
            
            if response.status_code in [200, 201, 202]:
                logger.debug(f"Alert sent via webhook: {alert.id}")
                return True
            else:
                logger.error(f"Webhook failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check webhook health."""
        try:
            # Send a test ping
            response = await self.http_client.get(
                self.webhook_url,
                timeout=5.0
            )
            return response.status_code < 500
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()


class LogChannel(AlertChannel):
    """Log-based alert notification channel."""
    
    def __init__(self, log_level: str = "ERROR"):
        """
        Initialize log channel.
        
        Args:
            log_level: Log level for alerts
        """
        self.log_level = getattr(logging, log_level.upper())
        self.logger = logging.getLogger("alerts")
        
        logger.info(f"Log alert channel initialized with level: {log_level}")
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to logs."""
        try:
            log_message = f"ALERT [{alert.severity.upper()}] {alert.name}: {alert.message}"
            if alert.component:
                log_message += f" (Component: {alert.component})"
            
            self.logger.log(
                self.log_level,
                log_message,
                extra={
                    "alert_id": alert.id,
                    "alert_severity": alert.severity.value,
                    "alert_component": alert.component,
                    "alert_metadata": alert.metadata
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Log alert failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Log channel is always healthy."""
        return True


class AlertManager:
    """
    Comprehensive alerting system for system failures and performance issues.
    
    Features:
    - Rule-based alert generation
    - Multiple notification channels
    - Alert deduplication and rate limiting
    - Alert lifecycle management
    - Integration with health monitoring
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        alert_retention_hours: int = 24,
        max_active_alerts: int = 100
    ):
        """
        Initialize alert manager.
        
        Args:
            check_interval: Interval between alert rule evaluations
            alert_retention_hours: Hours to retain resolved alerts
            max_active_alerts: Maximum number of active alerts
        """
        self.check_interval = check_interval
        self.alert_retention_hours = alert_retention_hours
        self.max_active_alerts = max_active_alerts
        
        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.resolved_alerts: Dict[str, Alert] = {}
        
        # Alert rules
        self.alert_rules: Dict[str, AlertRule] = {}
        
        # Notification channels
        self.channels: Dict[str, AlertChannel] = {}
        
        # Rate limiting and deduplication
        self.alert_counts: Dict[str, List[datetime]] = {}
        self.last_alert_times: Dict[str, datetime] = {}
        
        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        self._stop_event = asyncio.Event()
        
        # Initialize default alert rules
        self._setup_default_rules()
        
        logger.info(
            "Alert manager initialized",
            extra={
                "check_interval": check_interval,
                "retention_hours": alert_retention_hours,
                "max_active": max_active_alerts
            }
        )
    
    def _setup_default_rules(self) -> None:
        """Setup default alert rules for common issues."""
        
        # System health alerts
        self.add_rule(AlertRule(
            name="system_unhealthy",
            condition=lambda health: (
                isinstance(health, SystemHealth) and 
                health.status == HealthStatus.UNHEALTHY
            ),
            severity=AlertSeverity.CRITICAL,
            message_template="System is unhealthy: {unhealthy_components} components failing",
            cooldown_minutes=5
        ))
        
        self.add_rule(AlertRule(
            name="system_degraded",
            condition=lambda health: (
                isinstance(health, SystemHealth) and 
                health.status == HealthStatus.DEGRADED
            ),
            severity=AlertSeverity.HIGH,
            message_template="System performance degraded: {degraded_components} components affected",
            cooldown_minutes=10
        ))
        
        # Component health alerts
        self.add_rule(AlertRule(
            name="component_unhealthy",
            condition=lambda health: (
                isinstance(health, ComponentHealth) and 
                health.status == HealthStatus.UNHEALTHY
            ),
            severity=AlertSeverity.HIGH,
            message_template="Component {component_name} is unhealthy: {error_message}",
            cooldown_minutes=5
        ))
        
        self.add_rule(AlertRule(
            name="component_high_latency",
            condition=lambda health: (
                isinstance(health, ComponentHealth) and 
                health.response_time_ms > 5000
            ),
            severity=AlertSeverity.MEDIUM,
            message_template="Component {component_name} has high latency: {response_time_ms}ms",
            cooldown_minutes=15
        ))
        
        self.add_rule(AlertRule(
            name="component_low_success_rate",
            condition=lambda health: (
                isinstance(health, ComponentHealth) and 
                health.success_rate < 80.0
            ),
            severity=AlertSeverity.MEDIUM,
            message_template="Component {component_name} has low success rate: {success_rate}%",
            cooldown_minutes=10
        ))
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add alert rule.
        
        Args:
            rule: AlertRule to add
        """
        self.alert_rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> None:
        """
        Remove alert rule.
        
        Args:
            rule_name: Name of rule to remove
        """
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            logger.info(f"Removed alert rule: {rule_name}")
    
    def add_channel(self, name: str, channel: AlertChannel) -> None:
        """
        Add notification channel.
        
        Args:
            name: Unique name for channel
            channel: AlertChannel instance
        """
        self.channels[name] = channel
        logger.info(f"Added alert channel: {name}")
    
    def remove_channel(self, name: str) -> None:
        """
        Remove notification channel.
        
        Args:
            name: Name of channel to remove
        """
        if name in self.channels:
            del self.channels[name]
            logger.info(f"Removed alert channel: {name}")
    
    async def evaluate_rules(self, data: Any) -> List[Alert]:
        """
        Evaluate alert rules against provided data.
        
        Args:
            data: Data to evaluate rules against
            
        Returns:
            List of new alerts generated
        """
        new_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            
            try:
                # Check if rule condition is met
                if rule.condition(data):
                    # Check rate limiting and cooldown
                    if self._should_create_alert(rule_name, rule):
                        alert = await self._create_alert(rule, data)
                        new_alerts.append(alert)
                        
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_name}: {e}")
        
        return new_alerts
    
    def _should_create_alert(self, rule_name: str, rule: AlertRule) -> bool:
        """Check if alert should be created based on rate limiting and cooldown."""
        now = datetime.now(UTC)
        
        # Check cooldown
        if rule_name in self.last_alert_times:
            time_since_last = now - self.last_alert_times[rule_name]
            if time_since_last.total_seconds() < rule.cooldown_minutes * 60:
                return False
        
        # Check rate limiting
        if rule_name not in self.alert_counts:
            self.alert_counts[rule_name] = []
        
        # Clean old entries
        hour_ago = now - timedelta(hours=1)
        self.alert_counts[rule_name] = [
            timestamp for timestamp in self.alert_counts[rule_name]
            if timestamp > hour_ago
        ]
        
        # Check if under rate limit
        if len(self.alert_counts[rule_name]) >= rule.max_alerts_per_hour:
            return False
        
        return True
    
    async def _create_alert(self, rule: AlertRule, data: Any) -> Alert:
        """Create new alert from rule and data."""
        alert_id = str(uuid4())
        
        # Format message template
        message = rule.message_template
        component = None
        
        if isinstance(data, SystemHealth):
            message = message.format(
                unhealthy_components=len(data.summary.get("critical_issues", [])),
                degraded_components=len(data.summary.get("performance_issues", [])),
                health_percentage=data.health_percentage
            )
        elif isinstance(data, ComponentHealth):
            component = data.component_name
            message = message.format(
                component_name=data.component_name,
                response_time_ms=data.response_time_ms,
                success_rate=data.success_rate,
                error_message=data.error_message or "Unknown error"
            )
        
        alert = Alert(
            id=alert_id,
            name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=message,
            component=component,
            metadata={
                "rule_name": rule.name,
                "data_type": type(data).__name__,
                **rule.metadata
            }
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        
        # Update rate limiting tracking
        now = datetime.now(UTC)
        self.last_alert_times[rule.name] = now
        if rule.name not in self.alert_counts:
            self.alert_counts[rule.name] = []
        self.alert_counts[rule.name].append(now)
        
        # Send notifications
        await self._send_alert_notifications(alert)
        
        logger.info(
            f"Created alert: {alert.name}",
            extra={
                "alert_id": alert_id,
                "severity": alert.severity.value,
                "component": component
            }
        )
        
        return alert
    
    async def _send_alert_notifications(self, alert: Alert) -> None:
        """Send alert to all configured channels."""
        if not self.channels:
            logger.warning("No alert channels configured")
            return
        
        # Send to all channels concurrently
        send_tasks = {
            name: channel.send_alert(alert)
            for name, channel in self.channels.items()
        }
        
        results = {}
        for name, task in send_tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Failed to send alert via {name}: {e}")
                results[name] = False
        
        # Log notification results
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        if successful == 0:
            logger.error(f"Failed to send alert {alert.id} to any channel")
        elif successful < total:
            logger.warning(f"Alert {alert.id} sent to {successful}/{total} channels")
        else:
            logger.debug(f"Alert {alert.id} sent to all {total} channels")
    
    async def resolve_alert(self, alert_id: str, reason: Optional[str] = None) -> bool:
        """
        Resolve an active alert.
        
        Args:
            alert_id: ID of alert to resolve
            reason: Optional reason for resolution
            
        Returns:
            True if alert was resolved
        """
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.resolve()
        
        if reason:
            alert.metadata["resolution_reason"] = reason
        
        # Move to resolved alerts
        self.resolved_alerts[alert_id] = alert
        del self.active_alerts[alert_id]
        
        logger.info(
            f"Resolved alert: {alert.name}",
            extra={"alert_id": alert_id, "reason": reason}
        )
        
        return True
    
    async def acknowledge_alert(self, alert_id: str, reason: Optional[str] = None) -> bool:
        """
        Acknowledge an active alert.
        
        Args:
            alert_id: ID of alert to acknowledge
            reason: Optional reason for acknowledgment
            
        Returns:
            True if alert was acknowledged
        """
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.acknowledge()
        
        if reason:
            alert.metadata["acknowledgment_reason"] = reason
        
        logger.info(
            f"Acknowledged alert: {alert.name}",
            extra={"alert_id": alert_id, "reason": reason}
        )
        
        return True
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        component: Optional[str] = None
    ) -> List[Alert]:
        """
        Get active alerts with optional filtering.
        
        Args:
            severity: Filter by severity
            component: Filter by component
            
        Returns:
            List of matching active alerts
        """
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if component:
            alerts = [a for a in alerts if a.component == component]
        
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert status."""
        active_by_severity = {}
        for severity in AlertSeverity:
            active_by_severity[severity.value] = len([
                a for a in self.active_alerts.values()
                if a.severity == severity
            ])
        
        return {
            "total_active": len(self.active_alerts),
            "total_resolved": len(self.resolved_alerts),
            "active_by_severity": active_by_severity,
            "rules_enabled": len([r for r in self.alert_rules.values() if r.enabled]),
            "channels_configured": len(self.channels),
            "last_evaluation": datetime.now(UTC).isoformat()
        }
    
    async def cleanup_old_alerts(self) -> int:
        """Clean up old resolved alerts."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.alert_retention_hours)
        
        old_alerts = [
            alert_id for alert_id, alert in self.resolved_alerts.items()
            if alert.resolved_at and alert.resolved_at < cutoff_time
        ]
        
        for alert_id in old_alerts:
            del self.resolved_alerts[alert_id]
        
        if old_alerts:
            logger.info(f"Cleaned up {len(old_alerts)} old resolved alerts")
        
        return len(old_alerts)
    
    async def start_monitoring(self) -> None:
        """Start automatic alert monitoring."""
        if self.is_monitoring:
            logger.warning("Alert monitoring is already running")
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"Started alert monitoring with {self.check_interval}s interval")
    
    async def stop_monitoring(self) -> None:
        """Stop automatic alert monitoring."""
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
        
        logger.info("Stopped alert monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main alert monitoring loop."""
        while self.is_monitoring and not self._stop_event.is_set():
            try:
                # Clean up old alerts periodically
                await self.cleanup_old_alerts()
                
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
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(min(self.check_interval, 60))
    
    async def health_check_channels(self) -> Dict[str, bool]:
        """Check health of all notification channels."""
        health_tasks = {
            name: channel.health_check()
            for name, channel in self.channels.items()
        }
        
        results = {}
        for name, task in health_tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Channel health check failed for {name}: {e}")
                results[name] = False
        
        return results
    
    async def close(self) -> None:
        """Close alert manager and cleanup resources."""
        await self.stop_monitoring()
        
        # Close all channels
        for channel in self.channels.values():
            if hasattr(channel, 'close'):
                await channel.close()
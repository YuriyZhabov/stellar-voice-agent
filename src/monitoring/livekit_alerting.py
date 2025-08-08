"""
LiveKit Alerting System

Advanced alerting system for LiveKit monitoring with multiple notification channels.
Supports email, webhook, and logging-based alerts with configurable thresholds.

Requirements addressed:
- 7.4: Alert system for critical errors
"""

import asyncio
import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable, Set
from uuid import uuid4

import aiohttp

from src.monitoring.livekit_system_monitor import Alert, AlertLevel, HealthStatus


logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Configuration for alert rules."""
    name: str
    condition: str  # e.g., "latency > 5000", "error_rate > 0.1"
    level: AlertLevel
    service: Optional[str] = None
    cooldown_minutes: int = 15
    enabled: bool = True
    description: str = ""


@dataclass
class NotificationChannel:
    """Base configuration for notification channels."""
    name: str
    enabled: bool = True
    alert_levels: Set[AlertLevel] = field(default_factory=lambda: {AlertLevel.ERROR, AlertLevel.CRITICAL})


@dataclass
class EmailChannel(NotificationChannel):
    """Email notification channel configuration."""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    to_emails: List[str] = field(default_factory=list)
    use_tls: bool = True


@dataclass
class WebhookChannel(NotificationChannel):
    """Webhook notification channel configuration."""
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3


@dataclass
class SlackChannel(NotificationChannel):
    """Slack notification channel configuration."""
    webhook_url: str = ""
    channel: str = "#alerts"
    username: str = "LiveKit Monitor"
    icon_emoji: str = ":warning:"


class AlertNotifier(ABC):
    """Abstract base class for alert notifiers."""
    
    @abstractmethod
    async def send_alert(self, alert: Alert, channel: NotificationChannel) -> bool:
        """Send an alert notification."""
        pass


class EmailNotifier(AlertNotifier):
    """Email alert notifier."""
    
    async def send_alert(self, alert: Alert, channel: EmailChannel) -> bool:
        """Send alert via email."""
        try:
            if not channel.to_emails:
                logger.warning("No email recipients configured")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = channel.from_email
            msg['To'] = ', '.join(channel.to_emails)
            msg['Subject'] = f"[{alert.level.value.upper()}] LiveKit Alert: {alert.service}"
            
            # Create email body
            body = self._create_email_body(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(channel.smtp_host, channel.smtp_port) as server:
                if channel.use_tls:
                    server.starttls()
                if channel.smtp_username and channel.smtp_password:
                    server.login(channel.smtp_username, channel.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent for {alert.service}: {alert.message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _create_email_body(self, alert: Alert) -> str:
        """Create HTML email body."""
        level_colors = {
            AlertLevel.INFO: "#17a2b8",
            AlertLevel.WARNING: "#ffc107",
            AlertLevel.ERROR: "#dc3545",
            AlertLevel.CRITICAL: "#721c24"
        }
        
        color = level_colors.get(alert.level, "#6c757d")
        
        return f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">LiveKit System Alert</h2>
                    <p style="margin: 5px 0 0 0;">Level: {alert.level.value.upper()}</p>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 5px 5px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 120px;">Service:</td>
                            <td style="padding: 8px;">{alert.service}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Message:</td>
                            <td style="padding: 8px;">{alert.message}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Time:</td>
                            <td style="padding: 8px;">{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Alert ID:</td>
                            <td style="padding: 8px; font-family: monospace;">{alert.id}</td>
                        </tr>
                    </table>
                    
                    {self._format_details(alert.details) if alert.details else ''}
                </div>
            </div>
        </body>
        </html>
        """
    
    def _format_details(self, details: Dict[str, Any]) -> str:
        """Format alert details as HTML."""
        if not details:
            return ""
        
        html = "<h4>Details:</h4><ul>"
        for key, value in details.items():
            html += f"<li><strong>{key}:</strong> {value}</li>"
        html += "</ul>"
        return html


class WebhookNotifier(AlertNotifier):
    """Webhook alert notifier."""
    
    async def send_alert(self, alert: Alert, channel: WebhookChannel) -> bool:
        """Send alert via webhook."""
        try:
            payload = {
                "alert_id": alert.id,
                "level": alert.level.value,
                "service": alert.service,
                "message": alert.message,
                "details": alert.details,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved
            }
            
            headers = {
                "Content-Type": "application/json",
                **channel.headers
            }
            
            timeout = aiohttp.ClientTimeout(total=channel.timeout)
            
            for attempt in range(channel.retry_attempts):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(
                            channel.url,
                            json=payload,
                            headers=headers
                        ) as response:
                            if response.status < 400:
                                logger.info(f"Webhook alert sent for {alert.service}: {alert.message}")
                                return True
                            else:
                                logger.warning(f"Webhook returned status {response.status}")
                                
                except asyncio.TimeoutError:
                    logger.warning(f"Webhook timeout on attempt {attempt + 1}")
                except Exception as e:
                    logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
                
                if attempt < channel.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            logger.error(f"Failed to send webhook alert after {channel.retry_attempts} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class SlackNotifier(AlertNotifier):
    """Slack alert notifier."""
    
    async def send_alert(self, alert: Alert, channel: SlackChannel) -> bool:
        """Send alert to Slack."""
        try:
            color_map = {
                AlertLevel.INFO: "#36a64f",
                AlertLevel.WARNING: "#ff9500",
                AlertLevel.ERROR: "#ff0000",
                AlertLevel.CRITICAL: "#8b0000"
            }
            
            payload = {
                "channel": channel.channel,
                "username": channel.username,
                "icon_emoji": channel.icon_emoji,
                "attachments": [
                    {
                        "color": color_map.get(alert.level, "#808080"),
                        "title": f"LiveKit Alert: {alert.service}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Level",
                                "value": alert.level.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Service",
                                "value": alert.service,
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.id,
                                "short": True
                            }
                        ],
                        "footer": "LiveKit Monitor",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            # Add details if present
            if alert.details:
                details_text = "\n".join([f"*{k}:* {v}" for k, v in alert.details.items()])
                payload["attachments"][0]["fields"].append({
                    "title": "Details",
                    "value": details_text,
                    "short": False
                })
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    channel.webhook_url,
                    json=payload
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack alert sent for {alert.service}: {alert.message}")
                        return True
                    else:
                        logger.error(f"Slack webhook returned status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


class LiveKitAlertManager:
    """
    Advanced alert management system for LiveKit monitoring.
    
    Manages alert rules, notification channels, and alert lifecycle.
    """
    
    def __init__(self):
        self.alert_rules: List[AlertRule] = []
        self.notification_channels: List[NotificationChannel] = []
        self.notifiers: Dict[type, AlertNotifier] = {
            EmailChannel: EmailNotifier(),
            WebhookChannel: WebhookNotifier(),
            SlackChannel: SlackNotifier()
        }
        
        # Alert tracking
        self.recent_alerts: Dict[str, datetime] = {}  # For cooldown tracking
        self.alert_history: List[Alert] = []
        
        logger.info("LiveKit Alert Manager initialized")
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        self.notification_channels.append(channel)
        logger.info(f"Added notification channel: {channel.name} ({type(channel).__name__})")
    
    async def process_alert(self, alert: Alert) -> None:
        """Process an alert through the alert system."""
        try:
            # Check cooldown
            cooldown_key = f"{alert.service}:{alert.level.value}:{hash(alert.message)}"
            
            if self._is_in_cooldown(cooldown_key):
                logger.debug(f"Alert in cooldown, skipping: {alert.message}")
                return
            
            # Record alert
            self.alert_history.append(alert)
            self.recent_alerts[cooldown_key] = alert.timestamp
            
            # Send notifications
            await self._send_notifications(alert)
            
            logger.info(f"Processed alert: {alert.level.value} - {alert.service} - {alert.message}")
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
    
    def _is_in_cooldown(self, cooldown_key: str) -> bool:
        """Check if an alert type is in cooldown period."""
        if cooldown_key not in self.recent_alerts:
            return False
        
        last_alert_time = self.recent_alerts[cooldown_key]
        cooldown_period = timedelta(minutes=15)  # Default cooldown
        
        return datetime.now(UTC) - last_alert_time < cooldown_period
    
    async def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications through configured channels."""
        for channel in self.notification_channels:
            if not channel.enabled:
                continue
            
            if alert.level not in channel.alert_levels:
                continue
            
            notifier = self.notifiers.get(type(channel))
            if not notifier:
                logger.warning(f"No notifier found for channel type: {type(channel)}")
                continue
            
            try:
                success = await notifier.send_alert(alert, channel)
                if success:
                    logger.debug(f"Alert sent via {channel.name}")
                else:
                    logger.warning(f"Failed to send alert via {channel.name}")
                    
            except Exception as e:
                logger.error(f"Error sending alert via {channel.name}: {e}")
    
    def evaluate_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Evaluate metrics against alert rules and generate alerts."""
        alerts = []
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            try:
                if self._evaluate_condition(rule.condition, metrics):
                    alert = Alert(
                        level=rule.level,
                        service=rule.service or "system",
                        message=f"Alert rule triggered: {rule.name}",
                        details={
                            "rule": rule.name,
                            "condition": rule.condition,
                            "description": rule.description,
                            "metrics": metrics
                        }
                    )
                    alerts.append(alert)
                    
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.name}: {e}")
        
        return alerts
    
    def _evaluate_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """Evaluate an alert condition against metrics."""
        try:
            # Simple condition evaluation
            # This is a basic implementation - in production, use a proper expression evaluator
            
            # Replace metric names with values
            expression = condition
            for key, value in metrics.items():
                expression = expression.replace(key, str(value))
            
            # Evaluate the expression
            return eval(expression)
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        now = datetime.now(UTC)
        last_24h = now - timedelta(hours=24)
        
        recent_alerts = [
            alert for alert in self.alert_history
            if alert.timestamp > last_24h
        ]
        
        stats = {
            "total_alerts_24h": len(recent_alerts),
            "alerts_by_level": {},
            "alerts_by_service": {},
            "active_channels": len([ch for ch in self.notification_channels if ch.enabled]),
            "active_rules": len([rule for rule in self.alert_rules if rule.enabled])
        }
        
        # Count by level
        for alert in recent_alerts:
            level = alert.level.value
            stats["alerts_by_level"][level] = stats["alerts_by_level"].get(level, 0) + 1
        
        # Count by service
        for alert in recent_alerts:
            service = alert.service
            stats["alerts_by_service"][service] = stats["alerts_by_service"].get(service, 0) + 1
        
        return stats


# Global alert manager instance
_alert_manager: Optional[LiveKitAlertManager] = None


def get_alert_manager() -> LiveKitAlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = LiveKitAlertManager()
    return _alert_manager


def initialize_default_alert_rules() -> None:
    """Initialize default alert rules."""
    manager = get_alert_manager()
    
    # High latency alert
    manager.add_alert_rule(AlertRule(
        name="High API Latency",
        condition="avg_api_latency_ms > 5000",
        level=AlertLevel.WARNING,
        service="api",
        description="API latency is above 5 seconds"
    ))
    
    # Low success rate alert
    manager.add_alert_rule(AlertRule(
        name="Low Connection Success Rate",
        condition="connection_success_rate < 0.8",
        level=AlertLevel.ERROR,
        service="connection",
        description="Connection success rate is below 80%"
    ))
    
    # High error rate alert
    manager.add_alert_rule(AlertRule(
        name="High Error Rate",
        condition="error_rate > 0.1",
        level=AlertLevel.ERROR,
        service="system",
        description="Error rate is above 10%"
    ))
    
    # Critical error rate alert
    manager.add_alert_rule(AlertRule(
        name="Critical Error Rate",
        condition="error_rate > 0.25",
        level=AlertLevel.CRITICAL,
        service="system",
        description="Error rate is above 25%"
    ))
    
    logger.info("Default alert rules initialized")
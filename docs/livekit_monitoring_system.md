# LiveKit Monitoring and Diagnostics System

Comprehensive monitoring and diagnostics system for LiveKit integration with health checks, performance metrics, alerting, and detailed logging.

## Overview

The LiveKit monitoring system provides:

- **Health Checks**: Automated testing of all LiveKit API services
- **Performance Metrics**: Real-time monitoring of system performance
- **Alerting System**: Multi-channel notifications for critical issues
- **Structured Logging**: Detailed operation logging with error codes
- **Health Endpoints**: HTTP endpoints for external monitoring

## Components

### 1. LiveKit System Monitor

The core monitoring component that performs health checks and tracks metrics.

```python
from src.monitoring.livekit_system_monitor import (
    LiveKitSystemMonitor,
    initialize_monitor,
    start_global_monitoring
)

# Initialize monitor
monitor = initialize_monitor(api_client, auth_manager)

# Start continuous monitoring
await start_global_monitoring()

# Get health status
health_summary = monitor.get_health_summary()
performance_metrics = monitor.get_performance_summary()
```

#### Health Checks

The monitor performs health checks on:

- **RoomService API**: Tests room listing and basic operations
- **Egress Service**: Validates recording and export capabilities
- **Ingress Service**: Checks media import functionality
- **SIP Service**: Tests SIP trunk availability
- **Authentication System**: Validates JWT token creation

#### Performance Metrics

Tracks key performance indicators:

- API latency and response times
- Connection success/failure rates
- Active rooms and participants
- Error rates and patterns
- System resource usage

### 2. Alert Management System

Advanced alerting with multiple notification channels.

```python
from src.monitoring.livekit_alerting import (
    get_alert_manager,
    EmailChannel,
    WebhookChannel,
    SlackChannel,
    AlertLevel
)

alert_manager = get_alert_manager()

# Add email notifications
email_channel = EmailChannel(
    name="admin_email",
    smtp_host="smtp.gmail.com",
    to_emails=["admin@example.com"],
    alert_levels={AlertLevel.ERROR, AlertLevel.CRITICAL}
)
alert_manager.add_notification_channel(email_channel)

# Add Slack notifications
slack_channel = SlackChannel(
    name="slack_alerts",
    webhook_url="https://hooks.slack.com/services/...",
    channel="#alerts"
)
alert_manager.add_notification_channel(slack_channel)
```

#### Alert Rules

Configurable rules for automatic alert generation:

```python
from src.monitoring.livekit_alerting import AlertRule

# High latency alert
high_latency_rule = AlertRule(
    name="High API Latency",
    condition="avg_api_latency_ms > 5000",
    level=AlertLevel.WARNING,
    service="api"
)
alert_manager.add_alert_rule(high_latency_rule)
```

#### Notification Channels

Supported notification channels:

- **Email**: SMTP-based email notifications
- **Webhook**: HTTP POST to custom endpoints
- **Slack**: Slack webhook integration

### 3. Structured Logging

Comprehensive logging with error codes and operation tracking.

```python
from src.monitoring.livekit_logging import (
    get_logger,
    operation_context,
    LiveKitErrorCode
)

logger = get_logger("livekit_service")

# Basic logging with context
logger.info(
    "Room created successfully",
    service="room",
    room_name="meeting-123",
    participant_id="user-456",
    latency_ms=125.3
)

# Error logging with error codes
logger.error(
    "Failed to create room",
    error_code=LiveKitErrorCode.ROOM_CREATION_FAILED,
    service="room",
    details={"reason": "Invalid configuration"}
)

# Operation context for tracking
with operation_context("create_room_with_sip", service="room") as ctx:
    # All logs within this context will include operation_id
    logger.info("Starting room creation")
    # ... perform operations ...
    logger.info("Room creation completed")
```

#### Error Codes

Standardized error codes for different categories:

- **Authentication**: `LK1001-LK1099`
- **Connection**: `LK1100-LK1199`
- **API**: `LK1200-LK1299`
- **Room**: `LK1300-LK1399`
- **Participant**: `LK1400-LK1499`
- **Media**: `LK1500-LK1599`
- **SIP**: `LK1600-LK1699`
- **Egress**: `LK1700-LK1799`
- **Ingress**: `LK1800-LK1899`
- **System**: `LK1900-LK1999`

### 4. Health Check Endpoints

HTTP endpoints for external monitoring systems.

```python
from src.monitoring.health_endpoints import health_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(health_router)
```

#### Available Endpoints

- `GET /health/` - Basic health check
- `GET /health/livekit` - Comprehensive LiveKit health status
- `GET /health/metrics` - Performance metrics
- `GET /health/detailed` - Detailed system status
- `GET /health/alerts` - System alerts
- `POST /health/alerts/{alert_id}/resolve` - Resolve alert
- `GET /health/readiness` - Kubernetes readiness probe
- `GET /health/liveness` - Kubernetes liveness probe

## Configuration

### Environment Variables

```bash
# Monitoring configuration
LIVEKIT_MONITORING_ENABLED=true
LIVEKIT_MONITORING_INTERVAL=60
LIVEKIT_METRICS_RETENTION_HOURS=24

# Alerting configuration
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_USERNAME=alerts@example.com
ALERT_EMAIL_PASSWORD=app_password
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=admin@example.com

ALERT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ALERT_WEBHOOK_URL=https://monitoring.example.com/webhook

# Logging configuration
LOG_LEVEL=INFO
LOG_STRUCTURED=true
LOG_DIR=logs
```

### Configuration File

Create `config/monitoring.yaml`:

```yaml
monitoring:
  enabled: true
  check_interval: 60
  metrics_retention_hours: 24
  
  health_checks:
    room_service: true
    egress_service: true
    ingress_service: true
    sip_service: true
    auth_system: true
  
  alert_rules:
    - name: "High API Latency"
      condition: "avg_api_latency_ms > 5000"
      level: "warning"
      service: "api"
      cooldown_minutes: 15
    
    - name: "Low Success Rate"
      condition: "connection_success_rate < 0.8"
      level: "error"
      service: "connection"
      cooldown_minutes: 10
  
  notification_channels:
    - type: "email"
      name: "admin_email"
      enabled: true
      config:
        smtp_host: "smtp.gmail.com"
        smtp_port: 587
        from_email: "alerts@example.com"
        to_emails: ["admin@example.com"]
      alert_levels: ["error", "critical"]
    
    - type: "slack"
      name: "slack_alerts"
      enabled: true
      config:
        webhook_url: "https://hooks.slack.com/services/..."
        channel: "#alerts"
        username: "LiveKit Monitor"
      alert_levels: ["warning", "error", "critical"]

logging:
  level: "INFO"
  structured: true
  format: "json"
  
  handlers:
    console:
      enabled: true
      level: "INFO"
    
    file:

      enabled: true
      level: "DEBUG"
      max_bytes: 50000000  # 50MB
      backup_count: 10
    
    error_file:
      enabled: true
      level: "ERROR"
      max_bytes: 10000000  # 10MB
      backup_count: 5
```

## Usage Examples

### Basic Monitoring Setup

```python
import asyncio
from src.monitoring.livekit_system_monitor import initialize_monitor, start_global_monitoring
from src.clients.livekit_api_client import get_api_client
from src.auth.livekit_auth import get_auth_manager

async def setup_monitoring():
    # Get required components
    api_client = get_api_client()
    auth_manager = get_auth_manager()
    
    # Initialize monitor
    monitor = initialize_monitor(
        api_client=api_client,
        auth_manager=auth_manager,
        check_interval=60,  # Check every minute
        metrics_retention_hours=24
    )
    
    # Add alert callback
    def alert_handler(alert):
        print(f"ALERT: [{alert.level.value}] {alert.service}: {alert.message}")
    
    monitor.add_alert_callback(alert_handler)
    
    # Start monitoring
    await start_global_monitoring()
    
    return monitor

# Run monitoring
monitor = asyncio.run(setup_monitoring())
```

### Advanced Alerting Configuration

```python
from src.monitoring.livekit_alerting import (
    get_alert_manager,
    initialize_default_alert_rules,
    EmailChannel,
    SlackChannel,
    AlertRule,
    AlertLevel
)

def setup_alerting():
    alert_manager = get_alert_manager()
    
    # Initialize default rules
    initialize_default_alert_rules()
    
    # Add custom alert rule
    custom_rule = AlertRule(
        name="Room Creation Failures",
        condition="room_creation_failures > 5",
        level=AlertLevel.CRITICAL,
        service="room",
        cooldown_minutes=5,
        description="Too many room creation failures"
    )
    alert_manager.add_alert_rule(custom_rule)
    
    # Configure email notifications
    email_channel = EmailChannel(
        name="critical_alerts",
        smtp_host="smtp.company.com",
        smtp_port=587,
        smtp_username="monitoring@company.com",
        smtp_password="secure_password",
        from_email="livekit-alerts@company.com",
        to_emails=["devops@company.com", "admin@company.com"],
        alert_levels={AlertLevel.CRITICAL}
    )
    alert_manager.add_notification_channel(email_channel)
    
    # Configure Slack notifications
    slack_channel = SlackChannel(
        name="dev_alerts",
        webhook_url="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
        channel="#livekit-alerts",
        username="LiveKit Monitor",
        icon_emoji=":warning:",
        alert_levels={AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL}
    )
    alert_manager.add_notification_channel(slack_channel)
    
    return alert_manager
```

### Structured Logging Integration

```python
from src.monitoring.livekit_logging import get_logger, operation_context, LiveKitErrorCode

# Get logger for your service
logger = get_logger("voice_ai_service")

async def handle_sip_call(call_id: str, caller_number: str):
    """Example of structured logging in SIP call handling."""
    
    with operation_context("handle_sip_call", service="sip") as ctx:
        try:
            logger.info(
                "SIP call received",
                operation_id=ctx.operation_id,
                call_id=call_id,
                caller_number=caller_number,
                service="sip"
            )
            
            # Create room for call
            room_name = f"sip-call-{call_id}"
            
            logger.log_room_event(
                event="room_creation_started",
                room_name=room_name,
                call_id=call_id
            )
            
            # Simulate room creation
            await asyncio.sleep(0.1)
            
            logger.log_room_event(
                event="room_created",
                room_name=room_name,
                call_id=call_id,
                participants_limit=2
            )
            
            # Log SIP events
            logger.log_sip_event(
                event="call_connected",
                call_id=call_id,
                trunk_name="novofon-trunk",
                caller_number=caller_number,
                room_name=room_name
            )
            
            return {"success": True, "room_name": room_name}
            
        except Exception as e:
            logger.error(
                "Failed to handle SIP call",
                error_code=LiveKitErrorCode.SIP_CALL_FAILED,
                operation_id=ctx.operation_id,
                call_id=call_id,
                caller_number=caller_number,
                service="sip",
                details={"error": str(e)}
            )
            raise
```

### Health Check Integration

```python
from fastapi import FastAPI
from src.monitoring.health_endpoints import health_router

# Create FastAPI app
app = FastAPI(title="LiveKit Voice AI Agent")

# Include health check endpoints
app.include_router(health_router, prefix="/api")

# Custom health check endpoint
@app.get("/api/health/voice-ai")
async def voice_ai_health():
    """Custom health check for Voice AI components."""
    monitor = get_monitor()
    if not monitor:
        return {"status": "unhealthy", "error": "Monitor not initialized"}
    
    # Check Voice AI specific components
    health_results = await monitor.run_health_checks()
    
    # Add custom checks
    voice_ai_status = {
        "stt_service": "healthy",  # Check STT service
        "tts_service": "healthy",  # Check TTS service
        "llm_service": "healthy",  # Check LLM service
    }
    
    overall_healthy = all(
        result.status.value == "healthy" 
        for result in health_results.values()
    ) and all(
        status == "healthy" 
        for status in voice_ai_status.values()
    )
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "livekit_services": {
            service: result.status.value 
            for service, result in health_results.items()
        },
        "voice_ai_services": voice_ai_status,
        "timestamp": datetime.now(UTC).isoformat()
    }
```

## Monitoring Dashboards

### Grafana Integration

Create Grafana dashboard using the metrics endpoints:

```json
{
  "dashboard": {
    "title": "LiveKit System Monitoring",
    "panels": [
      {
        "title": "Service Health Status",
        "type": "stat",
        "targets": [
          {
            "url": "http://localhost:8000/health/livekit",
            "format": "json"
          }
        ]
      },
      {
        "title": "API Latency",
        "type": "graph",
        "targets": [
          {
            "url": "http://localhost:8000/health/metrics",
            "format": "json",
            "metric": "avg_api_latency_ms"
          }
        ]
      },
      {
        "title": "Connection Success Rate",
        "type": "gauge",
        "targets": [
          {
            "url": "http://localhost:8000/health/metrics",
            "format": "json",
            "metric": "connection_success_rate"
          }
        ]
      },
      {
        "title": "Active Rooms and Participants",
        "type": "graph",
        "targets": [
          {
            "url": "http://localhost:8000/health/metrics",
            "format": "json",
            "metrics": ["active_rooms", "active_participants"]
          }
        ]
      }
    ]
  }
}
```

### Prometheus Integration

Export metrics to Prometheus:

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
api_requests_total = Counter('livekit_api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
api_request_duration = Histogram('livekit_api_request_duration_seconds', 'API request duration')
active_rooms = Gauge('livekit_active_rooms', 'Number of active rooms')
active_participants = Gauge('livekit_active_participants', 'Number of active participants')

def export_metrics_to_prometheus(monitor: LiveKitSystemMonitor):
    """Export monitor metrics to Prometheus."""
    metrics = monitor.get_performance_summary()
    
    active_rooms.set(metrics['active_rooms'])
    active_participants.set(metrics['active_participants'])
    
    # Update API metrics from monitor data
    for latency in monitor.metrics.api_latency[-10:]:  # Last 10 measurements
        api_request_duration.observe(latency / 1000)  # Convert to seconds

# Start Prometheus metrics server
start_http_server(8001)
```

## Troubleshooting

### Common Issues

#### 1. Monitor Not Starting

```python
# Check if monitor is initialized
monitor = get_monitor()
if not monitor:
    print("Monitor not initialized. Call initialize_monitor() first.")

# Check monitoring status
if not monitor._monitoring_active:
    print("Monitoring not active. Call start_global_monitoring().")
```

#### 2. Health Checks Failing

```python
# Run individual health checks for debugging
monitor = get_monitor()

# Test room service
room_result = await monitor._check_room_service()
print(f"Room service: {room_result.status.value}")
if room_result.error:
    print(f"Error: {room_result.error}")

# Test auth system
auth_result = await monitor._check_auth_system()
print(f"Auth system: {auth_result.status.value}")
if auth_result.error:
    print(f"Error: {auth_result.error}")
```

#### 3. Alerts Not Being Sent

```python
# Check alert manager configuration
alert_manager = get_alert_manager()

print(f"Active rules: {len([r for r in alert_manager.alert_rules if r.enabled])}")
print(f"Active channels: {len([c for c in alert_manager.notification_channels if c.enabled])}")

# Test alert creation
test_alert = Alert(
    level=AlertLevel.INFO,
    service="test",
    message="Test alert"
)
await alert_manager.process_alert(test_alert)
```

#### 4. High Memory Usage

```python
# Check metrics history size
monitor = get_monitor()
print(f"Metrics history size: {len(monitor.metrics_history)}")
print(f"Error log size: {len(monitor.error_log)}")
print(f"API latency measurements: {len(monitor.metrics.api_latency)}")

# Manually trigger cleanup
await monitor._cleanup_old_data()
```

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
from src.monitoring.livekit_logging import setup_logging

# Enable debug logging
setup_logging(level=logging.DEBUG)

# Get debug logger
debug_logger = get_logger("debug", level=logging.DEBUG)
debug_logger.debug("Debug logging enabled")
```

### Performance Tuning

#### Optimize Check Intervals

```python
# For high-traffic systems, increase check interval
monitor = initialize_monitor(
    api_client=api_client,
    auth_manager=auth_manager,
    check_interval=300,  # 5 minutes instead of 1 minute
    metrics_retention_hours=12  # Reduce retention
)
```

#### Limit Metrics Storage

```python
# Limit metrics history to prevent memory growth
monitor.metrics_history = deque(maxlen=100)  # Keep only 100 snapshots
monitor.error_log = deque(maxlen=200)  # Keep only 200 errors
```

## Best Practices

### 1. Monitoring Strategy

- **Start Simple**: Begin with basic health checks and gradually add more detailed monitoring
- **Set Appropriate Intervals**: Balance between timely detection and system load
- **Use Structured Logging**: Always include relevant context in log messages
- **Monitor What Matters**: Focus on metrics that directly impact user experience

### 2. Alert Configuration

- **Avoid Alert Fatigue**: Set appropriate thresholds to prevent too many false positives
- **Use Cooldown Periods**: Prevent spam from repeated alerts for the same issue
- **Escalation Paths**: Configure different notification channels for different severity levels
- **Test Regularly**: Verify that alerts are working by testing notification channels

### 3. Performance Considerations

- **Async Operations**: Use async/await for all I/O operations to prevent blocking
- **Resource Limits**: Set limits on metrics storage to prevent memory leaks
- **Efficient Queries**: Optimize health check queries to minimize impact on LiveKit services
- **Batch Operations**: Group related operations to reduce overhead

### 4. Security

- **Secure Credentials**: Store SMTP passwords and webhook URLs securely
- **API Key Protection**: Ensure API keys are not logged or exposed in error messages
- **Access Control**: Restrict access to health endpoints in production
- **Audit Logging**: Log all administrative actions for security auditing

## Integration with Existing Systems

### Docker Compose

```yaml
version: '3.8'
services:
  voice-ai-agent:
    build: .
    environment:
      - LIVEKIT_MONITORING_ENABLED=true
      - LIVEKIT_MONITORING_INTERVAL=60
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"  # Main application
      - "8001:8001"  # Prometheus metrics
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/liveness"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: livekit-voice-ai
spec:
  replicas: 2
  selector:
    matchLabels:
      app: livekit-voice-ai
  template:
    metadata:
      labels:
        app: livekit-voice-ai
    spec:
      containers:
      - name: voice-ai-agent
        image: livekit-voice-ai:latest
        ports:
        - containerPort: 8000
        env:
        - name: LIVEKIT_MONITORING_ENABLED
          value: "true"
        livenessProbe:
          httpGet:
            path: /health/liveness
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### CI/CD Integration

```yaml
# GitHub Actions example
name: Health Check Tests
on: [push, pull_request]

jobs:
  health-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run monitoring tests
      run: |
        pytest tests/test_livekit_system_monitor.py -v
        pytest tests/test_livekit_alerting.py -v
        pytest tests/test_livekit_logging.py -v
    
    - name: Test health endpoints
      run: |
        python -m pytest tests/test_health_endpoints.py -v
```

This comprehensive monitoring system provides robust observability for your LiveKit integration, ensuring reliable operation and quick issue detection.e:
  
    enabled: true
      level: "DEBUG"
      file: "logs/livekit.log"
      max_size: "50MB"
      backup_count: 10
    
    error_file:
      enabled: true
      level: "ERROR"
      file: "logs/livekit_errors.log"
      max_size: "10MB"
      backup_count: 5
```

## Usage Examples

### Basic Health Monitoring

```python
import asyncio
from src.monitoring.livekit_system_monitor import initialize_monitor, start_global_monitoring

async def basic_monitoring():
    # Initialize
    monitor = initialize_monitor(api_client, auth_manager)
    
    # Start monitoring
    await start_global_monitoring()
    
    # Get status
    health = monitor.get_health_summary()
    metrics = monitor.get_performance_summary()
    
    print(f"System Status: {health['overall_status']}")
    print(f"Healthy Services: {health['healthy_services']}/{health['total_services']}")
    print(f"Average Latency: {metrics['avg_api_latency_ms']:.2f}ms")
```

### Custom Alert Rules

```python
from src.monitoring.livekit_alerting import get_alert_manager, AlertRule, AlertLevel

alert_manager = get_alert_manager()

# Custom alert for room capacity
room_capacity_rule = AlertRule(
    name="Room Capacity Warning",
    condition="active_rooms > 100",
    level=AlertLevel.WARNING,
    service="room",
    cooldown_minutes=30,
    description="High number of active rooms"
)

alert_manager.add_alert_rule(room_capacity_rule)
```

### Integration with FastAPI

```python
from fastapi import FastAPI
from src.monitoring.health_endpoints import health_router

app = FastAPI()
app.include_router(health_router)

# Health endpoints will be available at:
# GET /health/livekit - LiveKit service health
# GET /health/metrics - Performance metrics
# GET /health/alerts - System alerts
```

## Monitoring Dashboards

### Prometheus Integration

The system can export metrics to Prometheus:

```python
from src.monitoring.prometheus_exporter import setup_prometheus_metrics

# Set up Prometheus metrics
setup_prometheus_metrics(monitor)

# Metrics will be available at /metrics endpoint
```

### Grafana Dashboard

Import the provided Grafana dashboard configuration:

```json
{
  "dashboard": {
    "title": "LiveKit System Monitor",
    "panels": [
      {
        "title": "Service Health",
        "type": "stat",
        "targets": [
          {
            "expr": "livekit_service_health",
            "legendFormat": "{{service}}"
          }
        ]
      },
      {
        "title": "API Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "livekit_api_latency_ms",
            "legendFormat": "Latency"
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

### Common Issues

#### High Memory Usage

If monitoring uses too much memory:

```python
# Reduce metrics retention
monitor = LiveKitSystemMonitor(
    api_client=api_client,
    auth_manager=auth_manager,
    metrics_retention_hours=6  # Reduce from 24 to 6 hours
)

# Limit metrics history
monitor.metrics_history = deque(maxlen=100)  # Reduce from 1000
```

#### Alert Spam

To prevent alert spam:

```python
# Increase cooldown periods
alert_rule = AlertRule(
    name="High Latency",
    condition="avg_api_latency_ms > 5000",
    level=AlertLevel.WARNING,
    cooldown_minutes=60  # Increase cooldown
)

# Use alert level filtering
email_channel = EmailChannel(
    name="critical_only",
    alert_levels={AlertLevel.CRITICAL}  # Only critical alerts
)
```

#### Missing Health Checks

If some services show as unhealthy:

```python
# Check service availability
try:
    rooms = await api_client.list_rooms()
    print("RoomService is available")
except Exception as e:
    print(f"RoomService error: {e}")

# Verify API credentials
try:
    token = auth_manager.create_participant_token("test", "test-room")
    print("Auth system is working")
except Exception as e:
    print(f"Auth error: {e}")
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
from src.monitoring.livekit_logging import setup_logging

# Enable debug logging
setup_logging(level=logging.DEBUG)

# Get debug logger
logger = get_logger("debug", level=logging.DEBUG)
logger.debug("Debug information", details={"key": "value"})
```

## Performance Considerations

### Resource Usage

The monitoring system is designed to be lightweight:

- **Memory**: ~10-50MB depending on retention settings
- **CPU**: <1% during normal operation
- **Network**: Minimal overhead for health checks
- **Storage**: Log rotation prevents disk space issues

### Optimization Tips

1. **Adjust Check Intervals**: Increase interval for less critical environments
2. **Limit Metrics Retention**: Reduce retention period for memory savings
3. **Filter Alerts**: Use appropriate alert levels to reduce noise
4. **Batch Operations**: Group related operations for efficiency

## Security Considerations

### Sensitive Data Protection

The monitoring system protects sensitive information:

```python
# API keys are masked in logs
logger.info("API call made", api_key="***masked***")

# JWT tokens are not logged in full
logger.info("Token created", token_length=len(token))

# Error details exclude sensitive data
logger.error("Auth failed", error_code="LK1001", details={"endpoint": "/auth"})
```

### Access Control

Secure monitoring endpoints:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@health_router.get("/detailed")
async def get_detailed_status(
    token: str = Depends(security),
    monitor: LiveKitSystemMonitor = Depends(get_system_monitor)
):
    # Verify token before returning sensitive data
    if not verify_monitoring_token(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return monitor.get_detailed_metrics()
```

## API Reference

### LiveKitSystemMonitor

Main monitoring class with comprehensive health checking and metrics collection.

#### Methods

- `run_health_checks()` - Execute all health checks
- `get_health_summary()` - Get overall health status
- `get_performance_summary()` - Get performance metrics
- `get_detailed_metrics()` - Get comprehensive system status
- `record_api_latency(ms)` - Record API call latency
- `record_room_created()` - Track room creation
- `record_participant_joined()` - Track participant activity

### LiveKitAlertManager

Advanced alert management with multiple notification channels.

#### Methods

- `add_alert_rule(rule)` - Add custom alert rule
- `add_notification_channel(channel)` - Add notification channel
- `process_alert(alert)` - Process and send alert
- `evaluate_metrics(metrics)` - Check metrics against rules

### LiveKitLogger

Structured logging with error codes and operation tracking.

#### Methods

- `info(message, **context)` - Log info message
- `error(message, error_code, **context)` - Log error with code
- `log_api_call(method, endpoint, **details)` - Log API call
- `log_room_event(event, room_name, **details)` - Log room event

## Migration Guide

### From Basic Logging

Replace basic logging:

```python
# Before
import logging
logger = logging.getLogger(__name__)
logger.info("Room created")

# After
from src.monitoring.livekit_logging import get_logger
logger = get_logger(__name__)
logger.info("Room created", service="room", room_name="meeting-123")
```

### From Manual Health Checks

Replace manual health checks:

```python
# Before
async def check_livekit_health():
    try:
        rooms = await api_client.list_rooms()
        return {"status": "healthy", "rooms": len(rooms)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# After
from src.monitoring.livekit_system_monitor import get_monitor
monitor = get_monitor()t_api
hea_client
from src.auth.livekit_auth import get_auth_manager

async def setup_monitoring():
    # Initialize components
    api_client = get_api_client()
    auth_manager = get_auth_manager()
    
    # Initialize monitor
    monitor = initialize_monitor(api_client, auth_manager)
    
    # Start monitoring
    await start_global_monitoring()
    
    print("Monitoring system started")

# Run setup
asyncio.run(setup_monitoring())
```

### Custols={"resulm Alt": result}
        )
    except Exception as e:
        return HealthCheckResult(
            service="new_service",
            status=HealthStatus.UNHEALTHY,
            error=str(e)
        )
```

2. Add to `run_health_checks()` method:

```python
checks["new_service"] = await self._check_new_service()
```

### Adding New Alert Channels

To add a new notification channel:

1. Create channel configuration class:

```python
@dataclass
class NewChannel(NotificationChannel):
    api_key: str = ""
    endpoint: str = ""
```

2. Create notifier class:

```python
class NewNotifier(AlertNotifier):
    async def send_alert(self, alert: Alert, channrouter(healtel:h_router)

# Custom endpoint using monitor
@app.get("/api/system/status")
async def get_system_status():
    from src.monitoring.livekit_system_monitor import get_monitor
    
    monitor = get_monitor()
    if not monitor:
        return {"error": "Monitor not initialized"}
    
    return monitor.get_detailed_metrics()
```

## Monitoring Best Practices

### 1. Health Check Frequency

- **Production**: 60-300 seconds
- **Development**: 30-60 seconds
- **Critical systems**: 15-30 seconds

### 2. Alert Thresholds

Recommended thresholds:

- **API Latency**: Warning > 2s, Error > 5s
- **Success Rate**: Warning < 95%, Error < 90%
- **Error Rate**: Warning > 5%, Error > 10%
- **SIP Quality**: Warning < 4.0 MOS, Error < 3.5 MOS

### 3. Log Retention

- **Application logs**: 30 days
- **Error logs**: 90 days
- **Metrics history**: 7 days
- **Alert history**: 30 days

### 4. Notification Channels

Configure multiple channels for redundancy:

- **Critical alerts**: Email + Slack + PagerDuty
- **Error alerts**: Email + Slack
- **Warning alerts**: Slack only

## Troubleshooting

### Common Issues

#### Monitor Not Starting

```python
# Check if API client is properly configured
from src.clients.livekit_api_client import get_api_client

client = get_api_client()
health = await client.health_check()
print(f"API Client Health: {health}")
```

#### High Memory Usage

```python
# Reduce metrics retention
monitor = initialize_monitor(
    api_client,
    auth_manager,
    metrics_retention_hours=6  # Reduce from default 24h
)
```

#### Missing Alerts

```python
# Check alert manager configuration
from src.monitoring.livekit_alerting import get_alert_manager

alert_manager = get_alert_manager()
stats = alert_manager.get_alert_statistics()
print(f"Alert Statistics: {stats}")
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
from src.monitoring.livekit_logging import setup_logging
import logging

# Enable debug logging
setup_logging(level=logging.DEBUG)

# Get debug logger
logger = get_logger("debug", level=logging.DEBUG)
logger.debug("Debug mode enabled")
```

## Performance Impact

### Resource Usage

- **CPU**: < 5% additional overhead
- **Memory**: ~50-100MB for metrics storage
- **Network**: Minimal (health checks only)
- **Disk**: ~10-50MB/day for logs

### Optimization Tips

1. **Adjust check intervals** based on criticality
2. **Use appropriate log levels** in production
3. **Configure log rotation** to prevent disk filling
4. **Monitor the monitor** - set up alerts for monitoring system itself

## Integration with External Systems

### Prometheus Integration

```python
# Export metrics to Prometheus
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics
api_calls_total = Counter('livekit_api_calls_total', 'Total API calls', ['service', 'status'])
api_latency = Histogram('livekit_api_latency_seconds', 'API call latency', ['service'])
active_rooms = Gauge('livekit_active_rooms', 'Number of active rooms')

# Update metrics in monitor callbacks
def prometheus_callback(alert):
    if alert.service == "room_service":
        api_calls_total.labels(service="room", status="error").inc()
```

### Grafana Dashboards

Key metrics to visualize:

- API response times (percentiles)
- Success/error rates over time
- Active rooms and participants
- Alert frequency by service
- System resource usage

### ELK Stack Integration

```python
# Configure structured logging for ELK
from src.monitoring.livekit_logging import setup_logging

setup_logging(
    level="INFO",
    format="json",  # JSON format for Elasticsearch
    include_trace=True
)
```

## Security Considerations

### Sensitive Data Handling

- API keys are masked in logs
- JWT tokens are not logged in full
- Personal participant data is anonymized
- Health check endpoints don't expose secrets

### Access Control

```python
# Secure health endpoints
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/health/detailed")
async def secure_health_check(token: str = Depends(security)):
    # Validate token
    if not validate_monitoring_token(token):
        raise HTTPException(status_code=401)
    
    return get_detailed_metrics()
```

## Maintenance

### Regular Tasks

1. **Log rotation**: Automated via configuration
2. **Metrics cleanup**: Automatic based on retention settings
3. **Alert review**: Weekly review of alert patterns
4. **Threshold tuning**: Monthly adjustment based on trends

### Updates and Upgrades

- Monitor system compatibility with LiveKit updates
- Test alert channels regularly
- Update error code mappings for new API versions
- Review and update alert thresholds based on system changes

## Support and Troubleshooting

For issues with the monitoring system:

1. Check logs in `logs/livekit.log` and `logs/livekit_errors.log`
2. Verify API client connectivity
3. Test alert channels manually
4. Review configuration files
5. Check system resources (CPU, memory, disk)

The monitoring system is designed to be self-healing and will attempt to recover from transient failures automatically.
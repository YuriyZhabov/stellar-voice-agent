# Voice AI Agent Monitoring System

## Overview

The Voice AI Agent includes a comprehensive monitoring system that provides real-time health checks, metrics collection, alerting, and dashboard-ready data export. The monitoring system is designed to ensure high availability and performance of all critical components.

## Architecture

The monitoring system consists of four main components:

### 1. Health Monitor (`src/monitoring/health_monitor.py`)
- **Purpose**: Monitors the health of all critical system components
- **Features**:
  - Automated health checks for STT, LLM, TTS, database, Redis, LiveKit, and orchestrator
  - Configurable health thresholds and check intervals
  - Health status aggregation and trending
  - Integration with metrics collection
  - Support for custom health check functions

### 2. Alert Manager (`src/monitoring/alerting.py`)
- **Purpose**: Generates and manages alerts for system failures and performance issues
- **Features**:
  - Rule-based alert generation
  - Multiple notification channels (webhook, log, email)
  - Alert deduplication and rate limiting
  - Alert lifecycle management (active, acknowledged, resolved)
  - Integration with health monitoring

### 3. Metrics Exporter (`src/monitoring/metrics_exporter.py`)
- **Purpose**: Exports metrics to external monitoring tools
- **Features**:
  - Prometheus metrics export (push and pull)
  - JSON export for custom monitoring systems
  - Configurable export intervals
  - Multiple exporter support
  - Health checks for export destinations

### 4. Dashboard Manager (`src/monitoring/dashboard.py`)
- **Purpose**: Provides dashboard-ready metrics and visualizations
- **Features**:
  - Pre-configured dashboard templates
  - Real-time metrics aggregation
  - Custom dashboard creation
  - Multiple chart types and visualizations
  - Export capabilities for external dashboards

## Configuration

### Environment Variables

```bash
# Alert webhook URL (optional)
ALERT_WEBHOOK_URL=https://your-webhook-endpoint.com/alerts

# Prometheus Pushgateway URL (optional)
PROMETHEUS_PUSHGATEWAY_URL=http://prometheus-pushgateway:9091

# Monitoring intervals (optional, defaults shown)
HEALTH_CHECK_INTERVAL=30
ALERT_CHECK_INTERVAL=60
METRICS_EXPORT_INTERVAL=30
DASHBOARD_UPDATE_INTERVAL=30
```

### Health Check Thresholds

Default thresholds can be customized when registering components:

```python
from src.monitoring.health_monitor import HealthThreshold

custom_threshold = HealthThreshold(
    response_time_ms=3000.0,    # 3 seconds
    success_rate_percent=90.0,  # 90%
    error_rate_percent=10.0,    # 10%
    memory_usage_percent=80.0,  # 80%
    cpu_usage_percent=75.0,     # 75%
    disk_usage_percent=85.0     # 85%
)
```

## API Endpoints

The monitoring system exposes several HTTP endpoints:

### Health Check Endpoints

#### `GET /health`
Basic health check endpoint returning overall system status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "healthy_components": 4,
  "total_components": 4,
  "health_percentage": 100.0
}
```

#### `GET /health/detailed`
Detailed health check with individual component status.

**Response:**
```json
{
  "status": "healthy",
  "last_check": "2024-01-15T10:30:00Z",
  "healthy_components": 4,
  "total_components": 4,
  "health_percentage": 100.0,
  "components": {
    "stt_client": {
      "component_type": "stt_client",
      "component_name": "stt_client",
      "status": "healthy",
      "last_check": "2024-01-15T10:30:00Z",
      "response_time_ms": 150.5,
      "success_rate": 98.5,
      "error_rate": 1.5
    }
  }
}
```

### Metrics Endpoints

#### `GET /metrics`
Prometheus-compatible metrics endpoint.

**Response:** Plain text Prometheus exposition format
```
# HELP system_health_status Voice AI Agent metric
# TYPE system_health_status gauge
system_health_status 1.0 1705315800000

# HELP component_health_response_time_ms Voice AI Agent metric
# TYPE component_health_response_time_ms gauge
component_health_response_time_ms{component="stt_client"} 150.5 1705315800000
```

### Alert Endpoints

#### `GET /alerts`
Get active alerts and summary.

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert-123",
      "name": "component_unhealthy",
      "severity": "high",
      "status": "active",
      "message": "Component stt_client is unhealthy: Connection timeout",
      "component": "stt_client",
      "created_at": "2024-01-15T10:25:00Z",
      "updated_at": "2024-01-15T10:25:00Z"
    }
  ],
  "summary": {
    "total_active": 1,
    "total_resolved": 5,
    "active_by_severity": {
      "critical": 0,
      "high": 1,
      "medium": 0,
      "low": 0,
      "info": 0
    }
  }
}
```

### Dashboard Endpoints

#### `GET /dashboards`
List available dashboards.

**Response:**
```json
{
  "dashboards": [
    {
      "id": "system_overview",
      "title": "System Overview",
      "description": "High-level system health and performance metrics",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "api_performance",
      "title": "API Performance",
      "description": "API usage, latency, and error metrics",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### `GET /dashboard/{dashboard_id}`
Get specific dashboard data.

**Response:**
```json
{
  "id": "system_overview",
  "title": "System Overview",
  "description": "High-level system health and performance metrics",
  "refresh_interval": 30,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "panels": [
    {
      "id": "system_health",
      "title": "System Health",
      "description": "Overall system health status",
      "panel_type": "metrics",
      "layout": {"width": 6, "height": 4},
      "metrics": [
        {
          "name": "system_health_percentage",
          "value": 100.0,
          "unit": "%",
          "timestamp": "2024-01-15T10:30:00Z",
          "chart_type": "gauge",
          "color": "green",
          "threshold_warning": 80.0,
          "threshold_critical": 60.0
        }
      ]
    }
  ]
}
```

## Default Dashboards

### System Overview
- System health percentage
- Component status table
- Active alerts
- Performance metrics trends

### API Performance
- Request volume and rate
- Response time distribution
- Error rates and types
- Per-endpoint performance

### AI Services
- STT service metrics
- LLM service metrics
- TTS service metrics
- AI service costs and usage

### Infrastructure
- System resources (CPU, memory, disk)
- Database performance
- Redis cache metrics
- LiveKit service metrics
- Network usage

## Alert Rules

### Default Alert Rules

1. **System Unhealthy** (Critical)
   - Triggered when overall system health is unhealthy
   - Cooldown: 5 minutes

2. **System Degraded** (High)
   - Triggered when system performance is degraded
   - Cooldown: 10 minutes

3. **Component Unhealthy** (High)
   - Triggered when any component is unhealthy
   - Cooldown: 5 minutes

4. **Component High Latency** (Medium)
   - Triggered when component response time > 5 seconds
   - Cooldown: 15 minutes

5. **Component Low Success Rate** (Medium)
   - Triggered when component success rate < 80%
   - Cooldown: 10 minutes

### Custom Alert Rules

You can add custom alert rules programmatically:

```python
from src.monitoring.alerting import AlertRule, AlertSeverity

custom_rule = AlertRule(
    name="high_memory_usage",
    condition=lambda data: data.get("memory_usage", 0) > 90,
    severity=AlertSeverity.HIGH,
    message_template="High memory usage detected: {memory_usage}%",
    cooldown_minutes=15,
    max_alerts_per_hour=4
)

alert_manager.add_rule(custom_rule)
```

## Notification Channels

### Log Channel
Sends alerts to application logs.

```python
from src.monitoring.alerting import LogChannel

log_channel = LogChannel(log_level="ERROR")
alert_manager.add_channel("log", log_channel)
```

### Webhook Channel
Sends alerts to HTTP webhook endpoints.

```python
from src.monitoring.alerting import WebhookChannel

webhook_channel = WebhookChannel(
    webhook_url="https://your-webhook.com/alerts",
    timeout=10.0,
    headers={"Authorization": "Bearer your-token"}
)
alert_manager.add_channel("webhook", webhook_channel)
```

## Metrics Export

### Prometheus Export

#### Push Mode
Automatically pushes metrics to Prometheus Pushgateway:

```python
from src.monitoring.metrics_exporter import PrometheusExporter

prometheus_exporter = PrometheusExporter(
    pushgateway_url="http://prometheus-pushgateway:9091",
    job_name="voice_ai_agent",
    push_interval=15.0
)
```

#### Pull Mode
Exposes metrics endpoint for Prometheus scraping at `/metrics`.

### JSON Export
Exports metrics to JSON files or HTTP endpoints:

```python
from src.monitoring.metrics_exporter import JSONExporter

# File export
json_exporter = JSONExporter(file_path="./metrics/metrics.json")

# HTTP export
json_exporter = JSONExporter(endpoint_url="https://your-metrics-api.com/ingest")
```

## Integration with External Tools

### Grafana
1. Configure Prometheus data source
2. Import dashboard templates from `dashboards/grafana/`
3. Use `/dashboard/{id}` endpoints for custom panels

### Datadog
1. Configure webhook channel with Datadog webhook URL
2. Use JSON exporter to send metrics to Datadog API
3. Create custom dashboards using exported data

### New Relic
1. Configure webhook alerts
2. Use metrics export to send data to New Relic Insights
3. Create custom dashboards and alerts

## Troubleshooting

### Common Issues

1. **Health checks failing**
   - Check component connectivity
   - Verify health check thresholds
   - Review component logs

2. **Alerts not being sent**
   - Verify notification channels are configured
   - Check alert rule conditions
   - Review rate limiting settings

3. **Metrics not exporting**
   - Verify exporter configuration
   - Check network connectivity to export destinations
   - Review export interval settings

4. **Dashboard data not updating**
   - Check dashboard update interval
   - Verify health monitor is running
   - Review component registration

### Debugging

Enable debug logging to troubleshoot monitoring issues:

```python
import logging
logging.getLogger("src.monitoring").setLevel(logging.DEBUG)
```

### Performance Considerations

- Health check intervals should balance freshness with system load
- Metrics export intervals should consider network bandwidth
- Alert rate limiting prevents notification spam
- Dashboard updates can be resource-intensive with many metrics

## Best Practices

1. **Health Check Design**
   - Keep health checks lightweight and fast
   - Use appropriate timeouts
   - Include meaningful error messages

2. **Alert Configuration**
   - Set appropriate severity levels
   - Use cooldown periods to prevent spam
   - Include actionable information in alert messages

3. **Metrics Collection**
   - Collect metrics that matter for your use case
   - Use appropriate metric types (counter, gauge, histogram)
   - Include relevant labels for filtering

4. **Dashboard Design**
   - Focus on key performance indicators
   - Use appropriate visualization types
   - Group related metrics together

5. **Monitoring Monitoring**
   - Monitor the monitoring system itself
   - Set up alerts for monitoring failures
   - Regularly review and update thresholds
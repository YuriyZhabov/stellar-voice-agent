# Prometheus Health Check and Diagnostic System

## Overview

The Prometheus Health Check and Diagnostic System provides comprehensive monitoring, health checking, and troubleshooting capabilities for Prometheus monitoring services in the Voice AI Agent system.

## Features

### 🔍 Comprehensive Health Checking
- **Service Status Validation**: Checks if Prometheus service is running and accessible
- **Configuration Validation**: Validates YAML syntax and configuration structure
- **Endpoint Accessibility**: Tests all critical Prometheus endpoints
- **Target Connectivity**: Verifies scrape targets are reachable
- **Performance Monitoring**: Measures response times and service metrics

### 🛠️ Diagnostic Capabilities
- **Root Cause Analysis**: Identifies potential causes of Prometheus failures
- **Automated Troubleshooting**: Provides step-by-step recovery procedures
- **Log Analysis**: Examines container logs for error patterns
- **System Information**: Collects relevant system and environment data
- **Recovery Recommendations**: Suggests specific actions to resolve issues

### 📊 Reporting and Monitoring
- **Health Reports**: Generates comprehensive health status reports
- **JSON Export**: Saves diagnostic data in structured format
- **Integration Ready**: Easy integration with existing monitoring systems
- **Real-time Monitoring**: Supports continuous health monitoring loops

## Components

### Core Classes

#### `PrometheusHealthChecker`
Main class providing comprehensive health checking and diagnostic capabilities.

```python
from monitoring.prometheus_health import PrometheusHealthChecker

checker = PrometheusHealthChecker(
    prometheus_url="http://localhost:9091",
    config_path="monitoring/prometheus/prometheus.yml",
    timeout=10
)

# Perform comprehensive health check
health_result = await checker.comprehensive_health_check()
print(f"Status: {health_result.status}")

# Diagnose issues if unhealthy
if health_result.status != "healthy":
    diagnosis = checker.diagnose_failures(health_result)
    print(f"Issues: {diagnosis['issues_found']}")

checker.close()
```

#### `PrometheusHealthResult`
Data class containing health check results with detailed status information.

#### `PrometheusConfigStatus`
Data class containing configuration validation results and recommendations.

### Convenience Functions

#### `check_prometheus_health()`
Quick health check function for simple use cases.

```python
from monitoring.prometheus_health import check_prometheus_health

health_result = await check_prometheus_health()
if health_result.status == "healthy":
    print("✅ Prometheus is healthy!")
else:
    print(f"❌ Issues: {health_result.error_messages}")
```

#### `diagnose_prometheus_issues()`
Comprehensive diagnostic function for troubleshooting.

```python
from monitoring.prometheus_health import diagnose_prometheus_issues

diagnosis = await diagnose_prometheus_issues()
print(f"Root causes: {diagnosis['root_causes']}")
print(f"Recovery steps: {diagnosis['troubleshooting_steps']}")
```

#### `generate_prometheus_report()`
Generate comprehensive health and diagnostic report.

```python
from monitoring.prometheus_health import generate_prometheus_report

report = await generate_prometheus_report()
# Save report
with open('prometheus_report.json', 'w') as f:
    json.dump(report, f, indent=2)
```

### Command-Line Tools

#### `scripts/prometheus_diagnostics.py`
Comprehensive diagnostic script for command-line usage.

```bash
# Basic diagnostics
python scripts/prometheus_diagnostics.py

# Custom Prometheus URL
python scripts/prometheus_diagnostics.py --url http://localhost:9091

# Save diagnostic report
python scripts/prometheus_diagnostics.py --output diagnostics.json

# Verify fix after troubleshooting
python scripts/prometheus_diagnostics.py --verify

# Verbose output
python scripts/prometheus_diagnostics.py --verbose
```

## Integration

### Health Check Integration

The Prometheus health checker is integrated into the main application health system:

```python
from health import comprehensive_health_check

health_data = comprehensive_health_check()
prometheus_status = health_data["checks"]["prometheus"]
print(f"Prometheus: {prometheus_status}")
```

### Docker Health Checks

The system includes Docker-compatible health checks:

```bash
# Container health check
python healthcheck.py
```

### Configuration

Prometheus health checking can be configured via `config/prometheus_health.yaml`:

```yaml
prometheus:
  url: "http://localhost:9091"
  config_path: "monitoring/prometheus/prometheus.yml"
  health_check:
    timeout: 10
    retry_attempts: 3
    retry_delay: 2

targets:
  expected:
    - "voice-ai-agent:8000"
    - "voice-ai-agent:8001"
  check_timeout: 5
```

## Usage Examples

### Basic Health Monitoring

```python
import asyncio
from monitoring.prometheus_health import check_prometheus_health

async def monitor_prometheus():
    while True:
        health = await check_prometheus_health()
        
        if health.status == "healthy":
            print("✅ Prometheus healthy")
        else:
            print(f"⚠️ Prometheus issues: {health.error_messages}")
            # Send alert or take corrective action
        
        await asyncio.sleep(60)  # Check every minute

# Run monitoring
asyncio.run(monitor_prometheus())
```

### Automated Diagnostics

```python
from monitoring.prometheus_health import diagnose_prometheus_issues

async def automated_troubleshooting():
    diagnosis = await diagnose_prometheus_issues()
    
    if diagnosis["summary"]["critical_issues"]:
        print("🚨 Critical issues detected!")
        
        # Execute recovery actions
        for step in diagnosis["recovery_steps"][:3]:  # Try first 3 steps
            print(f"Executing: {step['command']}")
            # subprocess.run(step['command'], shell=True)
    
    return diagnosis

# Run automated troubleshooting
diagnosis = asyncio.run(automated_troubleshooting())
```

### Integration with Monitoring Systems

```python
import json
from monitoring.prometheus_health import generate_prometheus_report

async def export_metrics():
    """Export Prometheus health metrics for external monitoring."""
    report = await generate_prometheus_report()
    
    # Extract key metrics
    metrics = {
        "prometheus_healthy": report["health_check"]["status"] == "healthy",
        "prometheus_response_time_ms": report["health_check"]["response_time_ms"],
        "prometheus_service_running": report["health_check"]["service_running"],
        "prometheus_config_valid": report["health_check"]["config_valid"],
        "prometheus_endpoints_accessible": len([
            ep for ep, accessible in report["health_check"]["endpoints_accessible"].items() 
            if accessible
        ])
    }
    
    # Send to monitoring system (e.g., Grafana, DataDog, etc.)
    return metrics
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Prometheus Service Not Running
**Symptoms**: `service_running: false`, connection refused errors

**Solutions**:
```bash
# Check container status
docker ps -a | grep prometheus

# Start Prometheus
docker-compose up -d prometheus

# Check logs
docker logs voice-ai-prometheus
```

#### 2. Configuration Errors
**Symptoms**: `config_valid: false`, YAML syntax errors

**Solutions**:
```bash
# Validate YAML syntax
yamllint monitoring/prometheus/prometheus.yml

# Test configuration
docker exec voice-ai-prometheus promtool check config /etc/prometheus/prometheus.yml

# Check file permissions
ls -la monitoring/prometheus/prometheus.yml
```

#### 3. Network Connectivity Issues
**Symptoms**: Endpoint accessibility failures, target unreachable

**Solutions**:
```bash
# Check Docker network
docker network ls
docker network inspect voice-ai-network

# Test connectivity between containers
docker exec voice-ai-prometheus wget -O- http://voice-ai-agent:8000/health
```

#### 4. Port Conflicts
**Symptoms**: Cannot bind to port, address already in use

**Solutions**:
```bash
# Check port usage
netstat -tulpn | grep 9091

# Kill conflicting processes
sudo lsof -ti:9091 | xargs kill -9

# Use different port in docker-compose.yml
```

### Diagnostic Commands

```bash
# Run comprehensive diagnostics
python scripts/prometheus_diagnostics.py --verbose

# Check specific component
python -c "
import asyncio
from monitoring.prometheus_health import check_prometheus_health
result = asyncio.run(check_prometheus_health())
print(f'Status: {result.status}')
print(f'Errors: {result.error_messages}')
"

# Verify fix
python scripts/prometheus_diagnostics.py --verify
```

## Testing

### Unit Tests

Run the test suite to verify functionality:

```bash
# Run Prometheus health tests
python -m pytest tests/test_prometheus_health.py -v

# Run basic functionality test
python tests/test_prometheus_health.py
```

### Integration Tests

```bash
# Test with running Prometheus
docker-compose up -d prometheus
python examples/prometheus_health_example.py

# Test diagnostic script
python scripts/prometheus_diagnostics.py --output test_report.json
```

## Performance Considerations

- **Response Time**: Health checks typically complete in 50-200ms
- **Resource Usage**: Minimal CPU and memory overhead
- **Network Impact**: Uses connection pooling and retry logic
- **Scalability**: Supports concurrent health checks

## Security Considerations

- **Network Access**: Only requires HTTP access to Prometheus endpoints
- **File Permissions**: Reads configuration files with appropriate permissions
- **Logging**: Sensitive information is not logged
- **Error Handling**: Graceful degradation on security restrictions

## Future Enhancements

- **Alerting Integration**: Direct integration with alerting systems
- **Metrics Export**: Export health metrics to Prometheus itself
- **Auto-Recovery**: Automated recovery actions for common issues
- **Dashboard Integration**: Real-time health dashboard
- **Historical Analysis**: Trend analysis and health history

## Support

For issues or questions about the Prometheus Health Check and Diagnostic System:

1. Check the troubleshooting section above
2. Run diagnostic script: `python scripts/prometheus_diagnostics.py --verbose`
3. Review logs in `logs/prometheus_health.log`
4. Check Docker container logs: `docker logs voice-ai-prometheus`

## License

This system is part of the Voice AI Agent project and follows the same licensing terms.
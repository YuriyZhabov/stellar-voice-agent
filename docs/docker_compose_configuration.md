# Docker Compose Configuration Guide

This document describes the Docker Compose configuration for the Voice AI Agent monitoring stack, including Prometheus, Grafana, and related services.

## Overview

The monitoring stack consists of the following services:
- **voice-ai-agent**: Main application service
- **redis**: Cache and session storage
- **prometheus**: Metrics collection and monitoring
- **grafana**: Visualization and dashboards
- **loki**: Log aggregation
- **node-exporter**: System metrics collection

## Service Configuration

### Prometheus Service

The Prometheus service is configured with the following key features:

#### Port Configuration
- **External Port**: 9091 (to avoid conflicts with application metrics on 9090)
- **Internal Port**: 9090 (standard Prometheus port)

#### Health Checks
```yaml
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:9090/-/healthy", "||", "exit", "1"]
  interval: 15s
  timeout: 5s
  retries: 5
  start_period: 30s
```

#### Volume Mounts
- Configuration: `./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro`
- Rules: `./monitoring/prometheus/rules:/etc/prometheus/rules:ro`
- Alerts: `./monitoring/prometheus/alerts:/etc/prometheus/alerts:ro`
- Data: `prometheus_data:/prometheus`

#### Command Arguments
- `--config.file=/etc/prometheus/prometheus.yml`: Configuration file location
- `--storage.tsdb.path=/prometheus`: Data storage path
- `--storage.tsdb.retention.time=200h`: Data retention (8+ days for dev, 30 days for prod)
- `--web.enable-lifecycle`: Enable configuration reload via API
- `--web.enable-admin-api`: Enable admin API endpoints
- `--log.level=info`: Logging level (warn for production)

#### Security
- Runs as user `65534:65534` (nobody user) for security
- Read-only configuration mounts

### Service Dependencies

The services are configured with proper startup dependencies:

```yaml
voice-ai-agent:
  depends_on:
    redis:
      condition: service_healthy
    prometheus:
      condition: service_healthy

prometheus:
  depends_on:
    redis:
      condition: service_healthy

grafana:
  depends_on:
    prometheus:
      condition: service_healthy
```

This ensures:
1. Redis starts first and becomes healthy
2. Prometheus starts after Redis is healthy
3. Voice AI Agent starts after both Redis and Prometheus are healthy
4. Grafana starts after Prometheus is healthy

## Network Configuration

All services are connected to the `voice-ai-network` bridge network, enabling:
- Service-to-service communication using service names
- Isolation from other Docker networks
- Proper DNS resolution between containers

## Volume Configuration

### Persistent Volumes
- `redis_data`: Redis data persistence
- `prometheus_data`: Prometheus metrics storage
- `grafana_data`: Grafana configuration and dashboards
- `loki_data`: Loki log storage

### Configuration Mounts
- Prometheus configuration and rules (read-only)
- Grafana dashboards and datasources (read-only)
- Application logs and data (read-write)

## Prometheus Configuration

### Scrape Targets

The Prometheus configuration includes the following scrape targets:

```yaml
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'voice-ai-agent'
    static_configs:
      - targets: ['voice-ai-agent:8000']
    metrics_path: '/metrics'

  - job_name: 'voice-ai-agent-health'
    static_configs:
      - targets: ['voice-ai-agent:8000']
    metrics_path: '/health'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Rules and Alerts

- **Rules**: Located in `monitoring/prometheus/rules/`
  - Service availability metrics
  - Performance aggregations
  - System health calculations

- **Alerts**: Located in `monitoring/prometheus/alerts/`
  - Service down alerts
  - Performance degradation alerts
  - System health alerts

## Development vs Production

### Development Configuration (`docker-compose.yml`)
- Shorter data retention (200h / ~8 days)
- More verbose logging
- Development-specific environment variables
- Exposed ports for direct access

### Production Configuration (`docker-compose.prod.yml`)
- Longer data retention (720h / 30 days)
- Resource limits and reservations
- Production-optimized settings
- Security hardening
- Less verbose logging

## Usage

### Starting the Stack

```bash
# Development
docker compose up -d

# Production
docker compose -f docker-compose.prod.yml up -d
```

### Validating Configuration

```bash
# Validate Docker Compose configuration
python scripts/validate_docker_compose.py

# Test the running stack
python scripts/test_docker_compose.py
```

### Accessing Services

- **Prometheus**: http://localhost:9091
- **Grafana**: http://localhost:3000 (admin/admin)
- **Voice AI Agent**: http://localhost:8000
- **Node Exporter**: http://localhost:9100

### Monitoring Health

```bash
# Check service status
docker compose ps

# Check service logs
docker compose logs prometheus
docker compose logs voice-ai-agent

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   - Ensure no other services are using ports 9091, 3000, 8000
   - Check with `netstat -tulpn | grep :9091`

2. **Service Dependencies**
   - Services may fail if dependencies are not healthy
   - Check health status with `docker-compose ps`

3. **Volume Permissions**
   - Ensure proper permissions for mounted directories
   - Prometheus runs as user 65534:65534

4. **Network Connectivity**
   - Services should be able to reach each other by service name
   - Test with `docker exec <container> ping <service-name>`

### Health Check Failures

If Prometheus health checks fail:

1. Check container logs: `docker-compose logs prometheus`
2. Verify configuration: `python scripts/validate_docker_compose.py`
3. Test connectivity: `curl http://localhost:9091/-/healthy`
4. Check dependencies: Ensure Redis is healthy first

### Configuration Reload

To reload Prometheus configuration without restart:

```bash
# Send SIGHUP to reload configuration
docker compose kill -s SIGHUP prometheus

# Or use the API (if web.enable-lifecycle is enabled)
curl -X POST http://localhost:9091/-/reload
```

## Security Considerations

1. **User Permissions**: Prometheus runs as non-root user (65534:65534)
2. **Read-only Mounts**: Configuration files are mounted read-only
3. **Network Isolation**: Services are isolated in their own network
4. **Resource Limits**: Production configuration includes resource limits
5. **Secrets Management**: Sensitive data should use Docker secrets or environment files

## Monitoring and Alerting

The configuration includes comprehensive monitoring:

- **Service Health**: All services have health checks
- **Metrics Collection**: Prometheus scrapes all service metrics
- **Alerting Rules**: Configured for service failures and performance issues
- **Log Aggregation**: Loki collects and indexes logs
- **Visualization**: Grafana provides dashboards and alerts

For more details on specific monitoring features, see the [Prometheus Health System Documentation](prometheus_health_system.md).
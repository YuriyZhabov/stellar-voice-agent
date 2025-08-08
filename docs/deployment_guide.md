# Voice AI Agent - Production Deployment Guide

This comprehensive guide covers the deployment of the Voice AI Agent system in production environments with optimal performance and reliability.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Environment Setup](#environment-setup)
4. [Configuration](#configuration)
5. [Deployment Methods](#deployment-methods)
6. [Performance Optimization](#performance-optimization)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

## Prerequisites

### Required Services and Accounts

- **Deepgram Account**: For speech-to-text services
- **OpenAI Account**: For language model services
- **Cartesia Account**: For text-to-speech services
- **LiveKit Cloud Account**: For SIP integration
- **SIP Provider**: Novofon or compatible SIP trunk

### Required Tools

- Docker and Docker Compose (v2.0+)
- Python 3.11+ (for local development)
- Git
- Make (for build automation)

## System Requirements

### Minimum Production Requirements

- **CPU**: 4 cores (8 recommended)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 50GB SSD (100GB recommended)
- **Network**: 1Gbps connection with low latency to AI services
- **OS**: Ubuntu 20.04+ or CentOS 8+

### Recommended Production Requirements

- **CPU**: 8 cores with high clock speed
- **RAM**: 32GB
- **Storage**: 200GB NVMe SSD
- **Network**: 10Gbps connection with CDN/edge locations
- **OS**: Ubuntu 22.04 LTS

### Performance Targets

- **Response Latency**: < 1.5 seconds end-to-end
- **Concurrent Calls**: 100+ simultaneous calls
- **Uptime**: 99.9% availability
- **Audio Quality**: HD voice with minimal jitter

## Environment Setup

### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install system dependencies
sudo apt install -y make git curl wget htop iotop nethogs
```

### 2. Application Deployment

```bash
# Clone repository
git clone <repository-url>
cd voice-ai-agent

# Create production environment file
cp .env.template .env.production

# Edit configuration (see Configuration section)
nano .env.production

# Build and deploy
make docker-build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Configuration

### Environment Variables

Create `.env.production` with the following configuration:

```bash
# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security
SECRET_KEY=<generate-strong-32-char-key>

# Domain and Network
DOMAIN=your-domain.com
PUBLIC_IP=<your-public-ip>
PORT=8000

# SIP Configuration
SIP_NUMBER=<your-phone-number>
SIP_SERVER=<sip-server-hostname>
SIP_USERNAME=<sip-username>
SIP_PASSWORD=<sip-password>
SIP_TRANSPORT=UDP
SIP_PORT=5060

# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=<livekit-api-key>
LIVEKIT_API_SECRET=<livekit-api-secret>
LIVEKIT_SIP_URI=sip:<your-number>@your-livekit-server.com

# AI Services
DEEPGRAM_API_KEY=<deepgram-api-key>
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=en-US

OPENAI_API_KEY=<openai-api-key>
OPENAI_MODEL=gpt-4-turbo
OPENAI_ORG_ID=<openai-org-id>

CARTESIA_API_KEY=<cartesia-api-key>
CARTESIA_VOICE_ID=default

# Performance Settings
MAX_RESPONSE_LATENCY=1.5
MAX_CONCURRENT_CALLS=100
AUDIO_BUFFER_SIZE=4096
RESPONSE_TIMEOUT=8.0
RETRY_ATTEMPTS=2

# Database
DATABASE_URL=sqlite:///./data/voice_ai.db
DB_POOL_SIZE=20

# Redis (if used)
REDIS_URL=redis://redis:6379/0

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
SENTRY_DSN=<sentry-dsn>
SENTRY_ENVIRONMENT=production

# Logging
STRUCTURED_LOGGING=true
LOG_FORMAT=json
LOG_FILE_PATH=/app/logs/voice_ai_agent.log
```

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  voice-ai-agent:
    environment:
      - ENVIRONMENT=production
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./config/production.yaml:/app/config/production.yaml:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - voice-ai-agent
    restart: unless-stopped

  prometheus:
    volumes:
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

## Deployment Methods

### Method 1: Docker Compose (Recommended)

```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f voice-ai-agent

# Scale services
docker-compose up -d --scale voice-ai-agent=3
```

### Method 2: Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-ai-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-ai-agent
  template:
    metadata:
      labels:
        app: voice-ai-agent
    spec:
      containers:
      - name: voice-ai-agent
        image: voice-ai-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

### Method 3: Systemd Service

```bash
# Create systemd service file
sudo tee /etc/systemd/system/voice-ai-agent.service > /dev/null <<EOF
[Unit]
Description=Voice AI Agent
After=network.target

[Service]
Type=simple
User=voiceai
WorkingDirectory=/opt/voice-ai-agent
Environment=ENVIRONMENT=production
ExecStart=/opt/voice-ai-agent/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable voice-ai-agent
sudo systemctl start voice-ai-agent
```

## Performance Optimization

### 1. System-Level Optimizations

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize network settings
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
echo "net.core.netdev_max_backlog = 5000" >> /etc/sysctl.conf
sysctl -p

# Optimize CPU scheduling
echo "kernel.sched_migration_cost_ns = 5000000" >> /etc/sysctl.conf
```

### 2. Application-Level Optimizations

```bash
# Use production configuration
export ENVIRONMENT=production
export OPTIMIZATION_LEVEL=aggressive

# Enable performance features
export ENABLE_STREAMING=true
export ENABLE_PREFETCH=true
export ENABLE_COMPRESSION=true
export ENABLE_CACHING=true
```

### 3. Database Optimizations

```sql
-- SQLite optimizations
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
```

## Monitoring and Observability

### 1. Health Checks

```bash
# Application health
curl -f http://localhost:8000/health

# Component health
curl -f http://localhost:8000/health/detailed

# Metrics endpoint
curl http://localhost:8000/metrics
```

### 2. Log Monitoring

```bash
# View application logs
tail -f logs/voice_ai_agent.log

# View error logs
tail -f logs/voice_ai_agent_errors.log

# View performance logs
tail -f logs/voice_ai_agent_performance.log
```

### 3. Metrics and Alerting

Configure Prometheus alerts in `monitoring/alerts.yml`:

```yaml
groups:
- name: voice-ai-agent
  rules:
  - alert: HighLatency
    expr: avg_latency > 1.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High response latency detected"
      
  - alert: LowSuccessRate
    expr: success_rate < 0.95
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Low success rate detected"
```

## Security Considerations

### 1. Network Security

```bash
# Configure firewall
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # Application
sudo ufw allow 5060/udp  # SIP
```

### 2. SSL/TLS Configuration

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    location / {
        proxy_pass http://voice-ai-agent:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. API Key Management

```bash
# Use environment variables for secrets
export DEEPGRAM_API_KEY=$(cat /run/secrets/deepgram_key)
export OPENAI_API_KEY=$(cat /run/secrets/openai_key)
export CARTESIA_API_KEY=$(cat /run/secrets/cartesia_key)
```

## Troubleshooting

### Common Issues

#### 1. High Latency

```bash
# Check system resources
htop
iotop
nethogs

# Check application metrics
curl http://localhost:8000/metrics | grep latency

# Optimize configuration
export MAX_CONCURRENT_CALLS=50
export AUDIO_BUFFER_SIZE=2048
```

#### 2. Connection Issues

```bash
# Test SIP connectivity
nmap -sU -p 5060 <sip-server>

# Test LiveKit connectivity
curl -I https://<livekit-server>

# Check DNS resolution
nslookup <domain>
```

#### 3. Memory Issues

```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head

# Adjust memory limits
export MAX_MEMORY_MB=4096
docker update --memory=8g voice-ai-agent
```

### Log Analysis

```bash
# Search for errors
grep -i error logs/voice_ai_agent.log

# Analyze performance
grep "LATENCY:" logs/voice_ai_agent_performance.log | tail -100

# Check call statistics
grep "CALL_" logs/voice_ai_agent_audit.log | tail -50
```

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Monitor system health and metrics
- Check error logs for issues
- Verify backup completion

#### Weekly
- Review performance trends
- Update security patches
- Clean up old log files

#### Monthly
- Performance optimization review
- Capacity planning assessment
- Security audit

### Backup and Recovery

```bash
# Backup database
cp data/voice_ai.db backups/voice_ai_$(date +%Y%m%d).db

# Backup configuration
tar -czf backups/config_$(date +%Y%m%d).tar.gz .env config/

# Backup logs
tar -czf backups/logs_$(date +%Y%m%d).tar.gz logs/
```

### Updates and Rollbacks

```bash
# Update application
git pull origin main
make docker-build
docker-compose up -d --no-deps voice-ai-agent

# Rollback if needed
docker-compose down
docker tag voice-ai-agent:previous voice-ai-agent:latest
docker-compose up -d
```

## Performance Benchmarks

### Expected Performance Metrics

- **Average Latency**: 0.8-1.2 seconds
- **95th Percentile Latency**: < 1.5 seconds
- **99th Percentile Latency**: < 2.0 seconds
- **Throughput**: 50-100 calls/second
- **Success Rate**: > 99%
- **Memory Usage**: 2-4GB under normal load
- **CPU Usage**: 30-60% under normal load

### Load Testing

```bash
# Run performance tests
make test-performance

# Run load tests
make test-load

# Run stability tests
make test-stability
```

## Support and Escalation

### Monitoring Dashboards
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Application Health: http://localhost:8000/health

### Log Locations
- Application: `/app/logs/voice_ai_agent.log`
- Errors: `/app/logs/voice_ai_agent_errors.log`
- Performance: `/app/logs/voice_ai_agent_performance.log`
- Audit: `/app/logs/voice_ai_agent_audit.log`

### Emergency Procedures
1. Check system health: `curl http://localhost:8000/health`
2. Review recent errors: `tail -100 logs/voice_ai_agent_errors.log`
3. Restart if necessary: `docker-compose restart voice-ai-agent`
4. Scale up if needed: `docker-compose up -d --scale voice-ai-agent=5`
5. Contact support with logs and metrics

---

This deployment guide provides comprehensive instructions for deploying the Voice AI Agent in production environments with optimal performance, security, and reliability.
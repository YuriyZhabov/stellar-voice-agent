# Voice AI Agent - Operational Runbook

This runbook provides step-by-step procedures for operating, monitoring, and troubleshooting the Voice AI Agent system in production.

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Monitoring and Alerting](#monitoring-and-alerting)
4. [Incident Response](#incident-response)
5. [Performance Optimization](#performance-optimization)
6. [Maintenance Procedures](#maintenance-procedures)
7. [Emergency Procedures](#emergency-procedures)
8. [Troubleshooting Guide](#troubleshooting-guide)

## System Overview

### Architecture Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SIP Provider  │────│   LiveKit SIP   │────│  Voice AI Agent │
│   (Novofon)     │    │   Integration   │    │     System      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐             │
                       │   AI Services   │─────────────┘
                       │ STT/LLM/TTS     │
                       └─────────────────┘
```

### Key Services
- **Voice AI Agent**: Main application handling call orchestration
- **LiveKit**: SIP integration and audio streaming
- **Deepgram**: Speech-to-text processing
- **OpenAI**: Language model processing
- **Cartesia**: Text-to-speech synthesis
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards

### Critical Metrics
- **Response Latency**: < 1.5 seconds (target)
- **Success Rate**: > 99%
- **Concurrent Calls**: Up to 100
- **System Uptime**: > 99.9%

## Daily Operations

### Morning Checklist (9:00 AM)

1. **System Health Check**
   ```bash
   # Check overall system health
   curl -f http://localhost:8000/health
   
   # Verify all components are healthy
   curl http://localhost:8000/health/detailed | jq '.components'
   ```

2. **Review Overnight Metrics**
   ```bash
   # Check error count from last 24 hours
   grep -c "ERROR" logs/voice_ai_agent.log | tail -1
   
   # Review performance metrics
   grep "LATENCY:" logs/voice_ai_agent_performance.log | tail -20
   ```

3. **Verify Service Status**
   ```bash
   # Check Docker containers
   docker-compose ps
   
   # Verify all services are running
   docker-compose logs --tail=50 voice-ai-agent
   ```

4. **Review Dashboard Alerts**
   - Open Grafana dashboard: http://localhost:3000
   - Check for any active alerts
   - Review performance trends from last 24 hours

### Midday Check (1:00 PM)

1. **Performance Review**
   ```bash
   # Check current system load
   htop
   
   # Review memory usage
   free -h
   
   # Check disk space
   df -h
   ```

2. **Call Volume Analysis**
   ```bash
   # Count calls in last hour
   grep "CALL_START" logs/voice_ai_agent_audit.log | grep "$(date '+%Y-%m-%d %H')" | wc -l
   
   # Check success rate
   grep "CALL_END" logs/voice_ai_agent_audit.log | grep "$(date '+%Y-%m-%d %H')" | wc -l
   ```

### Evening Review (6:00 PM)

1. **Daily Summary Report**
   ```bash
   # Generate daily report
   python3 scripts/generate_daily_report.py
   ```

2. **Log Rotation Check**
   ```bash
   # Check log file sizes
   ls -lh logs/
   
   # Rotate logs if needed
   logrotate /etc/logrotate.d/voice-ai-agent
   ```

3. **Backup Verification**
   ```bash
   # Verify daily backup completed
   ls -la backups/$(date +%Y%m%d)*
   ```

## Monitoring and Alerting

### Key Metrics to Monitor

#### Performance Metrics
- **Average Response Latency**: Target < 1.2s, Alert > 1.5s
- **95th Percentile Latency**: Target < 1.5s, Alert > 2.0s
- **Throughput**: Calls per second
- **Success Rate**: Target > 99%, Alert < 95%

#### System Metrics
- **CPU Usage**: Alert > 80%
- **Memory Usage**: Alert > 85%
- **Disk Usage**: Alert > 90%
- **Network I/O**: Monitor for anomalies

#### Application Metrics
- **Active Calls**: Monitor concurrent call count
- **Error Rate**: Alert > 1%
- **Queue Length**: Alert if growing
- **Component Health**: All components should be healthy

### Alert Response Procedures

#### High Latency Alert (> 1.5s)

1. **Immediate Actions**
   ```bash
   # Check system resources
   htop
   iotop
   
   # Review recent errors
   tail -100 logs/voice_ai_agent_errors.log
   
   # Check component health
   curl http://localhost:8000/health/detailed
   ```

2. **Investigation Steps**
   ```bash
   # Analyze latency breakdown
   grep "LATENCY:" logs/voice_ai_agent_performance.log | tail -50
   
   # Check AI service response times
   grep "stt_latency\|llm_latency\|tts_latency" logs/voice_ai_agent.log | tail -20
   ```

3. **Mitigation Actions**
   ```bash
   # Restart application if needed
   docker-compose restart voice-ai-agent
   
   # Scale up if high load
   docker-compose up -d --scale voice-ai-agent=3
   ```

#### Low Success Rate Alert (< 95%)

1. **Immediate Actions**
   ```bash
   # Check error patterns
   grep "ERROR\|FAILED" logs/voice_ai_agent_errors.log | tail -50
   
   # Verify external service connectivity
   curl -I https://api.deepgram.com
   curl -I https://api.openai.com
   ```

2. **Investigation Steps**
   ```bash
   # Analyze failed calls
   grep "CALL_END.*failed" logs/voice_ai_agent_audit.log | tail -20
   
   # Check circuit breaker status
   curl http://localhost:8000/metrics | grep circuit_breaker
   ```

#### High Resource Usage Alert

1. **CPU Usage > 80%**
   ```bash
   # Identify CPU-intensive processes
   top -o %CPU
   
   # Check for runaway processes
   ps aux --sort=-%cpu | head -10
   
   # Scale horizontally if needed
   docker-compose up -d --scale voice-ai-agent=5
   ```

2. **Memory Usage > 85%**
   ```bash
   # Check memory usage by process
   ps aux --sort=-%mem | head -10
   
   # Look for memory leaks
   grep "memory_usage" logs/voice_ai_agent_performance.log | tail -20
   
   # Restart if memory leak detected
   docker-compose restart voice-ai-agent
   ```

## Incident Response

### Severity Levels

#### P0 - Critical (System Down)
- **Response Time**: Immediate (< 5 minutes)
- **Examples**: Complete system outage, no calls processing
- **Actions**: Follow emergency procedures, engage on-call team

#### P1 - High (Degraded Service)
- **Response Time**: < 15 minutes
- **Examples**: High error rate, significant latency increase
- **Actions**: Immediate investigation and mitigation

#### P2 - Medium (Performance Issues)
- **Response Time**: < 1 hour
- **Examples**: Moderate latency increase, minor errors
- **Actions**: Investigation during business hours

#### P3 - Low (Minor Issues)
- **Response Time**: < 4 hours
- **Examples**: Logging issues, minor configuration problems
- **Actions**: Fix during next maintenance window

### Incident Response Workflow

1. **Detection**
   - Automated alerts via Prometheus/Grafana
   - User reports
   - Monitoring dashboard anomalies

2. **Assessment**
   ```bash
   # Quick health check
   curl -f http://localhost:8000/health
   
   # Check system status
   docker-compose ps
   
   # Review recent logs
   tail -100 logs/voice_ai_agent_errors.log
   ```

3. **Mitigation**
   - Apply immediate fixes
   - Scale resources if needed
   - Implement workarounds

4. **Resolution**
   - Fix root cause
   - Verify system stability
   - Update monitoring if needed

5. **Post-Incident**
   - Document incident
   - Conduct post-mortem
   - Implement preventive measures

## Performance Optimization

### Real-Time Performance Tuning

1. **Latency Optimization**
   ```bash
   # Enable aggressive optimization
   export OPTIMIZATION_LEVEL=aggressive
   
   # Reduce buffer sizes for lower latency
   export AUDIO_BUFFER_SIZE=2048
   
   # Increase concurrent processing
   export MAX_CONCURRENT_CALLS=150
   ```

2. **Throughput Optimization**
   ```bash
   # Enable connection pooling
   export ENABLE_CONNECTION_POOLING=true
   
   # Enable caching
   export ENABLE_CACHING=true
   
   # Enable compression
   export ENABLE_COMPRESSION=true
   ```

3. **Resource Optimization**
   ```bash
   # Adjust memory limits
   docker update --memory=8g voice-ai-agent
   
   # Adjust CPU limits
   docker update --cpus=4.0 voice-ai-agent
   ```

### Performance Monitoring Commands

```bash
# Monitor real-time performance
watch -n 5 'curl -s http://localhost:8000/metrics | grep -E "(latency|success_rate|active_calls)"'

# Generate performance report
python3 scripts/performance_report.py --last-hour

# Run performance benchmark
make test-performance
```

## Maintenance Procedures

### Weekly Maintenance (Sundays 2:00 AM)

1. **System Updates**
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade -y
   
   # Update Docker images
   docker-compose pull
   docker-compose up -d
   ```

2. **Log Cleanup**
   ```bash
   # Compress old logs
   find logs/ -name "*.log" -mtime +7 -exec gzip {} \;
   
   # Remove old compressed logs
   find logs/ -name "*.gz" -mtime +30 -delete
   ```

3. **Database Maintenance**
   ```bash
   # Vacuum SQLite database
   sqlite3 data/voice_ai.db "VACUUM;"
   
   # Analyze database statistics
   sqlite3 data/voice_ai.db "ANALYZE;"
   ```

4. **Performance Baseline Update**
   ```bash
   # Run performance tests
   make test-performance
   
   # Update baseline metrics
   python3 scripts/update_baseline.py
   ```

### Monthly Maintenance (First Sunday)

1. **Security Updates**
   ```bash
   # Update SSL certificates
   certbot renew
   
   # Rotate API keys (if needed)
   # Update .env with new keys
   docker-compose restart voice-ai-agent
   ```

2. **Capacity Planning**
   ```bash
   # Generate capacity report
   python3 scripts/capacity_report.py --last-month
   
   # Review resource utilization trends
   # Plan for scaling if needed
   ```

3. **Backup Verification**
   ```bash
   # Test backup restoration
   cp backups/latest_backup.db test_restore.db
   sqlite3 test_restore.db ".tables"
   rm test_restore.db
   ```

## Emergency Procedures

### Complete System Failure

1. **Immediate Response**
   ```bash
   # Check system status
   systemctl status docker
   docker-compose ps
   
   # Restart all services
   docker-compose down
   docker-compose up -d
   ```

2. **If Restart Fails**
   ```bash
   # Check system resources
   df -h
   free -h
   
   # Check for corrupted files
   docker system prune -f
   
   # Restore from backup if needed
   cp backups/latest_backup.db data/voice_ai.db
   ```

### Database Corruption

1. **Detection**
   ```bash
   # Check database integrity
   sqlite3 data/voice_ai.db "PRAGMA integrity_check;"
   ```

2. **Recovery**
   ```bash
   # Stop application
   docker-compose stop voice-ai-agent
   
   # Restore from backup
   cp backups/$(ls -t backups/ | head -1) data/voice_ai.db
   
   # Restart application
   docker-compose start voice-ai-agent
   ```

### High Load Emergency

1. **Immediate Scaling**
   ```bash
   # Scale up immediately
   docker-compose up -d --scale voice-ai-agent=10
   
   # Enable load balancing
   # Update nginx configuration if needed
   ```

2. **Load Shedding**
   ```bash
   # Reduce concurrent calls temporarily
   export MAX_CONCURRENT_CALLS=50
   
   # Enable circuit breakers
   export CIRCUIT_BREAKER_THRESHOLD=0.1
   ```

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: High Latency

**Symptoms:**
- Response times > 2 seconds
- User complaints about delays
- Latency alerts firing

**Diagnosis:**
```bash
# Check component latencies
grep "LATENCY:" logs/voice_ai_agent_performance.log | tail -20

# Check system resources
htop
iotop
```

**Solutions:**
1. Restart application: `docker-compose restart voice-ai-agent`
2. Scale up: `docker-compose up -d --scale voice-ai-agent=3`
3. Optimize configuration: Reduce buffer sizes, increase timeouts

#### Issue: Connection Failures

**Symptoms:**
- Failed to connect to AI services
- SIP registration failures
- Network timeout errors

**Diagnosis:**
```bash
# Test external connectivity
curl -I https://api.deepgram.com
curl -I https://api.openai.com
nmap -p 5060 <sip-server>

# Check DNS resolution
nslookup api.deepgram.com
```

**Solutions:**
1. Check network configuration
2. Verify API keys and credentials
3. Check firewall rules
4. Restart networking: `sudo systemctl restart networking`

#### Issue: Memory Leaks

**Symptoms:**
- Gradually increasing memory usage
- Out of memory errors
- System becoming unresponsive

**Diagnosis:**
```bash
# Monitor memory usage over time
grep "memory_usage" logs/voice_ai_agent_performance.log | tail -50

# Check for memory leaks
ps aux --sort=-%mem | head -10
```

**Solutions:**
1. Restart application: `docker-compose restart voice-ai-agent`
2. Increase memory limits: `docker update --memory=16g voice-ai-agent`
3. Enable garbage collection tuning
4. Review code for memory leaks

### Diagnostic Commands

```bash
# System health overview
curl http://localhost:8000/health/detailed | jq '.'

# Performance metrics
curl http://localhost:8000/metrics | grep -E "(latency|calls|errors)"

# Recent errors
tail -100 logs/voice_ai_agent_errors.log

# Active connections
netstat -an | grep :8000

# Process information
ps aux | grep voice-ai

# Docker container stats
docker stats voice-ai-agent

# Disk usage
du -sh logs/ data/ backups/
```

### Log Analysis

```bash
# Find error patterns
grep -E "(ERROR|CRITICAL|FAILED)" logs/voice_ai_agent.log | tail -50

# Analyze call patterns
grep "CALL_START\|CALL_END" logs/voice_ai_agent_audit.log | tail -100

# Performance analysis
grep "LATENCY:\|THROUGHPUT:" logs/voice_ai_agent_performance.log | tail -50

# Search for specific issues
grep -i "timeout\|connection\|refused" logs/voice_ai_agent.log
```

## Contact Information

### Escalation Path

1. **Level 1**: On-call engineer
2. **Level 2**: Senior engineer
3. **Level 3**: Engineering manager
4. **Level 4**: CTO/VP Engineering

### Emergency Contacts

- **On-call Phone**: +1-XXX-XXX-XXXX
- **Slack Channel**: #voice-ai-alerts
- **Email**: voice-ai-oncall@company.com

### External Vendors

- **Deepgram Support**: support@deepgram.com
- **OpenAI Support**: support@openai.com
- **Cartesia Support**: support@cartesia.ai
- **LiveKit Support**: support@livekit.io

---

This operational runbook provides comprehensive procedures for maintaining the Voice AI Agent system in production. Keep this document updated as the system evolves and new procedures are developed.
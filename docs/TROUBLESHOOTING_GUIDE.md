# Voice AI Agent - Comprehensive Troubleshooting Guide

## Table of Contents

1. [Quick Diagnostic Commands](#quick-diagnostic-commands)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Component-Specific Troubleshooting](#component-specific-troubleshooting)
4. [Performance Issues](#performance-issues)
5. [Network and Connectivity Issues](#network-and-connectivity-issues)
6. [Configuration Problems](#configuration-problems)
7. [Database Issues](#database-issues)
8. [Security and Authentication Issues](#security-and-authentication-issues)
9. [Monitoring and Alerting Issues](#monitoring-and-alerting-issues)
10. [Emergency Recovery Procedures](#emergency-recovery-procedures)

## Quick Diagnostic Commands

### System Health Check
```bash
# Overall system health
make health

# Detailed health check with component status
curl -s http://localhost:8000/health | jq '.'

# Check all Docker containers
docker-compose ps

# View recent logs
docker-compose logs --tail=50 voice-ai-agent

# Check system resources
htop
free -h
df -h
```

### Application Status
```bash
# Check if application is responding
curl -f http://localhost:8000/health || echo "Application not responding"

# Check specific endpoints
curl -s http://localhost:8000/metrics | head -20

# View application logs
tail -f logs/voice_ai_agent.log

# Check for errors in logs
grep -i error logs/voice_ai_agent.log | tail -10
```

### Network Connectivity
```bash
# Test external API connectivity
curl -I https://api.deepgram.com
curl -I https://api.groq.com
curl -I https://api.cartesia.ai

# Check DNS resolution
nslookup api.deepgram.com
nslookup api.groq.com

# Test port connectivity
telnet localhost 8000
nc -zv localhost 8000
```

## Common Issues and Solutions

### Issue 1: Application Won't Start

**Symptoms:**
- Container exits immediately
- "Connection refused" errors
- Import errors in logs

**Diagnostic Steps:**
```bash
# Check container logs
docker-compose logs voice-ai-agent

# Check for port conflicts
netstat -tulpn | grep :8000

# Verify environment variables
docker-compose config

# Check file permissions
ls -la .env
ls -la data/
```

**Common Solutions:**

1. **Missing Environment Variables:**
   ```bash
   # Copy template and configure
   cp .env.template .env
   nano .env  # Add your API keys
   ```

2. **Port Already in Use:**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # Kill the process or change port in .env
   export PORT=8001
   ```

3. **Permission Issues:**
   ```bash
   # Fix file permissions
   chmod 644 .env
   chmod -R 755 data/
   chown -R $USER:$USER data/
   ```

4. **Missing Dependencies:**
   ```bash
   # Rebuild containers
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Issue 2: High Response Latency

**Symptoms:**
- Response times > 2 seconds
- Timeout errors
- Poor user experience

**Diagnostic Steps:**
```bash
# Check current latency
curl -w "@curl-format.txt" -s http://localhost:8000/health

# Monitor real-time latency
watch -n 1 'curl -s http://localhost:8000/metrics | grep latency'

# Check component latencies
grep "stt_latency\|llm_latency\|tts_latency" logs/voice_ai_agent.log | tail -20

# Check system load
uptime
iostat 1 5
```

**Solutions:**

1. **Scale Up Resources:**
   ```bash
   # Increase container resources
   docker update --memory=8g --cpus=4.0 voice-ai-agent_voice-ai-agent_1
   
   # Scale horizontally
   docker-compose up -d --scale voice-ai-agent=3
   ```

2. **Optimize Configuration:**
   ```bash
   # Reduce audio buffer size
   export AUDIO_BUFFER_SIZE=1024
   
   # Increase timeout values
   export REQUEST_TIMEOUT=60
   
   # Enable connection pooling
   export ENABLE_CONNECTION_POOLING=true
   ```

3. **Check External Services:**
   ```bash
   # Test API response times
   time curl -s https://api.deepgram.com/v1/projects
   time curl -s https://api.groq.com/openai/v1/models
   ```

### Issue 3: Memory Leaks

**Symptoms:**
- Gradually increasing memory usage
- Out of memory errors
- Container restarts

**Diagnostic Steps:**
```bash
# Monitor memory usage
docker stats voice-ai-agent_voice-ai-agent_1

# Check memory usage over time
grep "memory_usage" logs/voice_ai_agent.log | tail -50

# Check for memory leaks in Python
pip install memory-profiler
python -m memory_profiler src/main.py
```

**Solutions:**

1. **Restart Application:**
   ```bash
   docker-compose restart voice-ai-agent
   ```

2. **Increase Memory Limits:**
   ```bash
   # Update docker-compose.yml
   services:
     voice-ai-agent:
       mem_limit: 8g
   ```

3. **Enable Garbage Collection:**
   ```bash
   # Add to environment
   export PYTHONOPTIMIZE=1
   export GC_THRESHOLD=700,10,10
   ```

### Issue 4: Database Connection Errors

**Symptoms:**
- "Database locked" errors
- Connection timeout errors
- Data not persisting

**Diagnostic Steps:**
```bash
# Check database file
ls -la data/voice_ai.db

# Test database connectivity
sqlite3 data/voice_ai.db ".tables"

# Check for database locks
lsof data/voice_ai.db

# Verify database integrity
sqlite3 data/voice_ai.db "PRAGMA integrity_check;"
```

**Solutions:**

1. **Fix Database Permissions:**
   ```bash
   chmod 664 data/voice_ai.db
   chown $USER:$USER data/voice_ai.db
   ```

2. **Unlock Database:**
   ```bash
   # Kill processes holding locks
   fuser -k data/voice_ai.db
   
   # Or restart application
   docker-compose restart voice-ai-agent
   ```

3. **Restore from Backup:**
   ```bash
   # Stop application
   docker-compose stop voice-ai-agent
   
   # Restore backup
   cp backups/$(ls -t backups/ | head -1) data/voice_ai.db
   
   # Start application
   docker-compose start voice-ai-agent
   ```

## Component-Specific Troubleshooting

### Deepgram STT Issues

**Common Problems:**
- Authentication failures
- Audio format errors
- Transcription quality issues

**Diagnostic Commands:**
```bash
# Test Deepgram API
curl -H "Authorization: Token YOUR_API_KEY" \
     https://api.deepgram.com/v1/projects

# Check audio format support
file audio_sample.wav

# Test transcription
python -c "
from src.clients.deepgram_stt import DeepgramSTTClient
import asyncio
client = DeepgramSTTClient()
print(asyncio.run(client.health_check()))
"
```

**Solutions:**

1. **API Key Issues:**
   ```bash
   # Verify API key format
   echo $DEEPGRAM_API_KEY | wc -c  # Should be 40+ characters
   
   # Test API key
   curl -H "Authorization: Token $DEEPGRAM_API_KEY" \
        https://api.deepgram.com/v1/projects
   ```

2. **Audio Format Issues:**
   ```bash
   # Convert audio to supported format
   ffmpeg -i input.mp3 -ar 16000 -ac 1 -f wav output.wav
   ```

3. **Model Configuration:**
   ```bash
   # Update model in .env
   export DEEPGRAM_MODEL=nova-2
   export DEEPGRAM_LANGUAGE=en-US
   ```

### Groq LLM Issues

**Common Problems:**
- Rate limiting
- Context window exceeded
- Model availability

**Diagnostic Commands:**
```bash
# Test Groq API
curl -H "Authorization: Bearer $GROQ_API_KEY" \
     https://api.groq.com/openai/v1/models

# Check rate limits
curl -H "Authorization: Bearer $GROQ_API_KEY" \
     -H "Content-Type: application/json" \
     https://api.groq.com/openai/v1/chat/completions \
     -d '{"model":"llama3-8b-8192","messages":[{"role":"user","content":"test"}]}'

# Test client health
python -c "
from src.clients.groq_llm import GroqLLMClient
import asyncio
client = GroqLLMClient()
print(asyncio.run(client.health_check()))
"
```

**Solutions:**

1. **Rate Limiting:**
   ```bash
   # Increase retry delays
   export RETRY_BASE_DELAY=2.0
   export RETRY_MAX_DELAY=120.0
   
   # Enable request queuing
   export ENABLE_REQUEST_QUEUING=true
   ```

2. **Context Management:**
   ```bash
   # Reduce context window
   export CONTEXT_WINDOW_SIZE=3000
   export MAX_RESPONSE_TOKENS=100
   ```

3. **Model Selection:**
   ```bash
   # Use different model
   export GROQ_MODEL=llama3-70b-8192
   ```

### Cartesia TTS Issues

**Common Problems:**
- Voice ID not found
- Audio format issues
- Synthesis failures

**Diagnostic Commands:**
```bash
# Test Cartesia API
curl -H "X-API-Key: $CARTESIA_API_KEY" \
     https://api.cartesia.ai/voices

# Test synthesis
python -c "
from src.clients.cartesia_tts import CartesiaTTSClient
import asyncio
client = CartesiaTTSClient()
print(asyncio.run(client.health_check()))
"

# Check available voices
python -c "
from src.clients.cartesia_tts import CartesiaTTSClient
import asyncio
client = CartesiaTTSClient()
voices = asyncio.run(client.get_available_voices())
print([v['id'] for v in voices])
"
```

**Solutions:**

1. **Voice Configuration:**
   ```bash
   # Use valid voice ID
   export CARTESIA_VOICE_ID=064b17af-d36b-4bfb-b003-be07dba1b649
   ```

2. **Audio Format:**
   ```bash
   # Use supported format
   export AUDIO_FORMAT=wav
   export AUDIO_SAMPLE_RATE=16000
   ```

### LiveKit Integration Issues

**Common Problems:**
- SIP registration failures
- Audio quality issues
- Connection drops

**Diagnostic Commands:**
```bash
# Test LiveKit connectivity
curl -H "Authorization: Bearer $LIVEKIT_API_KEY" \
     $LIVEKIT_URL/twirp/livekit.RoomService/ListRooms

# Check SIP configuration
cat livekit-sip.yaml

# Test SIP connectivity with Novofon
sip-tester --server sip.novofon.ru --username 0053248
```

**Solutions:**

1. **SIP Configuration (Novofon):**
   ```bash
   # Update SIP settings for Novofon
   export SIP_NUMBER=+79952227978
   export SIP_SERVER=sip.novofon.ru
   export SIP_USERNAME=0053248
   export SIP_PASSWORD=s8zrerUKYC
   export SIP_TRANSPORT=UDP
   export SIP_PORT=5060
   
   # Check firewall rules
   sudo ufw allow 5060/udp
   ```

2. **Audio Configuration:**
   ```bash
   # Optimize for telephony
   export AUDIO_SAMPLE_RATE=8000
   export AUDIO_CODEC=PCMU
   ```

## Performance Issues

### High CPU Usage

**Diagnostic Steps:**
```bash
# Identify CPU-intensive processes
top -o %CPU
ps aux --sort=-%cpu | head -10

# Check CPU usage by container
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Profile Python application
pip install py-spy
py-spy top --pid $(pgrep -f "python.*main.py")
```

**Solutions:**

1. **Scale Horizontally:**
   ```bash
   docker-compose up -d --scale voice-ai-agent=5
   ```

2. **Optimize Code:**
   ```bash
   # Enable optimizations
   export PYTHONOPTIMIZE=2
   export OPTIMIZATION_LEVEL=aggressive
   ```

3. **Resource Limits:**
   ```bash
   # Set CPU limits
   docker update --cpus=4.0 voice-ai-agent_voice-ai-agent_1
   ```

### High Memory Usage

**Diagnostic Steps:**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Monitor memory over time
watch -n 5 'free -h'

# Check for memory leaks
valgrind --tool=memcheck python src/main.py
```

**Solutions:**

1. **Increase Memory:**
   ```bash
   docker update --memory=16g voice-ai-agent_voice-ai-agent_1
   ```

2. **Optimize Memory Usage:**
   ```bash
   # Enable garbage collection
   export PYTHONGC=1
   
   # Reduce cache sizes
   export CACHE_SIZE=100
   ```

### Disk I/O Issues

**Diagnostic Steps:**
```bash
# Check disk usage
df -h
du -sh logs/ data/ backups/

# Monitor I/O
iostat -x 1 5
iotop

# Check for large files
find . -size +100M -type f
```

**Solutions:**

1. **Clean Up Logs:**
   ```bash
   # Rotate logs
   logrotate -f /etc/logrotate.d/voice-ai-agent
   
   # Compress old logs
   find logs/ -name "*.log" -mtime +7 -exec gzip {} \;
   ```

2. **Optimize Database:**
   ```bash
   # Vacuum database
   sqlite3 data/voice_ai.db "VACUUM;"
   
   # Move to faster storage
   mv data/ /mnt/ssd/data/
   ln -s /mnt/ssd/data/ data
   ```

## Network and Connectivity Issues

### DNS Resolution Problems

**Diagnostic Steps:**
```bash
# Test DNS resolution
nslookup api.deepgram.com
dig api.groq.com
host api.cartesia.ai

# Check DNS configuration
cat /etc/resolv.conf

# Test with different DNS servers
nslookup api.deepgram.com 8.8.8.8
```

**Solutions:**

1. **Update DNS Configuration:**
   ```bash
   # Use Google DNS
   echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
   echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf
   ```

2. **Flush DNS Cache:**
   ```bash
   sudo systemctl restart systemd-resolved
   sudo systemctl flush-dns
   ```

### Firewall Issues

**Diagnostic Steps:**
```bash
# Check firewall status
sudo ufw status verbose

# Check iptables rules
sudo iptables -L -n

# Test port connectivity
nc -zv api.deepgram.com 443
telnet api.groq.com 443
```

**Solutions:**

1. **Open Required Ports:**
   ```bash
   # Allow HTTP/HTTPS
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   
   # Allow application port
   sudo ufw allow 8000/tcp
   
   # Allow SIP
   sudo ufw allow 5060/udp
   ```

2. **Configure Proxy (if needed):**
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

### SSL/TLS Issues

**Diagnostic Steps:**
```bash
# Test SSL connectivity
openssl s_client -connect api.deepgram.com:443
curl -vI https://api.groq.com

# Check certificate validity
echo | openssl s_client -connect api.cartesia.ai:443 2>/dev/null | openssl x509 -noout -dates
```

**Solutions:**

1. **Update CA Certificates:**
   ```bash
   sudo apt update
   sudo apt install ca-certificates
   sudo update-ca-certificates
   ```

2. **Disable SSL Verification (temporary):**
   ```bash
   export PYTHONHTTPSVERIFY=0
   export CURL_CA_BUNDLE=""
   ```

## Configuration Problems

### Environment Variable Issues

**Diagnostic Steps:**
```bash
# Check environment variables
env | grep -E "(DEEPGRAM|GROQ|CARTESIA|LIVEKIT)"

# Validate configuration
python -c "from src.config import get_settings; print(get_settings())"

# Check .env file
cat .env | grep -v "^#" | grep -v "^$"
```

**Solutions:**

1. **Fix Missing Variables:**
   ```bash
   # Copy template
   cp .env.template .env
   
   # Add missing variables
   echo "MISSING_VAR=value" >> .env
   ```

2. **Validate API Keys:**
   ```bash
   # Check key formats
   python -c "
   from src.security import validate_api_key, APIKeyType
   print(validate_api_key('$DEEPGRAM_API_KEY', APIKeyType.DEEPGRAM))
   "
   ```

### Configuration Validation Errors

**Diagnostic Steps:**
```bash
# Run configuration validation
python -c "
from src.config import validate_settings
result = validate_settings()
print(result)
"

# Check for syntax errors
python -m py_compile src/config.py
```

**Solutions:**

1. **Fix Validation Errors:**
   ```bash
   # Check required fields for production
   if [ "$ENVIRONMENT" = "production" ]; then
     echo "Checking production requirements..."
     # Add missing required fields
   fi
   ```

2. **Reset Configuration:**
   ```bash
   # Backup current config
   cp .env .env.backup
   
   # Reset to template
   cp .env.template .env
   # Reconfigure with correct values
   ```

## Database Issues

### Database Corruption

**Diagnostic Steps:**
```bash
# Check database integrity
sqlite3 data/voice_ai.db "PRAGMA integrity_check;"

# Check database schema
sqlite3 data/voice_ai.db ".schema"

# Check for locks
lsof data/voice_ai.db
```

**Solutions:**

1. **Repair Database:**
   ```bash
   # Dump and restore
   sqlite3 data/voice_ai.db ".dump" > backup.sql
   rm data/voice_ai.db
   sqlite3 data/voice_ai.db < backup.sql
   ```

2. **Restore from Backup:**
   ```bash
   # Stop application
   docker-compose stop voice-ai-agent
   
   # Restore latest backup
   cp backups/$(ls -t backups/ | head -1) data/voice_ai.db
   
   # Start application
   docker-compose start voice-ai-agent
   ```

### Migration Issues

**Diagnostic Steps:**
```bash
# Check migration status
python -c "
from src.database.migrations import MigrationManager
import asyncio
manager = MigrationManager()
print(asyncio.run(manager.get_current_version()))
"

# Check migration history
sqlite3 data/voice_ai.db "SELECT * FROM migration_history;"
```

**Solutions:**

1. **Run Migrations:**
   ```bash
   python -c "
   from src.database.migrations import MigrationManager
   import asyncio
   manager = MigrationManager()
   asyncio.run(manager.migrate_to_latest())
   "
   ```

2. **Reset Database:**
   ```bash
   # Backup data
   sqlite3 data/voice_ai.db ".dump" > data_backup.sql
   
   # Remove database
   rm data/voice_ai.db
   
   # Recreate with migrations
   python -c "
   from src.database.migrations import MigrationManager
   import asyncio
   manager = MigrationManager()
   asyncio.run(manager.migrate_to_latest())
   "
   ```

## Security and Authentication Issues

### API Key Problems

**Diagnostic Steps:**
```bash
# Test API keys
curl -H "Authorization: Token $DEEPGRAM_API_KEY" https://api.deepgram.com/v1/projects
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
curl -H "X-API-Key: $CARTESIA_API_KEY" https://api.cartesia.ai/voices

# Check key formats
echo $DEEPGRAM_API_KEY | wc -c
echo $GROQ_API_KEY | wc -c
```

**Solutions:**

1. **Regenerate API Keys:**
   - Log into service dashboards
   - Generate new API keys
   - Update .env file
   - Restart application

2. **Check Key Permissions:**
   - Verify account status
   - Check usage limits
   - Ensure proper permissions

### SSL Certificate Issues

**Diagnostic Steps:**
```bash
# Check certificate validity
openssl x509 -in /path/to/cert.pem -text -noout

# Test SSL connection
openssl s_client -connect localhost:443 -servername yourdomain.com
```

**Solutions:**

1. **Renew Certificates:**
   ```bash
   # Using certbot
   sudo certbot renew
   
   # Restart services
   sudo systemctl reload nginx
   ```

2. **Update Certificate Configuration:**
   ```bash
   # Update paths in configuration
   export SSL_CERT_PATH=/path/to/new/cert.pem
   export SSL_KEY_PATH=/path/to/new/key.pem
   ```

## Monitoring and Alerting Issues

### Prometheus Not Collecting Metrics

**Diagnostic Steps:**
```bash
# Check Prometheus status
curl http://localhost:9090/api/v1/query?query=up

# Check targets
curl http://localhost:9090/api/v1/targets

# Check application metrics endpoint
curl http://localhost:8000/metrics
```

**Solutions:**

1. **Fix Prometheus Configuration:**
   ```bash
   # Check prometheus.yml
   cat monitoring/prometheus/prometheus.yml
   
   # Restart Prometheus
   docker-compose restart prometheus
   ```

2. **Fix Application Metrics:**
   ```bash
   # Enable metrics in application
   export ENABLE_METRICS=true
   
   # Restart application
   docker-compose restart voice-ai-agent
   ```

### Grafana Dashboard Issues

**Diagnostic Steps:**
```bash
# Check Grafana status
curl http://localhost:3000/api/health

# Check data sources
curl -u admin:admin http://localhost:3000/api/datasources

# Test queries
curl -u admin:admin http://localhost:3000/api/ds/query
```

**Solutions:**

1. **Fix Data Source:**
   ```bash
   # Update Prometheus URL in Grafana
   # Go to Configuration > Data Sources
   # Update Prometheus URL to http://prometheus:9090
   ```

2. **Import Dashboard:**
   ```bash
   # Import dashboard JSON
   curl -X POST \
     -H "Content-Type: application/json" \
     -u admin:admin \
     http://localhost:3000/api/dashboards/db \
     -d @monitoring/grafana/dashboards/voice-ai-agent.json
   ```

## Emergency Recovery Procedures

### Complete System Recovery

**When to Use:**
- Complete system failure
- Data corruption
- Security breach

**Recovery Steps:**

1. **Immediate Response:**
   ```bash
   # Stop all services
   docker-compose down
   
   # Check system integrity
   fsck /dev/sda1
   
   # Check for malware
   sudo rkhunter --check
   ```

2. **Data Recovery:**
   ```bash
   # Restore from backup
   cp backups/latest_full_backup.tar.gz /tmp/
   cd /tmp
   tar -xzf latest_full_backup.tar.gz
   
   # Restore database
   cp backup/data/voice_ai.db /path/to/project/data/
   
   # Restore configuration
   cp backup/.env /path/to/project/
   ```

3. **System Rebuild:**
   ```bash
   # Pull latest images
   docker-compose pull
   
   # Rebuild containers
   docker-compose build --no-cache
   
   # Start services
   docker-compose up -d
   ```

4. **Verification:**
   ```bash
   # Check system health
   make health
   
   # Run tests
   make test
   
   # Verify functionality
   curl -f http://localhost:8000/health
   ```

### Disaster Recovery Checklist

- [ ] Stop all services
- [ ] Assess damage extent
- [ ] Restore from backups
- [ ] Verify data integrity
- [ ] Update security credentials
- [ ] Restart services
- [ ] Run health checks
- [ ] Monitor for issues
- [ ] Document incident
- [ ] Update recovery procedures

---

**Remember:** When in doubt, check the logs first, then the configuration, then the network connectivity. Most issues can be resolved by following these systematic troubleshooting steps.
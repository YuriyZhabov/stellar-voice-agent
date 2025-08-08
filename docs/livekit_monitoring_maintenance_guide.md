# Руководство по мониторингу и обслуживанию системы LiveKit

## Обзор

Данное руководство описывает процедуры мониторинга, обслуживания и поддержки системы LiveKit, интегрированной с Voice AI Agent. Включает настройку мониторинга, интерпретацию метрик, процедуры обслуживания и планы реагирования на инциденты.

## 1. Система мониторинга

### 1.1 Архитектура мониторинга

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Application   │───▶│   Metrics        │───▶│   Prometheus    │
│   Components    │    │   Collection     │    │   Server        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐            ▼
│   Health Check  │───▶│   Alert Manager  │    ┌─────────────────┐
│   Endpoints     │    │   & Notifications│    │   Grafana       │
└─────────────────┘    └──────────────────┘    │   Dashboard     │
                                               └─────────────────┘
```

### 1.2 Компоненты мониторинга

#### Health Check Endpoints

```python
# Доступные endpoints для проверки состояния
GET /health                    # Общее состояние системы
GET /health/detailed          # Детальная информация о компонентах
GET /health/livekit          # Состояние LiveKit API
GET /health/sip              # Состояние SIP интеграции
GET /health/ai               # Состояние AI сервисов
GET /health/database         # Состояние базы данных
GET /health/redis            # Состояние Redis кэша
```

#### Prometheus Metrics

```python
# Основные метрики системы
livekit_api_requests_total           # Общее количество API запросов
livekit_api_request_duration_seconds # Время выполнения API запросов
livekit_rooms_active                 # Количество активных комнат
livekit_participants_active          # Количество активных участников
livekit_connections_total            # Общее количество подключений
livekit_connection_errors_total      # Количество ошибок подключения
livekit_sip_calls_active            # Активные SIP звонки
livekit_sip_call_duration_seconds   # Длительность SIP звонков
livekit_audio_quality_score         # Оценка качества аудио
livekit_system_cpu_usage            # Использование CPU
livekit_system_memory_usage         # Использование памяти
```

### 1.3 Настройка мониторинга

#### Конфигурация Prometheus

```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'livekit-voice-ai'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 10s
    metrics_path: '/metrics'
    
  - job_name: 'livekit-server'
    static_configs:
      - targets: ['your-livekit-server.com:7880']
    scrape_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "LiveKit Voice AI System",
    "panels": [
      {
        "title": "API Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, livekit_api_request_duration_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Active Rooms & Participants",
        "type": "stat",
        "targets": [
          {
            "expr": "livekit_rooms_active",
            "legendFormat": "Active Rooms"
          },
          {
            "expr": "livekit_participants_active",
            "legendFormat": "Active Participants"
          }
        ]
      }
    ]
  }
}
```

## 2. Ключевые метрики и пороговые значения

### 2.1 Производительность системы

| Метрика | Нормальное значение | Предупреждение | Критическое |
|---------|-------------------|----------------|-------------|
| API Latency (95th percentile) | < 100ms | 100-500ms | > 500ms |
| CPU Usage | < 70% | 70-85% | > 85% |
| Memory Usage | < 80% | 80-90% | > 90% |
| Disk Usage | < 80% | 80-90% | > 90% |
| Error Rate | < 1% | 1-5% | > 5% |

### 2.2 LiveKit специфичные метрики

| Метрика | Нормальное значение | Предупреждение | Критическое |
|---------|-------------------|----------------|-------------|
| Room Creation Success Rate | > 99% | 95-99% | < 95% |
| Participant Connection Success | > 98% | 95-98% | < 95% |
| Audio Quality Score | > 4.0/5.0 | 3.0-4.0 | < 3.0 |
| SIP Call Success Rate | > 95% | 90-95% | < 90% |
| Token Refresh Success Rate | > 99.5% | 99-99.5% | < 99% |

### 2.3 Бизнес метрики

| Метрика | Нормальное значение | Предупреждение | Критическое |
|---------|-------------------|----------------|-------------|
| Average Call Duration | 2-10 minutes | < 1 minute | < 30 seconds |
| Calls per Hour | Зависит от нагрузки | Резкое снижение | Полное отсутствие |
| AI Response Time | < 2 seconds | 2-5 seconds | > 5 seconds |
| Voice Recognition Accuracy | > 90% | 80-90% | < 80% |

## 3. Алерты и уведомления

### 3.1 Конфигурация алертов

```yaml
# monitoring/prometheus/rules/livekit_alerts.yml
groups:
  - name: livekit.rules
    rules:
      # High API Latency
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, livekit_api_request_duration_seconds_bucket) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "95th percentile latency is {{ $value }}s"
      
      # High Error Rate
      - alert: HighErrorRate
        expr: rate(livekit_connection_errors_total[5m]) / rate(livekit_connections_total[5m]) > 0.05
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      # System Resource Usage
      - alert: HighCPUUsage
        expr: livekit_system_cpu_usage > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"
      
      # SIP Call Issues
      - alert: SIPCallFailures
        expr: rate(livekit_sip_call_failures_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SIP call failures detected"
          description: "SIP call failure rate is {{ $value }}/min"
```

### 3.2 Каналы уведомлений

#### Slack Integration

```python
# src/monitoring/alerting.py
import requests
import json

class SlackAlerting:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_alert(self, alert_data: dict):
        """Отправка алерта в Slack."""
        
        color = {
            'critical': '#FF0000',
            'warning': '#FFA500',
            'info': '#00FF00'
        }.get(alert_data.get('severity', 'info'), '#808080')
        
        message = {
            "attachments": [
                {
                    "color": color,
                    "title": f"🚨 {alert_data['alert_name']}",
                    "text": alert_data['description'],
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert_data['severity'].upper(),
                            "short": True
                        },
                        {
                            "title": "Component",
                            "value": alert_data.get('component', 'Unknown'),
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": alert_data['timestamp'],
                            "short": False
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(
            self.webhook_url,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        
        return response.status_code == 200
```

#### Email Notifications

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailAlerting:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    async def send_alert_email(self, alert_data: dict, recipients: list):
        """Отправка алерта по email."""
        
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[{alert_data['severity'].upper()}] {alert_data['alert_name']}"
        
        body = f"""
        Alert: {alert_data['alert_name']}
        Severity: {alert_data['severity']}
        Component: {alert_data.get('component', 'Unknown')}
        Description: {alert_data['description']}
        Timestamp: {alert_data['timestamp']}
        
        Please check the system dashboard for more details.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
```

## 4. Процедуры обслуживания

### 4.1 Ежедневные задачи

#### Автоматизированные проверки

```bash
#!/bin/bash
# scripts/daily_health_check.sh

echo "=== Daily Health Check $(date) ==="

# 1. Проверка состояния системы
echo "1. System Health Check:"
curl -s http://localhost:8000/health | jq '.'

# 2. Проверка логов на ошибки
echo "2. Error Log Check:"
grep -i error logs/livekit_system.log | tail -10

# 3. Проверка использования ресурсов
echo "3. Resource Usage:"
df -h | grep -E '(Filesystem|/dev/)'
free -h
top -bn1 | head -5

# 4. Проверка активных соединений
echo "4. Active Connections:"
netstat -an | grep :8000 | wc -l

# 5. Проверка Redis
echo "5. Redis Status:"
redis-cli ping

# 6. Проверка базы данных
echo "6. Database Status:"
python -c "
from src.database.connection import DatabaseConnection
db = DatabaseConnection()
print(f'Database connection: {db.test_connection()}')
"

echo "=== Health Check Complete ==="
```

#### Мониторинг метрик

```python
#!/usr/bin/env python3
# scripts/daily_metrics_report.py

import asyncio
import json
from datetime import datetime, timedelta, UTC
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.clients.livekit_api_client import LiveKitAPIClient

async def generate_daily_report():
    """Генерация ежедневного отчета по метрикам."""
    
    # Инициализация
    api_client = LiveKitAPIClient(
        url=os.getenv('LIVEKIT_URL'),
        api_key=os.getenv('LIVEKIT_API_KEY'),
        api_secret=os.getenv('LIVEKIT_API_SECRET')
    )
    monitor = LiveKitSystemMonitor(api_client)
    
    # Сбор метрик
    health_status = await monitor.run_health_checks()
    performance = await monitor._check_performance()
    
    # Формирование отчета
    report = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "health_status": health_status,
        "performance_metrics": performance,
        "summary": {
            "overall_health": "healthy" if all(
                check["status"] == "healthy" 
                for check in health_status["checks"].values()
            ) else "degraded",
            "avg_api_latency": performance["avg_api_latency_ms"],
            "active_rooms": performance["active_rooms"],
            "error_rate": performance["error_rate"]
        }
    }
    
    # Сохранение отчета
    report_file = f"reports/daily_report_{report['date']}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Daily report saved to {report_file}")
    return report

if __name__ == "__main__":
    asyncio.run(generate_daily_report())
```

### 4.2 Еженедельные задачи

#### Анализ производительности

```bash
#!/bin/bash
# scripts/weekly_performance_analysis.sh

echo "=== Weekly Performance Analysis $(date) ==="

# 1. Анализ логов за неделю
echo "1. Log Analysis (Last 7 days):"
find logs/ -name "*.log" -mtime -7 -exec grep -l "ERROR\|CRITICAL" {} \;

# 2. Анализ трендов производительности
echo "2. Performance Trends:"
python scripts/analyze_performance_trends.py --days 7

# 3. Проверка роста данных
echo "3. Data Growth Analysis:"
du -sh data/ logs/ backups/

# 4. Анализ использования ресурсов
echo "4. Resource Usage Trends:"
sar -u 1 1  # CPU usage
sar -r 1 1  # Memory usage
sar -d 1 1  # Disk I/O

# 5. Проверка сертификатов SSL
echo "5. SSL Certificate Check:"
openssl x509 -in /path/to/cert.pem -text -noout | grep "Not After"

echo "=== Weekly Analysis Complete ==="
```

#### Очистка и архивирование

```python
#!/usr/bin/env python3
# scripts/weekly_cleanup.py

import os
import shutil
import gzip
from datetime import datetime, timedelta, UTC
from pathlib import Path

def cleanup_old_logs(log_dir: str = "logs", days_to_keep: int = 30):
    """Очистка старых логов."""
    
    cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
    log_path = Path(log_dir)
    
    for log_file in log_path.glob("*.log"):
        if log_file.stat().st_mtime < cutoff_date.timestamp():
            # Архивирование перед удалением
            archive_name = f"{log_file}.{cutoff_date.strftime('%Y%m%d')}.gz"
            with open(log_file, 'rb') as f_in:
                with gzip.open(archive_name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            log_file.unlink()
            print(f"Archived and removed: {log_file}")

def cleanup_old_recordings(recordings_dir: str = "recordings", days_to_keep: int = 90):
    """Очистка старых записей."""
    
    cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
    recordings_path = Path(recordings_dir)
    
    if not recordings_path.exists():
        return
    
    for recording_file in recordings_path.rglob("*"):
        if recording_file.is_file() and recording_file.stat().st_mtime < cutoff_date.timestamp():
            recording_file.unlink()
            print(f"Removed old recording: {recording_file}")

def cleanup_temp_files(temp_dir: str = "/tmp", pattern: str = "livekit_*"):
    """Очистка временных файлов."""
    
    temp_path = Path(temp_dir)
    for temp_file in temp_path.glob(pattern):
        if temp_file.is_file():
            temp_file.unlink()
            print(f"Removed temp file: {temp_file}")

if __name__ == "__main__":
    print("Starting weekly cleanup...")
    cleanup_old_logs()
    cleanup_old_recordings()
    cleanup_temp_files()
    print("Weekly cleanup complete.")
```

### 4.3 Ежемесячные задачи

#### Полный аудит системы

```python
#!/usr/bin/env python3
# scripts/monthly_system_audit.py

import asyncio
import json
from datetime import datetime, UTC
from src.security.livekit_security import LiveKitSecurityManager
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor

async def monthly_audit():
    """Проведение ежемесячного аудита системы."""
    
    audit_results = {
        "audit_date": datetime.now(UTC).isoformat(),
        "security_audit": {},
        "performance_audit": {},
        "configuration_audit": {},
        "recommendations": []
    }
    
    # 1. Аудит безопасности
    security_manager = LiveKitSecurityManager(
        os.getenv('LIVEKIT_API_KEY'),
        os.getenv('LIVEKIT_API_SECRET')
    )
    
    security_results = await security_manager.run_security_audit()
    audit_results["security_audit"] = security_results
    
    # 2. Аудит производительности
    monitor = LiveKitSystemMonitor(api_client)
    performance_results = await monitor.run_performance_audit()
    audit_results["performance_audit"] = performance_results
    
    # 3. Аудит конфигурации
    config_results = audit_configuration()
    audit_results["configuration_audit"] = config_results
    
    # 4. Генерация рекомендаций
    recommendations = generate_recommendations(audit_results)
    audit_results["recommendations"] = recommendations
    
    # Сохранение результатов
    audit_file = f"audits/monthly_audit_{datetime.now(UTC).strftime('%Y%m')}.json"
    with open(audit_file, 'w') as f:
        json.dump(audit_results, f, indent=2)
    
    print(f"Monthly audit completed. Results saved to {audit_file}")
    return audit_results

def audit_configuration():
    """Аудит конфигурации системы."""
    
    config_issues = []
    
    # Проверка переменных окружения
    required_vars = [
        'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET',
        'SIP_SERVER', 'SIP_USERNAME', 'SIP_PASSWORD'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            config_issues.append(f"Missing environment variable: {var}")
    
    # Проверка конфигурационных файлов
    config_files = [
        'config/livekit_auth.yaml',
        'config/monitoring.yaml',
        'config/security.yaml',
        'livekit-sip-correct.yaml'
    ]
    
    for config_file in config_files:
        if not os.path.exists(config_file):
            config_issues.append(f"Missing configuration file: {config_file}")
    
    return {
        "issues_found": len(config_issues),
        "issues": config_issues,
        "status": "healthy" if len(config_issues) == 0 else "needs_attention"
    }

def generate_recommendations(audit_results):
    """Генерация рекомендаций на основе результатов аудита."""
    
    recommendations = []
    
    # Рекомендации по безопасности
    security_audit = audit_results["security_audit"]
    failed_checks = [
        check for check, result in security_audit.items()
        if not result.get("passed", True)
    ]
    
    if failed_checks:
        recommendations.append({
            "category": "security",
            "priority": "high",
            "description": f"Address failed security checks: {', '.join(failed_checks)}"
        })
    
    # Рекомендации по производительности
    performance_audit = audit_results["performance_audit"]
    if performance_audit.get("avg_api_latency_ms", 0) > 100:
        recommendations.append({
            "category": "performance",
            "priority": "medium",
            "description": "API latency is above recommended threshold. Consider optimization."
        })
    
    # Рекомендации по конфигурации
    config_audit = audit_results["configuration_audit"]
    if config_audit["issues_found"] > 0:
        recommendations.append({
            "category": "configuration",
            "priority": "high",
            "description": "Configuration issues found. Review and fix missing components."
        })
    
    return recommendations

if __name__ == "__main__":
    asyncio.run(monthly_audit())
```

## 5. Планы реагирования на инциденты

### 5.1 Классификация инцидентов

#### Severity Levels

| Level | Описание | Время реагирования | Эскалация |
|-------|----------|-------------------|-----------|
| P1 - Critical | Полный отказ системы | 15 минут | Немедленная |
| P2 - High | Значительное снижение производительности | 1 час | 2 часа |
| P3 - Medium | Частичная функциональность нарушена | 4 часа | 8 часов |
| P4 - Low | Минорные проблемы | 24 часа | 48 часов |

#### Типы инцидентов

1. **Отказ аутентификации** - невозможность создания/валидации токенов
2. **Отказ API** - недоступность LiveKit API
3. **Проблемы SIP** - невозможность принимать/совершать звонки
4. **Проблемы производительности** - высокая латентность, низкая пропускная способность
5. **Проблемы безопасности** - подозрительная активность, утечки данных

### 5.2 Процедуры реагирования

#### P1 - Critical Incident Response

```bash
#!/bin/bash
# scripts/critical_incident_response.sh

echo "=== CRITICAL INCIDENT RESPONSE ==="
echo "Timestamp: $(date)"

# 1. Немедленная диагностика
echo "1. Running immediate diagnostics..."
python scripts/diagnose_livekit_connection.py > incident_diagnostics.log 2>&1

# 2. Проверка основных сервисов
echo "2. Checking core services..."
systemctl status redis-server
systemctl status nginx
curl -s http://localhost:8000/health || echo "Health check failed"

# 3. Проверка логов на критические ошибки
echo "3. Checking for critical errors..."
tail -100 logs/livekit_system.log | grep -i "critical\|fatal\|error"

# 4. Попытка автоматического восстановления
echo "4. Attempting automatic recovery..."
./scripts/auto_recovery.sh

# 5. Уведомление команды
echo "5. Notifying incident response team..."
python scripts/send_critical_alert.py --incident="System failure detected"

echo "=== CRITICAL INCIDENT RESPONSE COMPLETE ==="
```

#### Автоматическое восстановление

```python
#!/usr/bin/env python3
# scripts/auto_recovery.py

import asyncio
import subprocess
import time
from src.clients.livekit_api_client import LiveKitAPIClient
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor

async def attempt_auto_recovery():
    """Попытка автоматического восстановления системы."""
    
    recovery_steps = [
        ("restart_redis", restart_redis),
        ("restart_application", restart_application),
        ("clear_cache", clear_cache),
        ("reload_configuration", reload_configuration),
        ("test_connectivity", test_connectivity)
    ]
    
    recovery_log = []
    
    for step_name, step_function in recovery_steps:
        print(f"Executing recovery step: {step_name}")
        
        try:
            result = await step_function()
            recovery_log.append({
                "step": step_name,
                "status": "success",
                "result": result,
                "timestamp": time.time()
            })
            
            # Проверка после каждого шага
            if await test_system_health():
                print(f"System recovered after step: {step_name}")
                return recovery_log
                
        except Exception as e:
            recovery_log.append({
                "step": step_name,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time()
            })
            print(f"Recovery step failed: {step_name} - {e}")
    
    print("Automatic recovery failed. Manual intervention required.")
    return recovery_log

async def restart_redis():
    """Перезапуск Redis сервера."""
    result = subprocess.run(['systemctl', 'restart', 'redis-server'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Redis restart failed: {result.stderr}")
    return "Redis restarted successfully"

async def restart_application():
    """Перезапуск основного приложения."""
    # Graceful shutdown
    subprocess.run(['pkill', '-TERM', '-f', 'src/main.py'])
    time.sleep(5)
    
    # Force kill if still running
    subprocess.run(['pkill', '-KILL', '-f', 'src/main.py'])
    time.sleep(2)
    
    # Restart application
    subprocess.Popen(['python', 'src/main.py'])
    time.sleep(10)  # Wait for startup
    
    return "Application restarted"

async def clear_cache():
    """Очистка кэша."""
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.flushdb()
    return "Cache cleared"

async def reload_configuration():
    """Перезагрузка конфигурации."""
    # Reload environment variables
    subprocess.run(['systemctl', 'daemon-reload'])
    return "Configuration reloaded"

async def test_connectivity():
    """Тест подключения к внешним сервисам."""
    # Test LiveKit API
    try:
        api_client = LiveKitAPIClient(
            url=os.getenv('LIVEKIT_URL'),
            api_key=os.getenv('LIVEKIT_API_KEY'),
            api_secret=os.getenv('LIVEKIT_API_SECRET')
        )
        rooms = await api_client.list_rooms()
        return f"LiveKit API accessible. Found {len(rooms)} rooms."
    except Exception as e:
        raise Exception(f"LiveKit API test failed: {e}")

async def test_system_health():
    """Проверка общего состояния системы."""
    try:
        monitor = LiveKitSystemMonitor(api_client)
        health_status = await monitor.run_health_checks()
        
        # Проверка, что все критические компоненты работают
        critical_components = ['room_service', 'sip_service']
        for component in critical_components:
            if health_status['checks'].get(component, {}).get('status') != 'healthy':
                return False
        
        return True
    except:
        return False

if __name__ == "__main__":
    asyncio.run(attempt_auto_recovery())
```

### 5.3 Процедуры эскалации

#### Матрица эскалации

```
Level 1: Automated Response (0-15 min)
├── Automatic diagnostics
├── Auto-recovery attempts
└── Initial alerts

Level 2: On-call Engineer (15 min - 1 hour)
├── Manual diagnostics
├── Immediate fixes
└── Status updates

Level 3: Senior Engineer (1-2 hours)
├── Complex troubleshooting
├── Architecture decisions
└── Vendor escalation

Level 4: Management (2+ hours)
├── Customer communication
├── Resource allocation
└── Post-incident review
```

#### Контакты для эскалации

```yaml
# config/incident_contacts.yaml
escalation_contacts:
  level_1:
    - type: "automated"
      action: "run_diagnostics"
      
  level_2:
    - name: "On-call Engineer"
      phone: "+1-555-0123"
      email: "oncall@company.com"
      slack: "@oncall-engineer"
      
  level_3:
    - name: "Senior Engineer"
      phone: "+1-555-0456"
      email: "senior@company.com"
      slack: "@senior-engineer"
      
  level_4:
    - name: "Engineering Manager"
      phone: "+1-555-0789"
      email: "manager@company.com"
      slack: "@eng-manager"

notification_channels:
  critical:
    - slack: "#incidents"
    - email: "team@company.com"
    - sms: "+1-555-ALERT"
    
  high:
    - slack: "#alerts"
    - email: "oncall@company.com"
    
  medium:
    - slack: "#monitoring"
    
  low:
    - email: "logs@company.com"
```

## 6. Резервное копирование и восстановление

### 6.1 Стратегия резервного копирования

#### Что резервируется

1. **Конфигурационные файлы**
   - `.env` файлы
   - YAML конфигурации
   - SSL сертификаты

2. **База данных**
   - SQLite файлы
   - Схема базы данных
   - Пользовательские данные

3. **Логи системы**
   - Архивные логи
   - Метрики производительности
   - Аудит логи

4. **Записи разговоров** (если включены)
   - Аудио файлы
   - Метаданные записей

#### Расписание резервного копирования

```bash
# Crontab entries for backup schedule

# Ежедневное резервное копирование конфигураций (2:00 AM)
0 2 * * * /path/to/scripts/backup_configs.sh

# Еженедельное резервное копирование базы данных (Sunday 3:00 AM)
0 3 * * 0 /path/to/scripts/backup_database.sh

# Ежемесячное полное резервное копирование (1st day 4:00 AM)
0 4 1 * * /path/to/scripts/full_backup.sh
```

#### Скрипт резервного копирования

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="livekit_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "Starting backup: ${BACKUP_NAME}"

# Создание директории резервной копии
mkdir -p "${BACKUP_PATH}"

# 1. Резервное копирование конфигураций
echo "Backing up configurations..."
cp -r config/ "${BACKUP_PATH}/"
cp .env* "${BACKUP_PATH}/"
cp *.yaml "${BACKUP_PATH}/"

# 2. Резервное копирование базы данных
echo "Backing up database..."
mkdir -p "${BACKUP_PATH}/database"
cp data/*.db "${BACKUP_PATH}/database/" 2>/dev/null || true

# 3. Резервное копирование логов
echo "Backing up logs..."
mkdir -p "${BACKUP_PATH}/logs"
cp logs/*.log "${BACKUP_PATH}/logs/" 2>/dev/null || true

# 4. Резервное копирование скриптов
echo "Backing up scripts..."
cp -r scripts/ "${BACKUP_PATH}/"

# 5. Создание архива
echo "Creating archive..."
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"

# 6. Очистка старых резервных копий (старше 30 дней)
find "${BACKUP_DIR}" -name "livekit_backup_*.tar.gz" -mtime +30 -delete

echo "Backup completed: ${BACKUP_PATH}.tar.gz"

# 7. Проверка целостности архива
if tar -tzf "${BACKUP_PATH}.tar.gz" >/dev/null 2>&1; then
    echo "Backup integrity check: PASSED"
else
    echo "Backup integrity check: FAILED"
    exit 1
fi
```

### 6.2 Процедуры восстановления

#### Восстановление из резервной копии

```bash
#!/bin/bash
# scripts/restore.sh

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_name>"
    echo "Available backups:"
    ls -1 /backups/livekit_backup_*.tar.gz | sed 's/.*livekit_backup_//' | sed 's/.tar.gz//'
    exit 1
fi

BACKUP_NAME="livekit_backup_$1"
BACKUP_FILE="/backups/${BACKUP_NAME}.tar.gz"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "Restoring from backup: ${BACKUP_NAME}"

# 1. Остановка сервисов
echo "Stopping services..."
systemctl stop livekit-voice-ai
systemctl stop redis-server

# 2. Создание резервной копии текущего состояния
echo "Creating current state backup..."
./scripts/backup.sh

# 3. Извлечение архива
echo "Extracting backup..."
cd /tmp
tar -xzf "${BACKUP_FILE}"

# 4. Восстановление конфигураций
echo "Restoring configurations..."
cp -r "/tmp/${BACKUP_NAME}/config/"* config/
cp "/tmp/${BACKUP_NAME}/.env"* ./ 2>/dev/null || true
cp "/tmp/${BACKUP_NAME}/"*.yaml ./ 2>/dev/null || true

# 5. Восстановление базы данных
echo "Restoring database..."
cp "/tmp/${BACKUP_NAME}/database/"*.db data/ 2>/dev/null || true

# 6. Восстановление скриптов
echo "Restoring scripts..."
cp -r "/tmp/${BACKUP_NAME}/scripts/"* scripts/

# 7. Установка правильных разрешений
echo "Setting permissions..."
chmod +x scripts/*.sh
chmod 600 .env*

# 8. Запуск сервисов
echo "Starting services..."
systemctl start redis-server
sleep 5
systemctl start livekit-voice-ai

# 9. Проверка восстановления
echo "Verifying restoration..."
sleep 10
curl -s http://localhost:8000/health | jq '.'

# 10. Очистка временных файлов
rm -rf "/tmp/${BACKUP_NAME}"

echo "Restoration completed successfully"
```

## 7. Документация изменений

### 7.1 Change Log Template

```markdown
# Change Log

## [Version] - YYYY-MM-DD

### Added
- New features and functionality

### Changed
- Changes to existing functionality

### Deprecated
- Features that will be removed in future versions

### Removed
- Features removed in this version

### Fixed
- Bug fixes

### Security
- Security improvements and fixes

### Performance
- Performance improvements

### Configuration
- Configuration changes required
```

### 7.2 Процедура внесения изменений

1. **Планирование изменений**
   - Создание RFC (Request for Comments)
   - Оценка влияния на систему
   - Планирование downtime

2. **Тестирование**
   - Тестирование в staging environment
   - Regression testing
   - Performance testing

3. **Развертывание**
   - Blue-green deployment
   - Canary releases
   - Rollback procedures

4. **Мониторинг**
   - Post-deployment monitoring
   - Performance validation
   - Error tracking

## Заключение

Данное руководство обеспечивает комплексный подход к мониторингу и обслуживанию системы LiveKit. Регулярное выполнение описанных процедур гарантирует:

- Высокую доступность системы
- Быстрое обнаружение и устранение проблем
- Оптимальную производительность
- Безопасность данных и операций
- Готовность к инцидентам

Обновляйте процедуры по мере развития системы и накопления опыта эксплуатации.
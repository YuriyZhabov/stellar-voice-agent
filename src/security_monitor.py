"""
Security monitoring system for Voice AI Agent.
This module provides comprehensive security monitoring, threat detection,
and incident response capabilities.
"""

import asyncio
import json
import logging
import time
import hashlib
import ipaddress
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
import re
import aiofiles
import httpx
from collections import defaultdict, deque

from src.config import get_settings
from src.metrics import get_metrics_collector

logger = logging.getLogger(__name__)

@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_id: str
    timestamp: datetime
    event_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    source_ip: str
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False

@dataclass
class ThreatIntelligence:
    """Threat intelligence data."""
    ip_address: str
    threat_type: str
    confidence: float
    source: str
    last_seen: datetime
    details: Dict[str, Any] = field(default_factory=dict)

class SecurityMonitor:
    """Comprehensive security monitoring system."""
    
    def __init__(self):
        """Initialize security monitor."""
        self.settings = get_settings()
        self.metrics_collector = get_metrics_collector()
        
        # Security event storage
        self.security_events: List[SecurityEvent] = []
        self.threat_intelligence: Dict[str, ThreatIntelligence] = {}
        
        # Rate limiting tracking
        self.request_counts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.blocked_ips: Set[str] = set()
        
        # Suspicious patterns
        self.suspicious_patterns = [
            r'(?i)(union|select|insert|delete|drop|create|alter)\s+',
            r'(?i)<script[^>]*>.*?</script>',
            r'(?i)javascript:',
            r'(?i)(eval|exec|system|shell_exec)\s*\(',
            r'\.\./',
            r'/etc/passwd',
            r'/proc/self/environ',
            r'cmd\.exe',
            r'powershell',
        ]
        
        # Compile patterns for performance
        self.compiled_patterns = [re.compile(pattern) for pattern in self.suspicious_patterns]
        
        # Security thresholds
        self.thresholds = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'failed_auth_attempts': 5,
            'suspicious_pattern_threshold': 3,
            'geo_anomaly_threshold': 0.8,
        }
        
        # GeoIP database (simplified)
        self.known_countries = set()
        
        logger.info("Security monitor initialized")
    
    async def start_monitoring(self):
        """Start security monitoring tasks."""
        logger.info("Starting security monitoring...")
        
        # Start monitoring tasks
        tasks = [
            self.monitor_access_logs(),
            self.monitor_failed_authentications(),
            self.monitor_suspicious_patterns(),
            self.monitor_rate_limits(),
            self.update_threat_intelligence(),
            self.cleanup_old_events(),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_access_logs(self):
        """Monitor access logs for suspicious activity."""
        log_file = Path("logs/access.log")
        
        if not log_file.exists():
            logger.warning("Access log file not found")
            return
        
        try:
            async with aiofiles.open(log_file, 'r') as f:
                # Seek to end of file
                await f.seek(0, 2)
                
                while True:
                    line = await f.readline()
                    if line:
                        await self.analyze_log_entry(line.strip())
                    else:
                        await asyncio.sleep(1)
                        
        except Exception as e:
            logger.error(f"Error monitoring access logs: {e}")
    
    async def analyze_log_entry(self, log_line: str):
        """Analyze a single log entry for security threats."""
        try:
            # Parse log entry (simplified nginx log format)
            parts = log_line.split(' ')
            if len(parts) < 10:
                return
            
            ip_address = parts[0]
            timestamp_str = ' '.join(parts[3:5]).strip('[]')
            request = parts[6:9]
            status_code = parts[9] if len(parts) > 9 else '000'
            user_agent = ' '.join(parts[11:]) if len(parts) > 11 else ''
            
            # Create basic request info
            request_info = {
                'ip': ip_address,
                'timestamp': timestamp_str,
                'method': request[0] if request else '',
                'path': request[1] if len(request) > 1 else '',
                'status': status_code,
                'user_agent': user_agent.strip('"'),
            }
            
            # Analyze for threats
            await self.detect_threats(request_info)
            
        except Exception as e:
            logger.error(f"Error analyzing log entry: {e}")
    
    async def detect_threats(self, request_info: Dict[str, Any]):
        """Detect various types of security threats."""
        ip_address = request_info['ip']
        path = request_info.get('path', '')
        user_agent = request_info.get('user_agent', '')
        status = request_info.get('status', '000')
        
        # Rate limiting check
        await self.check_rate_limiting(ip_address)
        
        # Suspicious pattern detection
        await self.check_suspicious_patterns(ip_address, path, user_agent)
        
        # Failed authentication detection
        if status in ['401', '403']:
            await self.handle_failed_authentication(ip_address, path)
        
        # Bot detection
        await self.detect_bots(ip_address, user_agent)
        
        # Geographic anomaly detection
        await self.check_geographic_anomalies(ip_address)
        
        # Update metrics
        self.metrics_collector.increment_counter(
            "security_requests_analyzed_total",
            labels={"ip": ip_address, "status": status}
        )
    
    async def check_rate_limiting(self, ip_address: str):
        """Check for rate limiting violations."""
        current_time = time.time()
        
        # Add current request
        self.request_counts[ip_address].append(current_time)
        
        # Count requests in last minute
        minute_ago = current_time - 60
        recent_requests = [t for t in self.request_counts[ip_address] if t > minute_ago]
        
        if len(recent_requests) > self.thresholds['requests_per_minute']:
            await self.create_security_event(
                event_type="RATE_LIMIT_VIOLATION",
                severity="HIGH",
                source_ip=ip_address,
                description=f"Rate limit exceeded: {len(recent_requests)} requests in 1 minute",
                details={"request_count": len(recent_requests), "threshold": self.thresholds['requests_per_minute']}
            )
            
            # Block IP temporarily
            self.blocked_ips.add(ip_address)
            logger.warning(f"Blocked IP {ip_address} for rate limiting violation")
    
    async def check_suspicious_patterns(self, ip_address: str, path: str, user_agent: str):
        """Check for suspicious patterns in requests."""
        suspicious_count = 0
        detected_patterns = []
        
        # Check path for suspicious patterns
        for pattern in self.compiled_patterns:
            if pattern.search(path):
                suspicious_count += 1
                detected_patterns.append(pattern.pattern)
        
        # Check user agent for suspicious patterns
        for pattern in self.compiled_patterns:
            if pattern.search(user_agent):
                suspicious_count += 1
                detected_patterns.append(pattern.pattern)
        
        if suspicious_count >= self.thresholds['suspicious_pattern_threshold']:
            await self.create_security_event(
                event_type="SUSPICIOUS_PATTERN",
                severity="HIGH",
                source_ip=ip_address,
                endpoint=path,
                user_agent=user_agent,
                description=f"Suspicious patterns detected: {suspicious_count}",
                details={"patterns": detected_patterns, "count": suspicious_count}
            )
    
    async def handle_failed_authentication(self, ip_address: str, path: str):
        """Handle failed authentication attempts."""
        # Count failed attempts from this IP
        recent_failures = [
            event for event in self.security_events
            if event.source_ip == ip_address 
            and event.event_type == "FAILED_AUTHENTICATION"
            and event.timestamp > datetime.now(UTC) - timedelta(hours=1)
        ]
        
        if len(recent_failures) >= self.thresholds['failed_auth_attempts']:
            await self.create_security_event(
                event_type="BRUTE_FORCE_ATTACK",
                severity="CRITICAL",
                source_ip=ip_address,
                endpoint=path,
                description=f"Brute force attack detected: {len(recent_failures)} failed attempts",
                details={"failed_attempts": len(recent_failures)}
            )
            
            # Block IP
            self.blocked_ips.add(ip_address)
        else:
            await self.create_security_event(
                event_type="FAILED_AUTHENTICATION",
                severity="MEDIUM",
                source_ip=ip_address,
                endpoint=path,
                description="Failed authentication attempt"
            )
    
    async def detect_bots(self, ip_address: str, user_agent: str):
        """Detect malicious bots."""
        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper', 'scanner',
            'nikto', 'sqlmap', 'nmap', 'masscan', 'zap'
        ]
        
        user_agent_lower = user_agent.lower()
        
        for indicator in bot_indicators:
            if indicator in user_agent_lower:
                await self.create_security_event(
                    event_type="MALICIOUS_BOT",
                    severity="HIGH",
                    source_ip=ip_address,
                    user_agent=user_agent,
                    description=f"Malicious bot detected: {indicator}",
                    details={"bot_type": indicator}
                )
                break
    
    async def check_geographic_anomalies(self, ip_address: str):
        """Check for geographic anomalies."""
        try:
            # Simplified geo check (in production, use proper GeoIP database)
            if self.is_private_ip(ip_address):
                return
            
            # For demo purposes, flag non-Russian IPs as anomalies
            # In production, implement proper geolocation
            country = await self.get_country_for_ip(ip_address)
            
            if country and country not in ['RU', 'BY', 'KZ']:  # Expected countries
                await self.create_security_event(
                    event_type="GEOGRAPHIC_ANOMALY",
                    severity="MEDIUM",
                    source_ip=ip_address,
                    description=f"Request from unexpected country: {country}",
                    details={"country": country}
                )
                
        except Exception as e:
            logger.error(f"Error checking geographic anomalies: {e}")
    
    def is_private_ip(self, ip_address: str) -> bool:
        """Check if IP address is private."""
        try:
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private
        except ValueError:
            return False
    
    async def get_country_for_ip(self, ip_address: str) -> Optional[str]:
        """Get country code for IP address."""
        try:
            # Use a free GeoIP service (in production, use local database)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://ip-api.com/json/{ip_address}",
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get('countryCode')
        except Exception as e:
            logger.error(f"Error getting country for IP {ip_address}: {e}")
        
        return None
    
    async def create_security_event(
        self,
        event_type: str,
        severity: str,
        source_ip: str,
        endpoint: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        """Create a new security event."""
        event_id = hashlib.md5(
            f"{event_type}_{source_ip}_{time.time()}".encode()
        ).hexdigest()[:16]
        
        event = SecurityEvent(
            event_id=event_id,
            timestamp=datetime.now(UTC),
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            endpoint=endpoint,
            user_agent=user_agent,
            description=description,
            details=details or {}
        )
        
        self.security_events.append(event)
        
        # Log security event
        logger.warning(
            f"Security event: {event_type} from {source_ip} - {description}",
            extra={
                "event_id": event_id,
                "event_type": event_type,
                "severity": severity,
                "source_ip": source_ip,
                "details": details
            }
        )
        
        # Update metrics
        self.metrics_collector.increment_counter(
            "security_events_total",
            labels={"type": event_type, "severity": severity}
        )
        
        # Send alerts for high severity events
        if severity in ["HIGH", "CRITICAL"]:
            await self.send_security_alert(event)
    
    async def send_security_alert(self, event: SecurityEvent):
        """Send security alert notification."""
        try:
            # In production, integrate with alerting systems (email, Slack, etc.)
            alert_message = {
                "alert_type": "security_event",
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "severity": event.severity,
                "event_type": event.event_type,
                "source_ip": event.source_ip,
                "description": event.description,
                "details": event.details
            }
            
            # Log alert (in production, send to alerting system)
            logger.critical(f"SECURITY ALERT: {json.dumps(alert_message, indent=2)}")
            
            # Update alert metrics
            self.metrics_collector.increment_counter(
                "security_alerts_sent_total",
                labels={"severity": event.severity, "type": event.event_type}
            )
            
        except Exception as e:
            logger.error(f"Error sending security alert: {e}")
    
    async def monitor_failed_authentications(self):
        """Monitor for failed authentication patterns."""
        while True:
            try:
                # Check for authentication failures in the last hour
                one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
                
                failed_auth_events = [
                    event for event in self.security_events
                    if event.event_type == "FAILED_AUTHENTICATION"
                    and event.timestamp > one_hour_ago
                ]
                
                # Group by IP address
                ip_failures = defaultdict(int)
                for event in failed_auth_events:
                    ip_failures[event.source_ip] += 1
                
                # Check for brute force patterns
                for ip, count in ip_failures.items():
                    if count >= self.thresholds['failed_auth_attempts']:
                        await self.create_security_event(
                            event_type="BRUTE_FORCE_PATTERN",
                            severity="CRITICAL",
                            source_ip=ip,
                            description=f"Brute force pattern detected: {count} failures in 1 hour",
                            details={"failure_count": count}
                        )
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error monitoring failed authentications: {e}")
                await asyncio.sleep(60)
    
    async def monitor_suspicious_patterns(self):
        """Monitor for suspicious pattern trends."""
        while True:
            try:
                # Analyze patterns in the last hour
                one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
                
                pattern_events = [
                    event for event in self.security_events
                    if event.event_type == "SUSPICIOUS_PATTERN"
                    and event.timestamp > one_hour_ago
                ]
                
                if len(pattern_events) > 10:  # Threshold for pattern attack
                    await self.create_security_event(
                        event_type="PATTERN_ATTACK",
                        severity="HIGH",
                        source_ip="multiple",
                        description=f"Pattern attack detected: {len(pattern_events)} suspicious requests",
                        details={"event_count": len(pattern_events)}
                    )
                
                await asyncio.sleep(600)  # Check every 10 minutes
                
            except Exception as e:
                logger.error(f"Error monitoring suspicious patterns: {e}")
                await asyncio.sleep(60)
    
    async def monitor_rate_limits(self):
        """Monitor rate limiting effectiveness."""
        while True:
            try:
                # Clean up old request counts
                current_time = time.time()
                hour_ago = current_time - 3600
                
                for ip in list(self.request_counts.keys()):
                    # Remove old requests
                    while (self.request_counts[ip] and 
                           self.request_counts[ip][0] < hour_ago):
                        self.request_counts[ip].popleft()
                    
                    # Remove empty entries
                    if not self.request_counts[ip]:
                        del self.request_counts[ip]
                
                # Clean up blocked IPs (unblock after 1 hour)
                self.blocked_ips = {
                    ip for ip in self.blocked_ips
                    # In production, implement proper unblocking logic
                }
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error monitoring rate limits: {e}")
                await asyncio.sleep(60)
    
    async def update_threat_intelligence(self):
        """Update threat intelligence data."""
        while True:
            try:
                # In production, integrate with threat intelligence feeds
                # For now, just clean up old intelligence data
                
                one_week_ago = datetime.now(UTC) - timedelta(days=7)
                
                # Remove old threat intelligence
                self.threat_intelligence = {
                    ip: intel for ip, intel in self.threat_intelligence.items()
                    if intel.last_seen > one_week_ago
                }
                
                logger.info(f"Threat intelligence updated: {len(self.threat_intelligence)} entries")
                
                await asyncio.sleep(3600)  # Update every hour
                
            except Exception as e:
                logger.error(f"Error updating threat intelligence: {e}")
                await asyncio.sleep(300)
    
    async def cleanup_old_events(self):
        """Clean up old security events."""
        while True:
            try:
                # Keep events for 30 days
                thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
                
                old_count = len(self.security_events)
                self.security_events = [
                    event for event in self.security_events
                    if event.timestamp > thirty_days_ago
                ]
                
                cleaned_count = old_count - len(self.security_events)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old security events")
                
                await asyncio.sleep(86400)  # Clean up daily
                
            except Exception as e:
                logger.error(f"Error cleaning up old events: {e}")
                await asyncio.sleep(3600)
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status."""
        now = datetime.now(UTC)
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        recent_events = [e for e in self.security_events if e.timestamp > last_hour]
        daily_events = [e for e in self.security_events if e.timestamp > last_day]
        
        return {
            "timestamp": now.isoformat(),
            "total_events": len(self.security_events),
            "events_last_hour": len(recent_events),
            "events_last_day": len(daily_events),
            "blocked_ips": len(self.blocked_ips),
            "threat_intelligence_entries": len(self.threat_intelligence),
            "recent_events_by_type": {
                event_type: len([e for e in recent_events if e.event_type == event_type])
                for event_type in set(e.event_type for e in recent_events)
            },
            "recent_events_by_severity": {
                severity: len([e for e in recent_events if e.severity == severity])
                for severity in set(e.severity for e in recent_events)
            }
        }
    
    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP address is blocked."""
        return ip_address in self.blocked_ips
    
    async def unblock_ip(self, ip_address: str):
        """Manually unblock an IP address."""
        if ip_address in self.blocked_ips:
            self.blocked_ips.remove(ip_address)
            logger.info(f"Manually unblocked IP: {ip_address}")
            
            await self.create_security_event(
                event_type="IP_UNBLOCKED",
                severity="LOW",
                source_ip=ip_address,
                description="IP address manually unblocked"
            )

# Global security monitor instance
_security_monitor = None

def get_security_monitor() -> SecurityMonitor:
    """Get global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor
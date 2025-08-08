#!/usr/bin/env python3
"""
Real-time Call Activity Monitor

This script monitors call activity in real-time, showing logs, webhooks, and system status.
"""

import asyncio
import subprocess
import time
import json
import sys
from datetime import datetime
import threading
import queue

def print_timestamp():
    return datetime.now().strftime("%H:%M:%S")

def monitor_docker_logs():
    """Monitor Docker logs for call activity."""
    print(f"[{print_timestamp()}] 📋 Starting Docker logs monitor...")
    
    try:
        process = subprocess.Popen(
            ["docker", "compose", "-f", "docker-compose.simple.yml", "logs", "-f", "--tail=0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                timestamp = print_timestamp()
                # Filter for interesting events
                if any(keyword in line.lower() for keyword in [
                    'webhook', 'livekit', 'sip', 'call', 'participant', 'room', 'error', 'failed'
                ]):
                    print(f"[{timestamp}] 🐳 {line.strip()}")
                    
    except KeyboardInterrupt:
        process.terminate()
    except Exception as e:
        print(f"[{print_timestamp()}] ❌ Docker logs error: {e}")

def monitor_webhook_endpoint():
    """Monitor webhook endpoint for incoming requests."""
    print(f"[{print_timestamp()}] 🌐 Monitoring webhook endpoint...")
    
    # This would require access to web server logs or implementing a webhook logger
    # For now, we'll rely on Docker logs which should show webhook requests

def monitor_system_health():
    """Monitor system health periodically."""
    while True:
        try:
            timestamp = print_timestamp()
            
            # Check main service
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8000/health"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                try:
                    health_data = json.loads(result.stdout)
                    status = health_data.get('status', 'unknown')
                    print(f"[{timestamp}] 💓 System health: {status}")
                except:
                    print(f"[{timestamp}] 💓 System responding (health check has issues)")
            else:
                print(f"[{timestamp}] ❌ System not responding")
            
            # Check Prometheus
            result = subprocess.run(
                ["curl", "-s", "http://localhost:9090/-/healthy"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                print(f"[{timestamp}] 📊 Prometheus: healthy")
            else:
                print(f"[{timestamp}] ⚠️ Prometheus: not responding")
                
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[{print_timestamp()}] ❌ Health monitor error: {e}")
            time.sleep(30)

def main():
    """Main monitoring function."""
    print("🔍 Real-time Call Activity Monitor")
    print("=" * 60)
    print(f"[{print_timestamp()}] 🚀 Starting monitoring...")
    print()
    print("📊 Monitoring URLs:")
    print("   - Prometheus: http://localhost:9090")
    print("   - Grafana: http://localhost:3000 (admin/admin)")
    print("   - Voice AI Agent: http://localhost:8000")
    print()
    print("🎯 Watching for:")
    print("   - Incoming webhook calls")
    print("   - LiveKit events")
    print("   - SIP activity")
    print("   - System errors")
    print()
    print("📞 Make your test call now!")
    print("=" * 60)
    print()
    
    # Start health monitor in background thread
    health_thread = threading.Thread(target=monitor_system_health, daemon=True)
    health_thread.start()
    
    try:
        # Main thread monitors Docker logs
        monitor_docker_logs()
    except KeyboardInterrupt:
        print(f"\n[{print_timestamp()}] 🛑 Monitoring stopped by user")
    except Exception as e:
        print(f"\n[{print_timestamp()}] ❌ Monitor error: {e}")

if __name__ == "__main__":
    main()
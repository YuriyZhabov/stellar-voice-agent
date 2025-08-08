#!/usr/bin/env python3
"""
Real-time system monitoring script for Voice AI Agent.
This script provides live monitoring of system metrics and performance.
"""

import asyncio
import json
import logging
import time
import statistics
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
import sys
import requests
import curses
from dataclasses import dataclass, field

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce log noise for monitoring
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System metrics snapshot."""
    timestamp: datetime
    call_rate: float = 0.0
    active_calls: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    p95_latency: float = 0.0
    stt_latency: float = 0.0
    llm_latency: float = 0.0
    tts_latency: float = 0.0
    error_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    health_status: str = "unknown"
    alerts: List[str] = field(default_factory=list)

class SystemMonitor:
    """Real-time system monitoring."""
    
    def __init__(self):
        """Initialize the system monitor."""
        try:
            self.settings = get_settings()
        except Exception:
            # Fallback settings if config fails
            self.settings = type('Settings', (), {
                'health_check_port': 8001,
                'metrics_port': 8000
            })()
        
        self.base_url = f"http://localhost:{self.settings.health_check_port}"
        self.metrics_url = f"http://localhost:{self.settings.metrics_port}"
        self.prometheus_url = "http://localhost:9090"
        
        self.metrics_history = []
        self.max_history = 100
        
        # Alert thresholds
        self.thresholds = {
            'latency_warning': 1.5,
            'latency_critical': 3.0,
            'error_rate_warning': 0.1,
            'error_rate_critical': 0.25,
            'memory_warning': 2048,  # MB
            'memory_critical': 4096,  # MB
            'cpu_warning': 80,  # %
            'cpu_critical': 95,  # %
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}
    
    async def get_prometheus_metrics(self) -> Dict[str, float]:
        """Get metrics from Prometheus."""
        metrics = {}
        try:
            # Query Prometheus for key metrics
            queries = {
                'call_rate': 'rate(voice_ai_calls_total[1m])',
                'active_calls': 'voice_ai_active_calls',
                'success_rate': 'rate(voice_ai_calls_total{status="success"}[5m]) / rate(voice_ai_calls_total[5m]) * 100',
                'p95_latency': 'histogram_quantile(0.95, rate(voice_ai_response_latency_seconds_bucket[5m]))',
                'avg_latency': 'rate(voice_ai_response_latency_seconds_sum[5m]) / rate(voice_ai_response_latency_seconds_count[5m])',
                'stt_latency': 'histogram_quantile(0.95, rate(stt_request_duration_seconds_bucket[5m]))',
                'llm_latency': 'histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m]))',
                'tts_latency': 'histogram_quantile(0.95, rate(tts_request_duration_seconds_bucket[5m]))',
                'error_rate': 'rate(voice_ai_calls_total{status="error"}[5m]) / rate(voice_ai_calls_total[5m]) * 100',
                'memory_usage': 'process_resident_memory_bytes / 1024 / 1024',
                'cpu_usage': 'rate(process_cpu_seconds_total[5m]) * 100'
            }
            
            for metric_name, query in queries.items():
                try:
                    response = requests.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params={'query': query},
                        timeout=5
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data['status'] == 'success' and data['data']['result']:
                            value = float(data['data']['result'][0]['value'][1])
                            metrics[metric_name] = value
                        else:
                            metrics[metric_name] = 0.0
                    else:
                        metrics[metric_name] = 0.0
                except Exception:
                    metrics[metric_name] = 0.0
                    
        except Exception as e:
            logger.warning(f"Failed to get Prometheus metrics: {e}")
        
        return metrics
    
    async def collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        timestamp = datetime.now(UTC)
        
        # Get health status
        health_data = await self.get_health_status()
        health_status = health_data.get("status", "unknown")
        
        # Get Prometheus metrics
        prom_metrics = await self.get_prometheus_metrics()
        
        # Create metrics object
        metrics = SystemMetrics(
            timestamp=timestamp,
            call_rate=prom_metrics.get('call_rate', 0.0),
            active_calls=int(prom_metrics.get('active_calls', 0)),
            success_rate=prom_metrics.get('success_rate', 0.0),
            avg_latency=prom_metrics.get('avg_latency', 0.0),
            p95_latency=prom_metrics.get('p95_latency', 0.0),
            stt_latency=prom_metrics.get('stt_latency', 0.0),
            llm_latency=prom_metrics.get('llm_latency', 0.0),
            tts_latency=prom_metrics.get('tts_latency', 0.0),
            error_rate=prom_metrics.get('error_rate', 0.0),
            memory_usage_mb=prom_metrics.get('memory_usage', 0.0),
            cpu_usage_percent=prom_metrics.get('cpu_usage', 0.0),
            health_status=health_status
        )
        
        # Check for alerts
        alerts = []
        
        if metrics.p95_latency > self.thresholds['latency_critical']:
            alerts.append(f"CRITICAL: Latency {metrics.p95_latency:.2f}s")
        elif metrics.p95_latency > self.thresholds['latency_warning']:
            alerts.append(f"WARNING: Latency {metrics.p95_latency:.2f}s")
        
        if metrics.error_rate > self.thresholds['error_rate_critical']:
            alerts.append(f"CRITICAL: Error rate {metrics.error_rate:.1f}%")
        elif metrics.error_rate > self.thresholds['error_rate_warning']:
            alerts.append(f"WARNING: Error rate {metrics.error_rate:.1f}%")
        
        if metrics.memory_usage_mb > self.thresholds['memory_critical']:
            alerts.append(f"CRITICAL: Memory {metrics.memory_usage_mb:.0f}MB")
        elif metrics.memory_usage_mb > self.thresholds['memory_warning']:
            alerts.append(f"WARNING: Memory {metrics.memory_usage_mb:.0f}MB")
        
        if metrics.cpu_usage_percent > self.thresholds['cpu_critical']:
            alerts.append(f"CRITICAL: CPU {metrics.cpu_usage_percent:.1f}%")
        elif metrics.cpu_usage_percent > self.thresholds['cpu_warning']:
            alerts.append(f"WARNING: CPU {metrics.cpu_usage_percent:.1f}%")
        
        if health_status != "healthy":
            alerts.append(f"CRITICAL: Health status {health_status}")
        
        metrics.alerts = alerts
        
        # Add to history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)
        
        return metrics
    
    def get_trend(self, metric_name: str, window: int = 10) -> str:
        """Get trend for a metric (↑, ↓, →)."""
        if len(self.metrics_history) < 2:
            return "→"
        
        recent_values = []
        for m in self.metrics_history[-window:]:
            value = getattr(m, metric_name, 0)
            if isinstance(value, (int, float)):
                recent_values.append(value)
        
        if len(recent_values) < 2:
            return "→"
        
        # Simple trend calculation
        first_half = recent_values[:len(recent_values)//2]
        second_half = recent_values[len(recent_values)//2:]
        
        if not first_half or not second_half:
            return "→"
        
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        if avg_second > avg_first * 1.1:
            return "↑"
        elif avg_second < avg_first * 0.9:
            return "↓"
        else:
            return "→"
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human readable format."""
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        else:
            return f"{seconds:.2f}s"
    
    def format_bytes(self, bytes_value: float) -> str:
        """Format bytes in human readable format."""
        if bytes_value < 1024:
            return f"{bytes_value:.0f}MB"
        else:
            return f"{bytes_value/1024:.1f}GB"
    
    def display_console(self, metrics: SystemMetrics):
        """Display metrics in console format."""
        print(f"\n{'='*80}")
        print(f"Voice AI Agent System Monitor - {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'='*80}")
        
        # System Status
        status_color = "🟢" if metrics.health_status == "healthy" else "🔴"
        print(f"System Status: {status_color} {metrics.health_status.upper()}")
        
        # Key Metrics
        print(f"\nKey Metrics:")
        print(f"  Call Rate:      {metrics.call_rate:.2f} calls/sec {self.get_trend('call_rate')}")
        print(f"  Active Calls:   {metrics.active_calls} {self.get_trend('active_calls')}")
        print(f"  Success Rate:   {metrics.success_rate:.1f}% {self.get_trend('success_rate')}")
        print(f"  Avg Latency:    {self.format_duration(metrics.avg_latency)} {self.get_trend('avg_latency')}")
        print(f"  P95 Latency:    {self.format_duration(metrics.p95_latency)} {self.get_trend('p95_latency')}")
        print(f"  Error Rate:     {metrics.error_rate:.1f}% {self.get_trend('error_rate')}")
        
        # AI Service Latencies
        print(f"\nAI Service Latencies (P95):")
        print(f"  STT:            {self.format_duration(metrics.stt_latency)} {self.get_trend('stt_latency')}")
        print(f"  LLM:            {self.format_duration(metrics.llm_latency)} {self.get_trend('llm_latency')}")
        print(f"  TTS:            {self.format_duration(metrics.tts_latency)} {self.get_trend('tts_latency')}")
        
        # System Resources
        print(f"\nSystem Resources:")
        print(f"  Memory Usage:   {self.format_bytes(metrics.memory_usage_mb)} {self.get_trend('memory_usage_mb')}")
        print(f"  CPU Usage:      {metrics.cpu_usage_percent:.1f}% {self.get_trend('cpu_usage_percent')}")
        
        # Alerts
        if metrics.alerts:
            print(f"\n🚨 ALERTS:")
            for alert in metrics.alerts:
                print(f"  {alert}")
        else:
            print(f"\n✅ No active alerts")
        
        # Historical Summary
        if len(self.metrics_history) > 1:
            print(f"\nHistorical Summary (last {len(self.metrics_history)} samples):")
            latencies = [m.p95_latency for m in self.metrics_history if m.p95_latency > 0]
            if latencies:
                print(f"  Latency Min/Max: {min(latencies):.2f}s / {max(latencies):.2f}s")
            
            success_rates = [m.success_rate for m in self.metrics_history if m.success_rate > 0]
            if success_rates:
                print(f"  Success Rate Avg: {statistics.mean(success_rates):.1f}%")
    
    def display_curses(self, stdscr, metrics: SystemMetrics):
        """Display metrics using curses for real-time updates."""
        stdscr.clear()
        
        # Colors
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        
        row = 0
        
        # Title
        title = f"Voice AI Agent Monitor - {metrics.timestamp.strftime('%H:%M:%S')}"
        stdscr.addstr(row, 0, title, curses.A_BOLD)
        row += 2
        
        # System Status
        status_color = curses.color_pair(1) if metrics.health_status == "healthy" else curses.color_pair(3)
        stdscr.addstr(row, 0, f"Status: {metrics.health_status.upper()}", status_color | curses.A_BOLD)
        row += 2
        
        # Key Metrics
        stdscr.addstr(row, 0, "Key Metrics:", curses.A_BOLD)
        row += 1
        
        metrics_data = [
            ("Call Rate", f"{metrics.call_rate:.2f} calls/sec", self.get_trend('call_rate')),
            ("Active Calls", f"{metrics.active_calls}", self.get_trend('active_calls')),
            ("Success Rate", f"{metrics.success_rate:.1f}%", self.get_trend('success_rate')),
            ("Avg Latency", self.format_duration(metrics.avg_latency), self.get_trend('avg_latency')),
            ("P95 Latency", self.format_duration(metrics.p95_latency), self.get_trend('p95_latency')),
            ("Error Rate", f"{metrics.error_rate:.1f}%", self.get_trend('error_rate')),
        ]
        
        for name, value, trend in metrics_data:
            color = curses.color_pair(1)  # Default green
            if "Latency" in name and metrics.p95_latency > self.thresholds['latency_warning']:
                color = curses.color_pair(2) if metrics.p95_latency < self.thresholds['latency_critical'] else curses.color_pair(3)
            elif "Error Rate" in name and metrics.error_rate > self.thresholds['error_rate_warning']:
                color = curses.color_pair(2) if metrics.error_rate < self.thresholds['error_rate_critical'] else curses.color_pair(3)
            
            stdscr.addstr(row, 2, f"{name:15}: {value:15} {trend}", color)
            row += 1
        
        row += 1
        
        # AI Services
        stdscr.addstr(row, 0, "AI Service Latencies (P95):", curses.A_BOLD)
        row += 1
        
        ai_metrics = [
            ("STT", self.format_duration(metrics.stt_latency), self.get_trend('stt_latency')),
            ("LLM", self.format_duration(metrics.llm_latency), self.get_trend('llm_latency')),
            ("TTS", self.format_duration(metrics.tts_latency), self.get_trend('tts_latency')),
        ]
        
        for name, value, trend in ai_metrics:
            stdscr.addstr(row, 2, f"{name:15}: {value:15} {trend}")
            row += 1
        
        row += 1
        
        # System Resources
        stdscr.addstr(row, 0, "System Resources:", curses.A_BOLD)
        row += 1
        
        # Memory
        mem_color = curses.color_pair(1)
        if metrics.memory_usage_mb > self.thresholds['memory_warning']:
            mem_color = curses.color_pair(2) if metrics.memory_usage_mb < self.thresholds['memory_critical'] else curses.color_pair(3)
        stdscr.addstr(row, 2, f"Memory Usage   : {self.format_bytes(metrics.memory_usage_mb):15} {self.get_trend('memory_usage_mb')}", mem_color)
        row += 1
        
        # CPU
        cpu_color = curses.color_pair(1)
        if metrics.cpu_usage_percent > self.thresholds['cpu_warning']:
            cpu_color = curses.color_pair(2) if metrics.cpu_usage_percent < self.thresholds['cpu_critical'] else curses.color_pair(3)
        stdscr.addstr(row, 2, f"CPU Usage      : {metrics.cpu_usage_percent:.1f}%{' ':10} {self.get_trend('cpu_usage_percent')}", cpu_color)
        row += 2
        
        # Alerts
        if metrics.alerts:
            stdscr.addstr(row, 0, "🚨 ALERTS:", curses.color_pair(3) | curses.A_BOLD)
            row += 1
            for alert in metrics.alerts[:5]:  # Show max 5 alerts
                stdscr.addstr(row, 2, alert, curses.color_pair(3))
                row += 1
        else:
            stdscr.addstr(row, 0, "✅ No active alerts", curses.color_pair(1))
            row += 1
        
        row += 1
        
        # Instructions
        stdscr.addstr(row, 0, "Press 'q' to quit, 'r' to refresh", curses.color_pair(4))
        
        stdscr.refresh()
    
    async def run_console_monitor(self, interval: int = 5):
        """Run console-based monitoring."""
        print("Starting Voice AI Agent System Monitor...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                metrics = await self.collect_metrics()
                self.display_console(metrics)
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
    
    async def run_curses_monitor(self, interval: int = 2):
        """Run curses-based real-time monitoring."""
        def curses_main(stdscr):
            stdscr.nodelay(True)  # Non-blocking input
            curses.curs_set(0)    # Hide cursor
            
            async def monitor_loop():
                while True:
                    try:
                        # Check for quit command
                        key = stdscr.getch()
                        if key == ord('q'):
                            return
                        elif key == ord('r'):
                            # Force refresh
                            pass
                        
                        # Collect and display metrics
                        metrics = await self.collect_metrics()
                        self.display_curses(stdscr, metrics)
                        
                        await asyncio.sleep(interval)
                        
                    except KeyboardInterrupt:
                        return
                    except Exception as e:
                        stdscr.addstr(0, 0, f"Error: {str(e)}")
                        stdscr.refresh()
                        await asyncio.sleep(1)
            
            # Run the async monitor loop
            asyncio.run(monitor_loop())
        
        curses.wrapper(curses_main)
    
    async def export_metrics(self, filename: str):
        """Export current metrics to JSON file."""
        metrics = await self.collect_metrics()
        
        export_data = {
            "timestamp": metrics.timestamp.isoformat(),
            "metrics": {
                "call_rate": metrics.call_rate,
                "active_calls": metrics.active_calls,
                "success_rate": metrics.success_rate,
                "avg_latency": metrics.avg_latency,
                "p95_latency": metrics.p95_latency,
                "stt_latency": metrics.stt_latency,
                "llm_latency": metrics.llm_latency,
                "tts_latency": metrics.tts_latency,
                "error_rate": metrics.error_rate,
                "memory_usage_mb": metrics.memory_usage_mb,
                "cpu_usage_percent": metrics.cpu_usage_percent,
                "health_status": metrics.health_status
            },
            "alerts": metrics.alerts,
            "history": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "p95_latency": m.p95_latency,
                    "success_rate": m.success_rate,
                    "error_rate": m.error_rate,
                    "active_calls": m.active_calls
                }
                for m in self.metrics_history[-50:]  # Last 50 samples
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Metrics exported to {filename}")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Voice AI Agent System Monitor")
    parser.add_argument("--mode", choices=["console", "curses", "export"], default="curses",
                       help="Monitoring mode")
    parser.add_argument("--interval", type=int, default=2,
                       help="Update interval in seconds")
    parser.add_argument("--export-file", type=str,
                       help="Export metrics to JSON file")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor()
    
    if args.mode == "console":
        await monitor.run_console_monitor(args.interval)
    elif args.mode == "curses":
        await monitor.run_curses_monitor(args.interval)
    elif args.mode == "export":
        filename = args.export_file or f"metrics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await monitor.export_metrics(filename)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
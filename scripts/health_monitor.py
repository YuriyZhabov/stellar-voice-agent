#!/usr/bin/env python3
"""
Real-time health monitoring script for Voice AI Agent.

This script continuously monitors the health of all system components
and provides detailed reporting on any issues.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class HealthMonitor:
    """Real-time health monitoring for Voice AI Agent."""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.health_history = []
        self.logger = self._setup_logging()
        
        # Alert thresholds
        self.alert_thresholds = {
            "consecutive_failures": 3,
            "health_percentage_threshold": 80.0,
            "response_time_threshold": 5000.0,  # 5 seconds
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for health monitoring."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('health_monitor.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        try:
            from src.health import comprehensive_health_check_async
            
            start_time = time.time()
            health_data = await comprehensive_health_check_async()
            health_data['check_duration'] = time.time() - start_time
            
            return health_data
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
                "check_duration": 0.0
            }
    
    def analyze_health_trends(self) -> Dict[str, Any]:
        """Analyze health trends from history."""
        if len(self.health_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent_checks = self.health_history[-10:]  # Last 10 checks
        
        # Calculate health percentage trend
        health_percentages = [
            check.get("health_percentage", 0) 
            for check in recent_checks 
            if "health_percentage" in check
        ]
        
        if len(health_percentages) >= 2:
            trend = (
                "improving" if health_percentages[-1] > health_percentages[0] 
                else "declining" if health_percentages[-1] < health_percentages[0] 
                else "stable"
            )
        else:
            trend = "stable"
        
        # Check for consecutive failures
        consecutive_failures = 0
        for check in reversed(recent_checks):
            if check.get("status") in ["degraded", "unhealthy"]:
                consecutive_failures += 1
            else:
                break
        
        # Calculate average response times
        response_times = [
            check.get("response_time_ms", 0) 
            for check in recent_checks 
            if "response_time_ms" in check
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "trend": trend,
            "consecutive_failures": consecutive_failures,
            "average_response_time": avg_response_time,
            "health_percentage_trend": health_percentages[-5:] if len(health_percentages) >= 5 else health_percentages,
            "current_health_percentage": health_percentages[-1] if health_percentages else 0
        }
    
    def generate_alerts(self, current_health: Dict[str, Any], trends: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on health status and trends."""
        alerts = []
        
        # Critical system failures
        if current_health.get("status") == "unhealthy":
            alerts.append({
                "level": "critical",
                "message": f"System is unhealthy: {current_health.get('error', 'Unknown error')}",
                "timestamp": datetime.now().isoformat(),
                "component": "system"
            })
        
        # Consecutive failures
        consecutive_failures = trends.get("consecutive_failures", 0)
        if consecutive_failures >= self.alert_thresholds["consecutive_failures"]:
            alerts.append({
                "level": "warning",
                "message": f"System has been degraded for {consecutive_failures} consecutive checks",
                "timestamp": datetime.now().isoformat(),
                "component": "system"
            })
        
        # Low health percentage
        health_percentage = trends.get("current_health_percentage", 100)
        if health_percentage < self.alert_thresholds["health_percentage_threshold"]:
            alerts.append({
                "level": "warning",
                "message": f"System health is low: {health_percentage:.1f}%",
                "timestamp": datetime.now().isoformat(),
                "component": "system"
            })
        
        # High response times
        avg_response_time = trends.get("average_response_time", 0)
        if avg_response_time > self.alert_thresholds["response_time_threshold"]:
            alerts.append({
                "level": "warning",
                "message": f"Average response time is high: {avg_response_time:.1f}ms",
                "timestamp": datetime.now().isoformat(),
                "component": "performance"
            })
        
        # Individual component failures
        checks = current_health.get("checks", {})
        for component, status in checks.items():
            if "failed" in str(status):
                alerts.append({
                    "level": "error",
                    "message": f"Component {component} is failing: {status}",
                    "timestamp": datetime.now().isoformat(),
                    "component": component
                })
            elif "not_configured" in str(status):
                alerts.append({
                    "level": "warning",
                    "message": f"Component {component} is not configured: {status}",
                    "timestamp": datetime.now().isoformat(),
                    "component": component
                })
        
        return alerts
    
    def print_health_status(self, health_data: Dict[str, Any], trends: Dict[str, Any], alerts: List[Dict[str, Any]]):
        """Print formatted health status."""
        print("\n" + "=" * 80)
        print(f"🏥 Voice AI Agent Health Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Overall status
        status = health_data.get("status", "unknown")
        status_emoji = "🟢" if status == "healthy" else "🟡" if status == "degraded" else "🔴"
        print(f"\n{status_emoji} Overall Status: {status.upper()}")
        
        health_percentage = health_data.get("health_percentage", 0)
        print(f"📊 Health: {health_percentage:.1f}%")
        
        response_time = health_data.get("response_time_ms", 0)
        print(f"⏱️  Response Time: {response_time:.1f}ms")
        
        # Component status
        print(f"\n📋 Component Status:")
        checks = health_data.get("checks", {})
        
        # Group components by category
        ai_services = ["deepgram", "openai", "cartesia", "livekit"]
        infrastructure = ["database", "redis"]
        system = ["python_version", "basic_imports", "project_structure", "environment", "config", "disk_space", "memory"]
        
        def print_component_group(title: str, components: List[str]):
            print(f"\n  {title}:")
            for component in components:
                if component in checks:
                    status = checks[component]
                    status_emoji = "✅" if str(status).startswith("ok") else "⚠️" if "warning" in str(status) or "configured" in str(status) else "❌"
                    print(f"    {status_emoji} {component}: {status}")
        
        print_component_group("🤖 AI Services", ai_services)
        print_component_group("🏗️  Infrastructure", infrastructure)
        print_component_group("⚙️  System", system)
        
        # Trends
        print(f"\n📈 Trends:")
        print(f"  Health Trend: {trends.get('trend', 'unknown')}")
        print(f"  Consecutive Issues: {trends.get('consecutive_failures', 0)}")
        print(f"  Avg Response Time: {trends.get('average_response_time', 0):.1f}ms")
        
        # Alerts
        if alerts:
            print(f"\n🚨 Active Alerts:")
            for alert in alerts:
                alert_emoji = "🔴" if alert["level"] == "critical" else "🟡" if alert["level"] == "warning" else "🟠"
                print(f"  {alert_emoji} {alert['level'].upper()}: {alert['message']}")
        else:
            print(f"\n✅ No active alerts")
        
        print("\n" + "=" * 80)
    
    async def run_continuous_monitoring(self, duration_minutes: Optional[int] = None):
        """Run continuous health monitoring."""
        print(f"🚀 Starting continuous health monitoring (interval: {self.check_interval}s)")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes) if duration_minutes else None
        
        try:
            while True:
                # Check if we should stop (duration-based)
                if end_time and datetime.now() >= end_time:
                    break
                
                # Perform health check
                health_data = await self.check_system_health()
                
                # Add to history
                self.health_history.append(health_data)
                
                # Keep only last 100 entries
                if len(self.health_history) > 100:
                    self.health_history = self.health_history[-100:]
                
                # Analyze trends
                trends = self.analyze_health_trends()
                
                # Generate alerts
                alerts = self.generate_alerts(health_data, trends)
                
                # Print status
                self.print_health_status(health_data, trends, alerts)
                
                # Log critical alerts
                for alert in alerts:
                    if alert["level"] == "critical":
                        self.logger.critical(f"{alert['component']}: {alert['message']}")
                    elif alert["level"] == "error":
                        self.logger.error(f"{alert['component']}: {alert['message']}")
                    elif alert["level"] == "warning":
                        self.logger.warning(f"{alert['component']}: {alert['message']}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            print(f"❌ Monitoring error: {e}")
    
    async def run_single_check(self) -> Dict[str, Any]:
        """Run a single health check and return results."""
        health_data = await self.check_system_health()
        trends = {"trend": "single_check", "consecutive_failures": 0, "average_response_time": 0, "current_health_percentage": health_data.get("health_percentage", 0)}
        alerts = self.generate_alerts(health_data, trends)
        
        return {
            "health": health_data,
            "trends": trends,
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }


async def main():
    """Main monitoring function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Voice AI Agent health")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--duration", "-d", type=int, help="Duration in minutes (default: continuous)")
    parser.add_argument("--single", "-s", action="store_true", help="Run single check and exit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    monitor = HealthMonitor(check_interval=args.interval)
    
    if args.single:
        # Single check
        result = await monitor.run_single_check()
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            health_data = result["health"]
            trends = result["trends"]
            alerts = result["alerts"]
            monitor.print_health_status(health_data, trends, alerts)
        
        # Exit with appropriate code
        status = result["health"].get("status", "unknown")
        if status == "unhealthy":
            sys.exit(1)
        elif status == "degraded":
            sys.exit(2)
        else:
            sys.exit(0)
    else:
        # Continuous monitoring
        await monitor.run_continuous_monitoring(args.duration)


if __name__ == "__main__":
    asyncio.run(main())
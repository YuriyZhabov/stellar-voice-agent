#!/usr/bin/env python3
"""
Automated deployment health verification script.

This script continuously monitors the deployment health and provides
real-time feedback on system status.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DeploymentHealthMonitor:
    """Continuous deployment health monitoring."""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.health_history = []
        self.alert_thresholds = {
            "consecutive_failures": 3,
            "response_time_threshold": 5.0,
            "memory_threshold_gb": 2.0,
            "cpu_threshold_percent": 90.0
        }
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for health monitoring."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('deployment_health.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    async def check_service_health(self, service_name: str, url: str, timeout: int = 10) -> Dict[str, Any]:
        """Check health of a specific service."""
        start_time = time.time()
        
        try:
            response = requests.get(url, timeout=timeout)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                # For voice-ai-agent, parse the health response
                if service_name == "voice-ai-agent":
                    try:
                        health_data = response.json()
                        health_percentage = health_data.get("health_percentage", 0)
                        status = health_data.get("status", "unknown")
                        
                        # Accept both healthy and degraded (if >75%) as healthy
                        if status == "healthy" or (status == "degraded" and health_percentage >= 75.0):
                            return {
                                "service": service_name,
                                "status": "healthy",
                                "response_time": response_time,
                                "status_code": response.status_code,
                                "health_percentage": health_percentage,
                                "timestamp": datetime.now().isoformat()
                            }
                        else:
                            return {
                                "service": service_name,
                                "status": "degraded",
                                "response_time": response_time,
                                "status_code": response.status_code,
                                "health_percentage": health_percentage,
                                "error": f"Health status: {status}",
                                "timestamp": datetime.now().isoformat()
                            }
                    except json.JSONDecodeError:
                        pass  # Fall through to default handling
                
                return {
                    "service": service_name,
                    "status": "healthy",
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "service": service_name,
                    "status": "unhealthy",
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except requests.exceptions.Timeout:
            return {
                "service": service_name,
                "status": "timeout",
                "response_time": timeout,
                "error": "Request timeout",
                "timestamp": datetime.now().isoformat()
            }
        except requests.exceptions.ConnectionError:
            return {
                "service": service_name,
                "status": "unreachable",
                "response_time": time.time() - start_time,
                "error": "Connection error",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "response_time": time.time() - start_time,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all services."""
        services = {
            "voice-ai-agent": "http://localhost:8000/health",
            "prometheus": "http://localhost:9091/-/healthy",
            "grafana": "http://localhost:3000/api/health",
            "loki": "http://localhost:3100/ready"
        }
        
        health_checks = []
        for service_name, url in services.items():
            health_check = await self.check_service_health(service_name, url)
            health_checks.append(health_check)
        
        # Calculate overall health
        healthy_services = sum(1 for check in health_checks if check["status"] == "healthy")
        total_services = len(health_checks)
        
        # For voice-ai-agent, also consider degraded with >75% health as acceptable
        voice_ai_check = next((check for check in health_checks if check["service"] == "voice-ai-agent"), None)
        if voice_ai_check and voice_ai_check["status"] == "degraded":
            health_percentage = voice_ai_check.get("health_percentage", 0)
            if health_percentage >= 75.0:
                healthy_services += 1  # Count as healthy if >75%
        
        overall_status = "healthy" if healthy_services == total_services else "degraded" if healthy_services > 0 else "critical"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "healthy_services": healthy_services,
            "total_services": total_services,
            "services": health_checks,
            "health_percentage": (healthy_services / total_services) * 100
        }
    
    async def get_application_metrics(self) -> Dict[str, Any]:
        """Get detailed application metrics."""
        try:
            # Try to get application health details from HTTP endpoint first
            try:
                response = requests.get("http://localhost:8000/health", timeout=10)
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Extract key metrics
                    metrics = {
                        "status": health_data.get("status", "unknown"),
                        "response_time_ms": health_data.get("response_time_ms", 0),
                        "health_percentage": health_data.get("health_percentage", 0),
                        "checks": health_data.get("checks", {}),
                        "python_version": health_data.get("python_version", "unknown"),
                        "environment": health_data.get("environment", "unknown")
                    }
                    
                    return metrics
                else:
                    # If HTTP endpoint fails, try direct health check
                    return await self._get_direct_health_metrics()
            except requests.RequestException:
                # If HTTP request fails, try direct health check
                return await self._get_direct_health_metrics()
                
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_direct_health_metrics(self) -> Dict[str, Any]:
        """Get health metrics directly using comprehensive_health_check_async."""
        try:
            # Import and run comprehensive health check directly
            import sys
            from pathlib import Path
            
            # Add project root to path
            project_root = Path(__file__).parent.parent
            sys.path.insert(0, str(project_root))
            
            from src.health import comprehensive_health_check_async
            
            health_data = await comprehensive_health_check_async()
            
            # Extract key metrics
            metrics = {
                "status": health_data.get("status", "unknown"),
                "response_time_ms": health_data.get("response_time_ms", 0),
                "health_percentage": health_data.get("health_percentage", 0),
                "checks": health_data.get("checks", {}),
                "python_version": health_data.get("python_version", "unknown"),
                "environment": health_data.get("environment", "unknown"),
                "source": "direct_check"
            }
            
            return metrics
            
        except Exception as e:
            return {"error": f"Direct health check failed: {e}"}
    
    async def check_resource_usage(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            # Get metrics from Prometheus if available
            response = requests.get("http://localhost:9091/api/v1/query", params={
                "query": "process_resident_memory_bytes"
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    memory_bytes = float(data["data"]["result"][0]["value"][1])
                    memory_gb = memory_bytes / (1024 ** 3)
                    
                    return {
                        "memory_gb": round(memory_gb, 2),
                        "memory_status": "normal" if memory_gb < self.alert_thresholds["memory_threshold_gb"] else "high"
                    }
            
            return {"error": "Unable to fetch resource metrics"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_health_trends(self) -> Dict[str, Any]:
        """Analyze health trends from history."""
        if len(self.health_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent_checks = self.health_history[-10:]  # Last 10 checks
        
        # Calculate health percentage trend
        health_percentages = [check["health_percentage"] for check in recent_checks]
        
        if len(health_percentages) >= 2:
            trend = "improving" if health_percentages[-1] > health_percentages[0] else "declining" if health_percentages[-1] < health_percentages[0] else "stable"
        else:
            trend = "stable"
        
        # Check for consecutive failures
        consecutive_failures = 0
        for check in reversed(recent_checks):
            if check["overall_status"] in ["degraded", "critical"]:
                consecutive_failures += 1
            else:
                break
        
        # Calculate average response times
        response_times = []
        for check in recent_checks:
            for service in check.get("services", []):
                if "response_time" in service:
                    response_times.append(service["response_time"])
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "trend": trend,
            "consecutive_failures": consecutive_failures,
            "average_response_time": round(avg_response_time, 3),
            "health_percentage_trend": health_percentages[-5:] if len(health_percentages) >= 5 else health_percentages
        }
    
    def generate_alerts(self, current_health: Dict[str, Any], trends: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on health status and trends."""
        alerts = []
        
        # Critical service failures
        if current_health["overall_status"] == "critical":
            alerts.append({
                "level": "critical",
                "message": "All services are down or unreachable",
                "timestamp": datetime.now().isoformat()
            })
        
        # Consecutive failures
        consecutive_failures = trends.get("consecutive_failures", 0)
        if consecutive_failures >= self.alert_thresholds["consecutive_failures"]:
            alerts.append({
                "level": "warning",
                "message": f"System has been degraded for {consecutive_failures} consecutive checks",
                "timestamp": datetime.now().isoformat()
            })
        
        # High response times
        if trends["average_response_time"] > self.alert_thresholds["response_time_threshold"]:
            alerts.append({
                "level": "warning",
                "message": f"Average response time is high: {trends['average_response_time']}s",
                "timestamp": datetime.now().isoformat()
            })
        
        # Individual service failures
        for service in current_health.get("services", []):
            if service["status"] != "healthy":
                alerts.append({
                    "level": "warning",
                    "message": f"Service {service['service']} is {service['status']}: {service.get('error', 'Unknown error')}",
                    "timestamp": datetime.now().isoformat()
                })
        
        return alerts
    
    def print_health_status(self, health_data: Dict[str, Any], metrics: Dict[str, Any], trends: Dict[str, Any], alerts: List[Dict[str, Any]]):
        """Print formatted health status."""
        print("\n" + "=" * 80)
        print(f"🏥 Voice AI Agent Health Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Overall status
        status_emoji = "🟢" if health_data["overall_status"] == "healthy" else "🟡" if health_data["overall_status"] == "degraded" else "🔴"
        print(f"\n{status_emoji} Overall Status: {health_data['overall_status'].upper()}")
        print(f"📊 Health: {health_data['health_percentage']:.1f}% ({health_data['healthy_services']}/{health_data['total_services']} services)")
        
        # Service status
        print(f"\n📋 Service Status:")
        for service in health_data["services"]:
            status_emoji = "✅" if service["status"] == "healthy" else "⚠️" if service["status"] in ["timeout", "degraded"] else "❌"
            response_time = f" ({service['response_time']:.3f}s)" if "response_time" in service else ""
            print(f"  {status_emoji} {service['service']}: {service['status']}{response_time}")
        
        # Application metrics
        if "error" not in metrics:
            print(f"\n🔧 Application Metrics:")
            print(f"  Status: {metrics.get('status', 'unknown')}")
            print(f"  Environment: {metrics.get('environment', 'unknown')}")
            print(f"  Response Time: {metrics.get('response_time_ms', 0)}ms")
        
        # Trends
        print(f"\n📈 Trends:")
        print(f"  Health Trend: {trends['trend']}")
        print(f"  Consecutive Issues: {trends['consecutive_failures']}")
        print(f"  Avg Response Time: {trends['average_response_time']}s")
        
        # Alerts
        if alerts:
            print(f"\n🚨 Active Alerts:")
            for alert in alerts:
                alert_emoji = "🔴" if alert["level"] == "critical" else "🟡"
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
                
                # Perform health checks
                health_data = await self.check_all_services()
                metrics = await self.get_application_metrics()
                
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
                self.print_health_status(health_data, metrics, trends, alerts)
                
                # Log critical alerts
                for alert in alerts:
                    if alert["level"] == "critical":
                        self.logger.critical(alert["message"])
                    elif alert["level"] == "warning":
                        self.logger.warning(alert["message"])
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            print(f"❌ Monitoring error: {e}")
    
    async def run_single_check(self) -> Dict[str, Any]:
        """Run a single health check and return results."""
        health_data = await self.check_all_services()
        metrics = await self.get_application_metrics()
        
        return {
            "health": health_data,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }


async def main():
    """Main monitoring function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Voice AI Agent deployment health")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--duration", "-d", type=int, help="Duration in minutes (default: continuous)")
    parser.add_argument("--single", "-s", action="store_true", help="Run single check and exit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    monitor = DeploymentHealthMonitor(check_interval=args.interval)
    
    if args.single:
        # Single check
        result = await monitor.run_single_check()
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            health_data = result["health"]
            metrics = result["metrics"]
            trends = {"trend": "single_check", "consecutive_failures": 0, "average_response_time": 0}
            alerts = monitor.generate_alerts(health_data, trends)
            monitor.print_health_status(health_data, metrics, trends, alerts)
        
        # Exit with appropriate code
        if result["health"]["overall_status"] == "critical":
            sys.exit(1)
        elif result["health"]["overall_status"] == "degraded":
            sys.exit(2)
        else:
            sys.exit(0)
    else:
        # Continuous monitoring
        await monitor.run_continuous_monitoring(args.duration)


if __name__ == "__main__":
    asyncio.run(main())
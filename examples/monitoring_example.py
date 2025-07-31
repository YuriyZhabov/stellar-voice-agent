#!/usr/bin/env python3
"""
Example demonstrating the Voice AI Agent monitoring system.

This example shows how to:
1. Set up health monitoring for components
2. Configure alerting with multiple channels
3. Export metrics to different destinations
4. Create and use dashboards
"""

import asyncio
import logging
import time
from datetime import datetime, UTC

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import monitoring components
from src.monitoring.health_monitor import HealthMonitor, ComponentType, HealthThreshold
from src.monitoring.alerting import AlertManager, AlertRule, AlertSeverity, WebhookChannel, LogChannel
from src.monitoring.metrics_exporter import MetricsExportManager, PrometheusExporter, JSONExporter
from src.monitoring.dashboard import DashboardManager


class MockService:
    """Mock service for demonstration."""
    
    def __init__(self, name: str, failure_rate: float = 0.0):
        self.name = name
        self.failure_rate = failure_rate
        self.call_count = 0
        self.is_healthy = True
    
    async def health_check(self):
        """Mock health check."""
        self.call_count += 1
        
        # Simulate occasional failures
        import random
        if random.random() < self.failure_rate:
            return {
                "status": "unhealthy",
                "success_rate": 50.0,
                "error_rate": 50.0,
                "details": {"error": "Simulated failure"}
            }
        
        return {
            "status": "healthy",
            "success_rate": 95.0,
            "error_rate": 5.0,
            "details": {"calls": self.call_count}
        }
    
    def set_healthy(self, healthy: bool):
        """Set service health status."""
        self.is_healthy = healthy


async def main():
    """Main demonstration function."""
    print("🚀 Voice AI Agent Monitoring System Demo")
    print("=" * 50)
    
    # Create mock services
    stt_service = MockService("STT Service", failure_rate=0.1)
    llm_service = MockService("LLM Service", failure_rate=0.05)
    tts_service = MockService("TTS Service", failure_rate=0.15)
    
    # 1. Setup Health Monitor
    print("\n📊 Setting up Health Monitor...")
    health_monitor = HealthMonitor(
        check_interval=5.0,  # Check every 5 seconds
        enable_auto_checks=True
    )
    
    # Register components with custom thresholds
    custom_threshold = HealthThreshold(
        response_time_ms=2000.0,
        success_rate_percent=85.0,
        error_rate_percent=15.0
    )
    
    health_monitor.register_component(
        "stt_service",
        ComponentType.STT_CLIENT,
        stt_service.health_check,
        threshold=custom_threshold
    )
    
    health_monitor.register_component(
        "llm_service",
        ComponentType.LLM_CLIENT,
        llm_service.health_check
    )
    
    health_monitor.register_component(
        "tts_service",
        ComponentType.TTS_CLIENT,
        tts_service.health_check
    )
    
    print("✅ Health monitor configured with 3 components")
    
    # 2. Setup Alert Manager
    print("\n🚨 Setting up Alert Manager...")
    alert_manager = AlertManager(check_interval=10.0)
    
    # Add notification channels
    log_channel = LogChannel(log_level="WARNING")
    alert_manager.add_channel("log", log_channel)
    
    # Add custom alert rule
    custom_rule = AlertRule(
        name="service_degraded",
        condition=lambda health: (
            hasattr(health, 'success_rate') and 
            health.success_rate < 90.0
        ),
        severity=AlertSeverity.MEDIUM,
        message_template="Service {component_name} is degraded (success rate: {success_rate}%)",
        cooldown_minutes=2
    )
    alert_manager.add_rule(custom_rule)
    
    print("✅ Alert manager configured with log channel")
    
    # 3. Setup Metrics Exporter
    print("\n📈 Setting up Metrics Exporter...")
    metrics_exporter = MetricsExportManager(export_interval=15.0)
    
    # Add JSON file exporter
    json_exporter = JSONExporter(file_path="./monitoring_demo_metrics.json")
    metrics_exporter.add_exporter("json", json_exporter)
    
    print("✅ Metrics exporter configured with JSON output")
    
    # 4. Setup Dashboard Manager
    print("\n📋 Setting up Dashboard Manager...")
    dashboard_manager = DashboardManager(
        health_monitor=health_monitor,
        alert_manager=alert_manager,
        update_interval=10.0
    )
    
    print("✅ Dashboard manager configured")
    
    # 5. Start all monitoring services
    print("\n🔄 Starting monitoring services...")
    await health_monitor.start_monitoring()
    await alert_manager.start_monitoring()
    await metrics_exporter.start_exporting()
    await dashboard_manager.start_updating()
    
    print("✅ All monitoring services started")
    
    # 6. Demonstrate monitoring in action
    print("\n🎭 Demonstrating monitoring system...")
    
    try:
        for i in range(30):  # Run for 30 iterations
            print(f"\n--- Iteration {i+1} ---")
            
            # Get system health
            system_health = health_monitor.get_system_health()
            if system_health:
                print(f"System Health: {system_health.status.value} "
                      f"({system_health.health_percentage:.1f}%)")
                
                # Show component details
                for name, component in system_health.components.items():
                    status_emoji = "✅" if component.status.value == "healthy" else "⚠️" if component.status.value == "degraded" else "❌"
                    print(f"  {status_emoji} {name}: {component.status.value} "
                          f"(response: {component.response_time_ms:.1f}ms, "
                          f"success: {component.success_rate:.1f}%)")
            
            # Check for active alerts
            active_alerts = alert_manager.get_active_alerts()
            if active_alerts:
                print(f"🚨 Active Alerts: {len(active_alerts)}")
                for alert in active_alerts[:3]:  # Show first 3
                    print(f"  - {alert.severity.value.upper()}: {alert.message}")
            else:
                print("✅ No active alerts")
            
            # Simulate service issues occasionally
            if i == 10:
                print("🔧 Simulating STT service degradation...")
                stt_service.failure_rate = 0.5
            elif i == 15:
                print("🔧 Simulating LLM service failure...")
                llm_service.failure_rate = 1.0
            elif i == 20:
                print("🔧 Restoring all services...")
                stt_service.failure_rate = 0.1
                llm_service.failure_rate = 0.05
                tts_service.failure_rate = 0.15
            
            # Wait before next iteration
            await asyncio.sleep(2)
        
        # 7. Demonstrate dashboard export
        print("\n📊 Exporting dashboard data...")
        
        # Export system overview dashboard
        dashboard_data = await dashboard_manager.export_dashboard_data("system_overview")
        print(f"System Overview Dashboard: {len(dashboard_data['panels'])} panels")
        
        # Show some metrics
        for panel in dashboard_data['panels'][:2]:  # Show first 2 panels
            print(f"  Panel: {panel['title']} ({len(panel['metrics'])} metrics)")
            for metric in panel['metrics'][:3]:  # Show first 3 metrics
                print(f"    - {metric['name']}: {metric['value']} {metric['unit']}")
        
        # 8. Show alert summary
        print("\n📋 Alert Summary:")
        alert_summary = alert_manager.get_alert_summary()
        print(f"  Total Active: {alert_summary['total_active']}")
        print(f"  Total Resolved: {alert_summary['total_resolved']}")
        print(f"  By Severity: {alert_summary['active_by_severity']}")
        
        # 9. Show health trends
        print("\n📈 Health Trends:")
        for component_name in ["stt_service", "llm_service", "tts_service"]:
            trend = health_monitor.get_component_health_trend(component_name, hours=1)
            if "error" not in trend:
                print(f"  {component_name}: {trend['availability_percentage']:.1f}% availability "
                      f"({trend['total_checks']} checks)")
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    
    finally:
        # 10. Cleanup
        print("\n🧹 Cleaning up...")
        await dashboard_manager.stop_updating()
        await metrics_exporter.stop_exporting()
        await alert_manager.stop_monitoring()
        await health_monitor.stop_monitoring()
        
        # Close exporters
        await metrics_exporter.close()
        await alert_manager.close()
        
        print("✅ Cleanup completed")
    
    print("\n🎉 Monitoring system demo completed!")
    print("\nGenerated files:")
    print("  - monitoring_demo_metrics.json (metrics export)")
    print("\nCheck the logs for alert notifications!")


if __name__ == "__main__":
    asyncio.run(main())
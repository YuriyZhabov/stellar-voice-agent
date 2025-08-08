"""Example usage of Prometheus monitoring dashboard and alerts."""

import asyncio
import json
import logging
from datetime import datetime, UTC

from src.monitoring.prometheus_dashboard import PrometheusMonitoringDashboard
from src.monitoring.health_monitor import HealthMonitor
from src.monitoring.alerting import AlertManager, WebhookChannel, LogChannel


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Demonstrate Prometheus monitoring dashboard functionality."""
    
    logger.info("Starting Prometheus monitoring dashboard example")
    
    # Initialize components
    health_monitor = HealthMonitor(enable_auto_checks=False)
    alert_manager = AlertManager()
    
    # Add alert channels
    alert_manager.add_channel("log", LogChannel(log_level="INFO"))
    
    # Optionally add webhook channel (uncomment if you have a webhook endpoint)
    # alert_manager.add_channel("webhook", WebhookChannel("http://localhost:8080/webhook"))
    
    # Create Prometheus monitoring dashboard
    dashboard = PrometheusMonitoringDashboard(
        prometheus_url="http://localhost:9091",
        health_monitor=health_monitor,
        alert_manager=alert_manager,
        update_interval=15.0
    )
    
    try:
        logger.info("Starting monitoring services...")
        
        # Start alert manager monitoring
        await alert_manager.start_monitoring()
        
        # Start health monitoring
        await health_monitor.start_monitoring()
        
        # Start Prometheus dashboard monitoring
        await dashboard.start_monitoring()
        
        logger.info("All monitoring services started successfully")
        
        # Demonstrate dashboard functionality
        await demonstrate_dashboard_features(dashboard, alert_manager)
        
        # Keep running for a while to see monitoring in action
        logger.info("Monitoring for 2 minutes... Press Ctrl+C to stop")
        await asyncio.sleep(120)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Cleanup
        logger.info("Stopping monitoring services...")
        await dashboard.stop_monitoring()
        await health_monitor.stop_monitoring()
        await alert_manager.stop_monitoring()
        await dashboard.close()
        logger.info("Shutdown complete")


async def demonstrate_dashboard_features(dashboard: PrometheusMonitoringDashboard, alert_manager: AlertManager):
    """Demonstrate various dashboard features."""
    
    logger.info("=== Prometheus Dashboard Features Demo ===")
    
    # 1. Check Prometheus health
    logger.info("1. Checking Prometheus health...")
    health = await dashboard.check_prometheus_health()
    logger.info(f"Prometheus health: {health.status.value} (Response time: {health.response_time_ms:.1f}ms)")
    if health.error_message:
        logger.warning(f"Health check error: {health.error_message}")
    
    # 2. Get scrape targets status
    logger.info("2. Getting scrape targets status...")
    targets_status = await dashboard.get_scrape_targets_status()
    if "error" not in targets_status:
        logger.info(f"Scrape targets: {targets_status['healthy_targets']}/{targets_status['total_targets']} healthy ({targets_status['health_percentage']:.1f}%)")
        for target in targets_status['targets']:
            logger.info(f"  - {target['job']} ({target['instance']}): {target['status']}")
    else:
        logger.error(f"Failed to get scrape targets: {targets_status['error']}")
    
    # 3. Update dashboard panels
    logger.info("3. Updating dashboard panels...")
    updated_metrics = await dashboard.update_all_panels()
    logger.info(f"Updated {len(updated_metrics)} dashboard panels")
    
    for panel_id, metric in updated_metrics.items():
        panel = dashboard.panels[panel_id]
        logger.info(f"  - {panel.title}: {metric.value} {panel.unit}")
    
    # 4. Test Prometheus queries
    logger.info("4. Testing Prometheus queries...")
    test_queries = [
        ("up", "Service availability"),
        ("prometheus_config_last_reload_successful", "Config reload status"),
        ("rate(prometheus_http_requests_total[5m])", "HTTP request rate"),
        ("prometheus_tsdb_head_series", "Time series count")
    ]
    
    for query, description in test_queries:
        result = await dashboard.query_prometheus(query)
        if result.get("status") == "success":
            data = result.get("data", {})
            results = data.get("result", [])
            logger.info(f"  - {description}: {len(results)} results")
        else:
            logger.warning(f"  - {description}: Query failed - {result.get('error', 'Unknown error')}")
    
    # 5. Evaluate Prometheus alerts
    logger.info("5. Evaluating Prometheus alerts...")
    await dashboard.evaluate_prometheus_alerts()
    
    active_alerts = alert_manager.get_active_alerts()
    if active_alerts:
        logger.info(f"Active alerts: {len(active_alerts)}")
        for alert in active_alerts:
            logger.info(f"  - {alert.name} ({alert.severity.value}): {alert.message}")
    else:
        logger.info("No active alerts")
    
    # 6. Get dashboard data
    logger.info("6. Getting complete dashboard data...")
    dashboard_data = dashboard.get_dashboard_data()
    
    logger.info(f"Dashboard: {dashboard_data['title']}")
    logger.info(f"Last update: {dashboard_data['last_update']}")
    logger.info(f"Panels: {dashboard_data['summary']['updated_panels']}/{dashboard_data['summary']['total_panels']} updated")
    logger.info(f"Monitoring active: {dashboard_data['summary']['monitoring_active']}")
    
    # 7. Show panel details
    logger.info("7. Panel details:")
    for panel_id, panel_data in dashboard_data['panels'].items():
        if panel_data['current_value'] is not None:
            logger.info(f"  - {panel_data['title']}: {panel_data['current_value']} {panel_data['unit']}")
            
            # Check thresholds
            thresholds = panel_data.get('thresholds', {})
            current_value = panel_data['current_value']
            
            if 'critical' in thresholds and current_value <= thresholds['critical']:
                logger.warning(f"    ⚠️  CRITICAL threshold exceeded!")
            elif 'warning' in thresholds and current_value <= thresholds['warning']:
                logger.warning(f"    ⚠️  WARNING threshold exceeded!")
    
    # 8. Demonstrate alert summary
    logger.info("8. Alert summary:")
    alert_summary = alert_manager.get_alert_summary()
    logger.info(f"  - Total active alerts: {alert_summary['total_active']}")
    logger.info(f"  - Total resolved alerts: {alert_summary['total_resolved']}")
    logger.info(f"  - Alert rules enabled: {alert_summary['rules_enabled']}")
    logger.info(f"  - Notification channels: {alert_summary['channels_configured']}")
    
    for severity, count in alert_summary['active_by_severity'].items():
        if count > 0:
            logger.info(f"  - {severity.upper()} alerts: {count}")
    
    logger.info("=== Demo Complete ===")


async def test_prometheus_connectivity():
    """Test basic Prometheus connectivity."""
    
    logger.info("Testing Prometheus connectivity...")
    
    dashboard = PrometheusMonitoringDashboard(prometheus_url="http://localhost:9091")
    
    try:
        # Test basic query
        result = await dashboard.query_prometheus("up")
        
        if result.get("status") == "success":
            logger.info("✅ Prometheus is accessible and responding to queries")
            
            data = result.get("data", {})
            results = data.get("result", [])
            logger.info(f"Found {len(results)} metrics")
            
            # Show some sample metrics
            for i, metric_result in enumerate(results[:5]):
                labels = metric_result.get("metric", {})
                value = metric_result.get("value", [None, "0"])[1]
                job = labels.get("job", "unknown")
                instance = labels.get("instance", "unknown")
                logger.info(f"  {i+1}. {job} ({instance}): {value}")
                
        else:
            logger.error(f"❌ Prometheus query failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"❌ Failed to connect to Prometheus: {e}")
    finally:
        await dashboard.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Just test connectivity
        asyncio.run(test_prometheus_connectivity())
    else:
        # Run full demo
        asyncio.run(main())
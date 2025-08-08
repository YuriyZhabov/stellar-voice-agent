"""
LiveKit System Monitoring Example

Demonstrates how to use the LiveKit monitoring and diagnostics system.
"""

import asyncio
import logging
from datetime import datetime, UTC

from src.monitoring.livekit_system_monitor import (
    LiveKitSystemMonitor,
    initialize_monitor,
    start_global_monitoring,
    stop_global_monitoring,
    get_monitor
)
from src.monitoring.livekit_alerting import (
    LiveKitAlertManager,
    get_alert_manager,
    initialize_default_alert_rules,
    EmailChannel,
    WebhookChannel,
    SlackChannel,
    AlertLevel
)
from src.monitoring.livekit_logging import (
    get_logger,
    setup_logging,
    operation_context,
    LiveKitErrorCode
)
from src.monitoring.health_endpoints import health_router
from src.clients.livekit_api_client import get_api_client
from src.auth.livekit_auth import get_auth_manager


# Set up logging
setup_logging(level=logging.INFO)
logger = get_logger("monitoring_example")


async def basic_monitoring_example():
    """Basic monitoring system usage example."""
    
    logger.info("Starting basic monitoring example")
    
    try:
        # Get API client and auth manager
        api_client = get_api_client()
        auth_manager = get_auth_manager()
        
        # Initialize monitor
        monitor = initialize_monitor(
            api_client=api_client,
            auth_manager=auth_manager,
            check_interval=30,  # Check every 30 seconds
            metrics_retention_hours=24
        )
        
        # Add alert callback
        def alert_callback(alert):
            print(f"🚨 ALERT: [{alert.level.value.upper()}] {alert.service}: {alert.message}")
        
        monitor.add_alert_callback(alert_callback)
        
        # Start monitoring
        await start_global_monitoring()
        
        # Run for a while
        print("Monitoring started. Running health checks...")
        await asyncio.sleep(5)
        
        # Get health summary
        health_summary = monitor.get_health_summary()
        print(f"Health Summary: {health_summary}")
        
        # Get performance metrics
        performance = monitor.get_performance_summary()
        print(f"Performance Metrics: {performance}")
        
        # Simulate some operations
        monitor.record_room_created()
        monitor.record_participant_joined()
        monitor.record_api_latency(150.5)
        
        # Get updated metrics
        updated_metrics = monitor.get_performance_summary()
        print(f"Updated Metrics: {updated_metrics}")
        
        # Stop monitoring
        await stop_global_monitoring()
        
        logger.info("Basic monitoring example completed")
        
    except Exception as e:
        logger.error("Error in basic monitoring example", error_code=LiveKitErrorCode.SYSTEM_CONFIG_ERROR)
        raise


async def advanced_alerting_example():
    """Advanced alerting system usage example."""
    
    logger.info("Starting advanced alerting example")
    
    try:
        # Get alert manager
        alert_manager = get_alert_manager()
        
        # Initialize default alert rules
        initialize_default_alert_rules()
        
        # Add email notification channel
        email_channel = EmailChannel(
            name="admin_email",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="alerts@example.com",
            smtp_password="app_password",
            from_email="alerts@example.com",
            to_emails=["admin@example.com"],
            alert_levels={AlertLevel.ERROR, AlertLevel.CRITICAL}
        )
        alert_manager.add_notification_channel(email_channel)
        
        # Add webhook notification channel
        webhook_channel = WebhookChannel(
            name="monitoring_webhook",
            url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            headers={"Authorization": "Bearer token"},
            alert_levels={AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL}
        )
        alert_manager.add_notification_channel(webhook_channel)
        
        # Add Slack notification channel
        slack_channel = SlackChannel(
            name="slack_alerts",
            webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
            channel="#alerts",
            username="LiveKit Monitor",
            alert_levels={AlertLevel.ERROR, AlertLevel.CRITICAL}
        )
        alert_manager.add_notification_channel(slack_channel)
        
        # Simulate metrics that would trigger alerts
        test_metrics = {
            "avg_api_latency_ms": 6000,  # High latency
            "connection_success_rate": 0.7,  # Low success rate
            "error_rate": 0.15  # High error rate
        }
        
        # Evaluate metrics against alert rules
        alerts = alert_manager.evaluate_metrics(test_metrics)
        
        print(f"Generated {len(alerts)} alerts from test metrics")
        
        # Process alerts
        for alert in alerts:
            await alert_manager.process_alert(alert)
        
        # Get alert statistics
        stats = alert_manager.get_alert_statistics()
        print(f"Alert Statistics: {stats}")
        
        logger.info("Advanced alerting example completed")
        
    except Exception as e:
        logger.error("Error in advanced alerting example", error_code=LiveKitErrorCode.SYSTEM_CONFIG_ERROR)
        raise


async def logging_example():
    """Structured logging usage example."""
    
    logger.info("Starting logging example")
    
    try:
        # Basic logging with context
        logger.info(
            "Room created successfully",
            service="room",
            room_name="test-room-123",
            participant_id="user-456",
            latency_ms=125.3
        )
        
        # Error logging with error code
        logger.error(
            "Failed to create room",
            error_code=LiveKitErrorCode.ROOM_CREATION_FAILED,
            service="room",
            room_name="failed-room",
            details={"reason": "Invalid configuration"}
        )
        
        # API call logging
        logger.log_api_call(
            method="POST",
            endpoint="/twirp/livekit.RoomService/CreateRoom",
            status_code=200,
            latency_ms=89.2,
            room_name="api-test-room"
        )
        
        # Room event logging
        logger.log_room_event(
            event="participant_joined",
            room_name="meeting-room",
            participant_id="user-789",
            participant_name="John Doe"
        )
        
        # SIP event logging
        logger.log_sip_event(
            event="call_started",
            call_id="call-123",
            trunk_name="novofon-trunk",
            caller_number="+1234567890"
        )
        
        # Media event logging
        logger.log_media_event(
            event="track_published",
            track_id="track-456",
            codec="opus",
            bitrate=64000
        )
        
        # Operation context example
        with operation_context("create_room_with_participants", service="room") as ctx:
            # Simulate room creation
            await asyncio.sleep(0.1)
            
            logger.info(
                "Room created",
                operation_id=ctx.operation_id,
                room_name="context-room"
            )
            
            # Simulate participant joining
            await asyncio.sleep(0.05)
            
            logger.info(
                "Participant joined",
                operation_id=ctx.operation_id,
                participant_id="user-context"
            )
        
        logger.info("Logging example completed")
        
    except Exception as e:
        logger.error("Error in logging example", error_code=LiveKitErrorCode.SYSTEM_CONFIG_ERROR)
        raise


async def health_check_example():
    """Health check endpoints usage example."""
    
    logger.info("Starting health check example")
    
    try:
        # Initialize monitoring
        api_client = get_api_client()
        auth_manager = get_auth_manager()
        monitor = initialize_monitor(api_client, auth_manager)
        
        # Run health checks manually
        health_results = await monitor.run_health_checks()
        
        print("Health Check Results:")
        for service, result in health_results.items():
            status_emoji = "✅" if result.status.value == "healthy" else "❌"
            latency_info = f" ({result.latency_ms:.2f}ms)" if result.latency_ms else ""
            error_info = f" - {result.error}" if result.error else ""
            
            print(f"  {status_emoji} {service}: {result.status.value}{latency_info}{error_info}")
        
        # Get detailed system status
        detailed_status = monitor.get_detailed_metrics()
        
        print(f"\nSystem Overview:")
        print(f"  Overall Status: {detailed_status['health_summary']['overall_status']}")
        print(f"  Healthy Services: {detailed_status['health_summary']['healthy_services']}/{detailed_status['health_summary']['total_services']}")
        print(f"  Active Alerts: {detailed_status['health_summary']['active_alerts']}")
        print(f"  Connection Success Rate: {detailed_status['current_metrics']['connection_success_rate']:.2%}")
        print(f"  Average API Latency: {detailed_status['current_metrics']['avg_api_latency_ms']:.2f}ms")
        
        logger.info("Health check example completed")
        
    except Exception as e:
        logger.error("Error in health check example", error_code=LiveKitErrorCode.SYSTEM_HEALTH_CHECK_FAILED)
        raise


async def integration_example():
    """Complete integration example."""
    
    logger.info("Starting integration example")
    
    try:
        # Set up complete monitoring system
        api_client = get_api_client()
        auth_manager = get_auth_manager()
        
        # Initialize monitor
        monitor = initialize_monitor(api_client, auth_manager)
        
        # Set up alerting
        alert_manager = get_alert_manager()
        initialize_default_alert_rules()
        
        # Connect monitor to alert manager
        def monitor_alert_callback(alert):
            asyncio.create_task(alert_manager.process_alert(alert))
        
        monitor.add_alert_callback(monitor_alert_callback)
        
        # Start monitoring
        await start_global_monitoring()
        
        print("🚀 LiveKit monitoring system started")
        print("📊 Running health checks and collecting metrics...")
        
        # Let it run for a bit
        await asyncio.sleep(10)
        
        # Simulate some system activity
        print("🎭 Simulating system activity...")
        
        # Simulate room operations
        for i in range(3):
            monitor.record_room_created()
            monitor.record_participant_joined()
            monitor.record_api_latency(100 + i * 50)
            await asyncio.sleep(1)
        
        # Get final status
        final_status = monitor.get_detailed_metrics()
        
        print(f"\n📈 Final System Status:")
        print(f"  Rooms Created: {final_status['room_stats']['created']}")
        print(f"  Participants Joined: {final_status['participant_stats']['joined']}")
        print(f"  Total API Calls: {final_status['connection_stats']['total_attempts']}")
        print(f"  Average Latency: {final_status['current_metrics']['avg_api_latency_ms']:.2f}ms")
        
        # Stop monitoring
        await stop_global_monitoring()
        
        print("✅ Integration example completed successfully")
        
        logger.info("Integration example completed")
        
    except Exception as e:
        logger.error("Error in integration example", error_code=LiveKitErrorCode.SYSTEM_CONFIG_ERROR)
        raise


async def main():
    """Run all examples."""
    
    print("🔍 LiveKit Monitoring System Examples")
    print("=" * 50)
    
    examples = [
        ("Basic Monitoring", basic_monitoring_example),
        ("Advanced Alerting", advanced_alerting_example),
        ("Structured Logging", logging_example),
        ("Health Checks", health_check_example),
        ("Complete Integration", integration_example)
    ]
    
    for name, example_func in examples:
        print(f"\n🎯 Running {name} Example...")
        try:
            await example_func()
            print(f"✅ {name} example completed successfully")
        except Exception as e:
            print(f"❌ {name} example failed: {e}")
            logger.error(f"Example failed: {name}", exc_info=True)
        
        print("-" * 30)
    
    print("\n🎉 All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
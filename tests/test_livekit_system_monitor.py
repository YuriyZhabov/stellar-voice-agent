"""
Tests for LiveKit System Monitor

Comprehensive tests for the monitoring and diagnostics system.
"""

import asyncio
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.monitoring.livekit_system_monitor import (
    LiveKitSystemMonitor,
    HealthStatus,
    AlertLevel,
    HealthCheckResult,
    PerformanceMetrics,
    Alert,
    get_monitor,
    initialize_monitor
)
from src.clients.livekit_api_client import LiveKitAPIClient
from src.auth.livekit_auth import LiveKitAuthManager


@pytest.fixture
def mock_api_client():
    """Mock API client for testing."""
    client = MagicMock(spec=LiveKitAPIClient)
    client.list_rooms = AsyncMock(return_value=[])
    client.get_egress_client = MagicMock()
    client.get_ingress_client = MagicMock()
    client.get_sip_client = MagicMock()
    
    # Mock service clients
    egress_client = MagicMock()
    egress_client.list_egress = AsyncMock(return_value=[])
    client.get_egress_client.return_value = egress_client
    
    ingress_client = MagicMock()
    ingress_client.list_ingress = AsyncMock(return_value=[])
    client.get_ingress_client.return_value = ingress_client
    
    sip_client = MagicMock()
    sip_client.list_sip_inbound_trunk = AsyncMock(return_value=[])
    client.get_sip_client.return_value = sip_client
    
    return client


@pytest.fixture
def mock_auth_manager():
    """Mock auth manager for testing."""
    auth_manager = MagicMock(spec=LiveKitAuthManager)
    auth_manager.create_participant_token.return_value = "mock.jwt.token"
    return auth_manager


@pytest.fixture
def monitor(mock_api_client, mock_auth_manager):
    """Create monitor instance for testing."""
    return LiveKitSystemMonitor(
        api_client=mock_api_client,
        auth_manager=mock_auth_manager,
        check_interval=1,  # Fast interval for testing
        metrics_retention_hours=1
    )


class TestLiveKitSystemMonitor:
    """Test cases for LiveKit System Monitor."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.api_client is not None
        assert monitor.auth_manager is not None
        assert monitor.check_interval == 1
        assert monitor.metrics_retention_hours == 1
        assert not monitor._monitoring_active
        assert len(monitor.alerts) == 0
        assert len(monitor.health_results) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_room_service_success(self, monitor, mock_api_client):
        """Test successful room service health check."""
        mock_api_client.list_rooms.return_value = [{"name": "test-room"}]
        
        result = await monitor._check_room_service()
        
        assert result.service == "room_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.latency_ms > 0
        assert result.error is None
        assert result.details["rooms_count"] == 1
        
        mock_api_client.list_rooms.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_room_service_failure(self, monitor, mock_api_client):
        """Test failed room service health check."""
        mock_api_client.list_rooms.side_effect = Exception("Connection failed")
        
        result = await monitor._check_room_service()
        
        assert result.service == "room_service"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.latency_ms is None
        assert result.error == "Connection failed"
    
    @pytest.mark.asyncio
    async def test_health_check_egress_service_success(self, monitor, mock_api_client):
        """Test successful egress service health check."""
        egress_client = mock_api_client.get_egress_client.return_value
        egress_client.list_egress.return_value = []
        
        result = await monitor._check_egress_service()
        
        assert result.service == "egress_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.error is None
        
        egress_client.list_egress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_ingress_service_success(self, monitor, mock_api_client):
        """Test successful ingress service health check."""
        ingress_client = mock_api_client.get_ingress_client.return_value
        ingress_client.list_ingress.return_value = []
        
        result = await monitor._check_ingress_service()
        
        assert result.service == "ingress_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.error is None
        
        ingress_client.list_ingress.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_sip_service_success(self, monitor, mock_api_client):
        """Test successful SIP service health check."""
        sip_client = mock_api_client.get_sip_client.return_value
        sip_client.list_sip_inbound_trunk.return_value = []
        
        result = await monitor._check_sip_service()
        
        assert result.service == "sip_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.error is None
        
        sip_client.list_sip_inbound_trunk.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_sip_service_not_available(self, monitor, mock_api_client):
        """Test SIP service not available."""
        sip_client = mock_api_client.get_sip_client.return_value
        sip_client.list_sip_inbound_trunk.side_effect = Exception("Service not found")
        
        result = await monitor._check_sip_service()
        
        assert result.service == "sip_service"
        assert result.status == HealthStatus.UNKNOWN
        assert result.error == "Service not found"
    
    @pytest.mark.asyncio
    async def test_health_check_auth_system_success(self, monitor, mock_auth_manager):
        """Test successful auth system health check."""
        mock_auth_manager.create_participant_token.return_value = "header.payload.signature"
        
        result = await monitor._check_auth_system()
        
        assert result.service == "auth_system"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.error is None
        assert result.details["token_length"] == 24  # Updated expected length
        
        mock_auth_manager.create_participant_token.assert_called_once_with(
            identity="health-check",
            room_name="health-check-room"
        )
    
    @pytest.mark.asyncio
    async def test_health_check_auth_system_failure(self, monitor, mock_auth_manager):
        """Test failed auth system health check."""
        mock_auth_manager.create_participant_token.side_effect = Exception("Auth failed")
        
        result = await monitor._check_auth_system()
        
        assert result.service == "auth_system"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Auth failed"
    
    @pytest.mark.asyncio
    async def test_run_health_checks(self, monitor):
        """Test running all health checks."""
        results = await monitor.run_health_checks()
        
        assert len(results) == 5  # room, egress, ingress, sip, auth
        assert "room_service" in results
        assert "egress_service" in results
        assert "ingress_service" in results
        assert "sip_service" in results
        assert "auth_system" in results
        
        # Check that results are stored
        assert len(monitor.health_results) == 5
    
    @pytest.mark.asyncio
    async def test_alert_creation_for_unhealthy_service(self, monitor, mock_api_client):
        """Test alert creation when service is unhealthy."""
        mock_api_client.list_rooms.side_effect = Exception("Service down")
        
        await monitor.run_health_checks()
        
        # Should have created an alert for the unhealthy service
        assert len(monitor.alerts) > 0
        
        error_alerts = [alert for alert in monitor.alerts if alert.level == AlertLevel.ERROR]
        assert len(error_alerts) > 0
        
        room_service_alert = next(
            (alert for alert in error_alerts if alert.service == "room_service"),
            None
        )
        assert room_service_alert is not None
        assert "unhealthy" in room_service_alert.message.lower()
    
    @pytest.mark.asyncio
    async def test_alert_creation_for_high_latency(self, monitor, mock_api_client):
        """Test alert creation for high latency."""
        # Create a health check result with high latency
        from src.monitoring.livekit_system_monitor import HealthCheckResult, HealthStatus
        
        high_latency_result = HealthCheckResult(
            service="room_service",
            status=HealthStatus.HEALTHY,
            latency_ms=6000.0  # 6 seconds - above threshold
        )
        
        # Manually trigger alert evaluation
        await monitor._evaluate_health_alerts({"room_service": high_latency_result})
        
        # Should have created a warning alert for high latency
        warning_alerts = [alert for alert in monitor.alerts if alert.level == AlertLevel.WARNING]
        assert len(warning_alerts) > 0
        
        # Check that the alert is about high latency
        latency_alert = next(
            (alert for alert in warning_alerts if "latency" in alert.message.lower()),
            None
        )
        assert latency_alert is not None
    
    def test_connection_tracking(self, monitor):
        """Test connection success/failure tracking."""
        # Record some connections
        monitor._record_connection_success()
        monitor._record_connection_success()
        monitor._record_connection_failure()
        
        assert monitor.connection_stats["successful"] == 2
        assert monitor.connection_stats["failed"] == 1
        assert monitor.connection_stats["total_attempts"] == 3
    
    def test_room_tracking(self, monitor):
        """Test room creation/deletion tracking."""
        monitor.record_room_created()
        monitor.record_room_created()
        monitor.record_room_deleted()
        
        assert monitor.room_stats["created"] == 2
        assert monitor.room_stats["deleted"] == 1
        assert monitor.room_stats["active"] == 1
    
    def test_participant_tracking(self, monitor):
        """Test participant join/leave tracking."""
        monitor.record_participant_joined()
        monitor.record_participant_joined()
        monitor.record_participant_left()
        
        assert monitor.participant_stats["joined"] == 2
        assert monitor.participant_stats["left"] == 1
        assert monitor.participant_stats["active"] == 1
    
    def test_api_latency_recording(self, monitor):
        """Test API latency recording."""
        monitor.record_api_latency(100.5)
        monitor.record_api_latency(200.3)
        
        assert len(monitor.metrics.api_latency) == 2
        assert 100.5 in monitor.metrics.api_latency
        assert 200.3 in monitor.metrics.api_latency
    
    def test_error_logging(self, monitor):
        """Test error logging."""
        monitor._log_error("test_service", "Test error", {"key": "value"})
        
        assert len(monitor.error_log) == 1
        error = monitor.error_log[0]
        assert error["service"] == "test_service"
        assert error["error"] == "Test error"
        assert error["details"]["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_alert_resolution(self, monitor):
        """Test alert resolution."""
        # Create an alert
        alert = await monitor._create_alert(
            AlertLevel.WARNING,
            "test_service",
            "Test alert"
        )
        
        assert not alert.resolved
        
        # Resolve the alert
        success = await monitor.resolve_alert(alert.id)
        
        assert success
        assert alert.resolved
    
    def test_health_summary(self, monitor):
        """Test health summary generation."""
        # Add some health results
        monitor.health_results["service1"] = HealthCheckResult(
            service="service1",
            status=HealthStatus.HEALTHY
        )
        monitor.health_results["service2"] = HealthCheckResult(
            service="service2",
            status=HealthStatus.UNHEALTHY
        )
        
        summary = monitor.get_health_summary()
        
        assert summary["healthy_services"] == 1
        assert summary["total_services"] == 2
        assert summary["overall_status"] == HealthStatus.DEGRADED.value
    
    def test_performance_summary(self, monitor):
        """Test performance summary generation."""
        # Add some metrics
        monitor.record_api_latency(100)
        monitor.record_api_latency(200)
        monitor._record_connection_success()
        monitor._record_connection_success()
        monitor._record_connection_failure()
        
        # Update metrics to calculate success rate
        monitor.metrics.connection_success_rate = monitor.connection_stats["successful"] / monitor.connection_stats["total_attempts"]
        
        summary = monitor.get_performance_summary()
        
        assert summary["avg_api_latency_ms"] == 150.0
        assert summary["connection_success_rate"] == 2/3
        assert summary["total_connections"] == 3
    
    def test_detailed_metrics(self, monitor):
        """Test detailed metrics retrieval."""
        # Add some data
        monitor.record_room_created()
        monitor.record_participant_joined()
        
        metrics = monitor.get_detailed_metrics()
        
        assert "current_metrics" in metrics
        assert "health_summary" in metrics
        assert "health_details" in metrics
        assert "recent_alerts" in metrics
        assert "connection_stats" in metrics
        assert "room_stats" in metrics
        assert "participant_stats" in metrics
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_start_stop(self, monitor):
        """Test starting and stopping monitoring loop."""
        assert not monitor._monitoring_active
        
        # Start monitoring
        await monitor.start_monitoring()
        assert monitor._monitoring_active
        assert monitor._monitoring_task is not None
        
        # Stop monitoring
        await monitor.stop_monitoring()
        assert not monitor._monitoring_active
    
    @pytest.mark.asyncio
    async def test_alert_callbacks(self, monitor):
        """Test alert callback system."""
        callback_called = False
        received_alert = None
        
        def test_callback(alert):
            nonlocal callback_called, received_alert
            callback_called = True
            received_alert = alert
        
        monitor.add_alert_callback(test_callback)
        
        # Create an alert
        alert = await monitor._create_alert(
            AlertLevel.ERROR,
            "test_service",
            "Test alert"
        )
        
        assert callback_called
        assert received_alert == alert
        
        # Remove callback
        monitor.remove_alert_callback(test_callback)
        
        # Create another alert
        callback_called = False
        await monitor._create_alert(
            AlertLevel.INFO,
            "test_service",
            "Another alert"
        )
        
        assert not callback_called
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, monitor):
        """Test cleanup of old monitoring data."""
        # Create old alert
        old_alert = Alert(
            level=AlertLevel.INFO,
            service="test",
            message="Old alert"
        )
        old_alert.timestamp = datetime.now(UTC) - timedelta(hours=25)
        old_alert.resolved = True
        monitor.alerts.append(old_alert)
        
        # Create recent alert
        recent_alert = Alert(
            level=AlertLevel.INFO,
            service="test",
            message="Recent alert"
        )
        monitor.alerts.append(recent_alert)
        
        # Add old error log entry
        old_error = {
            "timestamp": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
            "service": "test",
            "error": "Old error"
        }
        monitor.error_log.append(old_error)
        
        # Run cleanup
        await monitor._cleanup_old_data()
        
        # Old resolved alert should be removed, recent alert should remain
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0] == recent_alert
        
        # Old error should be removed
        assert len(monitor.error_log) == 0


class TestGlobalMonitorFunctions:
    """Test global monitor functions."""
    
    def test_initialize_monitor(self, mock_api_client, mock_auth_manager):
        """Test monitor initialization."""
        monitor = initialize_monitor(mock_api_client, mock_auth_manager)
        
        assert monitor is not None
        assert get_monitor() == monitor
    
    @pytest.mark.asyncio
    async def test_global_monitoring_start_stop(self, mock_api_client, mock_auth_manager):
        """Test global monitoring start/stop."""
        from src.monitoring.livekit_system_monitor import (
            start_global_monitoring,
            stop_global_monitoring
        )
        
        # Initialize monitor
        initialize_monitor(mock_api_client, mock_auth_manager)
        
        # Start global monitoring
        await start_global_monitoring()
        
        monitor = get_monitor()
        assert monitor._monitoring_active
        
        # Stop global monitoring
        await stop_global_monitoring()
        assert not monitor._monitoring_active
"""Tests for monitoring system components."""

import asyncio
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from src.monitoring.health_monitor import (
    HealthMonitor, HealthStatus, ComponentType, ComponentHealth, 
    SystemHealth, HealthThreshold
)
from src.monitoring.alerting import (
    AlertManager, Alert, AlertSeverity, AlertStatus, AlertRule,
    WebhookChannel, LogChannel
)
from src.monitoring.metrics_exporter import (
    MetricsExportManager, PrometheusExporter, JSONExporter,
    MetricPoint, MetricsSnapshot
)
from src.monitoring.dashboard import (
    DashboardManager, Dashboard, DashboardPanel, DashboardMetric
)


class TestHealthMonitor:
    """Test health monitoring system."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create health monitor instance."""
        return HealthMonitor(check_interval=1.0, enable_auto_checks=False)
    
    @pytest.fixture
    def mock_health_checker(self):
        """Mock health checker function."""
        return AsyncMock(return_value=True)
    
    def test_health_monitor_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert health_monitor.check_interval == 1.0
        assert not health_monitor.enable_auto_checks
        assert len(health_monitor.components) == 0
        assert len(health_monitor.health_checkers) == 0
    
    def test_register_component(self, health_monitor, mock_health_checker):
        """Test component registration."""
        health_monitor.register_component(
            "test_component",
            ComponentType.STT_CLIENT,
            mock_health_checker
        )
        
        assert "test_component" in health_monitor.components
        assert "test_component" in health_monitor.health_checkers
        assert "test_component" in health_monitor.thresholds
    
    def test_unregister_component(self, health_monitor, mock_health_checker):
        """Test component unregistration."""
        health_monitor.register_component(
            "test_component",
            ComponentType.STT_CLIENT,
            mock_health_checker
        )
        
        health_monitor.unregister_component("test_component")
        
        assert "test_component" not in health_monitor.components
        assert "test_component" not in health_monitor.health_checkers
        assert "test_component" not in health_monitor.thresholds
    
    @pytest.mark.asyncio
    async def test_check_component_health_success(self, health_monitor, mock_health_checker):
        """Test successful component health check."""
        health_monitor.register_component(
            "test_component",
            ComponentType.STT_CLIENT,
            mock_health_checker
        )
        
        health = await health_monitor.check_component_health("test_component")
        
        assert health.component_name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.response_time_ms > 0
        mock_health_checker.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_component_health_failure(self, health_monitor):
        """Test failed component health check."""
        failing_checker = AsyncMock(side_effect=Exception("Health check failed"))
        
        health_monitor.register_component(
            "failing_component",
            ComponentType.STT_CLIENT,
            failing_checker
        )
        
        health = await health_monitor.check_component_health("failing_component")
        
        assert health.component_name == "failing_component"
        assert health.status == HealthStatus.UNHEALTHY
        assert "Health check failed" in health.error_message
    
    @pytest.mark.asyncio
    async def test_check_component_health_timeout(self, health_monitor):
        """Test component health check timeout."""
        async def slow_checker():
            await asyncio.sleep(2)  # Longer than timeout
            return True
        
        health_monitor.component_timeout = 0.1  # Short timeout
        health_monitor.register_component(
            "slow_component",
            ComponentType.STT_CLIENT,
            slow_checker
        )
        
        health = await health_monitor.check_component_health("slow_component")
        
        assert health.component_name == "slow_component"
        assert health.status == HealthStatus.UNHEALTHY
        assert "timed out" in health.error_message
    
    @pytest.mark.asyncio
    async def test_check_all_components(self, health_monitor):
        """Test checking all components."""
        # Register multiple components
        health_monitor.register_component(
            "healthy_component",
            ComponentType.STT_CLIENT,
            AsyncMock(return_value=True)
        )
        health_monitor.register_component(
            "unhealthy_component",
            ComponentType.LLM_CLIENT,
            AsyncMock(side_effect=Exception("Failed"))
        )
        
        system_health = await health_monitor.check_all_components()
        
        assert isinstance(system_health, SystemHealth)
        assert system_health.total_components == 2
        assert system_health.healthy_components == 1
        assert system_health.status == HealthStatus.UNHEALTHY  # One component failed
    
    def test_get_component_health_trend(self, health_monitor):
        """Test component health trend analysis."""
        # Add some mock history
        component_name = "test_component"
        health_monitor.health_history[component_name] = [
            ComponentHealth(
                component_type=ComponentType.STT_CLIENT,
                component_name=component_name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(UTC),
                response_time_ms=100.0,
                success_rate=95.0,
                error_rate=5.0
            )
        ]
        
        trend = health_monitor.get_component_health_trend(component_name, hours=1)
        
        assert trend["component_name"] == component_name
        assert trend["total_checks"] == 1
        assert trend["availability_percentage"] == 100.0


class TestAlertManager:
    """Test alerting system."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create alert manager instance."""
        return AlertManager(check_interval=1.0)
    
    @pytest.fixture
    def mock_webhook_channel(self):
        """Mock webhook channel."""
        channel = MagicMock(spec=WebhookChannel)
        channel.send_alert = AsyncMock(return_value=True)
        channel.health_check = AsyncMock(return_value=True)
        return channel
    
    def test_alert_manager_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert alert_manager.check_interval == 1.0
        assert len(alert_manager.alert_rules) > 0  # Default rules
        assert len(alert_manager.channels) == 0
        assert len(alert_manager.active_alerts) == 0
    
    def test_add_remove_rule(self, alert_manager):
        """Test adding and removing alert rules."""
        rule = AlertRule(
            name="test_rule",
            condition=lambda x: True,
            severity=AlertSeverity.HIGH,
            message_template="Test alert"
        )
        
        alert_manager.add_rule(rule)
        assert "test_rule" in alert_manager.alert_rules
        
        alert_manager.remove_rule("test_rule")
        assert "test_rule" not in alert_manager.alert_rules
    
    def test_add_remove_channel(self, alert_manager, mock_webhook_channel):
        """Test adding and removing notification channels."""
        alert_manager.add_channel("webhook", mock_webhook_channel)
        assert "webhook" in alert_manager.channels
        
        alert_manager.remove_channel("webhook")
        assert "webhook" not in alert_manager.channels
    
    @pytest.mark.asyncio
    async def test_evaluate_rules_creates_alert(self, alert_manager, mock_webhook_channel):
        """Test rule evaluation creates alerts."""
        # Add channel
        alert_manager.add_channel("webhook", mock_webhook_channel)
        
        # Add test rule
        rule = AlertRule(
            name="test_rule",
            condition=lambda x: x == "trigger",
            severity=AlertSeverity.HIGH,
            message_template="Test alert triggered"
        )
        alert_manager.add_rule(rule)
        
        # Evaluate with triggering data
        alerts = await alert_manager.evaluate_rules("trigger")
        
        assert len(alerts) == 1
        assert alerts[0].name == "test_rule"
        assert alerts[0].severity == AlertSeverity.HIGH
        assert alerts[0].status == AlertStatus.ACTIVE
        
        # Check alert was sent to channel
        mock_webhook_channel.send_alert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, alert_manager):
        """Test alert resolution."""
        # Create test alert
        rule = AlertRule(
            name="test_rule",
            condition=lambda x: True,
            severity=AlertSeverity.HIGH,
            message_template="Test alert"
        )
        alert_manager.add_rule(rule)
        
        alerts = await alert_manager.evaluate_rules("trigger")
        alert_id = alerts[0].id
        
        # Resolve alert
        success = await alert_manager.resolve_alert(alert_id, "Test resolution")
        
        assert success
        assert alert_id not in alert_manager.active_alerts
        assert alert_id in alert_manager.resolved_alerts
        assert alert_manager.resolved_alerts[alert_id].status == AlertStatus.RESOLVED
    
    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, alert_manager):
        """Test alert acknowledgment."""
        # Create test alert
        rule = AlertRule(
            name="test_rule",
            condition=lambda x: True,
            severity=AlertSeverity.HIGH,
            message_template="Test alert"
        )
        alert_manager.add_rule(rule)
        
        alerts = await alert_manager.evaluate_rules("trigger")
        alert_id = alerts[0].id
        
        # Acknowledge alert
        success = await alert_manager.acknowledge_alert(alert_id, "Test acknowledgment")
        
        assert success
        assert alert_id in alert_manager.active_alerts
        assert alert_manager.active_alerts[alert_id].status == AlertStatus.ACKNOWLEDGED
    
    def test_get_active_alerts_filtering(self, alert_manager):
        """Test filtering active alerts."""
        # Create test alerts with different severities
        alert1 = Alert(
            id="1",
            name="critical_alert",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACTIVE,
            message="Critical issue",
            component="component1"
        )
        alert2 = Alert(
            id="2",
            name="high_alert",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="High issue",
            component="component2"
        )
        
        alert_manager.active_alerts["1"] = alert1
        alert_manager.active_alerts["2"] = alert2
        
        # Test severity filtering
        critical_alerts = alert_manager.get_active_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical_alerts) == 1
        assert critical_alerts[0].severity == AlertSeverity.CRITICAL
        
        # Test component filtering
        component1_alerts = alert_manager.get_active_alerts(component="component1")
        assert len(component1_alerts) == 1
        assert component1_alerts[0].component == "component1"


class TestMetricsExporter:
    """Test metrics export system."""
    
    @pytest.fixture
    def metrics_snapshot(self):
        """Create test metrics snapshot."""
        return MetricsSnapshot(
            timestamp=datetime.now(UTC),
            metrics=[
                MetricPoint(
                    name="test_metric",
                    value=42.0,
                    timestamp=datetime.now(UTC).timestamp(),
                    labels={"service": "test"},
                    metric_type="gauge"
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_prometheus_exporter_without_pushgateway(self, metrics_snapshot):
        """Test Prometheus exporter without pushgateway."""
        exporter = PrometheusExporter()
        
        success = await exporter.export_metrics(metrics_snapshot)
        assert success
        
        # Check metrics registry
        exposition = exporter.get_metrics_exposition()
        assert "test_metric" in exposition
        assert "42" in exposition
    
    @pytest.mark.asyncio
    async def test_json_exporter_file(self, metrics_snapshot, tmp_path):
        """Test JSON exporter to file."""
        file_path = tmp_path / "metrics.json"
        exporter = JSONExporter(file_path=str(file_path))
        
        success = await exporter.export_metrics(metrics_snapshot)
        assert success
        assert file_path.exists()
        
        # Check file content
        import json
        with open(file_path) as f:
            data = json.load(f)
        
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["name"] == "test_metric"
        assert data["metrics"][0]["value"] == 42.0
    
    @pytest.mark.asyncio
    async def test_metrics_export_manager(self, metrics_snapshot):
        """Test metrics export manager."""
        manager = MetricsExportManager(export_interval=1.0)
        
        # Add test exporter
        test_exporter = MagicMock()
        test_exporter.export_metrics = AsyncMock(return_value=True)
        test_exporter.health_check = AsyncMock(return_value=True)
        
        manager.add_exporter("test", test_exporter)
        
        # Test export
        results = await manager.export_all()
        
        assert "test" in results
        assert results["test"] is True
        test_exporter.export_metrics.assert_called_once()


class TestDashboardManager:
    """Test dashboard system."""
    
    @pytest.fixture
    def health_monitor(self):
        """Mock health monitor."""
        monitor = MagicMock(spec=HealthMonitor)
        monitor.get_system_health.return_value = SystemHealth(
            status=HealthStatus.HEALTHY,
            last_check=datetime.now(UTC),
            components={},
            summary={"total_components": 2, "healthy_components": 2}
        )
        monitor.get_all_component_health.return_value = {}
        return monitor
    
    @pytest.fixture
    def alert_manager(self):
        """Mock alert manager."""
        manager = MagicMock(spec=AlertManager)
        manager.get_active_alerts.return_value = []
        return manager
    
    @pytest.fixture
    def dashboard_manager(self, health_monitor, alert_manager):
        """Create dashboard manager instance."""
        return DashboardManager(
            health_monitor=health_monitor,
            alert_manager=alert_manager,
            update_interval=1.0
        )
    
    def test_dashboard_manager_initialization(self, dashboard_manager):
        """Test dashboard manager initialization."""
        assert dashboard_manager.update_interval == 1.0
        assert len(dashboard_manager.dashboards) > 0  # Default dashboards
        
        # Check default dashboards exist
        assert "system_overview" in dashboard_manager.dashboards
        assert "api_performance" in dashboard_manager.dashboards
        assert "ai_services" in dashboard_manager.dashboards
        assert "infrastructure" in dashboard_manager.dashboards
    
    def test_get_dashboard(self, dashboard_manager):
        """Test getting dashboard by ID."""
        dashboard = dashboard_manager.get_dashboard("system_overview")
        
        assert dashboard is not None
        assert dashboard.id == "system_overview"
        assert dashboard.title == "System Overview"
        assert len(dashboard.panels) > 0
    
    def test_create_custom_dashboard(self, dashboard_manager):
        """Test creating custom dashboard."""
        panels = [
            DashboardPanel(
                id="custom_panel",
                title="Custom Panel",
                description="Test panel",
                metrics=[]
            )
        ]
        
        dashboard = dashboard_manager.create_custom_dashboard(
            "custom_dashboard",
            "Custom Dashboard",
            "Test dashboard",
            panels
        )
        
        assert dashboard.id == "custom_dashboard"
        assert dashboard.title == "Custom Dashboard"
        assert len(dashboard.panels) == 1
        assert "custom_dashboard" in dashboard_manager.dashboards
    
    def test_delete_dashboard(self, dashboard_manager):
        """Test deleting dashboard."""
        # Create custom dashboard first
        panels = []
        dashboard_manager.create_custom_dashboard(
            "test_dashboard",
            "Test Dashboard",
            "Test",
            panels
        )
        
        # Delete it
        success = dashboard_manager.delete_dashboard("test_dashboard")
        
        assert success
        assert "test_dashboard" not in dashboard_manager.dashboards
    
    @pytest.mark.asyncio
    async def test_update_dashboard(self, dashboard_manager):
        """Test updating dashboard."""
        dashboard_id = "system_overview"
        original_updated_at = dashboard_manager.dashboards[dashboard_id].updated_at
        
        # Wait a bit to ensure timestamp difference
        await asyncio.sleep(0.01)
        
        await dashboard_manager.update_dashboard(dashboard_id)
        
        updated_dashboard = dashboard_manager.dashboards[dashboard_id]
        assert updated_dashboard.updated_at > original_updated_at
    
    @pytest.mark.asyncio
    async def test_export_dashboard_data(self, dashboard_manager):
        """Test exporting dashboard data."""
        dashboard_data = await dashboard_manager.export_dashboard_data("system_overview")
        
        assert "id" in dashboard_data
        assert "title" in dashboard_data
        assert "panels" in dashboard_data
        assert dashboard_data["id"] == "system_overview"
        assert isinstance(dashboard_data["panels"], list)


@pytest.mark.asyncio
async def test_monitoring_integration():
    """Test integration between monitoring components."""
    # Create health monitor
    health_monitor = HealthMonitor(check_interval=0.1, enable_auto_checks=False)
    
    # Register test component
    async def test_health_checker():
        return {"status": "healthy", "success_rate": 95.0}
    
    health_monitor.register_component(
        "test_service",
        ComponentType.STT_CLIENT,
        test_health_checker
    )
    
    # Create alert manager
    alert_manager = AlertManager(check_interval=0.1)
    
    # Add test alert rule
    rule = AlertRule(
        name="component_degraded",
        condition=lambda health: (
            isinstance(health, ComponentHealth) and 
            health.success_rate < 90.0
        ),
        severity=AlertSeverity.MEDIUM,
        message_template="Component {component_name} degraded"
    )
    alert_manager.add_rule(rule)
    
    # Check component health
    component_health = await health_monitor.check_component_health("test_service")
    
    # Evaluate alerts
    alerts = await alert_manager.evaluate_rules(component_health)
    
    # Should not create alert since success rate is 95%
    assert len(alerts) == 0
    
    # Create dashboard manager
    dashboard_manager = DashboardManager(
        health_monitor=health_monitor,
        alert_manager=alert_manager,
        update_interval=0.1
    )
    
    # Update dashboard
    await dashboard_manager.update_dashboard("system_overview")
    
    # Export dashboard data
    dashboard_data = await dashboard_manager.export_dashboard_data("system_overview")
    
    assert dashboard_data["id"] == "system_overview"
    assert len(dashboard_data["panels"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])
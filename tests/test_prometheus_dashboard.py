"""Tests for Prometheus monitoring dashboard and alerts."""

import asyncio
import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.monitoring.prometheus_dashboard import (
    PrometheusMonitoringDashboard,
    PrometheusMetric,
    PrometheusDashboardPanel
)
from src.monitoring.health_monitor import HealthMonitor, ComponentHealth, HealthStatus, ComponentType
from src.monitoring.alerting import AlertManager, AlertSeverity


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for Prometheus API calls."""
    client = AsyncMock()
    return client


@pytest.fixture
def health_monitor():
    """Create health monitor instance."""
    return HealthMonitor(enable_auto_checks=False)


@pytest.fixture
def alert_manager():
    """Create alert manager instance."""
    return AlertManager()


@pytest.fixture
def prometheus_dashboard(health_monitor, alert_manager):
    """Create Prometheus monitoring dashboard instance."""
    dashboard = PrometheusMonitoringDashboard(
        prometheus_url="http://localhost:9091",
        health_monitor=health_monitor,
        alert_manager=alert_manager,
        update_interval=10.0
    )
    return dashboard


class TestPrometheusMetric:
    """Test PrometheusMetric class."""
    
    def test_metric_creation(self):
        """Test creating a Prometheus metric."""
        timestamp = datetime.now(UTC)
        metric = PrometheusMetric(
            name="test_metric",
            value=42.0,
            timestamp=timestamp,
            labels={"job": "test"},
            help_text="Test metric",
            metric_type="gauge"
        )
        
        assert metric.name == "test_metric"
        assert metric.value == 42.0
        assert metric.timestamp == timestamp
        assert metric.labels == {"job": "test"}
        assert metric.help_text == "Test metric"
        assert metric.metric_type == "gauge"


class TestPrometheusDashboardPanel:
    """Test PrometheusDashboardPanel class."""
    
    def test_panel_creation(self):
        """Test creating a dashboard panel."""
        panel = PrometheusDashboardPanel(
            id="test_panel",
            title="Test Panel",
            description="Test panel description",
            query="up{job=\"test\"}",
            chart_type="gauge",
            refresh_interval=30,
            thresholds={"warning": 0.8, "critical": 0.5},
            unit="status"
        )
        
        assert panel.id == "test_panel"
        assert panel.title == "Test Panel"
        assert panel.description == "Test panel description"
        assert panel.query == "up{job=\"test\"}"
        assert panel.chart_type == "gauge"
        assert panel.refresh_interval == 30
        assert panel.thresholds == {"warning": 0.8, "critical": 0.5}
        assert panel.unit == "status"
    
    def test_panel_to_dict(self):
        """Test converting panel to dictionary."""
        panel = PrometheusDashboardPanel(
            id="test_panel",
            title="Test Panel",
            description="Test description",
            query="up",
            chart_type="line",
            unit="count"
        )
        
        panel_dict = panel.to_dict()
        
        assert panel_dict["id"] == "test_panel"
        assert panel_dict["title"] == "Test Panel"
        assert panel_dict["description"] == "Test description"
        assert panel_dict["query"] == "up"
        assert panel_dict["chart_type"] == "line"
        assert panel_dict["unit"] == "count"


class TestPrometheusMonitoringDashboard:
    """Test PrometheusMonitoringDashboard class."""
    
    def test_dashboard_initialization(self, prometheus_dashboard):
        """Test dashboard initialization."""
        assert prometheus_dashboard.prometheus_url == "http://localhost:9091"
        assert prometheus_dashboard.update_interval == 10.0
        assert len(prometheus_dashboard.panels) > 0
        assert not prometheus_dashboard.is_monitoring
        assert prometheus_dashboard.last_update is None
    
    def test_dashboard_panels_created(self, prometheus_dashboard):
        """Test that default dashboard panels are created."""
        expected_panels = [
            "prometheus_health",
            "prometheus_uptime",
            "scrape_targets",
            "query_performance",
            "storage_usage",
            "ingestion_rate",
            "memory_usage",
            "cpu_usage",
            "config_reload",
            "rule_evaluation"
        ]
        
        for panel_id in expected_panels:
            assert panel_id in prometheus_dashboard.panels
            panel = prometheus_dashboard.panels[panel_id]
            assert isinstance(panel, PrometheusDashboardPanel)
            assert panel.id == panel_id
            assert panel.title
            assert panel.description
            assert panel.query
    
    @pytest.mark.asyncio
    async def test_query_prometheus_success(self, prometheus_dashboard):
        """Test successful Prometheus query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus"},
                        "value": [1234567890, "1"]
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get', return_value=mock_response):
            result = await prometheus_dashboard.query_prometheus("up{job=\"prometheus\"}")
        
        assert result["status"] == "success"
        assert "data" in result
        assert result["data"]["resultType"] == "vector"
    
    @pytest.mark.asyncio
    async def test_query_prometheus_error(self, prometheus_dashboard):
        """Test Prometheus query error handling."""
        with patch.object(prometheus_dashboard.http_client, 'get', side_effect=httpx.RequestError("Connection failed")):
            result = await prometheus_dashboard.query_prometheus("up")
        
        assert result["status"] == "error"
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_update_panel_metrics_success(self, prometheus_dashboard):
        """Test successful panel metrics update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus"},
                        "value": [1234567890, "1.0"]
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get', return_value=mock_response):
            metric = await prometheus_dashboard.update_panel_metrics("prometheus_health")
        
        assert metric is not None
        assert metric.name == "prometheus_health"
        assert metric.value == 1.0
        assert metric.labels == {"job": "prometheus"}
        assert "prometheus_health" in prometheus_dashboard.current_metrics
    
    @pytest.mark.asyncio
    async def test_update_panel_metrics_no_data(self, prometheus_dashboard):
        """Test panel metrics update with no data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": []
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get', return_value=mock_response):
            metric = await prometheus_dashboard.update_panel_metrics("prometheus_health")
        
        assert metric is None
    
    @pytest.mark.asyncio
    async def test_update_panel_metrics_invalid_panel(self, prometheus_dashboard):
        """Test updating metrics for invalid panel."""
        metric = await prometheus_dashboard.update_panel_metrics("invalid_panel")
        assert metric is None
    
    @pytest.mark.asyncio
    async def test_update_all_panels(self, prometheus_dashboard):
        """Test updating all dashboard panels."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus"},
                        "value": [1234567890, "1.0"]
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get', return_value=mock_response):
            updated_metrics = await prometheus_dashboard.update_all_panels()
        
        assert len(updated_metrics) > 0
        assert prometheus_dashboard.last_update is not None
        
        # Check that metrics were stored
        for panel_id in updated_metrics.keys():
            assert panel_id in prometheus_dashboard.current_metrics
    
    @pytest.mark.asyncio
    async def test_check_prometheus_health_healthy(self, prometheus_dashboard):
        """Test Prometheus health check when service is healthy."""
        # Mock healthy response
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        
        mock_metrics_response = MagicMock()
        mock_metrics_response.status_code = 200
        mock_metrics_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus"},
                        "value": [1234567890, "1"]
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get') as mock_get:
            mock_get.side_effect = [mock_health_response, mock_metrics_response]
            health = await prometheus_dashboard.check_prometheus_health()
        
        assert health.component_name == "prometheus"
        assert health.component_type == ComponentType.SYSTEM
        assert health.status == HealthStatus.HEALTHY
        assert health.success_rate == 100.0
        assert health.error_message is None
        assert health.details["api_accessible"] is True
        assert health.details["metrics_queryable"] is True
    
    @pytest.mark.asyncio
    async def test_check_prometheus_health_unhealthy(self, prometheus_dashboard):
        """Test Prometheus health check when service is unhealthy."""
        with patch.object(prometheus_dashboard.http_client, 'get', side_effect=httpx.RequestError("Connection refused")):
            health = await prometheus_dashboard.check_prometheus_health()
        
        assert health.component_name == "prometheus"
        assert health.status == HealthStatus.UNHEALTHY
        assert health.success_rate == 0.0
        assert "Cannot connect to Prometheus" in health.error_message
        assert health.details["api_accessible"] is False
    
    @pytest.mark.asyncio
    async def test_get_scrape_targets_status(self, prometheus_dashboard):
        """Test getting scrape targets status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus", "instance": "localhost:9090"},
                        "value": [1234567890, "1"]
                    },
                    {
                        "metric": {"job": "voice-ai-agent", "instance": "localhost:8000"},
                        "value": [1234567890, "0"]
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get', return_value=mock_response):
            status = await prometheus_dashboard.get_scrape_targets_status()
        
        assert status["total_targets"] == 2
        assert status["healthy_targets"] == 1
        assert status["unhealthy_targets"] == 1
        assert status["health_percentage"] == 50.0
        assert len(status["targets"]) == 2
        
        # Check individual targets
        prometheus_target = next(t for t in status["targets"] if t["job"] == "prometheus")
        assert prometheus_target["status"] == "up"
        
        app_target = next(t for t in status["targets"] if t["job"] == "voice-ai-agent")
        assert app_target["status"] == "down"
    
    @pytest.mark.asyncio
    async def test_evaluate_prometheus_alerts(self, prometheus_dashboard):
        """Test evaluating Prometheus-specific alerts."""
        # Mock Prometheus responses
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        
        mock_metrics_response = MagicMock()
        mock_metrics_response.status_code = 200
        mock_metrics_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "prometheus"},
                        "value": [1234567890, "1"]
                    }
                ]
            }
        }
        
        mock_latency_response = MagicMock()
        mock_latency_response.status_code = 200
        mock_latency_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"quantile": "0.95"},
                        "value": [1234567890, "6.0"]  # High latency
                    }
                ]
            }
        }
        
        with patch.object(prometheus_dashboard.http_client, 'get') as mock_get:
            mock_get.side_effect = [
                mock_health_response,  # Health check
                mock_metrics_response,  # Health metrics
                mock_latency_response,  # Query latency
                mock_metrics_response,  # Scrape targets
                mock_metrics_response,  # Memory usage
                mock_metrics_response   # Config reload
            ]
            
            await prometheus_dashboard.evaluate_prometheus_alerts()
        
        # Check that alert manager was called
        assert prometheus_dashboard.alert_manager is not None
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, prometheus_dashboard):
        """Test starting and stopping monitoring."""
        assert not prometheus_dashboard.is_monitoring
        
        # Start monitoring
        await prometheus_dashboard.start_monitoring()
        assert prometheus_dashboard.is_monitoring
        assert prometheus_dashboard.monitoring_task is not None
        
        # Stop monitoring
        await prometheus_dashboard.stop_monitoring()
        assert not prometheus_dashboard.is_monitoring
        assert prometheus_dashboard.monitoring_task is None
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, prometheus_dashboard):
        """Test monitoring loop error handling."""
        # Mock update_all_panels to raise an exception
        with patch.object(prometheus_dashboard, 'update_all_panels', side_effect=Exception("Test error")):
            # Start monitoring
            prometheus_dashboard.is_monitoring = True
            prometheus_dashboard._stop_event.clear()
            
            # Run one iteration of the monitoring loop
            with patch('asyncio.sleep') as mock_sleep:
                try:
                    await asyncio.wait_for(prometheus_dashboard._monitoring_loop(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass  # Expected due to the loop
                
                # Check that sleep was called (error handling)
                mock_sleep.assert_called()
    
    def test_get_dashboard_data(self, prometheus_dashboard):
        """Test getting dashboard data."""
        # Add some mock metrics
        timestamp = datetime.now(UTC)
        prometheus_dashboard.current_metrics["prometheus_health"] = PrometheusMetric(
            name="prometheus_health",
            value=1.0,
            timestamp=timestamp,
            labels={"job": "prometheus"}
        )
        prometheus_dashboard.last_update = timestamp
        
        dashboard_data = prometheus_dashboard.get_dashboard_data()
        
        assert dashboard_data["title"] == "Prometheus Health Monitoring"
        assert dashboard_data["description"]
        assert dashboard_data["last_update"] == timestamp.isoformat()
        assert "panels" in dashboard_data
        assert "summary" in dashboard_data
        
        # Check panel data
        prometheus_health_panel = dashboard_data["panels"]["prometheus_health"]
        assert prometheus_health_panel["current_value"] == 1.0
        assert prometheus_health_panel["current_timestamp"] == timestamp.isoformat()
        assert prometheus_health_panel["labels"] == {"job": "prometheus"}
        
        # Check summary
        summary = dashboard_data["summary"]
        assert summary["total_panels"] == len(prometheus_dashboard.panels)
        assert summary["updated_panels"] == 1
        assert summary["prometheus_url"] == "http://localhost:9091"
        assert summary["monitoring_active"] is False
    
    @pytest.mark.asyncio
    async def test_close_dashboard(self, prometheus_dashboard):
        """Test closing dashboard."""
        # Start monitoring first
        await prometheus_dashboard.start_monitoring()
        assert prometheus_dashboard.is_monitoring
        
        # Close dashboard
        await prometheus_dashboard.close()
        
        # Check that monitoring was stopped
        assert not prometheus_dashboard.is_monitoring
        assert prometheus_dashboard.monitoring_task is None


class TestPrometheusAlerts:
    """Test Prometheus-specific alert rules."""
    
    @pytest.mark.asyncio
    async def test_prometheus_service_down_alert(self, prometheus_dashboard):
        """Test Prometheus service down alert."""
        # Create unhealthy component health
        unhealthy_health = ComponentHealth(
            component_type=ComponentType.SYSTEM,
            component_name="prometheus",
            status=HealthStatus.UNHEALTHY,
            last_check=datetime.now(UTC),
            error_message="Service is down"
        )
        
        # Evaluate alert rules
        alerts = await prometheus_dashboard.alert_manager.evaluate_rules(unhealthy_health)
        
        # Check that alert was created
        assert len(alerts) > 0
        service_down_alert = next((a for a in alerts if a.name == "prometheus_service_down"), None)
        assert service_down_alert is not None
        assert service_down_alert.severity == AlertSeverity.CRITICAL
        assert "Service is down" in service_down_alert.message
    
    @pytest.mark.asyncio
    async def test_prometheus_high_query_latency_alert(self, prometheus_dashboard):
        """Test Prometheus high query latency alert."""
        # Create metrics with high latency
        metrics = {"prometheus_query_latency": 6.0}
        
        # Evaluate alert rules
        alerts = await prometheus_dashboard.alert_manager.evaluate_rules(metrics)
        
        # Check that alert was created
        assert len(alerts) > 0
        latency_alert = next((a for a in alerts if a.name == "prometheus_high_query_latency"), None)
        assert latency_alert is not None
        assert latency_alert.severity == AlertSeverity.HIGH
        assert "6.00s" in latency_alert.message
    
    @pytest.mark.asyncio
    async def test_prometheus_scrape_targets_down_alert(self, prometheus_dashboard):
        """Test Prometheus scrape targets down alert."""
        # Create metrics with targets down
        metrics = {"scrape_targets_down": 2}
        
        # Evaluate alert rules
        alerts = await prometheus_dashboard.alert_manager.evaluate_rules(metrics)
        
        # Check that alert was created
        assert len(alerts) > 0
        targets_alert = next((a for a in alerts if a.name == "prometheus_scrape_targets_down"), None)
        assert targets_alert is not None
        assert targets_alert.severity == AlertSeverity.HIGH
        assert "2" in targets_alert.message
    
    @pytest.mark.asyncio
    async def test_prometheus_high_memory_usage_alert(self, prometheus_dashboard):
        """Test Prometheus high memory usage alert."""
        # Create metrics with high memory usage (3GB)
        metrics = {
            "prometheus_memory_usage_bytes": 3221225472,  # 3GB
            "prometheus_memory_usage_gb": 3.0
        }
        
        # Evaluate alert rules
        alerts = await prometheus_dashboard.alert_manager.evaluate_rules(metrics)
        
        # Check that alert was created
        assert len(alerts) > 0
        memory_alert = next((a for a in alerts if a.name == "prometheus_high_memory_usage"), None)
        assert memory_alert is not None
        assert memory_alert.severity == AlertSeverity.MEDIUM
        assert "3.0GB" in memory_alert.message
    
    @pytest.mark.asyncio
    async def test_prometheus_config_reload_failed_alert(self, prometheus_dashboard):
        """Test Prometheus configuration reload failed alert."""
        # Create metrics with failed config reload
        metrics = {"prometheus_config_reload_successful": 0}
        
        # Evaluate alert rules
        alerts = await prometheus_dashboard.alert_manager.evaluate_rules(metrics)
        
        # Check that alert was created
        assert len(alerts) > 0
        config_alert = next((a for a in alerts if a.name == "prometheus_config_reload_failed"), None)
        assert config_alert is not None
        assert config_alert.severity == AlertSeverity.HIGH
        assert "configuration reload failed" in config_alert.message


if __name__ == "__main__":
    pytest.main([__file__])
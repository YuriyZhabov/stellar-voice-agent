"""Real-time Prometheus health monitoring dashboard and alerts."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
import yaml

from src.config import get_settings
from src.monitoring.health_monitor import HealthMonitor, ComponentHealth, HealthStatus, ComponentType
from src.monitoring.alerting import AlertManager, Alert, AlertSeverity, AlertRule
from src.monitoring.prometheus_health import PrometheusHealthChecker
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


@dataclass
class PrometheusMetric:
    """Prometheus metric with metadata."""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram, summary


@dataclass
class PrometheusDashboardPanel:
    """Dashboard panel for Prometheus metrics."""
    id: str
    title: str
    description: str
    query: str
    chart_type: str = "line"  # line, gauge, bar, table
    refresh_interval: int = 30
    thresholds: Dict[str, float] = field(default_factory=dict)
    unit: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for dashboard consumption."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "query": self.query,
            "chart_type": self.chart_type,
            "refresh_interval": self.refresh_interval,
            "thresholds": self.thresholds,
            "unit": self.unit
        }


class PrometheusMonitoringDashboard:
    """
    Real-time Prometheus health monitoring dashboard.
    
    Features:
    - Real-time Prometheus service health monitoring
    - Performance metrics tracking
    - Resource usage monitoring
    - Alert integration for Prometheus failures
    - Custom dashboard panels for Prometheus metrics
    """
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9091",
        health_monitor: Optional[HealthMonitor] = None,
        alert_manager: Optional[AlertManager] = None,
        update_interval: float = 30.0
    ):
        """
        Initialize Prometheus monitoring dashboard.
        
        Args:
            prometheus_url: URL of Prometheus server
            health_monitor: HealthMonitor instance
            alert_manager: AlertManager instance
            update_interval: Dashboard update interval in seconds
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.health_monitor = health_monitor
        self.alert_manager = alert_manager
        self.update_interval = update_interval
        
        # HTTP client for Prometheus API
        self.http_client = httpx.AsyncClient(timeout=10.0)
        
        # Prometheus health checker
        self.prometheus_health = PrometheusHealthChecker()
        
        # Metrics collector
        self.metrics_collector = get_metrics_collector()
        
        # Dashboard state
        self.panels: Dict[str, PrometheusDashboardPanel] = {}
        self.current_metrics: Dict[str, PrometheusMetric] = {}
        self.last_update: Optional[datetime] = None
        
        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        self._stop_event = asyncio.Event()
        
        # Initialize dashboard panels
        self._create_dashboard_panels()
        
        # Setup Prometheus-specific alert rules
        self._setup_prometheus_alerts()
        
        logger.info(
            "Prometheus monitoring dashboard initialized",
            extra={
                "prometheus_url": prometheus_url,
                "update_interval": update_interval,
                "panels": len(self.panels)
            }
        )
    
    def _create_dashboard_panels(self) -> None:
        """Create default dashboard panels for Prometheus monitoring."""
        
        # Prometheus service health panel
        self.panels["prometheus_health"] = PrometheusDashboardPanel(
            id="prometheus_health",
            title="Prometheus Service Health",
            description="Overall health status of Prometheus service",
            query="up{job=\"prometheus\"}",
            chart_type="gauge",
            thresholds={"critical": 0.5, "warning": 0.8},
            unit="status"
        )
        
        # Prometheus uptime panel
        self.panels["prometheus_uptime"] = PrometheusDashboardPanel(
            id="prometheus_uptime",
            title="Prometheus Uptime",
            description="Prometheus service uptime percentage",
            query="avg_over_time(up{job=\"prometheus\"}[24h]) * 100",
            chart_type="gauge",
            thresholds={"critical": 95.0, "warning": 99.0},
            unit="%"
        )
        
        # Scrape targets health
        self.panels["scrape_targets"] = PrometheusDashboardPanel(
            id="scrape_targets",
            title="Scrape Targets Health",
            description="Health status of all scrape targets",
            query="up",
            chart_type="table",
            thresholds={"critical": 0.5},
            unit="status"
        )
        
        # Query performance
        self.panels["query_performance"] = PrometheusDashboardPanel(
            id="query_performance",
            title="Query Performance",
            description="Prometheus query execution time",
            query="prometheus_engine_query_duration_seconds{quantile=\"0.95\"}",
            chart_type="line",
            thresholds={"warning": 1.0, "critical": 5.0},
            unit="seconds"
        )
        
        # Storage usage
        self.panels["storage_usage"] = PrometheusDashboardPanel(
            id="storage_usage",
            title="Storage Usage",
            description="Prometheus storage disk usage",
            query="prometheus_tsdb_symbol_table_size_bytes + prometheus_tsdb_head_series",
            chart_type="line",
            thresholds={"warning": 80.0, "critical": 95.0},
            unit="bytes"
        )
        
        # Ingestion rate
        self.panels["ingestion_rate"] = PrometheusDashboardPanel(
            id="ingestion_rate",
            title="Sample Ingestion Rate",
            description="Rate of samples ingested by Prometheus",
            query="rate(prometheus_tsdb_symbol_table_size_bytes[5m])",
            chart_type="line",
            unit="samples/sec"
        )
        
        # Memory usage
        self.panels["memory_usage"] = PrometheusDashboardPanel(
            id="memory_usage",
            title="Memory Usage",
            description="Prometheus process memory usage",
            query="process_resident_memory_bytes{job=\"prometheus\"}",
            chart_type="line",
            thresholds={"warning": 1073741824, "critical": 2147483648},  # 1GB, 2GB
            unit="bytes"
        )
        
        # CPU usage
        self.panels["cpu_usage"] = PrometheusDashboardPanel(
            id="cpu_usage",
            title="CPU Usage",
            description="Prometheus process CPU usage",
            query="rate(process_cpu_seconds_total{job=\"prometheus\"}[5m]) * 100",
            chart_type="line",
            thresholds={"warning": 70.0, "critical": 90.0},
            unit="%"
        )
        
        # Configuration reload status
        self.panels["config_reload"] = PrometheusDashboardPanel(
            id="config_reload",
            title="Configuration Reload Status",
            description="Status of last configuration reload",
            query="prometheus_config_last_reload_successful",
            chart_type="gauge",
            thresholds={"critical": 0.5},
            unit="status"
        )
        
        # Rule evaluation duration
        self.panels["rule_evaluation"] = PrometheusDashboardPanel(
            id="rule_evaluation",
            title="Rule Evaluation Duration",
            description="Time taken to evaluate recording and alerting rules",
            query="prometheus_rule_evaluation_duration_seconds{quantile=\"0.95\"}",
            chart_type="line",
            thresholds={"warning": 1.0, "critical": 5.0},
            unit="seconds"
        )
        
        logger.info(f"Created {len(self.panels)} dashboard panels")
    
    def _setup_prometheus_alerts(self) -> None:
        """Setup Prometheus-specific alert rules."""
        if not self.alert_manager:
            logger.warning("No alert manager provided, skipping Prometheus alerts setup")
            return
        
        # Prometheus service down alert
        self.alert_manager.add_rule(AlertRule(
            name="prometheus_service_down",
            condition=lambda health: (
                isinstance(health, ComponentHealth) and
                health.component_name == "prometheus" and
                health.status == HealthStatus.UNHEALTHY
            ),
            severity=AlertSeverity.CRITICAL,
            message_template="Prometheus service is down: {error_message}",
            cooldown_minutes=2,
            max_alerts_per_hour=6
        ))
        
        # Prometheus high query latency alert
        self.alert_manager.add_rule(AlertRule(
            name="prometheus_high_query_latency",
            condition=lambda metrics: (
                isinstance(metrics, dict) and
                "prometheus_query_latency" in metrics and
                metrics["prometheus_query_latency"] > 5.0
            ),
            severity=AlertSeverity.HIGH,
            message_template="Prometheus query latency is high: {prometheus_query_latency:.2f}s",
            cooldown_minutes=10,
            max_alerts_per_hour=3
        ))
        
        # Prometheus scrape targets down alert
        self.alert_manager.add_rule(AlertRule(
            name="prometheus_scrape_targets_down",
            condition=lambda metrics: (
                isinstance(metrics, dict) and
                "scrape_targets_down" in metrics and
                metrics["scrape_targets_down"] > 0
            ),
            severity=AlertSeverity.HIGH,
            message_template="Prometheus has {scrape_targets_down} scrape targets down",
            cooldown_minutes=5,
            max_alerts_per_hour=4
        ))
        
        # Prometheus high memory usage alert
        self.alert_manager.add_rule(AlertRule(
            name="prometheus_high_memory_usage",
            condition=lambda metrics: (
                isinstance(metrics, dict) and
                "prometheus_memory_usage_bytes" in metrics and
                metrics["prometheus_memory_usage_bytes"] > 2147483648  # 2GB
            ),
            severity=AlertSeverity.MEDIUM,
            message_template="Prometheus memory usage is high: {prometheus_memory_usage_gb:.1f}GB",
            cooldown_minutes=15,
            max_alerts_per_hour=2
        ))
        
        # Prometheus configuration reload failed alert
        self.alert_manager.add_rule(AlertRule(
            name="prometheus_config_reload_failed",
            condition=lambda metrics: (
                isinstance(metrics, dict) and
                "prometheus_config_reload_successful" in metrics and
                metrics["prometheus_config_reload_successful"] == 0
            ),
            severity=AlertSeverity.HIGH,
            message_template="Prometheus configuration reload failed",
            cooldown_minutes=5,
            max_alerts_per_hour=3
        ))
        
        logger.info("Setup Prometheus-specific alert rules")
    
    async def query_prometheus(self, query: str, time_range: Optional[str] = None) -> Dict[str, Any]:
        """
        Query Prometheus API.
        
        Args:
            query: PromQL query string
            time_range: Optional time range for range queries
            
        Returns:
            Query result from Prometheus API
        """
        try:
            if time_range:
                # Range query
                url = f"{self.prometheus_url}/api/v1/query_range"
                params = {
                    "query": query,
                    "start": time_range,
                    "end": "now",
                    "step": "30s"
                }
            else:
                # Instant query
                url = f"{self.prometheus_url}/api/v1/query"
                params = {"query": query}
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") != "success":
                logger.error(f"Prometheus query failed: {result.get('error', 'Unknown error')}")
                return {"status": "error", "error": result.get("error", "Unknown error")}
            
            return result
            
        except httpx.RequestError as e:
            logger.error(f"Failed to query Prometheus: {e}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error querying Prometheus: {e}")
            return {"status": "error", "error": str(e)}
    
    async def update_panel_metrics(self, panel_id: str) -> Optional[PrometheusMetric]:
        """
        Update metrics for a specific dashboard panel.
        
        Args:
            panel_id: ID of panel to update
            
        Returns:
            Updated PrometheusMetric or None if failed
        """
        if panel_id not in self.panels:
            logger.error(f"Panel not found: {panel_id}")
            return None
        
        panel = self.panels[panel_id]
        
        try:
            # Query Prometheus for panel data
            result = await self.query_prometheus(panel.query)
            
            if result.get("status") == "error":
                logger.error(f"Failed to query panel {panel_id}: {result.get('error')}")
                return None
            
            data = result.get("data", {})
            result_type = data.get("resultType")
            results = data.get("result", [])
            
            if not results:
                logger.warning(f"No data returned for panel {panel_id}")
                return None
            
            # Extract metric value based on result type
            if result_type == "vector":
                # Instant vector - take first result
                first_result = results[0]
                value = float(first_result["value"][1])
                labels = first_result.get("metric", {})
            elif result_type == "matrix":
                # Range vector - take latest value from first series
                first_result = results[0]
                values = first_result.get("values", [])
                if values:
                    value = float(values[-1][1])
                    labels = first_result.get("metric", {})
                else:
                    logger.warning(f"No values in matrix result for panel {panel_id}")
                    return None
            else:
                logger.error(f"Unsupported result type for panel {panel_id}: {result_type}")
                return None
            
            # Create metric object
            metric = PrometheusMetric(
                name=panel_id,
                value=value,
                timestamp=datetime.now(UTC),
                labels=labels,
                help_text=panel.description,
                metric_type=panel.chart_type
            )
            
            # Store current metric
            self.current_metrics[panel_id] = metric
            
            # Update internal metrics
            self.metrics_collector.set_gauge(
                f"prometheus_dashboard_{panel_id}",
                value,
                labels={"panel": panel_id, **labels}
            )
            
            logger.debug(f"Updated panel {panel_id}: {value} {panel.unit}")
            
            return metric
            
        except Exception as e:
            logger.error(f"Error updating panel {panel_id}: {e}")
            return None
    
    async def update_all_panels(self) -> Dict[str, PrometheusMetric]:
        """
        Update all dashboard panels.
        
        Returns:
            Dictionary of updated metrics by panel ID
        """
        start_time = time.time()
        
        # Update all panels concurrently
        update_tasks = {
            panel_id: self.update_panel_metrics(panel_id)
            for panel_id in self.panels.keys()
        }
        
        updated_metrics = {}
        for panel_id, task in update_tasks.items():
            try:
                metric = await task
                if metric:
                    updated_metrics[panel_id] = metric
            except Exception as e:
                logger.error(f"Failed to update panel {panel_id}: {e}")
        
        update_duration = (time.time() - start_time) * 1000
        self.last_update = datetime.now(UTC)
        
        # Update dashboard-level metrics
        self.metrics_collector.set_gauge("prometheus_dashboard_panels_updated", len(updated_metrics))
        self.metrics_collector.record_histogram("prometheus_dashboard_update_duration_ms", update_duration)
        
        logger.info(
            f"Updated {len(updated_metrics)}/{len(self.panels)} dashboard panels",
            extra={"duration_ms": update_duration}
        )
        
        return updated_metrics
    
    async def check_prometheus_health(self) -> ComponentHealth:
        """
        Check Prometheus service health.
        
        Returns:
            ComponentHealth for Prometheus service
        """
        start_time = time.time()
        
        try:
            # Check if Prometheus is responding
            response = await self.http_client.get(f"{self.prometheus_url}/-/healthy", timeout=5.0)
            
            if response.status_code == 200:
                # Get additional health metrics
                metrics_result = await self.query_prometheus("up{job=\"prometheus\"}")
                
                response_time_ms = (time.time() - start_time) * 1000
                
                if metrics_result.get("status") == "success":
                    data = metrics_result.get("data", {})
                    results = data.get("result", [])
                    
                    if results and float(results[0]["value"][1]) == 1.0:
                        status = HealthStatus.HEALTHY
                        success_rate = 100.0
                        error_message = None
                    else:
                        status = HealthStatus.DEGRADED
                        success_rate = 50.0
                        error_message = "Prometheus metrics indicate service issues"
                else:
                    status = HealthStatus.DEGRADED
                    success_rate = 75.0
                    error_message = "Prometheus API queries failing"
                
                details = {
                    "api_accessible": True,
                    "metrics_queryable": metrics_result.get("status") == "success",
                    "prometheus_url": self.prometheus_url
                }
                
            else:
                status = HealthStatus.UNHEALTHY
                success_rate = 0.0
                error_message = f"Prometheus health endpoint returned HTTP {response.status_code}"
                details = {"api_accessible": False, "http_status": response.status_code}
                response_time_ms = (time.time() - start_time) * 1000
                
        except httpx.RequestError as e:
            status = HealthStatus.UNHEALTHY
            success_rate = 0.0
            error_message = f"Cannot connect to Prometheus: {str(e)}"
            details = {"api_accessible": False, "connection_error": str(e)}
            response_time_ms = (time.time() - start_time) * 1000
            
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            success_rate = 0.0
            error_message = f"Prometheus health check failed: {str(e)}"
            details = {"api_accessible": False, "error": str(e)}
            response_time_ms = (time.time() - start_time) * 1000
        
        health = ComponentHealth(
            component_type=ComponentType.SYSTEM,
            component_name="prometheus",
            status=status,
            last_check=datetime.now(UTC),
            response_time_ms=response_time_ms,
            success_rate=success_rate,
            error_rate=100.0 - success_rate,
            details=details,
            error_message=error_message
        )
        
        # Register with health monitor if available
        if self.health_monitor:
            self.health_monitor.component_health["prometheus"] = health
        
        return health
    
    async def get_scrape_targets_status(self) -> Dict[str, Any]:
        """
        Get status of all Prometheus scrape targets.
        
        Returns:
            Dictionary with scrape targets status information
        """
        try:
            # Query all targets
            result = await self.query_prometheus("up")
            
            if result.get("status") != "success":
                return {"error": "Failed to query scrape targets"}
            
            data = result.get("data", {})
            results = data.get("result", [])
            
            targets_status = {
                "total_targets": len(results),
                "healthy_targets": 0,
                "unhealthy_targets": 0,
                "targets": []
            }
            
            for target_result in results:
                labels = target_result.get("metric", {})
                value = float(target_result["value"][1])
                
                target_info = {
                    "job": labels.get("job", "unknown"),
                    "instance": labels.get("instance", "unknown"),
                    "status": "up" if value == 1.0 else "down",
                    "labels": labels
                }
                
                targets_status["targets"].append(target_info)
                
                if value == 1.0:
                    targets_status["healthy_targets"] += 1
                else:
                    targets_status["unhealthy_targets"] += 1
            
            targets_status["health_percentage"] = (
                (targets_status["healthy_targets"] / max(1, targets_status["total_targets"])) * 100
            )
            
            return targets_status
            
        except Exception as e:
            logger.error(f"Error getting scrape targets status: {e}")
            return {"error": str(e)}
    
    async def evaluate_prometheus_alerts(self) -> None:
        """Evaluate Prometheus-specific alert conditions."""
        if not self.alert_manager:
            return
        
        try:
            # Check Prometheus health
            prometheus_health = await self.check_prometheus_health()
            await self.alert_manager.evaluate_rules(prometheus_health)
            
            # Collect metrics for alert evaluation
            alert_metrics = {}
            
            # Query latency metric
            latency_result = await self.query_prometheus(
                "prometheus_engine_query_duration_seconds{quantile=\"0.95\"}"
            )
            if latency_result.get("status") == "success":
                data = latency_result.get("data", {})
                results = data.get("result", [])
                if results:
                    alert_metrics["prometheus_query_latency"] = float(results[0]["value"][1])
            
            # Scrape targets status
            targets_status = await self.get_scrape_targets_status()
            if "unhealthy_targets" in targets_status:
                alert_metrics["scrape_targets_down"] = targets_status["unhealthy_targets"]
            
            # Memory usage
            memory_result = await self.query_prometheus("process_resident_memory_bytes{job=\"prometheus\"}")
            if memory_result.get("status") == "success":
                data = memory_result.get("data", {})
                results = data.get("result", [])
                if results:
                    memory_bytes = float(results[0]["value"][1])
                    alert_metrics["prometheus_memory_usage_bytes"] = memory_bytes
                    alert_metrics["prometheus_memory_usage_gb"] = memory_bytes / (1024**3)
            
            # Configuration reload status
            config_result = await self.query_prometheus("prometheus_config_last_reload_successful")
            if config_result.get("status") == "success":
                data = config_result.get("data", {})
                results = data.get("result", [])
                if results:
                    alert_metrics["prometheus_config_reload_successful"] = float(results[0]["value"][1])
            
            # Evaluate alert rules with collected metrics
            await self.alert_manager.evaluate_rules(alert_metrics)
            
        except Exception as e:
            logger.error(f"Error evaluating Prometheus alerts: {e}")
    
    async def start_monitoring(self) -> None:
        """Start real-time Prometheus monitoring."""
        if self.is_monitoring:
            logger.warning("Prometheus monitoring is already running")
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(
            f"Started Prometheus monitoring with {self.update_interval}s interval",
            extra={"prometheus_url": self.prometheus_url}
        )
    
    async def stop_monitoring(self) -> None:
        """Stop real-time Prometheus monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        logger.info("Stopped Prometheus monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring and not self._stop_event.is_set():
            try:
                # Update dashboard panels
                await self.update_all_panels()
                
                # Evaluate alerts
                await self.evaluate_prometheus_alerts()
                
                # Wait for next update interval
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.update_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    continue  # Continue monitoring
                    
            except Exception as e:
                logger.error(f"Error in Prometheus monitoring loop: {e}")
                await asyncio.sleep(min(self.update_interval, 60))
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get current dashboard data.
        
        Returns:
            Complete dashboard data for frontend consumption
        """
        return {
            "title": "Prometheus Health Monitoring",
            "description": "Real-time monitoring of Prometheus service health and performance",
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "panels": {
                panel_id: {
                    **panel.to_dict(),
                    "current_value": self.current_metrics[panel_id].value if panel_id in self.current_metrics else None,
                    "current_timestamp": self.current_metrics[panel_id].timestamp.isoformat() if panel_id in self.current_metrics else None,
                    "labels": self.current_metrics[panel_id].labels if panel_id in self.current_metrics else {}
                }
                for panel_id, panel in self.panels.items()
            },
            "summary": {
                "total_panels": len(self.panels),
                "updated_panels": len(self.current_metrics),
                "prometheus_url": self.prometheus_url,
                "monitoring_active": self.is_monitoring
            }
        }
    
    async def close(self) -> None:
        """Close dashboard and cleanup resources."""
        await self.stop_monitoring()
        await self.http_client.aclose()
        logger.info("Prometheus monitoring dashboard closed")
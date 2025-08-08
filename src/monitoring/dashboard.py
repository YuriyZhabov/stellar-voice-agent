"""Dashboard-ready metrics and visualization system for monitoring tools."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from src.config import get_settings
from src.metrics import get_metrics_collector
from src.monitoring.health_monitor import HealthMonitor, SystemHealth, ComponentHealth, HealthStatus
from src.monitoring.alerting import AlertManager, Alert, AlertSeverity


logger = logging.getLogger(__name__)


@dataclass
class DashboardMetric:
    """Individual dashboard metric with visualization metadata."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    chart_type: str = "gauge"  # gauge, line, bar, pie
    color: str = "blue"
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for dashboard consumption."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "chart_type": self.chart_type,
            "color": self.color,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "labels": self.labels,
            "metadata": self.metadata
        }


@dataclass
class DashboardPanel:
    """Dashboard panel containing related metrics."""
    id: str
    title: str
    description: str
    metrics: List[DashboardMetric]
    panel_type: str = "metrics"  # metrics, chart, table, alert
    layout: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for dashboard consumption."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "panel_type": self.panel_type,
            "layout": self.layout,
            "metrics": [m.to_dict() for m in self.metrics],
            "last_updated": datetime.now(UTC).isoformat()
        }


@dataclass
class Dashboard:
    """Complete dashboard configuration."""
    id: str
    title: str
    description: str
    panels: List[DashboardPanel]
    refresh_interval: int = 30  # seconds
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for dashboard consumption."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "refresh_interval": self.refresh_interval,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "panels": [p.to_dict() for p in self.panels]
        }


class DashboardManager:
    """
    Dashboard-ready metrics system for monitoring tools.
    
    Features:
    - Real-time metrics aggregation for dashboards
    - Pre-configured dashboard templates
    - Health status visualization
    - Alert integration
    - Performance metrics tracking
    - Cost and usage analytics
    - Custom dashboard creation
    """
    
    def __init__(
        self,
        health_monitor: HealthMonitor,
        alert_manager: AlertManager,
        update_interval: float = 30.0
    ):
        """
        Initialize dashboard manager.
        
        Args:
            health_monitor: HealthMonitor instance
            alert_manager: AlertManager instance
            update_interval: Interval between dashboard updates
        """
        self.health_monitor = health_monitor
        self.alert_manager = alert_manager
        self.update_interval = update_interval
        
        # Metrics collection
        self.metrics_collector = get_metrics_collector()
        
        # Dashboard storage
        self.dashboards: Dict[str, Dashboard] = {}
        
        # Metrics history for trending
        self.metrics_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.max_history_points = 1000
        
        # Update task
        self.update_task: Optional[asyncio.Task] = None
        self.is_updating = False
        self._stop_event = asyncio.Event()
        
        # Initialize default dashboards
        self._create_default_dashboards()
        
        logger.info(
            "Dashboard manager initialized",
            extra={"update_interval": update_interval}
        )
    
    def _create_default_dashboards(self) -> None:
        """Create default dashboard templates."""
        
        # System Overview Dashboard
        system_dashboard = Dashboard(
            id="system_overview",
            title="System Overview",
            description="High-level system health and performance metrics",
            panels=[
                DashboardPanel(
                    id="system_health",
                    title="System Health",
                    description="Overall system health status",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 6, "height": 4}
                ),
                DashboardPanel(
                    id="component_status",
                    title="Component Status",
                    description="Individual component health status",
                    metrics=[],
                    panel_type="table",
                    layout={"width": 6, "height": 4}
                ),
                DashboardPanel(
                    id="active_alerts",
                    title="Active Alerts",
                    description="Current system alerts",
                    metrics=[],
                    panel_type="alert",
                    layout={"width": 12, "height": 3}
                ),
                DashboardPanel(
                    id="performance_metrics",
                    title="Performance Metrics",
                    description="System performance indicators",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 12, "height": 6}
                )
            ]
        )
        
        # API Performance Dashboard
        api_dashboard = Dashboard(
            id="api_performance",
            title="API Performance",
            description="API usage, latency, and error metrics",
            panels=[
                DashboardPanel(
                    id="api_requests",
                    title="API Requests",
                    description="Request volume and rate",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 6, "height": 4}
                ),
                DashboardPanel(
                    id="api_latency",
                    title="API Latency",
                    description="Response time distribution",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 6, "height": 4}
                ),
                DashboardPanel(
                    id="api_errors",
                    title="API Errors",
                    description="Error rates and types",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 6, "height": 4}
                ),
                DashboardPanel(
                    id="api_endpoints",
                    title="Endpoint Performance",
                    description="Per-endpoint metrics",
                    metrics=[],
                    panel_type="table",
                    layout={"width": 6, "height": 4}
                )
            ]
        )
        
        # AI Services Dashboard
        ai_dashboard = Dashboard(
            id="ai_services",
            title="AI Services",
            description="STT, LLM, and TTS service metrics",
            panels=[
                DashboardPanel(
                    id="stt_metrics",
                    title="Speech-to-Text",
                    description="STT service performance",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="llm_metrics",
                    title="Language Model",
                    description="LLM service performance",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="tts_metrics",
                    title="Text-to-Speech",
                    description="TTS service performance",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="ai_costs",
                    title="AI Service Costs",
                    description="Usage costs and trends",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 12, "height": 4}
                )
            ]
        )
        
        # Infrastructure Dashboard
        infra_dashboard = Dashboard(
            id="infrastructure",
            title="Infrastructure",
            description="System resources and infrastructure metrics",
            panels=[
                DashboardPanel(
                    id="system_resources",
                    title="System Resources",
                    description="CPU, memory, and disk usage",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 8, "height": 4}
                ),
                DashboardPanel(
                    id="database_metrics",
                    title="Database",
                    description="Database performance metrics",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="redis_metrics",
                    title="Redis Cache",
                    description="Redis performance metrics",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="livekit_metrics",
                    title="LiveKit",
                    description="LiveKit service metrics",
                    metrics=[],
                    panel_type="metrics",
                    layout={"width": 4, "height": 4}
                ),
                DashboardPanel(
                    id="network_metrics",
                    title="Network",
                    description="Network usage and connectivity",
                    metrics=[],
                    panel_type="chart",
                    layout={"width": 4, "height": 4}
                )
            ]
        )
        
        # Store dashboards
        self.dashboards = {
            "system_overview": system_dashboard,
            "api_performance": api_dashboard,
            "ai_services": ai_dashboard,
            "infrastructure": infra_dashboard
        }
        
        logger.info(f"Created {len(self.dashboards)} default dashboards")
    
    async def update_all_dashboards(self) -> None:
        """Update all dashboard metrics."""
        for dashboard_id in self.dashboards.keys():
            try:
                await self.update_dashboard(dashboard_id)
            except Exception as e:
                logger.error(f"Failed to update dashboard {dashboard_id}: {e}")
    
    async def update_dashboard(self, dashboard_id: str) -> None:
        """Update specific dashboard metrics."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard not found: {dashboard_id}")
        
        dashboard = self.dashboards[dashboard_id]
        
        # Update each panel
        for panel in dashboard.panels:
            await self._update_panel(panel)
        
        dashboard.updated_at = datetime.now(UTC)
        
        logger.debug(f"Updated dashboard: {dashboard_id}")
    
    async def _update_panel(self, panel: DashboardPanel) -> None:
        """Update individual panel metrics."""
        panel.metrics.clear()
        
        if panel.id == "system_health":
            await self._update_system_health_panel(panel)
        elif panel.id == "component_status":
            await self._update_component_status_panel(panel)
        elif panel.id == "active_alerts":
            await self._update_active_alerts_panel(panel)
        elif panel.id == "performance_metrics":
            await self._update_performance_metrics_panel(panel)
        elif panel.id == "api_requests":
            await self._update_api_requests_panel(panel)
        elif panel.id == "api_latency":
            await self._update_api_latency_panel(panel)
        elif panel.id == "api_errors":
            await self._update_api_errors_panel(panel)
        elif panel.id == "api_endpoints":
            await self._update_api_endpoints_panel(panel)
        elif panel.id in ["stt_metrics", "llm_metrics", "tts_metrics"]:
            await self._update_ai_service_panel(panel)
        elif panel.id == "ai_costs":
            await self._update_ai_costs_panel(panel)
        elif panel.id == "system_resources":
            await self._update_system_resources_panel(panel)
        elif panel.id in ["database_metrics", "redis_metrics", "livekit_metrics"]:
            await self._update_infrastructure_panel(panel)
        elif panel.id == "network_metrics":
            await self._update_network_metrics_panel(panel)
    
    async def _update_system_health_panel(self, panel: DashboardPanel) -> None:
        """Update system health panel."""
        system_health = self.health_monitor.get_system_health()
        
        if system_health:
            # Overall health percentage
            panel.metrics.append(DashboardMetric(
                name="system_health_percentage",
                value=system_health.health_percentage,
                unit="%",
                timestamp=system_health.last_check,
                chart_type="gauge",
                color="green" if system_health.health_percentage > 80 else "yellow" if system_health.health_percentage > 60 else "red",
                threshold_warning=80.0,
                threshold_critical=60.0
            ))
            
            # Component counts
            panel.metrics.extend([
                DashboardMetric(
                    name="healthy_components",
                    value=system_health.healthy_components,
                    unit="count",
                    timestamp=system_health.last_check,
                    chart_type="gauge",
                    color="green"
                ),
                DashboardMetric(
                    name="total_components",
                    value=system_health.total_components,
                    unit="count",
                    timestamp=system_health.last_check,
                    chart_type="gauge",
                    color="blue"
                )
            ])
    
    async def _update_component_status_panel(self, panel: DashboardPanel) -> None:
        """Update component status panel."""
        all_health = self.health_monitor.get_all_component_health()
        
        for component_name, health in all_health.items():
            status_value = {
                HealthStatus.HEALTHY: 1.0,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0.0,
                HealthStatus.UNKNOWN: -1.0
            }.get(health.status, 0.0)
            
            panel.metrics.extend([
                DashboardMetric(
                    name=f"{component_name}_status",
                    value=status_value,
                    unit="status",
                    timestamp=health.last_check,
                    chart_type="gauge",
                    color="green" if status_value == 1.0 else "yellow" if status_value == 0.5 else "red",
                    labels={"component": component_name, "type": health.component_type.value}
                ),
                DashboardMetric(
                    name=f"{component_name}_response_time",
                    value=health.response_time_ms,
                    unit="ms",
                    timestamp=health.last_check,
                    chart_type="line",
                    color="blue",
                    threshold_warning=1000.0,
                    threshold_critical=5000.0,
                    labels={"component": component_name}
                )
            ])
    
    async def _update_active_alerts_panel(self, panel: DashboardPanel) -> None:
        """Update active alerts panel."""
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Alert counts by severity
        severity_counts = {}
        for severity in AlertSeverity:
            count = len([a for a in active_alerts if a.severity == severity])
            severity_counts[severity.value] = count
            
            panel.metrics.append(DashboardMetric(
                name=f"alerts_{severity.value}",
                value=count,
                unit="count",
                timestamp=datetime.now(UTC),
                chart_type="gauge",
                color="red" if severity == AlertSeverity.CRITICAL else "orange" if severity == AlertSeverity.HIGH else "yellow",
                labels={"severity": severity.value}
            ))
        
        # Total active alerts
        panel.metrics.append(DashboardMetric(
            name="total_active_alerts",
            value=len(active_alerts),
            unit="count",
            timestamp=datetime.now(UTC),
            chart_type="gauge",
            color="red" if len(active_alerts) > 0 else "green"
        ))
    
    async def _update_performance_metrics_panel(self, panel: DashboardPanel) -> None:
        """Update performance metrics panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Extract key performance metrics
        for metric_name, metric_data in all_metrics.items():
            if "response_time" in metric_name or "latency" in metric_name:
                if metric_data["type"] in ["histogram", "timer"]:
                    stats = metric_data["stats"]
                    panel.metrics.extend([
                        DashboardMetric(
                            name=f"{metric_name}_avg",
                            value=stats["avg"],
                            unit="ms",
                            timestamp=datetime.now(UTC),
                            chart_type="line",
                            color="blue",
                            labels=metric_data.get("labels", {})
                        ),
                        DashboardMetric(
                            name=f"{metric_name}_p95",
                            value=stats["p95"],
                            unit="ms",
                            timestamp=datetime.now(UTC),
                            chart_type="line",
                            color="orange",
                            labels=metric_data.get("labels", {})
                        )
                    ])
            elif "throughput" in metric_name or "requests" in metric_name:
                if metric_data["type"] == "counter":
                    panel.metrics.append(DashboardMetric(
                        name=metric_name,
                        value=metric_data["value"],
                        unit="count",
                        timestamp=datetime.now(UTC),
                        chart_type="line",
                        color="green",
                        labels=metric_data.get("labels", {})
                    ))
    
    async def _update_api_requests_panel(self, panel: DashboardPanel) -> None:
        """Update API requests panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Request volume metrics
        for metric_name, metric_data in all_metrics.items():
            if "api_request" in metric_name and metric_data["type"] == "counter":
                panel.metrics.append(DashboardMetric(
                    name=metric_name,
                    value=metric_data["value"],
                    unit="requests",
                    timestamp=datetime.now(UTC),
                    chart_type="line",
                    color="blue",
                    labels=metric_data.get("labels", {})
                ))
    
    async def _update_api_latency_panel(self, panel: DashboardPanel) -> None:
        """Update API latency panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Latency metrics
        for metric_name, metric_data in all_metrics.items():
            if "api_latency" in metric_name and metric_data["type"] in ["histogram", "timer"]:
                stats = metric_data["stats"]
                panel.metrics.extend([
                    DashboardMetric(
                        name=f"{metric_name}_p50",
                        value=stats["p50"],
                        unit="ms",
                        timestamp=datetime.now(UTC),
                        chart_type="line",
                        color="green",
                        labels=metric_data.get("labels", {})
                    ),
                    DashboardMetric(
                        name=f"{metric_name}_p95",
                        value=stats["p95"],
                        unit="ms",
                        timestamp=datetime.now(UTC),
                        chart_type="line",
                        color="orange",
                        labels=metric_data.get("labels", {})
                    ),
                    DashboardMetric(
                        name=f"{metric_name}_p99",
                        value=stats["p99"],
                        unit="ms",
                        timestamp=datetime.now(UTC),
                        chart_type="line",
                        color="red",
                        labels=metric_data.get("labels", {})
                    )
                ])
    
    async def _update_api_errors_panel(self, panel: DashboardPanel) -> None:
        """Update API errors panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Error metrics
        for metric_name, metric_data in all_metrics.items():
            if "error" in metric_name and metric_data["type"] == "counter":
                panel.metrics.append(DashboardMetric(
                    name=metric_name,
                    value=metric_data["value"],
                    unit="errors",
                    timestamp=datetime.now(UTC),
                    chart_type="line",
                    color="red",
                    labels=metric_data.get("labels", {})
                ))
    
    async def _update_api_endpoints_panel(self, panel: DashboardPanel) -> None:
        """Update API endpoints panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Group metrics by endpoint
        endpoint_metrics = {}
        for metric_name, metric_data in all_metrics.items():
            labels = metric_data.get("labels", {})
            endpoint = labels.get("endpoint", "unknown")
            
            if endpoint not in endpoint_metrics:
                endpoint_metrics[endpoint] = {}
            
            if "request" in metric_name:
                endpoint_metrics[endpoint]["requests"] = metric_data["value"]
            elif "latency" in metric_name and metric_data["type"] in ["histogram", "timer"]:
                endpoint_metrics[endpoint]["avg_latency"] = metric_data["stats"]["avg"]
            elif "error" in metric_name:
                endpoint_metrics[endpoint]["errors"] = metric_data["value"]
        
        # Create metrics for each endpoint
        for endpoint, metrics in endpoint_metrics.items():
            for metric_type, value in metrics.items():
                panel.metrics.append(DashboardMetric(
                    name=f"endpoint_{metric_type}",
                    value=value,
                    unit="count" if metric_type in ["requests", "errors"] else "ms",
                    timestamp=datetime.now(UTC),
                    chart_type="bar",
                    color="blue" if metric_type == "requests" else "red" if metric_type == "errors" else "green",
                    labels={"endpoint": endpoint}
                ))
    
    async def _update_ai_service_panel(self, panel: DashboardPanel) -> None:
        """Update AI service panel."""
        service_type = panel.id.replace("_metrics", "")
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Service-specific metrics
        for metric_name, metric_data in all_metrics.items():
            if service_type in metric_name:
                if metric_data["type"] == "counter":
                    panel.metrics.append(DashboardMetric(
                        name=metric_name,
                        value=metric_data["value"],
                        unit="count",
                        timestamp=datetime.now(UTC),
                        chart_type="gauge",
                        color="blue",
                        labels=metric_data.get("labels", {})
                    ))
                elif metric_data["type"] in ["histogram", "timer"]:
                    stats = metric_data["stats"]
                    panel.metrics.append(DashboardMetric(
                        name=f"{metric_name}_avg",
                        value=stats["avg"],
                        unit="ms",
                        timestamp=datetime.now(UTC),
                        chart_type="gauge",
                        color="green",
                        labels=metric_data.get("labels", {})
                    ))
    
    async def _update_ai_costs_panel(self, panel: DashboardPanel) -> None:
        """Update AI costs panel."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Cost-related metrics
        for metric_name, metric_data in all_metrics.items():
            if "cost" in metric_name or "usage" in metric_name:
                panel.metrics.append(DashboardMetric(
                    name=metric_name,
                    value=metric_data["value"],
                    unit="USD" if "cost" in metric_name else "tokens",
                    timestamp=datetime.now(UTC),
                    chart_type="line",
                    color="purple",
                    labels=metric_data.get("labels", {})
                ))
    
    async def _update_system_resources_panel(self, panel: DashboardPanel) -> None:
        """Update system resources panel."""
        import psutil
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        panel.metrics.append(DashboardMetric(
            name="cpu_usage",
            value=cpu_percent,
            unit="%",
            timestamp=datetime.now(UTC),
            chart_type="gauge",
            color="green" if cpu_percent < 70 else "yellow" if cpu_percent < 90 else "red",
            threshold_warning=70.0,
            threshold_critical=90.0
        ))
        
        # Memory usage
        memory = psutil.virtual_memory()
        panel.metrics.extend([
            DashboardMetric(
                name="memory_usage",
                value=memory.percent,
                unit="%",
                timestamp=datetime.now(UTC),
                chart_type="gauge",
                color="green" if memory.percent < 80 else "yellow" if memory.percent < 95 else "red",
                threshold_warning=80.0,
                threshold_critical=95.0
            ),
            DashboardMetric(
                name="memory_available",
                value=memory.available / (1024**3),  # GB
                unit="GB",
                timestamp=datetime.now(UTC),
                chart_type="gauge",
                color="blue"
            )
        ])
        
        # Disk usage
        disk = psutil.disk_usage('/')
        panel.metrics.extend([
            DashboardMetric(
                name="disk_usage",
                value=(disk.used / disk.total) * 100,
                unit="%",
                timestamp=datetime.now(UTC),
                chart_type="gauge",
                color="green" if (disk.used / disk.total) < 0.8 else "yellow" if (disk.used / disk.total) < 0.95 else "red",
                threshold_warning=80.0,
                threshold_critical=95.0
            ),
            DashboardMetric(
                name="disk_free",
                value=disk.free / (1024**3),  # GB
                unit="GB",
                timestamp=datetime.now(UTC),
                chart_type="gauge",
                color="blue"
            )
        ])
    
    async def _update_infrastructure_panel(self, panel: DashboardPanel) -> None:
        """Update infrastructure component panel."""
        service_name = panel.id.replace("_metrics", "")
        
        # Get component health
        component_health = self.health_monitor.get_component_health(service_name)
        if component_health:
            panel.metrics.extend([
                DashboardMetric(
                    name=f"{service_name}_status",
                    value=1.0 if component_health.status == HealthStatus.HEALTHY else 0.0,
                    unit="status",
                    timestamp=component_health.last_check,
                    chart_type="gauge",
                    color="green" if component_health.status == HealthStatus.HEALTHY else "red"
                ),
                DashboardMetric(
                    name=f"{service_name}_response_time",
                    value=component_health.response_time_ms,
                    unit="ms",
                    timestamp=component_health.last_check,
                    chart_type="gauge",
                    color="blue",
                    threshold_warning=1000.0,
                    threshold_critical=5000.0
                )
            ])
    
    async def _update_network_metrics_panel(self, panel: DashboardPanel) -> None:
        """Update network metrics panel."""
        import psutil
        
        # Network I/O
        net_io = psutil.net_io_counters()
        panel.metrics.extend([
            DashboardMetric(
                name="network_bytes_sent",
                value=net_io.bytes_sent / (1024**2),  # MB
                unit="MB",
                timestamp=datetime.now(UTC),
                chart_type="line",
                color="blue"
            ),
            DashboardMetric(
                name="network_bytes_recv",
                value=net_io.bytes_recv / (1024**2),  # MB
                unit="MB",
                timestamp=datetime.now(UTC),
                chart_type="line",
                color="green"
            ),
            DashboardMetric(
                name="network_packets_sent",
                value=net_io.packets_sent,
                unit="packets",
                timestamp=datetime.now(UTC),
                chart_type="line",
                color="orange"
            ),
            DashboardMetric(
                name="network_packets_recv",
                value=net_io.packets_recv,
                unit="packets",
                timestamp=datetime.now(UTC),
                chart_type="line",
                color="purple"
            )
        ])
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get dashboard by ID."""
        return self.dashboards.get(dashboard_id)
    
    def get_all_dashboards(self) -> Dict[str, Dashboard]:
        """Get all dashboards."""
        return self.dashboards.copy()
    
    def create_custom_dashboard(
        self,
        dashboard_id: str,
        title: str,
        description: str,
        panels: List[DashboardPanel]
    ) -> Dashboard:
        """Create custom dashboard."""
        dashboard = Dashboard(
            id=dashboard_id,
            title=title,
            description=description,
            panels=panels
        )
        
        self.dashboards[dashboard_id] = dashboard
        
        logger.info(f"Created custom dashboard: {dashboard_id}")
        return dashboard
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete dashboard."""
        if dashboard_id in self.dashboards:
            del self.dashboards[dashboard_id]
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
        return False
    
    async def export_dashboard_data(self, dashboard_id: str) -> Dict[str, Any]:
        """Export dashboard data for external consumption."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard not found: {dashboard_id}")
        
        await self.update_dashboard(dashboard_id)
        dashboard = self.dashboards[dashboard_id]
        
        return dashboard.to_dict()
    
    async def start_updating(self) -> None:
        """Start automatic dashboard updates."""
        if self.is_updating:
            logger.warning("Dashboard updates are already running")
            return
        
        self.is_updating = True
        self._stop_event.clear()
        
        self.update_task = asyncio.create_task(self._update_loop())
        
        logger.info(f"Started dashboard updates with {self.update_interval}s interval")
    
    async def stop_updating(self) -> None:
        """Stop automatic dashboard updates."""
        if not self.is_updating:
            return
        
        self.is_updating = False
        self._stop_event.set()
        
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
            self.update_task = None
        
        logger.info("Stopped dashboard updates")
    
    async def _update_loop(self) -> None:
        """Main dashboard update loop."""
        while self.is_updating and not self._stop_event.is_set():
            try:
                await self.update_all_dashboards()
                
                # Wait for next update interval
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.update_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    continue  # Continue updating
                    
            except Exception as e:
                logger.error(f"Error in dashboard update loop: {e}")
                await asyncio.sleep(min(self.update_interval, 60))
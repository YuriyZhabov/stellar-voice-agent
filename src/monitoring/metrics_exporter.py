"""Metrics export system for dashboard-ready monitoring tools."""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import httpx

from src.config import get_settings
from src.metrics import get_metrics_collector


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram, timer
    
    def to_prometheus_format(self) -> str:
        """Convert to Prometheus exposition format."""
        label_str = ""
        if self.labels:
            label_pairs = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"
        
        return f"{self.name}{label_str} {self.value} {int(self.timestamp * 1000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels,
            "type": self.metric_type
        }


@dataclass
class MetricsSnapshot:
    """Snapshot of all metrics at a point in time."""
    timestamp: datetime
    metrics: List[MetricPoint]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics],
            "metadata": self.metadata
        }


class MetricsExporter(ABC):
    """Abstract base class for metrics exporters."""
    
    @abstractmethod
    async def export_metrics(self, snapshot: MetricsSnapshot) -> bool:
        """
        Export metrics snapshot.
        
        Args:
            snapshot: Metrics snapshot to export
            
        Returns:
            True if export was successful
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if exporter is healthy."""
        pass


class PrometheusExporter(MetricsExporter):
    """
    Prometheus metrics exporter.
    
    Exports metrics in Prometheus exposition format for scraping
    or pushes to Prometheus Pushgateway.
    """
    
    def __init__(
        self,
        pushgateway_url: Optional[str] = None,
        job_name: str = "voice_ai_agent",
        instance_name: Optional[str] = None,
        push_interval: float = 15.0,
        timeout: float = 10.0
    ):
        """
        Initialize Prometheus exporter.
        
        Args:
            pushgateway_url: URL of Prometheus Pushgateway (optional)
            job_name: Job name for metrics
            instance_name: Instance name for metrics
            push_interval: Interval between pushes in seconds
            timeout: HTTP timeout for pushes
        """
        self.pushgateway_url = pushgateway_url
        self.job_name = job_name
        self.instance_name = instance_name or f"voice_ai_agent_{int(time.time())}"
        self.push_interval = push_interval
        self.timeout = timeout
        
        # HTTP client for pushing metrics
        self.http_client = httpx.AsyncClient(timeout=timeout)
        
        # Metrics registry for exposition
        self.metrics_registry: Dict[str, MetricPoint] = {}
        
        # Push task management
        self.push_task: Optional[asyncio.Task] = None
        self.is_pushing = False
        self._stop_event = asyncio.Event()
        
        logger.info(
            "Prometheus exporter initialized",
            extra={
                "pushgateway_url": pushgateway_url,
                "job_name": job_name,
                "instance_name": self.instance_name
            }
        )
    
    async def export_metrics(self, snapshot: MetricsSnapshot) -> bool:
        """Export metrics snapshot to Prometheus."""
        try:
            # Update metrics registry
            for metric in snapshot.metrics:
                key = f"{metric.name}_{hash(frozenset(metric.labels.items()))}"
                self.metrics_registry[key] = metric
            
            # If pushgateway is configured, push metrics
            if self.pushgateway_url:
                return await self._push_to_gateway(snapshot)
            
            # Otherwise, just update registry for scraping
            return True
            
        except Exception as e:
            logger.error(f"Failed to export metrics to Prometheus: {e}")
            return False
    
    async def _push_to_gateway(self, snapshot: MetricsSnapshot) -> bool:
        """Push metrics to Prometheus Pushgateway."""
        try:
            # Convert metrics to Prometheus format
            prometheus_data = []
            for metric in snapshot.metrics:
                prometheus_data.append(metric.to_prometheus_format())
            
            # Add job and instance labels
            prometheus_text = "\n".join(prometheus_data)
            
            # Construct pushgateway URL
            push_url = urljoin(
                self.pushgateway_url,
                f"/metrics/job/{self.job_name}/instance/{self.instance_name}"
            )
            
            # Push to gateway
            response = await self.http_client.post(
                push_url,
                content=prometheus_text,
                headers={"Content-Type": "text/plain"}
            )
            
            if response.status_code == 200:
                logger.debug(f"Successfully pushed {len(snapshot.metrics)} metrics to Prometheus")
                return True
            else:
                logger.error(f"Failed to push metrics: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error pushing metrics to Prometheus: {e}")
            return False
    
    def get_metrics_exposition(self) -> str:
        """Get metrics in Prometheus exposition format for scraping."""
        lines = []
        
        # Group metrics by name for HELP and TYPE comments
        metrics_by_name: Dict[str, List[MetricPoint]] = {}
        for metric in self.metrics_registry.values():
            if metric.name not in metrics_by_name:
                metrics_by_name[metric.name] = []
            metrics_by_name[metric.name].append(metric)
        
        # Generate exposition format
        for metric_name, metric_list in metrics_by_name.items():
            # Add HELP comment
            lines.append(f"# HELP {metric_name} Voice AI Agent metric")
            
            # Add TYPE comment
            metric_type = metric_list[0].metric_type
            prometheus_type = {
                "counter": "counter",
                "gauge": "gauge", 
                "histogram": "histogram",
                "timer": "histogram"
            }.get(metric_type, "gauge")
            lines.append(f"# TYPE {metric_name} {prometheus_type}")
            
            # Add metric lines
            for metric in metric_list:
                lines.append(metric.to_prometheus_format())
        
        return "\n".join(lines)
    
    async def start_pushing(self) -> None:
        """Start automatic metrics pushing."""
        if not self.pushgateway_url:
            logger.info("No pushgateway URL configured, skipping automatic pushing")
            return
        
        if self.is_pushing:
            logger.warning("Metrics pushing is already running")
            return
        
        self.is_pushing = True
        self._stop_event.clear()
        
        self.push_task = asyncio.create_task(self._push_loop())
        
        logger.info(f"Started Prometheus metrics pushing with {self.push_interval}s interval")
    
    async def stop_pushing(self) -> None:
        """Stop automatic metrics pushing."""
        if not self.is_pushing:
            return
        
        self.is_pushing = False
        self._stop_event.set()
        
        if self.push_task:
            self.push_task.cancel()
            try:
                await self.push_task
            except asyncio.CancelledError:
                pass
            self.push_task = None
        
        logger.info("Stopped Prometheus metrics pushing")
    
    async def _push_loop(self) -> None:
        """Main metrics pushing loop."""
        while self.is_pushing and not self._stop_event.is_set():
            try:
                # Create snapshot from current metrics
                metrics_collector = get_metrics_collector()
                all_metrics = metrics_collector.get_all_metrics()
                
                metric_points = []
                for name, metric_data in all_metrics.items():
                    if metric_data["type"] == "counter":
                        metric_points.append(MetricPoint(
                            name=name,
                            value=metric_data["value"],
                            timestamp=time.time(),
                            labels=metric_data.get("labels", {}),
                            metric_type="counter"
                        ))
                    elif metric_data["type"] == "gauge":
                        metric_points.append(MetricPoint(
                            name=name,
                            value=metric_data["value"],
                            timestamp=time.time(),
                            labels=metric_data.get("labels", {}),
                            metric_type="gauge"
                        ))
                    elif metric_data["type"] in ["histogram", "timer"]:
                        stats = metric_data["stats"]
                        labels = metric_data.get("labels", {})
                        
                        # Add histogram metrics
                        metric_points.extend([
                            MetricPoint(f"{name}_count", stats["count"], time.time(), labels, "counter"),
                            MetricPoint(f"{name}_sum", stats["sum"], time.time(), labels, "counter"),
                            MetricPoint(f"{name}_avg", stats["avg"], time.time(), labels, "gauge"),
                            MetricPoint(f"{name}_p50", stats["p50"], time.time(), labels, "gauge"),
                            MetricPoint(f"{name}_p95", stats["p95"], time.time(), labels, "gauge"),
                            MetricPoint(f"{name}_p99", stats["p99"], time.time(), labels, "gauge"),
                        ])
                
                snapshot = MetricsSnapshot(
                    timestamp=datetime.now(UTC),
                    metrics=metric_points,
                    metadata={"exporter": "prometheus", "job": self.job_name}
                )
                
                await self.export_metrics(snapshot)
                
                # Wait for next push interval
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.push_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    continue  # Continue pushing
                    
            except Exception as e:
                logger.error(f"Error in metrics push loop: {e}")
                await asyncio.sleep(min(self.push_interval, 60))
    
    async def health_check(self) -> bool:
        """Check if Prometheus exporter is healthy."""
        if not self.pushgateway_url:
            return True  # Always healthy if not pushing
        
        try:
            # Test connectivity to pushgateway
            response = await self.http_client.get(
                urljoin(self.pushgateway_url, "/api/v1/status/config"),
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Prometheus health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close the exporter and cleanup resources."""
        await self.stop_pushing()
        await self.http_client.aclose()


class JSONExporter(MetricsExporter):
    """
    JSON metrics exporter for custom monitoring systems.
    
    Exports metrics as JSON to HTTP endpoints or files.
    """
    
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        file_path: Optional[str] = None,
        timeout: float = 10.0
    ):
        """
        Initialize JSON exporter.
        
        Args:
            endpoint_url: HTTP endpoint to POST metrics to
            file_path: File path to write metrics to
            timeout: HTTP timeout
        """
        self.endpoint_url = endpoint_url
        self.file_path = file_path
        self.timeout = timeout
        
        if not endpoint_url and not file_path:
            raise ValueError("Either endpoint_url or file_path must be specified")
        
        # HTTP client for endpoint exports
        self.http_client = httpx.AsyncClient(timeout=timeout) if endpoint_url else None
        
        logger.info(
            "JSON exporter initialized",
            extra={
                "endpoint_url": endpoint_url,
                "file_path": file_path
            }
        )
    
    async def export_metrics(self, snapshot: MetricsSnapshot) -> bool:
        """Export metrics snapshot as JSON."""
        try:
            json_data = snapshot.to_dict()
            
            success = True
            
            # Export to HTTP endpoint
            if self.endpoint_url and self.http_client:
                try:
                    response = await self.http_client.post(
                        self.endpoint_url,
                        json=json_data,
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code not in [200, 201, 202]:
                        logger.error(f"HTTP export failed: {response.status_code}")
                        success = False
                except Exception as e:
                    logger.error(f"HTTP export error: {e}")
                    success = False
            
            # Export to file
            if self.file_path:
                try:
                    import os
                    os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                    
                    with open(self.file_path, 'w') as f:
                        json.dump(json_data, f, indent=2)
                except Exception as e:
                    logger.error(f"File export error: {e}")
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if JSON exporter is healthy."""
        if self.endpoint_url and self.http_client:
            try:
                # Test connectivity to endpoint
                response = await self.http_client.get(
                    self.endpoint_url,
                    timeout=5.0
                )
                return response.status_code < 500
            except Exception:
                return False
        
        if self.file_path:
            try:
                # Test file write permissions
                import os
                import tempfile
                
                dir_path = os.path.dirname(self.file_path)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                
                # Test write with temporary file
                with tempfile.NamedTemporaryFile(dir=dir_path, delete=True):
                    pass
                return True
            except Exception:
                return False
        
        return True
    
    async def close(self) -> None:
        """Close the exporter and cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()


class MetricsExportManager:
    """
    Manager for multiple metrics exporters.
    
    Coordinates metrics export across multiple destinations
    and provides unified interface for metrics export.
    """
    
    def __init__(self, export_interval: float = 30.0):
        """
        Initialize metrics export manager.
        
        Args:
            export_interval: Interval between exports in seconds
        """
        self.export_interval = export_interval
        self.exporters: Dict[str, MetricsExporter] = {}
        
        # Export task management
        self.export_task: Optional[asyncio.Task] = None
        self.is_exporting = False
        self._stop_event = asyncio.Event()
        
        # Metrics collection
        self.metrics_collector = get_metrics_collector()
        
        logger.info(f"Metrics export manager initialized with {export_interval}s interval")
    
    def add_exporter(self, name: str, exporter: MetricsExporter) -> None:
        """
        Add a metrics exporter.
        
        Args:
            name: Unique name for the exporter
            exporter: MetricsExporter instance
        """
        self.exporters[name] = exporter
        logger.info(f"Added metrics exporter: {name}")
    
    def remove_exporter(self, name: str) -> None:
        """
        Remove a metrics exporter.
        
        Args:
            name: Name of exporter to remove
        """
        if name in self.exporters:
            del self.exporters[name]
            logger.info(f"Removed metrics exporter: {name}")
    
    async def export_all(self) -> Dict[str, bool]:
        """
        Export metrics to all configured exporters.
        
        Returns:
            Dictionary mapping exporter names to success status
        """
        # Create metrics snapshot
        snapshot = await self._create_metrics_snapshot()
        
        # Export to all exporters concurrently
        export_tasks = {
            name: exporter.export_metrics(snapshot)
            for name, exporter in self.exporters.items()
        }
        
        results = {}
        for name, task in export_tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Export failed for {name}: {e}")
                results[name] = False
        
        return results
    
    async def _create_metrics_snapshot(self) -> MetricsSnapshot:
        """Create a snapshot of current metrics."""
        all_metrics = self.metrics_collector.get_all_metrics()
        
        metric_points = []
        for name, metric_data in all_metrics.items():
            if metric_data["type"] == "counter":
                metric_points.append(MetricPoint(
                    name=name,
                    value=metric_data["value"],
                    timestamp=time.time(),
                    labels=metric_data.get("labels", {}),
                    metric_type="counter"
                ))
            elif metric_data["type"] == "gauge":
                metric_points.append(MetricPoint(
                    name=name,
                    value=metric_data["value"],
                    timestamp=time.time(),
                    labels=metric_data.get("labels", {}),
                    metric_type="gauge"
                ))
            elif metric_data["type"] in ["histogram", "timer"]:
                stats = metric_data["stats"]
                labels = metric_data.get("labels", {})
                
                # Add histogram/timer metrics
                metric_points.extend([
                    MetricPoint(f"{name}_count", stats["count"], time.time(), labels, "counter"),
                    MetricPoint(f"{name}_sum", stats["sum"], time.time(), labels, "counter"),
                    MetricPoint(f"{name}_avg", stats["avg"], time.time(), labels, "gauge"),
                    MetricPoint(f"{name}_min", stats["min"], time.time(), labels, "gauge"),
                    MetricPoint(f"{name}_max", stats["max"], time.time(), labels, "gauge"),
                    MetricPoint(f"{name}_p50", stats["p50"], time.time(), labels, "gauge"),
                    MetricPoint(f"{name}_p95", stats["p95"], time.time(), labels, "gauge"),
                    MetricPoint(f"{name}_p99", stats["p99"], time.time(), labels, "gauge"),
                ])
        
        # Add system metrics
        settings = get_settings()
        metric_points.extend([
            MetricPoint("system_info", 1, time.time(), {
                "version": "0.1.0",
                "environment": settings.environment.value,
                "instance": settings.domain
            }, "gauge")
        ])
        
        return MetricsSnapshot(
            timestamp=datetime.now(UTC),
            metrics=metric_points,
            metadata={
                "total_metrics": len(metric_points),
                "exporters": list(self.exporters.keys())
            }
        )
    
    async def start_exporting(self) -> None:
        """Start automatic metrics export."""
        if self.is_exporting:
            logger.warning("Metrics export is already running")
            return
        
        if not self.exporters:
            logger.info("No exporters configured, skipping automatic export")
            return
        
        self.is_exporting = True
        self._stop_event.clear()
        
        self.export_task = asyncio.create_task(self._export_loop())
        
        logger.info(f"Started metrics export with {self.export_interval}s interval")
    
    async def stop_exporting(self) -> None:
        """Stop automatic metrics export."""
        if not self.is_exporting:
            return
        
        self.is_exporting = False
        self._stop_event.set()
        
        if self.export_task:
            self.export_task.cancel()
            try:
                await self.export_task
            except asyncio.CancelledError:
                pass
            self.export_task = None
        
        logger.info("Stopped metrics export")
    
    async def _export_loop(self) -> None:
        """Main metrics export loop."""
        while self.is_exporting and not self._stop_event.is_set():
            try:
                results = await self.export_all()
                
                # Log export results
                successful = sum(1 for success in results.values() if success)
                total = len(results)
                
                if successful == total:
                    logger.debug(f"Successfully exported metrics to all {total} exporters")
                else:
                    logger.warning(f"Exported metrics to {successful}/{total} exporters")
                
                # Wait for next export interval
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.export_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    continue  # Continue exporting
                    
            except Exception as e:
                logger.error(f"Error in metrics export loop: {e}")
                await asyncio.sleep(min(self.export_interval, 60))
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all exporters."""
        health_tasks = {
            name: exporter.health_check()
            for name, exporter in self.exporters.items()
        }
        
        results = {}
        for name, task in health_tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Health check failed for exporter {name}: {e}")
                results[name] = False
        
        return results
    
    async def close(self) -> None:
        """Close all exporters and cleanup resources."""
        await self.stop_exporting()
        
        for exporter in self.exporters.values():
            if hasattr(exporter, 'close'):
                await exporter.close()
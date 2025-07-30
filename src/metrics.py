"""Metrics collection system for monitoring and observability."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional, Any
from enum import Enum


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Individual metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HistogramBucket:
    """Histogram bucket for latency measurements."""
    upper_bound: float
    count: int = 0


class MetricsCollector:
    """Thread-safe metrics collector."""
    
    def __init__(self):
        self._lock = Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment counter metric."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._counters[key] += value
            if labels:
                self._labels[key] = labels
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set gauge metric value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._gauges[key] = value
            if labels:
                self._labels[key] = labels
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record histogram value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._histograms[key].append(value)
            if labels:
                self._labels[key] = labels
    
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record timer duration."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._timers[key].append(duration)
            if labels:
                self._labels[key] = labels
    
    def _get_metric_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Generate metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._counters.get(key, 0.0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            values = self._histograms.get(key, [])
            
            if not values:
                return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p50": self._percentile(values, 0.5),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99)
            }
    
    def get_timer_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get timer statistics."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            values = self._timers.get(key, [])
            
            if not values:
                return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p50": self._percentile(values, 0.5),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99)
            }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((len(sorted_values) - 1) * percentile)
        return sorted_values[index]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as dictionary."""
        with self._lock:
            metrics = {}
            
            # Counters
            for key, value in self._counters.items():
                metrics[key] = {
                    "type": "counter",
                    "value": value,
                    "labels": self._labels.get(key, {})
                }
            
            # Gauges
            for key, value in self._gauges.items():
                metrics[key] = {
                    "type": "gauge",
                    "value": value,
                    "labels": self._labels.get(key, {})
                }
            
            # Histograms
            for key in self._histograms.keys():
                values = self._histograms[key]
                if not values:
                    stats = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
                else:
                    stats = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p50": self._percentile(values, 0.5),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
                metrics[key] = {
                    "type": "histogram",
                    "stats": stats,
                    "labels": self._labels.get(key, {})
                }
            
            # Timers
            for key in self._timers.keys():
                values = self._timers[key]
                if not values:
                    stats = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
                else:
                    stats = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p50": self._percentile(values, 0.5),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
                metrics[key] = {
                    "type": "timer",
                    "stats": stats,
                    "labels": self._labels.get(key, {})
                }
            
            return metrics
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._labels.clear()


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.record_timer(self.name, duration, self.labels)


# Global metrics collector instance
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    return metrics_collector


def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment counter metric."""
    metrics_collector.increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Set gauge metric value."""
    metrics_collector.set_gauge(name, value, labels)


def record_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record histogram value."""
    metrics_collector.record_histogram(name, value, labels)


def record_timer(name: str, duration: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record timer duration."""
    metrics_collector.record_timer(name, duration, labels)


def timer(name: str, labels: Optional[Dict[str, str]] = None) -> Timer:
    """Create timer context manager."""
    return Timer(metrics_collector, name, labels)
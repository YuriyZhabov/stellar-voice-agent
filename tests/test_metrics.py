"""Tests for metrics collection system."""

import pytest
import time
from unittest.mock import patch
from src.metrics import (
    MetricsCollector,
    Timer,
    MetricType,
    MetricValue,
    HistogramBucket,
    get_metrics_collector,
    increment_counter,
    set_gauge,
    record_histogram,
    record_timer,
    timer
)


class TestMetricValue:
    """Test MetricValue dataclass."""
    
    def test_metric_value_creation(self):
        """Test creating MetricValue with default timestamp."""
        value = MetricValue(value=10.5)
        assert value.value == 10.5
        assert isinstance(value.timestamp, float)
        assert value.labels == {}
    
    def test_metric_value_with_labels(self):
        """Test creating MetricValue with labels."""
        labels = {"service": "api", "version": "1.0"}
        value = MetricValue(value=5.0, labels=labels)
        assert value.value == 5.0
        assert value.labels == labels


class TestHistogramBucket:
    """Test HistogramBucket dataclass."""
    
    def test_histogram_bucket_creation(self):
        """Test creating HistogramBucket."""
        bucket = HistogramBucket(upper_bound=1.0)
        assert bucket.upper_bound == 1.0
        assert bucket.count == 0
    
    def test_histogram_bucket_with_count(self):
        """Test creating HistogramBucket with count."""
        bucket = HistogramBucket(upper_bound=5.0, count=10)
        assert bucket.upper_bound == 5.0
        assert bucket.count == 10


class TestMetricsCollector:
    """Test MetricsCollector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = MetricsCollector()
    
    def test_increment_counter_basic(self):
        """Test basic counter increment."""
        self.collector.increment_counter("test_counter")
        assert self.collector.get_counter("test_counter") == 1.0
    
    def test_increment_counter_with_value(self):
        """Test counter increment with custom value."""
        self.collector.increment_counter("test_counter", 5.5)
        assert self.collector.get_counter("test_counter") == 5.5
    
    def test_increment_counter_multiple_times(self):
        """Test multiple counter increments."""
        self.collector.increment_counter("test_counter", 2.0)
        self.collector.increment_counter("test_counter", 3.0)
        assert self.collector.get_counter("test_counter") == 5.0
    
    def test_increment_counter_with_labels(self):
        """Test counter increment with labels."""
        labels = {"method": "GET", "status": "200"}
        self.collector.increment_counter("http_requests", 1.0, labels)
        assert self.collector.get_counter("http_requests", labels) == 1.0
        assert self.collector.get_counter("http_requests") == 0.0  # Different key
    
    def test_set_gauge_basic(self):
        """Test basic gauge setting."""
        self.collector.set_gauge("cpu_usage", 75.5)
        assert self.collector.get_gauge("cpu_usage") == 75.5
    
    def test_set_gauge_overwrite(self):
        """Test gauge value overwrite."""
        self.collector.set_gauge("memory_usage", 50.0)
        self.collector.set_gauge("memory_usage", 60.0)
        assert self.collector.get_gauge("memory_usage") == 60.0
    
    def test_set_gauge_with_labels(self):
        """Test gauge setting with labels."""
        labels = {"instance": "server1"}
        self.collector.set_gauge("cpu_usage", 80.0, labels)
        assert self.collector.get_gauge("cpu_usage", labels) == 80.0
        assert self.collector.get_gauge("cpu_usage") is None  # Different key
    
    def test_record_histogram_basic(self):
        """Test basic histogram recording."""
        self.collector.record_histogram("response_time", 0.5)
        stats = self.collector.get_histogram_stats("response_time")
        assert stats["count"] == 1
        assert stats["sum"] == 0.5
        assert stats["min"] == 0.5
        assert stats["max"] == 0.5
        assert stats["avg"] == 0.5
    
    def test_record_histogram_multiple_values(self):
        """Test histogram with multiple values."""
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        for value in values:
            self.collector.record_histogram("latency", value)
        
        stats = self.collector.get_histogram_stats("latency")
        assert stats["count"] == 5
        assert stats["sum"] == 1.5
        assert stats["min"] == 0.1
        assert stats["max"] == 0.5
        assert stats["avg"] == 0.3
        assert stats["p50"] == 0.3
        assert stats["p95"] == 0.4
        assert stats["p99"] == 0.4
    
    def test_record_histogram_with_labels(self):
        """Test histogram recording with labels."""
        labels = {"endpoint": "/api/users"}
        self.collector.record_histogram("request_duration", 1.2, labels)
        stats = self.collector.get_histogram_stats("request_duration", labels)
        assert stats["count"] == 1
        assert stats["sum"] == 1.2
    
    def test_record_timer_basic(self):
        """Test basic timer recording."""
        self.collector.record_timer("operation_time", 2.5)
        stats = self.collector.get_timer_stats("operation_time")
        assert stats["count"] == 1
        assert stats["sum"] == 2.5
        assert stats["min"] == 2.5
        assert stats["max"] == 2.5
        assert stats["avg"] == 2.5
    
    def test_record_timer_multiple_values(self):
        """Test timer with multiple values."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for value in values:
            self.collector.record_timer("db_query", value)
        
        stats = self.collector.get_timer_stats("db_query")
        assert stats["count"] == 5
        assert stats["sum"] == 15.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["avg"] == 3.0
        assert stats["p50"] == 3.0
        assert stats["p95"] == 4.0
        assert stats["p99"] == 4.0
    
    def test_record_timer_with_labels(self):
        """Test timer recording with labels."""
        labels = {"query_type": "SELECT"}
        self.collector.record_timer("db_query_time", 0.8, labels)
        stats = self.collector.get_timer_stats("db_query_time", labels)
        assert stats["count"] == 1
        assert stats["sum"] == 0.8
    
    def test_get_metric_key_without_labels(self):
        """Test metric key generation without labels."""
        key = self.collector._get_metric_key("test_metric", None)
        assert key == "test_metric"
    
    def test_get_metric_key_with_labels(self):
        """Test metric key generation with labels."""
        labels = {"service": "api", "method": "GET"}
        key = self.collector._get_metric_key("test_metric", labels)
        assert key == "test_metric{method=GET,service=api}"
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        assert self.collector._percentile(values, 0.5) == 5
        assert self.collector._percentile(values, 0.9) == 9
        assert self.collector._percentile(values, 0.95) == 9
        assert self.collector._percentile(values, 0.99) == 9
    
    def test_percentile_empty_list(self):
        """Test percentile calculation with empty list."""
        assert self.collector._percentile([], 0.5) == 0.0
    
    def test_get_histogram_stats_empty(self):
        """Test histogram stats for non-existent metric."""
        stats = self.collector.get_histogram_stats("non_existent")
        expected = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
        assert stats == expected
    
    def test_get_timer_stats_empty(self):
        """Test timer stats for non-existent metric."""
        stats = self.collector.get_timer_stats("non_existent")
        expected = {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
        assert stats == expected
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        # Add some metrics
        self.collector.increment_counter("requests", 5.0)
        self.collector.set_gauge("cpu", 80.0)
        self.collector.record_histogram("latency", 0.5)
        self.collector.record_timer("duration", 2.0)
        
        metrics = self.collector.get_all_metrics()
        
        assert "requests" in metrics
        assert metrics["requests"]["type"] == "counter"
        assert metrics["requests"]["value"] == 5.0
        
        assert "cpu" in metrics
        assert metrics["cpu"]["type"] == "gauge"
        assert metrics["cpu"]["value"] == 80.0
        
        assert "latency" in metrics
        assert metrics["latency"]["type"] == "histogram"
        assert "stats" in metrics["latency"]
        
        assert "duration" in metrics
        assert metrics["duration"]["type"] == "timer"
        assert "stats" in metrics["duration"]
    
    def test_reset_metrics(self):
        """Test resetting all metrics."""
        # Add some metrics
        self.collector.increment_counter("test_counter")
        self.collector.set_gauge("test_gauge", 50.0)
        self.collector.record_histogram("test_histogram", 1.0)
        self.collector.record_timer("test_timer", 2.0)
        
        # Verify metrics exist
        assert self.collector.get_counter("test_counter") == 1.0
        assert self.collector.get_gauge("test_gauge") == 50.0
        
        # Reset and verify
        self.collector.reset()
        assert self.collector.get_counter("test_counter") == 0.0
        assert self.collector.get_gauge("test_gauge") is None
        assert self.collector.get_histogram_stats("test_histogram")["count"] == 0
        assert self.collector.get_timer_stats("test_timer")["count"] == 0


class TestTimer:
    """Test Timer context manager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = MetricsCollector()
    
    @patch('time.time')
    def test_timer_context_manager(self, mock_time):
        """Test timer context manager functionality."""
        mock_time.side_effect = [1000.0, 1002.5]  # Start and end times
        
        with Timer(self.collector, "test_operation"):
            pass  # Simulate some work
        
        stats = self.collector.get_timer_stats("test_operation")
        assert stats["count"] == 1
        assert stats["sum"] == 2.5
    
    @patch('time.time')
    def test_timer_with_labels(self, mock_time):
        """Test timer with labels."""
        mock_time.side_effect = [1000.0, 1001.5]
        labels = {"operation": "database_query"}
        
        with Timer(self.collector, "db_operation", labels):
            pass
        
        stats = self.collector.get_timer_stats("db_operation", labels)
        assert stats["count"] == 1
        assert stats["sum"] == 1.5
    
    def test_timer_real_time(self):
        """Test timer with real time measurement."""
        with Timer(self.collector, "sleep_test"):
            time.sleep(0.01)  # Sleep for 10ms
        
        stats = self.collector.get_timer_stats("sleep_test")
        assert stats["count"] == 1
        assert stats["sum"] >= 0.01  # Should be at least 10ms


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset global collector
        get_metrics_collector().reset()
    
    def test_get_metrics_collector(self):
        """Test getting global metrics collector."""
        collector = get_metrics_collector()
        assert isinstance(collector, MetricsCollector)
        
        # Should return the same instance
        collector2 = get_metrics_collector()
        assert collector is collector2
    
    def test_global_increment_counter(self):
        """Test global increment_counter function."""
        increment_counter("global_counter", 3.0)
        collector = get_metrics_collector()
        assert collector.get_counter("global_counter") == 3.0
    
    def test_global_set_gauge(self):
        """Test global set_gauge function."""
        set_gauge("global_gauge", 75.0)
        collector = get_metrics_collector()
        assert collector.get_gauge("global_gauge") == 75.0
    
    def test_global_record_histogram(self):
        """Test global record_histogram function."""
        record_histogram("global_histogram", 1.5)
        collector = get_metrics_collector()
        stats = collector.get_histogram_stats("global_histogram")
        assert stats["count"] == 1
        assert stats["sum"] == 1.5
    
    def test_global_record_timer(self):
        """Test global record_timer function."""
        record_timer("global_timer", 2.5)
        collector = get_metrics_collector()
        stats = collector.get_timer_stats("global_timer")
        assert stats["count"] == 1
        assert stats["sum"] == 2.5
    
    @patch('time.time')
    def test_global_timer_function(self, mock_time):
        """Test global timer function."""
        mock_time.side_effect = [1000.0, 1003.0]
        
        with timer("global_timer_test"):
            pass
        
        collector = get_metrics_collector()
        stats = collector.get_timer_stats("global_timer_test")
        assert stats["count"] == 1
        assert stats["sum"] == 3.0
    
    def test_global_functions_with_labels(self):
        """Test global functions with labels."""
        labels = {"service": "test"}
        
        increment_counter("labeled_counter", 1.0, labels)
        set_gauge("labeled_gauge", 50.0, labels)
        record_histogram("labeled_histogram", 0.5, labels)
        record_timer("labeled_timer", 1.0, labels)
        
        collector = get_metrics_collector()
        assert collector.get_counter("labeled_counter", labels) == 1.0
        assert collector.get_gauge("labeled_gauge", labels) == 50.0
        assert collector.get_histogram_stats("labeled_histogram", labels)["count"] == 1
        assert collector.get_timer_stats("labeled_timer", labels)["count"] == 1


class TestMetricType:
    """Test MetricType enum."""
    
    def test_metric_type_values(self):
        """Test MetricType enum values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.TIMER.value == "timer"


class TestThreadSafety:
    """Test thread safety of MetricsCollector."""
    
    def test_concurrent_counter_increments(self):
        """Test concurrent counter increments."""
        import threading
        
        collector = MetricsCollector()
        num_threads = 10
        increments_per_thread = 100
        
        def increment_worker():
            for _ in range(increments_per_thread):
                collector.increment_counter("concurrent_counter")
        
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=increment_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        expected_total = num_threads * increments_per_thread
        assert collector.get_counter("concurrent_counter") == expected_total
    
    def test_concurrent_gauge_sets(self):
        """Test concurrent gauge sets."""
        import threading
        
        collector = MetricsCollector()
        num_threads = 5
        
        def gauge_worker(value):
            collector.set_gauge("concurrent_gauge", value)
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=gauge_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Final value should be one of the set values
        final_value = collector.get_gauge("concurrent_gauge")
        assert final_value in range(num_threads)
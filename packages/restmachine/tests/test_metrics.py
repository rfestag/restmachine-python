"""Tests for metrics collection."""

import pytest
import time
from unittest.mock import Mock

from restmachine.metrics import (
    MetricsCollector,
    EphemeralMetrics,
    MetricUnit,
    MetricValue,
    MetricsPublisher,
    METRICS
)


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_add_metric(self):
        """Test adding a metric."""
        collector = MetricsCollector()
        collector.add_metric("test.metric", 42.5, unit=MetricUnit.Count)

        assert "test.metric" in collector.metrics
        assert len(collector.metrics["test.metric"]) == 1
        assert collector.metrics["test.metric"][0].value == 42.5
        assert collector.metrics["test.metric"][0].unit == MetricUnit.Count

    def test_add_metric_multiple_values(self):
        """Test adding multiple values for same metric name."""
        collector = MetricsCollector()
        collector.add_metric("requests", 1, unit=MetricUnit.Count)
        collector.add_metric("requests", 1, unit=MetricUnit.Count)
        collector.add_metric("requests", 3, unit=MetricUnit.Count)

        assert "requests" in collector.metrics
        assert len(collector.metrics["requests"]) == 3
        assert [m.value for m in collector.metrics["requests"]] == [1, 1, 3]

    def test_add_metric_with_string_unit(self):
        """Test adding metric with string unit."""
        collector = MetricsCollector()
        collector.add_metric("test", 10, unit="Count")

        assert collector.metrics["test"][0].unit == MetricUnit.Count

    def test_add_metric_invalid_value(self):
        """Test that non-numeric values raise ValueError."""
        collector = MetricsCollector()

        with pytest.raises(ValueError, match="Metric value must be numeric"):
            collector.add_metric("test", "not a number")

    def test_add_metric_with_kwargs(self):
        """Test adding platform-specific fields via kwargs."""
        collector = MetricsCollector()
        collector.add_metric("test", 10, resolution=1, custom_field="value")

        metric = collector.metrics["test"][0]
        assert hasattr(metric, 'resolution')
        assert metric.resolution == 1
        assert hasattr(metric, 'custom_field')
        assert metric.custom_field == "value"

    def test_add_dimension(self):
        """Test adding dimensions."""
        collector = MetricsCollector()
        collector.add_dimension("environment", "production")
        collector.add_dimension("region", "us-east-1")

        assert collector.dimensions["environment"] == "production"
        assert collector.dimensions["region"] == "us-east-1"

    def test_add_dimension_converts_to_string(self):
        """Test that dimension values are converted to strings."""
        collector = MetricsCollector()
        collector.add_dimension("status_code", 200)

        assert collector.dimensions["status_code"] == "200"
        assert isinstance(collector.dimensions["status_code"], str)

    def test_set_default_dimensions(self):
        """Test setting default dimensions."""
        collector = MetricsCollector()
        collector.set_default_dimensions(
            environment="production",
            service="api"
        )

        assert collector.default_dimensions["environment"] == "production"
        assert collector.default_dimensions["service"] == "api"

    def test_get_all_dimensions(self):
        """Test getting merged dimensions."""
        collector = MetricsCollector()
        collector.set_default_dimensions(environment="production")
        collector.add_dimension("method", "GET")

        all_dims = collector.get_all_dimensions()
        assert all_dims["environment"] == "production"
        assert all_dims["method"] == "GET"

    def test_clear_default_dimensions(self):
        """Test clearing default dimensions."""
        collector = MetricsCollector()
        collector.set_default_dimensions(environment="production")
        collector.clear_default_dimensions()

        assert len(collector.default_dimensions) == 0

    def test_add_metadata(self):
        """Test adding metadata."""
        collector = MetricsCollector()
        collector.add_metadata("request_id", "abc-123")
        collector.add_metadata("user_id", 12345)

        assert collector.metadata["request_id"] == "abc-123"
        assert collector.metadata["user_id"] == 12345

    def test_start_stop_timer(self):
        """Test timer functionality."""
        collector = MetricsCollector()

        collector.start_timer("operation")
        time.sleep(0.01)  # Sleep 10ms
        collector.stop_timer("operation")

        assert "operation" in collector.metrics
        # Should be around 10ms (with some tolerance)
        elapsed = collector.metrics["operation"][0].value
        assert 8 < elapsed < 20  # Allowing for timing variance

    def test_stop_timer_without_start_raises_error(self):
        """Test that stopping non-existent timer raises KeyError."""
        collector = MetricsCollector()

        with pytest.raises(KeyError, match="Timer 'nonexistent' was not started"):
            collector.stop_timer("nonexistent")

    def test_clear_metrics(self):
        """Test clearing metrics."""
        collector = MetricsCollector()
        collector.set_default_dimensions(environment="production")
        collector.add_metric("test", 1)
        collector.add_dimension("method", "GET")
        collector.add_metadata("request_id", "123")
        collector.start_timer("test_timer")

        collector.clear_metrics()

        # Metrics, dimensions, metadata, and timers should be cleared
        assert len(collector.metrics) == 0
        assert len(collector.dimensions) == 0
        assert len(collector.metadata) == 0
        assert len(collector._timers) == 0

        # Default dimensions should be preserved
        assert collector.default_dimensions["environment"] == "production"


class TestEphemeralMetrics:
    """Tests for EphemeralMetrics."""

    def test_ephemeral_has_no_default_dimensions(self):
        """Test that ephemeral metrics don't inherit default dimensions."""
        ephemeral = EphemeralMetrics()

        assert len(ephemeral.default_dimensions) == 0

    def test_ephemeral_is_isolated(self):
        """Test that ephemeral metrics are completely isolated."""
        collector = MetricsCollector()
        collector.set_default_dimensions(shared="value")

        ephemeral = EphemeralMetrics()
        ephemeral.add_dimension("isolated", "yes")

        # Ephemeral should not have shared dimension
        assert "shared" not in ephemeral.get_all_dimensions()
        assert ephemeral.get_all_dimensions()["isolated"] == "yes"


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_metric_value_defaults(self):
        """Test MetricValue default values."""
        metric = MetricValue(value=10.5)

        assert metric.value == 10.5
        assert metric.unit == MetricUnit.NoUnit
        assert metric.timestamp is None

    def test_metric_value_with_all_fields(self):
        """Test MetricValue with all fields."""
        timestamp = int(time.time() * 1000)
        metric = MetricValue(
            value=42,
            unit=MetricUnit.Milliseconds,
            timestamp=timestamp
        )

        assert metric.value == 42
        assert metric.unit == MetricUnit.Milliseconds
        assert metric.timestamp == timestamp


class TestMetricsPublisher:
    """Tests for MetricsPublisher abstract base class."""

    def test_cannot_instantiate_abstract_publisher(self):
        """Test that MetricsPublisher cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MetricsPublisher()

    def test_can_implement_publisher(self):
        """Test that we can implement a custom publisher."""
        class TestPublisher(MetricsPublisher):
            def __init__(self):
                self.published = []
                self.enabled = True

            def is_enabled(self):
                return self.enabled

            def publish(self, collector, request=None, response=None, context=None):
                self.published.append({
                    'collector': collector,
                    'request': request,
                    'response': response,
                    'context': context
                })

        publisher = TestPublisher()
        collector = MetricsCollector()
        collector.add_metric("test", 1)

        publisher.publish(collector)

        assert len(publisher.published) == 1
        assert publisher.published[0]['collector'] == collector


class TestMetricUnit:
    """Tests for MetricUnit enum."""

    def test_metric_units_are_strings(self):
        """Test that MetricUnit values are strings."""
        assert MetricUnit.Count == "Count"
        assert MetricUnit.Milliseconds == "Milliseconds"
        assert MetricUnit.Bytes == "Bytes"

    def test_can_create_from_string(self):
        """Test creating MetricUnit from string."""
        unit = MetricUnit("Count")
        assert unit == MetricUnit.Count


class TestMetricsLogLevel:
    """Tests for custom METRICS log level."""

    def test_metrics_log_level_exists(self):
        """Test that METRICS log level is registered."""
        import logging

        assert METRICS == 25
        assert logging.getLevelName(METRICS) == 'METRICS'

    def test_metrics_log_level_between_info_and_warning(self):
        """Test that METRICS is between INFO and WARNING."""
        import logging

        assert logging.INFO < METRICS < logging.WARNING

"""Platform-agnostic metrics collection.

This module provides a lightweight metrics collection system that works via
Python's logging infrastructure. Metrics are opt-in via log level configuration.

Example:
    # Enable metrics logging
    import logging
    from restmachine.metrics import METRICS

    logger = logging.getLogger("restmachine.metrics")
    logger.setLevel(METRICS)
    logger.addHandler(logging.StreamHandler())

    # Use in handlers
    @app.get("/users/{id}")
    def get_user(id: str, metrics):
        metrics.add_metric("users.fetched", 1, unit=MetricUnit.Count)
        metrics.add_dimension("user_type", "premium")
        return {"user": id}
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import time

# Custom log level for metrics (between INFO=20 and WARNING=30)
METRICS = 25
logging.addLevelName(METRICS, 'METRICS')


class MetricUnit(str, Enum):
    """Standard metric units (platform-agnostic)."""
    # Time
    Seconds = "Seconds"
    Milliseconds = "Milliseconds"
    Microseconds = "Microseconds"
    Nanoseconds = "Nanoseconds"

    # Bytes
    Bytes = "Bytes"
    Kilobytes = "Kilobytes"
    Megabytes = "Megabytes"
    Gigabytes = "Gigabytes"
    Terabytes = "Terabytes"

    # Counts
    Count = "Count"

    # Rates
    CountPerSecond = "Count/Second"
    BytesPerSecond = "Bytes/Second"
    KilobytesPerSecond = "Kilobytes/Second"
    MegabytesPerSecond = "Megabytes/Second"
    GigabytesPerSecond = "Gigabytes/Second"
    TerabytesPerSecond = "Terabytes/Second"

    # Percentage
    Percent = "Percent"

    # None
    NoUnit = "None"


@dataclass
class MetricValue:
    """Platform-agnostic metric value."""
    value: float
    unit: MetricUnit = MetricUnit.NoUnit
    timestamp: Optional[int] = None  # Unix timestamp in milliseconds


class MetricsCollector:
    """Platform-agnostic metrics collector.

    Collects metrics without enforcing platform-specific limits.
    Publishers are responsible for validation and transformation.

    Features:
    - Default dimensions that apply to all metrics
    - Multiple values for same metric name (for aggregation)
    - Metadata for high-cardinality data
    - Timer utilities for measuring durations

    Example:
        metrics = MetricsCollector()

        # Add metrics
        metrics.add_metric("requests", 1, unit=MetricUnit.Count)

        # Add dimensions (for grouping)
        metrics.add_dimension("endpoint", "/api/users")
        metrics.add_dimension("method", "GET")

        # Add metadata (high-cardinality context)
        metrics.add_metadata("request_id", "abc-123")

        # Use timers
        metrics.start_timer("db_query")
        # ... do work ...
        metrics.stop_timer("db_query")
    """

    def __init__(self):
        """Initialize metrics collector."""
        # Metrics can have multiple values (for aggregation)
        self.metrics: Dict[str, List[MetricValue]] = {}

        # Dimensions/Labels (terminology varies by platform)
        self.dimensions: Dict[str, str] = {}
        self.default_dimensions: Dict[str, str] = {}

        # Metadata (high-cardinality context, not for grouping)
        self.metadata: Dict[str, Any] = {}

        # Timers
        self._timers: Dict[str, float] = {}

    def set_default_dimensions(self, **dimensions: str):
        """Set default dimensions for all metrics.

        Default dimensions persist across metrics and are merged with
        per-metric dimensions.

        Args:
            **dimensions: Key-value pairs for dimensions

        Example:
            metrics.set_default_dimensions(
                environment="production",
                region="us-east-1"
            )
        """
        self.default_dimensions.update(dimensions)

    def clear_default_dimensions(self):
        """Clear all default dimensions."""
        self.default_dimensions.clear()

    def add_metric(self, name: str, value: float,
                   unit: Union[MetricUnit, str] = MetricUnit.NoUnit,
                   timestamp: Optional[int] = None,
                   **kwargs):
        """Add a metric value.

        Multiple calls with the same name will accumulate values in a list.

        Args:
            name: Metric name
            value: Metric value (must be numeric)
            unit: Unit of measurement (default: None)
            timestamp: Optional timestamp (ms since epoch)
            **kwargs: Platform-specific fields (e.g., resolution for CloudWatch)

        Example:
            metrics.add_metric("users.created", 1, unit=MetricUnit.Count)
            metrics.add_metric("users.created", 5, unit=MetricUnit.Count)
            # Results in: users.created: [1, 5]

            # CloudWatch high-resolution metric (platform-specific)
            metrics.add_metric(
                "api.latency",
                45.2,
                unit=MetricUnit.Milliseconds,
                resolution=1  # CloudWatch-specific
            )

        Raises:
            ValueError: If value is not numeric
        """
        if not isinstance(value, (int, float)):
            raise ValueError(f"Metric value must be numeric, got {type(value)}")

        # Convert string unit to enum
        if isinstance(unit, str):
            try:
                unit = MetricUnit(unit)
            except ValueError:
                unit = MetricUnit.NoUnit

        # Create metric value
        metric_value = MetricValue(
            value=value,
            unit=unit,
            timestamp=timestamp or int(time.time() * 1000)
        )

        # Store platform-specific fields (e.g., CloudWatch resolution)
        for key, val in kwargs.items():
            setattr(metric_value, key, val)

        # Add to metrics list (multiple values allowed)
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(metric_value)

    def add_dimension(self, key: str, value: str):
        """Add a dimension for metric grouping.

        Dimensions are used to group metrics. Different platforms have
        different names:
        - CloudWatch: dimensions
        - Prometheus: labels
        - OpenTelemetry: attributes

        Args:
            key: Dimension name
            value: Dimension value (will be converted to string)

        Example:
            metrics.add_dimension("user_type", "premium")
            metrics.add_dimension("endpoint", "/api/users")
        """
        self.dimensions[key] = str(value)

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the metrics context.

        Metadata is high-cardinality data that doesn't become metric dimensions.
        Useful for debugging, tracing, or adding contextual information without
        impacting metric dimension cardinality.

        Args:
            key: Metadata key
            value: Metadata value (any JSON-serializable type)

        Example:
            metrics.add_metadata("request_id", "abc-123")
            metrics.add_metadata("user_id", 12345)
            metrics.add_metadata("trace_id", trace_id)
        """
        self.metadata[key] = value

    def start_timer(self, name: str):
        """Start a named timer.

        Args:
            name: Timer name

        Example:
            metrics.start_timer("database_query")
            # ... do database work ...
            metrics.stop_timer("database_query")
        """
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str,
                   unit: Union[MetricUnit, str] = MetricUnit.Milliseconds,
                   **kwargs):
        """Stop a timer and record the elapsed time as a metric.

        Args:
            name: Timer name (must have been started with start_timer)
            unit: Unit of measurement (default: Milliseconds)
            **kwargs: Additional metric options

        Raises:
            KeyError: If timer was not started

        Example:
            metrics.start_timer("api_call")
            result = api.fetch_data()
            metrics.stop_timer("api_call")
        """
        if name not in self._timers:
            raise KeyError(f"Timer '{name}' was not started")

        start_time = self._timers.pop(name)
        elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
        self.add_metric(name, elapsed, unit=unit, **kwargs)

    def get_all_dimensions(self) -> Dict[str, str]:
        """Get merged default and request dimensions.

        Returns:
            Merged dictionary of all dimensions
        """
        all_dims = {}
        all_dims.update(self.default_dimensions)
        all_dims.update(self.dimensions)
        return all_dims

    def clear_metrics(self):
        """Clear all metrics (but preserve default dimensions)."""
        self.metrics.clear()
        self.dimensions.clear()
        self.metadata.clear()
        self._timers.clear()


class EphemeralMetrics(MetricsCollector):
    """Isolated metrics collector that prevents dimension pollution.

    Use this for multi-tenant scenarios or when you need completely
    isolated metrics that don't share default dimensions with the
    main metrics collector.

    Example:
        # Main metrics for request
        metrics.add_metric("request.count", 1)

        # Isolated metrics for specific tenant
        tenant_metrics = EphemeralMetrics()
        tenant_metrics.add_dimension("tenant_id", "acme-corp")
        tenant_metrics.add_metric("tenant.api_calls", 1)
    """

    def __init__(self):
        """Initialize ephemeral metrics with no shared state."""
        super().__init__()
        # Ensure default dimensions don't leak
        self.default_dimensions = {}


class MetricsPublisher(ABC):
    """Abstract base for metrics publishers.

    Publishers transform platform-agnostic metrics to specific formats
    and handle platform-specific validation/limits.
    """

    @abstractmethod
    def publish(self, collector: MetricsCollector, request: Any = None,
                response: Any = None, context: Any = None):
        """Publish metrics from collector.

        Publishers are responsible for:
        - Platform-specific validation (e.g., CloudWatch's 100 metric limit)
        - Format transformation (e.g., EMF, OTLP, Prometheus exposition)
        - Error handling (don't break the app)

        Args:
            collector: MetricsCollector with collected metrics
            request: Optional request object for context
            response: Optional response object for context
            context: Optional platform context (e.g., Lambda context)
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this publisher is enabled.

        Returns:
            True if metrics should be collected and published
        """
        pass

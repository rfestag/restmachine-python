"""AWS CloudWatch EMF metrics publisher.

This module provides CloudWatch Embedded Metric Format (EMF) publishers
for automatically creating CloudWatch metrics from Lambda logs.

Environment Variables:
    RESTMACHINE_METRICS_ENABLED: Enable/disable metrics (default: true)
    RESTMACHINE_METRICS_NAMESPACE: CloudWatch namespace (default: "RestMachine")
    RESTMACHINE_SERVICE_NAME: Service name dimension (default: AWS_LAMBDA_FUNCTION_NAME)
    RESTMACHINE_METRICS_RESOLUTION: Default resolution in seconds, 1 or 60 (default: 60)

Example:
    # Production with high-resolution
    RESTMACHINE_METRICS_NAMESPACE=MyApp/Production
    RESTMACHINE_SERVICE_NAME=api-gateway
    RESTMACHINE_METRICS_RESOLUTION=1

    # Development - disable metrics
    RESTMACHINE_METRICS_ENABLED=false
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional

from restmachine.metrics import MetricsPublisher, MetricsCollector, METRICS


class CloudWatchEMFPublisher(MetricsPublisher):
    """Publishes metrics as CloudWatch Embedded Metric Format.

    Handles CloudWatch-specific constraints:
    - Max 100 metrics per EMF object
    - Max 30 dimensions
    - Resolution (1s or 60s)

    The EMF format allows CloudWatch to automatically extract metrics
    from JSON logs without requiring PutMetricData API calls.

    Example:
        publisher = CloudWatchEMFPublisher(
            namespace="MyApp/API",
            service_name="user-service",
            default_resolution=1  # High-resolution metrics
        )

        # Configure logging
        logger = logging.getLogger("restmachine.metrics.emf")
        logger.setLevel(METRICS)
        logger.addHandler(logging.StreamHandler())

        # Use with adapter
        adapter = AwsApiGatewayAdapter(app, metrics_publisher=publisher)
    """

    # CloudWatch EMF limits
    MAX_METRICS = 100
    MAX_DIMENSIONS = 30

    def __init__(self, namespace: str = "RestMachine/Requests",
                 service_name: Optional[str] = None,
                 logger_name: str = "restmachine.metrics.emf",
                 default_resolution: int = 60):
        """Initialize EMF publisher.

        Args:
            namespace: CloudWatch namespace
            service_name: Service name dimension
            logger_name: Logger for EMF output
            default_resolution: Default resolution (1 or 60 seconds)
        """
        self.namespace = namespace
        self.service_name = service_name
        self.logger = logging.getLogger(logger_name)
        self.default_resolution = default_resolution

    def is_enabled(self) -> bool:
        """Check if EMF logging is enabled.

        Returns:
            True if logger is enabled at METRICS level
        """
        return self.logger.isEnabledFor(METRICS)

    def publish(self, collector: MetricsCollector, request: Any = None,
                response: Any = None, context: Any = None):
        """Publish metrics as EMF JSON.

        Validates against CloudWatch limits and splits into multiple
        EMF objects if needed.

        Args:
            collector: MetricsCollector with collected metrics
            request: Optional request object
            response: Optional response object
            context: Optional Lambda context
        """
        if not self.is_enabled():
            return

        # Get dimensions
        dimensions = collector.get_all_dimensions()
        if self.service_name:
            dimensions["service"] = self.service_name

        # Validate dimensions
        if len(dimensions) > self.MAX_DIMENSIONS:
            self.logger.warning(
                f"Too many dimensions ({len(dimensions)}), truncating to {self.MAX_DIMENSIONS}"
            )
            dimensions = dict(list(dimensions.items())[:self.MAX_DIMENSIONS])

        # Split metrics if exceeding 100
        metric_chunks = self._chunk_metrics(collector.metrics)

        for chunk in metric_chunks:
            emf_data = self._build_emf(chunk, dimensions, collector.metadata)
            self.logger.log(METRICS, json.dumps(emf_data))

    def _chunk_metrics(self, metrics: Dict) -> List[Dict]:
        """Split metrics into chunks of max 100.

        Args:
            metrics: Dictionary of metric name to list of values

        Returns:
            List of metric chunks
        """
        chunks = []
        current_chunk: Dict[str, Any] = {}

        for name, values in metrics.items():
            if len(current_chunk) >= self.MAX_METRICS:
                chunks.append(current_chunk)
                current_chunk = {}
            current_chunk[name] = values

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _build_emf(self, metrics: Dict, dimensions: Dict[str, str],
                   metadata: Dict[str, Any]) -> Dict:
        """Build EMF JSON structure.

        Args:
            metrics: Dictionary of metrics to include
            dimensions: Dimensions for the metrics
            metadata: Additional metadata to include

        Returns:
            EMF-formatted dictionary
        """
        dimension_keys = list(dimensions.keys())

        # Build metric definitions and values
        metric_definitions = []
        metric_values: Dict[str, Any] = {}

        for name, values in metrics.items():
            first_value = values[0]

            metric_def = {"Name": name}

            # Unit
            if first_value.unit.value != "None":
                metric_def["Unit"] = first_value.unit.value

            # Resolution (CloudWatch-specific, from kwargs)
            resolution = getattr(first_value, 'resolution', self.default_resolution)
            if resolution == 1:
                metric_def["StorageResolution"] = 1

            metric_definitions.append(metric_def)

            # Values (single or array)
            if len(values) == 1:
                metric_values[name] = values[0].value
            else:
                metric_values[name] = [v.value for v in values]

        # Build EMF structure
        emf_output: Dict[str, Any] = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [{
                    "Namespace": self.namespace,
                    "Dimensions": [dimension_keys] if dimension_keys else [[]],
                    "Metrics": metric_definitions
                }]
            }
        }

        # Add dimensions, metrics, and metadata as top-level fields
        emf_output.update(dimensions)
        emf_output.update(metric_values)
        emf_output.update(metadata)

        return emf_output

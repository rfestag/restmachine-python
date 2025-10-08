"""Base metrics handler for platform adapters.

This module provides metrics lifecycle management for platform adapters
(AWS Lambda, ASGI, etc.) to instrument the full request lifecycle.
"""

from typing import Any, Optional, Callable
import logging

from restmachine.metrics import MetricsCollector, MetricsPublisher


logger = logging.getLogger(__name__)


class MetricsHandler:
    """Handles metrics lifecycle in platform adapters.

    This is used by platform adapters (AWS, ASGI, etc.) to:
    1. Create metrics collector if enabled
    2. Time the full request lifecycle
    3. Publish metrics at the end

    Example:
        # In an adapter
        metrics_handler = MetricsHandler(app, emf_publisher)

        def handle_event(event, context):
            return metrics_handler.handle_request(
                event,
                context,
                convert_fn=self.convert_to_request,
                execute_fn=self.app.execute,
                response_fn=self.convert_from_response
            )
    """

    def __init__(self, app, publisher: Optional[MetricsPublisher] = None):
        """Initialize metrics handler.

        Args:
            app: RestApplication instance
            publisher: Optional metrics publisher
        """
        self.app = app
        self.publisher = publisher

    def create_collector(self) -> MetricsCollector:
        """Create metrics collector.

        Returns:
            MetricsCollector instance
        """
        # Always create collector so handlers can use it
        # We just skip publishing if publisher is disabled
        return MetricsCollector()

    def handle_request(self, event: Any, context: Any,
                      convert_fn: Callable, execute_fn: Callable,
                      response_fn: Callable) -> Any:
        """Handle request with metrics collection.

        This wraps the full request lifecycle with metrics timing.

        Args:
            event: Platform event
            context: Platform context
            convert_fn: Function to convert event to Request
            execute_fn: Function to execute request
            response_fn: Function to convert Response to platform format

        Returns:
            Platform-specific response
        """
        # Create metrics collector (always)
        metrics = self.create_collector()
        metrics.start_timer("adapter.total_time")

        try:
            # Convert event to request
            metrics.start_timer("adapter.event_to_request")
            request = convert_fn(event, context)
            metrics.stop_timer("adapter.event_to_request")

            # Store in app cache for injection
            self.app._dependency_cache.set("metrics", metrics)

            # Execute application
            metrics.start_timer("application.execute")
            response = execute_fn(request)
            metrics.stop_timer("application.execute")

            # Convert response
            metrics.start_timer("adapter.response_conversion")
            platform_response = response_fn(response, event, context)
            metrics.stop_timer("adapter.response_conversion")
            metrics.stop_timer("adapter.total_time")

            # Add response context
            metrics.add_metadata("status_code", response.status_code)
            metrics.add_dimension("method", request.method.value)
            metrics.add_dimension("path", request.path)

            # Publish (only if enabled)
            self._safe_publish(metrics, request, response, context)

            return platform_response

        except Exception as e:
            # Record error metrics
            metrics.add_metric("errors", 1, unit="Count")
            metrics.add_metadata("error", str(e))
            metrics.add_metadata("error_type", type(e).__name__)
            self._safe_publish(metrics, context=context)

            raise

    def _safe_publish(self, metrics: MetricsCollector, request: Any = None,
                     response: Any = None, context: Any = None):
        """Safely publish metrics (don't break app on failure).

        Args:
            metrics: MetricsCollector with collected metrics
            request: Optional request object
            response: Optional response object
            context: Optional platform context
        """
        # Only publish if publisher exists and is enabled
        if not self.publisher or not self.publisher.is_enabled():
            return

        try:
            self.publisher.publish(metrics, request, response, context)
        except Exception as e:
            logger.warning(f"Failed to publish metrics: {e}", exc_info=True)

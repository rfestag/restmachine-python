"""
Tests for MetricsHandler - platform adapter metrics lifecycle.

The MetricsHandler is used by platform adapters (AWS Lambda, ASGI) to
instrument the full request lifecycle with metrics collection and publishing.
"""

import pytest
from unittest.mock import Mock, MagicMock
from restmachine import RestApplication, Request, Response, HTTPMethod
from restmachine.metrics import MetricsCollector, MetricsPublisher
from restmachine.metrics_handler import MetricsHandler


@pytest.fixture
def app():
    """Create a test application."""
    app = RestApplication()

    @app.get("/test")
    def test_handler():
        return {"message": "test"}

    return app


@pytest.fixture
def mock_publisher():
    """Create a mock metrics publisher."""
    publisher = Mock(spec=MetricsPublisher)
    publisher.is_enabled.return_value = True
    return publisher


class TestMetricsHandlerInitialization:
    """Test MetricsHandler initialization."""

    def test_init_with_publisher(self, app, mock_publisher):
        """Test initialization with publisher."""
        handler = MetricsHandler(app, mock_publisher)

        assert handler.app is app
        assert handler.publisher is mock_publisher

    def test_init_without_publisher(self, app):
        """Test initialization without publisher."""
        handler = MetricsHandler(app)

        assert handler.app is app
        assert handler.publisher is None

    def test_create_collector(self, app):
        """Test creating metrics collector."""
        handler = MetricsHandler(app)
        collector = handler.create_collector()

        assert isinstance(collector, MetricsCollector)


class TestMetricsHandlerRequestLifecycle:
    """Test MetricsHandler request handling."""

    def test_handle_request_success(self, app, mock_publisher):
        """Test successful request handling with metrics."""
        handler = MetricsHandler(app, mock_publisher)

        # Mock event, context, and conversion functions
        event = {"path": "/test", "httpMethod": "GET"}
        context = {"requestId": "test-123"}

        def convert_fn(event, context):
            return Request(method=HTTPMethod.GET, path="/test", headers={})

        def execute_fn(request):
            return Response(status_code=200, body={"message": "test"})

        def response_fn(response, event, context):
            return {"statusCode": 200, "body": '{"message": "test"}'}

        # Execute
        result = handler.handle_request(
            event, context,
            convert_fn=convert_fn,
            execute_fn=execute_fn,
            response_fn=response_fn
        )

        # Verify result
        assert result == {"statusCode": 200, "body": '{"message": "test"}'}

        # Verify publisher was called
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Verify metrics were collected (timers become metrics when stopped)
        assert isinstance(metrics, MetricsCollector)
        assert "adapter.total_time" in metrics.metrics
        assert "adapter.event_to_request" in metrics.metrics
        assert "application.execute" in metrics.metrics
        assert "adapter.response_conversion" in metrics.metrics

    def test_handle_request_without_publisher(self, app):
        """Test request handling without publisher."""
        handler = MetricsHandler(app, publisher=None)

        event = {"path": "/test"}
        context = {}

        def convert_fn(event, context):
            return Request(method=HTTPMethod.GET, path="/test", headers={})

        def execute_fn(request):
            return Response(status_code=200, body={"message": "test"})

        def response_fn(response, event, context):
            return {"statusCode": 200}

        # Should not raise even without publisher
        result = handler.handle_request(
            event, context,
            convert_fn=convert_fn,
            execute_fn=execute_fn,
            response_fn=response_fn
        )

        assert result == {"statusCode": 200}

    def test_handle_request_with_disabled_publisher(self, app, mock_publisher):
        """Test request handling with disabled publisher."""
        mock_publisher.is_enabled.return_value = False
        handler = MetricsHandler(app, mock_publisher)

        event = {"path": "/test"}
        context = {}

        def convert_fn(event, context):
            return Request(method=HTTPMethod.GET, path="/test", headers={})

        def execute_fn(request):
            return Response(status_code=200, body={})

        def response_fn(response, event, context):
            return {"statusCode": 200}

        handler.handle_request(
            event, context,
            convert_fn=convert_fn,
            execute_fn=execute_fn,
            response_fn=response_fn
        )

        # Publisher should not be called when disabled
        mock_publisher.publish.assert_not_called()

    def test_handle_request_error_handling(self, app, mock_publisher):
        """Test error handling and error metrics."""
        handler = MetricsHandler(app, mock_publisher)

        event = {"path": "/error"}
        context = {"requestId": "error-123"}

        def convert_fn(event, context):
            return Request(method=HTTPMethod.GET, path="/error", headers={})

        def execute_fn(request):
            raise ValueError("Test error")

        def response_fn(response, event, context):
            return {"statusCode": 500}

        # Should raise the error
        with pytest.raises(ValueError, match="Test error"):
            handler.handle_request(
                event, context,
                convert_fn=convert_fn,
                execute_fn=execute_fn,
                response_fn=response_fn
            )

        # Verify error metrics were recorded and published
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Check error metrics
        assert "errors" in metrics.metrics
        assert metrics.metrics["errors"][0].value == 1
        assert "error" in metrics.metadata
        assert metrics.metadata["error"] == "Test error"
        assert metrics.metadata["error_type"] == "ValueError"

    def test_handle_request_conversion_error(self, app, mock_publisher):
        """Test error during event conversion."""
        handler = MetricsHandler(app, mock_publisher)

        event = {}
        context = {}

        def convert_fn(event, context):
            raise RuntimeError("Conversion failed")

        def execute_fn(request):
            return Response(status_code=200)

        def response_fn(response, event, context):
            return {}

        with pytest.raises(RuntimeError, match="Conversion failed"):
            handler.handle_request(
                event, context,
                convert_fn=convert_fn,
                execute_fn=execute_fn,
                response_fn=response_fn
            )

        # Should still publish error metrics
        mock_publisher.publish.assert_called_once()


class TestMetricsHandlerPublishing:
    """Test MetricsHandler metrics publishing."""

    def test_safe_publish_success(self, app, mock_publisher):
        """Test successful metrics publishing."""
        handler = MetricsHandler(app, mock_publisher)
        metrics = MetricsCollector()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})
        response = Response(status_code=200)
        context = {}

        handler._safe_publish(metrics, request, response, context)

        mock_publisher.publish.assert_called_once_with(
            metrics, request, response, context
        )

    def test_safe_publish_with_publisher_error(self, app, mock_publisher, caplog):
        """Test publishing with publisher error doesn't crash."""
        mock_publisher.publish.side_effect = Exception("Publish failed")
        handler = MetricsHandler(app, mock_publisher)
        metrics = MetricsCollector()

        # Should not raise
        handler._safe_publish(metrics)

        # Should log warning
        assert "Failed to publish metrics" in caplog.text

    def test_safe_publish_no_publisher(self, app):
        """Test publishing without publisher."""
        handler = MetricsHandler(app, publisher=None)
        metrics = MetricsCollector()

        # Should not raise
        handler._safe_publish(metrics)

    def test_safe_publish_minimal_args(self, app, mock_publisher):
        """Test publishing with minimal arguments."""
        handler = MetricsHandler(app, mock_publisher)
        metrics = MetricsCollector()

        handler._safe_publish(metrics)

        mock_publisher.publish.assert_called_once_with(
            metrics, None, None, None
        )


class TestMetricsHandlerIntegration:
    """Integration tests for MetricsHandler."""

    def test_full_request_lifecycle_with_metrics(self, app, mock_publisher):
        """Test complete request lifecycle with metrics collection."""
        handler = MetricsHandler(app, mock_publisher)

        # Simulate Lambda event
        event = {
            "path": "/test",
            "httpMethod": "GET",
            "headers": {},
        }
        context = {
            "requestId": "abc-123",
            "functionName": "test-function"
        }

        def convert_fn(event, context):
            return Request(
                method=HTTPMethod.GET,
                path=event["path"],
                headers=event.get("headers", {})
            )

        def execute_fn(request):
            # Simulate app execution
            return app.execute(request)

        def response_fn(response, event, context):
            return {
                "statusCode": response.status_code,
                "body": str(response.body)
            }

        result = handler.handle_request(
            event, context,
            convert_fn=convert_fn,
            execute_fn=execute_fn,
            response_fn=response_fn
        )

        # Verify response
        assert result["statusCode"] == 200

        # Verify metrics were published
        mock_publisher.publish.assert_called_once()
        metrics = mock_publisher.publish.call_args[0][0]

        # Verify all timing metrics exist (timers become metrics when stopped)
        assert "adapter.total_time" in metrics.metrics
        assert "adapter.event_to_request" in metrics.metrics
        assert "application.execute" in metrics.metrics
        assert "adapter.response_conversion" in metrics.metrics

        # Verify all timers were stopped (converted to metrics with values)
        for timer_name in ["adapter.total_time", "adapter.event_to_request",
                           "application.execute", "adapter.response_conversion"]:
            assert timer_name in metrics.metrics, f"{timer_name} was not recorded"
            assert len(metrics.metrics[timer_name]) > 0, f"{timer_name} has no values"

        # Verify dimensions and metadata
        assert metrics.metadata["status_code"] == 200
        assert metrics.dimensions["method"] == "GET"
        assert metrics.dimensions["path"] == "/test"

    def test_metrics_injected_into_app(self, app):
        """Test that metrics collector is injected into app cache."""
        handler = MetricsHandler(app)

        # Track if metrics were available
        metrics_available = []

        @app.get("/metrics-test")
        def handler_with_metrics(metrics: MetricsCollector):
            metrics_available.append(metrics is not None)
            return {"ok": True}

        event = {}
        context = {}

        def convert_fn(event, context):
            return Request(method=HTTPMethod.GET, path="/metrics-test", headers={})

        def execute_fn(request):
            return app.execute(request)

        def response_fn(response, event, context):
            return {"statusCode": 200}

        handler.handle_request(
            event, context,
            convert_fn=convert_fn,
            execute_fn=execute_fn,
            response_fn=response_fn
        )

        # Metrics should have been available in handler
        assert len(metrics_available) == 1
        assert metrics_available[0] is True

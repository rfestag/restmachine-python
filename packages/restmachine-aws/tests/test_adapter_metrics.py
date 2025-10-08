"""Tests for AWS adapter metrics integration."""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock

from restmachine import RestApplication
from restmachine.metrics import MetricsCollector, MetricUnit, METRICS
from restmachine_aws import AwsApiGatewayAdapter
from restmachine_aws.metrics import CloudWatchEMFPublisher


class TestAwsAdapterMetrics:
    """Tests for AWS adapter metrics integration."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        app = RestApplication()

        @app.get("/test")
        def test_handler(metrics):
            metrics.add_metric("test.requests", 1, unit=MetricUnit.Count)
            metrics.add_dimension("endpoint", "/test")
            return {"message": "ok"}

        return app

    @pytest.fixture
    def apigw_v2_event(self):
        """Create API Gateway v2 test event."""
        return {
            "version": "2.0",
            "routeKey": "GET /test",
            "rawPath": "/test",
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/test"
                }
            },
            "headers": {},
            "isBase64Encoded": False
        }

    def test_metrics_enabled_by_default(self, app):
        """Test that metrics are enabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = AwsApiGatewayAdapter(app)
            assert adapter.metrics_handler.publisher is not None
            assert isinstance(adapter.metrics_handler.publisher, CloudWatchEMFPublisher)

    def test_metrics_disabled_with_parameter(self, app):
        """Test disabling metrics with enable_metrics=False."""
        adapter = AwsApiGatewayAdapter(app, enable_metrics=False)
        assert adapter.metrics_handler.publisher is None

    def test_metrics_disabled_with_explicit_none(self, app):
        """Test disabling metrics with metrics_publisher=None."""
        adapter = AwsApiGatewayAdapter(app, metrics_publisher=None)
        assert adapter.metrics_handler.publisher is None

    def test_metrics_disabled_via_env_var(self, app):
        """Test disabling metrics via environment variable."""
        with patch.dict(os.environ, {'RESTMACHINE_METRICS_ENABLED': 'false'}):
            adapter = AwsApiGatewayAdapter(app)
            assert adapter.metrics_handler.publisher is None

    def test_custom_namespace_via_parameter(self, app):
        """Test setting custom namespace via parameter."""
        adapter = AwsApiGatewayAdapter(app, namespace="MyApp/API")
        assert adapter.metrics_handler.publisher.namespace == "MyApp/API"

    def test_custom_service_name_via_parameter(self, app):
        """Test setting custom service name via parameter."""
        adapter = AwsApiGatewayAdapter(app, service_name="user-service")
        assert adapter.metrics_handler.publisher.service_name == "user-service"

    def test_high_resolution_metrics_via_parameter(self, app):
        """Test enabling high-resolution metrics."""
        adapter = AwsApiGatewayAdapter(app, metrics_resolution=1)
        assert adapter.metrics_handler.publisher.default_resolution == 1

    def test_namespace_from_env_var(self, app):
        """Test that namespace can be set via environment variable."""
        with patch.dict(os.environ, {'RESTMACHINE_METRICS_NAMESPACE': 'EnvApp/API'}):
            adapter = AwsApiGatewayAdapter(app)
            assert adapter.metrics_handler.publisher.namespace == "EnvApp/API"

    def test_service_name_from_lambda_function_name(self, app):
        """Test that service name defaults to Lambda function name."""
        with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'my-function'}):
            adapter = AwsApiGatewayAdapter(app)
            assert adapter.metrics_handler.publisher.service_name == "my-function"

    def test_parameter_overrides_env_var(self, app):
        """Test that parameter takes precedence over environment variable."""
        with patch.dict(os.environ, {'RESTMACHINE_METRICS_NAMESPACE': 'EnvApp'}):
            adapter = AwsApiGatewayAdapter(
                app,
                namespace="ParamApp"
            )
            assert adapter.metrics_handler.publisher.namespace == "ParamApp"

    def test_metrics_injected_into_handler(self, app, apigw_v2_event):
        """Test that metrics collector is injected into handlers."""
        adapter = AwsApiGatewayAdapter(app, namespace="TestApp")

        with patch.object(adapter.metrics_handler.publisher.logger, 'isEnabledFor', return_value=False):
            response = adapter.handle_event(apigw_v2_event)

        assert response["statusCode"] == 200

    def test_metrics_published_on_success(self, app, apigw_v2_event):
        """Test that metrics are published on successful request."""
        adapter = AwsApiGatewayAdapter(app, namespace="TestApp")

        with patch.object(adapter.metrics_handler.publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(adapter.metrics_handler.publisher.logger, 'log') as mock_log:
                response = adapter.handle_event(apigw_v2_event)

                # Should have logged metrics
                assert mock_log.call_count == 1
                emf_data = json.loads(mock_log.call_args[0][1])

                # Check that handler metrics are included
                assert emf_data["test.requests"] == 1
                assert emf_data["endpoint"] == "/test"

                # Check that adapter metrics are included
                assert "adapter.total_time" in emf_data
                assert "adapter.event_to_request" in emf_data
                assert "application.execute" in emf_data

    def test_metrics_include_request_context(self, app, apigw_v2_event):
        """Test that metrics include request context."""
        adapter = AwsApiGatewayAdapter(app)

        with patch.object(adapter.metrics_handler.publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(adapter.metrics_handler.publisher.logger, 'log') as mock_log:
                response = adapter.handle_event(apigw_v2_event)

                emf_data = json.loads(mock_log.call_args[0][1])

                # Check dimensions
                assert emf_data["method"] == "GET"
                assert emf_data["path"] == "/test"

    def test_metrics_on_error(self, app, apigw_v2_event):
        """Test that metrics are published even on error."""
        # Create app with handler that raises error
        error_app = RestApplication()

        @error_app.get("/test")
        def error_handler(metrics):
            metrics.add_metric("before.error", 1)
            raise ValueError("Test error")

        adapter = AwsApiGatewayAdapter(error_app)

        with patch.object(adapter.metrics_handler.publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(adapter.metrics_handler.publisher.logger, 'log') as mock_log:
                # Adapter should return error response, not raise
                response = adapter.handle_event(apigw_v2_event)

                # Should have returned an error response
                assert response["statusCode"] == 400  # ValueError -> Bad Request

                # Should still have logged metrics
                assert mock_log.call_count == 1
                emf_data = json.loads(mock_log.call_args[0][1])

                # Check that handler metrics were collected before error
                assert emf_data["before.error"] == 1

    def test_custom_publisher(self, app, apigw_v2_event):
        """Test using a custom metrics publisher."""
        class CustomPublisher:
            def __init__(self):
                self.published = []

            def is_enabled(self):
                return True

            def publish(self, collector, request=None, response=None, context=None):
                self.published.append(collector)

        custom_publisher = CustomPublisher()
        adapter = AwsApiGatewayAdapter(app, metrics_publisher=custom_publisher)

        response = adapter.handle_event(apigw_v2_event)

        assert len(custom_publisher.published) == 1
        collector = custom_publisher.published[0]
        assert "test.requests" in collector.metrics

    def test_logging_configured_automatically(self, app):
        """Test that EMF logging is configured automatically."""
        import logging

        # Clear any existing handlers
        emf_logger = logging.getLogger("restmachine.metrics.emf")
        emf_logger.handlers.clear()

        adapter = AwsApiGatewayAdapter(app)

        # Should have configured the logger
        assert len(emf_logger.handlers) > 0
        assert emf_logger.level == METRICS
        assert emf_logger.propagate is False

    def test_does_not_reconfigure_logger_if_handlers_exist(self, app):
        """Test that logger is not reconfigured if handlers already exist."""
        import logging

        emf_logger = logging.getLogger("restmachine.metrics.emf")
        custom_handler = logging.NullHandler()
        emf_logger.addHandler(custom_handler)
        initial_handler_count = len(emf_logger.handlers)

        adapter = AwsApiGatewayAdapter(app)

        # Should not have added more handlers
        assert len(emf_logger.handlers) == initial_handler_count

    def test_metrics_always_available(self, app, apigw_v2_event):
        """Test that metrics collector is always available (even when disabled)."""
        metrics_value = None

        disabled_app = RestApplication()

        @disabled_app.get("/test")
        def test_handler(metrics):
            nonlocal metrics_value
            metrics_value = metrics
            # Should be able to use metrics even when disabled
            metrics.add_metric("test", 1)
            return {"ok": True}

        adapter = AwsApiGatewayAdapter(disabled_app, enable_metrics=False)
        response = adapter.handle_event(apigw_v2_event)

        # Metrics collector should always be provided (never None)
        from restmachine.metrics import MetricsCollector
        assert isinstance(metrics_value, MetricsCollector)

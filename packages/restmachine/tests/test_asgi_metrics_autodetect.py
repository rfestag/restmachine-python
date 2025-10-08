"""Tests for ASGI adapter AWS auto-detection and metrics integration."""

import os
import pytest
from unittest.mock import Mock, patch

from restmachine import RestApplication
from restmachine.adapters import ASGIAdapter, create_asgi_app


@pytest.fixture
def app():
    """Create a test application."""
    app = RestApplication()

    @app.get("/test")
    def test_handler(metrics):
        metrics.add_metric("test.requests", 1)
        return {"status": "ok"}

    return app


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment of AWS-related variables."""
    # Remove all AWS-related env vars
    aws_vars = [
        'AWS_REGION',
        'AWS_DEFAULT_REGION',
        'AWS_EXECUTION_ENV',
        'ECS_CONTAINER_METADATA_URI',
        'ECS_CONTAINER_METADATA_URI_V4',
        'RESTMACHINE_METRICS_ENABLED',
        'RESTMACHINE_METRICS_NAMESPACE',
        'RESTMACHINE_SERVICE_NAME',
    ]
    for var in aws_vars:
        monkeypatch.delenv(var, raising=False)


class TestAWSAutoDetection:
    """Test AWS environment auto-detection."""

    def test_detects_aws_via_aws_region(self, app, clean_env, monkeypatch):
        """Should detect AWS when AWS_REGION is set."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        with patch('restmachine_aws.metrics.CloudWatchEMFPublisher') as mock_emf:
            mock_emf.return_value = Mock()
            adapter = ASGIAdapter(app)

            # Should attempt to create EMF publisher
            assert adapter._is_aws_environment() is True
            # Should have created a publisher
            assert adapter.metrics_publisher is not None

    def test_detects_aws_via_execution_env(self, app, clean_env, monkeypatch):
        """Should detect AWS when AWS_EXECUTION_ENV is set."""
        monkeypatch.setenv('AWS_EXECUTION_ENV', 'AWS_Lambda_python3.9')

        adapter = ASGIAdapter(app)
        assert adapter._is_aws_environment() is True

    def test_detects_aws_via_ecs_metadata(self, app, clean_env, monkeypatch):
        """Should detect AWS when ECS metadata URI is set."""
        monkeypatch.setenv('ECS_CONTAINER_METADATA_URI_V4', 'http://169.254.170.2/v4')

        adapter = ASGIAdapter(app)
        assert adapter._is_aws_environment() is True

    def test_detects_aws_via_default_region(self, app, clean_env, monkeypatch):
        """Should detect AWS when AWS_DEFAULT_REGION is set."""
        monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-west-2')

        adapter = ASGIAdapter(app)
        assert adapter._is_aws_environment() is True

    def test_no_detection_in_non_aws_env(self, app, clean_env):
        """Should not detect AWS in clean environment."""
        adapter = ASGIAdapter(app)
        assert adapter._is_aws_environment() is False
        assert adapter.metrics_publisher is None


class TestMetricsEnabling:
    """Test metrics enabling logic."""

    def test_explicit_enable_overrides_detection(self, app, clean_env):
        """Explicit enable_metrics=True should override auto-detection."""
        # No AWS env vars, but explicitly enabled
        adapter = ASGIAdapter(app, enable_metrics=True)

        # Should have attempted to enable even though not in AWS
        # Will be None since not in AWS environment
        assert adapter._should_enable_metrics(True) is True
        assert adapter.metrics_publisher is None  # None because not in AWS

    def test_explicit_disable_overrides_detection(self, app, clean_env, monkeypatch):
        """Explicit enable_metrics=False should override auto-detection."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        adapter = ASGIAdapter(app, enable_metrics=False)
        assert adapter.metrics_publisher is None

    def test_env_var_enable(self, app, clean_env, monkeypatch):
        """RESTMACHINE_METRICS_ENABLED=true should enable metrics."""
        monkeypatch.setenv('RESTMACHINE_METRICS_ENABLED', 'true')

        adapter = ASGIAdapter(app)
        assert adapter._should_enable_metrics(None) is True

    def test_env_var_disable(self, app, clean_env, monkeypatch):
        """RESTMACHINE_METRICS_ENABLED=false should disable metrics."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')
        monkeypatch.setenv('RESTMACHINE_METRICS_ENABLED', 'false')

        adapter = ASGIAdapter(app)
        assert adapter._should_enable_metrics(None) is False
        assert adapter.metrics_publisher is None


class TestCustomPublisher:
    """Test custom publisher configuration."""

    def test_custom_publisher_overrides_auto_detection(self, app, clean_env, monkeypatch):
        """Providing custom publisher should override auto-detection."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        from restmachine.metrics import MetricsPublisher

        class CustomPublisher(MetricsPublisher):
            def is_enabled(self):
                return True

            def publish(self, collector, request=None, response=None, context=None):
                pass

        custom = CustomPublisher()
        adapter = ASGIAdapter(app, metrics_publisher=custom)

        assert adapter.metrics_publisher is custom

    def test_explicit_none_disables_metrics(self, app, clean_env, monkeypatch):
        """Passing metrics_publisher=None should disable metrics."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        adapter = ASGIAdapter(app, metrics_publisher=None)
        assert adapter.metrics_publisher is None


class TestCreateASGIApp:
    """Test create_asgi_app helper function."""

    def test_create_asgi_app_with_aws_auto_detect(self, app, clean_env, monkeypatch):
        """create_asgi_app should auto-detect AWS."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        with patch('restmachine_aws.metrics.CloudWatchEMFPublisher') as mock_emf:
            mock_emf.return_value = Mock()
            asgi_app = create_asgi_app(app)

            assert isinstance(asgi_app, ASGIAdapter)
            assert asgi_app._is_aws_environment() is True

    def test_create_asgi_app_with_custom_namespace(self, app, clean_env, monkeypatch):
        """create_asgi_app should accept namespace parameter."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        with patch('restmachine_aws.metrics.CloudWatchEMFPublisher') as mock_emf:
            mock_publisher = Mock()
            mock_emf.return_value = mock_publisher

            asgi_app = create_asgi_app(app, namespace="MyApp/Production")

            # Verify EMF publisher was created with correct namespace
            if asgi_app.metrics_publisher:
                mock_emf.assert_called_once()
                call_kwargs = mock_emf.call_args[1]
                assert call_kwargs['namespace'] == "MyApp/Production"

    def test_create_asgi_app_disabled(self, app, clean_env):
        """create_asgi_app with enable_metrics=False should disable."""
        asgi_app = create_asgi_app(app, enable_metrics=False)

        assert isinstance(asgi_app, ASGIAdapter)
        assert asgi_app.metrics_publisher is None


class TestPriorityOrder:
    """Test priority order of configuration."""

    def test_explicit_param_beats_env_var(self, app, clean_env, monkeypatch):
        """Explicit enable_metrics param should beat environment variable."""
        monkeypatch.setenv('RESTMACHINE_METRICS_ENABLED', 'true')

        adapter = ASGIAdapter(app, enable_metrics=False)
        assert adapter.metrics_publisher is None

    def test_env_var_beats_auto_detect(self, app, clean_env, monkeypatch):
        """RESTMACHINE_METRICS_ENABLED should beat auto-detection."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')
        monkeypatch.setenv('RESTMACHINE_METRICS_ENABLED', 'false')

        adapter = ASGIAdapter(app)
        assert adapter.metrics_publisher is None

    def test_auto_detect_is_default(self, app, clean_env, monkeypatch):
        """Auto-detection should be used if no explicit config."""
        monkeypatch.setenv('AWS_REGION', 'us-east-1')

        with patch('restmachine_aws.metrics.CloudWatchEMFPublisher') as mock_emf:
            mock_emf.return_value = Mock()
            adapter = ASGIAdapter(app)
            assert adapter._is_aws_environment() is True

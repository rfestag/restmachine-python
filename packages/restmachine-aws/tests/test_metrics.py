"""Tests for AWS CloudWatch EMF metrics."""

import pytest
import json
import logging
from unittest.mock import Mock, patch, MagicMock

from restmachine.metrics import MetricsCollector, MetricUnit, METRICS
from restmachine_aws.metrics import CloudWatchEMFPublisher


class TestCloudWatchEMFPublisher:
    """Tests for CloudWatchEMFPublisher."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        publisher = CloudWatchEMFPublisher()

        assert publisher.namespace == "RestMachine/Requests"
        assert publisher.service_name is None
        assert publisher.default_resolution == 60

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        publisher = CloudWatchEMFPublisher(
            namespace="MyApp/API",
            service_name="user-service",
            default_resolution=1
        )

        assert publisher.namespace == "MyApp/API"
        assert publisher.service_name == "user-service"
        assert publisher.default_resolution == 1

    def test_is_enabled_when_logger_enabled(self):
        """Test is_enabled returns True when logger is enabled."""
        publisher = CloudWatchEMFPublisher()

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            assert publisher.is_enabled() is True

    def test_is_enabled_when_logger_disabled(self):
        """Test is_enabled returns False when logger is disabled."""
        publisher = CloudWatchEMFPublisher()

        with patch.object(publisher.logger, 'isEnabledFor', return_value=False):
            assert publisher.is_enabled() is False

    def test_publish_when_disabled_does_nothing(self):
        """Test that publish does nothing when disabled."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()
        collector.add_metric("test", 1)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=False):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)
                mock_log.assert_not_called()

    def test_publish_emf_structure(self):
        """Test that published EMF has correct structure."""
        publisher = CloudWatchEMFPublisher(namespace="TestApp")
        collector = MetricsCollector()
        collector.add_metric("test.metric", 42, unit=MetricUnit.Count)
        collector.add_dimension("environment", "test")

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                # Get the logged EMF data
                assert mock_log.call_count == 1
                log_call = mock_log.call_args
                assert log_call[0][0] == METRICS

                emf_data = json.loads(log_call[0][1])

                # Check structure
                assert "_aws" in emf_data
                assert "CloudWatchMetrics" in emf_data["_aws"]
                assert "Timestamp" in emf_data["_aws"]

                # Check namespace
                assert emf_data["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "TestApp"

                # Check dimensions
                assert emf_data["environment"] == "test"

                # Check metrics
                assert emf_data["test.metric"] == 42

    def test_publish_with_service_name(self):
        """Test that service name is added as dimension."""
        publisher = CloudWatchEMFPublisher(
            namespace="TestApp",
            service_name="api-service"
        )
        collector = MetricsCollector()
        collector.add_metric("test", 1)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                emf_data = json.loads(mock_log.call_args[0][1])
                assert emf_data["service"] == "api-service"

    def test_publish_with_multiple_metric_values(self):
        """Test publishing multiple values for same metric."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()
        collector.add_metric("requests", 1, unit=MetricUnit.Count)
        collector.add_metric("requests", 3, unit=MetricUnit.Count)
        collector.add_metric("requests", 2, unit=MetricUnit.Count)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                emf_data = json.loads(mock_log.call_args[0][1])
                assert emf_data["requests"] == [1, 3, 2]

    def test_publish_with_high_resolution_metric(self):
        """Test publishing high-resolution metric."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()
        collector.add_metric("latency", 45.2, unit=MetricUnit.Milliseconds, resolution=1)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                emf_data = json.loads(mock_log.call_args[0][1])
                metrics_def = emf_data["_aws"]["CloudWatchMetrics"][0]["Metrics"][0]
                assert metrics_def["StorageResolution"] == 1

    def test_publish_with_metadata(self):
        """Test that metadata is included in EMF output."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()
        collector.add_metric("test", 1)
        collector.add_metadata("request_id", "abc-123")
        collector.add_metadata("user_id", 456)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                emf_data = json.loads(mock_log.call_args[0][1])
                assert emf_data["request_id"] == "abc-123"
                assert emf_data["user_id"] == 456

    def test_chunk_metrics_under_limit(self):
        """Test that metrics under 100 are not chunked."""
        publisher = CloudWatchEMFPublisher()
        metrics = {f"metric_{i}": [Mock(value=i)] for i in range(50)}

        chunks = publisher._chunk_metrics(metrics)

        assert len(chunks) == 1
        assert len(chunks[0]) == 50

    def test_chunk_metrics_over_limit(self):
        """Test that metrics over 100 are chunked."""
        publisher = CloudWatchEMFPublisher()
        metrics = {f"metric_{i}": [Mock(value=i)] for i in range(150)}

        chunks = publisher._chunk_metrics(metrics)

        assert len(chunks) == 2
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 50

    def test_publish_chunks_metrics_over_100(self):
        """Test that publisher creates multiple EMF objects for >100 metrics."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()

        # Add 150 metrics
        for i in range(150):
            collector.add_metric(f"metric_{i}", i)

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                publisher.publish(collector)

                # Should have 2 log calls (100 + 50)
                assert mock_log.call_count == 2

    def test_truncates_dimensions_over_30(self):
        """Test that dimensions over 30 are truncated with warning."""
        publisher = CloudWatchEMFPublisher()
        collector = MetricsCollector()
        collector.add_metric("test", 1)

        # Add 35 dimensions
        for i in range(35):
            collector.add_dimension(f"dim_{i}", f"value_{i}")

        with patch.object(publisher.logger, 'isEnabledFor', return_value=True):
            with patch.object(publisher.logger, 'log') as mock_log:
                with patch.object(publisher.logger, 'warning') as mock_warning:
                    publisher.publish(collector)

                    # Should log warning
                    mock_warning.assert_called_once()
                    assert "Too many dimensions" in mock_warning.call_args[0][0]

                    # Should only include 30 dimensions
                    emf_data = json.loads(mock_log.call_args[0][1])
                    dimension_keys = emf_data["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
                    assert len(dimension_keys) == 30

    def test_build_emf_with_all_features(self):
        """Test building complete EMF with all features."""
        publisher = CloudWatchEMFPublisher(
            namespace="MyApp",
            service_name="api"
        )

        collector = MetricsCollector()
        collector.add_metric("requests", 1, unit=MetricUnit.Count)
        collector.add_metric("latency", 45.2, unit=MetricUnit.Milliseconds, resolution=1)
        collector.add_dimension("method", "GET")
        collector.add_dimension("path", "/users")

        metrics = {
            "requests": collector.metrics["requests"],
            "latency": collector.metrics["latency"]
        }
        dimensions = collector.get_all_dimensions()
        dimensions["service"] = "api"
        metadata = {"trace_id": "xyz"}

        emf = publisher._build_emf(metrics, dimensions, metadata)

        # Verify structure
        assert emf["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "MyApp"
        assert "requests" in emf
        assert "latency" in emf
        assert emf["method"] == "GET"
        assert emf["path"] == "/users"
        assert emf["service"] == "api"
        assert emf["trace_id"] == "xyz"

        # Verify metrics definitions
        metrics_defs = emf["_aws"]["CloudWatchMetrics"][0]["Metrics"]
        assert len(metrics_defs) == 2

        # Check high-resolution metric
        latency_def = next(m for m in metrics_defs if m["Name"] == "latency")
        assert latency_def["StorageResolution"] == 1

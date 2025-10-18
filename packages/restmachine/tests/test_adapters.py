"""
Tests for ASGI adapter - platform integration for ASGI servers.

The ASGIAdapter enables RestMachine applications to run on ASGI servers
(Uvicorn, Hypercorn, etc.) with streaming, metrics, and lifecycle support.
"""

import asyncio
import io
import json
import os
import pytest
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from restmachine import RestApplication, Request, Response, HTTPMethod
from restmachine.adapters import ASGIAdapter, create_asgi_app
from restmachine.metrics import MetricsCollector, MetricsPublisher
from restmachine.models import MultiValueHeaders

pytestmark = pytest.mark.anyio


# Test fixtures

@pytest.fixture
def app():
    """Create a test application."""
    app = RestApplication()

    @app.get("/test")
    def test_handler():
        return {"message": "test"}

    @app.get("/metrics-test")
    def metrics_handler(metrics: MetricsCollector):
        metrics.add_metric("custom_metric", 1)
        return {"metrics": "collected"}

    @app.post("/echo")
    def echo_handler(request: Request):
        if request.body:
            content = request.body.read()
            return {"received": content.decode("utf-8")}
        return {"received": ""}

    return app


@pytest.fixture
def mock_publisher():
    """Create a mock metrics publisher."""
    publisher = Mock(spec=MetricsPublisher)
    publisher.is_enabled.return_value = True
    return publisher


# Helper functions for ASGI testing

async def receive_from_messages(messages: List[Dict[str, Any]]):
    """Create a receive callable from a list of messages."""
    messages_iter = iter(messages)

    async def receive():
        try:
            return next(messages_iter)
        except StopIteration:
            # Return empty message if no more messages
            return {"type": "http.request", "body": b"", "more_body": False}

    return receive


def create_basic_scope(path="/test", method="GET", headers=None, query_string=b""):
    """Create a basic ASGI HTTP scope."""
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
        "headers": headers or [],
        "scheme": "http",
        "server": ("localhost", 8000),
        "asgi": {"version": "3.0"},
    }


class MockSend:
    """Mock ASGI send callable that records messages."""

    def __init__(self):
        self.messages = []

    async def __call__(self, message: Dict[str, Any]):
        self.messages.append(message)

    def get_response_start(self):
        """Get the http.response.start message."""
        for msg in self.messages:
            if msg.get("type") == "http.response.start":
                return msg
        return None

    def get_response_body(self):
        """Get all http.response.body messages concatenated."""
        body_parts = []
        for msg in self.messages:
            if msg.get("type") == "http.response.body":
                body_parts.append(msg.get("body", b""))
        return b"".join(body_parts)

    def get_status(self):
        """Get response status code."""
        start = self.get_response_start()
        return start["status"] if start else None

    def get_headers(self):
        """Get response headers as dict (normalized to lowercase)."""
        start = self.get_response_start()
        if not start:
            return {}
        headers = {}
        for name, value in start.get("headers", []):
            # Normalize to lowercase for case-insensitive comparison
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        return headers


# Tests

class TestASGIAdapterInitialization:
    """Test ASGIAdapter initialization and configuration."""

    def test_init_basic(self, app):
        """Test basic initialization without metrics."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)

            assert adapter.app is app
            assert adapter.metrics_publisher is None

    def test_init_with_custom_publisher(self, app, mock_publisher):
        """Test initialization with custom publisher."""
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        assert adapter.app is app
        assert adapter.metrics_publisher is mock_publisher

    def test_init_disable_metrics_explicitly(self, app):
        """Test explicitly disabling metrics."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        assert adapter.metrics_publisher is None

    def test_is_aws_environment_aws_region(self, app):
        """Test AWS detection via AWS_REGION."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._is_aws_environment() is True

    def test_is_aws_environment_execution_env(self, app):
        """Test AWS detection via AWS_EXECUTION_ENV."""
        with patch.dict(os.environ, {"AWS_EXECUTION_ENV": "AWS_ECS_FARGATE"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._is_aws_environment() is True

    def test_is_aws_environment_ecs_metadata(self, app):
        """Test AWS detection via ECS metadata URI."""
        with patch.dict(os.environ, {"ECS_CONTAINER_METADATA_URI": "http://169.254.170.2/v3"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._is_aws_environment() is True

    def test_is_aws_environment_default_region(self, app):
        """Test AWS detection via AWS_DEFAULT_REGION."""
        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "us-west-2"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._is_aws_environment() is True

    def test_is_not_aws_environment(self, app):
        """Test non-AWS environment."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._is_aws_environment() is False

    def test_should_enable_metrics_explicit_true(self, app):
        """Test explicit enable overrides auto-detection."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            # Even though not in AWS, explicit True should enable
            assert adapter._should_enable_metrics(True) is True

    def test_should_enable_metrics_explicit_false(self, app):
        """Test explicit disable overrides auto-detection."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            # Even in AWS, explicit False should disable
            assert adapter._should_enable_metrics(False) is False

    def test_should_enable_metrics_env_var_true(self, app):
        """Test RESTMACHINE_METRICS_ENABLED=true."""
        with patch.dict(os.environ, {"RESTMACHINE_METRICS_ENABLED": "true"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._should_enable_metrics(None) is True

    def test_should_enable_metrics_env_var_false(self, app):
        """Test RESTMACHINE_METRICS_ENABLED=false."""
        with patch.dict(os.environ, {"RESTMACHINE_METRICS_ENABLED": "false", "AWS_REGION": "us-east-1"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            # Env var should override AWS detection
            assert adapter._should_enable_metrics(None) is False

    def test_should_enable_metrics_aws_auto_detect(self, app):
        """Test metrics auto-enabled in AWS."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            assert adapter._should_enable_metrics(None) is True

    def test_create_default_publisher_non_aws(self, app):
        """Test no default publisher in non-AWS environment."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            publisher = adapter._create_default_publisher()
            assert publisher is None

    def test_create_default_publisher_aws_without_package(self, app):
        """Test AWS detection but restmachine-aws not installed."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)
            # Mock the import to fail by patching builtins.__import__
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "restmachine_aws.metrics":
                    raise ImportError("restmachine-aws not installed")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                publisher = adapter._create_default_publisher()
                # Should return None and log warning
                assert publisher is None


class TestASGIAdapterRequestConversion:
    """Test converting ASGI scope to Request."""

    # Async test - handled by pytest-anyio
    async def test_start_request_basic_get(self, app):
        """Test basic GET request conversion."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert request.method == HTTPMethod.GET
        assert request.path == "/test"
        assert more_body is False
        assert request.body is None  # Empty body

    # Async test - handled by pytest-anyio
    async def test_start_request_with_query_params(self, app):
        """Test request with query parameters."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(
            path="/test",
            method="GET",
            query_string=b"foo=bar&baz=qux"
        )

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert request.query_params == {"foo": "bar", "baz": "qux"}

    # Async test - handled by pytest-anyio
    async def test_start_request_with_headers(self, app):
        """Test request with headers."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(
            path="/test",
            method="GET",
            headers=[
                [b"content-type", b"application/json"],
                [b"authorization", b"Bearer token123"],
            ]
        )

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert request.headers.get("content-type") == "application/json"
        assert request.headers.get("authorization") == "Bearer token123"

    # Async test - handled by pytest-anyio
    async def test_start_request_with_body(self, app):
        """Test request with body."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="POST")

        async def receive():
            return {"type": "http.request", "body": b"test body", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert more_body is False
        assert request.body is not None
        content = request.body.read()
        assert content == b"test body"

    # Async test - handled by pytest-anyio
    async def test_start_request_with_streaming_body(self, app):
        """Test request with streaming body."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="POST")

        async def receive():
            return {"type": "http.request", "body": b"chunk1", "more_body": True}

        request, more_body = await adapter._start_request(scope, receive)

        assert more_body is True
        assert request.body is not None
        # First chunk should be available
        chunk = request.body.read(6)
        assert chunk == b"chunk1"

    # Async test - handled by pytest-anyio
    async def test_start_request_https(self, app):
        """Test HTTPS request (TLS)."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="GET")
        scope["scheme"] = "https"

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert request.tls is True

    # Async test - handled by pytest-anyio
    async def test_start_request_with_client_cert(self, app):
        """Test request with client certificate (mutual TLS)."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="GET")
        scope["scheme"] = "https"
        scope["extensions"] = {
            "tls": {
                "client_cert": "-----BEGIN CERTIFICATE-----\nMIIC..."
            }
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request, more_body = await adapter._start_request(scope, receive)

        assert request.tls is True
        assert request.client_cert == "-----BEGIN CERTIFICATE-----\nMIIC..."


class TestASGIAdapterResponseConversion:
    """Test converting Response to ASGI response."""

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_json(self, app):
        """Test JSON response conversion."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        response = Response(
            status_code=200,
            body={"message": "test"},
            headers={}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        headers = send.get_headers()
        assert "content-type" in headers
        assert headers["content-type"] == "application/json"
        body = send.get_response_body()
        assert json.loads(body) == {"message": "test"}

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_bytes(self, app):
        """Test bytes response conversion."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        response = Response(
            status_code=200,
            body=b"raw bytes",
            headers={"Content-Type": "application/octet-stream"}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        body = send.get_response_body()
        assert body == b"raw bytes"

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_string(self, app):
        """Test string response conversion."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        response = Response(
            status_code=200,
            body="text response",
            headers={"Content-Type": "text/plain"}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        body = send.get_response_body()
        assert body == b"text response"

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_stream(self, app):
        """Test streaming response."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create a stream
        stream = io.BytesIO(b"streaming data")

        response = Response(
            status_code=200,
            body=stream,
            headers={"Content-Type": "application/octet-stream"}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        body = send.get_response_body()
        assert body == b"streaming data"

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_with_custom_headers(self, app):
        """Test response with custom headers."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        headers = MultiValueHeaders()
        headers.add("X-Custom-Header", "value1")
        headers.add("X-Another", "value2")

        response = Response(
            status_code=200,
            body={"message": "test"},
            headers=headers
        )

        await adapter._response_to_asgi(response, send)

        response_headers = send.get_headers()
        assert "x-custom-header" in response_headers
        assert response_headers["x-custom-header"] == "value1"
        assert "x-another" in response_headers
        assert response_headers["x-another"] == "value2"

    # Async test - handled by pytest-anyio
    async def test_response_to_asgi_empty_body(self, app):
        """Test response with empty body."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        response = Response(
            status_code=204,
            body=None,
            headers={}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 204
        body = send.get_response_body()
        assert body == b""


class TestASGIAdapterHTTPHandling:
    """Test full HTTP request/response handling."""

    # Async test - handled by pytest-anyio
    async def test_handle_basic_get_request(self, app):
        """Test handling basic GET request."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        assert send.get_status() == 200
        body = json.loads(send.get_response_body())
        assert body == {"message": "test"}

    # Async test - handled by pytest-anyio
    async def test_handle_post_request_with_body(self, app):
        """Test handling POST request with body."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/echo", method="POST")

        async def receive():
            return {"type": "http.request", "body": b"hello world", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        assert send.get_status() == 200
        body = json.loads(send.get_response_body())
        assert body == {"received": "hello world"}

    # Async test - handled by pytest-anyio
    async def test_handle_streaming_request_body(self, app):
        """Test that streaming request bodies are supported.

        Note: Synchronous handlers only receive the first chunk immediately.
        The background task continues receiving, but synchronous read() doesn't
        block waiting for more chunks. For full streaming, use async handlers.
        """
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/echo", method="POST")

        chunks = [
            {"type": "http.request", "body": b"chunk1", "more_body": True},
            {"type": "http.request", "body": b"chunk2", "more_body": True},
            {"type": "http.request", "body": b"chunk3", "more_body": False},
        ]
        chunks_iter = iter(chunks)

        async def receive():
            return next(chunks_iter)

        send = MockSend()

        await adapter(scope, receive, send)

        assert send.get_status() == 200
        body = json.loads(send.get_response_body())
        # Synchronous handler only gets first chunk (BytesIO.read() doesn't block)
        # Full streaming requires async handlers or buffering all chunks first
        assert body == {"received": "chunk1"}

    # Async test - handled by pytest-anyio
    async def test_handle_not_found(self, app):
        """Test handling 404 Not Found."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/nonexistent", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        assert send.get_status() == 404

    # Async test - handled by pytest-anyio
    async def test_handle_unsupported_protocol(self, app):
        """Test handling unsupported ASGI protocol."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = {
            "type": "websocket",  # Not supported
            "path": "/ws",
        }

        async def receive():
            return {}

        send = MockSend()

        await adapter(scope, receive, send)

        assert send.get_status() == 404
        body = send.get_response_body()
        assert b"Only HTTP protocol is supported" in body


class TestASGIAdapterLifespan:
    """Test ASGI lifespan protocol handling."""

    # Async test - handled by pytest-anyio
    async def test_lifespan_startup_success(self, app):
        """Test successful startup."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        startup_called = []

        @app.on_startup
        async def on_startup():
            startup_called.append(True)

        scope = {"type": "lifespan"}

        messages = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        messages_iter = iter(messages)

        async def receive():
            return next(messages_iter)

        send = MockSend()

        await adapter(scope, receive, send)

        # Check startup was called
        assert len(startup_called) == 1

        # Check messages sent
        assert len(send.messages) == 2
        assert send.messages[0]["type"] == "lifespan.startup.complete"
        assert send.messages[1]["type"] == "lifespan.shutdown.complete"

    # Async test - handled by pytest-anyio
    async def test_lifespan_startup_failure(self, app):
        """Test startup failure."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        @app.on_startup
        async def on_startup():
            raise RuntimeError("Startup failed")

        scope = {"type": "lifespan"}

        async def receive():
            return {"type": "lifespan.startup"}

        send = MockSend()

        with pytest.raises(RuntimeError, match="Startup failed"):
            await adapter(scope, receive, send)

        # Check failure message sent
        assert len(send.messages) == 1
        assert send.messages[0]["type"] == "lifespan.startup.failed"
        assert "Startup failed" in send.messages[0]["message"]

    # Async test - handled by pytest-anyio
    async def test_lifespan_shutdown_success(self, app):
        """Test successful shutdown."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        shutdown_called = []

        @app.on_shutdown
        async def on_shutdown():
            shutdown_called.append(True)

        scope = {"type": "lifespan"}

        messages = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        messages_iter = iter(messages)

        async def receive():
            return next(messages_iter)

        send = MockSend()

        await adapter(scope, receive, send)

        # Check shutdown was called
        assert len(shutdown_called) == 1

        # Check shutdown complete message
        assert send.messages[1]["type"] == "lifespan.shutdown.complete"


class TestASGIAdapterErrorHandling:
    """Test error handling in ASGI adapter."""

    # Async test - handled by pytest-anyio
    async def test_handle_application_error(self, app):
        """Test that application errors are handled by RestMachine's execute()."""
        # Add handler that raises error
        @app.get("/error")
        def error_handler():
            raise ValueError("Test error")

        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = create_basic_scope(path="/error", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # RestMachine converts ValueError to 400 Bad Request (client error)
        # The adapter's except block only catches adapter-level errors
        status = send.get_status()
        body_bytes = send.get_response_body()

        # ValueError → 400 Bad Request (correct behavior)
        assert status == 400
        body = json.loads(body_bytes)
        assert "error" in body
        assert "Test error" in body["error"]

    # Async test - handled by pytest-anyio
    async def test_error_metrics_recorded(self, app, mock_publisher):
        """Test that error metrics are recorded."""
        # Add handler that raises error
        @app.get("/error")
        def error_handler():
            raise ValueError("Test error")

        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        scope = create_basic_scope(path="/error", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # Verify metrics were published (application handled the error, not adapter)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Metrics should be recorded even for error responses
        # (No "errors" metric because app.execute() handled it, not adapter)
        assert "adapter.total_time" in metrics.metrics
        assert metrics.metadata["status_code"] == 400


class TestASGIAdapterMetrics:
    """Test metrics collection and publishing in ASGI adapter."""

    # Async test - handled by pytest-anyio
    async def test_metrics_collected(self, app, mock_publisher):
        """Test that metrics are collected during request."""
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        scope = create_basic_scope(path="/test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # Verify metrics were published
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Verify timing metrics exist
        assert "adapter.total_time" in metrics.metrics
        assert "adapter.scope_to_request" in metrics.metrics
        assert "application.execute" in metrics.metrics
        assert "adapter.response_conversion" in metrics.metrics

        # Verify metadata
        assert metrics.metadata["status_code"] == 200
        assert metrics.dimensions["method"] == "GET"
        assert metrics.dimensions["path"] == "/test"

    # Async test - handled by pytest-anyio
    async def test_metrics_injected_into_app(self, app, mock_publisher):
        """Test that metrics collector is injected into app."""
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        scope = create_basic_scope(path="/metrics-test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # Verify request succeeded
        assert send.get_status() == 200

        # Verify metrics were published (handler added custom metric)
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Custom metric should be present
        assert "custom_metric" in metrics.metrics

    # Async test - handled by pytest-anyio
    async def test_metrics_not_published_when_disabled(self, app, mock_publisher):
        """Test metrics not published when publisher disabled."""
        mock_publisher.is_enabled.return_value = False
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        scope = create_basic_scope(path="/test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # Verify publish was not called
        mock_publisher.publish.assert_not_called()

    # Async test - handled by pytest-anyio
    async def test_metrics_publishing_failure_handled(self, app, mock_publisher):
        """Test that metrics publishing failures don't crash requests."""
        mock_publisher.publish.side_effect = Exception("Publish failed")
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        scope = create_basic_scope(path="/test", method="GET")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        # Should not raise
        await adapter(scope, receive, send)

        # Request should still succeed
        assert send.get_status() == 200


class TestASGIAdapterRangeRequests:
    """Test range request support (RFC 9110 Section 14)."""

    # Async test - handled by pytest-anyio
    async def test_range_response_with_bytes(self, app):
        """Test 206 Partial Content with bytes body."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create a range response
        body_data = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        response = Response(
            status_code=206,
            body=body_data,
            headers={"Content-Range": "bytes 10-19/36", "Content-Length": "10"}
        )
        response.range_start = 10
        response.range_end = 19

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 206
        body = send.get_response_body()
        assert body == b"ABCDEFGHIJ"  # bytes 10-19

    # Async test - handled by pytest-anyio
    async def test_range_response_with_stream(self, app):
        """Test 206 Partial Content with seekable stream."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create a stream
        stream_data = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        stream = io.BytesIO(stream_data)

        response = Response(
            status_code=206,
            body=stream,
            headers={"Content-Range": "bytes 5-14/36", "Content-Length": "10"}
        )
        response.range_start = 5
        response.range_end = 14

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 206
        body = send.get_response_body()
        assert body == b"56789ABCDE"  # bytes 5-14

    # Async test - handled by pytest-anyio
    async def test_range_response_with_path_zerocopysend(self, app, tmp_path):
        """Test 206 Partial Content with Path using zero-copy send."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create test file
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        response = Response(
            status_code=206,
            body=test_file,
            headers={"Content-Range": "bytes 20-29/36", "Content-Length": "10"}
        )
        response.range_start = 20
        response.range_end = 29

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 206
        # Check that zerocopysend was attempted
        zerocopysend_msgs = [m for m in send.messages if m.get("type") == "http.response.zerocopysend"]
        if zerocopysend_msgs:
            # Server supports zero-copy
            assert zerocopysend_msgs[0]["file"] == str(test_file.absolute())
            assert zerocopysend_msgs[0]["offset"] == 20
            assert zerocopysend_msgs[0]["count"] == 10
        else:
            # Fallback to streaming
            body = send.get_response_body()
            assert body == b"KLMNOPQRST"

    # Async test - handled by pytest-anyio
    async def test_range_response_with_path_fallback(self, app, tmp_path):
        """Test 206 Partial Content with Path falling back to streaming."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        # Create mock send that rejects zerocopysend
        class MockSendNoZeroCopy(MockSend):
            async def __call__(self, message: Dict[str, Any]):
                if message.get("type") == "http.response.zerocopysend":
                    raise KeyError("zerocopysend not supported")
                await super().__call__(message)

        send = MockSendNoZeroCopy()

        # Create test file
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        response = Response(
            status_code=206,
            body=test_file,
            headers={"Content-Range": "bytes 15-24/36", "Content-Length": "10"}
        )
        response.range_start = 15
        response.range_end = 24

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 206
        body = send.get_response_body()
        assert body == b"FGHIJKLMNO"  # bytes 15-24

    # Async test - handled by pytest-anyio
    async def test_range_response_validation_error(self, app):
        """Test range response with missing range fields raises error."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create invalid range response (missing range_start)
        response = Response(
            status_code=206,
            body=b"test data",
            headers={}
        )
        response.range_end = 10  # Only set range_end, not range_start

        with pytest.raises(ValueError, match="Range response missing range_start or range_end"):
            await adapter._send_range_response(response, send)

    # Async test - handled by pytest-anyio
    async def test_send_chunked_bytes(self, app):
        """Test _send_chunked_bytes helper method."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create stream with known data
        stream = io.BytesIO(b"A" * 200000)  # 200KB

        # Send 100KB in chunks
        await adapter._send_chunked_bytes(stream, send, 100000, chunk_size=32768)

        # Verify all chunks sent
        body = send.get_response_body()
        assert len(body) == 100000
        assert body == b"A" * 100000


class TestASGIAdapterPathFileServing:
    """Test Path file serving with pathsend extension."""

    # Async test - handled by pytest-anyio
    async def test_response_with_path_existing_file(self, app, tmp_path):
        """Test serving existing file via Path."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from file!")

        response = Response(
            status_code=200,
            body=test_file,
            headers={"Content-Type": "text/plain"}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        # Check pathsend extension was added
        start_msg = send.get_response_start()
        if "extensions" in start_msg:
            assert "http.response.pathsend" in start_msg["extensions"]
            assert start_msg["extensions"]["http.response.pathsend"]["path"] == str(test_file.absolute())
        # Body should be streamed as fallback
        body = send.get_response_body()
        assert body == b"Hello from file!"

    # Async test - handled by pytest-anyio
    async def test_response_with_path_nonexistent_file(self, app, tmp_path):
        """Test serving nonexistent file via Path."""
        adapter = ASGIAdapter(app, enable_metrics=False)
        send = MockSend()

        # Create path to nonexistent file
        test_file = tmp_path / "nonexistent.txt"

        response = Response(
            status_code=200,
            body=test_file,
            headers={}
        )

        await adapter._response_to_asgi(response, send)

        assert send.get_status() == 200
        # Should send empty body
        body = send.get_response_body()
        assert body == b""


class TestASGIAdapterExceptionHandling:
    """Test adapter-level exception handling."""

    # Async test - handled by pytest-anyio
    async def test_adapter_exception_during_request_conversion(self, app):
        """Test exception during ASGI scope to Request conversion."""
        adapter = ASGIAdapter(app, enable_metrics=False)

        # Create invalid scope that will cause conversion error
        scope = create_basic_scope(path="/test", method="INVALID_METHOD")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        # Should catch exception and return 500
        await adapter(scope, receive, send)

        assert send.get_status() == 500
        body = json.loads(send.get_response_body())
        assert "error" in body

    # Async test - handled by pytest-anyio
    async def test_adapter_exception_metrics_recorded(self, app, mock_publisher):
        """Test that adapter-level exceptions record error metrics."""
        adapter = ASGIAdapter(app, metrics_publisher=mock_publisher)

        # Create invalid scope
        scope = create_basic_scope(path="/test", method="INVALID_METHOD")

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        send = MockSend()

        await adapter(scope, receive, send)

        # Verify error metrics were published
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args[0]
        metrics = call_args[0]

        # Should have error metrics from adapter exception handler
        assert "errors" in metrics.metrics
        assert "error" in metrics.metadata


class TestASGIAdapterLifespanErrors:
    """Test lifespan error handling."""

    # Async test - handled by pytest-anyio
    async def test_lifespan_shutdown_error(self, caplog):
        """Test error during shutdown is logged but doesn't fail lifespan.

        Individual shutdown handlers that fail are caught and logged by the
        application, so the lifespan completes successfully from the adapter's
        perspective. This matches ASGI best practices.
        """
        # Create fresh app for this test
        app = RestApplication()

        # Register shutdown handler that will fail
        @app.on_shutdown
        async def on_shutdown():
            raise RuntimeError("Shutdown error")

        adapter = ASGIAdapter(app, enable_metrics=False)

        scope = {"type": "lifespan"}

        messages = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        messages_iter = iter(messages)

        async def receive():
            return next(messages_iter)

        send = MockSend()

        # Should not raise - error is logged
        await adapter(scope, receive, send)

        # Check shutdown completed (errors in handlers are logged but don't fail lifespan)
        assert len(send.messages) == 2
        assert send.messages[1]["type"] == "lifespan.shutdown.complete"

        # Verify error was logged
        assert "Shutdown error" in caplog.text


class TestASGIAdapterAWSCloudWatchSetup:
    """Test AWS CloudWatch EMF publisher auto-configuration."""

    def test_create_default_publisher_in_aws(self, app):
        """Test CloudWatch publisher creation in AWS environment."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=True):
            # Mock the CloudWatch publisher import (imported inside the function)
            mock_publisher = Mock(spec=MetricsPublisher)

            with patch("restmachine_aws.metrics.CloudWatchEMFPublisher", return_value=mock_publisher) as mock_class:
                adapter = ASGIAdapter(app, enable_metrics=False)
                publisher = adapter._create_default_publisher(
                    namespace="TestApp",
                    service_name="test-service",
                    resolution=60
                )

                # Verify CloudWatch publisher was created with correct params
                mock_class.assert_called_once_with(
                    namespace="TestApp",
                    service_name="test-service",
                    default_resolution=60
                )
                assert publisher is mock_publisher

    def test_create_default_publisher_with_env_vars(self, app):
        """Test CloudWatch publisher uses environment variables."""
        with patch.dict(os.environ, {
            "AWS_REGION": "us-west-2",
            "RESTMACHINE_METRICS_NAMESPACE": "MyApp",
            "RESTMACHINE_SERVICE_NAME": "my-service",
            "RESTMACHINE_METRICS_RESOLUTION": "1"
        }, clear=True):
            mock_publisher = Mock(spec=MetricsPublisher)

            with patch("restmachine_aws.metrics.CloudWatchEMFPublisher", return_value=mock_publisher) as mock_class:
                adapter = ASGIAdapter(app, enable_metrics=False)
                publisher = adapter._create_default_publisher()

                # Should use env vars
                mock_class.assert_called_once()
                call_kwargs = mock_class.call_args[1]
                assert call_kwargs["namespace"] == "MyApp"
                assert call_kwargs["service_name"] == "my-service"
                # Resolution validation logic is in the adapter
                # Since we pass resolution arg, it should be used

    def test_create_default_publisher_invalid_resolution(self, app):
        """Test CloudWatch publisher handles invalid resolution."""
        with patch.dict(os.environ, {
            "AWS_REGION": "us-east-1",
            "RESTMACHINE_METRICS_RESOLUTION": "invalid"
        }, clear=True):
            mock_publisher = Mock(spec=MetricsPublisher)

            with patch("restmachine_aws.metrics.CloudWatchEMFPublisher", return_value=mock_publisher) as mock_class:
                adapter = ASGIAdapter(app, enable_metrics=False)
                # Pass invalid resolution that will be validated
                publisher = adapter._create_default_publisher(resolution=99)

                # Should fall back to env var, which is invalid, then to 60
                mock_class.assert_called_once()
                call_kwargs = mock_class.call_args[1]
                assert call_kwargs["default_resolution"] == 60

    def test_configure_default_logging(self, app):
        """Test EMF logging configuration."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = ASGIAdapter(app, enable_metrics=False)

            # Configure logging
            adapter._configure_default_logging()

            # Verify EMF logger was configured
            import logging
            emf_logger = logging.getLogger("restmachine.metrics.emf")
            assert emf_logger.level == logging.INFO + 5  # METRICS level
            assert len(emf_logger.handlers) > 0
            assert emf_logger.propagate is False


class TestCreateASGIApp:
    """Test create_asgi_app convenience function."""

    def test_create_asgi_app_basic(self, app):
        """Test creating ASGI app with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            asgi_app = create_asgi_app(app, enable_metrics=False)

            assert isinstance(asgi_app, ASGIAdapter)
            assert asgi_app.app is app

    def test_create_asgi_app_with_publisher(self, app, mock_publisher):
        """Test creating ASGI app with custom publisher."""
        asgi_app = create_asgi_app(app, metrics_publisher=mock_publisher)

        assert isinstance(asgi_app, ASGIAdapter)
        assert asgi_app.metrics_publisher is mock_publisher

    def test_create_asgi_app_with_kwargs(self, app):
        """Test creating ASGI app with additional kwargs."""
        asgi_app = create_asgi_app(
            app,
            enable_metrics=False,
            namespace="TestApp",
            service_name="test-service"
        )

        assert isinstance(asgi_app, ASGIAdapter)

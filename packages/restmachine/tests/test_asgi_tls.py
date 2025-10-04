"""
Tests for ASGI TLS extension support.
"""

import pytest

from restmachine import RestApplication, HTTPMethod

pytestmark = pytest.mark.anyio


class TestASGITLSExtension:
    """Test ASGI TLS extension support in the ASGI adapter."""

    async def test_https_request_sets_tls_true(self):
        """HTTPS requests should have tls=True."""
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {"tls": request.tls}

        asgi_app = ASGIAdapter(app)

        # Create HTTPS scope
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "scheme": "https",  # HTTPS connection
            "headers": [[b"accept", b"application/json"]],
            "query_string": b"",
        }

        # Mock receive and send
        received_body = []
        sent_response = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent_response.append(message)

        # Execute request
        await asgi_app(scope, receive, send)

        # Verify response
        assert len(sent_response) == 2
        start_message = sent_response[0]
        body_message = sent_response[1]

        assert start_message["type"] == "http.response.start"
        assert start_message["status"] == 200

        import json
        response_body = json.loads(body_message["body"].decode("utf-8"))
        assert response_body["tls"] is True

    async def test_http_request_sets_tls_false(self):
        """HTTP requests should have tls=False."""
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {"tls": request.tls}

        asgi_app = ASGIAdapter(app)

        # Create HTTP scope
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "scheme": "http",  # HTTP connection (no TLS)
            "headers": [[b"accept", b"application/json"]],
            "query_string": b"",
        }

        # Mock receive and send
        sent_response = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent_response.append(message)

        # Execute request
        await asgi_app(scope, receive, send)

        # Verify response
        assert len(sent_response) == 2
        body_message = sent_response[1]

        import json
        response_body = json.loads(body_message["body"].decode("utf-8"))
        assert response_body["tls"] is False

    async def test_client_cert_from_tls_extension(self):
        """Client certificate should be extracted from TLS extension."""
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "has_client_cert": request.client_cert is not None,
                "client_cert_subject": request.client_cert.get("subject") if request.client_cert else None
            }

        asgi_app = ASGIAdapter(app)

        # Create HTTPS scope with TLS extension
        client_cert = {
            "subject": [("CN", "example.com"), ("O", "Example Inc")],
            "issuer": [("CN", "Example CA"), ("O", "Example Inc")],
            "version": 3,
            "serial_number": 12345,
            "notBefore": "2024-01-01T00:00:00Z",
            "notAfter": "2025-01-01T00:00:00Z",
        }

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "scheme": "https",
            "headers": [[b"accept", b"application/json"]],
            "query_string": b"",
            "extensions": {
                "tls": {
                    "client_cert": client_cert
                }
            }
        }

        # Mock receive and send
        sent_response = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent_response.append(message)

        # Execute request
        await asgi_app(scope, receive, send)

        # Verify response
        assert len(sent_response) == 2
        body_message = sent_response[1]

        import json
        response_body = json.loads(body_message["body"].decode("utf-8"))
        assert response_body["tls"] is True
        assert response_body["has_client_cert"] is True
        # JSON serialization converts tuples to lists
        assert response_body["client_cert_subject"] == [["CN", "example.com"], ["O", "Example Inc"]]

    async def test_no_client_cert_when_not_provided(self):
        """Client certificate should be None when not provided."""
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "client_cert": request.client_cert
            }

        asgi_app = ASGIAdapter(app)

        # Create HTTPS scope without TLS extension
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "scheme": "https",
            "headers": [[b"accept", b"application/json"]],
            "query_string": b"",
        }

        # Mock receive and send
        sent_response = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent_response.append(message)

        # Execute request
        await asgi_app(scope, receive, send)

        # Verify response
        assert len(sent_response) == 2
        body_message = sent_response[1]

        import json
        response_body = json.loads(body_message["body"].decode("utf-8"))
        assert response_body["tls"] is True
        assert response_body["client_cert"] is None

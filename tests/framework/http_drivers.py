"""
HTTP server test drivers for multi-driver testing framework.

These drivers allow testing RestMachine applications through actual HTTP servers
(Uvicorn, Hypercorn) to validate real-world behavior including HTTP protocol
compliance, headers handling, and content negotiation.
"""

import asyncio
import json
import threading
import time

import pytest
import requests

from restmachine import RestApplication
from tests.framework.dsl import HttpRequest, HttpResponse
from tests.framework.drivers import DriverInterface


class HttpServerDriver(DriverInterface):
    """
    Base class for HTTP server test drivers.

    These drivers start actual HTTP servers in background threads and make
    real HTTP requests to test the application behavior.
    """

    def __init__(self, app: RestApplication, server_type: str, http_version: str = "http1",
                 host: str = "127.0.0.1", port: int = 0):
        """
        Initialize HTTP server driver.

        Args:
            app: RestMachine application to test
            server_type: Type of server ("uvicorn" or "hypercorn")
            http_version: HTTP version ("http1", "http2", or "http3")
            host: Host to bind to
            port: Port to bind to (0 for auto-assignment)
        """
        self.app = app
        self.server_type = server_type
        self.http_version = http_version
        self.host = host
        self.port = port
        self.actual_port = None
        self.server_thread = None
        self.server_started = threading.Event()
        self.server_error = None

    def start_server(self):
        """Start the HTTP server in a background thread."""
        def run_server():
            try:
                if self.server_type == "uvicorn":
                    self._start_uvicorn()
                elif self.server_type == "hypercorn":
                    self._start_hypercorn()
                else:
                    raise ValueError(f"Unknown server type: {self.server_type}")
            except Exception as e:
                self.server_error = e
                self.server_started.set()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Wait for server to start
        if not self.server_started.wait(timeout=10):
            raise TimeoutError("Server failed to start within 10 seconds")

        if self.server_error:
            raise self.server_error

    def _start_uvicorn(self):
        """Start Uvicorn server."""
        try:
            import uvicorn
            from restmachine.servers import UvicornDriver  # noqa: F401
        except ImportError:
            pytest.skip("Uvicorn not available")

        # Find available port if not specified
        if self.port == 0:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, 0))
                self.actual_port = s.getsockname()[1]
        else:
            self.actual_port = self.port

        # Create server instance
        from restmachine.server import create_asgi_app
        asgi_app = create_asgi_app(self.app)

        config = uvicorn.Config(
            app=asgi_app,
            host=self.host,
            port=self.actual_port,
            log_level="error",  # Quiet during tests
            access_log=False,
        )

        server = uvicorn.Server(config)

        # Signal that server is starting
        self.server_started.set()

        # Run server in current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    def _start_hypercorn(self):
        """Start Hypercorn server."""
        try:
            import hypercorn.asyncio
            from hypercorn import Config
        except ImportError:
            pytest.skip("Hypercorn not available")

        # Find available port if not specified
        if self.port == 0:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, 0))
                self.actual_port = s.getsockname()[1]
        else:
            self.actual_port = self.port

        # Create Hypercorn configuration
        config = Config()
        config.bind = [f"{self.host}:{self.actual_port}"]
        config.loglevel = "ERROR"  # Quiet during tests
        config.access_log_format = None  # Disable access logs

        # Configure HTTP version
        if self.http_version == "http2":
            config.h2 = True

        from restmachine.server import create_asgi_app
        asgi_app = create_asgi_app(self.app)

        # Signal that server is starting
        self.server_started.set()

        # Run server with a new event loop
        # Note: Hypercorn uses signal handlers that don't work in threads,
        # so we wrap it to avoid those issues
        async def run_server():
            try:
                await hypercorn.asyncio.serve(asgi_app, config, shutdown_trigger=lambda: asyncio.Future())
            except RuntimeError as e:
                # Ignore "set_wakeup_fd only works in main thread" errors
                if "set_wakeup_fd" not in str(e):
                    raise

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_server())
        except Exception:
            pass  # Server will be stopped when thread exits

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute HTTP request against the running server."""
        if not self.server_started.is_set():
            raise RuntimeError("Server not started")

        # Build URL
        url = f"http://{self.host}:{self.actual_port}{request.path}"

        # Prepare request parameters
        kwargs = {
            "method": request.method,
            "url": url,
            "headers": request.headers,
            "params": request.query_params,
            "timeout": 30,
        }

        # Add body if present
        if request.body is not None:
            if isinstance(request.body, dict):
                # Check if it should be JSON or form data
                content_type = request.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    kwargs["json"] = request.body
                else:
                    kwargs["data"] = request.body
            else:
                kwargs["data"] = request.body

        # Make HTTP request
        try:
            response = requests.request(**kwargs)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}")

        # Convert response body based on content type
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = response.text
        else:
            body = response.text if response.text else None

        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=body,
            content_type=response.headers.get("content-type")
        )

    def __enter__(self):
        """Context manager entry."""
        self.start_server()
        # Give server a moment to fully start
        time.sleep(0.1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Servers will be cleaned up when the daemon thread ends
        pass


class UvicornHttpDriver(HttpServerDriver):
    """Test driver for Uvicorn HTTP server."""

    def __init__(self, app: RestApplication, http_version: str = "http1", **kwargs):
        super().__init__(app, "uvicorn", http_version, **kwargs)


class HypercornHttpDriver(HttpServerDriver):
    """Test driver for Hypercorn HTTP server."""

    def __init__(self, app: RestApplication, http_version: str = "http1", **kwargs):
        super().__init__(app, "hypercorn", http_version, **kwargs)


class UvicornHttp1Driver(UvicornHttpDriver):
    """Uvicorn HTTP/1.1 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http1", **kwargs)


class UvicornHttp2Driver(UvicornHttpDriver):
    """Uvicorn HTTP/2 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http2", **kwargs)


class HypercornHttp1Driver(HypercornHttpDriver):
    """Hypercorn HTTP/1.1 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http1", **kwargs)


class HypercornHttp2Driver(HypercornHttpDriver):
    """Hypercorn HTTP/2 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http2", **kwargs)
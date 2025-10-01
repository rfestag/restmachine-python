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
        self.server_shutdown = threading.Event()
        self.server_error = None
        self.server_instance = None
        self.event_loop = None
        self.session = None
        self._server_ready = False

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

        # Wait for server to start (reduced timeout, servers start quickly)
        if not self.server_started.wait(timeout=5):
            raise TimeoutError("Server failed to start within 5 seconds")

        if self.server_error:
            raise self.server_error

        self._server_ready = True

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
        self.server_instance = server

        # Signal that server is starting
        self.server_started.set()

        # Run server in current thread with proper cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.event_loop = loop

        try:
            loop.run_until_complete(server.serve())
        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Wait for all tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

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
        shutdown_event = asyncio.Event()
        self.shutdown_event = shutdown_event

        async def run_server():
            try:
                await hypercorn.asyncio.serve(asgi_app, config, shutdown_trigger=shutdown_event.wait)
            except RuntimeError as e:
                # Ignore "set_wakeup_fd only works in main thread" errors
                if "set_wakeup_fd" not in str(e):
                    raise

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.event_loop = loop

        try:
            loop.run_until_complete(run_server())
        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Wait for all tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute HTTP request against the running server."""
        if not self.server_started.is_set():
            raise RuntimeError("Server not started")

        # Create session if not exists (reuse for all requests)
        if self.session is None:
            self.session = requests.Session()

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
            response = self.session.request(**kwargs)
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
        # Minimal wait - server is already running after start_server()
        time.sleep(0.02)  # Reduced from 0.1s
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - properly shut down server and clean up resources."""
        # Close the requests session
        if self.session:
            self.session.close()
            self.session = None

        # Shut down the server
        if self.server_instance:
            # Uvicorn server shutdown
            if hasattr(self.server_instance, 'should_exit'):
                self.server_instance.should_exit = True

        # Hypercorn shutdown
        if hasattr(self, 'shutdown_event') and self.shutdown_event:
            # Signal hypercorn to shut down
            if self.event_loop and not self.event_loop.is_closed():
                try:
                    self.event_loop.call_soon_threadsafe(self.shutdown_event.set)
                except Exception:
                    pass  # Loop might already be closing

        # Give server time to shut down gracefully
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)

        # Force cleanup of event loop if still exists
        if self.event_loop and not self.event_loop.is_closed():
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(self.event_loop)
                for task in pending:
                    task.cancel()
            except Exception:
                pass  # Loop might be in bad state

        return False  # Don't suppress exceptions


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


class HypercornHttp1Driver(HypercornHttpDriver):
    """Hypercorn HTTP/1.1 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http1", **kwargs)


class HypercornHttp2Driver(HypercornHttpDriver):
    """Hypercorn HTTP/2 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http2", **kwargs)
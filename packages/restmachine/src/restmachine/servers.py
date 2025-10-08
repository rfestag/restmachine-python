"""
HTTP server drivers for RestMachine applications.

This module provides drivers for running RestMachine applications with different
HTTP servers, supporting both HTTP/1.1 and HTTP/2 protocols.
"""

import asyncio
import logging
import sys
from abc import ABC, abstractmethod
from typing import Optional, Union

from .application import RestApplication
from .server import create_asgi_app

logger = logging.getLogger(__name__)


class ServerDriver(ABC):
    """Base class for HTTP server drivers."""

    def __init__(self, app: RestApplication, host: str = "127.0.0.1", port: int = 8000, **adapter_kwargs):
        """
        Initialize the server driver.

        Args:
            app: The RestMachine application to serve
            host: Host to bind to
            port: Port to bind to
            **adapter_kwargs: Additional arguments passed to ASGIAdapter (e.g., metrics config)
        """
        self.app = app
        self.host = host
        self.port = port
        self.asgi_app = create_asgi_app(app, **adapter_kwargs)

    @abstractmethod
    def run(self, **kwargs):
        """Run the server."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the server implementation is available."""
        pass


class UvicornDriver(ServerDriver):
    """
    Uvicorn server driver supporting HTTP/1.1 and HTTP/2.

    Uvicorn is a lightning-fast ASGI server implementation, using uvloop
    and httptools for excellent performance.
    """

    def __init__(self, app: RestApplication, host: str = "127.0.0.1", port: int = 8000,
                 http_version: str = "http1"):
        """
        Initialize the Uvicorn driver.

        Args:
            app: The RestMachine application to serve
            host: Host to bind to
            port: Port to bind to
            http_version: HTTP version to use ("http1" or "http2")
        """
        super().__init__(app, host, port)
        if http_version not in ("http1", "http2"):
            raise ValueError("http_version must be 'http1' or 'http2'")
        self.http_version = http_version

    def is_available(self) -> bool:
        """Check if Uvicorn is available."""
        try:
            import uvicorn  # noqa: F401  # type: ignore
            return True
        except ImportError:
            return False

    def run(self,
            log_level: str = "info",
            reload: bool = False,
            workers: int = 1,
            ssl_keyfile: Optional[str] = None,
            ssl_certfile: Optional[str] = None,
            **kwargs):
        """
        Run the Uvicorn server.

        Args:
            log_level: Logging level
            reload: Enable auto-reload for development
            workers: Number of worker processes
            ssl_keyfile: SSL key file for HTTPS
            ssl_certfile: SSL certificate file for HTTPS
            **kwargs: Additional Uvicorn configuration options
        """
        if not self.is_available():
            raise ImportError(
                "Uvicorn is not installed. Install with: pip install 'restmachine[uvicorn]'"
            )

        import uvicorn

        # Configure HTTP version specific settings
        config_kwargs = {
            "host": self.host,
            "port": self.port,
            "log_level": log_level,
            "reload": reload,
            "workers": workers,
            **kwargs
        }

        if self.http_version == "http2":
            # HTTP/2 configuration
            config_kwargs.update({
                "http": "h11",  # Use h11 for HTTP/2 support
                "ws": "none",   # Disable WebSocket for HTTP/2
            })
            if ssl_keyfile and ssl_certfile:
                config_kwargs.update({
                    "ssl_keyfile": ssl_keyfile,
                    "ssl_certfile": ssl_certfile,
                })
            else:
                logger.warning(
                    "HTTP/2 typically requires HTTPS. Consider providing ssl_keyfile and ssl_certfile."
                )
        else:
            # HTTP/1.1 configuration (default)
            if ssl_keyfile and ssl_certfile:
                config_kwargs.update({
                    "ssl_keyfile": ssl_keyfile,
                    "ssl_certfile": ssl_certfile,
                })

        logger.info(f"Starting Uvicorn server on {self.host}:{self.port} ({self.http_version.upper()})")
        uvicorn.run(self.asgi_app, **config_kwargs)


class HypercornDriver(ServerDriver):
    """
    Hypercorn server driver supporting HTTP/1.1, HTTP/2, and HTTP/3.

    Hypercorn is an ASGI server with full HTTP/2 and HTTP/3 support,
    making it ideal for modern web applications.
    """

    def __init__(self, app: RestApplication, host: str = "127.0.0.1", port: int = 8000,
                 http_version: str = "http1"):
        """
        Initialize the Hypercorn driver.

        Args:
            app: The RestMachine application to serve
            host: Host to bind to
            port: Port to bind to
            http_version: HTTP version to use ("http1", "http2", or "http3")
        """
        super().__init__(app, host, port)
        if http_version not in ("http1", "http2", "http3"):
            raise ValueError("http_version must be 'http1', 'http2', or 'http3'")
        self.http_version = http_version

    def is_available(self) -> bool:
        """Check if Hypercorn is available."""
        try:
            import hypercorn  # noqa: F401  # type: ignore
            return True
        except ImportError:
            return False

    def run(self,
            log_level: str = "info",
            workers: int = 1,
            ssl_keyfile: Optional[str] = None,
            ssl_certfile: Optional[str] = None,
            access_log: bool = True,
            **kwargs):
        """
        Run the Hypercorn server.

        Args:
            log_level: Logging level
            workers: Number of worker processes
            ssl_keyfile: SSL key file for HTTPS
            ssl_certfile: SSL certificate file for HTTPS
            access_log: Enable access logging
            **kwargs: Additional Hypercorn configuration options
        """
        if not self.is_available():
            raise ImportError(
                "Hypercorn is not installed. Install with: pip install 'restmachine[hypercorn]'"
            )

        import hypercorn.asyncio  # type: ignore
        from hypercorn import Config  # type: ignore

        # Create Hypercorn configuration
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.workers = workers
        config.loglevel = log_level.upper()
        config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s" if access_log else None  # type: ignore[assignment]

        # Configure HTTP version specific settings
        if self.http_version == "http2":
            config.h2 = True  # type: ignore[attr-defined]
            if ssl_keyfile and ssl_certfile:
                config.keyfile = ssl_keyfile
                config.certfile = ssl_certfile
            else:
                logger.warning(
                    "HTTP/2 typically requires HTTPS. Consider providing ssl_keyfile and ssl_certfile."
                )
        elif self.http_version == "http3":
            config.h3 = True  # type: ignore[attr-defined]
            if ssl_keyfile and ssl_certfile:
                config.keyfile = ssl_keyfile
                config.certfile = ssl_certfile
            else:
                raise ValueError("HTTP/3 requires SSL certificates (ssl_keyfile and ssl_certfile)")
        else:
            # HTTP/1.1 configuration (default)
            if ssl_keyfile and ssl_certfile:
                config.keyfile = ssl_keyfile
                config.certfile = ssl_certfile

        # Apply additional configuration
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        logger.info(f"Starting Hypercorn server on {self.host}:{self.port} ({self.http_version.upper()})")

        # Run the server
        if sys.version_info >= (3, 7):
            asyncio.run(hypercorn.asyncio.serve(self.asgi_app, config))  # type: ignore[arg-type]
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(hypercorn.asyncio.serve(self.asgi_app, config))  # type: ignore[arg-type]


def serve(app: RestApplication,
          server: str = "uvicorn",
          host: str = "127.0.0.1",
          port: int = 8000,
          http_version: str = "http1",
          **kwargs) -> None:
    """
    Serve a RestMachine application with the specified HTTP server.

    Args:
        app: The RestMachine application to serve
        server: Server implementation to use ("uvicorn" or "hypercorn")
        host: Host to bind to
        port: Port to bind to
        http_version: HTTP version to use ("http1", "http2", or "http3" for Hypercorn)
        **kwargs: Additional server-specific configuration options

    Raises:
        ValueError: If an invalid server or http_version is specified
        ImportError: If the specified server is not installed
    """
    driver: Union[UvicornDriver, HypercornDriver]
    if server == "uvicorn":
        driver = UvicornDriver(app, host, port, http_version)
    elif server == "hypercorn":
        driver = HypercornDriver(app, host, port, http_version)
    else:
        raise ValueError(f"Unknown server: {server}. Supported servers: uvicorn, hypercorn")

    if not driver.is_available():
        install_command = f"pip install 'restmachine[{server}]'"
        raise ImportError(f"{server} is not installed. Install with: {install_command}")

    driver.run(**kwargs)


# Convenience functions for specific servers
def serve_uvicorn(app: RestApplication, **kwargs) -> None:
    """Serve with Uvicorn server."""
    serve(app, server="uvicorn", **kwargs)


def serve_hypercorn(app: RestApplication, **kwargs) -> None:
    """Serve with Hypercorn server."""
    serve(app, server="hypercorn", **kwargs)
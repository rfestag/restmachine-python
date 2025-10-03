"""Uvicorn test driver for RestMachine testing framework."""

from restmachine import RestApplication
from restmachine.testing.http_drivers import HttpServerDriver


class UvicornHttpDriver(HttpServerDriver):
    """Test driver for Uvicorn HTTP server."""

    def __init__(self, app: RestApplication, http_version: str = "http1", **kwargs):
        super().__init__(app, "uvicorn", http_version, **kwargs)


class UvicornHttp1Driver(UvicornHttpDriver):
    """Uvicorn HTTP/1.1 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http1", **kwargs)

"""Hypercorn test driver for RestMachine testing framework."""

from restmachine import RestApplication
from restmachine.testing.http_drivers import HttpServerDriver


class HypercornHttpDriver(HttpServerDriver):
    """Test driver for Hypercorn HTTP server."""

    def __init__(self, app: RestApplication, http_version: str = "http1", **kwargs):
        super().__init__(app, "hypercorn", http_version, **kwargs)


class HypercornHttp1Driver(HypercornHttpDriver):
    """Hypercorn HTTP/1.1 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http1", **kwargs)


class HypercornHttp2Driver(HypercornHttpDriver):
    """Hypercorn HTTP/2 test driver."""

    def __init__(self, app: RestApplication, **kwargs):
        super().__init__(app, "http2", **kwargs)

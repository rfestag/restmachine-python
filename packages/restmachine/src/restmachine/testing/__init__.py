"""
Test framework for RESTful API testing using 4-layer architecture.
"""

from .dsl import RestApiDsl, HttpRequest, HttpResponse
from .drivers import RestMachineDriver, HttpDriver, MockDriver
from .multi_driver_base import (
    MultiDriverTestBase,
    multi_driver_test_class,
    skip_driver,
    only_drivers
)

# HTTP server drivers (optional)
try:
    from .http_drivers import (  # noqa: F401
        UvicornHttpDriver,
        HypercornHttpDriver,
        UvicornHttp1Driver,
        UvicornHttp2Driver,
        HypercornHttp1Driver,
        HypercornHttp2Driver,
    )
    _HTTP_DRIVERS_AVAILABLE = True
except ImportError:
    _HTTP_DRIVERS_AVAILABLE = False

__all__ = [
    'RestApiDsl',
    'HttpRequest',
    'HttpResponse',
    'RestMachineDriver',
    'HttpDriver',
    'MockDriver',
    'MultiDriverTestBase',
    'multi_driver_test_class',
    'skip_driver',
    'only_drivers'
]

# Add HTTP drivers if available
if _HTTP_DRIVERS_AVAILABLE:
    __all__.extend([
        'UvicornHttpDriver',
        'HypercornHttpDriver',
        'UvicornHttp1Driver',
        'UvicornHttp2Driver',
        'HypercornHttp1Driver',
        'HypercornHttp2Driver',
    ])

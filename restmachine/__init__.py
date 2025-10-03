"""
A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine,
content negotiation support, and Pydantic-based validation.

This module provides a Flask-like interface with powerful dependency injection
capabilities, a webmachine-inspired state machine, flexible content negotiation,
and comprehensive request/response validation using Pydantic models.
"""

from http import HTTPStatus

from .application import RestApplication
from .content_renderers import (
    ContentRenderer,
    HTMLRenderer,
    JSONRenderer,
    PlainTextRenderer,
)
from .adapters import Adapter, AwsApiGatewayAdapter
from .dependencies import DependencyScope
from .error_models import ErrorResponse
from .exceptions import ValidationError
from .models import HTTPMethod, Request, Response
from .router import Router
from .template_helpers import render

# Server functionality (optional imports)
try:
    from .servers import (  # noqa: F401
        HypercornDriver,
        ServerDriver,
        UvicornDriver,
        serve,
        serve_hypercorn,
        serve_uvicorn,
    )
    _SERVER_AVAILABLE = True
except ImportError:
    _SERVER_AVAILABLE = False

__version__ = "0.1.0"
__author__ = "REST Framework Contributors"
__license__ = "MIT"

__all__ = [
    "RestApplication",
    "Router",
    "Request",
    "Response",
    "HTTPMethod",
    "HTTPStatus",
    "JSONRenderer",
    "HTMLRenderer",
    "PlainTextRenderer",
    "ContentRenderer",
    "DependencyScope",
    "ErrorResponse",
    "ValidationError",
    "Adapter",
    "AwsApiGatewayAdapter",
    "render",
]

# Add server exports if available
if _SERVER_AVAILABLE:
    __all__.extend([
        "ServerDriver",
        "UvicornDriver",
        "HypercornDriver",
        "serve",
        "serve_uvicorn",
        "serve_hypercorn",
    ])

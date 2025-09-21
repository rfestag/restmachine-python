"""
A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine,
content negotiation support, and Pydantic-based validation.

This module provides a Flask-like interface with powerful dependency injection
capabilities, a webmachine-inspired state machine, flexible content negotiation,
and comprehensive request/response validation using Pydantic models.
"""

from .application import RestApplication
from .content_renderers import (
    ContentRenderer,
    HTMLRenderer,
    JSONRenderer,
    PlainTextRenderer,
)
from .exceptions import ValidationError
from .models import HTTPMethod, Request, Response

__version__ = "0.1.0"
__author__ = "REST Framework Contributors"
__license__ = "MIT"

__all__ = [
    "RestApplication",
    "Request",
    "Response",
    "HTTPMethod",
    "JSONRenderer",
    "HTMLRenderer",
    "PlainTextRenderer",
    "ContentRenderer",
    "ValidationError",
]

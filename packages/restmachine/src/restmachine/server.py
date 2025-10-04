"""
HTTP server implementations for RestMachine applications.

This module provides server drivers for running RestMachine applications
with various HTTP servers (Uvicorn, Hypercorn) supporting both HTTP/1.1
and HTTP/2 protocols.

The ASGI adapter has been moved to the adapters module. Import it from there:
    from restmachine.adapters import ASGIAdapter, create_asgi_app
"""

# Re-export ASGI adapter from adapters module for backward compatibility
from .adapters import ASGIAdapter, create_asgi_app  # noqa: F401

__all__ = ["ASGIAdapter", "create_asgi_app"]
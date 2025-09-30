"""
HTTP server implementations for RestMachine applications.

This module provides ASGI adapters and server drivers for running RestMachine
applications with various HTTP servers (Uvicorn, Hypercorn) supporting both
HTTP/1.1 and HTTP/2 protocols.
"""

import json
import urllib.parse
from typing import Any, Dict, Optional

from .application import RestApplication
from .models import HTTPMethod, Request, Response


class ASGIAdapter:
    """
    ASGI adapter that converts between ASGI protocol and RestMachine Request/Response objects.

    This adapter allows RestMachine applications to run on any ASGI-compatible server
    while maintaining the synchronous nature of RestMachine applications internally.
    """

    def __init__(self, app: RestApplication):
        """Initialize the ASGI adapter with a RestMachine application."""
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive, send):
        """ASGI application entry point."""
        if scope["type"] != "http":
            # Only handle HTTP requests
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Not Found",
            })
            return

        # Convert ASGI scope and body to RestMachine Request
        request = await self._asgi_to_restmachine_request(scope, receive)

        # Execute the request through RestMachine
        try:
            response = self.app.execute(request)
        except Exception as e:
            # Handle unexpected errors
            import json
            response = Response(
                status_code=500,
                body=json.dumps({"error": "Internal Server Error", "detail": str(e)}),
                headers={"Content-Type": "application/json"}
            )

        # Convert RestMachine Response to ASGI response
        await self._restmachine_to_asgi_response(response, send)

    async def _asgi_to_restmachine_request(self, scope: Dict[str, Any], receive) -> Request:
        """Convert ASGI scope and body to RestMachine Request."""
        method = HTTPMethod(scope["method"])
        path = scope["path"]
        query_string = scope.get("query_string", b"").decode("utf-8")

        # Parse headers - normalize all to lowercase for case-insensitive matching
        headers = {}
        for header_name, header_value in scope.get("headers", []):
            name = header_name.decode("latin-1").lower()
            value = header_value.decode("latin-1")
            headers[name] = value

        # Parse query parameters
        query_params = {}
        if query_string:
            query_params = dict(urllib.parse.parse_qsl(query_string))

        # Read body
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        # Convert body to string if present, but do NOT parse it
        # RestMachine's application layer will handle parsing based on Content-Type
        body_content: Optional[str] = None
        if body:
            try:
                body_content = body.decode("utf-8")
            except UnicodeDecodeError:
                # If it can't be decoded as UTF-8, use latin-1 as fallback
                body_content = body.decode("latin-1")

        return Request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body_content
        )

    async def _restmachine_to_asgi_response(self, response: Response, send):
        """Convert RestMachine Response to ASGI response."""
        # Prepare body first to calculate Content-Length
        if response.body is None:
            body = b""
        elif isinstance(response.body, (str, int, float, bool)):
            body = str(response.body).encode("utf-8")
        elif isinstance(response.body, (dict, list)):
            body = json.dumps(response.body).encode("utf-8")
        elif isinstance(response.body, bytes):
            body = response.body
        else:
            body = str(response.body).encode("utf-8")

        # Prepare headers
        headers = []
        content_type_set = False
        content_length_set = False

        if response.headers:
            for name, value in response.headers.items():
                name_lower = name.lower()
                if name_lower == "content-type":
                    content_type_set = True
                elif name_lower == "content-length":
                    content_length_set = True
                headers.append([
                    name.encode("latin-1"),
                    str(value).encode("latin-1")
                ])

        # Set Content-Type for JSON if not already set
        if not content_type_set and isinstance(response.body, (dict, list)):
            headers.append([b"content-type", b"application/json"])

        # Always set Content-Length to match actual body length
        if not content_length_set:
            headers.append([b"content-length", str(len(body)).encode("latin-1")])
        else:
            # Update existing Content-Length header to match actual body
            headers = [
                [name, str(len(body)).encode("latin-1") if name.lower() == b"content-length" else value]
                for name, value in headers
            ]

        # Send response
        await send({
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })


def create_asgi_app(app: RestApplication) -> ASGIAdapter:
    """
    Create an ASGI application from a RestMachine application.

    Args:
        app: The RestMachine application to wrap

    Returns:
        An ASGI-compatible application
    """
    return ASGIAdapter(app)
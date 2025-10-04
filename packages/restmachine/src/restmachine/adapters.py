"""
Adapters for running RestMachine applications on different platforms.

This module provides adapters for:
- ASGI servers (Uvicorn, Hypercorn, etc.)
- AWS Lambda (API Gateway, ALB, Lambda Function URLs)
- Other event-driven platforms (Azure Functions, Google Cloud Functions, etc.)

Adapters convert between external platform formats and RestMachine's internal
Request/Response models.
"""

import json
import urllib.parse
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from .models import HTTPMethod, MultiValueHeaders, Request, Response

if TYPE_CHECKING:
    from .application import RestApplication


class Adapter(ABC):
    """
    Abstract base class for synchronous event adapters.

    Use this base class for platforms that use synchronous event handling,
    such as AWS Lambda, Azure Functions, Google Cloud Functions, etc.

    For ASGI servers, use ASGIAdapter instead.
    """

    @abstractmethod
    def handle_event(self, event: Any, context: Optional[Any] = None) -> Any:
        """
        Handle an external event and return the appropriate response format.

        Args:
            event: The external event (e.g., AWS Lambda event)
            context: Optional context (e.g., AWS Lambda context)

        Returns:
            Response in the format expected by the external system
        """
        pass

    @abstractmethod
    def convert_to_request(self, event: Any, context: Optional[Any] = None) -> Request:
        """
        Convert an external event to a Request object.

        Args:
            event: The external event
            context: Optional context

        Returns:
            Request object that can be processed by the app
        """
        pass

    @abstractmethod
    def convert_from_response(self, response: Response, event: Any, context: Optional[Any] = None) -> Any:
        """
        Convert a Response object to the format expected by the external system.

        Args:
            response: Response from the app
            event: Original external event
            context: Optional context

        Returns:
            Response in the format expected by the external system
        """
        pass


class ASGIAdapter:
    """
    ASGI 3.0 adapter for running RestMachine applications on ASGI servers.

    This adapter enables RestMachine applications to run on any ASGI-compatible server
    (Uvicorn, Hypercorn, Daphne, etc.) while maintaining the synchronous programming
    model internally.

    The adapter handles:
    - Converting ASGI scope/receive/send to RestMachine Request
    - Executing the synchronous RestMachine application
    - Converting RestMachine Response to ASGI response format
    - Proper header normalization and encoding
    - Content-Type and Content-Length handling

    Example:
        ```python
        from restmachine import RestApplication
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/")
        def home():
            return {"message": "Hello World"}

        # Create ASGI application
        asgi_app = ASGIAdapter(app)

        # Use with any ASGI server:
        # uvicorn module:asgi_app
        # hypercorn module:asgi_app
        ```
    """

    def __init__(self, app: "RestApplication"):
        """
        Initialize the ASGI adapter.

        Args:
            app: The RestMachine application to wrap
        """
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive, send):
        """
        ASGI 3.0 application entry point.

        Args:
            scope: ASGI connection scope dictionary
            receive: Async callable to receive ASGI messages
            send: Async callable to send ASGI messages
        """
        if scope["type"] != "http":
            # Only handle HTTP requests
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"Not Found - Only HTTP protocol is supported",
            })
            return

        # Convert ASGI scope and body to RestMachine Request
        request = await self._asgi_to_request(scope, receive)

        # Execute the request through RestMachine
        try:
            response = self.app.execute(request)
        except Exception as e:
            # Handle unexpected errors gracefully
            response = Response(
                status_code=500,
                body=json.dumps({"error": "Internal Server Error", "detail": str(e)}),
                headers={"Content-Type": "application/json"}
            )

        # Convert RestMachine Response to ASGI response
        await self._response_to_asgi(response, send)

    async def _asgi_to_request(self, scope: Dict[str, Any], receive) -> Request:
        """
        Convert ASGI scope and receive callable to RestMachine Request.

        Follows ASGI patterns for header and query parameter handling.

        Args:
            scope: ASGI connection scope
            receive: ASGI receive callable

        Returns:
            RestMachine Request object
        """
        # Extract HTTP method and path
        method = HTTPMethod(scope["method"])
        path = scope["path"]

        # Parse query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = {}
        if query_string:
            # Parse into dict (takes first value for duplicate keys)
            query_params = dict(urllib.parse.parse_qsl(query_string))

        # Parse headers - ASGI uses lowercase names and bytes
        # Use MultiValueHeaders to support duplicate header names
        headers = MultiValueHeaders()
        for header_name, header_value in scope.get("headers", []):
            name = header_name.decode("latin-1").lower()
            value = header_value.decode("latin-1")
            headers.add(name, value)

        # Read request body
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        # Convert body to string if present
        # RestMachine's application layer will handle parsing based on Content-Type
        body_content: Optional[str] = None
        if body:
            try:
                body_content = body.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback to latin-1 if UTF-8 fails
                body_content = body.decode("latin-1")

        return Request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body_content
        )

    async def _response_to_asgi(self, response: Response, send):
        """
        Convert RestMachine Response to ASGI response format.

        Handles proper encoding, Content-Type, and Content-Length headers.

        Args:
            response: RestMachine Response object
            send: ASGI send callable
        """
        # Convert body to bytes first to calculate Content-Length
        if response.body is None:
            body = b""
        elif isinstance(response.body, bytes):
            body = response.body
        elif isinstance(response.body, (dict, list)):
            body = json.dumps(response.body).encode("utf-8")
        elif isinstance(response.body, (str, int, float, bool)):
            body = str(response.body).encode("utf-8")
        else:
            body = str(response.body).encode("utf-8")

        # Prepare headers - ASGI requires bytes
        # Use items_all() to get all header values including duplicates
        headers = []
        content_type_set = False
        content_length_set = False

        if response.headers and isinstance(response.headers, MultiValueHeaders):
            for name, value in response.headers.items_all():
                name_lower = name.lower()
                if name_lower == "content-type":
                    content_type_set = True
                elif name_lower == "content-length":
                    content_length_set = True

                headers.append([
                    name.encode("latin-1"),
                    str(value).encode("latin-1")
                ])

        # Set Content-Type for JSON responses if not already set
        if not content_type_set and isinstance(response.body, (dict, list)):
            headers.append([b"content-type", b"application/json"])

        # Always ensure Content-Length matches actual body length
        if not content_length_set:
            headers.append([b"content-length", str(len(body)).encode("latin-1")])
        else:
            # Update existing Content-Length to match actual body
            headers = [
                [name, str(len(body)).encode("latin-1") if name.lower() == b"content-length" else value]
                for name, value in headers
            ]

        # Send response start
        await send({
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        })

        # Send response body
        await send({
            "type": "http.response.body",
            "body": body,
        })


def create_asgi_app(app: "RestApplication") -> ASGIAdapter:
    """
    Create an ASGI application from a RestMachine application.

    This is a convenience function for creating ASGI adapters.

    Args:
        app: The RestMachine application to wrap

    Returns:
        An ASGI-compatible application

    Example:
        ```python
        from restmachine import RestApplication
        from restmachine.adapters import create_asgi_app

        app = RestApplication()

        @app.get("/")
        def home():
            return {"message": "Hello World"}

        # Create ASGI app
        asgi_app = create_asgi_app(app)

        # Run with uvicorn
        # uvicorn module:asgi_app --reload
        ```
    """
    return ASGIAdapter(app)
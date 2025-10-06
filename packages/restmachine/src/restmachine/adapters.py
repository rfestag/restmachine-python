"""
Adapters for running RestMachine applications on different platforms.

This module provides adapters for:
- ASGI servers (Uvicorn, Hypercorn, etc.)
- AWS Lambda (API Gateway, ALB, Lambda Function URLs)
- Other event-driven platforms (Azure Functions, Google Cloud Functions, etc.)

Adapters convert between external platform formats and RestMachine's internal
Request/Response models.
"""

import io
import json
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, Optional, cast

from .models import HTTPMethod, MultiValueHeaders, Request, Response
from .streaming import BytesStreamBuffer

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
    - True streaming of request bodies (application receives data as it arrives)
    - Converting ASGI scope/receive/send to RestMachine Request
    - Executing the synchronous RestMachine application in a thread pool
    - Converting RestMachine Response to ASGI response format (streaming if needed)
    - Proper header normalization and encoding
    - Content-Type and Content-Length handling

    Streaming behavior:
    - Request bodies: The adapter receives the first chunk, passes the stream to the
      application immediately, and continues receiving chunks in the background. The
      application can start processing before all data has arrived.
    - Response bodies: File-like objects are streamed in 8KB chunks with proper
      ASGI more_body signaling.

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
        if scope["type"] == "lifespan":
            # Handle ASGI lifespan protocol for startup/shutdown
            await self._handle_lifespan(receive, send)
            return

        if scope["type"] != "http":
            # Only handle HTTP and lifespan
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

        # Start the request and get the first body chunk
        request, more_body = await self._start_request(scope, receive)

        # Execute the request through RestMachine
        # If there's more body data to stream, run execute in thread pool
        # and continue receiving body chunks in background
        try:
            if more_body and request.body is not None:
                # Start background task to continue receiving body chunks
                import asyncio
                receive_task = asyncio.create_task(
                    self._continue_receiving_body(request.body, receive)
                )

                # Run synchronous execute in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.app.execute, request)

                # Ensure body receiving is complete
                await receive_task
            else:
                # No streaming needed, run execute in thread pool
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.app.execute, request)

        except Exception as e:
            # Handle unexpected errors gracefully
            response = Response(
                status_code=500,
                body=json.dumps({"error": "Internal Server Error", "detail": str(e)}),
                headers={"Content-Type": "application/json"}
            )

        # Convert RestMachine Response to ASGI response
        await self._response_to_asgi(response, send)

    async def _handle_lifespan(self, receive, send):
        """
        Handle ASGI lifespan protocol for startup and shutdown.

        The lifespan protocol allows the application to run code on startup
        and shutdown, such as opening/closing database connections.

        Args:
            receive: ASGI receive callable
            send: ASGI send callable
        """
        while True:
            message = await receive()

            if message["type"] == "lifespan.startup":
                try:
                    # Run all registered startup handlers
                    await self.app.startup()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    # Startup failed - report error to server
                    await send({
                        "type": "lifespan.startup.failed",
                        "message": str(e)
                    })
                    # Re-raise so server knows startup failed
                    raise

            elif message["type"] == "lifespan.shutdown":
                try:
                    # Run all registered shutdown handlers
                    await self.app.shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                except Exception as e:
                    # Log error but don't fail shutdown
                    import logging
                    logging.error(f"Error during shutdown: {e}", exc_info=True)
                    await send({
                        "type": "lifespan.shutdown.failed",
                        "message": str(e)
                    })
                # Exit the lifespan loop after shutdown
                return

    async def _start_request(self, scope: Dict[str, Any], receive):
        """
        Start a RestMachine Request by parsing headers and receiving the first body chunk.

        This method receives only the first chunk of body data and returns immediately,
        allowing the application to start processing while more data is still being received.

        Args:
            scope: ASGI connection scope
            receive: ASGI receive callable

        Returns:
            Tuple of (Request object, bool indicating if more body data is coming)
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

        # Create a streaming body buffer and receive ONLY the first chunk
        # This allows the application to start processing immediately
        body_stream_temp = BytesStreamBuffer()
        message = await receive()
        chunk = message.get("body", b"")
        if chunk:
            body_stream_temp.write(chunk)
        more_body = message.get("more_body", False)

        # If no more body, close the stream now
        if not more_body:
            body_stream_temp.close_writing()

        # If there's no content, set body to None instead of empty stream
        body_stream: Optional[BytesStreamBuffer] = None if body_stream_temp.tell() == 0 else body_stream_temp

        # Extract TLS information (ASGI TLS extension)
        # Check if connection is using TLS (https)
        tls = scope.get("scheme", "http") == "https"

        # Extract client certificate if available (mutual TLS)
        client_cert = None
        extensions = scope.get("extensions", {})
        if "tls" in extensions:
            tls_info = extensions["tls"]
            # ASGI TLS extension format
            client_cert = tls_info.get("client_cert")

        request = Request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body_stream,
            tls=tls,
            client_cert=client_cert
        )

        return request, more_body

    async def _continue_receiving_body(self, body_stream: BytesStreamBuffer, receive):
        """
        Continue receiving body chunks and writing to the stream.

        This runs in the background while the application processes the request,
        allowing true streaming of request bodies.

        Args:
            body_stream: The stream to write chunks to
            receive: ASGI receive callable
        """
        while True:
            message = await receive()
            chunk = message.get("body", b"")
            if chunk:
                body_stream.write(chunk)
            more_body = message.get("more_body", False)
            if not more_body:
                body_stream.close_writing()
                break

    def _convert_body_to_bytes(self, body: Any) -> bytes:
        """
        Convert response body to bytes for ASGI.

        Args:
            body: Response body (None, bytes, str, dict, list, etc.)

        Returns:
            Body as bytes
        """
        if body is None:
            return b""
        elif isinstance(body, bytes):
            return body
        elif isinstance(body, (dict, list)):
            return json.dumps(body).encode("utf-8")
        elif isinstance(body, (str, int, float, bool)):
            return str(body).encode("utf-8")
        else:
            return str(body).encode("utf-8")

    def _prepare_asgi_headers(self, response: Response, is_stream: bool, body_bytes: Optional[bytes] = None):
        """
        Prepare headers for ASGI response.

        Args:
            response: RestMachine Response object
            is_stream: Whether the body is a stream
            body_bytes: Bytes body (for Content-Length calculation)

        Returns:
            Tuple of (headers list, content_type_set, content_length_set)
        """
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

        # Set Content-Length for non-streaming bodies
        if not is_stream and not content_length_set and body_bytes is not None:
            headers.append([b"content-length", str(len(body_bytes)).encode("latin-1")])

        return headers

    async def _send_streaming_body(self, body_stream: BinaryIO, send):
        """
        Send a streaming body to ASGI in chunks.

        Args:
            body_stream: File-like object to stream
            send: ASGI send callable
        """
        chunk_size = 8192  # 8KB chunks
        while True:
            chunk = body_stream.read(chunk_size)
            if not chunk:
                break
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            })
        # Send final empty chunk to signal end
        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })

    async def _response_to_asgi(self, response: Response, send):
        """
        Convert RestMachine Response to ASGI response format.

        Handles proper encoding, Content-Type, and Content-Length headers.
        Supports streaming response bodies and efficient file serving via Path objects.

        For Path objects, uses the ASGI http.response.pathsend extension for efficient
        file serving when supported by the server.

        Args:
            response: RestMachine Response object
            send: ASGI send callable
        """
        # Check if body is a Path (file to serve)
        is_path = isinstance(response.body, Path)

        # Check if body is a stream
        is_stream = isinstance(response.body, io.IOBase)

        # For non-streaming, non-Path bodies, convert to bytes
        body = None
        if not is_stream and not is_path:
            body = self._convert_body_to_bytes(response.body)

        # Prepare headers
        headers = self._prepare_asgi_headers(response, is_stream or is_path, body)

        # Build response start message
        response_start = {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        }

        # For Path objects, add the pathsend extension
        if is_path:
            path_obj = cast(Path, response.body)
            response_start["extensions"] = {
                "http.response.pathsend": {
                    "path": str(path_obj.absolute())
                }
            }

        # Send response start
        await send(response_start)

        # Send response body
        if is_path:
            # For Path, send empty body - the server will serve the file using the extension
            # If the server doesn't support the extension, we fall back to reading the file
            path_obj = cast(Path, response.body)
            if path_obj.exists() and path_obj.is_file():
                # Open and stream the file as fallback
                # Most ASGI servers that support pathsend will ignore the body we send
                with path_obj.open('rb') as f:
                    await self._send_streaming_body(f, send)
            else:
                # File doesn't exist, send empty body
                await send({
                    "type": "http.response.body",
                    "body": b"",
                })
        elif is_stream:
            await self._send_streaming_body(cast(BinaryIO, response.body), send)
        else:
            # Send entire body at once for non-streaming responses
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
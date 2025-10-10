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
import logging
import os
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, BinaryIO, Callable, Dict, Optional, Union, cast

from .models import HTTPMethod, MultiValueHeaders, Request, Response
from .streaming import BytesStreamBuffer
from .metrics import MetricsCollector, MetricsPublisher, METRICS

if TYPE_CHECKING:
    from .application import RestApplication

logger = logging.getLogger(__name__)


# Sentinel for default metrics publisher
class _DefaultPublisher:
    pass

_DEFAULT_PUBLISHER = _DefaultPublisher()


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
    - **Automatic AWS detection** - Enables CloudWatch EMF metrics when running in AWS

    Streaming behavior:
    - Request bodies: The adapter receives the first chunk, passes the stream to the
      application immediately, and continues receiving chunks in the background. The
      application can start processing before all data has arrived.
    - Response bodies: File-like objects are streamed in 8KB chunks with proper
      ASGI more_body signaling.

    Metrics behavior:
    - **AWS auto-detection**: When AWS environment is detected (via AWS_REGION or
      AWS_EXECUTION_ENV), CloudWatch EMF metrics are automatically enabled
    - **Manual configuration**: Pass custom metrics_publisher for other platforms
    - **Disable**: Set enable_metrics=False to disable metrics

    Example:
        ```python
        from restmachine import RestApplication
        from restmachine.adapters import ASGIAdapter

        app = RestApplication()

        @app.get("/")
        def home(metrics):
            metrics.add_metric("requests", 1)
            return {"message": "Hello World"}

        # Create ASGI application - metrics auto-enabled if in AWS
        asgi_app = ASGIAdapter(app)

        # Use with any ASGI server:
        # uvicorn module:asgi_app
        # hypercorn module:asgi_app
        ```
    """

    def __init__(self,
                 app: "RestApplication",
                 metrics_publisher: Union[MetricsPublisher, None, _DefaultPublisher] = _DEFAULT_PUBLISHER,
                 enable_metrics: Optional[bool] = None,
                 namespace: Optional[str] = None,
                 service_name: Optional[str] = None,
                 metrics_resolution: int = 60):
        """
        Initialize the ASGI adapter with optional metrics support.

        Automatically detects AWS environment and enables CloudWatch EMF metrics
        when running on AWS (ECS, EC2, App Runner, etc.).

        Args:
            app: The RestMachine application to wrap
            metrics_publisher: Metrics publisher. Defaults to auto-detection:
                              - CloudWatch EMF if AWS environment detected
                              - None if not in AWS
                              Pass explicit publisher to override, or None to disable.
            enable_metrics: Explicitly enable/disable metrics (overrides auto-detection)
            namespace: CloudWatch namespace (used if AWS detected, default: "RestMachine")
            service_name: Service name dimension (default: from env or "asgi-app")
            metrics_resolution: Metric resolution in seconds, 1 or 60 (default: 60)

        Examples:
            # Auto-detect AWS and enable EMF
            adapter = ASGIAdapter(app)

            # Custom namespace for AWS
            adapter = ASGIAdapter(app, namespace="MyApp/API")

            # Custom publisher (Prometheus, etc.)
            adapter = ASGIAdapter(app, metrics_publisher=PrometheusPublisher())

            # Disable metrics
            adapter = ASGIAdapter(app, enable_metrics=False)
        """
        self.app = app

        # Determine if metrics should be enabled
        metrics_enabled = self._should_enable_metrics(enable_metrics)

        # Auto-configure publisher if not provided
        publisher: Optional[MetricsPublisher]
        if isinstance(metrics_publisher, _DefaultPublisher):
            if metrics_enabled:
                publisher = self._create_default_publisher(
                    namespace=namespace,
                    service_name=service_name,
                    resolution=metrics_resolution
                )
                if publisher:
                    self._configure_default_logging()
            else:
                publisher = None
        else:
            publisher = metrics_publisher

        self.metrics_publisher = publisher

    def _is_aws_environment(self) -> bool:
        """Detect if running in an AWS environment.

        Checks for AWS-specific environment variables that indicate
        the application is running on AWS infrastructure.

        Returns:
            True if AWS environment detected, False otherwise
        """
        # Check for AWS_REGION (set in Lambda, ECS, EC2, App Runner, etc.)
        if os.environ.get('AWS_REGION'):
            return True

        # Check for AWS_EXECUTION_ENV (set in Lambda)
        if os.environ.get('AWS_EXECUTION_ENV'):
            return True

        # Check for ECS metadata endpoint
        if os.environ.get('ECS_CONTAINER_METADATA_URI') or os.environ.get('ECS_CONTAINER_METADATA_URI_V4'):
            return True

        # Check for AWS_DEFAULT_REGION (common in AWS deployments)
        if os.environ.get('AWS_DEFAULT_REGION'):
            return True

        return False

    def _should_enable_metrics(self, explicit_enable: Optional[bool]) -> bool:
        """Determine if metrics should be enabled.

        Priority:
        1. Explicit enable_metrics parameter
        2. RESTMACHINE_METRICS_ENABLED environment variable
        3. Auto-detect AWS environment
        4. Default to False (no metrics)

        Args:
            explicit_enable: User's explicit enable/disable choice

        Returns:
            True if metrics should be enabled
        """
        if explicit_enable is not None:
            return explicit_enable

        # Check environment variable
        env_value = os.environ.get('RESTMACHINE_METRICS_ENABLED', '').lower()
        if env_value in ('true', '1', 'yes', 'on'):
            return True
        elif env_value in ('false', '0', 'no', 'off'):
            return False

        # Auto-detect AWS environment
        is_aws = self._is_aws_environment()
        if is_aws:
            logger.info("AWS environment detected - enabling CloudWatch EMF metrics")
        return is_aws

    def _create_default_publisher(self,
                                  namespace: Optional[str] = None,
                                  service_name: Optional[str] = None,
                                  resolution: int = 60) -> Optional[MetricsPublisher]:
        """Create default metrics publisher based on environment.

        For AWS environments, creates CloudWatch EMF publisher.
        For non-AWS, returns None (no default publisher).

        Args:
            namespace: CloudWatch namespace
            service_name: Service name for dimension
            resolution: Metric resolution in seconds

        Returns:
            MetricsPublisher if appropriate for environment, None otherwise
        """
        if not self._is_aws_environment():
            return None

        # In AWS - create CloudWatch EMF publisher
        try:
            from restmachine_aws.metrics import CloudWatchEMFPublisher

            # Namespace: arg > env > default
            final_namespace = namespace or \
                             os.environ.get('RESTMACHINE_METRICS_NAMESPACE', 'RestMachine')

            # Service name: arg > env > default
            final_service = service_name or \
                           os.environ.get('RESTMACHINE_SERVICE_NAME', 'asgi-app')

            # Resolution: arg > env > default
            if resolution not in (1, 60):
                resolution_str = os.environ.get('RESTMACHINE_METRICS_RESOLUTION', '60')
                try:
                    resolution = int(resolution_str)
                    if resolution not in (1, 60):
                        resolution = 60
                except ValueError:
                    resolution = 60

            logger.info(f"Configuring CloudWatch EMF metrics: namespace={final_namespace}, service={final_service}")

            publisher: MetricsPublisher = CloudWatchEMFPublisher(
                namespace=final_namespace,
                service_name=final_service,
                default_resolution=resolution
            )
            return publisher
        except ImportError:
            logger.warning(
                "AWS environment detected but restmachine-aws not installed. "
                "Install with: pip install restmachine-aws"
            )
            return None

    def _configure_default_logging(self):
        """Configure logging for EMF output."""
        emf_logger = logging.getLogger("restmachine.metrics.emf")

        if not emf_logger.handlers:
            emf_logger.setLevel(METRICS)
            handler = logging.StreamHandler()
            handler.setLevel(METRICS)
            emf_logger.addHandler(handler)
            emf_logger.propagate = False

    async def __call__(self, scope: Dict[str, Any], receive: Callable[[], Awaitable[Dict[str, Any]]], send: Callable[[Dict[str, Any]], Awaitable[None]]):
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

        # Create metrics collector (always, even if publishing disabled)
        metrics = MetricsCollector()
        metrics.start_timer("adapter.total_time")

        try:
            # Start the request and get the first body chunk
            metrics.start_timer("adapter.scope_to_request")
            request, more_body = await self._start_request(scope, receive)
            metrics.stop_timer("adapter.scope_to_request")

            # Inject metrics into dependency cache
            self.app._dependency_cache.set("metrics", metrics)

            # Execute the request through RestMachine
            # If there's more body data to stream, run execute in thread pool
            # and continue receiving body chunks in background
            metrics.start_timer("application.execute")
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
            finally:
                metrics.stop_timer("application.execute")

            # Add response metrics
            metrics.start_timer("adapter.response_conversion")
            metrics.add_metadata("status_code", response.status_code)
            metrics.add_dimension("method", request.method.value)
            metrics.add_dimension("path", request.path)

            # Convert RestMachine Response to ASGI response
            await self._response_to_asgi(response, send)
            metrics.stop_timer("adapter.response_conversion")
            metrics.stop_timer("adapter.total_time")

            # Publish metrics (if enabled)
            await self._safe_publish(metrics, request, response)

        except Exception as e:
            # Record error metrics
            metrics.add_metric("errors", 1, unit="Count")
            metrics.add_metadata("error", str(e))
            metrics.add_metadata("error_type", type(e).__name__)

            # Publish error metrics
            await self._safe_publish(metrics)

            # Handle unexpected errors gracefully
            response = Response(
                status_code=500,
                body=json.dumps({"error": "Internal Server Error", "detail": str(e)}),
                headers={"Content-Type": "application/json"}
            )
            await self._response_to_asgi(response, send)

    async def _safe_publish(self, metrics: MetricsCollector, request: Any = None, response: Any = None):
        """Safely publish metrics without breaking the request.

        Args:
            metrics: MetricsCollector with collected metrics
            request: Optional request object
            response: Optional response object
        """
        if not self.metrics_publisher or not self.metrics_publisher.is_enabled():
            return

        try:
            # Run publish in thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.metrics_publisher.publish,
                metrics,
                request,
                response,
                None
            )
        except Exception as e:
            logger.warning(f"Failed to publish metrics: {e}", exc_info=True)

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

        For Path objects, uses the ASGI http.response.pathsend or http.response.zerocopysend
        extensions for efficient file serving when supported by the server.

        Range Request Support:
        - For Path ranges: Uses http.response.zerocopysend with offset/count (zero-copy)
        - For stream ranges: Seeks and streams the requested range
        - For byte ranges: Slices and sends the requested bytes

        Args:
            response: RestMachine Response object
            send: ASGI send callable
        """
        # Check for range response - handle specially
        if response.is_range_response():
            await self._send_range_response(response, send)
            return

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

    async def _send_range_response(self, response: Response, send):
        """
        Send a 206 Partial Content response.

        Uses zero-copy extensions when possible for efficient file serving.

        RFC 9110 Section 14: Range requests allow partial content transfer.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14

        Args:
            response: Response with range_start and range_end set
            send: ASGI send callable
        """
        from .models import is_seekable_stream
        from typing import cast, BinaryIO

        # Validate range fields are set (guaranteed by is_range_response())
        if response.range_start is None or response.range_end is None:
            raise ValueError("Range response missing range_start or range_end fields")

        # Prepare headers (already includes Content-Range, Content-Length)
        headers = self._prepare_asgi_headers(response, False, None)

        # Check if body is a Path (file)
        is_path = isinstance(response.body, Path)

        # Try zero-copy send for file ranges
        if is_path:
            path_obj = cast(Path, response.body)

            # Build response start with zerocopysend extension
            response_start = {
                "type": "http.response.start",
                "status": 206,
                "headers": headers,
            }

            # Send response start
            await send(response_start)

            # Try zero-copy send (supported by uvicorn, hypercorn)
            try:
                await send({
                    "type": "http.response.zerocopysend",
                    "file": str(path_obj.absolute()),
                    "offset": response.range_start,
                    "count": response.range_end - response.range_start + 1
                })
                return
            except (KeyError, TypeError):
                # Server doesn't support zerocopysend - fall back to reading
                with path_obj.open('rb') as f:
                    f.seek(response.range_start)
                    remaining = response.range_end - response.range_start + 1
                    await self._send_chunked_bytes(f, send, remaining)
                return

        # Handle stream ranges
        if is_seekable_stream(response.body):
            # Send response start
            await send({
                "type": "http.response.start",
                "status": 206,
                "headers": headers,
            })

            # Seek and stream the range
            stream = cast(BinaryIO, response.body)
            stream.seek(response.range_start)
            remaining = response.range_end - response.range_start + 1
            await self._send_chunked_bytes(stream, send, remaining)

            # Close stream if it's a file
            if hasattr(stream, 'close'):
                stream.close()
            return

        # Handle bytes ranges
        if isinstance(response.body, bytes):
            # Send response start
            await send({
                "type": "http.response.start",
                "status": 206,
                "headers": headers,
            })

            # Slice and send
            range_bytes = response.body[response.range_start:response.range_end + 1]
            await send({
                "type": "http.response.body",
                "body": range_bytes,
            })
            return

        # Fallback - shouldn't reach here
        await send({
            "type": "http.response.start",
            "status": 206,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": b"",
        })

    async def _send_chunked_bytes(self, stream: BinaryIO, send, total_bytes: int, chunk_size: int = 65536):
        """
        Send a specific number of bytes from a stream in chunks.

        Args:
            stream: Stream to read from (already seeked to correct position)
            send: ASGI send callable
            total_bytes: Total number of bytes to send
            chunk_size: Size of each chunk (default 64KB)
        """
        remaining = total_bytes

        while remaining > 0:
            to_read = min(chunk_size, remaining)
            chunk = stream.read(to_read)

            if not chunk:
                break  # Stream ended unexpectedly

            # Ensure chunk is bytes
            if isinstance(chunk, str):
                chunk = chunk.encode('utf-8')

            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": remaining > len(chunk)
            })

            remaining -= len(chunk)


def create_asgi_app(app: "RestApplication", **adapter_kwargs: Any) -> ASGIAdapter:
    """
    Create an ASGI application from a RestMachine application.

    This is a convenience function for creating ASGI adapters with optional
    metrics configuration.

    Args:
        app: The RestMachine application to wrap
        **adapter_kwargs: Additional arguments passed to ASGIAdapter:
            - metrics_publisher: Custom metrics publisher
            - enable_metrics: Explicitly enable/disable metrics
            - namespace: CloudWatch namespace (if AWS detected)
            - service_name: Service name dimension
            - metrics_resolution: Metric resolution (1 or 60 seconds)

    Returns:
        An ASGI-compatible application

    Examples:
        ```python
        from restmachine import RestApplication
        from restmachine.adapters import create_asgi_app

        app = RestApplication()

        @app.get("/")
        def home(metrics):
            metrics.add_metric("requests", 1)
            return {"message": "Hello World"}

        # Auto-detect AWS and enable EMF (default)
        asgi_app = create_asgi_app(app)

        # Custom namespace for AWS
        asgi_app = create_asgi_app(app, namespace="MyApp/API")

        # Disable metrics
        asgi_app = create_asgi_app(app, enable_metrics=False)

        # Run with uvicorn
        # uvicorn module:asgi_app --reload
        ```
    """
    return ASGIAdapter(app, **adapter_kwargs)
"""
Driver implementations for different execution environments.

This is the third layer in Dave Farley's 4-layer testing architecture.
Drivers know how to translate DSL requests into actual system calls.
"""

import io
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

from restmachine import RestApplication, HTTPMethod, Request as RestMachineRequest, BytesStreamBuffer
from .dsl import HttpRequest, HttpResponse


class DriverInterface(ABC):
    """Abstract interface for all drivers."""

    @abstractmethod
    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute an HTTP request and return the response."""
        pass


class RestMachineDriver(DriverInterface):
    """
    Driver that executes requests directly against the RestMachine library.

    This is the most direct way to test the library without any intermediate layers.
    """

    def __init__(self, app: RestApplication):
        """Initialize with a RestApplication instance."""
        self.app = app

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute request directly through RestApplication."""
        # Convert DSL request to RestMachine request
        rm_request = self._convert_to_restmachine_request(request)

        # Execute through the library
        rm_response = self.app.execute(rm_request)

        # Convert RestMachine response back to DSL response
        return self._convert_from_restmachine_response(rm_response)

    def _convert_to_restmachine_request(self, request: HttpRequest) -> RestMachineRequest:
        """Convert DSL HttpRequest to RestMachine Request."""
        # Convert method string to HTTPMethod enum
        method = HTTPMethod(request.method.upper())

        # Prepare body as a stream
        body_stream = None
        if request.body is not None:
            # Convert body to bytes
            if isinstance(request.body, dict):
                # Check content type to determine encoding
                content_type = request.headers.get("Content-Type", "")
                if "application/x-www-form-urlencoded" in content_type:
                    # URL-encode form data
                    from urllib.parse import urlencode
                    body_bytes = urlencode(request.body).encode('utf-8')
                else:
                    # Default to JSON for dict bodies
                    body_bytes = json.dumps(request.body).encode('utf-8')
            elif isinstance(request.body, bytes):
                body_bytes = request.body
            else:
                body_bytes = str(request.body).encode('utf-8')

            # Create stream from bytes
            body_stream = BytesStreamBuffer()
            body_stream.write(body_bytes)
            body_stream.close_writing()

        # Create RestMachine request
        return RestMachineRequest(
            method=method,
            path=request.path,
            headers=request.headers.copy(),
            query_params=request.query_params.copy() if request.query_params else None,
            body=body_stream
        )

    def _convert_from_restmachine_response(self, response) -> HttpResponse:
        """Convert RestMachine Response to DSL HttpResponse."""
        # Handle streaming, Path, and non-streaming bodies
        body = response.body
        content_type = response.content_type

        # Check if this is a range response
        is_range = response.is_range_response() if hasattr(response, 'is_range_response') else False

        if is_range:
            # Handle range responses - extract only the requested range
            range_start = response.range_start
            range_end = response.range_end

            if isinstance(body, Path):
                # Read only the requested range from file
                if body.exists() and body.is_file():
                    with body.open('rb') as f:
                        f.seek(range_start)
                        body_bytes = f.read(range_end - range_start + 1)
                else:
                    body_bytes = b""
                body = body_bytes

            elif isinstance(body, io.IOBase):
                # Read only the requested range from stream
                if hasattr(body, 'seek'):
                    body.seek(range_start)
                body_bytes = body.read(range_end - range_start + 1)
                body = body_bytes

            elif isinstance(body, bytes):
                # Slice the requested range
                body = body[range_start:range_end + 1]

            # Range responses are always bytes, don't try to decode
            # (tests expect bytes for range responses)

        else:
            # Non-range response - original behavior
            # If body is a Path, read the file
            if isinstance(body, Path):
                if body.exists() and body.is_file():
                    with body.open('rb') as f:
                        body_bytes = f.read()
                    # Try to decode as UTF-8
                    try:
                        body = body_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        # Keep as bytes if not valid UTF-8
                        body = body_bytes
                else:
                    body = None

            # If body is a stream, read it all
            elif isinstance(body, io.IOBase):
                body_bytes = body.read()
                # Try to decode as UTF-8
                try:
                    body = body_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Keep as bytes if not valid UTF-8
                    body = body_bytes

            # Parse JSON bodies
            if body and content_type and 'application/json' in content_type:
                try:
                    body = json.loads(body) if isinstance(body, (str, bytes)) else body
                except (json.JSONDecodeError, TypeError):
                    # Keep as string if not valid JSON
                    pass

        return HttpResponse(
            status_code=response.status_code,
            headers=response.headers.copy() if response.headers else {},
            body=body,
            content_type=content_type
        )

    def get_openapi_spec(self) -> Dict[str, Any]:
        """Get OpenAPI specification from the application."""
        if hasattr(self.app, 'generate_openapi_json'):
            openapi_json = self.app.generate_openapi_json()
            import json
            return json.loads(openapi_json)
        elif hasattr(self.app, 'generate_openapi'):
            return self.app.generate_openapi()
        else:
            raise NotImplementedError("Application does not support OpenAPI generation")


class HttpDriver(DriverInterface):
    """
    Driver that executes requests through actual HTTP calls.

    This would be used to test against a running HTTP server.
    For now, this is a placeholder for future implementation.
    """

    def __init__(self, base_url: str):
        """Initialize with base URL of the running server."""
        self.base_url = base_url.rstrip('/')

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute request through actual HTTP call."""
        # This would use requests library or similar to make actual HTTP calls
        # For now, just raise NotImplementedError
        raise NotImplementedError(
            "HttpDriver is not yet implemented. "
            "This would make actual HTTP requests to a running server."
        )


class MockDriver(DriverInterface):
    """
    Mock driver for testing the test framework itself.

    Useful for unit testing the DSL and driver abstractions.
    """

    def __init__(self):
        """Initialize with empty response queue."""
        self.requests = []
        self.responses = []
        self.response_index = 0

    def expect_response(self, response: HttpResponse):
        """Queue a response to be returned by the next execute call."""
        self.responses.append(response)

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Record request and return next queued response."""
        self.requests.append(request)

        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response

        # Default response if none queued
        return HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"message": "Mock response"}
        )

    def get_requests(self):
        """Get all recorded requests."""
        return self.requests.copy()

    def reset(self):
        """Reset recorded requests and responses."""
        self.requests.clear()
        self.responses.clear()
        self.response_index = 0



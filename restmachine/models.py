"""
Core data models for the REST framework.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class HTTPMethod(Enum):
    """Enumeration of supported HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class Request:
    """Represents an HTTP request."""

    method: HTTPMethod
    path: str
    headers: Dict[str, str]
    body: Optional[str] = None
    query_params: Optional[Dict[str, str]] = None
    path_params: Optional[Dict[str, str]] = None

    def get_accept_header(self) -> str:
        """Get the Accept header, defaulting to */* if not present."""
        return self.headers.get("Accept", "*/*")

    def get_content_type(self) -> Optional[str]:
        """Get the Content-Type header."""
        return self.headers.get("Content-Type")


@dataclass
class Response:
    """Represents an HTTP response."""

    status_code: int
    body: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    content_type: Optional[str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.content_type:
            self.headers["Content-Type"] = self.content_type

        # Automatically inject Content-Length header
        if self.status_code != 204:  # Do not include Content-Length for 204 responses
            if self.body is not None:
                # Calculate byte length of body
                body_bytes = self.body.encode('utf-8') if isinstance(self.body, str) else self.body
                content_length = len(body_bytes) if body_bytes else 0
            else:
                # No body, set Content-Length to 0
                content_length = 0
            self.headers["Content-Length"] = str(content_length)

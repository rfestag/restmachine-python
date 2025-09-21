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

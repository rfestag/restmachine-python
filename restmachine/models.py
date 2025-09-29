"""
Core data models for the REST framework.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


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

    def get_if_match(self) -> Optional[List[str]]:
        """Get the If-Match header values as a list of ETags."""
        if_match = self.headers.get("If-Match")
        if not if_match:
            return None
        if if_match.strip() == "*":
            return ["*"]
        # Parse comma-separated ETags, handling quoted values
        etags = []
        for etag in if_match.split(","):
            etag = etag.strip()
            if etag.startswith('"') and etag.endswith('"'):
                etags.append(etag)
            elif etag.startswith('W/"') and etag.endswith('"'):
                etags.append(etag)
            else:
                etags.append(f'"{etag}"')
        return etags

    def get_if_none_match(self) -> Optional[List[str]]:
        """Get the If-None-Match header values as a list of ETags."""
        if_none_match = self.headers.get("If-None-Match")
        if not if_none_match:
            return None
        if if_none_match.strip() == "*":
            return ["*"]
        # Parse comma-separated ETags, handling quoted values
        etags = []
        for etag in if_none_match.split(","):
            etag = etag.strip()
            if etag.startswith('"') and etag.endswith('"'):
                etags.append(etag)
            elif etag.startswith('W/"') and etag.endswith('"'):
                etags.append(etag)
            else:
                etags.append(f'"{etag}"')
        return etags

    def get_if_modified_since(self) -> Optional[datetime]:
        """Get the If-Modified-Since header as a datetime object."""
        if_modified_since = self.headers.get("If-Modified-Since")
        if not if_modified_since:
            return None
        try:
            # Parse HTTP date format: "Mon, 01 Jan 2024 00:00:00 GMT"
            parsed = datetime.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S %Z")
            # Convert to UTC timezone-aware datetime for proper comparison
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                # Try alternative format: "Mon, 01-Jan-2024 00:00:00 GMT"
                parsed = datetime.strptime(if_modified_since, "%a, %d-%b-%Y %H:%M:%S %Z")
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None

    def get_if_unmodified_since(self) -> Optional[datetime]:
        """Get the If-Unmodified-Since header as a datetime object."""
        if_unmodified_since = self.headers.get("If-Unmodified-Since")
        if not if_unmodified_since:
            return None
        try:
            # Parse HTTP date format: "Mon, 01 Jan 2024 00:00:00 GMT"
            parsed = datetime.strptime(if_unmodified_since, "%a, %d %b %Y %H:%M:%S %Z")
            # Convert to UTC timezone-aware datetime for proper comparison
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                # Try alternative format: "Mon, 01-Jan-2024 00:00:00 GMT"
                parsed = datetime.strptime(if_unmodified_since, "%a, %d-%b-%Y %H:%M:%S %Z")
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None


@dataclass
class Response:
    """Represents an HTTP response."""

    status_code: int
    body: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    content_type: Optional[str] = None
    request: Optional['Request'] = None
    available_content_types: Optional[list] = None
    pre_calculated_headers: Optional[Dict[str, str]] = None
    etag: Optional[str] = None
    last_modified: Optional[datetime] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}

        # If we have pre-calculated headers, use them first
        if self.pre_calculated_headers:
            self.headers.update(self.pre_calculated_headers)

        # Set content type
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

        # Automatically inject Vary header only if not already provided via pre_calculated_headers
        if not self.pre_calculated_headers or "Vary" not in self.pre_calculated_headers:
            vary_values = []

            # Add "Authorization" to Vary if request has Authorization header
            if self.request and self.request.headers.get("Authorization"):
                vary_values.append("Authorization")

            # Add "Accept" to Vary if endpoint accepts more than one content type
            if self.available_content_types and len(self.available_content_types) > 1:
                vary_values.append("Accept")

            # Set Vary header if we have values to include
            if vary_values:
                self.headers["Vary"] = ", ".join(vary_values)

    def set_etag(self, etag: str, weak: bool = False):
        """Set the ETag header.

        Args:
            etag: The ETag value (without quotes)
            weak: Whether this is a weak ETag (prefixed with W/)
        """
        if self.headers is None:
            self.headers = {}

        if weak:
            self.headers["ETag"] = f'W/"{etag}"'
        else:
            self.headers["ETag"] = f'"{etag}"'
        self.etag = etag

    def set_last_modified(self, last_modified: datetime):
        """Set the Last-Modified header.

        Args:
            last_modified: The last modified datetime
        """
        # Format as HTTP date: "Mon, 01 Jan 2024 00:00:00 GMT"
        if self.headers is None:
            self.headers = {}
        self.headers["Last-Modified"] = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.last_modified = last_modified

    def generate_etag_from_content(self, weak: bool = False):
        """Generate and set ETag based on response body content.

        Args:
            weak: Whether to generate a weak ETag
        """
        if self.body is None:
            return

        # Generate SHA-256 hash of content for ETag
        content_bytes = self.body.encode('utf-8') if isinstance(self.body, str) else self.body
        etag = hashlib.sha256(content_bytes).hexdigest()
        self.set_etag(etag, weak)


def parse_etags(etag_header: str) -> List[str]:
    """Parse comma-separated ETag values from a header.

    Args:
        etag_header: The raw ETag header value

    Returns:
        List of parsed ETag values (including quotes and W/ prefix if present)
    """
    if not etag_header:
        return []

    if etag_header.strip() == "*":
        return ["*"]

    etags = []
    for etag in etag_header.split(","):
        etag = etag.strip()
        if etag.startswith('"') and etag.endswith('"'):
            etags.append(etag)
        elif etag.startswith('W/"') and etag.endswith('"'):
            etags.append(etag)
        else:
            # Assume unquoted ETag, add quotes
            etags.append(f'"{etag}"')
    return etags


def etags_match(etag1: str, etag2: str, strong_comparison: bool = True) -> bool:
    """Compare two ETag values according to RFC 7232.

    Args:
        etag1: First ETag value (with quotes and W/ prefix if applicable)
        etag2: Second ETag value (with quotes and W/ prefix if applicable)
        strong_comparison: Whether to perform strong comparison (weak ETags don't match)

    Returns:
        True if ETags match according to the comparison type
    """
    if not etag1 or not etag2:
        return False

    # Extract the actual ETag values (without W/ prefix and quotes)
    def extract_etag_value(etag: str) -> tuple[str, bool]:
        etag = etag.strip()
        is_weak = etag.startswith('W/')
        if is_weak:
            etag = etag[2:]  # Remove W/ prefix
        if etag.startswith('"') and etag.endswith('"'):
            etag = etag[1:-1]  # Remove quotes
        return etag, is_weak

    value1, is_weak1 = extract_etag_value(etag1)
    value2, is_weak2 = extract_etag_value(etag2)

    # Strong comparison: both must be strong ETags and values must match
    if strong_comparison:
        return not (is_weak1 or is_weak2) and value1 == value2

    # Weak comparison: values must match regardless of weak/strong
    return value1 == value2

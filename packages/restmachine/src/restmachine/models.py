"""
Core data models for the REST framework.
"""

import hashlib
import io
import logging
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# Set up logger for this module
logger = logging.getLogger(__name__)


class MultiValueHeaders:
    """
    Multi-value, case-insensitive headers container.

    HTTP headers are case-insensitive per RFC 7230, and the same header can appear
    multiple times. This class handles both requirements:

    - Case-insensitive lookups
    - Multiple values per header name

    Common headers that can appear multiple times:

    - Set-Cookie, Accept, Accept-Language, Accept-Encoding
    - Vary, WWW-Authenticate, Warning, Via, Link

    Example::

        headers = MultiValueHeaders()
        headers.add('Set-Cookie', 'session=abc')
        headers.add('Set-Cookie', 'user=123')
        headers.get('set-cookie')      # Returns 'session=abc' (first value)
        headers.get_all('set-cookie')  # Returns ['session=abc', 'user=123']
        headers['content-type'] = 'application/json'  # Sets single value

        # Dict-like iteration (returns first value for each header)
        for name, value in headers.items():
            print(f"{name}: {value}")
    """

    def __init__(self, data=None):
        """
        Initialize headers from dict, list of tuples, or another MultiValueHeaders.

        Args:
            data: Can be:
                - Dict[str, str] or Dict[str, List[str]]
                - List of (name, value) tuples
                - Another MultiValueHeaders instance
                - None
        """
        # Internal storage: Dict[lowercase_name, List[Tuple[original_name, value]]]
        self._headers: Dict[str, List[Tuple[str, str]]] = {}

        if data is not None:
            if isinstance(data, MultiValueHeaders):
                self._headers = {k: list(v) for k, v in data._headers.items()}
            elif isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, list):
                        for v in value:
                            self.add(key, v)
                    else:
                        self.add(key, value)
            elif isinstance(data, (list, tuple)):
                for key, value in data:
                    self.add(key, value)

    def add(self, name: str, value: str) -> None:
        """
        Add a header value, allowing multiple values for the same name.

        Args:
            name: Header name (case-insensitive)
            value: Header value
        """
        name_lower = name.lower()
        if name_lower not in self._headers:
            self._headers[name_lower] = []
        self._headers[name_lower].append((name, value))

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get the first value for a header name.

        Args:
            name: Header name (case-insensitive)
            default: Default value if header not found

        Returns:
            First header value or default
        """
        # Handle non-string keys gracefully
        if not isinstance(name, str):
            return default

        name_lower = name.lower()
        if name_lower in self._headers and self._headers[name_lower]:
            return self._headers[name_lower][0][1]
        return default

    def get_all(self, name: str) -> List[str]:
        """
        Get all values for a header name.

        Args:
            name: Header name (case-insensitive)

        Returns:
            List of all values for this header (empty list if not found)
        """
        name_lower = name.lower()
        if name_lower in self._headers:
            return [value for _, value in self._headers[name_lower]]
        return []

    def set(self, name: str, value: str) -> None:
        """
        Set a header to a single value, replacing any existing values.

        Args:
            name: Header name (case-insensitive)
            value: Header value
        """
        name_lower = name.lower()
        self._headers[name_lower] = [(name, value)]

    def __setitem__(self, name: str, value: str) -> None:
        """Set a header to a single value (dict-like interface)."""
        self.set(name, value)

    def __getitem__(self, name: str) -> str:
        """
        Get first value for a header (dict-like interface).

        Raises:
            KeyError: If header not found
        """
        # Handle non-string keys - raise KeyError
        if not isinstance(name, str):
            raise KeyError(name)

        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __contains__(self, name: str) -> bool:
        """Check if header exists (case-insensitive)."""
        if not isinstance(name, str):
            return False
        return name.lower() in self._headers

    def __delitem__(self, name: str) -> None:
        """Delete all values for a header."""
        if not isinstance(name, str):
            raise KeyError(name)

        name_lower = name.lower()
        if name_lower in self._headers:
            del self._headers[name_lower]
        else:
            raise KeyError(name)

    def __iter__(self):
        """Iterate over header names (using original casing of first occurrence)."""
        for values in self._headers.values():
            if values:
                yield values[0][0]

    def keys(self):
        """Return header names (using original casing of first occurrence)."""
        return list(self)

    def values(self):
        """Return first value for each header."""
        return [values[0][1] for values in self._headers.values() if values]

    def items(self):
        """Return (name, first_value) pairs."""
        return [(values[0][0], values[0][1]) for values in self._headers.values() if values]

    def items_all(self):
        """
        Return all (name, value) pairs including duplicates.

        Useful for serialization to formats that support multiple headers.
        """
        result = []
        for values in self._headers.values():
            result.extend(values)
        return result

    def to_dict(self) -> Dict[str, str]:
        """
        Convert to a simple dict with first value for each header.

        Returns:
            Dict with lowercase keys and first values
        """
        return {values[0][0]: values[0][1] for values in self._headers.values() if values}

    def to_multidict(self) -> Dict[str, List[str]]:
        """
        Convert to a dict with lists of all values.

        Returns:
            Dict with lowercase keys and lists of all values
        """
        return {
            values[0][0]: [v for _, v in values]
            for values in self._headers.values() if values
        }

    def update(self, other) -> None:
        """
        Update headers from dict or iterable.

        For dict-like behavior, this replaces existing headers with the same name
        rather than adding to them. Use add() directly if you want to append values.
        """
        if isinstance(other, MultiValueHeaders):
            # For MultiValueHeaders, we need to handle multi-value headers properly
            # Group by header name first, then set all values at once
            for name_lower, values in other._headers.items():
                # Clear existing values for this header
                if name_lower in self._headers:
                    del self._headers[name_lower]
                # Add all new values
                for original_name, value in values:
                    self.add(original_name, value)
        elif isinstance(other, dict):
            for key, value in other.items():
                if isinstance(value, list):
                    # Replace with all values from list
                    self.set(key, value[0]) if value else None
                    for v in value[1:]:
                        self.add(key, v)
                else:
                    # Replace with single value
                    self.set(key, value)
        elif isinstance(other, (list, tuple)):
            for key, value in other:
                # For list of tuples, set first occurrence, add subsequent ones
                # But since we process sequentially, we just set each one
                # which means last one wins for simple cases
                self.set(key, value)

    def __repr__(self):
        """String representation showing all headers."""
        items = [(name, value) for name, value in self.items()]
        return f"MultiValueHeaders({items!r})"

    def __len__(self):
        """Return number of distinct header names."""
        return len(self._headers)

    def copy(self):
        """Return a shallow copy of the headers."""
        return MultiValueHeaders(self)


# Backward compatibility alias
CaseInsensitiveDict = MultiValueHeaders


class HTTPMethod(Enum):
    """Enumeration of supported HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class Request:
    """Represents an HTTP request.

    Supports the ASGI TLS extension for TLS/SSL connection information.

    The body is a file-like stream of bytes that can be read by content parsers.
    This allows efficient handling of large request bodies without loading
    everything into memory.
    """

    method: HTTPMethod
    path: str
    headers: Union[Dict[str, str], 'MultiValueHeaders']
    body: Optional[BinaryIO] = None
    query_params: Optional[Dict[str, str]] = None
    path_params: Optional[Dict[str, str]] = None
    tls: bool = False  # ASGI TLS extension: whether connection uses TLS
    client_cert: Optional[Dict[str, Any]] = None  # ASGI TLS extension: client certificate info

    def __post_init__(self):
        """Ensure headers is a MultiValueHeaders for case-insensitive header lookups."""
        if not isinstance(self.headers, MultiValueHeaders):
            self.headers = MultiValueHeaders(self.headers)

    def get_accept_header(self) -> str:
        """Get the Accept header, defaulting to */* if not present."""
        # Try lowercase first (from ASGI), fall back to title case (from test drivers)
        result = self.headers.get("accept") or self.headers.get("Accept")
        return result if result else "*/*"

    def get_content_type(self) -> Optional[str]:
        """Get the Content-Type header."""
        # Try lowercase first (from ASGI), fall back to title case (from test drivers)
        return self.headers.get("content-type") or self.headers.get("Content-Type")

    def get_authorization_header(self) -> Optional[str]:
        """Get the Authorization header."""
        # Try lowercase first (from ASGI), fall back to title case (from test drivers)
        return self.headers.get("authorization") or self.headers.get("Authorization")

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
    """Represents an HTTP response.

    The body can be:
    - str: Will be encoded to UTF-8 bytes
    - bytes: Used directly
    - BinaryIO: File-like object that will be streamed (useful for large files, S3 objects, etc.)
    - Path: Local filesystem path to a file (will be served efficiently)
    - dict/list: Will be JSON-encoded
    - None: Empty response body

    For Path objects:
    - ASGI servers will use the path send extension for efficient file serving
    - Lambda will read the file and send as body
    - Content-Type is automatically detected from file extension
    - Content-Length is automatically set from file size
    """

    status_code: int
    body: Optional[Union[str, bytes, BinaryIO, Path, dict, list]] = None
    headers: Optional[Union[Dict[str, str], 'MultiValueHeaders']] = None
    content_type: Optional[str] = None
    request: Optional['Request'] = None
    available_content_types: Optional[list] = None
    pre_calculated_headers: Optional[Union[Dict[str, str], 'MultiValueHeaders']] = None
    etag: Optional[str] = None
    last_modified: Optional[datetime] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = MultiValueHeaders()
        elif not isinstance(self.headers, MultiValueHeaders):
            self.headers = MultiValueHeaders(self.headers)

        # If we have pre-calculated headers, use them first
        if self.pre_calculated_headers:
            self.headers.update(self.pre_calculated_headers)

        # Handle Path objects - set Content-Type and Content-Length
        if isinstance(self.body, Path):
            # Detect Content-Type from file extension if not already set
            if not self.content_type and "Content-Type" not in self.headers:
                detected_type, _ = mimetypes.guess_type(str(self.body))
                if detected_type:
                    self.headers["Content-Type"] = detected_type
                    self.content_type = detected_type  # Also update the field
                else:
                    # Default to application/octet-stream for unknown types
                    self.headers["Content-Type"] = "application/octet-stream"
                    self.content_type = "application/octet-stream"

            # Set Content-Length from file size
            if self.body.exists() and self.body.is_file():
                file_size = self.body.stat().st_size
                self.headers["Content-Length"] = str(file_size)

        # Set content type
        if self.content_type:
            self.headers["Content-Type"] = self.content_type

        # Automatically inject Content-Length header (but not for streaming bodies, Path, or 204)
        if self.status_code != HTTPStatus.NO_CONTENT:
            if self.body is not None and not isinstance(self.body, (io.IOBase, Path)):
                # Calculate byte length of body (only for non-streaming bodies)
                import json
                if isinstance(self.body, str):
                    body_bytes = self.body.encode('utf-8')
                elif isinstance(self.body, (dict, list)):
                    body_bytes = json.dumps(self.body).encode('utf-8')
                elif isinstance(self.body, bytes):
                    body_bytes = self.body
                else:
                    body_bytes = str(self.body).encode('utf-8')

                content_length = len(body_bytes) if body_bytes else 0
                self.headers["Content-Length"] = str(content_length)
            elif self.body is None:
                # No body, set Content-Length to 0
                self.headers["Content-Length"] = "0"
            # For streaming bodies (io.IOBase) and Path objects, Content-Length is handled separately
            # Path: Already set above from file size
            # io.IOBase: Adapter will need to handle Transfer-Encoding: chunked

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

        Note:
            For streaming bodies (BinaryIO), this will read the entire stream to calculate
            the hash. The stream will be reset to the beginning after hashing.
        """
        if self.body is None:
            return

        # Generate SHA-256 hash of content for ETag
        import json
        if isinstance(self.body, str):
            content_bytes = self.body.encode('utf-8')
        elif isinstance(self.body, bytes):
            content_bytes = self.body
        elif isinstance(self.body, (dict, list)):
            content_bytes = json.dumps(self.body).encode('utf-8')
        elif isinstance(self.body, io.IOBase):
            # For streaming bodies, read all content for hash, then reset
            hasher = hashlib.sha256()
            original_pos = self.body.tell() if hasattr(self.body, 'tell') else 0
            while True:
                chunk = self.body.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
            # Reset stream to original position
            if hasattr(self.body, 'seek'):
                self.body.seek(original_pos)
            etag = hasher.hexdigest()
            self.set_etag(etag, weak)
            return
        else:
            content_bytes = str(self.body).encode('utf-8')

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

"""
Tests for Range requests and partial content (HTTP Range Requests).

RFC 9110 Section 14: Range requests allow clients to request partial
transfer of a selected representation.
https://www.rfc-editor.org/rfc/rfc9110.html#section-14
"""

import io
import pytest
from pathlib import Path
from restmachine import RestApplication, Response, FileResponse
from tests.framework import MultiDriverTestBase


class TestRangeRequests(MultiDriverTestBase):
    """Test Range request support per RFC 9110 Section 14."""

    ENABLED_DRIVERS = ['direct', 'asgi']

    def create_app(self) -> RestApplication:
        """Create app with range-capable resources."""
        app = RestApplication()

        # Large text content for range testing
        large_content = "0123456789" * 100  # 1000 bytes (bytes 0-999)

        @app.get("/bytes.txt")
        def get_bytes():
            """Return bytes content that supports range requests.

            RFC 9110 Section 14.1: Origin server MAY generate 206 (Partial Content)
            response to valid Range request.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-14.1
            """
            return Response(
                status_code=200,
                body=large_content.encode('utf-8'),
                headers={"Content-Type": "text/plain"}
            )

        @app.get("/stream.txt")
        def get_stream():
            """Return stream content that supports range requests."""
            stream = io.BytesIO(large_content.encode('utf-8'))
            return Response(
                status_code=200,
                body=stream,
                headers={"Content-Type": "text/plain"}
            )

        @app.get("/string.txt")
        def get_string():
            """Return string content (converted to bytes for range support)."""
            return Response(
                status_code=200,
                body=large_content,
                headers={"Content-Type": "text/plain"}
            )

        @app.get("/dict.json")
        def get_dict():
            """Return dict content (doesn't support ranges)."""
            return Response(
                status_code=200,
                body={"data": "value"},
                headers={"Content-Type": "application/json"}
            )

        @app.resource_exists
        def resource_exists(request):
            """Check if resource exists."""
            return request.path in ["/bytes.txt", "/stream.txt", "/string.txt", "/dict.json"]

        return app

    def test_accept_ranges_bytes_for_rangeable_content(self, api):
        """Test Accept-Ranges: bytes for content that supports ranges.

        RFC 9110 Section 14.5: Accept-Ranges field allows server to indicate
        whether it supports range requests for target resource.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.5
        """
        api_client, driver_name = api

        response = api_client.get_resource("/bytes.txt")

        assert response.status_code == 200
        assert response.get_header("Accept-Ranges") == "bytes"

    def test_accept_ranges_none_for_non_rangeable_content(self, api):
        """Test Accept-Ranges: none for content that doesn't support ranges.

        RFC 9110 Section 14.5: Server that does not support any kind of range
        request for target resource MAY send "Accept-Ranges: none".
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.5
        """
        api_client, driver_name = api

        response = api_client.get_resource("/dict.json")

        assert response.status_code == 200
        assert response.get_header("Accept-Ranges") == "none"

    def test_range_request_first_500_bytes(self, api):
        """Test Range request for first 500 bytes.

        RFC 9110 Section 14.2: Range: bytes=0-499 requests first 500 bytes.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.2
        """
        api_client, driver_name = api

        request = api_client.get("/bytes.txt").with_header("Range", "bytes=0-499")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 0-499/1000"
        assert response.get_header("Content-Length") == "500"
        assert len(response.body) == 500
        assert response.body == b"0123456789" * 50  # First 500 bytes

    def test_range_request_middle_bytes(self, api):
        """Test Range request for middle bytes.

        RFC 9110 Section 14.2: Range: bytes=500-999 requests bytes 500-999.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.2
        """
        api_client, driver_name = api

        request = api_client.get("/bytes.txt").with_header("Range", "bytes=500-999")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 500-999/1000"
        assert response.get_header("Content-Length") == "500"
        assert len(response.body) == 500
        assert response.body == b"0123456789" * 50  # Second 500 bytes

    def test_range_request_last_500_bytes(self, api):
        """Test Range request for last 500 bytes using suffix range.

        RFC 9110 Section 14.2: Range: bytes=-500 requests last 500 bytes.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.2
        """
        api_client, driver_name = api

        request = api_client.get("/bytes.txt").with_header("Range", "bytes=-500")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 500-999/1000"
        assert response.get_header("Content-Length") == "500"
        assert len(response.body) == 500
        assert response.body == b"0123456789" * 50  # Last 500 bytes

    def test_range_request_open_ended(self, api):
        """Test Range request with open-ended range.

        RFC 9110 Section 14.2: Range: bytes=500- requests all bytes from 500 onward.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14.2
        """
        api_client, driver_name = api

        request = api_client.get("/bytes.txt").with_header("Range", "bytes=500-")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 500-999/1000"
        assert response.get_header("Content-Length") == "500"
        assert len(response.body) == 500

    def test_416_range_out_of_bounds(self, api):
        """Test 416 Range Not Satisfiable for out-of-bounds range.

        RFC 9110 Section 15.5.17: 416 Range Not Satisfiable indicates that
        none of the ranges in request's Range header field overlap current
        extent of selected representation.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.17
        """
        api_client, driver_name = api

        request = api_client.get("/bytes.txt").with_header("Range", "bytes=1000-1999")
        response = api_client.execute(request)

        assert response.status_code == 416
        assert response.get_header("Content-Range") == "bytes */1000"

    def test_range_request_on_stream(self, api):
        """Test Range request works with stream bodies."""
        api_client, driver_name = api

        request = api_client.get("/stream.txt").with_header("Range", "bytes=0-99")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 0-99/1000"
        assert len(response.body) == 100
        assert response.body == b"0123456789" * 10

    def test_range_request_on_string_body(self, api):
        """Test Range request works with string bodies (auto-converted to bytes)."""
        api_client, driver_name = api

        request = api_client.get("/string.txt").with_header("Range", "bytes=0-99")
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 0-99/1000"
        assert len(response.body) == 100
        assert response.body == b"0123456789" * 10

    def test_no_range_header_returns_full_content(self, api):
        """Test that without Range header, full content is returned."""
        api_client, driver_name = api

        response = api_client.get_resource("/bytes.txt")

        assert response.status_code == 200
        assert response.get_header("Accept-Ranges") == "bytes"
        assert "Content-Range" not in response.headers
        assert len(response.body) == 1000


class TestIfRangeHeader(MultiDriverTestBase):
    """Test If-Range conditional range requests per RFC 9110 Section 13.1.5."""

    ENABLED_DRIVERS = ['direct', 'asgi']

    def create_app(self) -> RestApplication:
        """Create app with ETag support for If-Range testing."""
        app = RestApplication()

        content = "0123456789" * 100  # 1000 bytes

        @app.get("/etag-file.txt")
        def get_etag_file():
            """Return file with ETag for If-Range testing."""
            response = Response(
                status_code=200,
                body=content.encode('utf-8'),
                headers={"Content-Type": "text/plain"}
            )
            response.etag = '"test-etag-123"'
            return response

        @app.resource_exists
        def resource_exists(request):
            return request.path == "/etag-file.txt"

        return app

    def test_if_range_with_matching_etag(self, api):
        """Test If-Range with matching ETag sends 206 Partial Content.

        RFC 9110 Section 13.1.5: If-Range with matching validator should
        return 206 Partial Content with requested range.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5
        """
        api_client, driver_name = api

        request = api_client.get("/etag-file.txt") \
            .with_header("Range", "bytes=0-99") \
            .with_header("If-Range", '"test-etag-123"')
        response = api_client.execute(request)

        assert response.status_code == 206
        assert response.get_header("Content-Range") == "bytes 0-99/1000"
        assert len(response.body) == 100

    def test_if_range_with_non_matching_etag(self, api):
        """Test If-Range with non-matching ETag sends 200 OK with full content.

        RFC 9110 Section 13.1.5: If-Range with non-matching validator should
        ignore Range header and return 200 OK with full representation.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5
        """
        api_client, driver_name = api

        request = api_client.get("/etag-file.txt") \
            .with_header("Range", "bytes=0-99") \
            .with_header("If-Range", '"wrong-etag"')
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Content-Range" not in response.headers
        assert len(response.body) == 1000

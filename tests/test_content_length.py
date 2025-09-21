"""
Tests for automatic Content-Length header injection.
"""


from restmachine.models import Response


class TestContentLengthHeader:
    """Test automatic Content-Length header injection for different scenarios."""

    def test_200_response_with_body(self):
        """Test 200 response with body gets correct Content-Length."""
        response = Response(200, "Hello, World!")
        expected_length = len("Hello, World!".encode('utf-8'))
        assert response.headers["Content-Length"] == str(expected_length)

    def test_200_response_with_no_body(self):
        """Test 200 response with no body gets Content-Length of 0."""
        response = Response(200, None)
        assert response.headers["Content-Length"] == "0"

    def test_200_response_with_empty_string_body(self):
        """Test 200 response with empty string body gets Content-Length of 0."""
        response = Response(200, "")
        assert response.headers["Content-Length"] == "0"

    def test_204_response_no_content_length(self):
        """Test 204 response does not have Content-Length header."""
        response = Response(204)
        assert "Content-Length" not in response.headers

    def test_200_response_with_unicode_content(self):
        """Test 200 response with Unicode content gets correct byte length."""
        unicode_body = "Hello, 世界! 🌍"
        response = Response(200, unicode_body)
        expected_length = len(unicode_body.encode('utf-8'))
        assert response.headers["Content-Length"] == str(expected_length)

    def test_response_with_existing_headers(self):
        """Test that Content-Length is added to existing headers."""
        headers = {"X-Custom": "value"}
        response = Response(200, "test", headers=headers)
        assert response.headers["Content-Length"] == "4"
        assert response.headers["X-Custom"] == "value"

    def test_response_with_content_type(self):
        """Test that Content-Length works with content type."""
        response = Response(200, "test", content_type="application/json")
        assert response.headers["Content-Length"] == "4"
        assert response.headers["Content-Type"] == "application/json"
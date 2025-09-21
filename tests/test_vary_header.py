"""
Tests for automatic Vary header injection.
"""

import pytest

from restmachine import HTTPMethod, Request, Response, RestApplication


class TestVaryHeader:
    """Test automatic Vary header injection for different scenarios."""

    def test_response_with_authorization_header(self):
        """Test that Vary: Authorization is added when request has Authorization header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Authorization": "Bearer token123"}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json"]
        )
        assert "Vary" in response.headers
        assert "Authorization" in response.headers["Vary"]

    def test_response_without_authorization_header(self):
        """Test that Vary: Authorization is NOT added when request has no Authorization header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json"]
        )
        if "Vary" in response.headers:
            assert "Authorization" not in response.headers["Vary"]

    def test_response_with_multiple_content_types(self):
        """Test that Vary: Accept is added when endpoint accepts multiple content types."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json", "text/html", "text/plain"]
        )
        assert "Vary" in response.headers
        assert "Accept" in response.headers["Vary"]

    def test_response_with_single_content_type(self):
        """Test that Vary: Accept is NOT added when endpoint accepts only one content type."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json"]
        )
        if "Vary" in response.headers:
            assert "Accept" not in response.headers["Vary"]

    def test_response_with_both_authorization_and_multiple_content_types(self):
        """Test that both Authorization and Accept are added to Vary header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Authorization": "Bearer token123"}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json", "text/html"]
        )
        assert "Vary" in response.headers
        vary_header = response.headers["Vary"]
        assert "Authorization" in vary_header
        assert "Accept" in vary_header
        assert "Authorization, Accept" == vary_header

    def test_response_without_vary_conditions(self):
        """Test that no Vary header is added when neither condition is met."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={}
        )
        response = Response(
            200,
            "test content",
            request=request,
            available_content_types=["application/json"]
        )
        assert "Vary" not in response.headers

    def test_204_response_with_vary_conditions(self):
        """Test that Vary header is added to 204 responses when conditions are met."""
        request = Request(
            method=HTTPMethod.DELETE,
            path="/test",
            headers={"Authorization": "Bearer token123"}
        )
        response = Response(
            204,
            request=request,
            available_content_types=["application/json", "text/html"]
        )
        assert "Vary" in response.headers
        vary_header = response.headers["Vary"]
        assert "Authorization" in vary_header
        assert "Accept" in vary_header

    def test_vary_header_with_existing_headers(self):
        """Test that Vary header is added alongside existing headers."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Authorization": "Bearer token123"}
        )
        headers = {"X-Custom": "value", "Cache-Control": "max-age=3600"}
        response = Response(
            200,
            "test content",
            headers=headers,
            request=request,
            available_content_types=["application/json", "text/html"]
        )
        assert "Vary" in response.headers
        assert "X-Custom" in response.headers
        assert "Cache-Control" in response.headers
        assert response.headers["X-Custom"] == "value"
        assert response.headers["Cache-Control"] == "max-age=3600"

    def test_end_to_end_with_rest_application(self):
        """Test Vary header behavior in an end-to-end scenario with RestApplication."""
        app = RestApplication()

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        # Test with authorization header and multiple content types available
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Authorization": "Bearer token123", "Accept": "application/json"}
        )

        response = app.execute(request)

        # Should have Vary header with both Authorization and Accept
        # (since app has multiple default content renderers: JSON, HTML, PlainText)
        assert "Vary" in response.headers
        vary_header = response.headers["Vary"]
        assert "Authorization" in vary_header
        assert "Accept" in vary_header

    def test_end_to_end_without_authorization(self):
        """Test Vary header behavior without authorization header."""
        app = RestApplication()

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        # Test without authorization header but with multiple content types available
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        # Should have Vary header with only Accept
        # (since app has multiple default content renderers: JSON, HTML, PlainText)
        assert "Vary" in response.headers
        vary_header = response.headers["Vary"]
        assert "Authorization" not in vary_header
        assert "Accept" in vary_header
        assert vary_header == "Accept"
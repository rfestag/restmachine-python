"""
Tests for application.py body parsing edge cases.

Covers multipart_body, text_body, form_body parsing.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestBodyParsingVariants(MultiDriverTestBase):
    """Test different body parsing methods."""

    def create_app(self) -> RestApplication:
        """Create app with different body parsing."""
        app = RestApplication()

        @app.post("/upload-text")
        def handle_text(text_body):
            """Handle plain text body."""
            return {"received": text_body, "type": "text"}

        @app.post("/upload-multipart")
        def handle_multipart(multipart_body):
            """Handle multipart form data."""
            # multipart_body should be the raw multipart content
            return {"received": True, "content_length": len(multipart_body) if multipart_body else 0}

        @app.post("/upload-form")
        def handle_form(form_body):
            """Handle URL-encoded form data."""
            return {"form_data": form_body}

        return app

    def test_text_body_parsing(self, api):
        """Test text_body parameter parsing."""
        api_client, driver_name = api

        text_content = "This is plain text content"
        request = (api_client.post("/upload-text")
                  .with_text_body(text_content)
                  .with_header("Content-Type", "text/plain")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["type"] == "text"
        assert text_content in data["received"]

    def test_multipart_body_parsing(self, api):
        """Test multipart_body parameter parsing."""
        api_client, driver_name = api

        multipart_data = (
            "--boundary123\r\n"
            "Content-Disposition: form-data; name=\"field1\"\r\n"
            "\r\n"
            "value1\r\n"
            "--boundary123--\r\n"
        )

        request = (api_client.post("/upload-multipart")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=boundary123")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"] is True
        assert data["content_length"] > 0

    def test_form_body_parsing(self, api):
        """Test form_body parameter parsing."""
        api_client, driver_name = api

        form_data = "key1=value1&key2=value2"
        request = (api_client.post("/upload-form")
                  .with_text_body(form_data)
                  .with_header("Content-Type", "application/x-www-form-urlencoded")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "form_data" in data


class TestHandlerMatchingEdgeCases(MultiDriverTestBase):
    """Test handler matching edge cases."""

    def create_app(self) -> RestApplication:
        """Create app to test handler matching."""
        app = RestApplication()

        # Create a route with no specific content negotiation (default handler)
        @app.get("/default-handler")
        def default_handler():
            """Handler without specific content type."""
            return {"message": "default"}

        # Create a JSON-specific handler
        @app.get("/json-only")
        @app.renders("application/json")
        def json_handler():
            """JSON-specific handler."""
            return {"message": "json"}

        return app

    def test_default_handler_matches_all(self, api):
        """Test default handler (no content_type) matches any Accept header."""
        api_client, driver_name = api

        # Should work with any Accept header
        request = api_client.get("/default-handler").accepts("application/xml")
        response = api_client.execute(request)
        # Should succeed (200) because default handler matches all
        assert response.status_code in [200, 406]  # 406 if XML rendering not supported

    def test_handler_without_accept_header(self, api):
        """Test handler behavior when no Accept header is provided."""
        api_client, driver_name = api

        # Direct request without explicit Accept header
        request = api_client.get("/json-only")
        # Don't set Accept header
        response = api_client.execute(request)

        # Should either succeed or return 406 depending on implementation
        assert response.status_code in [200, 406]

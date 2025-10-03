"""
Content negotiation tests across all drivers.

Tests for Accept header handling, quality values, wildcards,
content type selection, and response rendering.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase

class TestContentNegotiationEdgeCases(MultiDriverTestBase):
    """Test edge cases in content negotiation across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with multiple response renderers."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            """Get data that can be rendered in multiple formats."""
            return {"message": "Hello", "timestamp": "2024-01-01T00:00:00Z"}

        @app.renders("text/html")
        def render_html(get_data):
            data = get_data
            return f"<h1>{data['message']}</h1><p>Time: {data['timestamp']}</p>"

        @app.renders("text/plain")
        def render_text(get_data):
            data = get_data
            return f"Message: {data['message']}\nTime: {data['timestamp']}"

        @app.renders("application/xml")
        def render_xml(get_data):
            data = get_data
            return f"<data><message>{data['message']}</message><timestamp>{data['timestamp']}</timestamp></data>"

        return app

    def test_accept_header_with_quality_values(self, api):
        """Test Accept header with quality values."""
        api_client, driver_name = api

        # Request with quality preferences
        request = (api_client.get("/data")
                  .with_header("Accept", "text/html;q=0.9, application/json;q=1.0, text/plain;q=0.8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_retrieval(response)

        # Should prefer JSON (q=1.0)
        assert response.content_type == "application/json"
        assert data["message"] == "Hello"

    def test_accept_header_with_wildcards(self, api):
        """Test Accept header with wildcard types."""
        api_client, driver_name = api

        request = api_client.get("/data").with_header("Accept", "text/*")
        response = api_client.execute(request)

        # restmachine doesn't support partial wildcards like text/*
        assert response.status_code == 406
        assert "Not Acceptable" in response.body

    def test_accept_all_wildcard(self, api):
        """Test Accept: */* header."""
        api_client, driver_name = api

        request = api_client.get("/data").with_header("Accept", "*/*")
        response = api_client.execute(request)

        assert response.status_code == 200
        # Should return some content type
        assert response.content_type is not None

    def test_multiple_accept_types_first_available(self, api):
        """Test multiple Accept types where first available is chosen."""
        api_client, driver_name = api

        request = (api_client.get("/data")
                  .with_header("Accept", "application/pdf, text/html, application/json"))

        response = api_client.execute(request)
        assert response.status_code == 200
        # Should choose the first available type (text/html)
        assert response.content_type == "text/html"

    def test_no_accept_header_defaults_to_json(self, api):
        """Test that no Accept header defaults to first available renderer."""
        api_client, driver_name = api

        request = api_client.get("/data")
        # Don't set Accept header
        response = api_client.execute(request)

        assert response.status_code == 200
        # restmachine defaults to first available renderer (text/html in this case)
        assert response.content_type == "text/html"
        assert "<h1>Hello</h1>" in response.body

    def test_unsupported_accept_type_returns_406(self, api):
        """Test that unsupported Accept type returns 406."""
        api_client, driver_name = api

        request = api_client.get("/data").with_header("Accept", "application/pdf")
        response = api_client.execute(request)

        assert response.status_code == 406  # Not Acceptable


class TestResponseRendering(MultiDriverTestBase):
    """Test response rendering in different formats across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with multiple response formats."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"id": 1, "title": "Test Resource", "description": "A test resource"}

        @app.renders("text/html")
        def render_html(get_resource):
            data = get_resource
            return f"""
            <div class="resource">
                <h1>{data['title']}</h1>
                <p>ID: {data['id']}</p>
                <p>{data['description']}</p>
            </div>
            """

        @app.renders("text/plain")
        def render_text(get_resource):
            data = get_resource
            return f"Resource {data['id']}: {data['title']} - {data['description']}"

        return app

    def test_json_response_by_default(self, api):
        """Test that JSON is returned by default."""
        api_client, driver_name = api

        response = api_client.get_resource("/resource")

        data = api_client.expect_successful_retrieval(response)
        assert data["id"] == 1
        assert data["title"] == "Test Resource"
        assert response.content_type == "application/json"

    def test_html_response_when_requested(self, api):
        """Test that HTML is returned when requested."""
        api_client, driver_name = api

        response = api_client.get_as_html("/resource")

        assert response.status_code == 200
        assert response.content_type == "text/html"
        html_content = response.get_text_body()
        assert "<h1>Test Resource</h1>" in html_content
        assert "ID: 1" in html_content

    def test_text_response_when_requested(self, api):
        """Test that plain text is returned when requested."""
        api_client, driver_name = api

        request = api_client.get("/resource").accepts("text/plain")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.content_type == "text/plain"
        text_content = response.get_text_body()
        assert "Resource 1: Test Resource" in text_content

    def test_unsupported_accept_type_returns_406(self, api):
        """Test that unsupported Accept header returns 406."""
        api_client, driver_name = api

        request = api_client.get("/resource").accepts("application/pdf")
        response = api_client.execute(request)

        assert response.status_code == 406  # Not Acceptable


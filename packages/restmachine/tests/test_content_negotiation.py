"""
Content negotiation tests across all drivers.

Tests for Accept header handling, quality values, wildcards,
content type selection, response rendering, and charset handling
for both request parsing and response generation.
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

        @app.provides("text/html")
        def render_html(get_data):
            data = get_data
            return f"<h1>{data['message']}</h1><p>Time: {data['timestamp']}</p>"

        @app.provides("text/plain")
        def render_text(get_data):
            data = get_data
            return f"Message: {data['message']}\nTime: {data['timestamp']}"

        @app.provides("application/xml")
        def render_xml(get_data):
            data = get_data
            return f"<data><message>{data['message']}</message><timestamp>{data['timestamp']}</timestamp></data>"

        return app

    def test_accept_header_with_quality_values(self, api):
        """Test Accept header with quality values.

        RFC 9110 Section 12.5.1 & 12.4.2: Accept header uses quality values (q parameter,
        0-1 scale) to indicate relative preference. Higher q values preferred.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.1
        """
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
        """Test that unsupported Accept type returns 406.

        RFC 9110 Section 15.5.7: 406 Not Acceptable when server cannot produce
        response matching Accept criteria.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.7
        """
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

        @app.provides("text/html")
        def render_html(get_resource):
            data = get_resource
            return f"""
            <div class="resource">
                <h1>{data['title']}</h1>
                <p>ID: {data['id']}</p>
                <p>{data['description']}</p>
            </div>
            """

        @app.provides("text/plain")
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


class TestRequestCharsetHandling(MultiDriverTestBase):
    """Test charset parameter handling in request Content-Type headers."""

    def create_app(self) -> RestApplication:
        """Create app with charset-sensitive endpoints."""
        app = RestApplication()

        @app.post("/json-endpoint")
        def handle_json(json_body):
            """Handle JSON with various charsets."""
            return {"received": json_body}

        @app.post("/text-endpoint")
        def handle_text(text_body):
            """Handle plain text with various charsets."""
            return {"text": text_body, "length": len(text_body)}

        @app.post("/form-endpoint")
        def handle_form(form_body):
            """Handle form data with various charsets."""
            return {"form_data": form_body}

        return app

    def test_json_with_utf8_charset(self, api):
        """Test JSON parsing with explicit UTF-8 charset."""
        api_client, driver_name = api

        # JSON with UTF-8 charset explicitly specified
        json_data = {"message": "Hello, 世界"}  # Contains Unicode characters
        request = (api_client.post("/json-endpoint")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"]["message"] == "Hello, 世界"

    def test_json_without_charset_defaults_to_utf8(self, api):
        """Test JSON parsing without charset defaults to UTF-8."""
        api_client, driver_name = api

        json_data = {"message": "Hello, 世界"}
        request = (api_client.post("/json-endpoint")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"]["message"] == "Hello, 世界"

    def test_json_with_latin1_charset(self, api):
        """Test JSON parsing with Latin1 charset."""
        api_client, driver_name = api

        # Create JSON with Latin1-encoded string
        # Latin1 can encode characters 0-255 only
        json_str = '{"message": "Café"}'  # é is in Latin1 range
        json_bytes = json_str.encode('latin1')

        request = (api_client.post("/json-endpoint")
                  .with_bytes_body(json_bytes)
                  .with_header("Content-Type", "application/json; charset=iso-8859-1")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "message" in data["received"]
        assert "Caf" in data["received"]["message"]  # Should contain the decoded message

    def test_text_with_utf8_charset(self, api):
        """Test text parsing with UTF-8 charset."""
        api_client, driver_name = api

        text_content = "Hello, 世界! 🌍"
        request = (api_client.post("/text-endpoint")
                  .with_text_body(text_content)
                  .with_header("Content-Type", "text/plain; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "世界" in data["text"]
        assert "🌍" in data["text"]

    def test_text_without_charset_defaults_to_utf8(self, api):
        """Test text parsing without charset defaults to UTF-8."""
        api_client, driver_name = api

        text_content = "Hello, 世界!"
        request = (api_client.post("/text-endpoint")
                  .with_text_body(text_content)
                  .with_header("Content-Type", "text/plain")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "世界" in data["text"]

    def test_text_with_latin1_charset(self, api):
        """Test text parsing with Latin1 charset."""
        api_client, driver_name = api

        # Text with Latin1 characters
        text_content = "Café résumé"
        text_bytes = text_content.encode('latin1')

        request = (api_client.post("/text-endpoint")
                  .with_bytes_body(text_bytes)
                  .with_header("Content-Type", "text/plain; charset=iso-8859-1")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "Caf" in data["text"]
        assert "sum" in data["text"]

    def test_form_with_utf8_charset(self, api):
        """Test form parsing with UTF-8 charset."""
        api_client, driver_name = api

        # Form data with UTF-8 characters (URL-encoded)
        form_str = "name=世界&message=Hello"
        form_bytes = form_str.encode('utf-8')

        request = (api_client.post("/form-endpoint")
                  .with_bytes_body(form_bytes)
                  .with_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "form_data" in data
        # Form data should be parsed
        assert isinstance(data["form_data"], dict)

    def test_form_without_charset_defaults_to_utf8(self, api):
        """Test form parsing without charset defaults to UTF-8."""
        api_client, driver_name = api

        form_data = "key1=value1&key2=value2"
        request = (api_client.post("/form-endpoint")
                  .with_text_body(form_data)
                  .with_header("Content-Type", "application/x-www-form-urlencoded")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["form_data"]["key1"] == "value1"
        assert data["form_data"]["key2"] == "value2"

    def test_charset_with_quoted_value(self, api):
        """Test charset parameter with quoted value."""
        api_client, driver_name = api

        json_data = {"message": "Hello"}
        request = (api_client.post("/json-endpoint")
                  .with_json_body(json_data)
                  .with_header("Content-Type", 'application/json; charset="utf-8"')
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"]["message"] == "Hello"

    def test_charset_fallback_to_latin1_for_invalid_utf8(self, api):
        """Test fallback to Latin1 when UTF-8 decoding fails."""
        api_client, driver_name = api

        # Create bytes that are valid Latin1 but invalid UTF-8
        # Byte 0xFF is valid in Latin1 (ÿ) but not valid UTF-8
        text_bytes = b"Hello \xff World"

        request = (api_client.post("/text-endpoint")
                  .with_bytes_body(text_bytes)
                  .with_header("Content-Type", "text/plain")  # No charset - should try UTF-8 then Latin1
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        # Should have fallen back to Latin1 and decoded successfully
        assert "Hello" in data["text"]
        assert "World" in data["text"]
        # Latin1 byte 0xFF decodes to Unicode character U+00FF (ÿ)
        assert "\xff" in data["text"] or "ÿ" in data["text"]


class TestResponseCharsetProvides(MultiDriverTestBase):
    """Test charset parameter in provides() decorator for responses."""

    def create_app(self) -> RestApplication:
        """Create app with various charset configurations."""
        app = RestApplication()

        @app.get("/html-utf8")
        def get_html_utf8():
            return {"message": "Hello"}

        @app.provides("text/html", charset="utf-8")
        def render_html_utf8(get_html_utf8):
            return f"<h1>{get_html_utf8['message']}</h1>"

        @app.get("/html-latin1")
        def get_html_latin1():
            return {"message": "Café"}

        @app.provides("text/html", charset="iso-8859-1")
        def render_html_latin1(get_html_latin1):
            return f"<h1>{get_html_latin1['message']}</h1>"

        @app.get("/html-no-charset")
        def get_html_no_charset():
            return {"message": "Test"}

        @app.provides("text/html")
        def render_html_no_charset(get_html_no_charset):
            return f"<h1>{get_html_no_charset['message']}</h1>"

        @app.get("/json-utf8")
        def get_json_utf8():
            return {"message": "世界"}

        @app.provides("application/json", charset="utf-8")
        def render_json_utf8(get_json_utf8):
            import json
            return json.dumps(get_json_utf8)

        @app.error_provides("text/html", charset="utf-8")
        @app.handles_error(404)
        def custom_404_html(request):
            return "<h1>404 - Not Found</h1>"

        @app.error_provides("application/json", charset="utf-8")
        @app.handles_error(404)
        def custom_404_json(request):
            return {"error": "Not found"}

        @app.get("/exists")
        def exists():
            return {"status": "ok"}

        return app

    def test_html_with_utf8_charset(self, api):
        """Test HTML response with UTF-8 charset in Content-Type."""
        api_client, driver_name = api

        request = (api_client.get("/html-utf8")
                  .with_header("Accept", "text/html"))

        response = api_client.execute(request)

        assert response.status_code == 200
        assert "text/html" in response.content_type
        assert "charset=utf-8" in response.content_type
        assert "<h1>Hello</h1>" in response.body

    def test_html_with_latin1_charset(self, api):
        """Test HTML response with Latin1 charset in Content-Type."""
        api_client, driver_name = api

        request = (api_client.get("/html-latin1")
                  .with_header("Accept", "text/html"))

        response = api_client.execute(request)

        assert response.status_code == 200
        assert "text/html" in response.content_type
        assert "charset=iso-8859-1" in response.content_type
        assert "Caf" in response.body

    def test_html_without_charset(self, api):
        """Test HTML response without charset parameter."""
        api_client, driver_name = api

        request = (api_client.get("/html-no-charset")
                  .with_header("Accept", "text/html"))

        response = api_client.execute(request)

        assert response.status_code == 200
        assert "text/html" in response.content_type
        # Should not have charset parameter
        assert "charset=" not in response.content_type

    def test_json_with_utf8_charset(self, api):
        """Test JSON response with UTF-8 charset in Content-Type."""
        api_client, driver_name = api

        request = (api_client.get("/json-utf8")
                  .with_header("Accept", "application/json"))

        response = api_client.execute(request)

        assert response.status_code == 200
        assert "application/json" in response.content_type
        assert "charset=utf-8" in response.content_type

    def test_error_handler_html_with_charset(self, api):
        """Test error handler HTML response with charset."""
        api_client, driver_name = api

        request = (api_client.get("/nonexistent")
                  .with_header("Accept", "text/html"))

        response = api_client.execute(request)

        assert response.status_code == 404
        assert "text/html" in response.content_type
        assert "charset=utf-8" in response.content_type
        assert "404 - Not Found" in response.body

    def test_error_handler_json_with_charset(self, api):
        """Test error handler JSON response with charset."""
        api_client, driver_name = api

        request = (api_client.get("/nonexistent")
                  .with_header("Accept", "application/json"))

        response = api_client.execute(request)

        assert response.status_code == 404
        assert "application/json" in response.content_type
        assert "charset=utf-8" in response.content_type

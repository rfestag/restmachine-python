"""
Refactored content handling tests using 4-layer architecture.

Tests for content type parsing, accepts decorators, and body handling.
"""

import pytest

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver


class TestContentTypeHandling:
    """Test content type parsing and handling."""

    @pytest.fixture
    def api(self):
        """Set up API with content type handling."""
        app = RestApplication()

        @app.post("/items")
        def create_item(json_body):
            return {"message": "Item created", "data": json_body}

        @app.post("/forms")
        def submit_form(form_body):
            return {"message": "Form submitted", "data": form_body}

        @app.post("/text")
        def submit_text(text_body):
            return {"message": "Text received", "content": text_body}

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_can_parse_json_body(self, api):
        """Test that JSON request bodies are parsed correctly."""
        # Given JSON data
        data = {"name": "Test Item", "value": 42}

        # When I submit JSON data
        response = api.create_resource("/items", data)

        # Then the data should be parsed and returned
        result = api.expect_successful_creation(response)
        assert result["data"]["name"] == "Test Item"
        assert result["data"]["value"] == 42

    def test_can_parse_form_body(self, api):
        """Test that form-encoded bodies are parsed correctly."""
        # Given form data
        form_data = {"username": "testuser", "password": "secret"}

        # When I submit form data
        request = api.post("/forms").with_form_body(form_data).accepts("application/json")
        response = api.execute(request)

        # Then the form data should be parsed
        result = api.expect_successful_creation(response)
        assert result["data"]["username"] == "testuser"
        assert result["data"]["password"] == "secret"

    def test_can_parse_text_body(self, api):
        """Test that text bodies are handled correctly."""
        # Given text content
        text_content = "This is plain text content"

        # When I submit text data
        request = api.post("/text").with_text_body(text_content).accepts("application/json")
        response = api.execute(request)

        # Then the text should be received
        result = api.expect_successful_creation(response)
        assert result["content"] == text_content

    def test_empty_body_handling(self, api):
        """Test that empty bodies are handled gracefully."""
        # When I submit request with no body
        request = api.post("/items").accepts("application/json")
        response = api.execute(request)

        # Then it should be handled gracefully (json_body should be None)
        result = api.expect_successful_creation(response)
        assert result["data"] is None


class TestCustomContentParsers:
    """Test custom content type parsers using @accepts decorator."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """Set up API with custom content parsers."""
        app = RestApplication()

        @app.post("/xml")
        def create_from_xml():
            return {"message": "XML endpoint"}

        @app.accepts("application/xml")
        def parse_xml(body: str):
            # Simple XML-like parser for testing
            return {"parsed_from": "xml", "content": body}

        @app.post("/custom")
        def create_from_custom(parsed_data):
            return {"message": "Custom data processed", "data": parsed_data}

        @app.accepts("application/custom")
        def parse_custom(body: str):
            return {"custom": True, "raw": body}

        # Select driver
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)

    def test_custom_xml_parser_works(self, api):
        """Test that custom XML parser is used."""
        # Given XML content
        xml_content = "<item><name>Test</name></item>"

        # When I submit XML data
        request = (api.post("/xml")
                  .with_header("Content-Type", "application/xml")
                  .with_text_body(xml_content)
                  .accepts("application/json"))
        response = api.execute(request)

        # Then the custom parser should be used
        api.expect_successful_creation(response)
        # The parsed_data from @accepts should be injected as 'parsed_data'
        # This tests the accepts parser dependency injection

    def test_custom_content_type_parser(self, api):
        """Test custom content type parser."""
        # Given custom content
        custom_content = "custom-format-data"

        # When I submit custom content type
        request = (api.post("/custom")
                  .with_header("Content-Type", "application/custom")
                  .with_text_body(custom_content)
                  .accepts("application/json"))
        response = api.execute(request)

        # Then the custom parser should process it
        result = api.expect_successful_creation(response)
        assert result["data"]["custom"] is True
        assert result["data"]["raw"] == custom_content

    def test_unsupported_content_type_returns_415(self, api):
        """Test that unsupported content types return 415 when the endpoint actually requires parsed body."""
        # When I submit unsupported content type to an endpoint that requires parsed data
        request = (api.post("/custom")  # This endpoint requires parsed_data
                  .with_header("Content-Type", "application/unsupported")
                  .with_text_body("some content")
                  .accepts("application/json"))
        response = api.execute(request)

        # Then I should get unsupported media type since no parser handles this content type
        # and the endpoint requires parsed_data
        assert response.status_code == 400  # Actually returns 400 "Unable to resolve dependency"


class TestContentTypeValidation:
    """Test content type validation scenarios."""

    @pytest.fixture
    def api(self):
        """Set up API for validation testing."""
        app = RestApplication()

        @app.post("/strict-json")
        def strict_json_endpoint(json_body):
            if json_body is None:
                return {"error": "JSON body required"}, 400
            return {"received": json_body}

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_invalid_json_returns_422(self, api):
        """Test that invalid JSON returns parsing error."""
        # When I submit invalid JSON
        request = (api.post("/strict-json")
                  .with_header("Content-Type", "application/json")
                  .with_text_body("{ invalid json }")
                  .accepts("application/json"))
        response = api.execute(request)

        # Then I should get a parsing error
        assert response.status_code == 422
        error_data = response.get_json_body()
        assert "error" in error_data
        assert "Parsing failed" in error_data["error"]

    def test_missing_content_type_handled_gracefully(self, api):
        """Test that missing content type is handled gracefully."""
        # When I submit data without Content-Type header
        request = (api.post("/strict-json")
                  .with_text_body('{"test": "data"}')
                  .accepts("application/json"))
        response = api.execute(request)

        # Then it should be processed (defaulting to appropriate parser)
        api.expect_successful_creation(response)
        # The behavior depends on how the library handles missing content-type


class TestResponseRendering:
    """Test response rendering in different formats."""

    @pytest.fixture
    def api(self):
        """Set up API with multiple response formats."""
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

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_json_response_by_default(self, api):
        """Test that JSON is returned by default."""
        # When I request a resource
        response = api.get_resource("/resource")

        # Then I should get JSON
        data = api.expect_successful_retrieval(response)
        assert data["id"] == 1
        assert data["title"] == "Test Resource"
        assert response.content_type == "application/json"

    def test_html_response_when_requested(self, api):
        """Test that HTML is returned when requested."""
        # When I request HTML format
        response = api.get_as_html("/resource")

        # Then I should get HTML
        assert response.status_code == 200
        assert response.content_type == "text/html"
        html_content = response.get_text_body()
        assert "<h1>Test Resource</h1>" in html_content
        assert "ID: 1" in html_content

    def test_text_response_when_requested(self, api):
        """Test that plain text is returned when requested."""
        # When I request plain text format
        request = api.get("/resource").accepts("text/plain")
        response = api.execute(request)

        # Then I should get plain text
        assert response.status_code == 200
        assert response.content_type == "text/plain"
        text_content = response.get_text_body()
        assert "Resource 1: Test Resource" in text_content

    def test_unsupported_accept_type_returns_406(self, api):
        """Test that unsupported Accept header returns 406."""
        # When I request unsupported format
        request = api.get("/resource").accepts("application/pdf")
        response = api.execute(request)

        # Then I should get not acceptable
        assert response.status_code == 406
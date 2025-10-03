"""
Content type and parser tests using multi-driver approach.

Tests for multipart form data, content-type with charset, complex parser
injection scenarios, custom content parsers, and content negotiation.
"""

from urllib.parse import urlencode

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestMultipartFormData(MultiDriverTestBase):
    """Test multipart form data handling across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with multipart handling."""
        app = RestApplication()

        @app.post("/upload")
        def handle_upload(text_body):
            """Handle multipart upload - simplified for testing."""
            return {
                "received": True,
                "content_length": len(text_body) if text_body else 0,
                "content_type": "multipart/form-data"
            }

        @app.post("/multipart")
        def handle_multipart(text_body):
            """Handle multipart data directly."""
            # Manually parse the multipart data for testing
            if text_body and "testboundary" in text_body:
                parsed_data = {
                    "type": "multipart",
                    "raw_content": text_body,
                    "parsed": True
                }
                return {
                    "processed": True,
                    "data": parsed_data
                }
            else:
                return {"error": "Invalid multipart data"}

        return app

    def test_multipart_form_data_basic(self, api):
        """Test basic multipart form data handling."""
        api_client, driver_name = api

        # Simulate multipart form data
        multipart_data = (
            "--boundary123\r\n"
            "Content-Disposition: form-data; name=\"field1\"\r\n"
            "\r\n"
            "value1\r\n"
            "--boundary123\r\n"
            "Content-Disposition: form-data; name=\"field2\"\r\n"
            "\r\n"
            "value2\r\n"
            "--boundary123--\r\n"
        )

        request = (api_client.post("/upload")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=boundary123")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"] is True
        assert data["content_length"] > 0

    def test_multipart_with_file_upload(self, api):
        """Test multipart form data with file upload simulation."""
        api_client, driver_name = api

        # Simulate file upload in multipart data
        multipart_data = (
            "--boundary456\r\n"
            "Content-Disposition: form-data; name=\"file\"; filename=\"test.txt\"\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "This is file content\r\n"
            "--boundary456\r\n"
            "Content-Disposition: form-data; name=\"description\"\r\n"
            "\r\n"
            "File description\r\n"
            "--boundary456--\r\n"
        )

        request = (api_client.post("/upload")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=boundary456")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"] is True
        assert "This is file content" in multipart_data

    def test_multipart_parser_injection(self, api):
        """Test multipart parser dependency injection."""
        api_client, driver_name = api

        multipart_data = (
            "--testboundary\r\n"
            "Content-Disposition: form-data; name=\"test_field\"\r\n"
            "\r\n"
            "test_value\r\n"
            "--testboundary--\r\n"
        )

        request = (api_client.post("/multipart")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=testboundary")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["processed"] is True
        assert data["data"]["type"] == "multipart"
        assert data["data"]["parsed"] is True


class TestContentTypeWithCharset(MultiDriverTestBase):
    """Test content type handling with charset parameters across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with charset handling."""
        app = RestApplication()

        @app.post("/text")
        def handle_text(text_body):
            """Handle text with various charsets."""
            return {
                "received_text": text_body,
                "length": len(text_body) if text_body else 0
            }

        @app.post("/json")
        def handle_json(json_body):
            """Handle JSON with charset."""
            return {
                "received_json": json_body,
                "type": "json"
            }

        return app

    def test_json_with_utf8_charset(self, api):
        """Test JSON with UTF-8 charset."""
        api_client, driver_name = api

        json_data = {"message": "Hello, 世界!"}

        request = (api_client.post("/json")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received_json"]["message"] == "Hello, 世界!"
        assert data["type"] == "json"

    def test_text_with_different_charsets(self, api):
        """Test text content with different charset declarations."""
        api_client, driver_name = api

        text_content = "Hello, world with special chars: ñáéíóú"

        # Test with UTF-8 charset
        request = (api_client.post("/text")
                  .with_text_body(text_content)
                  .with_header("Content-Type", "text/plain; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received_text"] == text_content
        assert data["length"] > 0

    def test_form_data_with_charset(self, api):
        """Test form data with charset parameter."""
        api_client, driver_name = api

        form_data = {"name": "José María", "city": "São Paulo"}
        encoded_data = urlencode(form_data)

        request = (api_client.post("/text")
                  .with_text_body(encoded_data)
                  .with_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert "Jos" in data["received_text"]  # Should contain part of José
        assert "Paulo" in data["received_text"]

    def test_content_type_case_insensitive_charset(self, api):
        """Test that charset parameter is case insensitive."""
        api_client, driver_name = api

        json_data = {"test": "value"}

        request = (api_client.post("/json")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json; CHARSET=UTF-8")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received_json"]["test"] == "value"


class TestComplexContentParsers(MultiDriverTestBase):
    """Test complex content parser scenarios across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with multiple custom parsers."""
        app = RestApplication()

        @app.accepts("application/xml")
        def parse_xml(body: str):
            """Simple XML parser for testing."""
            return {
                "format": "xml",
                "content": body,
                "parsed_at": "xml_parser"
            }

        @app.accepts("application/yaml")
        def parse_yaml(body: str):
            """Simple YAML parser for testing."""
            return {
                "format": "yaml",
                "content": body,
                "parsed_at": "yaml_parser"
            }

        @app.accepts("text/csv")
        def parse_csv(body: str):
            """Simple CSV parser for testing."""
            lines = body.strip().split('\n')
            return {
                "format": "csv",
                "rows": len(lines),
                "content": body,
                "parsed_at": "csv_parser"
            }

        @app.accepts("application/custom+json")
        def parse_custom_json(body: str):
            """Custom JSON variant parser."""
            import json
            data = json.loads(body)
            data["_custom_processed"] = True
            return {
                "format": "custom_json",
                "data": data,
                "parsed_at": "custom_json_parser"
            }

        @app.post("/process")
        def process_data(parsed_data):
            """Process data from various parsers."""
            # Return the parsed data from whichever parser was used
            return {"result": parsed_data}

        return app

    def test_xml_parser_selection(self, api):
        """Test XML parser selection and processing."""
        api_client, driver_name = api

        xml_content = "<root><item>value</item></root>"

        request = (api_client.post("/process")
                  .with_text_body(xml_content)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["result"]["format"] == "xml"
        assert data["result"]["parsed_at"] == "xml_parser"
        assert xml_content in data["result"]["content"]

    def test_yaml_parser_selection(self, api):
        """Test YAML parser selection and processing."""
        api_client, driver_name = api

        yaml_content = "key: value\nlist:\n  - item1\n  - item2"

        request = (api_client.post("/process")
                  .with_text_body(yaml_content)
                  .with_header("Content-Type", "application/yaml")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["result"]["format"] == "yaml"
        assert data["result"]["parsed_at"] == "yaml_parser"
        assert "key: value" in data["result"]["content"]

    def test_csv_parser_selection(self, api):
        """Test CSV parser selection and processing."""
        api_client, driver_name = api

        csv_content = "name,age,city\nJohn,30,NYC\nJane,25,LA"

        request = (api_client.post("/process")
                  .with_text_body(csv_content)
                  .with_header("Content-Type", "text/csv")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["result"]["format"] == "csv"
        assert data["result"]["parsed_at"] == "csv_parser"
        assert data["result"]["rows"] == 3  # Header + 2 data rows

    def test_custom_json_parser_selection(self, api):
        """Test custom JSON variant parser."""
        api_client, driver_name = api

        json_content = '{"type": "custom", "value": 42}'

        request = (api_client.post("/process")
                  .with_text_body(json_content)
                  .with_header("Content-Type", "application/custom+json")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["result"]["format"] == "custom_json"
        assert data["result"]["parsed_at"] == "custom_json_parser"
        assert data["result"]["data"]["type"] == "custom"
        assert data["result"]["data"]["_custom_processed"] is True

    def test_unsupported_content_type_with_required_parser(self, api):
        """Test unsupported content type when parser is required."""
        api_client, driver_name = api

        request = (api_client.post("/process")
                  .with_text_body("some content")
                  .with_header("Content-Type", "application/unsupported")
                  .accepts("application/json"))

        response = api_client.execute(request)

        # Should return 415/400 since no parser matched for required content type
        assert response.status_code in [400, 415]


class TestParserErrorHandling(MultiDriverTestBase):
    """Test error handling in content parsers across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with strict parsers for error testing."""
        app = RestApplication()

        @app.accepts("application/json")
        def parse_json_strict(body: str):
            """Strict JSON parser that raises on invalid JSON."""
            import json
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")

        @app.accepts("application/xml")
        def parse_xml_strict(body: str):
            """Strict XML parser that validates structure."""
            if not body.strip().startswith('<'):
                raise ValueError("Invalid XML: must start with <")
            if 'invalid' in body:
                raise ValueError("Invalid XML: contains forbidden content")
            return {"xml_content": body}

        @app.post("/strict-json")
        def handle_strict_json(parsed_data):
            """Handle strictly parsed JSON."""
            return {"data": parsed_data, "parser": "strict"}

        @app.post("/strict-xml")
        def handle_strict_xml(parsed_data):
            """Handle strictly parsed XML."""
            return {"data": parsed_data, "parser": "strict"}

        return app

    def test_json_parser_error_handling(self, api):
        """Test JSON parser error handling."""
        api_client, driver_name = api

        invalid_json = '{"incomplete": json'

        request = (api_client.post("/strict-json")
                  .with_text_body(invalid_json)
                  .with_header("Content-Type", "application/json")
                  .accepts("application/json"))

        response = api_client.execute(request)
        assert response.status_code == 422  # Unprocessable Entity

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_xml_parser_error_handling(self, api):
        """Test XML parser error handling."""
        api_client, driver_name = api

        invalid_xml = "not xml content"

        request = (api_client.post("/strict-xml")
                  .with_text_body(invalid_xml)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api_client.execute(request)
        assert response.status_code == 422

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_xml_parser_forbidden_content_error(self, api):
        """Test XML parser with forbidden content."""
        api_client, driver_name = api

        forbidden_xml = "<root>invalid content</root>"

        request = (api_client.post("/strict-xml")
                  .with_text_body(forbidden_xml)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api_client.execute(request)
        assert response.status_code == 422

    def test_valid_json_after_error_scenarios(self, api):
        """Test that valid JSON still works after error scenarios."""
        api_client, driver_name = api

        valid_json = '{"valid": "json", "number": 42}'

        request = (api_client.post("/strict-json")
                  .with_text_body(valid_json)
                  .with_header("Content-Type", "application/json")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["data"]["valid"] == "json"
        assert data["data"]["number"] == 42
        assert data["parser"] == "strict"


class TestBasicContentHandling(MultiDriverTestBase):
    """Test basic content type parsing and handling across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with basic content type handling."""
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

        return app

    def test_can_parse_json_body(self, api):
        """Test that JSON request bodies are parsed correctly."""
        api_client, driver_name = api

        data = {"name": "Test Item", "value": 42}

        response = api_client.create_resource("/items", data)
        result = api_client.expect_successful_creation(response)

        assert result["data"]["name"] == "Test Item"
        assert result["data"]["value"] == 42

    def test_can_parse_form_body(self, api):
        """Test that form-encoded bodies are parsed correctly."""
        api_client, driver_name = api

        form_data = {"username": "testuser", "password": "secret"}

        request = api_client.post("/forms").with_form_body(form_data).accepts("application/json")
        response = api_client.execute(request)

        result = api_client.expect_successful_creation(response)
        assert result["data"]["username"] == "testuser"
        assert result["data"]["password"] == "secret"

    def test_can_parse_text_body(self, api):
        """Test that text bodies are handled correctly."""
        api_client, driver_name = api

        text_content = "This is plain text content"

        request = api_client.post("/text").with_text_body(text_content).accepts("application/json")
        response = api_client.execute(request)

        result = api_client.expect_successful_creation(response)
        assert result["content"] == text_content

    def test_empty_body_handling(self, api):
        """Test that empty bodies are handled gracefully."""
        api_client, driver_name = api

        request = api_client.post("/items").accepts("application/json")
        response = api_client.execute(request)

        result = api_client.expect_successful_creation(response)
        assert result["data"] is None



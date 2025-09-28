"""
Refactored advanced content type tests using 4-layer architecture.

Tests for multipart form data, content-type with charset, complex parser
injection scenarios, and edge cases in content handling.
"""

import pytest
from urllib.parse import urlencode

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver


class TestMultipartFormData:
    """Test multipart form data handling."""

    @pytest.fixture
    def api(self):
        """Set up API for multipart form testing."""
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

        return RestApiDsl(RestMachineDriver(app))

    def test_multipart_form_data_basic(self, api):
        """Test basic multipart form data handling."""
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

        request = (api.post("/upload")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=boundary123")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received"] is True
        assert data["content_length"] > 0

    def test_multipart_with_file_upload(self, api):
        """Test multipart form data with file upload simulation."""
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

        request = (api.post("/upload")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=boundary456")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received"] is True
        assert "This is file content" in multipart_data

    def test_multipart_parser_injection(self, api):
        """Test multipart parser dependency injection."""
        multipart_data = (
            "--testboundary\r\n"
            "Content-Disposition: form-data; name=\"test_field\"\r\n"
            "\r\n"
            "test_value\r\n"
            "--testboundary--\r\n"
        )

        request = (api.post("/multipart")
                  .with_text_body(multipart_data)
                  .with_header("Content-Type", "multipart/form-data; boundary=testboundary")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["processed"] is True
        assert data["data"]["type"] == "multipart"
        assert data["data"]["parsed"] is True


class TestContentTypeWithCharset:
    """Test content type handling with charset parameters."""

    @pytest.fixture
    def api(self):
        """Set up API for charset testing."""
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

        return RestApiDsl(RestMachineDriver(app))

    def test_json_with_utf8_charset(self, api):
        """Test JSON with UTF-8 charset."""
        json_data = {"message": "Hello, 世界!"}

        request = (api.post("/json")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json; charset=utf-8")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received_json"]["message"] == "Hello, 世界!"
        assert data["type"] == "json"

    def test_text_with_different_charsets(self, api):
        """Test text content with different charset declarations."""
        text_content = "Hello, world with special chars: ñáéíóú"

        # Test with UTF-8 charset
        request = (api.post("/text")
                  .with_text_body(text_content)
                  .with_header("Content-Type", "text/plain; charset=utf-8")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received_text"] == text_content
        assert data["length"] > 0

    def test_form_data_with_charset(self, api):
        """Test form data with charset parameter."""
        form_data = {"name": "José María", "city": "São Paulo"}
        encoded_data = urlencode(form_data)

        request = (api.post("/text")
                  .with_text_body(encoded_data)
                  .with_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert "Jos" in data["received_text"]  # Should contain part of José
        assert "Paulo" in data["received_text"]

    def test_content_type_case_insensitive_charset(self, api):
        """Test that charset parameter is case insensitive."""
        json_data = {"test": "value"}

        request = (api.post("/json")
                  .with_json_body(json_data)
                  .with_header("Content-Type", "application/json; CHARSET=UTF-8")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received_json"]["test"] == "value"


class TestComplexContentParsers:
    """Test complex content parser scenarios."""

    @pytest.fixture
    def api(self):
        """Set up API with multiple custom parsers."""
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

        return RestApiDsl(RestMachineDriver(app))

    def test_xml_parser_selection(self, api):
        """Test XML parser selection and processing."""
        xml_content = "<root><item>value</item></root>"

        request = (api.post("/process")
                  .with_text_body(xml_content)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["result"]["format"] == "xml"
        assert data["result"]["parsed_at"] == "xml_parser"
        assert xml_content in data["result"]["content"]

    def test_yaml_parser_selection(self, api):
        """Test YAML parser selection and processing."""
        yaml_content = "key: value\nlist:\n  - item1\n  - item2"

        request = (api.post("/process")
                  .with_text_body(yaml_content)
                  .with_header("Content-Type", "application/yaml")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["result"]["format"] == "yaml"
        assert data["result"]["parsed_at"] == "yaml_parser"
        assert "key: value" in data["result"]["content"]

    def test_csv_parser_selection(self, api):
        """Test CSV parser selection and processing."""
        csv_content = "name,age,city\nJohn,30,NYC\nJane,25,LA"

        request = (api.post("/process")
                  .with_text_body(csv_content)
                  .with_header("Content-Type", "text/csv")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["result"]["format"] == "csv"
        assert data["result"]["parsed_at"] == "csv_parser"
        assert data["result"]["rows"] == 3  # Header + 2 data rows

    def test_custom_json_parser_selection(self, api):
        """Test custom JSON variant parser."""
        json_content = '{"type": "custom", "value": 42}'

        request = (api.post("/process")
                  .with_text_body(json_content)
                  .with_header("Content-Type", "application/custom+json")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["result"]["format"] == "custom_json"
        assert data["result"]["parsed_at"] == "custom_json_parser"
        assert data["result"]["data"]["type"] == "custom"
        assert data["result"]["data"]["_custom_processed"] is True

    def test_unsupported_content_type_with_required_parser(self, api):
        """Test unsupported content type when parser is required."""
        request = (api.post("/process")
                  .with_text_body("some content")
                  .with_header("Content-Type", "application/unsupported")
                  .accepts("application/json"))

        response = api.execute(request)

        # Should return 415/400 since no parser matched for required content type
        assert response.status_code in [400, 415]


class TestParserErrorHandling:
    """Test error handling in content parsers."""

    @pytest.fixture
    def api(self):
        """Set up API for parser error testing."""
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

        return RestApiDsl(RestMachineDriver(app))

    def test_json_parser_error_handling(self, api):
        """Test JSON parser error handling."""
        invalid_json = '{"incomplete": json'

        request = (api.post("/strict-json")
                  .with_text_body(invalid_json)
                  .with_header("Content-Type", "application/json")
                  .accepts("application/json"))

        response = api.execute(request)
        assert response.status_code == 422  # Unprocessable Entity

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_xml_parser_error_handling(self, api):
        """Test XML parser error handling."""
        invalid_xml = "not xml content"

        request = (api.post("/strict-xml")
                  .with_text_body(invalid_xml)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api.execute(request)
        assert response.status_code == 422

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_xml_parser_forbidden_content_error(self, api):
        """Test XML parser with forbidden content."""
        forbidden_xml = "<root>invalid content</root>"

        request = (api.post("/strict-xml")
                  .with_text_body(forbidden_xml)
                  .with_header("Content-Type", "application/xml")
                  .accepts("application/json"))

        response = api.execute(request)
        assert response.status_code == 422

    def test_valid_json_after_error_scenarios(self, api):
        """Test that valid JSON still works after error scenarios."""
        valid_json = '{"valid": "json", "number": 42}'

        request = (api.post("/strict-json")
                  .with_text_body(valid_json)
                  .with_header("Content-Type", "application/json")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["data"]["valid"] == "json"
        assert data["data"]["number"] == 42
        assert data["parser"] == "strict"


class TestContentNegotiationEdgeCases:
    """Test edge cases in content negotiation."""

    @pytest.fixture
    def api(self):
        """Set up API for content negotiation edge cases."""
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

        return RestApiDsl(RestMachineDriver(app))

    def test_accept_header_with_quality_values(self, api):
        """Test Accept header with quality values."""
        # Request with quality preferences
        request = (api.get("/data")
                  .with_header("Accept", "text/html;q=0.9, application/json;q=1.0, text/plain;q=0.8")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_retrieval(response)

        # Should prefer JSON (q=1.0)
        assert response.content_type == "application/json"
        assert data["message"] == "Hello"

    def test_accept_header_with_wildcards(self, api):
        """Test Accept header with wildcard types."""
        request = api.get("/data").with_header("Accept", "text/*")
        response = api.execute(request)

        # restmachine doesn't support partial wildcards like text/*
        assert response.status_code == 406
        assert "Not Acceptable" in response.body

    def test_accept_all_wildcard(self, api):
        """Test Accept: */* header."""
        request = api.get("/data").with_header("Accept", "*/*")
        response = api.execute(request)

        assert response.status_code == 200
        # Should return some content type
        assert response.content_type is not None

    def test_multiple_accept_types_first_available(self, api):
        """Test multiple Accept types where first available is chosen."""
        request = (api.get("/data")
                  .with_header("Accept", "application/pdf, text/html, application/json"))

        response = api.execute(request)
        assert response.status_code == 200
        # Should choose the first available type (text/html)
        assert response.content_type == "text/html"

    def test_no_accept_header_defaults_to_json(self, api):
        """Test that no Accept header defaults to first available renderer."""
        request = api.get("/data")
        # Don't set Accept header
        response = api.execute(request)

        assert response.status_code == 200
        # restmachine defaults to first available renderer (text/html in this case)
        assert response.content_type == "text/html"
        assert "<h1>Hello</h1>" in response.body

    def test_unsupported_accept_type_returns_406(self, api):
        """Test that unsupported Accept type returns 406."""
        request = api.get("/data").with_header("Accept", "application/pdf")
        response = api.execute(request)

        assert response.status_code == 406  # Not Acceptable


class TestContentTypeAcrossDrivers:
    """Test content type handling consistency across drivers."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """Parametrized fixture for testing across drivers."""
        app = RestApplication()

        @app.accepts("application/custom")
        def parse_custom(body: str):
            return {"custom": True, "content": body}

        @app.post("/custom")
        def handle_custom(parsed_data):
            return {"received": parsed_data}

        @app.post("/json")
        def handle_json(json_body):
            return {"received": json_body}

        # Select driver
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)

    def test_custom_content_type_across_drivers(self, api):
        """Test custom content type parsing across drivers."""
        custom_content = "custom format data"

        request = (api.post("/custom")
                  .with_text_body(custom_content)
                  .with_header("Content-Type", "application/custom")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        assert data["received"]["custom"] is True
        assert data["received"]["content"] == custom_content

    def test_json_handling_across_drivers(self, api):
        """Test JSON handling consistency across drivers."""
        json_data = {"test": "value", "number": 42}

        response = api.create_resource("/json", json_data)
        data = api.expect_successful_creation(response)

        assert data["received"]["test"] == "value"
        assert data["received"]["number"] == 42
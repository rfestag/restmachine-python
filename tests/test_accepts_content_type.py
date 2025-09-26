"""
Tests for the accepts decorator and Content-Type handling functionality.
"""

import json
import pytest
from unittest.mock import Mock

from restmachine import RestApplication
from restmachine.models import Request, HTTPMethod


class TestAcceptsContentType:

    def test_accepts_decorator_basic_functionality(self):
        """Test that the accepts decorator can be applied and registered."""
        app = RestApplication()

        @app.post("/test")
        def create_item():
            return {"message": "Item created"}

        @app.accepts("application/xml")
        def parse_xml(body: str):
            # Simple XML-like parser for testing
            return {"parsed_from": "xml", "content": body}

        # Check that the accepts wrapper was registered to the route
        route = app._routes[-1]  # Most recent route
        assert "application/xml" in route.accepts_dependencies
        assert route.accepts_dependencies["application/xml"].content_type == "application/xml"
        assert route.accepts_dependencies["application/xml"].func == parse_xml

    def test_accepts_decorator_global_registration(self):
        """Test that accepts decorator registers globally when no route exists."""
        app = RestApplication()

        @app.accepts("application/custom")
        def parse_custom(body: str):
            return {"custom": True, "data": body}

        # Should be registered globally
        assert "application/custom" in app._accepts_dependencies
        assert app._accepts_dependencies["application/custom"].content_type == "application/custom"

    def test_custom_content_type_parser_with_request(self):
        """Test that custom content-type parsers work with actual requests."""
        app = RestApplication()

        @app.post("/items")
        def create_item(parsed_data):
            return {"received": parsed_data}

        @app.accepts("application/xml")
        def parse_xml(body: str):
            # Simple XML-like parser
            if "<item>" in body and "</item>" in body:
                content = body.replace("<item>", "").replace("</item>", "")
                return {"name": content.strip()}
            return {"error": "Invalid XML"}

        # Create a request with XML content
        request = Request(
            method=HTTPMethod.POST,
            path="/items",
            headers={"Content-Type": "application/xml"},
            body="<item>Test Item</item>"
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["name"] == "Test Item"

    def test_built_in_json_body_parser(self):
        """Test the built-in json_body parser."""
        app = RestApplication()

        @app.post("/json-test")
        def handle_json(json_body):
            return {"received": json_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/json-test",
            headers={"Content-Type": "application/json"},
            body='{"name": "test", "value": 123}'
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["name"] == "test"
        assert response_data["received"]["value"] == 123

    def test_built_in_form_body_parser(self):
        """Test the built-in form_body parser."""
        app = RestApplication()

        @app.post("/form-test")
        def handle_form(form_body):
            return {"received": form_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/form-test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body="name=test&value=123&tags=a&tags=b"
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["name"] == "test"
        assert response_data["received"]["value"] == "123"
        assert response_data["received"]["tags"] == ["a", "b"]  # Multiple values should be preserved as list

    def test_built_in_text_body_parser(self):
        """Test the built-in text_body parser."""
        app = RestApplication()

        @app.post("/text-test")
        def handle_text(text_body):
            return {"received": text_body, "length": len(text_body)}

        request = Request(
            method=HTTPMethod.POST,
            path="/text-test",
            headers={"Content-Type": "text/plain"},
            body="This is plain text content"
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"] == "This is plain text content"
        assert response_data["length"] == 26

    def test_built_in_multipart_body_parser(self):
        """Test the built-in multipart_body parser."""
        app = RestApplication()

        @app.post("/multipart-test")
        def handle_multipart(multipart_body):
            return {"received": multipart_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/multipart-test",
            headers={"Content-Type": "multipart/form-data; boundary=----WebKitFormBoundary"},
            body="------WebKitFormBoundary\r\nContent-Disposition: form-data; name=\"field1\"\r\n\r\nvalue1\r\n------WebKitFormBoundary--"
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        # For now, multipart returns raw content with metadata
        assert "_raw_body" in response_data["received"]
        assert response_data["received"]["_content_type"] == "multipart/form-data"

    def test_unsupported_content_type_returns_415(self):
        """Test that unsupported content types return 415 Unsupported Media Type."""
        app = RestApplication()

        @app.post("/test")
        def handle_request(json_body):  # Expects JSON
            return {"received": json_body}

        # Send request with unsupported content type
        request = Request(
            method=HTTPMethod.POST,
            path="/test",
            headers={"Content-Type": "application/unknown"},
            body="some data"
        )

        response = app.execute(request)

        assert response.status_code == 415
        assert "Unsupported Media Type" in response.body

    def test_content_type_with_charset(self):
        """Test that content types with charset parameters work correctly."""
        app = RestApplication()

        @app.post("/charset-test")
        def handle_json(json_body):
            return {"received": json_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/charset-test",
            headers={"Content-Type": "application/json; charset=utf-8"},
            body='{"message": "test"}'
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["message"] == "test"

    def test_accepts_parser_injection(self):
        """Test that accepts parsers can use dependency injection."""
        app = RestApplication()

        @app.post("/injection-test")
        def handle_request(parsed_data):
            return {"received": parsed_data}

        @app.accepts("application/custom")
        def parse_custom(body: str, headers: dict):
            # Parser can access headers through dependency injection
            return {
                "content": body,
                "content_length": headers.get("Content-Length"),
                "custom": True
            }

        request = Request(
            method=HTTPMethod.POST,
            path="/injection-test",
            headers={"Content-Type": "application/custom", "Content-Length": "10"},
            body="test data"
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["content"] == "test data"
        assert response_data["received"]["custom"] is True

    def test_no_content_type_header_defaults_gracefully(self):
        """Test that requests without Content-Type headers are handled gracefully."""
        app = RestApplication()

        @app.post("/no-content-type")
        def handle_request(json_body):
            return {"received": json_body}

        # Request without Content-Type header but with JSON body
        request = Request(
            method=HTTPMethod.POST,
            path="/no-content-type",
            headers={},
            body='{"message": "test"}'
        )

        # Should assume application/octet-stream and try to parse as JSON, but fail gracefully
        response = app.execute(request)

        # Should return 415 since octet-stream is not supported for JSON parsing
        assert response.status_code == 415

    def test_empty_body_handling(self):
        """Test that empty bodies are handled correctly."""
        app = RestApplication()

        @app.post("/empty-body")
        def handle_request(json_body):
            return {"received": json_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/empty-body",
            headers={"Content-Type": "application/json"},
            body=""
        )

        response = app.execute(request)

        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"] is None

    def test_invalid_json_handling(self):
        """Test that invalid JSON returns 422 error."""
        app = RestApplication()

        @app.post("/invalid-json")
        def handle_request(json_body):
            return {"received": json_body}

        request = Request(
            method=HTTPMethod.POST,
            path="/invalid-json",
            headers={"Content-Type": "application/json"},
            body="{ invalid json }"
        )

        response = app.execute(request)

        # Should return 422 due to invalid JSON
        assert response.status_code == 422
        response_data = json.loads(response.body)
        assert response_data["error"] == "Parsing failed"
        assert "Invalid JSON" in response_data["message"]

    def test_accepts_parser_exception_returns_422(self):
        """Test that exceptions in accepts parsers return 422 status code."""
        app = RestApplication()

        @app.post("/failing-parser")
        def handle_request(parsed_data):
            return {"received": parsed_data}

        @app.accepts("application/xml")
        def parse_xml_fail(body: str):
            # This parser will always fail
            raise ValueError("XML parsing failed due to malformed structure")

        request = Request(
            method=HTTPMethod.POST,
            path="/failing-parser",
            headers={"Content-Type": "application/xml"},
            body="<invalid>xml</structure>"
        )

        response = app.execute(request)

        # Should return 422 when accepts parser throws exception
        assert response.status_code == 422
        response_data = json.loads(response.body)
        assert response_data["error"] == "Parsing failed"
        assert "XML parsing failed" in response_data["message"]

    def test_accepts_parser_dependency_injection_exception_returns_422(self):
        """Test that exceptions in accepts parsers using dependency injection return 422."""
        app = RestApplication()

        @app.post("/failing-parser-with-deps")
        def handle_request(parsed_data):
            return {"received": parsed_data}

        @app.accepts("application/custom")
        def parse_custom_with_deps(body: str, headers: dict):
            # This parser will fail when trying to access something that doesn't exist
            missing_header = headers["NonExistentHeader"]  # This will raise KeyError
            return {"content": body, "header": missing_header}

        request = Request(
            method=HTTPMethod.POST,
            path="/failing-parser-with-deps",
            headers={"Content-Type": "application/custom"},
            body="test data"
        )

        response = app.execute(request)

        # Should return 422 when accepts parser throws exception
        assert response.status_code == 422
        response_data = json.loads(response.body)
        assert response_data["error"] == "Parsing failed"
        assert "Failed to parse application/custom request body" in response_data["message"]

    def test_accepts_parser_exception_with_built_in_fallback(self):
        """Test that built-in parsers are not affected by accepts parser failure."""
        app = RestApplication()

        @app.post("/mixed-parsers")
        def handle_request(json_body):
            # Using built-in json_body parameter
            return {"received": json_body}

        @app.accepts("application/xml")
        def parse_xml_fail(body: str):
            # This parser will always fail, but shouldn't affect JSON parsing
            raise ValueError("XML parsing failed")

        # Test with JSON (should work fine)
        request = Request(
            method=HTTPMethod.POST,
            path="/mixed-parsers",
            headers={"Content-Type": "application/json"},
            body='{"message": "test"}'
        )

        response = app.execute(request)
        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data["received"]["message"] == "test"

    def test_invalid_form_data_returns_422(self):
        """Test that invalid form data returns 422 error."""
        app = RestApplication()

        @app.post("/invalid-form")
        def handle_request(form_body):
            return {"received": form_body}

        # Create a request with malformed form data that causes an exception
        # We'll use a mock that will raise an exception during parsing
        from unittest.mock import patch

        request = Request(
            method=HTTPMethod.POST,
            path="/invalid-form",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body="invalid\x00form\x01data"  # Contains null bytes that might cause issues
        )

        # This should still work as parse_qs can handle most input, but let's force an exception
        with patch('restmachine.application.parse_qs', side_effect=Exception("Form parsing error")):
            response = app.execute(request)

            # Should return 422 due to form parsing error
            assert response.status_code == 422
            response_data = json.loads(response.body)
            assert response_data["error"] == "Parsing failed"
            assert "Invalid form data" in response_data["message"]
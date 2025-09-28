"""
DSL (Domain Specific Language) for RESTful test actions.

This is the second layer in Dave Farley's 4-layer testing architecture:
1. Test Layer (actual test methods)
2. DSL Layer (this file) - describes what we want to do in business terms
3. Driver Layer - knows how to interact with the system
4. System Under Test (restmachine library)
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import json
import os


@dataclass
class HttpRequest:
    """Represents an HTTP request in business terms."""
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    body: Optional[Union[str, Dict[str, Any]]] = None
    content_type: Optional[str] = None

    def with_json_body(self, data: Dict[str, Any]) -> 'HttpRequest':
        """Add JSON body to the request."""
        self.body = data
        self.content_type = "application/json"
        self.headers["Content-Type"] = "application/json"
        return self

    def with_form_body(self, data: Dict[str, str]) -> 'HttpRequest':
        """Add form body to the request."""
        self.body = data
        self.content_type = "application/x-www-form-urlencoded"
        self.headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self

    def with_text_body(self, text: str) -> 'HttpRequest':
        """Add text body to the request."""
        self.body = text
        # Only set content type if not already set
        if "Content-Type" not in self.headers:
            self.content_type = "text/plain"
            self.headers["Content-Type"] = "text/plain"
        return self

    def with_header(self, name: str, value: str) -> 'HttpRequest':
        """Add a header to the request."""
        self.headers[name] = value
        return self

    def with_auth(self, token: str) -> 'HttpRequest':
        """Add authorization header."""
        self.headers["Authorization"] = f"Bearer {token}"
        return self

    def accepts(self, content_type: str) -> 'HttpRequest':
        """Set the Accept header."""
        self.headers["Accept"] = content_type
        return self


@dataclass
class HttpResponse:
    """Represents an HTTP response in business terms."""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Union[str, Dict[str, Any], List[Any]]] = None
    content_type: Optional[str] = None

    def is_successful(self) -> bool:
        """Check if response indicates success (2xx)."""
        return 200 <= self.status_code < 300

    def is_client_error(self) -> bool:
        """Check if response indicates client error (4xx)."""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """Check if response indicates server error (5xx)."""
        return 500 <= self.status_code < 600

    def has_header(self, name: str) -> bool:
        """Check if response has a specific header."""
        return name in self.headers

    def get_header(self, name: str) -> Optional[str]:
        """Get header value."""
        return self.headers.get(name)

    def get_json_body(self):
        """Get response body as JSON object or list."""
        if isinstance(self.body, (dict, list)):
            return self.body
        if isinstance(self.body, str):
            import json
            return json.loads(self.body)
        raise ValueError("Response body is not JSON")

    def get_text_body(self) -> str:
        """Get response body as text."""
        if isinstance(self.body, str):
            return self.body
        if isinstance(self.body, (dict, list)):
            import json
            return json.dumps(self.body)
        return str(self.body)


class RestApiDsl:
    """
    Domain-Specific Language for REST API testing.

    This provides a high-level, business-focused way to describe REST operations
    without knowing implementation details.
    """

    def __init__(self, driver):
        """Initialize with a driver that knows how to execute requests."""
        self._driver = driver

    # Request builders (fluent interface)
    def get(self, path: str) -> HttpRequest:
        """Create a GET request."""
        return HttpRequest(method="GET", path=path)

    def post(self, path: str) -> HttpRequest:
        """Create a POST request."""
        return HttpRequest(method="POST", path=path)

    def put(self, path: str) -> HttpRequest:
        """Create a PUT request."""
        return HttpRequest(method="PUT", path=path)

    def patch(self, path: str) -> HttpRequest:
        """Create a PATCH request."""
        return HttpRequest(method="PATCH", path=path)

    def delete(self, path: str) -> HttpRequest:
        """Create a DELETE request."""
        return HttpRequest(method="DELETE", path=path)

    def head(self, path: str) -> HttpRequest:
        """Create a HEAD request."""
        return HttpRequest(method="HEAD", path=path)

    def options(self, path: str) -> HttpRequest:
        """Create an OPTIONS request."""
        return HttpRequest(method="OPTIONS", path=path)

    # Execution
    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute a request using the underlying driver."""
        return self._driver.execute(request)

    # Convenience methods for common patterns
    def create_resource(self, path: str, data: Dict[str, Any]) -> HttpResponse:
        """Create a resource with JSON data."""
        request = self.post(path).with_json_body(data).accepts("application/json")
        return self.execute(request)

    def get_resource(self, path: str) -> HttpResponse:
        """Get a resource as JSON."""
        request = self.get(path).accepts("application/json")
        return self.execute(request)

    def update_resource(self, path: str, data: Dict[str, Any]) -> HttpResponse:
        """Update a resource with JSON data."""
        request = self.put(path).with_json_body(data).accepts("application/json")
        return self.execute(request)

    def delete_resource(self, path: str) -> HttpResponse:
        """Delete a resource."""
        request = self.delete(path).accepts("application/json")
        return self.execute(request)

    def search_resources(self, path: str, query: Dict[str, str]) -> HttpResponse:
        """Search resources with query parameters."""
        request = self.get(path).accepts("application/json")
        request.query_params.update(query)
        return self.execute(request)

    # Authentication helpers
    def authenticated_request(self, request: HttpRequest, token: str) -> HttpResponse:
        """Execute a request with authentication."""
        return self.execute(request.with_auth(token))

    def login(self, path: str, credentials: Dict[str, str]) -> HttpResponse:
        """Perform login and return response with session/token."""
        return self.create_resource(path, credentials)

    # Content negotiation helpers
    def get_as_html(self, path: str) -> HttpResponse:
        """Get a resource as HTML."""
        request = self.get(path).accepts("text/html")
        return self.execute(request)

    def get_as_xml(self, path: str) -> HttpResponse:
        """Get a resource as XML."""
        request = self.get(path).accepts("application/xml")
        return self.execute(request)

    # Conditional request helpers
    def get_if_modified_since(self, path: str, date: str) -> HttpResponse:
        """Get resource only if modified since date."""
        request = self.get(path).with_header("If-Modified-Since", date).accepts("application/json")
        return self.execute(request)

    def get_if_none_match(self, path: str, etag: str) -> HttpResponse:
        """Get resource only if ETag doesn't match."""
        request = self.get(path).with_header("If-None-Match", etag).accepts("application/json")
        return self.execute(request)

    def update_if_match(self, path: str, data: Dict[str, Any], etag: str) -> HttpResponse:
        """Update resource only if ETag matches."""
        request = self.put(path).with_json_body(data).with_header("If-Match", etag).accepts("application/json")
        return self.execute(request)

    # Validation and error testing helpers
    def submit_invalid_data(self, path: str, invalid_data: Dict[str, Any]) -> HttpResponse:
        """Submit invalid data expecting validation error."""
        return self.create_resource(path, invalid_data)

    def access_protected_resource(self, path: str) -> HttpResponse:
        """Access protected resource without auth (expecting 401)."""
        return self.get_resource(path)

    def access_forbidden_resource(self, path: str, token: str) -> HttpResponse:
        """Access forbidden resource with auth (expecting 403)."""
        request = self.get(path).with_auth(token).accepts("application/json")
        return self.execute(request)

    # Testing helpers for assertions
    def expect_successful_creation(self, response: HttpResponse, expected_fields: List[str] = None) -> Dict[str, Any]:
        """Assert successful resource creation and return data."""
        assert response.is_successful(), f"Expected successful response, got {response.status_code}"
        assert response.status_code in [200, 201], f"Expected 200 or 201, got {response.status_code}"

        data = response.get_json_body()
        if expected_fields:
            for field in expected_fields:
                assert field in data, f"Expected field '{field}' in response"

        return data

    def expect_successful_retrieval(self, response: HttpResponse) -> Dict[str, Any]:
        """Assert successful resource retrieval and return data."""
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        return response.get_json_body()

    def expect_not_found(self, response: HttpResponse):
        """Assert resource not found."""
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def expect_unauthorized(self, response: HttpResponse):
        """Assert unauthorized access."""
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def expect_forbidden(self, response: HttpResponse):
        """Assert forbidden access."""
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    def expect_validation_error(self, response: HttpResponse) -> Dict[str, Any]:
        """Assert validation error and return error details."""
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        return response.get_json_body()

    def expect_conflict(self, response: HttpResponse):
        """Assert resource conflict."""
        assert response.status_code == 409, f"Expected 409, got {response.status_code}"

    def expect_not_modified(self, response: HttpResponse):
        """Assert not modified response."""
        assert response.status_code == 304, f"Expected 304, got {response.status_code}"

    def expect_precondition_failed(self, response: HttpResponse):
        """Assert precondition failed."""
        assert response.status_code == 412, f"Expected 412, got {response.status_code}"

    def expect_no_content(self, response: HttpResponse):
        """Assert no content response."""
        assert response.status_code == 204, f"Expected 204, got {response.status_code}"

    # OpenAPI testing helpers
    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI specification from the application."""
        if hasattr(self._driver, 'get_openapi_spec'):
            return self._driver.get_openapi_spec()
        elif hasattr(self._driver, 'app') and hasattr(self._driver.app, 'generate_openapi'):
            return self._driver.app.generate_openapi()
        else:
            raise NotImplementedError("Driver does not support OpenAPI generation")

    def save_openapi_spec(self, directory: str = "docs", filename: str = "openapi.json") -> str:
        """Save OpenAPI specification to file and return the path."""
        spec = self.generate_openapi_spec()
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w') as f:
            json.dump(spec, f, indent=2)
        return filepath

    def validate_openapi_spec(self, spec: Dict[str, Any] = None) -> bool:
        """Validate OpenAPI specification."""
        try:
            from openapi_spec_validator import validate
        except ImportError:
            # Skip validation if openapi-spec-validator is not available
            return True

        if spec is None:
            spec = self.generate_openapi_spec()

        try:
            validate(spec)
            return True
        except Exception:
            return False

    def assert_openapi_valid(self, spec: Dict[str, Any] = None):
        """Assert that OpenAPI spec is valid."""
        if spec is None:
            spec = self.generate_openapi_spec()
        assert self.validate_openapi_spec(spec), "OpenAPI specification is invalid"

    def assert_has_path(self, spec: Dict[str, Any], path: str, method: str):
        """Assert that OpenAPI spec has a specific path and method."""
        assert "paths" in spec, "OpenAPI spec missing paths"
        assert path in spec["paths"], f"Path {path} not found in OpenAPI spec"
        assert method.lower() in spec["paths"][path], f"Method {method} not found for path {path}"

    def assert_has_schema(self, spec: Dict[str, Any], schema_name: str):
        """Assert that OpenAPI spec has a specific schema."""
        assert "components" in spec, "OpenAPI spec missing components"
        assert "schemas" in spec["components"], "OpenAPI spec missing schemas"
        assert schema_name in spec["components"]["schemas"], f"Schema {schema_name} not found"

    def get_path_operation(self, spec: Dict[str, Any], path: str, method: str) -> Dict[str, Any]:
        """Get path operation from OpenAPI spec."""
        return spec["paths"][path][method.lower()]

    def assert_request_body_schema(self, spec: Dict[str, Any], path: str, method: str, expected_schema: str):
        """Assert that path operation has expected request body schema."""
        operation = self.get_path_operation(spec, path, method)
        assert "requestBody" in operation, f"Path {path} {method} missing request body"
        content = operation["requestBody"]["content"]
        assert "application/json" in content, "Request body missing JSON content type"
        schema_ref = content["application/json"]["schema"]["$ref"]
        assert expected_schema in schema_ref, f"Expected schema {expected_schema} in request body"

    def assert_response_schema(self, spec: Dict[str, Any], path: str, method: str, status_code: str, expected_schema: str):
        """Assert that path operation has expected response schema."""
        operation = self.get_path_operation(spec, path, method)
        assert "responses" in operation, f"Path {path} {method} missing responses"
        assert status_code in operation["responses"], f"Status {status_code} not found in responses"
        response = operation["responses"][status_code]
        if "content" in response:
            content = response["content"]
            assert "application/json" in content, "Response missing JSON content type"
            schema_ref = content["application/json"]["schema"]["$ref"]
            assert expected_schema in schema_ref, f"Expected schema {expected_schema} in response"

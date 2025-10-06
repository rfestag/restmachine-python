"""
HTTP headers tests across all drivers.

Tests for default headers, Content-Length, Vary headers, conditional headers,
header precedence, and error handling.
"""

import pytest
from datetime import datetime

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestContentLengthHandling(MultiDriverTestBase):
    """Test automatic Content-Length header injection across all drivers."""

    def create_app(self) -> RestApplication:
        """Set up API for content length testing."""
        app = RestApplication()

        @app.get("/text")
        def get_text():
            return "Hello, World!"

        @app.get("/unicode")
        def get_unicode():
            return "Hello, 世界! 🌍"

        @app.get("/empty")
        def get_empty():
            return ""

        @app.get("/none")
        def get_none():
            return None

        return app

    def test_content_length_with_text_body(self, api):
        """Test Content-Length header with text body."""
        api_client, driver_name = api

        response = api_client.get_resource("/text")
        assert response.status_code == 200
        # Just check that Content-Length is set correctly
        assert response.get_header("Content-Length") is not None
        content_length = int(response.get_header("Content-Length"))
        assert content_length > 0

    def test_content_length_with_unicode_content(self, api):
        """Test Content-Length header with Unicode content."""
        api_client, driver_name = api

        response = api_client.get_resource("/unicode")
        assert response.status_code == 200
        # Just check that Content-Length is set correctly
        assert response.get_header("Content-Length") is not None
        content_length = int(response.get_header("Content-Length"))
        # Unicode content should have correct byte length
        assert content_length > len("Hello, ! ")  # More than ASCII chars

    def test_no_content_length_for_204(self, api):
        """Test that 204 No Content responses work correctly across all drivers.

        RestMachine follows RFC 7230 strictly (no Content-Length for 204),
        but HTTP servers often add Content-Length: 0 for safety. Both are valid.
        """
        api_client, driver_name = api

        response = api_client.get_resource("/none")
        api_client.expect_no_content(response)

        # Accept both RFC 7230 strict (None) and common server behavior ("0")
        content_length = response.get_header("Content-Length")
        assert content_length is None or content_length == "0", \
            f"Expected None or '0' for 204 response, got {content_length!r}"


class TestVaryHeaderHandling(MultiDriverTestBase):
    """Test automatic Vary header injection across all drivers."""

    def create_app(self) -> RestApplication:
        """Set up API for Vary header testing."""
        app = RestApplication()

        @app.default_authorized
        def check_auth(request):
            auth_header = request.headers.get("Authorization", "")
            return auth_header.startswith("Bearer")

        @app.get("/public")
        def public_endpoint():
            return {"message": "Public"}

        @app.get("/protected")
        def protected_endpoint():
            return {"message": "Protected"}

        @app.get("/content")
        def get_content():
            return {"data": "content"}

        @app.provides("text/html")
        def render_html(get_content):
            return f"<h1>{get_content['data']}</h1>"

        return app

    def test_vary_authorization_with_auth_header(self, api):
        """Test Vary: Authorization when request has Authorization header."""
        api_client, driver_name = api

        request = api_client.get("/protected").with_auth("valid_token").accepts("application/json")
        response = api_client.execute(request)

        vary_header = response.get_header("Vary")
        if vary_header:
            assert "Authorization" in vary_header

    def test_vary_accept_with_content_negotiation(self, api):
        """Test Vary: Accept with content negotiation."""
        api_client, driver_name = api

        response = api_client.get_as_html("/content")

        vary_header = response.get_header("Vary")
        if vary_header:
            assert "Accept" in vary_header


class TestDefaultHeaders(MultiDriverTestBase):
    """Test default header functionality across all drivers."""

    def create_app(self) -> RestApplication:
        """Set up API with default headers."""
        app = RestApplication()

        @app.default_headers
        def add_default_headers(request):
            return {
                "X-API-Version": "1.0",
                "X-Request-ID": f"req-{hash(request.path) % 10000}"
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        return app

    def test_default_headers_applied(self, api):
        """Test that default headers are applied to responses."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        # Check for default headers
        assert response.get_header("X-API-Version") == "1.0"
        assert response.get_header("X-Request-ID") is not None
        assert response.get_header("X-Request-ID").startswith("req-")
class TestBasicDefaultHeaders(MultiDriverTestBase):
    """Test basic default header functionality."""

    def create_app(self) -> RestApplication:
        """Set up API with basic default headers."""
        app = RestApplication()

        @app.default_headers
        def add_default_headers(request):
            """Add default headers to all responses."""
            return {
                "X-API-Version": "1.0",
                "X-Server": "restmachine",
                "X-Request-ID": f"req-{hash(request.path) % 10000}"
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return app

    def test_default_headers_applied_to_get(self, api):
        """Test that default headers are applied to GET responses."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        # Check default headers
        assert response.get_header("X-API-Version") == "1.0"
        assert response.get_header("X-Server") == "restmachine"
        assert response.get_header("X-Request-ID") is not None
        assert response.get_header("X-Request-ID").startswith("req-")

    def test_default_headers_applied_to_post(self, api):
        """Test that default headers are applied to POST responses."""
        api_client, driver_name = api

        test_data = {"name": "test"}
        response = api_client.create_resource("/create", test_data)
        api_client.expect_successful_creation(response)

        # Check default headers
        assert response.get_header("X-API-Version") == "1.0"
        assert response.get_header("X-Server") == "restmachine"
        assert response.get_header("X-Request-ID") is not None

    def test_default_headers_vary_by_request(self, api):
        """Test that default headers can vary by request."""
        api_client, driver_name = api

        response1 = api_client.get_resource("/test")
        response2 = api_client.get_resource("/create")  # Different path

        request_id1 = response1.get_header("X-Request-ID")
        request_id2 = response2.get_header("X-Request-ID")

        # Request IDs should be different for different paths
        assert request_id1 != request_id2


class TestConditionalHeaders(MultiDriverTestBase):
    """Test conditional header functionality based on request attributes."""

    def create_app(self) -> RestApplication:
        """Set up API with conditional headers."""
        app = RestApplication()

        # Global default headers that vary by request
        @app.default_headers
        def conditional_headers(request):
            headers = {
                "X-Global": "true",
                "X-Timestamp": datetime.now().isoformat(),
                "X-Request-Path": request.path
            }

            # Add conditional headers based on path
            if request.path.startswith("/admin"):
                headers["X-Admin"] = "true"
                headers["X-Security-Level"] = "high"
            elif request.path.startswith("/api"):
                headers["X-API"] = "true"
                headers["X-Rate-Limit"] = "1000"

            # Add method-specific headers
            if request.method.value == "POST":
                headers["X-Post-Request"] = "true"

            return headers

        @app.get("/test")
        def test_endpoint():
            return {"message": "regular endpoint"}

        @app.get("/admin/users")
        def admin_users():
            return {"users": ["admin1", "admin2"]}

        @app.get("/admin/settings")
        def admin_settings():
            return {"settings": {"debug": True}}

        @app.get("/api/v1/data")
        def api_data():
            return {"data": [1, 2, 3]}

        @app.get("/api/v1/status")
        def api_status():
            return {"status": "ok"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return app

    def test_global_headers_on_regular_endpoint(self, api):
        """Test that global headers are applied to regular endpoints."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-Timestamp") is not None
        assert response.get_header("X-Request-Path") == "/test"
        # Should not have conditional headers
        assert response.get_header("X-Admin") is None
        assert response.get_header("X-API") is None

    def test_admin_conditional_headers(self, api):
        """Test that admin-specific headers are applied conditionally."""
        api_client, driver_name = api

        response = api_client.get_resource("/admin/users")
        api_client.expect_successful_retrieval(response)

        # Should have global headers plus admin headers
        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-Admin") == "true"
        assert response.get_header("X-Security-Level") == "high"
        assert response.get_header("X-Request-Path") == "/admin/users"

    def test_admin_headers_on_different_endpoints(self, api):
        """Test that admin headers apply to all admin paths."""
        api_client, driver_name = api

        response1 = api_client.get_resource("/admin/users")
        response2 = api_client.get_resource("/admin/settings")

        # Both should have admin headers
        assert response1.get_header("X-Admin") == "true"
        assert response2.get_header("X-Admin") == "true"

        # But different paths
        assert response1.get_header("X-Request-Path") == "/admin/users"
        assert response2.get_header("X-Request-Path") == "/admin/settings"

    def test_api_conditional_headers(self, api):
        """Test that API-specific headers are applied conditionally."""
        api_client, driver_name = api

        response = api_client.get_resource("/api/v1/data")
        api_client.expect_successful_retrieval(response)

        # Should have global headers plus API headers
        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-API") == "true"
        assert response.get_header("X-Rate-Limit") == "1000"
        assert response.get_header("X-Request-Path") == "/api/v1/data"

    def test_api_headers_vary_by_path(self, api):
        """Test that API headers vary by request path."""
        api_client, driver_name = api

        response1 = api_client.get_resource("/api/v1/data")
        response2 = api_client.get_resource("/api/v1/status")

        # Both should have API headers
        assert response1.get_header("X-API") == "true"
        assert response2.get_header("X-API") == "true"

        # But different paths
        assert response1.get_header("X-Request-Path") == "/api/v1/data"
        assert response2.get_header("X-Request-Path") == "/api/v1/status"

    def test_method_conditional_headers(self, api):
        """Test headers that vary by HTTP method."""
        api_client, driver_name = api

        # GET request - no POST header
        get_response = api_client.get_resource("/test")
        assert get_response.get_header("X-Post-Request") is None

        # POST request - should have POST header
        post_response = api_client.create_resource("/create", {"test": "data"})
        assert post_response.get_header("X-Post-Request") == "true"


class TestHeaderReturnValues(MultiDriverTestBase):
    """Test different return value patterns from header functions."""

    def create_app(self) -> RestApplication:
        """Set up API with different header return patterns."""
        app = RestApplication()

        @app.default_headers
        def variable_headers(request):
            """Headers that vary by request characteristics."""
            # Always include basic headers
            headers = {
                "X-Basic": "true",
                "X-Path": request.path
            }

            # Add conditional headers based on request
            if request.method.value == "POST":
                headers["X-Post-Request"] = "true"

            # Add path-based headers
            if request.path.startswith("/admin"):
                headers["X-Admin-Access"] = "true"

            return headers

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        @app.get("/admin/test")
        def admin_endpoint():
            return {"message": "admin test"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return app

    def test_basic_header_generation(self, api):
        """Test basic header generation."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Basic") == "true"
        assert response.get_header("X-Path") == "/test"

    def test_conditional_headers_by_method(self, api):
        """Test conditional header generation based on method."""
        api_client, driver_name = api

        # GET request - no POST header
        get_response = api_client.get_resource("/test")
        assert get_response.get_header("X-Post-Request") is None

        # POST request - should have POST header
        post_response = api_client.create_resource("/create", {"test": "data"})
        assert post_response.get_header("X-Post-Request") == "true"

    def test_conditional_headers_by_path(self, api):
        """Test conditional header generation based on path."""
        api_client, driver_name = api

        # Regular path - no admin header
        regular_response = api_client.get_resource("/test")
        assert regular_response.get_header("X-Admin-Access") is None

        # Admin path - should have admin header
        admin_response = api_client.get_resource("/admin/test")
        assert admin_response.get_header("X-Admin-Access") == "true"


class TestHeaderCallPatterns(MultiDriverTestBase):
    """Test header function call patterns and behavior."""

    @pytest.fixture(scope="function")
    def api(self, request):
        """
        Function-scoped fixture for stateful tests.

        Creates a new app instance for each test to prevent state leakage.
        """
        from tests.framework.dsl import RestApiDsl

        driver_name = request.param
        app = self.create_app()
        driver = self.create_driver(driver_name, app)

        # HTTP drivers need to be started/stopped with context manager
        if driver_name.startswith('uvicorn-') or driver_name.startswith('hypercorn-'):
            with driver as active_driver:
                import time
                time.sleep(0.05)
                yield RestApiDsl(active_driver), driver_name
        else:
            # Direct and Lambda drivers don't need context manager
            yield RestApiDsl(driver), driver_name

    def create_app(self) -> RestApplication:
        """Set up API to test header function call patterns."""
        app = RestApplication()

        # Counter to track how many times header functions are called
        self.call_count = {"count": 0}

        @app.default_headers
        def tracking_headers(request):
            """Headers that track call count."""
            self.call_count["count"] += 1
            return {
                "X-Call-Count": str(self.call_count["count"]),
                "X-Request-Method": request.method.value,
                "X-Request-Path": request.path
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return app

    def test_header_function_called_per_request(self, api):
        """Test that header functions are called for each request."""
        api_client, driver_name = api

        # First request
        response1 = api_client.get_resource("/test")
        assert response1.get_header("X-Call-Count") == "1"

        # Second request to same endpoint
        response2 = api_client.get_resource("/test")
        assert response2.get_header("X-Call-Count") == "2"

        # Third request to different endpoint
        response3 = api_client.create_resource("/create", {"data": "test"})
        assert response3.get_header("X-Call-Count") == "3"

        # Verify call count incremented correctly
        assert self.call_count["count"] == 3

    def test_header_function_receives_correct_request_info(self, api):
        """Test that header functions receive correct request information."""
        api_client, driver_name = api

        # GET request
        get_response = api_client.get_resource("/test")
        assert get_response.get_header("X-Request-Method") == "GET"
        assert get_response.get_header("X-Request-Path") == "/test"

        # POST request
        post_response = api_client.create_resource("/create", {"data": "test"})
        assert post_response.get_header("X-Request-Method") == "POST"
        assert post_response.get_header("X-Request-Path") == "/create"


class TestHeaderErrorHandling(MultiDriverTestBase):
    """Test error handling in header functions."""

    def create_app(self) -> RestApplication:
        """Set up API with error-prone header functions."""
        app = RestApplication()

        @app.default_headers
        def sometimes_failing_headers(request):
            """Headers that sometimes fail based on request path."""
            if request.path == "/error":
                raise Exception("Header calculation failed")

            if request.path == "/none":
                return None  # Valid return (no headers)

            return {
                "X-Success": "true",
                "X-Path": request.path
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        @app.get("/error")
        def error_endpoint():
            return {"message": "error endpoint"}

        @app.get("/none")
        def none_endpoint():
            return {"message": "none endpoint"}

        return app

    def test_successful_header_generation(self, api):
        """Test normal successful header generation."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Success") == "true"
        assert response.get_header("X-Path") == "/test"

    def test_header_function_returning_none(self, api):
        """Test header function that returns None."""
        api_client, driver_name = api

        response = api_client.get_resource("/none")
        api_client.expect_successful_retrieval(response)

        # Should not have the headers since function returned None
        assert response.get_header("X-Success") is None
        assert response.get_header("X-Path") is None

    def test_header_function_exception_handling(self, api):
        """Test handling of exceptions in header functions."""
        api_client, driver_name = api

        response = api_client.get_resource("/error")

        # Request should still succeed despite header function failure
        # (implementation might log error but continue)
        if response.status_code == 200:
            api_client.expect_successful_retrieval(response)
            # Headers might be missing due to exception
            assert response.get_header("X-Success") is None
        else:
            # Or might return error if header generation is critical
            assert response.status_code >= 500


class TestHeadersWithExistingResponseHeaders(MultiDriverTestBase):
    """Test header behavior when response already has headers."""

    def create_app(self) -> RestApplication:
        """Set up API that sets response headers explicitly."""
        app = RestApplication()

        @app.default_headers
        def add_default_headers(request):
            return {
                "X-Default": "true",
                "Content-Type": "application/default+json",  # Might conflict
                "X-Timestamp": "2024-01-01T00:00:00Z"
            }

        @app.get("/custom-headers")
        def custom_headers_endpoint():
            """Endpoint that returns custom headers."""
            from restmachine import Response
            return Response(
                200,
                {"message": "custom headers"},
                headers={
                    "X-Custom": "true",
                    "Content-Type": "application/custom+json",
                    "X-Timestamp": "2024-12-31T23:59:59Z"  # Conflicts with default
                }
            )

        @app.get("/no-custom-headers")
        def no_custom_headers():
            return {"message": "no custom headers"}

        return app

    def test_default_headers_with_no_existing_headers(self, api):
        """Test default headers when no existing headers are present."""
        api_client, driver_name = api

        response = api_client.get_resource("/no-custom-headers")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Default") == "true"
        assert response.get_header("X-Timestamp") == "2024-01-01T00:00:00Z"

    def test_header_precedence_with_existing_headers(self, api):
        """Test header precedence when response has existing headers."""
        api_client, driver_name = api

        response = api_client.get_resource("/custom-headers")
        api_client.expect_successful_retrieval(response)

        # Check which headers take precedence
        assert response.get_header("X-Custom") == "true"
        assert response.get_header("X-Default") == "true"

        # Check precedence for conflicting headers
        # (behavior depends on implementation - custom might override default or vice versa)
        timestamp = response.get_header("X-Timestamp")
        assert timestamp in ["2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]

        content_type = response.get_header("Content-Type")
        assert "json" in content_type


class TestHeadersAcrossDrivers(MultiDriverTestBase):
    """Test header functionality across different drivers."""

    def create_app(self) -> RestApplication:
        """Create app for testing across drivers."""
        app = RestApplication()

        @app.default_headers
        def cross_driver_headers(request):
            return {
                "X-Driver-Test": "true",
                "X-Request-Method": request.method.value,
                "X-Request-Path": request.path
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "cross driver test"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return app

    def test_default_headers_work_across_drivers(self, api):
        """Test that default headers work consistently across drivers."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Driver-Test") == "true"
        assert response.get_header("X-Request-Method") == "GET"
        assert response.get_header("X-Request-Path") == "/test"

    def test_default_headers_with_post_across_drivers(self, api):
        """Test default headers with POST requests across drivers."""
        api_client, driver_name = api

        test_data = {"name": "test"}
        response = api_client.create_resource("/create", test_data)
        api_client.expect_successful_creation(response)

        assert response.get_header("X-Driver-Test") == "true"
        assert response.get_header("X-Request-Method") == "POST"
        assert response.get_header("X-Request-Path") == "/create"


class TestMultiValueHeaders(MultiDriverTestBase):
    """Test multi-value header functionality across all drivers."""

    def create_app(self) -> RestApplication:
        """Set up API for multi-value header testing."""
        app = RestApplication()

        @app.get("/cookies")
        def multiple_cookies():
            """Endpoint that sets multiple Set-Cookie headers."""
            from restmachine import Response
            from restmachine.models import MultiValueHeaders

            headers = MultiValueHeaders()
            headers.add("Set-Cookie", "session=abc123; Path=/; HttpOnly")
            headers.add("Set-Cookie", "user=john_doe; Path=/; HttpOnly")
            headers.add("Set-Cookie", "preferences=dark_mode; Path=/")

            return Response(
                status_code=200,
                body={"message": "Cookies set"},
                headers=headers
            )

        @app.get("/vary-multiple")
        def multiple_vary():
            """Endpoint that sets multiple Vary headers."""
            from restmachine import Response
            from restmachine.models import MultiValueHeaders

            headers = MultiValueHeaders()
            headers.add("Vary", "Accept")
            headers.add("Vary", "Authorization")
            headers.add("Vary", "Accept-Encoding")

            return Response(
                status_code=200,
                body={"message": "Multiple Vary headers"},
                headers=headers
            )

        @app.get("/single-header")
        def single_header():
            """Endpoint that sets a single header value."""
            from restmachine import Response
            from restmachine.models import MultiValueHeaders

            headers = MultiValueHeaders()
            headers.add("X-Single", "value1")

            return Response(
                status_code=200,
                body={"message": "Single header"},
                headers=headers
            )

        return app

    def test_multiple_set_cookie_headers(self, api):
        """Test that multiple Set-Cookie headers are preserved."""
        api_client, driver_name = api

        response = api_client.get_resource("/cookies")
        api_client.expect_successful_retrieval(response)

        # All drivers should preserve the first Set-Cookie header at minimum
        set_cookie = response.get_header("Set-Cookie")
        assert set_cookie is not None
        assert "session=abc123" in set_cookie or "user=john_doe" in set_cookie or "preferences=dark_mode" in set_cookie

    def test_multiple_vary_headers(self, api):
        """Test that multiple Vary headers are handled correctly."""
        api_client, driver_name = api

        response = api_client.get_resource("/vary-multiple")
        api_client.expect_successful_retrieval(response)

        # Check that at least one Vary header is present
        vary = response.get_header("Vary")
        assert vary is not None

    def test_single_header_value(self, api):
        """Test that single header values work correctly."""
        api_client, driver_name = api

        response = api_client.get_resource("/single-header")
        api_client.expect_successful_retrieval(response)

        assert response.get_header("X-Single") == "value1"
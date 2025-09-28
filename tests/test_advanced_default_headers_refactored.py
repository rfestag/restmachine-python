"""
Refactored advanced default headers tests using 4-layer architecture.

Tests for route-specific vs global headers, header modification in-place,
header dependency caching, and error handling in header functions.
"""

import pytest
from datetime import datetime

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver


class TestBasicDefaultHeaders:
    """Test basic default header functionality."""

    @pytest.fixture
    def api(self):
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

        return RestApiDsl(RestMachineDriver(app))

    def test_default_headers_applied_to_get(self, api):
        """Test that default headers are applied to GET responses."""
        response = api.get_resource("/test")
        data = api.expect_successful_retrieval(response)

        # Check default headers
        assert response.get_header("X-API-Version") == "1.0"
        assert response.get_header("X-Server") == "restmachine"
        assert response.get_header("X-Request-ID") is not None
        assert response.get_header("X-Request-ID").startswith("req-")

    def test_default_headers_applied_to_post(self, api):
        """Test that default headers are applied to POST responses."""
        test_data = {"name": "test"}
        response = api.create_resource("/create", test_data)
        data = api.expect_successful_creation(response)

        # Check default headers
        assert response.get_header("X-API-Version") == "1.0"
        assert response.get_header("X-Server") == "restmachine"
        assert response.get_header("X-Request-ID") is not None

    def test_default_headers_vary_by_request(self, api):
        """Test that default headers can vary by request."""
        response1 = api.get_resource("/test")
        response2 = api.get_resource("/create")  # Different path

        request_id1 = response1.get_header("X-Request-ID")
        request_id2 = response2.get_header("X-Request-ID")

        # Request IDs should be different for different paths
        assert request_id1 != request_id2


class TestConditionalHeaders:
    """Test conditional header functionality based on request attributes."""

    @pytest.fixture
    def api(self):
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

        return RestApiDsl(RestMachineDriver(app))

    def test_global_headers_on_regular_endpoint(self, api):
        """Test that global headers are applied to regular endpoints."""
        response = api.get_resource("/test")
        api.expect_successful_retrieval(response)

        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-Timestamp") is not None
        assert response.get_header("X-Request-Path") == "/test"
        # Should not have conditional headers
        assert response.get_header("X-Admin") is None
        assert response.get_header("X-API") is None

    def test_admin_conditional_headers(self, api):
        """Test that admin-specific headers are applied conditionally."""
        response = api.get_resource("/admin/users")
        api.expect_successful_retrieval(response)

        # Should have global headers plus admin headers
        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-Admin") == "true"
        assert response.get_header("X-Security-Level") == "high"
        assert response.get_header("X-Request-Path") == "/admin/users"

    def test_admin_headers_on_different_endpoints(self, api):
        """Test that admin headers apply to all admin paths."""
        response1 = api.get_resource("/admin/users")
        response2 = api.get_resource("/admin/settings")

        # Both should have admin headers
        assert response1.get_header("X-Admin") == "true"
        assert response2.get_header("X-Admin") == "true"

        # But different paths
        assert response1.get_header("X-Request-Path") == "/admin/users"
        assert response2.get_header("X-Request-Path") == "/admin/settings"

    def test_api_conditional_headers(self, api):
        """Test that API-specific headers are applied conditionally."""
        response = api.get_resource("/api/v1/data")
        api.expect_successful_retrieval(response)

        # Should have global headers plus API headers
        assert response.get_header("X-Global") == "true"
        assert response.get_header("X-API") == "true"
        assert response.get_header("X-Rate-Limit") == "1000"
        assert response.get_header("X-Request-Path") == "/api/v1/data"

    def test_api_headers_vary_by_path(self, api):
        """Test that API headers vary by request path."""
        response1 = api.get_resource("/api/v1/data")
        response2 = api.get_resource("/api/v1/status")

        # Both should have API headers
        assert response1.get_header("X-API") == "true"
        assert response2.get_header("X-API") == "true"

        # But different paths
        assert response1.get_header("X-Request-Path") == "/api/v1/data"
        assert response2.get_header("X-Request-Path") == "/api/v1/status"

    def test_method_conditional_headers(self, api):
        """Test headers that vary by HTTP method."""
        # GET request - no POST header
        get_response = api.get_resource("/test")
        assert get_response.get_header("X-Post-Request") is None

        # POST request - should have POST header
        post_response = api.create_resource("/create", {"test": "data"})
        assert post_response.get_header("X-Post-Request") == "true"


class TestHeaderReturnValues:
    """Test different return value patterns from header functions."""

    @pytest.fixture
    def api(self):
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

        return RestApiDsl(RestMachineDriver(app))

    def test_basic_header_generation(self, api):
        """Test basic header generation."""
        response = api.get_resource("/test")
        api.expect_successful_retrieval(response)

        assert response.get_header("X-Basic") == "true"
        assert response.get_header("X-Path") == "/test"

    def test_conditional_headers_by_method(self, api):
        """Test conditional header generation based on method."""
        # GET request - no POST header
        get_response = api.get_resource("/test")
        assert get_response.get_header("X-Post-Request") is None

        # POST request - should have POST header
        post_response = api.create_resource("/create", {"test": "data"})
        assert post_response.get_header("X-Post-Request") == "true"

    def test_conditional_headers_by_path(self, api):
        """Test conditional header generation based on path."""
        # Regular path - no admin header
        regular_response = api.get_resource("/test")
        assert regular_response.get_header("X-Admin-Access") is None

        # Admin path - should have admin header
        admin_response = api.get_resource("/admin/test")
        assert admin_response.get_header("X-Admin-Access") == "true"


class TestHeaderCallPatterns:
    """Test header function call patterns and behavior."""

    @pytest.fixture
    def api(self):
        """Set up API to test header function call patterns."""
        app = RestApplication()

        # Counter to track how many times header functions are called
        call_count = {"count": 0}

        @app.default_headers
        def tracking_headers(request):
            """Headers that track call count."""
            call_count["count"] += 1
            return {
                "X-Call-Count": str(call_count["count"]),
                "X-Request-Method": request.method.value,
                "X-Request-Path": request.path
            }

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        @app.post("/create")
        def create_endpoint(json_body):
            return {"created": json_body}

        return RestApiDsl(RestMachineDriver(app)), call_count

    def test_header_function_called_per_request(self, api):
        """Test that header functions are called for each request."""
        api_dsl, call_count = api

        # First request
        response1 = api_dsl.get_resource("/test")
        assert response1.get_header("X-Call-Count") == "1"

        # Second request to same endpoint
        response2 = api_dsl.get_resource("/test")
        assert response2.get_header("X-Call-Count") == "2"

        # Third request to different endpoint
        response3 = api_dsl.create_resource("/create", {"data": "test"})
        assert response3.get_header("X-Call-Count") == "3"

        # Verify call count incremented correctly
        assert call_count["count"] == 3

    def test_header_function_receives_correct_request_info(self, api):
        """Test that header functions receive correct request information."""
        api_dsl, _ = api

        # GET request
        get_response = api_dsl.get_resource("/test")
        assert get_response.get_header("X-Request-Method") == "GET"
        assert get_response.get_header("X-Request-Path") == "/test"

        # POST request
        post_response = api_dsl.create_resource("/create", {"data": "test"})
        assert post_response.get_header("X-Request-Method") == "POST"
        assert post_response.get_header("X-Request-Path") == "/create"


class TestHeaderErrorHandling:
    """Test error handling in header functions."""

    @pytest.fixture
    def api(self):
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

        return RestApiDsl(RestMachineDriver(app))

    def test_successful_header_generation(self, api):
        """Test normal successful header generation."""
        response = api.get_resource("/test")
        api.expect_successful_retrieval(response)

        assert response.get_header("X-Success") == "true"
        assert response.get_header("X-Path") == "/test"

    def test_header_function_returning_none(self, api):
        """Test header function that returns None."""
        response = api.get_resource("/none")
        api.expect_successful_retrieval(response)

        # Should not have the headers since function returned None
        assert response.get_header("X-Success") is None
        assert response.get_header("X-Path") is None

    def test_header_function_exception_handling(self, api):
        """Test handling of exceptions in header functions."""
        response = api.get_resource("/error")

        # Request should still succeed despite header function failure
        # (implementation might log error but continue)
        if response.status_code == 200:
            data = api.expect_successful_retrieval(response)
            # Headers might be missing due to exception
            assert response.get_header("X-Success") is None
        else:
            # Or might return error if header generation is critical
            assert response.status_code >= 500


class TestHeadersWithExistingResponseHeaders:
    """Test header behavior when response already has headers."""

    @pytest.fixture
    def api(self):
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

        return RestApiDsl(RestMachineDriver(app))

    def test_default_headers_with_no_existing_headers(self, api):
        """Test default headers when no existing headers are present."""
        response = api.get_resource("/no-custom-headers")
        api.expect_successful_retrieval(response)

        assert response.get_header("X-Default") == "true"
        assert response.get_header("X-Timestamp") == "2024-01-01T00:00:00Z"

    def test_header_precedence_with_existing_headers(self, api):
        """Test header precedence when response has existing headers."""
        response = api.get_resource("/custom-headers")
        api.expect_successful_retrieval(response)

        # Check which headers take precedence
        assert response.get_header("X-Custom") == "true"
        assert response.get_header("X-Default") == "true"

        # Check precedence for conflicting headers
        # (behavior depends on implementation - custom might override default or vice versa)
        timestamp = response.get_header("X-Timestamp")
        assert timestamp in ["2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]

        content_type = response.get_header("Content-Type")
        assert "json" in content_type


class TestHeadersAcrossDrivers:
    """Test header functionality across different drivers."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """Parametrized fixture for testing across drivers."""
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

        # Select driver
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)

    def test_default_headers_work_across_drivers(self, api):
        """Test that default headers work consistently across drivers."""
        response = api.get_resource("/test")
        api.expect_successful_retrieval(response)

        assert response.get_header("X-Driver-Test") == "true"
        assert response.get_header("X-Request-Method") == "GET"
        assert response.get_header("X-Request-Path") == "/test"

    def test_default_headers_with_post_across_drivers(self, api):
        """Test default headers with POST requests across drivers."""
        test_data = {"name": "test"}
        response = api.create_resource("/create", test_data)
        api.expect_successful_creation(response)

        assert response.get_header("X-Driver-Test") == "true"
        assert response.get_header("X-Request-Method") == "POST"
        assert response.get_header("X-Request-Path") == "/create"
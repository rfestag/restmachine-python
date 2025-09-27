"""
Refactored HTTP status code tests using 4-layer architecture.

Tests all HTTP status codes that can be returned by the framework.
"""

import pytest

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver


class TestBadRequestErrors:
    """Test 400 Bad Request scenarios."""

    def test_400_bad_request_malformed(self):
        """Test 400 Bad Request from malformed request."""
        app = RestApplication()

        @app.default_malformed_request
        def malformed_request():
            return True  # Always malformed

        @app.get("/test")
        def handler():
            return {"message": "Should not reach here"}

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/test")
        assert response.status_code == 400
        assert "Bad Request" in response.get_text_body()

    def test_400_bad_request_invalid_headers(self):
        """Test 400 Bad Request from invalid headers."""
        app = RestApplication()

        @app.default_content_headers_valid
        def content_headers_valid():
            return False  # Always invalid

        @app.get("/test")
        def handler():
            return {"message": "Should not reach here"}

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/test")
        assert response.status_code == 400
        assert "Bad Request" in response.get_text_body()


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization scenarios."""

    @pytest.fixture
    def api(self):
        """Set up API with auth scenarios."""
        app = RestApplication()

        @app.default_authorized
        def authorized(request):
            auth_header = request.headers.get("Authorization", "")
            if request.path == "/public":
                return True
            return auth_header.startswith("Bearer valid")

        @app.default_forbidden
        def forbidden(request):
            auth_header = request.headers.get("Authorization", "")
            if request.path == "/admin" and "admin" not in auth_header:
                return True
            return False

        @app.forbidden
        def permission_check(request):
            if request.path == "/forbidden-dependency":
                return None
            return True

        @app.get("/public")
        def public_endpoint():
            return {"message": "Public content"}

        @app.get("/protected")
        def protected_endpoint():
            return {"message": "Protected content"}

        @app.get("/admin")
        def admin_endpoint():
            return {"message": "Admin content"}

        @app.get("/forbidden-dependency")
        def forbidden_handler(permission_check):
            return {"message": "Should not reach here"}

        return RestApiDsl(RestMachineDriver(app))

    def test_401_unauthorized(self, api):
        """Test 401 Unauthorized from authorization failure."""
        response = api.access_protected_resource("/protected")
        api.expect_unauthorized(response)

    def test_403_forbidden_callback(self, api):
        """Test 403 Forbidden from forbidden callback."""
        # Use valid auth to pass authorization, but forbidden callback will trigger
        request = api.get("/admin").with_auth("valid_user_token").accepts("application/json")
        response = api.execute(request)
        assert response.status_code == 403
        assert "Forbidden" in response.get_text_body()

    def test_403_forbidden_dependency(self, api):
        """Test 403 Forbidden from forbidden dependency returning None."""
        # Use valid auth to pass authorization check first
        request = api.get("/forbidden-dependency").with_auth("valid_user").accepts("application/json")
        response = api.execute(request)
        assert response.status_code == 403
        assert "Forbidden" in response.get_text_body()


class TestMethodAndResourceErrors:
    """Test method and resource-related errors."""

    def test_405_method_not_allowed(self):
        """Test 405 Method Not Allowed."""
        app = RestApplication()

        @app.default_method_allowed
        def method_allowed():
            return False  # Method not allowed

        @app.get("/test")
        def handler():
            return {"message": "Should not reach here"}

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/test")
        assert response.status_code == 405
        assert "Method Not Allowed" in response.get_text_body()

    def test_406_not_acceptable(self):
        """Test 406 Not Acceptable when content negotiation fails."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello"}

        api = RestApiDsl(RestMachineDriver(app))
        request = api.get("/data").accepts("application/xml")
        response = api.execute(request)
        assert response.status_code == 406
        assert "Not Acceptable" in response.get_text_body()

    def test_414_uri_too_long(self):
        """Test 414 URI Too Long."""
        app = RestApplication()

        @app.default_uri_too_long
        def uri_too_long():
            return True  # URI is too long

        @app.get("/test")
        def handler():
            return {"message": "Should not reach here"}

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/test")
        assert response.status_code == 414
        assert "URI Too Long" in response.get_text_body()

    def test_404_resource_not_found_dependency(self):
        """Test 404 when resource_exists dependency returns None."""
        app = RestApplication()

        @app.resource_exists
        def check_resource_exists():
            return None  # Resource doesn't exist

        @app.get("/resource/{id}")
        def get_resource(check_resource_exists):
            return check_resource_exists

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/resource/1")
        api.expect_not_found(response)


class TestServerErrors:
    """Test server error scenarios."""

    def test_500_internal_server_error(self):
        """Test 500 Internal Server Error from unhandled exception."""
        app = RestApplication()

        @app.get("/error")
        def error_endpoint():
            raise Exception("Something went wrong")

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/error")
        assert response.is_server_error()
        assert response.status_code == 500

    def test_501_not_implemented(self):
        """Test 501 Not Implemented from known_method callback."""
        app = RestApplication()

        @app.default_known_method
        def known_method():
            return False  # Method not implemented

        @app.get("/test")
        def handler():
            return {"message": "Should not reach here"}

        api = RestApiDsl(RestMachineDriver(app))
        response = api.get_resource("/test")
        assert response.status_code == 501
        assert "Not Implemented" in response.get_text_body()


class TestSuccessStatusCodes:
    """Test success status codes."""

    @pytest.fixture
    def api(self):
        """Set up API for success scenarios."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello"}

        @app.get("/no-content")
        def no_content_handler():
            return None

        return RestApiDsl(RestMachineDriver(app))

    def test_200_ok_with_content(self, api):
        """Test 200 OK with response content."""
        response = api.get_resource("/data")
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Hello"
        assert response.status_code == 200

    def test_204_no_content(self, api):
        """Test 204 No Content when handler returns None."""
        response = api.get_resource("/no-content")
        api.expect_no_content(response)
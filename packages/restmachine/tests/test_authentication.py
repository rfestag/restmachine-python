"""
Authentication and authorization tests across all drivers.

Tests for authentication workflows, protected endpoints, authorization checks,
and forbidden resource handling.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestAuthentication(MultiDriverTestBase):
    """Test authentication and authorization across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with authentication."""
        app = RestApplication()

        # Simple session store for testing
        sessions = {"valid_token": {"user_id": "123", "role": "admin"}}

        @app.default_authorized
        def check_auth(request):
            # Only protect non-public endpoints
            if request.path == "/public":
                return True  # Public endpoint, always authorized
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return False
            token = auth_header[7:]
            return token in sessions

        @app.default_forbidden
        def check_permissions(request):
            # Admin endpoints require admin role
            if request.path.startswith("/admin"):
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    session = sessions.get(token, {})
                    return session.get("role") != "admin"
            return False

        @app.get("/public")
        def public_endpoint():
            return {"message": "Public content"}

        @app.get("/protected")
        def protected_endpoint():
            return {"message": "Protected content"}

        @app.get("/admin/stats")
        def admin_endpoint():
            return {"stats": "Admin only stats"}

        return app

    def test_public_endpoint_accessible_without_auth(self, api):
        """Test that public endpoints are accessible without authentication."""
        api_client, driver_name = api

        response = api_client.get_resource("/public")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Public content"

    def test_protected_endpoint_requires_auth(self, api):
        """Test that protected endpoints require authentication.

        RFC 9110 Section 15.5.2: 401 Unauthorized indicates request lacks valid
        authentication credentials for target resource.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.2
        """
        api_client, driver_name = api

        response = api_client.access_protected_resource("/protected")
        api_client.expect_unauthorized(response)

    def test_protected_endpoint_accessible_with_auth(self, api):
        """Test that protected endpoints are accessible with valid auth."""
        api_client, driver_name = api

        request = api_client.get("/protected").with_auth("valid_token").accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Protected content"

    def test_admin_endpoint_forbidden_for_non_admin(self, api):
        """Test that admin endpoints are forbidden for non-admin users."""
        api_client, driver_name = api

        response = api_client.access_forbidden_resource("/admin/stats", "user_token")
        # Will be unauthorized since user_token doesn't exist in sessions
        api_client.expect_unauthorized(response)

    def test_admin_endpoint_accessible_for_admin(self, api):
        """Test that admin endpoints are accessible for admin users."""
        api_client, driver_name = api

        request = api_client.get("/admin/stats").with_auth("valid_token").accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_retrieval(response)
        assert data["stats"] == "Admin only stats"


class TestAuthenticationAndAuthorization(MultiDriverTestBase):
    """Test authentication and authorization scenarios with 401 and 403 status codes."""

    def create_app(self) -> RestApplication:
        """Create app with auth scenarios."""
        app = RestApplication()

        @app.default_authorized
        def authorized(request):
            auth_header = request.get_authorization_header() or ""
            if request.path == "/public":
                return True
            return auth_header.startswith("Bearer valid")

        @app.default_forbidden
        def forbidden(request):
            auth_header = request.get_authorization_header() or ""
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

        return app

    def test_401_unauthorized(self, api):
        """Test 401 Unauthorized from authorization failure.

        RFC 9110 Section 15.5.2: Server generating 401 MUST send WWW-Authenticate
        header containing challenge for requested resource.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.2
        """
        api_client, driver_name = api

        response = api_client.access_protected_resource("/protected")
        api_client.expect_unauthorized(response)

    def test_403_forbidden_callback(self, api):
        """Test 403 Forbidden from forbidden callback.

        RFC 9110 Section 15.5.4: 403 Forbidden indicates server understood request but
        refuses to fulfill it. Unlike 401, authentication won't help.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.4
        """
        api_client, driver_name = api

        # Use valid auth to pass authorization, but forbidden callback will trigger
        request = api_client.get("/admin").with_auth("valid_user_token").accepts("application/json")
        response = api_client.execute(request)
        assert response.status_code == 403
        assert "Forbidden" in response.get_text_body()

    def test_403_forbidden_dependency(self, api):
        """Test 403 Forbidden from forbidden dependency returning None.

        RFC 9110 Section 15.5.4: 403 Forbidden appropriate when user authenticated
        but lacks necessary permissions for resource.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.4
        """
        api_client, driver_name = api

        # Use valid auth to pass authorization check first
        request = api_client.get("/forbidden-dependency").with_auth("valid_user").accepts("application/json")
        response = api_client.execute(request)
        assert response.status_code == 403
        assert "Forbidden" in response.get_text_body()

    def test_public_endpoint_access(self, api):
        """Test that public endpoint is accessible without auth."""
        api_client, driver_name = api

        response = api_client.get_resource("/public")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Public content"
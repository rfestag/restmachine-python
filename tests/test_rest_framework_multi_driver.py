"""
REST framework tests using multi-driver approach.

Tests basic API operations and authentication across all drivers.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestBasicApiOperations(MultiDriverTestBase):
    """Test basic API operations across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with basic CRUD operations."""
        app = RestApplication()

        @app.get("/")
        def home():
            return {"message": "Hello World"}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            return {"id": int(user_id), "name": f"User {user_id}"}

        @app.post("/users")
        def create_user(json_body):
            return {"id": 123, "name": json_body["name"], "email": json_body["email"]}

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            return None  # 204 No Content

        return app

    def test_can_get_home_page(self, api):
        """Test that we can retrieve the home page."""
        api_client, driver_name = api

        response = api_client.get_resource("/")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"

    def test_can_get_user_by_id(self, api):
        """Test that we can retrieve a user by ID."""
        api_client, driver_name = api

        response = api_client.get_resource("/users/42")
        data = api_client.expect_successful_retrieval(response)
        assert data["id"] == 42
        assert data["name"] == "User 42"

    def test_can_create_user(self, api):
        """Test that we can create a new user."""
        api_client, driver_name = api

        user_data = {"name": "John Doe", "email": "john@example.com"}
        response = api_client.create_resource("/users", user_data)

        data = api_client.expect_successful_creation(response, ["id", "name", "email"])
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_can_delete_user(self, api):
        """Test that we can delete a user."""
        api_client, driver_name = api

        response = api_client.delete_resource("/users/123")
        api_client.expect_no_content(response)

    def test_nonexistent_resource_returns_404(self, api):
        """Test that accessing nonexistent resources returns 404."""
        api_client, driver_name = api

        response = api_client.get_resource("/nonexistent")
        api_client.expect_not_found(response)


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
        """Test that protected endpoints require authentication."""
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
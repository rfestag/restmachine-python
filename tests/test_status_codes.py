"""
HTTP status code tests across all drivers.

Tests various HTTP status codes including success (200, 201, 204),
client errors (400, 404, 405, 406, 414), and server errors (500, 501).
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestSuccessStatusCodes(MultiDriverTestBase):
    """Test success status codes across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app for success scenarios."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello"}

        @app.get("/no-content")
        def no_content_handler():
            return None

        @app.post("/create")
        def create_resource(json_body):
            return {"id": 1, **json_body}

        return app

    def test_200_ok_with_content(self, api):
        """Test 200 OK with response content."""
        api_client, driver_name = api

        response = api_client.get_resource("/data")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello"
        assert response.status_code == 200

    def test_204_no_content(self, api):
        """Test 204 No Content when handler returns None."""
        api_client, driver_name = api

        response = api_client.get_resource("/no-content")
        api_client.expect_no_content(response)

    def test_201_created(self, api):
        """Test 201 Created from POST request."""
        api_client, driver_name = api

        create_data = {"name": "test", "type": "example"}
        response = api_client.create_resource("/create", create_data)
        data = api_client.expect_successful_creation(response, ["id", "name", "type"])
        assert data["name"] == "test"
        assert data["type"] == "example"
        assert "id" in data


class TestBasicApiOperations(MultiDriverTestBase):
    """Test basic API operations and additional success scenarios."""

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


class TestBadRequestErrors(MultiDriverTestBase):
    """Test 400 Bad Request scenarios across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with bad request scenarios."""
        app = RestApplication()

        @app.get("/malformed")
        def malformed_endpoint():
            return {"message": "Should not reach here"}

        @app.default_malformed_request
        def malformed_request():
            return True  # Always malformed

        @app.get("/invalid-headers")
        def invalid_headers_endpoint():
            return {"message": "Should not reach here"}

        @app.default_content_headers_valid
        def content_headers_valid():
            return False  # Always invalid

        return app

    def test_400_bad_request_malformed(self, api):
        """Test 400 Bad Request from malformed request."""
        api_client, driver_name = api

        response = api_client.get_resource("/malformed")
        assert response.status_code == 400
        assert "Bad Request" in response.get_text_body()

    def test_400_bad_request_invalid_headers(self, api):
        """Test 400 Bad Request from invalid headers."""
        api_client, driver_name = api

        response = api_client.get_resource("/invalid-headers")
        assert response.status_code == 400
        assert "Bad Request" in response.get_text_body()


class TestResourceExists(MultiDriverTestBase):
    """Test 404 resource not found scenarios."""

    def create_app(self) -> RestApplication:
        """Create app with resource existence checking."""
        app = RestApplication()

        @app.resource_exists
        def check_resource_exists():
            return None  # Resource doesn't exist

        @app.get("/resource/{id}")
        def get_resource(check_resource_exists):
            return check_resource_exists

        return app

    def test_404_resource_not_found_dependency(self, api):
        """Test 404 when resource_exists dependency returns None."""
        api_client, driver_name = api

        response = api_client.get_resource("/resource/1")
        api_client.expect_not_found(response)


class TestResourceExistsConditional(MultiDriverTestBase):
    """Test conditional resource existence checking."""

    def create_app(self) -> RestApplication:
        """Create app with conditional resource existence checking."""
        app = RestApplication()

        @app.resource_exists
        def check_resource_exists(request):
            # Resource doesn't exist for specific path
            if "/nonexistent" in request.path:
                return None
            return True

        @app.get("/resource/{id}")
        def get_resource(check_resource_exists):
            return {"id": "exists", "resource": check_resource_exists}

        return app

    def test_404_resource_not_found_conditional(self, api):
        """Test 404 when resource_exists dependency conditionally returns None."""
        api_client, driver_name = api

        response = api_client.get_resource("/resource/nonexistent")
        api_client.expect_not_found(response)

    def test_200_resource_found(self, api):
        """Test 200 when resource exists."""
        api_client, driver_name = api

        response = api_client.get_resource("/resource/1")
        data = api_client.expect_successful_retrieval(response)
        assert data["id"] == "exists"


class TestMethodNotAllowed(MultiDriverTestBase):
    """Test 405 Method Not Allowed scenarios."""

    def create_app(self) -> RestApplication:
        """Create app that always returns method not allowed."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"message": "Should not reach here"}

        @app.default_method_allowed
        def method_allowed():
            return False  # Method not allowed

        return app

    def test_405_method_not_allowed(self, api):
        """Test 405 Method Not Allowed."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        assert response.status_code == 405
        assert "Method Not Allowed" in response.get_text_body()


class TestMethodAndResourceErrors(MultiDriverTestBase):
    """Test method and resource-related errors across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with method and resource error scenarios."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello"}

        return app

    def test_406_not_acceptable(self, api):
        """Test 406 Not Acceptable when content negotiation fails."""
        api_client, driver_name = api

        request = api_client.get("/data").accepts("application/xml")
        response = api_client.execute(request)
        assert response.status_code == 406
        assert "Not Acceptable" in response.get_text_body()


class TestUriTooLong(MultiDriverTestBase):
    """Test 414 URI Too Long scenarios."""

    def create_app(self) -> RestApplication:
        """Create app that always returns URI too long."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"message": "Should not reach here"}

        @app.default_uri_too_long
        def uri_too_long():
            return True  # URI is too long

        return app

    def test_414_uri_too_long(self, api):
        """Test 414 URI Too Long."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        assert response.status_code == 414
        assert "URI Too Long" in response.get_text_body()


class TestServerErrors(MultiDriverTestBase):
    """Test server error scenarios across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with server error scenarios."""
        app = RestApplication()

        @app.get("/error")
        def error_endpoint():
            raise Exception("Something went wrong")

        return app

    def test_500_internal_server_error(self, api):
        """Test 500 Internal Server Error from unhandled exception."""
        api_client, driver_name = api

        response = api_client.get_resource("/error")
        assert response.is_server_error()
        assert response.status_code == 500


class TestNotImplemented(MultiDriverTestBase):
    """Test 501 Not Implemented scenarios."""

    def create_app(self) -> RestApplication:
        """Create app that always returns not implemented."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"message": "Should not reach here"}

        @app.default_known_method
        def known_method():
            return False  # Method not implemented

        return app

    def test_501_not_implemented(self, api):
        """Test 501 Not Implemented from known_method callback."""
        api_client, driver_name = api

        response = api_client.get_resource("/test")
        assert response.status_code == 501
        assert "Not Implemented" in response.get_text_body()
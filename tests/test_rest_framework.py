"""
Tests for the REST framework.
"""

import json

import pytest

from restmachine import (
    HTTPMethod,
    Request,
    Response,
    RestApplication,
)

# Import Pydantic if available for validation tests
try:
    from pydantic import BaseModel, Field, ValidationError

    PYDANTIC_AVAILABLE = True

    class UserModel(BaseModel):
        name: str = Field(..., min_length=1)
        email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
        age: int = Field(..., ge=0, le=150)

    class UserResponse(BaseModel):
        id: int
        name: str
        email: str

except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    ValidationError = Exception


class TestBasicFunctionality:
    """Test basic application functionality."""

    def test_application_creation(self):
        """Test that application can be created with default renderers."""
        app = RestApplication()
        assert len(app._content_renderers) == 3  # JSON, HTML, PlainText
        assert "application/json" in app._content_renderers
        assert "text/html" in app._content_renderers
        assert "text/plain" in app._content_renderers

    def test_basic_get_route(self):
        """Test basic GET route registration and execution."""
        app = RestApplication()

        @app.get("/hello")
        def hello():
            return "Hello, World!"

        request = Request(
            method=HTTPMethod.GET, path="/hello", headers={"Accept": "text/plain"}
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert response.body == "Hello, World!"
        assert response.content_type == "text/plain"

    def test_route_with_path_params(self):
        """Test route with path parameters."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user(request: Request):
            user_id = request.path_params["user_id"]
            return {"id": user_id, "name": f"User {user_id}"}

        request = Request(
            method=HTTPMethod.GET,
            path="/users/123",
            headers={"Accept": "application/json"},
        )

        response = app.execute(request)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["id"] == "123"
        assert data["name"] == "User 123"


class TestDependencyInjection:
    """Test dependency injection functionality."""

    def test_basic_dependency_injection(self):
        """Test basic dependency registration and injection."""
        app = RestApplication()

        @app.dependency()
        def user_service():
            return {"users": {"1": "Alice", "2": "Bob"}}

        @app.get("/users/{user_id}")
        def get_user(user_service, request: Request):
            user_id = request.path_params["user_id"]
            users = user_service["users"]
            if user_id not in users:
                return Response(404, "User not found")
            return {"id": user_id, "name": users[user_id]}

        request = Request(
            method=HTTPMethod.GET,
            path="/users/1",
            headers={"Accept": "application/json"},
        )

        response = app.execute(request)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["name"] == "Alice"


class TestContentNegotiation:
    """Test content negotiation functionality."""

    def test_json_content_negotiation(self):
        """Test JSON content negotiation."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello", "data": [1, 2, 3]}

        request = Request(
            method=HTTPMethod.GET, path="/data", headers={"Accept": "application/json"}
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert response.content_type == "application/json"
        data = json.loads(response.body)
        assert data["message"] == "Hello"

    def test_html_content_negotiation(self):
        """Test HTML content negotiation."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello", "data": [1, 2, 3]}

        request = Request(
            method=HTTPMethod.GET, path="/data", headers={"Accept": "text/html"}
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert "<!DOCTYPE html>" in response.body
        assert "Hello" in response.body


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestValidation:
    """Test validation functionality."""

    def test_validation_error_422(self):
        """Test that validation errors return 422."""
        app = RestApplication()

        @app.validates
        def validate_user(request: Request) -> UserModel:
            data = json.loads(request.body)
            return UserModel.model_validate(data)  # This will raise ValidationError

        @app.post("/users")
        def create_user(validate_user: UserModel):
            return {"message": "User created"}

        # Test invalid request
        invalid_data = {"name": "", "email": "invalid-email", "age": -5}
        request = Request(
            method=HTTPMethod.POST,
            path="/users",
            headers={"Accept": "application/json"},
            body=json.dumps(invalid_data),
        )

        response = app.execute(request)
        assert response.status_code == 422
        data = json.loads(response.body)
        assert data["error"] == "Validation failed"
        assert "details" in data


class TestStateMachine:
    """Test state machine functionality."""

    def test_service_unavailable_503(self):
        """Test service unavailable callback."""
        app = RestApplication()

        @app.default_service_available
        def service_available():
            return False  # Service is down

        @app.get("/test")
        def handler():
            return "Should not reach here"

        request = Request(
            method=HTTPMethod.GET, path="/test", headers={"Accept": "text/plain"}
        )

        response = app.execute(request)
        assert response.status_code == 503
        assert "Service Unavailable" in response.body

    def test_404_for_unknown_route(self):
        """Test 404 response for unknown routes."""
        app = RestApplication()

        request = Request(
            method=HTTPMethod.GET,
            path="/unknown",
            headers={"Accept": "application/json"},
        )

        response = app.execute(request)
        assert response.status_code == 404
        assert "Not Found" in response.body


if __name__ == "__main__":
    pytest.main([__file__])

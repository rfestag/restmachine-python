"""
Tests for enhanced dependency injection with Pydantic model validation.
"""

import pytest
import json
from typing import Optional

from restmachine.application import RestApplication
from restmachine.models import Request, HTTPMethod

# Import Pydantic if available
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestEnhancedDependencies:
    """Test enhanced dependency injection with Pydantic validation."""

    @pytest.fixture
    def app(self):
        """Create a test application with enhanced dependencies."""
        app = RestApplication()

        # Define Pydantic models for testing
        class CreateUserBody(BaseModel):
            """Request body for creating a user."""
            name: str = Field(..., description="User's full name")
            email: str = Field(..., description="User's email address")
            age: int = Field(..., ge=0, le=150, description="User's age")

        class UserQueryParams(BaseModel):
            """Query parameters for user search."""
            name: Optional[str] = Field(None, description="Filter by name")
            age_min: Optional[int] = Field(None, ge=0, description="Minimum age filter")
            age_max: Optional[int] = Field(None, le=150, description="Maximum age filter")
            active: Optional[bool] = Field(None, description="Filter by active status")

        class UserPathParams(BaseModel):
            """Path parameters for user endpoints."""
            user_id: int = Field(..., description="Unique user identifier")

        class UpdateUserBody(BaseModel):
            """Request body for updating a user."""
            name: Optional[str] = Field(None, description="Updated name")
            email: Optional[str] = Field(None, description="Updated email")

        # Validators that depend on built-in dependencies
        @app.validates
        def validate_create_user_body(body) -> CreateUserBody:
            """Validate user creation request body."""
            if not body:
                raise ValueError("Request body is required")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in request body")
            return CreateUserBody.model_validate(data)

        @app.validates
        def validate_user_query_params(query_params) -> UserQueryParams:
            """Validate user query parameters."""
            return UserQueryParams.model_validate(query_params)

        @app.validates
        def validate_user_path_params(path_params) -> UserPathParams:
            """Validate user path parameters."""
            return UserPathParams.model_validate(path_params)

        @app.validates
        def validate_update_user_body(body) -> UpdateUserBody:
            """Validate user update request body."""
            if not body:
                raise ValueError("Request body is required")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in request body")
            return UpdateUserBody.model_validate(data)

        # Test routes that use these validators
        @app.get('/users')
        def list_users(validate_user_query_params: UserQueryParams):
            """List users with optional filtering."""
            return {
                "users": [],
                "filters": validate_user_query_params.model_dump()
            }

        @app.post('/users')
        def create_user(validate_create_user_body: CreateUserBody):
            """Create a new user."""
            return {
                "message": "User created",
                "user": validate_create_user_body.model_dump()
            }

        @app.get('/users/{user_id}')
        def get_user(validate_user_path_params: UserPathParams):
            """Get a specific user by ID."""
            return {
                "user_id": validate_user_path_params.user_id,
                "user": {"name": "Test User"}
            }

        @app.put('/users/{user_id}')
        def update_user(validate_user_path_params: UserPathParams, validate_update_user_body: UpdateUserBody):
            """Update a user."""
            return {
                "user_id": validate_user_path_params.user_id,
                "updates": validate_update_user_body.model_dump(exclude_unset=True)
            }

        return app

    def test_body_dependency_validation(self, app):
        """Test that body dependency validation works correctly."""
        create_user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }

        response = app.execute(Request(
            method=HTTPMethod.POST,
            path='/users',
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            body=json.dumps(create_user_data)
        ))

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["message"] == "User created"
        assert data["user"]["name"] == "John Doe"
        assert data["user"]["email"] == "john@example.com"
        assert data["user"]["age"] == 30

    def test_path_params_dependency_validation(self, app):
        """Test that path_params dependency validation works correctly."""
        response = app.execute(Request(
            method=HTTPMethod.GET,
            path='/users/123',
            headers={'Accept': 'application/json'},
            path_params={'user_id': '123'}
        ))

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["user_id"] == 123  # Should be converted to int
        assert data["user"]["name"] == "Test User"

    def test_query_params_dependency_validation(self, app):
        """Test that query_params dependency validation works correctly."""
        response = app.execute(Request(
            method=HTTPMethod.GET,
            path='/users',
            headers={'Accept': 'application/json'},
            query_params={'name': 'John', 'age_min': '25', 'active': 'true'}
        ))

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["users"] == []
        filters = data["filters"]
        assert filters["name"] == "John"
        assert filters["age_min"] == 25  # Should be converted to int
        assert filters["active"] is True  # Should be converted to bool

    def test_combined_dependencies_validation(self, app):
        """Test that combined path_params and body dependencies work correctly."""
        update_data = {
            "name": "John Smith",
            "email": "johnsmith@example.com"
        }

        response = app.execute(Request(
            method=HTTPMethod.PUT,
            path='/users/123',
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            body=json.dumps(update_data),
            path_params={'user_id': '123'}
        ))

        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["user_id"] == 123
        assert data["updates"]["name"] == "John Smith"
        assert data["updates"]["email"] == "johnsmith@example.com"

    def test_invalid_body_validation_error(self, app):
        """Test that invalid body data returns proper validation error."""
        invalid_data = {
            "name": "",  # Empty name should fail validation
            "email": "invalid-email",  # Invalid email format
            "age": -5  # Negative age should fail validation
        }

        response = app.execute(Request(
            method=HTTPMethod.POST,
            path='/users',
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            body=json.dumps(invalid_data)
        ))

        assert response.status_code == 422  # Validation error

    def test_invalid_path_params_validation_error(self, app):
        """Test that invalid path params return proper validation error."""
        response = app.execute(Request(
            method=HTTPMethod.GET,
            path='/users/invalid',
            headers={'Accept': 'application/json'},
            path_params={'user_id': 'invalid'}  # Should be int
        ))

        assert response.status_code == 422  # Validation error


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestOpenAPIGeneration:
    """Test OpenAPI generation with enhanced dependencies."""

    @pytest.fixture
    def app(self):
        """Create a test application for OpenAPI generation."""
        app = RestApplication()

        class CreateUserBody(BaseModel):
            name: str = Field(..., description="User's full name")
            email: str = Field(..., description="User's email address")
            age: int = Field(..., ge=0, le=150, description="User's age")

        class UserQueryParams(BaseModel):
            name: Optional[str] = Field(None, description="Filter by name")
            age_min: Optional[int] = Field(None, ge=0, description="Minimum age filter")

        class UserPathParams(BaseModel):
            user_id: int = Field(..., description="Unique user identifier")

        @app.validates
        def validate_create_user_body(body) -> CreateUserBody:
            data = json.loads(body)
            return CreateUserBody.model_validate(data)

        @app.validates
        def validate_user_query_params(query_params) -> UserQueryParams:
            return UserQueryParams.model_validate(query_params)

        @app.validates
        def validate_user_path_params(path_params) -> UserPathParams:
            return UserPathParams.model_validate(path_params)

        @app.get('/users')
        def list_users(validate_user_query_params: UserQueryParams):
            return {"users": []}

        @app.post('/users')
        def create_user(validate_create_user_body: CreateUserBody):
            return {"message": "User created"}

        @app.get('/users/{user_id}')
        def get_user(validate_user_path_params: UserPathParams):
            return {"user": {}}

        return app

    def test_openapi_generation_includes_schemas(self, app):
        """Test that OpenAPI generation includes proper schemas from dependencies."""
        openapi_json = app.generate_openapi_json(
            title="Enhanced Dependencies Test API",
            version="1.0.0",
            description="API demonstrating enhanced dependency support"
        )

        openapi_spec = json.loads(openapi_json)

        # Check that the OpenAPI spec was generated
        assert openapi_spec["openapi"] == "3.0.0"
        assert openapi_spec["info"]["title"] == "Enhanced Dependencies Test API"

        paths = openapi_spec.get("paths", {})
        assert "/users" in paths
        assert "/users/{user_id}" in paths

    def test_request_body_schema_generation(self, app):
        """Test that request body schemas are properly generated."""
        openapi_json = app.generate_openapi_json(
            title="Test API", version="1.0.0"
        )
        openapi_spec = json.loads(openapi_json)

        # Check POST /users for request body schema
        post_users = openapi_spec["paths"]["/users"]["post"]
        assert "requestBody" in post_users

        request_schema = post_users["requestBody"]["content"]["application/json"]["schema"]
        assert "$ref" in request_schema

    def test_query_parameters_schema_generation(self, app):
        """Test that query parameter schemas are properly generated."""
        openapi_json = app.generate_openapi_json(
            title="Test API", version="1.0.0"
        )
        openapi_spec = json.loads(openapi_json)

        # Check GET /users for query parameters
        get_users = openapi_spec["paths"]["/users"]["get"]
        assert "parameters" in get_users

        query_params = [p for p in get_users["parameters"] if p.get("in") == "query"]
        assert len(query_params) > 0

        param_names = {p["name"] for p in query_params}
        assert "name" in param_names
        assert "age_min" in param_names

    def test_path_parameters_schema_generation(self, app):
        """Test that path parameter schemas are properly generated."""
        openapi_json = app.generate_openapi_json(
            title="Test API", version="1.0.0"
        )
        openapi_spec = json.loads(openapi_json)

        # Check GET /users/{user_id} for path parameters
        get_user = openapi_spec["paths"]["/users/{user_id}"]["get"]
        assert "parameters" in get_user

        path_params = [p for p in get_user["parameters"] if p.get("in") == "path"]
        assert len(path_params) == 1

        user_id_param = path_params[0]
        assert user_id_param["name"] == "user_id"
        assert user_id_param["schema"]["type"] == "integer"

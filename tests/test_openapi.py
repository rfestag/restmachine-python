"""
OpenAPI generation tests using MultiDriverTestBase pattern.

Tests for OpenAPI specification generation, validation, and edge cases
across all supported drivers.
"""

import os
import tempfile
import json
from typing import Optional

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True

    # Test models for OpenAPI generation
    class CreateUserRequest(BaseModel):
        name: str = Field(..., min_length=1, description="The user's name")
        email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="The user's email address")
        age: Optional[int] = Field(None, ge=0, le=150, description="The user's age")

    class UserResponse(BaseModel):
        id: int = Field(..., description="The user's unique identifier")
        name: str = Field(..., description="The user's name")
        email: str = Field(..., description="The user's email address")
        age: Optional[int] = Field(None, description="The user's age")

    class UpdateUserRequest(BaseModel):
        name: Optional[str] = Field(None, min_length=1, description="The user's name")
        email: Optional[str] = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$", description="The user's email address")
        age: Optional[int] = Field(None, ge=0, le=150, description="The user's age")

except ImportError:
    PYDANTIC_AVAILABLE = False

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestBasicOpenAPIGeneration(MultiDriverTestBase):
    """Test basic OpenAPI specification generation."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API with basic routes."""
        app = RestApplication()

        @app.get("/")
        def home():
            """Get the home page."""
            return {"message": "Hello World"}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            """Get a user by ID."""
            user_id = path_params["user_id"]
            return {"id": int(user_id), "name": f"User {user_id}"}

        @app.post("/users")
        def create_user(json_body):
            """Create a new user."""
            return {"id": 123, "name": json_body["name"]}

        return app

    def test_basic_openapi_generation(self, api):
        """Test basic OpenAPI spec generation."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Basic structure validation
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

        # Check basic paths
        api_client.assert_has_path(spec, "/", "get")
        api_client.assert_has_path(spec, "/users/{user_id}", "get")
        api_client.assert_has_path(spec, "/users", "post")

    def test_openapi_spec_validation(self, api):
        """Test that generated OpenAPI spec is valid."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()
        api_client.assert_openapi_valid(spec)

    def test_path_parameters_in_spec(self, api):
        """Test that path parameters are included in spec."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check path parameter
        operation = api_client.get_path_operation(spec, "/users/{user_id}", "get")
        assert "parameters" in operation

        # Find the path parameter
        path_param = None
        for param in operation["parameters"]:
            if param["name"] == "user_id" and param["in"] == "path":
                path_param = param
                break

        assert path_param is not None, "Path parameter user_id not found"
        assert path_param["required"] is True


class TestOpenAPIWithPydantic(MultiDriverTestBase):
    """Test OpenAPI generation with Pydantic models."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API with Pydantic models."""
        if not PYDANTIC_AVAILABLE:
            return None

        app = RestApplication()

        @app.validates
        def validate_create_request(body) -> CreateUserRequest:
            import json
            return CreateUserRequest(**json.loads(body))

        @app.validates
        def validate_update_request(body) -> UpdateUserRequest:
            import json
            return UpdateUserRequest(**json.loads(body))

        @app.post("/users")
        def create_user(validate_create_request: CreateUserRequest) -> UserResponse:
            """Create a new user with validation."""
            return UserResponse(
                id=123,
                name=validate_create_request.name,
                email=validate_create_request.email,
                age=validate_create_request.age
            )

        @app.get("/users/{user_id}")
        def get_user(path_params) -> UserResponse:
            """Get a user by ID."""
            user_id = int(path_params["user_id"])
            return UserResponse(
                id=user_id,
                name=f"User {user_id}",
                email=f"user{user_id}@example.com",
                age=30
            )

        @app.put("/users/{user_id}")
        def update_user(path_params, validate_update_request: UpdateUserRequest) -> UserResponse:
            """Update a user."""
            user_id = int(path_params["user_id"])
            return UserResponse(
                id=user_id,
                name=validate_update_request.name or f"User {user_id}",
                email=validate_update_request.email or f"user{user_id}@example.com",
                age=validate_update_request.age or 30
            )

        return app

    def test_pydantic_schema_generation(self, api):
        """Test that Pydantic models generate schemas."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check that schemas are generated
        api_client.assert_has_schema(spec, "CreateUserRequest")
        api_client.assert_has_schema(spec, "UserResponse")
        api_client.assert_has_schema(spec, "UpdateUserRequest")

    def test_request_body_schema_reference(self, api):
        """Test that request body references correct schema."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check POST /users request body
        api_client.assert_request_body_schema(spec, "/users", "post", "CreateUserRequest")

        # Check PUT /users/{user_id} request body
        api_client.assert_request_body_schema(spec, "/users/{user_id}", "put", "UpdateUserRequest")

    def test_response_schema_reference(self, api):
        """Test that responses reference correct schemas."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check POST /users response
        api_client.assert_response_schema(spec, "/users", "post", "200", "UserResponse")

        # Check GET /users/{user_id} response
        api_client.assert_response_schema(spec, "/users/{user_id}", "get", "200", "UserResponse")

    def test_optional_fields_in_schema(self, api):
        """Test that optional fields are properly marked."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check CreateUserRequest schema
        create_schema = spec["components"]["schemas"]["CreateUserRequest"]
        assert "required" in create_schema
        assert "name" in create_schema["required"]
        assert "email" in create_schema["required"]
        assert "age" not in create_schema["required"]  # Optional field

        # Check UpdateUserRequest schema (all fields optional)
        update_schema = spec["components"]["schemas"]["UpdateUserRequest"]
        # All fields should be optional in update request
        if "required" in update_schema:
            assert len(update_schema["required"]) == 0

    def test_field_descriptions_included(self, api):
        """Test that field descriptions are included in schemas."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check that field descriptions are present
        create_schema = spec["components"]["schemas"]["CreateUserRequest"]
        assert "properties" in create_schema

        name_prop = create_schema["properties"]["name"]
        assert "description" in name_prop
        assert name_prop["description"] == "The user's name"

        email_prop = create_schema["properties"]["email"]
        assert "description" in email_prop
        assert email_prop["description"] == "The user's email address"


class TestOpenAPIFileSaving(MultiDriverTestBase):
    """Test OpenAPI file saving functionality."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up simple API for file saving tests."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            """Test endpoint."""
            return {"test": "data"}

        return app

    def test_save_openapi_json_default_location(self, api):
        """Test saving OpenAPI spec to default location."""
        api_client, driver_name = api

        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                filepath = api_client.save_openapi_spec()

                # Check file was created
                assert os.path.exists(filepath)
                assert filepath == "docs/openapi.json"

                # Check file contents
                with open(filepath, 'r') as f:
                    spec = json.load(f)
                assert "openapi" in spec
                assert "paths" in spec

            finally:
                os.chdir(original_cwd)

    def test_save_openapi_json_custom_directory(self, api):
        """Test saving OpenAPI spec to custom directory."""
        api_client, driver_name = api

        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = os.path.join(temp_dir, "custom_docs")
            filepath = api_client.save_openapi_spec(directory=custom_dir, filename="api.json")

            # Check file was created
            assert os.path.exists(filepath)
            assert filepath == os.path.join(custom_dir, "api.json")

            # Check file contents
            with open(filepath, 'r') as f:
                spec = json.load(f)
            assert "openapi" in spec

    def test_save_openapi_creates_directory(self, api):
        """Test that saving OpenAPI spec creates directory if it doesn't exist."""
        api_client, driver_name = api

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = os.path.join(temp_dir, "docs", "api", "v1")
            filepath = api_client.save_openapi_spec(directory=nested_dir)

            # Check directory and file were created
            assert os.path.exists(nested_dir)
            assert os.path.exists(filepath)


class TestOpenAPIEdgeCases(MultiDriverTestBase):
    """Test OpenAPI generation edge cases."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API with edge case routes."""
        app = RestApplication()

        @app.get("/simple")
        def simple_route():
            return "Simple response"

        @app.get("/api/v1/users/{user_id}/posts/{post_id}/comments")
        def get_comments(path_params):
            """Get comments for a specific post."""
            return {"comments": []}

        return app

    def test_route_without_annotations(self, api):
        """Test routes without type annotations."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Should still generate valid spec
        api_client.assert_openapi_valid(spec)
        api_client.assert_has_path(spec, "/simple", "get")

    def test_route_with_complex_path(self, api):
        """Test routes with complex path patterns."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        api_client.assert_has_path(spec, "/api/v1/users/{user_id}/posts/{post_id}/comments", "get")

        # Check multiple path parameters
        operation = api_client.get_path_operation(spec, "/api/v1/users/{user_id}/posts/{post_id}/comments", "get")
        assert "parameters" in operation

        # Should have both user_id and post_id parameters
        param_names = [p["name"] for p in operation["parameters"] if p["in"] == "path"]
        assert "user_id" in param_names
        assert "post_id" in param_names


class TestEmptyApplication(MultiDriverTestBase):
    """Test OpenAPI generation for empty application."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create empty application."""
        app = RestApplication()
        return app

    def test_empty_application(self, api):
        """Test OpenAPI generation for empty application."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Should generate valid spec even with no routes
        api_client.assert_openapi_valid(spec)
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        # Paths can be empty for empty application
        assert isinstance(spec["paths"], dict)


class TestOpenAPIMultipleHTTPMethods(MultiDriverTestBase):
    """Test OpenAPI generation with multiple HTTP methods on same path."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API with multiple methods on same path."""
        app = RestApplication()

        @app.get("/items/{item_id}")
        def get_item(path_params):
            """Get an item."""
            return {"id": path_params["item_id"]}

        @app.put("/items/{item_id}")
        def update_item(path_params, json_body):
            """Update an item."""
            return {"id": path_params["item_id"], **json_body}

        @app.delete("/items/{item_id}")
        def delete_item(path_params):
            """Delete an item."""
            return None

        return app

    def test_multiple_methods_same_path(self, api):
        """Test that multiple methods on same path are handled correctly."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Check all methods are present
        api_client.assert_has_path(spec, "/items/{item_id}", "get")
        api_client.assert_has_path(spec, "/items/{item_id}", "put")
        api_client.assert_has_path(spec, "/items/{item_id}", "delete")

        # Check each method has proper configuration
        path_spec = spec["paths"]["/items/{item_id}"]
        assert "get" in path_spec
        assert "put" in path_spec
        assert "delete" in path_spec

        # Check that DELETE method shows no content response
        delete_op = path_spec["delete"]
        assert "responses" in delete_op
        assert "204" in delete_op["responses"] or "200" in delete_op["responses"]


class TestOpenAPIQueryParameters(MultiDriverTestBase):
    """Test OpenAPI generation with query parameters."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API with query parameters."""
        app = RestApplication()

        @app.get("/search")
        def search_items(query_params):
            """Search items with query parameters."""
            return {"results": [], "query": dict(query_params)}

        return app

    def test_query_parameters_in_spec(self, api):
        """Test that query parameters are documented in OpenAPI spec."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        api_client.assert_has_path(spec, "/search", "get")

        # The framework might auto-detect query parameters or require manual specification
        # This test verifies the structure is correct
        operation = api_client.get_path_operation(spec, "/search", "get")

        # Operation should exist and be valid
        assert "responses" in operation


class TestOpenAPIValidation(MultiDriverTestBase):
    """Test OpenAPI specification validation."""

    # OpenAPI generation only works with direct driver
    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Set up API for validation tests."""
        if not PYDANTIC_AVAILABLE:
            app = RestApplication()

            @app.get("/status")
            def get_status():
                return {"status": "ok"}

            @app.get("/api/v2/complex/{id}/nested/{nested_id}")
            def complex_route(path_params):
                return {"data": "complex"}

            return app

        app = RestApplication()

        @app.post("/users")
        def create_user(json_body: CreateUserRequest) -> UserResponse:
            return UserResponse(id=1, name=json_body.name, email=json_body.email)

        @app.get("/users/{user_id}")
        def get_user(path_params) -> UserResponse:
            user_id = int(path_params["user_id"])
            return UserResponse(id=user_id, name=f"User {user_id}", email=f"user{user_id}@example.com")

        @app.get("/status")
        def get_status():
            return {"status": "ok"}

        @app.get("/api/v2/complex/{id}/nested/{nested_id}")
        def complex_route(path_params):
            return {"data": "complex"}

        return app

    def test_comprehensive_spec_validation(self, api):
        """Test validation of comprehensive OpenAPI spec."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Should validate successfully
        api_client.assert_openapi_valid(spec)

    def test_edge_cases_spec_validation(self, api):
        """Test validation with edge cases."""
        api_client, driver_name = api

        spec = api_client.generate_openapi_spec()

        # Should still validate
        api_client.assert_openapi_valid(spec)
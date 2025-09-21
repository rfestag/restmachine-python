"""
Unit tests for OpenAPI specification generation features.
"""

import json
import os
import tempfile
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field

from restmachine import HTTPMethod, RestApplication
from restmachine.application import RouteHandler


# Test models
class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, description="The user's name")
    email: str = Field(
        ..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="The user's email address"
    )
    age: Optional[int] = Field(None, ge=0, le=150, description="The user's age")


class User(BaseModel):
    id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="The user's name")
    email: str = Field(..., description="The user's email address")
    age: Optional[int] = Field(None, description="The user's age")


class QueryParams(BaseModel):
    start: Optional[int] = Field(None, ge=0, description="Start index for pagination")
    limit: Optional[int] = Field(
        None, ge=1, le=100, description="Maximum number of items to return"
    )
    search: Optional[str] = Field(None, description="Search term to filter users")


class TestOpenAPIGeneration:
    """Test OpenAPI specification generation functionality."""

    def test_basic_openapi_generation(self):
        """Test that basic OpenAPI JSON can be generated."""
        app = RestApplication()

        @app.get("/users")
        def list_users() -> List[User]:
            """List all users in the system."""
            return []

        openapi_json = app.generate_openapi_json(
            title="Test API", version="1.0.0", description="A test API"
        )

        # Parse the JSON to verify it's valid
        spec = json.loads(openapi_json)

        # Verify basic structure
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Test API"
        assert spec["info"]["version"] == "1.0.0"
        assert spec["info"]["description"] == "A test API"
        assert "paths" in spec
        assert "/users" in spec["paths"]
        assert "get" in spec["paths"]["/users"]

    def test_openapi_with_path_parameters(self):
        """Test OpenAPI generation with path parameters."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user() -> User:
            """Get a specific user by their ID."""
            return User(id="1", name="Test", email="test@example.com")

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify path parameter is included
        operation = spec["paths"]["/users/{user_id}"]["get"]
        assert "parameters" in operation

        path_params = [p for p in operation["parameters"] if p["in"] == "path"]
        assert len(path_params) == 1
        assert path_params[0]["name"] == "user_id"
        assert path_params[0]["required"] is True
        assert path_params[0]["schema"]["type"] == "string"

    def test_openapi_with_request_body(self):
        """Test OpenAPI generation with request body schemas."""
        app = RestApplication()

        @app.validates
        def validate_create_request(body) -> CreateUserRequest:
            return CreateUserRequest(**json.loads(body))

        @app.post("/users")
        def create_user(validate_create_request: CreateUserRequest) -> User:
            """Create a new user."""
            return User(
                id="1",
                name=validate_create_request.name,
                email=validate_create_request.email,
            )

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify request body schema
        operation = spec["paths"]["/users"]["post"]
        assert "requestBody" in operation
        assert "content" in operation["requestBody"]
        assert "application/json" in operation["requestBody"]["content"]

        schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]
        assert "$ref" in schema_ref
        assert schema_ref["$ref"] == "#/components/schemas/CreateUserRequest"

        # Verify schema is included in components
        assert "components" in spec
        assert "schemas" in spec["components"]
        assert "CreateUserRequest" in spec["components"]["schemas"]

    def test_openapi_with_query_parameters(self):
        """Test OpenAPI generation with query parameters."""
        app = RestApplication()

        @app.validates
        def validate_query_params(query_params) -> QueryParams:
            return QueryParams(**query_params)

        @app.get("/users")
        def list_users(validate_query_params: QueryParams) -> List[User]:
            """List users with optional filtering and pagination."""
            return []

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify query parameters are included
        operation = spec["paths"]["/users"]["get"]
        assert "parameters" in operation

        query_params = [p for p in operation["parameters"] if p["in"] == "query"]
        assert len(query_params) >= 3  # start, limit, search

        param_names = [p["name"] for p in query_params]
        assert "start" in param_names
        assert "limit" in param_names
        assert "search" in param_names

    def test_openapi_with_response_schemas(self):
        """Test OpenAPI generation with response schemas."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user() -> User:
            """Get a specific user."""
            return User(id="1", name="Test", email="test@example.com")

        @app.get("/users")
        def list_users() -> List[User]:
            """List all users."""
            return []

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify single user response
        get_operation = spec["paths"]["/users/{user_id}"]["get"]
        assert "responses" in get_operation
        assert "200" in get_operation["responses"]

        response_schema = get_operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert "$ref" in response_schema
        assert response_schema["$ref"] == "#/components/schemas/User"

        # Verify list response
        list_operation = spec["paths"]["/users"]["get"]
        list_response_schema = list_operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert list_response_schema["type"] == "array"
        assert "$ref" in list_response_schema["items"]
        assert list_response_schema["items"]["$ref"] == "#/components/schemas/User"

    def test_openapi_with_no_content_response(self):
        """Test OpenAPI generation with None return type (204 No Content)."""
        app = RestApplication()

        @app.delete("/users/{user_id}")
        def delete_user() -> None:
            """Delete a user."""
            pass

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify 204 response
        operation = spec["paths"]["/users/{user_id}"]["delete"]
        assert "responses" in operation
        assert "204" in operation["responses"]
        assert operation["responses"]["204"]["description"] == "No Content"
        assert "content" not in operation["responses"]["204"]

    def test_openapi_with_docstrings(self):
        """Test that handler docstrings are included in OpenAPI spec."""
        app = RestApplication()

        @app.get("/users")
        def list_users() -> List[User]:
            """Retrieve a list of all users in the system.

            This endpoint supports pagination and filtering.
            """
            return []

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        operation = spec["paths"]["/users"]["get"]
        assert "description" in operation
        assert "Retrieve a list of all users" in operation["description"]

    def test_openapi_with_multiple_http_methods(self):
        """Test OpenAPI generation with multiple HTTP methods on same path."""
        app = RestApplication()

        @app.validates
        def validate_create_request(body) -> CreateUserRequest:
            return CreateUserRequest(**json.loads(body))

        @app.validates
        def validate_update_request(body) -> User:
            return User(**json.loads(body))

        @app.get("/users/{user_id}")
        def get_user() -> User:
            """Get a user."""
            return User(id="1", name="Test", email="test@example.com")

        @app.put("/users/{user_id}")
        def update_user(validate_update_request: User) -> User:
            """Update a user."""
            return validate_update_request

        @app.delete("/users/{user_id}")
        def delete_user() -> None:
            """Delete a user."""
            pass

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        user_path = spec["paths"]["/users/{user_id}"]
        assert "get" in user_path
        assert "put" in user_path
        assert "delete" in user_path

        # Verify each method has proper configuration
        assert (
            user_path["get"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["$ref"]
            == "#/components/schemas/User"
        )
        assert "requestBody" in user_path["put"]
        assert user_path["delete"]["responses"]["204"]["description"] == "No Content"

    def test_pydantic_schema_collection(self):
        """Test that Pydantic model schemas are properly collected."""
        app = RestApplication()

        @app.validates
        def validate_create_request(body) -> CreateUserRequest:
            return CreateUserRequest(**json.loads(body))

        @app.post("/users")
        def create_user(validate_create_request: CreateUserRequest) -> User:
            return User(
                id="1",
                name=validate_create_request.name,
                email=validate_create_request.email,
            )

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Verify both schemas are collected
        assert "components" in spec
        assert "schemas" in spec["components"]
        schemas = spec["components"]["schemas"]

        assert "CreateUserRequest" in schemas
        assert "User" in schemas

        # Verify schema structure
        user_schema = schemas["User"]
        assert user_schema["type"] == "object"
        assert "properties" in user_schema
        assert "id" in user_schema["properties"]
        assert "name" in user_schema["properties"]
        assert "email" in user_schema["properties"]

        create_schema = schemas["CreateUserRequest"]
        assert create_schema["type"] == "object"
        assert "properties" in create_schema
        assert "name" in create_schema["properties"]
        assert "email" in create_schema["properties"]

    def test_optional_fields_in_schema(self):
        """Test that optional fields are properly handled in schemas."""
        app = RestApplication()

        @app.validates
        def validate_query_params(query_params) -> QueryParams:
            return QueryParams(**query_params)

        @app.get("/users")
        def list_users(validate_query_params: QueryParams) -> List[User]:
            return []

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Check query parameters - optional fields should have required=False
        operation = spec["paths"]["/users"]["get"]
        query_params = [p for p in operation["parameters"] if p["in"] == "query"]

        for param in query_params:
            if param["name"] in ["start", "limit", "search"]:
                assert param["required"] is False

    def test_field_descriptions_included(self):
        """Test that Pydantic field descriptions are included in OpenAPI spec."""
        app = RestApplication()

        @app.validates
        def validate_create_request(body) -> CreateUserRequest:
            return CreateUserRequest(**json.loads(body))

        @app.post("/users")
        def create_user(validate_create_request: CreateUserRequest) -> User:
            return User(
                id="1",
                name=validate_create_request.name,
                email=validate_create_request.email,
            )

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Check that field descriptions are included
        create_schema = spec["components"]["schemas"]["CreateUserRequest"]
        name_property = create_schema["properties"]["name"]
        assert "description" in name_property
        assert name_property["description"] == "The user's name"


class TestOpenAPIFileSaving:
    """Test OpenAPI file saving functionality."""

    def test_save_openapi_json_default_location(self):
        """Test saving OpenAPI JSON to default docs directory."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                file_path = app.save_openapi_json(
                    filename="test_openapi.json", title="Test API", version="1.0.0"
                )

                # Verify file was created
                assert os.path.exists(file_path)
                assert file_path.endswith("docs/test_openapi.json")

                # Verify content is valid JSON
                with open(file_path, "r") as f:
                    spec = json.load(f)
                    assert spec["info"]["title"] == "Test API"
                    assert spec["info"]["version"] == "1.0.0"
                    assert "/test" in spec["paths"]

            finally:
                os.chdir(original_cwd)

    def test_save_openapi_json_custom_directory(self):
        """Test saving OpenAPI JSON to custom directory."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            custom_docs_dir = os.path.join(temp_dir, "api_docs")

            # Change to temp directory
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                file_path = app.save_openapi_json(
                    filename="custom_api.json",
                    docs_dir="api_docs",
                    title="Custom API",
                    version="2.0.0",
                    description="Custom API documentation",
                )

                # Verify file was created in custom directory
                assert os.path.exists(file_path)
                assert file_path.endswith("api_docs/custom_api.json")
                assert os.path.exists(custom_docs_dir)

                # Verify content
                with open(file_path, "r") as f:
                    spec = json.load(f)
                    assert spec["info"]["title"] == "Custom API"
                    assert spec["info"]["version"] == "2.0.0"
                    assert spec["info"]["description"] == "Custom API documentation"

            finally:
                os.chdir(original_cwd)

    def test_save_openapi_json_creates_directory(self):
        """Test that save_openapi_json creates docs directory if it doesn't exist."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return "test"

        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = os.path.join(temp_dir, "new_docs")

            # Verify directory doesn't exist initially
            assert not os.path.exists(docs_dir)

            # Change to temp directory
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                file_path = app.save_openapi_json(docs_dir="new_docs")

                # Verify directory was created
                assert os.path.exists(docs_dir)
                assert os.path.exists(file_path)

            finally:
                os.chdir(original_cwd)


class TestOpenAPIEdgeCases:
    """Test edge cases in OpenAPI generation."""

    def test_route_without_annotations(self):
        """Test handling of routes without type annotations."""
        app = RestApplication()

        @app.get("/untyped")
        def untyped_endpoint():
            """An endpoint without type annotations."""
            return {"message": "test"}

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Should still generate basic operation
        operation = spec["paths"]["/untyped"]["get"]
        assert "responses" in operation
        assert "200" in operation["responses"]
        # Response should not have content schema for untyped handlers
        assert "content" not in operation["responses"]["200"]

    def test_empty_application(self):
        """Test OpenAPI generation for application with no routes."""
        app = RestApplication()

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Should generate valid OpenAPI spec with empty paths
        assert spec["openapi"] == "3.0.0"
        assert "info" in spec
        assert "paths" in spec
        assert spec["paths"] == {}

    def test_route_with_complex_path(self):
        """Test routes with complex path patterns."""
        app = RestApplication()

        @app.get("/api/v1/users/{user_id}/posts/{post_id}")
        def get_user_post() -> dict:
            """Get a specific post by a specific user."""
            return {}

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        path = "/api/v1/users/{user_id}/posts/{post_id}"
        assert path in spec["paths"]

        operation = spec["paths"][path]["get"]
        assert "parameters" in operation

        path_params = [p for p in operation["parameters"] if p["in"] == "path"]
        assert len(path_params) == 2

        param_names = [p["name"] for p in path_params]
        assert "user_id" in param_names
        assert "post_id" in param_names

    def test_validation_without_pydantic_dependency(self):
        """Test handling when validation is used but parameter doesn't match dependency."""
        app = RestApplication()

        @app.validates
        def some_validator(body) -> CreateUserRequest:
            return CreateUserRequest(**json.loads(body))

        @app.post("/users")
        def create_user() -> User:
            """Create user without using the validator parameter."""
            return User(id="1", name="test", email="test@example.com")

        openapi_json = app.generate_openapi_json()
        spec = json.loads(openapi_json)

        # Should still generate valid spec, but without request body schema
        operation = spec["paths"]["/users"]["post"]
        assert "requestBody" not in operation


if __name__ == "__main__":
    pytest.main([__file__])

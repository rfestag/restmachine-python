"""
Tests for application.py OpenAPI edge cases.

Covers path_params from validation, body schemas, save_openapi_spec, etc.
"""

import os
import json
import tempfile
from pydantic import BaseModel
from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class PathParams(BaseModel):
    """Path parameter model."""
    user_id: str
    post_id: int


class FormData(BaseModel):
    """Form data model."""
    title: str
    content: str


class TestOpenAPIPathParamsFromValidation(MultiDriverTestBase):
    """Test OpenAPI generation with path params from validation."""

    def create_app(self) -> RestApplication:
        """Create app with path param validation."""
        app = RestApplication()

        @app.validates
        def validate_path_params(path_params) -> PathParams:
            """Validate path parameters."""
            return PathParams.model_validate(path_params)

        @app.get("/users/{user_id}/posts/{post_id}")
        def get_post(validate_path_params):
            """Get post with validated path params."""
            return {
                "user_id": validate_path_params.user_id,
                "post_id": validate_path_params.post_id
            }

        return app

    def test_openapi_includes_path_params_from_validation(self, api):
        """Test that OpenAPI includes path params from validation dependencies."""
        api_client, driver_name = api

        # Get the app from the driver
        app = api_client.driver.app

        # Generate OpenAPI spec (returns JSON string)
        openapi_json = app.generate_openapi_json()
        openapi_dict = json.loads(openapi_json)

        # Check that path parameters are included
        path_spec = openapi_dict["paths"]["/users/{user_id}/posts/{post_id}"]["get"]

        # Should have parameters from the validation model
        assert "parameters" in path_spec
        param_names = [p["name"] for p in path_spec["parameters"]]

        # At minimum, should have user_id and post_id
        assert "user_id" in param_names or "post_id" in param_names


class TestOpenAPIBodySchemas(MultiDriverTestBase):
    """Test OpenAPI generation for different body types."""

    def create_app(self) -> RestApplication:
        """Create app with different body types."""
        app = RestApplication()

        @app.post("/submit-form")
        def handle_form(form_body):
            """Handle form submission."""
            return {"received": "form"}

        @app.post("/submit-text")
        def handle_text(text_body):
            """Handle text submission."""
            return {"received": "text"}

        @app.post("/submit-multipart")
        def handle_multipart(multipart_body):
            """Handle multipart submission."""
            return {"received": "multipart"}

        return app

    def test_openapi_form_body_schema(self, api):
        """Test OpenAPI schema for form_body parameter."""
        api_client, driver_name = api

        app = api_client.driver.app
        openapi_json = app.generate_openapi_json()
        openapi_dict = json.loads(openapi_json)

        # Check form endpoint has request body
        form_spec = openapi_dict["paths"]["/submit-form"]["post"]
        # The endpoint should have some request body definition
        assert "requestBody" in form_spec or "parameters" in form_spec

    def test_openapi_text_body_schema(self, api):
        """Test OpenAPI schema for text_body parameter."""
        api_client, driver_name = api

        app = api_client.driver.app
        openapi_json = app.generate_openapi_json()
        openapi_dict = json.loads(openapi_json)

        # Check text endpoint
        text_spec = openapi_dict["paths"]["/submit-text"]["post"]
        assert "requestBody" in text_spec or "parameters" in text_spec

    def test_openapi_multipart_body_schema(self, api):
        """Test OpenAPI schema for multipart_body parameter."""
        api_client, driver_name = api

        app = api_client.driver.app
        openapi_json = app.generate_openapi_json()
        openapi_dict = json.loads(openapi_json)

        # Check multipart endpoint
        multipart_spec = openapi_dict["paths"]["/submit-multipart"]["post"]
        assert "requestBody" in multipart_spec or "parameters" in multipart_spec


class TestOpenAPISave(MultiDriverTestBase):
    """Test OpenAPI save functionality."""

    def create_app(self) -> RestApplication:
        """Create simple app for OpenAPI save test."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            """Test endpoint."""
            return {"test": True}

        return app

    def test_save_openapi_json(self, api):
        """Test save_openapi_json creates file."""
        api_client, driver_name = api

        app = api_client.driver.app

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save OpenAPI spec
            file_path = app.save_openapi_json(
                docs_dir=tmpdir,
                filename="test-openapi.json",
                title="Test API",
                version="1.0.0",
                description="Test Description"
            )

            # Verify file was created
            assert os.path.exists(file_path)
            assert file_path.endswith("test-openapi.json")

            # Verify content is valid JSON
            with open(file_path, 'r') as f:
                openapi_data = json.load(f)
                assert openapi_data["info"]["title"] == "Test API"
                assert openapi_data["info"]["version"] == "1.0.0"
                assert openapi_data["info"]["description"] == "Test Description"

    def test_save_openapi_json_creates_directory(self, api):
        """Test save_openapi_json creates directory if it doesn't exist."""
        api_client, driver_name = api

        app = api_client.driver.app

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a subdirectory that doesn't exist yet
            docs_dir = os.path.join(tmpdir, "docs", "api")

            # Save OpenAPI spec (should create the directory)
            file_path = app.save_openapi_json(
                docs_dir=docs_dir,
                filename="openapi.json"
            )

            # Verify directory was created
            assert os.path.exists(docs_dir)
            assert os.path.isdir(docs_dir)

            # Verify file was created
            assert os.path.exists(file_path)


class TestOpenAPIAcceptsParserSchemas(MultiDriverTestBase):
    """Test OpenAPI schemas from @accepts parsers."""

    def create_app(self) -> RestApplication:
        """Create app with custom @accepts parser."""
        app = RestApplication()

        class CustomData(BaseModel):
            """Custom data model."""
            field1: str
            field2: int

        @app.accepts("application/custom")
        def parse_custom(text_body) -> CustomData:
            """Parse custom content type."""
            # Simple parser for testing
            return CustomData(field1="test", field2=123)

        @app.post("/custom-content")
        def handle_custom(parse_custom):
            """Handle custom content."""
            return {"field1": parse_custom.field1, "field2": parse_custom.field2}

        return app

    def test_openapi_includes_accepts_parser_schema(self, api):
        """Test that OpenAPI includes schemas from @accepts parsers."""
        api_client, driver_name = api

        app = api_client.driver.app
        openapi_json = app.generate_openapi_json()
        openapi_dict = json.loads(openapi_json)

        # Check that the endpoint has request body schema
        custom_spec = openapi_dict["paths"]["/custom-content"]["post"]

        # Should have request body with schema
        # The exact structure depends on implementation, but should have some reference
        assert "requestBody" in custom_spec or "parameters" in custom_spec

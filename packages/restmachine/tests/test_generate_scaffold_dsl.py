"""
Tests for scaffold generator using the testing DSL.

This demonstrates the cleaner test style using the RestMachine testing DSL.
"""

import os
import pytest
from restmachine_orm import Model
from click.testing import CliRunner


class TestGenerateScaffoldWithDSL:
    """Test generate scaffold command using DSL."""

    def test_scaffold_command_creates_all_files(self, restmachine_app):
        """Test that scaffold command creates all expected files."""
        result = restmachine_app.add_scaffold("Product")
        result.assert_success()

        # Verify all files were created
        assert result.model_file.exists()
        assert result.schemas_file.exists()
        assert result.routes_file.exists()
        assert result.fixture_file.exists()
        assert result.test_file.exists()

    def test_scaffold_with_field_arguments(self, restmachine_app):
        """Test that scaffold command accepts field arguments."""
        result = restmachine_app.add_scaffold(
            "Product", ["name:str", "price:float", "stock:int"]
        )
        result.assert_success()

        # Verify model has the specified fields
        Product = restmachine_app.import_model("Product")

        restmachine_app.assert_inherits_from(Product, Model)
        restmachine_app.assert_model_has_fields(
            Product,
            {
                "id": str,  # UUID stored as str
                "name": str,
                "price": float,
                "stock": int,
            },
        )

    def test_scaffold_command_updates_models_init(self, restmachine_app):
        """Test that scaffold command updates models/__init__.py."""
        restmachine_app.add_scaffold("Product").assert_success()

        # Check models/__init__.py was updated
        init_content = restmachine_app.read_file("models/__init__.py")
        assert "from models.product import Product" in init_content

    def test_scaffold_command_updates_schemas_init(self, restmachine_app):
        """Test that scaffold command updates schemas/__init__.py."""
        restmachine_app.add_scaffold("Product").assert_success()

        # Check schemas/__init__.py was updated
        init_content = restmachine_app.read_file("schemas/__init__.py")
        assert (
            "from schemas.product_schemas import CreateProductRequest, UpdateProductRequest, ListProductsResponse"
            in init_content
        )

    def test_scaffold_command_mounts_router_in_app(self, restmachine_app):
        """Test that scaffold command mounts router in app.py."""
        restmachine_app.add_scaffold("Product").assert_success()

        # Check app.py was updated
        app_content = restmachine_app.read_file("app.py")
        assert "from routes.products import router as products_router" in app_content
        assert "app.mount('/products', products_router)" in app_content

    def test_scaffold_with_skip_tests_flag(self, restmachine_app):
        """Test scaffold command with --skip-tests flag."""
        result = restmachine_app.add_scaffold("Product", skip_tests=True)
        result.assert_success()

        # Test file should not exist
        assert result.test_file is None

        # Other files should still exist
        assert result.model_file.exists()
        assert result.routes_file.exists()

    def test_scaffold_with_skip_fixtures_flag(self, restmachine_app):
        """Test scaffold command with --skip-fixtures flag."""
        result = restmachine_app.add_scaffold("Product", skip_fixtures=True)
        result.assert_success()

        # Fixture file should not exist
        assert result.fixture_file is None

        # Other files should still exist
        assert result.model_file.exists()
        assert result.routes_file.exists()

    def test_scaffold_fails_outside_project(self, tmp_path):
        """Test that scaffold command fails when not in a RestMachine project."""
        from restmachine.cli import main

        # Use empty directory without RestMachine structure
        runner = CliRunner()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["generate", "scaffold", "Product"])
            assert result.exit_code != 0
            assert "Not in a RestMachine project" in result.output
        finally:
            os.chdir(old_cwd)

    def test_scaffold_handles_camelcase_input(self, restmachine_app):
        """Test scaffold with CamelCase input."""
        result = restmachine_app.add_scaffold("BlogPost")
        result.assert_success()

        # Files should use snake_case
        assert restmachine_app.file_exists("models/blog_post.py")
        assert restmachine_app.file_exists("schemas/blog_post_schemas.py")
        assert restmachine_app.file_exists("routes/blog_posts.py")

        # Content should use PascalCase for class
        BlogPost = restmachine_app.import_model("BlogPost")
        assert BlogPost.__name__ == "BlogPost"

    def test_scaffold_handles_snake_case_input(self, restmachine_app):
        """Test scaffold with snake_case input."""
        result = restmachine_app.add_scaffold("blog_post")
        result.assert_success()

        # Files should use snake_case
        assert restmachine_app.file_exists("models/blog_post.py")

        # Content should use PascalCase for class
        BlogPost = restmachine_app.import_model("BlogPost")
        assert BlogPost.__name__ == "BlogPost"

    def test_scaffold_pluralization(self, restmachine_app):
        """Test that scaffold correctly pluralizes resource names."""
        test_cases = [
            ("Category", "categories"),
            ("Status", "statuses"),
            ("Person", "people"),
        ]

        for resource, expected_plural in test_cases:
            result = restmachine_app.add_scaffold(resource)
            result.assert_success()

            # Routes file should use plural
            assert restmachine_app.file_exists(
                f"routes/{expected_plural}.py"
            ), f"Expected routes/{expected_plural}.py for {resource}"

    def test_generated_scaffold_has_valid_syntax(self, restmachine_app):
        """Test that generated scaffold files are syntactically valid."""
        result = restmachine_app.add_scaffold("Product")
        result.assert_success()

        # Verify all generated files have valid Python syntax
        import ast
        import py_compile

        for file_path in [
            result.model_file,
            result.schemas_file,
            result.routes_file,
            result.test_file,
        ]:
            # Test 1: File can be parsed as valid Python AST
            tree = ast.parse(file_path.read_text())
            assert tree is not None, f"AST parsing returned None for {file_path}"

            # Test 2: File can be compiled to bytecode
            py_compile.compile(str(file_path), doraise=True)

    def test_generated_scaffold_is_functional(self, restmachine_app):
        """Test that generated scaffold is functionally correct."""
        result = restmachine_app.add_scaffold("Product")
        result.assert_success()

        # Import the generated router module (tests for circular imports)
        routes_module = restmachine_app.import_router("Product")
        assert hasattr(routes_module, "router"), "Routes module should have router"

        # Verify app can be created and router mounted without errors
        from restmachine import RestApplication

        app = RestApplication()
        app.mount("/products", routes_module.router)

        # Generate OpenAPI schema
        import json

        spec_json = app.generate_openapi_json()
        spec = json.loads(spec_json)

        # Verify all standard REST endpoints are present
        assert "/products/" in spec["paths"], "List endpoint missing from OpenAPI"
        assert (
            "/products/{product_id}" in spec["paths"]
        ), "Get single endpoint missing from OpenAPI"

        list_path = spec["paths"]["/products/"]
        single_path = spec["paths"]["/products/{product_id}"]

        # Verify all HTTP methods are present
        assert "get" in list_path, "GET /products endpoint missing"
        assert "post" in list_path, "POST /products endpoint missing"
        assert "get" in single_path, "GET /products/{product_id} endpoint missing"
        assert "put" in single_path, "PUT /products/{product_id} endpoint missing"
        assert "delete" in single_path, "DELETE /products/{product_id} endpoint missing"

"""
Tests for model generator using the testing DSL.

This demonstrates the cleaner test style using the RestMachine testing DSL.
"""

import pytest
from restmachine_orm import Model
from datetime import datetime


class TestGenerateModelWithDSL:
    """Test generate model command using DSL."""

    def test_model_command_creates_model_with_fields(self, restmachine_app):
        """Test that model command creates model with specified fields."""
        result = restmachine_app.add_model(
            "User", ["name:str", "email:str", "age:int", "is_active:bool"]
        )
        result.assert_success()

        User = restmachine_app.import_model("User")

        restmachine_app.assert_inherits_from(User, Model)
        restmachine_app.assert_model_has_fields(
            User, {"name": str, "email": str, "age": int, "is_active": bool}
        )

    def test_model_command_with_uuid_field(self, restmachine_app):
        """Test model generation with UUID field."""
        result = restmachine_app.add_model("Product", ["id:uuid", "name:str", "price:float"])
        result.assert_success()

        Product = restmachine_app.import_model("Product")

        restmachine_app.assert_inherits_from(Product, Model)
        restmachine_app.assert_model_has_fields(
            Product, {"id": str, "name": str, "price": float}  # UUID is stored as str
        )

        # Create an instance and verify id is auto-generated
        product = Product(name="Test", price=9.99)
        assert hasattr(product, "id"), "Product should have auto-generated id"
        assert isinstance(product.id, str), "id should be a string"
        assert len(product.id) == 36, "id should be UUID format (36 chars with dashes)"

    def test_model_command_with_datetime_field(self, restmachine_app):
        """Test model generation with datetime field."""
        result = restmachine_app.add_model(
            "Event", ["title:str", "start_time:datetime", "end_time:datetime"]
        )
        result.assert_success()

        Event = restmachine_app.import_model("Event")

        restmachine_app.assert_inherits_from(Event, Model)
        restmachine_app.assert_model_has_fields(
            Event, {"title": str, "start_time": datetime, "end_time": datetime}
        )

    def test_model_command_creates_fixture(self, restmachine_app):
        """Test that model command creates fixture file."""
        result = restmachine_app.add_model("User", ["name:str", "age:int"])
        result.assert_success()

        # Just verify fixture file was created with basic structure
        assert result.fixture_file is not None
        assert result.fixture_file.exists(), "Fixture file should be created"

    def test_model_command_skip_fixtures(self, restmachine_app):
        """Test model command with --skip-fixtures flag."""
        result = restmachine_app.add_model("User", ["name:str"], skip_fixtures=True)
        result.assert_success()

        # Fixture should not exist
        assert result.fixture_file is None

        # Model should still exist
        assert result.model_file.exists()

    def test_model_command_updates_models_init(self, restmachine_app):
        """Test that model command updates models/__init__.py."""
        restmachine_app.add_model("User", ["name:str"]).assert_success()

        # Check models/__init__.py was updated
        init_content = restmachine_app.read_file("models/__init__.py")
        assert "from models.user import User" in init_content

    def test_model_command_invalid_field_format(self, restmachine_app):
        """Test that model command rejects invalid field format."""
        result = restmachine_app.add_model("User", ["invalid_field"])

        assert not result.success
        assert "Invalid field specification" in result.output

    def test_model_command_invalid_field_type(self, restmachine_app):
        """Test that model command rejects unsupported types."""
        result = restmachine_app.add_model("User", ["name:string"])  # Wrong, should be 'str'

        assert not result.success
        assert "Unsupported type" in result.output

    def test_model_command_handles_camelcase(self, restmachine_app):
        """Test model with CamelCase input."""
        result = restmachine_app.add_model("BlogPost", ["title:str"])
        result.assert_success()

        # File should use snake_case
        assert restmachine_app.file_exists("models/blog_post.py")

        # Import and verify class name is PascalCase
        BlogPost = restmachine_app.import_model("BlogPost")

        restmachine_app.assert_inherits_from(BlogPost, Model)
        assert BlogPost.__name__ == "BlogPost"
        restmachine_app.assert_model_has_fields(BlogPost, {"title": str})

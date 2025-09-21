"""
Tests for Pydantic Optional field handling in schemas.
"""

import json
from typing import Optional

import pytest

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    Field = None


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestOptionalSchema:
    """Test how Pydantic handles Optional fields in schemas."""

    def test_optional_field_schema_generation(self):
        """Test that Optional fields are correctly represented in JSON schema."""

        class TestModel(BaseModel):
            name: str = Field(description="Required name")
            age: Optional[int] = Field(None, description="Optional age", gt=0)
            email: Optional[str] = Field(None, description="Optional email")

        schema = TestModel.model_json_schema()

        # Verify schema structure
        assert "properties" in schema
        assert "required" in schema

        # Check required fields
        assert "name" in schema["required"]
        assert "age" not in schema["required"]
        assert "email" not in schema["required"]

        # Check field properties
        properties = schema["properties"]

        # Required field should be straightforward
        assert properties["name"]["type"] == "string"
        assert properties["name"]["description"] == "Required name"

        # Optional fields should allow null or have default handling
        assert "age" in properties
        assert properties["age"]["description"] == "Optional age"

        assert "email" in properties
        assert properties["email"]["description"] == "Optional email"

    def test_model_fields_inspection(self):
        """Test inspection of model fields for required/optional status."""

        class TestModel(BaseModel):
            name: str = Field(description="Required name")
            age: Optional[int] = Field(None, description="Optional age", gt=0)
            email: Optional[str] = Field(None, description="Optional email")

        fields = TestModel.model_fields

        # Check field annotations and requirements
        assert "name" in fields
        assert fields["name"].annotation is str
        assert fields["name"].is_required()

        assert "age" in fields
        assert fields["age"].annotation is Optional[int]
        assert not fields["age"].is_required()

        assert "email" in fields
        assert fields["email"].annotation is Optional[str]
        assert not fields["email"].is_required()
        assert fields["email"].default is None

    def test_schema_json_serialization(self):
        """Test that the generated schema can be serialized to JSON."""

        class TestModel(BaseModel):
            name: str = Field(description="Required name")
            age: Optional[int] = Field(None, description="Optional age", gt=0)
            email: Optional[str] = Field(None, description="Optional email")

        schema = TestModel.model_json_schema()

        # Should be able to serialize to JSON without errors
        json_schema = json.dumps(schema, indent=2)
        assert isinstance(json_schema, str)
        assert len(json_schema) > 0

        # Should be able to parse it back
        parsed_schema = json.loads(json_schema)
        assert parsed_schema == schema

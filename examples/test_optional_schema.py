"""Test script to examine how Pydantic handles Optional fields in schemas."""

from typing import Optional
from pydantic import BaseModel, Field
import json

class TestModel(BaseModel):
    name: str = Field(description="Required name")
    age: Optional[int] = Field(description="Optional age", gt=0)
    email: Optional[str] = Field(None, description="Optional email")

# Test Pydantic's schema generation
schema = TestModel.model_json_schema()
print("Pydantic generated schema:")
print(json.dumps(schema, indent=2))

# Test field info
print("\nModel fields:")
for field_name, field_info in TestModel.model_fields.items():
    print(f"  {field_name}: {field_info}")
    print(f"    annotation: {field_info.annotation}")
    print(f"    default: {field_info.default}")
    print(f"    is_required: {field_info.is_required()}")
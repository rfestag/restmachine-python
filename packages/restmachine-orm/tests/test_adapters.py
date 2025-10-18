"""
Tests for model adapters.

Tests the adapter interface and implementations for different backends.
"""

import pytest
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends.adapters import (
    ModelAdapter,
    OpenSearchAdapter,
    InMemoryAdapter,
    CompositeAdapter,
)


class User(Model):
    """Test user model."""
    id: str = Field(primary_key=True)
    email: str
    name: str
    age: int


class TestOpenSearchAdapter:
    """Test OpenSearchAdapter functionality."""

    def test_default_init(self):
        """Test OpenSearchAdapter with default initialization."""
        adapter = OpenSearchAdapter()
        assert adapter.id_field == "_id"
        assert adapter.include_type is True
        assert adapter.type_field == "_type"

    def test_custom_init(self):
        """Test OpenSearchAdapter with custom parameters."""
        adapter = OpenSearchAdapter(
            id_field="custom_id",
            include_type=False,
            type_field="custom_type"
        )
        assert adapter.id_field == "custom_id"
        assert adapter.include_type is False
        assert adapter.type_field == "custom_type"

    def test_model_to_storage_with_type(self):
        """Test model_to_storage includes type field when configured."""
        adapter = OpenSearchAdapter(include_type=True)
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        result = adapter.model_to_storage(user)

        assert result["id"] == "123"
        assert result["email"] == "alice@example.com"
        assert result["name"] == "Alice"
        assert result["age"] == 30
        assert result["_type"] == "User"

    def test_model_to_storage_without_type(self):
        """Test model_to_storage excludes type field when not configured."""
        adapter = OpenSearchAdapter(include_type=False)
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        result = adapter.model_to_storage(user)

        assert result["id"] == "123"
        assert result["email"] == "alice@example.com"
        assert "_type" not in result

    def test_model_to_storage_custom_type_field(self):
        """Test model_to_storage with custom type field name."""
        adapter = OpenSearchAdapter(include_type=True, type_field="entity_type")
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        result = adapter.model_to_storage(user)

        assert result["entity_type"] == "User"
        assert "_type" not in result

    def test_storage_to_model_removes_opensearch_fields(self):
        """Test storage_to_model removes OpenSearch-specific fields."""
        adapter = OpenSearchAdapter()
        data = {
            "id": "123",
            "email": "alice@example.com",
            "name": "Alice",
            "age": 30,
            "_type": "User",
            "_score": 1.5,
            "_index": "users",
            "_source": {"id": "123"}
        }

        result = adapter.storage_to_model(User, data)

        assert result["id"] == "123"
        assert result["email"] == "alice@example.com"
        assert "_type" not in result
        assert "_score" not in result
        assert "_index" not in result
        assert "_source" not in result

    def test_storage_to_model_custom_type_field(self):
        """Test storage_to_model removes custom type field."""
        adapter = OpenSearchAdapter(type_field="entity_type")
        data = {
            "id": "123",
            "email": "alice@example.com",
            "entity_type": "User"
        }

        result = adapter.storage_to_model(User, data)

        assert result["id"] == "123"
        assert "entity_type" not in result

    def test_get_primary_key_value(self):
        """Test get_primary_key_value extracts primary key."""
        adapter = OpenSearchAdapter()
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        pk = adapter.get_primary_key_value(user)

        assert pk == "123"

    def test_get_primary_key_value_no_pk_field_error(self):
        """Test get_primary_key_value raises error when no primary key field."""
        adapter = OpenSearchAdapter()

        # Model without primary key
        class NoPKModel(Model):
            name: str

        instance = NoPKModel(name="test")

        with pytest.raises(ValueError, match="No primary key field defined"):
            adapter.get_primary_key_value(instance)

    def test_get_entity_type(self):
        """Test get_entity_type returns class name."""
        adapter = OpenSearchAdapter()
        assert adapter.get_entity_type(User) == "User"


class TestInMemoryAdapter:
    """Test InMemoryAdapter functionality."""

    def test_model_to_storage_returns_dict(self):
        """Test model_to_storage returns model data as-is."""
        adapter = InMemoryAdapter()
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        result = adapter.model_to_storage(user)

        assert result["id"] == "123"
        assert result["email"] == "alice@example.com"
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_storage_to_model_returns_dict(self):
        """Test storage_to_model returns data as-is."""
        adapter = InMemoryAdapter()
        data = {"id": "123", "email": "alice@example.com", "name": "Alice", "age": 30}

        result = adapter.storage_to_model(User, data)

        assert result == data
        # Should be a new dict, not the same object
        assert result is not data

    def test_get_primary_key_value(self):
        """Test get_primary_key_value extracts primary key."""
        adapter = InMemoryAdapter()
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        pk = adapter.get_primary_key_value(user)

        assert pk == "123"

    def test_get_primary_key_value_no_pk_field_error(self):
        """Test get_primary_key_value raises error when no primary key field."""
        adapter = InMemoryAdapter()

        # Model without primary key
        class NoPKModel(Model):
            name: str

        instance = NoPKModel(name="test")

        with pytest.raises(ValueError, match="No primary key field defined"):
            adapter.get_primary_key_value(instance)


class TestCompositeAdapter:
    """Test CompositeAdapter functionality."""

    def test_init(self):
        """Test CompositeAdapter initialization."""
        search_adapter = OpenSearchAdapter()
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        assert composite.search_adapter is search_adapter
        assert composite.storage_adapter is storage_adapter

    def test_model_to_storage_uses_storage_adapter(self):
        """Test model_to_storage delegates to storage adapter."""
        search_adapter = OpenSearchAdapter(include_type=True)
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        user = User(id="123", email="alice@example.com", name="Alice", age=30)
        result = composite.model_to_storage(user)

        # Should use storage_adapter (InMemoryAdapter)
        # InMemoryAdapter just returns model_dump(), no _type field
        assert result["id"] == "123"
        assert "_type" not in result

    def test_storage_to_model_uses_storage_adapter(self):
        """Test storage_to_model delegates to storage adapter."""
        search_adapter = OpenSearchAdapter()
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        data = {"id": "123", "email": "alice@example.com", "name": "Alice", "age": 30}
        result = composite.storage_to_model(User, data)

        # Should use storage_adapter (InMemoryAdapter)
        assert result == data

    def test_get_primary_key_value_uses_storage_adapter(self):
        """Test get_primary_key_value delegates to storage adapter."""
        search_adapter = OpenSearchAdapter()
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        user = User(id="123", email="alice@example.com", name="Alice", age=30)
        pk = composite.get_primary_key_value(user)

        # Should use storage_adapter
        assert pk == "123"

    def test_model_to_search_uses_search_adapter(self):
        """Test model_to_search delegates to search adapter."""
        search_adapter = OpenSearchAdapter(include_type=True)
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        user = User(id="123", email="alice@example.com", name="Alice", age=30)
        result = composite.model_to_search(user)

        # Should use search_adapter (OpenSearchAdapter)
        assert result["id"] == "123"
        assert result["_type"] == "User"

    def test_search_to_model_uses_search_adapter(self):
        """Test search_to_model delegates to search adapter."""
        search_adapter = OpenSearchAdapter()
        storage_adapter = InMemoryAdapter()
        composite = CompositeAdapter(search_adapter, storage_adapter)

        data = {
            "id": "123",
            "email": "alice@example.com",
            "_type": "User",
            "_score": 1.5
        }
        result = composite.search_to_model(User, data)

        # Should use search_adapter (OpenSearchAdapter) which removes _type and _score
        assert result["id"] == "123"
        assert "_type" not in result
        assert "_score" not in result


class TestModelAdapterInterface:
    """Test ModelAdapter abstract interface."""

    def test_get_index_keys_default_implementation(self):
        """Test get_index_keys default implementation returns empty dict."""
        # Use a concrete adapter to test the default implementation
        adapter = InMemoryAdapter()
        user = User(id="123", email="alice@example.com", name="Alice", age=30)

        result = adapter.get_index_keys(user)

        assert result == {}

    def test_get_entity_type_default_implementation(self):
        """Test get_entity_type default implementation returns class name."""
        adapter = InMemoryAdapter()

        result = adapter.get_entity_type(User)

        assert result == "User"


class TestAdapterEdgeCases:
    """Test edge cases and error scenarios."""

    def test_opensearch_adapter_with_numeric_id(self):
        """Test OpenSearchAdapter converts numeric IDs to strings."""
        adapter = OpenSearchAdapter()

        class NumericIDModel(Model):
            id: int = Field(primary_key=True)
            name: str

        instance = NumericIDModel(id=123, name="test")
        pk = adapter.get_primary_key_value(instance)

        # Should be converted to string
        assert pk == "123"
        assert isinstance(pk, str)

    def test_storage_to_model_preserves_all_fields(self):
        """Test storage_to_model preserves all non-special fields."""
        adapter = OpenSearchAdapter()
        data = {
            "id": "123",
            "email": "alice@example.com",
            "name": "Alice",
            "age": 30,
            "custom_field": "value",
            "_type": "User"
        }

        result = adapter.storage_to_model(User, data)

        # All regular fields should be preserved
        assert result["id"] == "123"
        assert result["custom_field"] == "value"
        # But _type should be removed
        assert "_type" not in result

    def test_inmemory_adapter_storage_to_model_creates_copy(self):
        """Test InMemoryAdapter.storage_to_model creates a new dict."""
        adapter = InMemoryAdapter()
        data = {"id": "123", "name": "Alice"}

        result = adapter.storage_to_model(User, data)

        # Should be a copy, not the same object
        assert result is not data
        # But with same content
        assert result == data

        # Modifying result should not affect original
        result["new_field"] = "value"
        assert "new_field" not in data

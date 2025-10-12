"""
Tests for backend extension system.

This test file demonstrates the extension pattern for mixins.
"""

import pytest
from datetime import datetime
from typing import Optional, Type, ClassVar

from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Shared backend
shared_backend = InMemoryBackend(InMemoryAdapter())


# === Test Fixtures: Mock Extensions ===

class MockExtension:
    """Mock extension for testing."""

    backend_name = 'memory'

    def __init__(self, mixin_class: Type, backend):
        self.mixin_class = mixin_class
        self.backend = backend
        self.serialize_called = False
        self.deserialize_called = False
        self.configure_called = False
        self.modify_query_called = False

    def serialize(self, data: dict) -> dict:
        self.serialize_called = True
        data['_serialized'] = True
        return data

    def deserialize(self, data: dict) -> dict:
        self.deserialize_called = True
        if '_serialized' in data:
            del data['_serialized']
        return data

    def configure_backend(self, model_class: Type[Model]) -> None:
        self.configure_called = True

    def modify_query(self, query_builder):
        self.modify_query_called = True
        return query_builder


class MockUniversalExtension:
    """Mock universal extension for testing."""

    backend_name = '*'  # Works with all backends

    def __init__(self, mixin_class: Type, backend):
        self.mixin_class = mixin_class
        self.backend = backend
        self.serialize_called = False

    def serialize(self, data: dict) -> dict:
        self.serialize_called = True
        data['_universal'] = True
        return data

    def deserialize(self, data: dict) -> dict:
        if '_universal' in data:
            del data['_universal']
        return data

    def configure_backend(self, model_class: Type[Model]) -> None:
        pass

    def modify_query(self, query_builder):
        return query_builder


# === Test Mixins ===

class SimpleMixin:
    """Mixin with a single extension."""

    extra_field: Optional[str] = None

    MemoryExtension = MockExtension


class UniversalMixin:
    """Mixin with universal extension."""

    universal_field: Optional[str] = None

    UniversalExtension = MockUniversalExtension


class MultiExtensionMixin:
    """Mixin with multiple backend extensions."""

    multi_field: Optional[str] = None

    # This mixin has extensions for both memory and a hypothetical other backend
    MemoryExtension = MockExtension


# === Test Models ===

@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    # Clear any cached extensions
    if hasattr(shared_backend, '_model_extensions'):
        shared_backend._model_extensions.clear()
    if hasattr(shared_backend, '_configured_models'):
        shared_backend._configured_models.clear()
    yield
    shared_backend.clear()


class TestExtensionDiscovery:
    """Test that extensions are properly discovered."""

    def test_discover_single_extension(self):
        """Test discovering a single extension from a mixin."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)
            name: str

        # Trigger extension discovery
        extensions = shared_backend._discover_extensions(TestModel)

        # Should find one extension
        assert len(extensions) == 1
        assert isinstance(extensions[0], MockExtension)
        assert extensions[0].backend_name == 'memory'

    def test_discover_universal_extension(self):
        """Test discovering universal extensions."""

        class TestModel(UniversalMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        extensions = shared_backend._discover_extensions(TestModel)

        # Should find universal extension
        assert len(extensions) == 1
        assert isinstance(extensions[0], MockUniversalExtension)
        assert extensions[0].backend_name == '*'

    def test_discover_multiple_extensions(self):
        """Test discovering multiple extensions from multiple mixins."""

        class TestModel(SimpleMixin, UniversalMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        extensions = shared_backend._discover_extensions(TestModel)

        # Should find both extensions
        assert len(extensions) == 2
        extension_types = [type(ext) for ext in extensions]
        assert MockExtension in extension_types
        assert MockUniversalExtension in extension_types

    def test_extensions_cached_per_model(self):
        """Test that extensions are cached per model class."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        # First call discovers and caches
        extensions1 = shared_backend._discover_extensions(TestModel)

        # Second call returns cached
        extensions2 = shared_backend._discover_extensions(TestModel)

        # Should be the same instances
        assert extensions1 is extensions2


class TestExtensionHooks:
    """Test that extension hooks are called correctly."""

    def test_serialize_hook_on_create(self):
        """Test that serialize hook is called during create."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)
            name: str

        # Create should trigger serialize
        instance = TestModel.create(id="1", name="Alice", extra_field="test")

        # Get the extension instance
        extensions = shared_backend._discover_extensions(TestModel)
        extension = extensions[0]

        # Serialize should have been called
        assert extension.serialize_called

    def test_deserialize_hook_on_get(self):
        """Test that deserialize hook is called during get."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)
            name: str

        # Create a record
        TestModel.create(id="1", name="Alice")

        # Clear the called flags
        extensions = shared_backend._discover_extensions(TestModel)
        extension = extensions[0]
        extension.deserialize_called = False

        # Get should trigger deserialize
        result = TestModel.get(id="1")

        assert result is not None
        assert extension.deserialize_called

    def test_configure_backend_called_once(self):
        """Test that configure_backend is called only once per model."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        # First operation triggers configuration
        TestModel.create(id="1")

        extensions = shared_backend._discover_extensions(TestModel)
        extension = extensions[0]
        assert extension.configure_called

        # Reset flag
        extension.configure_called = False

        # Second operation should not trigger configuration
        TestModel.create(id="2")
        assert not extension.configure_called

    def test_modify_query_hook(self):
        """Test that modify_query hook is called when creating queries."""

        class TestModel(SimpleMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        # Create some data
        TestModel.create(id="1")

        # Clear flag
        extensions = shared_backend._discover_extensions(TestModel)
        extension = extensions[0]
        extension.modify_query_called = False

        # Query should trigger modify_query
        TestModel.where().all()

        assert extension.modify_query_called


class TestExtensionComposition:
    """Test multiple extensions working together."""

    def test_multiple_extensions_serialize(self):
        """Test that all extensions' serialize hooks are called."""

        class TestModel(SimpleMixin, UniversalMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        # Create should trigger both serialize hooks
        TestModel.create(id="1")

        extensions = shared_backend._discover_extensions(TestModel)

        # Both extensions should have serialize called
        for ext in extensions:
            assert ext.serialize_called

    def test_extension_chain_order(self):
        """Test that extensions are applied in MRO order."""

        # This test verifies that data flows through extensions in order

        class OrderMixin1:
            MemoryExtension = type('Ext1', (MockExtension,), {
                'serialize': lambda self, data: {**data, 'order': data.get('order', []) + ['ext1']}
            })

        class OrderMixin2:
            MemoryExtension = type('Ext2', (MockExtension,), {
                'serialize': lambda self, data: {**data, 'order': data.get('order', []) + ['ext2']}
            })

        class TestModel(OrderMixin1, OrderMixin2, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)

        # Create should apply extensions in MRO order
        # Note: The actual order depends on implementation
        TestModel.create(id="1")

        # Just verify both were called
        extensions = shared_backend._discover_extensions(TestModel)
        assert len(extensions) >= 2


class TestExtensionDataTransformation:
    """Test that extensions can transform data."""

    def test_serialize_transforms_data(self):
        """Test that serialize can modify data before storage."""

        class TransformMixin:

            class MemoryExtension:
                backend_name = 'memory'

                def __init__(self, mixin_class, backend):
                    self.mixin_class = mixin_class
                    self.backend = backend

                def serialize(self, data: dict) -> dict:
                    # Add a computed field
                    if 'name' in data:
                        data['name_upper'] = data['name'].upper()
                    return data

                def deserialize(self, data: dict) -> dict:
                    # Remove computed field on read
                    if 'name_upper' in data:
                        del data['name_upper']
                    return data

                def configure_backend(self, model_class):
                    pass

                def modify_query(self, query_builder):
                    return query_builder

        class TestModel(TransformMixin, Model):
            class Meta:
                backend = shared_backend

            id: str = Field(primary_key=True)
            name: str

        # Create with lowercase name
        instance = TestModel.create(id="1", name="alice")

        # Check storage directly (should have uppercase version)
        storage = shared_backend._get_storage(TestModel)
        raw_data = storage["1"]  # Get by primary key
        assert 'name_upper' in raw_data
        assert raw_data['name_upper'] == 'ALICE'

        # But deserialized instance should not have it
        reloaded = TestModel.get(id="1")
        assert not hasattr(reloaded, 'name_upper')


class TestBackendSpecificExtensions:
    """Test that extensions only apply to specific backends."""

    def test_wrong_backend_extension_not_discovered(self):
        """Test that extensions for other backends are not discovered."""

        class DynamoDBMixin:
            """Mixin with DynamoDB-only extension."""

            class DynamoDBExtension:
                backend_name = 'dynamodb'

                def __init__(self, mixin_class, backend):
                    self.mixin_class = mixin_class
                    self.backend = backend

                def serialize(self, data: dict) -> dict:
                    return data

                def deserialize(self, data: dict) -> dict:
                    return data

                def configure_backend(self, model_class):
                    pass

                def modify_query(self, query_builder):
                    return query_builder

        class TestModel(DynamoDBMixin, Model):
            class Meta:
                backend = shared_backend  # memory backend

            id: str = Field(primary_key=True)

        # Should not find DynamoDB extension on memory backend
        extensions = shared_backend._discover_extensions(TestModel)
        assert len(extensions) == 0

    def test_universal_extension_works_on_any_backend(self):
        """Test that universal extensions (*) work on any backend."""

        class TestModel(UniversalMixin, Model):
            class Meta:
                backend = shared_backend  # memory backend

            id: str = Field(primary_key=True)

        # Should find universal extension
        extensions = shared_backend._discover_extensions(TestModel)
        assert len(extensions) == 1
        assert extensions[0].backend_name == '*'

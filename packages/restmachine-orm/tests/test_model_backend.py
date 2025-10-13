"""
Tests for model_backend configuration patterns.

This test file demonstrates the new recommended patterns for configuring backends.
"""

import pytest
from typing import ClassVar

from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Shared backend instances
backend1 = InMemoryBackend(InMemoryAdapter())
backend2 = InMemoryBackend(InMemoryAdapter())


class TestModelBackendClassVar:
    """Test the ClassVar model_backend pattern (recommended)."""

    def test_classvar_pattern_basic_crud(self):
        """Test basic CRUD operations with ClassVar model_backend."""
        class User(Model):
            model_backend: ClassVar[InMemoryBackend] = backend1

            id: str = Field(primary_key=True)
            name: str

        # Create
        user = User.create(id="1", name="Alice")
        assert user.id == "1"
        assert user.name == "Alice"

        # Read
        loaded = User.get(id="1")
        assert loaded is not None
        assert loaded.name == "Alice"

        # Update
        loaded.name = "Alice Updated"
        loaded.save()
        reloaded = User.get(id="1")
        assert reloaded.name == "Alice Updated"

        # Delete
        assert loaded.delete()
        assert User.get(id="1") is None

        # Cleanup
        backend1.clear()

    def test_classvar_pattern_with_mixins(self):
        """Test that model_backend works with mixins."""
        from restmachine_orm import TimestampMixin
        from datetime import datetime

        class Document(TimestampMixin, Model):
            model_backend: ClassVar[InMemoryBackend] = backend1

            id: str = Field(primary_key=True)
            title: str

        doc = Document.create(id="1", title="Test")

        # TimestampMixin should work
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)

        # Cleanup
        backend1.clear()


class TestModelBackendClassParameter:
    """Test the class parameter model_backend pattern."""

    def test_class_parameter_pattern_basic_crud(self):
        """Test basic CRUD operations with class parameter model_backend."""
        class User(Model, model_backend=backend2):
            id: str = Field(primary_key=True)
            name: str

        # Create
        user = User.create(id="1", name="Bob")
        assert user.id == "1"
        assert user.name == "Bob"

        # Read
        loaded = User.get(id="1")
        assert loaded is not None
        assert loaded.name == "Bob"

        # Cleanup
        backend2.clear()

    def test_class_parameter_with_mixins(self):
        """Test that class parameter model_backend works with mixins."""
        from restmachine_orm import TimestampMixin
        from datetime import datetime

        class Document(TimestampMixin, Model, model_backend=backend2):
            id: str = Field(primary_key=True)
            title: str

        doc = Document.create(id="1", title="Test")

        # TimestampMixin should work
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)

        # Cleanup
        backend2.clear()


class TestFieldNamedBackend:
    """Test that users can safely use 'backend' as a field name."""

    def test_backend_field_name_no_conflict(self):
        """Test that model_backend doesn't conflict with a field named 'backend'."""
        class Deployment(Model):
            model_backend: ClassVar[InMemoryBackend] = backend1

            id: str = Field(primary_key=True)
            backend: str  # User's field - should work fine!
            version: str

        # Create a deployment with 'backend' as a data field
        deployment = Deployment.create(
            id="1",
            backend="production",  # This is the user's field
            version="1.0.0"
        )

        assert deployment.backend == "production"
        assert deployment.version == "1.0.0"

        # Verify it persists correctly
        loaded = Deployment.get(id="1")
        assert loaded is not None
        assert loaded.backend == "production"

        # Cleanup
        backend1.clear()


class TestNoBackendConfigured:
    """Test error handling when no backend is configured."""

    def test_missing_backend_error_message(self):
        """Test that helpful error is raised when backend is not configured."""
        # Use a unique class name to avoid any potential caching issues
        class UserNoBackend(Model):
            id: str = Field(primary_key=True)
            name: str

        # Verify that model_backend is indeed None
        assert UserNoBackend.model_backend is None

        with pytest.raises(RuntimeError) as exc_info:
            UserNoBackend.create(id="1", name="Test")

        # Check error message mentions the new pattern
        assert "model_backend" in str(exc_info.value)
        assert "UserNoBackend" in str(exc_info.value)

"""
Tests for Model CRUD operations.

Tests create, save, update, delete and their callback execution.
"""

import pytest
from typing import ClassVar, Optional
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.models.decorators import before_save, after_save


shared_backend = InMemoryBackend()


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


class TestModelCreateWithCallbacks:
    """Test Model.create() with before/after save callbacks."""

    def test_create_calls_before_save_callback(self):
        """Test create() calls @before_save callbacks."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            normalized_name: Optional[str] = None

            @before_save
            def normalize_name(self):
                call_log.append("before_save")
                self.normalized_name = self.name.upper()

        user = User.create(id="1", name="Alice")

        assert "before_save" in call_log
        assert user.normalized_name == "ALICE"

    def test_create_calls_after_save_callback(self):
        """Test create() calls @after_save callbacks."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

            @after_save
            def log_creation(self):
                call_log.append(f"created_{self.id}")

        user = User.create(id="1", name="Alice")

        assert "created_1" in call_log

    def test_create_calls_multiple_callbacks_in_order(self):
        """Test create() calls multiple callbacks in definition order."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

            @before_save
            def first_callback(self):
                call_log.append("first")

            @before_save
            def second_callback(self):
                call_log.append("second")

            @after_save
            def third_callback(self):
                call_log.append("third")

        User.create(id="1", name="Alice")

        assert call_log == ["first", "second", "third"]


class TestModelSaveInstance:
    """Test instance.save() method."""

    def test_save_new_instance_creates_record(self):
        """Test save() on new instance creates it in backend."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User(id="1", name="Alice")
        result = user.save()

        assert result is user
        assert user._is_persisted is True

        # Verify it was saved
        loaded = User.get(id="1")
        assert loaded is not None
        assert loaded.name == "Alice"

    def test_save_existing_instance_updates_record(self):
        """Test save() on existing instance updates it."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            age: int

        # Create initial record
        user = User.create(id="1", name="Alice", age=30)

        # Modify and save
        user.age = 31
        user.save()

        # Verify update
        loaded = User.get(id="1")
        assert loaded.age == 31

    def test_save_calls_before_save_callback(self):
        """Test save() calls @before_save callbacks."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            updated_count: int = 0

            @before_save
            def increment_counter(self):
                call_log.append("before_save")
                self.updated_count += 1

        user = User(id="1", name="Alice")
        user.save()

        assert "before_save" in call_log
        assert user.updated_count == 1

    def test_save_calls_after_save_callback(self):
        """Test save() calls @after_save callbacks."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

            @after_save
            def log_save(self):
                call_log.append(f"saved_{self.id}")

        user = User(id="1", name="Alice")
        user.save()

        assert "saved_1" in call_log


class TestModelSaveUpdate:
    """Test Model save() for updates."""

    def test_save_on_existing_instance_updates_record(self):
        """Test save() on persisted instance updates it."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            age: int

        # Create initial record
        user = User.create(id="1", name="Alice", age=30)

        # Modify and save (update path)
        user.age = 31
        user.save()

        # Verify update
        loaded = User.get(id="1")
        assert loaded.age == 31
        assert loaded.name == "Alice"  # Unchanged field preserved

    def test_save_update_calls_callbacks(self):
        """Test save() on existing record calls callbacks."""
        call_log = []

        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

            @before_save
            def before_callback(self):
                call_log.append("before")

            @after_save
            def after_callback(self):
                call_log.append("after")

        user = User.create(id="1", name="Alice")
        call_log.clear()

        # Modify and save (update path)
        user.name = "Alice Updated"
        user.save()

        assert call_log == ["before", "after"]


class TestModelDelete:
    """Test Model.delete() instance method."""

    def test_delete_instance_method_removes_record(self):
        """Test delete() instance method removes record."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")

        # Delete using instance method
        result = user.delete()
        assert result is True

        # Verify deletion
        loaded = User.get(id="1")
        assert loaded is None

    def test_delete_created_instance(self):
        """Test deleting a created instance."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            age: int

        user = User.create(id="1", name="Alice", age=30)

        # Verify it exists
        assert User.get(id="1") is not None

        # Delete it
        result = user.delete()
        assert result is True

        # Verify it's gone
        assert User.get(id="1") is None

    def test_delete_saved_instance(self):
        """Test deleting an instance that was saved."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User(id="1", name="Alice")
        user.save()

        # Delete it
        result = user.delete()
        assert result is True

        # Verify it's gone
        assert User.get(id="1") is None


class TestModelGetAttribute:
    """Test Model __getattribute__ for QueryField access."""

    def test_access_regular_field_returns_value(self):
        """Test accessing regular field returns its value."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User(id="1", name="Alice")
        assert user.name == "Alice"

    def test_access_model_field_on_class_returns_query_field(self):
        """Test accessing field on class returns QueryField."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            age: int

        # Access field on class should return QueryField
        field = User.name
        assert hasattr(field, 'field_name')
        assert field.field_name == "name"
        assert hasattr(field, 'model_class')
        assert field.model_class is User


class TestModelValidation:
    """Test model validation during save/create."""

    def test_create_validates_model(self):
        """Test create() validates model before saving."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            age: int  # Required field

        # Should raise validation error for missing required field
        with pytest.raises(Exception):  # Pydantic ValidationError
            User.create(id="1", name="Alice")  # Missing age

    def test_create_validates_field_types(self):
        """Test create() validates field types."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            age: int

        # Should raise validation error for wrong type
        with pytest.raises(Exception):  # Pydantic ValidationError
            User.create(id="1", age="not an integer")  # type: ignore


class TestModelPersistenceFlag:
    """Test _is_persisted flag tracking."""

    def test_new_instance_not_persisted(self):
        """Test new instance has _is_persisted=False."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User(id="1", name="Alice")
        assert user._is_persisted is False

    def test_created_instance_is_persisted(self):
        """Test created instance has _is_persisted=True."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")
        assert user._is_persisted is True

    def test_saved_instance_is_persisted(self):
        """Test saved instance has _is_persisted=True."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User(id="1", name="Alice")
        user.save()
        assert user._is_persisted is True

    def test_loaded_instance_is_persisted(self):
        """Test loaded instance has _is_persisted=True."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        User.create(id="1", name="Alice")
        loaded = User.get(id="1")

        assert loaded is not None
        assert loaded._is_persisted is True

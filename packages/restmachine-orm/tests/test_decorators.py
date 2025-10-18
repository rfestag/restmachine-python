"""
Tests for model decorators.

Tests decorators for composite keys, GSI keys, and callback hooks.
"""

import pytest
from typing import ClassVar, Optional
from restmachine_orm import Model, Field
from restmachine_orm.models.decorators import (
    partition_key,
    sort_key,
    gsi_partition_key,
    gsi_sort_key,
    is_partition_key_method,
    is_sort_key_method,
    is_gsi_partition_key_method,
    is_gsi_sort_key_method,
    before_save,
    after_save,
    BeforeSaveCallback,
    AfterSaveCallback,
)
from restmachine_orm.backends import InMemoryBackend


shared_backend = InMemoryBackend()


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


class TestPartitionKeyDecorator:
    """Test @partition_key decorator."""

    def test_partition_key_decorator_marks_method(self):
        """Test @partition_key marks method with metadata."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)
            todo_id: str

            @partition_key
            def pk(self) -> str:
                return f"USER#{self.user_id}"

        # Check metadata is set
        assert hasattr(TodoItem.pk, "_is_partition_key")
        assert TodoItem.pk._is_partition_key is True
        assert TodoItem.pk._key_name == "pk"

    def test_partition_key_method_callable(self):
        """Test @partition_key decorated method is callable."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)
            todo_id: str

            @partition_key
            def pk(self) -> str:
                return f"USER#{self.user_id}"

        item = TodoItem(user_id="alice", todo_id="1")
        assert item.pk() == "USER#alice"

    def test_partition_key_wraps_function_name(self):
        """Test @partition_key preserves function name."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)

            @partition_key
            def pk(self) -> str:
                return f"USER#{self.user_id}"

        assert TodoItem.pk.__name__ == "pk"

    def test_is_partition_key_method(self):
        """Test is_partition_key_method helper."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)

            @partition_key
            def pk(self) -> str:
                return f"USER#{self.user_id}"

            def regular_method(self) -> str:
                return "not a key"

        assert is_partition_key_method(TodoItem.pk) is True
        assert is_partition_key_method(TodoItem.regular_method) is False


class TestSortKeyDecorator:
    """Test @sort_key decorator."""

    def test_sort_key_decorator_marks_method(self):
        """Test @sort_key marks method with metadata."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)
            todo_id: str

            @sort_key
            def sk(self) -> str:
                return f"TODO#{self.todo_id}"

        assert hasattr(TodoItem.sk, "_is_sort_key")
        assert TodoItem.sk._is_sort_key is True
        assert TodoItem.sk._key_name == "sk"

    def test_sort_key_method_callable(self):
        """Test @sort_key decorated method is callable."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)
            todo_id: str

            @sort_key
            def sk(self) -> str:
                return f"TODO#{self.todo_id}"

        item = TodoItem(user_id="alice", todo_id="1")
        assert item.sk() == "TODO#1"

    def test_is_sort_key_method(self):
        """Test is_sort_key_method helper."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)

            @sort_key
            def sk(self) -> str:
                return f"TODO#{self.user_id}"

            def regular_method(self) -> str:
                return "not a key"

        assert is_sort_key_method(TodoItem.sk) is True
        assert is_sort_key_method(TodoItem.regular_method) is False


class TestGSIPartitionKeyDecorator:
    """Test @gsi_partition_key decorator."""

    def test_gsi_partition_key_decorator_marks_method(self):
        """Test @gsi_partition_key marks method with metadata."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            email: str

            @gsi_partition_key("EmailIndex")
            def gsi_pk_email(self) -> str:
                return self.email

        assert hasattr(User.gsi_pk_email, "_is_gsi_partition_key")
        assert User.gsi_pk_email._is_gsi_partition_key is True
        assert User.gsi_pk_email._gsi_name == "EmailIndex"
        assert User.gsi_pk_email._key_name == "gsi_pk_email"

    def test_gsi_partition_key_method_callable(self):
        """Test @gsi_partition_key decorated method is callable."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            email: str

            @gsi_partition_key("EmailIndex")
            def gsi_pk_email(self) -> str:
                return self.email

        user = User(id="123", email="alice@example.com")
        assert user.gsi_pk_email() == "alice@example.com"

    def test_is_gsi_partition_key_method(self):
        """Test is_gsi_partition_key_method helper."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            email: str

            @gsi_partition_key("EmailIndex")
            def gsi_pk_email(self) -> str:
                return self.email

            def regular_method(self) -> str:
                return "not a key"

        assert is_gsi_partition_key_method(User.gsi_pk_email) is True
        assert is_gsi_partition_key_method(User.regular_method) is False


class TestGSISortKeyDecorator:
    """Test @gsi_sort_key decorator."""

    def test_gsi_sort_key_decorator_marks_method(self):
        """Test @gsi_sort_key marks method with metadata."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            email: str
            created_at: str

            @gsi_sort_key("EmailIndex")
            def gsi_sk_email(self) -> str:
                return self.created_at

        assert hasattr(User.gsi_sk_email, "_is_gsi_sort_key")
        assert User.gsi_sk_email._is_gsi_sort_key is True
        assert User.gsi_sk_email._gsi_name == "EmailIndex"
        assert User.gsi_sk_email._key_name == "gsi_sk_email"

    def test_gsi_sort_key_method_callable(self):
        """Test @gsi_sort_key decorated method is callable."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            created_at: str

            @gsi_sort_key("EmailIndex")
            def gsi_sk_email(self) -> str:
                return self.created_at

        user = User(id="123", created_at="2025-01-15")
        assert user.gsi_sk_email() == "2025-01-15"

    def test_is_gsi_sort_key_method(self):
        """Test is_gsi_sort_key_method helper."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            created_at: str

            @gsi_sort_key("EmailIndex")
            def gsi_sk_email(self) -> str:
                return self.created_at

            def regular_method(self) -> str:
                return "not a key"

        assert is_gsi_sort_key_method(User.gsi_sk_email) is True
        assert is_gsi_sort_key_method(User.regular_method) is False


class TestBeforeSaveCallback:
    """Test @before_save callback decorator."""

    def test_before_save_callback_descriptor_init(self):
        """Test BeforeSaveCallback descriptor initialization."""
        def dummy_func(self):
            pass

        callback = BeforeSaveCallback(dummy_func)
        assert callback.func is dummy_func

    def test_before_save_callback_get_instance(self):
        """Test BeforeSaveCallback.__get__ returns bound method."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            call_count: int = 0

            @before_save
            def increment_count(self):
                self.call_count += 1

        user = User(id="123", name="Alice")
        # Get the descriptor's bound method
        bound_method = user.increment_count

        # Should be callable
        assert callable(bound_method)

    def test_before_save_callback_get_class(self):
        """Test BeforeSaveCallback.__get__ on class returns function."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)

            @before_save
            def callback(self):
                pass

        # Accessing from class should return the original function
        func = User.callback
        assert callable(func)


class TestAfterSaveCallback:
    """Test @after_save callback decorator."""

    def test_after_save_callback_descriptor_init(self):
        """Test AfterSaveCallback descriptor initialization."""
        def dummy_func(self):
            pass

        callback = AfterSaveCallback(dummy_func)
        assert callback.func is dummy_func

    def test_after_save_callback_get_instance(self):
        """Test AfterSaveCallback.__get__ returns bound method."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str
            call_count: int = 0

            @after_save
            def increment_count(self):
                self.call_count += 1

        user = User(id="123", name="Alice")
        bound_method = user.increment_count

        assert callable(bound_method)

    def test_after_save_callback_get_class(self):
        """Test AfterSaveCallback.__get__ on class returns function."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)

            @after_save
            def callback(self):
                pass

        # Accessing from class should return the original function
        func = User.callback
        assert callable(func)


class TestCallbackRegistration:
    """Test callback registration on model classes."""

    def test_before_save_registers_callback(self):
        """Test @before_save registers callback in _before_save_callbacks."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)

            @before_save
            def callback1(self):
                pass

            @before_save
            def callback2(self):
                pass

        # Should have registered both callbacks
        assert hasattr(User, "_before_save_callbacks")
        assert len(User._before_save_callbacks) == 2

    def test_after_save_registers_callback(self):
        """Test @after_save registers callback in _after_save_callbacks."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)

            @after_save
            def callback1(self):
                pass

            @after_save
            def callback2(self):
                pass

        # Should have registered both callbacks
        assert hasattr(User, "_after_save_callbacks")
        assert len(User._after_save_callbacks) == 2

    def test_callbacks_not_shared_with_parent(self):
        """Test subclass has its own callback list, not shared with parent."""
        class Parent(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)

            @before_save
            def parent_callback(self):
                pass

        class Child(Parent):
            @before_save
            def child_callback(self):
                pass

        # Parent should only have its own callback
        assert len(Parent._before_save_callbacks) == 1

        # Child should have both callbacks (inherited + its own)
        # But the list should be in Child's __dict__, not shared
        assert "_before_save_callbacks" in Child.__dict__


class TestDecoratorEdgeCases:
    """Test edge cases with decorators."""

    def test_multiple_gsi_keys_different_indexes(self):
        """Test model with multiple GSI keys for different indexes."""
        class User(Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            email: str
            tenant_id: str

            @gsi_partition_key("EmailIndex")
            def gsi_pk_email(self) -> str:
                return self.email

            @gsi_partition_key("TenantIndex")
            def gsi_pk_tenant(self) -> str:
                return f"TENANT#{self.tenant_id}"

        user = User(id="123", email="alice@example.com", tenant_id="org-1")

        # Both GSI methods should work
        assert user.gsi_pk_email() == "alice@example.com"
        assert user.gsi_pk_tenant() == "TENANT#org-1"

        # Both should be marked as GSI partition keys
        assert is_gsi_partition_key_method(User.gsi_pk_email)
        assert is_gsi_partition_key_method(User.gsi_pk_tenant)

        # With correct index names
        assert User.gsi_pk_email._gsi_name == "EmailIndex"
        assert User.gsi_pk_tenant._gsi_name == "TenantIndex"

    def test_partition_and_sort_key_together(self):
        """Test model with both @partition_key and @sort_key."""
        class TodoItem(Model):
            model_backend: ClassVar = shared_backend

            user_id: str = Field(primary_key=True)
            todo_id: str

            @partition_key
            def pk(self) -> str:
                return f"USER#{self.user_id}"

            @sort_key
            def sk(self) -> str:
                return f"TODO#{self.todo_id}"

        item = TodoItem(user_id="alice", todo_id="1")

        assert item.pk() == "USER#alice"
        assert item.sk() == "TODO#1"
        assert is_partition_key_method(TodoItem.pk)
        assert is_sort_key_method(TodoItem.sk)

    def test_helper_functions_with_none(self):
        """Test is_*_method helpers return False for None."""
        assert is_partition_key_method(None) is False
        assert is_sort_key_method(None) is False
        assert is_gsi_partition_key_method(None) is False
        assert is_gsi_sort_key_method(None) is False

    def test_helper_functions_with_regular_function(self):
        """Test is_*_method helpers return False for regular functions."""
        def regular_func():
            pass

        assert is_partition_key_method(regular_func) is False
        assert is_sort_key_method(regular_func) is False
        assert is_gsi_partition_key_method(regular_func) is False
        assert is_gsi_sort_key_method(regular_func) is False

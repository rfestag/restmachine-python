"""
Tests for RestMachine ORM models.

These tests demonstrate the API and verify core functionality.
"""

import pytest
from datetime import datetime
from typing import Optional

from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Example model definitions for testing
class User(Model):
    """Simple user model with primary key."""

    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = Field(max_length=100)
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)


class TodoItem(Model):
    """Todo item with composite DynamoDB keys."""

    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    user_id: str
    todo_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: bool = False
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)

    @partition_key
    def pk(self) -> str:
        """Partition key: USER#{user_id}"""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort key: TODO#{created_at}#{todo_id}"""
        return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"


class TestModelDefinition:
    """Test model definition and metadata."""

    def test_user_model_fields(self):
        """Test that User model has correct fields."""
        assert "id" in User.model_fields
        assert "email" in User.model_fields
        assert "name" in User.model_fields
        assert "age" in User.model_fields
        assert "created_at" in User.model_fields
        assert "updated_at" in User.model_fields

    def test_todo_key_generation(self):
        """Test that composite keys are generated correctly."""
        todo = TodoItem(
            user_id="alice",
            todo_id="todo-123",
            title="Test todo",
            created_at=datetime(2025, 1, 15, 10, 30, 0)
        )
        assert todo.pk() == "USER#alice"
        assert todo.sk() == "TODO#2025-01-15T10:30:00#todo-123"


class TestModelValidation:
    """Test Pydantic validation integration."""

    def test_field_validation_success(self):
        """Test successful field validation."""
        user = User(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30

    def test_field_validation_min_max(self):
        """Test min/max validation."""
        # Valid age
        user = User(id="user-123", email="alice@example.com", name="Alice", age=30)
        assert user.age == 30

        # Invalid age (too high)
        with pytest.raises(Exception):  # Pydantic ValidationError
            User(id="user-123", email="alice@example.com", name="Alice", age=200)

        # Invalid age (negative)
        with pytest.raises(Exception):
            User(id="user-123", email="alice@example.com", name="Alice", age=-1)

    def test_field_validation_length(self):
        """Test string length validation."""
        # Valid title
        todo = TodoItem(
            user_id="alice",
            todo_id="todo-123",
            title="Buy groceries"
        )
        assert todo.title == "Buy groceries"

        # Empty title (min_length=1)
        with pytest.raises(Exception):
            TodoItem(user_id="alice", todo_id="todo-123", title="")

        # Title too long (max_length=200)
        with pytest.raises(Exception):
            TodoItem(user_id="alice", todo_id="todo-123", title="x" * 201)

    def test_auto_now_add_field(self):
        """Test auto_now_add sets timestamp on creation."""
        user = User(id="user-123", email="alice@example.com", name="Alice")
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)

    def test_auto_now_field(self):
        """Test auto_now updates timestamp."""
        user = User(id="user-123", email="alice@example.com", name="Alice")
        original_updated = user.updated_at
        assert original_updated is not None

        # Simulate a save operation that would trigger auto_now
        # (actual save testing requires a backend)

    def test_default_values(self):
        """Test default field values."""
        user = User(id="user-123", email="alice@example.com", name="Alice")
        assert user.age == 0  # Default value

        todo = TodoItem(user_id="alice", todo_id="todo-123", title="Test")
        assert todo.completed is False  # Default value
        assert todo.description is None  # Optional field


class TestModelSerialization:
    """Test model serialization/deserialization."""

    def test_model_dump(self):
        """Test converting model to dictionary."""
        user = User(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )
        data = user.model_dump()
        assert data["id"] == "user-123"
        assert data["email"] == "alice@example.com"
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_model_dump_json(self):
        """Test JSON serialization."""
        user = User(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )
        json_str = user.model_dump_json()
        assert "user-123" in json_str
        assert "alice@example.com" in json_str

    def test_model_from_dict(self):
        """Test creating model from dictionary."""
        data = {
            "id": "user-123",
            "email": "alice@example.com",
            "name": "Alice",
            "age": 30,
        }
        user = User(**data)
        assert user.id == "user-123"
        assert user.email == "alice@example.com"


# Note: CRUD operation tests require a backend implementation
# These will be added in backend-specific test files

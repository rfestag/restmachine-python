"""
Tests for InMemory backend.

Tests the in-memory storage backend used for testing and examples.
"""

import pytest
from datetime import datetime
from typing import Optional

from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter
from restmachine_orm.backends.base import NotFoundError, DuplicateKeyError


# Shared backend instance for all models
shared_backend = InMemoryBackend(InMemoryAdapter())


class User(Model):
    """Simple user model for testing."""

    class Meta:
        backend = shared_backend

    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TodoItem(Model):
    """Todo item for testing."""

    class Meta:
        backend = shared_backend

    user_id: str
    todo_id: str = Field(primary_key=True)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    User.Meta.backend.clear()
    TodoItem.Meta.backend.clear()
    yield
    User.Meta.backend.clear()
    TodoItem.Meta.backend.clear()


class TestInMemoryBackendSetup:
    """Test backend initialization and configuration."""

    def test_backend_initialization(self):
        """Test that backend initializes correctly."""
        backend = InMemoryBackend(InMemoryAdapter())
        assert backend.adapter is not None
        assert isinstance(backend._storage, dict)

    def test_backend_with_default_adapter(self):
        """Test backend initializes with default adapter."""
        backend = InMemoryBackend()
        assert backend.adapter is not None
        assert isinstance(backend.adapter, InMemoryAdapter)


class TestInMemoryCRUD:
    """Test basic CRUD operations."""

    def test_create_user(self):
        """Test creating a user record."""
        user = User.create(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30
        assert user._is_persisted is True

    def test_create_todo(self):
        """Test creating a todo item."""
        todo = TodoItem.create(
            user_id="alice",
            todo_id="todo-1",
            title="Write tests",
            description="Comprehensive test coverage",
            priority=4
        )

        assert todo.user_id == "alice"
        assert todo.todo_id == "todo-1"
        assert todo.title == "Write tests"
        assert todo.priority == 4
        assert not todo.completed

    def test_create_duplicate_raises_error(self):
        """Test that creating duplicate raises DuplicateKeyError."""
        User.create(id="user-123", email="alice@example.com", name="Alice")

        with pytest.raises(DuplicateKeyError):
            User.create(id="user-123", email="different@example.com", name="Different")

    def test_get_user(self):
        """Test retrieving a user by ID."""
        # Create user
        User.create(id="user-123", email="alice@example.com", name="Alice", age=30)

        # Retrieve user
        user = User.get(id="user-123")
        assert user is not None
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30

    def test_get_nonexistent_returns_none(self):
        """Test that getting nonexistent record returns None."""
        user = User.get(id="nonexistent")
        assert user is None

    def test_update_user(self):
        """Test updating a user record."""
        # Create user
        user = User.create(id="user-123", email="alice@example.com", name="Alice", age=30)

        # Update user
        user.age = 31
        user.name = "Alice Smith"
        user.save()

        assert user.age == 31
        assert user.name == "Alice Smith"

        # Verify in storage
        refreshed = User.get(id="user-123")
        assert refreshed is not None
        assert refreshed.age == 31
        assert refreshed.name == "Alice Smith"

    def test_update_nonexistent_raises_error(self):
        """Test that updating nonexistent record raises NotFoundError."""
        user = User(id="nonexistent", email="test@example.com", name="Test")
        user._is_persisted = True  # Trick it into thinking it exists

        with pytest.raises(NotFoundError):
            user.save()

    def test_delete_user(self):
        """Test deleting a user record."""
        # Create user
        user = User.create(id="user-123", email="alice@example.com", name="Alice")

        # Delete user
        assert user.delete() is True

        # Verify deleted
        assert User.get(id="user-123") is None

    def test_delete_nonexistent_returns_false(self):
        """Test that deleting nonexistent record returns False."""
        user = User(id="nonexistent", email="test@example.com", name="Test")
        assert user.delete() is False

    def test_upsert_creates_new_record(self):
        """Test that upsert creates a new record when it doesn't exist."""
        # Upsert a new user
        user = User.upsert(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30
        assert user._is_persisted is True

        # Verify in storage
        retrieved = User.get(id="user-123")
        assert retrieved is not None
        assert retrieved.email == "alice@example.com"
        assert retrieved.name == "Alice"

    def test_upsert_overwrites_existing_record(self):
        """Test that upsert overwrites an existing record without error."""
        # Create initial user
        user1 = User.create(
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        # Upsert with same ID but different data
        user2 = User.upsert(
            id="user-123",
            email="alice.new@example.com",
            name="Alice Smith",
            age=31
        )

        assert user2.id == "user-123"
        assert user2.email == "alice.new@example.com"
        assert user2.name == "Alice Smith"
        assert user2.age == 31
        assert user2._is_persisted is True

        # Verify in storage - should have new values
        retrieved = User.get(id="user-123")
        assert retrieved is not None
        assert retrieved.email == "alice.new@example.com"
        assert retrieved.name == "Alice Smith"
        assert retrieved.age == 31

    def test_upsert_no_duplicate_error(self):
        """Test that upsert does not raise DuplicateKeyError."""
        # Create user
        User.create(id="user-123", email="alice@example.com", name="Alice")

        # Upsert with same ID should NOT raise error
        user = User.upsert(id="user-123", email="different@example.com", name="Different")
        assert user.id == "user-123"
        assert user.email == "different@example.com"

    def test_upsert_todo_item(self):
        """Test upserting a todo item."""
        # Upsert new todo
        todo1 = TodoItem.upsert(
            user_id="alice",
            todo_id="todo-1",
            title="Original Title",
            description="Original description",
            priority=3
        )
        assert todo1.title == "Original Title"
        assert todo1.priority == 3

        # Upsert same todo with different data
        todo2 = TodoItem.upsert(
            user_id="alice",
            todo_id="todo-1",
            title="Updated Title",
            description="Updated description",
            priority=5,
            completed=True
        )
        assert todo2.title == "Updated Title"
        assert todo2.priority == 5
        assert todo2.completed is True

        # Verify only one todo exists
        retrieved = TodoItem.get(todo_id="todo-1")
        assert retrieved is not None
        assert retrieved.title == "Updated Title"


class TestInMemoryQuery:
    """Test query operations."""

    def test_all_users(self):
        """Test retrieving all users."""
        # Create multiple users
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Get all users
        users = User.all()
        assert len(users) == 3

        # Check that all are persisted
        for user in users:
            assert user._is_persisted

    def test_where_with_kwargs(self):
        """Test where() with kwargs (AND conditions)."""
        # Create users with different ages
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Query with kwargs - should AND conditions
        users = User.where(age__gte=30).all()
        assert len(users) == 2
        ages = [u.age for u in users]
        assert 30 in ages
        assert 35 in ages

    def test_and_filter(self):
        """Test .and_() method."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Filter by age >= 30
        users = User.where().and_(age__gte=30).all()
        assert len(users) == 2

    def test_not_filter(self):
        """Test .not_() method for excluding records."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=30)

        # Exclude age 30
        users = User.where().not_(age=30).all()
        assert len(users) == 1
        assert users[0].age == 25

    def test_query_first(self):
        """Test getting first result."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)

        # Get first user
        user = User.where().first()
        assert user is not None
        assert user.id in ["user-1", "user-2"]

    def test_query_first_empty_returns_none(self):
        """Test that first() on empty query returns None."""
        user = User.where().first()
        assert user is None

    def test_query_count(self):
        """Test counting records."""
        User.create(id="user-1", email="alice@example.com", name="Alice")
        User.create(id="user-2", email="bob@example.com", name="Bob")
        User.create(id="user-3", email="carol@example.com", name="Carol")

        assert User.where().count() == 3

    def test_query_exists(self):
        """Test checking if records exist."""
        assert not User.where(email="alice@example.com").exists()

        User.create(id="user-1", email="alice@example.com", name="Alice")

        assert User.where(email="alice@example.com").exists()
        assert not User.where(email="bob@example.com").exists()

    def test_find_by(self):
        """Test find_by() method."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)

        # Find by email
        user = User.find_by(email="alice@example.com")
        assert user is not None
        assert user.id == "user-1"
        assert user.name == "Alice"

        # Find nonexistent
        user = User.find_by(email="nonexistent@example.com")
        assert user is None

    def test_query_with_limit(self):
        """Test query with limit."""
        for i in range(10):
            User.create(id=f"user-{i}", email=f"user{i}@example.com", name=f"User {i}")

        # Get first 3 users
        users = User.where().limit(3).all()
        assert len(users) == 3

    def test_query_with_offset(self):
        """Test query with offset."""
        for i in range(10):
            User.create(id=f"user-{i}", email=f"user{i}@example.com", name=f"User {i}")

        # Skip first 3 users
        users = User.where().offset(3).all()
        assert len(users) == 7

    def test_query_with_order_by(self):
        """Test query with ordering."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Order by age ascending
        users = User.where().order_by("age").all()
        assert len(users) == 3
        assert users[0].age == 25
        assert users[1].age == 30
        assert users[2].age == 35

        # Order by age descending
        users = User.where().order_by("-age").all()
        assert len(users) == 3
        assert users[0].age == 35
        assert users[1].age == 30
        assert users[2].age == 25


class TestInMemoryEdgeCases:
    """Test edge cases and error handling."""

    def test_clear_specific_model(self):
        """Test clearing storage for specific model."""
        User.create(id="user-1", email="alice@example.com", name="Alice")
        TodoItem.create(user_id="alice", todo_id="todo-1", title="Test")

        # Clear only users
        User.Meta.backend.clear(User)

        assert len(User.all()) == 0
        assert len(TodoItem.all()) == 1

    def test_clear_all_storage(self):
        """Test clearing all storage."""
        User.create(id="user-1", email="alice@example.com", name="Alice")
        TodoItem.create(user_id="alice", todo_id="todo-1", title="Test")

        # Clear all
        User.Meta.backend.clear()

        assert len(User.all()) == 0
        assert len(TodoItem.all()) == 0

    def test_query_with_multiple_filters(self):
        """Test query with multiple filter conditions."""
        # Create todos with different properties
        for i in range(5):
            TodoItem.create(
                user_id="alice",
                todo_id=f"todo-{i}",
                title=f"Task {i}",
                priority=i + 1,
                completed=(i % 2 != 0)  # Odd indices are completed
            )

        # Query with multiple filters (ANDed together)
        todos = TodoItem.where(completed=False, priority__gte=3).all()

        # Should match todos with priority >= 3 AND completed=False
        # That's todo-2 (priority=3) and todo-4 (priority=5)
        assert len(todos) == 2

    def test_count_with_filters(self):
        """Test count with filters."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Count all
        assert User.Meta.backend.count(User) == 3

        # Count with filter
        assert User.Meta.backend.count(User, age=30) == 1

    def test_exists_with_filters(self):
        """Test exists with filters."""
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)

        assert User.Meta.backend.exists(User, age=30)
        assert not User.Meta.backend.exists(User, age=25)

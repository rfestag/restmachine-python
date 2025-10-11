"""
Tests for basic CRUD operations using the testing DSL.

This test file demonstrates the multi-backend testing pattern.
The same tests run against all configured backends.
"""

import pytest
from datetime import datetime
from typing import Optional, List, Type

from restmachine_orm import Model, Field
from restmachine_orm.backends.base import DuplicateKeyError, NotFoundError
from restmachine_orm.testing import MultiBackendTestBase


# Test models
class User(Model):
    """Simple user model for testing."""
    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)


class TodoItem(Model):
    """Todo item for testing."""
    user_id: str
    todo_id: str = Field(primary_key=True)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)


class TestCRUDOperations(MultiBackendTestBase):
    """Test basic CRUD operations across all backends."""

    def get_test_models(self) -> List[Type]:
        """Return models used in these tests."""
        return [User, TodoItem]

    def test_create_user(self, orm):
        """Test creating a user record."""
        orm_client, backend_name = orm

        # Create user using DSL
        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        # Verify fields
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_create_duplicate_raises_error(self, orm):
        """Test that creating duplicate raises DuplicateKeyError."""
        orm_client, backend_name = orm

        # Create first user
        orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        # Attempt to create duplicate
        orm_client.expect_create_failure(
            User,
            DuplicateKeyError,
            id="user-123",
            email="different@example.com",
            name="Different"
        )

    def test_get_user(self, orm):
        """Test retrieving a user by ID."""
        orm_client, backend_name = orm

        # Create user
        orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        # Retrieve user
        user = orm_client.get_and_verify_exists(User, id="user-123")
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30

    def test_get_nonexistent_returns_none(self, orm):
        """Test that getting nonexistent record returns None."""
        orm_client, backend_name = orm

        # Verify nonexistent
        orm_client.get_and_verify_not_exists(User, id="nonexistent")

    def test_update_user(self, orm):
        """Test updating a user record."""
        orm_client, backend_name = orm

        # Create user
        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )
        original_created = user.created_at

        # Update user
        updated_user = orm_client.update_and_verify(
            user,
            age=31,
            name="Alice Smith"
        )

        assert updated_user.age == 31
        assert updated_user.name == "Alice Smith"
        assert updated_user.created_at == original_created
        assert updated_user.updated_at is not None

        # Verify in storage
        refreshed = orm_client.get_and_verify_exists(User, id="user-123")
        assert refreshed.age == 31
        assert refreshed.name == "Alice Smith"

    def test_update_nonexistent_raises_error(self, orm):
        """Test that updating nonexistent record raises NotFoundError."""
        orm_client, backend_name = orm

        # Create instance without saving
        user = User(id="nonexistent", email="test@example.com", name="Test")
        user._is_persisted = True  # Trick it into thinking it exists

        # Attempt to update
        orm_client.expect_update_failure(
            user,
            NotFoundError,
            name="Updated"
        )

    def test_delete_user(self, orm):
        """Test deleting a user record."""
        orm_client, backend_name = orm

        # Create user
        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        # Delete user
        orm_client.delete_and_verify(user)

        # Verify deleted
        orm_client.get_and_verify_not_exists(User, id="user-123")

    def test_delete_nonexistent_returns_false(self, orm):
        """Test that deleting nonexistent record returns False."""
        orm_client, backend_name = orm

        # Create instance without saving
        user = User(id="nonexistent", email="test@example.com", name="Test")

        # Attempt to delete
        result = orm_client.delete_model(user)
        assert not result.success or result.data["deleted"] is False

    def test_upsert_creates_new_record(self, orm):
        """Test that upsert creates a new record when it doesn't exist."""
        orm_client, backend_name = orm

        # Upsert new user
        user = orm_client.upsert_and_verify(
            User,
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
        assert user.created_at is not None

        # Verify in storage
        retrieved = orm_client.get_and_verify_exists(User, id="user-123")
        assert retrieved.email == "alice@example.com"
        assert retrieved.name == "Alice"

    def test_upsert_overwrites_existing_record(self, orm):
        """Test that upsert overwrites an existing record without error."""
        orm_client, backend_name = orm

        # Create initial user
        user1 = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        # Upsert with same ID but different data
        user2 = orm_client.upsert_and_verify(
            User,
            id="user-123",
            email="alice.new@example.com",
            name="Alice Smith",
            age=31
        )

        assert user2.id == "user-123"
        assert user2.email == "alice.new@example.com"
        assert user2.name == "Alice Smith"
        assert user2.age == 31

        # Verify in storage - should have new values
        retrieved = orm_client.get_and_verify_exists(User, id="user-123")
        assert retrieved.email == "alice.new@example.com"
        assert retrieved.name == "Alice Smith"
        assert retrieved.age == 31

    def test_upsert_no_duplicate_error(self, orm):
        """Test that upsert does not raise DuplicateKeyError."""
        orm_client, backend_name = orm

        # Create user
        orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        # Upsert with same ID should NOT raise error
        user = orm_client.upsert_and_verify(
            User,
            id="user-123",
            email="different@example.com",
            name="Different"
        )

        assert user.id == "user-123"
        assert user.email == "different@example.com"


class TestQueryOperations(MultiBackendTestBase):
    """Test query operations across all backends."""

    def get_test_models(self) -> List[Type]:
        """Return models used in these tests."""
        return [User, TodoItem]

    def test_all_users(self, orm):
        """Test retrieving all users."""
        orm_client, backend_name = orm

        # Create multiple users
        orm_client.create_and_verify(User, id="user-1", email="alice@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="bob@example.com", name="Bob", age=25)
        orm_client.create_and_verify(User, id="user-3", email="carol@example.com", name="Carol", age=35)

        # Get all users
        users = orm_client.query_and_verify_count(User, 3)

        # Check that all are persisted
        for user in users:
            assert user._is_persisted

    def test_query_with_filters(self, orm):
        """Test querying with filters."""
        orm_client, backend_name = orm

        # Create users with different ages
        orm_client.create_and_verify(User, id="user-1", email="alice@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="bob@example.com", name="Bob", age=25)
        orm_client.create_and_verify(User, id="user-3", email="carol@example.com", name="Carol", age=35)

        # Query with age >= 30
        result = orm_client.query_models(User, filters={"age__gte": 30})
        assert result.success
        assert len(result.data) == 2

        ages = [u.age for u in result.data]
        assert 30 in ages
        assert 35 in ages

    def test_query_count(self, orm):
        """Test counting records."""
        orm_client, backend_name = orm

        # Create users
        orm_client.create_and_verify(User, id="user-1", email="alice@example.com", name="Alice")
        orm_client.create_and_verify(User, id="user-2", email="bob@example.com", name="Bob")
        orm_client.create_and_verify(User, id="user-3", email="carol@example.com", name="Carol")

        # Count all
        count = orm_client.count_models(User)
        assert count == 3

    def test_query_exists(self, orm):
        """Test checking if records exist."""
        orm_client, backend_name = orm

        # Initially no users
        assert not orm_client.model_exists(User, email="alice@example.com")

        # Create user
        orm_client.create_and_verify(User, id="user-1", email="alice@example.com", name="Alice")

        # Now exists
        assert orm_client.model_exists(User, email="alice@example.com")
        assert not orm_client.model_exists(User, email="bob@example.com")

    def test_query_with_ordering(self, orm):
        """Test query with ordering."""
        orm_client, backend_name = orm

        # Create users with different ages
        orm_client.create_and_verify(User, id="user-1", email="alice@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="bob@example.com", name="Bob", age=25)
        orm_client.create_and_verify(User, id="user-3", email="carol@example.com", name="Carol", age=35)

        # Order by age ascending
        result = orm_client.query_models(User, order_by=["age"])
        assert result.success
        assert len(result.data) == 3
        assert result.data[0].age == 25
        assert result.data[1].age == 30
        assert result.data[2].age == 35

        # Order by age descending
        result = orm_client.query_models(User, order_by=["-age"])
        assert result.success
        assert len(result.data) == 3
        assert result.data[0].age == 35
        assert result.data[1].age == 30
        assert result.data[2].age == 25

    def test_query_with_limit(self, orm):
        """Test query with limit."""
        orm_client, backend_name = orm

        # Create multiple users
        for i in range(10):
            orm_client.create_and_verify(
                User,
                id=f"user-{i}",
                email=f"user{i}@example.com",
                name=f"User {i}"
            )

        # Query with limit
        result = orm_client.query_models(User, limit=3)
        assert result.success
        assert len(result.data) == 3

    def test_query_with_offset(self, orm):
        """Test query with offset."""
        orm_client, backend_name = orm

        # Create multiple users
        for i in range(10):
            orm_client.create_and_verify(
                User,
                id=f"user-{i}",
                email=f"user{i}@example.com",
                name=f"User {i}"
            )

        # Query with offset
        result = orm_client.query_models(User, offset=3)
        assert result.success
        assert len(result.data) == 7

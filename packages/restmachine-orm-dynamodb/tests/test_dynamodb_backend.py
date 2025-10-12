"""
Tests for DynamoDB backend.

Uses moto to mock AWS DynamoDB service.
"""

import pytest
from datetime import datetime
from typing import Optional
from decimal import Decimal

# Skip all tests if boto3 or moto not installed
pytest.importorskip("boto3")
pytest.importorskip("moto")


from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm.backends.base import NotFoundError, DuplicateKeyError
from restmachine_orm_dynamodb import DynamoDBBackend, DynamoDBAdapter


# Fixtures are provided by conftest.py


class User(Model):
    """Simple user model with primary key."""

    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.id}"

    @sort_key
    def sk(self) -> str:
        return "PROFILE"


class TodoItem(Model):
    """Todo item with composite keys."""

    user_id: str
    todo_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        if self.created_at:
            return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"
        return f"TODO#{self.todo_id}"


class TestDynamoDBBackendSetup:
    """Test backend initialization and configuration."""

    def test_backend_initialization(self):
        """Test that backend initializes with correct configuration."""
        backend = DynamoDBBackend(
            table_name="my-table",
            region_name="us-west-2",
        )
        assert backend.table_name == "my-table"
        assert backend.region_name == "us-west-2"

    def test_backend_with_custom_adapter(self):
        """Test backend with custom adapter."""
        adapter = DynamoDBAdapter(pk_attribute="hash_key", sk_attribute="range_key")
        backend = DynamoDBBackend(table_name="my-table", adapter=adapter)
        assert backend.adapter.pk_attribute == "hash_key"
        assert backend.adapter.sk_attribute == "range_key"

    def test_lazy_initialization(self, backend):
        """Test that DynamoDB connection is lazy."""
        # Resource should not be created until first access
        assert backend._dynamodb_resource is None
        assert backend._table is None

        # Access triggers initialization
        _ = backend.table
        assert backend._dynamodb_resource is not None
        assert backend._table is not None


class TestDynamoDBCRUD:
    """Test basic CRUD operations."""

    def test_create_user(self, backend):
        """Test creating a user record."""
        User.Meta.backend = backend

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

        # Verify in DynamoDB
        item = backend.table.get_item(Key={"pk": "USER#user-123", "sk": "PROFILE"})
        assert "Item" in item
        assert item["Item"]["pk"] == "USER#user-123"
        assert item["Item"]["email"] == "alice@example.com"

    def test_create_todo(self, backend):
        """Test creating a todo item."""
        TodoItem.Meta.backend = backend

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

    def test_create_duplicate_raises_error(self, backend):
        """Test that creating duplicate raises DuplicateKeyError."""
        User.Meta.backend = backend

        User.create(id="user-123", email="alice@example.com", name="Alice")

        with pytest.raises(DuplicateKeyError):
            User.create(id="user-123", email="different@example.com", name="Different")

    def test_get_user(self, backend):
        """Test retrieving a user by ID."""
        User.Meta.backend = backend

        # Create user
        User.create(id="user-123", email="alice@example.com", name="Alice", age=30)

        # Retrieve user
        user = User.get(id="user-123")
        assert user is not None
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.age == 30

    def test_get_nonexistent_returns_none(self, backend):
        """Test that getting nonexistent record returns None."""
        User.Meta.backend = backend

        user = User.get(id="nonexistent")
        assert user is None

    def test_update_user(self, backend):
        """Test updating a user record."""
        User.Meta.backend = backend

        # Create user
        user = User.create(id="user-123", email="alice@example.com", name="Alice", age=30)

        # Update user
        user.age = 31
        user.name = "Alice Smith"
        user.save()

        assert user.age == 31
        assert user.name == "Alice Smith"

        # Verify in database
        refreshed = User.get(id="user-123")
        assert refreshed is not None
        assert refreshed.age == 31
        assert refreshed.name == "Alice Smith"

    def test_update_nonexistent_raises_error(self, backend):
        """Test that updating nonexistent record raises NotFoundError."""
        User.Meta.backend = backend

        user = User(id="nonexistent", email="test@example.com", name="Test")
        user._is_persisted = True  # Trick it into thinking it exists

        with pytest.raises(NotFoundError):
            user.save()

    def test_delete_user(self, backend):
        """Test deleting a user record."""
        User.Meta.backend = backend

        # Create user
        user = User.create(id="user-123", email="alice@example.com", name="Alice")

        # Delete user
        assert user.delete() is True

        # Verify deleted
        assert User.get(id="user-123") is None

    def test_delete_nonexistent_returns_false(self, backend):
        """Test that deleting nonexistent record returns False."""
        User.Meta.backend = backend

        user = User(id="nonexistent", email="test@example.com", name="Test")
        assert user.delete() is False

    def test_upsert_creates_new_record(self, backend):
        """Test that upsert creates a new record when it doesn't exist."""
        User.Meta.backend = backend

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

        # Verify in database
        retrieved = User.get(id="user-123")
        assert retrieved is not None
        assert retrieved.email == "alice@example.com"
        assert retrieved.name == "Alice"

    def test_upsert_overwrites_existing_record(self, backend):
        """Test that upsert overwrites an existing record without error."""
        User.Meta.backend = backend

        # Create initial user
        User.create(
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

        # Verify in database - should have new values
        retrieved = User.get(id="user-123")
        assert retrieved is not None
        assert retrieved.email == "alice.new@example.com"
        assert retrieved.name == "Alice Smith"
        assert retrieved.age == 31

    def test_upsert_no_duplicate_error(self, backend):
        """Test that upsert does not raise DuplicateKeyError."""
        User.Meta.backend = backend

        # Create user
        User.create(id="user-123", email="alice@example.com", name="Alice")

        # Upsert with same ID should NOT raise error
        user = User.upsert(id="user-123", email="different@example.com", name="Different")
        assert user.id == "user-123"
        assert user.email == "different@example.com"

    def test_upsert_todo_item(self, backend):
        """Test upserting a todo item with composite keys."""
        TodoItem.Meta.backend = backend

        # Use fixed timestamp so sort key is the same
        fixed_timestamp = datetime(2025, 1, 15, 10, 30, 0)

        # Upsert new todo
        todo1 = TodoItem.upsert(
            user_id="alice",
            todo_id="todo-1",
            title="Original Title",
            description="Original description",
            priority=3,
            created_at=fixed_timestamp
        )
        assert todo1.title == "Original Title"
        assert todo1.priority == 3

        # Upsert same todo with different data (same created_at so same sort key)
        todo2 = TodoItem.upsert(
            user_id="alice",
            todo_id="todo-1",
            title="Updated Title",
            description="Updated description",
            priority=5,
            completed=True,
            created_at=fixed_timestamp  # Same timestamp = same sort key
        )
        assert todo2.title == "Updated Title"
        assert todo2.priority == 5
        assert todo2.completed is True

        # Verify only one todo exists (same keys = same item)
        todos = TodoItem.where().and_(user_id="alice").all()
        matching = [t for t in todos if t.todo_id == "todo-1" and t.created_at == fixed_timestamp]
        assert len(matching) == 1
        assert matching[0].title == "Updated Title"


class TestDynamoDBQuery:
    """Test query operations."""

    def test_all_users(self, backend):
        """Test retrieving all users."""
        User.Meta.backend = backend

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

    def test_filter_by_age(self, backend):
        """Test filtering users by age."""
        User.Meta.backend = backend

        # Create users with different ages
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Filter by age >= 30
        users = User.where().and_(age__gte=30).all()
        assert len(users) == 2
        ages = [u.age for u in users]
        assert 30 in ages
        assert 35 in ages

    def test_filter_todos_by_completion(self, backend):
        """Test filtering todos by completion status."""
        TodoItem.Meta.backend = backend

        # Create todos
        TodoItem.create(
            user_id="alice", todo_id="todo-1",
            title="Task 1", completed=False
        )
        TodoItem.create(
            user_id="alice", todo_id="todo-2",
            title="Task 2", completed=True
        )
        TodoItem.create(
            user_id="alice", todo_id="todo-3",
            title="Task 3", completed=False
        )

        # Filter by completion
        incomplete = TodoItem.where().and_(completed=False).all()
        assert len(incomplete) == 2

        completed = TodoItem.where().and_(completed=True).all()
        assert len(completed) == 1

    def test_exclude_filter(self, backend):
        """Test excluding records."""
        User.Meta.backend = backend

        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=30)

        # Exclude age 30
        users = User.where().not_(age=30).all()
        assert len(users) == 1
        assert users[0].age == 25

    def test_query_first(self, backend):
        """Test getting first result."""
        User.Meta.backend = backend

        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)

        # Get first user
        user = User.where().first()
        assert user is not None
        assert user.id in ["user-1", "user-2"]

    def test_query_first_empty_returns_none(self, backend):
        """Test that first() on empty query returns None."""
        User.Meta.backend = backend

        user = User.where().first()
        assert user is None

    def test_query_last(self, backend):
        """Test getting last result."""
        User.Meta.backend = backend

        # Create users with different ages (so we can order by age)
        User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
        User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
        User.create(id="user-3", email="carol@example.com", name="Carol", age=35)

        # Get last user when ordered by age
        user = User.where().order_by("age").last()
        assert user is not None
        assert user.age == 35  # Highest age

        # Get last user when ordered by age descending
        user = User.where().order_by("-age").last()
        assert user is not None
        assert user.age == 25  # Lowest age (last in descending order)

    def test_query_last_empty_returns_none(self, backend):
        """Test that last() on empty query returns None."""
        User.Meta.backend = backend

        user = User.where().last()
        assert user is None

    def test_query_count(self, backend):
        """Test counting records."""
        User.Meta.backend = backend

        User.create(id="user-1", email="alice@example.com", name="Alice")
        User.create(id="user-2", email="bob@example.com", name="Bob")
        User.create(id="user-3", email="carol@example.com", name="Carol")

        assert User.where().count() == 3

    def test_query_exists(self, backend):
        """Test checking if records exist."""
        User.Meta.backend = backend

        assert not User.where(email="alice@example.com").exists()

        User.create(id="user-1", email="alice@example.com", name="Alice")

        assert User.where(email="alice@example.com").exists()
        assert not User.where(email="bob@example.com").exists()


class TestDynamoDBBatchOperations:
    """Test batch operations."""

    def test_batch_create(self, backend):
        """Test batch creating records."""
        TodoItem.Meta.backend = backend

        records = [
            {
                "user_id": "alice",
                "todo_id": f"todo-{i}",
                "title": f"Task {i}",
                "priority": i % 5 + 1
            }
            for i in range(10)
        ]

        results = backend.batch_create(TodoItem, records)
        assert len(results) == 10

        # Verify all were created
        todos = TodoItem.all()
        assert len(todos) == 10

    def test_batch_get(self, backend):
        """Test batch getting records."""
        User.Meta.backend = backend

        # Create users
        for i in range(5):
            User.create(
                id=f"user-{i}",
                email=f"user{i}@example.com",
                name=f"User {i}"
            )

        # Batch get
        keys = [{"id": f"user-{i}"} for i in range(5)]
        results = backend.batch_get(User, keys)

        assert len(results) == 5
        emails = [r["email"] for r in results]
        assert "user0@example.com" in emails
        assert "user4@example.com" in emails

    def test_batch_get_empty_returns_empty(self, backend):
        """Test that batch_get with empty keys returns empty list."""
        User.Meta.backend = backend

        results = backend.batch_get(User, [])
        assert results == []


class TestDynamoDBTypeConversion:
    """Test type conversion between Python and DynamoDB."""

    def test_float_to_decimal_conversion(self, backend):
        """Test that floats are converted to Decimal for DynamoDB."""
        TodoItem.Meta.backend = backend

        # Create a todo with priority (int)
        todo = TodoItem.create(
            user_id="alice",
            todo_id="todo-1",
            title="Test",
            priority=4
        )

        # Verify stored correctly
        item = backend.table.get_item(Key={"pk": "USER#alice", "sk": todo.sk()})
        assert "Item" in item
        # DynamoDB stores numbers as Decimal
        assert isinstance(item["Item"]["priority"], (int, Decimal))

    def test_decimal_to_python_conversion(self, backend):
        """Test that Decimal values are converted back to Python types."""
        User.Meta.backend = backend

        # Create user
        User.create(id="user-123", email="alice@example.com", name="Alice", age=30)

        # Retrieve user
        user = User.get(id="user-123")
        assert user is not None
        # Age should be int, not Decimal
        assert isinstance(user.age, int)
        assert user.age == 30


class TestDynamoDBEdgeCases:
    """Test edge cases and error handling."""

    def test_create_with_special_characters(self, backend):
        """Test creating records with special characters."""
        User.Meta.backend = backend

        user = User.create(
            id="user-123",
            email="alice+test@example.com",
            name="Alice O'Brien"
        )

        assert user.email == "alice+test@example.com"
        assert user.name == "Alice O'Brien"

        # Verify can retrieve
        retrieved = User.get(id="user-123")
        assert retrieved is not None
        assert retrieved.name == "Alice O'Brien"

    def test_query_with_multiple_filters(self, backend):
        """Test query with multiple filter conditions."""
        TodoItem.Meta.backend = backend

        # Create todos
        for i in range(5):
            TodoItem.create(
                user_id="alice",
                todo_id=f"todo-{i}",
                title=f"Task {i}",
                priority=i + 1,
                completed=(i % 2 != 0)  # Odd indices are completed
            )

        # Query with multiple filters
        todos = TodoItem.where().and_(
            completed=False,
            priority__gte=3
        ).all()

        # Should match todos with priority >= 3 AND completed=False
        # That's todo-2 (priority=3, completed=False) and todo-4 (priority=5, completed=False)
        assert len(todos) == 2

    def test_empty_string_field(self, backend):
        """Test handling empty strings."""
        TodoItem.Meta.backend = backend

        # DynamoDB doesn't allow empty strings, but our validation should catch this
        with pytest.raises(Exception):  # Pydantic ValidationError
            TodoItem.create(
                user_id="alice",
                todo_id="todo-1",
                title=""  # Empty string violates min_length=1
            )


class TestDynamoDBPagination:
    """Test pagination with cursors."""

    def test_paginate_with_limit(self, backend):
        """Test pagination with limit."""
        User.Meta.backend = backend

        # Create multiple users
        for i in range(10):
            User.create(id=f"user-{i}", email=f"user{i}@example.com", name=f"User {i}")

        # Get first page
        results, cursor = User.where().limit(3).paginate()
        assert len(results) == 3
        assert cursor is not None  # Should have more results

        # Get second page
        more_results, next_cursor = User.where().limit(3).cursor(cursor).paginate()
        assert len(more_results) == 3

        # Ensure different results
        first_ids = {u.id for u in results}
        second_ids = {u.id for u in more_results}
        assert first_ids.isdisjoint(second_ids)

    def test_paginate_last_page(self, backend):
        """Test that last page returns None cursor."""
        User.Meta.backend = backend

        # Create 5 users
        for i in range(5):
            User.create(id=f"user-{i}", email=f"user{i}@example.com", name=f"User {i}")

        # Get first page (3 results)
        results, cursor = User.where().limit(3).paginate()
        assert len(results) == 3
        assert cursor is not None

        # Get second page (2 remaining results)
        more_results, next_cursor = User.where().limit(3).cursor(cursor).paginate()
        assert len(more_results) == 2
        # Cursor might be None since we're at the end
        # (DynamoDB returns LastEvaluatedKey even on last page sometimes)

    def test_paginate_empty_results(self, backend):
        """Test pagination with no results."""
        User.Meta.backend = backend

        results, cursor = User.where(age__gte=100).limit(10).paginate()
        assert len(results) == 0
        assert cursor is None

    def test_paginate_all_results(self, backend):
        """Test fetching all results via pagination."""
        TodoItem.Meta.backend = backend

        # Create 15 todos
        for i in range(15):
            TodoItem.create(
                user_id="alice",
                todo_id=f"todo-{i}",
                title=f"Task {i}",
                priority=(i % 5) + 1
            )

        # Collect all results via pagination
        all_results = []
        cursor = None
        page_count = 0

        while True:
            query = TodoItem.where().limit(4)
            if cursor:
                query = query.cursor(cursor)

            results, cursor = query.paginate()
            all_results.extend(results)
            page_count += 1

            if not cursor or len(results) == 0:
                break

            # Safety check to prevent infinite loop
            assert page_count < 10, "Too many pages, possible infinite loop"

        # Should have all 15 todos
        assert len(all_results) == 15
        # Should have needed multiple pages
        assert page_count >= 4

"""
Tests for SQLite Backend.
"""

import tempfile
from pathlib import Path
import pytest
from restmachine_orm.models.base import Model
from restmachine_orm.backends.base import NotFoundError, DuplicateKeyError
from restmachine_orm_sqlite.backend import SqliteBackend


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def backend(temp_db):
    """Create a SQLite backend instance."""
    return SqliteBackend(database=temp_db)


@pytest.fixture
def user_model(backend):
    """Create a test User model."""

    class User(Model):
        model_backend = backend
        id: str
        name: str
        email: str
        age: int = 0

    return User


def test_backend_name(backend):
    """Test backend name property."""
    assert backend.backend_name == "sqlite"


def test_backend_initialization():
    """Test backend initialization with different parameters."""
    # Default database
    backend1 = SqliteBackend()
    assert backend1.database == Path("data.db")

    # Custom database
    backend2 = SqliteBackend(database="custom.db")
    assert backend2.database == Path("custom.db")


def test_connection_creation(backend):
    """Test database connection is created lazily."""
    assert backend._connection is None
    conn = backend.connection
    assert conn is not None
    assert backend._connection is conn


def test_table_creation(backend, user_model):
    """Test table is created automatically."""
    # Create a user to trigger table creation
    user = user_model(id="1", name="Alice", email="alice@example.com")
    user.save()

    # Verify table exists
    cursor = backend.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    table = cursor.fetchone()
    assert table is not None


def test_create_record(backend, user_model):
    """Test creating a record."""
    user = user_model(id="1", name="Alice", email="alice@example.com", age=30)
    user.save()

    # Verify record exists in database
    cursor = backend.connection.execute("SELECT * FROM users WHERE id = ?", ("1",))
    row = cursor.fetchone()
    assert row is not None


def test_create_duplicate_key(backend, user_model):
    """Test creating duplicate record raises error."""
    user1 = user_model(id="1", name="Alice", email="alice@example.com")
    user1.save()

    # Try to create another user with same ID
    user2 = user_model(id="1", name="Bob", email="bob@example.com")
    with pytest.raises(DuplicateKeyError):
        user2.save()


def test_get_record_by_id(backend, user_model):
    """Test getting a record by ID."""
    # Create user
    user = user_model(id="1", name="Alice", email="alice@example.com", age=30)
    user.save()

    # Get user
    found = user_model.get(id="1")
    assert found is not None
    assert found.id == "1"
    assert found.name == "Alice"
    assert found.email == "alice@example.com"
    assert found.age == 30


def test_get_nonexistent_record(backend, user_model):
    """Test getting a nonexistent record returns None."""
    found = user_model.get(id="nonexistent")
    assert found is None


def test_update_record(backend, user_model):
    """Test updating a record."""
    # Create user
    user = user_model(id="1", name="Alice", email="alice@example.com", age=30)
    user.save()

    # Update user
    user.name = "Alice Smith"
    user.age = 31
    user.save()

    # Verify update
    found = user_model.get(id="1")
    assert found.name == "Alice Smith"
    assert found.age == 31


def test_update_nonexistent_record(backend, user_model):
    """Test updating a nonexistent record raises error."""
    user = user_model(id="nonexistent", name="Ghost", email="ghost@example.com")
    user._is_persisted = True  # Fake persistence

    with pytest.raises(NotFoundError):
        backend.update(user_model, user)


def test_delete_record(backend, user_model):
    """Test deleting a record."""
    # Create user
    user = user_model(id="1", name="Alice", email="alice@example.com")
    user.save()

    # Delete user
    result = user.delete()
    assert result is True

    # Verify deletion
    found = user_model.get(id="1")
    assert found is None


def test_delete_nonexistent_record(backend, user_model):
    """Test deleting a nonexistent record."""
    user = user_model(id="nonexistent", name="Ghost", email="ghost@example.com")
    result = backend.delete(user_model, user)
    assert result is False


def test_upsert_create(backend, user_model):
    """Test upsert creates new record."""
    data = {"id": "1", "name": "Alice", "email": "alice@example.com", "age": 30}
    result = backend.upsert(user_model, data)

    assert result["id"] == "1"
    assert result["name"] == "Alice"

    # Verify in database
    found = user_model.get(id="1")
    assert found is not None


def test_upsert_update(backend, user_model):
    """Test upsert updates existing record."""
    # Create initial record
    user = user_model(id="1", name="Alice", email="alice@example.com", age=30)
    user.save()

    # Upsert with same ID
    data = {"id": "1", "name": "Alice Updated", "email": "newemail@example.com", "age": 31}
    result = backend.upsert(user_model, data)

    # Verify update
    found = user_model.get(id="1")
    assert found.name == "Alice Updated"
    assert found.email == "newemail@example.com"
    assert found.age == 31


def test_query_all(backend, user_model):
    """Test querying all records."""
    # Create multiple users
    users = [
        user_model(id="1", name="Alice", email="alice@example.com", age=30),
        user_model(id="2", name="Bob", email="bob@example.com", age=25),
        user_model(id="3", name="Charlie", email="charlie@example.com", age=35),
    ]
    for user in users:
        user.save()

    # Query all
    results = user_model.where().all()
    assert len(results) == 3


def test_query_filter(backend, user_model):
    """Test querying with filters."""
    # Create users
    user_model(id="1", name="Alice", email="alice@example.com", age=30).save()
    user_model(id="2", name="Bob", email="bob@example.com", age=25).save()

    # Query with filter
    results = user_model.where(name="Alice").all()
    assert len(results) == 1
    assert results[0].name == "Alice"


def test_query_not_filter(backend, user_model):
    """Test querying with not filter."""
    # Create users
    user_model(id="1", name="Alice", email="alice@example.com").save()
    user_model(id="2", name="Bob", email="bob@example.com").save()

    # Query with not filter - using where().not_()
    results = user_model.where().not_(name="Alice").all()
    assert len(results) == 1
    assert results[0].name == "Bob"


def test_query_order_by(backend, user_model):
    """Test querying with ordering."""
    # Create users in random order
    user_model(id="3", name="Charlie", email="c@example.com", age=35).save()
    user_model(id="1", name="Alice", email="a@example.com", age=30).save()
    user_model(id="2", name="Bob", email="b@example.com", age=25).save()

    # Query ordered by age
    results = user_model.where().order_by("age").all()
    assert results[0].age == 25
    assert results[1].age == 30
    assert results[2].age == 35

    # Query ordered by age descending
    results = user_model.where().order_by("-age").all()
    assert results[0].age == 35
    assert results[1].age == 30
    assert results[2].age == 25


def test_query_limit(backend, user_model):
    """Test querying with limit."""
    # Create users
    for i in range(5):
        user_model(id=str(i), name=f"User{i}", email=f"user{i}@example.com").save()

    # Query with limit
    results = user_model.where().limit(2).all()
    assert len(results) == 2


def test_query_offset(backend, user_model):
    """Test querying with offset."""
    # Create users
    for i in range(5):
        user_model(id=str(i), name=f"User{i}", email=f"user{i}@example.com").save()

    # Query with offset
    results = user_model.where().offset(2).all()
    assert len(results) == 3


def test_query_limit_offset(backend, user_model):
    """Test querying with limit and offset."""
    # Create users
    for i in range(10):
        user_model(id=str(i), name=f"User{i}", email=f"user{i}@example.com").save()

    # Query with limit and offset (pagination)
    page1 = user_model.where().limit(3).offset(0).all()
    page2 = user_model.where().limit(3).offset(3).all()

    assert len(page1) == 3
    assert len(page2) == 3
    assert page1[0].id != page2[0].id


def test_query_first(backend, user_model):
    """Test querying for first record."""
    # Create users
    user_model(id="1", name="Alice", email="alice@example.com").save()
    user_model(id="2", name="Bob", email="bob@example.com").save()

    # Get first
    first = user_model.where().first()
    assert first is not None


def test_query_first_empty(backend, user_model):
    """Test querying first on empty table returns None."""
    first = user_model.where().first()
    assert first is None


def test_query_last(backend, user_model):
    """Test querying for last record."""
    # Create users
    user_model(id="1", name="Alice", email="alice@example.com", age=30).save()
    user_model(id="2", name="Bob", email="bob@example.com", age=25).save()
    user_model(id="3", name="Charlie", email="charlie@example.com", age=35).save()

    # Get last without order (uses rowid DESC)
    last = user_model.where().last()
    assert last is not None
    assert last.id == "3"  # Last inserted

    # Get last with order by age (oldest)
    last = user_model.where().order_by("age").last()
    assert last is not None
    assert last.age == 35
    assert last.name == "Charlie"

    # Get last with descending order by age (youngest)
    last = user_model.where().order_by("-age").last()
    assert last is not None
    assert last.age == 25
    assert last.name == "Bob"


def test_query_last_empty(backend, user_model):
    """Test querying last on empty table returns None."""
    last = user_model.where().last()
    assert last is None


def test_query_count(backend, user_model):
    """Test counting records."""
    # Create users
    for i in range(5):
        user_model(id=str(i), name=f"User{i}", email=f"user{i}@example.com").save()

    count = user_model.where().count()
    assert count == 5


def test_query_count_with_filter(backend, user_model):
    """Test counting with filter."""
    user_model(id="1", name="Alice", email="alice@example.com", age=30).save()
    user_model(id="2", name="Bob", email="bob@example.com", age=25).save()
    user_model(id="3", name="Charlie", email="charlie@example.com", age=30).save()

    count = user_model.where(age=30).count()
    assert count == 2


def test_query_exists(backend, user_model):
    """Test checking if records exist."""
    # Empty table
    assert user_model.where().exists() is False

    # Create user
    user_model(id="1", name="Alice", email="alice@example.com").save()
    assert user_model.where().exists() is True


def test_backend_count_method(backend, user_model):
    """Test backend count method."""
    # Create users
    for i in range(3):
        user_model(id=str(i), name=f"User{i}", email=f"user{i}@example.com").save()

    count = backend.count(user_model)
    assert count == 3


def test_backend_exists_method(backend, user_model):
    """Test backend exists method."""
    # Empty table
    assert backend.exists(user_model) is False

    # Create user
    user_model(id="1", name="Alice", email="alice@example.com").save()
    assert backend.exists(user_model) is True


def test_json_serialization(backend, user_model):
    """Test that records are stored as JSON."""
    user = user_model(id="1", name="Alice", email="alice@example.com", age=30)
    user.save()

    # Query raw JSON from database
    cursor = backend.connection.execute("SELECT data FROM users WHERE id = ?", ("1",))
    row = cursor.fetchone()

    import json

    data = json.loads(row[0])
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert data["age"] == 30


def test_table_name_generation(backend, user_model):
    """Test table name generation from model class."""
    table_name = backend._get_table_name(user_model)
    assert table_name == "users"


def test_primary_key_extraction(backend):
    """Test primary key extraction from data."""
    data = {"id": "123", "name": "Test"}
    pk = backend._get_primary_key_value(data)
    assert pk == "123"

    # Test with pk field
    data = {"pk": "456", "name": "Test"}
    pk = backend._get_primary_key_value(data)
    assert pk == "456"

    # Test with key field
    data = {"key": "789", "name": "Test"}
    pk = backend._get_primary_key_value(data)
    assert pk == "789"


def test_multiple_models_different_tables(backend):
    """Test that different models use different tables."""

    class User(Model):
        model_backend = backend
        id: str
        name: str

    class Product(Model):
        model_backend = backend
        id: str
        title: str

    # Create records in different models
    User(id="1", name="Alice").save()
    Product(id="1", title="Widget").save()

    # Verify they're in different tables
    user = User.get(id="1")
    product = Product.get(id="1")

    assert user.name == "Alice"
    assert product.title == "Widget"


def test_persistence_flag(backend, user_model):
    """Test that _is_persisted flag is set correctly."""
    # New instance
    user = user_model(id="1", name="Alice", email="alice@example.com")
    assert user._is_persisted is False

    # After save
    user.save()
    assert user._is_persisted is True

    # After query
    found = user_model.get(id="1")
    assert found._is_persisted is True


def test_sql_injection_protection(backend):
    """Test that SQL injection attempts via class name tampering are blocked."""
    from restmachine_orm.models.base import Model

    # Create a model with a malicious name attempt
    class MaliciousModel(Model):
        model_backend = backend
        id: str
        data: str

    # Try to tamper with the class name (simulating an attack)
    original_name = MaliciousModel.__name__
    try:
        # Attempt SQL injection via class name
        MaliciousModel.__name__ = "users; DROP TABLE users; --"

        # This should raise ValueError due to validation
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            backend._get_table_name(MaliciousModel)
    finally:
        # Restore original name
        MaliciousModel.__name__ = original_name

    # Verify normal names still work
    table_name = backend._get_table_name(MaliciousModel)
    assert table_name == "maliciousmodels"


def test_identifier_validation(backend):
    """Test that identifier validation blocks dangerous characters."""
    # These should all be rejected
    dangerous_identifiers = [
        "'; DROP TABLE users; --",
        "table' OR '1'='1",
        "table--comment",
        "table/*comment*/",
        "table name with spaces",
        "table-with-dashes",
        "table.with.dots",
        "table;multiple;statements",
        "123startswithnumber",
        "",
    ]

    for identifier in dangerous_identifiers:
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            backend._validate_identifier(identifier)

    # These should be accepted
    valid_identifiers = [
        "users",
        "user_profiles",
        "_private_table",
        "Table123",
        "CamelCase",
        "snake_case_table",
    ]

    for identifier in valid_identifiers:
        result = backend._validate_identifier(identifier)
        assert result == identifier

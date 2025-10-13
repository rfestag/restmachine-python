# Multi-Backend Testing

RestMachine ORM includes a testing framework that lets you write tests once and run them against all backends automatically.

## Architecture

The testing framework follows Dave Farley's 4-layer testing architecture:

```
┌─────────────────────────────────────┐
│  Test Layer                         │
│  (test methods)                     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  DSL Layer                          │
│  (backend-agnostic operations)      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Driver Layer                       │
│  (backend-specific implementations) │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  System Under Test                  │
│  (RestMachine ORM)                  │
└─────────────────────────────────────┘
```

## Quick Example

```python
from typing import List, Type
from restmachine_orm import Model, Field
from restmachine_orm_testing import MultiBackendTestBase

class User(Model):
    id: str = Field(primary_key=True)
    email: str
    name: str

class TestUserModel(MultiBackendTestBase):
    def get_test_models(self) -> List[Type]:
        return [User]

    def test_create_user(self, orm):
        """This test runs against ALL enabled backends."""
        orm_client, backend_name = orm

        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        assert user.id == "user-123"
        assert user.email == "alice@example.com"
```

When you run this test, it automatically runs against all enabled backends (by default, just `inmemory`).

## Writing Tests

### Basic Structure

```python
from restmachine_orm_testing import MultiBackendTestBase
from typing import List, Type

class TestYourFeature(MultiBackendTestBase):
    def get_test_models(self) -> List[Type]:
        """Return models used in tests."""
        return [User, TodoItem]

    def test_something(self, orm):
        """Each test receives orm fixture."""
        orm_client, backend_name = orm
        # Use orm_client DSL here
```

### Enabling Multiple Backends

```python
class TestUserCRUD(MultiBackendTestBase):
    ENABLED_BACKENDS = ['inmemory', 'dynamodb']

    def get_test_models(self) -> List[Type]:
        return [User]

    def test_create_user(self, orm):
        # Runs twice: once for InMemory, once for DynamoDB
        orm_client, backend_name = orm
        user = orm_client.create_and_verify(User, id="user-1", name="Alice")
```

### Skip Specific Backends

```python
from restmachine_orm_testing import skip_backend, only_backends

class TestFeatures(MultiBackendTestBase):
    @skip_backend('dynamodb')
    def test_memory_only(self, orm):
        """Skipped for DynamoDB."""
        pass

    @only_backends('inmemory')
    def test_only_inmemory(self, orm):
        """Only runs for InMemory."""
        pass
```

## DSL Methods

The DSL provides backend-agnostic operations:

### Create

```python
# Create and verify
user = orm_client.create_and_verify(
    User,
    id="user-123",
    email="alice@example.com",
    name="Alice"
)

# Expect creation to fail
from restmachine_orm.backends.base import DuplicateKeyError

orm_client.expect_create_failure(
    User,
    DuplicateKeyError,
    id="user-123",  # Duplicate
    email="different@example.com"
)
```

### Read

```python
# Get and verify exists
user = orm_client.get_and_verify_exists(User, id="user-123")

# Verify doesn't exist
orm_client.get_and_verify_not_exists(User, id="nonexistent")
```

### Update

```python
# Update and verify
updated = orm_client.update_and_verify(
    user,
    age=31,
    name="Alice Smith"
)

# Expect update to fail
from restmachine_orm.backends.base import NotFoundError

nonexistent = User(id="fake", email="fake@example.com", name="Fake")
orm_client.expect_update_failure(
    nonexistent,
    NotFoundError,
    age=25
)
```

### Delete

```python
# Delete and verify
orm_client.delete_and_verify(user)
```

### Upsert

```python
# Upsert and verify
user = orm_client.upsert_and_verify(
    User,
    id="user-123",
    email="alice.new@example.com",
    name="Alice"
)
```

### Query

```python
# Query with filters
result = orm_client.query_models(
    User,
    filters={"age__gte": 25, "age__lte": 50"},
    order_by=["age"],
    limit=10
)
assert result.success
users = result.data

# Query and verify count
users = orm_client.query_and_verify_count(
    User,
    expected_count=3,
    filters={"age__gte": 30}
)

# Count matching records
count = orm_client.count_models(User, age__gte=30)

# Check if exists
exists = orm_client.model_exists(User, email="alice@example.com")

# Get all
all_users = orm_client.all_models(User)
```

## Complete Example

```python
from typing import List, Type
from datetime import datetime
from restmachine_orm import Model, Field
from restmachine_orm.backends.base import DuplicateKeyError, NotFoundError
from restmachine_orm_testing import MultiBackendTestBase

class User(Model):
    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, default=0)
    created_at: datetime | None = Field(None, auto_now_add=True)

class TestUserModel(MultiBackendTestBase):
    ENABLED_BACKENDS = ['inmemory', 'dynamodb']

    def get_test_models(self) -> List[Type]:
        return [User]

    def test_create_user(self, orm):
        """Test creating a user."""
        orm_client, backend_name = orm

        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.created_at is not None

    def test_create_duplicate_fails(self, orm):
        """Test duplicate creation fails."""
        orm_client, backend_name = orm

        orm_client.create_and_verify(
            User,
            id="user-123",
            email="test@example.com",
            name="Test"
        )

        orm_client.expect_create_failure(
            User,
            DuplicateKeyError,
            id="user-123",
            email="different@example.com",
            name="Different"
        )

    def test_get_user(self, orm):
        """Test retrieving a user."""
        orm_client, backend_name = orm

        # Create user
        orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        # Get user
        user = orm_client.get_and_verify_exists(User, id="user-123")
        assert user.email == "alice@example.com"

        # Verify nonexistent
        orm_client.get_and_verify_not_exists(User, id="nonexistent")

    def test_update_user(self, orm):
        """Test updating a user."""
        orm_client, backend_name = orm

        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )

        updated = orm_client.update_and_verify(
            user,
            age=31,
            name="Alice Smith"
        )

        assert updated.age == 31
        assert updated.name == "Alice Smith"

    def test_delete_user(self, orm):
        """Test deleting a user."""
        orm_client, backend_name = orm

        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        orm_client.delete_and_verify(user)
        orm_client.get_and_verify_not_exists(User, id="user-123")

    def test_upsert_user(self, orm):
        """Test upserting a user."""
        orm_client, backend_name = orm

        # Initial upsert (creates)
        user1 = orm_client.upsert_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice",
            age=30
        )
        assert user1.age == 30

        # Second upsert (updates)
        user2 = orm_client.upsert_and_verify(
            User,
            id="user-123",
            email="alice.new@example.com",
            name="Alice Jones",
            age=31
        )
        assert user2.age == 31
        assert user2.email == "alice.new@example.com"

    def test_query_users(self, orm):
        """Test querying users."""
        orm_client, backend_name = orm

        # Create test data
        orm_client.create_and_verify(User, id="user-1", email="a@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="b@example.com", name="Bob", age=25)
        orm_client.create_and_verify(User, id="user-3", email="c@example.com", name="Carol", age=35)

        # Query with filters
        users = orm_client.query_and_verify_count(
            User,
            expected_count=2,
            filters={"age__gte": 30}
        )

        ages = [u.age for u in users]
        assert 30 in ages
        assert 35 in ages

    def test_count_and_exists(self, orm):
        """Test counting and existence checks."""
        orm_client, backend_name = orm

        # Create users
        orm_client.create_and_verify(User, id="user-1", email="a@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="b@example.com", name="Bob", age=25)

        # Count
        count = orm_client.count_models(User, age__gte=30)
        assert count == 1

        # Exists
        exists = orm_client.model_exists(User, email="a@example.com")
        assert exists

        not_exists = orm_client.model_exists(User, email="nonexistent@example.com")
        assert not not_exists
```

## Adding a New Backend

To add support for a new backend:

### 1. Create Driver

```python
# In your backend package
from restmachine_orm_testing import DriverInterface, CreateOperation, OperationResult

class MyBackendDriver(DriverInterface):
    def __init__(self, **config):
        self.backend = MyBackend(**config)

    def execute_create(self, operation: CreateOperation) -> OperationResult:
        try:
            self.setup_backend(operation.model_class)
            instance = operation.model_class.create(**operation.data)
            return OperationResult(
                success=True,
                instance=instance,
                data=instance.model_dump()
            )
        except Exception as e:
            return OperationResult(success=False, error=e)

    # Implement other methods...

    def get_backend_name(self) -> str:
        return "mybackend"

    def setup_backend(self, model_class):
        model_class.model_backend = self.backend
```

### 2. Register Driver

In your package's `conftest.py`:

```python
import pytest
from restmachine_orm_testing import MultiBackendTestBase
from my_backend.testing import MyBackendDriver

# Register driver
original_create_driver = MultiBackendTestBase.create_driver

@classmethod
def patched_create_driver(cls, backend_name: str):
    if backend_name == 'mybackend':
        return MyBackendDriver(config_option="value")
    return original_create_driver(backend_name)

MultiBackendTestBase.create_driver = patched_create_driver
```

### 3. Enable in Tests

```python
class TestFeatures(MultiBackendTestBase):
    ENABLED_BACKENDS = ['inmemory', 'mybackend']

    def get_test_models(self):
        return [User]

    def test_something(self, orm):
        # Now runs for both backends
        pass
```

## Benefits

1. **Write Once, Test Everywhere**: Same test code for all backends
2. **Backend Consistency**: Ensures all backends behave the same
3. **Easy Backend Addition**: Just implement driver and register
4. **Confidence**: New features work everywhere before release
5. **Maintainability**: Changes to DSL apply to all backends

## See Also

- [Installation](../getting-started/installation.md) - Install backends
- [DynamoDB Backend](../backends/dynamodb.md) - Test with DynamoDB
- [API Reference](../api/backends.md) - Complete API documentation

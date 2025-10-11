# RestMachine ORM Testing Framework

This document explains the testing framework for RestMachine ORM, which follows the same pattern as RestMachine's testing architecture (Dave Farley's 4-layer testing architecture).

## Architecture Overview

The testing framework consists of 4 layers:

1. **Test Layer** - Actual test methods (e.g., `test_create_user`)
2. **DSL Layer** - Business-focused description of ORM operations
3. **Driver Layer** - Translates DSL operations to backend-specific calls
4. **System Under Test** - The RestMachine ORM library

## Key Components

### 1. DSL (Domain-Specific Language)

Located in `restmachine_orm_testing.dsl`, the DSL provides a high-level, backend-agnostic API for ORM operations:

```python
from restmachine_orm_testing import OrmDsl

# Create model
user = orm_client.create_and_verify(
    User,
    id="user-123",
    email="alice@example.com",
    name="Alice"
)

# Get model
user = orm_client.get_and_verify_exists(User, id="user-123")

# Update model
updated = orm_client.update_and_verify(user, age=31, name="Alice Smith")

# Delete model
orm_client.delete_and_verify(user)

# Upsert model
user = orm_client.upsert_and_verify(User, id="user-123", email="new@example.com")

# Query models
users = orm_client.query_and_verify_count(User, expected_count=3, age__gte=18)
```

### 2. Drivers

Located in `restmachine_orm_testing.drivers`, drivers know how to execute DSL operations against specific backends:

- **InMemoryDriver** - Tests against in-memory storage (reference implementation)
- **DynamoDBDriver** - Tests against DynamoDB (will be in separate package)

Each driver implements the `DriverInterface`:

```python
class DriverInterface(ABC):
    @abstractmethod
    def execute_create(self, operation: CreateOperation) -> OperationResult:
        pass

    @abstractmethod
    def execute_get(self, operation: GetOperation) -> OperationResult:
        pass

    # ... other operations
```

### 3. Multi-Backend Test Base

Located in `restmachine_orm_testing.multi_backend_base`, the base class automatically runs tests against all configured backends:

```python
from restmachine_orm_testing import MultiBackendTestBase, multi_backend_test_class

@multi_backend_test_class()
class TestUserModel(MultiBackendTestBase):
    def get_test_models(self) -> List[Type]:
        """Return models used in these tests."""
        return [User]

    def test_create_user(self, orm):
        """Test runs automatically against all enabled backends."""
        orm_client, backend_name = orm

        user = orm_client.create_and_verify(
            User,
            id="user-123",
            email="alice@example.com",
            name="Alice"
        )

        assert user.id == "user-123"
```

## Writing Tests

### Basic Test Structure

```python
from restmachine_orm_testing import MultiBackendTestBase, multi_backend_test_class
from restmachine_orm import Model, Field

# Define your models
class User(Model):
    id: str = Field(primary_key=True)
    email: str
    name: str

# Create test class
@multi_backend_test_class()
class TestUserOperations(MultiBackendTestBase):
    def get_test_models(self) -> List[Type]:
        return [User]

    def test_something(self, orm):
        orm_client, backend_name = orm
        # Your test code using orm_client DSL
```

### Enabling Multiple Backends

To test against multiple backends, configure `ENABLED_BACKENDS`:

```python
@multi_backend_test_class(enabled_backends=['inmemory', 'dynamodb'])
class TestUserOperations(MultiBackendTestBase):
    def get_test_models(self) -> List[Type]:
        return [User]

    def test_something(self, orm):
        orm_client, backend_name = orm
        # This test runs twice: once for InMemory, once for DynamoDB
```

### Skipping Specific Backends

Use decorators to skip tests for specific backends:

```python
from restmachine_orm_testing import skip_backend, only_backends

class TestUserOperations(MultiBackendTestBase):
    @skip_backend('dynamodb', 'This test requires in-memory features')
    def test_something(self, orm):
        # Skipped for DynamoDB backend
        pass

    @only_backends('inmemory')
    def test_inmemory_specific(self, orm):
        # Only runs for InMemory backend
        pass
```

### Available DSL Methods

#### Creation and Verification
- `create_and_verify()` - Create and verify success
- `expect_create_failure()` - Expect creation to fail

#### Retrieval
- `get_and_verify_exists()` - Get and verify it exists
- `get_and_verify_not_exists()` - Verify it doesn't exist

#### Update
- `update_and_verify()` - Update and verify success
- `expect_update_failure()` - Expect update to fail

#### Deletion
- `delete_and_verify()` - Delete and verify success

#### Upsert
- `upsert_and_verify()` - Upsert and verify success

#### Queries
- `query_models()` - Query with filters, ordering, limit, offset
- `query_and_verify_count()` - Query and verify result count
- `count_models()` - Count matching records
- `model_exists()` - Check if records exist
- `all_models()` - Get all records

#### Utilities
- `clear_storage()` - Clear storage for testing
- `get_backend_name()` - Get current backend name
- `is_backend()` - Check if current backend matches name

## Example: Complete Test File

```python
"""
Tests for User model CRUD operations.

These tests run against all enabled backends automatically.
"""

from typing import List, Type
from restmachine_orm import Model, Field
from restmachine_orm.backends.base import DuplicateKeyError
from restmachine_orm_testing import MultiBackendTestBase, multi_backend_test_class


class User(Model):
    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, default=0)


@multi_backend_test_class()
class TestUserCRUD(MultiBackendTestBase):
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

    def test_create_duplicate_fails(self, orm):
        """Test that creating duplicate raises error."""
        orm_client, backend_name = orm

        # Create first user
        orm_client.create_and_verify(User, id="user-123", email="test@example.com", name="Test")

        # Attempt duplicate
        orm_client.expect_create_failure(
            User,
            DuplicateKeyError,
            id="user-123",
            email="different@example.com",
            name="Different"
        )

    def test_query_users(self, orm):
        """Test querying users."""
        orm_client, backend_name = orm

        # Create test data
        orm_client.create_and_verify(User, id="user-1", email="a@example.com", name="Alice", age=30)
        orm_client.create_and_verify(User, id="user-2", email="b@example.com", name="Bob", age=25)
        orm_client.create_and_verify(User, id="user-3", email="c@example.com", name="Carol", age=35)

        # Query with filters
        result = orm_client.query_models(User, filters={"age__gte": 30})
        assert result.success
        assert len(result.data) == 2
```

## Backend-Specific Drivers

### Creating a Driver for a New Backend

To add support for a new backend:

1. Create a driver class implementing `DriverInterface`
2. Add it to the driver map in `create_driver()`
3. Enable it in test classes with `@multi_backend_test_class(enabled_backends=['inmemory', 'your_backend'])`

Example:

```python
class MyBackendDriver(DriverInterface):
    def __init__(self, config):
        self.backend = MyBackend(config)

    def execute_create(self, operation: CreateOperation) -> OperationResult:
        try:
            self.setup_backend(operation.model_class)
            instance = operation.model_class.create(**operation.data)
            return OperationResult(success=True, instance=instance, data=instance.model_dump())
        except Exception as e:
            return OperationResult(success=False, error=e)

    # ... implement other methods
```

## Separate Backend Packages

Backend implementations should live in separate packages:

- `restmachine-orm` - Core ORM + InMemory backend (reference implementation)
- `restmachine-orm-dynamodb` - DynamoDB backend + DynamoDB driver
- `restmachine-orm-opensearch` - OpenSearch backend + OpenSearch driver

Each backend package:
1. Imports DSL from `restmachine-orm-testing`
2. Provides its own driver implementation
3. Can monkey-patch `create_driver()` via conftest.py to register itself

Example `conftest.py` in `restmachine-orm-dynamodb`:

```python
# conftest.py in restmachine-orm-dynamodb package
import pytest
from restmachine_orm_testing import MultiBackendTestBase
from restmachine_orm_dynamodb.testing import DynamoDBDriver

# Register DynamoDB driver
original_create_driver = MultiBackendTestBase.create_driver

@classmethod
def patched_create_driver(cls, backend_name: str):
    if backend_name == 'dynamodb':
        return DynamoDBDriver(table_name="test-table", region_name="us-east-1")
    return original_create_driver(backend_name)

MultiBackendTestBase.create_driver = patched_create_driver
```

## Benefits

1. **Backend Agnostic** - Same test code works for all backends
2. **Easy to Add Backends** - Just implement a driver and register it
3. **Confidence** - Ensures new features work across all backends
4. **Maintainability** - Changes to DSL automatically apply to all backends
5. **Clear Separation** - DSL layer isolates test logic from backend details

## Next Steps

To complete the refactoring:

1. ✅ Create testing DSL in `restmachine-orm`
2. ✅ Create driver interface and InMemory driver
3. ✅ Create multi-backend test base
4. ✅ Create example tests using new DSL
5. Move old tests (`test_memory_backend.py`, `test_models.py`) to use new DSL
6. Extract DynamoDB backend to `restmachine-orm-dynamodb` package
7. Create DynamoDB driver in that package
8. Update DynamoDB tests to use DSL

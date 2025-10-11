# In-Memory Backend

The in-memory backend stores data in Python dictionaries, perfect for development, testing, and examples.

## Features

- Zero external dependencies
- Fast operations
- Automatic cleanup
- Perfect for unit tests

## Basic Usage

```python
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter

# Create backend
backend = InMemoryBackend(InMemoryAdapter())

class User(Model):
    class Meta:
        backend = backend

    id: str = Field(primary_key=True)
    email: str
    name: str

# Use normally
user = User.create(id="user-1", email="alice@example.com", name="Alice")
```

## Shared vs Isolated Backends

### Shared Backend

```python
# Shared across all models
shared_backend = InMemoryBackend(InMemoryAdapter())

class User(Model):
    class Meta:
        backend = shared_backend

class TodoItem(Model):
    class Meta:
        backend = shared_backend

# Both use same backend
user = User.create(id="user-1", name="Alice")
todo = TodoItem.create(id="todo-1", title="Task")
```

### Isolated Backends

```python
# Each model has own storage
class User(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

class TodoItem(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

# Completely independent storage
```

## Clearing Data

```python
backend = InMemoryBackend(InMemoryAdapter())

# Create some data
User.create(id="user-1", name="Alice")
User.create(id="user-2", name="Bob")

# Clear specific model
backend.clear(User)
assert User.where().count() == 0

# Clear all data
backend.clear()
```

## Testing

The in-memory backend is ideal for tests:

```python
import pytest

@pytest.fixture
def backend():
    backend = InMemoryBackend(InMemoryAdapter())
    yield backend
    backend.clear()  # Cleanup after test

@pytest.fixture
def user_model(backend):
    class User(Model):
        class Meta:
            backend = backend

        id: str = Field(primary_key=True)
        name: str

    return User

def test_user_crud(user_model):
    # Test with fresh backend
    user = user_model.create(id="user-1", name="Alice")
    assert user.name == "Alice"

    retrieved = user_model.get(id="user-1")
    assert retrieved.name == "Alice"

    # Data is automatically cleaned up after test
```

## Limitations

- Data lost when process ends
- No persistence
- No transactions
- Not suitable for production

The in-memory backend is designed for:
- Development and prototyping
- Unit tests
- Examples and tutorials
- Learning the ORM API

For production use, see:
- [DynamoDB Backend](dynamodb.md) - AWS DynamoDB
- OpenSearch Backend (coming soon)

## Performance

The in-memory backend is extremely fast:

- Create: O(1)
- Get: O(1)
- Update: O(1)
- Delete: O(1)
- Query: O(n) - scans all records

For performance testing, use the in-memory backend as a baseline.

## See Also

- [DynamoDB Backend](dynamodb.md) - Persistent storage
- [Multi-Backend Testing](../testing/multi-backend.md) - Test across backends

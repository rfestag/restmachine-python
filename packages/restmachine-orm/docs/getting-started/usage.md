# Basic Usage

This guide covers the core features of RestMachine ORM.

## Defining Models

Models are defined by inheriting from `Model` and using Pydantic fields:

```python
from datetime import datetime
from typing import Optional
from restmachine_orm import Model, Field

class User(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = Field(max_length=100)
    age: int = Field(ge=0, le=150, default=0)
    is_active: bool = True
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)
```

### Field Options

- `primary_key=True`: Mark as primary key (required for at least one field)
- `unique=True`: Ensure uniqueness
- `index=True`: Create index for efficient queries
- `default`: Default value
- `auto_now_add=True`: Set to current timestamp on creation
- `auto_now=True`: Update to current timestamp on save

### Validation

Models inherit Pydantic's validation:

```python
class Product(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    sku: str = Field(primary_key=True, pattern=r'^[A-Z]{3}\d{6}$')
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    stock: int = Field(ge=0, default=0)

# Valid
product = Product.create(
    sku="ABC123456",
    name="Widget",
    price=19.99,
    stock=100
)

# Invalid - raises ValidationError
product = Product.create(
    sku="invalid",  # Doesn't match pattern
    name="",  # Too short
    price=-5.0,  # Must be > 0
    stock=-10  # Must be >= 0
)
```

## CRUD Operations

### Create

```python
# Basic creation
user = User.create(
    id="user-123",
    email="alice@example.com",
    name="Alice"
)

# With validation
try:
    user = User.create(id="", email="invalid", name="X" * 200)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### Read

```python
# Get by primary key
user = User.get(id="user-123")
if user:
    print(f"Found: {user.name}")
else:
    print("User not found")

# Get all
all_users = User.all()

# First/last
first_user = User.where().first()
last_user = User.where().order_by("created_at").last()
```

### Update

```python
# Get and update
user = User.get(id="user-123")
user.name = "Alice Smith"
user.age = 31
user.save()

# auto_now fields are automatically updated
print(user.updated_at)  # Current timestamp
```

### Delete

```python
# Delete instance
user = User.get(id="user-123")
success = user.delete()  # Returns True if deleted, False if not found

# Verify
user = User.get(id="user-123")
print(user)  # None
```

### Upsert

```python
# Insert or update
user = User.upsert(
    id="user-123",
    email="alice@example.com",
    name="Alice"
)

# Overwrites if exists, creates if doesn't
user = User.upsert(
    id="user-123",  # Same ID
    email="alice.new@example.com",  # Different email
    name="Alice Jones"
)
```

## Querying

RestMachine ORM provides a chainable query interface:

### Basic Filters

```python
# Exact match
users = User.where().and_(age=30).all()

# Multiple conditions (AND)
users = User.where().and_(age=30, is_active=True).all()

# NOT condition
users = User.where().not_(age=30).all()
```

### Comparison Operators

```python
# Greater than / less than
users = User.where().and_(age__gt=25).all()
users = User.where().and_(age__gte=25).all()
users = User.where().and_(age__lt=50).all()
users = User.where().and_(age__lte=50).all()

# Combine conditions
users = User.where() \
    .and_(age__gte=25) \
    .and_(age__lte=50) \
    .and_(is_active=True) \
    .all()
```

### Ordering

```python
# Ascending order
users = User.where().order_by("age").all()
users = User.where().order_by("name").all()

# Descending order
users = User.where().order_by("-age").all()

# Multiple fields
users = User.where().order_by("age", "-created_at").all()
```

### Pagination

```python
# Limit
users = User.where().limit(10).all()

# Offset
users = User.where().offset(20).limit(10).all()

# Cursor-based (for large datasets)
results, cursor = User.where().limit(10).paginate()
if cursor:
    more_results, next_cursor = User.where().limit(10).cursor(cursor).paginate()
```

### Aggregation

```python
# Count
total = User.where().count()
active = User.where().and_(is_active=True).count()

# Exists
has_admin = User.where().and_(role="admin").exists()
```

## Working with Relationships

RestMachine ORM doesn't have built-in relationship management, but you can implement patterns:

```python
class Author(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    name: str

class Book(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    title: str
    author_id: str  # Foreign key

    def get_author(self) -> Optional[Author]:
        """Get related author."""
        return Author.get(id=self.author_id)

# Usage
author = Author.create(id="author-1", name="Alice")
book = Book.create(id="book-1", title="Python Guide", author_id="author-1")

# Get related author
author = book.get_author()
print(f"{book.title} by {author.name}")
```

## Error Handling

```python
from restmachine_orm.backends.base import (
    NotFoundError,
    DuplicateKeyError,
    ValidationError
)

# Duplicate key
try:
    User.create(id="user-1", email="alice@example.com", name="Alice")
    User.create(id="user-1", email="bob@example.com", name="Bob")  # Duplicate
except DuplicateKeyError:
    print("User with this ID already exists")

# Not found
user = User(id="nonexistent", email="test@example.com", name="Test")
user._is_persisted = True  # Pretend it exists
try:
    user.save()
except NotFoundError:
    print("Cannot update: user not found")

# Validation errors
from pydantic import ValidationError
try:
    User.create(id="", email="invalid", name="")
except ValidationError as e:
    for error in e.errors():
        print(f"{error['loc']}: {error['msg']}")
```

## Next Steps

- [DynamoDB Backend](../backends/dynamodb.md) - Persistent storage with DynamoDB
- [Multi-Backend Testing](../testing/multi-backend.md) - Test models across backends
- [API Reference](../api/models.md) - Complete API documentation

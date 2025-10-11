# Quick Start

This guide will walk you through creating your first RestMachine ORM models and performing basic operations.

## Your First Model

Let's create a simple User model:

```python
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter

class User(Model):
    """A simple user model."""

    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
```

Key points:
- Models inherit from `Model`
- Use Pydantic's `Field` for metadata
- Configure backend in `Meta` class
- At least one field must be marked `primary_key=True`

## Create Records

```python
# Create a user
user = User.create(
    id="user-1",
    email="alice@example.com",
    name="Alice Smith",
    age=30
)

print(f"Created user: {user.name}")
# Output: Created user: Alice Smith
```

## Read Records

```python
# Get by primary key
user = User.get(id="user-1")
if user:
    print(f"Found: {user.email}")

# Query with filters
users = User.where().and_(age__gte=25).all()
for user in users:
    print(f"{user.name} is {user.age} years old")
```

## Update Records

```python
# Get the user
user = User.get(id="user-1")

# Update fields
user.age = 31
user.name = "Alice Jones"

# Save changes
user.save()
```

## Delete Records

```python
# Get the user
user = User.get(id="user-1")

# Delete
success = user.delete()
if success:
    print("User deleted")

# Verify deletion
user = User.get(id="user-1")
print(user)  # Output: None
```

## Complete Example

Here's a complete working example:

```python
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter

# Define model
class TodoItem(Model):
    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)

# Create todos
todo1 = TodoItem.create(
    id="todo-1",
    title="Write documentation",
    priority=5
)

todo2 = TodoItem.create(
    id="todo-2",
    title="Write tests",
    priority=4,
    completed=True
)

todo3 = TodoItem.create(
    id="todo-3",
    title="Deploy to production",
    priority=5
)

# Query incomplete high-priority items
urgent_todos = TodoItem.where() \
    .and_(completed=False) \
    .and_(priority__gte=4) \
    .order_by("-priority") \
    .all()

print("Urgent incomplete todos:")
for todo in urgent_todos:
    print(f"  [{todo.priority}] {todo.title}")

# Output:
# Urgent incomplete todos:
#   [5] Write documentation
#   [5] Deploy to production

# Complete a todo
todo1.completed = True
todo1.save()

# Count completed
completed_count = TodoItem.where().and_(completed=True).count()
print(f"\nCompleted: {completed_count} todos")
# Output: Completed: 2 todos
```

## Next Steps

- [Basic Usage](usage.md) - Learn about querying, validation, and more
- [DynamoDB Backend](../backends/dynamodb.md) - Use DynamoDB for persistent storage
- [Multi-Backend Testing](../testing/multi-backend.md) - Test across backends

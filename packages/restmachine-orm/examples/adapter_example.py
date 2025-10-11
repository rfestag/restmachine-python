"""
Example: Adapter Pattern with RestMachine ORM

This example demonstrates:
- Using adapters to map models to different storage backends
- In-memory backend for testing/examples
- DynamoDB adapter for single-table design
- Composite keys with @partition_key and @sort_key decorators
"""

from datetime import datetime
from typing import Optional

from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm.backends import (
    InMemoryBackend,
    InMemoryAdapter,
    DynamoDBAdapter,
)


# ============================================================================
# EXAMPLE 1: Simple Model with InMemoryBackend
# ============================================================================

print("=" * 70)
print("EXAMPLE 1: Simple User Model (InMemoryBackend)")
print("=" * 70)


class User(Model):
    """Simple user model with InMemoryBackend."""

    class Meta:
        backend = InMemoryBackend(InMemoryAdapter())

    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)


# Create users
print("\n1. Creating users...")
alice = User.create(id="user-1", email="alice@example.com", name="Alice", age=30)
print(f"Created: {alice.name} ({alice.email})")

bob = User.create(id="user-2", email="bob@example.com", name="Bob", age=25)
print(f"Created: {bob.name} ({bob.email})")

# Query
print("\n2. Querying users...")
all_users = User.all()
print(f"Total users: {len(all_users)}")

adult_users = User.query().filter(age__gte=18).all()
print(f"Adult users: {len(adult_users)}")

# Get by ID
print("\n3. Getting user by ID...")
user = User.get(id="user-1")
if user:
    print(f"Found: {user.name}")

# Update
print("\n4. Updating user...")
alice.age = 31
alice.save()
print(f"Updated age to: {alice.age}")

# Delete
print("\n5. Deleting user...")
bob.delete()
print(f"Deleted: {bob.name}")

remaining = User.count()
print(f"Remaining users: {remaining}")


# ============================================================================
# EXAMPLE 2: DynamoDB Adapter with Composite Keys
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 2: Todo with DynamoDB Adapter (Composite Keys)")
print("=" * 70)


class TodoItem(Model):
    """
    Todo item demonstrating DynamoDB single-table design.

    The DynamoDBAdapter maps this model to DynamoDB format:
    - pk: partition key from @partition_key method
    - sk: sort key from @sort_key method
    - entity_type: "TodoItem" for filtering
    - All other fields as attributes
    """

    class Meta:
        # In production, this would connect to real DynamoDB
        # For this example, we use InMemoryBackend with DynamoDBAdapter
        # to show how the adapter transforms the data
        backend = InMemoryBackend(DynamoDBAdapter())

    user_id: str
    todo_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)

    @partition_key
    def pk(self) -> str:
        """Partition key: Group by user."""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort key: Allow chronological ordering."""
        if self.created_at:
            return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"
        return f"TODO#{self.todo_id}"


# Create todos
print("\n1. Creating todos...")
todo1 = TodoItem.create(
    user_id="alice",
    todo_id="todo-1",
    title="Write documentation"
)
print(f"Created: {todo1.title}")
print(f"  DynamoDB PK: {todo1.pk()}")
print(f"  DynamoDB SK: {todo1.sk()}")

# Look at the storage format
backend = TodoItem.Meta.backend
adapter = backend.adapter
storage_format = adapter.model_to_storage(todo1)
print(f"\n2. DynamoDB storage format:")
for key, value in storage_format.items():
    if key not in ['created_at', 'updated_at']:  # Skip timestamps for clarity
        print(f"  {key}: {value}")

# Create more todos
todo2 = TodoItem.create(
    user_id="alice",
    todo_id="todo-2",
    title="Review pull request"
)
print(f"\nCreated: {todo2.title}")

todo3 = TodoItem.create(
    user_id="bob",
    todo_id="todo-3",
    title="Deploy to production"
)
print(f"Created: {todo3.title}")

# Query - the adapter handles filtering by partition key
print("\n3. Querying todos...")
all_todos = TodoItem.all()
print(f"Total todos: {len(all_todos)}")

# The DynamoDB adapter enables efficient queries by partition key
# (In real DynamoDB, this would be a single-partition query)
alice_todos = TodoItem.query().all()  # Would filter by pk in real DynamoDB
print(f"All todos: {len(alice_todos)}")


# ============================================================================
# EXAMPLE 3: Understanding Adapters
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 3: Understanding Adapters")
print("=" * 70)

print("""
Adapters map models to storage backends:

1. InMemoryAdapter:
   - Simple 1:1 mapping
   - Uses primary key field as-is
   - Perfect for testing

2. DynamoDBAdapter:
   - Maps to single-table design
   - Generates pk/sk from decorated methods
   - Adds entity_type for filtering
   - Handles GSI keys

3. OpenSearchAdapter:
   - Maps to documents with _id
   - Handles searchable fields
   - Adds document type

4. CompositeAdapter:
   - Delegates to multiple adapters
   - Search operations → OpenSearch
   - Storage operations → DynamoDB
   - Perfect for graph databases

Benefits:
- Model class stays backend-agnostic
- Adapter handles storage-specific logic
- Easy to switch backends for testing
- Backend-specific optimizations possible
""")


# ============================================================================
# SUMMARY
# ============================================================================

print("=" * 70)
print("EXAMPLES COMPLETE")
print("=" * 70)
print(f"\nCreated {User.count()} users and {TodoItem.count()} todos")
print("\nThe adapter pattern provides:")
print("  ✓ Backend-agnostic models")
print("  ✓ Storage-specific optimizations")
print("  ✓ Easy testing with InMemoryBackend")
print("  ✓ Production-ready for DynamoDB, OpenSearch, etc.")

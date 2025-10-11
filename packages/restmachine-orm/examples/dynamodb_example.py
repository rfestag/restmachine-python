"""
Example: DynamoDB Backend with RestMachine ORM

This example demonstrates:
- Connecting to DynamoDB (local or AWS)
- Creating models with composite keys
- CRUD operations
- Query operations with filters
- Batch operations
- Type conversions

Prerequisites:
    pip install boto3

For local testing, run DynamoDB Local:
    docker run -p 8000:8000 amazon/dynamodb-local
"""

from datetime import datetime
from typing import Optional

from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm.backends import DynamoDBBackend, DynamoDBAdapter

# ============================================================================
# SETUP: Create DynamoDB Backend
# ============================================================================

print("=" * 70)
print("EXAMPLE: DynamoDB Backend")
print("=" * 70)

# Option 1: Local DynamoDB (for development/testing)
backend = DynamoDBBackend(
    table_name="orm-example",
    endpoint_url="http://localhost:8000",  # Local DynamoDB
    region_name="us-east-1",
)

# Option 2: AWS DynamoDB (uncomment for production)
# backend = DynamoDBBackend(
#     table_name="orm-example",
#     region_name="us-east-1",  # Your AWS region
# )

# Create table if it doesn't exist
try:
    backend.dynamodb.create_table(
        TableName="orm-example",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print("\n✓ Created DynamoDB table 'orm-example'")
    # Wait for table to be active
    backend.table.wait_until_exists()
except Exception as e:
    if "ResourceInUseException" in str(e):
        print("\n✓ Using existing DynamoDB table 'orm-example'")
    else:
        print(f"\n✗ Error creating table: {e}")
        print("\nMake sure DynamoDB Local is running:")
        print("  docker run -p 8000:8000 amazon/dynamodb-local")
        exit(1)


# ============================================================================
# EXAMPLE 1: User Model with Simple Keys
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 1: User Model")
print("=" * 70)


class User(Model):
    """User model with pk/sk based on user ID."""

    class Meta:
        backend = backend

    user_id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    age: int = Field(ge=0, le=150, default=0)
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)

    @partition_key
    def pk(self) -> str:
        """Partition key: USER#{user_id}"""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort key: Always 'PROFILE' for user records"""
        return "PROFILE"


print("\n1. Creating users...")
alice = User.create(
    user_id="alice",
    email="alice@example.com",
    name="Alice",
    age=30
)
print(f"Created: {alice.name} ({alice.email})")
print(f"  DynamoDB Key: pk={alice.pk()}, sk={alice.sk()}")

bob = User.create(
    user_id="bob",
    email="bob@example.com",
    name="Bob",
    age=25
)
print(f"Created: {bob.name} ({bob.email})")

print("\n2. Getting user...")
user = User.get(user_id="alice")
if user:
    print(f"Found: {user.name}, age {user.age}")

print("\n3. Updating user...")
alice.age = 31
alice.save()
print(f"Updated Alice's age to: {alice.age}")

print("\n4. Querying users...")
all_users = User.all()
print(f"Total users: {len(all_users)}")

young_users = User.query().filter(age__lt=30).all()
print(f"Users under 30: {len(young_users)}")
for user in young_users:
    print(f"  - {user.name}, age {user.age}")


# ============================================================================
# EXAMPLE 2: Todo Items with Time-Sortable Keys
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 2: Todo Items with Time-Sortable Keys")
print("=" * 70)


class TodoItem(Model):
    """
    Todo item with composite keys for efficient queries.

    Partition key groups todos by user.
    Sort key includes timestamp for chronological ordering.
    """

    class Meta:
        backend = backend

    user_id: str
    todo_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)
    created_at: Optional[datetime] = Field(None, auto_now_add=True)
    updated_at: Optional[datetime] = Field(None, auto_now=True)

    @partition_key
    def pk(self) -> str:
        """Group todos by user"""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort by creation time, then todo ID"""
        if self.created_at:
            return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"
        return f"TODO#{self.todo_id}"


print("\n1. Creating todos...")
todo1 = TodoItem.create(
    user_id="alice",
    todo_id="todo-1",
    title="Write documentation",
    description="Complete the DynamoDB backend docs",
    priority=5
)
print(f"Created: {todo1.title}")
print(f"  DynamoDB Key: pk={todo1.pk()}, sk={todo1.sk()}")

todo2 = TodoItem.create(
    user_id="alice",
    todo_id="todo-2",
    title="Review pull request",
    priority=4
)
print(f"Created: {todo2.title}")

todo3 = TodoItem.create(
    user_id="alice",
    todo_id="todo-3",
    title="Deploy to production",
    completed=True,
    priority=5
)
print(f"Created: {todo3.title}")

print("\n2. Querying todos...")
all_todos = TodoItem.all()
print(f"Total todos: {len(all_todos)}")

incomplete = TodoItem.query().filter(completed=False).all()
print(f"\nIncomplete todos: {len(incomplete)}")
for todo in incomplete:
    print(f"  - [{todo.priority}] {todo.title}")

high_priority = TodoItem.query().filter(
    completed=False,
    priority__gte=4
).all()
print(f"\nHigh-priority incomplete todos: {len(high_priority)}")
for todo in high_priority:
    print(f"  - [{todo.priority}] {todo.title}")


# ============================================================================
# EXAMPLE 3: Batch Operations
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 3: Batch Operations")
print("=" * 70)

print("\n1. Batch creating todos...")
batch_todos = [
    {
        "user_id": "bob",
        "todo_id": f"todo-{i}",
        "title": f"Task {i}",
        "priority": (i % 5) + 1,
    }
    for i in range(5)
]

results = backend.batch_create(TodoItem, batch_todos)
print(f"Created {len(results)} todos in batch for Bob")

print("\n2. Batch getting users...")
keys = [{"user_id": "alice"}, {"user_id": "bob"}]
users = backend.batch_get(User, keys)
print(f"Retrieved {len(users)} users:")
for user_data in users:
    print(f"  - {user_data['name']} ({user_data['email']})")


# ============================================================================
# EXAMPLE 4: Type Conversions
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 4: Type Conversions")
print("=" * 70)

print("\n1. DateTime conversion...")
print(f"Alice's created_at (Python): {alice.created_at}")
print(f"  Type: {type(alice.created_at)}")

# Check what's stored in DynamoDB
item = backend.table.get_item(Key={"pk": alice.pk(), "sk": alice.sk()})
print(f"\nStored in DynamoDB as: {item['Item']['created_at']}")
print(f"  Type: {type(item['Item']['created_at'])}")

print("\n2. Integer conversion...")
print(f"Alice's age (Python): {alice.age}")
print(f"  Type: {type(alice.age)}")

print(f"\nStored in DynamoDB as: {item['Item']['age']}")
print(f"  Type: {type(item['Item']['age'])}")


# ============================================================================
# EXAMPLE 5: Error Handling
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 5: Error Handling")
print("=" * 70)

print("\n1. Duplicate key error...")
try:
    User.create(
        user_id="alice",
        email="different@example.com",
        name="Different Alice"
    )
except Exception as e:
    print(f"✓ Caught expected error: {type(e).__name__}")

print("\n2. Validation error...")
try:
    TodoItem.create(
        user_id="alice",
        todo_id="invalid",
        title="",  # Empty title violates min_length=1
    )
except Exception as e:
    print(f"✓ Caught expected error: {type(e).__name__}")

print("\n3. Not found error...")
user = User.get(user_id="nonexistent")
print(f"✓ User.get() returned: {user}")


# ============================================================================
# EXAMPLE 6: Deleting Records
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 6: Deleting Records")
print("=" * 70)

print("\n1. Deleting a todo...")
todo1.delete()
print(f"✓ Deleted: {todo1.title}")

remaining = TodoItem.query().filter(user_id="alice").all()
print(f"Remaining todos for Alice: {len(remaining)}")

print("\n2. Deleting a user...")
bob.delete()
print(f"✓ Deleted: {bob.name}")

total_users = User.count()
print(f"Total users remaining: {total_users}")


# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("""
The DynamoDB backend provides:
  ✓ Composite keys (pk/sk) for efficient access patterns
  ✓ Automatic type conversion (datetime, Decimal, etc.)
  ✓ Full CRUD operations
  ✓ Rich query capabilities with filters
  ✓ Batch operations for performance
  ✓ Error handling and validation
  ✓ Integration with Pydantic for data validation

Single-table design benefits:
  ✓ All entities in one table
  ✓ Efficient queries using pk/sk
  ✓ Cost-effective (fewer read/write units)
  ✓ Easy to add new entity types

Next steps:
  - Add GSI indexes for additional access patterns
  - Implement conditional updates
  - Add DynamoDB Streams for event processing
  - Set up TTL for automatic expiration
""")

print("\n✓ Example completed successfully!")

"""
Example: Todo application using RestMachine ORM.

This example demonstrates:
- Model definition with validation
- Composite DynamoDB keys
- ActiveRecord CRUD operations
- Query builder interface
- Integration with RestMachine
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

# Note: This is aspirational code showing the intended API
# Backend implementations are not yet complete

from restmachine_orm import Model, Field, partition_key, sort_key
# from restmachine_orm.backends.dynamodb import DynamoDBBackend


# ============================================================================
# MODEL DEFINITIONS
# ============================================================================

class User(Model):
    """
    User model with simple primary key.

    Demonstrates:
    - Primary key field
    - Unique constraints
    - Validation rules
    - Auto-timestamp fields
    """

    # Configure backend (uncomment when DynamoDB backend is implemented)
    # class Meta:
    #     backend = DynamoDBBackend(table_name="users")

    # Fields
    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150, default=0)
    role: str = Field(default="user")  # user, admin, etc.
    created_at: datetime = Field(auto_now_add=True)
    updated_at: datetime = Field(auto_now=True)


class TodoItem(Model):
    """
    Todo item with composite DynamoDB keys.

    Demonstrates:
    - Composite partition and sort keys
    - Key generation from multiple fields
    - Hierarchical key structure
    """

    # Configure backend
    # class Meta:
    #     backend = DynamoDBBackend(table_name="todos")

    # Fields
    user_id: str
    todo_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: bool = False
    priority: int = Field(ge=1, le=5, default=3)
    created_at: datetime = Field(auto_now_add=True)
    updated_at: datetime = Field(auto_now=True)

    @partition_key
    def pk(self) -> str:
        """
        Partition key: USER#{user_id}

        Groups all todos for a user together.
        """
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """
        Sort key: TODO#{created_at}#{todo_id}

        Enables:
        - Chronological ordering
        - Unique identification
        - Range queries by date
        """
        return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_crud_operations():
    """Demonstrate basic CRUD operations."""

    print("=" * 70)
    print("CRUD OPERATIONS")
    print("=" * 70)

    # CREATE
    print("\n1. Creating users...")
    alice = User.create(
        id=str(uuid4()),
        email="alice@example.com",
        name="Alice Smith",
        age=30,
        role="admin"
    )
    print(f"Created user: {alice.name} ({alice.email})")

    bob = User.create(
        id=str(uuid4()),
        email="bob@example.com",
        name="Bob Jones",
        age=25
    )
    print(f"Created user: {bob.name} ({bob.email})")

    # READ
    print("\n2. Reading user...")
    user = User.get(id=alice.id)
    if user:
        print(f"Found user: {user.name}")

    # UPDATE
    print("\n3. Updating user...")
    alice.age = 31
    alice.save()
    print(f"Updated age to: {alice.age}")

    # DELETE
    print("\n4. Deleting user...")
    bob.delete()
    print(f"Deleted user: {bob.name}")


def example_todo_operations():
    """Demonstrate todo-specific operations with composite keys."""

    print("\n" + "=" * 70)
    print("TODO OPERATIONS (Composite Keys)")
    print("=" * 70)

    user_id = "alice"

    # Create todos
    print("\n1. Creating todos...")
    todo1 = TodoItem.create(
        user_id=user_id,
        todo_id=str(uuid4()),
        title="Write documentation",
        description="Document the ORM API",
        priority=5
    )
    print(f"Created: {todo1.title}")
    print(f"  PK: {todo1.pk()}")
    print(f"  SK: {todo1.sk()}")

    todo2 = TodoItem.create(
        user_id=user_id,
        todo_id=str(uuid4()),
        title="Review pull request",
        priority=4
    )
    print(f"Created: {todo2.title}")

    todo3 = TodoItem.create(
        user_id=user_id,
        todo_id=str(uuid4()),
        title="Deploy to production",
        completed=True,
        priority=5
    )
    print(f"Created: {todo3.title}")

    # Query by partition key
    print("\n2. Querying all todos for user...")
    todos = TodoItem.query().filter(pk=f"USER#{user_id}").all()
    print(f"Found {len(todos)} todos")

    # Query with sort key condition
    print("\n3. Querying recent todos...")
    recent = (TodoItem.query()
        .filter(pk=f"USER#{user_id}")
        .filter(sk__startswith="TODO#2025")
        .all())
    print(f"Found {len(recent)} recent todos")

    # Update todo
    print("\n4. Completing todo...")
    todo1.completed = True
    todo1.save()
    print(f"Marked as completed: {todo1.title}")


def example_query_builder():
    """Demonstrate query builder interface."""

    print("\n" + "=" * 70)
    print("QUERY BUILDER")
    print("=" * 70)

    print("\n1. Basic filtering...")
    # users = User.query().filter(age__gte=18).all()

    print("\n2. Multiple conditions...")
    # users = User.query().filter(age__gte=18, role="admin").all()

    print("\n3. Ordering and limiting...")
    # users = User.query().filter(age__gte=18).order_by("-created_at").limit(10).all()

    print("\n4. Complex queries with Q objects...")
    # from restmachine_orm.query.expressions import Q
    # users = User.query().filter(
    #     Q(age__gte=18, role="admin") | Q(role="superuser")
    # ).all()

    print("\n5. Existence checks...")
    # exists = User.query().filter(email="alice@example.com").exists()

    print("\n6. Counting...")
    # count = User.query().filter(age__gte=18).count()


def example_restmachine_integration():
    """Demonstrate integration with RestMachine."""

    print("\n" + "=" * 70)
    print("RESTMACHINE INTEGRATION")
    print("=" * 70)

    # This shows how the ORM integrates with RestMachine
    print("""
from restmachine import RestApplication
from restmachine_orm import Model, Field

class Todo(Model):
    id: str = Field(primary_key=True)
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False

app = RestApplication()

@app.post("/todos")
def create_todo(title: str, completed: bool = False) -> Todo:
    '''RestMachine automatically validates using the model schema.'''
    return Todo.create(id=generate_id(), title=title, completed=completed)

@app.get("/todos/{todo_id}")
def get_todo(todo_id: str) -> Todo:
    return Todo.get(id=todo_id)

@app.put("/todos/{todo_id}")
def update_todo(todo_id: str, title: str = None, completed: bool = None) -> Todo:
    todo = Todo.get(id=todo_id)
    if title is not None:
        todo.title = title
    if completed is not None:
        todo.completed = completed
    todo.save()
    return todo
    """)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("RESTMACHINE ORM EXAMPLES")
    print("=" * 70)
    print("\nNOTE: These are aspirational examples showing the intended API.")
    print("Backend implementations are not yet complete.\n")

    # Uncomment when backends are implemented:
    # example_crud_operations()
    # example_todo_operations()
    example_query_builder()
    example_restmachine_integration()

    print("\n" + "=" * 70)
    print("EXAMPLES COMPLETE")
    print("=" * 70 + "\n")

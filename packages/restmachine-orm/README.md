# RestMachine ORM

An ActiveRecord-style ORM/ODM framework for Python with support for multiple backends including DynamoDB, OpenSearch, and composite storage systems.

## Features

- **ActiveRecord Pattern** - Define models with schema and get full CRUD operations
- **Multiple Backends** - DynamoDB, OpenSearch, and composite backends
- **Pydantic Integration** - Built-in validation compatible with RestMachine
- **Composite Keys** - Decorator-based partition and sort key generation
- **Query Builder** - Fluent interface for building complex queries
- **Graph Database Support** - Composite backend using OpenSearch for discovery and DynamoDB hexastore for traversal

## Installation

```bash
# Base installation
pip install restmachine-orm

# With DynamoDB support
pip install restmachine-orm[dynamodb]

# With OpenSearch support
pip install restmachine-orm[opensearch]

# With all backends
pip install restmachine-orm[all]
```

## Quick Start

### Basic Model Definition

```python
from restmachine_orm import Model, Field
from restmachine_orm.backends.dynamodb import DynamoDBBackend

class User(Model):
    """User model stored in DynamoDB."""

    class Meta:
        backend = DynamoDBBackend(table_name="users")

    # Fields
    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = Field(max_length=100)
    age: int = Field(ge=0, le=150, default=0)
    created_at: datetime = Field(auto_now_add=True)
    updated_at: datetime = Field(auto_now=True)

# Create
user = User.create(id="user-123", email="alice@example.com", name="Alice")

# Read
user = User.get(id="user-123")
users = User.query().filter(age__gte=18).all()

# Update
user.name = "Alice Smith"
user.save()

# Delete
user.delete()
```

### DynamoDB with Composite Keys

```python
from restmachine_orm import Model, Field, partition_key, sort_key

class TodoItem(Model):
    """Todo item with composite DynamoDB key."""

    class Meta:
        backend = DynamoDBBackend(table_name="todos")

    user_id: str
    todo_id: str
    title: str
    completed: bool = False
    created_at: datetime

    @partition_key
    def pk(self) -> str:
        """Partition key: USER#{user_id}"""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort key: TODO#{created_at}#{todo_id}"""
        return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"

# Query by partition key
todos = TodoItem.query().filter(pk="USER#alice").all()

# Query with sort key condition
recent_todos = (TodoItem.query()
    .filter(pk="USER#alice")
    .filter(sk__startswith="TODO#2025")
    .all())
```

### OpenSearch Integration

```python
from restmachine_orm.backends.opensearch import OpenSearchBackend

class Article(Model):
    """Article with full-text search."""

    class Meta:
        backend = OpenSearchBackend(index_name="articles")

    id: str = Field(primary_key=True)
    title: str = Field(searchable=True)
    content: str = Field(searchable=True)
    tags: list[str] = Field(default_factory=list)
    published_at: datetime

# Full-text search
articles = Article.search("python web framework").all()

# Complex queries
articles = (Article.query()
    .search("REST API")
    .filter(published_at__gte=datetime(2025, 1, 1))
    .filter(tags__contains="tutorial")
    .order_by("-published_at")
    .limit(10)
    .all())
```

### Composite Backend (Graph Database)

```python
from restmachine_orm.backends.composite import CompositeBackend
from restmachine_orm.backends.opensearch import OpenSearchBackend
from restmachine_orm.backends.dynamodb import DynamoDBBackend

class GraphNode(Model):
    """Graph node with OpenSearch for discovery, DynamoDB for edges."""

    class Meta:
        backend = CompositeBackend(
            search=OpenSearchBackend(index_name="nodes"),
            storage=DynamoDBBackend(table_name="graph-edges")
        )

    id: str = Field(primary_key=True)
    type: str  # e.g., "Person", "Company", "Product"
    properties: dict = Field(default_factory=dict)

    @partition_key
    def pk(self) -> str:
        return f"{self.type}#{self.id}"

    @sort_key
    def sk(self) -> str:
        return "NODE"

# Find nodes via OpenSearch
people = GraphNode.search("John").filter(type="Person").all()

# Navigate graph via DynamoDB hexastore
person = GraphNode.get(id="person-123")
friends = person.traverse(relationship="FRIENDS_WITH", direction="outbound")
```

## Integration with RestMachine

Models are Pydantic-compatible and work seamlessly with RestMachine:

```python
from restmachine import RestApplication
from restmachine_orm import Model, Field

class Todo(Model):
    id: str = Field(primary_key=True)
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False

app = RestApplication()

@app.post("/todos")
def create_todo(title: str, completed: bool = False) -> Todo:
    """RestMachine automatically validates using Pydantic schema."""
    return Todo.create(
        id=generate_id(),
        title=title,
        completed=completed
    )

@app.get("/todos/{todo_id}")
def get_todo(todo_id: str) -> Todo:
    return Todo.get(id=todo_id)
```

## Architecture

### Models
- **Base Model** - ActiveRecord-style base class with CRUD operations
- **Field Definitions** - Pydantic-based field types with validation
- **Decorators** - `@partition_key`, `@sort_key` for composite key generation

### Backends
- **DynamoDB** - Single-table design with GSIs, composite keys, hexastore support
- **OpenSearch** - Full-text search, aggregations, complex queries
- **Composite** - Combines multiple backends for hybrid use cases

### Query Builder
- **Fluent Interface** - Chain methods for complex queries
- **Backend Agnostic** - Translates to backend-specific queries
- **Type Safe** - Leverages Python type hints

## Roadmap

### Phase 1: Foundation ✅ Complete
- [x] Project structure and packaging
- [x] Base model implementation with ActiveRecord pattern
- [x] Field definitions and Pydantic validation
- [x] Adapter pattern for backend abstraction
- [x] In-memory backend for testing
- [x] Query builder with field lookups

### Phase 2: DynamoDB Backend ✅ Complete
- [x] DynamoDB backend with boto3 integration
- [x] Composite keys (partition key + sort key)
- [x] Query operations with filters
- [x] Batch operations (BatchGetItem, BatchWriteItem)
- [x] Conditional updates
- [x] Type conversion (datetime, Decimal, etc.)
- [x] Comprehensive test coverage with moto

### Phase 3: OpenSearch Backend 🚧 Planned
- [ ] OpenSearch backend implementation
- [ ] Full-text search capabilities
- [ ] Aggregations support
- [ ] Query builder extensions for search

### Phase 4: Advanced Features 🚧 Planned
- [ ] GSI queries and management
- [ ] Composite backend for hybrid use cases
- [ ] Hexastore implementation for graph traversal
- [ ] Relationship management
- [ ] Migration system
- [ ] Admin UI integration

## License

MIT

# Contributing to RestMachine ORM

Thank you for your interest in contributing to RestMachine ORM!

## Development Setup

```bash
cd packages/restmachine-orm

# Install in development mode with all dependencies
pip install -e ".[all,dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/restmachine_orm --cov-report=term-missing
```

## Architecture Overview

RestMachine ORM follows the ActiveRecord pattern and consists of several key components:

### 1. Models (`src/restmachine_orm/models/`)

- **base.py** - Base `Model` class that provides CRUD operations
- **fields.py** - Field definitions with Pydantic integration
- **decorators.py** - Decorators for composite keys (`@partition_key`, `@sort_key`)

Models inherit from `pydantic.BaseModel` for validation and `Model` for database operations.

### 2. Backends (`src/restmachine_orm/backends/`)

- **base.py** - Abstract `Backend` interface
- **dynamodb.py** - DynamoDB implementation (TODO)
- **opensearch.py** - OpenSearch implementation (TODO)
- **composite.py** - Composite backend for graph databases (TODO)

All backends implement the same interface defined in `Backend` base class.

### 3. Query Builder (`src/restmachine_orm/query/`)

- **base.py** - Abstract `QueryBuilder` with fluent interface
- **expressions.py** - Q objects for complex boolean queries

Each backend provides its own QueryBuilder implementation that translates to backend-specific query language.

## Implementation Roadmap

### Phase 1: Core Foundation ✅

- [x] Project structure and packaging
- [x] Base model class with Pydantic integration
- [x] Field definitions with ORM metadata
- [x] Composite key decorators
- [x] Backend interface definition
- [x] Query builder interface
- [x] Q expression objects

### Phase 2: DynamoDB Backend (Next Priority)

- [ ] DynamoDB backend implementation
  - [ ] Connection management (boto3)
  - [ ] Single-table design support
  - [ ] Composite key handling (pk/sk)
  - [ ] GSI support
  - [ ] Batch operations
  - [ ] Conditional updates
- [ ] DynamoDB query builder
  - [ ] Key condition expressions
  - [ ] Filter expressions
  - [ ] Projection expressions
- [ ] Hexastore implementation for graphs
  - [ ] SPO, SOP, PSO, POS, OSP, OPS indexes
  - [ ] Graph traversal operations
- [ ] Tests with moto

### Phase 3: OpenSearch Backend

- [ ] OpenSearch backend implementation
  - [ ] Connection management
  - [ ] Index management
  - [ ] Document CRUD operations
  - [ ] Bulk operations
- [ ] OpenSearch query builder
  - [ ] Full-text search
  - [ ] Term queries
  - [ ] Range queries
  - [ ] Bool queries
  - [ ] Aggregations
- [ ] Tests with OpenSearch test container

### Phase 4: Composite Backend

- [ ] Composite backend implementation
  - [ ] Orchestrate multiple backends
  - [ ] OpenSearch for node discovery
  - [ ] DynamoDB for edge storage
  - [ ] Query routing logic
- [ ] Graph operations
  - [ ] Node creation with indexing
  - [ ] Edge creation with hexastore
  - [ ] Graph traversal
  - [ ] Path finding

### Phase 5: Advanced Features

- [ ] Relationship management
  - [ ] One-to-many
  - [ ] Many-to-many
  - [ ] Lazy loading
- [ ] Migration system
  - [ ] Schema versioning
  - [ ] Migration generation
  - [ ] Migration execution
- [ ] Caching layer
  - [ ] In-memory cache
  - [ ] Redis integration
- [ ] Admin UI
  - [ ] Auto-generated admin interface
  - [ ] CRUD operations
  - [ ] Query interface

## Adding a New Backend

To add support for a new backend:

1. **Create backend file**: `src/restmachine_orm/backends/your_backend.py`

2. **Implement Backend interface**:

```python
from restmachine_orm.backends.base import Backend
from restmachine_orm.query.base import QueryBuilder

class YourBackend(Backend):
    def __init__(self, **config):
        self.config = config
        # Initialize connection

    def create(self, model_class, data):
        # Implement create logic
        pass

    def get(self, model_class, **filters):
        # Implement get logic
        pass

    # ... implement other methods
```

3. **Create query builder**:

```python
class YourQueryBuilder(QueryBuilder):
    def filter(self, **conditions):
        # Translate to backend-specific query
        self._filters.append(conditions)
        return self

    def all(self):
        # Execute query and return models
        pass

    # ... implement other methods
```

4. **Add tests**: `tests/test_your_backend.py`

5. **Update documentation**: Add examples to README.md

## DynamoDB Implementation Guidelines

### Single-Table Design

RestMachine ORM uses single-table design for DynamoDB:

- **pk** (partition key) - Composite key from `@partition_key` method
- **sk** (sort key) - Composite key from `@sort_key` method
- **entity_type** - Model class name for filtering
- All model fields as attributes

### Composite Key Patterns

```python
@partition_key
def pk(self) -> str:
    # Use hierarchical keys for access patterns
    return f"{ENTITY_TYPE}#{self.id}"

@sort_key
def sk(self) -> str:
    # Include metadata for sorting and filtering
    return f"METADATA#{self.created_at.isoformat()}"
```

### GSI Design

Global Secondary Indexes should be defined using field metadata:

```python
class User(Model):
    email: str = Field(gsi_partition_key="EmailIndex")
    created_at: datetime = Field(gsi_sort_key="EmailIndex")
```

### Hexastore for Graphs

For graph databases, implement hexastore pattern with 6 GSIs:

- SPO: Subject-Predicate-Object
- SOP: Subject-Object-Predicate
- PSO: Predicate-Subject-Object
- POS: Predicate-Object-Subject
- OSP: Object-Subject-Predicate
- OPS: Object-Predicate-Subject

This enables efficient traversal in any direction.

## Testing Guidelines

### Unit Tests

Test individual components in isolation:

```python
def test_model_validation():
    user = User(id="123", email="test@example.com", name="Test")
    assert user.id == "123"
```

### Integration Tests

Test with real backend (use moto for DynamoDB):

```python
@mock_dynamodb
def test_dynamodb_create():
    # Setup table
    backend = DynamoDBBackend(table_name="test")
    backend.initialize()

    # Test create
    user = User.create(id="123", email="test@example.com")
    assert user._is_persisted
```

### Test Markers

Use pytest markers to categorize tests:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Tests requiring external services
- `@pytest.mark.dynamodb` - DynamoDB-specific tests
- `@pytest.mark.opensearch` - OpenSearch-specific tests

## Code Style

- Follow PEP 8
- Use type hints for all functions
- Docstrings for all public APIs (Google style)
- Maximum line length: 100 characters

## Documentation

- Update README.md with new features
- Add docstrings with examples
- Create examples in `examples/` directory
- Update this CONTRIBUTING.md with architectural decisions

## Questions?

Open an issue for discussion or reach out to the maintainers.

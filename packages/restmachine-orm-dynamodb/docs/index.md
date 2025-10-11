# DynamoDB Backend

The DynamoDB backend provides persistent storage for RestMachine ORM using AWS DynamoDB.

## Features

- **Single-Table Design**: Store multiple entities in one DynamoDB table
- **Composite Keys**: Full support for partition and sort keys
- **Type Conversion**: Automatic Decimal ↔ Python type conversion
- **Batch Operations**: Efficient batch create and get operations
- **Pagination**: Cursor-based pagination for large datasets
- **Testing Support**: Built-in test utilities with moto

## Installation

```bash
pip install restmachine-orm-dynamodb
```

Or with the convenience extra:

```bash
pip install restmachine-orm[dynamodb]
```

## Quick Start

```python
from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm_dynamodb import DynamoDBBackend

# Configure backend
backend = DynamoDBBackend(
    table_name="my-app-table",
    region_name="us-east-1"
)

class User(Model):
    class Meta:
        backend = backend

    id: str = Field(primary_key=True)
    email: str
    name: str

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.id}"

    @sort_key
    def sk(self) -> str:
        return "PROFILE"

# Use normally
user = User.create(
    id="user-123",
    email="alice@example.com",
    name="Alice"
)

# Retrieve
user = User.get(id="user-123")
```

## Composite Keys

DynamoDB uses composite keys (partition key + sort key):

```python
from datetime import datetime

class TodoItem(Model):
    class Meta:
        backend = backend

    user_id: str
    todo_id: str
    title: str
    created_at: datetime

    @partition_key
    def pk(self) -> str:
        """Partition key: USER#{user_id}"""
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        """Sort key: TODO#{created_at}#{todo_id}"""
        return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"

# Create
todo = TodoItem.create(
    user_id="alice",
    todo_id="todo-1",
    title="Write docs"
)
```

## Table Schema

Your DynamoDB table should have this schema:

```python
{
    "TableName": "my-app-table",
    "KeySchema": [
        {"AttributeName": "pk", "KeyType": "HASH"},
        {"AttributeName": "sk", "KeyType": "RANGE"}
    ],
    "AttributeDefinitions": [
        {"AttributeName": "pk", "AttributeType": "S"},
        {"AttributeName": "sk", "AttributeType": "S"}
    ],
    "BillingMode": "PAY_PER_REQUEST"
}
```

## Configuration

### AWS Credentials

Uses boto3, which supports multiple credential sources:

```python
# Environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Or explicit session
import boto3

session = boto3.Session(
    aws_access_key_id="...",
    aws_secret_access_key="...",
    region_name="us-east-1"
)

backend = DynamoDBBackend(
    table_name="my-table",
    session=session
)
```

### Local Development

Use DynamoDB Local:

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

```python
backend = DynamoDBBackend(
    table_name="my-table",
    region_name="us-east-1",
    endpoint_url="http://localhost:8000"
)
```

## Testing

The package includes test utilities using moto:

```python
import pytest
from moto import mock_aws
import boto3
from restmachine_orm_dynamodb import DynamoDBBackend

@pytest.fixture
def backend():
    with mock_aws():
        # Create table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        table.wait_until_exists()

        yield DynamoDBBackend(
            table_name="test-table",
            region_name="us-east-1"
        )

def test_user_crud(backend):
    class User(Model):
        class Meta:
            backend = backend

        id: str = Field(primary_key=True)
        name: str

        @partition_key
        def pk(self):
            return f"USER#{self.id}"

        @sort_key
        def sk(self):
            return "PROFILE"

    user = User.create(id="user-1", name="Alice")
    assert user.name == "Alice"
```

## Features

### Batch Operations

```python
# Batch create
records = [
    {"user_id": "alice", "todo_id": f"todo-{i}", "title": f"Task {i}"}
    for i in range(10)
]
results = backend.batch_create(TodoItem, records)

# Batch get
keys = [{"user_id": "alice", "todo_id": f"todo-{i}"} for i in range(5)]
items = backend.batch_get(TodoItem, keys)
```

### Pagination

```python
# First page
results, cursor = User.where().limit(100).paginate()

# Next page
if cursor:
    more_results, next_cursor = User.where() \
        .limit(100) \
        .cursor(cursor) \
        .paginate()
```

### Single-Table Design

```python
# Multiple entity types in one table
class User(Model):
    class Meta:
        backend = backend

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.id}"

class Order(Model):
    class Meta:
        backend = backend

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        return f"ORDER#{self.order_id}"

# Both use same table
user = User.create(id="user-1", name="Alice")
order = Order.create(user_id="user-1", order_id="order-1", total=99.99)
```

## Documentation

For complete documentation, see:

- [Main ORM Documentation](../restmachine-orm/index.md) - Core concepts
- [DynamoDB Backend Guide](../restmachine-orm/backends/dynamodb.md) - Detailed guide
- [Multi-Backend Testing](../restmachine-orm/testing/multi-backend.md) - Testing across backends

## API Reference

See [API Reference](api.md) for complete API documentation.

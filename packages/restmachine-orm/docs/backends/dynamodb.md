# DynamoDB Backend

The DynamoDB backend provides persistent storage using AWS DynamoDB with support for single-table design patterns.

## Installation

```bash
pip install restmachine-orm-dynamodb
```

Or with the convenience extra:

```bash
pip install restmachine-orm[dynamodb]
```

## Basic Usage

```python
from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm_dynamodb import DynamoDBBackend, DynamoDBAdapter

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

# Use like any other model
user = User.create(id="user-123", email="alice@example.com", name="Alice")
```

## Composite Keys

DynamoDB uses composite keys (partition key + sort key). Define them with decorators:

```python
from datetime import datetime
from restmachine_orm import partition_key, sort_key

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
```

## Table Schema

DynamoDB backend expects tables with this schema:

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

### Custom Attribute Names

```python
adapter = DynamoDBAdapter(
    pk_attribute="hash_key",
    sk_attribute="range_key",
    entity_type_attribute="type"
)

backend = DynamoDBBackend(
    table_name="my-table",
    adapter=adapter
)
```

## Single-Table Design

Store multiple entity types in one table:

```python
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


class Order(Model):
    class Meta:
        backend = backend

    user_id: str
    order_id: str
    total: float

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @sort_key
    def sk(self) -> str:
        return f"ORDER#{self.order_id}"

# Both use same table
user = User.create(id="user-1", email="alice@example.com", name="Alice")
order = Order.create(user_id="user-1", order_id="order-1", total=99.99)

# Query all items for a user
items = backend.scan(User)  # Filters by entity_type automatically
```

## Batch Operations

```python
# Batch create
todos = [
    {"user_id": "alice", "todo_id": f"todo-{i}", "title": f"Task {i}"}
    for i in range(10)
]
results = backend.batch_create(TodoItem, todos)

# Batch get
keys = [{"user_id": "alice", "todo_id": f"todo-{i}"} for i in range(5)]
items = backend.batch_get(TodoItem, keys)
```

## Type Conversion

DynamoDB uses Decimal for numbers. The backend handles conversion:

```python
class Product(Model):
    class Meta:
        backend = backend

    sku: str = Field(primary_key=True)
    price: float  # Stored as Decimal, returned as float
    stock: int  # Stored as Decimal, returned as int

product = Product.create(sku="ABC123", price=19.99, stock=100)

# Retrieval converts back to Python types
product = Product.get(sku="ABC123")
assert isinstance(product.price, float)
assert isinstance(product.stock, int)
```

## Pagination

For large result sets, use cursor-based pagination:

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

## Global Secondary Indexes (GSI)

Support for GSIs coming soon. Current workaround:

```python
from restmachine_orm import gsi_partition_key, gsi_sort_key

class User(Model):
    class Meta:
        backend = backend

    id: str = Field(primary_key=True)
    email: str
    tenant_id: str

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.id}"

    @sort_key
    def sk(self) -> str:
        return "PROFILE"

    @gsi_partition_key("TenantIndex")
    def gsi_pk_tenant(self) -> str:
        return f"TENANT#{self.tenant_id}"

    @gsi_sort_key("TenantIndex")
    def gsi_sk_tenant(self) -> str:
        return f"USER#{self.id}"

# GSI attributes (gsi_pk_TenantIndex, gsi_sk_TenantIndex) are automatically stored
```

## Configuration

### AWS Credentials

The backend uses boto3, which supports multiple credential sources:

1. Environment variables
2. AWS credentials file (~/.aws/credentials)
3. IAM role (for EC2/Lambda)

```python
import boto3

# Explicit credentials
session = boto3.Session(
    aws_access_key_id="...",
    aws_secret_access_key="...",
    region_name="us-east-1"
)

backend = DynamoDBBackend(
    table_name="my-table",
    session=session  # Optional: use custom session
)
```

### Local Development

Use DynamoDB Local for development:

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

```python
backend = DynamoDBBackend(
    table_name="my-table",
    region_name="us-east-1",
    endpoint_url="http://localhost:8000"  # Local DynamoDB
)
```

## Testing

The DynamoDB backend includes test utilities using moto:

```python
import pytest
from moto import mock_aws
import boto3

@pytest.fixture
def dynamodb_backend():
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

        # Create backend
        backend = DynamoDBBackend(
            table_name="test-table",
            region_name="us-east-1"
        )
        yield backend

def test_user_crud(dynamodb_backend):
    class User(Model):
        class Meta:
            backend = dynamodb_backend

        id: str = Field(primary_key=True)
        name: str

        @partition_key
        def pk(self):
            return f"USER#{self.id}"

        @sort_key
        def sk(self):
            return "PROFILE"

    # Test CRUD operations
    user = User.create(id="user-1", name="Alice")
    assert user.name == "Alice"

    retrieved = User.get(id="user-1")
    assert retrieved.name == "Alice"
```

## Best Practices

1. **Design Keys Carefully**: Partition keys should distribute load evenly
2. **Use Sort Keys for Hierarchies**: Enable efficient range queries
3. **Entity Type Filtering**: Let the adapter handle entity_type automatically
4. **Batch Operations**: Use batch_create/batch_get for bulk operations
5. **Pagination**: Always paginate large result sets
6. **Testing**: Use moto for unit tests, real DynamoDB for integration tests

## See Also

- [In-Memory Backend](inmemory.md) - For development and testing
- [Multi-Backend Testing](../testing/multi-backend.md) - Test across backends
- [API Reference](../api/backends.md) - Complete backend API

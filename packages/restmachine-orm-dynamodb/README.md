# RestMachine ORM - DynamoDB Backend

DynamoDB backend implementation for RestMachine ORM.

## Installation

```bash
pip install restmachine-orm-dynamodb
```

This will automatically install `restmachine-orm` and `boto3` as dependencies.

## Usage

```python
from restmachine_orm import Model, Field, partition_key, sort_key
from restmachine_orm_dynamodb import DynamoDBBackend

class User(Model):
    class Meta:
        backend = DynamoDBBackend(
            table_name="users",
            region_name="us-east-1"
        )

    id: str
    email: str
    name: str

    @partition_key
    def pk(self) -> str:
        return f"USER#{self.id}"

    @sort_key
    def sk(self) -> str:
        return "PROFILE"

# Use the model
user = User.create(id="123", email="alice@example.com", name="Alice")
user = User.get(id="123")
user.name = "Alice Smith"
user.save()
```

## Features

- Single-table design with partition and sort keys
- Automatic key generation from decorated methods
- Support for Global Secondary Indexes (GSI)
- Query and scan operations
- Batch operations
- Optimistic locking with version fields
- Type conversion between Python and DynamoDB types

## Testing

The package includes a DynamoDB driver for the RestMachine ORM testing framework:

```python
from restmachine_orm.testing import MultiBackendTestBase, multi_backend_test_class

@multi_backend_test_class(enabled_backends=['inmemory', 'dynamodb'])
class TestUserModel(MultiBackendTestBase):
    def get_test_models(self):
        return [User]

    def test_create_user(self, orm):
        orm_client, backend_name = orm
        # Test runs against both InMemory and DynamoDB!
        user = orm_client.create_and_verify(User, id="123", email="test@example.com")
```

## Requirements

- Python 3.9+
- boto3
- restmachine-orm

## License

MIT

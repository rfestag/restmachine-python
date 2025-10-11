# Installation

RestMachine ORM can be installed with different backend support depending on your needs.

## Core Package

The core package includes the ORM framework and in-memory backend:

```bash
pip install restmachine-orm
```

This is sufficient for:
- Development and testing
- Simple applications without external dependencies
- Learning the ORM API

## With Backend Support

### DynamoDB Backend

For DynamoDB support:

```bash
pip install restmachine-orm restmachine-orm-dynamodb
```

Or using the convenience extra:

```bash
pip install restmachine-orm[dynamodb]
```

### All Backends

To install all available backends:

```bash
pip install restmachine-orm[all]
```

## Development Installation

For contributing to RestMachine ORM:

```bash
# Clone the repository
git clone https://github.com/rfestag/restmachine-python.git
cd restmachine-python

# Install in editable mode with dev dependencies
pip install -e ./packages/restmachine-orm[dev]
pip install -e ./packages/restmachine-orm-dynamodb[test]
```

## Requirements

- Python 3.9+
- pydantic >= 2.0.0

### Backend-Specific Requirements

**DynamoDB**:
- boto3 >= 1.26.0

**OpenSearch** (coming soon):
- opensearch-py >= 2.0.0

## Verifying Installation

```python
from restmachine_orm import Model, Field
print("RestMachine ORM installed successfully!")

# Check DynamoDB backend availability
try:
    from restmachine_orm_dynamodb import DynamoDBBackend
    print("DynamoDB backend available")
except ImportError:
    print("DynamoDB backend not installed")
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started with your first model
- [Basic Usage](usage.md) - Learn core ORM features

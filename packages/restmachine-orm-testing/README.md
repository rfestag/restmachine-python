# restmachine-orm-testing

Testing framework and utilities for RestMachine ORM backends.

## Overview

This package provides a comprehensive testing framework for ORM backend implementations, including:

- **Testing DSL**: A fluent, readable API for writing backend tests
- **Driver Interface**: Abstract interface for backend testing
- **Multi-Backend Testing**: Base classes for running tests across multiple backends
- **Assertion Helpers**: Common assertions for CRUD operations

## Installation

```bash
pip install restmachine-orm-testing
```

## Usage

### Basic Testing DSL

```python
from restmachine_orm_testing import ModelTestDSL
from restmachine_orm_testing.drivers import InMemoryDriver

# Create a driver for your backend
driver = InMemoryDriver()
dsl = ModelTestDSL(driver)

# Write fluent tests
result = dsl.create_model(User, email="alice@example.com", name="Alice")
assert result.success
assert result.instance.email == "alice@example.com"

# Use verification helpers
dsl.create_and_verify(User, email="bob@example.com", name="Bob")
```

### Multi-Backend Testing

```python
from restmachine_orm_testing import MultiBackendTestBase, multi_backend_test_class

@multi_backend_test_class(enabled_backends=["memory", "dynamodb"])
class TestUserCRUD(MultiBackendTestBase):
    def get_test_model_class(self):
        return User

    def test_create_user(self):
        result = self.dsl.create_and_verify(
            User,
            email="test@example.com",
            name="Test User"
        )
        assert result.instance.email == "test@example.com"
```

## Development

This package is part of the RestMachine monorepo and is designed to be used as a dev dependency for testing ORM backend implementations.

## License

MIT

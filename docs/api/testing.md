# Testing

## Overview

RestMachine provides testing utilities for writing tests against your REST APIs.

## Testing Drivers

Test your application with different drivers:

```python
from restmachine import RestApplication
from restmachine.testing import DirectDriver

app = RestApplication()

@app.get('/hello')
def hello():
    return {"message": "Hello"}

# Test with DirectDriver
driver = DirectDriver(app)
response = driver.get('/hello')

assert response.status_code == 200
assert response.json() == {"message": "Hello"}
```

## HTTP Testing DSL

Use the testing DSL for more readable tests:

```python
from restmachine.testing import test_http

def test_my_api():
    with test_http(app) as client:
        response = client.get('/users')
        assert response.status_code == 200
        assert 'users' in response.json()
```

## Testing with Dependencies

Mock dependencies in tests:

```python
@app.dependency()
def database():
    return create_db_connection()

# In tests
def test_with_mock_db():
    mock_db = MockDatabase()

    # Override dependency
    app.dependency_cache['database'] = mock_db

    response = DirectDriver(app).get('/users')
    assert response.status_code == 200
```

## See Also

- [Testing Guide](../guide/testing.md) - Complete testing guide
- [Application API](application.md) - Application class
- [Request & Response](models.md) - Request/response models

# Testing Your Application

RestMachine provides comprehensive testing utilities to help you write robust tests for your REST APIs. This guide covers both simple testing patterns and the advanced 4-layer testing architecture.

## Quick Start

### Direct Request Testing

The simplest way to test your RestMachine application is to create requests directly and execute them:

```python
from restmachine import RestApplication, Request, HTTPMethod

def test_get_user():
    app = RestApplication()

    @app.get("/users/{user_id}")
    def get_user(user_id: int):
        return {"id": user_id, "name": "Test User"}

    # Create a request
    request = Request(
        method=HTTPMethod.GET,
        path="/users/123",
        headers={"Accept": "application/json"}
    )

    # Execute the request
    response = app.execute(request)

    # Assert the response
    assert response.status_code == 200
    assert response.body == '{"id": 123, "name": "Test User"}'
```

### Testing with Pytest

RestMachine works seamlessly with pytest:

```python
import pytest
from restmachine import RestApplication, Request, HTTPMethod
import json

@pytest.fixture
def app():
    """Create a test application."""
    app = RestApplication()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/users")
    def list_users():
        return [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]

    return app

def test_health_check(app):
    """Test health endpoint."""
    request = Request(
        method=HTTPMethod.GET,
        path="/health",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert data["status"] == "ok"

def test_list_users(app):
    """Test user listing."""
    request = Request(
        method=HTTPMethod.GET,
        path="/users",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    users = json.loads(response.body)
    assert len(users) == 2
    assert users[0]["name"] == "Alice"
```

## Advanced Testing with DSL

RestMachine provides a powerful Domain-Specific Language (DSL) for testing, based on Dave Farley's 4-layer testing architecture.

### 4-Layer Architecture

1. **Test Layer** - Your actual test methods
2. **DSL Layer** - Business-focused API operations
3. **Driver Layer** - How to execute requests
4. **System Under Test** - Your RestMachine application

### Using the DSL

The DSL provides a fluent, readable API for testing:

```python
from restmachine import RestApplication
from restmachine.testing import RestApiDsl, RestMachineDriver

def test_create_user_with_dsl():
    # Create app
    app = RestApplication()

    @app.post("/users")
    def create_user(json_body: dict):
        return {"id": 1, **json_body}, 201

    # Create DSL client
    driver = RestMachineDriver(app)
    api = RestApiDsl(driver)

    # Create request using fluent API
    request = (api.post("/users")
        .with_json_body({"name": "Alice", "email": "alice@example.com"})
        .accepts("application/json"))

    # Execute and verify
    response = api.execute(request)

    assert response.status_code == 201
    data = response.get_json_body()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
```

### Business-Focused Methods

The DSL includes business-focused methods that hide HTTP details:

```python
from restmachine.testing import RestApiDsl, RestMachineDriver

def test_resource_operations():
    app = RestApplication()

    @app.get("/items/{item_id}")
    def get_item(item_id: int):
        return {"id": item_id, "name": "Test Item"}

    @app.post("/items")
    def create_item(json_body: dict):
        return {"id": 1, **json_body}, 201

    api = RestApiDsl(RestMachineDriver(app))

    # Get a resource
    response = api.get_resource("/items/123")
    item = api.expect_successful_retrieval(response)
    assert item["id"] == 123

    # Create a resource
    response = api.create_resource("/items", {"name": "New Item"})
    created = api.expect_successful_creation(response)
    assert created["name"] == "New Item"

    # Update a resource
    response = api.update_resource("/items/1", {"name": "Updated"})
    api.expect_successful_modification(response)

    # Delete a resource
    response = api.delete_resource("/items/1")
    api.expect_successful_deletion(response)
```

## Multi-Driver Testing

Test your application across multiple environments (direct, ASGI, HTTP) automatically:

### Setup Multi-Driver Tests

```python
from restmachine import RestApplication
from restmachine.testing import MultiDriverTestBase

class TestUserApi(MultiDriverTestBase):
    """Test user API across all drivers."""

    def create_app(self) -> RestApplication:
        """Create the application to test."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user(user_id: int):
            return {"id": user_id, "name": f"User {user_id}"}

        @app.post("/users")
        def create_user(json_body: dict):
            return {"id": 1, **json_body}, 201

        return app

    def test_get_user(self, api):
        """Test getting a user (runs on all drivers)."""
        api_client, driver_name = api

        response = api_client.get_resource("/users/42")
        user = api_client.expect_successful_retrieval(response)

        assert user["id"] == 42
        assert user["name"] == "User 42"

    def test_create_user(self, api):
        """Test creating a user (runs on all drivers)."""
        api_client, driver_name = api

        user_data = {"name": "Alice", "email": "alice@example.com"}
        response = api_client.create_resource("/users", user_data)

        created = api_client.expect_successful_creation(response)
        assert created["name"] == "Alice"
        assert created["email"] == "alice@example.com"
```

### Driver-Specific Tests

Skip or run tests only on specific drivers:

```python
from restmachine.testing import MultiDriverTestBase, skip_driver, only_drivers

class TestAdvancedFeatures(MultiDriverTestBase):

    def create_app(self) -> RestApplication:
        # ... create app

    @skip_driver("mock")
    def test_real_http_only(self, api):
        """This test skips the mock driver."""
        api_client, driver_name = api
        # Test real HTTP-specific features
        pass

    @only_drivers(["uvicorn", "hypercorn"])
    def test_asgi_only(self, api):
        """This test runs only on ASGI drivers."""
        api_client, driver_name = api
        # Test ASGI-specific features
        pass
```

## Testing Dependencies

### Mocking Dependencies

Replace dependencies with mocks for testing:

```python
def test_with_mock_database():
    app = RestApplication()

    # Mock database dependency
    @app.dependency()
    def database():
        return {"users": [{"id": 1, "name": "Test"}]}

    @app.get("/users")
    def get_users(database):
        return database["users"]

    request = Request(
        method=HTTPMethod.GET,
        path="/users",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    users = json.loads(response.body)
    assert len(users) == 1
```

### Testing Startup Handlers

Startup handlers run automatically during testing:

```python
def test_startup_handlers():
    app = RestApplication()

    @app.on_startup
    def test_config():
        return {"api_key": "test-key-123"}

    @app.get("/config")
    def get_config(test_config):
        return test_config

    request = Request(
        method=HTTPMethod.GET,
        path="/config",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    config = json.loads(response.body)
    assert config["api_key"] == "test-key-123"
```

## Testing Error Handling

### Testing Validation Errors

```python
from pydantic import BaseModel

def test_validation_errors():
    app = RestApplication()

    class CreateUser(BaseModel):
        name: str
        email: str
        age: int

    @app.validates
    def create_user_data(json_body) -> CreateUser:
        return CreateUser.model_validate(json_body)

    @app.post("/users")
    def create_user(create_user_data: CreateUser):
        return create_user_data.model_dump(), 201

    # Invalid data (missing required field)
    request = Request(
        method=HTTPMethod.POST,
        path="/users",
        headers={"Content-Type": "application/json"},
        body='{"name": "Alice"}'  # Missing email and age
    )
    response = app.execute(request)

    assert response.status_code == 400
    error = json.loads(response.body)
    assert "email" in str(error)
```

### Testing Authorization

```python
def test_unauthorized_access():
    app = RestApplication()

    @app.authorized
    def check_auth(request):
        token = request.headers.get("authorization")
        if not token or not token.startswith("Bearer "):
            return None  # Unauthorized
        return {"user": "alice"}

    @app.get("/protected")
    def protected_route(check_auth):
        return {"message": "Access granted"}

    # Without auth token
    request = Request(
        method=HTTPMethod.GET,
        path="/protected",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)
    assert response.status_code == 401

    # With valid token
    request = Request(
        method=HTTPMethod.GET,
        path="/protected",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer valid-token"
        }
    )
    response = app.execute(request)
    assert response.status_code == 200
```

## Testing with Different Content Types

### JSON Responses

```python
def test_json_response():
    app = RestApplication()

    @app.get("/data")
    def get_data():
        return {"message": "Hello", "count": 42}

    request = Request(
        method=HTTPMethod.GET,
        path="/data",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.headers.get("Content-Type") == "application/json"
    data = json.loads(response.body)
    assert data["message"] == "Hello"
```

### XML Responses

```python
def test_xml_response():
    app = RestApplication()

    @app.get("/data")
    def get_data():
        return {"message": "Hello"}

    request = Request(
        method=HTTPMethod.GET,
        path="/data",
        headers={"Accept": "application/xml"}
    )
    response = app.execute(request)

    assert response.headers.get("Content-Type") == "application/xml"
    assert b"<message>Hello</message>" in response.body
```

## Integration Testing

### Testing with Real Databases

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def database():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    # Create tables, seed data
    yield session
    session.close()

def test_with_database(database):
    app = RestApplication()

    @app.dependency()
    def db():
        return database

    @app.get("/users")
    def get_users(db):
        # Query real database
        users = db.query(User).all()
        return [{"id": u.id, "name": u.name} for u in users]

    # Test with real database
    request = Request(
        method=HTTPMethod.GET,
        path="/users",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)
    assert response.status_code == 200
```

## Best Practices

### 1. Use Fixtures for Common Setup

```python
@pytest.fixture
def auth_app():
    """App with authentication configured."""
    app = RestApplication()

    @app.dependency()
    def current_user():
        return {"id": 1, "name": "Test User"}

    @app.get("/me")
    def get_current_user(current_user):
        return current_user

    return app

def test_current_user(auth_app):
    # Use the fixture
    request = Request(
        method=HTTPMethod.GET,
        path="/me",
        headers={"Accept": "application/json"}
    )
    response = auth_app.execute(request)
    assert response.status_code == 200
```

### 2. Test Edge Cases

```python
def test_edge_cases():
    app = RestApplication()

    @app.get("/users/{user_id}")
    def get_user(user_id: int):
        if user_id <= 0:
            return {"error": "Invalid ID"}, 400
        if user_id > 1000:
            return None, 404
        return {"id": user_id}

    # Test negative ID
    response = app.execute(Request(
        method=HTTPMethod.GET,
        path="/users/-1",
        headers={"Accept": "application/json"}
    ))
    assert response.status_code == 400

    # Test large ID
    response = app.execute(Request(
        method=HTTPMethod.GET,
        path="/users/9999",
        headers={"Accept": "application/json"}
    ))
    assert response.status_code == 404
```

### 3. Use Parametrized Tests

```python
@pytest.mark.parametrize("user_id,expected_name", [
    (1, "Alice"),
    (2, "Bob"),
    (3, "Charlie")
])
def test_multiple_users(user_id, expected_name):
    app = RestApplication()

    users = {
        1: "Alice",
        2: "Bob",
        3: "Charlie"
    }

    @app.get("/users/{user_id}")
    def get_user(user_id: int):
        return {"id": user_id, "name": users.get(user_id)}

    request = Request(
        method=HTTPMethod.GET,
        path=f"/users/{user_id}",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    user = json.loads(response.body)
    assert user["name"] == expected_name
```

## Next Steps

- Learn about [Authentication & Authorization](authentication.md) patterns
- Explore [Error Handling](error-handling.md) strategies
- Read about [Deployment](deployment/uvicorn.md) options

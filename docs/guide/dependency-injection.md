# Dependency Injection

RestMachine features pytest-style dependency injection that makes your code clean, testable, and maintainable. Dependencies are automatically resolved and cached during request processing.

## Basic Dependencies

### Defining Dependencies

Use the `@app.dependency()` decorator to define a dependency:

```python
from restmachine import RestApplication

app = RestApplication()

@app.dependency()
def database():
    return {"users": [], "posts": []}

@app.get('/users')
def list_users(database):
    return {"users": database["users"]}
```

Dependencies are injected by matching parameter names with dependency function names.

### Dependency Caching

By default, dependencies are cached per request:

```python
@app.dependency()
def get_timestamp():
    from datetime import datetime
    print("Creating timestamp...")
    return datetime.now()

@app.dependency()
def request_logger(get_timestamp):
    print(f"Request at: {get_timestamp}")
    return "logger"

@app.get('/example')
def example_handler(get_timestamp, request_logger):
    # get_timestamp is only created once per request
    return {"timestamp": str(get_timestamp)}

# Output when request is made:
# Creating timestamp...
# Request at: 2024-01-15 10:30:00
```

## Nested Dependencies

Dependencies can depend on other dependencies:

```python
@app.dependency()
def config():
    return {
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "myapp"
    }

@app.dependency()
def database_url(config):
    return f"postgresql://{config['db_host']}:{config['db_port']}/{config['db_name']}"

@app.dependency()
def database(database_url):
    print(f"Connecting to {database_url}")
    # In real app, create actual connection
    return {"connected": True, "url": database_url}

@app.get('/status')
def status(database):
    return database
```

## Accessing the Request

Inject the `Request` object to access request data:

```python
from restmachine import Request

@app.dependency()
def current_user(request: Request):
    # Extract user from authentication header
    auth_header = request.headers.get('authorization', '')

    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        # In real app, validate token and get user
        return {"id": "123", "name": "Alice", "token": token}

    return None

@app.get('/profile')
def get_profile(current_user):
    if not current_user:
        from restmachine import Response
        return Response(401, '{"error": "Unauthorized"}')

    return current_user
```

### Path and Query Parameters

Access path and query parameters through the Request:

```python
@app.dependency()
def user_id(request: Request):
    return request.path_params.get('user_id')

@app.dependency()
def pagination(request: Request):
    page = int(request.query_params.get('page', '1'))
    limit = int(request.query_params.get('limit', '20'))
    offset = (page - 1) * limit
    return {"page": page, "limit": limit, "offset": offset}

@app.get('/users')
def list_users(pagination, database):
    users = database["users"]
    start = pagination["offset"]
    end = start + pagination["limit"]
    return {
        "users": users[start:end],
        "page": pagination["page"],
        "total": len(users)
    }

@app.get('/users/{user_id}')
def get_user(user_id, database):
    user = next((u for u in database["users"] if u["id"] == user_id), None)
    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')
    return user
```

## Session-Scoped Dependencies

For resources that should be shared across requests (like database connections), use startup handlers:

```python
@app.on_startup
def database():
    print("Opening database connection...")
    # In real app, create connection pool
    return {
        "pool": "connection_pool",
        "users": [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"}
        ]
    }

@app.on_shutdown
def close_database(database):
    print("Closing database connection...")
    # In real app, close connection pool

@app.get('/users')
def list_users(database):
    # Same database instance used across all requests
    return {"users": database["users"]}
```

!!! note "Session vs Request Scope"
    - `@app.on_startup` dependencies are created once when the application starts
    - `@app.dependency()` dependencies are created per request and cached for that request
    - Choose session scope for expensive resources (database pools, caches)
    - Choose request scope for request-specific data (current user, pagination)

## Validation Dependencies

Combine dependency injection with validation for clean request handling:

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=0, le=150)

@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.dependency()
def unique_email(validate_user: UserCreate, database):
    # Check if email already exists
    existing = next(
        (u for u in database["users"] if u["email"] == validate_user.email),
        None
    )
    if existing:
        from restmachine import Response
        raise ValueError("Email already registered")

    return validate_user.email

@app.post('/users')
def create_user(validate_user: UserCreate, unique_email: str, database):
    user = validate_user.model_dump()
    user["id"] = str(len(database["users"]) + 1)
    database["users"].append(user)
    return user, 201
```

## Advanced Patterns

### Factory Dependencies

Create dependencies that return different implementations:

```python
@app.dependency()
def storage(request: Request):
    # Choose storage based on environment or request
    env = request.headers.get('X-Environment', 'production')

    if env == 'test':
        return {"type": "memory", "data": {}}
    else:
        return {"type": "postgres", "connection": "..."}

@app.get('/data')
def get_data(storage):
    return {"storage_type": storage["type"]}
```

### Conditional Dependencies

Dependencies that may or may not be available:

```python
@app.dependency()
def optional_feature(request: Request):
    feature_flag = request.headers.get('X-Enable-Feature')
    if feature_flag == 'true':
        return {"enabled": True, "config": {...}}
    return None

@app.get('/feature')
def use_feature(optional_feature):
    if optional_feature:
        return {"status": "enabled", "config": optional_feature["config"]}
    return {"status": "disabled"}
```

### Optional Dependencies

Use default values for optional dependencies:

```python
@app.dependency()
def cache():
    # Simulate cache that might not be available
    return None  # Cache not configured

@app.get('/data')
def get_data(cache=None, database=None):
    if cache:
        return {"source": "cache", "data": cache.get("data")}

    if database:
        return {"source": "database", "data": database["users"]}

    return {"source": "none", "data": []}
```

## Repository Pattern

Use dependency injection to implement clean repository patterns:

```python
class UserRepository:
    def __init__(self, database):
        self.database = database

    def get_all(self):
        return self.database["users"]

    def get_by_id(self, user_id):
        return next(
            (u for u in self.database["users"] if u["id"] == user_id),
            None
        )

    def create(self, user_data):
        user = {**user_data, "id": str(len(self.database["users"]) + 1)}
        self.database["users"].append(user)
        return user

    def delete(self, user_id):
        self.database["users"] = [
            u for u in self.database["users"] if u["id"] != user_id
        ]

@app.dependency()
def user_repository(database):
    return UserRepository(database)

@app.get('/users')
def list_users(user_repository: UserRepository):
    return {"users": user_repository.get_all()}

@app.get('/users/{user_id}')
def get_user(user_id: str, user_repository: UserRepository):
    user = user_repository.get_by_id(user_id)
    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')
    return user

@app.post('/users')
def create_user(validate_user: UserCreate, user_repository: UserRepository):
    user = user_repository.create(validate_user.model_dump())
    return user, 201
```

## Service Pattern

Build services on top of repositories:

```python
class UserService:
    def __init__(self, user_repository, email_service):
        self.user_repository = user_repository
        self.email_service = email_service

    def register_user(self, user_data):
        # Create user
        user = self.user_repository.create(user_data)

        # Send welcome email
        self.email_service.send_welcome(user["email"])

        return user

    def get_user_with_stats(self, user_id):
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return None

        # Add computed statistics
        return {
            **user,
            "stats": {
                "posts": 0,  # Would query posts
                "followers": 0  # Would query followers
            }
        }

@app.dependency()
def email_service():
    class EmailService:
        def send_welcome(self, email):
            print(f"Sending welcome email to {email}")

    return EmailService()

@app.dependency()
def user_service(user_repository, email_service):
    return UserService(user_repository, email_service)

@app.post('/register')
def register(validate_user: UserCreate, user_service: UserService):
    user = user_service.register_user(validate_user.model_dump())
    return user, 201

@app.get('/users/{user_id}/stats')
def user_stats(user_id: str, user_service: UserService):
    user = user_service.get_user_with_stats(user_id)
    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')
    return user
```

## Testing with Dependency Overrides

Override dependencies for testing:

```python
# app.py
app = RestApplication()

@app.dependency()
def database():
    # Production database
    return create_real_database()

@app.get('/users')
def list_users(database):
    return {"users": database.get_all_users()}

# test_app.py
import pytest
from restmachine import Request

def test_list_users():
    # Create test database
    test_db = {
        "users": [
            {"id": "1", "name": "Test User"}
        ]
    }

    # Override database dependency
    @app.dependency()
    def database():
        return test_db

    # Test the endpoint
    request = Request(method='GET', path='/users')
    response = app.execute(request)

    import json
    data = json.loads(response.body)
    assert len(data["users"]) == 1
    assert data["users"][0]["name"] == "Test User"
```

## Complete Example

Here's a complete example combining all concepts:

```python
from restmachine import RestApplication, Request, Response
from pydantic import BaseModel, EmailStr
import json

app = RestApplication()

# Models
class UserCreate(BaseModel):
    name: str
    email: EmailStr

class User(UserCreate):
    id: str

# Session-scoped dependencies
@app.on_startup
def database():
    return {
        "users": [
            {"id": "1", "name": "Alice", "email": "alice@example.com"},
            {"id": "2", "name": "Bob", "email": "bob@example.com"}
        ]
    }

@app.on_shutdown
def close_database(database):
    print("Cleaning up database...")

# Repositories
class UserRepository:
    def __init__(self, database):
        self.database = database

    def get_all(self, offset=0, limit=20):
        return self.database["users"][offset:offset+limit]

    def get_by_id(self, user_id):
        return next((u for u in self.database["users"] if u["id"] == user_id), None)

    def get_by_email(self, email):
        return next((u for u in self.database["users"] if u["email"] == email), None)

    def create(self, user_data):
        user = {**user_data, "id": str(len(self.database["users"]) + 1)}
        self.database["users"].append(user)
        return user

    def count(self):
        return len(self.database["users"])

# Request-scoped dependencies
@app.dependency()
def user_repository(database):
    return UserRepository(database)

@app.dependency()
def pagination(request: Request):
    page = int(request.query_params.get('page', '1'))
    limit = int(request.query_params.get('limit', '20'))
    offset = (page - 1) * limit
    return {"page": page, "limit": limit, "offset": offset}

@app.dependency()
def current_user(request: Request, user_repository: UserRepository):
    auth_header = request.headers.get('authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    # In real app, validate token
    user_id = auth_header[7:]  # Simplified: token is user_id
    return user_repository.get_by_id(user_id)

# Validation dependencies
@app.validates
def validate_user(request: Request) -> UserCreate:
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.dependency()
def unique_email(validate_user: UserCreate, user_repository: UserRepository):
    existing = user_repository.get_by_email(validate_user.email)
    if existing:
        raise ValueError(f"Email {validate_user.email} already registered")
    return validate_user

# Routes
@app.get('/users')
def list_users(pagination, user_repository: UserRepository):
    users = user_repository.get_all(
        offset=pagination["offset"],
        limit=pagination["limit"]
    )
    total = user_repository.count()

    return {
        "users": users,
        "page": pagination["page"],
        "total": total,
        "pages": (total + pagination["limit"] - 1) // pagination["limit"]
    }

@app.get('/users/{user_id}')
def get_user(request: Request, user_repository: UserRepository):
    user_id = request.path_params['user_id']
    user = user_repository.get_by_id(user_id)

    if not user:
        return Response(404, json.dumps({"error": "User not found"}))

    return user

@app.post('/users')
def create_user(unique_email: UserCreate, user_repository: UserRepository):
    user = user_repository.create(unique_email.model_dump())
    return user, 201

@app.get('/profile')
def get_profile(current_user):
    if not current_user:
        return Response(401, json.dumps({"error": "Unauthorized"}))

    return {
        "user": current_user,
        "message": "This is your profile"
    }

# Error handler for validation errors
@app.error_handler(400)
def validation_error(request, message, **kwargs):
    return {"error": "Validation failed", "details": message}

# Run with ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Naming Conventions

Use clear, descriptive names for dependencies:

```python
# Good
@app.dependency()
def current_user(request: Request):
    ...

@app.dependency()
def database_connection():
    ...

# Avoid
@app.dependency()
def dep1():
    ...

@app.dependency()
def get_data():  # Too generic
    ...
```

### 2. Scope Selection

Choose the right scope for each dependency:

```python
# Session scope: Expensive resources shared across requests
@app.on_startup
def database_pool():
    return create_connection_pool()

@app.on_startup
def cache_client():
    return create_redis_client()

# Request scope: Request-specific data
@app.dependency()
def current_user(request: Request):
    return extract_user_from_token(request)

@app.dependency()
def request_id(request: Request):
    return request.headers.get('X-Request-ID', generate_id())
```

### 3. Dependency Organization

Group related dependencies:

```python
# auth.py
@app.dependency()
def current_user(request: Request):
    ...

@app.dependency()
def require_admin(current_user):
    if not current_user or not current_user.get('is_admin'):
        raise PermissionError("Admin access required")
    return current_user

# database.py
@app.on_startup
def database():
    ...

@app.dependency()
def user_repository(database):
    ...

@app.dependency()
def post_repository(database):
    ...
```

### 4. Error Handling

Handle dependency errors gracefully:

```python
@app.dependency()
def database():
    try:
        return create_database_connection()
    except ConnectionError as e:
        print(f"Database connection failed: {e}")
        raise

@app.dependency()
def current_user(request: Request):
    try:
        return validate_token(request.headers.get('authorization'))
    except InvalidTokenError:
        return None  # Return None instead of raising

@app.get('/protected')
def protected_route(current_user):
    if not current_user:
        from restmachine import Response
        return Response(401, '{"error": "Unauthorized"}')
    return {"user": current_user}
```

### 5. Type Hints

Use type hints for better IDE support and clarity:

```python
from typing import Optional, Dict, Any

@app.dependency()
def database() -> Dict[str, Any]:
    return {"users": [], "posts": []}

@app.dependency()
def current_user(request: Request) -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get('authorization')
    if not auth_header:
        return None
    return {"id": "123", "name": "User"}

@app.get('/profile')
def get_profile(current_user: Optional[Dict[str, Any]]):
    if not current_user:
        from restmachine import Response
        return Response(401, '{"error": "Unauthorized"}')
    return current_user
```

## Next Steps

- [Validation →](validation.md) - Learn about request validation with Pydantic
- [Authentication →](authentication.md) - Implement authentication and authorization
- [Testing →](testing.md) - Test your application with dependency overrides
- [Advanced Features →](../advanced/lifecycle.md) - Deep dive into lifecycle management

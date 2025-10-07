# Usage Guide

This guide covers how to use RestMachine's decorators to build REST APIs. We'll start with the most common patterns and progress to advanced usage.

## Route Decorators

Route decorators define HTTP endpoints for your API.

### Basic Routes

```python
from restmachine import RestApplication

app = RestApplication()

@app.get('/users')
def list_users():
    return {"users": ["Alice", "Bob"]}

@app.post('/users')
def create_user(json_body):
    return {"created": json_body}, 201

@app.get('/users/{user_id}')
def get_user(path_params):
    return {"id": path_params['user_id']}

@app.put('/users/{user_id}')
def update_user(path_params, json_body):
    return {"id": path_params['user_id'], "data": json_body}

@app.patch('/users/{user_id}')
def partial_update(path_params, json_body):
    return {"id": path_params['user_id'], "updates": json_body}

@app.delete('/users/{user_id}')
def delete_user(path_params):
    return None  # Returns 204 No Content

@app.head('/users/{user_id}')
def check_user(path_params):
    return None  # HEAD doesn't return body

@app.options('/users')
def user_options():
    return None, 200, {"Allow": "GET, POST, OPTIONS"}
```

### Path Parameters

Extract values from URL paths:

```python
@app.get('/users/{user_id}')
def get_user(path_params):
    user_id = path_params['user_id']
    return {"id": user_id}

@app.get('/posts/{post_id}/comments/{comment_id}')
def get_comment(path_params):
    return {
        "post_id": path_params['post_id'],
        "comment_id": path_params['comment_id']
    }
```

### Query Parameters

Access query string parameters:

```python
@app.get('/search')
def search(query_params):
    query = query_params.get('q', '')
    limit = int(query_params.get('limit', '20'))
    return {"query": query, "limit": limit}
```

### Request Body

Access request data through dependencies:

```python
# JSON body
@app.post('/data')
def handle_json(json_body):
    return {"received": json_body}

# Headers
@app.get('/headers')
def show_headers(request_headers):
    user_agent = request_headers.get('user-agent')
    return {"user_agent": user_agent}

# Full request object
@app.post('/raw')
def handle_raw(request):
    method = request.method
    path = request.path
    body = request.body
    return {"method": method, "path": path}
```

## Resource Decorators

Resource decorators define facts about your resources that the state machine uses to make decisions.

### Resource Existence

Automatically handle 404 responses:

```python
@app.on_startup
def database():
    return {"users": {"1": {"id": "1", "name": "Alice"}}}

@app.resource_exists
def user(path_params, database):
    """Returns None if not found, triggering automatic 404."""
    user_id = path_params['user_id']
    return database["users"].get(user_id)

@app.get('/users/{user_id}')
def get_user(user):
    # If user is None, 404 already returned
    # Otherwise user is cached and available here
    return user

@app.delete('/users/{user_id}')
def delete_user(user, database):
    # Same resource_exists dependency
    # Automatic 404 if user doesn't exist
    database["users"].pop(user['id'])
    return None
```

### Validation

Validate requests with Pydantic models:

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)

@app.validates
def user_create(json_body) -> UserCreate:
    """Returns 400/422 automatically on validation error."""
    return UserCreate.model_validate(json_body)

@app.post('/users')
def create_user(user_create: UserCreate, database):
    # Validation already handled by state machine
    user = user_create.model_dump()
    user['id'] = generate_id()
    database["users"][user['id']] = user
    return user, 201
```

Multiple validation decorators for different endpoints:

```python
class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None

@app.validates
def user_update(json_body) -> UserUpdate:
    return UserUpdate.model_validate(json_body)

@app.put('/users/{user_id}')
def update_user(user, user_update: UserUpdate):
    # Both validations applied automatically
    if user_update.name:
        user['name'] = user_update.name
    if user_update.email:
        user['email'] = user_update.email
    return user
```

## State Machine Decorators

State machine decorators define decision points that determine HTTP responses.

### Authorization

Check if requests are authenticated:

```python
@app.dependency()
def current_user(request_headers, database):
    token = request_headers.get('authorization', '').replace('Bearer ', '')
    return database.get_user_by_token(token)

@app.authorized
def check_auth(current_user):
    """Returns 401 if False."""
    return current_user is not None

@app.get('/protected')
def protected_resource(current_user):
    return {"user": current_user, "message": "Access granted"}
```

Per-route authorization:

```python
@app.get('/admin/users')
@app.authorized
def check_admin_auth(current_user):
    """Route-specific authorization check."""
    return current_user and current_user.get('is_admin')

def admin_users(database):
    return {"users": database.get_all_users()}
```

### Permissions

Check if authenticated users have required permissions:

```python
@app.forbidden
def check_permission(current_user, path_params):
    """Returns 403 if True (access is forbidden)."""
    # Allow users to access their own resources
    requested_user_id = path_params.get('user_id')
    is_own_resource = current_user['id'] == requested_user_id
    is_admin = current_user.get('is_admin', False)

    # Forbidden if not own resource and not admin
    return not is_own_resource and not is_admin

@app.put('/users/{user_id}')
def update_user(user, json_body):
    # 401 if not authenticated
    # 403 if not authorized (not own resource and not admin)
    # Otherwise update proceeds
    user.update(json_body)
    return user
```

### Conditional Requests (ETags)

Enable efficient caching with ETags:

```python
import hashlib

@app.etag
def user_etag(user):
    """Calculate ETag for user resource."""
    if not user:
        return None
    import json
    content = json.dumps(user, sort_keys=True)
    return f'"{hashlib.md5(content.encode()).hexdigest()}"'

@app.get('/users/{user_id}')
def get_user(user):
    # If client sends If-None-Match with matching ETag → 304 Not Modified
    # Otherwise → 200 OK with user data
    return user

@app.put('/users/{user_id}')
def update_user(user, json_body):
    # If client sends If-Match and it doesn't match → 412 Precondition Failed
    # This prevents mid-air collisions
    user.update(json_body)
    return user
```

### Last-Modified

Enable time-based conditional requests:

```python
from datetime import datetime

@app.last_modified
def user_last_modified(user):
    """Return last modification time."""
    if not user:
        return None
    return datetime.fromisoformat(user['updated_at'])

@app.get('/users/{user_id}')
def get_user(user):
    # If client sends If-Modified-Since and resource not modified → 304 Not Modified
    return user
```

### Service Availability

Control when your API is available:

```python
import os

@app.service_available
def check_maintenance(request):
    """Returns 503 if False."""
    # Allow health checks during maintenance
    if request.path == '/health':
        return True

    # Check maintenance mode
    return not os.environ.get('MAINTENANCE_MODE')

@app.get('/health')
def health_check():
    return {"status": "ok"}
```

### Method Checking

Control which HTTP methods are supported:

```python
@app.known_method
def check_method(request):
    """Returns 501 if False."""
    allowed = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'}
    return request.method.value in allowed
```

## Content Rendering

Define how responses are rendered in different formats.

### Multiple Content Types

Support multiple response formats:

```python
import json

@app.content_renderer("application/json")
def render_json(data):
    return json.dumps(data)

@app.content_renderer("application/xml")
def render_xml(data):
    return f"<data>{data}</data>"

@app.content_renderer("text/csv")
def render_csv(data):
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return str(data)

@app.get('/data')
def get_data():
    return {"message": "Hello"}
    # Client sends Accept: application/json → JSON response
    # Client sends Accept: application/xml  → XML response
    # Client sends Accept: text/csv         → CSV response
```

### Template Rendering

Render HTML templates:

```python
@app.content_renderer("text/html")
def render_html(data):
    # Use your preferred template engine
    from jinja2 import Template
    template = Template("<h1>{{ title }}</h1><p>{{ message }}</p>")
    return template.render(**data)

@app.get('/page')
def show_page():
    return {
        "title": "Welcome",
        "message": "Hello, World!"
    }
    # Accept: text/html → Rendered HTML page
```

## Dependency Decorators

Create reusable dependencies for your application.

### Basic Dependencies

```python
@app.dependency()
def database():
    return create_db_connection()

@app.dependency()
def pagination(query_params):
    page = int(query_params.get('page', '1'))
    limit = int(query_params.get('limit', '20'))
    return {"page": page, "limit": limit, "offset": (page - 1) * limit}

@app.get('/users')
def list_users(database, pagination):
    users = database.get_users(
        offset=pagination['offset'],
        limit=pagination['limit']
    )
    return {"users": users, "page": pagination['page']}
```

### Lifecycle Dependencies

Create dependencies that persist across requests:

```python
@app.on_startup
def database():
    """Created once at startup."""
    print("Opening database connection...")
    return create_connection_pool()

@app.on_shutdown
def close_database(database):
    """Called when application shuts down."""
    print("Closing database connection...")
    database.close()

@app.get('/users')
def list_users(database):
    # Same database instance across all requests
    return {"users": database.query_all()}
```

### Nested Dependencies

Dependencies can depend on other dependencies:

```python
@app.dependency()
def config():
    return {"db_host": "localhost", "db_port": 5432}

@app.dependency()
def database_url(config):
    return f"postgresql://{config['db_host']}:{config['db_port']}/mydb"

@app.dependency()
def database(database_url):
    return create_connection(database_url)
```

## Error Handling

Handle errors gracefully with custom error handlers.

### Custom Error Handlers

Define handlers for specific status codes:

```python
@app.error_handler(404)
def not_found_handler(request, message, **kwargs):
    return {
        "error": "Not Found",
        "message": message,
        "path": request.path
    }

@app.error_handler(500)
def server_error_handler(request, message, **kwargs):
    # Log the error
    import logging
    logging.error(f"Server error: {message}")

    return {
        "error": "Internal Server Error",
        "message": "Something went wrong"
    }
```

### Validation Error Handling

Handle Pydantic validation errors:

```python
from pydantic import ValidationError as PydanticValidationError

@app.error_handler(400)
def validation_error_handler(request, message, **kwargs):
    """Handle Pydantic validation errors."""
    validation_error = kwargs.get('validation_error')

    if validation_error and isinstance(validation_error, PydanticValidationError):
        errors = []
        for error in validation_error.errors():
            errors.append({
                "field": '.'.join(str(loc) for loc in error['loc']),
                "message": error['msg'],
                "type": error['type']
            })

        return {
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": errors
        }

    return {"error": "Bad Request", "message": message}
```

### Exception-Based Error Handling

Use custom exceptions:

```python
class AuthenticationError(Exception):
    pass

@app.dependency()
def current_user(request_headers):
    auth_header = request_headers.get('authorization')
    if not auth_header:
        raise AuthenticationError("Missing authentication header")
    return validate_token(auth_header)

@app.error_handler(401)
def auth_error_handler(request, message, **kwargs):
    exc_info = kwargs.get('exc_info')
    if exc_info and isinstance(exc_info[1], AuthenticationError):
        return {
            "error": "Authentication Failed",
            "message": str(exc_info[1]),
            "hint": "Include 'Authorization: Bearer <token>' header"
        }
    return {"error": "Unauthorized", "message": message}
```

### Error Context

Add context to error responses:

```python
import uuid
from datetime import datetime

@app.error_handler(500)
def server_error_with_context(request, message, **kwargs):
    """Server error with tracking information."""
    import logging

    request_id = request.headers.get('x-request-id', str(uuid.uuid4()))
    timestamp = datetime.now().isoformat()

    # Log detailed error
    exc_info = kwargs.get('exc_info')
    if exc_info:
        logging.error(
            f"Server error [{request_id}]: {message}",
            exc_info=exc_info,
            extra={
                'request_id': request_id,
                'path': request.path,
                'method': request.method
            }
        )

    # Return safe error response
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "request_id": request_id,
        "timestamp": timestamp
    }
```

### Consistent Error Format

Use a consistent format across all errors:

```python
def error_response(error_type: str, message: str, **extras):
    """Create consistent error response."""
    from datetime import datetime
    response = {
        "error": error_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    response.update(extras)
    return response

@app.error_handler(400)
def bad_request(request, message, **kwargs):
    return error_response("Bad Request", message, path=request.path)

@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    return error_response("Unauthorized", message)

@app.error_handler(404)
def not_found(request, message, **kwargs):
    return error_response("Not Found", message, path=request.path)
```

## Complete Example

Here's a complete example using multiple decorators:

```python
from restmachine import RestApplication
from pydantic import BaseModel, EmailStr
from datetime import datetime
import hashlib

app = RestApplication()

# Models
class UserCreate(BaseModel):
    name: str
    email: EmailStr

# Session dependencies
@app.on_startup
def database():
    return {"users": {}}

# Request dependencies
@app.dependency()
def current_user(request_headers, database):
    token = request_headers.get('authorization', '').replace('Bearer ', '')
    return database.get('users', {}).get(token)

# Resource decorators
@app.resource_exists
def user(path_params, database):
    return database["users"].get(path_params['user_id'])

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

# State machine decorators
@app.authorized
def is_authenticated(current_user):
    return current_user is not None

@app.forbidden
def can_modify(current_user, user):
    return current_user['id'] != user['id'] and not current_user.get('is_admin')

@app.etag
def user_etag(user):
    if not user:
        return None
    content = f"{user['id']}{user.get('updated_at', '')}"
    return f'"{hashlib.md5(content.encode()).hexdigest()}"'

# Routes
@app.get('/users')
def list_users(database):
    return {"users": list(database["users"].values())}

@app.post('/users')
def create_user(user_create: UserCreate, database):
    user = user_create.model_dump()
    user['id'] = str(len(database["users"]) + 1)
    user['updated_at'] = datetime.now().isoformat()
    database["users"][user['id']] = user
    return user, 201

@app.get('/users/{user_id}')
def get_user(user):
    return user

@app.put('/users/{user_id}')
def update_user(user, user_create: UserCreate):
    user['name'] = user_create.name
    user['email'] = user_create.email
    user['updated_at'] = datetime.now().isoformat()
    return user

@app.delete('/users/{user_id}')
def delete_user(user, database):
    database["users"].pop(user['id'])
    return None

# Error handlers
@app.error_handler(404)
def not_found(request, message, **kwargs):
    return {"error": "Not Found", "message": message, "path": request.path}

@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    return {"error": "Unauthorized", "message": "Authentication required"}
```

## Best Practices

### 1. Order Decorators Correctly

When stacking decorators, order matters:

```python
@app.get('/admin/users')
@app.authorized
def check_admin_auth(current_user):
    return current_user and current_user.get('is_admin')

def admin_users(database):
    return {"users": database.get_all_users()}
```

### 2. Use Specific Dependencies

Use specific dependencies instead of generic `request`:

```python
# Good
@app.get('/search')
def search(query_params):
    query = query_params.get('q')
    return {"results": search_db(query)}

# Less ideal
@app.get('/search')
def search(request):
    query = request.query_params.get('q')
    return {"results": search_db(query)}
```

### 3. Keep Dependencies Focused

Each dependency should have a single responsibility:

```python
# Good - focused dependencies
@app.dependency()
def current_user(request_headers):
    return extract_user_from_token(request_headers)

@app.dependency()
def is_admin(current_user):
    return current_user and current_user.get('is_admin')

# Less ideal - doing too much
@app.dependency()
def auth_and_check_admin(request_headers):
    user = extract_user_from_token(request_headers)
    return user and user.get('is_admin')
```

### 4. Return Correct Status Codes

Use appropriate status codes in responses:

```python
@app.post('/users')
def create_user(user_create: UserCreate):
    user = create_user_in_db(user_create)
    return user, 201  # Created

@app.delete('/users/{user_id}')
def delete_user(user):
    delete_from_db(user)
    return None  # 204 No Content

@app.put('/users/{user_id}')
def update_user(user, user_update):
    updated = update_in_db(user, user_update)
    return updated  # 200 OK
```

## Next Steps

- [Concepts →](concepts.md) - Understand the core concepts
- [Authentication →](authentication.md) - Implement authentication
- [Content Negotiation →](content-negotiation.md) - Multiple response formats
- [ETags →](etags.md) - Efficient caching
- [OpenAPI →](openapi.md) - API documentation

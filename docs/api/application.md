# Application

::: restmachine.RestApplication
    options:
      show_root_heading: true
      heading_level: 2
      show_source: false
      members:
        - __init__
        - get
        - post
        - put
        - patch
        - delete
        - head
        - options
        - route
        - dependency
        - validates
        - content_renderer
        - error_handler
        - on_startup
        - on_shutdown
        - mount
        - execute
        - startup_sync
        - shutdown_sync

## Overview

`RestApplication` is the main entry point for building REST APIs with RestMachine. It provides:

- **Route registration** - Flask-style decorators for HTTP methods
- **Dependency injection** - pytest-style parameter injection
- **Content negotiation** - Automatic format selection based on Accept headers
- **Validation** - Optional Pydantic integration for request/response validation
- **Lifecycle hooks** - Startup and shutdown handlers
- **Router mounting** - Compose applications from multiple routers

## Quick Start

```python
from restmachine import RestApplication

app = RestApplication()

@app.get('/hello/{name}')
def hello(path_params):
    name = path_params['name']
    return {"message": f"Hello, {name}!"}
```

## Route Registration

### HTTP Method Decorators

Register routes using HTTP method decorators:

```python
@app.get('/users')
def list_users():
    return {"users": [...]}

@app.post('/users')
def create_user(json_body):
    # json_body automatically injected for JSON requests
    return {"created": True}, 201

@app.put('/users/{user_id}')
def update_user(path_params, json_body):
    user_id = path_params['user_id']
    return {"updated": user_id}

@app.delete('/users/{user_id}')
def delete_user(path_params):
    user_id = path_params['user_id']
    return {"deleted": user_id}, 204
```

### Path Parameters

Use `{param}` syntax for path parameters, accessed via the `path_params` dependency:

```python
@app.get('/users/{user_id}/posts/{post_id}')
def get_post(path_params):
    user_id = path_params['user_id']
    post_id = path_params['post_id']
    return {"user_id": user_id, "post_id": post_id}
```

### Generic Route Registration

Use `@app.route()` for custom methods or multiple methods:

```python
@app.route('PATCH', '/users/{user_id}')
def patch_user(request):
    return {"patched": True}
```

## Dependency Injection

Share resources across handlers using pytest-style dependency injection:

```python
@app.on_startup
def database():
    """Create database connection at startup."""
    return create_db_connection()

@app.resource_exists
def user(database, path_params):
    """Check if user exists and return it."""
    user_id = path_params.get('user_id')
    return database.get_user(user_id)  # Returns None if not found

@app.get('/users/{user_id}')
def get_user(user):
    """User is injected, 404 handled automatically if None."""
    return user

@app.get('/posts')
def list_posts(database):
    """Database instance is reused across all requests."""
    return {"posts": database.query("SELECT * FROM posts")}
```

Startup dependencies persist across all requests. See [Dependency Injection Guide](../guide/dependency-injection.md) for details.

## Request Validation

Validate request bodies using Pydantic with the `@app.validates` decorator:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

@app.validates
def validate_user(json_body) -> UserCreate:
    """Validates JSON body, returns 422 on validation error."""
    return UserCreate.model_validate(json_body)

@app.post('/users')
def create_user(validate_user: UserCreate):
    """Validated model is injected, errors handled automatically."""
    return {"created": validate_user.model_dump()}, 201
```

## Content Negotiation

Serve multiple formats using the `@app.provides` decorator:

```python
@app.get('/data')
def get_data():
    return {"key": "value"}

@app.provides("text/html")
def render_html(get_data):
    data = get_data
    return f"<div>{data}</div>"

@app.provides("application/xml")
def render_xml(get_data):
    data = get_data
    return f"<result>{data}</result>"
# Returns JSON, HTML, or XML based on Accept header
```

Built-in renderers: JSON (default), HTML, Plain Text. See [Content Negotiation Guide](../guide/content-negotiation.md) for details.

## Error Handling

Register custom error handlers:

```python
@app.error_handler(404)
def not_found_handler(error):
    """Handle 404 errors."""
    return {"error": "Not Found", "path": error.get("path")}, 404

@app.error_handler(500)
def server_error_handler(error):
    """Handle 500 errors."""
    return {"error": "Internal Server Error"}, 500

@app.error_handler()  # Default handler for all errors
def default_error_handler(error):
    """Fallback for unhandled errors."""
    return {"error": "Something went wrong"}, 500
```

## Lifecycle Handlers

Manage application startup and shutdown:

```python
@app.on_startup
def init_database():
    """Runs once at startup."""
    print("Initializing database...")
    return create_db_connection()

@app.on_shutdown
def close_database(init_database):
    """Runs at shutdown, can inject startup dependencies."""
    print("Closing database...")
    init_database.close()

@app.on_startup(scope=DependencyScope.SESSION)
def load_config():
    """SESSION scope - persists across requests."""
    return load_app_config()
```

See [Lifecycle Handlers Guide](../advanced/lifecycle.md) for details.

## Mounting Routers

Compose applications from multiple routers:

```python
from restmachine import Router

api_v1 = Router()

@api_v1.get('/users')
def list_users():
    return {"users": [...]}

# Mount at /api/v1
app.mount('/api/v1', api_v1)

# Access: GET /api/v1/users
```

See [Router API](router.md) for details.

## Executing Requests

Execute requests directly (useful for testing):

```python
from restmachine import Request, HTTPMethod

request = Request(
    method=HTTPMethod.GET,
    path="/users/123",
    headers={},
    query_params={},
    body=""
)

response = app.execute(request)
print(response.status_code, response.body)
```

## Deployment

### ASGI Servers

```python
from restmachine import ASGIAdapter

asgi_app = ASGIAdapter(app)

# Run with uvicorn
# uvicorn app:asgi_app --reload
```

### AWS Lambda

```python
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

## Configuration

### Constructor Options

```python
app = RestApplication(
    # Add custom configuration here if needed
)
```

## See Also

- [Getting Started Guide](../getting-started/quickstart.md) - Build your first API
- [Basic Application Guide](../guide/basic-application.md) - Core concepts
- [Dependency Injection](../guide/dependency-injection.md) - Share resources
- [Content Negotiation](../guide/content-negotiation.md) - Multiple formats
- [Validation](../guide/validation.md) - Request/response validation
- [Router API](router.md) - Composable routers
- [Request & Response](models.md) - Request/response models

# Basic Application

This guide covers the fundamentals of building a RestMachine application.

## Creating Your First Application

### Minimal Application

The simplest RestMachine application requires just a few lines:

```python
from restmachine import RestApplication

app = RestApplication()

@app.get('/')
def home():
    return {"message": "Hello, World!"}
```

### Running the Application

You can test your application in several ways:

=== "Direct Execution"
    ```python
    from restmachine import Request, HTTPMethod

    request = Request(method=HTTPMethod.GET, path='/')
    response = app.execute(request)
    print(response.body)  # {"message": "Hello, World!"}
    ```

=== "With ASGI Server"
    ```python
    from restmachine import ASGIAdapter

    asgi_app = ASGIAdapter(app)

    # Run with: uvicorn app:asgi_app --reload
    ```

## Defining Routes

### HTTP Methods

RestMachine supports all standard HTTP methods:

```python
@app.get('/users')
def list_users():
    return {"users": ["Alice", "Bob"]}

@app.post('/users')
def create_user(json_body):
    # Access parsed JSON body via dependency injection
    return {"created": json_body}, 201

@app.put('/users/{user_id}')
def update_user(path_params, json_body):
    user_id = path_params['user_id']
    return {"updated": user_id, "data": json_body}

@app.patch('/users/{user_id}')
def partial_update(path_params, json_body):
    return {"patched": path_params['user_id']}

@app.delete('/users/{user_id}')
def delete_user(path_params):
    # Returning None gives 204 No Content
    return None

@app.head('/users/{user_id}')
def user_head(path_params):
    # HEAD requests don't return a body
    return None

@app.options('/users')
def user_options():
    return None, 200, {"Allow": "GET, POST, OPTIONS"}
```

### Path Parameters

Capture dynamic path segments using the `path_params` dependency:

```python
@app.get('/users/{user_id}')
def get_user(path_params):
    user_id = path_params['user_id']
    return {"user_id": user_id}

@app.get('/posts/{post_id}/comments/{comment_id}')
def get_comment(path_params):
    post_id = path_params['post_id']
    comment_id = path_params['comment_id']
    return {
        "post_id": post_id,
        "comment_id": comment_id
    }
```

### Query Parameters

Access query string parameters using the `query_params` dependency:

```python
@app.get('/search')
def search(query_params):
    # URL: /search?q=python&limit=10
    query = query_params.get('q', '')
    limit = int(query_params.get('limit', '20'))

    return {
        "query": query,
        "limit": limit,
        "results": []
    }
```

## Working with Requests

### Request Object

The `Request` object contains all information about the incoming request:

```python
@app.post('/example')
def example_handler(request):
    # HTTP method
    method = request.method  # HTTPMethod.POST

    # Path
    path = request.path  # "/example"

    # Headers (case-insensitive)
    content_type = request.headers.get('content-type')
    auth = request.headers.get('authorization')

    # Body (raw bytes or string)
    body = request.body

    # Query parameters
    params = request.query_params  # dict

    # Path parameters
    path_params = request.path_params  # dict

    # Parsed JSON (if content-type is application/json)
    import json
    if content_type == 'application/json':
        data = json.loads(body)

    return {"received": True}
```

### Request Headers

Headers are case-insensitive and support multiple values. Use the `request_headers` dependency:

```python
@app.get('/headers')
def show_headers(request_headers):
    # Get single header
    user_agent = request_headers.get('user-agent')

    # Get all headers
    all_headers = dict(request_headers)

    # Check if header exists
    has_auth = 'authorization' in request_headers

    return {
        "user_agent": user_agent,
        "headers": all_headers,
        "authenticated": has_auth
    }
```

### Request Body

For JSON requests, use the `json_body` dependency for automatic parsing:

```python
@app.post('/data')
def handle_json(json_body):
    # json_body is automatically parsed from application/json requests
    return {"received": json_body}
```

For other content types, use the `request` dependency:

```python
@app.post('/form')
def handle_form(request):
    content_type = request.headers.get('content-type', '')

    if 'application/x-www-form-urlencoded' in content_type:
        from urllib.parse import parse_qs
        data = parse_qs(request.body.decode())
        return {"form": data}

    elif 'text/plain' in content_type:
        text = request.body.decode()
        return {"text": text}

    else:
        return {"error": "Unsupported content type"}, 415
```

## Working with Responses

### Returning Data

RestMachine automatically serializes return values:

```python
# Return dict (automatically JSON-encoded)
@app.get('/json')
def return_json():
    return {"key": "value"}

# Return string
@app.get('/text')
def return_text():
    return "Plain text response"

# Return list
@app.get('/list')
def return_list():
    return [1, 2, 3, 4, 5]

# Return None (204 No Content)
@app.delete('/resource')
def delete_resource():
    return None
```

### Response Object

For more control, return a `Response` object:

```python
from restmachine import Response

@app.get('/custom')
def custom_response():
    return Response(
        status_code=201,
        body='{"created": true}',
        headers={
            'Content-Type': 'application/json',
            'X-Custom-Header': 'value'
        }
    )
```

### Status Codes

Specify status codes in several ways:

```python
# Tuple: (body, status_code)
@app.post('/users')
def create_user(json_body):
    return {"user": "created"}, 201

# Tuple: (body, status_code, headers)
@app.get('/redirect')
def redirect():
    return None, 302, {"Location": "/new-location"}

# Response object
@app.get('/error')
def error():
    from restmachine import Response
    return Response(404, "Not Found")
```

### Response Headers

Add custom headers:

```python
@app.get('/cached')
def cached_resource():
    return (
        {"data": "value"},
        200,
        {
            'Cache-Control': 'max-age=3600',
            'ETag': '"abc123"',
            'Last-Modified': 'Wed, 21 Oct 2015 07:28:00 GMT'
        }
    )
```

## Content Negotiation

RestMachine automatically handles content negotiation based on the `Accept` header:

```python
import json

# Register JSON renderer (built-in)
@app.content_renderer("application/json")
def render_json(data):
    return json.dumps(data)

# Register XML renderer
@app.content_renderer("application/xml")
def render_xml(data):
    return f"<data>{data}</data>"

# Register CSV renderer
@app.content_renderer("text/csv")
def render_csv(data):
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return str(data)

@app.get('/data')
def get_data():
    return {"message": "Hello"}

# Client requests:
# Accept: application/json → {"message": "Hello"}
# Accept: application/xml  → <data>{'message': 'Hello'}</data>
# Accept: text/csv         → message
```

## Error Handling

### Built-in Error Responses

Use decorators to automatically generate appropriate error responses:

```python
# Use @app.resource_exists to return 404 when resource not found
@app.resource_exists
def user_exists(path_params):
    user_id = path_params['user_id']
    # Return None to trigger 404, or return the resource
    users = {"1": {"id": "1", "name": "Alice"}}
    return users.get(user_id)

@app.get('/users/{user_id}')
def get_user(user_exists):
    # user_exists is injected - if it was None, 404 already returned
    return user_exists
```

### Custom Error Handlers

Define custom handlers for specific status codes:

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
    print(f"Server error: {message}")

    return {
        "error": "Internal Server Error",
        "message": "Something went wrong"
    }
```

## Application Configuration

### Debug Mode

Enable debug mode for development:

```python
app = RestApplication()

# Development
if __name__ == '__main__':
    # Enable detailed error messages
    import traceback
    app.debug = True
```

### Custom Configuration

Store configuration in your application:

```python
class Config:
    DEBUG = True
    DATABASE_URL = "postgresql://localhost/mydb"
    API_KEY = "secret"

app = RestApplication()
app.config = Config()

@app.get('/config')
def show_config():
    return {
        "debug": app.config.DEBUG,
        "database": app.config.DATABASE_URL
    }
```

## Complete Example

Here's a complete example using dependency injection and decorators:

```python
from restmachine import RestApplication, Request, HTTPMethod
from pydantic import BaseModel, Field

app = RestApplication()

# In-memory data store
users = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com"}
}

# Validation models
class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')

class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None

# Decorators for proper status codes
@app.resource_exists
def user_exists(path_params):
    """Returns user or None (which triggers 404)."""
    user_id = path_params.get('user_id')
    return users.get(user_id)

@app.validates
def validate_create(json_body) -> CreateUserRequest:
    """Validates create request, returns 422 on error."""
    return CreateUserRequest.model_validate(json_body)

@app.validates
def validate_update(json_body) -> UpdateUserRequest:
    """Validates update request, returns 422 on error."""
    return UpdateUserRequest.model_validate(json_body)

# List all users
@app.get('/users')
def list_users(query_params):
    # Support filtering by name
    name_filter = query_params.get('name')

    if name_filter:
        filtered = [u for u in users.values()
                   if name_filter.lower() in u['name'].lower()]
        return {"users": filtered}

    return {"users": list(users.values())}

# Get single user
@app.get('/users/{user_id}')
def get_user(user_exists):
    # user_exists decorator handles 404 automatically
    return user_exists

# Create user
@app.post('/users')
def create_user(validate_create: CreateUserRequest):
    # Validation decorator handles 422 automatically
    user_id = str(len(users) + 1)
    user = {
        "id": user_id,
        **validate_create.model_dump()
    }
    users[user_id] = user
    return user, 201

# Update user
@app.put('/users/{user_id}')
def update_user(user_exists, validate_update: UpdateUserRequest):
    # Both decorators handle 404 and 422 automatically
    if validate_update.name:
        user_exists['name'] = validate_update.name
    if validate_update.email:
        user_exists['email'] = validate_update.email

    return user_exists

# Delete user
@app.delete('/users/{user_id}')
def delete_user(user_exists, path_params):
    # resource_exists decorator handles 404 automatically
    user_id = path_params['user_id']
    del users[user_id]
    return None  # Returns 204 No Content

# Custom error handler
@app.error_handler(404)
def not_found(request, message, **kwargs):
    return {
        "error": "Not Found",
        "message": message,
        "path": request.path
    }

# Run with ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)

if __name__ == '__main__':
    # Test locally
    req = Request(method=HTTPMethod.GET, path='/users')
    resp = app.execute(req)
    print(resp.body)
```

## Next Steps

- [Dependency Injection →](dependency-injection.md) - Learn advanced DI patterns
- [Request Validation →](validation.md) - Add Pydantic validation
- [Authentication →](authentication.md) - Secure your API
- [Testing →](testing.md) - Test your application

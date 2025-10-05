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
def create_user(request):
    # Access request body
    import json
    data = json.loads(request.body)
    return {"created": data}, 201

@app.put('/users/{user_id}')
def update_user(request):
    user_id = request.path_params['user_id']
    return {"updated": user_id}

@app.patch('/users/{user_id}')
def partial_update(request):
    return {"patched": True}

@app.delete('/users/{user_id}')
def delete_user(request):
    return {"deleted": True}, 204

@app.head('/users/{user_id}')
def user_exists(request):
    # HEAD requests don't return a body
    return None, 200

@app.options('/users')
def user_options():
    return None, 200, {"Allow": "GET, POST, OPTIONS"}
```

### Path Parameters

Capture dynamic path segments:

```python
@app.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']
    return {"user_id": user_id}

@app.get('/posts/{post_id}/comments/{comment_id}')
def get_comment(request):
    post_id = request.path_params['post_id']
    comment_id = request.path_params['comment_id']
    return {
        "post_id": post_id,
        "comment_id": comment_id
    }
```

### Query Parameters

Access query string parameters:

```python
@app.get('/search')
def search(request):
    # URL: /search?q=python&limit=10
    query = request.query_params.get('q', '')
    limit = int(request.query_params.get('limit', '20'))

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

Headers are case-insensitive and support multiple values:

```python
@app.get('/headers')
def show_headers(request):
    # Get single header
    user_agent = request.headers.get('user-agent')

    # Get all headers
    all_headers = dict(request.headers)

    # Check if header exists
    has_auth = 'authorization' in request.headers

    return {
        "user_agent": user_agent,
        "headers": all_headers,
        "authenticated": has_auth
    }
```

### Request Body

Handle different content types:

```python
import json

@app.post('/data')
def handle_data(request):
    content_type = request.headers.get('content-type', '')

    if 'application/json' in content_type:
        data = json.loads(request.body)
        return {"json": data}

    elif 'application/x-www-form-urlencoded' in content_type:
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
def create_user(request):
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

RestMachine automatically generates appropriate error responses:

```python
@app.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']

    # Simulate user not found
    if user_id == "999":
        from restmachine import Response
        return Response(404, "User not found")

    return {"user_id": user_id}
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

Here's a complete example combining all concepts:

```python
from restmachine import RestApplication, Request, Response
import json

app = RestApplication()

# In-memory data store
users = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com"}
}

# List all users
@app.get('/users')
def list_users(request):
    # Support filtering by name
    name_filter = request.query_params.get('name')

    if name_filter:
        filtered = [u for u in users.values()
                   if name_filter.lower() in u['name'].lower()]
        return {"users": filtered}

    return {"users": list(users.values())}

# Get single user
@app.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']

    user = users.get(user_id)
    if not user:
        return Response(404, json.dumps({"error": "User not found"}))

    return user

# Create user
@app.post('/users')
def create_user(request):
    data = json.loads(request.body)

    # Validate required fields
    if 'name' not in data or 'email' not in data:
        return Response(400, json.dumps({
            "error": "Missing required fields: name, email"
        }))

    # Generate ID
    user_id = str(len(users) + 1)
    user = {
        "id": user_id,
        "name": data['name'],
        "email": data['email']
    }
    users[user_id] = user

    return user, 201

# Update user
@app.put('/users/{user_id}')
def update_user(request):
    user_id = request.path_params['user_id']

    if user_id not in users:
        return Response(404, json.dumps({"error": "User not found"}))

    data = json.loads(request.body)
    users[user_id].update(data)

    return users[user_id]

# Delete user
@app.delete('/users/{user_id}')
def delete_user(request):
    user_id = request.path_params['user_id']

    if user_id not in users:
        return Response(404, json.dumps({"error": "User not found"}))

    del users[user_id]
    return None, 204

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
    req = Request(method='GET', path='/users')
    resp = app.execute(req)
    print(resp.body)
```

## Next Steps

- [Dependency Injection →](dependency-injection.md) - Learn advanced DI patterns
- [Request Validation →](validation.md) - Add Pydantic validation
- [Authentication →](authentication.md) - Secure your API
- [Testing →](testing.md) - Test your application

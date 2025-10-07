# Request & Response Models

## Request

::: restmachine.Request
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## Response

::: restmachine.Response
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## HTTPMethod

::: restmachine.HTTPMethod
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## Overview

These are the core models for handling HTTP requests and responses in RestMachine.

### Request Model

The `Request` object encapsulates an incoming HTTP request with:

- **method** - HTTP method (GET, POST, PUT, DELETE, etc.)
- **path** - Request path
- **headers** - HTTP headers (case-insensitive)
- **query_params** - Query string parameters
- **path_params** - Path parameters from route matching
- **body** - Request body (string or bytes)

### Response Model

The `Response` object represents an HTTP response with:

- **status_code** - HTTP status code (200, 404, 500, etc.)
- **body** - Response body (string)
- **headers** - HTTP response headers

### HTTPMethod Enum

Enum of supported HTTP methods:
- GET
- POST
- PUT
- DELETE
- PATCH
- HEAD
- OPTIONS

## Request Usage

### Accessing Request Data

```python
@app.get('/users/{user_id}')
def get_user(request: Request):
    # Path parameters
    user_id = request.path_params['user_id']

    # Query parameters
    page = request.query_params.get('page', '1')

    # Headers
    auth = request.headers.get('authorization')

    # Body (for POST/PUT)
    # body = request.body

    return {"user_id": user_id, "page": page}
```

### Creating Requests Manually

Useful for testing:

```python
from restmachine import Request, HTTPMethod

request = Request(
    method=HTTPMethod.GET,
    path="/users/123",
    headers={"authorization": "Bearer token"},
    query_params={"page": "1"},
    path_params={"user_id": "123"},
    body=""
)

response = app.execute(request)
```

## Response Usage

### Returning Responses

Handlers can return responses in multiple ways:

**1. Dictionary (auto-converted to JSON):**

```python
@app.get('/users')
def list_users():
    return {"users": [...]}  # 200 OK with JSON
```

**2. Tuple (body, status_code):**

```python
@app.post('/users')
def create_user(request):
    return {"created": True}, 201  # 201 Created
```

**3. Tuple (body, status_code, headers):**

```python
@app.get('/file')
def download_file():
    return "file contents", 200, {
        "Content-Type": "text/plain",
        "Content-Disposition": "attachment; filename=file.txt"
    }
```

**4. Explicit Response object:**

```python
from restmachine import Response

@app.get('/custom')
def custom_response():
    return Response(
        status_code=200,
        body='{"custom": true}',
        headers={"X-Custom-Header": "value"}
    )
```

### Response Status Codes

Use `http.HTTPStatus` for readable status codes:

```python
from http import HTTPStatus

@app.post('/users')
def create_user(request):
    return {"created": True}, HTTPStatus.CREATED

@app.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']
    user = db.get(user_id)

    if not user:
        return {"error": "Not found"}, HTTPStatus.NOT_FOUND

    return user, HTTPStatus.OK
```

Common status codes:
- `200 OK` - Successful GET/PUT/PATCH
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## HTTPMethod Usage

The `HTTPMethod` enum provides type-safe HTTP method constants:

```python
from restmachine import HTTPMethod

# Used internally for route matching
@app.route(HTTPMethod.POST, '/users')
def create_user(request):
    return {"created": True}

# Or use string (converted automatically)
@app.route('PATCH', '/users/{user_id}')
def patch_user(request):
    return {"patched": True}
```

## Headers

### Request Headers

Headers are case-insensitive:

```python
@app.get('/data')
def get_data(request: Request):
    # All of these work:
    auth = request.headers.get('Authorization')
    auth = request.headers.get('authorization')
    auth = request.headers.get('AUTHORIZATION')

    content_type = request.headers.get('content-type')

    return {"auth": auth, "type": content_type}
```

### Response Headers

Set response headers in tuple return or Response object:

```python
# Via tuple
@app.get('/data')
def get_data():
    return {"data": ...}, 200, {
        "Cache-Control": "max-age=3600",
        "X-API-Version": "1.0"
    }

# Via Response
from restmachine import Response

@app.get('/data')
def get_data():
    return Response(
        status_code=200,
        body='{"data": "value"}',
        headers={
            "Cache-Control": "max-age=3600",
            "X-API-Version": "1.0"
        }
    )
```

## Query Parameters

Access query parameters from the request:

```python
@app.get('/search')
def search(request: Request):
    # GET /search?q=python&page=2
    query = request.query_params.get('q')
    page = int(request.query_params.get('page', '1'))

    results = search_db(query, page=page)
    return {"results": results, "page": page}
```

## Request Body

Access and parse request bodies:

```python
@app.post('/users')
def create_user(request: Request):
    import json

    # Parse JSON body
    data = json.loads(request.body)
    name = data['name']
    email = data['email']

    user = db.create_user(name=name, email=email)
    return {"created": user}, 201
```

For automatic validation, use `@app.validates`:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    return UserCreate.model_validate(json.loads(request.body))

@app.post('/users')
def create_user(validate_user: UserCreate):
    # validate_user is already parsed and validated
    return {"created": validate_user.model_dump()}, 201
```

## See Also

- [Application API](application.md) - Main application class
- [Basic Application Guide](../guide/basic-application.md) - Core concepts
- [Validation Guide](../guide/validation.md) - Request validation
- [Testing Guide](../guide/testing.md) - Testing with Request/Response

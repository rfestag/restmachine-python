# Overview

RestMachine is a Python REST framework designed to make building APIs simple while providing powerful features when you need them.

## Philosophy

RestMachine follows these core principles:

1. **Simple by default** - Start with minimal code, add features as needed
2. **Explicit over implicit** - Clear, readable code over magic
3. **Dependency injection** - pytest-style DI for clean, testable code
4. **HTTP semantics** - Respect HTTP standards and best practices
5. **Deployment flexibility** - Run anywhere from local dev to AWS Lambda

## Architecture

### State Machine

RestMachine uses a webmachine-inspired HTTP state machine to handle requests. This provides:

- Automatic content negotiation
- Conditional request handling (ETags, If-Modified-Since)
- Correct HTTP status codes by default
- Extensible via callbacks

```mermaid
graph TD
    A[Incoming Request] --> B{Route Matched?}
    B -->|No| C[404 Not Found]
    B -->|Yes| D{Method Allowed?}
    D -->|No| E[405 Method Not Allowed]
    D -->|Yes| F{Content Negotiation}
    F -->|Success| G[Execute Handler]
    F -->|Fail| H[406 Not Acceptable]
    G --> I{Validation}
    I -->|Success| J[Render Response]
    I -->|Fail| K[400 Bad Request]
    J --> L[Send Response]
```

### Dependency Injection

Dependencies are resolved using pytest-style parameter injection:

```python
@app.dependency()
def database():
    return create_db_connection()

@app.get('/users')
def list_users(database):  # 'database' automatically injected
    return database.query("SELECT * FROM users")
```

Dependencies are cached within a request by default, ensuring expensive operations (like database connections) only happen once.

## Core Concepts

### Application

The `RestApplication` is the main entry point:

```python
from restmachine import RestApplication

app = RestApplication()
```

### Routes

Routes are defined using decorators:

```python
@app.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']
    return {"id": user_id}
```

Supported HTTP methods:
- `@app.get(path)`
- `@app.post(path)`
- `@app.put(path)`
- `@app.patch(path)`
- `@app.delete(path)`
- `@app.head(path)`
- `@app.options(path)`

### Request & Response

- **Request** - Contains method, path, headers, body, query params, path params
- **Response** - Can be dict (auto-serialized), string, or explicit Response object

```python
from restmachine import Response

@app.get('/custom')
def custom_response():
    return Response(
        status_code=201,
        body="Created",
        headers={"X-Custom": "Header"}
    )
```

### Content Negotiation

RestMachine automatically negotiates content types based on the `Accept` header:

```python
@app.content_renderer("application/json")
def render_json(data):
    import json
    return json.dumps(data)

@app.content_renderer("application/xml")
def render_xml(data):
    return f"<data>{data}</data>"
```

Requests with `Accept: application/json` will use the JSON renderer, while `Accept: application/xml` will use the XML renderer.

## Deployment Options

RestMachine supports multiple deployment targets:

| Deployment | Use Case | Adapter |
|-----------|----------|---------|
| **ASGI Servers** | Production web servers | `ASGIAdapter` |
| **AWS Lambda** | Serverless, auto-scaling | `AwsApiGatewayAdapter` |
| **Direct** | Testing, development | `app.execute(request)` |

### ASGI Deployment

```python
from restmachine import ASGIAdapter

asgi_app = ASGIAdapter(app)
```

Run with any ASGI server:

```bash
uvicorn app:asgi_app --reload           # Uvicorn
hypercorn app:asgi_app --reload         # Hypercorn
daphne app:asgi_app                     # Daphne
```

### AWS Lambda Deployment

```python
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

Supports:
- API Gateway REST API (v1)
- API Gateway HTTP API (v2)
- Application Load Balancer (ALB)
- Lambda Function URLs

## What's Next?

- [Installation →](installation.md) - Install RestMachine
- [Quick Start →](quickstart.md) - Build your first API
- [Basic Application →](../guide/basic-application.md) - Learn the fundamentals

# RestMachine

*A lightweight REST framework with pytest-style dependency injection and webmachine-inspired state machine*

[![Build Status](https://github.com/rfestag/restmachine-python/workflows/CI/badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Coverage](https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Code Quality](https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/rfestag/restmachine-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

RestMachine is a modern Python REST framework that makes building APIs straightforward:

- **Easy to learn** - Familiar Flask-like decorators and intuitive patterns
- **Share resources cleanly** - Pass database connections, configs, and services to handlers without globals
- **HTTP done right** - Automatic content negotiation, proper status codes, and standards compliance
- **Flexible validation** - Use Pydantic when you need it, skip it when you don't
- **Deploy anywhere** - Same code runs on Uvicorn, Hypercorn, or AWS Lambda
- **Start simple** - Zero required dependencies, add features as you need them

## Quick Example

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.get('/hello/{name}')
def hello(request: Request):
    name = request.path_params['name']
    return {"message": f"Hello, {name}!"}

# Run with ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

Deploy with any ASGI server:

```bash
uvicorn app:asgi_app --reload
```

Or deploy to AWS Lambda:

```python
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

## Key Features

### Share Resources Easily

Pass database connections, configs, and services to your handlers automatically:

```python
@app.on_startup
def database():
    """Initialize database connection at startup."""
    return create_db_connection()

@app.resource_exists
def user(database, path_params):
    user_id = path_params['user_id']
    return database.get_user(user_id)  # Returns None if not found

@app.get('/users/{user_id}')
def get_user(user):
    return user  # 404 handled automatically if None
```

### Request Validation

Optional Pydantic integration for type-safe validation:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

@app.validates
def user_create(request: Request) -> UserCreate:
    import json
    return UserCreate.model_validate(json.loads(request.body))

@app.post('/users')
def create_user(user_create: UserCreate):
    return {"created": user_create.model_dump()}
```

### Serve Multiple Formats

Automatically serve JSON, XML, or custom formats based on what clients request:

```python
@app.get('/data')
def get_data():
    return {"message": "Hello", "timestamp": "2024-01-01"}

@app.provides("text/html")
def render_html(get_data):
    data = get_data
    return f"<h1>{data['message']}</h1><p>Time: {data['timestamp']}</p>"

@app.provides("text/xml")
def render_xml(get_data):
    data = get_data
    return f"<result><message>{data['message']}</message></result>"
```

### Automatic OpenAPI Documentation

Generate OpenAPI 3.0 specifications automatically from your code:

```python
# Generate OpenAPI spec
openapi_json = app.generate_openapi_json(
    title="My API",
    version="1.0.0"
)

# Or save to file for Swagger UI, client SDK generation, etc.
app.save_openapi_json(filename="openapi.json")
```

### Manage Resources Cleanly

Set up and tear down resources like database connections automatically:

```python
@app.on_startup
def database():
    print("Opening database connection...")
    return create_db_connection()

@app.on_shutdown
def close_database(database):
    print("Closing database connection...")
    database.close()
```

## Installation

=== "Basic"
    ```bash
    pip install restmachine
    ```

=== "With Validation"
    ```bash
    pip install restmachine[validation]
    ```

=== "With AWS Lambda"
    ```bash
    pip install restmachine restmachine-aws
    ```

## Next Steps

- **[Getting Started →](getting-started/overview.md)** - Learn the basics
- **[Quick Start →](getting-started/quickstart.md)** - Build your first API
- **[User Guide →](guide/basic-application.md)** - Comprehensive tutorials
- **[API Reference →](api/application.md)** - Detailed API documentation

## Why RestMachine?

**RestMachine makes building REST APIs easier** by handling the tricky parts of HTTP for you:

- **Easy to learn** - If you know Flask or FastAPI, you already know RestMachine. Familiar decorator syntax, intuitive patterns.

- **Smart HTTP handling** - RestMachine understands HTTP semantics and automatically handles content negotiation, conditional requests (ETags), and proper status codes. You focus on your business logic.

- **Clean, testable code** - Share resources like database connections across handlers without global state. pytest-style dependency injection makes testing straightforward.

- **Deploy anywhere** - Start developing locally with any ASGI server (Uvicorn, Hypercorn), then deploy to AWS Lambda with zero code changes. Same application code, different deployment targets.

- **Start simple, grow gradually** - Begin with just Python 3.9+, no required dependencies. Add validation (Pydantic), template rendering (Jinja2), or other features only when you need them.

- **Transparent behavior** - The state machine surfaces HTTP request details (content types, cache headers, auth status) as simple facts you can inspect and extend. No hidden magic, just clear control flow.

## Community & Support

- **GitHub**: [rfestag/restmachine-python](https://github.com/rfestag/restmachine-python)
- **Issues**: [Report bugs or request features](https://github.com/rfestag/restmachine-python/issues)
- **Security**: See [Security Policy](development/security.md)

## License

RestMachine is released under the [MIT License](about/license.md).

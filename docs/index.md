# RestMachine

<div align="center">

**A lightweight REST framework with pytest-style dependency injection and webmachine-inspired state machine**

[![Build Status](https://github.com/rfestag/restmachine-python/workflows/CI/badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Coverage](https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Code Quality](https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/rfestag/restmachine-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

## Overview

RestMachine is a modern Python REST framework that combines the simplicity of Flask-like decorators with powerful features for building robust APIs:

- **Flask-like API** - Simple decorator-based route registration
- **Dependency Injection** - pytest-style DI with automatic caching
- **State Machine** - Webmachine-inspired HTTP state machine for robust request processing
- **Content Negotiation** - Automatic content type negotiation with pluggable renderers
- **Validation** - Optional Pydantic integration for request/response validation
- **ASGI Support** - Deploy with Uvicorn, Hypercorn, or Daphne
- **AWS Lambda** - First-class support for serverless deployment
- **Lightweight** - Zero required dependencies for basic functionality

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

### Dependency Injection

pytest-style dependency injection with automatic caching:

```python
@app.dependency()
def database():
    return create_db_connection()

@app.get('/users/{user_id}')
def get_user(database, request: Request):
    user_id = request.path_params['user_id']
    return database.get_user(user_id)
```

### Request Validation

Optional Pydantic integration for type-safe validation:

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
    return {"created": validate_user.model_dump()}
```

### Content Negotiation

Automatic content negotiation with pluggable renderers:

```python
@app.content_renderer("application/json")
def json_renderer(data):
    import json
    return json.dumps(data)

@app.content_renderer("text/xml")
def xml_renderer(data):
    return f"<result>{data}</result>"
```

### Startup & Shutdown Handlers

Clean resource management with lifecycle hooks:

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

| Feature | RestMachine | Flask | FastAPI |
|---------|-------------|-------|---------|
| Dependency Injection | ✅ pytest-style | ❌ Manual | ✅ Type-based |
| State Machine | ✅ Webmachine-inspired | ❌ Middleware | ❌ Middleware |
| Content Negotiation | ✅ Automatic | ⚠️ Manual | ⚠️ Limited |
| Validation | ✅ Optional Pydantic | ❌ Manual | ✅ Pydantic |
| ASGI Support | ✅ Built-in | ⚠️ Via extension | ✅ Native |
| AWS Lambda | ✅ First-class | ⚠️ Via adapter | ⚠️ Via Mangum |
| Learning Curve | Low | Low | Medium |
| Zero Dependencies | ✅ Optional | ❌ Required | ❌ Required |

## Community & Support

- **GitHub**: [rfestag/restmachine-python](https://github.com/rfestag/restmachine-python)
- **Issues**: [Report bugs or request features](https://github.com/rfestag/restmachine-python/issues)
- **Security**: See [Security Policy](development/security.md)

## License

RestMachine is released under the [MIT License](about/license.md).

# Restmachine

[![Build Status](https://github.com/rfestag/restmachine-python/workflows/Test/badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Coverage](https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/rfestag/restmachine-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine, content negotiation support, and Pydantic-based validation.

## Features

- **Flask-like API**: Simple and intuitive decorator-based route registration
- **Dependency Injection**: pytest-style dependency injection with automatic caching
- **State Machine**: Webmachine-inspired HTTP state machine for robust request processing
- **Content Negotiation**: Automatic content type negotiation with pluggable renderers
- **Validation**: Optional Pydantic integration for request/response validation
- **ASGI Support**: Built-in ASGI adapter for deployment with Uvicorn, Hypercorn, Daphne, etc.
- **TLS/SSL Support**: ASGI TLS extension support with client certificate information for mTLS
- **Multi-Value Headers**: Full HTTP spec compliance with support for duplicate header names
- **Lightweight**: Zero required dependencies for basic functionality

## Installation

### Basic Installation

*** Note *** This has not been released yet and cannot be installed yet.
```bash
pip install restmachine
```

### With Validation Support

```bash
pip install restmachine[validation]
```

### Development Installation

```bash
git clone https://github.com/rfestag/restmachine-python.git
cd restmachine-python
pip install -e packages/restmachine[dev]
```

## Quick Start

### Basic Example

```python
from restmachine import RestApplication, Request, HTTPMethod

app = RestApplication()

@app.get('/hello')
def hello():
    return {"message": "Hello, World!"}

@app.get('/users/{user_id}')
def get_user(request: Request):
    user_id = request.path_params['user_id']
    return {"id": user_id, "name": f"User {user_id}"}

# Execute a request
request = Request(
    method=HTTPMethod.GET,
    path='/hello',
    headers={'Accept': 'application/json'}
)

response = app.execute(request)
print(response.body)  # {"message": "Hello, World!"}
```

### Dependency Injection

```python
@app.dependency()
def database():
    return {"users": {"1": "Alice", "2": "Bob"}}

@app.get('/users/{user_id}')
def get_user(database, request: Request):
    user_id = request.path_params['user_id']
    users = database['users']
    if user_id not in users:
        return Response(404, "User not found")
    return {"id": user_id, "name": users[user_id]}
```

### Validation with Pydantic

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    age: int = Field(..., ge=0, le=150)

@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.post('/users')
def create_user(validate_user: UserCreate):
    return {
        "message": "User created",
        "user": validate_user.model_dump()
    }
```

## Deployment

### Running with ASGI Servers

RestMachine includes a built-in ASGI adapter for seamless deployment with any ASGI-compatible server.

#### Using Uvicorn

```python
# app.py
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello from Uvicorn!"}

# Create ASGI application
asgi_app = ASGIAdapter(app)
```

Run with Uvicorn:
```bash
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --reload
```

#### Using Hypercorn

```python
# app.py
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello from Hypercorn!"}

# Create ASGI application
asgi_app = ASGIAdapter(app)
```

Run with Hypercorn (supports HTTP/2):
```bash
hypercorn app:asgi_app --bind 0.0.0.0:8000 --reload
```

#### Using Gunicorn with Uvicorn Workers

For production deployments with multiple workers:
```bash
gunicorn app:asgi_app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Convenience Function

You can also use the `create_asgi_app()` helper:
```python
from restmachine import RestApplication, create_asgi_app

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World!"}

# Convenience function (equivalent to ASGIAdapter(app))
asgi_app = create_asgi_app(app)
```

#### Startup and Shutdown Events

RestMachine supports ASGI lifespan events for running code on application startup and shutdown:

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

# Startup handler - runs when the application starts
@app.on_startup
async def startup():
    print("Opening database connection...")
    # Initialize database connections, load ML models, etc.

# Shutdown handler - runs when the application stops
@app.on_shutdown
async def shutdown():
    print("Closing database connection...")
    # Close connections, cleanup resources, etc.

@app.get("/")
def home():
    return {"message": "Hello World!"}

asgi_app = ASGIAdapter(app)
```

**Dependency Injection**: Startup handlers are automatically registered as session-scoped dependencies. Their return values can be injected into route handlers and shutdown handlers:

```python
@app.on_startup
def database():
    # This runs once on startup
    print("Opening database connection...")
    return create_db_connection()

@app.get("/users")
def get_users(database):  # database from startup is injected here
    return database.query("SELECT * FROM users")

@app.on_shutdown
def close_database(database):  # database from startup is injected for cleanup
    print("Closing database connection...")
    database.close()
```

Both sync and async handlers are supported:
```python
@app.on_startup
def sync_startup():
    print("This is a synchronous startup handler")

@app.on_startup
async def async_startup():
    await initialize_async_resources()
```

Multiple handlers can be registered and will run in registration order. Startup dependencies are cached across all requests (session scope).

#### TLS/SSL and Client Certificates

RestMachine supports the ASGI TLS extension, providing access to TLS connection information and client certificates for mutual TLS (mTLS):

```python
@app.get("/secure")
def secure_endpoint(request):
    # Check if connection uses TLS
    if not request.tls:
        return Response(403, "HTTPS required")

    # Access client certificate for mTLS
    if request.client_cert:
        subject = request.client_cert.get("subject", [])
        # Extract Common Name from subject
        cn = next((value for field, value in subject if field == "CN"), None)
        return {"message": f"Welcome, {cn}"}

    return {"message": "TLS connection established"}
```

**ASGI Servers**: TLS info is automatically extracted from the ASGI scope:
- `request.tls`: True for HTTPS, False for HTTP
- `request.client_cert`: Client certificate dict (if mTLS is configured)

**AWS Lambda**: API Gateway and ALB always use HTTPS, and mTLS certificates are automatically extracted from events.

### AWS Lambda Deployment

For serverless deployment on AWS Lambda (API Gateway, ALB, or Function URLs):

```bash
pip install restmachine-aws
```

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

# Startup handlers execute during Lambda cold start
@app.on_startup
def database():
    # Opens connection once per container
    return create_db_connection()

@app.get("/users")
def get_users(database):  # Injected from startup
    return database.query_users()

# Startup handlers execute automatically when adapter is created
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

**Event Types Supported**: The adapter automatically detects and handles:
- API Gateway REST API (v1) - payload format 1.0
- API Gateway HTTP API (v2) - payload format 2.0
- Application Load Balancer (ALB) Lambda target events
- Lambda Function URL events (v2 format)

**ALB Features**:
- Multi-value headers and query parameters
- mTLS verify mode (parsed certificate headers)
- mTLS passthrough mode (full PEM certificate)

**Startup Handlers**: Automatically execute during Lambda cold start (when `AwsApiGatewayAdapter` is initialized). Return values are cached and injected as session-scoped dependencies across all requests in the same container.

**Shutdown Handlers**: Executed via Lambda Extension. Shutdown handlers support dependency injection, allowing them to inject startup dependencies for cleanup:

```bash
python -m restmachine_aws create-extension
```

This creates `extensions/restmachine-shutdown` which automatically calls shutdown handlers when the Lambda container terminates. Deploy it with your function:

```python
@app.on_shutdown
def close_database(database):  # Injects database from startup handler
    database.close()  # Cleanup on container termination
```

The extension works automatically - no code changes needed!

## Code Quality

This project maintains high code quality standards with automated checks:

- **Complexity Analysis**: Radon for cyclomatic complexity and maintainability index
- **Type Safety**: MyPy with strict type checking
- **Code Style**: Ruff for linting and formatting
- **Security**: Bandit for security vulnerability scanning
- **Test Coverage**: Pytest with comprehensive test suite (592 tests)

```bash
# Run all quality checks
tox

# Run specific checks
tox -e complexity      # Code complexity analysis
tox -e type-check      # Type checking
tox -e lint            # Code linting
tox -e security        # Security scanning
```

**Current Metrics:**
- Average Complexity: A (3.59) - Excellent
- Test Coverage: 592 tests passing
- Total Lines of Code: 7,501

See [docs/CODE_QUALITY_STANDARDS.md](docs/CODE_QUALITY_STANDARDS.md) for detailed standards and [docs/COMPLEXITY_REFACTORING_PLAN.md](docs/COMPLEXITY_REFACTORING_PLAN.md) for improvement roadmap.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Examples

Check out the [examples/](examples/) directory for more comprehensive usage examples.

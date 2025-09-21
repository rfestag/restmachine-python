# Restmachine

A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine, content negotiation support, and Pydantic-based validation.

## Features

- **Flask-like API**: Simple and intuitive decorator-based route registration
- **Dependency Injection**: pytest-style dependency injection with automatic caching
- **State Machine**: Webmachine-inspired HTTP state machine for robust request processing
- **Content Negotiation**: Automatic content type negotiation with pluggable renderers
- **Validation**: Optional Pydantic integration for request/response validation
- **Lightweight**: Zero required dependencies for basic functionality

## Installation

### Basic Installation

```bash
pip install restmachine
```

### With Validation Support

```bash
pip install restmachine[validation]
```

### Development Installation

```bash
git clone https://github.com/yourusername/restmachine.git
cd restmachine
pip install -e .[dev,validation]
```

## Quick Start

### Basic Example

```python
from resmachine import RestApplication, Request, HTTPMethod

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Examples

Check out the [examples/](examples/) directory for more comprehensive usage examples.

# OpenAPI (Swagger) Generation

RestMachine automatically generates OpenAPI 3.0 specifications from your application code. This enables automatic API documentation, client SDK generation, and integration with tools like Swagger UI.

## Quick Start

Generate an OpenAPI spec from your application:

```python
from restmachine import RestApplication
from pydantic import BaseModel, EmailStr

app = RestApplication()

class UserCreate(BaseModel):
    name: str
    email: EmailStr

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

@app.on_startup
def database():
    return {"users": {}}

@app.resource_exists
def user(path_params, database):
    user_id = path_params.get('user_id')
    return database["users"].get(user_id)

@app.get('/users/{user_id}')
def get_user(user):
    """Get a user by ID."""
    return user

@app.post('/users')
def create_user(user_create: UserCreate, database):
    """Create a new user."""
    user_id = str(len(database["users"]) + 1)
    user = {"id": user_id, **user_create.model_dump()}
    database["users"][user_id] = user
    return user, 201

# Generate OpenAPI spec
openapi_json = app.generate_openapi_json(
    title="User API",
    version="1.0.0",
    description="API for managing users"
)

# Or save to file
app.save_openapi_json(
    filename="openapi.json",
    docs_dir="docs",
    title="User API",
    version="1.0.0"
)
```

## Generating Specifications

### Generate as JSON String

Get the OpenAPI spec as a JSON string:

```python
openapi_json = app.generate_openapi_json(
    title="My API",
    version="1.0.0",
    description="My awesome API"
)

# Parse if needed
import json
spec = json.loads(openapi_json)
print(spec["info"]["title"])  # "My API"
```

### Save to File

Save the spec directly to a file:

```python
file_path = app.save_openapi_json(
    filename="openapi.json",     # Output filename
    docs_dir="docs",              # Output directory
    title="My API",
    version="1.0.0",
    description="API documentation"
)

print(f"OpenAPI spec saved to: {file_path}")
# Output: OpenAPI spec saved to: docs/openapi.json
```

## Automatic Schema Detection

RestMachine automatically detects schemas from:

### Path Parameters

Path parameters are extracted from route patterns:

```python
@app.get('/users/{user_id}')
def get_user(path_params):
    return {"user_id": path_params['user_id']}
```

OpenAPI output:
```json
{
  "paths": {
    "/users/{user_id}": {
      "get": {
        "parameters": [
          {
            "name": "user_id",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ]
      }
    }
  }
}
```

### Path Parameters with Validation

Use Pydantic models for typed path parameters:

```python
from pydantic import BaseModel

class PathParams(BaseModel):
    user_id: str
    post_id: int

@app.validates
def path_params_model(path_params) -> PathParams:
    return PathParams.model_validate(path_params)

@app.get('/users/{user_id}/posts/{post_id}')
def get_post(path_params_model: PathParams):
    return {
        "user_id": path_params_model.user_id,
        "post_id": path_params_model.post_id
    }
```

OpenAPI output includes type information:
```json
{
  "parameters": [
    {
      "name": "user_id",
      "in": "path",
      "required": true,
      "schema": {"type": "string"}
    },
    {
      "name": "post_id",
      "in": "path",
      "required": true,
      "schema": {"type": "integer"}
    }
  ]
}
```

### Query Parameters

Query parameter schemas are detected from validation dependencies:

```python
from pydantic import BaseModel, Field

class ListParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: str | None = Field(default=None, description="Sort field")

@app.validates
def list_params(query_params) -> ListParams:
    return ListParams.model_validate(query_params)

@app.get('/users')
def list_users(list_params: ListParams, database):
    """List users with pagination."""
    return {"users": [], "page": list_params.page}
```

OpenAPI includes query parameter definitions:
```json
{
  "parameters": [
    {
      "name": "page",
      "in": "query",
      "required": false,
      "schema": {"type": "integer", "minimum": 1, "default": 1},
      "description": "Page number"
    },
    {
      "name": "limit",
      "in": "query",
      "required": false,
      "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
      "description": "Items per page"
    }
  ]
}
```

### Request Bodies

Request body schemas from validation dependencies:

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    email: EmailStr = Field(description="User's email address")
    age: int = Field(ge=18, le=120, description="User's age")

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

@app.post('/users')
def create_user(user_create: UserCreate):
    """Create a new user."""
    return {"created": user_create.model_dump()}, 201
```

OpenAPI includes request body schema:
```json
{
  "requestBody": {
    "required": true,
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/UserCreate"
        }
      }
    }
  },
  "components": {
    "schemas": {
      "UserCreate": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "User's full name"
          },
          "email": {
            "type": "string",
            "format": "email",
            "description": "User's email address"
          },
          "age": {
            "type": "integer",
            "minimum": 18,
            "maximum": 120,
            "description": "User's age"
          }
        },
        "required": ["name", "email", "age"]
      }
    }
  }
}
```

### Response Schemas

Document response schemas using type hints:

```python
from pydantic import BaseModel
from typing import List

class User(BaseModel):
    id: str
    name: str
    email: str

class UserList(BaseModel):
    users: List[User]
    total: int

@app.get('/users')
def list_users() -> UserList:
    """List all users."""
    return UserList(users=[], total=0)
```

## Using Docstrings

Handler docstrings become operation descriptions:

```python
@app.get('/users/{user_id}')
def get_user(user):
    """
    Get a user by ID.

    Returns user information including name, email, and creation date.
    Returns 404 if the user is not found.
    """
    return user

@app.post('/users')
def create_user(user_create: UserCreate):
    """
    Create a new user.

    Validates the user data and creates a new user account.
    Email must be unique. Returns 422 for validation errors.
    """
    return {"created": True}, 201
```

These docstrings appear in the OpenAPI spec:
```json
{
  "paths": {
    "/users/{user_id}": {
      "get": {
        "summary": "Get a user by ID",
        "description": "Returns user information including name, email, and creation date.\nReturns 404 if the user is not found."
      }
    }
  }
}
```

## Integration with Swagger UI

### Serving OpenAPI Spec

Serve the OpenAPI spec from your API:

```python
@app.get('/openapi.json')
def get_openapi_spec():
    """Return OpenAPI specification."""
    import json
    return json.loads(app.generate_openapi_json(
        title="My API",
        version="1.0.0"
    ))
```

### Using Swagger UI

Add Swagger UI to visualize your API:

```python
from restmachine import RestApplication

app = RestApplication()

# Your API routes...

@app.get('/openapi.json')
def openapi_spec():
    """OpenAPI specification endpoint."""
    import json
    return json.loads(app.generate_openapi_json(
        title="My API",
        version="1.0.0",
        description="API documentation"
    ))

@app.get('/docs')
def swagger_ui():
    """Swagger UI documentation page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Documentation</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
            SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
            });
        </script>
    </body>
    </html>
    """
```

Access Swagger UI at `http://localhost:8000/docs`.

### Using ReDoc

Alternative documentation with ReDoc:

```python
@app.get('/redoc')
def redoc_ui():
    """ReDoc documentation page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Documentation</title>
    </head>
    <body>
        <redoc spec-url="/openapi.json"></redoc>
        <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
```

## Build-Time Generation

Generate OpenAPI specs during your build process:

```python
# scripts/generate_openapi.py
from my_app import app

if __name__ == "__main__":
    app.save_openapi_json(
        filename="openapi.json",
        docs_dir="docs",
        title="My API",
        version="1.0.0",
        description="Production API documentation"
    )
    print("OpenAPI spec generated!")
```

Run during build:
```bash
python scripts/generate_openapi.py
```

## Client SDK Generation

Use the OpenAPI spec to generate client SDKs:

### Using OpenAPI Generator

```bash
# Generate TypeScript client
openapi-generator-cli generate \
    -i docs/openapi.json \
    -g typescript-axios \
    -o clients/typescript

# Generate Python client
openapi-generator-cli generate \
    -i docs/openapi.json \
    -g python \
    -o clients/python

# Generate Java client
openapi-generator-cli generate \
    -i docs/openapi.json \
    -g java \
    -o clients/java
```

### Using OpenAPI TypeScript Codegen

```bash
npx openapi-typescript-codegen \
    --input docs/openapi.json \
    --output src/api \
    --client axios
```

## Complete Example

Full API with OpenAPI documentation:

```python
from restmachine import RestApplication
from pydantic import BaseModel, EmailStr, Field
from typing import List

app = RestApplication()

# Models
class UserCreate(BaseModel):
    name: str = Field(min_length=1, description="User's name")
    email: EmailStr = Field(description="User's email")

class User(BaseModel):
    id: str
    name: str
    email: str

class UserList(BaseModel):
    users: List[User]
    total: int

# Database
@app.on_startup
def database():
    return {
        "users": {
            "1": {"id": "1", "name": "Alice", "email": "alice@example.com"}
        }
    }

# Validation
@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

@app.resource_exists
def user(path_params, database):
    user_id = path_params.get('user_id')
    return database["users"].get(user_id)

# Routes
@app.get('/users')
def list_users(database) -> UserList:
    """
    List all users.

    Returns a paginated list of all registered users.
    """
    users_list = [User(**u) for u in database["users"].values()]
    return UserList(users=users_list, total=len(users_list))

@app.get('/users/{user_id}')
def get_user(user) -> User:
    """
    Get a user by ID.

    Returns user details including name and email.
    Returns 404 if user not found.
    """
    return User(**user)

@app.post('/users')
def create_user(user_create: UserCreate, database):
    """
    Create a new user.

    Creates a new user account with the provided information.
    Email must be unique. Returns 422 for validation errors.
    """
    user_id = str(len(database["users"]) + 1)
    user = {"id": user_id, **user_create.model_dump()}
    database["users"][user_id] = user
    return User(**user), 201

@app.delete('/users/{user_id}')
def delete_user(user, path_params, database):
    """
    Delete a user.

    Permanently removes a user account.
    Returns 404 if user not found.
    """
    user_id = path_params['user_id']
    del database["users"][user_id]
    return None

# OpenAPI endpoint
@app.get('/openapi.json')
def openapi_spec():
    """OpenAPI 3.0 specification."""
    import json
    return json.loads(app.generate_openapi_json(
        title="User Management API",
        version="1.0.0",
        description="API for managing user accounts"
    ))

# Documentation UI
@app.get('/docs')
def swagger_ui():
    """Interactive API documentation."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>User API Documentation</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
            SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
            });
        </script>
    </body>
    </html>
    """

# Save spec to file (optional - useful for CI/CD)
if __name__ == "__main__":
    app.save_openapi_json(
        filename="openapi.json",
        docs_dir="docs",
        title="User Management API",
        version="1.0.0",
        description="API for managing user accounts"
    )
    print("OpenAPI spec saved to docs/openapi.json")
```

## Best Practices

### 1. Use Pydantic Models

Always use Pydantic models for comprehensive schema generation:

```python
# Good - generates complete schema
class UserCreate(BaseModel):
    name: str
    email: EmailStr

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

# Less ideal - schema inference limited
@app.post('/users')
def create_user(json_body):
    return {"created": True}
```

### 2. Add Field Descriptions

Use Field descriptions for better documentation:

```python
from pydantic import Field

class UserCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
        description="User's full name"
    )
    email: EmailStr = Field(
        description="User's email address (must be unique)"
    )
```

### 3. Write Clear Docstrings

Document your endpoints with clear docstrings:

```python
@app.get('/users/{user_id}')
def get_user(user):
    """
    Get user by ID.

    Retrieves detailed information about a specific user.

    Returns:
        User object with id, name, and email

    Errors:
        404: User not found
    """
    return user
```

### 4. Version Your API

Include version in your OpenAPI spec:

```python
app.generate_openapi_json(
    title="My API",
    version="2.1.0",  # Use semantic versioning
    description="Production API v2"
)
```

### 5. Generate at Build Time

Generate specs during deployment:

```bash
# In your CI/CD pipeline
python -c "from app import app; app.save_openapi_json()"
```

## Next Steps

- [Testing →](testing.md) - Test your API
- [Deployment →](deployment/uvicorn.md) - Deploy with documentation
- [Validation →](validation.md) - Request validation with Pydantic
- [Content Negotiation →](content-negotiation.md) - Multiple response formats

# Quick Start

This guide will walk you through creating your first RestMachine application using the CLI to scaffold a simple blog API.

## Create Your First Project

### 1. Install RestMachine

```bash
pip install restmachine restmachine-orm-sqlite uvicorn[standard]
```

This installs:

- `restmachine` - Core framework and CLI
- `restmachine-orm-sqlite` - SQLite backend for local development
- `uvicorn` - ASGI server for running your API

### 2. Create a New Project

```bash
restmachine new blog-api
cd blog-api
```

This creates a complete project structure:

```
blog-api/
├── app.py              # Main application entry point
├── config/             # Configuration files
├── db/                 # Database fixtures and migrations
├── lib/                # Shared utilities
├── models/             # Data models
├── routes/             # API route handlers
├── schemas/            # Request/response schemas
└── tests/              # Test files
```

### 3. Generate a Blog Post Resource

Use the scaffold generator to create a complete CRUD API for blog posts:

```bash
restmachine generate scaffold Post title:str content:str author:str published:bool
```

This single command generates:

- ✓ Model (`models/post.py`) with the specified fields
- ✓ CRUD routes (`routes/posts.py`) - list, create, show, update, delete
- ✓ Request/response schemas (`schemas/post_schemas.py`)
- ✓ Integration tests (`tests/integration/test_posts_api.py`)
- ✓ Fixture file (`db/fixtures/base/posts.yaml`) with example data

The generated model looks like:

```python
# models/post.py
from restmachine_orm import Model
from pydantic import Field

class Post(Model):
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    author: str
    published: bool
```

And the routes include:

```python
# routes/posts.py
from restmachine import Router

router = Router()

@router.get('/')
def list_posts():
    """List all posts."""
    posts = Post.all()
    return {"posts": [post.model_dump() for post in posts]}

@router.post('/')
def create_post(create_post_request: CreatePostRequest):
    """Create a new post."""
    post = Post.create(**create_post_request.model_dump())
    return post.model_dump(), 201

@router.get('/{id}')
def show_post(post: Post):
    """Get a specific post."""
    return post.model_dump()

@router.put('/{id}')
def update_post(post: Post, update_post_request: UpdatePostRequest):
    """Update a post."""
    post.update(**update_post_request.model_dump(exclude_unset=True))
    return post.model_dump()

@router.delete('/{id}')
def delete_post(post: Post):
    """Delete a post."""
    post.delete()
    return None, 204
```

### 4. Run Your API

Start the development server:

```bash
uvicorn app:asgi_app --reload
```

Your API is now running at `http://localhost:8000` with these endpoints:

- `GET /posts` - List all posts
- `POST /posts` - Create a new post
- `GET /posts/{id}` - Get a specific post
- `PUT /posts/{id}` - Update a post
- `DELETE /posts/{id}` - Delete a post

### 5. Test Your API

**Create a post:**

```bash
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Blog Post",
    "content": "Hello, RestMachine!",
    "author": "Alice",
    "published": true
  }'
```

**List all posts:**

```bash
curl http://localhost:8000/posts
```

**Get a specific post:**

```bash
curl http://localhost:8000/posts/{id}
```

## Add a Health Check Endpoint

Now let's add a custom endpoint using the controller generator.

### 1. Generate a Health Check Controller

```bash
restmachine generate controller health --actions status:get:/
```

This creates:

- ✓ Controller file (`routes/health.py`)
- ✓ Router mounted at `/health`
- ✓ Custom action `status` at `GET /health/`

### 2. Customize the Health Check

Edit `routes/health.py` to add a real health check:

```python
from restmachine import Router

router = Router()

@router.get('/')
def status():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "blog-api",
        "version": "1.0.0"
    }
```

### 3. Test the Health Check

```bash
curl http://localhost:8000/health/
# {"status": "healthy", "service": "blog-api", "version": "1.0.0"}
```

## Add Database Seeding

RestMachine includes a fixture system for seeding your database with test data.

### 1. Create a Fixture File

The scaffold generator already created `db/fixtures/base/posts.yaml`:

```yaml
model: Post
upsert_key: id
records:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    title: "Getting Started with RestMachine"
    content: "RestMachine makes building REST APIs easy!"
    author: "RestMachine Team"
    published: true
```

### 2. Seed the Database

```bash
restmachine seed
```

This loads all fixtures from `db/fixtures/` into your database. Now when you run:

```bash
curl http://localhost:8000/posts
```

You'll see the seeded post!

## Run the Test Suite

The scaffold generator created comprehensive integration tests:

```bash
pytest tests/integration/test_posts_api.py -v
```

You should see tests for:

- ✓ Listing posts
- ✓ Creating posts
- ✓ Getting individual posts
- ✓ Updating posts
- ✓ Deleting posts

## Deploy to Production

### Option 1: Deploy with ASGI Server

Your project already includes an ASGI adapter in `app.py`:

```python
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

Deploy with Uvicorn in production:

```bash
# Single worker
uvicorn app:asgi_app --host 0.0.0.0 --port 8000

# Multiple workers
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 4
```

Or with Gunicorn + Uvicorn workers:

```bash
gunicorn app:asgi_app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Option 2: Deploy to AWS Lambda

Install the AWS adapter:

```bash
pip install restmachine-aws
```

Create a Lambda handler:

```python
# lambda_handler.py
from restmachine_aws import AwsApiGatewayAdapter
from app import app

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

Package and deploy:

```bash
# Package dependencies
pip install --target ./package restmachine restmachine-aws restmachine-orm-sqlite
cd package && zip -r ../lambda_function.zip . && cd ..
zip lambda_function.zip lambda_handler.py app.py -r models/ routes/ schemas/

# Deploy to Lambda
aws lambda create-function \
  --function-name blog-api \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 30
```

See the [AWS Lambda Deployment Guide](../guide/deployment-lambda.md) for detailed instructions.

## CLI Command Reference

Here are the key CLI commands you'll use:

### Project Scaffolding

```bash
# Create a new project
restmachine new <project-name>

# Create minimal project (no examples)
restmachine new <project-name> --minimal
```

### Code Generation

```bash
# Generate complete CRUD resource (model + controller + schemas + tests)
restmachine generate scaffold <Name> field:type field:type ...

# Generate just a model
restmachine generate model <Name> field:type field:type ...

# Generate controller with specific actions
restmachine generate controller <name> --actions list,create,show

# Generate controller with custom action
restmachine generate controller <name> --actions activate:post:/{id}/activate
```

### Available Field Types

- `str` - String field
- `int` - Integer field
- `float` - Float field
- `bool` - Boolean field
- `datetime` - DateTime field (auto-imports datetime)
- `uuid` - UUID field (auto-imports uuid, uses as primary key)

Example:

```bash
restmachine generate scaffold User \
  name:str \
  email:str \
  age:int \
  is_active:bool \
  created_at:datetime
```

### Database Operations

```bash
# Seed database with fixtures
restmachine seed

# Seed specific fixture file
restmachine seed --fixture posts.yaml

# Dry run (show what would be loaded)
restmachine seed --dry-run

# Clear tables before seeding
restmachine seed --clear
```

### Backend Management

```bash
# List available backends
restmachine list backends

# Create project with specific backend
restmachine new myapp --backend sqlite

# Generate model with backend override
restmachine generate model User name:str --backend aws
```

## Next Steps

Now that you have a working blog API:

- **[Models & ORM →](../../restmachine-orm/docs/api/models.md)** - Learn about database operations and queries
- **[Dependency Injection →](../guide/dependency-injection.md)** - Master DI patterns for cleaner code
- **[Request Validation →](../guide/validation.md)** - Add Pydantic validation to your schemas
- **[Testing Guide →](../guide/testing.md)** - Write comprehensive tests for your API
- **[Database Seeding →](../guides/database-seeding.md)** - Advanced fixture loading strategies
- **[OpenAPI Documentation →](../guide/openapi.md)** - Auto-generate API documentation

## Common Issues

??? question "Command not found: restmachine"
    Make sure RestMachine is installed in your current environment:
    ```bash
    pip install restmachine
    ```
    If using a virtual environment, ensure it's activated.

??? question "No backends available"
    Install a backend package:
    ```bash
    pip install restmachine-orm-sqlite  # For SQLite
    pip install restmachine-orm-dynamodb  # For DynamoDB
    ```

??? question "Generated code has import errors"
    Make sure you've installed the required backend:
    ```bash
    pip install restmachine-orm-sqlite
    ```

??? question "Seed command fails"
    Ensure your models are properly registered in `models/__init__.py` and your backend is initialized in `app.py`.

??? question "Tests are failing"
    Make sure the test database is set up. The generated tests use an in-memory backend by default. Check `tests/conftest.py` for configuration.

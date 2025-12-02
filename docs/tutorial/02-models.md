# Creating Your First Model

In this section, you'll create a `Post` model and generate a complete CRUD API for it.

## Generate a Scaffold

RestMachine's scaffold generator creates everything you need for a complete resource:

```bash
restmachine generate scaffold Post title:str content:str author:str published:bool
```

This single command generates:

- ✅ `models/post.py` - Database model
- ✅ `routes/posts.py` - CRUD endpoints
- ✅ `schemas/post_schemas.py` - Request/response validation
- ✅ `db/fixtures/posts.yaml` - Seed data
- ✅ `tests/integration/test_posts_api.py` - Integration tests

## Understanding the Generated Model

Open `models/post.py`:

```python
from datetime import datetime
from typing import ClassVar
from restmachine_orm import Model, Field
from models import backend


class Post(Model):
    """Post model for blog-api."""

    model_backend: ClassVar = backend
    table_name: ClassVar[str] = "posts"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    author: str
    published: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

Key points:

- **Model** - Base class from `restmachine_orm`
- **Fields** - Type-annotated attributes become database columns
- **Backend** - Shared database connection
- **Automatic timestamps** - `created_at` and `updated_at` are auto-managed

## Exploring the Routes

Open `routes/posts.py` to see the generated endpoints:

```python
from restmachine import Router
from models.post import Post
from schemas.post_schemas import (
    CreatePostRequest,
    UpdatePostRequest,
    ListPostsResponse,
)

router = Router()

# Resource loader - loads post from path parameters
@router.resource_exists
@router.get('/{post_id}')
def post(path_params) -> Post:
    """Load post by ID."""
    post_id = path_params.get('post_id')
    return Post.find_by(id=post_id)

@router.get('/')
def list_posts(query_params) -> ListPostsResponse:
    """List all posts with pagination."""
    limit = int(query_params.get('limit', 50))
    cursor = query_params.get('cursor')

    results, next_cursor = Post.where().cursor(cursor).limit(limit).paginate()

    return ListPostsResponse(
        items=results,
        cursor=next_cursor if next_cursor else None,
    )

@router.post('/')
def create_post(json_body) -> tuple:
    """Create a new post."""
    data = CreatePostRequest.model_validate(json_body)
    post = Post.create(**data.model_dump())
    return post.model_dump(), 201

@router.patch('/{post_id}')
def update_post(post: Post, json_body) -> Post:
    """Update an existing post."""
    data = UpdatePostRequest.model_validate(json_body)
    updates = data.model_dump(exclude_unset=True)

    updated = post.model_copy(updates=updates)
    updated.save()
    return updated

@router.delete('/{post_id}')
def delete_post(post: Post):
    """Delete a post."""
    post.delete()
    return None
```

Notice:
- **Resource loader** (`post` function) - Automatically loads the post and returns 404 if not found
- **Dependency injection** - The `post` parameter in `update_post` is injected automatically
- **Validation** - Pydantic schemas validate all inputs

## Understanding the Schemas

Open `schemas/post_schemas.py`:

```python
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from models.post import Post


class CreatePostRequest(BaseModel):
    """Schema for creating a post."""
    title: str
    content: str
    author: str
    published: bool = False


class UpdatePostRequest(BaseModel):
    """Schema for updating a post."""
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published: Optional[bool] = None


class ListPostsResponse(BaseModel):
    """Schema for listing posts."""
    items: List[Post]
    cursor: Optional[str] = None
```

Schemas provide:
- Type validation
- Automatic API documentation
- Clear contracts between client and server

## Mount the Router

The scaffold generator automatically updated `app.py`:

```python
from restmachine import RestMachine
from routes import posts

app = RestMachine()

# Mount the posts router
app.mount('/posts', posts.router)
```

## Test Your API

Restart the server (if needed):

```bash
python main.py
```

Create a post:

```bash
curl -X POST http://localhost:3000/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "Hello, RestMachine!",
    "author": "Alice",
    "published": true
  }'
```

List posts:

```bash
curl http://localhost:3000/posts
```

Get a specific post:

```bash
curl http://localhost:3000/posts/{id}
```

## Seed Data

The generator created fixture data in `db/fixtures/posts.yaml`:

```yaml
model: Post
records:
  - id: post_1
    title: "Getting Started with RestMachine"
    content: "RestMachine makes building APIs easy..."
    author: "Admin"
    published: true
```

Load the fixtures:

```bash
restmachine seed
```

Now when you list posts, you'll see the seeded data!

## Next Steps

You've created a complete CRUD API with just one command! Next, we'll add relationships between models.

[Next: Model Relationships →](03-relationships.md)

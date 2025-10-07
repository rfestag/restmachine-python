# Router

::: restmachine.Router
    options:
      show_root_heading: true
      heading_level: 2
      show_source: false
      members:
        - __init__
        - get
        - post
        - put
        - patch
        - delete
        - head
        - options
        - route

## Overview

`Router` allows you to organize routes into reusable, composable units. Routers can be mounted onto applications or other routers, enabling modular API design.

## Why Use Routers?

- **Modularity** - Organize routes by feature or domain
- **Reusability** - Share routers across applications
- **Composition** - Build complex APIs from simple components
- **Separation of Concerns** - Keep related routes together

## Basic Usage

```python
from restmachine import RestApplication, Router

app = RestApplication()
users_router = Router()

@users_router.get('/users')
def list_users():
    return {"users": [...]}

@users_router.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']
    return {"id": user_id}

@users_router.post('/users')
def create_user(request):
    return {"created": True}, 201

# Mount router at /api/v1
app.mount('/api/v1', users_router)

# Routes become:
# GET  /api/v1/users
# GET  /api/v1/users/{user_id}
# POST /api/v1/users
```

## Route Registration

Routers support the same HTTP method decorators as `RestApplication`:

```python
router = Router()

@router.get('/items')
def list_items():
    return {"items": []}

@router.post('/items')
def create_item(request):
    return {"created": True}

@router.put('/items/{item_id}')
def update_item(request):
    return {"updated": True}

@router.delete('/items/{item_id}')
def delete_item(request):
    return {"deleted": True}

@router.patch('/items/{item_id}')
def patch_item(request):
    return {"patched": True}

@router.head('/items')
def head_items():
    return None  # HEAD returns only headers

@router.options('/items')
def options_items():
    return {"methods": ["GET", "POST"]}
```

## Nested Routers

Mount routers onto other routers:

```python
from restmachine import Router

# API v1 router
api_v1 = Router()

# Users sub-router
users = Router()
@users.get('/users')
def list_users():
    return {"users": []}

# Posts sub-router
posts = Router()
@posts.get('/posts')
def list_posts():
    return {"posts": []}

# Mount sub-routers
api_v1.mount('/api/v1', users)
api_v1.mount('/api/v1', posts)

# Mount to application
app.mount('/', api_v1)

# Routes become:
# GET /api/v1/users
# GET /api/v1/posts
```

## Modular API Design

Organize by feature:

```python
# users.py
from restmachine import Router

users_router = Router()

@users_router.get('/users')
def list_users():
    return {"users": []}

@users_router.post('/users')
def create_user(request):
    return {"created": True}
```

```python
# posts.py
from restmachine import Router

posts_router = Router()

@posts_router.get('/posts')
def list_posts():
    return {"posts": []}

@posts_router.post('/posts')
def create_post(request):
    return {"created": True}
```

```python
# app.py
from restmachine import RestApplication
from users import users_router
from posts import posts_router

app = RestApplication()

app.mount('/api', users_router)
app.mount('/api', posts_router)

# Routes:
# GET  /api/users
# POST /api/users
# GET  /api/posts
# POST /api/posts
```

## Versioned APIs

Create multiple API versions:

```python
from restmachine import Router

# API v1
api_v1 = Router()

@api_v1.get('/users')
def list_users_v1():
    return {"users": [], "version": "1.0"}

# API v2
api_v2 = Router()

@api_v2.get('/users')
def list_users_v2():
    return {"users": [], "version": "2.0", "new_field": "value"}

# Mount both versions
app.mount('/api/v1', api_v1)
app.mount('/api/v2', api_v2)

# Routes:
# GET /api/v1/users -> v1 response
# GET /api/v2/users -> v2 response
```

## Path Parameters

Path parameters work the same as in applications:

```python
router = Router()

@router.get('/users/{user_id}')
def get_user(request):
    user_id = request.path_params['user_id']
    return {"id": user_id}

@router.get('/users/{user_id}/posts/{post_id}')
def get_post(request):
    user_id = request.path_params['user_id']
    post_id = request.path_params['post_id']
    return {"user_id": user_id, "post_id": post_id}
```

## Dependency Injection

Routers don't have their own dependency registry - dependencies are resolved from the parent application:

```python
from restmachine import RestApplication, Router

app = RestApplication()

@app.dependency()
def database():
    return create_db_connection()

router = Router()

@router.get('/users')
def list_users(database):
    # database is injected from app
    return {"users": database.query("SELECT * FROM users")}

app.mount('/api', router)
```

## Static File Routers

Use specialized routers for static files:

```python
from restmachine import RestApplication
from restmachine_web import StaticRouter

app = RestApplication()

# Static files router
static = StaticRouter(serve="./public")
app.mount('/static', static)

# GET /static/css/style.css -> serves ./public/css/style.css
```

See [StaticRouter API](../restmachine-web/api/static-router.md) for details.

## Comparison: Router vs Application

| Feature | Router | RestApplication |
|---------|--------|-----------------|
| Route registration | ✅ Yes | ✅ Yes |
| Dependency injection | ❌ No (uses parent) | ✅ Yes |
| Content negotiation | ❌ No (uses parent) | ✅ Yes |
| Lifecycle handlers | ❌ No | ✅ Yes |
| Error handlers | ❌ No | ✅ Yes |
| Mounting | ✅ Yes | ✅ Yes |
| Execution | ❌ No | ✅ Yes |

**Use Router when:**
- Organizing routes by feature
- Building reusable route collections
- Creating modular APIs

**Use RestApplication when:**
- Creating the main application
- Need dependency injection
- Need lifecycle handlers
- Need custom error handling

## See Also

- [Application API](application.md) - Main application class
- [Basic Application Guide](../guide/basic-application.md) - Core concepts
- [StaticRouter](../restmachine-web/api/static-router.md) - Serve static files

# Core Concepts

RestMachine combines dependency injection with a webmachine-inspired state machine to create a powerful, declarative framework for building REST APIs. This guide explains these core concepts and how they work together.

## Dependency Injection

RestMachine features pytest-style dependency injection that makes your code clean, testable, and maintainable. Dependencies are automatically resolved and cached during request processing.

### How It Works

Dependencies are functions that provide values to your route handlers. RestMachine automatically matches parameter names in your handlers with dependency function names:

```python
from restmachine import RestApplication

app = RestApplication()

@app.dependency()
def database():
    return {"users": [], "posts": []}

@app.get('/users')
def list_users(database):
    # database is injected automatically
    return {"users": database["users"]}
```

### Dependency Scopes

RestMachine supports two scopes:

**Request-scoped** (default): Created once per request and cached for that request:

```python
@app.dependency()
def get_timestamp():
    from datetime import datetime
    print("Creating timestamp...")
    return datetime.now()

@app.get('/example')
def example_handler(get_timestamp):
    # get_timestamp is only created once per request
    return {"timestamp": str(get_timestamp)}
```

**Session-scoped**: Created once when the application starts and shared across all requests:

```python
@app.on_startup
def database():
    print("Opening database connection...")
    # In real app, create connection pool
    return create_db_pool()

@app.on_shutdown
def close_database(database):
    print("Closing database connection...")
    database.close()

@app.get('/users')
def list_users(database):
    # Same database instance used across all requests
    return {"users": database.query_all()}
```

### Nested Dependencies

Dependencies can depend on other dependencies, creating a dependency graph:

```python
@app.dependency()
def config():
    return {"db_host": "localhost", "db_port": 5432}

@app.dependency()
def database_url(config):
    return f"postgresql://{config['db_host']}:{config['db_port']}/mydb"

@app.dependency()
def database(database_url):
    print(f"Connecting to {database_url}")
    return create_connection(database_url)

@app.get('/status')
def status(database):
    # config → database_url → database are all resolved automatically
    return {"connected": database.is_connected()}
```

## The State Machine

RestMachine uses a webmachine-inspired state machine to process HTTP requests. Instead of running middleware in sequence, the state machine makes decisions at specific points to determine the appropriate HTTP response.

### Why a State Machine?

The state machine approach provides several benefits:

- **Standards-compliant**: Automatically follows HTTP/1.1 specifications
- **Correct status codes**: Returns appropriate status codes based on request conditions
- **Declarative**: Use decorators to define API behavior
- **Built-in features**: Conditional requests, content negotiation, and more

### How Dependencies Define API Facts

The key insight of RestMachine is that **dependencies define facts about your API**, and the state machine uses these facts to automatically generate correct HTTP responses.

For example:

```python
@app.resource_exists
def user(path_params, database):
    """Define the fact: does this user exist?"""
    user_id = path_params['user_id']
    return database.get_user(user_id)  # None = doesn't exist

@app.get('/users/{user_id}')
def get_user(user):
    # If user is None, the state machine already returned 404
    # If we reach here, user definitely exists
    return user
```

In this example:
- The `@app.resource_exists` decorator defines a dependency that answers: "Does the resource exist?"
- If it returns `None`, the state machine automatically returns `404 Not Found`
- If it returns a value, that value is cached and available to your handler
- Your handler only runs when the resource exists

### State Machine Flow

The state machine processes requests through decision points:

```
Request → B13: Route exists? → B12: Service available? → ...
  → G7: Resource exists? → G3-G6: Conditional requests
  → C3-C4: Content negotiation → Execute handler → Response
```

Each decision point can be customized with decorators:

| Decorator | Decision | Effect |
|-----------|----------|--------|
| `@app.resource_exists` | Does the resource exist? | Return 404 if None |
| `@app.authorized` | Is request authorized? | Return 401 if False |
| `@app.forbidden` | Is access forbidden? | Return 403 if True |
| `@app.validates` | Is request valid? | Return 400/422 on validation error |
| `@app.etag` | What's the ETag? | Enable conditional requests |
| `@app.last_modified` | When was it modified? | Enable conditional requests |

### Dependencies as Facts

Each decorator defines a "fact" that the state machine uses:

```python
# Fact: User must be authenticated
@app.authorized
def check_auth(request_headers):
    token = request_headers.get('authorization')
    return validate_token(token)  # False = not authorized

# Fact: User must have admin role
@app.forbidden
def check_admin(request_headers):
    user = get_user_from_token(request_headers.get('authorization'))
    return user.role != 'admin'  # True = forbidden

# Fact: Resource has an ETag
@app.etag
def user_etag(user):
    import hashlib
    return f'"{hashlib.md5(str(user).encode()).hexdigest()}"'

@app.delete('/users/{user_id}')
def delete_user(user, database):
    # State machine ensures:
    # 1. User is authenticated (401 if not)
    # 2. User is admin (403 if not)
    # 3. Resource exists (404 if not)
    # 4. ETag matches (412 if not, for If-Match header)
    # Only then does this handler run
    database.delete(user['id'])
    return None  # 204 No Content
```

### Automatic HTTP Responses

The state machine automatically handles:

**Conditional Requests:**
```python
@app.etag
def user_etag(user):
    return calculate_etag(user)

@app.last_modified
def user_last_modified(user):
    return user['updated_at']

@app.get('/users/{user_id}')
def get_user(user):
    # If client sends If-None-Match with matching ETag → 304 Not Modified
    # If client sends If-Modified-Since and not modified → 304 Not Modified
    # Otherwise → 200 OK with user data
    return user
```

**Content Negotiation:**
```python
@app.content_renderer("application/json")
def render_json(data):
    import json
    return json.dumps(data)

@app.content_renderer("application/xml")
def render_xml(data):
    return f"<data>{data}</data>"

@app.get('/data')
def get_data():
    return {"message": "Hello"}
    # Client sends Accept: application/json → JSON response
    # Client sends Accept: application/xml → XML response
    # Client sends Accept: text/html → 406 Not Acceptable
```

**Resource Existence:**
```python
@app.resource_exists
def article(path_params, database):
    return database.get_article(path_params['article_id'])

@app.get('/articles/{article_id}')
def get_article(article):
    # article is None → 404 already returned
    # article exists → 200 with data
    return article

@app.delete('/articles/{article_id}')
def delete_article(article, database):
    # Same resource_exists dependency
    # Automatic 404 if article doesn't exist
    database.delete(article['id'])
    return None
```

## Combining Concepts

The power of RestMachine comes from combining dependency injection with the state machine:

```python
from restmachine import RestApplication
from pydantic import BaseModel
from datetime import datetime
import hashlib

app = RestApplication()

# Session-scoped dependency
@app.on_startup
def database():
    return create_db_connection()

# Request-scoped dependencies
@app.dependency()
def current_user(request_headers, database):
    token = request_headers.get('authorization', '').replace('Bearer ', '')
    return database.get_user_by_token(token)

# State machine facts
@app.resource_exists
def article(path_params, database):
    """Fact: Does the article exist?"""
    return database.get_article(path_params['article_id'])

@app.authorized
def is_authenticated(current_user):
    """Fact: Is user authenticated?"""
    return current_user is not None

@app.forbidden
def can_edit_article(current_user, article):
    """Fact: Can user edit this article?"""
    # Forbidden if user is not the author
    return current_user['id'] != article['author_id']

@app.etag
def article_etag(article):
    """Fact: What's the article's ETag?"""
    content = f"{article['id']}{article['updated_at']}"
    return f'"{hashlib.md5(content.encode()).hexdigest()}"'

@app.last_modified
def article_last_modified(article):
    """Fact: When was article last modified?"""
    return datetime.fromisoformat(article['updated_at'])

# Validation
class ArticleUpdate(BaseModel):
    title: str
    content: str

@app.validates
def article_update(json_body) -> ArticleUpdate:
    """Fact: Is the request valid?"""
    return ArticleUpdate.model_validate(json_body)

# Route handler
@app.put('/articles/{article_id}')
def update_article(article, article_update: ArticleUpdate, database):
    """
    The state machine ensures:
    1. Article exists (404 if not)
    2. User is authenticated (401 if not)
    3. User can edit article (403 if not)
    4. Request is valid (400/422 if not)
    5. ETag matches (412 if client sent If-Match and it doesn't match)
    6. Article was modified (304 if client sent If-None-Match and it matches)

    If all checks pass, this handler runs:
    """
    article['title'] = article_update.title
    article['content'] = article_update.content
    article['updated_at'] = datetime.now().isoformat()
    database.update_article(article)
    return article
```

In this example:
- Dependencies define facts about the API (auth, permissions, validation)
- The state machine uses these facts to make decisions
- HTTP responses are automatically generated based on these decisions
- Your handler only runs when all conditions are met

## Key Principles

1. **Dependencies define facts** about your API (existence, authorization, validation)
2. **The state machine makes decisions** based on these facts
3. **HTTP responses are automatic** - you focus on business logic
4. **Decorators are declarative** - state what your API needs, not how to check
5. **Everything is cacheable** - dependencies run once per request

## Next Steps

- [Usage →](usage.md) - Learn how to use decorators in practice
- [Advanced State Machine →](../advanced/state-machine.md) - Deep dive into the state machine
- [Lifecycle Management →](../advanced/lifecycle.md) - Startup and shutdown handlers

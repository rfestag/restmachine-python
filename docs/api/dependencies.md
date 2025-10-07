# Dependencies

::: restmachine.DependencyScope
    options:
      show_root_heading: true
      heading_level: 2
      show_source: false

## Overview

The dependency injection system in RestMachine allows you to share resources across handlers automatically. Dependencies are defined using the `@app.dependency()` decorator and resolved based on parameter names.

## Quick Start

```python
from restmachine import RestApplication

app = RestApplication()

@app.dependency()
def database():
    """Create database connection."""
    return create_db_connection()

@app.get('/users')
def list_users(database):
    """database is automatically injected."""
    return {"users": database.query("SELECT * FROM users")}
```

## Dependency Scopes

### REQUEST Scope (Default)

Dependencies are created once per request and cached:

```python
@app.dependency()  # Default scope is REQUEST
def database():
    print("Creating database connection")
    return create_db_connection()

@app.get('/users')
def list_users(database):
    return {"users": database.query("SELECT * FROM users")}

@app.get('/posts')
def list_posts(database):
    # Same database instance as list_users (within same request)
    return {"posts": database.query("SELECT * FROM posts")}
```

### SESSION Scope

Dependencies are created once per application lifetime:

```python
from restmachine import DependencyScope

@app.dependency(scope=DependencyScope.SESSION)
def config():
    """Load config once at startup."""
    print("Loading configuration...")
    return load_app_config()

@app.get('/info')
def get_info(config):
    # Config is loaded once and reused across all requests
    return {"version": config['version']}
```

## Dependency Chain

Dependencies can depend on other dependencies:

```python
@app.dependency()
def database():
    return create_db_connection()

@app.dependency()
def user_repository(database):
    """Depends on database."""
    return UserRepository(database)

@app.get('/users/{user_id}')
def get_user(user_id: str, user_repository):
    """user_repository (and database) are automatically injected."""
    user = user_repository.get(user_id)
    return user or ({"error": "Not found"}, 404)
```

## See Also

- [Dependency Injection Guide](../guide/dependency-injection.md) - Complete guide
- [Application API](application.md) - Main application class
- [Lifecycle Handlers](../advanced/lifecycle.md) - Startup dependencies

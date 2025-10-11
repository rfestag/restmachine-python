# Startup & Shutdown Handlers

RestMachine provides lifecycle hooks to manage application startup and shutdown events. These handlers are useful for initializing resources (database connections, caches, etc.) and cleaning them up when the application stops.

## Overview

Lifecycle handlers allow you to:

- **Initialize resources** once when the application starts
- **Share initialized resources** across all requests via dependency injection
- **Clean up resources** when the application shuts down
- **Execute async or sync** initialization/cleanup code

## Startup Handlers

Startup handlers run when the application starts and can return values that are automatically registered as dependencies.

### Basic Usage

```python
from restmachine import RestApplication

app = RestApplication()

@app.on_startup
def database():
    print("Connecting to database...")
    return create_database_connection()

@app.get("/users")
def get_users(database):  # database from startup is injected
    return database.query("SELECT * FROM users")
```

### Key Features

**Automatic Dependency Injection**
- Startup handler return values are automatically registered as dependencies
- Available to all route handlers by parameter name
- Session-scoped (cached for the lifetime of the application)

**Sync and Async Support**
```python
@app.on_startup
async def async_database():
    conn = await asyncpg.connect(DATABASE_URL)
    return conn

@app.on_startup
def sync_cache():
    return redis.Redis(host='localhost', port=6379)
```

### Multiple Startup Handlers

You can register multiple startup handlers, and all their return values will be available as dependencies:

```python
@app.on_startup
def database():
    return create_database_connection()

@app.on_startup
def cache():
    return create_redis_connection()

@app.on_startup
def config():
    return load_configuration()

@app.get("/status")
def status(database, cache, config):
    return {
        "db": database.is_connected(),
        "cache": cache.ping(),
        "config": config.version
    }
```

### Startup Handlers with Dependencies

Startup handlers can depend on other startup handlers that were registered earlier:

```python
@app.on_startup
def config():
    return {
        "db_url": "postgresql://localhost/mydb",
        "cache_url": "redis://localhost:6379"
    }

@app.on_startup
def database(config):  # Depends on config startup handler
    return connect_database(config["db_url"])

@app.on_startup
def cache(config):  # Also depends on config
    return connect_redis(config["cache_url"])
```

## Shutdown Handlers

Shutdown handlers run when the application stops, allowing you to clean up resources properly.

### Basic Usage

```python
@app.on_shutdown
def cleanup():
    print("Closing connections...")
    # Close database, cache, etc.
```

### Cleanup with Dependencies

Shutdown handlers can access startup handler dependencies to properly close resources:

```python
@app.on_startup
def database():
    return create_database_connection()

@app.on_shutdown
def close_database(database):  # Receives database from startup
    print("Closing database connection...")
    database.close()
```

### Multiple Shutdown Handlers

```python
@app.on_shutdown
def close_database(database):
    database.close()

@app.on_shutdown
def close_cache(cache):
    cache.disconnect()

@app.on_shutdown
async def cleanup_temp_files():
    await remove_temp_files()
```

### Shutdown Order

Shutdown handlers run in the order they were registered. If you need specific cleanup order, register handlers accordingly:

```python
# This runs first
@app.on_shutdown
def close_sessions():
    session_manager.close_all()

# This runs second
@app.on_shutdown
def close_database():
    database.disconnect()
```

## Complete Example

Here's a complete example with database connection pooling and proper cleanup:

```python
from restmachine import RestApplication
import psycopg2.pool

app = RestApplication()

@app.on_startup
def database_pool():
    """Create a connection pool at startup."""
    print("Creating database connection pool...")
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=5,
        maxconn=20,
        host='localhost',
        database='mydb',
        user='user',
        password='password'
    )
    return pool

@app.dependency()
def database_connection(database_pool):
    """Get a connection from the pool for each request."""
    conn = database_pool.getconn()
    try:
        yield conn
    finally:
        database_pool.putconn(conn)

@app.on_shutdown
def close_database_pool(database_pool):
    """Close all connections when shutting down."""
    print("Closing database connection pool...")
    database_pool.closeall()

@app.get("/users/{user_id}")
def get_user(user_id: int, database_connection):
    cursor = database_connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return {"id": user[0], "name": user[1]} if user else None
```

## ASGI Lifecycle Integration

When running with an ASGI server, lifecycle handlers are integrated with ASGI lifespan events:

### Uvicorn

```python
# app.py
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.on_startup
async def startup():
    print("Application starting...")
    # Initialize resources

@app.on_shutdown
async def shutdown():
    print("Application shutting down...")
    # Cleanup resources

# Run with:
# uvicorn app:asgi_app
asgi_app = ASGIAdapter(app)
```

### Hypercorn

```python
# Works the same with Hypercorn
# hypercorn app:asgi_app
```

### AWS Lambda

In Lambda, startup handlers run once per container initialization (cold start), and shutdown handlers run when the Lambda execution environment is terminated:

```python
from restmachine import RestApplication

app = RestApplication()

@app.on_startup
def init_resources():
    # Runs once per Lambda container initialization
    return expensive_resource()

@app.get("/process")
def process(init_resources):
    # Reuses the same resource across warm invocations
    return init_resources.process()

# Lambda handler - use restmachine-aws package for Lambda support
# from restmachine_aws import LambdaAdapter
# handler = LambdaAdapter(app)
```

## Best Practices

### 1. Use Startup Handlers for Expensive Initialization

```python
@app.on_startup
def ml_model():
    """Load ML model once at startup, not per request."""
    return load_large_model()

@app.post("/predict")
def predict(data: dict, ml_model):
    return {"prediction": ml_model.predict(data)}
```

### 2. Always Clean Up Resources

```python
@app.on_startup
def file_handle():
    return open('data.txt', 'r')

@app.on_shutdown
def close_file(file_handle):
    file_handle.close()  # Always close files
```

### 3. Handle Errors Gracefully

```python
@app.on_startup
def database():
    try:
        return connect_to_database()
    except ConnectionError as e:
        print(f"Failed to connect to database: {e}")
        return None  # Return None or a mock

@app.get("/users")
def get_users(database):
    if database is None:
        return {"error": "Database unavailable"}, 503
    return database.query_users()
```

### 4. Use Async for I/O Operations

```python
@app.on_startup
async def async_resources():
    """Use async for I/O-bound initialization."""
    async with aiohttp.ClientSession() as session:
        config = await fetch_remote_config(session)
    return config
```

## Testing with Lifecycle Handlers

When testing, startup and shutdown handlers are automatically invoked:

```python
from restmachine import Request, HTTPMethod

def test_with_lifecycle():
    app = RestApplication()

    @app.on_startup
    def test_db():
        return {"users": []}

    @app.get("/users")
    def get_users(test_db):
        return test_db["users"]

    # Startup handler runs automatically
    request = Request(method=HTTPMethod.GET, path="/users")
    response = app.execute(request)
    assert response.status_code == 200
```

## Comparison with Other Frameworks

| Feature | RestMachine | FastAPI | Flask |
|---------|-------------|---------|-------|
| Startup handlers | `@app.on_startup` | `@app.on_event("startup")` | `@app.before_first_request` |
| Shutdown handlers | `@app.on_shutdown` | `@app.on_event("shutdown")` | `@app.teardown_appcontext` |
| Auto dependency injection | ✓ | ✗ | ✗ |
| Async support | ✓ | ✓ | Limited |
| ASGI lifespan | ✓ | ✓ | ✗ |

## Next Steps

- Learn about [Performance Optimization](performance.md) with caching strategies
- Explore [Lambda Extensions](../restmachine-aws/guides/lambda-extensions.md) for AWS-specific lifecycle hooks
- Read about [Dependency Injection](../guide/dependency-injection.md) for advanced patterns

# Performance Optimization

RestMachine is designed for high performance with minimal overhead. This guide covers optimization techniques, caching strategies, and best practices for building fast APIs.

## Dependency Caching

### Understanding Dependency Scope

RestMachine caches dependencies per request by default:

```python
from restmachine import RestApplication

app = RestApplication()

@app.dependency()
def expensive_computation():
    """Cached per request."""
    import time
    print("Computing...")
    time.sleep(0.1)  # Simulate expensive operation
    return {"result": "value"}

@app.dependency()
def uses_computation(expensive_computation):
    """Reuses cached computation."""
    return {"data": expensive_computation["result"]}

@app.get('/api/data')
def get_data(expensive_computation, uses_computation):
    """Both dependencies use same cached computation."""
    # expensive_computation only runs once per request
    return {
        "direct": expensive_computation,
        "indirect": uses_computation
    }
```

### Session-Scoped Dependencies

Use session scope for expensive resources:

```python
@app.on_startup
def database_pool():
    """Created once at startup, reused across all requests."""
    import psycopg2.pool
    return psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=20,
        host='localhost',
        database='mydb'
    )

@app.on_shutdown
def close_pool(database_pool):
    """Clean up on shutdown."""
    database_pool.closeall()

@app.dependency()
def database_connection(database_pool):
    """Get connection from pool (per request)."""
    conn = database_pool.getconn()
    try:
        yield conn
    finally:
        database_pool.putconn(conn)

@app.get('/users')
def list_users(database_connection):
    """Use pooled connection."""
    with database_connection.cursor() as cur:
        cur.execute("SELECT * FROM users")
        return {"users": cur.fetchall()}
```

## State Machine Optimization

### Bypass State Machine for Simple Routes

For high-performance endpoints, consider bypassing the state machine:

```python
# Standard route (with state machine)
@app.get('/api/data')
def get_data():
    return {"message": "Hello"}

# Direct route (bypass state machine for maximum performance)
@app.get('/api/fast', bypass_state_machine=True)
def fast_endpoint():
    """Ultra-fast endpoint without state machine overhead."""
    return {"message": "Fast!"}, 200, {'Content-Type': 'application/json'}
```

### Optimize State Machine Decorators

Minimize state machine processing by using specific decorators:

```python
from restmachine.decorators import (
    skip_content_negotiation,
    skip_auth_check,
    cache_response
)

@app.get('/api/public-data')
@skip_content_negotiation  # Only return JSON
@skip_auth_check  # No authentication needed
@cache_response(max_age=3600)  # Cache for 1 hour
def public_data():
    """Optimized public endpoint."""
    return {"data": [...]}
```

## ASGI Server Tuning

### Uvicorn Configuration

Optimize Uvicorn for production:

```bash
# Production configuration
uvicorn app:asgi_app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools \
  --log-level warning \
  --no-access-log \
  --limit-concurrency 1000 \
  --backlog 2048
```

Python configuration:

```python
# uvicorn_config.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
loop = "uvloop"
http = "httptools"
log_level = "warning"
access_log = False
limit_concurrency = 1000
backlog = 2048
```

Run with config:

```bash
uvicorn app:asgi_app --config uvicorn_config.py
```

### Hypercorn Configuration

Optimize Hypercorn for high performance:

```toml
# hypercorn_config.toml
bind = ["0.0.0.0:8000"]
workers = 4
worker_class = "uvloop"
keep_alive = 5
graceful_timeout = 10

# Performance tuning
backlog = 2048
h11_max_incomplete_size = 16384

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "warning"
```

## Connection Pooling

### Database Connection Pool

Use connection pooling for databases:

```python
from contextlib import contextmanager
import psycopg2.pool

@app.on_startup
def db_pool():
    """Create connection pool."""
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=5,
        maxconn=20,
        host='localhost',
        database='mydb',
        user='user',
        password='password',
        connect_timeout=3
    )

@contextmanager
def get_db_connection(db_pool):
    """Get connection from pool with context manager."""
    conn = db_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)

@app.get('/users')
def list_users(db_pool):
    """Use pooled connection efficiently."""
    with get_db_connection(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users LIMIT 100")
            return {"users": cur.fetchall()}
```

### HTTP Client Pooling

Reuse HTTP connections:

```python
import httpx

@app.on_startup
def http_client():
    """Create persistent HTTP client."""
    return httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100
        )
    )

@app.on_shutdown
async def close_http_client(http_client):
    """Close HTTP client."""
    await http_client.aclose()

@app.get('/api/external')
async def call_external_api(http_client):
    """Use pooled HTTP client."""
    response = await http_client.get('https://api.example.com/data')
    return response.json()
```

## Caching Strategies

### In-Memory Caching

Implement simple in-memory cache:

```python
from functools import lru_cache
from datetime import datetime, timedelta

# LRU cache for expensive computations
@lru_cache(maxsize=1000)
def expensive_function(param: str):
    """Cached with LRU eviction."""
    # Expensive computation
    return {"result": param.upper()}

# Time-based cache
CACHE = {}
CACHE_TTL = timedelta(minutes=5)

@app.dependency()
def get_cached_data():
    """Data cached with TTL."""
    now = datetime.now()

    # Check cache
    if 'data' in CACHE:
        cached_at, value = CACHE['data']
        if now - cached_at < CACHE_TTL:
            return value

    # Fetch fresh data
    data = fetch_expensive_data()
    CACHE['data'] = (now, data)

    return data

@app.get('/api/cached')
def cached_endpoint(get_cached_data):
    return get_cached_data
```

### Redis Caching

Use Redis for distributed caching:

```python
import redis
import json
from datetime import timedelta

@app.on_startup
def redis_client():
    """Create Redis connection pool."""
    return redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=20
    )

@app.dependency()
def cache(redis_client):
    """Cache operations."""
    class Cache:
        def __init__(self, client):
            self.client = client

        def get(self, key: str):
            value = self.client.get(key)
            return json.loads(value) if value else None

        def set(self, key: str, value, ttl: int = 300):
            self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )

        def delete(self, key: str):
            self.client.delete(key)

    return Cache(redis_client)

@app.get('/users/{user_id}')
def get_user(request, cache, database):
    """Get user with caching."""
    user_id = request.path_params['user_id']
    cache_key = f"user:{user_id}"

    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Fetch from database
    user = database.get_user(user_id)

    # Cache for 5 minutes
    cache.set(cache_key, user, ttl=300)

    return user
```

## Response Compression

### Enable Compression in ASGI Server

Configure compression in Uvicorn/Hypercorn:

```python
# With middleware
from starlette.middleware.gzip import GZipMiddleware

app = RestApplication()

# Add compression middleware to ASGI app
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
asgi_app = GZipMiddleware(asgi_app, minimum_size=1000)
```

Or configure in reverse proxy (Nginx):

```nginx
# nginx.conf
http {
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/json
        application/javascript
        application/xml+rss;
}
```

## Async Operations

### Async Dependencies

Use async for I/O-bound operations:

```python
import asyncio
import httpx

@app.on_startup
async def async_http_client():
    """Async HTTP client."""
    return httpx.AsyncClient(timeout=10.0)

@app.dependency()
async def fetch_user_data(async_http_client, request):
    """Async dependency."""
    user_id = request.path_params['user_id']

    # Parallel requests
    user_response, posts_response = await asyncio.gather(
        async_http_client.get(f'https://api.example.com/users/{user_id}'),
        async_http_client.get(f'https://api.example.com/users/{user_id}/posts')
    )

    return {
        "user": user_response.json(),
        "posts": posts_response.json()
    }

@app.get('/users/{user_id}/profile')
async def user_profile(fetch_user_data):
    """Async endpoint."""
    return fetch_user_data
```

### Background Tasks

Offload work to background:

```python
from concurrent.futures import ThreadPoolExecutor
import threading

@app.on_startup
def executor():
    """Thread pool for background tasks."""
    return ThreadPoolExecutor(max_workers=10)

@app.dependency()
def background_tasks(executor):
    """Background task runner."""
    tasks = []

    def add_task(func, *args, **kwargs):
        future = executor.submit(func, *args, **kwargs)
        tasks.append(future)

    def wait_all():
        for future in tasks:
            future.result()

    return add_task, wait_all

@app.post('/users')
def create_user(validate_user, database, background_tasks):
    """Create user with background email."""
    add_task, wait_all = background_tasks

    # Create user
    user = database.create_user(validate_user.model_dump())

    # Send email in background
    add_task(send_welcome_email, user['email'])

    # Don't wait for background tasks
    return user, 201
```

## Query Optimization

### Efficient Database Queries

Optimize database access:

```python
@app.get('/users')
def list_users(request, database):
    """Optimized user listing."""
    # Use query parameters for filtering
    limit = min(int(request.query_params.get('limit', '20')), 100)
    offset = int(request.query_params.get('offset', '0'))

    # Efficient query with LIMIT/OFFSET
    with database.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, email, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset)
        )

        users = cur.fetchall()

    return {
        "users": users,
        "limit": limit,
        "offset": offset
    }
```

### N+1 Query Prevention

Avoid N+1 queries with eager loading:

```python
@app.get('/posts')
def list_posts(database):
    """List posts with authors (avoid N+1)."""
    with database.cursor() as cur:
        # Single query with JOIN
        cur.execute(
            """
            SELECT
                p.id, p.title, p.content,
                u.id as author_id, u.name as author_name
            FROM posts p
            JOIN users u ON p.author_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 20
            """
        )

        rows = cur.fetchall()

        posts = [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "author": {
                    "id": row[3],
                    "name": row[4]
                }
            }
            for row in rows
        ]

    return {"posts": posts}
```

## Response Optimization

### Pagination

Implement efficient pagination:

```python
from typing import Optional

class PaginationParams:
    def __init__(self, page: int = 1, per_page: int = 20):
        self.page = max(1, page)
        self.per_page = min(per_page, 100)  # Max 100 items
        self.offset = (self.page - 1) * self.per_page

@app.dependency()
def pagination(request) -> PaginationParams:
    """Parse pagination parameters."""
    page = int(request.query_params.get('page', '1'))
    per_page = int(request.query_params.get('per_page', '20'))
    return PaginationParams(page, per_page)

@app.get('/users')
def list_users(pagination: PaginationParams, database):
    """Paginated user list."""
    with database.cursor() as cur:
        # Get total count
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]

        # Get page of results
        cur.execute(
            "SELECT * FROM users LIMIT %s OFFSET %s",
            (pagination.per_page, pagination.offset)
        )
        users = cur.fetchall()

    return {
        "users": users,
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": total,
            "pages": (total + pagination.per_page - 1) // pagination.per_page
        }
    }
```

### Field Selection

Allow clients to select fields:

```python
@app.get('/users/{user_id}')
def get_user(request, database):
    """Get user with field selection."""
    user_id = request.path_params['user_id']

    # Parse fields parameter
    fields_param = request.query_params.get('fields', '')
    allowed_fields = {'id', 'name', 'email', 'created_at', 'bio'}

    if fields_param:
        selected_fields = set(fields_param.split(',')) & allowed_fields
    else:
        selected_fields = allowed_fields

    # Build query
    field_list = ', '.join(selected_fields)

    with database.cursor() as cur:
        cur.execute(
            f"SELECT {field_list} FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()

    if not row:
        from restmachine import Response
        return Response(404, '{"error": "Not found"}')

    # Build response with selected fields
    user = dict(zip(selected_fields, row))

    return user
```

## Monitoring and Profiling

### Request Timing

Track request performance:

```python
import time
import logging

logger = logging.getLogger(__name__)

@app.dependency()
def request_timer(request):
    """Track request timing."""
    start_time = time.time()

    yield

    duration = time.time() - start_time

    # Log slow requests
    if duration > 1.0:
        logger.warning(
            f"Slow request: {request.method} {request.path} took {duration:.2f}s"
        )

    # Add timing header
    return {'X-Response-Time': f"{duration:.3f}"}

@app.get('/api/data')
def get_data(request_timer):
    """Endpoint with timing."""
    # Simulate work
    time.sleep(0.1)

    return {"message": "Hello"}, 200, request_timer
```

### Memory Profiling

Monitor memory usage:

```python
import tracemalloc
import logging

logger = logging.getLogger(__name__)

@app.on_startup
def start_memory_profiling():
    """Start memory profiling."""
    tracemalloc.start()

@app.dependency()
def memory_monitor():
    """Monitor memory for request."""
    snapshot1 = tracemalloc.take_snapshot()

    yield

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    # Log top memory allocations
    for stat in top_stats[:3]:
        logger.debug(f"Memory: {stat}")

@app.get('/api/data')
def get_data(memory_monitor):
    """Endpoint with memory monitoring."""
    data = fetch_large_dataset()
    return data
```

## Complete Example

Here's a complete high-performance application:

```python
from restmachine import RestApplication, Request
from functools import lru_cache
import psycopg2.pool
import redis
import json
from datetime import datetime

app = RestApplication()

# Connection pools
@app.on_startup
def db_pool():
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=5, maxconn=20,
        host='localhost', database='mydb'
    )

@app.on_startup
def redis_client():
    return redis.Redis(
        host='localhost', decode_responses=True,
        max_connections=20
    )

# Caching dependency
@app.dependency()
def cache(redis_client):
    class Cache:
        def get(self, key):
            val = redis_client.get(key)
            return json.loads(val) if val else None

        def set(self, key, value, ttl=300):
            redis_client.setex(key, ttl, json.dumps(value))

    return Cache()

# Optimized user endpoint
@app.get('/users/{user_id}')
def get_user(request, db_pool, cache):
    """High-performance user endpoint."""
    user_id = request.path_params['user_id']
    cache_key = f"user:{user_id}"

    # Try cache
    user = cache.get(cache_key)
    if user:
        return user, 200, {'X-Cache': 'HIT'}

    # Database query
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email FROM users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()

            if not row:
                from restmachine import Response
                return Response(404, '{"error": "Not found"}')

            user = {"id": row[0], "name": row[1], "email": row[2]}

            # Cache result
            cache.set(cache_key, user, ttl=300)

            return user, 200, {'X-Cache': 'MISS'}
    finally:
        db_pool.putconn(conn)

# ASGI with optimizations
from restmachine import ASGIAdapter
from starlette.middleware.gzip import GZipMiddleware

asgi_app = ASGIAdapter(app)
asgi_app = GZipMiddleware(asgi_app, minimum_size=1000)
```

## Best Practices

### 1. Use Connection Pooling

Always pool database and HTTP connections:

```python
# Good: Connection pool
@app.on_startup
def db_pool():
    return create_pool(min=5, max=20)

# Bad: New connection per request
@app.dependency()
def database():
    return create_connection()  # Don't do this!
```

### 2. Cache Expensive Operations

Cache computations and queries:

```python
# Good: Cached
@lru_cache(maxsize=1000)
def expensive_computation(param):
    return result

# Bad: Recompute every time
def expensive_computation(param):
    return result  # No caching
```

### 3. Use Async for I/O

Use async for I/O-bound operations:

```python
# Good: Async I/O
@app.get('/data')
async def get_data(http_client):
    return await http_client.get('https://api.example.com')

# Less optimal: Sync I/O (blocks worker)
@app.get('/data')
def get_data():
    return requests.get('https://api.example.com')
```

### 4. Implement Pagination

Always paginate large result sets:

```python
# Good: Paginated
@app.get('/users')
def list_users(pagination):
    return db.query().limit(pagination.per_page).offset(pagination.offset)

# Bad: Return all results
@app.get('/users')
def list_users():
    return db.query().all()  # Could be millions!
```

### 5. Monitor Performance

Track and log performance metrics:

```python
import time

@app.dependency()
def perf_monitor(request):
    start = time.time()
    yield
    duration = time.time() - start
    if duration > 1.0:
        logger.warning(f"Slow: {request.path} {duration:.2f}s")
```

## Next Steps

- [Lifecycle →](lifecycle.md) - Manage application lifecycle
- [State Machine →](state-machine.md) - Understand request flow
- [Testing →](../guide/testing.md) - Performance testing
- [Deployment →](../guide/deployment/uvicorn.md) - Production deployment

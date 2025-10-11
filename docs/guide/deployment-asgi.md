# ASGI Deployment

RestMachine applications can be deployed using any ASGI server. This guide covers generic ASGI deployment with examples using popular servers.

## What is ASGI?

ASGI (Asynchronous Server Gateway Interface) is the Python standard for async web servers and applications. It enables:

- High-performance async request handling
- HTTP/2 and HTTP/3 support (server-dependent)
- Long-polling and server-sent events

## Creating an ASGI Application

Convert your RestMachine application to ASGI:

```python
from restmachine import RestApplication, ASGIAdapter

# Create your application
app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello, World!"}

# Create ASGI adapter
asgi_app = ASGIAdapter(app)
```

Save this as `app.py` and you can run it with any ASGI server.

## Choosing an ASGI Server

Popular ASGI servers include:

| Server | HTTP/1.1 | HTTP/2 | HTTP/3 | Auto-reload | Best For |
|--------|----------|--------|--------|-------------|----------|
| **Uvicorn** | ✓ | Limited | ✗ | ✓ | Development, production HTTP/1.1 |
| **Hypercorn** | ✓ | ✓ | ✓ | ✗ | HTTP/2, HTTP/3 support |
| **Daphne** | ✓ | ✗ | ✗ | ✗ | Django Channels integration |

## Uvicorn

Uvicorn is a lightning-fast ASGI server built on uvloop and httptools.

### Installation

```bash
pip install uvicorn
# Or with standard extras for production
pip install 'uvicorn[standard]'
```

### Basic Usage

```bash
# Run application
uvicorn app:asgi_app

# Development mode with auto-reload
uvicorn app:asgi_app --reload

# Production with multiple workers
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 4
```

### Configuration

```bash
# Custom host and port
uvicorn app:asgi_app --host 0.0.0.0 --port 8000

# With SSL
uvicorn app:asgi_app --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem

# Logging
uvicorn app:asgi_app --log-level info

# Connection limits
uvicorn app:asgi_app --limit-concurrency 1000
```

### Programmatic Usage

```python
import uvicorn
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello!"}

asgi_app = ASGIAdapter(app)

if __name__ == "__main__":
    uvicorn.run(
        asgi_app,
        host="0.0.0.0",
        port=8000,
        workers=4
    )
```

## Hypercorn

Hypercorn is an ASGI server with full HTTP/2 and HTTP/3 support.

### Installation

```bash
pip install hypercorn
# For HTTP/3 support
pip install 'hypercorn[h3]'
```

### Basic Usage

```bash
# Run application
hypercorn app:asgi_app

# Custom host and port
hypercorn app:asgi_app --bind 0.0.0.0:8000

# Multiple workers
hypercorn app:asgi_app --workers 4

# HTTP/2 with SSL
hypercorn app:asgi_app \
  --bind 0.0.0.0:8443 \
  --keyfile ./key.pem \
  --certfile ./cert.pem
```

### Configuration

```bash
# Logging
hypercorn app:asgi_app --log-level info --access-log -

# Keep-alive timeout
hypercorn app:asgi_app --keep-alive-timeout 5

# Graceful shutdown
hypercorn app:asgi_app --graceful-timeout 30
```

### Programmatic Usage

```python
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello!"}

asgi_app = ASGIAdapter(app)

if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    asyncio.run(serve(asgi_app, config))
```

## Production Deployment

### Using Systemd

Create a systemd service file:

**/etc/systemd/system/myapp.service:**

```ini
[Unit]
Description=My RestMachine Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/myapp
Environment="PATH=/var/www/myapp/venv/bin"
ExecStart=/var/www/myapp/venv/bin/uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 4

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable myapp
sudo systemctl start myapp
sudo systemctl status myapp
```

### Behind a Reverse Proxy

Use Nginx as a reverse proxy:

**/etc/nginx/sites-available/myapp:**

```nginx
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Docker Deployment

Create a Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app:asgi_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Build and run:

```bash
docker build -t myapp .
docker run -p 8000:8000 myapp
```

### Environment Configuration

Use environment variables for configuration:

```python
import os
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

# Configuration from environment
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WORKERS = int(os.getenv("WORKERS", "4"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

@app.get("/")
def home():
    return {"message": "Hello!"}

asgi_app = ASGIAdapter(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        asgi_app,
        host=HOST,
        port=PORT,
        workers=WORKERS,
        log_level=LOG_LEVEL
    )
```

## Lifecycle Management

RestMachine supports startup and shutdown handlers for resource management:

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.on_startup
def database():
    """Initialize database connection pool at startup."""
    print("Opening database connection...")
    return create_connection_pool()

@app.on_shutdown
def close_database(database):
    """Close database connections at shutdown."""
    print("Closing database connection...")
    database.close()

@app.get("/users")
def list_users(database):
    # Database connection is reused across requests
    return {"users": database.query_all()}

asgi_app = ASGIAdapter(app)
```

ASGI servers automatically call startup handlers when the server starts and shutdown handlers when it stops.

## Health Checks

Implement health check endpoints for monitoring:

```python
@app.get("/health")
def health_check():
    """Liveness probe."""
    return {"status": "healthy"}

@app.get("/ready")
def readiness_check(database):
    """Readiness probe."""
    if not database.is_connected():
        return {"status": "not ready"}, 503
    return {"status": "ready"}
```

Use these endpoints with orchestrators like Kubernetes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Performance Tips

### Worker Count

Set workers based on CPU cores:

```bash
# Common formula: (2 x CPU cores) + 1
# For 4 cores:
uvicorn app:asgi_app --workers 9
```

Or dynamically:

```python
import multiprocessing

workers = (multiprocessing.cpu_count() * 2) + 1
```

### Connection Limits

Configure connection limits for high-traffic applications:

```bash
uvicorn app:asgi_app --limit-concurrency 1000 --limit-max-requests 10000
```

### Logging

Control logging verbosity:

```bash
# Production - less verbose
uvicorn app:asgi_app --log-level warning --no-access-log

# Development - more verbose
uvicorn app:asgi_app --log-level debug
```

## Complete Example

Here's a complete production-ready example:

```python
# app.py
import os
import logging
from restmachine import RestApplication, ASGIAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create application
app = RestApplication()

@app.on_startup
def database():
    """Initialize database connection pool."""
    logger.info("Connecting to database...")
    # Return database connection pool
    # Note: create_db_pool() is a placeholder - implement based on your database
    return create_db_pool()

@app.on_shutdown
def close_database(database):
    """Close database connections."""
    logger.info("Closing database connections...")
    database.close()

@app.get("/")
def home():
    """Root endpoint."""
    return {"status": "ok", "version": "1.0.0"}

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/users")
def list_users(database):
    """List all users."""
    users = database.query_all_users()
    return {"users": users}

# Create ASGI app
asgi_app = ASGIAdapter(app)

# For running directly
if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "4"))
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run(
        asgi_app,
        host=host,
        port=port,
        workers=workers,
        log_level=log_level
    )
```

Run in development:

```bash
python app.py
```

Run in production:

```bash
export WORKERS=8
export LOG_LEVEL=warning
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 8
```

## Next Steps

- [Lambda Deployment →](deployment-lambda.md) - Deploy to AWS Lambda
- [Lifecycle Management →](../advanced/lifecycle.md) - Advanced startup/shutdown patterns
- [Performance Optimization →](../advanced/performance.md) - Tuning tips
- [Testing →](testing.md) - Test your ASGI application

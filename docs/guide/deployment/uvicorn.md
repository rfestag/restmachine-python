# Deploying with Uvicorn

[Uvicorn](https://www.uvicorn.org/) is a lightning-fast ASGI server built on uvloop and httptools, providing excellent performance for Python web applications. RestMachine provides seamless integration with Uvicorn for both development and production deployments.

## Installation

Install RestMachine with Uvicorn support:

```bash
pip install 'restmachine[uvicorn]'
```

Or install Uvicorn separately:

```bash
pip install restmachine uvicorn
```

For production, use uvicorn with standard extras:

```bash
pip install 'uvicorn[standard]'
```

## Quick Start

### Using the serve() Function

The simplest way to run your application with Uvicorn:

```python
# app.py
from restmachine import RestApplication, serve

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

if __name__ == "__main__":
    serve(app, server="uvicorn", host="0.0.0.0", port=8000)
```

Run the application:

```bash
python app.py
```

### Using the UvicornDriver

For more control, use the `UvicornDriver` class directly:

```python
# app.py
from restmachine import RestApplication
from restmachine.servers import UvicornDriver

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

if __name__ == "__main__":
    driver = UvicornDriver(app, host="0.0.0.0", port=8000)
    driver.run()
```

### Using ASGI Adapter

For maximum flexibility, create an ASGI app and run with Uvicorn directly:

```python
# app.py
from restmachine import RestApplication
from restmachine.adapters import create_asgi_app

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

# Create ASGI application
asgi_app = create_asgi_app(app)
```

Run with Uvicorn from the command line:

```bash
uvicorn app:asgi_app --host 0.0.0.0 --port 8000
```

## Configuration Options

### Basic Configuration

```python
from restmachine import RestApplication, serve

app = RestApplication()

serve(
    app,
    server="uvicorn",
    host="0.0.0.0",           # Bind to all interfaces
    port=8000,                # Port to listen on
    log_level="info",         # Logging level
)
```

### Development Configuration

Enable auto-reload for development:

```python
serve(
    app,
    server="uvicorn",
    reload=True,              # Auto-reload on code changes
    log_level="debug",        # Verbose logging
    host="127.0.0.1",         # Local only
    port=8000
)
```

Or from command line:

```bash
uvicorn app:asgi_app --reload --log-level debug
```

### Production Configuration

Use multiple workers for production:

```python
serve(
    app,
    server="uvicorn",
    host="0.0.0.0",
    port=8000,
    workers=4,                # Number of worker processes
    log_level="warning",      # Less verbose logging
)
```

Or from command line:

```bash
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 4
```

## SSL/HTTPS Support

### Development SSL

For development with self-signed certificates:

```python
serve(
    app,
    server="uvicorn",
    host="0.0.0.0",
    port=8443,
    ssl_keyfile="./certs/key.pem",
    ssl_certfile="./certs/cert.pem",
)
```

Command line:

```bash
uvicorn app:asgi_app --ssl-keyfile ./certs/key.pem --ssl-certfile ./certs/cert.pem
```

### Production SSL

For production, use proper SSL certificates (Let's Encrypt, etc.):

```python
serve(
    app,
    server="uvicorn",
    host="0.0.0.0",
    port=443,
    workers=4,
    ssl_keyfile="/etc/letsencrypt/live/example.com/privkey.pem",
    ssl_certfile="/etc/letsencrypt/live/example.com/fullchain.pem",
)
```

## Advanced Features

### HTTP/2 Support

Enable HTTP/2 (requires SSL):

```python
from restmachine.servers import UvicornDriver

driver = UvicornDriver(
    app,
    host="0.0.0.0",
    port=8443,
    http_version="http2"
)

driver.run(
    ssl_keyfile="./certs/key.pem",
    ssl_certfile="./certs/cert.pem",
)
```

### Custom Logging

Configure custom logging:

```python
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

serve(
    app,
    server="uvicorn",
    log_config=None,  # Use Python's logging config
    log_level="info"
)
```

### Access Logs

Enable or disable access logs:

```python
serve(
    app,
    server="uvicorn",
    access_log=True,  # Enable access logs (default)
)
```

Command line:

```bash
# Disable access logs for better performance
uvicorn app:asgi_app --no-access-log
```

## Production Deployment

### Systemd Service

Create a systemd service file for production deployment:

**`/etc/systemd/system/myapp.service`:**

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

Enable and start the service:

```bash
sudo systemctl enable myapp
sudo systemctl start myapp
sudo systemctl status myapp
```

### Behind Nginx

Use Nginx as a reverse proxy:

**`/etc/nginx/sites-available/myapp`:**

```nginx
upstream restmachine {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name example.com www.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://restmachine;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/myapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
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

# Run with Uvicorn
CMD ["uvicorn", "app:asgi_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**requirements.txt:**

```
restmachine[uvicorn]
```

Build and run:

```bash
docker build -t myapp .
docker run -p 8000:8000 myapp
```

### Docker Compose

**`docker-compose.yml`:**

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=info
      - WORKERS=4
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

## Complete Example

Here's a complete production-ready example:

```python
# app.py
import os
from restmachine import RestApplication
from restmachine.adapters import create_asgi_app
import logging

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
    return create_db_pool()

@app.on_shutdown
def close_database(database):
    """Close database connections."""
    logger.info("Closing database connections...")
    database.close()

@app.get("/")
def home():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/api/users/{user_id}")
def get_user(user_id: int, database):
    """Get a user by ID."""
    user = database.get_user(user_id)
    if not user:
        return {"error": "User not found"}, 404
    return user

# Create ASGI app
asgi_app = create_asgi_app(app)

# For running directly
if __name__ == "__main__":
    from restmachine.servers import serve_uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "4"))
    log_level = os.getenv("LOG_LEVEL", "info")

    serve_uvicorn(
        app,
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
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

## Performance Tuning

### Worker Count

Set workers based on CPU cores:

```python
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1  # Common formula

serve(app, server="uvicorn", workers=workers)
```

Or from environment:

```bash
export WORKERS=$(nproc --all)
uvicorn app:asgi_app --workers $WORKERS
```

### Connection Limits

Configure connection limits:

```bash
uvicorn app:asgi_app \
  --limit-concurrency 1000 \
  --limit-max-requests 10000 \
  --timeout-keep-alive 5
```

### Event Loop

Use uvloop for better performance (installed with `uvicorn[standard]`):

```bash
uvicorn app:asgi_app --loop uvloop
```

## Monitoring and Health Checks

### Health Check Endpoint

Add a health check endpoint:

```python
@app.get("/health")
def health_check():
    """Kubernetes/Docker health check."""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/ready")
def readiness_check(database):
    """Readiness check - verify dependencies."""
    if not database.is_connected():
        return {"status": "not ready"}, 503
    return {"status": "ready"}
```

### Kubernetes Probes

**Liveness probe:**

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
```

**Readiness probe:**

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Worker Timeout

Increase timeout for long-running requests:

```bash
uvicorn app:asgi_app --timeout-keep-alive 30
```

### Memory Issues

Monitor memory usage and adjust workers:

```bash
# Check memory usage
ps aux | grep uvicorn

# Reduce workers if memory is high
uvicorn app:asgi_app --workers 2
```

### Debugging

Enable debug logging:

```bash
uvicorn app:asgi_app --log-level debug --reload
```

## Best Practices

### 1. Use Environment Variables for Configuration

```python
import os

host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "8000"))
workers = int(os.getenv("WORKERS", "4"))
```

### 2. Implement Graceful Shutdown

```python
@app.on_shutdown
async def shutdown():
    """Clean up resources on shutdown."""
    await cleanup_tasks()
    logger.info("Application shut down gracefully")
```

### 3. Use Process Managers

Don't run Uvicorn directly in production. Use:
- Systemd
- Supervisor
- Docker
- Kubernetes

### 4. Monitor Application Health

Implement health checks and monitor:
- Request latency
- Error rates
- Memory usage
- CPU usage

### 5. Secure Your Deployment

- Use HTTPS in production
- Keep dependencies updated
- Limit worker count to available resources
- Use a reverse proxy (Nginx, Traefik)

## Comparison with Other Servers

| Feature | Uvicorn | Hypercorn | Gunicorn |
|---------|---------|-----------|----------|
| ASGI Support | ✓ | ✓ | ✗ (WSGI only) |
| HTTP/2 | Limited | ✓ | ✗ |
| HTTP/3 | ✗ | ✓ | ✗ |
| WebSockets | ✓ | ✓ | ✗ |
| Performance | Excellent | Very Good | Good |
| Production Ready | ✓ | ✓ | ✓ |
| Auto-reload | ✓ | ✗ | ✗ |

## Next Steps

- Learn about [Hypercorn deployment](hypercorn.md) for HTTP/2 and HTTP/3 support
- Explore [AWS Lambda deployment](aws-lambda.md) for serverless applications
- Read about [Performance Optimization](../../advanced/performance.md) for tuning tips

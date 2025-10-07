# Deploying with Hypercorn

[Hypercorn](https://pgjones.gitlab.io/hypercorn/) is a modern ASGI server with full support for HTTP/1.1, HTTP/2, and HTTP/3. It's ideal for applications that need the latest HTTP protocol features and excellent WebSocket support.

## Installation

Install RestMachine with Hypercorn support:

```bash
pip install 'restmachine[hypercorn]'
```

Or install Hypercorn separately:

```bash
pip install restmachine hypercorn
```

For HTTP/3 support, install additional dependencies:

```bash
pip install 'hypercorn[h3]'
```

## Quick Start

### Using the serve() Function

The simplest way to run your application with Hypercorn:

```python
# app.py
from restmachine import RestApplication, serve

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

if __name__ == "__main__":
    serve(app, server="hypercorn", host="0.0.0.0", port=8000)
```

Run the application:

```bash
python app.py
```

### Using the HypercornDriver

For more control, use the `HypercornDriver` class directly:

```python
# app.py
from restmachine import RestApplication
from restmachine.servers import HypercornDriver

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

if __name__ == "__main__":
    driver = HypercornDriver(app, host="0.0.0.0", port=8000)
    driver.run()
```

### Using ASGI Adapter

Create an ASGI app and run with Hypercorn from the command line:

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

Run with Hypercorn:

```bash
hypercorn app:asgi_app --bind 0.0.0.0:8000
```

## HTTP Protocol Support

### HTTP/1.1 (Default)

Standard HTTP/1.1 support:

```python
serve(
    app,
    server="hypercorn",
    host="0.0.0.0",
    port=8000,
    http_version="http1"  # Default
)
```

Command line:

```bash
hypercorn app:asgi_app --bind 0.0.0.0:8000
```

### HTTP/2

Enable HTTP/2 for better performance (requires SSL in browsers):

```python
from restmachine.servers import HypercornDriver

driver = HypercornDriver(
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

Command line:

```bash
hypercorn app:asgi_app \
  --bind 0.0.0.0:8443 \
  --keyfile ./certs/key.pem \
  --certfile ./certs/cert.pem
```

### HTTP/3 (QUIC)

Enable HTTP/3 for the latest protocol (requires SSL):

```python
from restmachine.servers import HypercornDriver

driver = HypercornDriver(
    app,
    host="0.0.0.0",
    port=8443,
    http_version="http3"  # HTTP/3 requires SSL
)

driver.run(
    ssl_keyfile="./certs/key.pem",
    ssl_certfile="./certs/cert.pem",
)
```

Command line with HTTP/3:

```bash
# Requires hypercorn[h3]
hypercorn app:asgi_app \
  --bind 0.0.0.0:8443 \
  --quic-bind 0.0.0.0:8443 \
  --keyfile ./certs/key.pem \
  --certfile ./certs/cert.pem
```

## Configuration Options

### Basic Configuration

```python
from restmachine import RestApplication, serve

app = RestApplication()

serve(
    app,
    server="hypercorn",
    host="0.0.0.0",
    port=8000,
    log_level="info",
)
```

### Production Configuration

```python
serve(
    app,
    server="hypercorn",
    host="0.0.0.0",
    port=8000,
    workers=4,              # Number of worker processes
    log_level="warning",    # Less verbose logging
    access_log=True,        # Enable access logging
)
```

Command line:

```bash
hypercorn app:asgi_app \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --log-level warning \
  --access-log -
```

### Worker Configuration

Set workers based on CPU cores:

```python
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1

serve(
    app,
    server="hypercorn",
    workers=workers
)
```

## SSL/HTTPS Configuration

### Development SSL

Self-signed certificates for development:

```python
serve(
    app,
    server="hypercorn",
    host="0.0.0.0",
    port=8443,
    http_version="http2",
    ssl_keyfile="./certs/key.pem",
    ssl_certfile="./certs/cert.pem",
)
```

Generate self-signed certificates:

```bash
# Generate private key
openssl genrsa -out key.pem 2048

# Generate self-signed certificate
openssl req -new -x509 -key key.pem -out cert.pem -days 365
```

### Production SSL

Use Let's Encrypt or other CA certificates:

```python
serve(
    app,
    server="hypercorn",
    host="0.0.0.0",
    port=443,
    http_version="http2",
    workers=4,
    ssl_keyfile="/etc/letsencrypt/live/example.com/privkey.pem",
    ssl_certfile="/etc/letsencrypt/live/example.com/fullchain.pem",
)
```

Command line:

```bash
hypercorn app:asgi_app \
  --bind 0.0.0.0:443 \
  --workers 4 \
  --keyfile /etc/letsencrypt/live/example.com/privkey.pem \
  --certfile /etc/letsencrypt/live/example.com/fullchain.pem
```

## Advanced Features

### Access Logging

Configure access log format:

```python
serve(
    app,
    server="hypercorn",
    access_log=True,  # Enable access logging
)
```

Command line with custom access log:

```bash
hypercorn app:asgi_app --access-log access.log --access-logformat "%(h)s %(r)s %(s)s %(b)s"
```

### Keep-Alive Settings

Configure keep-alive timeouts:

```bash
hypercorn app:asgi_app --keep-alive-timeout 5
```

### Graceful Shutdown

Configure graceful shutdown timeout:

```bash
hypercorn app:asgi_app --graceful-timeout 30
```

## Production Deployment

### Systemd Service

Create a systemd service for Hypercorn:

**`/etc/systemd/system/myapp.service`:**

```ini
[Unit]
Description=My RestMachine Application (Hypercorn)
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/myapp
Environment="PATH=/var/www/myapp/venv/bin"
ExecStart=/var/www/myapp/venv/bin/hypercorn app:asgi_app --bind 0.0.0.0:8000 --workers 4

[Install]
WantedBy=multi-user.target
```

With HTTP/2:

```ini
ExecStart=/var/www/myapp/venv/bin/hypercorn app:asgi_app \
    --bind 0.0.0.0:8443 \
    --workers 4 \
    --keyfile /etc/ssl/private/key.pem \
    --certfile /etc/ssl/certs/cert.pem
```

Enable and start:

```bash
sudo systemctl enable myapp
sudo systemctl start myapp
sudo systemctl status myapp
```

### Behind Nginx

Use Nginx as a reverse proxy with HTTP/2:

**`/etc/nginx/sites-available/myapp`:**

```nginx
upstream hypercorn {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://hypercorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Docker Deployment

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose ports (HTTP/2 and HTTP/3)
EXPOSE 8443 8443/udp

# Run with Hypercorn
CMD ["hypercorn", "app:asgi_app", "--bind", "0.0.0.0:8443", "--workers", "4"]
```

**requirements.txt:**

```
restmachine[hypercorn]
```

For HTTP/3:

```
restmachine
hypercorn[h3]
```

Build and run:

```bash
docker build -t myapp .
docker run -p 8443:8443 myapp
```

### Docker Compose with HTTP/2

**`docker-compose.yml`:**

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8443:8443"
    volumes:
      - ./certs:/certs:ro
    environment:
      - HYPERCORN_KEYFILE=/certs/key.pem
      - HYPERCORN_CERTFILE=/certs/cert.pem
    command: >
      hypercorn app:asgi_app
      --bind 0.0.0.0:8443
      --workers 4
      --keyfile /certs/key.pem
      --certfile /certs/cert.pem
    restart: unless-stopped
```

## Complete Example

Production-ready application with HTTP/2:

```python
# app.py
import os
import logging
from restmachine import RestApplication
from restmachine.adapters import create_asgi_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create application
app = RestApplication()

@app.on_startup
async def database():
    """Initialize async database connection."""
    logger.info("Connecting to database...")
    import asyncpg
    pool = await asyncpg.create_pool(
        host="localhost",
        database="myapp",
        user="appuser",
        password=os.getenv("DB_PASSWORD"),
        min_size=10,
        max_size=20
    )
    return pool

@app.on_shutdown
async def close_database(database):
    """Close database connections."""
    logger.info("Closing database pool...")
    await database.close()

@app.get("/")
def home():
    """Health check."""
    return {"status": "healthy", "protocol": "HTTP/2"}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int, database):
    """Get user with async database query."""
    async with database.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
        if not user:
            return {"error": "User not found"}, 404
        return dict(user)

# Create ASGI app
asgi_app = create_asgi_app(app)

# For running directly
if __name__ == "__main__":
    from restmachine.servers import serve_hypercorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8443"))
    workers = int(os.getenv("WORKERS", "4"))

    serve_hypercorn(
        app,
        host=host,
        port=port,
        http_version="http2",
        workers=workers,
        ssl_keyfile=os.getenv("SSL_KEYFILE"),
        ssl_certfile=os.getenv("SSL_CERTFILE"),
    )
```

Run in production:

```bash
export WORKERS=8
export SSL_KEYFILE=/etc/ssl/private/key.pem
export SSL_CERTFILE=/etc/ssl/certs/cert.pem
hypercorn app:asgi_app --bind 0.0.0.0:8443 --workers 8
```

## Performance Tuning

### Worker Configuration

Optimize workers for your workload:

```python
import os
import multiprocessing

# CPU-bound workload
workers = multiprocessing.cpu_count()

# I/O-bound workload (more workers)
workers = multiprocessing.cpu_count() * 2 + 1

# From environment
workers = int(os.getenv("WORKERS", str(multiprocessing.cpu_count())))
```

### Connection Limits

Set backlog for high-traffic applications:

```bash
hypercorn app:asgi_app --backlog 2048
```

### Keep-Alive Timeout

Adjust keep-alive timeout for your use case:

```bash
# Short timeout for many short requests
hypercorn app:asgi_app --keep-alive-timeout 2

# Longer timeout for persistent connections
hypercorn app:asgi_app --keep-alive-timeout 30
```

## WebSocket Support

Hypercorn has excellent WebSocket support:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """WebSocket endpoint."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        await websocket.close()
```

Configure WebSocket timeouts:

```bash
hypercorn app:asgi_app --websocket-ping-interval 20
```

## Monitoring

### Health Check Endpoints

```python
@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "healthy"}

@app.get("/ready")
async def readiness(database):
    """Readiness probe."""
    try:
        async with database.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not ready"}, 503
```

### Kubernetes Configuration

**Deployment with HTTP/2:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        ports:
        - containerPort: 8443
          name: https
          protocol: TCP
        env:
        - name: WORKERS
          value: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8443
            scheme: HTTPS
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8443
            scheme: HTTPS
          initialDelaySeconds: 5
          periodSeconds: 10
```

## Troubleshooting

### HTTP/2 Not Working

Verify HTTP/2 is enabled:

```bash
# Check with curl
curl -I --http2 https://localhost:8443

# Check protocol in logs
hypercorn app:asgi_app --log-level debug
```

### SSL Certificate Issues

Test SSL configuration:

```bash
# Verify certificate
openssl s_client -connect localhost:8443 -showcerts

# Check certificate validity
openssl x509 -in cert.pem -text -noout
```

### High Memory Usage

Reduce workers or enable worker recycling:

```bash
# Reduce workers
hypercorn app:asgi_app --workers 2

# Monitor memory
ps aux | grep hypercorn
```

### Connection Refused

Check if port is available:

```bash
# Check port
lsof -i :8443

# Test binding
hypercorn app:asgi_app --bind 127.0.0.1:8443
```

## Best Practices

### 1. Use HTTP/2 for Better Performance

HTTP/2 provides:
- Multiplexing (multiple requests over single connection)
- Header compression
- Server push capabilities

```python
serve(app, server="hypercorn", http_version="http2")
```

### 2. Enable Access Logs in Production

Monitor traffic with access logs:

```bash
hypercorn app:asgi_app --access-log /var/log/myapp/access.log
```

### 3. Configure Proper Timeouts

Set appropriate timeouts:

```bash
hypercorn app:asgi_app \
  --keep-alive-timeout 5 \
  --graceful-timeout 30
```

### 4. Use Async Handlers

Leverage async support for I/O operations:

```python
@app.get("/data")
async def get_data(database):
    """Async handler for better concurrency."""
    result = await database.query("SELECT * FROM data")
    return result
```

### 5. Implement Health Checks

Always provide health and readiness endpoints:

```python
@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/ready")
async def ready(database):
    # Check dependencies
    return {"status": "ready"}
```

## Comparison with Other Servers

| Feature | Hypercorn | Uvicorn | Gunicorn |
|---------|-----------|---------|----------|
| HTTP/1.1 | ✓ | ✓ | ✓ |
| HTTP/2 | ✓ | Limited | ✗ |
| HTTP/3 | ✓ | ✗ | ✗ |
| WebSockets | ✓ | ✓ | ✗ |
| Async/Await | ✓ | ✓ | Limited |
| Auto-reload | ✗ | ✓ | ✗ |
| Worker Management | ✓ | ✓ | ✓ |
| Production Ready | ✓ | ✓ | ✓ |

## When to Use Hypercorn

**Choose Hypercorn when you need:**

- ✅ HTTP/2 or HTTP/3 support
- ✅ Excellent WebSocket support
- ✅ Full async/await capabilities
- ✅ Modern protocol features
- ✅ Built-in HTTP/3 (QUIC) support

**Choose Uvicorn when you need:**

- ✅ Maximum HTTP/1.1 performance
- ✅ Auto-reload for development
- ✅ Simpler deployment
- ✅ Better uvloop integration

## Next Steps

- Learn about [Uvicorn deployment](uvicorn.md) for HTTP/1.1 performance
- Explore [AWS Lambda deployment](../../restmachine-aws/guides/lambda-deployment.md) for serverless
- Check [Performance Optimization](../../advanced/performance.md) tips

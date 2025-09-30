# RestMachine HTTP Server Examples

This directory contains examples demonstrating how to use RestMachine with different HTTP servers.

## Available Servers

RestMachine supports two high-performance ASGI servers:

### Uvicorn
- **Strengths**: Lightning-fast, excellent HTTP/1.1 support, mature and stable
- **HTTP Support**: HTTP/1.1, HTTP/2
- **Best for**: Production applications, high-performance HTTP/1.1 APIs

### Hypercorn
- **Strengths**: Full HTTP/2 and HTTP/3 support, comprehensive ASGI implementation
- **HTTP Support**: HTTP/1.1, HTTP/2, HTTP/3
- **Best for**: Modern applications requiring HTTP/2 or HTTP/3, WebSocket support

## Installation

Install the servers as optional dependencies:

```bash
# Install Uvicorn
pip install 'restmachine[uvicorn]'

# Install Hypercorn
pip install 'restmachine[hypercorn]'

# Install both servers
pip install 'restmachine[server]'
```

## Quick Start

### Using the High-Level API

```python
from restmachine import RestApplication, serve

app = RestApplication()

@app.get("/")
def hello():
    return {"message": "Hello World!"}

# Serve with Uvicorn (default)
serve(app, host="0.0.0.0", port=8000)

# Serve with Hypercorn
serve(app, server="hypercorn", host="0.0.0.0", port=8000)

# Serve with HTTP/2
serve(app, server="hypercorn", http_version="http2", port=8000)
```

### Using Server-Specific Functions

```python
from restmachine import RestApplication, serve_uvicorn, serve_hypercorn

app = RestApplication()

@app.get("/")
def hello():
    return {"message": "Hello World!"}

# Uvicorn with HTTP/1.1
serve_uvicorn(app, host="0.0.0.0", port=8000)

# Uvicorn with HTTP/2
serve_uvicorn(app, host="0.0.0.0", port=8000, http_version="http2")

# Hypercorn with HTTP/2
serve_hypercorn(app, host="0.0.0.0", port=8000, http_version="http2")

# Hypercorn with HTTP/3 (requires SSL)
serve_hypercorn(
    app,
    host="0.0.0.0",
    port=8000,
    http_version="http3",
    ssl_keyfile="server.key",
    ssl_certfile="server.crt"
)
```

### Using Driver Classes Directly

```python
from restmachine import RestApplication
from restmachine.servers import UvicornDriver, HypercornDriver

app = RestApplication()

@app.get("/")
def hello():
    return {"message": "Hello World!"}

# Uvicorn driver
uvicorn_driver = UvicornDriver(app, host="0.0.0.0", port=8000)
uvicorn_driver.run(log_level="info", reload=True)

# Hypercorn driver with HTTP/2
hypercorn_driver = HypercornDriver(app, host="0.0.0.0", port=8000, http_version="http2")
hypercorn_driver.run(log_level="info", workers=4)
```

## Examples

### 1. Basic Server Example (`basic_server_example.py`)

A complete TODO API demonstrating:
- CRUD operations
- Query parameters
- Path parameters
- Error handling
- Different HTTP servers and versions

**Run with:**
```bash
# Default (Uvicorn, HTTP/1.1)
python examples/basic_server_example.py

# Hypercorn with HTTP/2
python examples/basic_server_example.py --server hypercorn --http-version http2

# Development mode with auto-reload
python examples/basic_server_example.py --reload

# Different host and port
python examples/basic_server_example.py --host 0.0.0.0 --port 3000
```

### 2. Multi-Server Comparison (`multi_server_comparison.py`)

Benchmarks and compares different server configurations:
- Performance testing
- Feature compatibility
- Error handling validation

**Run with:**
```bash
python examples/multi_server_comparison.py
```

## HTTP Version Support

| Server    | HTTP/1.1 | HTTP/2 | HTTP/3 |
|-----------|----------|--------|--------|
| Uvicorn   | ✅       | ✅     | ❌     |
| Hypercorn | ✅       | ✅     | ✅     |

### Notes on HTTP/2 and HTTP/3

- **HTTP/2**: Typically requires HTTPS in production. Both servers support HTTP/2 over plain HTTP for development.
- **HTTP/3**: Only supported by Hypercorn and requires SSL certificates.

## Configuration Options

### Uvicorn Configuration

```python
serve_uvicorn(
    app,
    host="0.0.0.0",
    port=8000,
    http_version="http1",  # "http1" or "http2"
    log_level="info",
    reload=False,          # Auto-reload for development
    workers=1,             # Number of worker processes
    ssl_keyfile=None,      # SSL key file
    ssl_certfile=None,     # SSL certificate file
)
```

### Hypercorn Configuration

```python
serve_hypercorn(
    app,
    host="0.0.0.0",
    port=8000,
    http_version="http1",  # "http1", "http2", or "http3"
    log_level="info",
    workers=1,             # Number of worker processes
    ssl_keyfile=None,      # SSL key file (required for HTTP/3)
    ssl_certfile=None,     # SSL certificate file (required for HTTP/3)
    access_log=True,       # Enable access logging
)
```

## Testing with HTTP Servers

The test framework includes HTTP server drivers for integration testing:

```python
from tests.framework import UvicornHttp1Driver, HypercornHttp2Driver
from restmachine import RestApplication

app = RestApplication()

@app.get("/test")
def test():
    return {"status": "ok"}

# Test with Uvicorn HTTP/1.1
with UvicornHttp1Driver(app) as driver:
    from tests.framework import RestApiDsl
    api = RestApiDsl(driver)
    response = api.get_resource("/test")
    # ... assertions

# Test with Hypercorn HTTP/2
with HypercornHttp2Driver(app) as driver:
    api = RestApiDsl(driver)
    response = api.get_resource("/test")
    # ... assertions
```

## Production Deployment

### Uvicorn Production Setup

```bash
# Single process
uvicorn myapp:app --host 0.0.0.0 --port 8000

# Multiple workers
uvicorn myapp:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn (recommended for production)
gunicorn myapp:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Hypercorn Production Setup

```bash
# Single process
hypercorn myapp:app --bind 0.0.0.0:8000

# Multiple workers
hypercorn myapp:app --bind 0.0.0.0:8000 --workers 4

# HTTP/2 with SSL
hypercorn myapp:app --bind 0.0.0.0:443 --keyfile server.key --certfile server.crt
```

### Creating ASGI Application

For deployment with external ASGI servers:

```python
# myapp.py
from restmachine import RestApplication
from restmachine.server import create_asgi_app

app = RestApplication()

@app.get("/")
def hello():
    return {"message": "Hello World!"}

# Create ASGI application
asgi_app = create_asgi_app(app)

# This can be used with any ASGI server
# uvicorn myapp:asgi_app
# hypercorn myapp:asgi_app
```

## Performance Tips

1. **Use HTTP/2** for applications with many small requests
2. **Enable multiple workers** for CPU-bound applications
3. **Use Uvicorn** for maximum HTTP/1.1 performance
4. **Use Hypercorn** for HTTP/2/3 features or when WebSocket support is needed
5. **Enable SSL/TLS** in production for security and HTTP/2 compatibility
6. **Use a reverse proxy** (nginx, traefik) for static files and load balancing

## Troubleshooting

### ImportError: No module named 'uvicorn'
```bash
pip install 'restmachine[uvicorn]'
```

### ImportError: No module named 'hypercorn'
```bash
pip install 'restmachine[hypercorn]'
```

### HTTP/2 not working
- Ensure you're using HTTPS (many clients require HTTPS for HTTP/2)
- Check that your server supports HTTP/2 (Hypercorn recommended)
- Verify client supports HTTP/2

### SSL Certificate errors for HTTP/3
```bash
# Generate self-signed certificates for testing
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```

### Port already in use
- Use a different port: `--port 8001`
- Kill existing processes: `pkill -f python`
- Check what's using the port: `lsof -i :8000`
# CORS (Cross-Origin Resource Sharing)

RestMachine provides built-in CORS support with smart defaults, automatic method detection, and flexible configuration at app, router, or route level.

## Overview

CORS is a browser security feature that controls which web applications can access your API from different origins. RestMachine handles:

- **Automatic preflight responses** - OPTIONS requests with proper CORS headers
- **Method auto-detection** - No need to manually specify allowed methods
- **Smart defaults** - Sensible allow/expose headers out of the box
- **Three-tier configuration** - App-level, router-level, or route-level
- **Security validation** - Prevents unsafe wildcard + credentials combinations

## Quick Start

### Basic CORS Setup

The simplest CORS configuration - just specify allowed origins:

```python
from restmachine import RestApplication

app = RestApplication()

# Enable CORS for your frontend
app.cors(origins=["https://app.example.com"])

@app.get("/api/data")
def get_data():
    return {"message": "Hello from API"}

# That's it! Methods are auto-detected, headers use smart defaults
```

When a browser makes a request from `https://app.example.com`:

1. **Preflight (OPTIONS)**: RestMachine automatically responds with appropriate CORS headers
2. **Actual Request**: CORS headers are added to your response
3. **Methods**: Auto-detected from registered routes (GET, OPTIONS in this example)

## Configuration Levels

RestMachine supports CORS configuration at three levels with inheritance:

### 1. App-Level (Global)

Apply CORS to all routes in the application:

```python
app = RestApplication()

# All routes will have these CORS settings
app.cors(
    origins=["https://app.example.com", "https://admin.example.com"],
    credentials=True,
    max_age=86400  # 24 hours
)

@app.get("/api/users")
def list_users():
    return {"users": [...]}

@app.get("/api/posts")
def list_posts():
    return {"posts": [...]}
```

### 2. Router-Level

Apply CORS to all routes in a specific router:

```python
from restmachine import Router

app = RestApplication()

# Public API router - allow all origins
public_api = Router()
public_api.cors(origins="*")

@public_api.get("/status")
def get_status():
    return {"status": "ok"}

# Admin API router - restrict origins
admin_api = Router()
admin_api.cors(
    origins=["https://admin.example.com"],
    credentials=True
)

@admin_api.get("/dashboard")
def get_dashboard():
    return {"stats": {...}}

app.mount("/api/public", public_api)
app.mount("/api/admin", admin_api)
```

### 3. Route-Level (Most Specific)

Override CORS for specific endpoints:

```python
app = RestApplication()

# Default CORS for most routes
app.cors(origins=["https://app.example.com"])

@app.get("/api/data")
def get_data():
    # Uses app-level CORS
    return {"data": "value"}

@app.post("/api/webhook")
@app.cors(origins=["https://external-service.com"])
def webhook():
    # Overrides app-level CORS for this endpoint only
    return {"received": True}
```

**Priority**: Route-level > Router-level > App-level (most specific wins)

## Auto-Detection of Methods

RestMachine automatically detects allowed methods from your registered routes:

```python
app = RestApplication()
app.cors(origins=["https://app.example.com"])

@app.get("/users/{id}")
def get_user(id: str):
    return {"id": id}

@app.put("/users/{id}")
def update_user(id: str, json_body):
    return {"id": id, **json_body}

@app.delete("/users/{id}")
def delete_user(id: str):
    return None

# OPTIONS /users/123 automatically returns:
# Allow: DELETE, GET, OPTIONS, PUT
# Access-Control-Allow-Methods: DELETE, GET, OPTIONS, PUT
```

No need to manually specify methods - they're inferred from your routes!

### Manual Method Override

Override auto-detection when needed:

```python
@app.get("/admin/users")
@app.post("/admin/users")
@app.delete("/admin/users")
@app.cors(
    origins=["https://admin.example.com"],
    methods=["GET", "POST"]  # Don't expose DELETE via CORS
)
def admin_users():
    return {"users": [...]}
```

## Configuration Options

### Origins

Specify which origins can access your API:

```python
# Single origin
app.cors(origins="https://app.example.com")

# Multiple origins
app.cors(origins=[
    "https://app.example.com",
    "https://admin.example.com",
    "http://localhost:3000"  # Development
])

# Allow all origins (use cautiously!)
app.cors(origins="*")
```

### Credentials

Allow cookies and authorization headers:

```python
app.cors(
    origins=["https://app.example.com"],
    credentials=True  # Allows cookies, Authorization header
)

# Security note: Cannot use credentials=True with origins="*"
# This will raise ValueError - use specific origins instead
```

### Development with Credentials (Origin Reflection)

For development environments where you need credentials support from any origin (e.g., testing from multiple local ports), use `reflect_any_origin`:

```python
import os

app = RestApplication()

# Development only: reflect any origin with credentials
if os.getenv("ENV") == "development":
    app.cors(
        origins="*",
        credentials=True,
        reflect_any_origin=True  # WARNING: Development only!
    )
else:
    # Production: use explicit origins
    app.cors(
        origins=["https://app.example.com"],
        credentials=True
    )
```

**How it works**: When `reflect_any_origin=True`, the framework reflects the request's `Origin` header in the `Access-Control-Allow-Origin` response header instead of sending `*`. This allows credentials to work while accepting any origin.

**⚠️ WARNING**: Only use `reflect_any_origin=True` in development! In production, always specify explicit allowed origins for security.

**Use cases**:
- Local development with multiple ports (e.g., `http://localhost:3000`, `http://localhost:3001`)
- Testing mobile apps with various emulator origins
- Development environments where frontend origins frequently change

### Request Headers

Control which headers clients can send:

```python
app.cors(
    origins=["https://app.example.com"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Request-ID"
    ]
)

# Default allow_headers (if not specified):
# - Accept
# - Accept-Language
# - Content-Type
# - Content-Language
# - Authorization
# - X-Requested-With
```

### Response Headers

Control which headers JavaScript can read:

```python
app.cors(
    origins=["https://app.example.com"],
    expose_headers=[
        "X-Request-ID",
        "X-Rate-Limit-Remaining",
        "X-Total-Count"
    ]
)

# Default expose_headers (if not specified):
# - Content-Length
# - Content-Type
# - ETag
# - Location
# - X-Request-ID
```

### Preflight Cache

Control how long browsers cache preflight responses:

```python
app.cors(
    origins=["https://app.example.com"],
    max_age=86400  # 24 hours (default)
)

# For development (short cache)
app.cors(origins="*", max_age=300)  # 5 minutes

# For production (long cache)
app.cors(origins=[...], max_age=604800)  # 7 days
```

## Complete Example

Here's a production-ready CORS setup:

```python
from restmachine import RestApplication, Router, Response

app = RestApplication()

# App-level CORS for most routes
app.cors(
    origins=[
        "https://app.example.com",
        "https://www.example.com",
        "http://localhost:3000"  # Development
    ],
    credentials=True,
    max_age=86400
)

# Public API router (no credentials)
public_api = Router()
public_api.cors(
    origins="*",
    credentials=False,
    max_age=3600
)

@public_api.get("/status")
def api_status():
    """Public status endpoint."""
    return {"status": "operational", "version": "1.0"}

@public_api.get("/docs")
def api_docs():
    """Public API documentation."""
    return {"endpoints": [...]}

app.mount("/api/v1/public", public_api)

# Protected routes (use app-level CORS with credentials)
@app.get("/api/v1/user/profile")
def get_profile(request):
    """User profile - requires authentication."""
    auth = request.headers.get("Authorization")
    if not auth:
        return Response(401, {"error": "Unauthorized"})

    return {"user": "alice", "email": "alice@example.com"}

@app.post("/api/v1/user/settings")
def update_settings(json_body):
    """Update user settings."""
    return {"updated": True, **json_body}

# Webhook endpoint (different origin)
@app.post("/api/v1/webhooks/github")
@app.cors(
    origins=["https://github.com"],
    methods=["POST"]
)
def github_webhook(json_body):
    """GitHub webhook handler."""
    return {"received": True}

# ASGI app
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## How CORS Works

### Preflight Requests

When a browser makes a "complex" request (POST, PUT, DELETE, or custom headers), it first sends a preflight:

```http
OPTIONS /api/users HTTP/1.1
Host: api.example.com
Origin: https://app.example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type, Authorization
```

RestMachine automatically responds:

```http
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
Allow: GET, POST, OPTIONS
```

### Actual Requests

After successful preflight, the browser makes the actual request:

```http
POST /api/users HTTP/1.1
Host: api.example.com
Origin: https://app.example.com
Content-Type: application/json
Authorization: Bearer abc123

{"name": "Alice"}
```

RestMachine adds CORS headers to your response:

```http
HTTP/1.1 201 Created
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: X-Request-ID
Vary: Origin
Content-Type: application/json

{"id": "123", "name": "Alice"}
```

## Security Considerations

### Validate Origins

Always use specific origins in production:

```python
# ✅ Good: Specific origins
app.cors(origins=[
    "https://app.example.com",
    "https://admin.example.com"
])

# ⚠️  Use cautiously: Wildcard (no credentials allowed)
app.cors(origins="*", credentials=False)

# ❌ Invalid: Wildcard with credentials
app.cors(origins="*", credentials=True)  # Raises ValueError
```

### Credentials and Wildcards

You cannot use `credentials=True` with `origins="*"` - this is a security requirement:

```python
# This will raise ValueError
try:
    app.cors(origins="*", credentials=True)
except ValueError as e:
    print(e)  # "CORS: Cannot use wildcard origin '*' with credentials=True..."
```

**Exception for development**: You can bypass this restriction using `reflect_any_origin=True`, which reflects the request's origin instead of sending `*`:

```python
# This is allowed for development
app.cors(
    origins="*",
    credentials=True,
    reflect_any_origin=True  # Reflects origin instead of sending "*"
)
```

**⚠️ Production warning**: Never use `reflect_any_origin=True` in production! It allows any origin to access your API with credentials, which is a security risk. Always use explicit origins in production.

### Origin Validation

RestMachine checks the `Origin` header against your configuration:

```python
app.cors(origins=["https://app.example.com"])

# Request from https://app.example.com
# ✅ CORS headers added

# Request from https://evil.com
# ❌ No CORS headers added (browser blocks response)
```

## Testing CORS

### Manual Testing with curl

Test preflight request:

```bash
curl -X OPTIONS http://localhost:8000/api/users \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v
```

Test actual request:

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Origin: https://app.example.com" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}' \
  -v
```

### Automated Testing

```python
from restmachine import Request, HTTPMethod

def test_cors_preflight():
    """Test CORS preflight request."""
    app = RestApplication()
    app.cors(origins=["https://app.example.com"])

    @app.post("/api/data")
    def create_data(json_body):
        return {"created": True}

    # Preflight request
    request = Request(
        method=HTTPMethod.OPTIONS,
        path="/api/data",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST"
        }
    )
    response = app.execute(request)

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]

def test_cors_actual_request():
    """Test CORS on actual request."""
    app = RestApplication()
    app.cors(origins=["https://app.example.com"], credentials=True)

    @app.get("/api/data")
    def get_data():
        return {"data": "value"}

    # Actual request
    request = Request(
        method=HTTPMethod.GET,
        path="/api/data",
        headers={"Origin": "https://app.example.com"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "Origin" in response.headers["Vary"]
```

## Common Patterns

### Development vs Production

```python
import os

app = RestApplication()

# Different CORS config for dev/prod
if os.getenv("ENV") == "production":
    app.cors(
        origins=[
            "https://app.example.com",
            "https://www.example.com"
        ],
        credentials=True,
        max_age=86400
    )
else:
    # Permissive for development (with credentials support)
    app.cors(
        origins="*",
        credentials=True,
        reflect_any_origin=True,  # Reflect origin for credentials
        max_age=300
    )
```

### Multiple Frontends

```python
app = RestApplication()

# Main web app
web_origins = [
    "https://app.example.com",
    "https://www.example.com"
]

# Mobile app
mobile_origins = [
    "capacitor://localhost",  # Capacitor
    "ionic://localhost"       # Ionic
]

# Admin dashboard
admin_origins = [
    "https://admin.example.com"
]

# Combine all allowed origins
all_origins = web_origins + mobile_origins + admin_origins

app.cors(
    origins=all_origins,
    credentials=True
)
```

### API Gateway Pattern

```python
# Public gateway (no auth)
public = Router()
public.cors(origins="*", max_age=3600)

@public.get("/health")
def health():
    return {"healthy": True}

# Authenticated API
api = Router()
api.cors(
    origins=["https://app.example.com"],
    credentials=True
)

@api.get("/data")
def get_data(request):
    # Requires auth
    return {"data": [...]}

app.mount("/public", public)
app.mount("/api", api)
```

## Troubleshooting

### CORS Headers Not Appearing

**Problem**: No CORS headers in response

**Solutions**:
1. Ensure `Origin` header is present in request
2. Check origin is in allowed list
3. Verify CORS is configured (`app.cors(...)` called)

```python
# Check your configuration
app.cors(origins=["https://app.example.com"])

# Request must include Origin header
# curl -H "Origin: https://app.example.com" ...
```

### Preflight Failures

**Problem**: OPTIONS requests failing

**Solutions**:
1. Check if route exists for the path
2. Verify allowed methods include requested method
3. Ensure headers are allowed

```python
# Make sure route exists
@app.post("/api/data")  # ✅ Route registered
def create_data():
    pass

# Allow required headers
app.cors(
    origins=[...],
    allow_headers=["Content-Type", "Authorization"]  # ✅ Headers allowed
)
```

### Credentials Not Working

**Problem**: Cookies not sent with CORS requests

**Solutions**:
1. Set `credentials=True` in CORS config
2. Use specific origins (not wildcard)
3. Frontend must use `credentials: 'include'`

```python
# Backend
app.cors(
    origins=["https://app.example.com"],  # ✅ Specific origin
    credentials=True                       # ✅ Credentials enabled
)

# Frontend (JavaScript)
fetch('https://api.example.com/data', {
    credentials: 'include'  // ✅ Include cookies
})
```

## Best Practices

1. **Use Specific Origins in Production**
   ```python
   # ✅ Good
   app.cors(origins=["https://app.example.com"])

   # ⚠️  Only for development
   app.cors(origins="*")
   ```

2. **Enable Credentials When Needed**
   ```python
   app.cors(
       origins=["https://app.example.com"],
       credentials=True  # For cookies, auth headers
   )
   ```

3. **Set Appropriate Cache Duration**
   ```python
   # Development: short cache
   app.cors(origins=[...], max_age=300)

   # Production: longer cache
   app.cors(origins=[...], max_age=86400)
   ```

4. **Limit Exposed Headers**
   ```python
   # Only expose what clients need
   app.cors(
       origins=[...],
       expose_headers=["X-Request-ID", "X-Total-Count"]
   )
   ```

5. **Use Router-Level CORS for Organization**
   ```python
   public_api = Router()
   public_api.cors(origins="*")

   private_api = Router()
   private_api.cors(origins=[...], credentials=True)
   ```

## Next Steps

- [Authentication →](authentication.md) - Use CORS with authentication
- [Multi-Value Headers →](../advanced/headers.md) - Advanced header handling
- [Testing →](testing.md) - Test CORS configurations
- [Deployment →](deployment-asgi.md) - Deploy with CORS enabled

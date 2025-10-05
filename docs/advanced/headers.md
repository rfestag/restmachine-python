# Multi-Value Headers

RestMachine provides complete support for HTTP headers, including proper handling of multi-value headers according to the HTTP specification. This guide covers single and multi-value headers, cookies, caching, and best practices.

## Understanding Multi-Value Headers

### HTTP Specification

The HTTP specification allows headers to have multiple values in two forms:

1. **Multiple header lines with the same name:**
   ```
   Set-Cookie: session_id=abc123; HttpOnly
   Set-Cookie: user_pref=dark_mode; Path=/
   ```

2. **Comma-separated values in a single header:**
   ```
   Accept: text/html, application/json
   Cache-Control: no-cache, no-store, must-revalidate
   ```

RestMachine handles both forms correctly and provides APIs for working with multi-value headers.

## Reading Headers

### Single-Value Headers

Access most headers as single values:

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.get('/api/data')
def get_data(request: Request):
    """Access single-value headers."""
    # Get content type
    content_type = request.headers.get('content-type', 'application/json')

    # Get authorization header
    auth = request.headers.get('authorization')

    # Get user agent
    user_agent = request.headers.get('user-agent')

    # Check if header exists
    has_api_key = 'x-api-key' in request.headers

    return {
        "content_type": content_type,
        "has_auth": auth is not None,
        "user_agent": user_agent
    }
```

### Multi-Value Headers

Some headers can have multiple values:

```python
@app.get('/api/negotiation')
def content_negotiation(request: Request):
    """Handle multi-value Accept header."""
    # Accept header may have multiple values
    accept = request.headers.get('accept', '*/*')

    # Parse comma-separated values
    accepted_types = [
        t.strip().split(';')[0]  # Remove quality parameters
        for t in accept.split(',')
    ]

    # Select appropriate format
    if 'application/json' in accepted_types:
        return {"format": "json"}
    elif 'text/html' in accepted_types:
        return "<html><body>HTML Response</body></html>", 200, {
            'Content-Type': 'text/html'
        }
    else:
        return {"format": "default"}
```

### Reading All Headers

Access all headers as a dictionary:

```python
@app.get('/debug/headers')
def show_headers(request: Request):
    """Show all request headers."""
    # Get all headers as dict
    all_headers = dict(request.headers)

    # Filter sensitive headers
    safe_headers = {
        k: v for k, v in all_headers.items()
        if k.lower() not in ['authorization', 'cookie']
    }

    return {
        "headers": safe_headers,
        "count": len(all_headers)
    }
```

## Setting Response Headers

### Single Headers

Set single-value response headers:

```python
@app.get('/api/data')
def get_data():
    """Return data with custom headers."""
    data = {"message": "Hello"}

    headers = {
        'Content-Type': 'application/json',
        'X-API-Version': '1.0',
        'X-Request-ID': 'abc-123-def'
    }

    return data, 200, headers
```

### Multi-Value Headers

Set headers that appear multiple times:

```python
@app.get('/api/multi-header')
def multi_header_example():
    """Demonstrate multi-value headers."""
    # For Set-Cookie and other multi-value headers,
    # use MultiValueHeaders
    from restmachine.models import MultiValueHeaders

    headers = MultiValueHeaders()

    # Add multiple Set-Cookie headers
    headers.append('Set-Cookie', 'session_id=abc123; HttpOnly; SameSite=Lax')
    headers.append('Set-Cookie', 'user_pref=dark; Path=/')
    headers.append('Set-Cookie', 'lang=en; Max-Age=31536000')

    # Add single-value headers
    headers['Content-Type'] = 'application/json'
    headers['X-Custom'] = 'value'

    return {"status": "ok"}, 200, headers
```

## Working with Cookies

### Setting Cookies

Set cookies with proper attributes:

```python
from datetime import datetime, timedelta

@app.post('/auth/login')
def login(request: Request):
    """Set authentication cookies."""
    from restmachine.models import MultiValueHeaders

    headers = MultiValueHeaders()

    # Session cookie (expires when browser closes)
    headers.append(
        'Set-Cookie',
        'session_id=abc123; HttpOnly; Secure; SameSite=Strict; Path=/'
    )

    # Persistent cookie (expires in 7 days)
    max_age = 7 * 24 * 60 * 60  # 7 days in seconds
    headers.append(
        'Set-Cookie',
        f'remember_token=xyz789; HttpOnly; Secure; SameSite=Lax; '
        f'Max-Age={max_age}; Path=/'
    )

    # Preferences cookie (not sensitive)
    headers.append(
        'Set-Cookie',
        'theme=dark; SameSite=Lax; Max-Age=31536000; Path=/'
    )

    return {"message": "Logged in"}, 200, headers
```

### Reading Cookies

Parse cookies from request:

```python
@app.dependency()
def parse_cookies(request: Request) -> dict:
    """Parse cookies from Cookie header."""
    cookie_header = request.headers.get('cookie', '')

    cookies = {}
    for cookie in cookie_header.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            cookies[name] = value

    return cookies

@app.get('/api/profile')
def get_profile(parse_cookies: dict):
    """Access user profile using session cookie."""
    session_id = parse_cookies.get('session_id')

    if not session_id:
        from restmachine import Response
        return Response(401, '{"error": "Not authenticated"}')

    return {
        "session_id": session_id,
        "theme": parse_cookies.get('theme', 'light')
    }
```

### Deleting Cookies

Delete cookies by setting Max-Age=0:

```python
@app.post('/auth/logout')
def logout():
    """Clear authentication cookies."""
    from restmachine.models import MultiValueHeaders

    headers = MultiValueHeaders()

    # Delete cookies by setting Max-Age=0
    headers.append(
        'Set-Cookie',
        'session_id=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0'
    )

    headers.append(
        'Set-Cookie',
        'remember_token=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0'
    )

    return {"message": "Logged out"}, 200, headers
```

## Caching Headers

### Cache-Control

Set appropriate cache control headers:

```python
@app.get('/api/static-data')
def static_data():
    """Cacheable static data."""
    data = {"version": "1.0", "data": [...]}

    headers = {
        'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
        'ETag': '"abc123"',
        'Vary': 'Accept-Encoding'
    }

    return data, 200, headers

@app.get('/api/dynamic-data')
def dynamic_data():
    """Non-cacheable dynamic data."""
    data = {"timestamp": datetime.now().isoformat()}

    headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    return data, 200, headers

@app.get('/api/user-data')
def user_data():
    """Private user data (cache per user)."""
    data = {"user": "alice", "data": [...]}

    headers = {
        'Cache-Control': 'private, max-age=300',  # Cache for 5 minutes
        'Vary': 'Authorization'
    }

    return data, 200, headers
```

### ETags for Conditional Requests

Implement ETags for efficient caching:

```python
import hashlib
import json

@app.dependency()
def database():
    return {
        "users": [
            {"id": "1", "name": "Alice", "updated_at": "2024-01-01T10:00:00"}
        ]
    }

@app.get('/api/users/{user_id}')
def get_user(request: Request, database):
    """Get user with ETag support."""
    user_id = request.path_params['user_id']
    user = next((u for u in database['users'] if u['id'] == user_id), None)

    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')

    # Calculate ETag from user data
    user_json = json.dumps(user, sort_keys=True)
    etag = hashlib.md5(user_json.encode()).hexdigest()
    etag_header = f'"{etag}"'

    # Check If-None-Match header
    if_none_match = request.headers.get('if-none-match')
    if if_none_match == etag_header:
        # Resource unchanged
        return '', 304, {'ETag': etag_header}

    # Resource changed or first request
    headers = {
        'ETag': etag_header,
        'Cache-Control': 'private, must-revalidate'
    }

    return user, 200, headers
```

## CORS Headers

### Basic CORS

Handle Cross-Origin Resource Sharing:

```python
@app.dependency()
def add_cors_headers():
    """CORS headers dependency."""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400'  # 24 hours
    }

@app.options('/api/users')
def users_options(add_cors_headers):
    """Handle preflight request."""
    return '', 204, add_cors_headers

@app.get('/api/users')
def list_users(database, add_cors_headers):
    """List users with CORS."""
    return database['users'], 200, add_cors_headers
```

### Conditional CORS

Allow specific origins only:

```python
ALLOWED_ORIGINS = [
    'https://example.com',
    'https://app.example.com',
    'http://localhost:3000'
]

@app.dependency()
def cors_headers(request: Request):
    """Generate CORS headers based on origin."""
    origin = request.headers.get('origin')

    if origin in ALLOWED_ORIGINS:
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '86400'
        }

    return {}

@app.get('/api/data')
def get_data(cors_headers):
    """Return data with CORS if origin allowed."""
    return {"data": [...]}, 200, cors_headers
```

## Security Headers

### Common Security Headers

Set security headers to protect your application:

```python
@app.dependency()
def security_headers():
    """Common security headers."""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'",
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }

@app.get('/api/secure-data')
def secure_data(security_headers):
    """Return data with security headers."""
    return {"data": "sensitive"}, 200, security_headers
```

### Content Security Policy

Set detailed CSP headers:

```python
@app.get('/app')
def web_app():
    """Serve web app with CSP."""
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Secure App</title></head>
    <body><h1>Secure Application</h1></body>
    </html>
    """

    csp_directives = [
        "default-src 'self'",
        "script-src 'self' https://cdn.example.com",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "font-src 'self' https://fonts.googleapis.com",
        "connect-src 'self' https://api.example.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'"
    ]

    headers = {
        'Content-Type': 'text/html',
        'Content-Security-Policy': '; '.join(csp_directives)
    }

    return html, 200, headers
```

## Custom Headers

### Request ID Tracking

Track requests with unique IDs:

```python
import uuid

@app.dependency()
def request_id(request: Request) -> str:
    """Get or generate request ID."""
    return request.headers.get('x-request-id', str(uuid.uuid4()))

@app.get('/api/data')
def get_data(request_id: str):
    """Return data with request ID."""
    data = {"message": "Hello"}

    headers = {
        'X-Request-ID': request_id
    }

    return data, 200, headers
```

### Rate Limit Headers

Communicate rate limits to clients:

```python
from datetime import datetime, timedelta

@app.dependency()
def rate_limit_headers(request: Request):
    """Calculate rate limit headers."""
    # Simplified rate limiting
    limit = 100
    remaining = 75
    reset_time = datetime.now() + timedelta(hours=1)

    return {
        'X-RateLimit-Limit': str(limit),
        'X-RateLimit-Remaining': str(remaining),
        'X-RateLimit-Reset': str(int(reset_time.timestamp()))
    }

@app.get('/api/data')
def get_data(rate_limit_headers):
    """Return data with rate limit info."""
    return {"data": [...]}, 200, rate_limit_headers
```

## Header Middleware Pattern

### Global Header Injection

Add headers to all responses:

```python
@app.dependency()
def common_headers(request: Request):
    """Headers added to all responses."""
    headers = {
        'X-API-Version': '1.0',
        'X-Powered-By': 'RestMachine',
        'X-Request-Time': datetime.now().isoformat()
    }

    # Add security headers
    headers.update({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY'
    })

    return headers

# Include common_headers in all routes
@app.get('/api/users')
def list_users(database, common_headers):
    return database['users'], 200, common_headers

@app.get('/api/posts')
def list_posts(database, common_headers):
    return database['posts'], 200, common_headers
```

## Complete Example

Here's a complete example with comprehensive header handling:

```python
from restmachine import RestApplication, Request
from restmachine.models import MultiValueHeaders
from datetime import datetime, timedelta
import hashlib
import json
import uuid

app = RestApplication()

# Database
@app.on_startup
def database():
    return {
        "users": [
            {"id": "1", "name": "Alice", "email": "alice@example.com"}
        ]
    }

# Common dependencies
@app.dependency()
def request_id(request: Request) -> str:
    """Get or generate request ID."""
    return request.headers.get('x-request-id', str(uuid.uuid4()))

@app.dependency()
def security_headers():
    """Security headers for all responses."""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Strict-Transport-Security': 'max-age=31536000'
    }

@app.dependency()
def cors_headers(request: Request):
    """CORS headers."""
    origin = request.headers.get('origin', '')

    if origin.endswith('.example.com') or origin == 'http://localhost:3000':
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Credentials': 'true'
        }

    return {}

# Routes with caching
@app.get('/api/users/{user_id}')
def get_user(request: Request, database, security_headers):
    """Get user with ETag caching."""
    user_id = request.path_params['user_id']
    user = next((u for u in database['users'] if u['id'] == user_id), None)

    if not user:
        from restmachine import Response
        return Response(404, '{"error": "Not found"}')

    # Calculate ETag
    user_json = json.dumps(user, sort_keys=True)
    etag = f'"{hashlib.md5(user_json.encode()).hexdigest()}"'

    # Check If-None-Match
    if request.headers.get('if-none-match') == etag:
        headers = {**security_headers, 'ETag': etag}
        return '', 304, headers

    # Return user with caching headers
    headers = {
        **security_headers,
        'ETag': etag,
        'Cache-Control': 'private, max-age=300',
        'Vary': 'Accept-Encoding'
    }

    return user, 200, headers

# Routes with cookies
@app.post('/auth/login')
def login(security_headers):
    """Login with cookies."""
    headers = MultiValueHeaders()

    # Add security headers
    for key, value in security_headers.items():
        headers[key] = value

    # Set authentication cookies
    headers.append(
        'Set-Cookie',
        'session_id=abc123; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600'
    )

    headers.append(
        'Set-Cookie',
        'csrf_token=xyz789; SameSite=Strict; Path=/; Max-Age=3600'
    )

    return {"message": "Logged in"}, 200, headers

@app.post('/auth/logout')
def logout(security_headers):
    """Logout and clear cookies."""
    headers = MultiValueHeaders()

    for key, value in security_headers.items():
        headers[key] = value

    # Clear cookies
    headers.append(
        'Set-Cookie',
        'session_id=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0'
    )

    headers.append(
        'Set-Cookie',
        'csrf_token=; SameSite=Strict; Path=/; Max-Age=0'
    )

    return {"message": "Logged out"}, 200, headers

# CORS preflight
@app.options('/api/users')
def users_options(cors_headers, security_headers):
    """Handle CORS preflight."""
    headers = {
        **cors_headers,
        **security_headers,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400'
    }

    return '', 204, headers

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Use Secure Cookie Attributes

Always set secure attributes for cookies:

```python
# Good: Secure cookie
headers.append(
    'Set-Cookie',
    'session_id=abc; HttpOnly; Secure; SameSite=Strict; Path=/'
)

# Bad: Insecure cookie
headers.append('Set-Cookie', 'session_id=abc')
```

### 2. Set Appropriate Cache Headers

Cache static content, not dynamic:

```python
# Cache static data
@app.get('/api/config')
def get_config():
    return config, 200, {'Cache-Control': 'public, max-age=86400'}

# Don't cache user-specific data
@app.get('/api/profile')
def get_profile(current_user):
    return profile, 200, {'Cache-Control': 'private, no-cache'}
```

### 3. Use Security Headers

Always include security headers:

```python
security_headers = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Strict-Transport-Security': 'max-age=31536000'
}
```

### 4. Handle CORS Properly

Validate origins for CORS:

```python
# Good: Validate origin
if origin in ALLOWED_ORIGINS:
    headers['Access-Control-Allow-Origin'] = origin

# Bad: Allow all origins with credentials
headers['Access-Control-Allow-Origin'] = '*'
headers['Access-Control-Allow-Credentials'] = 'true'  # Invalid!
```

### 5. Use MultiValueHeaders for Set-Cookie

Use MultiValueHeaders for headers that can appear multiple times:

```python
from restmachine.models import MultiValueHeaders

headers = MultiValueHeaders()
headers.append('Set-Cookie', 'session=abc')
headers.append('Set-Cookie', 'theme=dark')
```

## Next Steps

- [TLS →](tls.md) - Secure communications with TLS
- [Authentication →](../guide/authentication.md) - Use headers for auth
- [Caching →](../guide/content-negotiation.md) - Advanced caching strategies
- [Testing →](../guide/testing.md) - Test header handling

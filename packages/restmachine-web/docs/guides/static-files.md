# Serving Static Files

RestMachine Web provides easy static file serving from local filesystem or S3, with built-in security and performance features.

## Installation

```bash
pip install restmachine-web
```

For S3 support:

```bash
pip install restmachine-web[s3]
```

## Quick Start

### Local Files

Serve files from a local directory:

```python
from restmachine import RestApplication
from restmachine_web import StaticRouter

app = RestApplication()

# Mount static files at /static
static = StaticRouter(serve="./public")
app.mount("/static", static)
```

Directory structure:

```
public/
├── css/
│   └── style.css
├── js/
│   └── app.js
├── images/
│   └── logo.png
└── index.html
```

Access files:

- `GET /static/index.html` → `public/index.html`
- `GET /static/css/style.css` → `public/css/style.css`
- `GET /static/images/logo.png` → `public/images/logo.png`

### S3 Files

Serve files from an S3 bucket:

```python
from restmachine_web import StaticRouter

# S3 bucket with optional prefix
s3_static = StaticRouter(serve="s3://my-bucket/assets/")
app.mount("/assets", s3_static)
```

Access files:

- `GET /assets/style.css` → `s3://my-bucket/assets/style.css`
- `GET /assets/js/app.js` → `s3://my-bucket/assets/js/app.js`

## Configuration

### Index Files

Serve `index.html` for directory requests:

```python
static = StaticRouter(
    serve="./public",
    index_file="index.html"  # Default
)

# GET /static/ → public/index.html
# GET /static/docs/ → public/docs/index.html
```

### S3 with Index Retry

Automatically append index file for S3 requests:

```python
s3_static = StaticRouter(
    serve="s3://my-bucket/site/",
    index_file="index.html",
    retry_with_index=True  # Try path + index.html if initial request fails
)

# GET /assets/docs → tries docs, then docs/index.html
```

This is useful for static websites hosted on S3.

## Security Features

### Path Traversal Protection

The router prevents directory traversal attacks:

```python
# These requests are blocked:
GET /static/../../../etc/passwd  # Returns 404
GET /static/..%2F..%2Fetc%2Fpasswd  # Returns 404
```

Requested paths are normalized and validated to ensure they stay within the served directory.

### Method Restrictions

Only `GET` requests are allowed. All other methods return `405 Method Not Allowed`:

```bash
GET /static/file.txt     # ✓ Allowed
POST /static/file.txt    # ✗ 405 Method Not Allowed
DELETE /static/file.txt  # ✗ 405 Method Not Allowed
```

## Content Types

Content-Type headers are set automatically based on file extension:

```python
# Automatic MIME type detection
GET /static/style.css    # Content-Type: text/css
GET /static/app.js       # Content-Type: application/javascript
GET /static/image.png    # Content-Type: image/png
GET /static/data.json    # Content-Type: application/json
GET /static/page.html    # Content-Type: text/html
```

## Complete Example

### Local Static Files

```python
from restmachine import RestApplication, ASGIAdapter
from restmachine_web import StaticRouter

app = RestApplication()

# API routes
@app.get("/api/hello")
def hello():
    return {"message": "Hello from API"}

# Static files
static = StaticRouter(serve="./public", index_file="index.html")
app.mount("/static", static)

# Serve with ASGI
asgi_app = ASGIAdapter(app)
```

Directory structure:

```
project/
├── app.py
└── public/
    ├── index.html
    ├── about.html
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

Run:

```bash
uvicorn app:asgi_app --reload
```

Access:

- `http://localhost:8000/api/hello` → API response
- `http://localhost:8000/static/` → public/index.html
- `http://localhost:8000/static/about.html` → public/about.html
- `http://localhost:8000/static/css/style.css` → public/css/style.css

### S3 Static Site

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter
from restmachine_web import StaticRouter

app = RestApplication()

# API routes
@app.get("/api/status")
def status():
    return {"status": "ok"}

# S3 static files
static = StaticRouter(
    serve="s3://my-static-site/",
    index_file="index.html",
    retry_with_index=True
)
app.mount("/", static)  # Serve at root

# AWS Lambda adapter
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

This serves a static site from S3 via Lambda:

- `GET /` → S3: `index.html`
- `GET /about` → S3: `about/index.html` (with retry_with_index)
- `GET /css/style.css` → S3: `css/style.css`
- `GET /api/status` → API handler (not static)

## Multiple Static Mounts

Serve different directories at different paths:

```python
from restmachine_web import StaticRouter

# Frontend assets
frontend = StaticRouter(serve="./frontend/dist")
app.mount("/app", frontend)

# Admin panel
admin = StaticRouter(serve="./admin/build")
app.mount("/admin", admin)

# User uploads (from S3)
uploads = StaticRouter(serve="s3://my-bucket/uploads/")
app.mount("/uploads", uploads)
```

Access:

- `/app/` → ./frontend/dist/
- `/admin/` → ./admin/build/
- `/uploads/` → s3://my-bucket/uploads/

## Error Handling

### File Not Found

Returns `404 Not Found`:

```python
GET /static/nonexistent.txt  # 404 Not Found
```

### Directory Without Index

If directory is requested but `index.html` doesn't exist:

```python
GET /static/somedir/  # 404 if somedir/index.html doesn't exist
```

### S3 Errors

S3 errors are converted to appropriate HTTP status codes:

```python
# NoSuchKey → 404 Not Found
# AccessDenied → 403 Forbidden
# Other errors → 500 Internal Server Error
```

## Best Practices

1. **Use Absolute Paths** - Specify full paths to avoid confusion
   ```python
   import os
   static_dir = os.path.join(os.path.dirname(__file__), "public")
   static = StaticRouter(serve=static_dir)
   ```

2. **Separate Static from Dynamic** - Keep static files in a dedicated directory
   ```
   project/
   ├── src/          # Python code
   └── public/       # Static files
   ```

3. **Use CDN for Production** - For high-traffic sites, use CloudFront or similar
   ```python
   # Development
   static = StaticRouter(serve="./public")

   # Production - use CDN, minimal static serving
   ```

4. **Cache Headers** - Add caching for better performance
   ```python
   # Future enhancement: cache-control headers
   ```

## Performance Considerations

### Local Files

- Files are read on each request
- Consider using a reverse proxy (nginx) for high-traffic static files
- Use `StaticRouter` for convenience, not high-performance static serving

### S3 Files

- Each request makes an S3 API call
- Consider CloudFront CDN for better performance and cost
- Use for serverless deployments where local filesystem isn't available

## See Also

- [StaticRouter API](../api/static-router.md) - Complete API reference
- [Template Rendering](templates.md) - Combine with dynamic templates
- [AWS Lambda Deployment](../../restmachine-aws/guides/lambda-deployment.md) - Deploy with Lambda

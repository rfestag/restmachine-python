# StaticRouter

::: restmachine_web.StaticRouter
    options:
      show_root_heading: true
      heading_level: 2

## Overview

`StaticRouter` is a specialized router for serving static files from local filesystem or S3 buckets. It inherits from `restmachine.Router` and provides secure, convenient static file serving with automatic MIME type detection and path traversal protection.

## Class Signature

```python
class StaticRouter(Router):
    def __init__(
        self,
        serve: str,
        index_file: str = "index.html",
        retry_with_index: bool = False
    )
```

## Parameters

### `serve` (required)

Path to serve files from. Can be:

- **Local path**: `"./public"`, `"/var/www/html"`, `"static/"`
- **S3 URI**: `"s3://bucket-name/prefix/"`

```python
# Local filesystem
StaticRouter(serve="./public")
StaticRouter(serve="/var/www/static")

# S3 bucket
StaticRouter(serve="s3://my-bucket/assets/")
StaticRouter(serve="s3://website-bucket/")
```

### `index_file` (optional)

Default: `"index.html"`

Name of the index file to serve for directory requests.

```python
# Serve index.html for directories
StaticRouter(serve="./public", index_file="index.html")

# Custom index file
StaticRouter(serve="./public", index_file="default.htm")
```

When a directory path is requested (e.g., `/static/docs/`), the router will serve `index_file` from that directory (`./public/docs/index.html`).

### `retry_with_index` (optional)

Default: `False`

For S3 paths only. If `True` and the initial S3 GetObject fails, retry by appending the index file name.

```python
StaticRouter(
    serve="s3://my-bucket/site/",
    retry_with_index=True
)

# GET /about → tries:
#   1. s3://my-bucket/site/about
#   2. s3://my-bucket/site/about/index.html
```

Useful for static websites where paths like `/about` should serve `/about/index.html`.

## Attributes

### `directory` (PathType, local only)

Resolved absolute path to the local directory being served.

```python
router = StaticRouter(serve="./public")
print(router.directory)  # /home/user/project/public
```

### `is_s3` (bool)

Whether this router serves from S3 or local filesystem.

```python
local = StaticRouter(serve="./public")
print(local.is_s3)  # False

s3 = StaticRouter(serve="s3://bucket/")
print(s3.is_s3)  # True
```

### `s3_bucket` (str, S3 only)

S3 bucket name.

```python
router = StaticRouter(serve="s3://my-bucket/assets/")
print(router.s3_bucket)  # "my-bucket"
```

### `s3_prefix` (str, S3 only)

S3 key prefix (path within bucket).

```python
router = StaticRouter(serve="s3://my-bucket/assets/css/")
print(router.s3_prefix)  # "assets/css/"
```

## Methods

### `_serve_file(path: str) -> Response`

Internal method that serves a file from the configured location.

**Parameters:**
- `path` (str): Requested file path (relative to serve location)

**Returns:**
- `Response`: RestMachine response with file contents

**Behavior:**
- Normalizes and validates the path
- Prevents directory traversal attacks
- Detects MIME type from file extension
- Returns 404 if file not found
- Returns 500 on read errors

## HTTP Methods

### Allowed: GET

Only GET requests are handled. Static files are read-only.

```python
GET /static/style.css     # ✓ Returns file
HEAD /static/style.css    # ✓ Returns headers only
```

### Not Allowed: POST, PUT, DELETE, PATCH

All modification methods return `405 Method Not Allowed`.

```python
POST /static/file.txt     # ✗ 405
PUT /static/file.txt      # ✗ 405
DELETE /static/file.txt   # ✗ 405
PATCH /static/file.txt    # ✗ 405
```

## Response Headers

### Content-Type

Automatically detected from file extension:

| Extension | Content-Type |
|-----------|--------------|
| `.html` | `text/html` |
| `.css` | `text/css` |
| `.js` | `application/javascript` |
| `.json` | `application/json` |
| `.png` | `image/png` |
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.svg` | `image/svg+xml` |
| `.pdf` | `application/pdf` |
| `.txt` | `text/plain` |
| (unknown) | `application/octet-stream` |

### Content-Length

Set automatically based on file size.

## Security Features

### Path Traversal Prevention

Requested paths are normalized and validated to prevent directory traversal:

```python
# These are blocked (return 404):
GET /../../../etc/passwd
GET /..%2F..%2Fetc%2Fpasswd
GET /./../../secret.key
```

The router ensures all served files are within the configured `serve` directory.

### Path Normalization

Multiple slashes and relative path components are normalized:

```python
# All normalize to: /css/style.css
GET //css//style.css
GET /./css/./style.css
GET /css/../css/style.css
```

## Error Responses

### 404 Not Found

Returned when:
- File doesn't exist
- Directory requested without index file
- Path traversal detected

```python
# File doesn't exist
GET /static/nonexistent.txt  # 404

# Directory without index.html
GET /static/docs/  # 404 if docs/index.html doesn't exist

# Invalid path
GET /static/../../../etc/passwd  # 404
```

### 403 Forbidden

Returned for S3 access denied errors:

```python
# S3 object exists but no permission
GET /static/protected.pdf  # 403 if S3 returns AccessDenied
```

### 405 Method Not Allowed

Returned for non-GET requests:

```python
POST /static/file.txt    # 405
DELETE /static/file.txt  # 405
```

### 500 Internal Server Error

Returned for:
- S3 service errors
- File read errors
- Other unexpected errors

## Usage Examples

### Basic Local Files

```python
from restmachine import RestApplication
from restmachine_web import StaticRouter

app = RestApplication()

static = StaticRouter(serve="./public")
app.mount("/static", static)

# Serves:
# GET /static/index.html → ./public/index.html
# GET /static/css/app.css → ./public/css/app.css
```

### S3 with Prefix

```python
static = StaticRouter(serve="s3://my-bucket/assets/v1/")
app.mount("/assets", static)

# Serves:
# GET /assets/logo.png → s3://my-bucket/assets/v1/logo.png
# GET /assets/js/app.js → s3://my-bucket/assets/v1/js/app.js
```

### Multiple Mounts

```python
# Frontend app
frontend = StaticRouter(serve="./frontend/build")
app.mount("/app", frontend)

# Documentation
docs = StaticRouter(serve="./docs/html")
app.mount("/docs", docs)

# User uploads (S3)
uploads = StaticRouter(serve="s3://bucket/uploads/")
app.mount("/uploads", uploads)
```

### Custom Index File

```python
static = StaticRouter(
    serve="./public",
    index_file="home.html"  # Serve home.html instead of index.html
)
app.mount("/", static)

# GET / → ./public/home.html
# GET /about/ → ./public/about/home.html
```

### S3 Static Website

```python
static = StaticRouter(
    serve="s3://my-site/",
    index_file="index.html",
    retry_with_index=True  # Try path + index.html on failure
)
app.mount("/", static)

# GET /about → tries:
#   1. s3://my-site/about (fails)
#   2. s3://my-site/about/index.html (succeeds)
```

## Installation

Local filesystem only:

```bash
pip install restmachine-web
```

With S3 support:

```bash
pip install restmachine-web[s3]
```

This installs `boto3` for S3 access.

## See Also

- [Static Files Guide](../guides/static-files.md) - Usage guide and examples
- [Router (Core)](../../api/router.md) - Base router class
- [Application.mount()](../../api/application.md) - Mounting routers

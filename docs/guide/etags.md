# Conditional Requests (ETags)

Conditional requests using ETags and Last-Modified headers allow clients to cache resources efficiently and prevent lost updates with optimistic concurrency control. RestMachine provides built-in support for these HTTP caching mechanisms.

## Overview

**ETags** (Entity Tags) are identifiers assigned to specific versions of a resource. They enable:

- **Efficient Caching**: Clients can avoid downloading unchanged resources
- **Optimistic Concurrency**: Prevent conflicting updates to the same resource
- **Bandwidth Savings**: Return `304 Not Modified` instead of full responses

## Basic ETag Usage

### Generating ETags

Use the `@app.generate_etag` decorator to create ETags for your resources:

```python
from restmachine import RestApplication

app = RestApplication()

@app.resource_exists
def document(path_params, database):
    """Get document by ID, returns None if not found."""
    doc_id = path_params.get("doc_id")
    return database.get(doc_id)

@app.generate_etag
def document_etag(document):
    """Generate ETag based on document version."""
    if document:
        return f'"{document["id"]}-v{document["version"]}"'
    return None

@app.get("/documents/{doc_id}")
def get_document(document):
    """404 handled automatically by resource_exists decorator."""
    return document
```

### How It Works

1. Client requests a resource
2. Server generates an ETag and includes it in the `ETag` header
3. Client caches the resource with its ETag
4. On subsequent requests, client sends the ETag in conditional headers
5. Server returns `304 Not Modified` if the resource hasn't changed

## Conditional GET Requests

### If-None-Match Header

Clients use `If-None-Match` to check if a resource has changed:

```python
app = RestApplication()

@app.on_startup
def database():
    return {
        "documents": {
            "doc1": {"id": "doc1", "title": "Document 1", "version": 1}
        }
    }

@app.resource_exists
def document(path_params, database):
    doc_id = path_params.get("doc_id")
    return database["documents"].get(doc_id)

@app.generate_etag
def document_etag(document):
    """Generate ETag from document version."""
    if document:
        return f'"{document["version"]}"'
    return None

@app.get("/documents/{doc_id}")
def get_document(document):
    return document
```

**Request Flow:**

```http
# First request
GET /documents/doc1
Accept: application/json

# Response
HTTP/1.1 200 OK
ETag: "1"
Content-Type: application/json

{"id": "doc1", "title": "Document 1", "version": 1}

# Second request (with ETag)
GET /documents/doc1
Accept: application/json
If-None-Match: "1"

# Response (resource unchanged)
HTTP/1.1 304 Not Modified
ETag: "1"
```

## Optimistic Concurrency Control

### If-Match Header

Use `If-Match` to prevent lost updates - the request only succeeds if the ETag matches:

```python
app = RestApplication()

@app.on_startup
def database():
    return {
        "documents": {
            "doc1": {"id": "doc1", "content": "Original", "version": 1}
        }
    }

@app.resource_exists
def document(path_params, database):
    doc_id = path_params.get("doc_id")
    return database["documents"].get(doc_id)

@app.generate_etag
def document_etag(document):
    """Generate ETag from document version."""
    if document:
        return f'"{document["version"]}"'
    return None

@app.put("/documents/{doc_id}")
def update_document(document, json_body, path_params, database):
    """Update document and increment version."""
    doc_id = path_params["doc_id"]

    # Update the document
    database["documents"][doc_id].update(json_body)
    database["documents"][doc_id]["version"] += 1

    return database["documents"][doc_id]
```

**Request Flow:**

```http
# Update request with correct ETag
PUT /documents/doc1
Content-Type: application/json
If-Match: "1"

{"content": "Updated content"}

# Response (success)
HTTP/1.1 200 OK
ETag: "2"

{"id": "doc1", "content": "Updated content", "version": 2}

# Conflicting update with old ETag
PUT /documents/doc1
Content-Type: application/json
If-Match: "1"

{"content": "Conflicting update"}

# Response (precondition failed)
HTTP/1.1 412 Precondition Failed
```

## Last-Modified Headers

Use `@app.last_modified` for time-based conditional requests:

```python
from datetime import datetime

@app.last_modified
def document_modified_time(document):
    """Get last modified time of document."""
    if document:
        return document["updated_at"]
    return None

@app.get("/documents/{doc_id}")
def get_document(document):
    return document
```

**Request Flow:**

```http
# First request
GET /documents/doc1

# Response
HTTP/1.1 200 OK
Last-Modified: Wed, 21 Oct 2015 07:28:00 GMT

{"id": "doc1", "title": "Document 1"}

# Conditional request
GET /documents/doc1
If-Modified-Since: Wed, 21 Oct 2015 07:28:00 GMT

# Response (not modified)
HTTP/1.1 304 Not Modified
Last-Modified: Wed, 21 Oct 2015 07:28:00 GMT
```

## Combining ETags and Last-Modified

You can use both mechanisms together for maximum flexibility:

```python
from datetime import datetime

@app.generate_etag
def document_etag(document):
    """Generate ETag from document version."""
    if document:
        return f'"{document["version"]}"'
    return None

@app.last_modified
def document_modified_time(document):
    """Get last modified time of document."""
    if document:
        return document["updated_at"]
    return None

@app.get("/documents/{doc_id}")
def get_document(document):
    return document
```

The server checks both conditions and returns `304 Not Modified` only if both indicate the resource is unchanged.

## ETag Generation Strategies

### Version-Based ETags

Use version numbers for simple, predictable ETags:

```python
@app.generate_etag
def version_etag(document):
    """Generate ETag from version number."""
    if document:
        return f'"{document["version"]}"'
    return None
```

### Hash-Based ETags

Generate ETags from content hashes:

```python
import hashlib
import json

@app.generate_etag
def content_hash_etag(document):
    """Generate ETag from content hash."""
    if document:
        # Create hash of document content
        content = json.dumps(document, sort_keys=True)
        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f'"{hash_value}"'
    return None
```

### Timestamp-Based ETags

Use modification timestamps:

```python
@app.generate_etag
def timestamp_etag(document):
    """Generate ETag from timestamp."""
    if document:
        timestamp = int(document["updated_at"].timestamp())
        return f'"{timestamp}"'
    return None
```

## Complete Example: Blog API with ETags

```python
from restmachine import RestApplication
from datetime import datetime
import hashlib
import json

app = RestApplication()

# Database initialized at startup
@app.on_startup
def database():
    return {
        "posts": {
            1: {
                "id": 1,
                "title": "First Post",
                "content": "Hello, World!",
                "version": 1,
                "updated_at": datetime.now()
            }
        }
    }

@app.resource_exists
def post(path_params, database):
    """Get post by ID, returns None if not found."""
    post_id = path_params.get("post_id")
    if post_id:
        return database["posts"].get(int(post_id))
    return None

@app.generate_etag
def post_etag(post):
    """Generate ETag for blog posts."""
    if post:
        # Combine ID and version for ETag
        return f'"{post["id"]}-{post["version"]}"'
    return None

@app.last_modified
def post_last_modified(post):
    """Get last modified time for blog posts."""
    if post:
        return post["updated_at"]
    return None

@app.get("/posts/{post_id}")
def get_post(post):
    """Get a blog post. 404 and conditional requests handled automatically."""
    return post

@app.put("/posts/{post_id}")
def update_post(post, json_body, path_params, database):
    """Update a blog post (requires matching ETag via If-Match header)."""
    post_id = int(path_params["post_id"])

    # Update post and increment version
    database["posts"][post_id].update(json_body)
    database["posts"][post_id]["version"] += 1
    database["posts"][post_id]["updated_at"] = datetime.now()

    return database["posts"][post_id]

@app.post("/posts")
def create_post(json_body, database):
    """Create a new blog post."""
    post_id = max(database["posts"].keys()) + 1
    post = {
        "id": post_id,
        "version": 1,
        "updated_at": datetime.now(),
        **json_body
    }
    database["posts"][post_id] = post
    return post, 201
```

## Testing Conditional Requests

### Testing ETags

```python
from restmachine import Request, HTTPMethod

def test_etag_caching():
    app = create_blog_app()  # From example above

    # First request
    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    etag = response.headers.get("ETag")
    assert etag is not None

    # Conditional request with same ETag
    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={
            "Accept": "application/json",
            "If-None-Match": etag
        }
    )
    response = app.execute(request)

    # Should return 304 Not Modified
    assert response.status_code == 304
```

### Testing Optimistic Concurrency

```python
def test_concurrent_updates():
    app = create_blog_app()

    # Get current ETag
    response = app.execute(Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "application/json"}
    ))
    etag = response.headers.get("ETag")

    # First update succeeds
    response = app.execute(Request(
        method=HTTPMethod.PUT,
        path="/posts/1",
        headers={
            "Content-Type": "application/json",
            "If-Match": etag
        },
        body='{"title": "Updated Title"}'
    ))
    assert response.status_code == 200

    # Second update with old ETag fails
    response = app.execute(Request(
        method=HTTPMethod.PUT,
        path="/posts/1",
        headers={
            "Content-Type": "application/json",
            "If-Match": etag  # Old ETag
        },
        body='{"title": "Conflicting Update"}'
    ))
    assert response.status_code == 412  # Precondition Failed
```

## Best Practices

### 1. Always Quote ETags

ETags should be quoted strings per HTTP specification:

```python
# Good
return f'"{version}"'

# Bad
return str(version)
```

### 2. Use Strong ETags

Strong ETags indicate byte-for-byte equality:

```python
# Strong ETag (default)
return '"abc123"'

# Weak ETag (indicates semantic equivalence)
return 'W/"abc123"'
```

### 3. Invalidate ETags on Updates

Increment version or regenerate hash after any modification:

```python
@app.put("/documents/{doc_id}")
def update_document(document, json_body, path_params, database):
    doc_id = path_params["doc_id"]
    database["documents"][doc_id].update(json_body)
    # IMPORTANT: Invalidate the ETag
    database["documents"][doc_id]["version"] += 1
    return database["documents"][doc_id]
```

### 4. Handle Missing ETags Gracefully

Not all resources need ETags:

```python
@app.dependency()
def resource_path(request):
    return request.path

@app.generate_etag
def maybe_etag(resource_path):
    # Return None if ETag doesn't make sense
    if resource_path.startswith("/stream/"):
        return None  # Streaming resources don't use ETags
    # Otherwise generate ETag
    return generate_etag_for_resource()
```

## HTTP Status Codes

| Status | Meaning | When Used |
|--------|---------|-----------|
| 200 OK | Resource returned | ETag doesn't match or no conditional header |
| 304 Not Modified | Resource unchanged | If-None-Match matches current ETag |
| 412 Precondition Failed | Condition not met | If-Match doesn't match current ETag |

## Next Steps

- Learn about [Multi-Value Headers](../advanced/headers.md) for advanced header handling
- Explore [Performance Optimization](../advanced/performance.md) with caching strategies
- Read about [State Machine](../advanced/state-machine.md) for understanding conditional request flow

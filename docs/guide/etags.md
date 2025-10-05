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

@app.generate_etag
def document_etag(request):
    """Generate ETag based on document version."""
    doc_id = request.path_params.get("doc_id")
    document = database.get(doc_id)
    if document:
        return f'"{doc_id}-v{document["version"]}"'
    return None

@app.get("/documents/{doc_id}")
def get_document(request):
    doc_id = request.path_params["doc_id"]
    return database.get(doc_id)
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

documents = {
    "doc1": {"id": "doc1", "title": "Document 1", "version": 1}
}

@app.generate_etag
def document_etag(request):
    doc_id = request.path_params.get("doc_id")
    if doc_id in documents:
        return f'"{documents[doc_id]["version"]}"'
    return None

@app.resource_exists
def document_exists(request):
    doc_id = request.path_params.get("doc_id")
    return documents.get(doc_id)

@app.get("/documents/{doc_id}")
def get_document(document_exists):
    return document_exists
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

documents = {
    "doc1": {"id": "doc1", "content": "Original", "version": 1}
}

@app.generate_etag
def document_etag(request):
    doc_id = request.path_params.get("doc_id")
    if doc_id in documents:
        version = documents[doc_id]["version"]
        return f'"{version}"'
    return None

@app.resource_exists
def document_exists(request):
    doc_id = request.path_params.get("doc_id")
    return documents.get(doc_id)

@app.put("/documents/{doc_id}")
def update_document(document_exists, json_body, request):
    """Update document and increment version."""
    doc_id = request.path_params["doc_id"]

    # Update the document
    documents[doc_id].update(json_body)
    documents[doc_id]["version"] += 1

    return documents[doc_id]
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
def document_modified_time(request):
    """Get last modified time of document."""
    doc_id = request.path_params.get("doc_id")
    if doc_id in documents:
        return documents[doc_id]["updated_at"]
    return None

@app.get("/documents/{doc_id}")
def get_document(document_exists):
    return document_exists
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
def document_etag(request):
    doc_id = request.path_params.get("doc_id")
    if doc_id in documents:
        return f'"{documents[doc_id]["version"]}"'
    return None

@app.last_modified
def document_modified_time(request):
    doc_id = request.path_params.get("doc_id")
    if doc_id in documents:
        return documents[doc_id]["updated_at"]
    return None

@app.get("/documents/{doc_id}")
def get_document(document_exists):
    return document_exists
```

The server checks both conditions and returns `304 Not Modified` only if both indicate the resource is unchanged.

## ETag Generation Strategies

### Version-Based ETags

Use version numbers for simple, predictable ETags:

```python
@app.generate_etag
def version_etag(document_exists):
    """Generate ETag from version number."""
    if document_exists:
        return f'"{document_exists["version"]}"'
    return None
```

### Hash-Based ETags

Generate ETags from content hashes:

```python
import hashlib
import json

@app.generate_etag
def content_hash_etag(document_exists):
    """Generate ETag from content hash."""
    if document_exists:
        # Create hash of document content
        content = json.dumps(document_exists, sort_keys=True)
        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f'"{hash_value}"'
    return None
```

### Timestamp-Based ETags

Use modification timestamps:

```python
@app.generate_etag
def timestamp_etag(document_exists):
    """Generate ETag from timestamp."""
    if document_exists:
        timestamp = int(document_exists["updated_at"].timestamp())
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

# Simple in-memory blog post storage
posts = {
    1: {
        "id": 1,
        "title": "First Post",
        "content": "Hello, World!",
        "version": 1,
        "updated_at": datetime.now()
    }
}

@app.generate_etag
def post_etag(request):
    """Generate ETag for blog posts."""
    post_id = request.path_params.get("post_id")
    if post_id and int(post_id) in posts:
        post = posts[int(post_id)]
        # Combine ID and version for ETag
        return f'"{post["id"]}-{post["version"]}"'
    return None

@app.last_modified
def post_last_modified(request):
    """Get last modified time for blog posts."""
    post_id = request.path_params.get("post_id")
    if post_id and int(post_id) in posts:
        return posts[int(post_id)]["updated_at"]
    return None

@app.resource_exists
def post_exists(request):
    """Check if post exists."""
    post_id = request.path_params.get("post_id")
    if post_id:
        return posts.get(int(post_id))
    return None

@app.get("/posts/{post_id}")
def get_post(post_exists):
    """Get a blog post (supports conditional requests)."""
    return post_exists

@app.put("/posts/{post_id}")
def update_post(post_exists, json_body, request):
    """Update a blog post (requires matching ETag)."""
    post_id = int(request.path_params["post_id"])

    # Update post and increment version
    posts[post_id].update(json_body)
    posts[post_id]["version"] += 1
    posts[post_id]["updated_at"] = datetime.now()

    return posts[post_id]

@app.post("/posts")
def create_post(json_body):
    """Create a new blog post."""
    post_id = max(posts.keys()) + 1
    post = {
        "id": post_id,
        "version": 1,
        "updated_at": datetime.now(),
        **json_body
    }
    posts[post_id] = post
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
def update_document(document_exists, json_body, request):
    doc_id = request.path_params["doc_id"]
    documents[doc_id].update(json_body)
    # IMPORTANT: Invalidate the ETag
    documents[doc_id]["version"] += 1
    return documents[doc_id]
```

### 4. Handle Missing ETags Gracefully

Not all resources need ETags:

```python
@app.generate_etag
def maybe_etag(request):
    # Return None if ETag doesn't make sense
    if request.path.startswith("/stream/"):
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

# Content Negotiation

Content negotiation allows clients to request resources in different formats (JSON, HTML, XML, etc.) using the HTTP `Accept` header. RestMachine provides built-in support for content negotiation with automatic format selection and rendering.

## Overview

**Content negotiation** enables a single endpoint to serve multiple representations of the same resource:

- **JSON** for API clients
- **HTML** for web browsers
- **XML** for legacy systems
- **Plain text** for simple clients
- **Custom formats** as needed

RestMachine selects the appropriate format based on the `Accept` header and returns `406 Not Acceptable` if the requested format isn't supported.

## Basic Usage

### The Accept Header

Clients specify their preferred format using the `Accept` header:

```http
GET /users/123
Accept: application/json
```

```http
GET /users/123
Accept: text/html
```

### Default JSON Rendering

By default, RestMachine automatically renders responses as JSON:

```python
from restmachine import RestApplication

app = RestApplication()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": "Alice", "email": "alice@example.com"}
```

**Request:**
```http
GET /users/123
Accept: application/json
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"id": 123, "name": "Alice", "email": "alice@example.com"}
```

## Multiple Response Formats

Use the `@app.renders` decorator to support multiple content types:

```python
from restmachine import RestApplication

app = RestApplication()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Return user data in the requested format."""
    return {
        "id": user_id,
        "name": "Alice",
        "email": "alice@example.com"
    }

@app.renders("text/html")
def render_user_html(get_user):
    """Render user as HTML."""
    user = get_user
    return f"""
    <div class="user">
        <h1>{user['name']}</h1>
        <p>ID: {user['id']}</p>
        <p>Email: {user['email']}</p>
    </div>
    """

@app.renders("text/plain")
def render_user_text(get_user):
    """Render user as plain text."""
    user = get_user
    return f"User {user['id']}: {user['name']} ({user['email']})"

@app.renders("application/xml")
def render_user_xml(get_user):
    """Render user as XML."""
    user = get_user
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<user>
    <id>{user['id']}</id>
    <name>{user['name']}</name>
    <email>{user['email']}</email>
</user>"""
```

### How It Works

1. **Route handler** returns the raw data (dictionary)
2. **Renderers** transform the data based on the `Accept` header
3. **RestMachine** selects the appropriate renderer automatically
4. **Response** is returned with the correct `Content-Type` header

### Renderer Dependency Injection

Renderers receive the route handler's return value as a dependency. The parameter name must match the handler function name:

```python
@app.get("/data")
def get_data():  # Handler name is "get_data"
    return {"value": 42}

@app.renders("text/html")
def render_html(get_data):  # Parameter name matches handler
    data = get_data
    return f"<p>Value: {data['value']}</p>"
```

## Quality Values

Clients can specify format preferences using quality values (`q`):

```http
Accept: text/html;q=0.9, application/json;q=1.0, text/plain;q=0.8
```

RestMachine selects the format with the highest quality value that's supported:

```python
app = RestApplication()

@app.get("/resource")
def get_resource():
    return {"message": "Hello"}

@app.renders("text/html")
def render_html(get_resource):
    return f"<h1>{get_resource['message']}</h1>"

@app.renders("text/plain")
def render_text(get_resource):
    return get_resource['message']
```

**Request with quality values:**
```http
GET /resource
Accept: text/html;q=0.9, application/json;q=1.0, text/plain;q=0.8
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"message": "Hello"}
```

RestMachine chose JSON because it has the highest quality value (`q=1.0`).

## Wildcard Accept Headers

### Accept All (`*/*`)

The `*/*` wildcard accepts any content type:

```http
GET /resource
Accept: */*
```

RestMachine will return the first available renderer (typically the route handler's default JSON response).

### Partial Wildcards Not Supported

RestMachine does not support partial wildcards like `text/*`:

```http
GET /resource
Accept: text/*
```

**Response:**
```http
HTTP/1.1 406 Not Acceptable
```

## Multiple Accept Types

When multiple types are specified, RestMachine selects the first available one:

```http
Accept: application/pdf, text/html, application/json
```

If `application/pdf` isn't supported but `text/html` is, RestMachine will return HTML.

## 406 Not Acceptable

When the client requests an unsupported format, RestMachine returns `406 Not Acceptable`:

```python
app = RestApplication()

@app.get("/data")
def get_data():
    return {"value": 123}

@app.renders("text/html")
def render_html(get_data):
    return f"<p>{get_data['value']}</p>"
```

**Request:**
```http
GET /data
Accept: application/pdf
```

**Response:**
```http
HTTP/1.1 406 Not Acceptable
Content-Type: text/plain

Not Acceptable
```

## Using Templates

Combine content negotiation with Jinja2 templates for rich HTML rendering:

```python
from restmachine import RestApplication, render

app = RestApplication()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {
        "id": user_id,
        "name": "Alice",
        "email": "alice@example.com",
        "bio": "Software engineer"
    }

@app.renders("text/html")
def render_user_html(get_user):
    """Render user with a template."""
    return render(
        template="user.html",
        package="templates",
        user=get_user
    )
```

**templates/user.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ user.name }}</title>
</head>
<body>
    <div class="user-profile">
        <h1>{{ user.name }}</h1>
        <p class="user-id">ID: {{ user.id }}</p>
        <p class="user-email">Email: {{ user.email }}</p>
        <p class="user-bio">{{ user.bio }}</p>
    </div>
</body>
</html>
```

**Request:**
```http
GET /users/123
Accept: text/html
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
    <title>Alice</title>
</head>
<body>
    <div class="user-profile">
        <h1>Alice</h1>
        <p class="user-id">ID: 123</p>
        <p class="user-email">Email: alice@example.com</p>
        <p class="user-bio">Software engineer</p>
    </div>
</body>
</html>
```

## Complete Example: Blog API

```python
from restmachine import RestApplication, render
from datetime import datetime

app = RestApplication()

# Sample blog posts
posts = {
    1: {
        "id": 1,
        "title": "Getting Started with RestMachine",
        "content": "RestMachine is a modern REST framework...",
        "author": "Alice",
        "created_at": datetime(2024, 1, 15)
    },
    2: {
        "id": 2,
        "title": "Content Negotiation Best Practices",
        "content": "Content negotiation allows...",
        "author": "Bob",
        "created_at": datetime(2024, 1, 20)
    }
}

@app.get("/posts")
def list_posts():
    """List all blog posts."""
    return list(posts.values())

@app.renders("text/html")
def render_posts_html(list_posts):
    """Render posts list as HTML."""
    posts_list = list_posts
    return render(
        inline="""
        <!DOCTYPE html>
        <html>
        <head><title>Blog Posts</title></head>
        <body>
            <h1>Blog Posts</h1>
            <ul>
            {% for post in posts %}
                <li>
                    <h2>{{ post.title }}</h2>
                    <p>by {{ post.author }} on {{ post.created_at.strftime('%Y-%m-%d') }}</p>
                    <p>{{ post.content[:100] }}...</p>
                </li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """,
        posts=posts_list
    )

@app.renders("text/plain")
def render_posts_text(list_posts):
    """Render posts list as plain text."""
    posts_list = list_posts
    lines = ["BLOG POSTS\n" + "="*50 + "\n"]
    for post in posts_list:
        lines.append(f"{post['title']}")
        lines.append(f"By {post['author']} on {post['created_at'].strftime('%Y-%m-%d')}")
        lines.append(f"{post['content'][:100]}...")
        lines.append("-" * 50)
    return "\n".join(lines)

@app.renders("application/xml")
def render_posts_xml(list_posts):
    """Render posts list as XML."""
    posts_list = list_posts
    xml_posts = []
    for post in posts_list:
        xml_posts.append(f"""
        <post>
            <id>{post['id']}</id>
            <title>{post['title']}</title>
            <author>{post['author']}</author>
            <content>{post['content']}</content>
            <created_at>{post['created_at'].isoformat()}</created_at>
        </post>
        """)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<posts>
    {''.join(xml_posts)}
</posts>"""

@app.get("/posts/{post_id}")
def get_post(post_id: int):
    """Get a single blog post."""
    return posts.get(post_id)

@app.renders("text/html")
def render_post_html(get_post):
    """Render single post as HTML."""
    post = get_post
    if not post:
        return "<h1>Post Not Found</h1>", 404

    return render(
        inline="""
        <!DOCTYPE html>
        <html>
        <head><title>{{ post.title }}</title></head>
        <body>
            <article>
                <h1>{{ post.title }}</h1>
                <p class="meta">By {{ post.author }} on {{ post.created_at.strftime('%Y-%m-%d') }}</p>
                <div class="content">{{ post.content }}</div>
            </article>
        </body>
        </html>
        """,
        post=post
    )
```

## Testing Content Negotiation

### Testing Different Formats

```python
from restmachine import Request, HTTPMethod

def test_json_response():
    app = create_blog_app()

    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/json"
    data = json.loads(response.body)
    assert data["title"] == "Getting Started with RestMachine"

def test_html_response():
    app = create_blog_app()

    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "text/html"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "text/html"
    assert "<h1>Getting Started with RestMachine</h1>" in response.body

def test_xml_response():
    app = create_blog_app()

    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "application/xml"}
    )
    response = app.execute(request)

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/xml"
    assert "<title>Getting Started with RestMachine</title>" in response.body
```

### Testing Quality Values

```python
def test_quality_values():
    app = create_blog_app()

    # Prefer JSON over HTML
    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "text/html;q=0.9, application/json;q=1.0"}
    )
    response = app.execute(request)

    assert response.headers.get("Content-Type") == "application/json"
```

### Testing Unsupported Formats

```python
def test_unsupported_format():
    app = create_blog_app()

    request = Request(
        method=HTTPMethod.GET,
        path="/posts/1",
        headers={"Accept": "application/pdf"}
    )
    response = app.execute(request)

    assert response.status_code == 406  # Not Acceptable
```

## Best Practices

### 1. Keep Renderers Simple

Renderers should focus on formatting, not business logic:

```python
# Good
@app.renders("text/html")
def render_html(get_user):
    user = get_user
    return f"<h1>{user['name']}</h1>"

# Bad - doing business logic in renderer
@app.renders("text/html")
def render_html_bad(request):
    user = database.get_user(request.path_params['user_id'])
    user['processed'] = True  # Don't modify data in renderer
    return f"<h1>{user['name']}</h1>"
```

### 2. Use Templates for Complex HTML

For anything beyond simple HTML, use templates:

```python
@app.renders("text/html")
def render_html(get_resource):
    return render(
        template="resource.html",
        package="templates",
        resource=get_resource
    )
```

### 3. Provide JSON as Default

Always support JSON for API clients:

```python
@app.get("/resource")
def get_resource():
    return {"data": "value"}  # Automatically JSON

@app.renders("text/html")  # Add HTML as an option
def render_html(get_resource):
    return f"<p>{get_resource['data']}</p>"
```

### 4. Handle Missing Resources Consistently

Return appropriate status codes in all renderers:

```python
@app.get("/posts/{post_id}")
def get_post(post_id: int):
    post = posts.get(post_id)
    if not post:
        return None, 404
    return post

@app.renders("text/html")
def render_post_html(get_post):
    post = get_post
    if not post:
        return "<h1>404 - Post Not Found</h1>", 404
    return f"<h1>{post['title']}</h1>"
```

### 5. Document Supported Formats

Make it clear which formats your API supports:

```python
@app.get("/api/docs")
def api_docs():
    """
    API Documentation

    Supported formats:
    - application/json (default)
    - text/html (web interface)
    - application/xml (legacy systems)
    """
    return {
        "supported_formats": [
            "application/json",
            "text/html",
            "application/xml"
        ]
    }
```

## Content Types Reference

| Content Type | Common Use Case | Example |
|--------------|----------------|---------|
| `application/json` | API responses (default) | `{"id": 1, "name": "Alice"}` |
| `text/html` | Web pages | `<h1>Alice</h1>` |
| `text/plain` | Simple text | `User: Alice` |
| `application/xml` | Legacy systems | `<user><name>Alice</name></user>` |
| `text/csv` | Data export | `id,name\n1,Alice` |
| `application/pdf` | Documents | Binary PDF data |

## HTTP Status Codes

| Status | Meaning | When Used |
|--------|---------|-----------|
| 200 OK | Success | Requested format is available and returned |
| 406 Not Acceptable | Unsupported format | Client requested a format that's not supported |

## Next Steps

- Learn about [Template Rendering](../advanced/templates.md) for advanced HTML generation
- Explore [Error Handling](error-handling.md) for custom error formats
- Read about [Testing](testing.md) to test multiple content types

# Template Rendering with Jinja2

RestMachine now includes built-in support for Jinja2 template rendering, providing Rails-like view capabilities for your REST APIs.

## Overview

The `render()` helper function allows you to:
- Render HTML templates from files or inline strings
- Use Jinja2's powerful templating features (inheritance, filters, etc.)
- Control autoescape settings for security
- Organize templates in custom packages/directories

## Installation

Jinja2 is now a core dependency of RestMachine:

```bash
pip install restmachine
```

Or if installing from source:

```bash
pip install -r requirements.txt
```

## Basic Usage

### Inline Templates

The simplest way to use templates is with inline strings:

```python
from restmachine import RestApplication, render

app = RestApplication()

@app.get("/hello/{name}")
def hello(name: str):
    return render(
        inline="<h1>Hello, {{ name }}!</h1>",
        name=name
    )
```

### File-Based Templates

Create a `views` directory in your project and add template files:

```
your-project/
├── views/
│   ├── __init__.py
│   ├── base.html
│   └── user_detail.html
├── app.py
└── ...
```

**Note**: The `views` directory should be in your application, not in the restmachine library. You control where templates are stored using the `package` parameter.

Then use them in your routes:

```python
@app.get("/user/{user_id}")
def get_user(user_id: str):
    user = {"id": user_id, "name": "John Doe", "email": "john@example.com"}
    return user

@app.renders("text/html")
def user_html(get_user):
    return render(
        template="user_detail.html",
        user=get_user
    )
```

## Function Signature

```python
def render(
    template: Optional[str] = None,
    package: str = "views",
    unsafe: bool = False,
    inline: Optional[str] = None,
    **kwargs: Any
) -> str
```

### Parameters

- **`template`**: Path to the template file relative to the package/views directory. Ignored if `inline` is provided.

- **`package`**: Package name or directory path for templates. Defaults to `"views"`.
  - Can be a Python package name (uses `PackageLoader`)
  - Can be a directory path (uses `FileSystemLoader`)
  - The function automatically detects which to use

- **`unsafe`**: Controls autoescape behavior. Defaults to `False`.
  - `False` (default): Autoescape is **enabled** (safe, recommended)
  - `True`: Autoescape is **disabled** (use with caution for trusted HTML)

- **`inline`**: Optional inline template string. If provided, renders this instead of loading from a file.

- **`**kwargs`**: Variables to pass to the template context for rendering.

## Template Examples

### Using Template Inheritance

**views/base.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My API{% endblock %}</title>
    {% block styles %}
    <style>
        body { font-family: Arial, sans-serif; }
    </style>
    {% endblock %}
</head>
<body>
    <header>
        <h1>{% block header %}API{% endblock %}</h1>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

**views/user_detail.html:**
```html
{% extends "base.html" %}

{% block title %}User: {{ user.name }}{% endblock %}

{% block header %}User Details{% endblock %}

{% block content %}
<div class="user">
    <h2>{{ user.name }}</h2>
    <p>Email: {{ user.email }}</p>
    <p>ID: {{ user.id }}</p>
</div>
{% endblock %}
```

### Using in Route Handlers

```python
from restmachine import RestApplication, render

app = RestApplication()

# Example 1: Simple inline template
@app.get("/welcome")
def welcome():
    return render(
        inline="<h1>Welcome to {{ app_name }}!</h1>",
        app_name="My API"
    )

# Example 2: File-based template with data
@app.get("/posts/{post_id}")
def get_post(post_id: str):
    post = {
        "id": post_id,
        "title": "My Post",
        "content": "Post content here..."
    }
    return post

@app.renders("text/html")
def post_html(get_post):
    return render(
        template="post_detail.html",
        post=get_post
    )

# Example 3: List rendering
@app.get("/users")
def list_users():
    users = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"}
    ]
    return users

@app.renders("text/html")
def users_html(list_users):
    return render(
        template="list.html",
        title="Users",
        items=list_users
    )
```

### Unsafe HTML (Raw Content)

When you need to render trusted HTML content without escaping:

```python
@app.get("/content/{id}")
def get_content(id: str):
    return {
        "title": "Rich Content",
        "html": "<strong>Bold</strong> and <em>italic</em> text"
    }

@app.renders("text/html")
def content_html(get_content):
    data = get_content
    # Using unsafe=True to disable autoescape
    return render(
        inline="""
        <h1>{{ title }}</h1>
        <div>{{ html|safe }}</div>
        """,
        title=data["title"],
        html=data["html"]
    )
```

**Security Note**: Only use `unsafe=True` or the `|safe` filter with trusted content!

### Custom Template Directory

You can specify a custom template directory:

```python
# Using a relative path
render(template="dashboard.html", package="./admin_templates", stats=stats)

# Using an absolute path
render(template="report.html", package="/var/app/templates", data=data)

# Using a different Python package
render(template="email.html", package="myapp.email_templates", user=user)
```

## Jinja2 Features

You have access to all Jinja2 features:

### Filters
```html
{{ user.name|upper }}
{{ post.content|safe }}
{{ date|default('N/A') }}
```

### Control Structures
```html
{% if user.is_admin %}
    <p>Admin user</p>
{% endif %}

{% for item in items %}
    <li>{{ item.name }}</li>
{% endfor %}
```

### Template Inheritance
```html
{% extends "base.html" %}
{% block content %}
    <!-- Your content -->
{% endblock %}
```

### Includes
```html
{% include "partials/header.html" %}
```

### Macros
```html
{% macro render_user(user) %}
    <div class="user">{{ user.name }}</div>
{% endmacro %}

{{ render_user(current_user) }}
```

## Directory Structure

When using file-based templates, organize them in your application (not in the restmachine library):

```
your-application/
├── views/                    # Your templates directory
│   ├── __init__.py
│   ├── base.html
│   ├── users/
│   │   └── detail.html
│   └── posts/
│       └── detail.html
├── app.py                    # Your application
└── requirements.txt
```

The restmachine library's `examples/views/` directory contains example templates for reference only.

## Complete Example

See `examples/template_example.py` in the restmachine repository for a comprehensive example showing:
- Inline templates
- File-based templates
- Template inheritance
- List rendering
- Content negotiation (HTML vs JSON)
- Unsafe HTML rendering

## Migration Guide

### From Hard-Coded HTML

**Before:**
```python
@app.renders("text/html")
def user_html(get_user):
    user = get_user
    return f"<h1>{user['name']}</h1><p>{user['email']}</p>"
```

**After:**
```python
@app.renders("text/html")
def user_html(get_user):
    return render(
        inline="<h1>{{ user.name }}</h1><p>{{ user.email }}</p>",
        user=get_user
    )
```

Or with a template file:
```python
@app.renders("text/html")
def user_html(get_user):
    return render(template="user.html", user=get_user)
```

## Best Practices

1. **Use Template Files**: For anything beyond simple snippets, use file-based templates for better maintainability.

2. **Enable Autoescape**: Keep `unsafe=False` (default) for security. Only use `unsafe=True` for trusted content.

3. **Organize Templates**: Use a consistent directory structure:
   ```
   views/
   ├── base.html
   ├── layouts/
   │   └── app.html
   ├── users/
   │   ├── index.html
   │   └── show.html
   └── posts/
       ├── index.html
       └── show.html
   ```

4. **Template Inheritance**: Use base templates to avoid repetition:
   ```html
   {% extends "base.html" %}
   ```

5. **Content Negotiation**: Combine with RestMachine's content negotiation:
   ```python
   @app.get("/users")
   def list_users():
       return users  # Returns JSON by default

   @app.renders("text/html")
   def users_html(list_users):
       return render(template="users.html", users=list_users)
   ```

## Troubleshooting

### Template Not Found

If you get a "template not found" error:

1. Check that the `views` directory exists and contains `__init__.py`
2. Verify the template path is correct
3. Try using an absolute path for the `package` parameter
4. Ensure the template file has the correct extension (`.html`)

### Escaping Issues

If HTML is being escaped when it shouldn't be:
- Use the `|safe` filter in the template: `{{ content|safe }}`
- Or set `unsafe=True` in the `render()` call (use with caution)

### Import Errors

If you get Jinja2 import errors:
```bash
pip install jinja2>=3.0.0
```

## API Reference

For the complete API reference, see:
- `restmachine.template_helpers.render()` - Main rendering function
- `restmachine.HTMLRenderer` - HTML content renderer (now uses Jinja2)

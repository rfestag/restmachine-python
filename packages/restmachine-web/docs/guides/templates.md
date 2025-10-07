# Template Rendering

RestMachine Web works seamlessly with template engines like Jinja2 for rendering HTML, XML, and other text-based formats.

## Quick Start

Install Jinja2:

```bash
pip install jinja2
```

Basic template rendering:

```python
from restmachine import RestApplication
from jinja2 import Environment, FileSystemLoader
import os

app = RestApplication()

# Configure Jinja2
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=True
)

@app.dependency()
def templates():
    """Provide Jinja2 environment."""
    return jinja_env

@app.get('/hello/{name}')
def hello_html(request, templates):
    """Render HTML template."""
    template = templates.get_template('hello.html')
    name = request.path_params['name']

    html = template.render(name=name)

    return html, 200, {'Content-Type': 'text/html'}
```

Template file (`templates/hello.html`):

```html
<!DOCTYPE html>
<html>
<head>
    <title>Hello {{ name }}</title>
</head>
<body>
    <h1>Hello, {{ name }}!</h1>
</body>
</html>
```

## Complete Guide

For comprehensive template rendering documentation, including:

- Helper dependencies for cleaner code
- Full HTML page rendering
- Template inheritance
- Custom filters and functions
- Error handling
- Best practices

See the [Template Rendering guide](../../advanced/templates.md) in the main documentation.

## Combining Templates with Static Files

Serve both static files and rendered templates:

```python
from restmachine import RestApplication
from restmachine_web import StaticRouter
from jinja2 import Environment, FileSystemLoader
import os

app = RestApplication()

# Static files (CSS, JS, images)
static = StaticRouter(serve="./public")
app.mount("/static", static)

# Templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=True
)

@app.dependency()
def templates():
    return jinja_env

@app.get('/')
def home(templates):
    """Render home page."""
    template = templates.get_template('home.html')
    html = template.render(
        title="Home",
        message="Welcome to RestMachine"
    )
    return html, 200, {'Content-Type': 'text/html'}

@app.get('/about')
def about(templates):
    """Render about page."""
    template = templates.get_template('about.html')
    html = template.render(title="About")
    return html, 200, {'Content-Type': 'text/html'}
```

Template with static assets (`templates/home.html`):

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <h1>{{ message }}</h1>
    <script src="/static/js/app.js"></script>
</body>
</html>
```

Directory structure:

```
project/
├── app.py
├── templates/
│   ├── home.html
│   └── about.html
└── public/
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

## Template Helper

Create a reusable template helper:

```python
@app.dependency()
def render_template(templates):
    """Helper for rendering templates with default context."""
    def render(template_name: str, **context):
        template = templates.get_template(template_name)
        # Add common context variables
        context.setdefault('site_name', 'My Site')
        context.setdefault('year', 2025)
        return template.render(**context)
    return render

@app.get('/users')
def list_users(database, render_template):
    """Render users list."""
    users = database.get_users()
    html = render_template('users.html', users=users)
    return html, 200, {'Content-Type': 'text/html'}
```

## API + HTML Pages

Serve both API and HTML from the same application:

```python
from restmachine import RestApplication
from restmachine_web import StaticRouter

app = RestApplication()

# API routes (JSON)
@app.get('/api/users')
def api_users(database):
    """JSON API endpoint."""
    users = database.get_users()
    return {"users": users}

@app.get('/api/users/{user_id}')
def api_user(user_id: str, database):
    """Get single user as JSON."""
    user = database.get_user(user_id)
    return user or ({"error": "Not found"}, 404)

# HTML routes
@app.get('/users')
def html_users(database, render_template):
    """HTML page listing users."""
    users = database.get_users()
    html = render_template('users.html', users=users)
    return html, 200, {'Content-Type': 'text/html'}

@app.get('/users/{user_id}')
def html_user(user_id: str, database, render_template):
    """HTML page for single user."""
    user = database.get_user(user_id)
    if not user:
        return render_template('404.html'), 404

    html = render_template('user.html', user=user)
    return html, 200, {'Content-Type': 'text/html'}

# Static files
static = StaticRouter(serve="./public")
app.mount("/static", static)
```

Access:

- `/api/users` → JSON response
- `/users` → HTML page
- `/api/users/123` → JSON response
- `/users/123` → HTML page
- `/static/css/style.css` → Static file

## See Also

- [Template Rendering (Main Docs)](../../advanced/templates.md) - Complete template guide
- [Static Files](static-files.md) - Serving static assets
- [Content Negotiation](../../guide/content-negotiation.md) - Serve JSON and HTML from the same endpoint

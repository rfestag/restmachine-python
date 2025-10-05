# Template Rendering

RestMachine supports template rendering for generating HTML, XML, and other text-based formats. This guide covers Jinja2 integration, template-based responses, and custom renderers.

## Jinja2 Integration

### Setup

Install Jinja2 for template rendering:

```bash
pip install jinja2
```

### Basic Template Rendering

Create a simple template rendering system:

```python
from restmachine import RestApplication, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

app = RestApplication()

# Configure Jinja2
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

@app.dependency()
def templates():
    """Provide Jinja2 environment."""
    return jinja_env

@app.get('/hello/{name}')
def hello_html(request: Request, templates):
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
    <p>Welcome to RestMachine</p>
</body>
</html>
```

### Template Helper Dependency

Create a template helper for cleaner code:

```python
@app.dependency()
def render_template(templates):
    """Template rendering helper."""
    def render(template_name: str, **context):
        template = templates.get_template(template_name)
        return template.render(**context)
    return render

@app.get('/users')
def list_users(database, render_template):
    """Render users list as HTML."""
    users = database["users"]

    html = render_template('users.html', users=users)

    return html, 200, {'Content-Type': 'text/html'}
```

## HTML Responses

### Full HTML Pages

Render complete HTML pages:

```python
@app.get('/dashboard')
def dashboard(current_user, database, render_template):
    """User dashboard."""
    stats = {
        'total_users': len(database['users']),
        'total_posts': len(database['posts']),
        'user_name': current_user['name']
    }

    html = render_template('dashboard.html', **stats)

    return html, 200, {'Content-Type': 'text/html'}
```

Template (`templates/dashboard.html`):

```html
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - {{ user_name }}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <nav>
        <h1>Dashboard</h1>
        <p>Welcome, {{ user_name }}</p>
    </nav>

    <main>
        <div class="stats">
            <div class="stat">
                <h2>{{ total_users }}</h2>
                <p>Total Users</p>
            </div>
            <div class="stat">
                <h2>{{ total_posts }}</h2>
                <p>Total Posts</p>
            </div>
        </div>
    </main>
</body>
</html>
```

### Template Inheritance

Use base templates for consistent layout:

Base template (`templates/base.html`):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}RestMachine App{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    {% block head %}{% endblock %}
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/users">Users</a>
            <a href="/posts">Posts</a>
        </nav>
    </header>

    <main>
        {% block content %}{% endblock %}
    </main>

    <footer>
        <p>&copy; 2024 RestMachine App</p>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>
```

Child template (`templates/users.html`):

```html
{% extends "base.html" %}

{% block title %}Users - RestMachine App{% endblock %}

{% block content %}
<h1>Users</h1>

<table>
    <thead>
        <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
        </tr>
    </thead>
    <tbody>
        {% for user in users %}
        <tr>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.role }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### Partial Templates

Use includes for reusable components:

```python
@app.get('/posts')
def list_posts(database, render_template):
    """Render posts with pagination."""
    posts = database["posts"]

    html = render_template(
        'posts.html',
        posts=posts,
        page=1,
        total_pages=5
    )

    return html, 200, {'Content-Type': 'text/html'}
```

Template with includes (`templates/posts.html`):

```html
{% extends "base.html" %}

{% block content %}
<h1>Posts</h1>

{% for post in posts %}
    {% include "partials/post_card.html" %}
{% endfor %}

{% include "partials/pagination.html" %}
{% endblock %}
```

Partial (`templates/partials/post_card.html`):

```html
<article class="post-card">
    <h2>{{ post.title }}</h2>
    <p class="meta">By {{ post.author }} on {{ post.created_at }}</p>
    <p>{{ post.excerpt }}</p>
    <a href="/posts/{{ post.id }}">Read more</a>
</article>
```

## XML Rendering

### XML Templates

Render XML responses:

```python
@app.get('/api/users.xml')
def users_xml(database, render_template):
    """Render users as XML."""
    users = database["users"]

    xml = render_template('users.xml', users=users)

    return xml, 200, {'Content-Type': 'application/xml'}
```

XML template (`templates/users.xml`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<users>
    {% for user in users %}
    <user id="{{ user.id }}">
        <name>{{ user.name }}</name>
        <email>{{ user.email }}</email>
        <role>{{ user.role }}</role>
    </user>
    {% endfor %}
</users>
```

### RSS/Atom Feeds

Generate RSS feeds:

```python
from datetime import datetime

@app.get('/feed.rss')
def rss_feed(database, render_template):
    """Generate RSS feed."""
    posts = database["posts"][:10]  # Latest 10 posts

    rss = render_template(
        'feed.rss',
        posts=posts,
        build_date=datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    )

    return rss, 200, {'Content-Type': 'application/rss+xml'}
```

RSS template (`templates/feed.rss`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>RestMachine Blog</title>
        <link>https://example.com</link>
        <description>Latest posts from RestMachine Blog</description>
        <lastBuildDate>{{ build_date }}</lastBuildDate>

        {% for post in posts %}
        <item>
            <title>{{ post.title }}</title>
            <link>https://example.com/posts/{{ post.id }}</link>
            <description>{{ post.excerpt }}</description>
            <pubDate>{{ post.published_at }}</pubDate>
            <guid>https://example.com/posts/{{ post.id }}</guid>
        </item>
        {% endfor %}
    </channel>
</rss>
```

## Custom Filters and Functions

### Template Filters

Add custom Jinja2 filters:

```python
from datetime import datetime

@app.dependency()
def templates():
    """Jinja2 environment with custom filters."""
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Custom filters
    def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
        """Format datetime."""
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime(format)

    def truncate_words(value, num_words=10):
        """Truncate to word count."""
        words = value.split()
        if len(words) <= num_words:
            return value
        return ' '.join(words[:num_words]) + '...'

    env.filters['datetime'] = format_datetime
    env.filters['truncate_words'] = truncate_words

    return env

# Usage in template:
# {{ post.created_at | datetime('%B %d, %Y') }}
# {{ post.content | truncate_words(20) }}
```

### Global Functions

Add global template functions:

```python
@app.dependency()
def templates(request: Request):
    """Jinja2 with global functions."""
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Global functions
    def url_for(endpoint, **params):
        """Generate URL for endpoint."""
        # Simplified URL generation
        url = f"/{endpoint}"
        if params:
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            url += f"?{query}"
        return url

    def static(filename):
        """Generate static file URL."""
        return f"/static/{filename}"

    env.globals['url_for'] = url_for
    env.globals['static'] = static
    env.globals['request'] = request

    return env

# Usage in template:
# <link rel="stylesheet" href="{{ static('css/style.css') }}">
# <a href="{{ url_for('posts', page=2) }}">Next</a>
```

## Content Negotiation with Templates

### Multiple Format Support

Support different formats based on Accept header:

```python
@app.get('/users')
def users_multi_format(request: Request, database, render_template):
    """Respond with HTML, JSON, or XML based on Accept header."""
    users = database["users"]
    accept = request.headers.get('accept', 'text/html')

    if 'application/json' in accept:
        return users

    elif 'application/xml' in accept:
        xml = render_template('users.xml', users=users)
        return xml, 200, {'Content-Type': 'application/xml'}

    else:  # Default to HTML
        html = render_template('users.html', users=users)
        return html, 200, {'Content-Type': 'text/html'}
```

### Custom Content Renderers

Register template renderers for content negotiation:

```python
@app.content_renderer("text/html")
def html_renderer(data):
    """Render data as HTML."""
    if isinstance(data, dict) and 'template' in data:
        template_name = data['template']
        context = data.get('context', {})
        template = jinja_env.get_template(template_name)
        return template.render(**context)

    # Fallback to JSON representation
    return f"<pre>{json.dumps(data, indent=2)}</pre>"

@app.get('/users')
def users_with_renderer(database):
    """Use content renderer for templates."""
    users = database["users"]

    return {
        'template': 'users.html',
        'context': {'users': users}
    }
```

## Form Handling

### HTML Forms

Render and process HTML forms:

```python
from pydantic import BaseModel, EmailStr

class UserForm(BaseModel):
    name: str
    email: EmailStr
    bio: str = ""

@app.get('/users/new')
def new_user_form(render_template):
    """Display user creation form."""
    html = render_template('user_form.html', errors={})
    return html, 200, {'Content-Type': 'text/html'}

@app.validates
def validate_user_form(request: Request) -> UserForm:
    """Validate form data."""
    from urllib.parse import parse_qs

    # Parse form data
    data = parse_qs(request.body.decode())
    form_data = {k: v[0] if len(v) == 1 else v for k, v in data.items()}

    return UserForm.model_validate(form_data)

@app.post('/users')
def create_user_from_form(validate_user_form: UserForm, database, render_template):
    """Create user from form submission."""
    # Create user
    user = validate_user_form.model_dump()
    user['id'] = str(len(database['users']) + 1)
    database['users'].append(user)

    # Render success page
    html = render_template('user_created.html', user=user)
    return html, 201, {'Content-Type': 'text/html'}

@app.error_handler(400)
def form_validation_error(request, message, **kwargs):
    """Render form with validation errors."""
    validation_error = kwargs.get('validation_error')

    if validation_error and 'text/html' in request.headers.get('accept', ''):
        errors = {}
        for error in validation_error.errors():
            field = error['loc'][0]
            errors[field] = error['msg']

        template = jinja_env.get_template('user_form.html')
        html = template.render(errors=errors)

        return html, 400, {'Content-Type': 'text/html'}

    # JSON error for API requests
    return {"error": "Validation failed", "message": message}
```

Form template (`templates/user_form.html`):

```html
{% extends "base.html" %}

{% block content %}
<h1>Create User</h1>

<form method="POST" action="/users">
    <div class="form-group">
        <label for="name">Name:</label>
        <input type="text" id="name" name="name" required>
        {% if errors.name %}
        <span class="error">{{ errors.name }}</span>
        {% endif %}
    </div>

    <div class="form-group">
        <label for="email">Email:</label>
        <input type="email" id="email" name="email" required>
        {% if errors.email %}
        <span class="error">{{ errors.email }}</span>
        {% endif %}
    </div>

    <div class="form-group">
        <label for="bio">Bio:</label>
        <textarea id="bio" name="bio"></textarea>
        {% if errors.bio %}
        <span class="error">{{ errors.bio }}</span>
        {% endif %}
    </div>

    <button type="submit">Create User</button>
</form>
{% endblock %}
```

## Email Templates

### HTML Emails

Generate HTML emails:

```python
@app.dependency()
def send_email():
    """Email sending function."""
    def send(to: str, subject: str, html: str):
        # Implementation using smtplib, SendGrid, etc.
        print(f"Sending email to {to}: {subject}")
        print(html)

    return send

@app.post('/users')
def create_user_with_email(
    validate_user: UserCreate,
    database,
    render_template,
    send_email
):
    """Create user and send welcome email."""
    # Create user
    user = validate_user.model_dump()
    user['id'] = str(len(database['users']) + 1)
    database['users'].append(user)

    # Render email template
    email_html = render_template(
        'emails/welcome.html',
        user_name=user['name']
    )

    # Send email
    send_email(
        to=user['email'],
        subject='Welcome to RestMachine!',
        html=email_html
    )

    return user, 201
```

Email template (`templates/emails/welcome.html`):

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { background: #007bff; color: white; padding: 20px; }
        .content { padding: 20px; }
        .button {
            display: inline-block;
            padding: 10px 20px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to RestMachine!</h1>
        </div>
        <div class="content">
            <p>Hi {{ user_name }},</p>
            <p>Thank you for joining RestMachine. We're excited to have you!</p>
            <p>
                <a href="https://example.com/getting-started" class="button">
                    Get Started
                </a>
            </p>
            <p>Best regards,<br>The RestMachine Team</p>
        </div>
    </div>
</body>
</html>
```

## Complete Example

Here's a complete template-based application:

```python
from restmachine import RestApplication, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, EmailStr
from datetime import datetime
import os

app = RestApplication()

# Configure templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Custom filters
def format_date(value, format='%B %d, %Y'):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)

jinja_env.filters['date'] = format_date

# Database
@app.on_startup
def database():
    return {
        "users": [
            {"id": "1", "name": "Alice", "email": "alice@example.com", "role": "admin"},
            {"id": "2", "name": "Bob", "email": "bob@example.com", "role": "user"}
        ],
        "posts": [
            {
                "id": "1",
                "title": "First Post",
                "content": "This is my first post!",
                "author_id": "1",
                "created_at": "2024-01-01T10:00:00"
            }
        ]
    }

# Dependencies
@app.dependency()
def render_template():
    """Template rendering helper."""
    def render(template_name: str, **context):
        template = jinja_env.get_template(template_name)
        return template.render(**context)
    return render

# Models
class PostCreate(BaseModel):
    title: str
    content: str

# Routes
@app.get('/')
def index(database, render_template):
    """Home page."""
    html = render_template(
        'index.html',
        user_count=len(database['users']),
        post_count=len(database['posts'])
    )
    return html, 200, {'Content-Type': 'text/html'}

@app.get('/users')
def list_users(database, render_template):
    """List users."""
    html = render_template('users.html', users=database['users'])
    return html, 200, {'Content-Type': 'text/html'}

@app.get('/posts')
def list_posts(database, render_template):
    """List posts."""
    posts = database['posts']

    # Enhance posts with author info
    for post in posts:
        author = next(
            (u for u in database['users'] if u['id'] == post['author_id']),
            None
        )
        post['author_name'] = author['name'] if author else 'Unknown'

    html = render_template('posts.html', posts=posts)
    return html, 200, {'Content-Type': 'text/html'}

@app.get('/posts/{post_id}')
def view_post(request: Request, database, render_template):
    """View single post."""
    post_id = request.path_params['post_id']
    post = next((p for p in database['posts'] if p['id'] == post_id), None)

    if not post:
        html = render_template('404.html')
        return html, 404, {'Content-Type': 'text/html'}

    # Get author
    author = next(
        (u for u in database['users'] if u['id'] == post['author_id']),
        None
    )
    post['author_name'] = author['name'] if author else 'Unknown'

    html = render_template('post.html', post=post)
    return html, 200, {'Content-Type': 'text/html'}

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Escape User Input

Always escape user-provided content:

```python
# Jinja2 auto-escapes in HTML/XML contexts
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Manual escaping when needed
from markupsafe import escape

@app.get('/search')
def search(request: Request, render_template):
    query = request.query_params.get('q', '')
    # Auto-escaped in template
    html = render_template('search.html', query=query)
    return html, 200, {'Content-Type': 'text/html'}
```

### 2. Use Template Caching

Enable template caching for production:

```python
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml']),
    cache_size=400,  # Cache up to 400 templates
    auto_reload=False  # Disable in production
)
```

### 3. Organize Templates

Use a clear directory structure:

```
templates/
├── base.html
├── index.html
├── users/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── posts/
│   ├── list.html
│   └── detail.html
├── emails/
│   ├── welcome.html
│   └── notification.html
└── partials/
    ├── header.html
    ├── footer.html
    └── pagination.html
```

### 4. Provide Context Processors

Add common context to all templates:

```python
@app.dependency()
def render_template(request: Request, current_user=None):
    """Render with common context."""
    def render(template_name: str, **context):
        # Add common context
        context.setdefault('request', request)
        context.setdefault('current_user', current_user)
        context.setdefault('site_name', 'RestMachine App')

        template = jinja_env.get_template(template_name)
        return template.render(**context)

    return render
```

### 5. Handle Missing Templates

Gracefully handle missing templates:

```python
from jinja2.exceptions import TemplateNotFound

@app.dependency()
def render_template():
    def render(template_name: str, **context):
        try:
            template = jinja_env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound:
            # Log error
            logger.error(f"Template not found: {template_name}")
            # Return 500 error
            raise ValueError(f"Template {template_name} not found")

    return render
```

## Next Steps

- [Content Negotiation →](../guide/content-negotiation.md) - Multi-format responses
- [Headers →](headers.md) - Content-Type and caching headers
- [Error Handling →](../guide/error-handling.md) - Template error pages
- [Testing →](../guide/testing.md) - Test template rendering

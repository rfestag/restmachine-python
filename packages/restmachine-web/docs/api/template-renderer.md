# Template Rendering

RestMachine Web doesn't provide a built-in template renderer class. Instead, it works seamlessly with popular Python template engines like Jinja2.

## Using Jinja2

The recommended approach is to use Jinja2 directly with RestMachine's dependency injection:

```python
from restmachine import RestApplication
from jinja2 import Environment, FileSystemLoader
import os

app = RestApplication()

# Configure Jinja2 as a dependency
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=True
)

@app.dependency()
def templates():
    """Provide Jinja2 environment to handlers."""
    return jinja_env

@app.get('/page/{name}')
def render_page(request, templates):
    """Render a template."""
    template = templates.get_template('page.html')
    name = request.path_params['name']

    html = template.render(name=name)
    return html, 200, {'Content-Type': 'text/html'}
```

## Template Helper Pattern

For cleaner code, create a rendering helper:

```python
@app.dependency()
def render_template(templates):
    """Helper for rendering templates."""
    def render(template_name: str, **context):
        template = templates.get_template(template_name)
        return template.render(**context)
    return render

@app.get('/users')
def list_users(database, render_template):
    """Render users list."""
    users = database.get_users()
    html = render_template('users.html', users=users)
    return html, 200, {'Content-Type': 'text/html'}
```

## Why No Built-in Renderer?

RestMachine follows the principle of **"batteries not included"** for template rendering:

1. **Flexibility** - Use any template engine (Jinja2, Mako, Chameleon, etc.)
2. **Simplicity** - No abstraction layer to learn
3. **Control** - Direct access to all template engine features
4. **Zero dependencies** - Don't pay for what you don't use

## Other Template Engines

### Mako

```python
from mako.template import Template
from mako.lookup import TemplateLookup

@app.dependency()
def templates():
    return TemplateLookup(directories=['./templates'])

@app.get('/page')
def render_page(templates):
    template = templates.get_template('page.html')
    html = template.render(title="My Page")
    return html, 200, {'Content-Type': 'text/html'}
```

### Chameleon

```python
from chameleon import PageTemplateLoader

@app.dependency()
def templates():
    return PageTemplateLoader('./templates')

@app.get('/page')
def render_page(templates):
    template = templates['page.pt']
    html = template(title="My Page")
    return html, 200, {'Content-Type': 'text/html'}
```

## Content Negotiation with Templates

Serve both JSON and HTML from the same handler:

```python
from restmachine import Request

@app.get('/users')
def list_users(request: Request, database, render_template):
    """Serve JSON or HTML based on Accept header."""
    users = database.get_users()

    # Check Accept header
    accept = request.headers.get('accept', '')

    if 'text/html' in accept:
        # Render HTML template
        html = render_template('users.html', users=users)
        return html, 200, {'Content-Type': 'text/html'}
    else:
        # Return JSON
        return {"users": users}
```

Or use content negotiation with renderers:

```python
@app.content_renderer("text/html")
def render_html(data, request):
    """Render any data as HTML."""
    # Get template name from route or data
    template_name = data.get('_template', 'default.html')
    template = jinja_env.get_template(template_name)
    return template.render(**data)

@app.get('/users')
def list_users(database):
    """Returns dict - rendered as JSON or HTML based on Accept."""
    users = database.get_users()
    return {
        "_template": "users.html",  # For HTML renderer
        "users": users
    }
```

## Combining with Static Files

Serve both templates and static assets:

```python
from restmachine_web import StaticRouter

app = RestApplication()

# Static files (CSS, JS, images)
static = StaticRouter(serve="./public")
app.mount("/static", static)

# Templates
@app.dependency()
def templates():
    return jinja_env

@app.get('/')
def home(render_template):
    return render_template('home.html'), 200, {'Content-Type': 'text/html'}
```

Template (`templates/home.html`):

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <h1>Welcome</h1>
    <script src="/static/js/app.js"></script>
</body>
</html>
```

## See Also

- [Template Rendering Guide](../guides/templates.md) - Complete guide with examples
- [Template Rendering (Main Docs)](../../advanced/templates.md) - Detailed patterns and best practices
- [Static Files Guide](../guides/static-files.md) - Serving CSS, JS, and images
- [Content Negotiation](../../guide/content-negotiation.md) - Serve multiple formats from one endpoint

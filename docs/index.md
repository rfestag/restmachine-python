<div style="display: flex; align-items: center; gap: 2rem; padding: 1.5rem 0;">
  <img src="images/logo.svg" alt="RestMachine Logo" style="width: 120px; height: auto; flex-shrink: 0;">
  <div>
    <h1 style="margin: 0; font-size: 2.5rem;">RestMachine</h1>
    <p style="font-size: 1.1rem; color: #666; margin: 0.5rem 0 0 0;">
      Harness the full power of the web without the fuss
    </p>
  </div>
</div>

<p style="text-align: center; margin-bottom: 2rem;">
<a href="https://github.com/rfestag/restmachine-python/actions"><img src="https://github.com/rfestag/restmachine-python/workflows/CI/badge.svg" alt="Build Status"></a>
<a href="https://github.com/rfestag/restmachine-python/actions"><img src="https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg" alt="Coverage"></a>
<a href="https://github.com/rfestag/restmachine-python/actions"><img src="https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg" alt="Code Quality"></a>
<a href="https://github.com/rfestag/restmachine-python"><img src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue" alt="Python Versions"></a>
<a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

## Overview

RestMachine is a modern Python web framework that makes building production-ready APIs straightforward. Like Rails or Django, RestMachine includes everything you need - from code generation and ORM to deployment - but keeps it simple and Pythonic.

## Why RestMachine?

- **Get started quickly** - Use the CLI to scaffold out your application.
- **Focus on results, not boilerplate** - Unique dependency injection system and decorators allow you to focus more on what your application does, leaving details like content negotiaion, proper status codes, and ETags to the framework. 
- **Deploy anywhere** - The same application can run serverless in AWS Lambda or within your favorit ASGI server.

<div style="text-align: center; margin: 2rem 0;">
  <a href="tutorial/01-setup/" style="display: inline-block; padding: 0.75rem 2rem; background: #354f7a; color: white; text-decoration: none; border-radius: 0.25rem; font-weight: bold; margin: 0.5rem;">Start the Tutorial</a>
  <a href="api/application/" style="display: inline-block; padding: 0.75rem 2rem; border: 2px solid #354f7a; color: #354f7a; text-decoration: none; border-radius: 0.25rem; font-weight: bold; margin: 0.5rem;">API Reference</a>
</div>

### Get started quickly with the CLI

Scaffold out your application quickly and easily, and start serving it immediately :

```bash
# Create a new project
restmachine new blog-api

# Generate a complete CRUD resource (model, routes, schemas, tests, fixtures)
restmachine generate scaffold Post title:str content:str author:str published:bool

# Run your API
uvicorn app:asgi_app --reload
```

That's it! You now have a full REST API with:

✅ Database models and migrations <br/>
✅ CRUD endpoints with proper HTTP semantics <br/>
✅ Request/response validation <br/>
✅ Seed data fixtures <br/>
✅ Integration tests <br/>

### Easily define HTTP endpoints

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.get('/hello/{name}')
def hello(request: Request):
    name = request.path_params['name']
    return {"message": f"Hello, {name}!"}

# Run with ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

### Decorators Define Semanatics

Rather than forcing you to understand the complexities of HTTP sematnics, RestMachine allows you to define certain "facts"
about your application through the use of decorators. Want to indicate that, whenever a certain function is called, your
endpoint will return a `404 Not Found` (such as when you look up a user from a database)? Simply decorate the lookup
with `resource_exists`. 

The best part is, using these decorators defines re-usable depenencies that can later be used by your various endpoints.
Many decorators exist that your application can leverage to affect semantics or simply re-use throughout.

```python
# Register a dependency that will be run once at startup and memoized
@app.on_startup
def database():
    """Initialize database connection at startup."""
    return create_db_connection()

# RestMachine will detect your database dependency and pass it in. The path_params is a built-in dependency you can just use
@app.resource_exists
def user(database, path_params):
    user_id = path_params['user_id']
    return database.get_user(user_id)  # Returns None if not found

# When your user hits this endpoint, the user dependency will be called (cached per-request)
@app.get('/users/{user_id}')
def get_user(user):
    return user  # Because user uses the resource_exists decorator, this will automatically handle 404 for you.
```

Decorators can even be used to define other useful HTTP sematnics, such as request validation and content negotiation

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

@app.validates
def user_create(request: Request) -> UserCreate:
    import json
    return UserCreate.model_validate(json.loads(request.body))

@app.post('/users')
def create_user(user_create: UserCreate):
    return {"created": user_create.model_dump()}

@app.provides("text/html")
def render_html(create_user):
    data = get_data
    return f"<h1>Sucessfully Created User</h1><p>Name: {create_user.name}</p><p>Email: {create_user.email}</p>"

@app.provides("text/xml")
def render_xml(create_user):
    data = get_data
    return f"<user><name>{create_user.name}</name><email>{create_user.email}</email></user>"
```

### Write Once, Run Anywhere

When you build applications, you often may not know the most cost efficient way to run it. Instead of re-writing your code
to run in on bare metal, a container, or serverless, RestMachine lets you write your application code once and chose the
appropriate driver to run it anywhere!

```bash
uvicorn app:asgi_app --reload
```

Or AWS Lambda via API Gateway:

```python
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```


### Automatic OpenAPI Documentation

Generate OpenAPI 3.0 specifications automatically from your code:

```python
# Generate OpenAPI spec
openapi_json = app.generate_openapi_json(
    title="My API",
    version="1.0.0"
)

# Or save to file for Swagger UI, client SDK generation, etc.
app.save_openapi_json(filename="openapi.json")
```

## Community & Support

- **GitHub**: [rfestag/restmachine-python](https://github.com/rfestag/restmachine-python)
- **Issues**: [Report bugs or request features](https://github.com/rfestag/restmachine-python/issues)
- **Security**: See [Security Policy](development/security.md)

## License

RestMachine is released under the [MIT License](about/license.md).

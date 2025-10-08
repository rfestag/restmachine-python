# Quick Start

This guide will walk you through creating your first RestMachine application and deploying it with various servers.

## Create Your First API

### 1. Install RestMachine

```bash
pip install restmachine uvicorn[standard]
```

### 2. Create `app.py`

```python
from restmachine import RestApplication

app = RestApplication()

@app.get('/')
def home():
    return {"message": "Welcome to RestMachine!"}

@app.get('/hello/{name}')
def hello(path_params):
    name = path_params['name']
    return {"message": f"Hello, {name}!"}

@app.post('/echo')
def echo(json_body):
    return {"you_sent": json_body}
```

### 3. Test Locally

You can test your application directly without a server:

```python
from restmachine import HTTPMethod

# Test GET
request = Request(method=HTTPMethod.GET, path='/')
response = app.execute(request)
print(response.body)  # {"message": "Welcome to RestMachine!"}

# Test with path params
request = Request(method=HTTPMethod.GET, path='/hello/World')
response = app.execute(request)
print(response.body)  # {"message": "Hello, World!"}
```

## Deploy with ASGI Servers

RestMachine includes built-in ASGI support for production deployment.

### Option 1: Uvicorn (Recommended)

**Add ASGI adapter to `app.py`:**

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get('/')
def home():
    return {"message": "Welcome to RestMachine!"}

# Create ASGI application
asgi_app = ASGIAdapter(app)
```

**Run with Uvicorn:**

```bash
# Development (with auto-reload)
uvicorn app:asgi_app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app:asgi_app --host 0.0.0.0 --port 8000 --workers 4
```

**Test it:**

```bash
curl http://localhost:8000/
# {"message": "Welcome to RestMachine!"}

curl http://localhost:8000/hello/RestMachine
# {"message": "Hello, RestMachine!"}
```

### Option 2: Hypercorn (HTTP/2 Support)

**Install:**

```bash
pip install hypercorn
```

**Run with Hypercorn:**

```bash
# Development
hypercorn app:asgi_app --reload --bind 0.0.0.0:8000

# Production with HTTP/2
hypercorn app:asgi_app --bind 0.0.0.0:8000 --workers 4
```

### Option 3: Gunicorn + Uvicorn Workers

For production deployments with process management:

```bash
pip install gunicorn uvicorn[standard]
```

```bash
gunicorn app:asgi_app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

## Deploy to AWS Lambda

RestMachine provides first-class support for AWS Lambda deployment.

### 1. Install AWS Package

```bash
pip install restmachine-aws
```

### 2. Create `lambda_handler.py`

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get('/')
def home():
    return {"message": "Welcome to RestMachine on Lambda!"}

@app.get('/hello/{name}')
def hello(path_params):
    name = path_params['name']
    return {"message": f"Hello, {name}!"}

# Create AWS Lambda adapter
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

### 3. Package for Deployment

Create a deployment package:

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install restmachine restmachine-aws

# Package the code
mkdir package
pip install --target ./package restmachine restmachine-aws
cd package
zip -r ../lambda_function.zip .
cd ..
zip lambda_function.zip lambda_handler.py
```

### 4. Deploy to AWS Lambda

Using AWS CLI:

```bash
# Create Lambda function
aws lambda create-function \
  --function-name restmachine-api \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 30 \
  --memory-size 512
```

### 5. Connect to API Gateway

**Create API Gateway REST API:**

```bash
aws apigatewayv2 create-api \
  --name restmachine-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:REGION:ACCOUNT:function:restmachine-api
```

**Or create Function URL (simpler):**

```bash
aws lambda create-function-url-config \
  --function-name restmachine-api \
  --auth-type NONE
```

### Supported Event Sources

The AWS adapter automatically detects and handles:

| Event Source | Format | Notes |
|-------------|--------|-------|
| **API Gateway REST API** | v1 (1.0) | Traditional REST APIs |
| **API Gateway HTTP API** | v2 (2.0) | Lower latency, cheaper |
| **Application Load Balancer** | ALB | Multi-value headers, mTLS |
| **Lambda Function URLs** | v2 | Simplest setup |

## Add Startup & Shutdown Handlers

RestMachine supports lifecycle hooks for resource management:

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

# Startup handler (runs once when app starts)
@app.on_startup
def database():
    print("Opening database connection...")
    return create_db_connection()

# Use dependency injection
@app.get('/users')
def list_users(database):  # 'database' injected from startup
    return database.query("SELECT * FROM users")

# Shutdown handler (runs when app stops)
@app.on_shutdown
def close_database(database):  # Can also inject dependencies
    print("Closing database connection...")
    database.close()

asgi_app = ASGIAdapter(app)
```

**ASGI Deployment:** Startup/shutdown handlers work automatically.

**AWS Lambda:** Startup handlers run during cold start. For shutdown handlers, see [Lambda Extensions](../restmachine-aws/guides/lambda-extensions.md).

## Generate OpenAPI Documentation

RestMachine automatically generates OpenAPI 3.0 specifications from your code:

```python
from restmachine import RestApplication
from pydantic import BaseModel, EmailStr

app = RestApplication()

class UserCreate(BaseModel):
    name: str
    email: EmailStr

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

@app.post('/users')
def create_user(user_create: UserCreate):
    """Create a new user account."""
    return {"created": user_create.model_dump()}, 201

# Generate OpenAPI spec
openapi_json = app.generate_openapi_json(
    title="My API",
    version="1.0.0",
    description="My awesome API"
)

# Or save to file
app.save_openapi_json(
    filename="openapi.json",
    docs_dir="docs"
)
```

### Add Interactive Documentation

Serve Swagger UI for interactive API documentation:

```python
@app.get('/openapi.json')
def openapi_spec():
    """OpenAPI specification endpoint."""
    import json
    return json.loads(app.generate_openapi_json(
        title="My API",
        version="1.0.0"
    ))

@app.get('/docs')
def swagger_ui():
    """Interactive API documentation."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Documentation</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
            SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
            });
        </script>
    </body>
    </html>
    """
```

Visit `http://localhost:8000/docs` to see your interactive API documentation.

See the [OpenAPI Guide](../guide/openapi.md) for advanced features including client SDK generation.

## Observability & Metrics

RestMachine includes built-in metrics collection to help you monitor your application's performance.

### Default Behavior

**AWS Lambda**: Metrics are automatically enabled and published to CloudWatch Logs in EMF (Embedded Metric Format). No configuration required!

```python
from restmachine_aws import AwsApiGatewayAdapter

# Metrics automatically enabled for CloudWatch
adapter = AwsApiGatewayAdapter(app)
```

**ASGI/Other Platforms**: Metrics collection is available but requires a custom publisher. See the [Metrics documentation](../metrics.md) for details.

### Adding Custom Metrics

Inject the `metrics` dependency to track business metrics:

```python
@app.get('/orders')
def list_orders(metrics):
    # Track request count
    metrics.add_metric("orders.listed", 1, unit="Count")

    # Track timing
    metrics.start_timer("db.query")
    orders = db.query("SELECT * FROM orders")
    metrics.stop_timer("db.query")

    return {"orders": orders}
```

### What Gets Logged

All requests automatically include:
- Total request time
- Application execution time
- Response conversion time
- HTTP method and path
- Status code

For more details:
- **[Core Metrics Guide](../metrics.md)** - Platform-agnostic metrics features
- **[AWS CloudWatch Metrics](../restmachine-aws/guides/metrics.md)** - CloudWatch EMF configuration

## Next Steps

Now that you have a running application:

- **[Basic Application →](../guide/basic-application.md)** - Learn fundamental concepts
- **[Dependency Injection →](../guide/dependency-injection.md)** - Master DI patterns
- **[Request Validation →](../guide/validation.md)** - Add Pydantic validation
- **[Deployment Guide →](../guide/deployment/uvicorn.md)** - Production deployment strategies

## Common Issues

??? question "Import Error: No module named 'restmachine'"
    Make sure you've installed RestMachine:
    ```bash
    pip install restmachine
    ```

??? question "ASGI server not working"
    Ensure you've created the ASGI adapter:
    ```python
    asgi_app = ASGIAdapter(app)
    ```
    And you're running the correct module: `uvicorn app:asgi_app`

??? question "Lambda function timing out"
    Increase the timeout in your Lambda configuration:
    ```bash
    aws lambda update-function-configuration \
      --function-name restmachine-api \
      --timeout 30
    ```

??? question "404 Not Found for all routes"
    Check that your API Gateway integration is configured correctly to proxy all requests to Lambda:
    - Use `{proxy+}` as the resource path
    - Enable "Lambda Proxy Integration"

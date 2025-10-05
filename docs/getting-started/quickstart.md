# Quick Start

This guide will walk you through creating your first RestMachine application and deploying it with various servers.

## Create Your First API

### 1. Install RestMachine

```bash
pip install restmachine uvicorn[standard]
```

### 2. Create `app.py`

```python
from restmachine import RestApplication, Request

app = RestApplication()

@app.get('/')
def home():
    return {"message": "Welcome to RestMachine!"}

@app.get('/hello/{name}')
def hello(request: Request):
    name = request.path_params['name']
    return {"message": f"Hello, {name}!"}

@app.post('/echo')
def echo(request: Request):
    return {"you_sent": request.body}
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
def hello(request):
    name = request.path_params['name']
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

**AWS Lambda:** Startup handlers run during cold start. For shutdown handlers, see [Lambda Extensions](../advanced/lambda-extensions.md).

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

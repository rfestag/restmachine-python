# AWS Lambda Adapter

::: restmachine_aws.AwsApiGatewayAdapter
    options:
      show_root_heading: true
      heading_level: 2

## Overview

The `AwsApiGatewayAdapter` converts AWS Lambda events into RestMachine requests and responses back into Lambda-compatible formats. It automatically detects and handles multiple event sources.

## Supported Event Sources

The adapter automatically detects and handles:

- **API Gateway REST API (v1)** - Payload format 1.0
- **API Gateway HTTP API (v2)** - Payload format 2.0
- **Application Load Balancer (ALB)** - ALB target integration
- **Lambda Function URLs** - Direct HTTPS endpoints (uses v2 format)

Version detection is automatic based on the event structure.

## Basic Usage

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get("/hello/{name}")
def hello(request):
    name = request.path_params['name']
    return {"message": f"Hello, {name}!"}

# Create adapter
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return adapter.handle_event(event, context)
```

## Automatic Startup

The adapter automatically runs startup handlers during Lambda cold start:

```python
@app.on_startup
def database():
    """Runs once per Lambda container."""
    print("Opening database connection...")
    return create_db_connection()

@app.get("/users/{user_id}")
def get_user(database, request):
    # Database connection is already initialized
    user_id = request.path_params['user_id']
    return database.get_user(user_id)
```

Startup handlers execute when the Lambda container initializes, not on every request. This ensures expensive operations (like opening database connections) only happen during cold starts.

## Event Format Detection

### API Gateway v1 (REST API)

```python
{
    "httpMethod": "GET",
    "path": "/users/123",
    "headers": {"Accept": "application/json"},
    "pathParameters": {"user_id": "123"},
    "queryStringParameters": {"page": "1"},
    "body": null,
    "requestContext": {
        "requestId": "abc123",
        "authorizer": {...}
    }
}
```

### API Gateway v2 (HTTP API)

```python
{
    "version": "2.0",
    "routeKey": "GET /users/{user_id}",
    "rawPath": "/users/123",
    "headers": {"accept": "application/json"},
    "pathParameters": {"user_id": "123"},
    "queryStringParameters": {"page": "1"},
    "body": null,
    "requestContext": {
        "http": {
            "method": "GET",
            "path": "/users/123"
        }
    }
}
```

### Application Load Balancer (ALB)

```python
{
    "httpMethod": "GET",
    "path": "/users/123",
    "headers": {"accept": "application/json"},
    "queryStringParameters": {"page": "1"},
    "body": null,
    "requestContext": {
        "elb": {
            "targetGroupArn": "arn:aws:..."
        }
    }
}
```

The adapter automatically detects the format and extracts the correct fields.

## Header Handling

Headers are normalized to lowercase for case-insensitive matching, following ASGI conventions:

```python
# API Gateway event
{
    "headers": {
        "Content-Type": "application/json",
        "X-Custom-Header": "value"
    }
}

# Converted to
request.headers = {
    "content-type": "application/json",
    "x-custom-header": "value"
}
```

Access headers in your handlers:

```python
@app.get("/api/data")
def get_data(request):
    content_type = request.headers.get("content-type")
    custom = request.headers.get("x-custom-header")
    return {"content_type": content_type, "custom": custom}
```

## Multi-Value Headers

The adapter properly handles multi-value headers (cookies, set-cookie, etc.):

```python
# API Gateway v1 with multiValueHeaders
{
    "multiValueHeaders": {
        "cookie": ["session=abc123", "tracking=xyz789"]
    }
}

# Converted to RestMachine request
request.headers = MultiValueHeaders({
    "cookie": ["session=abc123", "tracking=xyz789"]
})
```

## Query Parameters

Query parameters are parsed and available as dictionaries:

```python
# Event
{
    "queryStringParameters": {
        "page": "2",
        "limit": "10"
    }
}

# Access in handler
@app.get("/users")
def list_users(request):
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 20))
    return {"page": page, "limit": limit}
```

## Request Body

The adapter handles both plain text and base64-encoded bodies:

```python
# Plain text body
{
    "body": '{"name": "Alice", "email": "alice@example.com"}',
    "isBase64Encoded": false
}

# Base64-encoded body (binary data)
{
    "body": "iVBORw0KGgoAAAANSUhEUgAA...",
    "isBase64Encoded": true
}

# Access in handler
@app.post("/users")
def create_user(request):
    import json
    data = json.loads(request.body)
    return {"created": data}, 201
```

## Response Conversion

RestMachine responses are automatically converted to Lambda-compatible formats:

```python
# RestMachine response
Response(
    status_code=200,
    body='{"message": "Success"}',
    headers={"Content-Type": "application/json"}
)

# Converted to API Gateway v1 format
{
    "statusCode": 200,
    "body": '{"message": "Success"}',
    "headers": {"Content-Type": "application/json"},
    "multiValueHeaders": {},
    "isBase64Encoded": false
}

# Converted to API Gateway v2 format
{
    "statusCode": 200,
    "body": '{"message": "Success"}',
    "headers": {"content-type": "application/json"},
    "cookies": [],
    "isBase64Encoded": false
}
```

## Error Handling

The adapter handles errors gracefully:

```python
@app.get("/users/{user_id}")
def get_user(request):
    user_id = request.path_params['user_id']
    if not user_exists(user_id):
        return {"error": "User not found"}, 404
    return {"id": user_id, "name": "Alice"}

# Returns proper Lambda error response
{
    "statusCode": 404,
    "body": '{"error": "User not found"}',
    "headers": {"Content-Type": "application/json"}
}
```

## Method Reference

### `handle_event(event, context)`

Main entry point for Lambda handler.

**Parameters:**
- `event` (dict): AWS Lambda event dictionary
- `context` (optional): AWS Lambda context object

**Returns:**
- dict: Lambda-compatible response dictionary

**Example:**
```python
def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

### `convert_to_request(event, context)`

Convert AWS event to RestMachine Request object.

**Parameters:**
- `event` (dict): AWS Lambda event
- `context` (optional): Lambda context

**Returns:**
- Request: RestMachine Request object

### `convert_from_response(response, event, context)`

Convert RestMachine Response to Lambda response format.

**Parameters:**
- `response` (Response): RestMachine response
- `event` (dict): Original AWS event (for format detection)
- `context` (optional): Lambda context

**Returns:**
- dict: Lambda-compatible response

## See Also

- [Lambda Deployment Guide](../guides/lambda-deployment.md) - Complete deployment guide
- [Lambda Extensions](../guides/lambda-extensions.md) - Shutdown handler support
- [Lifecycle Handlers](../../advanced/lifecycle.md) - Startup and shutdown patterns

# Error Handling

RestMachine provides flexible error handling through custom error handlers, automatic HTTP status code mapping, and rich error responses. Learn how to handle errors gracefully and provide meaningful feedback to API consumers.

## Basic Error Responses

### Automatic Error Handling

RestMachine automatically handles common errors using declarative decorators:

```python
from restmachine import RestApplication, Request, Response
from pydantic import BaseModel, EmailStr

app = RestApplication()

@app.on_startup
def database():
    return {"users": {"1": {"id": "1", "name": "Alice"}}}

@app.resource_exists
def user(path_params, database):
    """Returns None if not found, triggering automatic 404."""
    user_id = path_params['user_id']
    return database["users"].get(user_id)

@app.get('/users/{user_id}')
def get_user(user):
    """404 handled automatically by resource_exists decorator."""
    return {"user": user}

class UserCreate(BaseModel):
    email: EmailStr
    name: str

@app.validates
def user_create(json_body) -> UserCreate:
    """Validates request, returns 400/422 automatically on error."""
    return UserCreate.model_validate(json_body)

@app.post('/users')
def create_user(user_create: UserCreate):
    """Validation errors handled automatically."""
    return {"created": user_create.model_dump()}, 201
```

### HTTP Status Codes

Use appropriate status codes for different error types:

```python
# 400 Bad Request - Client error (validation, malformed request)
return Response(400, '{"error": "Invalid input"}')

# 401 Unauthorized - Missing or invalid authentication
return Response(401, '{"error": "Authentication required"}')

# 403 Forbidden - Authenticated but not authorized
return Response(403, '{"error": "Access denied"}')

# 404 Not Found - Resource doesn't exist
return Response(404, '{"error": "Resource not found"}')

# 409 Conflict - Resource conflict (duplicate email, etc.)
return Response(409, '{"error": "Email already exists"}')

# 422 Unprocessable Entity - Semantic validation error
return Response(422, '{"error": "Invalid date range"}')

# 500 Internal Server Error - Server error
return Response(500, '{"error": "Internal server error"}')

# 503 Service Unavailable - Temporary unavailability
return Response(503, '{"error": "Service temporarily unavailable"}')
```

## Custom Error Handlers

### Defining Error Handlers

Use `@app.error_handler()` to customize error responses:

```python
@app.error_handler(404)
def not_found_handler(request, message, **kwargs):
    """Custom 404 error response."""
    return {
        "error": "Not Found",
        "message": message,
        "path": request.path,
        "method": request.method
    }

@app.error_handler(400)
def bad_request_handler(request, message, **kwargs):
    """Custom 400 error response."""
    return {
        "error": "Bad Request",
        "message": message,
        "timestamp": "2024-01-15T10:30:00Z"
    }

@app.error_handler(500)
def server_error_handler(request, message, **kwargs):
    """Custom 500 error response."""
    # Log the error
    import logging
    logging.error(f"Server error: {message}", extra={'path': request.path})

    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }
```

### Error Handler Parameters

Error handlers receive:

```python
@app.error_handler(400)
def validation_error(request, message, **kwargs):
    """
    Parameters:
    - request: The Request object
    - message: Error message string
    - **kwargs: Additional context (exc_info, validation_error, etc.)
    """

    # Access request details
    path = request.path
    method = request.method
    headers = request.headers

    # Access additional context
    exc_info = kwargs.get('exc_info')  # Exception info if available
    validation_error = kwargs.get('validation_error')  # Pydantic error

    return {
        "error": "Validation Error",
        "message": message,
        "path": path
    }
```

## Exception-Based Error Handling

### Raising Exceptions

Raise exceptions in dependencies or handlers:

```python
@app.dependency()
def current_user(request: Request):
    auth_header = request.headers.get('authorization')

    if not auth_header:
        raise ValueError("Authentication required")

    token = auth_header.replace('Bearer ', '')

    if not validate_token(token):
        raise ValueError("Invalid token")

    return get_user_from_token(token)

@app.get('/profile')
def get_profile(current_user):
    # current_user dependency raises ValueError if auth fails
    return {"user": current_user}

# Handle ValueError exceptions
@app.error_handler(401)
def unauthorized_handler(request, message, **kwargs):
    return {
        "error": "Unauthorized",
        "message": message
    }
```

### Custom Exceptions

Define custom exception classes:

```python
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

class AuthorizationError(Exception):
    """Raised when user lacks permissions."""
    pass

class ResourceNotFoundError(Exception):
    """Raised when resource doesn't exist."""
    pass

class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []

# Use in dependencies
@app.dependency()
def current_user(request: Request):
    auth_header = request.headers.get('authorization')

    if not auth_header:
        raise AuthenticationError("Missing authentication header")

    return validate_and_get_user(auth_header)

# Handle custom exceptions
@app.error_handler(401)
def auth_error_handler(request, message, **kwargs):
    exc_info = kwargs.get('exc_info')

    if exc_info and isinstance(exc_info[1], AuthenticationError):
        return {
            "error": "Authentication Failed",
            "message": str(exc_info[1]),
            "hint": "Include 'Authorization: Bearer <token>' header"
        }

    return {"error": "Unauthorized", "message": message}
```

## Validation Error Handling

### Pydantic Validation Errors

Handle Pydantic validation errors gracefully:

```python
from pydantic import BaseModel, EmailStr, Field, ValidationError as PydanticValidationError

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=18, le=120)

@app.validates
def user_create(json_body) -> UserCreate:
    """Validates request body, returns 422 automatically on validation error."""
    return UserCreate.model_validate(json_body)

@app.error_handler(400)
def validation_error_handler(request, message, **kwargs):
    """Handle Pydantic validation errors."""
    validation_error = kwargs.get('validation_error')

    if validation_error and isinstance(validation_error, PydanticValidationError):
        errors = []
        for error in validation_error.errors():
            errors.append({
                "field": '.'.join(str(loc) for loc in error['loc']),
                "message": error['msg'],
                "type": error['type']
            })

        return {
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": errors
        }

    return {
        "error": "Bad Request",
        "message": message
    }
```

### Field-Level Errors

Provide detailed field-level error information:

```python
@app.error_handler(400)
def detailed_validation_error(request, message, **kwargs):
    """Provide detailed validation errors."""
    validation_error = kwargs.get('validation_error')

    if not validation_error:
        return {"error": "Bad Request", "message": message}

    # Format Pydantic errors
    from pydantic import ValidationError
    if isinstance(validation_error, ValidationError):
        field_errors = {}

        for error in validation_error.errors():
            field = '.'.join(str(loc) for loc in error['loc'])
            field_errors[field] = {
                "message": error['msg'],
                "value": error.get('input'),
                "type": error['type']
            }

        return {
            "error": "Validation Error",
            "message": "One or more fields failed validation",
            "field_errors": field_errors
        }

    return {"error": "Bad Request", "message": message}
```

## Error Context and Logging

### Adding Error Context

Include useful context in error responses:

```python
import uuid
from datetime import datetime

@app.dependency()
def request_id(request: Request) -> str:
    """Generate or extract request ID."""
    return request.headers.get('x-request-id', str(uuid.uuid4()))

@app.error_handler(500)
def server_error_with_context(request, message, **kwargs):
    """Server error with tracking information."""
    import logging

    request_id = request.headers.get('x-request-id', 'unknown')
    timestamp = datetime.now().isoformat()

    # Log detailed error
    exc_info = kwargs.get('exc_info')
    if exc_info:
        logging.error(
            f"Server error [{request_id}]: {message}",
            exc_info=exc_info,
            extra={
                'request_id': request_id,
                'path': request.path,
                'method': request.method
            }
        )

    # Return safe error response
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "request_id": request_id,
        "timestamp": timestamp
    }
```

### Structured Logging

Implement structured error logging:

```python
import logging
import json

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

logger = logging.getLogger(__name__)

class StructuredMessage:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __str__(self):
        return json.dumps(self.kwargs)

@app.error_handler(500)
def logged_server_error(request, message, **kwargs):
    """Log structured error information."""
    exc_info = kwargs.get('exc_info')

    log_data = {
        "level": "error",
        "message": message,
        "request": {
            "method": request.method,
            "path": request.path,
            "headers": dict(request.headers)
        },
        "timestamp": datetime.now().isoformat()
    }

    if exc_info:
        log_data["exception"] = {
            "type": exc_info[0].__name__,
            "message": str(exc_info[1])
        }

    logger.error(StructuredMessage(**log_data))

    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }
```

## Error Response Formats

### Consistent Error Format

Use a consistent error response format:

```python
def error_response(error_type: str, message: str, **extras):
    """Create consistent error response."""
    response = {
        "error": error_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    response.update(extras)
    return response

@app.error_handler(400)
def bad_request(request, message, **kwargs):
    return error_response("Bad Request", message, path=request.path)

@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    return error_response("Unauthorized", message)

@app.error_handler(403)
def forbidden(request, message, **kwargs):
    return error_response("Forbidden", message, required_role="admin")

@app.error_handler(404)
def not_found(request, message, **kwargs):
    return error_response("Not Found", message, path=request.path)
```

### RFC 7807 Problem Details

Implement RFC 7807 Problem Details format:

```python
@app.error_handler(400)
def problem_details_bad_request(request, message, **kwargs):
    """RFC 7807 Problem Details format."""
    return {
        "type": "https://api.example.com/errors/bad-request",
        "title": "Bad Request",
        "status": 400,
        "detail": message,
        "instance": request.path
    }

@app.error_handler(404)
def problem_details_not_found(request, message, **kwargs):
    return {
        "type": "https://api.example.com/errors/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": message,
        "instance": request.path
    }

@app.error_handler(422)
def problem_details_validation(request, message, **kwargs):
    validation_error = kwargs.get('validation_error')
    errors = []

    if validation_error:
        from pydantic import ValidationError
        if isinstance(validation_error, ValidationError):
            for error in validation_error.errors():
                errors.append({
                    "field": '.'.join(str(loc) for loc in error['loc']),
                    "reason": error['msg']
                })

    return {
        "type": "https://api.example.com/errors/validation",
        "title": "Validation Error",
        "status": 422,
        "detail": message,
        "instance": request.path,
        "errors": errors
    }
```

## Cascading Error Handlers

### Fallback Handlers

Define fallback error handlers:

```python
# Specific handler for 404
@app.error_handler(404)
def not_found(request, message, **kwargs):
    return {"error": "Not Found", "message": message}

# Generic handler for all 4xx errors
@app.error_handler(400)
@app.error_handler(401)
@app.error_handler(403)
@app.error_handler(422)
def client_error(request, message, **kwargs):
    """Fallback for client errors."""
    return {
        "error": "Client Error",
        "message": message,
        "path": request.path
    }

# Generic handler for all 5xx errors
@app.error_handler(500)
@app.error_handler(502)
@app.error_handler(503)
def server_error(request, message, **kwargs):
    """Fallback for server errors."""
    import logging
    logging.error(f"Server error: {message}")

    return {
        "error": "Server Error",
        "message": "An unexpected error occurred"
    }
```

## Debug Mode Errors

### Development vs Production

Show detailed errors in development only:

```python
import os

DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

@app.error_handler(500)
def debug_aware_error(request, message, **kwargs):
    """Show stack trace in debug mode only."""
    import traceback

    exc_info = kwargs.get('exc_info')

    if DEBUG and exc_info:
        # Development: show detailed error
        return {
            "error": "Internal Server Error",
            "message": message,
            "exception": {
                "type": exc_info[0].__name__,
                "message": str(exc_info[1]),
                "traceback": traceback.format_exception(*exc_info)
            }
        }

    # Production: hide details
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }
```

## Complete Example

Here's a complete error handling setup:

```python
from restmachine import RestApplication, Request, Response
from pydantic import BaseModel, EmailStr, ValidationError as PydanticValidationError
from datetime import datetime
import logging
import json

app = RestApplication()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom exceptions
class AuthenticationError(Exception):
    pass

class AuthorizationError(Exception):
    pass

# Models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    age: int

# Database
@app.on_startup
def database():
    return {"users": []}

# Helpers
def error_response(error_type: str, message: str, status_code: int, **extras):
    """Create consistent error response."""
    response = {
        "error": error_type,
        "message": message,
        "status": status_code,
        "timestamp": datetime.now().isoformat()
    }
    response.update(extras)
    return response

# Error handlers
@app.error_handler(400)
def bad_request_handler(request, message, **kwargs):
    """Handle validation and bad request errors."""
    validation_error = kwargs.get('validation_error')

    if validation_error and isinstance(validation_error, PydanticValidationError):
        errors = [
            {
                "field": '.'.join(str(loc) for loc in error['loc']),
                "message": error['msg']
            }
            for error in validation_error.errors()
        ]

        return error_response(
            "Validation Error",
            "Request validation failed",
            400,
            details=errors
        )

    return error_response("Bad Request", message, 400, path=request.path)

@app.error_handler(401)
def unauthorized_handler(request, message, **kwargs):
    """Handle authentication errors."""
    exc_info = kwargs.get('exc_info')

    if exc_info and isinstance(exc_info[1], AuthenticationError):
        return error_response(
            "Authentication Failed",
            str(exc_info[1]),
            401,
            hint="Include 'Authorization: Bearer <token>' header"
        )

    return error_response("Unauthorized", message, 401)

@app.error_handler(403)
def forbidden_handler(request, message, **kwargs):
    """Handle authorization errors."""
    return error_response("Forbidden", message, 403, path=request.path)

@app.error_handler(404)
def not_found_handler(request, message, **kwargs):
    """Handle not found errors."""
    return error_response("Not Found", message, 404, path=request.path)

@app.error_handler(409)
def conflict_handler(request, message, **kwargs):
    """Handle resource conflict errors."""
    return error_response("Conflict", message, 409)

@app.error_handler(500)
def server_error_handler(request, message, **kwargs):
    """Handle server errors."""
    exc_info = kwargs.get('exc_info')

    # Log error
    if exc_info:
        logger.error(
            f"Server error: {message}",
            exc_info=exc_info,
            extra={'path': request.path, 'method': request.method}
        )

    return error_response(
        "Internal Server Error",
        "An unexpected error occurred",
        500
    )

# Validation
@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

# Dependencies
@app.dependency()
def current_user(request: Request):
    auth_header = request.headers.get('authorization', '')

    if not auth_header.startswith('Bearer '):
        raise AuthenticationError("Missing or invalid authentication header")

    # Simplified token validation
    return {"id": "1", "name": "Alice"}

# Routes
@app.post('/users')
def create_user(user_create: UserCreate, database):
    # Check for duplicate email
    existing = next(
        (u for u in database["users"] if u["email"] == user_create.email),
        None
    )

    if existing:
        return Response(
            409,
            json.dumps(error_response(
                "Conflict",
                f"User with email {user_create.email} already exists",
                409
            ))
        )

    user = user_create.model_dump()
    user["id"] = str(len(database["users"]) + 1)
    database["users"].append(user)

    return user, 201

@app.resource_exists
def user(path_params, database):
    """Returns None if not found, triggering automatic 404."""
    user_id = path_params['user_id']
    return next((u for u in database["users"] if u["id"] == user_id), None)

@app.get('/users/{user_id}')
def get_user(user):
    """404 handled automatically by resource_exists decorator."""
    return user

@app.get('/protected')
def protected_resource(current_user):
    return {"user": current_user, "message": "Access granted"}

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Use Appropriate Status Codes

Map errors to correct HTTP status codes:

```python
# Client errors (4xx)
- 400: Malformed request, validation errors
- 401: Missing or invalid authentication
- 403: Authenticated but lacking permissions
- 404: Resource not found
- 409: Resource conflict
- 422: Semantic validation error
- 429: Rate limit exceeded

# Server errors (5xx)
- 500: Unexpected server error
- 502: Bad gateway
- 503: Service unavailable
- 504: Gateway timeout
```

### 2. Don't Leak Sensitive Information

Hide internal details in production:

```python
@app.error_handler(500)
def safe_server_error(request, message, **kwargs):
    # DON'T: Expose internal details
    # return {"error": str(exc_info[1]), "stack": traceback}

    # DO: Return generic message
    return {"error": "Internal Server Error", "message": "An error occurred"}
```

### 3. Log All Server Errors

Always log server errors for debugging:

```python
@app.error_handler(500)
def logged_error(request, message, **kwargs):
    logger.error(f"Server error: {message}", exc_info=kwargs.get('exc_info'))
    return {"error": "Internal Server Error"}
```

### 4. Provide Actionable Error Messages

Help users fix the problem:

```python
# Bad
return {"error": "Invalid input"}

# Good
return {
    "error": "Validation Error",
    "message": "Email field is required",
    "field": "email"
}
```

### 5. Use Consistent Error Format

Maintain consistent structure across all errors:

```python
{
    "error": "Error Type",
    "message": "Human-readable message",
    "timestamp": "ISO 8601 timestamp",
    "path": "/api/endpoint",
    "details": {}  # Optional additional context
}
```

## Next Steps

- [Testing →](testing.md) - Test error handling
- [Content Negotiation →](content-negotiation.md) - Error responses in different formats
- [Deployment →](deployment/uvicorn.md) - Production error handling
- [Advanced Features →](../advanced/state-machine.md) - Understanding the error flow

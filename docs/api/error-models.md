# Error Models

::: restmachine.ErrorResponse
    options:
      show_root_heading: true
      heading_level: 2
      show_source: false

::: restmachine.ValidationError
    options:
      show_root_heading: true
      heading_level: 2
      show_source: false

## Overview

Error models provide structured error responses for REST APIs.

## ErrorResponse

Standard error response format:

```python
from restmachine import ErrorResponse

@app.get('/users/{user_id}')
def get_user(user_id: str):
    user = db.get(user_id)

    if not user:
        return ErrorResponse(
            error="Not Found",
            message=f"User {user_id} not found",
            status_code=404
        )

    return user
```

## ValidationError

Raised when request validation fails:

```python
from pydantic import BaseModel
from restmachine import ValidationError

class UserCreate(BaseModel):
    name: str
    email: str

@app.post('/users')
def create_user(request):
    try:
        data = UserCreate.model_validate_json(request.body)
    except Exception as e:
        raise ValidationError(str(e))

    return {"created": data.model_dump()}, 201
```

## See Also

- [Error Handling Guide](../guide/error-handling.md) - Complete guide
- [Application API](application.md) - Error handlers

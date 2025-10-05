# Validation

RestMachine provides flexible request validation through Pydantic integration. Use validation to ensure type safety, enforce business rules, and provide clear error messages.

## Basic Validation

### Installing Validation Support

Install RestMachine with Pydantic validation:

```bash
pip install restmachine[validation]
```

Or install Pydantic separately:

```bash
pip install pydantic
```

### Simple Model Validation

Use `@app.validates` to create a validation dependency:

```python
from restmachine import RestApplication, Request
from pydantic import BaseModel
import json

app = RestApplication()

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

@app.validates
def validate_user(request: Request) -> UserCreate:
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.post('/users')
def create_user(validate_user: UserCreate):
    return {
        "created": validate_user.model_dump()
    }, 201
```

## Pydantic Models

### Field Validation

Use Pydantic's field validators for rich validation:

```python
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=0, le=150)
    password: str = Field(..., min_length=8)
    bio: Optional[str] = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def name_must_not_contain_numbers(cls, v: str) -> str:
        if any(char.isdigit() for char in v):
            raise ValueError('name must not contain numbers')
        return v.strip()

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(char.isupper() for char in v):
            raise ValueError('password must contain uppercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('password must contain digit')
        return v

@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.post('/users')
def create_user(validate_user: UserCreate):
    user_data = validate_user.model_dump()
    # Hash password before storing
    user_data['password'] = hash_password(user_data['password'])
    return {"created": user_data}, 201
```

### Model Validation

Use `model_validator` for validations that span multiple fields:

```python
from pydantic import model_validator
from datetime import date

class EventCreate(BaseModel):
    title: str
    start_date: date
    end_date: date
    max_attendees: int = Field(..., gt=0)

    @model_validator(mode='after')
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError('end_date must be after start_date')
        return self

    @model_validator(mode='after')
    def check_duration(self):
        duration = (self.end_date - self.start_date).days
        if duration > 365:
            raise ValueError('event duration cannot exceed 1 year')
        return self

@app.validates
def validate_event(request: Request) -> EventCreate:
    import json
    data = json.loads(request.body)
    return EventCreate.model_validate(data)

@app.post('/events')
def create_event(validate_event: EventCreate):
    return {"created": validate_event.model_dump()}, 201
```

## Query Parameter Validation

Validate query parameters using Pydantic:

```python
from typing import Optional
from enum import Enum

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class ListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    order: SortOrder = SortOrder.asc

@app.validates
def validate_list_params(request: Request) -> ListParams:
    return ListParams.model_validate(request.query_params)

@app.get('/users')
def list_users(validate_list_params: ListParams, database):
    users = database["users"]

    # Apply sorting if specified
    if validate_list_params.sort_by:
        users = sorted(
            users,
            key=lambda u: u.get(validate_list_params.sort_by, ''),
            reverse=(validate_list_params.order == SortOrder.desc)
        )

    # Apply pagination
    offset = (validate_list_params.page - 1) * validate_list_params.limit
    return {
        "users": users[offset:offset+validate_list_params.limit],
        "page": validate_list_params.page,
        "limit": validate_list_params.limit,
        "total": len(users)
    }
```

## Path Parameter Validation

Validate path parameters using dependencies and Pydantic:

```python
from uuid import UUID
from pydantic import field_validator

class UserId(BaseModel):
    value: UUID

    @field_validator('value')
    @classmethod
    def validate_uuid(cls, v):
        # Additional validation if needed
        return v

@app.dependency()
def user_id(request: Request) -> UUID:
    raw_id = request.path_params.get('user_id')
    try:
        return UUID(raw_id)
    except ValueError:
        from restmachine import Response
        raise ValueError(f"Invalid user ID format: {raw_id}")

@app.get('/users/{user_id}')
def get_user(user_id: UUID, database):
    user = next(
        (u for u in database["users"] if u["id"] == str(user_id)),
        None
    )
    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')
    return user
```

## Custom Validators

### Reusable Validators

Create reusable validation functions:

```python
from typing import Annotated

def validate_phone_number(v: str) -> str:
    """Validate and normalize phone number."""
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, v))

    if len(digits) < 10:
        raise ValueError('phone number must have at least 10 digits')

    # Format as (XXX) XXX-XXXX
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    return digits

PhoneNumber = Annotated[str, field_validator('phone')(validate_phone_number)]

class ContactInfo(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_phone_number(v)

@app.validates
def validate_contact(request: Request) -> ContactInfo:
    import json
    data = json.loads(request.body)
    return ContactInfo.model_validate(data)

@app.post('/contacts')
def create_contact(validate_contact: ContactInfo):
    return {"contact": validate_contact.model_dump()}, 201
```

### Business Rule Validators

Implement complex business rules in validators:

```python
@app.dependency()
def database():
    return {
        "users": [
            {"id": "1", "email": "alice@example.com", "credits": 100},
            {"id": "2", "email": "bob@example.com", "credits": 50}
        ]
    }

class PurchaseRequest(BaseModel):
    user_id: str
    item_id: str
    quantity: int = Field(..., ge=1)
    price_per_item: float = Field(..., gt=0)

    @field_validator('quantity')
    @classmethod
    def quantity_limit(cls, v):
        if v > 100:
            raise ValueError('cannot purchase more than 100 items at once')
        return v

@app.dependency()
def validate_purchase(request: Request, database) -> PurchaseRequest:
    import json
    data = json.loads(request.body)
    purchase = PurchaseRequest.model_validate(data)

    # Check user exists and has sufficient credits
    user = next((u for u in database["users"] if u["id"] == purchase.user_id), None)
    if not user:
        raise ValueError(f"User {purchase.user_id} not found")

    total_cost = purchase.quantity * purchase.price_per_item
    if user["credits"] < total_cost:
        raise ValueError(
            f"Insufficient credits. Required: {total_cost}, Available: {user['credits']}"
        )

    return purchase

@app.post('/purchases')
def create_purchase(validate_purchase: PurchaseRequest):
    return {"purchase": validate_purchase.model_dump()}, 201
```

## Error Handling

### Default Error Responses

RestMachine automatically returns 400 Bad Request for validation errors:

```python
# Request: POST /users
# Body: {"name": "", "email": "invalid", "age": -5}

# Response: 400 Bad Request
# {
#   "error": "Validation Error",
#   "details": [
#     {"field": "name", "message": "String should have at least 1 character"},
#     {"field": "email", "message": "value is not a valid email address"},
#     {"field": "age", "message": "Input should be greater than or equal to 0"}
#   ]
# }
```

### Custom Error Handlers

Customize validation error responses:

```python
@app.error_handler(400)
def validation_error_handler(request, message, **kwargs):
    """Custom validation error response."""
    from pydantic import ValidationError

    # Check if this is a Pydantic validation error
    if 'validation_error' in kwargs:
        validation_error = kwargs['validation_error']
        if isinstance(validation_error, ValidationError):
            errors = []
            for error in validation_error.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in error['loc']),
                    "message": error['msg'],
                    "type": error['type']
                })

            return {
                "status": "error",
                "message": "Validation failed",
                "errors": errors,
                "path": request.path
            }

    # Generic 400 error
    return {
        "status": "error",
        "message": message,
        "path": request.path
    }
```

### Field-Level Error Messages

Provide user-friendly error messages:

```python
from pydantic import Field

class UserRegistration(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        description="Username must be 3-20 characters"
    )
    email: EmailStr = Field(
        ...,
        description="Must be a valid email address"
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters"
    )
    age: int = Field(
        ...,
        ge=18,
        le=120,
        description="Must be 18 or older"
    )

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('username must be alphanumeric')
        return v

    @field_validator('password')
    @classmethod
    def password_requirements(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('password must contain at least one number')
        if not any(c in '!@#$%^&*' for c in v):
            raise ValueError('password must contain at least one special character (!@#$%^&*)')
        return v
```

## Nested Models

### Validating Nested Data

Handle complex nested structures:

```python
from typing import List

class Address(BaseModel):
    street: str
    city: str
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')

class PhoneNumber(BaseModel):
    type: str  # "mobile", "home", "work"
    number: str

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if v not in ['mobile', 'home', 'work']:
            raise ValueError('type must be mobile, home, or work')
        return v

class UserProfile(BaseModel):
    name: str
    email: EmailStr
    address: Address
    phone_numbers: List[PhoneNumber] = Field(default_factory=list)

    @field_validator('phone_numbers')
    @classmethod
    def at_least_one_phone(cls, v):
        if not v:
            raise ValueError('at least one phone number is required')
        return v

@app.validates
def validate_profile(request: Request) -> UserProfile:
    import json
    data = json.loads(request.body)
    return UserProfile.model_validate(data)

@app.post('/profiles')
def create_profile(validate_profile: UserProfile):
    return {"profile": validate_profile.model_dump()}, 201

# Example request:
# {
#   "name": "Alice",
#   "email": "alice@example.com",
#   "address": {
#     "street": "123 Main St",
#     "city": "Springfield",
#     "state": "IL",
#     "zip_code": "62701"
#   },
#   "phone_numbers": [
#     {"type": "mobile", "number": "(555) 123-4567"}
#   ]
# }
```

## Partial Updates

### Validating PATCH Requests

Handle partial updates with optional fields:

```python
from typing import Optional

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    bio: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def at_least_one_field(self):
        if not any([self.name, self.email, self.age, self.bio]):
            raise ValueError('at least one field must be provided')
        return self

@app.validates
def validate_user_update(request: Request) -> UserUpdate:
    import json
    data = json.loads(request.body)
    return UserUpdate.model_validate(data)

@app.patch('/users/{user_id}')
def update_user(request: Request, validate_user_update: UserUpdate, database):
    user_id = request.path_params['user_id']
    user = next((u for u in database["users"] if u["id"] == user_id), None)

    if not user:
        from restmachine import Response
        return Response(404, '{"error": "User not found"}')

    # Update only provided fields
    update_data = validate_user_update.model_dump(exclude_unset=True)
    user.update(update_data)

    return user
```

## Content Type Validation

### Multiple Content Types

Validate different content types:

```python
@app.validates
def validate_user(request: Request) -> UserCreate:
    content_type = request.headers.get('content-type', '')

    if 'application/json' in content_type:
        import json
        data = json.loads(request.body)
        return UserCreate.model_validate(data)

    elif 'application/x-www-form-urlencoded' in content_type:
        from urllib.parse import parse_qs
        data = parse_qs(request.body.decode())
        # Convert query string format to dict
        cleaned_data = {k: v[0] if len(v) == 1 else v for k, v in data.items()}
        return UserCreate.model_validate(cleaned_data)

    else:
        from restmachine import Response
        raise ValueError('Unsupported content type')

@app.post('/users')
def create_user(validate_user: UserCreate):
    return {"created": validate_user.model_dump()}, 201
```

## Complete Example

Here's a complete example with validation:

```python
from restmachine import RestApplication, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
import json

app = RestApplication()

# Models
class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)

    @field_validator('name')
    @classmethod
    def lowercase_tag(cls, v):
        return v.lower().strip()

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: str
    tags: List[TagCreate] = Field(default_factory=list)
    published: bool = False

    @field_validator('tags')
    @classmethod
    def unique_tags(cls, v):
        tag_names = [tag.name for tag in v]
        if len(tag_names) != len(set(tag_names)):
            raise ValueError('tags must be unique')
        return v

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[TagCreate]] = None
    published: Optional[bool] = None

    @model_validator(mode='after')
    def at_least_one_field(self):
        if not any([self.title, self.content, self.tags, self.published]):
            raise ValueError('at least one field must be provided')
        return self

# Database
@app.on_startup
def database():
    return {
        "posts": [
            {
                "id": "1",
                "title": "First Post",
                "content": "Hello World",
                "author_id": "user1",
                "tags": ["python", "rest"],
                "published": True,
                "created_at": "2024-01-01T00:00:00"
            }
        ]
    }

# Validators
@app.validates
def validate_post(request: Request) -> PostCreate:
    data = json.loads(request.body)
    return PostCreate.model_validate(data)

@app.validates
def validate_post_update(request: Request) -> PostUpdate:
    data = json.loads(request.body)
    return PostUpdate.model_validate(data)

# Dependencies
@app.dependency()
def verify_author(validate_post: PostCreate, database):
    """Verify author exists."""
    # In real app, check user database
    if not validate_post.author_id:
        raise ValueError("author_id is required")
    return validate_post

# Routes
@app.post('/posts')
def create_post(verify_author: PostCreate, database):
    post = verify_author.model_dump()
    post["id"] = str(len(database["posts"]) + 1)
    post["created_at"] = datetime.now().isoformat()

    database["posts"].append(post)
    return post, 201

@app.get('/posts/{post_id}')
def get_post(request: Request, database):
    post_id = request.path_params['post_id']
    post = next((p for p in database["posts"] if p["id"] == post_id), None)

    if not post:
        return Response(404, json.dumps({"error": "Post not found"}))

    return post

@app.patch('/posts/{post_id}')
def update_post(request: Request, validate_post_update: PostUpdate, database):
    post_id = request.path_params['post_id']
    post = next((p for p in database["posts"] if p["id"] == post_id), None)

    if not post:
        return Response(404, json.dumps({"error": "Post not found"}))

    # Update only provided fields
    update_data = validate_post_update.model_dump(exclude_unset=True)
    post.update(update_data)

    return post

# Error handler
@app.error_handler(400)
def validation_error(request, message, **kwargs):
    return {
        "error": "Validation failed",
        "message": message,
        "path": request.path
    }

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Fail Fast

Validate as early as possible in the request lifecycle:

```python
# Good: Validate in dependency
@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    return UserCreate.model_validate(json.loads(request.body))

# Avoid: Validate in handler
@app.post('/users')
def create_user(request: Request):
    import json
    data = json.loads(request.body)  # Might fail
    user = UserCreate.model_validate(data)  # Validation too late
    ...
```

### 2. Provide Clear Error Messages

Use descriptive error messages:

```python
class UserCreate(BaseModel):
    age: int = Field(..., ge=18, description="Must be 18 or older")

    @field_validator('age')
    @classmethod
    def validate_age(cls, v):
        if v < 18:
            raise ValueError('You must be 18 or older to register')
        if v > 120:
            raise ValueError('Please enter a valid age')
        return v
```

### 3. Validate Business Rules

Combine Pydantic validation with business logic:

```python
@app.dependency()
def validate_unique_email(validate_user: UserCreate, database):
    existing = next(
        (u for u in database["users"] if u["email"] == validate_user.email),
        None
    )
    if existing:
        raise ValueError(f"Email {validate_user.email} is already registered")
    return validate_user
```

### 4. Use Type Hints

Leverage type hints for better IDE support:

```python
from typing import Annotated

UserId = Annotated[str, Field(pattern=r'^user_[a-z0-9]+$')]
Email = Annotated[str, EmailStr]

class User(BaseModel):
    id: UserId
    email: Email
    age: Annotated[int, Field(ge=18, le=120)]
```

### 5. Document Your Models

Add descriptions to help API consumers:

```python
class UserCreate(BaseModel):
    """User registration model."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Full name of the user"
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address for account verification"
    )
    age: int = Field(
        ...,
        ge=18,
        le=120,
        description="Age in years (must be 18 or older)"
    )
```

## Next Steps

- [Authentication →](authentication.md) - Secure your API with authentication
- [Error Handling →](error-handling.md) - Advanced error handling patterns
- [Testing →](testing.md) - Test validation logic
- [API Reference →](../api/models.md) - Complete API documentation

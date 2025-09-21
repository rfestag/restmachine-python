"""
Validation example for the REST Framework using Pydantic.

This example demonstrates:
- Pydantic model validation
- Request validation with @validates decorator
- Response validation with return type annotations
- Automatic 422 error responses for validation failures
- Custom validation logic

Requires: pip install restmachine[validation]
"""

try:
    from typing import List, Optional

    from pydantic import BaseModel, EmailStr, Field, validator

    PYDANTIC_AVAILABLE = True
except ImportError:
    print(
        "This example requires Pydantic. Install with: pip install restmachine[validation]"
    )
    exit(1)

import json

from restmachine import HTTPMethod, Request, Response, RestApplication

# Create the application
app = RestApplication()


# Pydantic models for validation
class UserCreate(BaseModel):
    """Model for creating a new user."""

    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: str = Field(..., description="User's email address")
    age: int = Field(..., ge=0, le=150, description="User's age")
    bio: Optional[str] = Field(None, max_length=500, description="User's biography")
    tags: List[str] = Field(default_factory=list, description="User tags")

    @validator("email")
    def validate_email(cls, v):
        """Custom email validation."""
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower()

    @validator("name")
    def validate_name(cls, v):
        """Custom name validation."""
        if len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return v.title()


class UserResponse(BaseModel):
    """Model for user responses."""

    id: int
    name: str
    email: str
    age: int
    bio: Optional[str] = None
    tags: List[str] = []
    created_at: str


class UserUpdate(BaseModel):
    """Model for updating a user."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    bio: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None

    @validator("email")
    def validate_email(cls, v):
        if v is not None:
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("Invalid email format")
            return v.lower()
        return v


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str
    details: Optional[List[dict]] = None


# In-memory storage
users_store = {}
next_user_id = 1


# Dependencies
@app.dependency()
def user_storage():
    """Provide access to user storage."""
    return users_store


@app.dependency()
def next_id():
    """Generate next user ID."""
    global next_user_id
    current_id = next_user_id
    next_user_id += 1
    return current_id


# Validation functions
@app.validates
def validate_user_create(request: Request) -> UserCreate:
    """Validate user creation request."""
    if not request.body:
        raise ValueError("Request body is required")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")

    # This will raise ValidationError if data is invalid
    return UserCreate.model_validate(data)


@app.validates
def validate_user_update(request: Request) -> UserUpdate:
    """Validate user update request."""
    if not request.body:
        raise ValueError("Request body is required")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")

    return UserUpdate.model_validate(data)


# Resource existence checking
@app.resource_exists
def user_exists(request: Request, user_storage):
    """Check if user exists and return user data."""
    user_id = request.path_params.get("user_id")
    if user_id is None:
        return None

    try:
        user_id = int(user_id)
    except ValueError:
        return None

    return user_storage.get(user_id)


# Routes with validation
@app.get("/")
def home() -> dict:
    """API home with endpoint information."""
    return {
        "name": "REST Framework Validation Example",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "This endpoint",
            "GET /users": "List all users",
            "POST /users": "Create a new user",
            "GET /users/{id}": "Get user by ID",
            "PUT /users/{id}": "Update user by ID",
            "DELETE /users/{id}": "Delete user by ID",
        },
        "validation": "This API uses Pydantic for request/response validation",
    }


@app.get("/users")
def list_users(user_storage) -> List[UserResponse]:
    """List all users with response validation."""
    from datetime import datetime

    users = []
    for user_id, user_data in user_storage.items():
        # Convert stored data to UserResponse format
        user_response = UserResponse(
            id=user_id,
            name=user_data["name"],
            email=user_data["email"],
            age=user_data["age"],
            bio=user_data.get("bio"),
            tags=user_data.get("tags", []),
            created_at=user_data.get("created_at", datetime.now().isoformat()),
        )
        users.append(user_response)

    return users


@app.post("/users")
def create_user(
    validate_user_create: UserCreate, user_storage, next_id
) -> UserResponse:
    """Create a new user with validation."""
    from datetime import datetime

    user_data = validate_user_create.model_dump()
    user_id = next_id
    user_data["created_at"] = datetime.now().isoformat()

    # Store user
    user_storage[user_id] = user_data

    # Return validated response
    return UserResponse(id=user_id, **user_data)


@app.get("/users/{user_id}")
def get_user(user_exists) -> UserResponse:
    """Get user by ID with validation."""
    from datetime import datetime

    # user_exists is automatically injected and validated by @resource_exists
    user_data = user_exists
    user_id = [k for k, v in users_store.items() if v == user_data][0]

    return UserResponse(
        id=user_id,
        name=user_data["name"],
        email=user_data["email"],
        age=user_data["age"],
        bio=user_data.get("bio"),
        tags=user_data.get("tags", []),
        created_at=user_data.get("created_at", datetime.now().isoformat()),
    )


@app.put("/users/{user_id}")
def update_user(
    validate_user_update: UserUpdate, user_exists, request: Request, user_storage
) -> UserResponse:
    """Update user with validation."""
    from datetime import datetime

    user_id = int(request.path_params["user_id"])
    current_user = user_exists

    # Apply updates
    update_data = validate_user_update.model_dump(exclude_unset=True)
    updated_user = {**current_user, **update_data}

    # Store updated user
    user_storage[user_id] = updated_user

    return UserResponse(
        id=user_id,
        name=updated_user["name"],
        email=updated_user["email"],
        age=updated_user["age"],
        bio=updated_user.get("bio"),
        tags=updated_user.get("tags", []),
        created_at=updated_user.get("created_at", datetime.now().isoformat()),
    )


@app.delete("/users/{user_id}")
def delete_user(user_exists, request: Request, user_storage) -> dict:
    """Delete user."""
    user_id = int(request.path_params["user_id"])
    deleted_user = user_storage.pop(user_id)

    return {
        "message": f"User {user_id} deleted successfully",
        "deleted_user": {"name": deleted_user["name"], "email": deleted_user["email"]},
    }


def main():
    """Demonstrate the validation API."""
    print("REST Framework Validation Example")
    print("=" * 35)

    # Test valid user creation
    print("1. Creating a valid user:")
    valid_user = {
        "name": "john doe",  # Will be title-cased
        "email": "JOHN@EXAMPLE.COM",  # Will be lowercased
        "age": 30,
        "bio": "Software developer",
        "tags": ["developer", "python"],
    }

    response = app.execute(
        Request(
            method=HTTPMethod.POST,
            path="/users",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(valid_user),
        )
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test invalid user creation (validation error)
    print("2. Creating an invalid user (should return 422):")
    invalid_user = {
        "name": "",  # Empty name
        "email": "invalid-email",  # Invalid email
        "age": -5,  # Invalid age
        "bio": "x" * 600,  # Bio too long
    }

    response = app.execute(
        Request(
            method=HTTPMethod.POST,
            path="/users",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(invalid_user),
        )
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test getting user
    print("3. Getting the created user:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/users/1",
            headers={"Accept": "application/json"},
        )
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test updating user
    print("4. Updating the user:")
    update_data = {"age": 31, "bio": "Senior software developer"}

    response = app.execute(
        Request(
            method=HTTPMethod.PUT,
            path="/users/1",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(update_data),
        )
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test listing users
    print("5. Listing all users:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET, path="/users", headers={"Accept": "application/json"}
        )
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()


if __name__ == "__main__":
    main()

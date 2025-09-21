"""
Basic usage example for the REST Framework.

This example demonstrates:
- Simple route registration
- Path parameters
- Dependency injection
- Basic error handling
"""

import json
from pydantic import BaseModel
from restmachine import HTTPMethod, Request, Response, RestApplication

# Create the application
app = RestApplication()

class User(BaseModel):
    id: str
    name: str
    email: str

class CreateUser(BaseModel):
    name: str
    email: str

# In-memory data store for this example
users_db = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com"},
}


# Simple dependency
@app.dependency()
def user_database():
    """Provide access to the user database."""
    return users_db

@app.validates
def create_user_request(body) -> CreateUser:
    """Validate create user request."""
    return CreateUser.model_validate(json.loads(body))


@app.resource_exists
def user(path_params, user_database) -> User:
    user = user_database.get(path_params.get("user_id"))
    if user is None:
        return None
    return User(**user)


@app.get("/users")
def list_users(user_database) -> list[User]:
    """List all users."""
    return [User(**u) for u in user_database.values()]


@app.post("/users")
def create_user(user_database, create_user_request) -> User:
    """Create a new user"""
    keys = list(user_database.keys())
    if keys:
        last_key = keys[-1]
        new_id = str(int(last_key) + 1)
    else:
        new_id = "1"
    new_user = User(**create_user_request.model_dump(), id=new_id)
    user_database[new_id] = new_user.model_dump()
    return new_user

@app.get("/users/{user_id}")
def get_user(user) -> User:
    """Get a specific user by ID."""
    return user

@app.delete("/users/{user_id}")
def delete_user(user_database, user) -> None:
    """Delete a specific user by ID."""
    del user_database[user.id]

def main():
    """Demonstrate the API with some example requests."""
    print("REST Framework Basic Example")
    print("=" * 30)

    # Test list users endpoint
    response = app.execute(
        Request(method=HTTPMethod.GET, path="/users", headers={"Accept": "application/json"})
    )
    print(f"GET /users: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test get user endpoint
    response = app.execute(
        Request(method=HTTPMethod.GET, path="/users/1", headers={"Accept": "application/json"})
    )
    print(f"GET /users/1: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test get non-existent user endpoint
    response = app.execute(
        Request(method=HTTPMethod.GET, path="/users/3", headers={"Accept": "application/json"})
    )
    print(f"GET /users/3: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test create user endpoint
    new_user = {"name": "Steve", "email": "steve@example.com"}
    response = app.execute(
        Request(
            method=HTTPMethod.POST, 
            path="/users", 
            headers={"Accept": "application/json"},
            body=json.dumps(new_user),
        )
    )
    print(f"POST /users: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test delete user endpoint
    response = app.execute(
        Request(method=HTTPMethod.DELETE, path="/users/1", headers={"Accept": "application/json"})
    )
    print(f"DELETE /users/1: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Test delete non-existent endpoint
    response = app.execute(
        Request(method=HTTPMethod.DELETE, path="/users/1", headers={"Accept": "application/json"})
    )
    print(f"DELETE /users/1: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # Final list after additions/removals
    response = app.execute(
        Request(method=HTTPMethod.GET, path="/users", headers={"Accept": "application/json"})
    )
    print(f"GET /users: {response.status_code}")
    print(f"Response: {response.body}")
    print()

if __name__ == "__main__":
    main()

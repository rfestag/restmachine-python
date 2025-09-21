"""
Basic usage example for the REST Framework.

This example demonstrates:
- Simple route registration
- Path parameters
- Dependency injection
- Different content types
- Basic error handling
"""

from rest_framework import RestApplication, Request, Response, HTTPMethod

# Create the application
app = RestApplication()

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

# Basic routes
@app.get('/')
def home():
    """Home endpoint."""
    return {
        "message": "Welcome to REST Framework!",
        "endpoints": [
            "GET /",
            "GET /users",
            "GET /users/{user_id}",
            "POST /users",
            "PUT /users/{user_id}",
            "DELETE /users/{user_id}"
        ]
    }

@app.get('/users')
def list_users(user_database):
    """List all users."""
    return {"users": list(user_database.values())}

@app.get('/users/{user_id}')
def get_user(user_database, request: Request):
    """Get a specific user by ID."""
    user_id = request.path_params['user_id']
    user = user_database.get(user_id)
    
    if not user:
        return Response(404, '{"error": "User not found"}', content_type="application/json")
    
    return user

def main():
    """Demonstrate the API with some example requests."""
    print("REST Framework Basic Example")
    print("=" * 30)
    
    # Test home endpoint
    response = app.execute(Request(
        method=HTTPMethod.GET,
        path='/',
        headers={'Accept': 'application/json'}
    ))
    print(f"GET /: {response.status_code}")
    print(f"Response: {response.body}")
    print()

if __name__ == "__main__":
    main()

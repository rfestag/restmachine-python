"""
Example demonstrating dependency injection scopes.

This example shows the difference between request-scoped and session-scoped dependencies.
"""

from restmachine import RestApplication


# Create the REST application
app = RestApplication()


# Example 1: Request-scoped dependency (default)
# This dependency is re-evaluated on every request
request_counter = {"value": 0}


@app.dependency(scope="request")  # scope="request" is the default
def get_request_count():
    """A request-scoped dependency that increments on each evaluation."""
    request_counter["value"] += 1
    return request_counter["value"]


# Example 2: Session-scoped dependency
# This dependency is evaluated once and cached across all requests
class DatabaseConnection:
    """Simulated database connection."""

    connection_count = 0

    def __init__(self):
        DatabaseConnection.connection_count += 1
        self.connection_id = DatabaseConnection.connection_count
        self.queries_executed = 0

    def query(self, sql: str):
        """Execute a query."""
        self.queries_executed += 1
        return f"Result from connection {self.connection_id} (query #{self.queries_executed})"


@app.dependency(name="db", scope="session")
def get_database():
    """
    A session-scoped database connection.

    This will be created once and reused across all requests.
    Perfect for expensive resources like database connections,
    API clients, or cache connections.
    """
    return DatabaseConnection()


# Routes that use the dependencies
@app.get("/request-scoped")
def request_scoped_endpoint(get_request_count):
    """
    This endpoint uses a request-scoped dependency.
    Each request will get a new counter value.
    """
    return {
        "message": "Request-scoped dependency example",
        "counter": get_request_count,
        "note": "This counter increments on every request"
    }


@app.get("/session-scoped")
def session_scoped_endpoint(db):
    """
    This endpoint uses a session-scoped dependency.
    The same database connection is reused across all requests.
    """
    result = db.query("SELECT * FROM users")
    return {
        "message": "Session-scoped dependency example",
        "connection_id": db.connection_id,
        "queries_executed": db.queries_executed,
        "query_result": result,
        "note": "The same connection is reused across all requests"
    }


@app.get("/mixed-scopes")
def mixed_scopes_endpoint(get_request_count, db):
    """
    This endpoint uses both request and session scoped dependencies.
    """
    result = db.query("SELECT COUNT(*) FROM users")
    return {
        "request_counter": get_request_count,  # Increments per request
        "connection_id": db.connection_id,      # Same across all requests
        "queries_executed": db.queries_executed, # Accumulates across requests
        "query_result": result
    }


# Example 3: Using scope with other decorators
@app.get("/users/{user_id}")
@app.resource_exists
def check_user_exists(user_id, db, scope="session"):
    """
    Resource existence check with session-scoped database.

    Note: The scope parameter is passed to the decorator, not the function.
    """
    # Query the database to check if user exists
    db.query(f"SELECT * FROM users WHERE id = {user_id}")
    # In a real app, you'd parse the result and check if user exists
    return {"id": user_id, "exists": True}


def get_user_details(user_id, check_user_exists, db):
    """Endpoint handler that uses the resource check."""
    result = db.query(f"SELECT * FROM users WHERE id = {user_id}")
    return {
        "user_id": user_id,
        "connection_id": db.connection_id,
        "query_result": result
    }


if __name__ == "__main__":
    from restmachine import serve

    print("Starting server...")
    print("\nTry these endpoints:")
    print("  - http://localhost:8000/request-scoped (increments counter each time)")
    print("  - http://localhost:8000/session-scoped (reuses same DB connection)")
    print("  - http://localhost:8000/mixed-scopes (uses both scopes)")
    print()
    print("Notice how:")
    print("  - Request-scoped dependencies reset between requests")
    print("  - Session-scoped dependencies persist across all requests")
    print()

    serve(app, port=8000)

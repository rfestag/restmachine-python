"""
Example demonstrating how to use the AWS API Gateway adapter with a REST application.

This example shows how to set up a REST application that can be deployed as an AWS Lambda
function and handle API Gateway events.

Key features demonstrated:
- AWS Lambda cold start optimization with startup handlers
- Database connection management via dependency injection
- Session-scoped dependencies for resource reuse across warm invocations
"""

from restmachine import AwsApiGatewayAdapter, RestApplication

# Create the REST application
app = RestApplication()


# Startup handlers execute during Lambda cold start (before first request)
# Their return values are cached as session-scoped dependencies
@app.on_startup
def database():
    """
    Initialize database connection during Lambda cold start.

    This executes once when the Lambda container starts (cold start).
    The connection is reused across all requests in the same container (warm starts).
    """
    print("Opening database connection...")
    # In a real application, this would create a real database connection:
    # import pymysql
    # return pymysql.connect(host='...', user='...', password='...', db='...')
    return {"connection": "mock_db_connection", "pool_size": 10}


@app.on_startup
def api_client():
    """
    Initialize external API client during Lambda cold start.

    Like database connections, API clients are expensive to create,
    so we initialize them once and reuse across requests.
    """
    print("Creating external API client...")
    # In a real application:
    # import requests
    # return requests.Session()
    return {"client": "mock_api_client", "base_url": "https://api.example.com"}


# Create the AWS API Gateway adapter
# IMPORTANT: Startup handlers execute automatically when adapter is initialized
adapter = AwsApiGatewayAdapter(app)


# Define some routes
@app.get("/")
def health_check(database, api_client):
    """
    Health check endpoint that uses startup dependencies.

    The database and api_client parameters are automatically injected
    from the startup handlers above - no additional configuration needed!
    """
    return {
        "status": "healthy",
        "message": "API is running",
        "database_status": "connected" if database else "disconnected",
        "api_client_status": "ready" if api_client else "unavailable"
    }


@app.get("/users/{user_id}")
def get_user(user_id, database):
    """
    Get user by ID using the database connection.

    The database parameter is injected from the startup handler.
    This connection was created during cold start and is reused
    across all requests in this Lambda container.
    """
    # In a real application, you would use the database connection:
    # cursor = database.cursor()
    # cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    # user = cursor.fetchone()
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
        "db_connection": database.get("connection", "unknown")
    }


@app.post("/users")
def create_user(json_body):
    """Create a new user."""
    # In a real application, you would save to a database
    new_user = {
        "id": "new-user-id",
        "name": json_body.get("name"),
        "email": json_body.get("email"),
        "created": True
    }

    return new_user


@app.get("/search")
def search_users(query_params):
    """Search users with query parameters."""
    query = query_params.get("q", "")
    limit = int(query_params.get("limit", "10"))

    # In a real application, you would search a database
    return {
        "query": query,
        "limit": limit,
        "results": [
            {"id": "1", "name": f"User matching '{query}'"},
            {"id": "2", "name": f"Another user matching '{query}'"}
        ][:limit]
    }


# AWS Lambda handler function
def lambda_handler(event, context):
    """
    AWS Lambda handler function for API Gateway events.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    return adapter.handle_event(event, context)


# Example usage and testing
if __name__ == "__main__":
    # Example API Gateway event for testing locally
    sample_event = {
        "httpMethod": "GET",
        "path": "/users/123",
        "headers": {
            "Accept": "application/json",
            "Host": "example.execute-api.us-east-1.amazonaws.com"
        },
        "pathParameters": {
            "user_id": "123"
        },
        "queryStringParameters": None,
        "body": None,
        "isBase64Encoded": False
    }

    # Test the handler locally
    response = lambda_handler(sample_event, None)
    print("Response:", response)

    # Example POST event
    post_event = {
        "httpMethod": "POST",
        "path": "/users",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        "pathParameters": None,
        "queryStringParameters": None,
        "body": '{"name": "John Doe", "email": "john@example.com"}',
        "isBase64Encoded": False
    }

    post_response = lambda_handler(post_event, None)
    print("POST Response:", post_response)

    # Example search event
    search_event = {
        "httpMethod": "GET",
        "path": "/search",
        "headers": {
            "Accept": "application/json"
        },
        "pathParameters": None,
        "queryStringParameters": {
            "q": "john",
            "limit": "5"
        },
        "body": None,
        "isBase64Encoded": False
    }

    search_response = lambda_handler(search_event, None)
    print("Search Response:", search_response)

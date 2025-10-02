"""
Example demonstrating how to use the AWS API Gateway adapter with a REST application.

This example shows how to set up a REST application that can be deployed as an AWS Lambda
function and handle API Gateway events.
"""

from restmachine import AwsApiGatewayAdapter, RestApplication

# Create the REST application
app = RestApplication()

# Create the AWS API Gateway adapter
adapter = AwsApiGatewayAdapter(app)


# Define some routes
@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "API is running"}


@app.get("/users/{user_id}")
def get_user(user_id):
    """Get user by ID."""
    # In a real application, you would fetch from a database
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
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

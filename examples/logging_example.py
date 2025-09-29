#!/usr/bin/env python3
"""
Example demonstrating comprehensive logging in restmachine.

This example shows how to configure logging to see different log levels:
- DEBUG: State machine flow and decisions
- WARNING: Gracefully handled exceptions
- ERROR: Security failures (401/403) and server errors (500)
"""

import logging
from restmachine import RestApplication
from restmachine.models import Request, HTTPMethod

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def create_app():
    """Create a sample application with various endpoints."""
    app = RestApplication()

    @app.get("/")
    def home():
        return {"message": "Welcome to the logging example!"}

    @app.get("/protected")
    def protected():
        return {"message": "This is protected data"}

    @app.authorized
    def check_auth(headers: dict):
        """Authorization check - will fail without proper token."""
        auth_header = headers.get("Authorization", "")
        return auth_header.startswith("Bearer valid-token")

    @app.get("/forbidden")
    def forbidden_resource():
        return {"message": "This should be forbidden"}

    @app.forbidden
    def check_forbidden(headers: dict):
        """Always return forbidden for this demo."""
        return True  # True means forbidden

    @app.get("/error")
    def error_endpoint():
        """Endpoint that generates an error."""
        raise ValueError("Intentional error for logging demonstration")

    return app

if __name__ == "__main__":
    # Set up logging to see all messages
    setup_logging()

    app = create_app()

    print("=== Logging Example for restmachine ===\n")

    # Example 1: Normal request (DEBUG logs)
    print("1. Normal request - shows DEBUG state machine flow:")
    request = Request(method=HTTPMethod.GET, path="/", headers={})
    response = app.execute(request)
    print(f"   Response: {response.status_code}\n")

    # Example 2: Authorization failure (ERROR logs)
    print("2. Authorization failure - shows ERROR logs:")
    request = Request(method=HTTPMethod.GET, path="/protected", headers={})
    response = app.execute(request)
    print(f"   Response: {response.status_code}\n")

    # Example 3: Forbidden access (ERROR logs)
    print("3. Forbidden access - shows ERROR logs:")
    request = Request(method=HTTPMethod.GET, path="/forbidden", headers={})
    response = app.execute(request)
    print(f"   Response: {response.status_code}\n")

    # Example 4: Route not found (DEBUG logs)
    print("4. Route not found - shows DEBUG logs stopping at route_exists:")
    request = Request(method=HTTPMethod.GET, path="/nonexistent", headers={})
    response = app.execute(request)
    print(f"   Response: {response.status_code}\n")

    print("=== End of Logging Example ===")
    print("\nLog levels used in restmachine:")
    print("- DEBUG: State machine transitions and flow decisions")
    print("- WARNING: Gracefully handled exceptions (ETag/header generation failures)")
    print("- ERROR: Security failures (401/403) and server errors (500)")
    print("- INFO: Not used by the library itself (reserved for examples/tests)")
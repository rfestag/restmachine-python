"""
Demonstration of the 4-layer testing architecture.

This shows how the same test can run against different drivers
to ensure the library works consistently across environments.
"""

import pytest

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver, MockDriver


class TestFrameworkDemo:
    """Demonstrate the testing framework capabilities."""

    def test_simple_api_with_direct_driver(self):
        """Test API using direct RestMachine driver."""
        # Set up the system under test (Layer 4)
        app = RestApplication()

        @app.get("/hello")
        def hello():
            return {"message": "Hello World"}

        # Set up the driver (Layer 3)
        driver = RestMachineDriver(app)

        # Set up the DSL (Layer 2)
        api = RestApiDsl(driver)

        # Test (Layer 1) - focus on business scenarios
        response = api.get_resource("/hello")
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"

    def test_simple_api_with_aws_lambda_driver(self):
        """Test the same API using AWS Lambda driver."""
        # Same system under test (Layer 4)
        app = RestApplication()

        @app.get("/hello")
        def hello():
            return {"message": "Hello World"}

        # Different driver (Layer 3) - tests AWS Lambda deployment scenario
        driver = AwsLambdaDriver(app)

        # Same DSL (Layer 2)
        api = RestApiDsl(driver)

        # Same test (Layer 1) - ensures consistency across deployments
        response = api.get_resource("/hello")
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"

    @pytest.mark.parametrize("driver_type", ["direct", "aws_lambda"])
    def test_crud_operations_across_drivers(self, driver_type):
        """Test CRUD operations work consistently across different drivers."""
        # Set up API
        app = RestApplication()
        users = {}  # Simple in-memory store

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            user = users.get(user_id)
            if not user:
                from restmachine import Response
                return Response(404, "Not Found")
            return user

        @app.post("/users")
        def create_user(json_body):
            user_id = str(len(users) + 1)
            user = {"id": user_id, **json_body}
            users[user_id] = user
            return user

        @app.put("/users/{user_id}")
        def update_user(path_params, json_body):
            user_id = path_params["user_id"]
            if user_id not in users:
                from restmachine import Response
                return Response(404, "Not Found")
            users[user_id].update(json_body)
            return users[user_id]

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            user_id = path_params["user_id"]
            if user_id not in users:
                from restmachine import Response
                return Response(404, "Not Found")
            del users[user_id]
            return None  # 204 No Content

        # Select driver
        if driver_type == "direct":
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        api = RestApiDsl(driver)

        # Test full CRUD cycle
        # Create
        user_data = {"name": "John Doe", "email": "john@example.com"}
        create_response = api.create_resource("/users", user_data)
        created_user = api.expect_successful_creation(create_response, ["id", "name", "email"])
        user_id = created_user["id"]

        # Read
        read_response = api.get_resource(f"/users/{user_id}")
        retrieved_user = api.expect_successful_retrieval(read_response)
        assert retrieved_user["name"] == "John Doe"
        assert retrieved_user["email"] == "john@example.com"

        # Update
        update_data = {"name": "Jane Doe"}
        update_response = api.update_resource(f"/users/{user_id}", update_data)
        updated_user = api.expect_successful_retrieval(update_response)
        assert updated_user["name"] == "Jane Doe"
        assert updated_user["email"] == "john@example.com"  # Should be unchanged

        # Delete
        delete_response = api.delete_resource(f"/users/{user_id}")
        api.expect_no_content(delete_response)

        # Verify deletion
        get_deleted_response = api.get_resource(f"/users/{user_id}")
        api.expect_not_found(get_deleted_response)

    def test_mock_driver_for_testing_framework(self):
        """Test the mock driver to verify the framework itself."""
        from tests.framework import MockDriver, HttpResponse

        # Set up mock driver
        mock = MockDriver()

        # Queue expected responses
        mock.expect_response(HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"message": "Mocked response"}
        ))

        # Set up DSL with mock
        api = RestApiDsl(mock)

        # Execute request
        response = api.get_resource("/test")

        # Verify mock behavior
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Mocked response"

        # Verify request was recorded
        requests = mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert requests[0].path == "/test"

    def test_dsl_fluent_interface(self):
        """Test the DSL's fluent interface for building requests."""
        from tests.framework import HttpResponse

        mock = MockDriver()
        mock.expect_response(HttpResponse(200, body={"success": True}))

        api = RestApiDsl(mock)

        # Demonstrate fluent interface
        request = (api.post("/users")
                  .with_json_body({"name": "Test User"})
                  .with_auth("token123")
                  .with_header("X-Custom", "value")
                  .accepts("application/json"))

        api.execute(request)

        # Verify the request was built correctly
        recorded_request = mock.get_requests()[0]
        assert recorded_request.method == "POST"
        assert recorded_request.path == "/users"
        assert recorded_request.headers["Authorization"] == "Bearer token123"
        assert recorded_request.headers["X-Custom"] == "value"
        assert recorded_request.headers["Accept"] == "application/json"
        assert recorded_request.headers["Content-Type"] == "application/json"
        assert recorded_request.body == {"name": "Test User"}

    def test_error_handling_patterns(self):
        """Test common error handling patterns using the DSL."""
        app = RestApplication()

        @app.get("/error")
        def error_endpoint():
            raise Exception("Something went wrong")

        @app.get("/not-found")
        def not_found():
            from restmachine import Response
            return Response(404, "Resource not found")

        driver = RestMachineDriver(app)
        api = RestApiDsl(driver)

        # Test server error
        error_response = api.get_resource("/error")
        assert error_response.is_server_error()

        # Test not found
        not_found_response = api.get_resource("/not-found")
        api.expect_not_found(not_found_response)

        # Test nonexistent endpoint
        nonexistent_response = api.get_resource("/does-not-exist")
        api.expect_not_found(nonexistent_response)

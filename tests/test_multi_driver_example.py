"""
Example test file demonstrating the new multi-driver approach.

This test file defines a single app in create_app() and automatically runs
each test method against all enabled drivers.
"""

import pytest
from restmachine import RestApplication, Response
from tests.framework import (
    MultiDriverTestBase,
    skip_driver,
    only_drivers,
    multi_driver_test_class
)


class TestBasicApiWithAllDrivers(MultiDriverTestBase):
    """
    Example test class using the new multi-driver approach.

    Each test method will automatically run against all enabled drivers:
    - direct (RestMachineDriver)
    - aws_lambda (AwsLambdaDriver with full binary support and debugging)
    """

    def create_app(self) -> RestApplication:
        """Create the application under test."""
        app = RestApplication()

        # Simple CRUD API for users
        users = {}  # In-memory storage

        @app.get("/")
        def home():
            return {"message": "Hello World", "version": "1.0.0"}

        @app.get("/users")
        def list_users():
            return {"users": list(users.values())}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            user = users.get(user_id)
            if not user:
                return Response(404, "User not found")
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
                return Response(404, "User not found")
            users[user_id].update(json_body)
            return users[user_id]

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            user_id = path_params["user_id"]
            if user_id not in users:
                return Response(404, "User not found")
            del users[user_id]
            return None  # 204 No Content

        @app.get("/error")
        def error_endpoint():
            raise Exception("Intentional error for testing")

        return app

    def test_home_endpoint(self, api):
        """Test home endpoint works across all drivers."""
        api_client, driver_name = api

        response = api_client.get_resource("/")
        data = api_client.expect_successful_retrieval(response)

        assert data["message"] == "Hello World"
        assert data["version"] == "1.0.0"

    def test_full_crud_cycle(self, api):
        """Test complete CRUD operations work across all drivers."""
        api_client, driver_name = api

        # Create user
        user_data = {"name": "John Doe", "email": "john@example.com"}
        create_response = api_client.create_resource("/users", user_data)
        created_user = api_client.expect_successful_creation(create_response, ["id", "name", "email"])
        user_id = created_user["id"]

        # Read user
        read_response = api_client.get_resource(f"/users/{user_id}")
        retrieved_user = api_client.expect_successful_retrieval(read_response)
        assert retrieved_user["name"] == "John Doe"
        assert retrieved_user["email"] == "john@example.com"

        # Update user
        update_data = {"name": "Jane Doe"}
        update_response = api_client.update_resource(f"/users/{user_id}", update_data)
        updated_user = api_client.expect_successful_retrieval(update_response)
        assert updated_user["name"] == "Jane Doe"
        assert updated_user["email"] == "john@example.com"  # Should be unchanged

        # List users
        list_response = api_client.get_resource("/users")
        users_data = api_client.expect_successful_retrieval(list_response)
        assert len(users_data["users"]) >= 1

        # Delete user
        delete_response = api_client.delete_resource(f"/users/{user_id}")
        api_client.expect_no_content(delete_response)

        # Verify deletion
        get_deleted_response = api_client.get_resource(f"/users/{user_id}")
        api_client.expect_not_found(get_deleted_response)

    def test_error_handling(self, api):
        """Test error handling works across all drivers."""
        api_client, driver_name = api

        # Test server error
        error_response = api_client.get_resource("/error")
        assert error_response.is_server_error()

        # Test not found
        not_found_response = api_client.get_resource("/users/999")
        api_client.expect_not_found(not_found_response)

        # Test nonexistent endpoint
        nonexistent_response = api_client.get_resource("/does-not-exist")
        api_client.expect_not_found(nonexistent_response)

    @skip_driver('mock', 'Mock driver does not execute real application logic')
    def test_skipped_for_mock_driver(self, api):
        """This test will be skipped when running with mock driver."""
        api_client, driver_name = api

        response = api_client.get_resource("/")
        data = api_client.expect_successful_retrieval(response)
        assert "message" in data

    @only_drivers('direct', 'aws_lambda')
    def test_only_certain_drivers(self, api):
        """This test only runs on direct and aws_lambda drivers."""
        api_client, driver_name = api

        response = api_client.get_resource("/")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"


@multi_driver_test_class(enabled_drivers=['direct', 'aws_lambda'])
class TestCustomDriverSelection(MultiDriverTestBase):
    """
    Example test class with custom driver selection.

    This class only runs tests against direct and aws_lambda drivers.
    """

    def create_app(self) -> RestApplication:
        """Create a simple app for testing."""
        app = RestApplication()

        @app.get("/ping")
        def ping():
            return {"status": "pong"}

        return app

    def test_ping_endpoint(self, api):
        """Test ping endpoint on selected drivers."""
        api_client, driver_name = api

        response = api_client.get_resource("/ping")
        data = api_client.expect_successful_retrieval(response)
        assert data["status"] == "pong"


class TestConsistentBehaviorAcrossDrivers(MultiDriverTestBase):
    """
    Example test class demonstrating proper multi-driver testing.

    This class shows how tests should work consistently across all drivers
    without any driver-specific conditional logic or assertions.

    The key principle: if your test needs different assertions for different
    drivers, the abstraction is leaky and the logic should be moved to the
    driver layer instead.
    """

    def create_app(self) -> RestApplication:
        """Create app that behaves consistently across all drivers."""
        app = RestApplication()

        @app.get("/info")
        def get_info():
            return {
                "service": "test-api",
                "environment": "test",
                "status": "healthy"
            }

        @app.get("/health")
        def health_check():
            return {"status": "ok"}

        return app

    def test_consistent_response_structure(self, api):
        """Test that response structure is identical across all drivers."""
        api_client, driver_name = api

        response = api_client.get_resource("/info")
        data = api_client.expect_successful_retrieval(response)

        # These assertions work the same regardless of driver
        # If they don't, then the drivers need to be fixed, not the test
        assert data["service"] == "test-api"
        assert data["environment"] == "test"
        assert data["status"] == "healthy"
        assert response.status_code == 200

    def test_consistent_error_handling(self, api):
        """Test that error handling is consistent across all drivers."""
        api_client, driver_name = api

        # 404 for non-existent endpoint should work the same everywhere
        response = api_client.get_resource("/does-not-exist")
        api_client.expect_not_found(response)

    def test_consistent_success_patterns(self, api):
        """Test that success patterns work identically."""
        api_client, driver_name = api

        response = api_client.get_resource("/health")
        data = api_client.expect_successful_retrieval(response)

        # Simple, consistent assertion that works everywhere
        assert data["status"] == "ok"

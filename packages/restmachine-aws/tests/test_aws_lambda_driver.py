"""
AWS driver tests using multi-driver approach.

Tests for AWS API Gateway driver functionality including event conversion,
base64 encoding, edge cases, and AWS-specific features.
"""

import base64

from restmachine import RestApplication, Response
from tests.framework import MultiDriverTestBase, only_drivers


class TestBasicAwsDriverFunctionality(MultiDriverTestBase):
    """Test basic AWS driver functionality."""

    def create_app(self) -> RestApplication:
        """Set up API for AWS driver testing."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"message": "Hello from AWS"}

        @app.post("/echo")
        def echo_endpoint(json_body):
            return {"echo": json_body}

        return app

    def test_basic_get_request(self, api):
        """Test basic GET request through AWS driver."""
        api_client, driver_name = api
        response = api_client.get_resource("/test")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello from AWS"

    def test_basic_post_request(self, api):
        """Test basic POST request through AWS driver."""
        api_client, driver_name = api
        test_data = {"name": "test", "value": 42}
        response = api_client.create_resource("/echo", test_data)
        data = api_client.expect_successful_creation(response)
        assert data["echo"]["name"] == "test"
        assert data["echo"]["value"] == 42


class TestAwsBase64Encoding(MultiDriverTestBase):
    """Test base64 encoding for binary data in AWS."""

    ENABLED_DRIVERS = ['aws_lambda']

    def create_app(self) -> RestApplication:
        """Set up API for binary data testing."""
        app = RestApplication()

        @app.post("/upload")
        def upload_endpoint(body):
            # Handle any body type (text or binary)
            return {"received_length": len(body) if body else 0}

        return app

    @only_drivers('aws_lambda')
    def test_base64_encoded_body(self, api):
        """Test handling of base64-encoded request body."""
        api_client, driver_name = api
        driver = api_client.driver

        # Create binary data
        binary_data = b"This is binary data \x00\x01\x02\x03"

        # Create event with base64 body
        event = driver.create_event_with_base64_body(
            method="POST",
            path="/upload",
            binary_data=binary_data,
            content_type="application/octet-stream"
        )

        # Verify event structure
        assert event["isBase64Encoded"] is True
        assert event["headers"]["Content-Type"] == "application/octet-stream"

        # Verify base64 encoding
        decoded_data = base64.b64decode(event["body"])
        assert decoded_data == binary_data

        # Execute request
        response = driver.execute_with_custom_event(event)
        assert response.status_code == 200

    @only_drivers('aws_lambda')
    def test_binary_data_through_dsl(self, api):
        """Test binary data handling through DSL."""
        api_client, driver_name = api

        # Send binary data through DSL
        binary_data = b"Binary content"
        request = (api_client.post("/upload")
                  .with_text_body(binary_data.decode('latin-1'))  # Simulate binary as text
                  .with_header("Content-Type", "application/octet-stream")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        # Check that data was processed
        assert data["received_length"] > 0


class TestAwsEdgeCases(MultiDriverTestBase):
    """Test AWS driver edge cases and error scenarios."""

    ENABLED_DRIVERS = ['aws_lambda']

    def create_app(self) -> RestApplication:
        """Set up API for edge case testing."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"status": "ok"}

        @app.post("/echo")
        def echo_endpoint(json_body):
            return json_body or {"empty": True}

        return app

    @only_drivers('aws_lambda')
    def test_event_with_missing_fields(self, api):
        """Test AWS event with missing/null fields."""
        api_client, driver_name = api
        driver = api_client.driver

        # Create event with missing fields
        event = driver.create_event_with_missing_fields("GET", "/test")

        # Verify structure
        assert event["headers"] is None
        assert event["queryStringParameters"] is None
        assert event["pathParameters"] is None
        assert event["body"] is None

        # Should still work
        response = driver.execute_with_custom_event(event)
        data = api_client.expect_successful_retrieval(response)
        assert data["status"] == "ok"

    @only_drivers('aws_lambda')
    def test_event_with_empty_parameters(self, api):
        """Test AWS event with empty parameter objects."""
        api_client, driver_name = api
        driver = api_client.driver

        event = driver.create_aws_event(
            method="GET",
            path="/test",
            headers={},
            query_params={},
            path_params={}
        )

        response = driver.execute_with_custom_event(event)
        data = api_client.expect_successful_retrieval(response)
        assert data["status"] == "ok"

    @only_drivers('aws_lambda')
    def test_malformed_json_body(self, api):
        """Test handling of malformed JSON in request body."""
        api_client, driver_name = api
        driver = api_client.driver

        # Create event with malformed JSON
        event = driver.create_aws_event(
            method="POST",
            path="/echo",
            headers={"Content-Type": "application/json"},
            body='{"invalid": json}'  # Malformed JSON
        )

        response = driver.execute_with_custom_event(event)

        # Should get parsing error
        assert response.status_code == 422  # Unprocessable Entity

    @only_drivers('aws_lambda')
    def test_aws_response_inspection(self, api):
        """Test inspection of raw AWS responses."""
        api_client, driver_name = api
        driver = api_client.driver

        response = api_client.get_resource("/test")
        api_client.expect_successful_retrieval(response)

        # Inspect raw AWS response
        # Note: get_last_aws_response may not be available in all driver versions
        if hasattr(driver, 'get_last_aws_response'):
            aws_response = driver.get_last_aws_response()
            if aws_response is not None:
                assert "statusCode" in aws_response
                assert "body" in aws_response
                assert "headers" in aws_response

                # Verify response structure
                assert aws_response["statusCode"] == 200
                assert isinstance(aws_response["body"], str)
                assert "Content-Type" in aws_response["headers"]


class TestAwsFormDataHandling(MultiDriverTestBase):
    """Test form data handling in AWS environment."""

    def create_app(self) -> RestApplication:
        """Set up API for form data testing."""
        app = RestApplication()

        @app.post("/form")
        def handle_form(form_body):
            return {"received": dict(form_body) if form_body else {}}

        return app

    def test_form_data_encoding(self, api):
        """Test that form data is properly URL-encoded."""
        api_client, driver_name = api
        form_data = {"username": "test_user", "password": "secret123", "remember": "true"}

        request = api_client.post("/form").with_form_body(form_data).accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_creation(response)
        assert data["received"]["username"] == "test_user"
        assert data["received"]["password"] == "secret123"
        assert data["received"]["remember"] == "true"

    def test_form_data_with_special_characters(self, api):
        """Test form data with special characters."""
        api_client, driver_name = api
        form_data = {
            "name": "User Name",
            "email": "user@example.com",
            "description": "Test & Development"
        }

        request = api_client.post("/form").with_form_body(form_data).accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_creation(response)
        assert data["received"]["name"] == "User Name"
        assert data["received"]["email"] == "user@example.com"
        assert data["received"]["description"] == "Test & Development"


class TestAwsIntegrationScenarios(MultiDriverTestBase):
    """Test complex AWS integration scenarios."""

    def create_app(self) -> RestApplication:
        """Set up comprehensive API for integration testing."""
        app = RestApplication()

        # Simple data store
        users = {}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            if user_id not in users:
                return Response(404, "User not found")
            return users[user_id]

        @app.post("/users")
        def create_user(json_body, query_params):
            user_id = str(len(users) + 1)
            user = {"id": user_id, **json_body}

            # Add metadata from query params
            if query_params and "source" in query_params:
                user["source"] = query_params["source"]

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
            return None

        return app

    def test_full_crud_cycle_through_aws(self, api):
        """Test complete CRUD cycle through AWS Lambda driver."""
        api_client, driver_name = api

        # Create user
        user_data = {"name": "AWS Test User", "email": "aws@example.com"}
        create_request = api_client.post("/users").with_json_body(user_data).accepts("application/json")
        create_request.query_params = {"source": "aws_test"}

        create_response = api_client.execute(create_request)
        created_user = api_client.expect_successful_creation(create_response, ["id", "name", "email"])
        user_id = created_user["id"]

        assert created_user["name"] == "AWS Test User"
        assert created_user["source"] == "aws_test"

        # Read user
        read_response = api_client.get_resource(f"/users/{user_id}")
        retrieved_user = api_client.expect_successful_retrieval(read_response)
        assert retrieved_user["name"] == "AWS Test User"
        assert retrieved_user["email"] == "aws@example.com"

        # Update user
        update_data = {"name": "Updated AWS User"}
        update_response = api_client.update_resource(f"/users/{user_id}", update_data)
        updated_user = api_client.expect_successful_retrieval(update_response)
        assert updated_user["name"] == "Updated AWS User"
        assert updated_user["email"] == "aws@example.com"  # Should be unchanged

        # Delete user
        delete_response = api_client.delete_resource(f"/users/{user_id}")
        api_client.expect_no_content(delete_response)

        # Verify deletion
        get_deleted_response = api_client.get_resource(f"/users/{user_id}")
        api_client.expect_not_found(get_deleted_response)

    def test_aws_error_handling(self, api):
        """Test error handling through AWS driver."""
        api_client, driver_name = api

        # Try to get non-existent user
        response = api_client.get_resource("/users/999")
        api_client.expect_not_found(response)

        # Try to update non-existent user
        update_response = api_client.update_resource("/users/999", {"name": "New Name"})
        api_client.expect_not_found(update_response)

        # Try to delete non-existent user
        delete_response = api_client.delete_resource("/users/999")
        api_client.expect_not_found(delete_response)


class TestAwsStartupHandlers(MultiDriverTestBase):
    """Test that startup handlers execute during AWS Lambda cold start."""

    def create_app(self) -> RestApplication:
        """Create app with startup handlers for AWS Lambda testing."""
        app = RestApplication()

        # Track startup handler executions
        self.database_calls = {"count": 0}
        self.api_client_calls = {"count": 0}

        @app.on_startup
        def database():
            """Simulates opening a database connection during cold start."""
            self.database_calls["count"] += 1
            return {"connection": f"db_connection_{self.database_calls['count']}"}

        @app.on_startup
        def api_client():
            """Simulates creating an API client during cold start."""
            self.api_client_calls["count"] += 1
            return {"client": f"api_client_{self.api_client_calls['count']}"}

        @app.get("/status")
        def status(database, api_client):
            """Endpoint that uses startup dependencies."""
            return {
                "database": database,
                "api_client": api_client,
                "database_call_count": self.database_calls["count"],
                "api_client_call_count": self.api_client_calls["count"]
            }

        return app

    def test_startup_handlers_execute_on_adapter_init(self, api):
        """Startup handlers should execute when AWS adapter is initialized (cold start)."""
        api_client, driver_name = api

        # Make first request - startup should have already executed during adapter init
        response = api_client.get_resource("/status")
        data = api_client.expect_successful_retrieval(response)

        # Verify startup handlers were called exactly once
        assert data["database_call_count"] == 1
        assert data["api_client_call_count"] == 1

        # Verify the cached values from startup are injected
        assert data["database"]["connection"] == "db_connection_1"
        assert data["api_client"]["client"] == "api_client_1"

    def test_startup_handlers_not_called_again_on_requests(self, api):
        """Startup handlers should not be called again on subsequent requests (warm starts)."""
        api_client, driver_name = api

        # Make multiple requests
        response1 = api_client.get_resource("/status")
        response2 = api_client.get_resource("/status")
        response3 = api_client.get_resource("/status")

        data1 = api_client.expect_successful_retrieval(response1)
        data2 = api_client.expect_successful_retrieval(response2)
        data3 = api_client.expect_successful_retrieval(response3)

        # All requests should show handlers were called exactly once
        assert data1["database_call_count"] == 1
        assert data1["api_client_call_count"] == 1
        assert data2["database_call_count"] == 1
        assert data2["api_client_call_count"] == 1
        assert data3["database_call_count"] == 1
        assert data3["api_client_call_count"] == 1

        # All should return the same cached values
        assert data1["database"]["connection"] == "db_connection_1"
        assert data2["database"]["connection"] == "db_connection_1"
        assert data3["database"]["connection"] == "db_connection_1"
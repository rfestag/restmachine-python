"""
Refactored AWS driver tests using 4-layer architecture.

Tests for AWS API Gateway driver functionality including event conversion,
base64 encoding, edge cases, and AWS-specific features.
"""

import base64

import pytest

from restmachine import RestApplication
from tests.framework import RestApiDsl, AwsLambdaDriver, EnhancedAwsDriver


class TestBasicAwsDriverFunctionality:
    """Test basic AWS driver functionality."""

    @pytest.fixture
    def api(self):
        """Set up API for AWS driver testing."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"message": "Hello from AWS"}

        @app.post("/echo")
        def echo_endpoint(json_body):
            return {"echo": json_body}

        return RestApiDsl(AwsLambdaDriver(app))

    def test_basic_get_request(self, api):
        """Test basic GET request through AWS driver."""
        response = api.get_resource("/test")
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Hello from AWS"

    def test_basic_post_request(self, api):
        """Test basic POST request through AWS driver."""
        test_data = {"name": "test", "value": 42}
        response = api.create_resource("/echo", test_data)
        data = api.expect_successful_creation(response)
        assert data["echo"]["name"] == "test"
        assert data["echo"]["value"] == 42


class TestAwsEventConversion:
    """Test AWS API Gateway event conversion."""

    @pytest.fixture
    def enhanced_api(self):
        """Set up API with enhanced AWS driver."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user(path_params):
            return {"id": path_params["user_id"], "name": f"User {path_params['user_id']}"}

        @app.post("/users")
        def create_user(json_body, query_params):
            # Access query parameters if provided
            source = query_params.get("source", "api") if query_params else "api"
            return {"id": 123, "name": json_body["name"], "source": source}

        driver = EnhancedAwsDriver(app)
        return RestApiDsl(driver), driver

    def test_aws_event_conversion_basic(self, enhanced_api):
        """Test basic AWS event conversion."""
        api, driver = enhanced_api

        response = api.get_resource("/users/42")
        data = api.expect_successful_retrieval(response)

        # Check that AWS event was created correctly
        last_event = driver.get_last_event()
        assert last_event is not None
        assert last_event["httpMethod"] == "GET"
        assert last_event["path"] == "/users/42"
        assert "requestContext" in last_event

    def test_aws_event_with_headers(self, enhanced_api):
        """Test AWS event conversion with custom headers."""
        api, driver = enhanced_api

        request = (api.get("/users/42")
                  .with_header("X-Custom-Header", "test-value")
                  .with_header("User-Agent", "test-agent")
                  .accepts("application/json"))
        response = api.execute(request)

        api.expect_successful_retrieval(response)

        # Check headers in AWS event
        last_event = driver.get_last_event()
        assert last_event["headers"]["X-Custom-Header"] == "test-value"
        assert last_event["headers"]["User-Agent"] == "test-agent"

    def test_aws_event_with_query_parameters(self, enhanced_api):
        """Test AWS event conversion with query parameters."""
        api, driver = enhanced_api

        request = api.post("/users").with_json_body({"name": "Test User"}).accepts("application/json")
        request.query_params = {"source": "test", "version": "1.0"}
        response = api.execute(request)

        data = api.expect_successful_creation(response)
        assert data["source"] == "test"

        # Check query parameters in AWS event
        last_event = driver.get_last_event()
        assert last_event["queryStringParameters"]["source"] == "test"
        assert last_event["queryStringParameters"]["version"] == "1.0"

    def test_custom_aws_event_creation(self, enhanced_api):
        """Test creating custom AWS events."""
        api, driver = enhanced_api

        # Create custom event
        custom_event = driver.create_aws_event(
            method="GET",
            path="/users/999",
            headers={"Authorization": "Bearer token123"},
            query_params={"include": "profile"},
            stage="production",
            request_id="custom-request-id"
        )

        # Execute with custom event
        response = driver.execute_with_custom_event(custom_event)
        data = api.expect_successful_retrieval(response)
        assert data["id"] == "999"

        # Verify custom event properties
        assert custom_event["httpMethod"] == "GET"
        assert custom_event["path"] == "/users/999"
        assert custom_event["headers"]["Authorization"] == "Bearer token123"
        assert custom_event["queryStringParameters"]["include"] == "profile"
        assert custom_event["requestContext"]["stage"] == "production"
        assert custom_event["requestContext"]["requestId"] == "custom-request-id"


class TestAwsBase64Encoding:
    """Test base64 encoding for binary data in AWS."""

    @pytest.fixture
    def enhanced_api(self):
        """Set up API for binary data testing."""
        app = RestApplication()

        @app.post("/upload")
        def upload_endpoint(body):
            # Handle any body type (text or binary)
            return {"received_length": len(body) if body else 0}

        driver = EnhancedAwsDriver(app)
        return RestApiDsl(driver), driver

    def test_base64_encoded_body(self, enhanced_api):
        """Test handling of base64-encoded request body."""
        api, driver = enhanced_api

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

    def test_binary_data_through_dsl(self, enhanced_api):
        """Test binary data handling through DSL."""
        api, driver = enhanced_api

        # Send binary data through DSL
        binary_data = b"Binary content"
        request = (api.post("/upload")
                  .with_text_body(binary_data.decode('latin-1'))  # Simulate binary as text
                  .with_header("Content-Type", "application/octet-stream")
                  .accepts("application/json"))

        response = api.execute(request)
        data = api.expect_successful_creation(response)

        # Check that data was processed
        assert data["received_length"] > 0


class TestAwsEdgeCases:
    """Test AWS driver edge cases and error scenarios."""

    @pytest.fixture
    def enhanced_api(self):
        """Set up API for edge case testing."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"status": "ok"}

        @app.post("/echo")
        def echo_endpoint(json_body):
            return json_body or {"empty": True}

        driver = EnhancedAwsDriver(app)
        return RestApiDsl(driver), driver

    def test_event_with_missing_fields(self, enhanced_api):
        """Test AWS event with missing/null fields."""
        api, driver = enhanced_api

        # Create event with missing fields
        event = driver.create_event_with_missing_fields("GET", "/test")

        # Verify structure
        assert event["headers"] is None
        assert event["queryStringParameters"] is None
        assert event["pathParameters"] is None
        assert event["body"] is None

        # Should still work
        response = driver.execute_with_custom_event(event)
        data = api.expect_successful_retrieval(response)
        assert data["status"] == "ok"

    def test_event_with_empty_parameters(self, enhanced_api):
        """Test AWS event with empty parameter objects."""
        api, driver = enhanced_api

        event = driver.create_aws_event(
            method="GET",
            path="/test",
            headers={},
            query_params={},
            path_params={}
        )

        response = driver.execute_with_custom_event(event)
        data = api.expect_successful_retrieval(response)
        assert data["status"] == "ok"

    def test_malformed_json_body(self, enhanced_api):
        """Test handling of malformed JSON in request body."""
        api, driver = enhanced_api

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

    def test_aws_response_inspection(self, enhanced_api):
        """Test inspection of raw AWS responses."""
        api, driver = enhanced_api

        response = api.get_resource("/test")
        api.expect_successful_retrieval(response)

        # Inspect raw AWS response
        aws_response = driver.get_last_aws_response()
        assert aws_response is not None
        assert "statusCode" in aws_response
        assert "body" in aws_response
        assert "headers" in aws_response

        # Verify response structure
        assert aws_response["statusCode"] == 200
        assert isinstance(aws_response["body"], str)
        assert "Content-Type" in aws_response["headers"]


class TestAwsFormDataHandling:
    """Test form data handling in AWS environment."""

    @pytest.fixture
    def api(self):
        """Set up API for form data testing."""
        app = RestApplication()

        @app.post("/form")
        def handle_form(form_body):
            return {"received": dict(form_body) if form_body else {}}

        return RestApiDsl(AwsLambdaDriver(app))

    def test_form_data_encoding(self, api):
        """Test that form data is properly URL-encoded."""
        form_data = {"username": "test_user", "password": "secret123", "remember": "true"}

        request = api.post("/form").with_form_body(form_data).accepts("application/json")
        response = api.execute(request)

        data = api.expect_successful_creation(response)
        assert data["received"]["username"] == "test_user"
        assert data["received"]["password"] == "secret123"
        assert data["received"]["remember"] == "true"

    def test_form_data_with_special_characters(self, api):
        """Test form data with special characters."""
        form_data = {
            "name": "User Name",
            "email": "user@example.com",
            "description": "Test & Development"
        }

        request = api.post("/form").with_form_body(form_data).accepts("application/json")
        response = api.execute(request)

        data = api.expect_successful_creation(response)
        assert data["received"]["name"] == "User Name"
        assert data["received"]["email"] == "user@example.com"
        assert data["received"]["description"] == "Test & Development"


class TestAwsIntegrationScenarios:
    """Test complex AWS integration scenarios."""

    @pytest.fixture
    def api(self):
        """Set up comprehensive API for integration testing."""
        app = RestApplication()

        # Simple data store
        users = {}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            if user_id not in users:
                from restmachine import Response
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
                from restmachine import Response
                return Response(404, "User not found")

            users[user_id].update(json_body)
            return users[user_id]

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            user_id = path_params["user_id"]
            if user_id not in users:
                from restmachine import Response
                return Response(404, "User not found")

            del users[user_id]
            return None

        return RestApiDsl(AwsLambdaDriver(app))

    def test_full_crud_cycle_through_aws(self, api):
        """Test complete CRUD cycle through AWS Lambda driver."""
        # Create user
        user_data = {"name": "AWS Test User", "email": "aws@example.com"}
        create_request = api.post("/users").with_json_body(user_data).accepts("application/json")
        create_request.query_params = {"source": "aws_test"}

        create_response = api.execute(create_request)
        created_user = api.expect_successful_creation(create_response, ["id", "name", "email"])
        user_id = created_user["id"]

        assert created_user["name"] == "AWS Test User"
        assert created_user["source"] == "aws_test"

        # Read user
        read_response = api.get_resource(f"/users/{user_id}")
        retrieved_user = api.expect_successful_retrieval(read_response)
        assert retrieved_user["name"] == "AWS Test User"
        assert retrieved_user["email"] == "aws@example.com"

        # Update user
        update_data = {"name": "Updated AWS User"}
        update_response = api.update_resource(f"/users/{user_id}", update_data)
        updated_user = api.expect_successful_retrieval(update_response)
        assert updated_user["name"] == "Updated AWS User"
        assert updated_user["email"] == "aws@example.com"  # Should be unchanged

        # Delete user
        delete_response = api.delete_resource(f"/users/{user_id}")
        api.expect_no_content(delete_response)

        # Verify deletion
        get_deleted_response = api.get_resource(f"/users/{user_id}")
        api.expect_not_found(get_deleted_response)

    def test_aws_error_handling(self, api):
        """Test error handling through AWS driver."""
        # Try to get non-existent user
        response = api.get_resource("/users/999")
        api.expect_not_found(response)

        # Try to update non-existent user
        update_response = api.update_resource("/users/999", {"name": "New Name"})
        api.expect_not_found(update_response)

        # Try to delete non-existent user
        delete_response = api.delete_resource("/users/999")
        api.expect_not_found(delete_response)
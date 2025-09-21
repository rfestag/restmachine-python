"""
Tests for driver functionality.
"""

import base64
import json
from unittest.mock import Mock

import pytest

from restmachine import AwsApiGatewayDriver, HTTPMethod, Request, Response, RestApplication


class TestAwsApiGatewayDriver:
    """Test the AWS API Gateway driver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = RestApplication()
        self.driver = AwsApiGatewayDriver(self.app)

    def test_convert_to_request_basic(self):
        """Test basic event to request conversion."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {
                "Host": "example.com",
                "User-Agent": "test-agent"
            },
            "queryStringParameters": {
                "param1": "value1",
                "param2": "value2"
            },
            "pathParameters": {
                "id": "123"
            },
            "body": None
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.GET
        assert request.path == "/test"
        assert request.headers["Host"] == "example.com"
        assert request.headers["User-Agent"] == "test-agent"
        assert request.query_params["param1"] == "value1"
        assert request.query_params["param2"] == "value2"
        assert request.path_params["id"] == "123"
        assert request.body is None

    def test_convert_to_request_with_body(self):
        """Test event to request conversion with body."""
        event = {
            "httpMethod": "POST",
            "path": "/api/users",
            "headers": {
                "Content-Type": "application/json"
            },
            "body": '{"name": "John", "email": "john@example.com"}',
            "isBase64Encoded": False
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.POST
        assert request.path == "/api/users"
        assert request.headers["Content-Type"] == "application/json"
        assert request.body == '{"name": "John", "email": "john@example.com"}'

    def test_convert_to_request_with_base64_body(self):
        """Test event to request conversion with base64 encoded body."""
        original_body = '{"name": "John", "email": "john@example.com"}'
        encoded_body = base64.b64encode(original_body.encode("utf-8")).decode("utf-8")

        event = {
            "httpMethod": "POST",
            "path": "/api/users",
            "headers": {
                "Content-Type": "application/json"
            },
            "body": encoded_body,
            "isBase64Encoded": True
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.POST
        assert request.body == original_body

    def test_convert_to_request_null_values(self):
        """Test event to request conversion with null values."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {
                "Host": "example.com",
                "Authorization": None  # API Gateway can send None
            },
            "queryStringParameters": {
                "param1": "value1",
                "param2": None  # API Gateway can send None
            },
            "pathParameters": None,
            "body": None
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.GET
        assert request.path == "/test"
        assert "Host" in request.headers
        assert "Authorization" not in request.headers  # None values filtered out
        assert request.query_params["param1"] == "value1"
        assert "param2" not in request.query_params  # None values filtered out
        assert request.path_params is None
        assert request.body is None

    def test_convert_from_response_basic(self):
        """Test basic response to API Gateway format conversion."""
        response = Response(
            status_code=200,
            body='{"message": "success"}',
            headers={"Content-Type": "application/json"},
        )

        event = {"httpMethod": "GET", "path": "/test"}
        api_response = self.driver.convert_from_response(response, event)

        assert api_response["statusCode"] == 200
        assert api_response["body"] == '{"message": "success"}'
        assert api_response["headers"]["Content-Type"] == "application/json"
        assert api_response["isBase64Encoded"] is False

    def test_convert_from_response_no_body(self):
        """Test response to API Gateway format conversion with no body."""
        response = Response(
            status_code=204,
            body=None,
            headers={"X-Custom": "header"},
        )

        event = {"httpMethod": "DELETE", "path": "/test"}
        api_response = self.driver.convert_from_response(response, event)

        assert api_response["statusCode"] == 204
        assert api_response["body"] == ""  # None converted to empty string
        assert api_response["headers"]["X-Custom"] == "header"
        assert api_response["isBase64Encoded"] is False

    def test_handle_event_integration(self):
        """Test full event handling integration."""
        # Set up a simple route
        @self.app.get("/users/{user_id}")
        def get_user(user_id):
            return {"id": user_id, "name": "John Doe"}

        # Create an API Gateway event
        event = {
            "httpMethod": "GET",
            "path": "/users/123",
            "headers": {
                "Accept": "application/json"
            },
            "pathParameters": {
                "user_id": "123"
            },
            "queryStringParameters": None,
            "body": None
        }

        # Handle the event
        api_response = self.driver.handle_event(event)

        # Verify the response
        assert api_response["statusCode"] == 200
        assert "application/json" in api_response["headers"]["Content-Type"]

        # Parse the response body to verify content
        response_data = json.loads(api_response["body"])
        assert response_data["id"] == "123"
        assert response_data["name"] == "John Doe"

    def test_handle_event_with_post_body(self):
        """Test event handling with POST body."""
        # Set up a POST route
        @self.app.post("/users")
        def create_user(body):
            data = json.loads(body)
            return {"id": "new-id", "name": data["name"], "email": data["email"]}

        # Create an API Gateway event with POST body
        event = {
            "httpMethod": "POST",
            "path": "/users",
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            "body": '{"name": "Jane Doe", "email": "jane@example.com"}',
            "isBase64Encoded": False
        }

        # Handle the event
        api_response = self.driver.handle_event(event)

        # Verify the response
        assert api_response["statusCode"] == 200
        assert "application/json" in api_response["headers"]["Content-Type"]

        # Parse the response body to verify content
        response_data = json.loads(api_response["body"])
        assert response_data["id"] == "new-id"
        assert response_data["name"] == "Jane Doe"
        assert response_data["email"] == "jane@example.com"

    def test_handle_event_route_not_found(self):
        """Test event handling when route is not found."""
        event = {
            "httpMethod": "GET",
            "path": "/nonexistent",
            "headers": {},
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None
        }

        api_response = self.driver.handle_event(event)

        # Should return 404
        assert api_response["statusCode"] == 404

    def test_convert_to_request_missing_fields(self):
        """Test event to request conversion with missing fields."""
        event = {
            "httpMethod": "GET"
            # Missing other fields
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.GET
        assert request.path == "/"  # Default path
        assert request.headers == {}
        assert request.query_params is None
        assert request.path_params is None
        assert request.body is None

    def test_convert_to_request_empty_parameters(self):
        """Test event to request conversion with empty parameter dictionaries."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {},
            "queryStringParameters": {},
            "pathParameters": {},
            "body": None
        }

        request = self.driver.convert_to_request(event)

        assert request.method == HTTPMethod.GET
        assert request.path == "/test"
        assert request.headers == {}
        assert request.query_params is None  # Empty dict converted to None
        assert request.path_params is None   # Empty dict converted to None
        assert request.body is None

    def test_handle_event_with_query_params(self):
        """Test event handling with query parameters."""
        # Set up a route that uses query params
        @self.app.get("/search")
        def search(query_params):
            return {"query": query_params.get("q", ""), "page": query_params.get("page", "1")}

        event = {
            "httpMethod": "GET",
            "path": "/search",
            "headers": {
                "Accept": "application/json"
            },
            "queryStringParameters": {
                "q": "python",
                "page": "2"
            },
            "body": None
        }

        api_response = self.driver.handle_event(event)

        assert api_response["statusCode"] == 200
        response_data = json.loads(api_response["body"])
        assert response_data["query"] == "python"
        assert response_data["page"] == "2"
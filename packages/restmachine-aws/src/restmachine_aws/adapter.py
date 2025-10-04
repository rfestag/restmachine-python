"""AWS API Gateway adapter for RestMachine."""

import json
from typing import Any, Dict, Optional

from restmachine import Adapter, Request, Response, HTTPMethod
from restmachine.models import MultiValueHeaders


class AwsApiGatewayAdapter(Adapter):
    """
    Adapter for AWS API Gateway Lambda proxy integration events.

    This adapter handles events from:
    - API Gateway REST APIs (v1)
    - API Gateway HTTP APIs (v2)
    - Application Load Balancer
    - Lambda Function URLs

    Follows ASGI patterns for header and parameter handling:
    - Headers are normalized to lowercase for case-insensitive matching
    - Query parameters are parsed consistently
    - Body encoding is handled transparently
    """

    def __init__(self, app):
        """
        Initialize the adapter with a RestApplication instance.

        Automatically executes startup handlers during cold start to ensure
        session-scoped dependencies (database connections, API clients, etc.)
        are initialized before the first request.

        Args:
            app: The RestApplication instance to execute requests against
        """
        self.app = app

        # Execute startup handlers during Lambda cold start
        # This ensures database connections, API clients, etc. are initialized
        # before the first request is processed
        if hasattr(app, '_startup_handlers') and app._startup_handlers:
            app.startup_sync()

    def handle_event(self, event: Dict[str, Any], context: Optional[Any] = None) -> Dict[str, Any]:
        """
        Handle an AWS API Gateway event.

        Args:
            event: AWS API Gateway event dictionary
            context: AWS Lambda context (optional)

        Returns:
            AWS API Gateway response dictionary
        """
        request = self.convert_to_request(event, context)
        response = self.app.execute(request)
        return self.convert_from_response(response, event, context)

    def convert_to_request(self, event: Dict[str, Any], context: Optional[Any] = None) -> Request:
        """
        Convert AWS API Gateway event to Request object.

        Follows ASGI patterns:
        - Headers normalized to lowercase
        - Query parameters parsed as dict
        - Base64 body automatically decoded

        Args:
            event: AWS API Gateway event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Extract HTTP method
        method = HTTPMethod(event.get("httpMethod", "GET"))

        # Extract path
        path = event.get("path", "/")

        # Extract and normalize headers (lowercase for case-insensitive matching)
        # This aligns with ASGI adapter pattern
        # Use MultiValueHeaders to support duplicate header names
        headers = MultiValueHeaders()
        if "headers" in event and event["headers"]:
            for key, value in event["headers"].items():
                if value is not None:  # API Gateway can send None values
                    headers.add(key.lower(), str(value))

        # Extract query parameters
        # Convert to dict, filtering out None values
        query_params = {}
        if "queryStringParameters" in event and event["queryStringParameters"]:
            query_params = {k: v for k, v in event["queryStringParameters"].items() if v is not None}

        # Extract path parameters
        path_params = None
        if "pathParameters" in event and event["pathParameters"]:
            path_params = {k: v for k, v in event["pathParameters"].items() if v is not None}

        # Extract and decode body
        body = event.get("body")
        if body and event.get("isBase64Encoded", False):
            import base64
            try:
                body = base64.b64decode(body).decode("utf-8")
            except Exception:
                # If decoding fails, try latin-1 as fallback
                body = base64.b64decode(body).decode("latin-1")

        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query_params=query_params,
            path_params=path_params
        )

    def convert_from_response(self, response: Response, event: Dict[str, Any], context: Optional[Any] = None) -> Dict[str, Any]:
        """
        Convert Response object to AWS API Gateway response format.

        Handles proper JSON serialization and header encoding.

        Args:
            response: Response from the app
            event: Original AWS API Gateway event
            context: AWS Lambda context (optional)

        Returns:
            AWS API Gateway response dictionary
        """
        # Convert body to string
        if response.body is None:
            body_str = ""
        elif isinstance(response.body, (dict, list)):
            body_str = json.dumps(response.body)
        elif isinstance(response.body, (str, int, float, bool)):
            body_str = str(response.body)
        else:
            body_str = str(response.body)

        # Build the API Gateway response
        # Convert MultiValueHeaders to dict (first value for each header)
        if response.headers:
            if isinstance(response.headers, MultiValueHeaders):
                headers_dict = response.headers.to_dict()
            else:
                headers_dict = dict(response.headers)
        else:
            headers_dict = {}

        api_response = {
            "statusCode": response.status_code,
            "headers": headers_dict,
            "body": body_str,
            "isBase64Encoded": False
        }

        # Ensure Content-Type is set for JSON responses
        if isinstance(response.body, (dict, list)) and "content-type" not in (
            {k.lower(): k for k in headers_dict.keys()}
        ):
            api_response["headers"]["Content-Type"] = "application/json"

        return api_response

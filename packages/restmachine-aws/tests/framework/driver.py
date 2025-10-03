"""AWS Lambda test driver for RestMachine AWS adapter."""

import base64
import json
from typing import Any, Dict, Optional

# Import DSL from core restmachine test framework
from restmachine.testing.dsl import HttpRequest, HttpResponse
from restmachine.testing.drivers import DriverInterface

# Import AWS adapter from this package
from restmachine_aws import AwsApiGatewayAdapter


class AwsLambdaDriver(DriverInterface):
    """
    Driver that executes requests through AWS Lambda/API Gateway simulation.

    This tests the library as it would work when deployed to AWS Lambda.
    Includes support for binary data, complete request context, and optional debugging.
    """

    def __init__(self, app, enable_debugging: bool = False):
        """Initialize with a RestApplication wrapped in AWS driver.

        Args:
            app: The RestApplication to wrap
            enable_debugging: If True, stores last event/response for inspection
        """
        self.aws_driver = AwsApiGatewayAdapter(app)
        self.app = app
        self.enable_debugging = enable_debugging
        self.last_event = None
        self.last_response = None

    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute request through AWS API Gateway simulation."""
        # Convert DSL request to AWS API Gateway event
        event = self._convert_to_aws_event(request)

        if self.enable_debugging:
            self.last_event = event

        # Execute through AWS driver
        aws_response = self.aws_driver.handle_event(event, None)

        if self.enable_debugging:
            self.last_response = aws_response

        # Convert AWS response back to DSL response
        return self._convert_from_aws_response(aws_response)

    def _convert_to_aws_event(self, request: HttpRequest) -> Dict[str, Any]:
        """Convert DSL HttpRequest to AWS API Gateway event with full AWS support."""
        # Prepare body
        body = None
        is_base64_encoded = False

        if request.body is not None:
            if isinstance(request.body, dict):
                # Check content type to determine encoding
                content_type = request.headers.get("Content-Type", "")
                if "application/x-www-form-urlencoded" in content_type:
                    # URL-encode form data
                    from urllib.parse import urlencode
                    body = urlencode(request.body)
                else:
                    # Default to JSON for dict bodies
                    body = json.dumps(request.body)
            elif isinstance(request.body, bytes):
                # Handle binary data by base64 encoding
                body = base64.b64encode(request.body).decode('utf-8')
                is_base64_encoded = True
            else:
                body = str(request.body)

        # Try to extract path parameters from the path
        path_parameters = self._extract_path_parameters(request.path)

        return {
            "httpMethod": request.method.upper(),
            "path": request.path,
            "headers": request.headers.copy(),
            "queryStringParameters": request.query_params.copy() if request.query_params else None,
            "pathParameters": path_parameters,
            "body": body,
            "isBase64Encoded": is_base64_encoded,
            "requestContext": {
                "requestId": "test-request-id",
                "stage": "test",
                "resourcePath": request.path,
                "httpMethod": request.method.upper(),
                "protocol": "HTTP/1.1",
                "requestTime": "09/Apr/2015:12:34:56 +0000",
                "requestTimeEpoch": 1428582896000
            }
        }

    def _convert_from_aws_response(self, aws_response: Dict[str, Any]) -> HttpResponse:
        """Convert AWS API Gateway response to DSL HttpResponse with full AWS support."""
        body = aws_response.get("body")
        headers = aws_response.get("headers", {})
        content_type = headers.get("Content-Type")

        # Handle base64 encoded responses
        if aws_response.get("isBase64Encoded", False) and body:
            try:
                body = base64.b64decode(body)
            except Exception:
                # Keep as string if base64 decoding fails
                pass

        # Parse JSON body if applicable
        if body and content_type and 'application/json' in content_type and isinstance(body, str):
            try:
                body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                pass

        return HttpResponse(
            status_code=aws_response.get("statusCode", 500),
            headers=headers,
            body=body,
            content_type=content_type
        )

    def _extract_path_parameters(self, path: str) -> Optional[Dict[str, str]]:
        """Extract path parameters from a parameterized path."""
        # Simple implementation - in real scenarios this would be more sophisticated
        # For testing purposes, we'll return None unless explicitly set
        return None

    def execute_with_custom_event(self, event: Dict[str, Any]) -> HttpResponse:
        """Execute with a custom AWS API Gateway event."""
        if self.enable_debugging:
            self.last_event = event

        aws_response = self.aws_driver.handle_event(event, None)

        if self.enable_debugging:
            self.last_response = aws_response

        return self._convert_from_aws_response(aws_response)

    def create_aws_event(self,
                        method: str,
                        path: str,
                        headers: Optional[Dict[str, str]] = None,
                        query_params: Optional[Dict[str, str]] = None,
                        path_params: Optional[Dict[str, str]] = None,
                        body: Optional[str] = None,
                        is_base64_encoded: bool = False,
                        stage: str = "test",
                        request_id: str = "test-request-id") -> Dict[str, Any]:
        """Create a custom AWS API Gateway event."""
        return {
            "httpMethod": method.upper(),
            "path": path,
            "headers": headers or {},
            "queryStringParameters": query_params,
            "pathParameters": path_params,
            "body": body,
            "isBase64Encoded": is_base64_encoded,
            "requestContext": {
                "requestId": request_id,
                "stage": stage,
                "resourcePath": path,
                "httpMethod": method.upper(),
                "protocol": "HTTP/1.1",
                "requestTime": "09/Apr/2015:12:34:56 +0000",
                "requestTimeEpoch": 1428582896000
            }
        }

    def create_event_with_base64_body(self,
                                     method: str,
                                     path: str,
                                     binary_data: bytes,
                                     content_type: str = "application/octet-stream") -> Dict[str, Any]:
        """Create an AWS event with base64-encoded binary body."""
        encoded_body = base64.b64encode(binary_data).decode('utf-8')
        headers = {"Content-Type": content_type}

        return self.create_aws_event(
            method=method,
            path=path,
            headers=headers,
            body=encoded_body,
            is_base64_encoded=True
        )

    def create_event_with_missing_fields(self, method: str, path: str) -> Dict[str, Any]:
        """Create an AWS event with missing/null fields to test edge cases."""
        return {
            "httpMethod": method.upper(),
            "path": path,
            "headers": None,
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request-id",
                "stage": "test"
            }
        }

    def get_last_event(self) -> Optional[Dict[str, Any]]:
        """Get the last AWS event that was processed."""
        return self.last_event if self.enable_debugging else None

    def get_last_aws_response(self) -> Optional[Dict[str, Any]]:
        """Get the last raw AWS response."""
        return self.last_response if self.enable_debugging else None

    def get_openapi_spec(self) -> Dict[str, Any]:
        """Get OpenAPI specification from the application."""
        if hasattr(self.app, 'generate_openapi_json'):
            openapi_json = self.app.generate_openapi_json()
            return json.loads(openapi_json)
        elif hasattr(self.app, 'generate_openapi'):
            return self.app.generate_openapi()
        else:
            raise NotImplementedError("Application does not support OpenAPI generation")

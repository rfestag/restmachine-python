"""
Driver interface for handling different event sources that execute the app.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .models import Request, Response


class Driver(ABC):
    """Abstract base class for drivers that convert external events to app requests."""

    @abstractmethod
    def handle_event(self, event: Any, context: Optional[Any] = None) -> Any:
        """
        Handle an external event and return the appropriate response format.

        Args:
            event: The external event (e.g., AWS Lambda event)
            context: Optional context (e.g., AWS Lambda context)

        Returns:
            Response in the format expected by the external system
        """
        pass

    @abstractmethod
    def convert_to_request(self, event: Any, context: Optional[Any] = None) -> Request:
        """
        Convert an external event to a Request object.

        Args:
            event: The external event
            context: Optional context

        Returns:
            Request object that can be processed by the app
        """
        pass

    @abstractmethod
    def convert_from_response(self, response: Response, event: Any, context: Optional[Any] = None) -> Any:
        """
        Convert a Response object to the format expected by the external system.

        Args:
            response: Response from the app
            event: Original external event
            context: Optional context

        Returns:
            Response in the format expected by the external system
        """
        pass


class AwsApiGatewayDriver(Driver):
    """Driver for AWS API Gateway Lambda proxy integration events."""

    def __init__(self, app):
        """
        Initialize the driver with a RestApplication instance.

        Args:
            app: The RestApplication instance to execute requests against
        """
        self.app = app

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

        Args:
            event: AWS API Gateway event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        from .models import HTTPMethod

        # Extract HTTP method
        method = HTTPMethod(event.get("httpMethod", "GET"))

        # Extract path
        path = event.get("path", "/")

        # Extract headers (case-insensitive)
        headers = {}
        if "headers" in event and event["headers"]:
            for key, value in event["headers"].items():
                if value is not None:  # API Gateway can send None values
                    headers[key] = str(value)

        # Extract query parameters
        query_params = None
        if "queryStringParameters" in event and event["queryStringParameters"]:
            query_params = {k: v for k, v in event["queryStringParameters"].items() if v is not None}

        # Extract path parameters
        path_params = None
        if "pathParameters" in event and event["pathParameters"]:
            path_params = {k: v for k, v in event["pathParameters"].items() if v is not None}

        # Extract body
        body = event.get("body")
        if body and event.get("isBase64Encoded", False):
            import base64
            body = base64.b64decode(body).decode("utf-8")

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

        Args:
            response: Response from the app
            event: Original AWS API Gateway event
            context: AWS Lambda context (optional)

        Returns:
            AWS API Gateway response dictionary
        """
        # Build the API Gateway response
        api_response = {
            "statusCode": response.status_code,
            "headers": response.headers or {},
            "body": response.body or "",
            "isBase64Encoded": False
        }

        # Handle cases where body might be None
        if api_response["body"] is None:
            api_response["body"] = ""

        return api_response
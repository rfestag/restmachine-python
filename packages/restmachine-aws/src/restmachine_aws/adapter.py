"""AWS API Gateway adapter for RestMachine."""

import json
from typing import Any, Dict, Optional

from restmachine import Adapter, Request, Response, HTTPMethod
from restmachine.models import MultiValueHeaders


class AwsApiGatewayAdapter(Adapter):
    """
    Adapter for AWS API Gateway Lambda proxy integration events.

    This adapter handles events from:
    - API Gateway REST APIs (v1) - payload format 1.0
    - API Gateway HTTP APIs (v2) - payload format 2.0
    - Application Load Balancer (ALB)
    - Lambda Function URLs (v2 format)

    Version detection is automatic based on event structure:
    - v1 events use `httpMethod` at top level
    - v2 events have `version: "2.0"` field
    - ALB events have `requestContext.elb` field

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
        Convert AWS event to Request object.

        Automatically detects and handles:
        - API Gateway (v1, v2) events
        - Application Load Balancer (ALB) events
        - Lambda Function URL events

        Args:
            event: AWS event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Detect event type and delegate to appropriate parser
        if self._is_alb_event(event):
            return self._parse_alb_event(event, context)
        else:
            return self._parse_apigw_event(event, context)

    def _parse_apigw_event(self, event: Dict[str, Any], context: Optional[Any] = None) -> Request:
        """
        Parse API Gateway event to Request object.

        Handles both formats:
        - API Gateway REST API (v1) - payload format 1.0
        - API Gateway HTTP API (v2) - payload format 2.0
        - Lambda Function URLs (uses v2 format)

        Automatically detects the format version and delegates to the appropriate parser.

        Args:
            event: API Gateway event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Detect version - v2 has "version" field set to "2.0"
        is_v2 = event.get("version") == "2.0"

        if is_v2:
            return self._parse_apigw_v2_event(event, context)
        else:
            return self._parse_apigw_v1_event(event, context)

    def _parse_apigw_v1_event(self, event: Dict[str, Any], context: Optional[Any] = None) -> Request:
        """
        Parse API Gateway REST API (v1) event to Request object.

        Args:
            event: API Gateway v1 event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Extract HTTP method (v1: top level)
        method = HTTPMethod(event.get("httpMethod", "GET"))

        # Extract path (v1: uses "path")
        path = event.get("path", "/")

        # Extract headers
        headers = MultiValueHeaders()
        if "headers" in event and event["headers"]:
            for key, value in event["headers"].items():
                if value is not None:
                    headers.add(key.lower(), str(value))

        # Extract query parameters
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
                body = base64.b64decode(body).decode("latin-1")

        # Extract TLS information - API Gateway always uses HTTPS
        tls = True

        # Extract client certificate (v1: requestContext.identity.clientCert)
        client_cert = None
        request_context = event.get("requestContext", {})
        if request_context:
            identity = request_context.get("identity", {})
            if identity:
                apigw_client_cert = identity.get("clientCert")
                if apigw_client_cert:
                    client_cert = {
                        "subject": self._parse_cert_subject(apigw_client_cert.get("subjectDN", "")),
                        "issuer": self._parse_cert_subject(apigw_client_cert.get("issuerDN", "")),
                        "serial_number": apigw_client_cert.get("serialNumber"),
                        "validity": {
                            "notBefore": apigw_client_cert.get("validity", {}).get("notBefore"),
                            "notAfter": apigw_client_cert.get("validity", {}).get("notAfter")
                        }
                    }

        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query_params=query_params,
            path_params=path_params,
            tls=tls,
            client_cert=client_cert
        )

    def _parse_apigw_v2_event(self, event: Dict[str, Any], context: Optional[Any] = None) -> Request:
        """
        Parse API Gateway HTTP API (v2) event to Request object.

        Args:
            event: API Gateway v2 event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Extract HTTP method (v2: requestContext.http.method)
        request_context = event.get("requestContext", {})
        http_context = request_context.get("http", {})
        method = HTTPMethod(http_context.get("method", "GET"))

        # Extract path (v2: uses "rawPath")
        path = event.get("rawPath", "/")

        # Extract headers
        headers = MultiValueHeaders()
        if "headers" in event and event["headers"]:
            for key, value in event["headers"].items():
                if value is not None:
                    headers.add(key.lower(), str(value))

        # Extract cookies (v2 has separate cookies array)
        if "cookies" in event and event["cookies"]:
            # Combine cookies into Cookie header
            cookie_value = "; ".join(event["cookies"])
            headers.add("cookie", cookie_value)

        # Extract query parameters
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
                body = base64.b64decode(body).decode("latin-1")

        # Extract TLS information - API Gateway always uses HTTPS
        tls = True

        # Extract client certificate (v2: requestContext.authentication.clientCert)
        client_cert = None
        if request_context:
            authentication = request_context.get("authentication", {})
            if authentication:
                apigw_client_cert = authentication.get("clientCert")
                if apigw_client_cert:
                    client_cert = {
                        "subject": self._parse_cert_subject(apigw_client_cert.get("subjectDN", "")),
                        "issuer": self._parse_cert_subject(apigw_client_cert.get("issuerDN", "")),
                        "serial_number": apigw_client_cert.get("serialNumber"),
                        "validity": {
                            "notBefore": apigw_client_cert.get("validity", {}).get("notBefore"),
                            "notAfter": apigw_client_cert.get("validity", {}).get("notAfter")
                        }
                    }

        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query_params=query_params,
            path_params=path_params,
            tls=tls,
            client_cert=client_cert
        )

    def _parse_alb_event(self, event: Dict[str, Any], context: Optional[Any] = None) -> Request:
        """
        Parse Application Load Balancer (ALB) event to Request object.

        ALB events support multi-value headers and query parameters.
        mTLS support includes both passthrough and verify modes.

        Args:
            event: ALB event dictionary
            context: AWS Lambda context (optional)

        Returns:
            Request object
        """
        # Extract HTTP method
        method = HTTPMethod(event.get("httpMethod", "GET"))

        # Extract path
        path = event.get("path", "/")

        # Extract headers - ALB can use either headers or multiValueHeaders
        headers = MultiValueHeaders()
        if "multiValueHeaders" in event and event["multiValueHeaders"]:
            # ALB with multi-value headers (preferred)
            for key, values in event["multiValueHeaders"].items():
                if values:  # Skip None or empty lists
                    for value in values:
                        if value is not None:
                            headers.add(key.lower(), str(value))
        elif "headers" in event and event["headers"]:
            # ALB with single-value headers fallback
            for key, value in event["headers"].items():
                if value is not None:
                    headers.add(key.lower(), str(value))

        # Extract query parameters - ALB can use either format
        query_params = {}
        if "multiValueQueryStringParameters" in event and event["multiValueQueryStringParameters"]:
            # ALB with multi-value query params - take first value for compatibility
            query_params = {k: v[0] for k, v in event["multiValueQueryStringParameters"].items() if v and v[0] is not None}
        elif "queryStringParameters" in event and event["queryStringParameters"]:
            query_params = {k: v for k, v in event["queryStringParameters"].items() if v is not None}

        # ALB doesn't support path parameters
        path_params = None

        # Extract and decode body
        body = event.get("body")
        if body and event.get("isBase64Encoded", False):
            import base64
            try:
                body = base64.b64decode(body).decode("utf-8")
            except Exception:
                body = base64.b64decode(body).decode("latin-1")

        # Extract TLS information - ALB always uses HTTPS
        tls = True

        # Extract client certificate from ALB mTLS headers (verify or passthrough mode)
        client_cert = self._extract_alb_client_cert(headers)

        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query_params=query_params,
            path_params=path_params,
            tls=tls,
            client_cert=client_cert
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

    def _is_alb_event(self, event: Dict[str, Any]) -> bool:
        """
        Detect if this is an ALB event vs API Gateway event.

        ALB events have requestContext.elb while API Gateway has requestContext.identity.

        Args:
            event: AWS event dictionary

        Returns:
            True if ALB event, False otherwise
        """
        request_context = event.get("requestContext", {})
        return "elb" in request_context

    def _extract_alb_client_cert(self, headers: MultiValueHeaders) -> Optional[Dict[str, Any]]:
        """
        Extract client certificate from ALB mTLS headers.

        ALB supports two mTLS modes:
        1. Passthrough mode: Full certificate in x-amzn-mtls-clientcert header (URL-encoded PEM)
        2. Verify mode: Parsed certificate fields in separate headers

        Args:
            headers: Request headers

        Returns:
            Client certificate dict in ASGI TLS extension format, or None
        """
        # Check for verify mode first (parsed headers)
        # These headers are present when ALB is configured to verify client certificates
        subject_header = headers.get("x-amzn-mtls-clientcert-subject")
        issuer_header = headers.get("x-amzn-mtls-clientcert-issuer")
        serial_header = headers.get("x-amzn-mtls-clientcert-serial-number")

        if subject_header or issuer_header:
            # Verify mode - certificate fields are parsed by ALB
            client_cert: Dict[str, Any] = {}

            if subject_header:
                client_cert["subject"] = self._parse_cert_subject(subject_header)

            if issuer_header:
                client_cert["issuer"] = self._parse_cert_subject(issuer_header)

            if serial_header:
                client_cert["serial_number"] = serial_header

            # ALB doesn't provide validity dates in verify mode headers
            # Add placeholder for consistency
            client_cert["validity"] = {
                "notBefore": None,
                "notAfter": None
            }

            return client_cert

        # Check for passthrough mode (full PEM certificate)
        cert_header = headers.get("x-amzn-mtls-clientcert")
        if cert_header:
            # Passthrough mode - certificate is URL-encoded PEM format
            # For now, we'll extract basic info from the PEM
            # In a real implementation, you'd use a library like cryptography
            # to fully parse the certificate
            try:
                import urllib.parse
                pem_cert = urllib.parse.unquote(cert_header)

                # Extract subject and issuer from PEM (simplified)
                # A full implementation would use cryptography.x509
                pem_client_cert: Dict[str, Any] = {
                    "subject": [],  # Would need certificate parsing library
                    "issuer": [],   # Would need certificate parsing library
                    "serial_number": None,
                    "validity": {
                        "notBefore": None,
                        "notAfter": None
                    },
                    "pem": pem_cert  # Store full PEM for applications that need it
                }

                return pem_client_cert
            except Exception:
                # If we can't parse the certificate, return None
                return None

        return None

    def _parse_cert_subject(self, dn_string: str) -> list:
        """
        Parse a certificate Distinguished Name (DN) string into a list of tuples.

        Converts DN format (e.g., "CN=example.com,O=Example Inc,C=US")
        into ASGI TLS extension format: [("CN", "example.com"), ("O", "Example Inc"), ("C", "US")]

        Args:
            dn_string: Distinguished Name string

        Returns:
            List of (field, value) tuples
        """
        if not dn_string:
            return []

        result = []
        # Split by comma (simple parsing, doesn't handle escaped commas)
        parts = dn_string.split(",")
        for part in parts:
            part = part.strip()
            if "=" in part:
                field, value = part.split("=", 1)
                result.append((field.strip(), value.strip()))

        return result

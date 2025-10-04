"""
Tests for TLS support in AWS Lambda adapter.
"""

import pytest

from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter


class TestAwsLambdaTLS:
    """Test TLS support in AWS API Gateway adapter."""

    def test_api_gateway_request_always_has_tls(self):
        """API Gateway requests should always have tls=True."""
        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {"tls": request.tls}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {"Accept": "application/json"},
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None,
            "requestContext": {}
        }

        response = adapter.handle_event(event)

        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True

    def test_client_cert_extracted_from_mtls_event(self):
        """Client certificate should be extracted from mTLS API Gateway event."""
        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "has_client_cert": request.client_cert is not None,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        # API Gateway event with mutual TLS client certificate
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {"Accept": "application/json"},
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None,
            "requestContext": {
                "identity": {
                    "clientCert": {
                        "subjectDN": "CN=example.com,O=Example Inc,C=US",
                        "issuerDN": "CN=Example CA,O=Example Inc,C=US",
                        "serialNumber": "1234567890",
                        "validity": {
                            "notBefore": "2024-01-01T00:00:00Z",
                            "notAfter": "2025-01-01T00:00:00Z"
                        }
                    }
                }
            }
        }

        response = adapter.handle_event(event)

        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["has_client_cert"] is True
        # JSON serialization converts tuples to lists
        assert body["client_cert"]["subject"] == [["CN", "example.com"], ["O", "Example Inc"], ["C", "US"]]
        assert body["client_cert"]["issuer"] == [["CN", "Example CA"], ["O", "Example Inc"], ["C", "US"]]
        assert body["client_cert"]["serial_number"] == "1234567890"
        assert body["client_cert"]["validity"]["notBefore"] == "2024-01-01T00:00:00Z"
        assert body["client_cert"]["validity"]["notAfter"] == "2025-01-01T00:00:00Z"

    def test_no_client_cert_when_not_mtls(self):
        """Client certificate should be None when mTLS is not used."""
        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        # Regular API Gateway event without mTLS
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {"Accept": "application/json"},
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None,
            "requestContext": {
                "identity": {}
            }
        }

        response = adapter.handle_event(event)

        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["client_cert"] is None

    def test_parse_cert_subject_helper(self):
        """Test the _parse_cert_subject helper method."""
        app = RestApplication()
        adapter = AwsApiGatewayAdapter(app)

        # Test parsing a DN string
        dn = "CN=example.com,O=Example Inc,C=US"
        result = adapter._parse_cert_subject(dn)

        assert result == [("CN", "example.com"), ("O", "Example Inc"), ("C", "US")]

    def test_parse_cert_subject_with_empty_string(self):
        """Test _parse_cert_subject with empty string."""
        app = RestApplication()
        adapter = AwsApiGatewayAdapter(app)

        result = adapter._parse_cert_subject("")
        assert result == []

    def test_parse_cert_subject_with_spaces(self):
        """Test _parse_cert_subject with spaces around values."""
        app = RestApplication()
        adapter = AwsApiGatewayAdapter(app)

        dn = "CN = example.com , O = Example Inc , C = US"
        result = adapter._parse_cert_subject(dn)

        assert result == [("CN", "example.com"), ("O", "Example Inc"), ("C", "US")]

    def test_request_dependency_injection_with_tls_info(self):
        """Test that request with TLS info can be injected into route handlers."""
        app = RestApplication()

        @app.get("/secure")
        def secure_route(request):
            # Verify TLS information is accessible through dependency injection
            if not request.tls:
                return {"error": "TLS required"}, 403

            if request.client_cert:
                subject = request.client_cert.get("subject", [])
                cn = next((value for field, value in subject if field == "CN"), None)
                return {"message": f"Welcome {cn}"}

            return {"message": "Welcome, authenticated user"}

        adapter = AwsApiGatewayAdapter(app)

        # Event with mTLS
        event_with_cert = {
            "httpMethod": "GET",
            "path": "/secure",
            "headers": {"Accept": "application/json"},
            "requestContext": {
                "identity": {
                    "clientCert": {
                        "subjectDN": "CN=alice@example.com,O=Example Inc",
                        "issuerDN": "CN=Example CA",
                        "serialNumber": "123",
                        "validity": {
                            "notBefore": "2024-01-01T00:00:00Z",
                            "notAfter": "2025-01-01T00:00:00Z"
                        }
                    }
                }
            }
        }

        response = adapter.handle_event(event_with_cert)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["message"] == "Welcome alice@example.com"

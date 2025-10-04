"""
Tests for AWS Application Load Balancer (ALB) support.
"""

import pytest

from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter


class TestAwsALBBasic:
    """Test basic ALB event handling."""

    def test_alb_event_detection(self):
        """ALB events should be properly detected."""
        app = RestApplication()
        adapter = AwsApiGatewayAdapter(app)

        # ALB event has requestContext.elb
        alb_event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/my-target-group/abc123"
                }
            },
            "httpMethod": "GET",
            "path": "/",
            "headers": {"host": "example.com"}
        }

        # API Gateway event has requestContext.identity
        apigw_event = {
            "requestContext": {
                "identity": {
                    "sourceIp": "192.168.1.1"
                }
            },
            "httpMethod": "GET",
            "path": "/",
            "headers": {"host": "example.com"}
        }

        assert adapter._is_alb_event(alb_event) is True
        assert adapter._is_alb_event(apigw_event) is False

    def test_basic_alb_request(self):
        """Basic ALB request should work."""
        app = RestApplication()

        @app.get("/test")
        def test_route():
            return {"message": "ALB test"}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/my-target-group/abc123"
                }
            },
            "httpMethod": "GET",
            "path": "/test",
            "headers": {
                "accept": "application/json",
                "host": "example.com"
            },
            "body": None,
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)

        assert response["statusCode"] == 200
        import json
        body = json.loads(response["body"])
        assert body["message"] == "ALB test"

    def test_alb_multivalue_headers(self):
        """ALB multi-value headers should be properly extracted."""
        app = RestApplication()

        @app.get("/headers")
        def headers_route(request):
            # Get all values of accept header
            accept_values = request.headers.get_all("accept")
            return {"accept_values": accept_values}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/headers",
            "multiValueHeaders": {
                "accept": ["application/json", "text/html"],
                "accept-encoding": ["gzip", "deflate"]
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        # Both accept values should be present
        assert "application/json" in body["accept_values"]
        assert "text/html" in body["accept_values"]

    def test_alb_multivalue_query_parameters(self):
        """ALB multi-value query parameters should use first value."""
        app = RestApplication()

        @app.get("/search")
        def search_route(request):
            # query_params is a dict, so we get the first value
            tag = request.query_params.get("tag")
            return {"tag": tag}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/search",
            "headers": {"host": "example.com"},
            "multiValueQueryStringParameters": {
                "tag": ["python", "aws"]  # Multiple tags
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        # Should get the first tag
        assert body["tag"] == "python"


class TestAwsALBmTLS:
    """Test ALB mTLS support (both verify and passthrough modes)."""

    def test_alb_mtls_verify_mode(self):
        """ALB mTLS verify mode should extract client certificate from headers."""
        app = RestApplication()

        @app.get("/secure")
        def secure_route(request):
            return {
                "tls": request.tls,
                "has_client_cert": request.client_cert is not None,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        # ALB mTLS verify mode - certificate fields in separate headers
        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/secure",
            "headers": {
                "host": "example.com",
                "x-amzn-mtls-clientcert-subject": "CN=client.example.com,O=Example Inc,C=US",
                "x-amzn-mtls-clientcert-issuer": "CN=Example CA,O=Example Inc,C=US",
                "x-amzn-mtls-clientcert-serial-number": "A1B2C3D4E5F6"
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["has_client_cert"] is True

        # Check certificate details
        cert = body["client_cert"]
        assert cert["subject"] == [["CN", "client.example.com"], ["O", "Example Inc"], ["C", "US"]]
        assert cert["issuer"] == [["CN", "Example CA"], ["O", "Example Inc"], ["C", "US"]]
        assert cert["serial_number"] == "A1B2C3D4E5F6"
        # Validity dates not available in verify mode
        assert cert["validity"]["notBefore"] is None
        assert cert["validity"]["notAfter"] is None

    def test_alb_mtls_passthrough_mode(self):
        """ALB mTLS passthrough mode should extract PEM certificate from header."""
        app = RestApplication()

        @app.get("/secure")
        def secure_route(request):
            return {
                "tls": request.tls,
                "has_client_cert": request.client_cert is not None,
                "has_pem": "pem" in (request.client_cert or {})
            }

        adapter = AwsApiGatewayAdapter(app)

        # Simplified PEM certificate (URL-encoded)
        pem_cert = "-----BEGIN%20CERTIFICATE-----%0AMIICxjCCAa4CAw...%0A-----END%20CERTIFICATE-----%0A"

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/secure",
            "headers": {
                "host": "example.com",
                "x-amzn-mtls-clientcert": pem_cert
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["has_client_cert"] is True
        assert body["has_pem"] is True

    def test_alb_no_mtls(self):
        """ALB without mTLS should not have client certificate."""
        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/test",
            "headers": {
                "host": "example.com"
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["client_cert"] is None

    def test_alb_mtls_verify_partial_headers(self):
        """ALB mTLS with only some headers should still work."""
        app = RestApplication()

        @app.get("/secure")
        def secure_route(request):
            return {
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        # Only subject header, no issuer
        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/secure",
            "headers": {
                "host": "example.com",
                "x-amzn-mtls-clientcert-subject": "CN=client.example.com"
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        cert = body["client_cert"]
        assert cert is not None
        assert cert["subject"] == [["CN", "client.example.com"]]
        assert "issuer" not in cert  # Not provided

    def test_alb_mtls_dependency_injection(self):
        """Client certificate from ALB should be accessible via dependency injection."""
        app = RestApplication()

        @app.get("/identity")
        def identity_route(request):
            # Extract CN from client certificate
            if request.client_cert:
                subject = request.client_cert.get("subject", [])
                cn = next((value for field, value in subject if field == "CN"), None)
                return {"identity": cn, "method": "certificate"}

            return {"identity": "anonymous", "method": "none"}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/identity",
            "headers": {
                "host": "example.com",
                "x-amzn-mtls-clientcert-subject": "CN=alice@example.com,O=Example Inc"
            },
            "body": None
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["identity"] == "alice@example.com"
        assert body["method"] == "certificate"


class TestALBvsAPIGateway:
    """Test that both ALB and API Gateway work with the same adapter."""

    def test_same_adapter_handles_both(self):
        """The same adapter should handle both ALB and API Gateway events."""
        app = RestApplication()

        @app.get("/test")
        def test_route():
            return {"message": "success"}

        adapter = AwsApiGatewayAdapter(app)

        # ALB event
        alb_event = {
            "requestContext": {
                "elb": {
                    "targetGroupArn": "arn:aws:elasticloadbalancing:..."
                }
            },
            "httpMethod": "GET",
            "path": "/test",
            "headers": {"host": "alb.example.com"}
        }

        # API Gateway event
        apigw_event = {
            "requestContext": {
                "identity": {
                    "sourceIp": "192.168.1.1"
                }
            },
            "httpMethod": "GET",
            "path": "/test",
            "headers": {"Host": "apigw.example.com"}
        }

        # Both should work
        alb_response = adapter.handle_event(alb_event)
        apigw_response = adapter.handle_event(apigw_event)

        assert alb_response["statusCode"] == 200
        assert apigw_response["statusCode"] == 200

        import json
        assert json.loads(alb_response["body"])["message"] == "success"
        assert json.loads(apigw_response["body"])["message"] == "success"

"""
Tests for AWS API Gateway HTTP API (v2) support.
"""

import pytest

from restmachine import RestApplication, Response
from restmachine_aws import AwsApiGatewayAdapter


class TestAwsApiGatewayV2Basic:
    """Test basic API Gateway v2 (HTTP API) event handling."""

    def test_v2_event_detection(self):
        """v2 events should be properly detected and parsed."""
        app = RestApplication()

        @app.get("/test")
        def test_route():
            return {"message": "v2 test"}

        adapter = AwsApiGatewayAdapter(app)

        # API Gateway HTTP API v2 event
        v2_event = {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": "/test",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json",
                "host": "example.com"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/test",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "192.168.1.1",
                    "userAgent": "test-agent"
                },
                "requestId": "test-request-id",
                "stage": "$default",
                "time": "12/Mar/2020:19:03:58 +0000",
                "timeEpoch": 1583348638390
            },
            "isBase64Encoded": False
        }

        response = adapter.handle_event(v2_event)

        assert response["statusCode"] == 200
        import json
        body = json.loads(response["body"])
        assert body["message"] == "v2 test"

    def test_v2_with_path_parameters(self):
        """v2 events with path parameters should work."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user(request):
            user_id = request.path_params["user_id"]
            return {"id": user_id, "name": f"User {user_id}"}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "version": "2.0",
            "routeKey": "GET /users/{user_id}",
            "rawPath": "/users/123",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json"
            },
            "pathParameters": {
                "user_id": "123"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/users/123"
                },
                "requestId": "test-request-id",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["id"] == "123"
        assert body["name"] == "User 123"

    def test_v2_with_query_parameters(self):
        """v2 events with query parameters should work."""
        app = RestApplication()

        @app.get("/search")
        def search(request):
            query = request.query_params.get("q", "")
            limit = request.query_params.get("limit", "10")
            return {"query": query, "limit": limit}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "version": "2.0",
            "routeKey": "GET /search",
            "rawPath": "/search",
            "rawQueryString": "q=test&limit=20",
            "headers": {
                "accept": "application/json"
            },
            "queryStringParameters": {
                "q": "test",
                "limit": "20"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/search"
                },
                "requestId": "test-request-id",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["query"] == "test"
        assert body["limit"] == "20"

    def test_v2_post_with_json_body(self):
        """v2 POST events with JSON body should work."""
        app = RestApplication()

        @app.post("/users")
        def create_user(json_body):
            return {"created": True, "user": json_body}

        adapter = AwsApiGatewayAdapter(app)

        import json
        user_data = {"name": "Alice", "email": "alice@example.com"}

        event = {
            "version": "2.0",
            "routeKey": "POST /users",
            "rawPath": "/users",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json",
                "content-type": "application/json"
            },
            "requestContext": {
                "http": {
                    "method": "POST",
                    "path": "/users"
                },
                "requestId": "test-request-id",
                "stage": "$default"
            },
            "body": json.dumps(user_data),
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        assert body["created"] is True
        assert body["user"]["name"] == "Alice"


class TestAwsApiGatewayV2Cookies:
    """Test v2 cookie handling."""

    def test_v2_cookies_array(self):
        """v2 events with cookies array should be combined into Cookie header."""
        app = RestApplication()

        @app.get("/cookies")
        def get_cookies(request):
            cookie_header = request.headers.get("cookie", "")
            return {"cookies": cookie_header}

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "version": "2.0",
            "routeKey": "GET /cookies",
            "rawPath": "/cookies",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json"
            },
            "cookies": [
                "session_id=abc123",
                "user_pref=dark_mode"
            ],
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/cookies"
                },
                "requestId": "test-request-id",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert "session_id=abc123" in body["cookies"]
        assert "user_pref=dark_mode" in body["cookies"]


class TestAwsApiGatewayV2mTLS:
    """Test v2 mTLS support."""

    def test_v2_mtls_client_certificate(self):
        """v2 events with mTLS should extract client certificate."""
        app = RestApplication()

        @app.get("/secure")
        def secure_route(request):
            return {
                "tls": request.tls,
                "has_client_cert": request.client_cert is not None,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "version": "2.0",
            "routeKey": "GET /secure",
            "rawPath": "/secure",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/secure"
                },
                "requestId": "test-request-id",
                "stage": "$default",
                "authentication": {
                    "clientCert": {
                        "subjectDN": "CN=client.example.com,O=Example Inc,C=US",
                        "issuerDN": "CN=Example CA,O=Example Inc,C=US",
                        "serialNumber": "A1B2C3D4E5F6",
                        "validity": {
                            "notBefore": "2023-01-01T00:00:00Z",
                            "notAfter": "2024-01-01T00:00:00Z"
                        }
                    }
                }
            },
            "isBase64Encoded": False
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
        assert cert["validity"]["notBefore"] == "2023-01-01T00:00:00Z"
        assert cert["validity"]["notAfter"] == "2024-01-01T00:00:00Z"

    def test_v2_without_mtls(self):
        """v2 events without mTLS should not have client certificate."""
        app = RestApplication()

        @app.get("/test")
        def test_route(request):
            return {
                "tls": request.tls,
                "client_cert": request.client_cert
            }

        adapter = AwsApiGatewayAdapter(app)

        event = {
            "version": "2.0",
            "routeKey": "GET /test",
            "rawPath": "/test",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/test"
                },
                "requestId": "test-request-id",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        response = adapter.handle_event(event)
        assert response["statusCode"] == 200

        import json
        body = json.loads(response["body"])
        assert body["tls"] is True
        assert body["client_cert"] is None


class TestV1vsV2Compatibility:
    """Test that both v1 and v2 work with the same adapter."""

    def test_same_adapter_handles_both_versions(self):
        """The same adapter should handle both v1 and v2 events."""
        app = RestApplication()

        @app.get("/test")
        def test_route():
            return {"message": "success"}

        adapter = AwsApiGatewayAdapter(app)

        # v1 event (REST API)
        v1_event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {
                "Accept": "application/json"
            },
            "requestContext": {
                "requestId": "test-v1",
                "stage": "prod",
                "identity": {
                    "sourceIp": "192.168.1.1"
                }
            }
        }

        # v2 event (HTTP API)
        v2_event = {
            "version": "2.0",
            "routeKey": "GET /test",
            "rawPath": "/test",
            "rawQueryString": "",
            "headers": {
                "accept": "application/json"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/test"
                },
                "requestId": "test-v2",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        # Both should work
        v1_response = adapter.handle_event(v1_event)
        v2_response = adapter.handle_event(v2_event)

        assert v1_response["statusCode"] == 200
        assert v2_response["statusCode"] == 200

        import json
        assert json.loads(v1_response["body"])["message"] == "success"
        assert json.loads(v2_response["body"])["message"] == "success"

    def test_v1_and_v2_produce_identical_results(self):
        """v1 and v2 events should produce identical results for the same request."""
        app = RestApplication()

        @app.post("/echo")
        def echo(json_body):
            return {"echoed": json_body}

        adapter = AwsApiGatewayAdapter(app)

        import json
        test_data = {"test": "data", "value": 42}

        # v1 event
        v1_event = {
            "httpMethod": "POST",
            "path": "/echo",
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            "body": json.dumps(test_data),
            "requestContext": {
                "requestId": "test-v1",
                "stage": "prod"
            }
        }

        # v2 event
        v2_event = {
            "version": "2.0",
            "routeKey": "POST /echo",
            "rawPath": "/echo",
            "rawQueryString": "",
            "headers": {
                "content-type": "application/json",
                "accept": "application/json"
            },
            "body": json.dumps(test_data),
            "requestContext": {
                "http": {
                    "method": "POST",
                    "path": "/echo"
                },
                "requestId": "test-v2",
                "stage": "$default"
            },
            "isBase64Encoded": False
        }

        v1_response = adapter.handle_event(v1_event)
        v2_response = adapter.handle_event(v2_event)

        # Both should return the same data
        v1_body = json.loads(v1_response["body"])
        v2_body = json.loads(v2_response["body"])

        assert v1_body == v2_body
        assert v1_body["echoed"]["test"] == "data"
        assert v1_body["echoed"]["value"] == 42

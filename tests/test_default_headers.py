"""
Tests for default_headers decorator functionality.
"""


from restmachine import HTTPMethod, Request, RestApplication


class TestDefaultHeaders:
    """Test default_headers decorator functionality."""

    def test_basic_headers_modification(self):
        """Test basic headers modification functionality."""
        app = RestApplication()

        @app.default_headers
        def add_security_headers(headers):
            headers["X-Frame-Options"] = "DENY"
            headers["X-Content-Type-Options"] = "nosniff"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_vary_header_preserved_with_authorization(self):
        """Test that Vary header is calculated first and preserved."""
        app = RestApplication()

        @app.default_headers
        def add_cache_headers(headers):
            headers["Cache-Control"] = "public, max-age=3600"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={
                "Authorization": "Bearer token123",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert "Vary" in response.headers
        vary_header = response.headers["Vary"]
        assert "Authorization" in vary_header
        assert "Accept" in vary_header
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "public, max-age=3600"

    def test_vary_header_with_multiple_content_types(self):
        """Test Vary header with multiple content types."""
        app = RestApplication()

        @app.default_headers
        def add_cors_headers(headers):
            headers["Access-Control-Allow-Origin"] = "*"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert "Vary" in response.headers
        assert "Accept" in response.headers["Vary"]
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_headers_dependency_injection(self):
        """Test dependency injection within headers functions."""
        app = RestApplication()

        @app.default_headers
        def conditional_headers(headers, request):
            if request.headers.get("Authorization"):
                headers["Cache-Control"] = "private, no-cache"
            else:
                headers["Cache-Control"] = "public, max-age=3600"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        # Test with authorization
        request_with_auth = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={
                "Authorization": "Bearer token123",
                "Accept": "application/json"
            }
        )

        response_with_auth = app.execute(request_with_auth)
        assert response_with_auth.headers["Cache-Control"] == "private, no-cache"

        # Test without authorization
        request_without_auth = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response_without_auth = app.execute(request_without_auth)
        assert response_without_auth.headers["Cache-Control"] == "public, max-age=3600"

    def test_route_specific_headers_dependencies(self):
        """Test route-specific headers dependencies."""
        app = RestApplication()

        @app.get("/public")
        def public_handler():
            return {"message": "public"}

        @app.default_headers
        def add_public_headers(headers):
            headers["Cache-Control"] = "public, max-age=3600"
            return headers

        @app.get("/private")
        def private_handler():
            return {"message": "private"}

        @app.default_headers
        def add_private_headers(headers):
            headers["Cache-Control"] = "private, no-cache"
            headers["X-Sensitive"] = "true"
            return headers

        # Test public endpoint
        public_request = Request(
            method=HTTPMethod.GET,
            path="/public",
            headers={"Accept": "application/json"}
        )

        public_response = app.execute(public_request)
        assert public_response.headers["Cache-Control"] == "public, max-age=3600"
        assert "X-Sensitive" not in public_response.headers

        # Test private endpoint
        private_request = Request(
            method=HTTPMethod.GET,
            path="/private",
            headers={"Accept": "application/json"}
        )

        private_response = app.execute(private_request)
        assert private_response.headers["Cache-Control"] == "private, no-cache"
        assert "X-Sensitive" in private_response.headers
        assert private_response.headers["X-Sensitive"] == "true"

    def test_global_headers_dependencies(self):
        """Test global headers dependencies applied to all routes."""
        app = RestApplication()

        @app.default_headers
        def add_global_security_headers(headers):
            headers["X-Frame-Options"] = "DENY"
            headers["X-XSS-Protection"] = "1; mode=block"
            return headers

        @app.get("/route1")
        def handler1():
            return {"route": "1"}

        @app.get("/route2")
        def handler2():
            return {"route": "2"}

        # Test both routes get global headers
        for path in ["/route1", "/route2"]:
            request = Request(
                method=HTTPMethod.GET,
                path=path,
                headers={"Accept": "application/json"}
            )

            response = app.execute(request)
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_multiple_headers_dependencies_execution_order(self):
        """Test multiple headers dependencies are executed in order."""
        app = RestApplication()

        execution_order = []

        @app.default_headers
        def first_headers(headers):
            execution_order.append("first")
            headers["X-First"] = "1"
            return headers

        @app.default_headers
        def second_headers(headers):
            execution_order.append("second")
            headers["X-Second"] = "2"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        assert execution_order == ["first", "second"]
        assert response.headers["X-First"] == "1"
        assert response.headers["X-Second"] == "2"

    def test_headers_modification_in_place(self):
        """Test that headers can be modified in-place without return."""
        app = RestApplication()

        @app.default_headers
        def modify_headers_in_place(headers):
            headers["X-Modified"] = "in-place"
            # Not returning headers - should still work

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        assert response.headers["X-Modified"] == "in-place"

    def test_headers_with_existing_response_headers(self):
        """Test that headers dependencies work with responses that already have headers."""
        app = RestApplication()

        @app.default_headers
        def add_custom_headers(headers):
            headers["X-Custom"] = "added"
            return headers

        @app.get("/test")
        def test_handler():
            from restmachine.models import Response
            return Response(200, '{"message": "test"}', headers={"X-Existing": "value"}, content_type="application/json")

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        assert response.headers["X-Custom"] == "added"
        assert response.headers["X-Existing"] == "value"

    def test_204_response_with_headers_dependencies(self):
        """Test headers dependencies with 204 responses."""
        app = RestApplication()

        @app.default_headers
        def add_no_content_headers(headers):
            headers["X-No-Content"] = "true"
            return headers

        @app.delete("/resource/{id}")
        def delete_handler() -> None:
            return None

        request = Request(
            method=HTTPMethod.DELETE,
            path="/resource/123",
            headers={"Authorization": "Bearer token123"}
        )

        response = app.execute(request)

        assert response.status_code == 204
        assert response.headers["X-No-Content"] == "true"
        assert "Vary" in response.headers
        assert "Authorization" in response.headers["Vary"]
        assert "Content-Length" not in response.headers  # 204 should not have Content-Length

    def test_headers_dependencies_error_handling(self):
        """Test that errors in headers dependencies don't break the response."""
        app = RestApplication()

        @app.default_headers
        def failing_headers(headers):
            raise Exception("Headers function failed")

        @app.default_headers
        def working_headers(headers):
            headers["X-Working"] = "yes"
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response = app.execute(request)

        # Should still get response despite failing headers dependency
        assert response.status_code == 200
        assert response.headers["X-Working"] == "yes"

    def test_headers_dependency_caching_per_request(self):
        """Test that headers are cached per request and don't leak between requests."""
        app = RestApplication()

        call_count = 0

        @app.default_headers
        def counting_headers(headers):
            nonlocal call_count
            call_count += 1
            headers["X-Call-Count"] = str(call_count)
            return headers

        @app.get("/test")
        def test_handler():
            return {"message": "test"}

        # First request
        request1 = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response1 = app.execute(request1)
        assert response1.headers["X-Call-Count"] == "1"

        # Second request should increment call count
        request2 = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"Accept": "application/json"}
        )

        response2 = app.execute(request2)
        assert response2.headers["X-Call-Count"] == "2"
"""
Tests for HTTP server implementations (Uvicorn and Hypercorn).

These tests validate that RestMachine applications work correctly when served
through actual HTTP servers, ensuring real-world compatibility.
"""

import pytest
from restmachine import RestApplication, Response

# Skip all tests if HTTP drivers are not available
pytest_plugins = []
try:
    from tests.framework.http_drivers import (
        UvicornHttp1Driver,
        HypercornHttp1Driver,
    )
    HTTP_DRIVERS_AVAILABLE = True
except ImportError:
    HTTP_DRIVERS_AVAILABLE = False


@pytest.mark.skipif(not HTTP_DRIVERS_AVAILABLE, reason="HTTP server drivers not available")
class TestHttpServerBasics:
    """Test basic HTTP server functionality."""

    def create_test_app(self) -> RestApplication:
        """Create a test application for HTTP server testing."""
        app = RestApplication()

        @app.get("/")
        def home():
            return {"message": "Hello World", "server": "http"}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            return {"id": path_params["user_id"], "name": f"User {path_params['user_id']}"}

        @app.post("/users")
        def create_user(json_body):
            return {"id": "123", "name": json_body["name"], "created": True}

        @app.put("/users/{user_id}")
        def update_user(path_params, json_body):
            return {"id": path_params["user_id"], "name": json_body["name"], "updated": True}

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            return None  # 204 No Content

        @app.get("/error")
        def error_endpoint():
            raise Exception("Test error")

        @app.get("/custom-status")
        def custom_status():
            return Response(201, {"message": "Created"})

        return app

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_basic_get_request(self, driver_class):
        """Test basic GET request handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.get_resource("/")
            data = api.expect_successful_retrieval(response)

            assert data["message"] == "Hello World"
            assert data["server"] == "http"

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_path_parameters(self, driver_class):
        """Test path parameter extraction."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.get_resource("/users/42")
            data = api.expect_successful_retrieval(response)

            assert data["id"] == "42"
            assert data["name"] == "User 42"

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_json_post_request(self, driver_class):
        """Test JSON POST request handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            user_data = {"name": "John Doe", "email": "john@example.com"}
            response = api.create_resource("/users", user_data)
            data = api.expect_successful_creation(response)

            assert data["id"] == "123"
            assert data["name"] == "John Doe"
            assert data["created"] is True

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_put_request(self, driver_class):
        """Test PUT request handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            update_data = {"name": "Jane Doe"}
            response = api.update_resource("/users/42", update_data)
            data = api.expect_successful_retrieval(response)

            assert data["id"] == "42"
            assert data["name"] == "Jane Doe"
            assert data["updated"] is True

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_delete_request(self, driver_class):
        """Test DELETE request handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.delete_resource("/users/42")
            api.expect_no_content(response)

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_error_handling(self, driver_class):
        """Test error handling through HTTP servers."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.get_resource("/error")
            assert response.is_server_error()

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_custom_status_codes(self, driver_class):
        """Test custom status code handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.get_resource("/custom-status")
            assert response.status_code == 201

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_not_found(self, driver_class):
        """Test 404 handling for non-existent endpoints."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            response = api.get_resource("/does-not-exist")
            api.expect_not_found(response)


@pytest.mark.skipif(not HTTP_DRIVERS_AVAILABLE, reason="HTTP server drivers not available")
class TestHttpServerHeaders:
    """Test HTTP header handling."""

    def create_test_app(self) -> RestApplication:
        """Create an app for header testing."""
        app = RestApplication()

        @app.get("/headers")
        def get_headers(request_headers):
            return {"received_headers": dict(request_headers)}

        @app.post("/echo-headers")
        def echo_headers(request_headers, json_body):
            return {
                "body": json_body,
                "headers": dict(request_headers)
            }

        return app

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_request_headers(self, driver_class):
        """Test that request headers are properly passed through."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            request = (api.get("/headers")
                      .with_header("X-Custom-Header", "test-value")
                      .with_header("Authorization", "Bearer token123"))

            response = api.execute(request)
            data = api.expect_successful_retrieval(response)

            # Headers are normalized to lowercase by ASGI adapter
            assert "x-custom-header" in data["received_headers"]
            assert data["received_headers"]["x-custom-header"] == "test-value"
            assert "authorization" in data["received_headers"]
            assert data["received_headers"]["authorization"] == "Bearer token123"

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_content_type_headers(self, driver_class):
        """Test Content-Type header handling."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            test_data = {"name": "Test"}
            request = (api.post("/echo-headers")
                      .with_json_body(test_data)
                      .accepts("application/json"))

            response = api.execute(request)
            data = api.expect_successful_creation(response)

            assert data["body"]["name"] == "Test"
            # Verify that Content-Type was properly set for JSON (lowercase from ASGI)
            assert "content-type" in data["headers"]


@pytest.mark.skipif(not HTTP_DRIVERS_AVAILABLE, reason="HTTP server drivers not available")
class TestHttpServerQueryParams:
    """Test query parameter handling."""

    def create_test_app(self) -> RestApplication:
        """Create an app for query parameter testing."""
        app = RestApplication()

        @app.get("/search")
        def search(query_params):
            return {
                "query": query_params.get("q", ""),
                "limit": int(query_params.get("limit", "10")),
                "all_params": dict(query_params)
            }

        return app

    @pytest.mark.parametrize("driver_class", [
        pytest.param(UvicornHttp1Driver, id="uvicorn-http1"),
        pytest.param(HypercornHttp1Driver, id="hypercorn-http1"),
    ])
    def test_query_parameters(self, driver_class):
        """Test query parameter parsing."""
        app = self.create_test_app()

        with driver_class(app) as driver:
            from tests.framework import RestApiDsl
            api = RestApiDsl(driver)

            request = api.get("/search")
            request.query_params = {"q": "test search", "limit": "20", "sort": "name"}

            response = api.execute(request)
            data = api.expect_successful_retrieval(response)

            assert data["query"] == "test search"
            assert data["limit"] == 20
            assert data["all_params"]["sort"] == "name"


@pytest.mark.skipif(not HTTP_DRIVERS_AVAILABLE, reason="HTTP server drivers not available")
class TestServerDriverAvailability:
    """Test server driver availability checks."""

    def test_uvicorn_availability(self):
        """Test Uvicorn driver availability check."""
        try:
            import uvicorn  # noqa: F401
            uvicorn_available = True
        except ImportError:
            uvicorn_available = False

        from restmachine.servers import UvicornDriver
        from restmachine import RestApplication

        app = RestApplication()
        driver = UvicornDriver(app)

        assert driver.is_available() == uvicorn_available

    def test_hypercorn_availability(self):
        """Test Hypercorn driver availability check."""
        try:
            import hypercorn  # noqa: F401
            hypercorn_available = True
        except ImportError:
            hypercorn_available = False

        from restmachine.servers import HypercornDriver
        from restmachine import RestApplication

        app = RestApplication()
        driver = HypercornDriver(app)

        assert driver.is_available() == hypercorn_available


@pytest.mark.skipif(not HTTP_DRIVERS_AVAILABLE, reason="HTTP server drivers not available")
class TestServerConfiguration:
    """Test server configuration options."""

    def test_uvicorn_http_versions(self):
        """Test Uvicorn HTTP version configuration."""
        from restmachine.servers import UvicornDriver
        from restmachine import RestApplication

        app = RestApplication()

        # Test HTTP/1.1
        driver1 = UvicornDriver(app, http_version="http1")
        assert driver1.http_version == "http1"

        # Test HTTP/2
        driver2 = UvicornDriver(app, http_version="http2")
        assert driver2.http_version == "http2"

        # Test invalid version
        with pytest.raises(ValueError):
            UvicornDriver(app, http_version="http3")

    def test_hypercorn_http_versions(self):
        """Test Hypercorn HTTP version configuration."""
        from restmachine.servers import HypercornDriver
        from restmachine import RestApplication

        app = RestApplication()

        # Test HTTP/1.1
        driver1 = HypercornDriver(app, http_version="http1")
        assert driver1.http_version == "http1"

        # Test HTTP/2
        driver2 = HypercornDriver(app, http_version="http2")
        assert driver2.http_version == "http2"

        # Test HTTP/3
        driver3 = HypercornDriver(app, http_version="http3")
        assert driver3.http_version == "http3"

        # Test invalid version
        with pytest.raises(ValueError):
            HypercornDriver(app, http_version="invalid")
"""
Tests for application.py custom decorators and providers.

Covers uncovered decorators like resource_from_request, forbidden,
default callbacks, request_id/trace_id providers, etc.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestCustomDecorators(MultiDriverTestBase):
    """Test custom decorators for application."""

    def create_app(self) -> RestApplication:
        """Create app with custom decorators."""
        app = RestApplication()

        # Test resource_from_request decorator
        @app.resource_from_request
        def get_item_from_url(request):
            """Extract item from URL."""
            item_id = request.path_params.get("item_id")
            if item_id == "123":
                return {"id": "123", "name": "Test Item"}
            return None

        @app.get("/items/{item_id}")
        def get_item(get_item_from_url):
            """Get item using resource_from_request."""
            return get_item_from_url

        # Test forbidden decorator
        @app.forbidden
        def check_admin_access(request):
            """Check if user has admin access."""
            # Return None for forbidden (this path triggers 403)
            if request.path == "/admin/data":
                return None  # Triggers 403
            return {"access": "granted"}

        @app.get("/admin/data")
        def admin_data(check_admin_access):
            """Admin-only endpoint using forbidden dependency."""
            return {"data": "sensitive", "access": check_admin_access}

        # Note: default_resource_exists is called when there's NO explicit resource_exists
        # for a route. So we just register it to cover the decorator code.
        @app.default_resource_exists
        def default_check_resource(request):
            """Default resource exists check."""
            # This would be called if no explicit resource_exists was defined
            return {"default": True}

        # Test default_route_not_found decorator
        @app.default_route_not_found
        def custom_404_handler(request):
            """Custom 404 handler."""
            return {"error": "Custom not found message", "path": request.path}

        return app

    def test_resource_from_request_decorator(self, api):
        """Test resource_from_request decorator."""
        api_client, driver_name = api

        response = api_client.get_resource("/items/123")
        data = api_client.expect_successful_retrieval(response)

        assert data["id"] == "123"
        assert data["name"] == "Test Item"

    def test_forbidden_decorator_blocks_access(self, api):
        """Test forbidden decorator blocks access when returning None."""
        api_client, driver_name = api

        # The forbidden dependency returns None for /admin/data, triggering 403
        response = api_client.get_resource("/admin/data")
        api_client.expect_forbidden(response)

    def test_default_resource_exists_decorator(self, api):
        """Test that default_resource_exists decorator can be registered."""
        api_client, driver_name = api

        # Just verify the app has the default callback registered
        app = api_client.driver.app
        assert "resource_exists" in app._default_callbacks


class TestCustomProviders(MultiDriverTestBase):
    """Test custom request_id and trace_id providers."""

    def create_app(self) -> RestApplication:
        """Create app with custom ID providers."""
        app = RestApplication()

        # Test custom request_id provider
        @app.request_id
        def custom_request_id(request):
            """Generate custom request ID from header."""
            return request.headers.get("X-Custom-Request-ID", "default-req-id")

        # Test custom trace_id provider
        @app.trace_id
        def custom_trace_id(request):
            """Generate custom trace ID from header."""
            return request.headers.get("X-Custom-Trace-ID", "default-trace-id")

        @app.get("/test-ids")
        def test_ids(request_id, trace_id):
            """Endpoint to test custom ID providers."""
            return {"request_id": request_id, "trace_id": trace_id}

        return app

    def test_custom_request_id_provider(self, api):
        """Test custom request_id provider."""
        api_client, driver_name = api

        request = api_client.get("/test-ids")
        request = request.with_header("X-Custom-Request-ID", "my-request-123")
        request = request.accepts("application/json")

        response = api_client.execute(request)
        data = api_client.expect_successful_retrieval(response)

        assert data["request_id"] == "my-request-123"

    def test_custom_request_id_provider_default(self, api):
        """Test custom request_id provider with default."""
        api_client, driver_name = api

        response = api_client.get_resource("/test-ids")
        data = api_client.expect_successful_retrieval(response)

        assert data["request_id"] == "default-req-id"

    def test_custom_trace_id_provider(self, api):
        """Test custom trace_id provider."""
        api_client, driver_name = api

        request = api_client.get("/test-ids")
        request = request.with_header("X-Custom-Trace-ID", "my-trace-456")
        request = request.accepts("application/json")

        response = api_client.execute(request)
        data = api_client.expect_successful_retrieval(response)

        assert data["trace_id"] == "my-trace-456"

    def test_custom_trace_id_provider_default(self, api):
        """Test custom trace_id provider with default."""
        api_client, driver_name = api

        response = api_client.get_resource("/test-ids")
        data = api_client.expect_successful_retrieval(response)

        assert data["trace_id"] == "default-trace-id"

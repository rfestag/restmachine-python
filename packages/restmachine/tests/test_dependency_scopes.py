"""
Tests for dependency injection scopes (request vs session).
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestRequestScopeDependencies(MultiDriverTestBase):
    """Test that request-scoped dependencies are re-evaluated on each request."""

    def create_app(self) -> RestApplication:
        """Create a test application with request-scoped dependency."""
        app = RestApplication()

        # Counter to track how many times the dependency is called
        call_count = {"value": 0}

        @app.dependency(scope="request")
        def request_counter():
            """A dependency that increments a counter each time it's called."""
            call_count["value"] += 1
            return call_count["value"]

        @app.get("/test")
        def test_endpoint(request_counter):
            """Endpoint that uses the request-scoped dependency."""
            return {"counter": request_counter}

        return app

    def test_request_scope_resets_between_requests(self, api):
        """Request-scoped dependencies should be re-evaluated on each request."""
        api_client, driver_name = api

        # First request should get counter = 1
        response1 = api_client.get_resource("/test")
        assert response1.body["counter"] == 1

        # Second request should get counter = 2 (dependency called again)
        response2 = api_client.get_resource("/test")
        assert response2.body["counter"] == 2

        # Third request should get counter = 3
        response3 = api_client.get_resource("/test")
        assert response3.body["counter"] == 3


class TestSessionScopeDependencies(MultiDriverTestBase):
    """Test that session-scoped dependencies persist across requests."""

    def create_app(self) -> RestApplication:
        """Create a test application with session-scoped dependency."""
        app = RestApplication()

        # Counter to track how many times the dependency is called
        call_count = {"value": 0}

        @app.dependency(scope="session")
        def session_counter():
            """A dependency that increments a counter each time it's called."""
            call_count["value"] += 1
            return call_count["value"]

        @app.get("/test")
        def test_endpoint(session_counter):
            """Endpoint that uses the session-scoped dependency."""
            return {"counter": session_counter}

        return app

    def test_session_scope_persists_across_requests(self, api):
        """Session-scoped dependencies should be evaluated once and cached across requests."""
        api_client, driver_name = api

        # First request should get counter = 1
        response1 = api_client.get_resource("/test")
        assert response1.body["counter"] == 1

        # Second request should get counter = 1 (cached from first request)
        response2 = api_client.get_resource("/test")
        assert response2.body["counter"] == 1

        # Third request should also get counter = 1
        response3 = api_client.get_resource("/test")
        assert response3.body["counter"] == 1


class TestMixedScopeDependencies(MultiDriverTestBase):
    """Test mixing request and session scoped dependencies."""

    def create_app(self) -> RestApplication:
        """Create a test application with both request and session scoped dependencies."""
        app = RestApplication()

        request_count = {"value": 0}
        session_count = {"value": 0}

        @app.dependency(scope="request")
        def request_counter():
            request_count["value"] += 1
            return request_count["value"]

        @app.dependency(scope="session")
        def session_counter():
            session_count["value"] += 1
            return session_count["value"]

        @app.get("/test")
        def test_endpoint(request_counter, session_counter):
            return {
                "request": request_counter,
                "session": session_counter
            }

        return app

    def test_mixed_scopes_behave_independently(self, api):
        """Request and session scoped dependencies should work correctly together."""
        api_client, driver_name = api

        # First request
        response1 = api_client.get_resource("/test")
        assert response1.body["request"] == 1
        assert response1.body["session"] == 1

        # Second request: request counter increments, session stays same
        response2 = api_client.get_resource("/test")
        assert response2.body["request"] == 2  # Re-evaluated
        assert response2.body["session"] == 1  # Cached

        # Third request
        response3 = api_client.get_resource("/test")
        assert response3.body["request"] == 3  # Re-evaluated again
        assert response3.body["session"] == 1  # Still cached


class TestScopeWithDatabaseConnection(MultiDriverTestBase):
    """Test session scope with a realistic database connection example."""

    def create_app(self) -> RestApplication:
        """Create a test application simulating database connections."""
        app = RestApplication()

        connection_count = {"value": 0}

        class FakeDatabase:
            """Fake database connection."""
            def __init__(self, connection_id):
                self.connection_id = connection_id
                self.query_count = 0

            def query(self, sql):
                self.query_count += 1
                return f"Result from connection {self.connection_id}, query #{self.query_count}"

        @app.dependency(name="db", scope="session")
        def get_database():
            """Session-scoped database connection."""
            connection_count["value"] += 1
            return FakeDatabase(connection_count["value"])

        @app.get("/users")
        def list_users(db):
            result = db.query("SELECT * FROM users")
            return {
                "connection_id": db.connection_id,
                "result": result
            }

        @app.get("/posts")
        def list_posts(db):
            result = db.query("SELECT * FROM posts")
            return {
                "connection_id": db.connection_id,
                "result": result
            }

        return app

    def test_session_scope_database_connection(self, api):
        """Session scope should reuse database connection across different endpoints."""
        api_client, driver_name = api

        # First request to /users
        response1 = api_client.get_resource("/users")
        assert response1.body["connection_id"] == 1
        assert "query #1" in response1.body["result"]

        # Second request to /posts should reuse the same connection
        response2 = api_client.get_resource("/posts")
        assert response2.body["connection_id"] == 1  # Same connection
        assert "query #2" in response2.body["result"]  # But query count increases

        # Third request to /users should still use same connection
        response3 = api_client.get_resource("/users")
        assert response3.body["connection_id"] == 1  # Same connection
        assert "query #3" in response3.body["result"]

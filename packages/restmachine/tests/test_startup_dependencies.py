"""
Tests for startup handler dependency injection.
"""

import json

import pytest

from restmachine import HTTPMethod, Request, Response, RestApplication


class TestStartupDependencies:
    """Test that startup handlers are automatically registered as dependencies."""

    def test_startup_handler_registered_as_dependency(self):
        """Startup handler return value should be injectable into route handlers."""
        app = RestApplication()

        # Define a startup handler that returns a value
        @app.on_startup
        def database():
            return {"connection": "mock_db_connection"}

        # Use the startup handler's return value in a route
        @app.get("/users")
        def get_users(database):
            return {"db": database}

        # Execute the route
        request = Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={"Accept": "application/json"}
        )
        response = app.execute(request)

        # Verify the database dependency was injected
        assert response.status_code == 200
        body = json.loads(response.body)
        assert body == {"db": {"connection": "mock_db_connection"}}

    def test_startup_handler_session_scoped(self):
        """Startup handler should be session-scoped (cached across requests)."""
        app = RestApplication()

        call_count = {"count": 0}

        @app.on_startup
        def counter():
            call_count["count"] += 1
            return call_count["count"]

        @app.get("/count")
        def get_count(counter):
            return {"count": counter}

        # Make multiple requests
        request = Request(
            method=HTTPMethod.GET,
            path="/count",
            headers={"Accept": "application/json"}
        )

        response1 = app.execute(request)
        response2 = app.execute(request)
        response3 = app.execute(request)

        # All should return 1 because it's session-scoped (cached)
        assert json.loads(response1.body) == {"count": 1}
        assert json.loads(response2.body) == {"count": 1}
        assert json.loads(response3.body) == {"count": 1}
        # Verify the function was only called once
        assert call_count["count"] == 1

    def test_shutdown_handler_not_registered_as_dependency(self):
        """Shutdown handlers should NOT be registered as dependencies."""
        app = RestApplication()

        @app.on_shutdown
        def cleanup():
            return "cleanup_value"

        @app.get("/test")
        def test_route():
            return {"message": "test"}

        # Verify cleanup is NOT in dependencies
        assert "cleanup" not in app._dependencies

    def test_multiple_startup_handlers_all_injectable(self):
        """Multiple startup handlers should all be injectable."""
        app = RestApplication()

        @app.on_startup
        def database():
            return "db_connection"

        @app.on_startup
        def cache():
            return "cache_connection"

        @app.get("/config")
        def get_config(database, cache):
            return {"database": database, "cache": cache}

        request = Request(
            method=HTTPMethod.GET,
            path="/config",
            headers={"Accept": "application/json"}
        )
        response = app.execute(request)

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body == {
            "database": "db_connection",
            "cache": "cache_connection"
        }

    def test_startup_handler_with_other_dependencies(self):
        """Startup handlers can depend on other dependencies."""
        app = RestApplication()

        @app.dependency()
        def config():
            return {"host": "localhost", "port": 5432}

        @app.on_startup
        def database(config):
            return f"connected to {config['host']}:{config['port']}"

        @app.get("/status")
        def get_status(database):
            return {"db_status": database}

        request = Request(
            method=HTTPMethod.GET,
            path="/status",
            headers={"Accept": "application/json"}
        )
        response = app.execute(request)

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body == {"db_status": "connected to localhost:5432"}

    def test_startup_handlers_only_called_once(self):
        """Startup handlers should only be called once, even with ASGI lifespan."""
        app = RestApplication()

        database_calls = {"count": 0}
        api_client_calls = {"count": 0}

        @app.on_startup
        def database():
            database_calls["count"] += 1
            return {"connection": f"db_{database_calls['count']}"}

        @app.on_startup
        def api_client():
            api_client_calls["count"] += 1
            return {"client": f"api_{api_client_calls['count']}"}

        @app.get("/status")
        def status(database, api_client):
            return {"database": database, "api_client": api_client}

        # Simulate ASGI lifespan startup using synchronous wrapper
        app.startup_sync()

        # Verify handlers were called once
        assert database_calls["count"] == 1
        assert api_client_calls["count"] == 1

        # Make a request - handlers should NOT be called again
        request = Request(
            method=HTTPMethod.GET,
            path="/status",
            headers={"Accept": "application/json"}
        )
        response = app.execute(request)

        # Verify handlers were NOT called again
        assert database_calls["count"] == 1
        assert api_client_calls["count"] == 1

        # Verify the response uses the cached values from startup
        body = json.loads(response.body)
        assert body == {
            "database": {"connection": "db_1"},
            "api_client": {"client": "api_1"}
        }

        # Make another request to verify caching persists
        response2 = app.execute(request)
        assert database_calls["count"] == 1
        assert api_client_calls["count"] == 1


class TestShutdownDependencies:
    """Test that shutdown handlers support dependency injection."""

    def test_shutdown_handler_can_inject_startup_dependency(self):
        """Shutdown handlers should be able to inject dependencies from startup handlers."""
        app = RestApplication()

        shutdown_received = {}

        @app.on_startup
        def database():
            return {"connection": "db_connection", "connected": True}

        @app.on_shutdown
        def close_database(database):
            # Modify the database to mark it as closed
            database["connected"] = False
            shutdown_received["database"] = database

        # Execute startup
        app.startup_sync()

        # Verify database was created
        assert app._dependency_cache.get("database", "session")["connected"] is True

        # Execute shutdown
        app.shutdown_sync()

        # Verify the shutdown handler received the database dependency
        assert "database" in shutdown_received
        assert shutdown_received["database"]["connection"] == "db_connection"
        assert shutdown_received["database"]["connected"] is False

    def test_shutdown_handler_with_multiple_dependencies(self):
        """Shutdown handlers should be able to inject multiple dependencies."""
        app = RestApplication()

        shutdown_calls = []

        @app.on_startup
        def database():
            return "db_connection"

        @app.on_startup
        def api_client():
            return "api_client_connection"

        @app.on_shutdown
        def cleanup(database, api_client):
            shutdown_calls.append({
                "database": database,
                "api_client": api_client
            })

        # Execute startup
        app.startup_sync()

        # Execute shutdown
        app.shutdown_sync()

        # Verify both dependencies were injected
        assert len(shutdown_calls) == 1
        assert shutdown_calls[0]["database"] == "db_connection"
        assert shutdown_calls[0]["api_client"] == "api_client_connection"

    def test_shutdown_handler_without_dependencies(self):
        """Shutdown handlers should work without any dependencies."""
        app = RestApplication()

        shutdown_called = {"called": False}

        @app.on_shutdown
        def cleanup():
            shutdown_called["called"] = True

        # Execute shutdown
        app.shutdown_sync()

        # Verify the handler was called
        assert shutdown_called["called"] is True

    def test_shutdown_handler_cannot_inject_request(self, caplog):
        """Shutdown handlers should not be able to inject request (no request context)."""
        import logging
        app = RestApplication()

        @app.on_shutdown
        def bad_cleanup(request):
            pass

        # Startup should succeed
        app.startup_sync()

        # Shutdown should log an error but not crash
        with caplog.at_level(logging.ERROR):
            app.shutdown_sync()

        # Verify the error was logged
        assert "Cannot inject 'request' in shutdown handlers" in caplog.text
        assert "Error in shutdown handler" in caplog.text

    def test_multiple_shutdown_handlers_with_dependencies(self):
        """Multiple shutdown handlers should all support dependency injection."""
        app = RestApplication()

        shutdown_order = []

        @app.on_startup
        def database():
            return {"name": "db", "closed": False}

        @app.on_startup
        def cache():
            return {"name": "cache", "closed": False}

        @app.on_shutdown
        def close_database(database):
            database["closed"] = True
            shutdown_order.append("database")

        @app.on_shutdown
        def close_cache(cache):
            cache["closed"] = True
            shutdown_order.append("cache")

        @app.on_shutdown
        def final_cleanup():
            shutdown_order.append("final")

        # Execute startup
        app.startup_sync()

        # Execute shutdown
        app.shutdown_sync()

        # Verify all handlers were called in order
        assert shutdown_order == ["database", "cache", "final"]

        # Verify dependencies were properly injected and modified
        db = app._dependency_cache.get("database", "session")
        assert db["closed"] is True
        cache_obj = app._dependency_cache.get("cache", "session")
        assert cache_obj["closed"] is True

    def test_shutdown_handler_can_inject_regular_dependencies(self):
        """Shutdown handlers should be able to inject regular dependencies too."""
        app = RestApplication()

        shutdown_received = {}

        @app.dependency()
        def config():
            return {"log_level": "INFO"}

        @app.on_startup
        def database():
            return "db_connection"

        @app.on_shutdown
        def cleanup(database, config):
            shutdown_received["database"] = database
            shutdown_received["config"] = config

        # Execute startup
        app.startup_sync()

        # Execute shutdown
        app.shutdown_sync()

        # Verify both dependencies were injected
        assert shutdown_received["database"] == "db_connection"
        assert shutdown_received["config"] == {"log_level": "INFO"}

"""
Performance benchmarks for state machine paths.

Tests focus on measuring the performance of different state machine
paths rather than payload sizes or JSON complexity. Each test represents
a distinct path through the state machine with different state counts.

State Machine Paths:
- Simple GET: ~7 states (no auth, no conditional)
- GET + Auth: ~9 states
- GET + Conditional: ~12 states
- POST Create: ~8 states
- Error paths: 1-10 states

This allows us to benchmark the state machine optimization and compare
old vs new implementations.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestSimpleGetPath(MultiDriverTestBase):
    """Benchmark: Simple GET path (~7 states).

    This is the fastest path through the state machine:
    - RouteExists
    - ServiceAvailable
    - KnownMethod
    - UriTooLong
    - MethodAllowed
    - MalformedRequest
    - ContentTypesProvided
    - ExecuteAndRender

    No authentication, no conditional requests.
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.get("/simple")
        def get_simple():
            return {"message": "Hello", "value": 42}

        @app.get("/resource/{id}")
        def get_resource(path_params):
            return {"id": path_params["id"], "data": "example"}

        return app

    def test_simple_get_no_params(self, api, benchmark):
        """Benchmark simplest GET request (no path params)."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/simple")

        data = api_client.expect_successful_retrieval(result)
        assert data["message"] == "Hello"
        assert data["value"] == 42

    def test_simple_get_with_path_param(self, api, benchmark):
        """Benchmark simple GET with path parameter."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/resource/123")

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == "123"


class TestAuthenticatedGetPath(MultiDriverTestBase):
    """Benchmark: GET with authentication (~9 states).

    Adds authorization checks to the simple path:
    - ... (all simple path states)
    - Authorized
    - Forbidden
    - ... (continue)
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        # Simple session store
        sessions = {"valid-token": {"user_id": "1", "name": "TestUser", "role": "user"}}

        @app.default_authorized
        def check_auth(request):
            # Public endpoint check
            if request.path == "/simple":
                return True
            # Check auth header
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
                return token in sessions
            return False

        @app.default_forbidden
        def check_permissions(request):
            # Admin endpoint check
            if request.path == "/admin":
                auth = request.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    token = auth[7:]
                    session = sessions.get(token, {})
                    return session.get("role") != "admin"
            return False

        @app.get("/protected")
        def get_protected():
            return {"user": "TestUser", "data": "secret"}

        @app.get("/admin")
        def get_admin():
            return {"user": "TestUser", "admin_data": "top secret"}

        return app

    def test_authenticated_get_success(self, api, benchmark):
        """Benchmark GET with valid authentication."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/protected").accepts("application/json")
            request.headers["Authorization"] = "Bearer valid-token"
            return api_client.execute(request)

        result = benchmark(make_request)

        data = api_client.expect_successful_retrieval(result)
        assert data["user"] == "TestUser"

    def test_authenticated_get_forbidden(self, api, benchmark):
        """Benchmark GET with authentication but insufficient permissions."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/admin").accepts("application/json")
            request.headers["Authorization"] = "Bearer valid-token"
            return api_client.execute(request)

        result = benchmark(make_request)

        # Should get 403 Forbidden
        assert result.status_code == 403


class TestConditionalGetPath(MultiDriverTestBase):
    """Benchmark: GET with conditional requests (~12 states).

    Adds conditional request processing:
    - ... (all simple path states)
    - ResourceExists
    - IfMatch
    - IfUnmodifiedSince
    - IfNoneMatch
    - IfModifiedSince
    - ... (continue)
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        # Resource store for conditional requests
        resources = {
            "123": {
                "id": 123,
                "data": "Example resource",
                "version": 1
            }
        }

        @app.resource_exists
        def check_resource_exists(request):
            resource_id = request.path_params.get("id")
            resource = resources.get(resource_id)
            return resource  # Returns resource if exists, None if not

        @app.generate_etag
        def make_etag(request):
            resource_id = request.path_params.get("id")
            resource = resources.get(resource_id)
            if resource:
                return f'"v{resource["version"]}"'  # Return quoted ETag
            return None

        @app.get("/conditional/{id}")
        def get_conditional(check_resource_exists, make_etag):
            # Dependencies are injected, just return the resource
            return check_resource_exists

        return app

    def test_conditional_get_etag_match(self, api, benchmark):
        """Benchmark GET with If-None-Match matching (304 Not Modified)."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/conditional/123").accepts("application/json")
            request.headers["If-None-Match"] = '"v1"'
            return api_client.execute(request)

        result = benchmark(make_request)

        # Should get 304 Not Modified
        assert result.status_code == 304

    def test_conditional_get_etag_mismatch(self, api, benchmark):
        """Benchmark GET with If-None-Match not matching (200 with data)."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/conditional/123").accepts("application/json")
            request.headers["If-None-Match"] = '"v999"'
            return api_client.execute(request)

        result = benchmark(make_request)

        # Should get 200 with data
        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 123


class TestPostCreatePath(MultiDriverTestBase):
    """Benchmark: POST create path (~8 states).

    Similar to simple GET but with request body parsing:
    - RouteExists
    - ServiceAvailable
    - KnownMethod
    - UriTooLong
    - MethodAllowed
    - MalformedRequest
    - ContentTypesAccepted
    - ExecuteAndRender
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.post("/resources")
        def create_resource(json_body):
            return {
                "id": 456,
                "name": json_body.get("name"),
                "value": json_body.get("value")
            }

        return app

    def test_post_create(self, api, benchmark):
        """Benchmark POST resource creation."""
        api_client, driver_name = api

        payload = {"name": "New Resource", "value": 100}
        result = benchmark(api_client.create_resource, "/resources", payload)

        data = api_client.expect_successful_creation(result, ["id", "name", "value"])
        assert data["id"] == 456
        assert data["name"] == "New Resource"


class TestPutUpdatePath(MultiDriverTestBase):
    """Benchmark: PUT update path (~9 states)."""

    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.put("/resources/{id}")
        def update_resource(path_params, json_body):
            return {
                "id": int(path_params["id"]),
                "name": json_body.get("name"),
                "updated": True
            }

        return app

    def test_put_update(self, api, benchmark):
        """Benchmark PUT resource update."""
        api_client, driver_name = api

        payload = {"name": "Updated Resource"}
        result = benchmark(api_client.update_resource, "/resources/123", payload)

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 123
        assert data["updated"] is True


class TestDeletePath(MultiDriverTestBase):
    """Benchmark: DELETE path (~8 states)."""

    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.delete("/resources/{id}")
        def delete_resource(path_params):
            return None  # 204 No Content

        return app

    def test_delete(self, api, benchmark):
        """Benchmark DELETE operation."""
        api_client, driver_name = api

        result = benchmark(api_client.delete_resource, "/resources/123")

        api_client.expect_no_content(result)


class TestErrorPaths(MultiDriverTestBase):
    """Benchmark: Error paths (1-10 states).

    Error responses can short-circuit the state machine:
    - 404: 1 state (RouteExists fails)
    - 405: 1 state (RouteExists, wrong method)
    - 401: ~9 states (Authorized fails)
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        @app.get("/exists")
        def get_exists():
            return {"status": "ok"}

        # Auth setup for 401/403 testing
        @app.default_authorized
        def check_auth(request):
            if request.path == "/protected":
                auth = request.headers.get("Authorization", "")
                return auth.startswith("Bearer valid-token")
            return True  # Other endpoints don't require auth

        @app.get("/protected")
        def get_protected():
            return {"data": "secret"}

        return app

    def test_404_not_found(self, api, benchmark):
        """Benchmark 404 error path (route not found)."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/nonexistent")

        assert result.status_code == 404

    def test_405_method_not_allowed(self, api, benchmark):
        """Benchmark 405 error path (wrong method)."""
        api_client, driver_name = api

        result = benchmark(api_client.create_resource, "/exists", {})

        assert result.status_code == 405

    def test_401_unauthorized(self, api, benchmark):
        """Benchmark 401 error path (no authentication)."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/protected")

        assert result.status_code == 401


class TestCRUDCyclePath(MultiDriverTestBase):
    """Benchmark: Complete CRUD cycle.

    Exercises multiple paths in sequence:
    - POST (create)
    - GET (read)
    - PUT (update)
    - GET (read again)
    - DELETE (remove)
    """

    def create_app(self) -> RestApplication:
        app = RestApplication()

        # In-memory store
        resources = {}
        next_id = [1]

        @app.post("/resources")
        def create_resource(json_body):
            resource_id = next_id[0]
            next_id[0] += 1
            resource = {"id": resource_id, **json_body}
            resources[resource_id] = resource
            return resource

        @app.get("/resources/{id}")
        def get_resource(path_params):
            resource_id = int(path_params["id"])
            return resources.get(resource_id, {"error": "Not found"})

        @app.put("/resources/{id}")
        def update_resource(path_params, json_body):
            resource_id = int(path_params["id"])
            if resource_id in resources:
                resources[resource_id].update(json_body)
                return resources[resource_id]
            return {"error": "Not found"}

        @app.delete("/resources/{id}")
        def delete_resource(path_params):
            resource_id = int(path_params["id"])
            resources.pop(resource_id, None)
            return None

        return app

    def test_crud_cycle(self, api, benchmark):
        """Benchmark complete CRUD cycle."""
        api_client, driver_name = api

        def crud_cycle():
            # Create
            create_result = api_client.create_resource("/resources", {"name": "Test"})
            resource = api_client.expect_successful_creation(create_result, ["id", "name"])
            resource_id = resource["id"]

            # Read
            get_result = api_client.get_resource(f"/resources/{resource_id}")
            api_client.expect_successful_retrieval(get_result)

            # Update
            update_result = api_client.update_resource(
                f"/resources/{resource_id}",
                {"name": "Updated"}
            )
            api_client.expect_successful_retrieval(update_result)

            # Delete
            delete_result = api_client.delete_resource(f"/resources/{resource_id}")
            api_client.expect_no_content(delete_result)

        benchmark(crud_cycle)

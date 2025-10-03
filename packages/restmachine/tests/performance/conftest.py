"""
Performance test optimizations.

This conftest.py provides module-scoped fixtures for HTTP server drivers
to avoid repeatedly starting/stopping servers for each test class.

For performance benchmarks, we create a single comprehensive app with all routes
and reuse it across all test classes in the module. This reduces server startup
overhead from ~40 restarts (8 classes × 5 drivers) to 5 (1 per driver).
"""

import pytest
from restmachine import RestApplication
from restmachine.testing.dsl import RestApiDsl


def create_comprehensive_performance_app() -> RestApplication:
    """
    Create a single app with all routes needed by all performance test classes.

    This allows module-scoped fixtures to reuse the same app and server
    across all performance tests, significantly reducing overhead.
    """
    app = RestApplication()

    # ====================================================================
    # TestSimpleGetPath routes
    # ====================================================================
    @app.get("/simple")
    def get_simple():
        return {"message": "Hello", "value": 42}

    @app.get("/resource/{id}")
    def get_resource(path_params):
        return {"id": path_params["id"], "data": "example"}

    # ====================================================================
    # TestAuthenticatedGetPath routes
    # ====================================================================
    sessions = {"valid-token": {"user_id": "1", "name": "TestUser", "role": "user"}}

    @app.default_authorized
    def check_auth(request):
        # Public endpoint check
        if request.path in ["/simple", "/exists"]:
            return True
        # Protected endpoint check
        if request.path in ["/protected", "/admin"]:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
                return token in sessions
            return False
        return True  # Other endpoints don't require auth

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

    # ====================================================================
    # TestConditionalGetPath routes
    # ====================================================================
    conditional_resources = {
        "123": {
            "id": 123,
            "data": "Example resource",
            "version": 1
        }
    }

    @app.resource_exists
    def check_resource_exists(request):
        resource_id = request.path_params.get("id")
        resource = conditional_resources.get(resource_id)
        return resource  # Returns resource if exists, None if not

    @app.generate_etag
    def make_etag(request):
        resource_id = request.path_params.get("id")
        resource = conditional_resources.get(resource_id)
        if resource:
            return f'"v{resource["version"]}"'  # Return quoted ETag
        return None

    @app.get("/conditional/{id}")
    def get_conditional(check_resource_exists, make_etag):
        # Dependencies are injected, just return the resource
        return check_resource_exists

    # ====================================================================
    # POST/PUT/DELETE routes are defined below in CRUD section
    # (they're the same routes, just with state management)
    # ====================================================================

    # ====================================================================
    # TestErrorPaths routes
    # ====================================================================
    @app.get("/exists")
    def get_exists():
        return {"status": "ok"}

    # Auth routes already defined above (check_auth handles /protected)

    # ====================================================================
    # Combined routes for POST/PUT/DELETE/GET on /resources
    # ====================================================================
    # These routes need to work for:
    # - TestPostCreatePath: expects id=456, includes "value" field
    # - TestPutUpdatePath: expects id from path, includes "updated=True"
    # - TestDeletePath: expects 204 No Content
    # - TestCRUDCyclePath: expects full CRUD with state management

    # In-memory store for CRUD operations
    crud_resources = {}
    crud_next_id = [1]  # Using list to make it mutable in closure

    @app.post("/resources")
    def create_resource_combined(json_body):
        # For TestPostCreatePath compatibility: always return id=456
        # For CRUD: store it for later retrieval
        resource = {
            "id": 456,
            "name": json_body.get("name"),
            "value": json_body.get("value")  # Include value for TestPostCreatePath
        }
        # Store for CRUD cycle
        crud_resources[456] = resource
        # Also store with incremental ID for CRUD cycle
        resource_id = crud_next_id[0]
        crud_next_id[0] += 1
        crud_resources[resource_id] = dict(resource, id=resource_id)
        return resource

    @app.get("/resources/{id}")
    def get_resource_combined(path_params):
        resource_id = int(path_params["id"])
        # Check if resource exists in store
        if resource_id in crud_resources:
            return crud_resources[resource_id]
        # For non-existent resources, return a default
        return {"id": resource_id, "error": "Not found"}

    @app.put("/resources/{id}")
    def update_resource_combined(path_params, json_body):
        resource_id = int(path_params["id"])
        # For TestPutUpdatePath: always return updated=True
        result = {
            "id": resource_id,
            "name": json_body.get("name"),
            "updated": True
        }
        # Update store for CRUD cycle
        if resource_id in crud_resources:
            crud_resources[resource_id].update(json_body)
            crud_resources[resource_id]["updated"] = True
        else:
            crud_resources[resource_id] = result
        return result

    @app.delete("/resources/{id}")
    def delete_resource_combined(path_params):
        resource_id = int(path_params["id"])
        crud_resources.pop(resource_id, None)
        return None  # 204 No Content

    return app


@pytest.fixture(scope="module")
def performance_app():
    """Module-scoped fixture providing a comprehensive app for all performance tests."""
    return create_comprehensive_performance_app()


@pytest.fixture(scope="module")
def api(request, performance_app):
    """
    Module-scoped fixture for performance tests.

    Overrides the class-scoped fixture from MultiDriverTestBase to use module scope.
    This significantly reduces server startup overhead for HTTP drivers:
    - Before: 40 server starts (8 classes × 5 drivers)
    - After: 5 server starts (1 per driver)

    For the direct driver, this has minimal impact since there's no server startup.
    For HTTP drivers (Uvicorn/Hypercorn), this saves ~4-8ms per test class.
    """
    driver_name = request.param

    # Import here to avoid circular dependencies
    from tests.framework import MultiDriverTestBase

    # Use the shared app instead of creating a new one per class
    app = performance_app
    driver = MultiDriverTestBase.create_driver(driver_name, app)

    # HTTP server drivers need to be started/stopped with context manager
    if driver_name.startswith('hypercorn-') or driver_name.startswith('uvicorn-'):
        with driver as active_driver:
            yield RestApiDsl(active_driver), driver_name
    else:
        # Direct driver and AWS Lambda don't need context manager
        yield RestApiDsl(driver), driver_name


def pytest_configure(config):
    """
    Override create_app for all performance test classes.

    This is called once when pytest starts. We monkey-patch the create_app
    method for test classes in this module to return the shared comprehensive app.
    """
    # Note: Actual monkey-patching happens in pytest_collection_modifyitems
    # since we need access to the actual test classes after collection
    pass


def pytest_collection_modifyitems(config, items):
    """
    Modify test items after collection.

    For performance test classes in this module, replace their create_app
    method to return the shared comprehensive app.
    """
    performance_app_instance = None

    for item in items:
        # Check if this is a performance test in this module
        if "performance/test_state_machine_paths.py" in str(item.fspath):
            # Override create_app for the test class to use shared app
            if item.cls and hasattr(item.cls, 'create_app'):
                # Create a new create_app method that returns the shared app
                def create_shared_app(self):
                    # Use the fixture-created app
                    # This will be called by tests but we override it in the fixture
                    return create_comprehensive_performance_app()

                # Replace the class's create_app method
                item.cls.create_app = create_shared_app

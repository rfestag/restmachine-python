"""
Performance benchmarks for basic CRUD operations.

Tests GET, POST, PUT, and DELETE operations across all drivers
to measure baseline performance and detect regressions.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestGetRequestPerformance(MultiDriverTestBase):
    """Benchmark GET request performance."""

    def create_app(self) -> RestApplication:
        """Create app with simple GET endpoints."""
        app = RestApplication()

        @app.get("/users/{id}")
        def get_user(path_params):
            return {"id": int(path_params["id"]), "name": "John Doe", "email": "john@example.com"}

        @app.get("/simple")
        def get_simple():
            return {"message": "Hello"}

        return app

    def test_get_with_path_param(self, api, benchmark):
        """Benchmark GET request with path parameter."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/users/123")

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 123
        assert data["name"] == "John Doe"

    def test_get_simple_response(self, api, benchmark):
        """Benchmark GET request with simple response."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/simple")

        data = api_client.expect_successful_retrieval(result)
        assert data["message"] == "Hello"


class TestPostRequestPerformance(MultiDriverTestBase):
    """Benchmark POST request performance."""

    def create_app(self) -> RestApplication:
        """Create app with POST endpoints."""
        app = RestApplication()

        @app.post("/users")
        def create_user(json_body):
            return {"id": 123, **json_body}

        @app.post("/echo")
        def echo_data(json_body):
            return json_body

        return app

    def test_post_create_user(self, api, benchmark):
        """Benchmark POST request creating a user."""
        api_client, driver_name = api

        user_data = {"name": "Jane Smith", "email": "jane@example.com", "role": "admin"}
        result = benchmark(api_client.create_resource, "/users", user_data)

        data = api_client.expect_successful_creation(result, ["id", "name", "email", "role"])
        assert data["name"] == "Jane Smith"
        assert data["id"] == 123

    def test_post_echo_json(self, api, benchmark):
        """Benchmark POST request echoing JSON data."""
        api_client, driver_name = api

        echo_data = {"key1": "value1", "key2": "value2", "nested": {"key3": "value3"}}
        result = benchmark(api_client.create_resource, "/echo", echo_data)

        data = api_client.expect_successful_creation(result, ["key1", "key2", "nested"])
        assert data["nested"]["key3"] == "value3"


class TestPutRequestPerformance(MultiDriverTestBase):
    """Benchmark PUT request performance."""

    def create_app(self) -> RestApplication:
        """Create app with PUT endpoints."""
        app = RestApplication()

        @app.put("/users/{id}")
        def update_user(path_params, json_body):
            return {"id": int(path_params["id"]), **json_body, "updated": True}

        return app

    def test_put_update_user(self, api, benchmark):
        """Benchmark PUT request updating a user."""
        api_client, driver_name = api

        update_data = {"name": "Jane Doe Updated", "email": "jane.updated@example.com"}

        def update_operation():
            return api_client.update_resource("/users/456", update_data)

        result = benchmark(update_operation)

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 456
        assert data["updated"] is True
        assert data["name"] == "Jane Doe Updated"


class TestDeleteRequestPerformance(MultiDriverTestBase):
    """Benchmark DELETE request performance."""

    def create_app(self) -> RestApplication:
        """Create app with DELETE endpoints."""
        app = RestApplication()

        @app.delete("/users/{id}")
        def delete_user(path_params):
            return None  # 204 No Content

        return app

    def test_delete_user(self, api, benchmark):
        """Benchmark DELETE request."""
        api_client, driver_name = api

        def delete_operation():
            return api_client.delete_resource("/users/789")

        result = benchmark(delete_operation)

        api_client.expect_no_content(result)


class TestMixedOperationsPerformance(MultiDriverTestBase):
    """Benchmark combined CRUD operations."""

    def create_app(self) -> RestApplication:
        """Create app with all CRUD endpoints."""
        app = RestApplication()

        # In-memory store for benchmarking
        users = {}
        next_id = [1]

        @app.get("/users")
        def list_users():
            return {"users": list(users.values()), "count": len(users)}

        @app.get("/users/{id}")
        def get_user(path_params):
            user_id = int(path_params["id"])
            return users.get(user_id, {"error": "Not found"})

        @app.post("/users")
        def create_user(json_body):
            user_id = next_id[0]
            next_id[0] += 1
            user = {"id": user_id, **json_body}
            users[user_id] = user
            return user

        @app.put("/users/{id}")
        def update_user(path_params, json_body):
            user_id = int(path_params["id"])
            if user_id in users:
                users[user_id].update(json_body)
                return users[user_id]
            return {"error": "Not found"}

        @app.delete("/users/{id}")
        def delete_user(path_params):
            user_id = int(path_params["id"])
            users.pop(user_id, None)
            return None

        return app

    def test_create_read_update_delete_cycle(self, api, benchmark):
        """Benchmark a complete CRUD cycle."""
        api_client, driver_name = api

        def crud_cycle():
            # Create
            create_result = api_client.create_resource("/users", {"name": "Test User"})
            user_data = api_client.expect_successful_creation(create_result, ["id", "name"])
            user_id = user_data["id"]

            # Read
            get_result = api_client.get_resource(f"/users/{user_id}")
            api_client.expect_successful_retrieval(get_result)

            # Update
            update_result = api_client.update_resource(f"/users/{user_id}", {"name": "Updated User"})
            api_client.expect_successful_retrieval(update_result)

            # Delete
            delete_result = api_client.delete_resource(f"/users/{user_id}")
            api_client.expect_no_content(delete_result)

        benchmark(crud_cycle)

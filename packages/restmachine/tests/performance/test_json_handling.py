"""
Performance benchmarks for JSON serialization and deserialization.

Tests JSON handling performance for various payload sizes and structures
across all drivers.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestSmallPayloadPerformance(MultiDriverTestBase):
    """Benchmark small JSON payload handling."""

    def create_app(self) -> RestApplication:
        """Create app with small payload endpoints."""
        app = RestApplication()

        @app.get("/small")
        def get_small():
            return {"id": 1, "name": "Test", "active": True}

        @app.post("/small")
        def post_small(json_body):
            return {"received": json_body, "processed": True}

        return app

    def test_get_small_json(self, api, benchmark):
        """Benchmark GET with small JSON response."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/small")

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 1
        assert data["name"] == "Test"

    def test_post_small_json(self, api, benchmark):
        """Benchmark POST with small JSON payload."""
        api_client, driver_name = api

        payload = {"field1": "value1", "field2": 42, "field3": True}
        result = benchmark(api_client.create_resource, "/small", payload)

        data = api_client.expect_successful_creation(result, ["received", "processed"])
        assert data["processed"] is True


class TestMediumPayloadPerformance(MultiDriverTestBase):
    """Benchmark medium JSON payload handling."""

    def create_app(self) -> RestApplication:
        """Create app with medium payload endpoints."""
        app = RestApplication()

        @app.get("/user")
        def get_user():
            return {
                "id": 12345,
                "username": "johndoe",
                "email": "john@example.com",
                "firstName": "John",
                "lastName": "Doe",
                "age": 30,
                "address": {
                    "street": "123 Main St",
                    "city": "Springfield",
                    "state": "IL",
                    "zipCode": "62701",
                    "country": "USA",
                },
                "phoneNumbers": [
                    {"type": "home", "number": "555-1234"},
                    {"type": "work", "number": "555-5678"},
                ],
                "preferences": {
                    "theme": "dark",
                    "notifications": True,
                    "language": "en",
                },
            }

        @app.post("/user")
        def create_user(json_body):
            return {"id": 12345, **json_body}

        return app

    def test_get_medium_json(self, api, benchmark):
        """Benchmark GET with medium JSON response."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/user")

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == 12345
        assert "address" in data
        assert "phoneNumbers" in data

    def test_post_medium_json(self, api, benchmark):
        """Benchmark POST with medium JSON payload."""
        api_client, driver_name = api

        payload = {
            "username": "janedoe",
            "email": "jane@example.com",
            "firstName": "Jane",
            "lastName": "Doe",
            "age": 28,
            "address": {
                "street": "456 Oak Ave",
                "city": "Portland",
                "state": "OR",
                "zipCode": "97201",
                "country": "USA",
            },
            "phoneNumbers": [{"type": "mobile", "number": "555-9999"}],
            "preferences": {"theme": "light", "notifications": False, "language": "en"},
        }
        result = benchmark(api_client.create_resource, "/user", payload)

        data = api_client.expect_successful_creation(result, ["id", "username", "address"])
        assert data["username"] == "janedoe"


class TestLargePayloadPerformance(MultiDriverTestBase):
    """Benchmark large JSON payload handling."""

    def create_app(self) -> RestApplication:
        """Create app with large payload endpoints."""
        app = RestApplication()

        @app.get("/list")
        def get_list():
            # Generate a list of 100 items
            return {
                "items": [
                    {
                        "id": i,
                        "name": f"Item {i}",
                        "description": f"Description for item {i}",
                        "price": i * 10.5,
                        "inStock": i % 2 == 0,
                        "category": "electronics" if i % 3 == 0 else "clothing",
                        "tags": [f"tag{i}", f"tag{i+1}", f"tag{i+2}"],
                    }
                    for i in range(100)
                ],
                "total": 100,
                "page": 1,
            }

        @app.post("/bulk")
        def bulk_create(json_body):
            items = json_body.get("items", [])
            return {"created": len(items), "items": items}

        return app

    def test_get_large_json_list(self, api, benchmark):
        """Benchmark GET with large JSON list response."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/list")

        data = api_client.expect_successful_retrieval(result)
        assert len(data["items"]) == 100
        assert data["total"] == 100

    def test_post_large_json_list(self, api, benchmark):
        """Benchmark POST with large JSON list payload."""
        api_client, driver_name = api

        items = [
            {
                "name": f"Product {i}",
                "price": i * 5.99,
                "quantity": i,
            }
            for i in range(50)
        ]
        payload = {"items": items}

        result = benchmark(api_client.create_resource, "/bulk", payload)

        data = api_client.expect_successful_creation(result, ["created", "items"])
        assert data["created"] == 50


class TestNestedJsonPerformance(MultiDriverTestBase):
    """Benchmark deeply nested JSON structure handling."""

    def create_app(self) -> RestApplication:
        """Create app with nested JSON endpoints."""
        app = RestApplication()

        @app.get("/nested")
        def get_nested():
            return {
                "level1": {
                    "level2": {
                        "level3": {
                            "level4": {
                                "level5": {
                                    "data": "deeply nested value",
                                    "array": [1, 2, 3, 4, 5],
                                }
                            }
                        }
                    }
                }
            }

        @app.post("/nested")
        def post_nested(json_body):
            return {"received": json_body, "depth": "deep"}

        return app

    def test_get_nested_json(self, api, benchmark):
        """Benchmark GET with deeply nested JSON."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/nested")

        data = api_client.expect_successful_retrieval(result)
        assert data["level1"]["level2"]["level3"]["level4"]["level5"]["data"] == "deeply nested value"

    def test_post_nested_json(self, api, benchmark):
        """Benchmark POST with deeply nested JSON."""
        api_client, driver_name = api

        payload = {
            "company": {
                "departments": [
                    {
                        "name": "Engineering",
                        "teams": [
                            {
                                "name": "Backend",
                                "members": [
                                    {"name": "Alice", "role": "Senior"},
                                    {"name": "Bob", "role": "Junior"},
                                ],
                            },
                            {
                                "name": "Frontend",
                                "members": [
                                    {"name": "Charlie", "role": "Senior"},
                                    {"name": "Diana", "role": "Mid"},
                                ],
                            },
                        ],
                    }
                ]
            }
        }

        result = benchmark(api_client.create_resource, "/nested", payload)

        data = api_client.expect_successful_creation(result, ["received", "depth"])
        assert data["depth"] == "deep"


class TestVariousDataTypesPerformance(MultiDriverTestBase):
    """Benchmark JSON with various data types."""

    def create_app(self) -> RestApplication:
        """Create app with mixed data type endpoints."""
        app = RestApplication()

        @app.get("/mixed")
        def get_mixed():
            return {
                "string": "text value",
                "integer": 42,
                "float": 3.14159,
                "boolean_true": True,
                "boolean_false": False,
                "null_value": None,
                "array_mixed": [1, "two", 3.0, True, None],
                "object_nested": {"key": "value", "number": 123},
            }

        @app.post("/mixed")
        def post_mixed(json_body):
            return {"types": "preserved", "data": json_body}

        return app

    def test_get_mixed_types(self, api, benchmark):
        """Benchmark GET with mixed data types."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/mixed")

        data = api_client.expect_successful_retrieval(result)
        assert data["integer"] == 42
        assert data["float"] == 3.14159
        assert data["boolean_true"] is True
        assert data["null_value"] is None

    def test_post_mixed_types(self, api, benchmark):
        """Benchmark POST with mixed data types."""
        api_client, driver_name = api

        payload = {
            "strings": ["one", "two", "three"],
            "numbers": [1, 2, 3, 4, 5],
            "floats": [1.1, 2.2, 3.3],
            "booleans": [True, False, True],
            "mixed_array": [1, "text", True, None, 3.14],
        }

        result = benchmark(api_client.create_resource, "/mixed", payload)

        data = api_client.expect_successful_creation(result, ["types", "data"])
        assert data["types"] == "preserved"

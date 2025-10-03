"""
Performance benchmarks for routing operations.

Tests routing performance with path parameters, query parameters,
and complex route matching across all drivers.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestPathParameterPerformance(MultiDriverTestBase):
    """Benchmark routing with path parameters."""

    def create_app(self) -> RestApplication:
        """Create app with various path parameter patterns."""
        app = RestApplication()

        # Use consistent parameter names to avoid route conflicts
        @app.get("/single/{id}")
        def get_single(path_params):
            return {"id": path_params["id"]}

        @app.get("/double/{user_id}/posts/{post_id}")
        def get_double(path_params):
            return {"user_id": path_params["user_id"], "post_id": path_params["post_id"]}

        @app.get("/triple/{user_id}/posts/{post_id}/comments/{comment_id}")
        def get_triple(path_params):
            return {
                "user_id": path_params["user_id"],
                "post_id": path_params["post_id"],
                "comment_id": path_params["comment_id"],
            }

        return app

    def test_single_path_param(self, api, benchmark):
        """Benchmark routing with single path parameter."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/single/123")

        data = api_client.expect_successful_retrieval(result)
        assert data["id"] == "123"

    def test_two_path_params(self, api, benchmark):
        """Benchmark routing with two path parameters."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/double/123/posts/456")

        data = api_client.expect_successful_retrieval(result)
        assert data["user_id"] == "123"
        assert data["post_id"] == "456"

    def test_three_path_params(self, api, benchmark):
        """Benchmark routing with three path parameters."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/triple/123/posts/456/comments/789")

        data = api_client.expect_successful_retrieval(result)
        assert data["user_id"] == "123"
        assert data["post_id"] == "456"
        assert data["comment_id"] == "789"


class TestQueryParameterPerformance(MultiDriverTestBase):
    """Benchmark routing with query parameters."""

    def create_app(self) -> RestApplication:
        """Create app with query parameter handling."""
        app = RestApplication()

        @app.get("/search")
        def search(query_params):
            return {
                "query": query_params.get("q", ""),
                "page": query_params.get("page", "1"),
                "limit": query_params.get("limit", "10"),
            }

        @app.get("/filter")
        def filter_items(query_params):
            return {
                "filters": {k: v for k, v in query_params.items()},
                "count": len(query_params),
            }

        return app

    def test_single_query_param(self, api, benchmark):
        """Benchmark routing with single query parameter."""
        api_client, driver_name = api

        result = benchmark(api_client.search_resources, "/search", {"q": "test"})

        data = api_client.expect_successful_retrieval(result)
        assert data["query"] == "test"

    def test_multiple_query_params(self, api, benchmark):
        """Benchmark routing with multiple query parameters."""
        api_client, driver_name = api

        result = benchmark(api_client.search_resources, "/search", {"q": "test", "page": "2", "limit": "20"})

        data = api_client.expect_successful_retrieval(result)
        assert data["query"] == "test"
        assert data["page"] == "2"
        assert data["limit"] == "20"

    def test_many_query_params(self, api, benchmark):
        """Benchmark routing with many query parameters."""
        api_client, driver_name = api

        query_params = {f"filter{i}": f"value{i}" for i in range(10)}
        result = benchmark(api_client.search_resources, "/filter", query_params)

        data = api_client.expect_successful_retrieval(result)
        assert data["count"] == 10


class TestComplexRoutingPerformance(MultiDriverTestBase):
    """Benchmark complex routing scenarios."""

    def create_app(self) -> RestApplication:
        """Create app with complex routing patterns."""
        app = RestApplication()

        @app.get("/api/v1/users/{user_id}")
        def get_user(path_params):
            return {"user_id": path_params["user_id"], "version": "v1"}

        @app.get("/api/v1/users/{user_id}/profile")
        def get_profile(path_params):
            return {"user_id": path_params["user_id"], "resource": "profile"}

        @app.get("/api/v1/users/{user_id}/settings")
        def get_settings(path_params):
            return {"user_id": path_params["user_id"], "resource": "settings"}

        @app.get("/api/v1/organizations/{org_id}/members/{member_id}")
        def get_org_member(path_params):
            return {"org_id": path_params["org_id"], "member_id": path_params["member_id"]}

        return app

    def test_versioned_api_route(self, api, benchmark):
        """Benchmark versioned API route matching."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/api/v1/users/123")

        data = api_client.expect_successful_retrieval(result)
        assert data["user_id"] == "123"
        assert data["version"] == "v1"

    def test_nested_resource_route(self, api, benchmark):
        """Benchmark nested resource route matching."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/api/v1/users/123/profile")

        data = api_client.expect_successful_retrieval(result)
        assert data["user_id"] == "123"
        assert data["resource"] == "profile"

    def test_deep_nested_route(self, api, benchmark):
        """Benchmark deeply nested route matching."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/api/v1/organizations/456/members/789")

        data = api_client.expect_successful_retrieval(result)
        assert data["org_id"] == "456"
        assert data["member_id"] == "789"


class TestMixedParametersPerformance(MultiDriverTestBase):
    """Benchmark routing with mixed path and query parameters."""

    def create_app(self) -> RestApplication:
        """Create app with mixed parameter patterns."""
        app = RestApplication()

        @app.get("/users/{id}/posts")
        def get_user_posts(path_params, query_params):
            return {
                "user_id": path_params["id"],
                "page": query_params.get("page", "1"),
                "sort": query_params.get("sort", "date"),
            }

        @app.get("/products/{category}/{subcategory}")
        def get_products(path_params, query_params):
            return {
                "category": path_params["category"],
                "subcategory": path_params["subcategory"],
                "min_price": query_params.get("min_price", "0"),
                "max_price": query_params.get("max_price", "1000"),
                "in_stock": query_params.get("in_stock", "true"),
            }

        return app

    def test_path_and_query_params(self, api, benchmark):
        """Benchmark routing with both path and query parameters."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/users/123/posts").accepts("application/json")
            request.query_params.update({"page": "2", "sort": "title"})
            return api_client.execute(request)

        result = benchmark(make_request)

        data = api_client.expect_successful_retrieval(result)
        assert data["user_id"] == "123"
        assert data["page"] == "2"
        assert data["sort"] == "title"

    def test_complex_mixed_params(self, api, benchmark):
        """Benchmark complex mixed parameter routing."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/products/electronics/laptops").accepts("application/json")
            request.query_params.update({
                "min_price": "500",
                "max_price": "2000",
                "in_stock": "true"
            })
            return api_client.execute(request)

        result = benchmark(make_request)

        data = api_client.expect_successful_retrieval(result)
        assert data["category"] == "electronics"
        assert data["subcategory"] == "laptops"
        assert data["min_price"] == "500"
        assert data["max_price"] == "2000"
        assert data["in_stock"] == "true"

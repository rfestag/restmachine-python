"""Tests for Router functionality and mounting."""

from restmachine import RestApplication, Router
from restmachine.models import Request, HTTPMethod
from restmachine.router import normalize_path


class TestPathNormalization:
    """Test path normalization utility."""

    def test_root_with_slash_path(self):
        assert normalize_path("/", "/users") == "/users"

    def test_root_with_no_slash_path(self):
        assert normalize_path("/", "users") == "/users"

    def test_prefix_with_slash_path(self):
        assert normalize_path("/api", "/users") == "/api/users"

    def test_prefix_with_no_slash_path(self):
        assert normalize_path("/api", "users") == "/api/users"

    def test_prefix_with_trailing_slash(self):
        assert normalize_path("/api/", "/users") == "/api/users"

    def test_root_to_root(self):
        assert normalize_path("/", "/") == "/"

    def test_prefix_with_param(self):
        assert normalize_path("/users", "/{id}") == "/users/{id}"


class TestBasicRouter:
    """Test basic Router functionality."""

    def test_router_get_route(self):
        router = Router()

        @router.get("/users")
        def get_users():
            return {"users": []}

        routes = router.get_all_routes()
        assert len(routes) == 1
        path, route = routes[0]
        assert path == "/users"
        assert route.method == HTTPMethod.GET

    def test_router_multiple_methods(self):
        router = Router()

        @router.get("/users")
        def get_users():
            return {"users": []}

        @router.post("/users")
        def create_user():
            return {"created": True}

        routes = router.get_all_routes()
        assert len(routes) == 2

    def test_router_with_path_params(self):
        router = Router()

        @router.get("/{id}")
        def get_user(id):
            return {"id": id}

        routes = router.get_all_routes()
        assert len(routes) == 1
        path, route = routes[0]
        assert path == "/{id}"


class TestRouterMounting:
    """Test router mounting functionality."""

    def test_mount_router_with_prefix(self):
        users_router = Router()

        @users_router.get("/")
        def list_users():
            return {"users": []}

        @users_router.get("/{id}")
        def get_user(id):
            return {"user": id}

        main_router = Router()
        main_router.mount("/users", users_router)

        routes = main_router.get_all_routes()
        assert len(routes) == 2

        paths = [path for path, _ in routes]
        assert "/users/" in paths
        assert "/users/{id}" in paths

    def test_nested_router_mounting(self):
        comments_router = Router()

        @comments_router.get("/")
        def list_comments():
            return {"comments": []}

        posts_router = Router()

        @posts_router.get("/")
        def list_posts():
            return {"posts": []}

        posts_router.mount("/{post_id}/comments", comments_router)

        main_router = Router()
        main_router.mount("/posts", posts_router)

        routes = main_router.get_all_routes()
        paths = [path for path, _ in routes]

        assert "/posts/" in paths
        assert "/posts/{post_id}/comments/" in paths

    def test_mount_avoids_double_slashes(self):
        router = Router()

        @router.get("/")
        def handler():
            return {}

        main_router = Router()
        main_router.mount("/", router)

        routes = main_router.get_all_routes()
        paths = [path for path, _ in routes]

        # Should be "/", not "//"
        assert "/" in paths
        assert "//" not in paths


class TestAppMounting:
    """Test mounting routers on the application."""

    def test_app_mount_basic(self):
        app = RestApplication()
        users_router = Router()

        @users_router.get("/")
        def list_users():
            return {"users": ["alice", "bob"]}

        app.mount("/users", users_router)

        request = Request(
            method=HTTPMethod.GET,
            path="/users/",
            headers={},
            body=None,
            query_params=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "alice" in response.body

    def test_app_mount_with_path_params(self):
        app = RestApplication()
        users_router = Router()

        @users_router.get("/{id}")
        def get_user(id):
            return {"user_id": id}

        app.mount("/users", users_router)

        request = Request(
            method=HTTPMethod.GET,
            path="/users/123",
            headers={},
            body=None,
            query_params=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "123" in response.body

    def test_app_mount_multiple_routers(self):
        app = RestApplication()

        users_router = Router()

        @users_router.get("/")
        def list_users():
            return {"resource": "users"}

        posts_router = Router()

        @posts_router.get("/")
        def list_posts():
            return {"resource": "posts"}

        app.mount("/users", users_router)
        app.mount("/posts", posts_router)

        # Test users
        request = Request(
            method=HTTPMethod.GET,
            path="/users/",
            headers={},
            body=None,
            query_params=None
        )
        response = app.execute(request)
        assert response.status_code == 200
        assert "users" in response.body

        # Test posts
        request = Request(
            method=HTTPMethod.GET,
            path="/posts/",
            headers={},
            body=None,
            query_params=None
        )
        response = app.execute(request)
        assert response.status_code == 200
        assert "posts" in response.body

    def test_app_with_root_routes_and_mounted_routers(self):
        """Test that routes on the app coexist with mounted routers."""
        app = RestApplication()

        # Root route on the app
        @app.get("/")
        def root():
            return {"message": "root"}

        # Mounted router
        users_router = Router()

        @users_router.get("/")
        def list_users():
            return {"resource": "users"}

        app.mount("/users", users_router)

        # Test root route
        request = Request(
            method=HTTPMethod.GET,
            path="/",
            headers={},
            body=None,
            query_params=None
        )
        response = app.execute(request)
        assert response.status_code == 200
        assert "root" in response.body

        # Test mounted route
        request = Request(
            method=HTTPMethod.GET,
            path="/users/",
            headers={},
            body=None,
            query_params=None
        )
        response = app.execute(request)
        assert response.status_code == 200
        assert "users" in response.body


class TestNestedMounting:
    """Test nested router mounting."""

    def test_deeply_nested_routers(self):
        app = RestApplication()

        # Level 3: Comments
        comments_router = Router()

        @comments_router.get("/")
        def list_comments():
            return {"resource": "comments"}

        # Level 2: Posts
        posts_router = Router()

        @posts_router.get("/")
        def list_posts():
            return {"resource": "posts"}

        posts_router.mount("/{post_id}/comments", comments_router)

        # Level 1: Users
        users_router = Router()

        @users_router.get("/")
        def list_users():
            return {"resource": "users"}

        users_router.mount("/{user_id}/posts", posts_router)

        # Mount on app
        app.mount("/api/users", users_router)

        # Test deeply nested route: /api/users/123/posts/456/comments/
        request = Request(
            method=HTTPMethod.GET,
            path="/api/users/123/posts/456/comments/",
            headers={},
            body=None,
            query_params=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "comments" in response.body


class TestWildcardRouting:
    """Test wildcard routing with ** and *name patterns."""

    def test_double_star_wildcard_basic(self):
        """Test ** wildcard captures remaining path segments."""
        app = RestApplication()

        @app.get("/files/**")
        def get_file(path):
            return {"path": path}

        request = Request(
            method=HTTPMethod.GET,
            path="/files/docs/guide/intro.md",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "docs/guide/intro.md" in response.body

    def test_named_wildcard_basic(self):
        """Test *name wildcard with custom parameter name."""
        app = RestApplication()

        @app.get("/static/*filepath")
        def serve_static(filepath):
            return {"file": filepath}

        request = Request(
            method=HTTPMethod.GET,
            path="/static/css/style.css",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "css/style.css" in response.body

    def test_wildcard_empty_path(self):
        """Test wildcard matching empty remaining path."""
        app = RestApplication()

        @app.get("/api/**")
        def catch_all(path):
            return {"remaining": path}

        request = Request(
            method=HTTPMethod.GET,
            path="/api/",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        # Empty path should return empty string
        import json
        data = json.loads(response.body)
        assert data["remaining"] == ""

    def test_wildcard_must_be_last_segment(self):
        """Test that wildcard must be the last segment in route."""
        import pytest
        app = RestApplication()

        # This should raise ValueError because wildcard is not last
        with pytest.raises(ValueError, match="must be the last segment"):
            @app.get("/files/**/other")
            def invalid_route(path):
                return {"path": path}

    def test_wildcard_matches_nested_paths(self):
        """Test wildcard matches deeply nested paths."""
        app = RestApplication()

        @app.get("/download/**")
        def download(path):
            return {"download": path}

        request = Request(
            method=HTTPMethod.GET,
            path="/download/2024/01/15/archive.zip",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "2024/01/15/archive.zip" in response.body


class TestRouteMatchingEdgeCases:
    """Test edge cases in route matching logic."""

    def test_route_priority_static_over_param(self):
        """Test that static routes take priority over param routes."""
        app = RestApplication()

        @app.get("/users/me")
        def get_current_user():
            return {"user": "current"}

        @app.get("/users/{id}")
        def get_user(id):
            return {"user": id}

        # Static route should match first
        request = Request(
            method=HTTPMethod.GET,
            path="/users/me",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "current" in response.body

    def test_route_priority_param_over_wildcard(self):
        """Test that param routes take priority over wildcard routes."""
        app = RestApplication()

        @app.get("/api/{resource}")
        def get_resource(resource):
            return {"resource": resource}

        @app.get("/api/**")
        def catch_all(path):
            return {"wildcard": path}

        # Param route should match first
        request = Request(
            method=HTTPMethod.GET,
            path="/api/users",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "users" in response.body
        assert "wildcard" not in response.body

    def test_has_path_with_handlers(self):
        """Test path existence check with handlers."""
        from restmachine.router import RouteNode

        node = RouteNode()
        node.handlers[HTTPMethod.GET] = lambda: {"ok": True}

        # Should return True when handlers exist
        assert node.has_path([]) is True

    def test_has_path_with_wildcard_empty(self):
        """Test path existence check with wildcard for empty path."""
        from restmachine.router import RouteNode

        node = RouteNode()
        child = RouteNode()
        child.handlers[HTTPMethod.GET] = lambda: {"ok": True}
        node.wildcard_child = ("path", child)

        # Should match wildcard even with empty path
        assert node.has_path([]) is True

    def test_has_path_static_match(self):
        """Test path existence with static child."""
        from restmachine.router import RouteNode

        node = RouteNode()
        child = RouteNode()
        child.handlers[HTTPMethod.GET] = lambda: {"ok": True}
        node.static_children["users"] = child

        # Should find path through static children
        assert node.has_path(["users"]) is True

    def test_has_path_param_match(self):
        """Test path existence with param child."""
        from restmachine.router import RouteNode

        node = RouteNode()
        child = RouteNode()
        child.handlers[HTTPMethod.GET] = lambda: {"ok": True}
        node.param_child = ("id", child)

        # Should find path through param child
        assert node.has_path(["123"]) is True

    def test_has_path_wildcard_match(self):
        """Test path existence with wildcard child."""
        from restmachine.router import RouteNode

        node = RouteNode()
        child = RouteNode()
        child.handlers[HTTPMethod.GET] = lambda: {"ok": True}
        node.wildcard_child = ("path", child)

        # Should find path through wildcard
        assert node.has_path(["any", "path", "here"]) is True


class TestRouterPrefixHandling:
    """Test router prefix normalization edge cases."""

    def test_mount_with_empty_prefix(self):
        """Test mounting router with empty/root prefix."""
        app = RestApplication()
        router = Router()

        @router.get("/test")
        def handler():
            return {"ok": True}

        # Mount at root
        app.mount("", router)

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_mount_with_slash_only_prefix(self):
        """Test mounting router with '/' prefix."""
        app = RestApplication()
        router = Router()

        @router.get("/test")
        def handler():
            return {"ok": True}

        # Mount at /
        app.mount("/", router)

        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_route_with_trailing_slash(self):
        """Test routes with trailing slashes."""
        app = RestApplication()

        @app.get("/users/")
        def handler():
            return {"ok": True}

        request = Request(
            method=HTTPMethod.GET,
            path="/users/",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200


class TestStandaloneRouterDecorators:
    """Test Router decorators on standalone routers (before mounting)."""

    def test_router_dependency_decorator(self):
        """Test @router.dependency() on standalone router."""
        router = Router()

        @router.dependency
        def custom_dep():
            return {"data": "from_router"}

        @router.get("/test")
        def handler(custom_dep):
            return custom_dep

        # Router should store dependency locally before mounting
        assert "custom_dep" in router._dependencies

        # Now mount and test
        app = RestApplication()
        app.mount("/api", router)

        request = Request(
            method=HTTPMethod.GET,
            path="/api/test",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200
        assert "from_router" in response.body

    def test_router_dependency_with_name(self):
        """Test @router.dependency(name=...) on standalone router."""
        router = Router()

        @router.dependency(name="my_service")
        def service_factory():
            return {"service": "data"}

        @router.get("/test")
        def handler(my_service):
            return my_service

        # Should use custom name
        assert "my_service" in router._dependencies

        app = RestApplication()
        app.mount("/api", router)

        request = Request(
            method=HTTPMethod.GET,
            path="/api/test",
            headers={},
            body=None
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_router_validates_decorator(self):
        """Test @router.validates() on standalone router."""
        try:
            from pydantic import BaseModel
            PYDANTIC_AVAILABLE = True

            class TestModel(BaseModel):
                value: int

        except ImportError:
            PYDANTIC_AVAILABLE = False
            return

        if not PYDANTIC_AVAILABLE:
            return

        router = Router()

        @router.validates
        def validate_data(json_body) -> TestModel:
            return TestModel.model_validate(json_body)

        @router.post("/test")
        def handler(validate_data):
            return {"validated": validate_data.value}

        # Router should store validation dependency locally
        assert "validate_data" in router._validation_dependencies

        app = RestApplication()
        app.mount("/api", router)

        from io import BytesIO
        request = Request(
            method=HTTPMethod.POST,
            path="/api/test",
            headers={"content-type": "application/json"},
            body=BytesIO(b'{"value": 42}')
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_router_accepts_decorator(self):
        """Test @router.accepts() on standalone router."""
        router = Router()

        @router.accepts("application/x-custom")
        def parse_custom(body_stream):
            return {"custom": body_stream.read().decode('utf-8')}

        # Router should store accepts dependency locally before mounting
        assert "application/x-custom" in router._accepts_dependencies
        assert "parse_custom" in router._dependencies

        # Verify decorator returns the original function
        assert parse_custom is not None
        assert callable(parse_custom)

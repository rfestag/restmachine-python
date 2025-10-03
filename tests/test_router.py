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

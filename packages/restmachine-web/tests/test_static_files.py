"""
Tests for static file serving functionality.
"""

import pytest
from pathlib import Path
from restmachine import RestApplication
from restmachine.testing import MultiDriverTestBase
from restmachine_web import StaticRouter


class TestStaticRouterInitialization:
    """Test StaticRouter initialization and configuration."""

    def test_init_with_valid_directory(self, tmp_path):
        """Test initialization with a valid directory."""
        static = StaticRouter(serve=str(tmp_path))
        assert static.directory == tmp_path.resolve()
        assert static.index_file == "index.html"

    def test_init_with_custom_index_file(self, tmp_path):
        """Test initialization with a custom index file name."""
        static = StaticRouter(serve=str(tmp_path), index_file="main.html")
        assert static.index_file == "main.html"

    def test_init_with_nonexistent_directory(self):
        """Test initialization with a directory that doesn't exist."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            StaticRouter(serve="/nonexistent/path/to/directory")

    def test_init_with_file_instead_of_directory(self, tmp_path):
        """Test initialization with a file path instead of directory."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test")
        with pytest.raises(ValueError, match="Path is not a directory"):
            StaticRouter(serve=str(file_path))


class TestStaticFilesServing(MultiDriverTestBase):
    """Test serving static files from a directory."""

    @pytest.fixture(scope="class")
    def static_dir(self, tmp_path_factory):
        """Create a temporary directory with test files."""
        tmp_path = tmp_path_factory.mktemp("static")
        # Create some test files
        (tmp_path / "test.txt").write_text("Hello, World!")
        (tmp_path / "test.html").write_text("<html><body>Test</body></html>")
        (tmp_path / "styles.css").write_text("body { color: red; }")

        # Create a subdirectory with files
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested file")
        (subdir / "index.html").write_text("<html><body>Subdir Index</body></html>")

        # Create a directory without an index file
        noindex = tmp_path / "noindex"
        noindex.mkdir()
        (noindex / "file.txt").write_text("File in directory")

        # Create root index
        (tmp_path / "index.html").write_text("<html><body>Root Index</body></html>")

        return tmp_path

    def create_app(self, static_dir) -> RestApplication:
        """Create a RestMachine app with static files mounted."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(static_dir))
        app.mount("/static", static_router)
        return app

    # Override api fixture to inject static_dir
    @pytest.fixture(scope="class")
    def api(self, request, static_dir):
        """Override api fixture to create app with static_dir."""
        driver_name = request.param
        app = self.create_app(static_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_serve_text_file(self, api):
        """Test serving a plain text file."""
        api_client, driver_name = api

        request = api_client.get("/static/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Hello, World!"
        assert "text/plain" in response.content_type

    def test_serve_html_file(self, api):
        """Test serving an HTML file."""
        api_client, driver_name = api

        request = api_client.get("/static/test.html")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "<html>" in response.body
        assert "text/html" in response.content_type

    def test_serve_css_file(self, api):
        """Test serving a CSS file."""
        api_client, driver_name = api

        request = api_client.get("/static/styles.css")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "color: red" in response.body
        assert "text/css" in response.content_type

    def test_serve_nested_file(self, api):
        """Test serving a file from a subdirectory."""
        api_client, driver_name = api

        request = api_client.get("/static/subdir/nested.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Nested file"

    def test_serve_directory_with_index(self, api):
        """Test serving a directory that has an index.html file."""
        api_client, driver_name = api

        request = api_client.get("/static/subdir/")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Subdir Index" in response.body
        assert "text/html" in response.content_type

    def test_serve_root_index(self, api):
        """Test serving the root index.html when accessing root path."""
        api_client, driver_name = api

        request = api_client.get("/static/")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Root Index" in response.body

    def test_directory_without_index_returns_404(self, api):
        """Test that a directory without an index file returns 404."""
        api_client, driver_name = api

        request = api_client.get("/static/noindex/")
        response = api_client.execute(request)

        assert response.status_code == 404

    def test_nonexistent_file_returns_404(self, api):
        """Test that requesting a nonexistent file returns 404."""
        api_client, driver_name = api

        request = api_client.get("/static/does-not-exist.txt")
        response = api_client.execute(request)

        assert response.status_code == 404


class TestStaticFilesSecurity(MultiDriverTestBase):
    """Test security features like path traversal protection."""

    @pytest.fixture(scope="class")
    def secure_dir(self, tmp_path_factory):
        """Create temp directory with static files and a sensitive file outside."""
        tmp_path = tmp_path_factory.mktemp("secure")
        # Create static directory
        static_dir = tmp_path / "public"
        static_dir.mkdir()
        (static_dir / "safe.txt").write_text("Safe content")

        # Create a sensitive file outside the static directory
        (tmp_path / "secret.txt").write_text("Secret content")

        return static_dir, tmp_path

    def create_app(self, secure_dir) -> RestApplication:
        """Create app with static files mounted."""
        static_dir, _ = secure_dir
        app = RestApplication()
        static_router = StaticRouter(serve=str(static_dir))
        app.mount("/static", static_router)
        return app

    # Override api fixture to inject secure_dir
    @pytest.fixture(scope="class")
    def api(self, request, secure_dir):
        """Override api fixture to create app with secure_dir."""
        driver_name = request.param
        app = self.create_app(secure_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_path_traversal_attack_parent_directory(self, api):
        """Test that path traversal using ../ is blocked."""
        api_client, driver_name = api

        request = api_client.get("/static/../secret.txt")
        response = api_client.execute(request)

        assert response.status_code == 404

    def test_path_traversal_attack_multiple_parent(self, api):
        """Test that multiple ../ path traversal attempts are blocked."""
        api_client, driver_name = api

        request = api_client.get("/static/../../secret.txt")
        response = api_client.execute(request)

        assert response.status_code == 404

    def test_path_traversal_attack_encoded(self, api):
        """Test that URL-encoded path traversal is blocked."""
        api_client, driver_name = api

        # %2e%2e%2f is URL-encoded ../
        request = api_client.get("/static/%2e%2e%2fsecret.txt")
        response = api_client.execute(request)

        assert response.status_code == 404

    def test_safe_file_is_accessible(self, api):
        """Test that legitimate files within the directory are accessible."""
        api_client, driver_name = api

        request = api_client.get("/static/safe.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Safe content"


class TestStaticFilesMounting(MultiDriverTestBase):
    """Test mounting static files at different paths."""

    @pytest.fixture(scope="class")
    def mount_dir(self, tmp_path_factory):
        """Create temporary directory with test file."""
        tmp_path = tmp_path_factory.mktemp("mount")
        (tmp_path / "test.txt").write_text("Test content")
        return tmp_path

    def create_app(self, mount_dir, path="/assets") -> RestApplication:
        """Create app with custom mount path."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(mount_dir))
        app.mount(path, static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, mount_dir):
        """Override api fixture for custom path tests."""
        driver_name = request.param
        app = self.create_app(mount_dir, path="/assets")
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_mount_at_custom_path(self, api):
        """Test mounting static files at a custom path."""
        api_client, driver_name = api

        request = api_client.get("/assets/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Test content"

    def test_router_is_mountable(self, mount_dir):
        """Test that StaticRouter can be mounted to an app."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(mount_dir))
        # This should not raise an exception
        app.mount("/static", static_router)
        # Verify routes were registered
        assert len(static_router._routes) > 0


class TestStaticFilesMountingAtRoot(MultiDriverTestBase):
    """Test mounting at root path - separate class for different fixture."""

    @pytest.fixture(scope="class")
    def root_dir(self, tmp_path_factory):
        """Create temporary directory for root mount test."""
        tmp_path = tmp_path_factory.mktemp("root")
        (tmp_path / "test.txt").write_text("Root content")
        return tmp_path

    def create_app(self, root_dir) -> RestApplication:
        """Create app mounted at root."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(root_dir))
        app.mount("/", static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, root_dir):
        """Override api fixture for root mount."""
        driver_name = request.param
        app = self.create_app(root_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_mount_at_root(self, api):
        """Test mounting static files at the root path."""
        api_client, driver_name = api

        request = api_client.get("/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Root content"


class TestStaticFilesMountingWithTrailingSlash(MultiDriverTestBase):
    """Test mounting with trailing slash - separate class for different fixture."""

    @pytest.fixture(scope="class")
    def slash_dir(self, tmp_path_factory):
        """Create temporary directory for trailing slash test."""
        tmp_path = tmp_path_factory.mktemp("slash")
        (tmp_path / "test.txt").write_text("Test content")
        return tmp_path

    def create_app(self, slash_dir) -> RestApplication:
        """Create app with trailing slash mount."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(slash_dir))
        app.mount("/static/", static_router)  # Note the trailing slash
        return app

    @pytest.fixture(scope="class")
    def api(self, request, slash_dir):
        """Override api fixture for trailing slash mount."""
        driver_name = request.param
        app = self.create_app(slash_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_mount_with_trailing_slash(self, api):
        """Test that mounting with a trailing slash works correctly."""
        api_client, driver_name = api

        request = api_client.get("/static/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert response.body == "Test content"


class TestStaticFilesCustomIndexFile(MultiDriverTestBase):
    """Test custom index file configuration."""

    @pytest.fixture(scope="class")
    def custom_index_dir(self, tmp_path_factory):
        """Create directory with custom index file."""
        tmp_path = tmp_path_factory.mktemp("custom_index")
        (tmp_path / "main.html").write_text("<html><body>Main Page</body></html>")
        return tmp_path

    def create_app(self, custom_index_dir) -> RestApplication:
        """Create app with custom index file."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(custom_index_dir), index_file="main.html")
        app.mount("/static", static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, custom_index_dir):
        """Override api fixture for custom index."""
        driver_name = request.param
        app = self.create_app(custom_index_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_custom_index_file(self, api):
        """Test serving a custom index file name."""
        api_client, driver_name = api

        request = api_client.get("/static/")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Main Page" in response.body


class TestStaticFilesMethodNotAllowed(MultiDriverTestBase):
    """Test that non-GET methods return 405 Method Not Allowed."""

    @pytest.fixture(scope="class")
    def method_dir(self, tmp_path_factory):
        """Create directory with test file."""
        tmp_path = tmp_path_factory.mktemp("method_test")
        (tmp_path / "test.txt").write_text("Test content")
        return tmp_path

    def create_app(self, method_dir) -> RestApplication:
        """Create app with static router."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(method_dir))
        app.mount("/static", static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, method_dir):
        """Override api fixture."""
        driver_name = request.param
        app = self.create_app(method_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_post_returns_405(self, api):
        """Test that POST requests return 405."""
        api_client, driver_name = api

        request = api_client.post("/static/test.txt").with_json_body({"data": "test"})
        response = api_client.execute(request)

        assert response.status_code == 405

    def test_put_returns_405(self, api):
        """Test that PUT requests return 405."""
        api_client, driver_name = api

        request = api_client.put("/static/test.txt").with_json_body({"data": "test"})
        response = api_client.execute(request)

        assert response.status_code == 405

    def test_delete_returns_405(self, api):
        """Test that DELETE requests return 405."""
        api_client, driver_name = api

        request = api_client.delete("/static/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 405


class TestStaticFilesCustomIndexNotFound(MultiDriverTestBase):
    """Test custom index file when not present."""

    @pytest.fixture(scope="class")
    def wrong_index_dir(self, tmp_path_factory):
        """Create directory with wrong index file."""
        tmp_path = tmp_path_factory.mktemp("wrong_index")
        # Directory has index.html but we're looking for main.html
        (tmp_path / "index.html").write_text("<html><body>Index</body></html>")
        return tmp_path

    def create_app(self, wrong_index_dir) -> RestApplication:
        """Create app looking for non-existent custom index."""
        app = RestApplication()
        static_router = StaticRouter(serve=str(wrong_index_dir), index_file="main.html")
        app.mount("/static", static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, wrong_index_dir):
        """Override api fixture for wrong index."""
        driver_name = request.param
        app = self.create_app(wrong_index_dir)
        driver = self.create_driver(driver_name, app)
        from restmachine.testing import RestApiDsl
        yield RestApiDsl(driver), driver_name

    def test_custom_index_not_found(self, api):
        """Test that missing custom index file returns 404."""
        api_client, driver_name = api

        request = api_client.get("/static/")
        response = api_client.execute(request)

        assert response.status_code == 404

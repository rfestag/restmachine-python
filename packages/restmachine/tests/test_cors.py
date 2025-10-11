"""
Tests for CORS (Cross-Origin Resource Sharing) functionality.

RFC 9110 Section 10.2.1: Allow header
https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.1

CORS Specification: https://fetch.spec.whatwg.org/#http-cors-protocol
"""

import pytest
from restmachine import RestApplication, Router, Response
from restmachine.cors import CORSConfig
from tests.framework import MultiDriverTestBase


class TestCORSConfig(MultiDriverTestBase):
    """Test CORSConfig dataclass functionality."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create minimal app for config tests."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"data": "test"}

        return app

    def test_cors_config_matches_specific_origin(self, api):
        """Test CORSConfig matches specific allowed origin."""
        config = CORSConfig(origins=["https://app.example.com"])

        assert config.matches_origin("https://app.example.com") is True
        assert config.matches_origin("https://evil.example.com") is False

    def test_cors_config_matches_wildcard_origin(self, api):
        """Test CORSConfig matches wildcard origin."""
        config = CORSConfig(origins="*")

        assert config.matches_origin("https://app.example.com") is True
        assert config.matches_origin("https://any-domain.com") is True

    def test_cors_config_matches_multiple_origins(self, api):
        """Test CORSConfig matches multiple allowed origins."""
        config = CORSConfig(
            origins=[
                "https://app.example.com",
                "https://admin.example.com",
                "http://localhost:3000"
            ]
        )

        assert config.matches_origin("https://app.example.com") is True
        assert config.matches_origin("https://admin.example.com") is True
        assert config.matches_origin("http://localhost:3000") is True
        assert config.matches_origin("https://evil.com") is False

    def test_cors_config_validates_wildcard_with_credentials(self, api):
        """Test CORSConfig rejects wildcard origin with credentials.

        Security requirement: Cannot use wildcard origin with credentials.
        """
        with pytest.raises(ValueError, match="Cannot use wildcard origin"):
            config = CORSConfig(origins="*", credentials=True)
            config.validate()

    def test_cors_config_allows_specific_origin_with_credentials(self, api):
        """Test CORSConfig allows specific origin with credentials."""
        config = CORSConfig(
            origins=["https://app.example.com"],
            credentials=True
        )
        config.validate()  # Should not raise

    def test_cors_config_default_headers(self, api):
        """Test CORSConfig provides smart defaults for headers."""
        config = CORSConfig(origins="*")

        # Default allow_headers
        assert "Accept" in config.allow_headers
        assert "Content-Type" in config.allow_headers
        assert "Authorization" in config.allow_headers

        # Default expose_headers
        assert "Content-Type" in config.expose_headers
        assert "ETag" in config.expose_headers
        assert "Location" in config.expose_headers


class TestCORSPreflight(MultiDriverTestBase):
    """Test CORS preflight requests (OPTIONS with Origin header)."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with CORS enabled."""
        app = RestApplication()

        # App-level CORS
        app.cors(origins=["https://app.example.com"], credentials=True)

        @app.get("/api/data")
        def get_data():
            return {"data": "value"}

        @app.post("/api/data")
        def post_data(json_body):
            return {"created": True}

        return app

    def test_preflight_response_complete(self, api):
        """Test CORS preflight returns complete response with all required headers.

        CORS spec: Preflight should return 204 with CORS headers.
        RFC 9110 Section 10.2.1: OPTIONS response should include Allow header.
        """
        api_client, driver_name = api

        request = api_client.options("/api/data")
        request = request.with_header("Origin", "https://app.example.com")
        request = request.with_header("Access-Control-Request-Method", "POST")
        response = api_client.execute(request)

        # Status
        assert response.status_code == 204

        # CORS headers
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://app.example.com"

        allow_methods = response.get_header("Access-Control-Allow-Methods")
        assert allow_methods is not None
        assert "GET" in allow_methods
        assert "POST" in allow_methods
        assert "OPTIONS" in allow_methods

        allow_headers = response.get_header("Access-Control-Allow-Headers")
        assert allow_headers is not None
        assert "Content-Type" in allow_headers
        assert "Authorization" in allow_headers

        allow_credentials = response.get_header("Access-Control-Allow-Credentials")
        assert allow_credentials == "true"

        max_age = response.get_header("Access-Control-Max-Age")
        assert max_age is not None
        assert int(max_age) > 0

        # RFC compliance - Allow header
        allow_header = response.get_header("Allow")
        assert allow_header is not None
        assert "GET" in allow_header
        assert "POST" in allow_header
        assert "OPTIONS" in allow_header

    def test_preflight_rejects_disallowed_origin(self, api):
        """Test CORS preflight from disallowed origin doesn't get CORS headers."""
        api_client, driver_name = api

        request = api_client.options("/api/data")
        request = request.with_header("Origin", "https://evil.com")
        request = request.with_header("Access-Control-Request-Method", "POST")
        response = api_client.execute(request)

        # Should not include CORS headers for disallowed origin
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin is None


class TestCORSActualRequests(MultiDriverTestBase):
    """Test CORS on actual requests (non-preflight)."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with CORS enabled."""
        app = RestApplication()

        app.cors(
            origins=["https://app.example.com"],
            credentials=True,
            expose_headers=["X-Request-ID", "X-Total-Count"]
        )

        @app.get("/api/data")
        def get_data():
            return Response(
                status_code=200,
                body={"data": "value"},
                headers={
                    "X-Request-ID": "abc-123",
                    "X-Total-Count": "42"
                }
            )

        @app.post("/api/data")
        def post_data(json_body):
            return {"created": True}

        return app

    def test_actual_request_includes_cors_headers(self, api):
        """Test actual request includes all CORS headers.

        Vary: Origin is required for proper caching of CORS responses.
        """
        api_client, driver_name = api

        request = api_client.get("/api/data")
        request = request.with_header("Origin", "https://app.example.com")
        response = api_client.execute(request)

        assert response.status_code == 200

        # CORS headers
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://app.example.com"

        allow_credentials = response.get_header("Access-Control-Allow-Credentials")
        assert allow_credentials == "true"

        expose_headers = response.get_header("Access-Control-Expose-Headers")
        assert expose_headers is not None
        assert "X-Request-ID" in expose_headers
        assert "X-Total-Count" in expose_headers

        # Vary header for caching
        vary_header = response.get_header("Vary")
        assert vary_header is not None
        assert "Origin" in vary_header

    def test_actual_request_without_origin_no_cors_headers(self, api):
        """Test request without Origin header doesn't get CORS headers."""
        api_client, driver_name = api

        request = api_client.get("/api/data")
        response = api_client.execute(request)

        assert response.status_code == 200
        # No CORS headers without Origin
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin is None

    def test_actual_request_from_disallowed_origin(self, api):
        """Test request from disallowed origin doesn't get CORS headers."""
        api_client, driver_name = api

        request = api_client.get("/api/data")
        request = request.with_header("Origin", "https://evil.com")
        response = api_client.execute(request)

        assert response.status_code == 200
        # No CORS headers for disallowed origin
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin is None


class TestCORSConfigurationHierarchy(MultiDriverTestBase):
    """Test CORS configuration hierarchy (route > router > app)."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with multi-level CORS config."""
        app = RestApplication()

        # App-level CORS (least specific)
        app.cors(origins=["https://app.example.com"])

        # Router with own CORS config
        api_router = Router()
        api_router.cors(origins=["https://api.example.com"])

        @api_router.get("/router-level")
        def router_endpoint():
            return {"source": "router"}

        # Route-level CORS (most specific)
        @api_router.get("/route-level")
        @api_router.cors(origins=["https://route.example.com"])
        def route_endpoint():
            return {"source": "route"}

        app.mount("/api", api_router)

        # App-level route (uses app CORS)
        @app.get("/app-level")
        def app_endpoint():
            return {"source": "app"}

        return app

    def test_app_level_cors_applied(self, api):
        """Test app-level CORS config is applied to routes."""
        api_client, driver_name = api

        request = api_client.options("/app-level")
        request = request.with_header("Origin", "https://app.example.com")
        request = request.with_header("Access-Control-Request-Method", "GET")
        response = api_client.execute(request)

        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://app.example.com"

    def test_router_level_cors_overrides_app(self, api):
        """Test router-level CORS config overrides app-level."""
        api_client, driver_name = api

        # Router origin should work
        request = api_client.options("/api/router-level")
        request = request.with_header("Origin", "https://api.example.com")
        request = request.with_header("Access-Control-Request-Method", "GET")
        response = api_client.execute(request)

        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://api.example.com"

        # App origin should not work (router overrides)
        request = api_client.options("/api/router-level")
        request = request.with_header("Origin", "https://app.example.com")
        request = request.with_header("Access-Control-Request-Method", "GET")
        response = api_client.execute(request)

        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin is None

    def test_route_level_cors_overrides_router_and_app(self, api):
        """Test route-level CORS config overrides router and app-level."""
        api_client, driver_name = api

        # Route origin should work
        request = api_client.options("/api/route-level")
        request = request.with_header("Origin", "https://route.example.com")
        request = request.with_header("Access-Control-Request-Method", "GET")
        response = api_client.execute(request)

        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://route.example.com"

        # Router origin should not work (route overrides)
        request = api_client.options("/api/route-level")
        request = request.with_header("Origin", "https://api.example.com")
        request = request.with_header("Access-Control-Request-Method", "GET")
        response = api_client.execute(request)

        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin is None


class TestCORSWithWildcardOrigin(MultiDriverTestBase):
    """Test CORS with wildcard origin."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with wildcard CORS (no credentials)."""
        app = RestApplication()

        # Wildcard origin (public API)
        app.cors(origins="*", credentials=False)

        @app.get("/public/data")
        def get_public_data():
            return {"public": "data"}

        return app

    def test_wildcard_allows_any_origin(self, api):
        """Test wildcard origin allows any origin."""
        api_client, driver_name = api

        # Test multiple different origins
        origins = [
            "https://app.example.com",
            "https://another-domain.com",
            "http://localhost:3000"
        ]

        for origin in origins:
            request = api_client.get("/public/data")
            request = request.with_header("Origin", origin)
            response = api_client.execute(request)

            allow_origin = response.get_header("Access-Control-Allow-Origin")
            assert allow_origin == origin

    def test_wildcard_no_credentials(self, api):
        """Test wildcard origin doesn't include credentials."""
        api_client, driver_name = api

        request = api_client.get("/public/data")
        request = request.with_header("Origin", "https://app.example.com")
        response = api_client.execute(request)

        allow_credentials = response.get_header("Access-Control-Allow-Credentials")
        assert allow_credentials is None or allow_credentials != "true"


class TestCORSOriginReflection(MultiDriverTestBase):
    """Test CORS with origin reflection for credentials support."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with origin reflection enabled."""
        app = RestApplication()

        # Reflect any origin (useful for development with credentials)
        app.cors(origins="*", credentials=True, reflect_any_origin=True)

        @app.get("/api/data")
        def get_data():
            return {"data": "value"}

        @app.post("/api/data")
        def post_data():
            return {"created": True}

        return app

    def test_reflect_any_origin_with_credentials(self, api):
        """Test that reflect_any_origin allows any origin with credentials."""
        api_client, driver_name = api

        # Test multiple different origins
        origins = [
            "https://app.example.com",
            "https://another-domain.com",
            "http://localhost:3000"
        ]

        for origin in origins:
            request = api_client.get("/api/data")
            request = request.with_header("Origin", origin)
            response = api_client.execute(request)

            # Should reflect the exact origin from request
            allow_origin = response.get_header("Access-Control-Allow-Origin")
            assert allow_origin == origin

            # Should include credentials header
            allow_credentials = response.get_header("Access-Control-Allow-Credentials")
            assert allow_credentials == "true"

    def test_reflect_origin_in_preflight(self, api):
        """Test that origin reflection works in preflight requests."""
        api_client, driver_name = api

        request = api_client.options("/api/data")
        request = request.with_header("Origin", "https://dev.example.com")
        request = request.with_header("Access-Control-Request-Method", "POST")
        response = api_client.execute(request)

        assert response.status_code == 204

        # Should reflect the exact origin from request
        allow_origin = response.get_header("Access-Control-Allow-Origin")
        assert allow_origin == "https://dev.example.com"

        # Should include credentials header
        allow_credentials = response.get_header("Access-Control-Allow-Credentials")
        assert allow_credentials == "true"

    def test_reflect_origin_validation(self, api):
        """Test that wildcard with credentials requires reflect_any_origin flag."""
        app = RestApplication()

        # This should raise validation error (wildcard + credentials without flag)
        with pytest.raises(ValueError, match="Cannot use wildcard origin"):
            app.cors(origins="*", credentials=True, reflect_any_origin=False)


class TestCORSMethodAutoDetection(MultiDriverTestBase):
    """Test automatic detection of allowed methods from routes."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with multiple HTTP methods."""
        app = RestApplication()

        app.cors(origins=["https://app.example.com"])

        @app.get("/resource")
        def get_resource():
            return {"data": "value"}

        @app.post("/resource")
        def post_resource(json_body):
            return {"created": True}

        @app.put("/resource")
        def put_resource(json_body):
            return {"updated": True}

        @app.delete("/resource")
        def delete_resource():
            return None

        return app

    def test_auto_detects_methods_in_cors_and_allow_headers(self, api):
        """Test CORS auto-detects methods in both CORS and Allow headers (RFC compliance)."""
        api_client, driver_name = api

        request = api_client.options("/resource")
        request = request.with_header("Origin", "https://app.example.com")
        request = request.with_header("Access-Control-Request-Method", "POST")
        response = api_client.execute(request)

        # Check CORS methods header
        allow_methods = response.get_header("Access-Control-Allow-Methods")
        assert allow_methods is not None
        for method in ["GET", "POST", "PUT", "DELETE", "OPTIONS"]:
            assert method in allow_methods

        # Check RFC Allow header
        allow_header = response.get_header("Allow")
        assert allow_header is not None
        for method in ["GET", "POST", "PUT", "DELETE"]:
            assert method in allow_header


class TestCORSMethodOverride(MultiDriverTestBase):
    """Test manual override of allowed methods in CORS."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with manual method override."""
        app = RestApplication()

        @app.get("/admin/resource")
        @app.post("/admin/resource")
        @app.delete("/admin/resource")
        @app.cors(
            origins=["https://admin.example.com"],
            methods=["GET", "POST"]  # Don't expose DELETE via CORS
        )
        def admin_resource():
            return {"admin": "data"}

        return app

    def test_manual_methods_override_auto_detection(self, api):
        """Test manually specified methods override auto-detection."""
        api_client, driver_name = api

        request = api_client.options("/admin/resource")
        request = request.with_header("Origin", "https://admin.example.com")
        request = request.with_header("Access-Control-Request-Method", "POST")
        response = api_client.execute(request)

        allow_methods = response.get_header("Access-Control-Allow-Methods")
        assert allow_methods is not None
        assert "GET" in allow_methods
        assert "POST" in allow_methods
        # DELETE should not be exposed via CORS
        assert "DELETE" not in allow_methods


class TestCORSAppConfigurationAPI(MultiDriverTestBase):
    """Test app.cors() configuration API."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """This test creates apps dynamically."""
        app = RestApplication()

        @app.get("/test")
        def test_endpoint():
            return {"test": "data"}

        return app

    def test_cors_requires_origins_parameter(self, api):
        """Test cors() raises error without origins parameter."""
        app = RestApplication()

        with pytest.raises(ValueError, match="origins parameter is required"):
            app.cors()

    @pytest.mark.parametrize("origins,expected", [
        ("https://app.example.com", ["https://app.example.com"]),
        (["https://app.example.com", "https://admin.example.com"],
         ["https://app.example.com", "https://admin.example.com"]),
        ("*", "*"),
    ])
    def test_cors_accepts_various_origin_formats(self, api, origins, expected):
        """Test cors() accepts different origin input formats."""
        app = RestApplication()
        app.cors(origins=origins)

        assert app._cors_config is not None
        assert app._cors_config.origins == expected

    def test_cors_as_decorator(self, api):
        """Test cors() can be used as route decorator."""
        app = RestApplication()

        @app.get("/endpoint")
        @app.cors(origins=["https://specific.example.com"])
        def endpoint():
            return {"data": "value"}

        # Route should have cors config
        route = app._root_router._routes[-1]
        assert route.cors_config is not None
        assert route.cors_config.origins == ["https://specific.example.com"]

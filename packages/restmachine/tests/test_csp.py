"""Tests for Content Security Policy (CSP) support."""

import pytest
from restmachine import RestApplication, Router, Response
from restmachine.csp import CSPConfig, CSPPreset
from restmachine.testing import MultiDriverTestBase


class TestCSPConfig(MultiDriverTestBase):
    """Test CSPConfig dataclass functionality."""

    ENABLED_DRIVERS = ['direct']

    def test_auto_quote_keywords(self, api):
        """Test that CSP keywords are auto-quoted."""
        config = CSPConfig(default_src=["self"])
        header = config.build_header()
        assert header == "default-src 'self'"

    def test_auto_quote_multiple_keywords(self, api):
        """Test multiple keywords are quoted correctly."""
        config = CSPConfig(
            script_src=["self", "unsafe-inline", "unsafe-eval"]
        )
        header = config.build_header()
        assert header == "script-src 'self' 'unsafe-inline' 'unsafe-eval'"

    def test_urls_not_quoted(self, api):
        """Test that URLs are not quoted."""
        config = CSPConfig(
            script_src=["self", "https://cdn.jsdelivr.net", "https://code.jquery.com"]
        )
        header = config.build_header()
        assert header == "script-src 'self' https://cdn.jsdelivr.net https://code.jquery.com"

    def test_wildcards_not_quoted(self, api):
        """Test that wildcards and domains are not quoted."""
        config = CSPConfig(
            img_src=["self", "*.example.com", "data:"]
        )
        header = config.build_header()
        assert header == "img-src 'self' *.example.com data:"

    def test_already_quoted_preserved(self, api):
        """Test that already-quoted values are preserved."""
        config = CSPConfig(
            script_src=["'self'", "'unsafe-inline'"]
        )
        header = config.build_header()
        assert header == "script-src 'self' 'unsafe-inline'"

    def test_nonce_auto_generated(self, api):
        """Test that nonce is auto-generated and quoted."""
        config = CSPConfig(
            script_src=["self"],
            nonce=True
        )
        header = config.build_header(nonce_value="abc123xyz")
        assert header == "script-src 'self' 'nonce-abc123xyz'"

    def test_nonce_only_on_script_and_style(self, api):
        """Test that nonce only applies to script-src and style-src."""
        config = CSPConfig(
            script_src=["self"],
            style_src=["self"],
            img_src=["self"],
            nonce=True
        )
        header = config.build_header(nonce_value="xyz789")
        assert "script-src 'self' 'nonce-xyz789'" in header
        assert "style-src 'self' 'nonce-xyz789'" in header
        assert "img-src 'self'" in header
        assert "'nonce-xyz789'" not in header.split("img-src")[1].split(";")[0]

    def test_report_only_header_name(self, api):
        """Test report-only mode uses correct header."""
        config = CSPConfig(default_src=["self"], report_only=True)
        assert config.header_name() == "Content-Security-Policy-Report-Only"

    def test_enforce_header_name(self, api):
        """Test enforce mode uses correct header."""
        config = CSPConfig(default_src=["self"], report_only=False)
        assert config.header_name() == "Content-Security-Policy"

    def test_multiple_directives(self, api):
        """Test multiple CSP directives."""
        config = CSPConfig(
            default_src=["self"],
            script_src=["self", "https://cdn.com"],
            style_src=["self", "unsafe-inline"],
            img_src=["self", "data:"],
            font_src=["self", "https://fonts.gstatic.com"]
        )
        header = config.build_header()

        assert "default-src 'self'" in header
        assert "script-src 'self' https://cdn.com" in header
        assert "style-src 'self' 'unsafe-inline'" in header
        assert "img-src 'self' data:" in header
        assert "font-src 'self' https://fonts.gstatic.com" in header


class TestCSPPresets(MultiDriverTestBase):
    """Test CSP preset configurations."""

    ENABLED_DRIVERS = ['direct']

    def test_strict_preset(self, api):
        """Test strict CSP preset."""
        config = CSPPreset.STRICT
        header = config.build_header()

        assert "default-src 'self'" in header
        assert "object-src 'none'" in header
        assert "base-uri 'self'" in header

    def test_basic_preset(self, api):
        """Test basic CSP preset."""
        config = CSPPreset.BASIC
        header = config.build_header()

        assert "default-src 'self'" in header

    def test_relaxed_preset(self, api):
        """Test relaxed CSP preset."""
        config = CSPPreset.RELAXED
        header = config.build_header()

        assert "default-src 'self'" in header
        assert "'unsafe-inline'" in header


class TestCSPApplication(MultiDriverTestBase):
    """Test CSP at application level."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with CSP."""
        app = RestApplication()

        app.csp(default_src=["self"])

        @app.get("/page")
        def get_page():
            return {"page": "content"}

        return app

    def test_app_level_csp_applied(self, api):
        """Test app-level CSP is applied to responses."""
        api_client, driver_name = api

        request = api_client.get("/page")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"


class TestCSPRouterLevel(MultiDriverTestBase):
    """Test CSP at router level."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with router-level CSP."""
        app = RestApplication()

        # App-level CSP
        app.csp(default_src=["self"])

        # Router with different CSP
        api_router = Router()
        api_router.csp(
            default_src=["self"],
            script_src=["self", "https://cdn.example.com"]
        )

        @api_router.get("/api/data")
        def get_api_data():
            return {"data": "value"}

        app.mount("/api", api_router)

        @app.get("/page")
        def get_page():
            return {"page": "content"}

        return app

    def test_router_level_csp_overrides_app(self, api):
        """Test router-level CSP overrides app-level."""
        api_client, driver_name = api

        # Router-level endpoint
        request = api_client.get("/api/api/data")
        response = api_client.execute(request)
        assert response.status_code == 200
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "script-src 'self' https://cdn.example.com" in csp

        # App-level endpoint
        request = api_client.get("/page")
        response = api_client.execute(request)
        assert response.status_code == 200
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"


class TestCSPRouteLevel(MultiDriverTestBase):
    """Test CSP at route level."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with route-level CSP."""
        app = RestApplication()

        app.csp(default_src=["self"])

        @app.get("/page")
        @app.csp(
            script_src=["self", "https://cdn.com"],
            nonce=True
        )
        def get_page():
            return {"page": "content"}

        @app.get("/other")
        def get_other():
            return {"page": "other"}

        return app

    def test_route_level_csp_overrides_app(self, api):
        """Test route-level CSP overrides app-level."""
        api_client, driver_name = api

        # Route with specific CSP
        request = api_client.get("/page")
        response = api_client.execute(request)
        assert response.status_code == 200
        csp = response.headers.get("Content-Security-Policy", "")
        assert "script-src 'self' https://cdn.com 'nonce-" in csp

        # Route without specific CSP (uses app-level)
        request = api_client.get("/other")
        response = api_client.execute(request)
        assert response.status_code == 200
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"


class TestCSPNonce(MultiDriverTestBase):
    """Test CSP nonce generation."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with nonce support."""
        app = RestApplication()

        @app.get("/with-nonce")
        @app.csp(script_src=["self"], nonce=True)
        def with_nonce(request):
            # Access nonce from request
            nonce = getattr(request, 'csp_nonce', None)
            return {"nonce": nonce}

        @app.get("/without-nonce")
        @app.csp(script_src=["self"])
        def without_nonce(request):
            nonce = getattr(request, 'csp_nonce', None)
            return {"nonce": nonce}

        return app

    def test_nonce_generated_per_request(self, api):
        """Test nonce is generated uniquely per request."""
        api_client, driver_name = api

        request1 = api_client.get("/with-nonce")
        response1 = api_client.execute(request1)
        request2 = api_client.get("/with-nonce")
        response2 = api_client.execute(request2)

        csp1 = response1.headers.get("Content-Security-Policy", "")
        csp2 = response2.headers.get("Content-Security-Policy", "")

        # Extract nonces
        nonce1 = csp1.split("'nonce-")[1].split("'")[0] if "'nonce-" in csp1 else None
        nonce2 = csp2.split("'nonce-")[1].split("'")[0] if "'nonce-" in csp2 else None

        assert nonce1 is not None
        assert nonce2 is not None
        assert nonce1 != nonce2  # Different per request

    def test_nonce_accessible_in_handler(self, api):
        """Test nonce is accessible in request handler."""
        api_client, driver_name = api

        request = api_client.get("/with-nonce")
        response = api_client.execute(request)
        assert response.status_code == 200

        body = response.body
        assert body["nonce"] is not None
        assert len(body["nonce"]) > 0

    def test_no_nonce_when_disabled(self, api):
        """Test no nonce when not enabled."""
        api_client, driver_name = api

        request = api_client.get("/without-nonce")
        response = api_client.execute(request)
        assert response.status_code == 200

        csp = response.headers.get("Content-Security-Policy", "")
        assert "'nonce-" not in csp

        body = response.body
        assert body["nonce"] is None


class TestCSPReportOnly(MultiDriverTestBase):
    """Test CSP report-only mode."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with report-only CSP."""
        app = RestApplication()

        app.csp(
            default_src=["self"],
            report_only=True,
            report_uri="/csp-violations"
        )

        @app.get("/page")
        def get_page():
            return {"page": "content"}

        @app.post("/csp-violations")
        def csp_report(body: dict):
            return {"reported": True}

        return app

    def test_report_only_header_used(self, api):
        """Test report-only header is used."""
        api_client, driver_name = api

        request = api_client.get("/page")
        response = api_client.execute(request)
        assert response.status_code == 200

        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers

    def test_report_uri_in_header(self, api):
        """Test report-uri is included in CSP header."""
        api_client, driver_name = api

        request = api_client.get("/page")
        response = api_client.execute(request)
        csp = response.headers.get("Content-Security-Policy-Report-Only", "")

        assert "report-uri /csp-violations" in csp


class TestCSPDynamicSources(MultiDriverTestBase):
    """Test dynamic CSP sources."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with dynamic CSP sources."""
        app = RestApplication()

        def get_allowed_cdns():
            return ["self", "https://cdn1.com", "https://cdn2.com"]

        app.csp(script_src=get_allowed_cdns)

        @app.get("/page")
        def get_page():
            return {"page": "content"}

        return app

    def test_callable_sources_resolved(self, api):
        """Test callable sources are resolved dynamically."""
        api_client, driver_name = api

        request = api_client.get("/page")
        response = api_client.execute(request)
        assert response.status_code == 200

        csp = response.headers.get("Content-Security-Policy", "")
        assert "script-src 'self' https://cdn1.com https://cdn2.com" in csp


class TestCSPPresetUsage(MultiDriverTestBase):
    """Test using CSP presets."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with CSP preset."""
        app = RestApplication()

        app.csp(preset=CSPPreset.STRICT)

        @app.get("/page")
        def get_page():
            return {"page": "content"}

        return app

    def test_preset_applied(self, api):
        """Test CSP preset is applied."""
        api_client, driver_name = api

        request = api_client.get("/page")
        response = api_client.execute(request)
        assert response.status_code == 200

        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp


class TestCSPProvider(MultiDriverTestBase):
    """Test per-request CSP provider."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with CSP provider."""
        app = RestApplication()

        @app.csp_provider
        def get_csp_for_request(request):
            if request.path.startswith("/admin"):
                return CSPConfig(
                    default_src=["self"],
                    script_src=["self"]
                )
            return CSPConfig(
                default_src=["self"],
                script_src=["self", "https://cdn.com"]
            )

        @app.get("/admin/panel")
        def admin_panel():
            return {"admin": True}

        @app.get("/public/page")
        def public_page():
            return {"public": True}

        return app

    def test_provider_returns_different_csp_per_path(self, api):
        """Test CSP provider returns different config per request."""
        api_client, driver_name = api

        # Admin path - stricter CSP
        request = api_client.get("/admin/panel")
        response = api_client.execute(request)
        assert response.status_code == 200
        csp = response.headers.get("Content-Security-Policy", "")
        assert csp == "default-src 'self'; script-src 'self'"

        # Public path - relaxed CSP
        request = api_client.get("/public/page")
        response = api_client.execute(request)
        assert response.status_code == 200
        csp = response.headers.get("Content-Security-Policy", "")
        assert "script-src 'self' https://cdn.com" in csp

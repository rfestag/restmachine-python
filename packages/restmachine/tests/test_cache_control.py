"""
Tests for Cache-Control and HTTP caching directives.

RFC 9111: HTTP Caching - defines how HTTP caches work and cache-control directives.
https://www.rfc-editor.org/rfc/rfc9111.html
"""

import pytest
from datetime import datetime, timezone, timedelta
from restmachine import RestApplication, Response
from tests.framework import MultiDriverTestBase


class TestCacheControlHeader(MultiDriverTestBase):
    """Test Cache-Control header per RFC 9111."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with various cache control scenarios."""
        app = RestApplication()

        @app.get("/cacheable")
        def get_cacheable():
            """Return cacheable resource.

            RFC 9111 Section 5.2: Cache-Control header field holds directives
            that control caching in requests and responses.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2
            """
            return Response(
                status_code=200,
                body={"data": "cacheable content"},
                headers={
                    "Cache-Control": "max-age=3600, public",
                    "Content-Type": "application/json"
                }
            )

        @app.get("/private")
        def get_private():
            """Return private (user-specific) resource.

            RFC 9111 Section 5.2.2.6: private directive indicates response
            is intended for single user and must not be stored by shared cache.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.6
            """
            return Response(
                status_code=200,
                body={"data": "private content"},
                headers={
                    "Cache-Control": "private, max-age=300"
                }
            )

        @app.get("/no-cache")
        def get_no_cache():
            """Return resource that must be revalidated.

            RFC 9111 Section 5.2.2.4: no-cache directive indicates response
            must not be used to satisfy subsequent request without validation.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.4
            """
            return Response(
                status_code=200,
                body={"data": "must revalidate"},
                headers={
                    "Cache-Control": "no-cache",
                    "ETag": '"v1"'
                }
            )

        @app.get("/no-store")
        def get_no_store():
            """Return resource that must not be stored.

            RFC 9111 Section 5.2.2.5: no-store directive indicates cache
            must not store any part of request or response.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.5
            """
            return Response(
                status_code=200,
                body={"data": "sensitive data"},
                headers={
                    "Cache-Control": "no-store"
                }
            )

        @app.get("/must-revalidate")
        def get_must_revalidate():
            """Return resource that must be revalidated when stale.

            RFC 9111 Section 5.2.2.2: must-revalidate directive indicates
            cache must not use stale response without successful validation.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.2
            """
            return Response(
                status_code=200,
                body={"data": "important"},
                headers={
                    "Cache-Control": "max-age=60, must-revalidate"
                }
            )

        @app.get("/immutable")
        def get_immutable():
            """Return immutable resource.

            RFC 8246: immutable directive indicates response will not change
            during its freshness lifetime.
            https://www.rfc-editor.org/rfc/rfc8246.html
            """
            return Response(
                status_code=200,
                body={"data": "never changes"},
                headers={
                    "Cache-Control": "max-age=31536000, immutable"  # 1 year
                }
            )

        return app

    @pytest.mark.parametrize("endpoint,expected_directive", [
        ("/cacheable", "max-age=3600"),
        ("/cacheable", "public"),
        ("/private", "private"),
        ("/no-cache", "no-cache"),
        ("/no-store", "no-store"),
        ("/must-revalidate", "must-revalidate"),
        ("/immutable", "immutable"),
    ])
    def test_cache_control_directives(self, api, endpoint, expected_directive):
        """Test various Cache-Control directives per RFC 9111.

        RFC 9111: HTTP Caching - defines cache-control directives:
        - max-age (5.2.2.1): Response fresh for specified seconds
        - public (5.2.2.9): May be stored by any cache
        - private (5.2.2.6): Single user only, no shared cache
        - no-cache (5.2.2.4): Must revalidate before use
        - no-store (5.2.2.5): Must not store any part
        - must-revalidate (5.2.2.2): No stale response without validation
        RFC 8246: immutable - Response body will not change over time
        """
        api_client, driver_name = api

        response = api_client.get_resource(endpoint)
        cache_control = response.get_header("Cache-Control")

        assert expected_directive in cache_control


class TestExpiresHeader(MultiDriverTestBase):
    """Test Expires header per RFC 9111 Section 5.3."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with Expires header."""
        app = RestApplication()

        @app.get("/expires")
        def get_with_expires():
            """Return resource with Expires header.

            RFC 9111 Section 5.3: Expires header field contains date/time
            after which response is considered stale.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-5.3
            """
            # Expires 1 hour from now
            expires_time = datetime.now(timezone.utc) + timedelta(hours=1)
            expires_str = expires_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

            return Response(
                status_code=200,
                body={"data": "value"},
                headers={
                    "Expires": expires_str,
                    "Content-Type": "application/json"
                }
            )

        return app

    def test_expires_header_format(self, api):
        """Test Expires header uses HTTP-date format.

        RFC 9111 Section 5.3: Expires field value is HTTP-date indicating
        time after which response is considered stale.
        https://www.rfc-editor.org/rfc/rfc9111.html#section-5.3

        RFC 9110 Section 5.6.7: HTTP-date must be in IMF-fixdate format.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-5.6.7
        """
        api_client, driver_name = api

        response = api_client.get_resource("/expires")
        expires = response.get_header("Expires")

        assert expires is not None
        # Should be in format: "Mon, 09 Oct 2025 12:00:00 GMT"
        assert "GMT" in expires


class TestAgeHeader(MultiDriverTestBase):
    """Test Age header per RFC 9111 Section 5.1."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app for Age header documentation."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"data": "value"}

        return app

    def test_age_header_documentation(self, api):
        """Document Age header usage.

        RFC 9111 Section 5.1: Age header field conveys sender's estimate of
        amount of time since response was generated or validated at origin.
        https://www.rfc-editor.org/rfc/rfc9111.html#section-5.1

        Age value is in seconds (non-negative integer).

        Age calculation (for caches):
        - When response stored: age = max(0, response_time - date_value)
        - When response sent: age = stored_age + resident_time

        Example:
        - Response generated at origin at 12:00:00
        - Cached by proxy at 12:00:05 (Age: 5)
        - Sent to client at 12:00:15 (Age: 15)

        Note: Age header typically added by caching proxies, not origin servers.
        Origin servers typically don't include Age header in responses.
        """
        pass


class TestVaryHeader(MultiDriverTestBase):
    """Test Vary header per RFC 9110 Section 12.5.5."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with Vary header."""
        app = RestApplication()

        @app.get("/content-negotiated")
        def get_negotiated(request):
            """Return content based on Accept header.

            RFC 9110 Section 12.5.5: Vary field describes request headers
            that might have influenced selection of representation.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.5
            """
            accept = request.headers.get("accept", "application/json")

            return Response(
                status_code=200,
                body={"data": "value"},
                headers={
                    "Content-Type": "application/json",
                    "Vary": "Accept"  # Response varies based on Accept header
                }
            )

        @app.get("/user-specific")
        def get_user_specific(request):
            """Return user-specific content.

            RFC 9111 Section 4.1: When origin server returns Vary header,
            cache must include varying header fields in cache key.
            https://www.rfc-editor.org/rfc/rfc9111.html#section-4.1
            """
            return Response(
                status_code=200,
                body={"user": "data"},
                headers={
                    "Vary": "Authorization",  # Different per user
                    "Cache-Control": "private, max-age=300"
                }
            )

        return app

    def test_vary_with_content_negotiation(self, api):
        """Test Vary header for content negotiation.

        RFC 9110 Section 12.5.5: When response content varies based on
        request header (like Accept), server SHOULD include that header
        in Vary field.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.5
        """
        api_client, driver_name = api

        response = api_client.get_resource("/content-negotiated")
        vary = response.get_header("Vary")

        assert "Accept" in vary

    def test_vary_with_authorization(self, api):
        """Test Vary: Authorization for user-specific content.

        RFC 9110 Section 12.5.5: Vary: Authorization indicates response
        content depends on Authorization header (different per user).
        https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.5
        """
        api_client, driver_name = api

        response = api_client.get_resource("/user-specific")
        vary = response.get_header("Vary")

        assert "Authorization" in vary

    def test_vary_star_documentation(self, api):
        """Document Vary: * usage.

        RFC 9110 Section 12.5.5: Vary field with value "*" indicates
        response varies on aspects not expressible in request headers
        (e.g., IP address, geolocation, time of day).
        https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.5

        Vary: * effectively makes response uncacheable by shared caches.

        Use case examples:
        - A/B testing based on hash of IP address
        - Content based on geographic location
        - Randomized content
        - Time-dependent content

        Note: Private caches (browser cache) may still cache Vary: * responses.
        """
        pass

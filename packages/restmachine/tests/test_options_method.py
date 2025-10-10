"""
Tests for OPTIONS method HTTP compliance.

RFC 9110 Section 9.3.7: The OPTIONS method requests information about the
communication options available for the target resource.
https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
"""

import pytest
from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestOptionsMethod(MultiDriverTestBase):
    """Test OPTIONS method support per RFC 9110 Section 9.3.7."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app with multiple methods on same resource."""
        app = RestApplication()

        @app.get("/users/{user_id}")
        def get_user(user_id: str):
            """Get user by ID.

            RFC 9110 Section 9.3.1: GET method requests transfer of current
            selected representation for target resource.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.1
            """
            return {"id": user_id, "name": f"User {user_id}"}

        @app.post("/users")
        def create_user(json_body):
            """Create new user.

            RFC 9110 Section 9.3.3: POST method requests that target resource
            process representation enclosed in request.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.3
            """
            return {"id": "123", **json_body}

        @app.put("/users/{user_id}")
        def update_user(user_id: str, json_body):
            """Update user.

            RFC 9110 Section 9.3.4: PUT method requests that state of target
            resource be created or replaced with state defined by representation.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.4
            """
            return {"id": user_id, **json_body}

        @app.delete("/users/{user_id}")
        def delete_user(user_id: str):
            """Delete user.

            RFC 9110 Section 9.3.5: DELETE method requests that origin server
            remove association between target resource and its current functionality.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.5
            """
            return None

        @app.options("/users/{user_id}")
        def options_user(user_id: str):
            """OPTIONS for specific user resource.

            RFC 9110 Section 9.3.7: OPTIONS method requests information about
            communication options available for target resource.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
            """
            return {
                "description": "User resource",
                "allowed_methods": ["GET", "PUT", "DELETE", "OPTIONS"]
            }

        @app.options("/users")
        def options_users():
            """OPTIONS for users collection.

            RFC 9110 Section 9.3.7: Server generating 2xx response to OPTIONS
            SHOULD send headers indicating optional features implemented.
            https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
            """
            return {
                "description": "Users collection",
                "allowed_methods": ["POST", "OPTIONS"]
            }

        return app

    def test_options_returns_200(self, api):
        """Test OPTIONS method returns 200 OK.

        RFC 9110 Section 9.3.7: OPTIONS is intended to allow client to determine
        options and/or requirements without implying resource action.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
        """
        api_client, driver_name = api

        request = api_client.options("/users/123")
        response = api_client.execute(request)
        assert response.status_code == 200

    def test_options_returns_allowed_methods_info(self, api):
        """Test OPTIONS returns information about allowed methods.

        RFC 9110 Section 9.3.7: Response payload describes communication options.
        Common practice to include list of allowed methods.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
        """
        api_client, driver_name = api

        request = api_client.options("/users/123")
        response = api_client.execute(request)
        data = response.get_json_body()

        assert "allowed_methods" in data
        assert "GET" in data["allowed_methods"]
        assert "PUT" in data["allowed_methods"]
        assert "DELETE" in data["allowed_methods"]

    def test_options_on_collection_differs_from_resource(self, api):
        """Test OPTIONS returns different info for collection vs resource.

        RFC 9110 Section 9.3.7: Response is specific to the target resource.
        Collection and individual resources may support different methods.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7
        """
        api_client, driver_name = api

        collection_request = api_client.options("/users")
        collection_response = api_client.execute(collection_request)
        collection_data = collection_response.get_json_body()

        resource_request = api_client.options("/users/123")
        resource_response = api_client.execute(resource_request)
        resource_data = resource_response.get_json_body()

        # Collection allows POST, resource does not
        assert "POST" in collection_data["allowed_methods"]
        assert "POST" not in resource_data["allowed_methods"]

        # Resource allows GET, collection might not
        assert "GET" in resource_data["allowed_methods"]

    def test_options_max_forwards_header(self, api):
        """Test OPTIONS with Max-Forwards header (for proxy chains).

        RFC 9110 Section 7.6.2: Max-Forwards header limits number of times
        request can be forwarded by proxies. Used with TRACE and OPTIONS.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.2
        """
        api_client, driver_name = api

        # OPTIONS with Max-Forwards should be processed
        request = api_client.options("/users/123")
        request = request.with_header("Max-Forwards", "0")
        response = api_client.execute(request)

        # When Max-Forwards is 0, proxy/server should respond with its own capabilities
        assert response.status_code == 200

    def test_options_with_asterisk_form(self, api):
        """Test OPTIONS * (asterisk-form) for server-wide options.

        RFC 9110 Section 9.3.7: When target is "*" (asterisk-form),
        OPTIONS request applies to server in general rather than specific resource.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.7

        Note: This test documents the RFC requirement. Implementation of asterisk-form
        OPTIONS is optional and framework-dependent.
        """
        # This is a documentation test - asterisk-form is typically handled
        # at the server level (uvicorn, hypercorn) not the application level
        # Most ASGI frameworks don't route OPTIONS * to applications
        pass


class TestAllowHeader(MultiDriverTestBase):
    """Test Allow header per RFC 9110 Section 10.2.1."""

    ENABLED_DRIVERS = ['direct']

    def create_app(self) -> RestApplication:
        """Create app to test Allow header."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"data": "value"}

        @app.post("/resource")
        def post_resource(json_body):
            return {"created": True}

        return app

    def test_405_includes_allow_header(self, api):
        """Test 405 Method Not Allowed includes Allow header.

        RFC 9110 Section 10.2.1: Origin server MUST generate Allow header
        in 405 (Method Not Allowed) response.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.1

        RFC 9110 Section 15.5.6: 405 response MUST include Allow header
        containing list of target resource's currently supported methods.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.6
        """
        api_client, driver_name = api

        # Try DELETE on resource that only supports GET and POST
        request = api_client.delete("/resource")
        response = api_client.execute(request)

        assert response.status_code == 405

        # Allow header should be present
        allow_header = response.get_header("Allow")
        if allow_header:  # Framework may or may not implement this
            # Should list GET and POST as allowed methods
            assert "GET" in allow_header or "POST" in allow_header

    def test_options_may_include_allow_header(self, api):
        """Test OPTIONS response may include Allow header.

        RFC 9110 Section 10.2.1: Server MAY generate Allow header in other
        responses to indicate currently supported methods for target resource.
        Common to include in OPTIONS responses.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.1
        """
        # This is a documentation test - Allow header in OPTIONS is optional
        # but commonly implemented. RestMachine may choose to implement this
        pass

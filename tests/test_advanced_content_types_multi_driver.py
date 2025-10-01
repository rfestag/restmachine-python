"""
Advanced content type tests using multi-driver approach.

Tests for content type handling consistency across different drivers.
This file contains only the unique tests not covered by test_content_parsers_multi_driver.py.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class TestContentTypeConsistencyAcrossDrivers(MultiDriverTestBase):
    """Test content type handling consistency across drivers."""

    def create_app(self) -> RestApplication:
        """Create app for testing consistency across drivers."""
        app = RestApplication()

        @app.accepts("application/custom")
        def parse_custom(body: str):
            return {"custom": True, "content": body}

        @app.post("/custom")
        def handle_custom(parsed_data):
            return {"received": parsed_data}

        @app.post("/json")
        def handle_json(json_body):
            return {"received": json_body}

        return app

    def test_custom_content_type_across_drivers(self, api):
        """Test custom content type parsing across drivers."""
        api_client, driver_name = api

        custom_content = "custom format data"

        request = (api_client.post("/custom")
                  .with_text_body(custom_content)
                  .with_header("Content-Type", "application/custom")
                  .accepts("application/json"))

        response = api_client.execute(request)
        data = api_client.expect_successful_creation(response)

        assert data["received"]["custom"] is True
        assert data["received"]["content"] == custom_content

    def test_json_handling_across_drivers(self, api):
        """Test JSON handling consistency across drivers."""
        api_client, driver_name = api

        json_data = {"test": "value", "number": 42}

        response = api_client.create_resource("/json", json_data)
        data = api_client.expect_successful_creation(response)

        assert data["received"]["test"] == "value"
        assert data["received"]["number"] == 42

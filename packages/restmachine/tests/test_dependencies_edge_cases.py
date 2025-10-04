"""
Tests for dependency parameter detection edge cases.

Covers uncovered lines in dependencies.py for response_headers
and backward-compatible 'headers' parameter in ValidationWrapper.
"""

from pydantic import BaseModel
from restmachine import RestApplication
from tests.framework import MultiDriverTestBase


class RequestData(BaseModel):
    """Test request model."""
    name: str
    value: int


class TestValidatorParameterDetection(MultiDriverTestBase):
    """Test that validators correctly detect parameter usage."""

    def create_app(self) -> RestApplication:
        """Create app with validators using different parameters."""
        app = RestApplication()

        # Test response_headers parameter in validator
        @app.validates
        def validator_with_response_headers(json_body, response_headers) -> RequestData:
            """Validator using response_headers parameter."""
            # Set a header in the validator
            response_headers["X-Validator-Header"] = "from-validator"
            return RequestData.model_validate(json_body)

        @app.post("/test-response-headers")
        def test_response_headers_endpoint(validator_with_response_headers):
            """Endpoint using validator with response_headers."""
            return {"name": validator_with_response_headers.name}

        # Test 'headers' parameter (backward compatibility) in validator
        @app.validates
        def validator_with_headers(json_body, headers) -> RequestData:
            """Validator using 'headers' parameter for backward compatibility."""
            # Access request headers
            return RequestData.model_validate(json_body)

        @app.post("/test-headers-backward-compat")
        def test_headers_endpoint(validator_with_headers):
            """Endpoint using validator with 'headers' parameter."""
            return {"value": validator_with_headers.value}

        # Test request_headers parameter in validator
        @app.validates
        def validator_with_request_headers(json_body, request_headers) -> RequestData:
            """Validator using request_headers parameter."""
            # Access request headers
            return RequestData.model_validate(json_body)

        @app.post("/test-request-headers")
        def test_request_headers_endpoint(validator_with_request_headers):
            """Endpoint using validator with request_headers."""
            return {"name": validator_with_request_headers.name, "value": validator_with_request_headers.value}

        return app

    def test_validator_with_response_headers(self, api):
        """Test that validator can use response_headers parameter."""
        api_client, driver_name = api

        data = {"name": "test", "value": 123}
        response = api_client.create_resource("/test-response-headers", data)
        result = api_client.expect_successful_creation(response)

        # The test just verifies the validator with response_headers parameter works
        # (covers line 97-98 in dependencies.py)
        assert result["name"] == "test"

    def test_validator_with_headers_backward_compat(self, api):
        """Test that validator can use 'headers' parameter (backward compatibility)."""
        api_client, driver_name = api

        data = {"name": "test", "value": 456}
        response = api_client.create_resource("/test-headers-backward-compat", data)
        result = api_client.expect_successful_creation(response)

        assert result["value"] == 456

    def test_validator_with_request_headers(self, api):
        """Test that validator can use request_headers parameter."""
        api_client, driver_name = api

        data = {"name": "test", "value": 789}
        response = api_client.create_resource("/test-request-headers", data)
        result = api_client.expect_successful_creation(response)

        assert result["name"] == "test"
        assert result["value"] == 789

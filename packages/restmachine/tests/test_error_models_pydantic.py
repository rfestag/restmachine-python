"""
Tests for error_models.py Pydantic version features.

Tests features that only work when Pydantic IS available.
"""

from pydantic import BaseModel, ValidationError
from restmachine.error_models import ErrorResponse


class TestErrorResponsePydantic:
    """Test ErrorResponse with Pydantic available."""

    def test_from_validation_error_with_pydantic(self):
        """Test creating ErrorResponse from a real Pydantic ValidationError."""

        # Define a model that will fail validation
        class UserModel(BaseModel):
            name: str
            age: int
            email: str

        # Trigger a validation error
        try:
            UserModel(name="", age="not-a-number", email="invalid")
        except ValidationError as e:
            # Create ErrorResponse from the validation error
            error_response = ErrorResponse.from_validation_error(
                e,
                message="User validation failed",
                request_id="req-123",
                trace_id="trace-456"
            )

            # Verify the response
            assert error_response.error == "User validation failed"
            assert error_response.request_id == "req-123"
            assert error_response.trace_id == "trace-456"
            assert error_response.details is not None
            assert len(error_response.details) > 0

            # Verify that include_url=False worked (no 'url' field in details)
            for detail in error_response.details:
                assert 'url' not in detail

    def test_from_validation_error_with_trace_id(self):
        """Test that trace_id is properly set in ErrorResponse."""

        class SimpleModel(BaseModel):
            value: int

        try:
            SimpleModel(value="not-an-int")
        except ValidationError as e:
            error_response = ErrorResponse.from_validation_error(
                e,
                message="Invalid value",
                trace_id="trace-789"
            )

            assert error_response.trace_id == "trace-789"
            assert error_response.request_id is None

    def test_pydantic_error_response_model_dump_json(self):
        """Test model_dump_json includes trace_id when set."""
        import json

        error_response = ErrorResponse(
            error="Test error",
            details=[{"field": "test", "message": "error"}],
            request_id="req-001",
            trace_id="trace-001"
        )

        json_str = error_response.model_dump_json(exclude_none=False)
        data = json.loads(json_str)

        assert data["error"] == "Test error"
        assert data["request_id"] == "req-001"
        assert data["trace_id"] == "trace-001"
        assert data["details"] == [{"field": "test", "message": "error"}]

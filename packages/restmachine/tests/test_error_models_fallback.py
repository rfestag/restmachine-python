"""
Tests for error_models.py fallback behavior when Pydantic is not available.

These tests mock the Pydantic import to ensure the fallback ErrorResponse
class works correctly when Pydantic is not installed.
"""

import sys
import pytest
from unittest.mock import patch


class TestErrorResponseFallback:
    """Test ErrorResponse fallback implementation."""

    def test_fallback_basic_error(self):
        """Test basic error response without Pydantic."""
        # Mock pydantic import failure
        with patch.dict(sys.modules, {'pydantic': None}):
            # Force reimport to trigger fallback
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            # Create error response
            error = error_models.ErrorResponse(
                error="Test error",
                details=[{"field": "name", "message": "Required"}],
                request_id="req-123",
                trace_id="trace-456"
            )

            assert error.error == "Test error"
            assert error.details == [{"field": "name", "message": "Required"}]
            assert error.request_id == "req-123"
            assert error.trace_id == "trace-456"

    def test_fallback_model_dump(self):
        """Test model_dump serialization without Pydantic."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            error = error_models.ErrorResponse(
                error="Validation failed",
                details=[{"field": "email", "message": "Invalid"}],
                request_id="req-789"
            )

            result = error.model_dump()

            assert result["error"] == "Validation failed"
            assert result["details"] == [{"field": "email", "message": "Invalid"}]
            assert result["request_id"] == "req-789"
            assert "trace_id" not in result  # None excluded by default

    def test_fallback_model_dump_exclude_none_false(self):
        """Test model_dump with exclude_none=False."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            error = error_models.ErrorResponse(
                error="Test error"
                # details, request_id, trace_id all None
            )

            result = error.model_dump(exclude_none=False)

            assert result["error"] == "Test error"
            assert result["details"] is None
            assert result["request_id"] is None
            assert result["trace_id"] is None

    def test_fallback_model_dump_json(self):
        """Test model_dump_json serialization without Pydantic."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            error = error_models.ErrorResponse(
                error="JSON test",
                details=[{"type": "value_error"}],
                request_id="req-json"
            )

            json_str = error.model_dump_json()

            import json
            result = json.loads(json_str)

            assert result["error"] == "JSON test"
            assert result["details"] == [{"type": "value_error"}]
            assert result["request_id"] == "req-json"
            assert "trace_id" not in result

    def test_fallback_from_validation_error(self):
        """Test creating ErrorResponse from validation error without Pydantic."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            # Create a mock validation error object
            class MockValidationError:
                def errors(self):
                    return [
                        {"loc": ["field1"], "msg": "Invalid value"},
                        {"loc": ["field2"], "msg": "Required"}
                    ]

            mock_error = MockValidationError()
            error = error_models.ErrorResponse.from_validation_error(
                mock_error,
                message="Validation failed",
                request_id="req-val"
            )

            assert error.error == "Validation failed"
            assert error.details == [
                {"loc": ["field1"], "msg": "Invalid value"},
                {"loc": ["field2"], "msg": "Required"}
            ]
            assert error.request_id == "req-val"

    def test_fallback_from_validation_error_no_errors_method(self):
        """Test from_validation_error with object that has no errors() method."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            # Create object without errors() method
            class MockError:
                pass

            mock_error = MockError()
            error = error_models.ErrorResponse.from_validation_error(
                mock_error,
                message="Generic error"
            )

            assert error.error == "Generic error"
            assert error.details is None

    def test_fallback_minimal_error(self):
        """Test error response with only required field."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import error_models
            importlib.reload(error_models)

            error = error_models.ErrorResponse(error="Minimal error")

            result = error.model_dump()
            assert result == {"error": "Minimal error"}

            json_str = error.model_dump_json()
            import json
            assert json.loads(json_str) == {"error": "Minimal error"}

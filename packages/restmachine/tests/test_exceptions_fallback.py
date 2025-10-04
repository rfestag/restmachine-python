"""
Tests for fallback ValidationError when Pydantic is not available.

These tests mock the absence of Pydantic to ensure the fallback
MyValidationError class works correctly.
"""

import sys
import json
from unittest.mock import patch


class TestValidationErrorFallback:
    """Test fallback ValidationError implementation."""

    def test_fallback_validation_error_basic(self):
        """Test basic ValidationError without Pydantic."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import exceptions
            importlib.reload(exceptions)

            # Create a ValidationError using the fallback
            error = exceptions.ValidationError("Field is required")

            assert error.message == "Field is required"
            assert str(error) == "Field is required"

    def test_fallback_validation_error_errors_method(self):
        """Test errors() method returns Pydantic-like format."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import exceptions
            importlib.reload(exceptions)

            error = exceptions.ValidationError("Validation failed")
            errors = error.errors()

            assert isinstance(errors, list)
            assert len(errors) == 1
            assert errors[0]["msg"] == "Validation failed"

    def test_fallback_validation_error_json_method(self):
        """Test json() method returns valid JSON."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import exceptions
            importlib.reload(exceptions)

            error = exceptions.ValidationError("Invalid data")
            json_str = error.json()

            # Parse JSON to verify it's valid
            data = json.loads(json_str)
            assert "detail" in data
            assert isinstance(data["detail"], list)
            assert data["detail"][0]["msg"] == "Invalid data"

    def test_fallback_validation_error_default_message(self):
        """Test ValidationError with default message."""
        with patch.dict(sys.modules, {'pydantic': None}):
            import importlib
            from restmachine import exceptions
            importlib.reload(exceptions)

            error = exceptions.ValidationError()
            assert error.message == "Validation failed"
            errors = error.errors()
            assert errors[0]["msg"] == "Validation failed"


class TestExceptionTypes:
    """Test that all exception types are defined."""

    def test_rest_framework_error_exists(self):
        """Test RestFrameworkError is defined."""
        from restmachine.exceptions import RestFrameworkError

        error = RestFrameworkError()
        assert isinstance(error, BaseException)

    def test_dependency_resolution_error_exists(self):
        """Test DependencyResolutionError is defined."""
        from restmachine.exceptions import DependencyResolutionError, RestFrameworkError

        error = DependencyResolutionError("Cannot resolve dependency")
        assert isinstance(error, RestFrameworkError)

    def test_route_not_found_error_exists(self):
        """Test RouteNotFoundError is defined."""
        from restmachine.exceptions import RouteNotFoundError, RestFrameworkError

        error = RouteNotFoundError("Route not found")
        assert isinstance(error, RestFrameworkError)

    def test_content_negotiation_error_exists(self):
        """Test ContentNegotiationError is defined."""
        from restmachine.exceptions import ContentNegotiationError, RestFrameworkError

        error = ContentNegotiationError("Cannot negotiate content")
        assert isinstance(error, RestFrameworkError)

    def test_accepts_parsing_error_exists(self):
        """Test AcceptsParsingError is defined and has attributes."""
        from restmachine.exceptions import AcceptsParsingError, RestFrameworkError

        original_exc = ValueError("Original error")
        error = AcceptsParsingError("Parser failed", original_exception=original_exc)

        assert isinstance(error, RestFrameworkError)
        assert error.message == "Parser failed"
        assert error.original_exception is original_exc

    def test_accepts_parsing_error_default_message(self):
        """Test AcceptsParsingError with default message."""
        from restmachine.exceptions import AcceptsParsingError

        error = AcceptsParsingError()
        assert error.message == "Failed to parse request body"
        assert error.original_exception is None

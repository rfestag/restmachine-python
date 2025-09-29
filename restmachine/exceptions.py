"""
Custom exceptions for the REST framework.
"""
from typing import Any, List, Dict

try:
    from pydantic import ValidationError as PydanticValidationError # type: ignore[import-not-found]

    PYDANTIC_AVAILABLE = True
    ValidationError = PydanticValidationError
except ImportError:
    PYDANTIC_AVAILABLE = False

    class MyValidationError(Exception):
        """Fallback ValidationError when Pydantic is not available."""

        def __init__(self, message="Validation failed"):
            self.message = message
            super().__init__(self.message)

        def errors(self) -> List[Dict[str, Any]]:
            """Return errors in Pydantic-like format."""
            return [{"msg": self.message}]

        def json(self) -> str:
            """Return JSON representation for compatibility."""
            import json
            return json.dumps({"detail": [{"msg": self.message}]})

    ValidationError = MyValidationError  # type: ignore[misc,assignment]


class RestFrameworkError(BaseException):
    """Base exception for REST framework errors."""

    pass


class DependencyResolutionError(RestFrameworkError):
    """Raised when a dependency cannot be resolved."""

    pass


class RouteNotFoundError(RestFrameworkError):
    """Raised when no route matches the request."""

    pass


class ContentNegotiationError(RestFrameworkError):
    """Raised when content negotiation fails."""

    pass


class AcceptsParsingError(RestFrameworkError):
    """Raised when a custom accepts parser fails to parse the request body."""

    def __init__(self, message="Failed to parse request body", original_exception=None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)

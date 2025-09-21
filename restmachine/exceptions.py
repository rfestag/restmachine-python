"""
Custom exceptions for the REST framework.
"""

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

        def errors(self):
            """Return errors in Pydantic-like format."""
            return [{"msg": self.message}]
    ValidationError = MyValidationError


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

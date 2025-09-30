"""
Dependency injection system for the REST framework.
"""

from typing import Any, Callable, Dict


class DependencyCache:
    """Cache for dependency injection results within a single request."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()


class ValidationWrapper:
    """Wrapper for validation functions that return Pydantic models."""

    def __init__(self, func: Callable):
        import inspect

        self.func = func
        self.name = func.__name__
        self.original_name = func.__name__

        # Store return annotation and inspect function signature
        sig = inspect.signature(func)
        self.return_annotation = (
            sig.return_annotation
            if sig.return_annotation != inspect.Signature.empty
            else None
        )

        # Track which built-in dependencies this validator uses
        self.depends_on_body = False
        self.depends_on_query_params = False
        self.depends_on_path_params = False
        self.depends_on_request_headers = False
        self.depends_on_response_headers = False

        for param_name, param in sig.parameters.items():
            if param_name in ["body", "json_body", "form_body", "text_body", "multipart_body"]:
                self.depends_on_body = True
            elif param_name == "query_params":
                self.depends_on_query_params = True
            elif param_name == "path_params":
                self.depends_on_path_params = True
            elif param_name in ["request_headers", "headers"]:  # headers for backwards compatibility
                self.depends_on_request_headers = True
            elif param_name == "response_headers":
                self.depends_on_response_headers = True


class DependencyWrapper:
    """Wrapper for dependencies with state machine callback behavior."""

    def __init__(self, func: Callable, state_name: str, name: str):
        self.func = func
        self.state_name = state_name
        self.name = name
        self.original_name = func.__name__


class HeadersWrapper:
    """Wrapper for header manipulation functions."""

    def __init__(self, func: Callable, name: str):
        self.func = func
        self.name = name
        self.original_name = func.__name__


class ContentNegotiationWrapper:
    """Wrapper for content-type specific renderers."""

    def __init__(self, func: Callable, content_type: str, handler_dependency_name: str):
        self.func = func
        self.content_type = content_type
        self.original_name = func.__name__
        self.handler_dependency_name = handler_dependency_name


class AcceptsWrapper:
    """Wrapper for content-type specific body parsers."""

    def __init__(self, func: Callable, content_type: str, name: str):
        self.func = func
        self.content_type = content_type
        self.name = name
        self.original_name = func.__name__

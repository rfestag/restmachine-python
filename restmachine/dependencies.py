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
        self.func = func
        self.name = func.__name__
        self.original_name = func.__name__


class DependencyWrapper:
    """Wrapper for dependencies with state machine callback behavior."""
    
    def __init__(self, func: Callable, state_name: str, name: str):
        self.func = func
        self.state_name = state_name
        self.name = name
        self.original_name = func.__name__


class ContentNegotiationWrapper:
    """Wrapper for content-type specific renderers."""
    
    def __init__(self, func: Callable, content_type: str, handler_dependency_name: str):
        self.func = func
        self.content_type = content_type
        self.original_name = func.__name__
        self.handler_dependency_name = handler_dependency_name

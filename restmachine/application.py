"""
Main application class for the REST framework.
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from .models import Request, Response, HTTPMethod
from .content_renderers import JSONRenderer, HTMLRenderer, PlainTextRenderer, ContentRenderer
from .dependencies import (
    DependencyCache, ValidationWrapper, DependencyWrapper, 
    ContentNegotiationWrapper
)
from .state_machine import RequestStateMachine
from .exceptions import ValidationError, PYDANTIC_AVAILABLE


class RouteHandler:
    """Represents a registered route and its handler."""
    
    def __init__(self, method: HTTPMethod, path: str, handler: Callable):
        self.method = method
        self.path = path
        self.handler = handler
        self.path_pattern = self._compile_path_pattern(path)
        self.content_renderers: Dict[str, ContentNegotiationWrapper] = {}
        self.validation_wrappers: List[ValidationWrapper] = []
    
    def _compile_path_pattern(self, path: str) -> str:
        """Convert path with {param} syntax to a pattern for matching."""
        # Replace {param} with named regex groups
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)
        return f"^{pattern}$"
    
    def matches(self, method: HTTPMethod, path: str) -> Optional[Dict[str, str]]:
        """Check if this route matches the given method and path."""
        if self.method != method:
            return None
        
        match = re.match(self.path_pattern, path)
        if match:
            return match.groupdict()
        return None
    
    def add_content_renderer(self, content_type: str, wrapper: ContentNegotiationWrapper):
        """Add a content-specific renderer for this route."""
        self.content_renderers[content_type] = wrapper
    
    def add_validation_wrapper(self, wrapper: ValidationWrapper):
        self.validation_wrappers.append(wrapper)


class RestApplication:
    """Main application class for the REST framework."""
    
    def __init__(self):
        self._routes: List[RouteHandler] = []
        self._dependencies: Dict[str, Union[Callable, DependencyWrapper]] = {}
        self._validation_dependencies: Dict[str, ValidationWrapper] = {}
        self._default_callbacks: Dict[str, Callable] = {}
        self._dependency_cache = DependencyCache()
        self._state_machine = RequestStateMachine(self)
        self._content_renderers: Dict[str, ContentRenderer] = {}
        
        # Add default content renderers
        self.add_content_renderer(JSONRenderer())
        self.add_content_renderer(HTMLRenderer())
        self.add_content_renderer(PlainTextRenderer())
    
    def add_content_renderer(self, renderer: ContentRenderer):
        """Add a global content renderer."""
        self._content_renderers[renderer.media_type] = renderer
    
    def dependency(self, name: Optional[str] = None):
        """Decorator to register a dependency provider."""
        def decorator(func: Callable):
            dep_name = name or func.__name__
            self._dependencies[dep_name] = func
            return func
        return decorator
    
    # State machine callback decorators for dependencies
    def resource_exists(self, func: Callable):
        """Decorator to wrap a dependency with resource existence checking."""
        wrapper = DependencyWrapper(func, 'resource_exists', func.__name__)
        self._dependencies[func.__name__] = wrapper
        return func
    
    def forbidden(self, func: Callable):
        """Decorator to wrap a dependency with forbidden checking."""
        wrapper = DependencyWrapper(func, 'forbidden', func.__name__)
        self._dependencies[func.__name__] = wrapper
        return func
    
    def authorized(self, func: Callable):
        """Decorator to wrap a dependency with authorization checking."""
        wrapper = DependencyWrapper(func, 'authorized', func.__name__)
        self._dependencies[func.__name__] = wrapper
        return func
    
    # Content negotiation decorators
    def renders(self, content_type: str):
        """Decorator to register a content-type specific renderer for an endpoint."""
        def decorator(func: Callable):
            # Find the most recently added route (should be the one this renderer is for)
            if self._routes:
                route = self._routes[-1]
                handler_name = route.handler.__name__
                wrapper = ContentNegotiationWrapper(func, content_type, handler_name)
                route.add_content_renderer(content_type, wrapper)
                
                # Also register this as a dependency so it can be injected
                self._dependencies[func.__name__] = func
            return func
        return decorator
    
    # Simplified validation decorator - just expects Pydantic model return
    def validates(self, func: Callable):
        """Decorator to mark a function as returning a validated Pydantic model."""
        if not PYDANTIC_AVAILABLE:
            raise ImportError("Pydantic is required for validation features")
        
        wrapper = ValidationWrapper(func)
        self._validation_dependencies[func.__name__] = wrapper
        # Also register as regular dependency for injection
        self._dependencies[func.__name__] = func
        return func
    
    # Default state machine callbacks
    def default_service_available(self, func: Callable):
        """Register a default service_available callback."""
        self._default_callbacks['service_available'] = func
        return func
    
    def default_known_method(self, func: Callable):
        """Register a default known_method callback."""
        self._default_callbacks['known_method'] = func
        return func
    
    def default_uri_too_long(self, func: Callable):
        """Register a default uri_too_long callback."""
        self._default_callbacks['uri_too_long'] = func
        return func
    
    def default_method_allowed(self, func: Callable):
        """Register a default method_allowed callback."""
        self._default_callbacks['method_allowed'] = func
        return func
    
    def default_malformed_request(self, func: Callable):
        """Register a default malformed_request callback."""
        self._default_callbacks['malformed_request'] = func
        return func
    
    def default_authorized(self, func: Callable):
        """Register a default authorized callback."""
        self._default_callbacks['authorized'] = func
        return func
    
    def default_forbidden(self, func: Callable):
        """Register a default forbidden callback."""
        self._default_callbacks['forbidden'] = func
        return func
    
    def default_content_headers_valid(self, func: Callable):
        """Register a default content_headers_valid callback."""
        self._default_callbacks['content_headers_valid'] = func
        return func
    
    def default_resource_exists(self, func: Callable):
        """Register a default resource_exists callback."""
        self._default_callbacks['resource_exists'] = func
        return func
    
    def default_route_not_found(self, func: Callable):
        """Register a default route_not_found callback."""
        self._default_callbacks['route_not_found'] = func
        return func
    
    # HTTP method decorators
    def get(self, path: str):
        """Decorator to register a GET route handler."""
        return self._route_decorator(HTTPMethod.GET, path)
    
    def post(self, path: str):
        """Decorator to register a POST route handler."""
        return self._route_decorator(HTTPMethod.POST, path)
    
    def put(self, path: str):
        """Decorator to register a PUT route handler."""
        return self._route_decorator(HTTPMethod.PUT, path)
    
    def delete(self, path: str):
        """Decorator to register a DELETE route handler."""
        return self._route_decorator(HTTPMethod.DELETE, path)
    
    def patch(self, path: str):
        """Decorator to register a PATCH route handler."""
        return self._route_decorator(HTTPMethod.PATCH, path)
    
    def _route_decorator(self, method: HTTPMethod, path: str):
        """Internal method to create route decorators."""
        def decorator(func: Callable):
            route = RouteHandler(method, path, func)
            self._routes.append(route)
            return func
        return decorator
    
    def _resolve_dependency(self, param_name: str, param_type: Type, request: Request) -> Any:
        """Resolve a dependency by name and type."""
        # Check cache first
        cached_value = self._dependency_cache.get(param_name)
        if cached_value is not None:
            return cached_value
        
        # Built-in dependencies
        if param_name == 'request' or param_type == Request:
            self._dependency_cache.set(param_name, request)
            return request
        
        # Check registered dependencies
        if param_name in self._dependencies:
            dep_or_wrapper = self._dependencies[param_name]
            
            if isinstance(dep_or_wrapper, DependencyWrapper):
                # For wrapped dependencies, the state machine will handle the resolution
                # and early exit logic. Here we just call the function.
                resolved_value = self._call_with_injection(dep_or_wrapper.func, request)
                self._dependency_cache.set(param_name, resolved_value)
                return resolved_value
            else:
                # Regular dependency - check if it's a validation dependency
                if param_name in self._validation_dependencies:
                    # This is a validation function that should return a Pydantic model
                    # Call it and validate the result
                    result = self._call_with_injection(dep_or_wrapper, request)
                    
                    # The function should return a Pydantic model
                    # If ValidationError occurs, it will be caught by the state machine
                    if hasattr(result, 'model_validate') or hasattr(result, 'model_dump'):
                        # It's already a Pydantic model, cache and return
                        self._dependency_cache.set(param_name, result)
                        return result
                    else:
                        # If it's not a Pydantic model, something went wrong
                        raise ValueError(f"Validation function {param_name} must return a Pydantic model")
                else:
                    # Regular dependency
                    resolved_value = self._call_with_injection(dep_or_wrapper, request)
                    self._dependency_cache.set(param_name, resolved_value)
                    return resolved_value
        
        raise ValueError(f"Unable to resolve dependency: {param_name}")
    
    def _call_with_injection(self, func: Callable, request: Request) -> Any:
        """Call a function with dependency injection."""
        sig = inspect.signature(func)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else None
            resolved_value = self._resolve_dependency(param_name, param_type, request)
            kwargs[param_name] = resolved_value
        
        return func(**kwargs)
    
    def _find_route(self, method: HTTPMethod, path: str) -> Optional[Tuple[RouteHandler, Dict[str, str]]]:
        """Find a matching route for the given method and path."""
        for route in self._routes:
            path_params = route.matches(method, path)
            if path_params is not None:
                return route, path_params
        return None
    
    def execute(self, request: Request) -> Response:
        """Execute a request through the state machine."""
        return self._state_machine.process_request(request)

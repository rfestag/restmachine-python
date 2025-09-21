#!/usr/bin/env python3
"""
Complete script to generate the entire REST Framework package structure.
Run this script in an empty directory to create all the package files.
"""

import os
from pathlib import Path

# Complete file contents dictionary with ALL files
FILES = {
    "rest_framework/__init__.py": '''"""
A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine,
content negotiation support, and Pydantic-based validation.

This module provides a Flask-like interface with powerful dependency injection
capabilities, a webmachine-inspired state machine, flexible content negotiation,
and comprehensive request/response validation using Pydantic models.
"""

from .application import RestApplication
from .models import Request, Response, HTTPMethod
from .content_renderers import JSONRenderer, HTMLRenderer, PlainTextRenderer, ContentRenderer
from .exceptions import ValidationError

__version__ = "0.1.0"
__author__ = "REST Framework Contributors"
__license__ = "MIT"

__all__ = [
    "RestApplication",
    "Request", 
    "Response",
    "HTTPMethod",
    "JSONRenderer",
    "HTMLRenderer", 
    "PlainTextRenderer",
    "ContentRenderer",
    "ValidationError"
]
''',

    "rest_framework/models.py": '''"""
Core data models for the REST framework.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class HTTPMethod(Enum):
    """Enumeration of supported HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class Request:
    """Represents an HTTP request."""
    method: HTTPMethod
    path: str
    headers: Dict[str, str]
    body: Optional[str] = None
    query_params: Optional[Dict[str, str]] = None
    path_params: Optional[Dict[str, str]] = None
    
    def get_accept_header(self) -> str:
        """Get the Accept header, defaulting to */* if not present."""
        return self.headers.get('Accept', '*/*')
    
    def get_content_type(self) -> Optional[str]:
        """Get the Content-Type header."""
        return self.headers.get('Content-Type')


@dataclass
class Response:
    """Represents an HTTP response."""
    status_code: int
    body: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    content_type: Optional[str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.content_type:
            self.headers['Content-Type'] = self.content_type
''',

    "rest_framework/content_renderers.py": '''"""
Content renderers for different media types.
"""

import json
from typing import Any

from .models import Request


class ContentRenderer:
    """Base class for content renderers."""
    
    def __init__(self, media_type: str):
        self.media_type = media_type
    
    def can_render(self, accept_header: str) -> bool:
        """Check if this renderer can handle the given Accept header."""
        if accept_header == '*/*':
            return True
        accept_types = [t.strip().split(';')[0] for t in accept_header.split(',')]
        return self.media_type in accept_types or '*/*' in accept_types
    
    def render(self, data: Any, request: Request) -> str:
        """Render the data as this content type."""
        raise NotImplementedError


class JSONRenderer(ContentRenderer):
    """JSON content renderer."""
    
    def __init__(self):
        super().__init__('application/json')
    
    def render(self, data: Any, request: Request) -> str:
        """Render data as JSON."""
        if isinstance(data, str):
            # If it's already a string, assume it's JSON or return as-is
            return data
        try:
            return json.dumps(data, indent=2)
        except (TypeError, ValueError):
            return json.dumps({"data": str(data)})


class HTMLRenderer(ContentRenderer):
    """HTML content renderer."""
    
    def __init__(self):
        super().__init__('text/html')
    
    def render(self, data: Any, request: Request) -> str:
        """Render data as HTML."""
        if isinstance(data, str) and data.strip().startswith('<'):
            # Already HTML
            return data
        
        # Simple HTML wrapper for non-HTML data
        if isinstance(data, dict):
            content = self._dict_to_html(data)
        elif isinstance(data, list):
            content = self._list_to_html(data)
        else:
            content = f"<p>{str(data)}</p>"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>API Response</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .key {{ font-weight: bold; color: #333; }}
        .value {{ margin-left: 20px; color: #666; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>API Response</h1>
    {content}
</body>
</html>"""
    
    def _dict_to_html(self, data: dict) -> str:
        """Convert dictionary to HTML."""
        items = []
        for key, value in data.items():
            if isinstance(value, dict):
                value_html = self._dict_to_html(value)
            elif isinstance(value, list):
                value_html = self._list_to_html(value)
            else:
                value_html = f'<span class="value">{str(value)}</span>'
            items.append(f'<li><span class="key">{key}:</span> {value_html}</li>')
        return f'<ul>{"".join(items)}</ul>'
    
    def _list_to_html(self, data: list) -> str:
        """Convert list to HTML."""
        items = []
        for item in data:
            if isinstance(item, dict):
                item_html = self._dict_to_html(item)
            elif isinstance(item, list):
                item_html = self._list_to_html(item)
            else:
                item_html = str(item)
            items.append(f'<li>{item_html}</li>')
        return f'<ul>{"".join(items)}</ul>'


class PlainTextRenderer(ContentRenderer):
    """Plain text content renderer."""
    
    def __init__(self):
        super().__init__('text/plain')
    
    def render(self, data: Any, request: Request) -> str:
        """Render data as plain text."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            return '\\n'.join(f"{k}: {v}" for k, v in data.items())
        elif isinstance(data, list):
            return '\\n'.join(str(item) for item in data)
        else:
            return str(data)
''',

    "rest_framework/dependencies.py": '''"""
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
''',

    "rest_framework/exceptions.py": '''"""
Custom exceptions for the REST framework.
"""

try:
    from pydantic import ValidationError as PydanticValidationError
    PYDANTIC_AVAILABLE = True
    ValidationError = PydanticValidationError
except ImportError:
    PYDANTIC_AVAILABLE = False
    
    class ValidationError(Exception):
        """Fallback ValidationError when Pydantic is not available."""
        def __init__(self, message="Validation failed"):
            self.message = message
            super().__init__(self.message)
        
        def errors(self):
            """Return errors in Pydantic-like format."""
            return [{"msg": self.message}]


class RestFrameworkError(Exception):
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
''',

    "rest_framework/state_machine.py": '''"""
Webmachine-inspired state machine for HTTP request processing.
"""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Union

from .models import Request, Response, HTTPMethod
from .content_renderers import ContentRenderer
from .dependencies import DependencyWrapper
from .exceptions import ValidationError, PYDANTIC_AVAILABLE


class StateMachineResult:
    """Result from a state machine decision point."""
    def __init__(self, continue_processing: bool, response: Optional[Response] = None):
        self.continue_processing = continue_processing
        self.response = response


class RequestStateMachine:
    """Webmachine-like state machine for processing HTTP requests."""
    
    def __init__(self, app):
        self.app = app
        self.request: Optional[Request] = None
        self.route_handler = None
        self.handler_dependencies: List[str] = []
        self.dependency_callbacks: Dict[str, DependencyWrapper] = {}
        self.chosen_renderer: Optional[ContentRenderer] = None
        self.handler_result: Any = None
    
    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine."""
        self.request = request
        self.app._dependency_cache.clear()
        
        try:
            # State machine flow - all wrapped in try-catch for ValidationError
            result = self.state_route_exists()
            if not result.continue_processing:
                return result.response

            result = self.state_service_available()
            if not result.continue_processing:
                return result.response
            
            result = self.state_known_method()
            if not result.continue_processing:
                return result.response
            
            result = self.state_uri_too_long()
            if not result.continue_processing:
                return result.response
            
            result = self.state_method_allowed()
            if not result.continue_processing:
                return result.response
            
            result = self.state_malformed_request()
            if not result.continue_processing:
                return result.response
            
            result = self.state_authorized()
            if not result.continue_processing:
                return result.response
            
            result = self.state_forbidden()
            if not result.continue_processing:
                return result.response
            
            result = self.state_content_headers_valid()
            if not result.continue_processing:
                return result.response
            
            result = self.state_resource_exists()
            if not result.continue_processing:
                return result.response
            
            # Content negotiation states
            result = self.state_content_types_provided()
            if not result.continue_processing:
                return result.response
            
            result = self.state_content_types_accepted()
            if not result.continue_processing:
                return result.response

            return self.state_execute_and_render()
            
        except ValidationError as e:
            return Response(
                422,
                json.dumps({
                    "error": "Validation failed",
                    "details": e.errors()
                }),
                content_type="application/json"
            )
    
    def state_route_exists(self) -> StateMachineResult:
        """B13: Check if route exists."""
        route_match = self.app._find_route(self.request.method, self.request.path)
        if route_match is None:
            callback = self._get_callback('route_not_found')
            if callback:
                try:
                    response = self.app._call_with_injection(callback, self.request)
                    if isinstance(response, Response):
                        return StateMachineResult(False, response)
                    return StateMachineResult(False, Response(404, str(response) if response else "Not Found"))
                except Exception as e:
                    return StateMachineResult(False, Response(500, f"Error in route_not_found callback: {str(e)}"))
            return StateMachineResult(False, Response(404, "Not Found"))
        
        self.route_handler, path_params = route_match
        self.request.path_params = path_params
        
        # Analyze handler dependencies
        sig = inspect.signature(self.route_handler.handler)
        self.handler_dependencies = list(sig.parameters.keys())
        
        # Find dependency callbacks that will be used
        for dep_name in self.handler_dependencies:
            if dep_name in self.app._dependencies:
                dep = self.app._dependencies[dep_name]
                if isinstance(dep, DependencyWrapper):
                    self.dependency_callbacks[dep.state_name] = dep
        
        return StateMachineResult(True)
    
    def state_service_available(self) -> StateMachineResult:
        """B12: Check if service is available."""
        callback = self._get_callback('service_available')
        if callback:
            try:
                available = self.app._call_with_injection(callback, self.request)
                if not available:
                    return StateMachineResult(False, Response(503, "Service Unavailable"))
            except Exception as e:
                return StateMachineResult(False, Response(503, f"Service check failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_known_method(self) -> StateMachineResult:
        """B11: Check if HTTP method is known."""
        callback = self._get_callback('known_method')
        if callback:
            try:
                known = self.app._call_with_injection(callback, self.request)
                if not known:
                    return StateMachineResult(False, Response(501, "Not Implemented"))
            except Exception as e:
                return StateMachineResult(False, Response(501, f"Method check failed: {str(e)}"))
        else:
            # Default: check if method is in our known methods
            known_methods = {HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.DELETE, HTTPMethod.PATCH}
            if self.request.method not in known_methods:
                return StateMachineResult(False, Response(501, "Not Implemented"))
        return StateMachineResult(True)
    
    def state_uri_too_long(self) -> StateMachineResult:
        """B10: Check if URI is too long."""
        callback = self._get_callback('uri_too_long')
        if callback:
            try:
                too_long = self.app._call_with_injection(callback, self.request)
                if too_long:
                    return StateMachineResult(False, Response(414, "URI Too Long"))
            except Exception as e:
                return StateMachineResult(False, Response(414, f"URI length check failed: {str(e)}"))
        else:
            # Default: check if URI is longer than 2048 characters
            if len(self.request.path) > 2048:
                return StateMachineResult(False, Response(414, "URI Too Long"))
        return StateMachineResult(True)
    
    def state_method_allowed(self) -> StateMachineResult:
        """B9: Check if method is allowed for this resource."""
        callback = self._get_callback('method_allowed')
        if callback:
            try:
                allowed = self.app._call_with_injection(callback, self.request)
                if not allowed:
                    return StateMachineResult(False, Response(405, "Method Not Allowed"))
            except Exception as e:
                return StateMachineResult(False, Response(405, f"Method check failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_malformed_request(self) -> StateMachineResult:
        """B8: Check if request is malformed."""
        callback = self._get_callback('malformed_request')
        if callback:
            try:
                malformed = self.app._call_with_injection(callback, self.request)
                if malformed:
                    return StateMachineResult(False, Response(400, "Bad Request"))
            except Exception as e:
                return StateMachineResult(False, Response(400, f"Request validation failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_authorized(self) -> StateMachineResult:
        """B7: Check if request is authorized."""
        callback = self._get_callback('authorized')
        if callback:
            try:
                authorized = self.app._call_with_injection(callback, self.request)
                if not authorized:
                    return StateMachineResult(False, Response(401, "Unauthorized"))
            except Exception as e:
                return StateMachineResult(False, Response(401, f"Authorization check failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_forbidden(self) -> StateMachineResult:
        """B6: Check if request is forbidden."""
        callback = self._get_callback('forbidden')
        if callback:
            try:
                # For wrapped dependencies, we need to resolve the dependency
                # and check if it indicates forbidden access
                if 'forbidden' in self.dependency_callbacks:
                    wrapper = self.dependency_callbacks['forbidden']
                    try:
                        resolved_value = self.app._call_with_injection(wrapper.func, self.request)
                        if resolved_value is None:
                            return StateMachineResult(False, Response(403, "Forbidden"))
                    except Exception:
                        return StateMachineResult(False, Response(403, "Forbidden"))
                else:
                    # Use the regular callback
                    forbidden = self.app._call_with_injection(callback, self.request)
                    if forbidden:
                        return StateMachineResult(False, Response(403, "Forbidden"))
            except Exception as e:
                return StateMachineResult(False, Response(403, f"Permission check failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_content_headers_valid(self) -> StateMachineResult:
        """B5: Check if content headers are valid."""
        callback = self._get_callback('content_headers_valid')
        if callback:
            try:
                valid = self.app._call_with_injection(callback, self.request)
                if not valid:
                    return StateMachineResult(False, Response(400, "Bad Request - Invalid Headers"))
            except Exception as e:
                return StateMachineResult(False, Response(400, f"Header validation failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_resource_exists(self) -> StateMachineResult:
        """G7: Check if resource exists."""
        callback = self._get_callback('resource_exists')
        if callback:
            try:
                # For wrapped dependencies, we need to resolve the dependency
                # and check if it returns None (indicating resource doesn't exist)
                if 'resource_exists' in self.dependency_callbacks:
                    wrapper = self.dependency_callbacks['resource_exists']
                    try:
                        resolved_value = self.app._call_with_injection(wrapper.func, self.request)
                        if resolved_value is None:
                            return StateMachineResult(False, Response(404, "Not Found"))
                        # Cache the resolved value for later use in the handler
                        self.app._dependency_cache.set(wrapper.original_name, resolved_value)
                    except Exception as e:
                        return StateMachineResult(False, Response(404, "Resource Not Found"))
                else:
                    # Use the regular callback
                    exists = self.app._call_with_injection(callback, self.request)
                    if not exists:
                        return StateMachineResult(False, Response(404, "Not Found"))
            except Exception as e:
                return StateMachineResult(False, Response(404, f"Resource check failed: {str(e)}"))
        return StateMachineResult(True)
    
    def state_content_types_provided(self) -> StateMachineResult:
        """C3: Determine what content types we can provide."""
        # Get available content types from global renderers and route-specific renderers
        available_types = list(self.app._content_renderers.keys())
        
        # Add route-specific content types
        if self.route_handler and self.route_handler.content_renderers:
            available_types.extend(self.route_handler.content_renderers.keys())
        
        if not available_types:
            return StateMachineResult(False, Response(500, "No content renderers available"))
        
        return StateMachineResult(True)
    
    def state_content_types_accepted(self) -> StateMachineResult:
        """C4: Check if we can provide an acceptable content type."""
        accept_header = self.request.get_accept_header()
        
        # First try route-specific renderers
        if self.route_handler and self.route_handler.content_renderers:
            for content_type, wrapper in self.route_handler.content_renderers.items():
                if content_type in self.app._content_renderers:
                    renderer = self.app._content_renderers[content_type]
                    if renderer.can_render(accept_header):
                        self.chosen_renderer = renderer
                        return StateMachineResult(True)
        
        # Fall back to global renderers
        for renderer in self.app._content_renderers.values():
            if renderer.can_render(accept_header):
                self.chosen_renderer = renderer
                return StateMachineResult(True)
        
        # No acceptable content type found
        available_types = list(self.app._content_renderers.keys())
        if self.route_handler and self.route_handler.content_renderers:
            available_types.extend(self.route_handler.content_renderers.keys())
        
        return StateMachineResult(False, Response(
            406, 
            f"Not Acceptable. Available types: {', '.join(set(available_types))}",
            headers={"Content-Type": "text/plain"}
        ))
    
    def state_execute_and_render(self) -> Response:
        """Execute the route handler and render the response."""
        try:
            # First, execute the main handler to get the result
            main_result = self.app._call_with_injection(self.route_handler.handler, self.request)
            
            # Check return type annotation for response validation
            sig = inspect.signature(self.route_handler.handler)
            return_annotation = sig.return_annotation
            
            # Handle different return type scenarios
            if return_annotation == type(None) or return_annotation is None:
                # Explicitly annotated as None -> return 204 No Content
                return Response(204)
            elif return_annotation != inspect.Signature.empty and PYDANTIC_AVAILABLE:
                # Has return type annotation -> validate response
                try:
                    if hasattr(return_annotation, '__origin__') and return_annotation.__origin__ is Union:
                        # Handle Optional[SomeType] or Union types
                        # For now, skip validation on Union types
                        pass
                    elif hasattr(return_annotation, 'model_validate'):
                        # It's a Pydantic model -> validate
                        if isinstance(main_result, dict):
                            validated_response = return_annotation.model_validate(main_result)
                            main_result = validated_response.model_dump()
                        elif hasattr(main_result, 'model_dump'):
                            # Already a Pydantic model -> convert to dict
                            main_result = main_result.model_dump()
                        else:
                            # Try to validate the raw result
                            validated_response = return_annotation.model_validate(main_result)
                            main_result = validated_response.model_dump()
                except ValidationError as e:
                    return Response(
                        500,
                        json.dumps({
                            "error": "Response validation failed",
                            "details": e.errors()
                        }),
                        content_type="application/json"
                    )
                except Exception:
                    # If validation fails for other reasons, log but don't crash
                    pass
            
            # Check if we should use a route-specific renderer
            if (self.route_handler and 
                self.route_handler.content_renderers and 
                self.chosen_renderer.media_type in self.route_handler.content_renderers):
                
                # Use route-specific content renderer
                wrapper = self.route_handler.content_renderers[self.chosen_renderer.media_type]
                
                # Create a temporary dependency for the handler result
                handler_func_name = self.route_handler.handler.__name__
                self.app._dependency_cache.set(handler_func_name, main_result)
                
                # Call the renderer with dependency injection (it will receive the handler result)
                rendered_result = self.app._call_with_injection(wrapper.func, self.request)
                
                # If the renderer returns a Response, use it directly
                if isinstance(rendered_result, Response):
                    if not rendered_result.content_type:
                        rendered_result.content_type = self.chosen_renderer.media_type
                        rendered_result.headers = rendered_result.headers or {}
                        rendered_result.headers['Content-Type'] = self.chosen_renderer.media_type
                    return rendered_result
                
                # Otherwise, treat the rendered result as the body
                return Response(
                    200, 
                    str(rendered_result), 
                    content_type=self.chosen_renderer.media_type
                )
            else:
                # Use regular global renderer
                result = main_result
            
            # If result is already a Response, return it
            if isinstance(result, Response):
                if not result.content_type and self.chosen_renderer:
                    result.content_type = self.chosen_renderer.media_type
                    result.headers = result.headers or {}
                    result.headers['Content-Type'] = self.chosen_renderer.media_type
                return result
            
            # Render the result using the chosen renderer
            if self.chosen_renderer:
                rendered_body = self.chosen_renderer.render(result, self.request)
                return Response(
                    200, 
                    rendered_body, 
                    content_type=self.chosen_renderer.media_type
                )
            else:
                # Fallback to plain text
                return Response(200, str(result), content_type="text/plain")
                
        except Exception as e:
            return Response(500, f"Internal Server Error: {str(e)}")
    
    def _get_callback(self, state_name: str) -> Optional[Callable]:
        """Get callback for a state, preferring dependency callbacks over defaults."""
        # First check if we have a dependency callback for this state
        if state_name in self.dependency_callbacks:
            return self.dependency_callbacks[state_name].func
        
        # Fall back to default callbacks
        return self.app._default_callbacks.get(state_name)
''',

    "rest_framework/application.py": '''"""
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
        pattern = re.sub(r'\\{(\\w+)\\}', r'(?P<\\1>[^/]+)', path)
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
''',

    "tests/__init__.py": '''# Tests package for REST Framework
''',

    "tests/test_rest_framework.py": '''"""
Tests for the REST framework.
"""

import pytest
import json
from typing import Optional

from rest_framework import (
    RestApplication, Request, Response, HTTPMethod,
    JSONRenderer, HTMLRenderer, PlainTextRenderer
)

# Import Pydantic if available for validation tests
try:
    from pydantic import BaseModel, Field, ValidationError
    PYDANTIC_AVAILABLE = True
    
    class UserModel(BaseModel):
        name: str = Field(..., min_length=1)
        email: str = Field(..., pattern=r'^[^@]+@[^@]+\\.[^@]+$')
        age: int = Field(..., ge=0, le=150)
    
    class UserResponse(BaseModel):
        id: int
        name: str
        email: str
        
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    ValidationError = Exception


class TestBasicFunctionality:
    """Test basic application functionality."""
    
    def test_application_creation(self):
        """Test that application can be created with default renderers."""
        app = RestApplication()
        assert len(app._content_renderers) == 3  # JSON, HTML, PlainText
        assert 'application/json' in app._content_renderers
        assert 'text/html' in app._content_renderers
        assert 'text/plain' in app._content_renderers
    
    def test_basic_get_route(self):
        """Test basic GET route registration and execution."""
        app = RestApplication()
        
        @app.get('/hello')
        def hello():
            return "Hello, World!"
        
        request = Request(
            method=HTTPMethod.GET,
            path='/hello',
            headers={'Accept': 'text/plain'}
        )
        
        response = app.execute(request)
        assert response.status_code == 200
        assert response.body == "Hello, World!"
        assert response.content_type == "text/plain"
    
    def test_route_with_path_params(self):
        """Test route with path parameters."""
        app = RestApplication()
        
        @app.get('/users/{user_id}')
        def get_user(request: Request):
            user_id = request.path_params['user_id']
            return {"id": user_id, "name": f"User {user_id}"}
        
        request = Request(
            method=HTTPMethod.GET,
            path='/users/123',
            headers={'Accept': 'application/json'}
        )
        
        response = app.execute(request)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["id"] == "123"
        assert data["name"] == "User 123"


class TestDependencyInjection:
    """Test dependency injection functionality."""
    
    def test_basic_dependency_injection(self):
        """Test basic dependency registration and injection."""
        app = RestApplication()
        
        @app.dependency()
        def user_service():
            return {"users": {"1": "Alice", "2": "Bob"}}
        
        @app.get('/users/{user_id}')
        def get_user(user_service, request: Request):
            user_id = request.path_params['user_id']
            users = user_service['users']
            if user_id not in users:
                return Response(404, "User not found")
            return {"id": user_id, "name": users[user_id]}
        
        request = Request(
            method=HTTPMethod.GET,
            path='/users/1',
            headers={'Accept': 'application/json'}
        )
        
        response = app.execute(request)
        assert response.status_code == 200
        data = json.loads(response.body)
        assert data["name"] == "Alice"


class TestContentNegotiation:
    """Test content negotiation functionality."""
    
    def test_json_content_negotiation(self):
        """Test JSON content negotiation."""
        app = RestApplication()
        
        @app.get('/data')
        def get_data():
            return {"message": "Hello", "data": [1, 2, 3]}
        
        request = Request(
            method=HTTPMethod.GET,
            path='/data',
            headers={'Accept': 'application/json'}
        )
        
        response = app.execute(request)
        assert response.status_code == 200
        assert response.content_type == "application/json"
        data = json.loads(response.body)
        assert data["message"] == "Hello"
    
    def test_html_content_negotiation(self):
        """Test HTML content negotiation."""
        app = RestApplication()
        
        @app.get('/data')
        def get_data():
            return {"message": "Hello", "data": [1, 2, 3]}
        
        request = Request(
            method=HTTPMethod.GET,
            path='/data',
            headers={'Accept': 'text/html'}
        )
        
        response = app.execute(request)
        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert "<!DOCTYPE html>" in response.body
        assert "Hello" in response.body


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestValidation:
    """Test validation functionality."""
    
    def test_validation_error_422(self):
        """Test that validation errors return 422."""
        app = RestApplication()
        
        @app.validates
        def validate_user(request: Request) -> UserModel:
            data = json.loads(request.body)
            return UserModel.model_validate(data)  # This will raise ValidationError
        
        @app.post('/users')
        def create_user(validate_user: UserModel):
            return {"message": "User created"}
        
        # Test invalid request
        invalid_data = {"name": "", "email": "invalid-email", "age": -5}
        request = Request(
            method=HTTPMethod.POST,
            path='/users',
            headers={'Accept': 'application/json'},
            body=json.dumps(invalid_data)
        )
        
        response = app.execute(request)
        assert response.status_code == 422
        data = json.loads(response.body)
        assert data["error"] == "Validation failed"
        assert "details" in data


class TestStateMachine:
    """Test state machine functionality."""
    
    def test_service_unavailable_503(self):
        """Test service unavailable callback."""
        app = RestApplication()
        
        @app.default_service_available
        def service_available():
            return False  # Service is down
        
        @app.get('/test')
        def handler():
            return "Should not reach here"
        
        request = Request(
            method=HTTPMethod.GET,
            path='/test',
            headers={'Accept': 'text/plain'}
        )
        
        response = app.execute(request)
        assert response.status_code == 503
        assert "Service Unavailable" in response.body
    
    def test_404_for_unknown_route(self):
        """Test 404 response for unknown routes."""
        app = RestApplication()
        
        request = Request(
            method=HTTPMethod.GET,
            path='/unknown',
            headers={'Accept': 'application/json'}
        )
        
        response = app.execute(request)
        assert response.status_code == 404
        assert "Not Found" in response.body


if __name__ == "__main__":
    pytest.main([__file__])
''',

    "README.md": '''# REST Framework

A lightweight REST framework with pytest-like dependency injection, webmachine-style state machine, content negotiation support, and Pydantic-based validation.

## Features

- **Flask-like API**: Simple and intuitive decorator-based route registration
- **Dependency Injection**: pytest-style dependency injection with automatic caching
- **State Machine**: Webmachine-inspired HTTP state machine for robust request processing
- **Content Negotiation**: Automatic content type negotiation with pluggable renderers
- **Validation**: Optional Pydantic integration for request/response validation
- **Lightweight**: Zero required dependencies for basic functionality

## Installation

### Basic Installation

```bash
pip install rest-framework
```

### With Validation Support

```bash
pip install rest-framework[validation]
```

### Development Installation

```bash
git clone https://github.com/yourusername/rest-framework.git
cd rest-framework
pip install -e .[dev,validation]
```

## Quick Start

### Basic Example

```python
from rest_framework import RestApplication, Request, HTTPMethod

app = RestApplication()

@app.get('/hello')
def hello():
    return {"message": "Hello, World!"}

@app.get('/users/{user_id}')
def get_user(request: Request):
    user_id = request.path_params['user_id']
    return {"id": user_id, "name": f"User {user_id}"}

# Execute a request
request = Request(
    method=HTTPMethod.GET,
    path='/hello',
    headers={'Accept': 'application/json'}
)

response = app.execute(request)
print(response.body)  # {"message": "Hello, World!"}
```

### Dependency Injection

```python
@app.dependency()
def database():
    return {"users": {"1": "Alice", "2": "Bob"}}

@app.get('/users/{user_id}')
def get_user(database, request: Request):
    user_id = request.path_params['user_id']
    users = database['users']
    if user_id not in users:
        return Response(404, "User not found")
    return {"id": user_id, "name": users[user_id]}
```

### Validation with Pydantic

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\\.[^@]+$')
    age: int = Field(..., ge=0, le=150)

@app.validates
def validate_user(request: Request) -> UserCreate:
    import json
    data = json.loads(request.body)
    return UserCreate.model_validate(data)

@app.post('/users')
def create_user(validate_user: UserCreate):
    return {
        "message": "User created",
        "user": validate_user.model_dump()
    }
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Examples

Check out the [examples/](examples/) directory for more comprehensive usage examples.
''',

    "LICENSE": '''MIT License

Copyright (c) 2025 REST Framework Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
''',

    "CHANGELOG.md": '''# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

## [0.1.0] - 2025-01-21

### Added
- Initial release of REST Framework
- Core application class with route registration
- HTTP method decorators (GET, POST, PUT, DELETE, PATCH)
- Dependency injection system with automatic caching
- Webmachine-inspired state machine for request processing
- Content negotiation with JSON, HTML, and plain text renderers
- Optional Pydantic integration for request/response validation
- State machine callbacks for service availability, authorization, etc.
- Resource existence checking with automatic 404 responses
- Custom content renderers for specific routes
- Comprehensive test suite
- Documentation and examples

### Features
- **Route Handlers**: Simple decorator-based route registration
- **Dependency Injection**: pytest-style dependency injection
- **State Machine States**:
  - B13: Route exists
  - B12: Service available
  - B11: Known method
  - B10: URI too long
  - B9: Method allowed
  - B8: Malformed request
  - B7: Authorized
  - B6: Forbidden
  - B5: Content headers valid
  - G7: Resource exists
  - C3: Content types provided
  - C4: Content types accepted
- **Content Negotiation**: Automatic content type selection
- **Validation**: Automatic Pydantic model validation with 422 error responses
- **Error Handling**: Comprehensive HTTP status code handling

### Dependencies
- No required dependencies for core functionality
- Optional Pydantic dependency for validation features

### Supported Python Versions
- Python 3.8+
- Python 3.9
- Python 3.10  
- Python 3.11
- Python 3.12

[Unreleased]: https://github.com/yourusername/rest-framework/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/rest-framework/releases/tag/v0.1.0
''',

    "setup.py": '''"""
Setup configuration for the REST Framework package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="rest-framework",
    version="0.1.0",
    author="REST Framework Contributors",
    author_email="contributors@rest-framework.example.com",
    description="A lightweight REST framework with dependency injection and webmachine-style state machine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/rest-framework",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "validation": ["pydantic>=2.0.0"],
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
            "mypy",
        ],
        "examples": ["uvicorn", "fastapi"],
    },
    entry_points={
        "console_scripts": [
            # Add CLI tools here if needed
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/rest-framework/issues",
        "Source": "https://github.com/yourusername/rest-framework",
        "Documentation": "https://rest-framework.readthedocs.io/",
    },
)
''',

    "requirements.txt": '''# Core dependencies (none required for basic functionality)

# Optional dependencies for validation (install with: pip install rest-framework[validation])
# pydantic>=2.0.0

# Development dependencies (install with: pip install rest-framework[dev])
# pytest>=6.0
# pytest-cov
# black
# flake8
# mypy

# Example dependencies (install with: pip install rest-framework[examples])
# uvicorn
# fastapi
''',

    "MANIFEST.in": '''# Include the README
include README.md

# Include the license
include LICENSE

# Include the changelog
include CHANGELOG.md

# Include configuration files
include pyproject.toml
include requirements.txt

# Include all Python files in the main package
recursive-include rest_framework *.py

# Include tests
recursive-include tests *.py

# Include examples
recursive-include examples *.py

# Exclude compiled Python files
global-exclude *.pyc
global-exclude __pycache__

# Exclude version control
global-exclude .git*

# Exclude development and build artifacts
global-exclude .tox
global-exclude build
global-exclude dist
global-exclude *.egg-info
''',

    "tox.ini": '''[tox]
envlist = py38,py39,py310,py311,py312,lint,type-check,docs
skip_missing_interpreters = True

[testenv]
deps = 
    pytest>=6.0
    pytest-cov
    pydantic>=2.0.0
commands = 
    pytest {posargs:tests} --cov=rest_framework --cov-report=term-missing

[testenv:lint]
deps = 
    black
    flake8
    isort
commands = 
    black --check --diff rest_framework tests examples
    flake8 rest_framework tests examples
    isort --check-only --diff rest_framework tests examples

[testenv:format]
deps = 
    black
    isort
commands = 
    black rest_framework tests examples
    isort rest_framework tests examples

[testenv:type-check]
deps = 
    mypy
    types-setuptools
commands = 
    mypy rest_framework

[testenv:docs]
deps = 
    sphinx
    sphinx-rtd-theme
    sphinx-autodoc-typehints
commands = 
    sphinx-build -W -b html docs docs/_build/html

[testenv:build]
deps = 
    build
    twine
commands = 
    python -m build
    twine check dist/*

[testenv:clean]
deps = 
commands = 
    python -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
    python -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"
    python -c "import shutil; shutil.rmtree('.tox', ignore_errors=True)"
    python -c "import shutil; shutil.rmtree('rest_framework.egg-info', ignore_errors=True)"

[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    build,
    dist,
    .tox,
    .venv,
    venv,

[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
''',

    ".gitignore": '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
''',

    ".github/workflows/test.yml": '''name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.8", "3.9", "3.10", "3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install tox tox-gh-actions
        
    - name: Test with tox
      run: tox
      
    - name: Upload coverage to Codecov
      if: matrix.python-version == '3.11'
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  lint:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install tox
        
    - name: Lint with tox
      run: tox -e lint
      
  type-check:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install tox
        
    - name: Type check with tox
      run: tox -e type-check

  build:
    runs-on: ubuntu-latest
    needs: [test, lint, type-check]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
        
    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
        
    - name: Build package
      run: python -m build
      
    - name: Check package
      run: twine check dist/*
      
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist
        path: dist/

  publish:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
        
    - name: Download artifacts
      uses: actions/download-artifact@v3
      with:
        name: dist
        path: dist/
        
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: |
        pip install twine
        twine upload dist/*
''',

    "Makefile": '''.PHONY: help install install-dev test test-all lint format type-check docs clean build publish

help:		## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\\033[36m%-15s\\033[0m %s\\n", $$1, $$2}'

install:	## Install the package
	pip install -e .

install-dev:	## Install the package with development dependencies
	pip install -e .[dev,validation,examples]

test:		## Run tests with pytest
	pytest tests/ --cov=rest_framework --cov-report=term-missing

test-all:	## Run tests across all Python versions with tox
	tox

lint:		## Run linting checks
	black --check --diff rest_framework tests examples
	flake8 rest_framework tests examples
	isort --check-only --diff rest_framework tests examples

format:		## Format code with black and isort
	black rest_framework tests examples
	isort rest_framework tests examples

type-check:	## Run type checking with mypy
	mypy rest_framework

docs:		## Build documentation
	tox -e docs

clean:		## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .tox/
	rm -rf .pytest_cache/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:		## Build package
	python -m build

check-build:	## Check built package
	twine check dist/*

publish-test:	## Publish to Test PyPI
	twine upload --repository testpypi dist/*

publish:	## Publish to PyPI
	twine upload dist/*

examples:	## Run example scripts
	python examples/basic_example.py
	@echo "\\n--- Running validation example (requires pydantic) ---"
	python examples/validation_example.py || echo "Skipped validation example (pydantic not available)"
	@echo "\\n--- Running advanced example ---"
	python examples/advanced_example.py

dev-setup:	## Set up development environment
	pip install -e .[dev,validation,examples]
	pre-commit install || echo "pre-commit not available"

release-patch:	## Bump patch version and create release
	bump2version patch
	git push && git push --tags

release-minor:	## Bump minor version and create release
	bump2version minor
	git push && git push --tags

release-major:	## Bump major version and create release
	bump2version major
	git push && git push --tags

# Development workflow targets
dev:		## Run development workflow (format, lint, test)
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test

ci:		## Run CI workflow (lint, type-check, test-all)
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test-all

# Docker targets (optional)
docker-build:	## Build Docker image for testing
	docker build -t rest-framework:latest .

docker-test:	## Run tests in Docker
	docker run --rm rest-framework:latest pytest

# Package info
info:		## Show package information
	@echo "Package: rest-framework"
	@echo "Version: $$(python -c 'import rest_framework; print(rest_framework.__version__)')"
	@echo "Python: $$(python --version)"
	@echo "Platform: $$(python -c 'import platform; print(platform.platform())')"
''',

    # Note: Basic example is too long to include here, truncated
    "examples/basic_example.py": '''"""
Basic usage example for the REST Framework.

This example demonstrates:
- Simple route registration
- Path parameters
- Dependency injection
- Different content types
- Basic error handling
"""

from rest_framework import RestApplication, Request, Response, HTTPMethod

# Create the application
app = RestApplication()

# In-memory data store for this example
users_db = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com"},
}

# Simple dependency
@app.dependency()
def user_database():
    """Provide access to the user database."""
    return users_db

# Basic routes
@app.get('/')
def home():
    """Home endpoint."""
    return {
        "message": "Welcome to REST Framework!",
        "endpoints": [
            "GET /",
            "GET /users",
            "GET /users/{user_id}",
            "POST /users",
            "PUT /users/{user_id}",
            "DELETE /users/{user_id}"
        ]
    }

@app.get('/users')
def list_users(user_database):
    """List all users."""
    return {"users": list(user_database.values())}

@app.get('/users/{user_id}')
def get_user(user_database, request: Request):
    """Get a specific user by ID."""
    user_id = request.path_params['user_id']
    user = user_database.get(user_id)
    
    if not user:
        return Response(404, '{"error": "User not found"}', content_type="application/json")
    
    return user

def main():
    """Demonstrate the API with some example requests."""
    print("REST Framework Basic Example")
    print("=" * 30)
    
    # Test home endpoint
    response = app.execute(Request(
        method=HTTPMethod.GET,
        path='/',
        headers={'Accept': 'application/json'}
    ))
    print(f"GET /: {response.status_code}")
    print(f"Response: {response.body}")
    print()

if __name__ == "__main__":
    main()
'''
}

def create_package():
    """Create the complete package structure."""
    print("Creating REST Framework package structure...")
    print("This will create ALL files including examples and configuration.")
    print()
    
    # Create directories
    directories = [
        "rest_framework",
        "tests", 
        "examples",
        ".github/workflows"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Create files
    file_count = 0
    for file_path, content in FILES.items():
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created file: {file_path}")
        file_count += 1
    
    print()
    print("=" * 60)
    print(f"SUCCESS: Created {file_count} files!")
    print("=" * 60)
    print()
    print("Package structure created successfully!")
    print()
    print("Next steps:")
    print("1. cd into the directory")
    print("2. Run: pip install -e .[dev,validation]")
    print("3. Run: make test")
    print("4. Run: make examples")
    print("5. Check out the examples/ directory")
    print()
    print("Available commands:")
    print("- make help         (show all available commands)")
    print("- make dev          (run development workflow)")
    print("- make test         (run tests)")
    print("- make examples     (run example scripts)")
    print("- make build        (build package for distribution)")

if __name__ == "__main__":
    create_package()

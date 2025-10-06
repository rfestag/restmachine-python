"""
Main application class for the REST framework.
"""

import inspect
import json
import logging
import os
import re
from urllib.parse import parse_qs
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
)

from .content_renderers import (
    ContentRenderer,
    HTMLRenderer,
    JSONRenderer,
    PlainTextRenderer,
)
from .dependencies import (
    AcceptsWrapper,
    ContentNegotiationWrapper,
    Dependency,
    DependencyCache,
    DependencyScope,
    DependencyWrapper,
    HeadersWrapper,
    ValidationWrapper,
)
from .exceptions import PYDANTIC_AVAILABLE, AcceptsParsingError
from .models import HTTPMethod, Request, Response
from .router import Router

# Set up logger for this module
logger = logging.getLogger(__name__)


class ErrorHandler:
    """Represents a custom error handler."""

    def __init__(self, handler: Callable, status_codes: Tuple[int, ...], content_type: Optional[str] = None, charset: Optional[str] = None):
        self.handler = handler
        self.status_codes = status_codes  # Empty tuple means default handler
        self.content_type = content_type  # None means default for that status code
        self.charset = charset  # Optional charset for Content-Type header

    def handles_status(self, status_code: int) -> bool:
        """Check if this handler handles the given status code."""
        if not self.status_codes:  # Default handler handles all codes
            return True
        return status_code in self.status_codes

    def matches_accept(self, accept_header: str) -> bool:
        """Check if this handler matches the Accept header."""
        if not self.content_type:  # Default handler matches all
            return True
        if not accept_header:
            return False
        # Simple check for content type in Accept header
        return self.content_type in accept_header or "*/*" in accept_header

    def get_full_content_type(self) -> Optional[str]:
        """Get the full Content-Type header value including charset if specified."""
        if not self.content_type:
            return None
        if self.charset:
            return f"{self.content_type}; charset={self.charset}"
        return self.content_type


class RouteHandler:
    """Represents a registered route and its handler."""

    def __init__(self, method: HTTPMethod, path: str, handler: Callable):
        self.method = method
        self.path = path
        self.handler = handler
        self.path_pattern = self._compile_path_pattern(path)
        self.content_renderers: Dict[str, ContentNegotiationWrapper] = {}
        self.validation_wrappers: List[ValidationWrapper] = []

        # Cache signature and parameter info for performance
        self.handler_signature = inspect.signature(handler)
        self.param_info: Dict[str, Optional[Type]] = {
            name: (param.annotation if param.annotation != inspect.Parameter.empty else None)
            for name, param in self.handler_signature.parameters.items()
        }

        # State machine callbacks resolved from handler dependencies
        # These are the ONLY route-specific lookups we maintain
        self.state_callbacks: Dict[str, Callable] = {}

        # Deprecated - kept for compatibility but should not be used
        self.dependencies: Dict[str, Union[Callable, DependencyWrapper, Dependency]] = {}
        self.validation_dependencies: Dict[str, ValidationWrapper] = {}
        self.headers_dependencies: Dict[str, HeadersWrapper] = {}
        self.accepts_dependencies: Dict[str, AcceptsWrapper] = {}

    def _compile_path_pattern(self, path: str) -> str:
        """Convert path with {param} syntax to a pattern for matching."""
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        return f"^{pattern}$"

    def add_content_renderer(self, content_type: str, wrapper: ContentNegotiationWrapper):
        """Add a content-specific renderer for this route."""
        self.content_renderers[content_type] = wrapper

    def add_validation_wrapper(self, wrapper: ValidationWrapper):
        self.validation_wrappers.append(wrapper)

    def resolve_state_callbacks(self, app: 'RestApplication') -> None:
        """Analyze handler dependencies and resolve state machine callbacks.

        This traverses the dependency graph to find state machine callbacks
        that apply to this route's handler, enabling O(1) lookup during request processing.
        """
        # State machine callback types to look for
        state_callback_types = {
            'resource_exists', 'resource_from_request', 'forbidden', 'authorized',
            'generate_etag', 'last_modified'
        }

        # Analyze each parameter of the handler
        for param_name in self.param_info.keys():
            # Check if this parameter is directly wrapped with a state callback
            # Two cases:
            # 1. param_name directly maps to a dependency (e.g., @dependency(name='foo'))
            # 2. param_name matches a state_name from a DependencyWrapper (e.g., generate_etag)

            # Case 1: Direct dependency lookup
            if param_name in app._dependencies:
                dep = app._dependencies[param_name]
                if isinstance(dep, DependencyWrapper) and dep.state_name in state_callback_types:
                    self.state_callbacks[dep.state_name] = dep.func

            # Case 2: Search for matching state_name across all dependencies
            if param_name in state_callback_types:
                for dep_key, dep_value in app._dependencies.items():
                    if isinstance(dep_value, DependencyWrapper) and dep_value.state_name == param_name:
                        self.state_callbacks[param_name] = dep_value.func
                        break


class RestApplication:
    """Main application class for the REST framework."""

    def __init__(self):
        self._dependencies: Dict[str, Union[Callable, DependencyWrapper, Dependency]] = {}
        self._validation_dependencies: Dict[str, ValidationWrapper] = {}
        self._headers_dependencies: Dict[str, HeadersWrapper] = {}
        self._accepts_dependencies: Dict[str, AcceptsWrapper] = {}
        self._default_callbacks: Dict[str, Callable] = {}
        self._dependency_cache = DependencyCache()
        self._content_renderers: Dict[str, ContentRenderer] = {}
        self._error_handlers: List[ErrorHandler] = []
        self._request_id_provider: Optional[Callable] = None
        self._trace_id_provider: Optional[Callable] = None
        self._startup_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []
        self._startup_executed = False  # Guard to prevent double execution

        # Create default root router - all routes go through this
        self._root_router = Router(app=self)

        # Add default content renderers
        self.add_content_renderer(JSONRenderer())
        self.add_content_renderer(HTMLRenderer())
        self.add_content_renderer(PlainTextRenderer())

        # Register built-in dependencies
        self._register_builtin_dependencies()

    def add_content_renderer(self, renderer: ContentRenderer):
        """Add a global content renderer."""
        self._content_renderers[renderer.media_type] = renderer

    def mount(self, prefix: str, router: Router):
        """Mount a router with a given prefix.

        Args:
            prefix: The path prefix for all routes in the mounted router
            router: The router to mount

        Example:
            app = RestApplication()
            users_router = Router()
            users_router.get("/")(lambda: {"users": []})
            users_router.get("/{id}")(lambda id: {"user": id})

            app.mount("/users", users_router)
            # This creates routes: GET /users/ and GET /users/{id}
        """
        self._root_router.mount(prefix, router)

    def _register_builtin_dependencies(self):
        """Register all built-in framework dependencies.

        This makes built-in dependencies use the same registration mechanism as
        user-defined dependencies, making the system more consistent and extensible.
        """
        # Simple built-in dependencies
        self._dependencies["request"] = Dependency(lambda request: request, scope="request")
        self._dependencies["body"] = Dependency(self._get_body_as_string, scope="request")
        self._dependencies["query_params"] = Dependency(lambda request: request.query_params or {}, scope="request")
        self._dependencies["path_params"] = Dependency(lambda request: request.path_params or {}, scope="request")
        self._dependencies["request_headers"] = Dependency(lambda request: request.headers, scope="request")
        self._dependencies["headers"] = Dependency(lambda request: request.headers, scope="request")  # Deprecated

        # Built-in dependencies that need application context
        self._dependencies["exception"] = Dependency(lambda: self._dependency_cache.get("exception"), scope="request")
        self._dependencies["response_headers"] = Dependency(self._get_response_headers, scope="request")
        self._dependencies["request_id"] = Dependency(self._get_request_id, scope="request")
        self._dependencies["trace_id"] = Dependency(self._get_trace_id, scope="request")

        # Body parser dependencies
        self._dependencies["json_body"] = Dependency(self._get_json_body, scope="request")
        self._dependencies["form_body"] = Dependency(self._get_form_body, scope="request")
        self._dependencies["multipart_body"] = Dependency(self._get_multipart_body, scope="request")
        self._dependencies["text_body"] = Dependency(self._get_text_body, scope="request")

    @staticmethod
    def _extract_charset_from_content_type(content_type: Optional[str]) -> Optional[str]:
        """Extract the charset parameter from a Content-Type header.

        Args:
            content_type: Content-Type header value (e.g., "application/json; charset=utf-8")

        Returns:
            The charset parameter value, or None if not specified

        Examples:
            >>> _extract_charset_from_content_type("application/json; charset=utf-8")
            "utf-8"
            >>> _extract_charset_from_content_type("text/html; charset=iso-8859-1")
            "iso-8859-1"
            >>> _extract_charset_from_content_type("application/json")
            None
        """
        if not content_type:
            return None

        # Split on semicolon to get parameters
        parts = content_type.split(';')
        for part in parts[1:]:  # Skip the media type itself
            part = part.strip()
            if part.lower().startswith('charset='):
                charset = part.split('=', 1)[1].strip()
                # Remove quotes if present
                if charset.startswith('"') and charset.endswith('"'):
                    charset = charset[1:-1]
                if charset.startswith("'") and charset.endswith("'"):
                    charset = charset[1:-1]
                return charset
        return None

    @staticmethod
    def _decode_bytes_with_fallback(data: bytes, content_type: Optional[str] = None) -> str:
        """Decode bytes using charset from Content-Type, with UTF-8 and Latin1 fallback.

        Args:
            data: Bytes to decode
            content_type: Optional Content-Type header value with charset parameter

        Returns:
            Decoded string

        Raises:
            UnicodeDecodeError: If all decoding attempts fail

        The decoding strategy is:
        1. If charset specified in Content-Type, try that first
        2. Fall back to UTF-8
        3. Fall back to Latin1 (ISO-8859-1) which never fails for valid bytes
        """
        if not data:
            return ""

        # Try charset from Content-Type first
        charset = RestApplication._extract_charset_from_content_type(content_type)
        if charset:
            try:
                return data.decode(charset)
            except (UnicodeDecodeError, LookupError):
                # Charset specified but failed - continue to fallbacks
                pass

        # Try UTF-8
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass

        # Fall back to Latin1 (ISO-8859-1) - this should always succeed
        # since Latin1 maps all byte values to Unicode code points
        return data.decode('latin1')

    def _get_body_as_string(self, request: Request) -> Optional[str]:
        """Built-in dependency provider for body as string.

        Reads from the request body stream and decodes using charset from Content-Type header.
        Falls back to UTF-8, then Latin1 if charset not specified.
        For backward compatibility with custom @app.accepts parsers.
        """
        if request.body is None:
            return None

        content_type = request.get_content_type()

        # If it's a stream, read and decode
        if hasattr(request.body, 'read'):
            raw_bytes = request.body.read()
            # Reset stream position for potential re-reading
            if hasattr(request.body, 'seek'):
                request.body.seek(0)
            return self._decode_bytes_with_fallback(raw_bytes, content_type) if raw_bytes else None

        # Legacy support for string/bytes (shouldn't happen with new code)
        if isinstance(request.body, bytes):
            return self._decode_bytes_with_fallback(request.body, content_type)
        return str(request.body) if request.body else None

    def _get_response_headers(self, request: Request) -> Dict[str, str]:
        """Built-in dependency provider for response_headers."""
        headers = self._dependency_cache.get("response_headers")
        if headers is None:
            # Get current route from cache (set during request processing)
            route = self._dependency_cache.get("__current_route__")
            headers = self._get_initial_headers(request, route)
            self._dependency_cache.set("response_headers", headers)
        return cast(Dict[str, str], headers)

    def _get_request_id(self, request: Request) -> str:
        """Built-in dependency provider for request_id."""
        if self._request_id_provider:
            # Get current route from cache
            route = self._dependency_cache.get("__current_route__")
            return cast(str, self._call_with_injection(self._request_id_provider, request, route))
        else:
            import uuid
            return str(uuid.uuid4())

    def _get_trace_id(self, request: Request) -> str:
        """Built-in dependency provider for trace_id."""
        if self._trace_id_provider:
            # Get current route from cache
            route = self._dependency_cache.get("__current_route__")
            return cast(str, self._call_with_injection(self._trace_id_provider, request, route))
        else:
            import uuid
            return str(uuid.uuid4())

    def _get_json_body(self, request: Request) -> Any:
        """Built-in dependency provider for json_body."""
        route = self._dependency_cache.get("__current_route__")
        return self._parse_body(request, route, "application/json")

    def _get_form_body(self, request: Request) -> Any:
        """Built-in dependency provider for form_body."""
        route = self._dependency_cache.get("__current_route__")
        return self._parse_body(request, route, "application/x-www-form-urlencoded")

    def _get_multipart_body(self, request: Request) -> Any:
        """Built-in dependency provider for multipart_body."""
        route = self._dependency_cache.get("__current_route__")
        return self._parse_body(request, route, "multipart/form-data")

    def _get_text_body(self, request: Request) -> Any:
        """Built-in dependency provider for text_body."""
        route = self._dependency_cache.get("__current_route__")
        return self._parse_body(request, route, "text/plain")

    def dependency(self, name: Optional[str] = None, scope: DependencyScope = "request"):
        """Decorator to register a dependency provider.

        Args:
            name: Optional name for the dependency. If not provided, uses the function name.
            scope: Dependency scope - "request" (default) or "session".
                   - "request": Cached per request, cleared between requests
                   - "session": Cached across all requests, never cleared automatically
        """

        def decorator(func: Callable):
            dep_name = name or func.__name__
            self._dependencies[dep_name] = Dependency(func, scope)
            return func

        return decorator

    # State machine callback decorators for dependencies
    def resource_exists(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with resource existence checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "resource_exists", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    def resource_from_request(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency for creating resource from request (for POST).

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "resource_from_request", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    def forbidden(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with forbidden checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "forbidden", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    def authorized(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with authorization checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "authorized", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    def default_headers(self, func: Callable):
        """Decorator to register a global headers manipulation function."""
        wrapper = HeadersWrapper(func, func.__name__)
        self._headers_dependencies[func.__name__] = wrapper
        self._dependencies[func.__name__] = func
        return func

    def generate_etag(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with ETag generation for conditional requests.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "generate_etag", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    def last_modified(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with Last-Modified date for conditional requests.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        wrapper = DependencyWrapper(func, "last_modified", func.__name__, scope)
        self._dependencies[func.__name__] = wrapper
        return func

    # Content negotiation decorators
    def provides(self, content_type: str, scope: DependencyScope = "request", charset: Optional[str] = None):
        """Decorator to register a content-type specific renderer for an endpoint.

        Provides better API symmetry with accepts() for content negotiation.

        NOTE: This still requires the decorator to be placed after the route decorator
        to attach the renderer to the correct route.

        Args:
            content_type: The content type this renderer provides
            scope: Dependency scope - "request" (default) or "session"
            charset: Optional charset to include in Content-Type header (e.g., "utf-8")
        """

        def decorator(func: Callable):
            # Find the most recently added route in the root router
            if self._root_router._routes:
                route = self._root_router._routes[-1]
                handler_name = route.handler.__name__
                wrapper = ContentNegotiationWrapper(func, content_type, handler_name, charset=charset)
                route.add_content_renderer(content_type, wrapper)

            # Also register this as a dependency so it can be injected
            self._dependencies[func.__name__] = Dependency(func, scope)
            return func

        return decorator

    # Simplified validation decorator - just expects Pydantic model return
    def validates(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to mark a function as returning a validated Pydantic model.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        if not PYDANTIC_AVAILABLE:
            raise ImportError("Pydantic is required for validation features")

        wrapper = ValidationWrapper(func, scope)
        self._validation_dependencies[func.__name__] = wrapper
        self._dependencies[func.__name__] = Dependency(func, scope)
        return func

    def accepts(self, content_type: str, scope: DependencyScope = "request"):
        """Decorator to register a global content-type specific body parser.

        Args:
            content_type: The content type this parser handles
            scope: Dependency scope - "request" (default) or "session"
        """

        def decorator(func: Callable):
            wrapper = AcceptsWrapper(func, content_type, func.__name__)
            self._accepts_dependencies[content_type] = wrapper
            self._dependencies[func.__name__] = Dependency(func, scope)
            return func

        return decorator

    # Default state machine callbacks
    def default_service_available(self, func: Callable):
        """Register a default service_available callback."""
        self._default_callbacks["service_available"] = func
        return func

    def default_known_method(self, func: Callable):
        """Register a default known_method callback."""
        self._default_callbacks["known_method"] = func
        return func

    def default_uri_too_long(self, func: Callable):
        """Register a default uri_too_long callback."""
        self._default_callbacks["uri_too_long"] = func
        return func

    def default_method_allowed(self, func: Callable):
        """Register a default method_allowed callback."""
        self._default_callbacks["method_allowed"] = func
        return func

    def default_malformed_request(self, func: Callable):
        """Register a default malformed_request callback."""
        self._default_callbacks["malformed_request"] = func
        return func

    def default_authorized(self, func: Callable):
        """Register a default authorized callback."""
        self._default_callbacks["authorized"] = func
        return func

    def default_forbidden(self, func: Callable):
        """Register a default forbidden callback."""
        self._default_callbacks["forbidden"] = func
        return func

    def default_content_headers_valid(self, func: Callable):
        """Register a default content_headers_valid callback."""
        self._default_callbacks["content_headers_valid"] = func
        return func

    def default_resource_exists(self, func: Callable):
        """Register a default resource_exists callback."""
        self._default_callbacks["resource_exists"] = func
        return func

    def default_route_not_found(self, func: Callable):
        """Register a default route_not_found callback."""
        self._default_callbacks["route_not_found"] = func
        return func

    # Error handler decorators
    def handles_error(self, *status_codes: int):
        """Decorator to register a custom error handler.

        Args:
            *status_codes: HTTP status codes this handler handles.
                          If empty, this becomes the default handler for all errors.

        Example::

            @app.handles_error(404)
            def custom_404(request):
                return {"error": "Resource not found", "code": "NOT_FOUND"}

            @app.handles_error()  # Default handler for all errors
            def default_error(request, exception):
                return {"error": "Something went wrong"}

            @app.handles_error(401, 403)  # Handle multiple codes
            def auth_error(request):
                return {"error": "Authentication required"}
        """
        def decorator(func: Callable):
            handler = ErrorHandler(func, status_codes, content_type=None)
            self._error_handlers.append(handler)
            return func
        return decorator

    def error_provides(self, content_type: str, charset: Optional[str] = None):
        """Decorator to specify content type for an error handler.

        Must be used with handles_error decorator. This creates a content-type-specific
        error handler separate from regular route handlers to avoid confusion.

        IMPORTANT: This decorator must be placed ABOVE @handles_error (applied first).

        Args:
            content_type: The content type this error handler provides
            charset: Optional charset to include in Content-Type header (e.g., "utf-8")

        Example::

            @app.error_provides("text/html", charset="utf-8")
            @app.handles_error(404)
            def custom_404_html(request):
                return "<h1>404 - Not Found</h1>"

            @app.error_provides("application/json")
            @app.handles_error(404)
            def custom_404_json(request):
                return {"error": "Not found"}
        """
        def decorator(func: Callable):
            # Find the most recently added error handler and update its content type
            if self._error_handlers:
                # The decorator is applied bottom-up, so the last handler added
                # is the one we just registered with @handles_error
                handler = self._error_handlers[-1]
                if handler.handler == func:
                    # Create a new handler with the same status codes but specific content type
                    new_handler = ErrorHandler(func, handler.status_codes, content_type, charset=charset)
                    # Replace the last handler
                    self._error_handlers[-1] = new_handler
            return func
        return decorator

    # Request/Trace ID decorators
    def request_id(self, func: Callable):
        """Decorator to register a custom request ID generator.

        The decorated function should accept a Request object and return a string.
        If not provided, a default UUID-based generator will be used.

        Example::

            @app.request_id
            def generate_request_id(request):
                # Check for existing request ID in headers
                return request.headers.get('X-Request-ID', str(uuid.uuid4()))
        """
        self._request_id_provider = func
        return func

    def trace_id(self, func: Callable):
        """Decorator to register a custom trace ID generator.

        The decorated function should accept a Request object and return a string.
        If not provided, a default UUID-based generator will be used.

        Example::

            @app.trace_id
            def generate_trace_id(request):
                # Check for existing trace ID in headers
                return request.headers.get('X-Trace-ID', str(uuid.uuid4()))
        """
        self._trace_id_provider = func
        return func

    # HTTP method decorators
    def get(self, path: str):
        """Decorator to register a GET route handler on the root router."""
        return self._root_router.get(path)

    def post(self, path: str):
        """Decorator to register a POST route handler on the root router."""
        return self._root_router.post(path)

    def put(self, path: str):
        """Decorator to register a PUT route handler on the root router."""
        return self._root_router.put(path)

    def delete(self, path: str):
        """Decorator to register a DELETE route handler on the root router."""
        return self._root_router.delete(path)

    def patch(self, path: str):
        """Decorator to register a PATCH route handler on the root router."""
        return self._root_router.patch(path)

    def _resolve_dependency(
        self, param_name: str, param_type: Optional[Type], request: Optional[Request], route: Optional[RouteHandler] = None
    ) -> Any:
        """Resolve a dependency by name and type.

        Raises ValueError if the dependency cannot be found, which indicates a programming error.

        Args:
            param_name: Name of the parameter to resolve
            param_type: Type annotation of the parameter (if available)
            request: Request object (can be None for shutdown handlers)
            route: Route handler (can be None for shutdown handlers)
        """
        # Store route in cache so built-in dependencies can access it
        if route is not None:
            self._dependency_cache.set("__current_route__", route, "request")

        # Get dependency scope
        dep_scope = self._get_dependency_scope(param_name, route)

        # Check cache first (using appropriate scope)
        cached_value = self._dependency_cache.get(param_name, dep_scope)
        if cached_value is not None:
            return cached_value

        # Handle Request type annotation or "request" parameter name
        if param_type == Request or param_name == "request":
            if request is None:
                raise ValueError("Cannot inject 'request' in shutdown handlers - no request context available")
            self._dependency_cache.set("request", request, dep_scope)
            return request

        # Check if the parameter name is in path_params
        if request is not None and request.path_params and param_name in request.path_params:
            path_value = request.path_params[param_name]
            self._dependency_cache.set(param_name, path_value, dep_scope)
            return path_value

        # Check if this is a registered dependency (built-in or custom)
        if self._dependency_exists(param_name, route):
            resolved_value = self._resolve_registered_dependency(param_name, request, route)
            self._dependency_cache.set(param_name, resolved_value, dep_scope)
            return resolved_value

        # Check if this is an accepts parser dependency (only if we have a request)
        if request is not None and self._accepts_dependency_exists(param_name, request, route):
            accepts_value = self._resolve_accepts_dependency(param_name, request, route)
            self._dependency_cache.set(param_name, accepts_value, dep_scope)
            return accepts_value

        # Dependency not found - this is a programming error
        raise ValueError(f"Unable to resolve dependency: {param_name}")

    def _get_dependency_scope(self, param_name: str, route: Optional[RouteHandler] = None) -> DependencyScope:
        """Get the scope for a dependency.

        Args:
            param_name: Name of the dependency
            route: Optional route (unused, kept for compatibility)

        Returns:
            The scope ("request" or "session"), defaults to "request"
        """
        # Check global dependencies
        if param_name in self._dependencies:
            dep_or_wrapper = self._dependencies[param_name]
            if hasattr(dep_or_wrapper, 'scope'):
                return dep_or_wrapper.scope

        # Check validation dependencies
        if param_name in self._validation_dependencies:
            validation_wrapper = self._validation_dependencies[param_name]
            if hasattr(validation_wrapper, 'scope'):
                return validation_wrapper.scope

        # Default to request scope
        return "request"

    def _dependency_exists(self, param_name: str, route: Optional[RouteHandler] = None) -> bool:
        """Check if a registered dependency exists."""
        return param_name in self._dependencies

    def _resolve_registered_dependency(self, param_name: str, request: Optional[Request], route: Optional[RouteHandler]) -> Any:
        """Resolve a registered dependency (built-in or custom).

        Returns the resolved value, which may be None for some dependencies like 'exception'.
        Assumes _dependency_exists() was called first and returned True.
        """
        dep_or_wrapper = self._dependencies[param_name]
        validation_dependency = self._validation_dependencies.get(param_name)

        if isinstance(dep_or_wrapper, DependencyWrapper):
            return self._call_with_injection(dep_or_wrapper.func, request, route)
        elif isinstance(dep_or_wrapper, Dependency):
            # Unwrap the Dependency wrapper
            if validation_dependency is not None:
                result = self._call_with_injection(dep_or_wrapper.func, request, route)
                if hasattr(result, "model_validate") or hasattr(result, "model_dump"):
                    return result
                else:
                    raise ValueError(f"Validation function {param_name} must return a Pydantic model")
            else:
                return self._call_with_injection(dep_or_wrapper.func, request, route)
        elif validation_dependency is not None:
            result = self._call_with_injection(dep_or_wrapper, request, route)
            if hasattr(result, "model_validate") or hasattr(result, "model_dump"):
                return result
            else:
                raise ValueError(f"Validation function {param_name} must return a Pydantic model")
        else:
            return self._call_with_injection(dep_or_wrapper, request, route)

    def _accepts_dependency_exists(self, param_name: str, request: Request, route: Optional[RouteHandler]) -> bool:
        """Check if an accepts parser dependency exists for this request."""
        content_type = request.get_content_type()
        if not content_type:
            return False

        base_content_type = content_type.split(';')[0].strip().lower()

        # Check global accepts dependencies
        accepts_wrapper = self._accepts_dependencies.get(base_content_type)

        return accepts_wrapper is not None and (param_name == accepts_wrapper.name or param_name in ['parsed_data', 'parsed_body'])

    def _resolve_accepts_dependency(self, param_name: str, request: Request, route: Optional[RouteHandler]) -> Any:
        """Resolve accepts parser dependencies.

        Assumes _accepts_dependency_exists() was called first and returned True.
        Returns the resolved value, which may be None.
        """
        content_type = request.get_content_type()
        if content_type is None:
            raise ValueError(f"Content-Type header is required for dependency {param_name}")

        base_content_type = content_type.split(';')[0].strip().lower()

        # Check global accepts dependencies
        accepts_wrapper: Optional[AcceptsWrapper] = self._accepts_dependencies.get(base_content_type)

        if accepts_wrapper is None:
            raise ValueError(f"Accepts parser for {base_content_type} not found")

        try:
            return self._call_with_injection(accepts_wrapper.func, request, route)
        except Exception as e:
            raise AcceptsParsingError(
                f"Failed to parse {base_content_type} request body: {str(e)}",
                original_exception=e
            )

    def _call_with_injection(self, func: Callable, request: Optional[Request], route: Optional[RouteHandler] = None) -> Any:
        """Call a function with dependency injection."""
        # Use cached signature if this is the route handler
        if route and func == route.handler:
            sig = route.handler_signature
        else:
            sig = inspect.signature(func)

        kwargs = {}

        for param_name, param in sig.parameters.items():
            param_type = (
                param.annotation
                if param.annotation != inspect.Parameter.empty
                else None
            )
            resolved_value = self._resolve_dependency(param_name, param_type, request, route)
            kwargs[param_name] = resolved_value

        return func(**kwargs)

    def _get_initial_headers(self, request: Request, route: Optional[RouteHandler]) -> Dict[str, str]:
        """Get initial headers with Vary header pre-calculated."""
        vary_values = []

        if request.headers.get("Authorization"):
            vary_values.append("Authorization")

        # Check if multiple content types are available
        available_types = set(self._content_renderers.keys())
        if route and route.content_renderers:
            available_types.update(route.content_renderers.keys())

        if len(available_types) > 1:
            vary_values.append("Accept")

        return {"Vary": ", ".join(vary_values)} if vary_values else {}

    def _parse_body(self, request: Request, route: Optional[RouteHandler], expected_content_type: str) -> Any:
        """Parse request body based on content type using accepts dependencies or built-in parsers."""
        if not request.body:
            return None

        content_type = request.get_content_type() or "application/octet-stream"
        base_content_type = content_type.split(';')[0].strip().lower()

        # Check for custom accepts parser first
        accepts_wrapper = self._get_accepts_wrapper(base_content_type, route)
        if accepts_wrapper:
            try:
                return self._call_with_injection(accepts_wrapper.func, request, route)
            except Exception as e:
                raise AcceptsParsingError(
                    f"Failed to parse {base_content_type} request body: {str(e)}",
                    original_exception=e
                )

        # Validate content type is supported
        if base_content_type != expected_content_type:
            supported_types = self._get_supported_content_types(route)
            if base_content_type not in supported_types:
                raise ValueError("Unsupported Media Type - 415")

        # Use built-in parsers
        return self._parse_with_builtin_parser(request.body, expected_content_type)

    def _get_accepts_wrapper(self, content_type: str, route: Optional[RouteHandler]):
        """Get accepts wrapper for content type from global dependencies."""
        return self._accepts_dependencies.get(content_type)

    def _get_supported_content_types(self, route: Optional[RouteHandler]) -> set:
        """Get all supported content types for validation."""
        supported_types = set(self._accepts_dependencies.keys())
        supported_types.update([
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain"
        ])
        return supported_types

    def _parse_json_from_stream(self, body, content_type: str) -> Any:
        """Parse JSON from a stream."""
        import io
        # Extract charset from Content-Type, default to UTF-8, fallback to Latin1
        charset = self._extract_charset_from_content_type(content_type) or 'utf-8'
        try:
            # Wrap bytes stream with TextIOWrapper for JSON parser
            text_stream = io.TextIOWrapper(body, encoding=charset)
            return json.load(text_stream)
        except (UnicodeDecodeError, LookupError):
            # If charset fails, try UTF-8
            body.seek(0)  # Reset stream
            try:
                text_stream = io.TextIOWrapper(body, encoding='utf-8')
                return json.load(text_stream)
            except UnicodeDecodeError:
                # Fall back to Latin1
                body.seek(0)
                text_stream = io.TextIOWrapper(body, encoding='latin1')
                return json.load(text_stream)

    def _parse_form_from_stream(self, body, content_type: str) -> dict:
        """Parse form data from a stream."""
        raw_bytes = body.read()
        body_str = self._decode_bytes_with_fallback(raw_bytes, content_type)
        parsed = parse_qs(body_str, keep_blank_values=True)
        return {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}

    def _parse_text_from_stream(self, body, content_type: str) -> str:
        """Parse text from a stream."""
        raw_bytes: bytes = body.read()
        return self._decode_bytes_with_fallback(raw_bytes, content_type)

    def _parse_multipart_from_stream(self, body) -> dict:
        """Parse multipart data from a stream."""
        raw_bytes = body.read()
        return {"_raw_body": raw_bytes, "_content_type": "multipart/form-data"}

    def _parse_stream_body(self, body, content_type: str) -> Any:
        """Parse body from a stream based on content type.

        Args:
            body: The body stream to parse
            content_type: Full Content-Type header value (may include charset parameter)
        """
        # Extract base content type (without parameters like charset)
        base_content_type = content_type.split(';')[0].strip()

        if base_content_type == "application/json":
            return self._parse_json_from_stream(body, content_type)
        elif base_content_type == "application/x-www-form-urlencoded":
            return self._parse_form_from_stream(body, content_type)
        elif base_content_type == "multipart/form-data":
            return self._parse_multipart_from_stream(body)
        elif base_content_type == "text/plain":
            return self._parse_text_from_stream(body, content_type)
        else:
            # Unknown content type - return raw bytes
            return body.read()

    def _parse_legacy_body(self, body, content_type: str) -> Any:
        """Parse legacy string/bytes body (for backwards compatibility)."""
        body_str = self._decode_bytes_with_fallback(body, content_type) if isinstance(body, bytes) else body

        # Extract base content type (without parameters like charset)
        base_content_type = content_type.split(';')[0].strip()

        if base_content_type == "application/json":
            return json.loads(body_str)
        elif base_content_type == "application/x-www-form-urlencoded":
            parsed = parse_qs(body_str, keep_blank_values=True)
            return {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}
        elif base_content_type == "multipart/form-data":
            return {"_raw_body": body_str, "_content_type": "multipart/form-data"}
        elif base_content_type == "text/plain":
            return body_str
        return body_str

    def _parse_with_builtin_parser(self, body, content_type: str) -> Any:
        """Parse body using built-in parsers.

        Args:
            body: BinaryIO stream or bytes-like object containing the request body
            content_type: The expected content type

        Returns:
            Parsed body data
        """
        try:
            # Handle None/empty body
            if body is None:
                return None

            # Parse stream or legacy body
            if hasattr(body, 'read'):
                return self._parse_stream_body(body, content_type)
            else:
                return self._parse_legacy_body(body, content_type)

        except json.JSONDecodeError as e:
            raise AcceptsParsingError(
                f"Failed to parse {content_type} request body: Invalid JSON - {str(e)}",
                original_exception=e
            )
        except UnicodeDecodeError as e:
            raise AcceptsParsingError(
                f"Failed to parse {content_type} request body: Invalid UTF-8 encoding - {str(e)}",
                original_exception=e
            )
        except Exception as e:
            if content_type == "application/x-www-form-urlencoded":
                raise AcceptsParsingError(
                    f"Failed to parse {content_type} request body: Invalid form data - {str(e)}",
                    original_exception=e
                )
            else:
                raise AcceptsParsingError(
                    f"Failed to parse {content_type} request body: {str(e)}",
                    original_exception=e
                )

    def _find_route(
        self, method: HTTPMethod, path: str
    ) -> Optional[Tuple[RouteHandler, Dict[str, str]]]:
        """Find a matching route for the given method and path.

        Uses the root router's trie-based matching for efficient O(k) lookup.
        """
        return self._root_router.match_route(path, method)

    def _path_has_routes(self, path: str) -> bool:
        """Check if any route exists for the given path (regardless of method).

        Uses the root router's trie-based lookup for efficient checking.
        """
        return self._root_router.has_path(path)

    def on_startup(self, func: Optional[Callable] = None):
        """Register a startup handler to run when the application starts.

        Can be used as a decorator::

            @app.on_startup
            async def database():
                print("Opening database connection...")
                return create_db_connection()

            @app.get("/users")
            def get_users(database):  # database from startup is injected here
                return database.query("SELECT * FROM users")

        Or called directly::

            app.on_startup(my_startup_function)

        Startup handlers are automatically registered as session-scoped dependencies,
        so their return values can be injected into route handlers and other dependencies.
        Handlers can be sync or async functions.
        """
        def decorator(f: Callable) -> Callable:
            self._startup_handlers.append(f)
            # Also register as a session-scoped dependency so return value can be injected
            self._dependencies[f.__name__] = Dependency(f, scope="session")
            return f

        if func is None:
            return decorator
        else:
            return decorator(func)

    def on_shutdown(self, func: Optional[Callable] = None):
        """Register a shutdown handler to run when the application stops.

        Can be used as a decorator::

            @app.on_shutdown
            async def shutdown():
                print("Application shutting down...")
                # Close connections, cleanup resources, etc.

        Or called directly::

            app.on_shutdown(my_shutdown_function)

        Handlers can be sync or async functions.
        """
        def decorator(f: Callable) -> Callable:
            self._shutdown_handlers.append(f)
            return f

        if func is None:
            return decorator
        else:
            return decorator(func)

    async def startup(self):
        """Run all registered startup handlers.

        This is called automatically by the ASGI adapter when the
        application starts. Handlers are run in registration order.

        The return values from startup handlers are cached in the session
        scope, making them available as dependencies throughout the application
        lifetime without being re-executed.

        Raises any exceptions from startup handlers.
        """
        # Guard against double execution
        if self._startup_executed:
            return
        self._startup_executed = True

        for handler in self._startup_handlers:
            # Execute the handler and get its return value
            if inspect.iscoroutinefunction(handler):
                result = await handler()
            else:
                result = handler()

            # Cache the result in session scope so it can be injected as a dependency
            # without re-executing the handler on the first request
            self._dependency_cache.set(handler.__name__, result, "session")

    async def shutdown(self):
        """Run all registered shutdown handlers.

        This is called automatically by the ASGI adapter when the
        application stops. Handlers are run in registration order.

        Shutdown handlers support dependency injection, allowing them to
        inject session-scoped dependencies (like database connections from
        startup handlers) for proper cleanup.

        Logs exceptions from shutdown handlers but does not raise them.
        """
        for handler in self._shutdown_handlers:
            try:
                # Resolve dependencies for the shutdown handler
                sig = inspect.signature(handler)
                kwargs = {}

                for param_name, param in sig.parameters.items():
                    param_type = (
                        param.annotation
                        if param.annotation != inspect.Parameter.empty
                        else None
                    )
                    # Pass None for request since shutdown handlers don't have request context
                    resolved_value = self._resolve_dependency(param_name, param_type, None, None)
                    kwargs[param_name] = resolved_value

                # Call the handler with resolved dependencies
                if inspect.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in shutdown handler: {e}", exc_info=True)

    def startup_sync(self):
        """Synchronous wrapper for startup().

        This is called automatically by the AWS Lambda adapter during cold start
        to execute startup handlers in a synchronous context (module-level initialization).

        Uses anyio.run() to execute the async startup() method synchronously.
        """
        import anyio
        anyio.run(self.startup)

    def shutdown_sync(self):
        """Synchronous wrapper for shutdown().

        This can be called by AWS Lambda Extensions or other synchronous shutdown hooks
        to execute shutdown handlers in a synchronous context.

        Uses anyio.run() to execute the async shutdown() method synchronously.
        """
        import anyio
        anyio.run(self.shutdown)

    def execute(self, request: Request) -> Response:
        """Execute a request through the state machine."""
        try:
            # Create a new state machine for each request to avoid state pollution
            from restmachine.state_machine import RequestStateMachine
            state_machine = RequestStateMachine(self)
            return state_machine.process_request(request)
        except Exception as e:
            logger.error(f"Unhandled exception processing {request.method.value} {request.path}: {e}")
            return Response(
                500,
                json.dumps({"error": "Internal server error"}),
                content_type="application/json"
            )

    def _is_pydantic_model(self, annotation) -> bool:
        """Check if the annotation is a Pydantic model."""
        if not PYDANTIC_AVAILABLE or annotation is None:
            return False
        try:
            return hasattr(annotation, "model_fields") and hasattr(
                annotation, "model_validate"
            )
        except (TypeError, AttributeError):
            return False

    def _is_optional_type(self, annotation) -> Tuple[bool, Type]:
        """Check if type annotation is Optional and return the inner type."""
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T] which is Union[T, None]
                inner_type = args[0] if args[1] is type(None) else args[1]
                return True, inner_type
        return False, annotation

    def _get_pydantic_schema(self, model_class) -> Dict[str, Any]:
        """Extract JSON schema from Pydantic model and convert to OpenAPI 3.0 compliant format."""
        if not self._is_pydantic_model(model_class):
            return {"type": "object"}
        try:
            pydantic_schema = model_class.model_json_schema()
            return self._convert_pydantic_schema_to_openapi(pydantic_schema)
        except (AttributeError, TypeError):
            return {"type": "object"}

    def _convert_pydantic_schema_to_openapi(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pydantic JSON schema to OpenAPI 3.0 compliant schema."""
        if isinstance(schema, dict):
            converted = {}
            for key, value in schema.items():
                if key == "anyOf" and isinstance(value, list):
                    # Handle anyOf patterns for optional fields
                    converted.update(self._convert_anyof_to_nullable(value))
                elif key == "exclusiveMinimum" and isinstance(value, (int, float)):
                    # Convert exclusiveMinimum from number to boolean + minimum
                    converted["minimum"] = value
                    converted["exclusiveMinimum"] = True
                elif key == "exclusiveMaximum" and isinstance(value, (int, float)):
                    # Convert exclusiveMaximum from number to boolean + maximum
                    converted["maximum"] = value
                    converted["exclusiveMaximum"] = True
                elif isinstance(value, dict):
                    # Recursively convert nested schemas
                    converted[key] = self._convert_pydantic_schema_to_openapi(value)
                elif isinstance(value, list):
                    # Process lists (like in anyOf, oneOf, etc.)
                    converted[key] = [
                        self._convert_pydantic_schema_to_openapi(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    converted[key] = value
            return converted
        else:
            return schema

    def _convert_anyof_to_nullable(self, anyof_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert anyOf with null to nullable field for OpenAPI 3.0."""
        result = {}

        # Check if this is the pattern: anyOf: [{"type": "someType"}, {"type": "null"}]
        if len(anyof_list) == 2:
            type_schema = None
            has_null = False

            for item in anyof_list:
                if isinstance(item, dict):
                    if item.get("type") == "null":
                        has_null = True
                    else:
                        type_schema = item

            if has_null and type_schema:
                # Convert to nullable field
                result.update(self._convert_pydantic_schema_to_openapi(type_schema))
                result["nullable"] = True
                return result

        # If it's not the nullable pattern, keep as anyOf but convert each schema
        result["anyOf"] = [self._convert_pydantic_schema_to_openapi(item) for item in anyof_list]
        return result

    def _pydantic_field_to_openapi_param(
        self, field_name: str, field_info, model_class
    ) -> Dict[str, Any]:
        """Convert a Pydantic field to OpenAPI parameter definition."""
        param = {
            "name": field_name,
            "in": "query",  # Will be overridden for path params
            "required": True,
            "schema": {"type": "string"},
        }

        try:
            # Get field info from Pydantic model
            field_annotation = model_class.model_fields.get(field_name)
            if field_annotation:
                # Check if field is optional
                is_optional, inner_type = self._is_optional_type(
                    field_annotation.annotation
                )
                param["required"] = not is_optional and field_annotation.default is None

                # Basic type mapping
                if inner_type is str:
                    param["schema"] = {"type": "string"}
                elif inner_type is int:
                    param["schema"] = {"type": "integer"}
                elif inner_type is float:
                    param["schema"] = {"type": "number"}
                elif inner_type is bool:
                    param["schema"] = {"type": "boolean"}
                else:
                    param["schema"] = {"type": "string"}

                # Add description if available
                if (
                    hasattr(field_annotation, "description")
                    and field_annotation.description
                ):
                    param["description"] = field_annotation.description

        except (AttributeError, TypeError):
            pass

        return param

    def _infer_schema_from_validation_dependencies(self, param_name: str, collect_schema_func, route: Optional[RouteHandler] = None) -> Optional[Dict[str, Any]]:
        """Infer schema from validation dependencies that might use the given parameter (e.g. json_body)."""
        # Look for global validation dependencies that take the parameter as input
        for validation_name, validation_wrapper in self._validation_dependencies.items():
            sig = inspect.signature(validation_wrapper.func)
            if param_name in sig.parameters:
                # This validation function takes the parameter as input
                return_annotation = sig.return_annotation
                if return_annotation and return_annotation != inspect.Parameter.empty:
                    if self._is_pydantic_model(return_annotation):
                        # Collect the schema and return a reference
                        schema_name = collect_schema_func(return_annotation)
                        if schema_name:
                            return {"$ref": f"#/components/schemas/{schema_name}"}
        return None

    def _get_primary_content_type_for_route(self, route: RouteHandler) -> Optional[str]:
        """Get the primary content type that this route expects for request bodies."""
        # Check global accepts dependencies
        if self._accepts_dependencies:
            # Return the first global accepts dependency content type
            return next(iter(self._accepts_dependencies.keys()))
        else:
            # Default to application/json
            return "application/json"

    def _infer_basic_schema_from_type(self, type_annotation) -> Dict[str, Any]:
        """Infer basic OpenAPI schema from Python type annotation."""
        if type_annotation is str:
            return {"type": "string"}
        elif type_annotation is int:
            return {"type": "integer"}
        elif type_annotation is float:
            return {"type": "number"}
        elif type_annotation is bool:
            return {"type": "boolean"}
        elif type_annotation is list:
            return {"type": "array", "items": {"type": "object"}}
        elif type_annotation is dict:
            return {"type": "object"}
        else:
            # Default fallback for unknown types
            return {"type": "object"}

    def generate_openapi_json(
        self,
        title: str = "REST API",
        version: str = "1.0.0",
        description: str = "API generated by REST Framework",
    ) -> str:
        """Generate OpenAPI 3.0 JSON specification from registered routes."""

        # Keep track of all schemas we've seen to avoid duplicates
        collected_schemas: Dict[str, Dict[str, Any]] = {}

        def _collect_schema(model_class: Type[Any]) -> Optional[str]:
            """Collect a Pydantic model schema and return its reference name."""
            if not self._is_pydantic_model(model_class):
                return None

            schema_name: str = model_class.__name__
            if schema_name not in collected_schemas:
                collected_schemas[schema_name] = self._get_pydantic_schema(model_class)

            return schema_name

        def _get_schema_ref(schema_name: str) -> Dict[str, str]:
            """Get a $ref object for a schema."""
            return {"$ref": f"#/components/schemas/{schema_name}"}

        def _extract_path_parameters(
            path: str, route: RouteHandler
        ) -> List[Dict[str, Any]]:
            """Extract path parameters from a route path."""
            params = []

            # First, check if there are validation dependencies that depend on path_params
            sig = inspect.signature(route.handler)
            path_params_from_validation = []

            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a global validation dependency
                validation_wrapper = self._validation_dependencies.get(param_name)

                if validation_wrapper:
                    # Check if this validation function depends on path_params
                    if (
                        hasattr(validation_wrapper, "depends_on_path_params")
                        and validation_wrapper.depends_on_path_params
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            # Extract Pydantic model fields
                            if self._is_pydantic_model(return_annotation):
                                try:
                                    model_fields = return_annotation.model_fields
                                    for field_name, field_info in model_fields.items():
                                        param_def = (
                                            self._pydantic_field_to_openapi_param(
                                                field_name,
                                                field_info,
                                                return_annotation,
                                            )
                                        )
                                        param_def["in"] = (
                                            "path"  # Set to path instead of the default
                                        )
                                        path_params_from_validation.append(param_def)
                                except (AttributeError, TypeError):
                                    # If we can't extract fields, skip this validation function
                                    pass

            # If we found path parameters from validation dependencies, use those
            if path_params_from_validation:
                return path_params_from_validation

            # Otherwise, fall back to extracting from path pattern (assuming strings)
            pattern = re.findall(r"\{(\w+)\}", path)
            for param_name in pattern:
                params.append(
                    {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )
            return params

        def _extract_query_string_parameters(
            route: RouteHandler,
        ) -> List[Dict[str, Any]]:
            """Extract query string parameters from validation dependencies."""
            params = []

            # Look at the route handler's parameters to find validation dependencies
            sig = inspect.signature(route.handler)
            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a global validation dependency
                validation_wrapper = self._validation_dependencies.get(param_name)

                if validation_wrapper:
                    # Check if this validation function depends on query_params
                    if (
                        hasattr(validation_wrapper, "depends_on_query_params")
                        and validation_wrapper.depends_on_query_params
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            # Extract Pydantic model fields
                            if self._is_pydantic_model(return_annotation):
                                try:
                                    model_fields = return_annotation.model_fields
                                    for field_name, field_info in model_fields.items():
                                        param_def = (
                                            self._pydantic_field_to_openapi_param(
                                                field_name,
                                                field_info,
                                                return_annotation,
                                            )
                                        )
                                        param_def["in"] = (
                                            "query"  # Set to query instead of the default
                                        )
                                        params.append(param_def)
                                except (AttributeError, TypeError):
                                    # If we can't extract fields, skip this validation function
                                    pass

            return params

        def _extract_request_body_schema(
            route: RouteHandler,
        ) -> Optional[Dict[str, Any]]:
            """Extract request body schema from validation dependencies, built-in parsers, and custom @accepts parsers."""
            sig = inspect.signature(route.handler)

            # First, check validation dependencies that depend on body
            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a global validation dependency
                validation_wrapper = self._validation_dependencies.get(param_name)

                if validation_wrapper:
                    # Check if this validation function depends on body
                    if (
                        hasattr(validation_wrapper, "depends_on_body")
                        and validation_wrapper.depends_on_body
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            if self._is_pydantic_model(return_annotation):
                                # Collect the schema and return a reference
                                schema_name = _collect_schema(return_annotation)
                                if schema_name:
                                    return _get_schema_ref(schema_name)

            # Check for built-in parsers (json_body, form_body, etc.) and custom @accepts parsers
            for param_name, param in sig.parameters.items():
                # Check if this parameter uses built-in parsers
                if param_name in ['json_body', 'form_body', 'text_body', 'multipart_body']:
                    # For built-in parsers, try to infer schema from validation dependencies that use them
                    schema_from_validation = self._infer_schema_from_validation_dependencies(param_name, _collect_schema, route)
                    if schema_from_validation:
                        return schema_from_validation

                    # Default schemas for built-in parsers when no validation is found
                    if param_name == 'json_body':
                        return {"type": "object"}
                    elif param_name == 'form_body':
                        return {"type": "object", "description": "Form data"}
                    elif param_name == 'text_body':
                        return {"type": "string"}
                    elif param_name == 'multipart_body':
                        return {"type": "object", "description": "Multipart form data"}

                # Check if this parameter might be resolved through custom @accepts parsers
                # Look for accepts dependencies that match this route
                content_type = self._get_primary_content_type_for_route(route)
                if content_type:
                    # Check global accepts dependencies
                    if content_type in self._accepts_dependencies:
                        accepts_wrapper = self._accepts_dependencies[content_type]
                        return_annotation = inspect.signature(accepts_wrapper.func).return_annotation
                        if return_annotation and return_annotation != inspect.Parameter.empty:
                            if self._is_pydantic_model(return_annotation):
                                schema_name = _collect_schema(return_annotation)
                                if schema_name:
                                    return _get_schema_ref(schema_name)
                            else:
                                # For non-Pydantic return types, infer basic schema
                                return self._infer_basic_schema_from_type(return_annotation)

            return None

        def _extract_response_schema(route: RouteHandler) -> Optional[Dict[str, Any]]:
            """Extract response schema from handler return type annotation. Returns None if no schema should be included."""
            sig = inspect.signature(route.handler)
            return_annotation = sig.return_annotation

            # Check if return type is explicitly None
            if return_annotation is type(None):
                return cast(None, None)  # No schema for 204 responses

            # Check if no annotation is provided
            if return_annotation == inspect.Parameter.empty:
                return None  # No schema for unannotated handlers

            if return_annotation and return_annotation != inspect.Parameter.empty:
                # Handle Optional types
                is_optional, inner_type = self._is_optional_type(return_annotation)
                actual_type = inner_type if is_optional else return_annotation

                # Handle List types
                origin = get_origin(actual_type)
                if origin is list:
                    # This is List[SomeType]
                    args = get_args(actual_type)
                    if args and self._is_pydantic_model(args[0]):
                        schema_name = _collect_schema(args[0])
                        if schema_name:
                            return {
                                "type": "array",
                                "items": _get_schema_ref(schema_name),
                            }
                elif self._is_pydantic_model(actual_type):
                    schema_name = _collect_schema(actual_type)
                    if schema_name:
                        return _get_schema_ref(schema_name)

            # Default fallback for other annotated types
            return {"type": "object"}

        def _route_uses_validation_dependencies(route: RouteHandler) -> bool:
            """Check if a route uses any validation dependencies that return Pydantic models."""
            sig = inspect.signature(route.handler)
            for param_name, param in sig.parameters.items():
                if param_name in self._validation_dependencies:
                    return True
            return False

        def _convert_path_to_openapi(path: str) -> str:
            """Convert {param} syntax to OpenAPI {param} syntax."""
            return path

        def _get_operation_info(route: RouteHandler) -> Dict[str, Any]:
            """Extract operation information from a route handler."""
            # Extract response schema from handler return type
            response_schema = _extract_response_schema(route)

            # Check if this is a None return type (should use 204)
            sig = inspect.signature(route.handler)
            return_annotation = sig.return_annotation

            operation: Dict[str, Any] = {
                "summary": route.handler.__name__.replace("_", " ").title(),
                "responses": {},
            }

            if return_annotation is None:
                # Handler explicitly returns None -> 204 No Content
                operation["responses"]["204"] = {"description": "No Content"}
            elif response_schema is inspect.Signature.empty:
                # No annotation or no schema -> 200 without content schema
                operation["responses"]["200"] = {"description": "Successful response"}
            elif response_schema:
                # Has schema -> 200 with content
                operation["responses"]["200"] = {
                    "description": "Successful response",
                    "content": {"application/json": {"schema": response_schema}},
                }
            else:
                # Has schema -> 200 with content
                operation["responses"]["200"] = {
                    "description": "Successful response",
                }

            # Check if this route uses validation dependencies and add 422 response
            uses_validation = _route_uses_validation_dependencies(route)
            if uses_validation:
                operation["responses"]["422"] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": {"type": "string"},
                                    "details": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }

            # Add description from docstring if available
            if route.handler.__doc__:
                operation["description"] = route.handler.__doc__.strip()

            # Add path parameters
            path_params = _extract_path_parameters(route.path, route)
            # Add query string parameters
            query_params = _extract_query_string_parameters(route)

            # Combine all parameters
            all_params = path_params + query_params
            if all_params:
                operation["parameters"] = all_params

            # Add request body for POST/PUT/PATCH methods
            if route.method.value in ["POST", "PUT", "PATCH"]:
                # Try to extract request body schema from validation dependencies
                request_body_schema = _extract_request_body_schema(route)
                if request_body_schema:
                    operation["requestBody"] = {
                        "content": {"application/json": {"schema": request_body_schema}}
                    }

            return operation

        # Build the OpenAPI specification
        openapi_spec: Dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": title, "version": version, "description": description},
            "paths": {},
        }

        # Process all routes to collect schemas and build paths
        # Get routes from root router (including mounted routers)
        all_routes = [route for path, route in self._root_router.get_all_routes()]

        for route in all_routes:
            openapi_path = _convert_path_to_openapi(route.path)

            if openapi_path not in openapi_spec["paths"]:
                openapi_spec["paths"][openapi_path] = {}

            method_lower = route.method.value.lower()
            openapi_spec["paths"][openapi_path][method_lower] = _get_operation_info(
                route
            )

        # Add components section if we have collected schemas
        if collected_schemas:
            openapi_spec["components"] = {"schemas": collected_schemas}

        return json.dumps(openapi_spec, indent=2)

    def save_openapi_json(
        self,
        filename: str = "openapi.json",
        docs_dir: str = "docs",
        title: str = "REST API",
        version: str = "1.0.0",
        description: str = "API generated by REST Framework",
    ) -> str:
        """Generate and save OpenAPI JSON specification to a file in the docs directory."""

        # Create docs directory if it doesn't exist
        if not os.path.exists(docs_dir):
            os.makedirs(docs_dir)

        # Generate OpenAPI JSON
        openapi_json = self.generate_openapi_json(title, version, description)

        # Write to file
        file_path = os.path.join(docs_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(openapi_json)

        return file_path

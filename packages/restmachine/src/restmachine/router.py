"""Router module for organizing routes with mounting support."""

from typing import Callable, List, Literal, Optional, Tuple, Dict, Any, Union, TYPE_CHECKING
from .models import HTTPMethod
from .dependencies import Dependency, AcceptsWrapper, DependencyScope, DependencyWrapper, HeadersWrapper
from .cors import CORSConfig
from .csp import CSPConfig

if TYPE_CHECKING:
    from .application import RouteHandler


class RouteNode:
    """A node in the route trie structure.

    Each node represents a path segment and can have:
    - static_children: Dict mapping exact segment strings to child nodes
    - param_child: Single child node for path parameters (e.g., {id})
    - wildcard_child: Single child node for wildcard parameters (e.g., *filepath)
    - handlers: Dict mapping HTTP methods to RouteHandlers at this path
    """

    def __init__(self):
        self.static_children: Dict[str, "RouteNode"] = {}
        self.param_child: Optional[Tuple[str, "RouteNode"]] = None  # (param_name, node)
        self.wildcard_child: Optional[Tuple[str, "RouteNode"]] = None  # (param_name, node) for *param
        self.handlers: Dict[HTTPMethod, "RouteHandler"] = {}

    def add_route(self, segments: List[str], method: HTTPMethod, handler: "RouteHandler") -> None:
        """Add a route to the trie.

        Args:
            segments: Path segments (e.g., ['api', 'users', '{id}', '*filepath'])
            method: HTTP method
            handler: RouteHandler instance
        """
        if not segments:
            # We've reached the end of the path
            self.handlers[method] = handler
            return

        segment = segments[0]
        remaining = segments[1:]

        # Check if this is a wildcard parameter (matches all remaining segments)
        # Support both * and ** syntax (** is preferred for "match all")
        if segment == '**' or (segment.startswith('*') and not segment.startswith('{*')):
            # For **, use default param name 'path'; for *name, extract the name
            if segment == '**':
                param_name = 'path'
            else:
                param_name = segment[1:]  # Extract parameter name (e.g., *filepath -> filepath)
            if remaining:
                raise ValueError(f"Wildcard parameter '{segment}' must be the last segment in the route")
            if self.wildcard_child is None:
                self.wildcard_child = (param_name, RouteNode())
            _, child_node = self.wildcard_child
            child_node.handlers[method] = handler
        # Check if this is a path parameter
        elif segment.startswith('{') and segment.endswith('}'):
            param_name = segment[1:-1]  # Extract parameter name
            if self.param_child is None:
                self.param_child = (param_name, RouteNode())
            _, child_node = self.param_child
            child_node.add_route(remaining, method, handler)
        else:
            # Static segment
            if segment not in self.static_children:
                self.static_children[segment] = RouteNode()
            self.static_children[segment].add_route(remaining, method, handler)

    def match(self, segments: List[str], method: HTTPMethod) -> Optional[Tuple["RouteHandler", Dict[str, str]]]:
        """Match a path against the trie.

        Args:
            segments: Path segments from the request
            method: HTTP method from the request

        Returns:
            Tuple of (RouteHandler, path_params) if matched, None otherwise
        """
        if not segments:
            # We've reached the end of the path
            handler = self.handlers.get(method)
            if handler:
                return (handler, {})
            # Check for wildcard that matches empty path
            if self.wildcard_child:
                param_name, child_node = self.wildcard_child
                handler = child_node.handlers.get(method)
                if handler:
                    return (handler, {param_name: ""})
            return None

        segment = segments[0]
        remaining = segments[1:]

        # Try static match first (more specific)
        if segment in self.static_children:
            result = self.static_children[segment].match(remaining, method)
            if result:
                return result

        # Try param match
        if self.param_child:
            param_name, child_node = self.param_child
            result = child_node.match(remaining, method)
            if result:
                handler, params = result
                params[param_name] = segment
                return (handler, params)

        # Try wildcard match (least specific - matches all remaining segments)
        if self.wildcard_child:
            param_name, child_node = self.wildcard_child
            handler = child_node.handlers.get(method)
            if handler:
                # Join all segments with / to get the full path
                wildcard_value = "/".join(segments)
                return (handler, {param_name: wildcard_value})

        return None

    def has_path(self, segments: List[str]) -> bool:
        """Check if any route exists at this path (regardless of method).

        Args:
            segments: Path segments from the request

        Returns:
            True if any route exists at this path
        """
        if not segments:
            # We've reached the end - check if any handlers exist
            if self.handlers:
                return True
            # Check for wildcard
            if self.wildcard_child:
                _, child_node = self.wildcard_child
                return bool(child_node.handlers)
            return False

        segment = segments[0]
        remaining = segments[1:]

        # Try static match
        if segment in self.static_children:
            if self.static_children[segment].has_path(remaining):
                return True

        # Try param match
        if self.param_child:
            _, child_node = self.param_child
            if child_node.has_path(remaining):
                return True

        # Try wildcard match
        if self.wildcard_child:
            _, child_node = self.wildcard_child
            return bool(child_node.handlers)

        return False


def normalize_path(prefix: str, path: str) -> str:
    """Normalize a path by combining prefix and path, handling double slashes.

    Args:
        prefix: The prefix path (e.g., "/", "/api", "/users")
        path: The route path (e.g., "/", "/list", "/{id}")

    Returns:
        Normalized path without double slashes

    Examples:
        normalize_path("/", "/users") -> "/users"
        normalize_path("/", "users") -> "/users"
        normalize_path("/api", "/users") -> "/api/users"
        normalize_path("/api", "users") -> "/api/users"
        normalize_path("/api/", "/users") -> "/api/users"
    """
    # Ensure prefix starts with /
    if not prefix.startswith('/'):
        prefix = '/' + prefix

    # Remove trailing slash from prefix unless it's just "/"
    if prefix != '/' and prefix.endswith('/'):
        prefix = prefix.rstrip('/')

    # Ensure path starts with /
    if not path.startswith('/'):
        path = '/' + path

    # Combine and handle the root case
    if prefix == '/':
        return path

    return prefix + path


class Router:
    """Router class for organizing routes with mounting support.

    Routers allow you to organize routes by functionality and mount them
    with different prefixes. Routers can also be nested (mounted into other routers).
    """

    def __init__(self, app: Optional[Any] = None):
        """Initialize a router.

        Args:
            app: Optional RestApplication instance for dependency/callback registration
        """
        self.app = app
        self._routes: List[RouteHandler] = []
        self._mounted_routers: List[Tuple[str, "Router"]] = []  # (prefix, router) pairs
        self._route_tree = RouteNode()  # Root of the route trie

        # Router-level dependencies and callbacks (used when app is not set)
        self._dependencies: Dict[str, Union[Callable, DependencyWrapper, Dependency]] = {}
        self._validation_dependencies: Dict[str, Any] = {}  # ValidationWrapper, imported later to avoid circular import
        self._headers_dependencies: Dict[str, HeadersWrapper] = {}
        self._accepts_dependencies: Dict[str, AcceptsWrapper] = {}
        self._callbacks: Dict[str, Callable] = {}

        # CORS configuration for this router (overrides app-level)
        self._cors_config: Optional[CORSConfig] = None

        # CSP configuration for this router (overrides app-level)
        self._csp_config: Optional[CSPConfig] = None

    def mount(self, prefix: str, router: "Router"):
        """Mount another router with a given prefix.

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
        # Set the app reference if not already set
        if router.app is None and self.app is not None:
            router.app = self.app

            # Transfer router's local dependencies to the app
            for dep_name, dependency in router._dependencies.items():
                self.app._dependencies[dep_name] = dependency

            # Transfer validation dependencies
            for dep_name, validation_wrapper in router._validation_dependencies.items():
                self.app._validation_dependencies[dep_name] = validation_wrapper

            # Transfer accepts dependencies
            for content_type, accepts_wrapper in router._accepts_dependencies.items():
                self.app._accepts_dependencies[content_type] = accepts_wrapper

            # Transfer callbacks
            for callback_name, callback in router._callbacks.items():
                if callback_name not in self.app._callbacks:
                    self.app._callbacks[callback_name] = callback

        self._mounted_routers.append((prefix, router))

        # Add all mounted routes to the tree immediately
        for route_path, route in router.get_all_routes(prefix):
            segments = [s for s in route_path.split('/') if s]
            self._route_tree.add_route(segments, route.method, route)

    def get_all_routes(self, prefix: str = "") -> List[Tuple[str, Any]]:
        """Get all routes from this router and mounted routers.

        Args:
            prefix: Path prefix to prepend to all routes

        Returns:
            List of (path, route_handler) tuples
        """
        # Import here to avoid circular import
        from .application import RouteHandler

        routes = []

        # Add routes from this router
        for route in self._routes:
            normalized_path = normalize_path(prefix, route.path)
            # Create a new RouteHandler with the normalized path
            normalized_route = RouteHandler(route.method, normalized_path, route.handler)
            # Copy over route-specific attributes
            normalized_route.state_callbacks = route.state_callbacks.copy()
            normalized_route.content_renderers = route.content_renderers.copy()
            normalized_route.validation_wrappers = route.validation_wrappers.copy()
            normalized_route.cors_config = route.cors_config
            routes.append((normalized_path, normalized_route))

        # Add routes from mounted routers
        for mount_prefix, mounted_router in self._mounted_routers:
            combined_prefix = normalize_path(prefix, mount_prefix)
            routes.extend(mounted_router.get_all_routes(combined_prefix))

        return routes

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

    def options(self, path: str):
        """Decorator to register an OPTIONS route handler."""
        return self._route_decorator(HTTPMethod.OPTIONS, path)

    def _route_decorator(self, method: HTTPMethod, path: str):
        """Internal method to create route decorators."""
        # Import here to avoid circular import
        from .application import RouteHandler

        def decorator(func: Callable):
            route = RouteHandler(method, path, func)

            # Check if function has CORS config marker (from @cors decorator)
            if hasattr(func, '_restmachine_cors_config'):
                route.cors_config = func._restmachine_cors_config
                delattr(func, '_restmachine_cors_config')  # Clean up marker

            # Check if function has CSP config marker (from @csp decorator)
            if hasattr(func, '_restmachine_csp_config'):
                route.csp_config = func._restmachine_csp_config
                delattr(func, '_restmachine_csp_config')  # Clean up marker

            self._routes.append(route)

            # Resolve state machine callbacks if app is available
            if self.app:
                route.resolve_state_callbacks(self.app)

            # Add to tree immediately
            segments = [s for s in path.split('/') if s]
            self._route_tree.add_route(segments, method, route)
            return func

        return decorator

    # Dependency decorators (forward to app if available, otherwise store locally)

    def dependency(self, func: Optional[Callable] = None, *, name: Optional[str] = None, scope: DependencyScope = "request"):
        """Decorator to register a global dependency that can be injected into any route handler.

        Dependencies are automatically injected based on parameter names in route handlers.
        """
        def decorator_wrapper(f: Callable):
            dep_name = name if name is not None else f.__name__

            # Register globally (either via app or locally)
            if self.app:
                self.app._dependencies[dep_name] = Dependency(f, scope)
            else:
                # Store locally if no app
                self._dependencies[dep_name] = Dependency(f, scope)

            return f

        if func is None:
            return decorator_wrapper
        else:
            return decorator_wrapper(func)

    def validates(self, func: Optional[Callable] = None, *, name: Optional[str] = None, scope: DependencyScope = "request"):
        """Decorator to register a global validation dependency."""
        # Import here to avoid circular import
        from .dependencies import ValidationWrapper

        def decorator_wrapper(f: Callable):
            dep_name = name if name is not None else f.__name__
            wrapper = ValidationWrapper(f, scope)

            # Register globally
            if self.app:
                self.app._validation_dependencies[dep_name] = wrapper
                self.app._dependencies[dep_name] = Dependency(f, scope)
            else:
                self._validation_dependencies[dep_name] = wrapper
                self._dependencies[dep_name] = Dependency(f, scope)

            return f

        if func is None:
            return decorator_wrapper
        else:
            return decorator_wrapper(func)

    def accepts(self, content_type: str, scope: DependencyScope = "request"):
        """Decorator to register a global content-type specific body parser."""
        def decorator(func: Callable):
            wrapper = AcceptsWrapper(func, content_type, func.__name__)

            # Register globally
            if self.app:
                self.app._accepts_dependencies[content_type] = wrapper
                self.app._dependencies[func.__name__] = Dependency(func, scope)
            else:
                self._accepts_dependencies[content_type] = wrapper
                self._dependencies[func.__name__] = Dependency(func, scope)

            return func

        return decorator

    # State machine callback decorators
    def resource_exists(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with resource existence checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "resource_exists", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def resource_from_request(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency for creating resource from request (for POST).

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "resource_from_request", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def forbidden(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with forbidden checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "forbidden", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def authorized(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with authorization checking.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "authorized", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def default_headers(self, func: Callable):
        """Decorator to register a global headers manipulation function."""
        wrapper = HeadersWrapper(func, func.__name__)

        if self.app:
            self.app._headers_dependencies[func.__name__] = wrapper
            self.app._dependencies[func.__name__] = func
        else:
            # Store locally if no app (will be registered when mounted)
            self._headers_dependencies[func.__name__] = wrapper
            self._dependencies[func.__name__] = func

        return func

    def generate_etag(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with ETag generation for conditional requests.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "generate_etag", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def last_modified(self, func: Callable, scope: DependencyScope = "request"):
        """Decorator to wrap a dependency with Last-Modified date for conditional requests.

        Args:
            scope: Dependency scope - "request" (default) or "session"
        """
        from .dependencies import DependencyWrapper

        wrapper = DependencyWrapper(func, "last_modified", func.__name__, scope)

        if self.app:
            self.app._dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper

        return func

    def provides(self, content_type: str, scope: DependencyScope = "request", charset: Optional[str] = None):
        """Decorator to register a content-type specific renderer for an endpoint.

        NOTE: This decorator must be placed after the route decorator to attach
        the renderer to the correct route.

        Args:
            content_type: The content type this renderer provides
            scope: Dependency scope - "request" (default) or "session"
            charset: Optional charset to include in Content-Type header (e.g., "utf-8")
        """
        from .dependencies import ContentNegotiationWrapper

        def decorator(func: Callable):
            # Find the most recently added route
            if self._routes:
                route = self._routes[-1]
                handler_name = route.handler.__name__
                wrapper = ContentNegotiationWrapper(func, content_type, handler_name, charset=charset)
                route.add_content_renderer(content_type, wrapper)

            # Also register this as a dependency so it can be injected
            if self.app:
                self.app._dependencies[func.__name__] = Dependency(func, scope)
            else:
                self._dependencies[func.__name__] = Dependency(func, scope)

            return func

        return decorator

    # Default state machine callbacks
    def default_service_available(self, func: Callable):
        """Register a default service_available callback."""
        if self.app:
            self.app._default_callbacks["service_available"] = func
        else:
            self._callbacks["service_available"] = func
        return func

    def default_known_method(self, func: Callable):
        """Register a default known_method callback."""
        if self.app:
            self.app._default_callbacks["known_method"] = func
        else:
            self._callbacks["known_method"] = func
        return func

    def default_uri_too_long(self, func: Callable):
        """Register a default uri_too_long callback."""
        if self.app:
            self.app._default_callbacks["uri_too_long"] = func
        else:
            self._callbacks["uri_too_long"] = func
        return func

    def default_method_allowed(self, func: Callable):
        """Register a default method_allowed callback."""
        if self.app:
            self.app._default_callbacks["method_allowed"] = func
        else:
            self._callbacks["method_allowed"] = func
        return func

    def default_malformed_request(self, func: Callable):
        """Register a default malformed_request callback."""
        if self.app:
            self.app._default_callbacks["malformed_request"] = func
        else:
            self._callbacks["malformed_request"] = func
        return func

    def default_authorized(self, func: Callable):
        """Register a default authorized callback."""
        if self.app:
            self.app._default_callbacks["authorized"] = func
        else:
            self._callbacks["authorized"] = func
        return func

    def default_forbidden(self, func: Callable):
        """Register a default forbidden callback."""
        if self.app:
            self.app._default_callbacks["forbidden"] = func
        else:
            self._callbacks["forbidden"] = func
        return func

    def default_content_headers_valid(self, func: Callable):
        """Register a default content_headers_valid callback."""
        if self.app:
            self.app._default_callbacks["content_headers_valid"] = func
        else:
            self._callbacks["content_headers_valid"] = func
        return func

    def default_resource_exists(self, func: Callable):
        """Register a default resource_exists callback."""
        if self.app:
            self.app._default_callbacks["resource_exists"] = func
        else:
            self._callbacks["resource_exists"] = func
        return func

    def default_route_not_found(self, func: Callable):
        """Register a default route_not_found callback."""
        if self.app:
            self.app._default_callbacks["route_not_found"] = func
        else:
            self._callbacks["route_not_found"] = func
        return func

    def cors(
        self,
        origins: Optional[Union[List[str], str]] = None,
        methods: Optional[List[str]] = None,
        allow_headers: Optional[List[str]] = None,
        expose_headers: Optional[List[str]] = None,
        credentials: bool = False,
        max_age: int = 86400,
        reflect_any_origin: bool = False,
    ):
        """Configure CORS for this router or as a route decorator.

        Can be used in two ways:

        1. Router-level configuration (applies to all routes in this router):
            ```python
            api_router = Router()
            api_router.cors(origins=["https://app.example.com"])
            ```

        2. Route-level decorator (applies to specific endpoint):
            ```python
            @api_router.get("/data")
            @api_router.cors(origins=["https://app.example.com"])
            def get_data():
                return {"data": "value"}
            ```

        Args:
            origins: Allowed origins. Can be a list of URLs or "*" for all origins.
            methods: HTTP methods to allow. If None, auto-detects from routes.
            allow_headers: Request headers allowed in actual request.
            expose_headers: Response headers JavaScript can access.
            credentials: Whether to allow credentials (cookies, auth headers).
            max_age: Preflight cache duration in seconds (default 24 hours).
            reflect_any_origin: Allow reflecting any origin with credentials (for development).
                              WARNING: Only use in development environments!

        Returns:
            Decorator function if used as decorator, None if router-level config.
        """
        # Normalize origins input
        if origins is None:
            raise ValueError("CORS: origins parameter is required")

        if isinstance(origins, str):
            normalized_origins: Union[List[str], Literal["*"]] = "*" if origins == "*" else [origins]
        else:
            normalized_origins = origins

        # Create CORS config with defaults
        # Use a temporary config to get defaults
        defaults_config = CORSConfig(origins="*")

        config = CORSConfig(
            origins=normalized_origins,
            methods=methods,
            allow_headers=allow_headers if allow_headers is not None else defaults_config.allow_headers,
            expose_headers=expose_headers if expose_headers is not None else defaults_config.expose_headers,
            credentials=credentials,
            max_age=max_age,
            reflect_any_origin=reflect_any_origin,
        )

        # Validate config
        config.validate()

        # Try to use as decorator
        def decorator(func: Callable):
            # Mark the function with CORS config so route decorator can pick it up
            func._restmachine_cors_config = config  # type: ignore
            return func

        # Store router-level config (but don't overwrite if already set)
        # This allows cors() to be used both for router-level config and as a route decorator
        if self._cors_config is None:
            self._cors_config = config

        # Return decorator function
        return decorator

    def csp(
        self,
        # Fetch directives
        default_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        script_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        style_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        img_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        font_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        connect_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        frame_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        object_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        media_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        worker_src: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        # Document directives
        base_uri: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        # Navigation directives
        form_action: Optional[Union[List[str], Callable[[], List[str]]]] = None,
        # Special options
        nonce: bool = False,
        report_uri: Optional[str] = None,
        report_only: bool = False,
        # Preset
        preset: Optional[CSPConfig] = None,
    ):
        """Configure Content Security Policy for this router or as a route decorator.

        Can be used in two ways:

        1. Router-level configuration (applies to all routes in this router):
            ```python
            api_router = Router()
            api_router.csp(default_src=["self"])
            ```

        2. Route-level decorator (applies to specific endpoint):
            ```python
            @api_router.get("/data")
            @api_router.csp(script_src=["self", "https://cdn.com"])
            def get_data():
                return {"data": "value"}
            ```

        Args:
            default_src: Default source list for fetch directives.
            script_src: Valid sources for JavaScript.
            style_src: Valid sources for stylesheets.
            img_src: Valid sources for images.
            font_src: Valid sources for fonts.
            connect_src: Valid sources for fetch, WebSocket, etc.
            frame_src: Valid sources for frames.
            object_src: Valid sources for plugins.
            media_src: Valid sources for audio/video.
            worker_src: Valid sources for workers.
            base_uri: Valid URLs for the <base> element.
            form_action: Valid endpoints for form submissions.
            nonce: Generate nonce for inline scripts/styles.
            report_uri: Endpoint for CSP violation reports.
            report_only: Use report-only mode (doesn't block, just reports).
            preset: Use a pre-configured CSP preset.

        Returns:
            Decorator function if used as decorator, None if router-level config.
        """
        # If preset is provided, use it
        if preset:
            config = preset
        else:
            # Create config from parameters
            config = CSPConfig(
                default_src=default_src,
                script_src=script_src,
                style_src=style_src,
                img_src=img_src,
                font_src=font_src,
                connect_src=connect_src,
                frame_src=frame_src,
                object_src=object_src,
                media_src=media_src,
                worker_src=worker_src,
                base_uri=base_uri,
                form_action=form_action,
                nonce=nonce,
                report_uri=report_uri,
                report_only=report_only,
            )

        # Decorator for route-level CSP
        def decorator(func: Callable):
            # Mark the function with CSP config so route decorator can pick it up
            func._restmachine_csp_config = config  # type: ignore
            return func

        # Store router-level config (but don't overwrite if already set)
        # This allows csp() to be used both for router-level config and as a route decorator
        if self._csp_config is None:
            self._csp_config = config

        # Return decorator function
        return decorator

    def match_route(self, path: str, method: HTTPMethod) -> Optional[Tuple[Any, Dict[str, str]]]:
        """Match a route using the trie structure.

        Args:
            path: Request path (e.g., "/api/users/123")
            method: HTTP method

        Returns:
            Tuple of (RouteHandler, path_params) if matched, None otherwise
        """
        segments = [s for s in path.split('/') if s]
        return self._route_tree.match(segments, method)

    def has_path(self, path: str) -> bool:
        """Check if any route exists at the given path (regardless of method).

        Args:
            path: Request path

        Returns:
            True if any route exists at this path
        """
        segments = [s for s in path.split('/') if s]
        return self._route_tree.has_path(segments)

    def get_methods_for_path(self, path: str) -> List[HTTPMethod]:
        """Get all HTTP methods that have registered routes at this path.

        Args:
            path: Request path (e.g., "/users/123")

        Returns:
            List of HTTPMethod enums that have routes at this path.
            Always includes OPTIONS if any routes exist.
        """
        segments = [s for s in path.split('/') if s]
        methods: set[HTTPMethod] = set()

        # Check all possible HTTP methods
        for method in HTTPMethod:
            # Skip OPTIONS for now, we'll add it at the end if routes exist
            if method == HTTPMethod.OPTIONS:
                continue

            result = self._route_tree.match(segments, method)
            if result:
                methods.add(method)

        # Always include OPTIONS if any routes exist
        if methods:
            methods.add(HTTPMethod.OPTIONS)

        # Return sorted list for consistent ordering
        return sorted(list(methods), key=lambda m: m.value)

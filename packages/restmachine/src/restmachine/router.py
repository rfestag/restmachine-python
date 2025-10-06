"""Router module for organizing routes with mounting support."""

from typing import Callable, List, Optional, Tuple, Dict, Any, TYPE_CHECKING
from .models import HTTPMethod
from .dependencies import Dependency, AcceptsWrapper, DependencyScope

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
        self._dependencies: Dict[str, Dependency] = {}
        self._validation_dependencies: Dict[str, Any] = {}  # ValidationWrapper, imported later to avoid circular import
        self._accepts_dependencies: Dict[str, AcceptsWrapper] = {}
        self._callbacks: Dict[str, Callable] = {}

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

    def _route_decorator(self, method: HTTPMethod, path: str):
        """Internal method to create route decorators."""
        # Import here to avoid circular import
        from .application import RouteHandler

        def decorator(func: Callable):
            route = RouteHandler(method, path, func)
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

"""
Proof of Concept: Proper State Machine Pattern

This shows how to refactor the current state machine into a proper
webmachine-style state machine with explicit transitions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Dict, List, Optional, Union
import logging

from restmachine.models import Request, Response
from restmachine.dependencies import DependencyWrapper
from restmachine.content_renderers import ContentRenderer

logger = logging.getLogger(__name__)


@dataclass
class StateContext:
    """Shared context passed through all state transitions."""
    app: 'RestApplication'  # type: ignore
    request: Request
    route_handler: Optional['RouteHandler'] = None  # type: ignore
    chosen_renderer: Optional[ContentRenderer] = None
    handler_dependencies: List[str] = field(default_factory=list)
    dependency_callbacks: Dict[str, DependencyWrapper] = field(default_factory=dict)


class State(ABC):
    """Base class for all state machine states."""

    @abstractmethod
    def execute(self, ctx: StateContext) -> Union['State', Response]:
        """Execute this state and return next state or terminal response.

        Returns:
            Either the next State to transition to, or a Response to return.
        """
        pass

    @property
    def name(self) -> str:
        """State name for logging."""
        return self.__class__.__name__


# ============================================================================
# DECISION STATES (return next state or response)
# ============================================================================

class RouteExistsState(State):
    """B13: Check if route exists for this method and path."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        route_match = ctx.app._find_route(ctx.request.method, ctx.request.path)

        if route_match is None:
            # Check if ANY route exists for this path (method mismatch)
            if ctx.app._path_has_routes(ctx.request.path):
                return create_error_response(
                    ctx, HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed"
                )

            # No route exists - check for custom handler
            callback = ctx.app._default_callbacks.get("route_not_found")
            if callback:
                try:
                    response = ctx.app._call_with_injection(callback, ctx.request, None)
                    if isinstance(response, Response):
                        return response
                except Exception as e:
                    logger.error(f"Error in route_not_found callback: {e}")

            return create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

        # Route found - populate context
        ctx.route_handler, path_params = route_match
        ctx.request.path_params = path_params
        ctx.handler_dependencies = list(ctx.route_handler.param_info.keys())

        # Copy pre-resolved state callbacks
        for state_name, callback in ctx.route_handler.state_callbacks.items():
            wrapper = DependencyWrapper(callback, state_name, callback.__name__)
            ctx.dependency_callbacks[state_name] = wrapper

        return ServiceAvailableState()


class ServiceAvailableState(State):
    """B12: Check if service is available."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = get_callback(ctx, "service_available")
        if callback:
            try:
                available = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not available:
                    return create_error_response(
                        ctx, HTTPStatus.SERVICE_UNAVAILABLE, "Service Unavailable"
                    )
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return create_error_response(
                    ctx, HTTPStatus.SERVICE_UNAVAILABLE, f"Service check failed: {str(e)}"
                )

        return KnownMethodState()


class KnownMethodState(State):
    """B11: Check if HTTP method is known."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = get_callback(ctx, "known_method")
        if callback:
            try:
                known = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not known:
                    return create_error_response(ctx, HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return create_error_response(
                    ctx, HTTPStatus.NOT_IMPLEMENTED, f"Method check failed: {str(e)}"
                )
        else:
            # Default: check against known methods
            from restmachine.models import HTTPMethod
            known_methods = {
                HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT,
                HTTPMethod.DELETE, HTTPMethod.PATCH
            }
            if ctx.request.method not in known_methods:
                return create_error_response(ctx, HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")

        return UriTooLongState()


class ResourceExistsState(State):
    """G7: Check if resource exists."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        # Check if we can skip conditional request states
        skip_conditional = not has_conditional_support(ctx)

        callback = get_callback(ctx, "resource_exists")
        if callback:
            try:
                if "resource_exists" in ctx.dependency_callbacks:
                    wrapper = ctx.dependency_callbacks["resource_exists"]
                    resolved_value = ctx.app._call_with_injection(
                        wrapper.func, ctx.request, ctx.route_handler
                    )
                    if resolved_value is None:
                        # Resource doesn't exist
                        from restmachine.models import HTTPMethod
                        if ctx.request.method == HTTPMethod.POST:
                            return ResourceFromRequestState()
                        return create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

                    # Cache resolved value
                    ctx.app._dependency_cache.set(wrapper.original_name, resolved_value)
                else:
                    exists = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                    if not exists:
                        from restmachine.models import HTTPMethod
                        if ctx.request.method == HTTPMethod.POST:
                            return ResourceFromRequestState()
                        return create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")
            except Exception as e:
                from restmachine.models import HTTPMethod
                if ctx.request.method == HTTPMethod.POST:
                    return ResourceFromRequestState()
                ctx.app._dependency_cache.set("exception", e)
                return create_error_response(
                    ctx, HTTPStatus.NOT_FOUND, f"Resource check failed: {str(e)}"
                )

        # Resource exists - decide next state based on flags
        if skip_conditional:
            return ContentTypesProvidedState()

        return IfMatchState()


class ExecuteAndRenderState(State):
    """Execute handler and render response (terminal state)."""

    def execute(self, ctx: StateContext) -> Response:
        """This always returns a Response - it's a terminal state."""
        # Import here to avoid circular import
        from restmachine.state_machine import RequestStateMachine

        # Use the existing implementation
        sm = RequestStateMachine(ctx.app)
        sm.request = ctx.request
        sm.route_handler = ctx.route_handler
        sm.chosen_renderer = ctx.chosen_renderer
        sm.handler_dependencies = ctx.handler_dependencies
        sm.dependency_callbacks = ctx.dependency_callbacks

        return sm.state_execute_and_render()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_error_response(ctx: StateContext, status_code: int, message: str) -> Response:
    """Create an error response (terminal state)."""
    # Import here to avoid circular import
    from restmachine.state_machine import RequestStateMachine

    sm = RequestStateMachine(ctx.app)
    sm.request = ctx.request
    sm.route_handler = ctx.route_handler

    return sm._create_error_response(status_code, message)


def get_callback(ctx: StateContext, state_name: str) -> Optional:
    """Get callback for a state."""
    if state_name in ctx.dependency_callbacks:
        return ctx.dependency_callbacks[state_name].func
    return ctx.app._default_callbacks.get(state_name)


def has_conditional_support(ctx: StateContext) -> bool:
    """Check if route has conditional request support."""
    if not ctx.route_handler:
        return False

    # Check if any conditional callbacks are registered
    conditional_states = {'generate_etag', 'last_modified'}
    return bool(conditional_states & set(ctx.route_handler.state_callbacks.keys()))


# ============================================================================
# MAIN STATE MACHINE
# ============================================================================

class RequestStateMachine:
    """Webmachine-style state machine for processing HTTP requests."""

    def __init__(self, app):
        self.app = app

    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine.

        This is the main entry point. It creates a context and executes
        states until a terminal Response is returned.
        """
        ctx = StateContext(app=self.app, request=request)
        self.app._dependency_cache.clear()

        logger.debug(f"Starting state machine for {request.method.value} {request.path}")

        # Start with initial state
        current_state: Union[State, Response] = RouteExistsState()

        # Execute states until we get a Response
        while not isinstance(current_state, Response):
            state_name = current_state.name
            logger.debug(f"→ {state_name}")

            try:
                current_state = current_state.execute(ctx)
            except Exception as e:
                logger.error(f"Error in state {state_name}: {e}")
                return create_error_response(
                    ctx, HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal error in {state_name}"
                )

        logger.debug(f"✓ Completed with status {current_state.status_code}")
        return current_state


# ============================================================================
# OPTIMIZATIONS WITH ROUTE FLAGS
# ============================================================================

@dataclass
class RouteCapabilities:
    """Flags indicating what capabilities a route needs."""
    needs_auth: bool = False
    needs_conditional: bool = False  # ETags, Last-Modified
    needs_content_negotiation: bool = True
    has_validators: bool = False

    @classmethod
    def from_route(cls, route: 'RouteHandler') -> 'RouteCapabilities':  # type: ignore
        """Analyze route and determine capabilities."""
        return cls(
            needs_auth='authorized' in route.state_callbacks or 'forbidden' in route.state_callbacks,
            needs_conditional='generate_etag' in route.state_callbacks or 'last_modified' in route.state_callbacks,
            needs_content_negotiation=bool(route.content_renderers),
            has_validators=bool(route.validation_wrappers)
        )


class OptimizedResourceExistsState(State):
    """Optimized version that can skip states based on route capabilities."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        # ... resource existence check logic ...

        # OPTIMIZATION: Skip unnecessary states based on route capabilities
        if ctx.route_handler:
            caps = RouteCapabilities.from_route(ctx.route_handler)

            if not caps.needs_conditional:
                # Skip all If-Match, If-None-Match, etc. states
                logger.debug("Skipping conditional states (not needed)")
                return ContentTypesProvidedState()

        return IfMatchState()

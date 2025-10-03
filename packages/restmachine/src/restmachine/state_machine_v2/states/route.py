"""
Route-related states.
"""

import logging
from http import HTTPStatus
from typing import Union

from restmachine.models import Response
from restmachine.dependencies import DependencyWrapper
from ..base import State, StateContext

logger = logging.getLogger(__name__)


class RouteExistsState(State):
    """B13: Check if route exists for this method and path.

    This is the initial state in the state machine. It determines if a route
    exists and whether the HTTP method is allowed.

    Transitions:
    - Route not found, no path match → NotFoundResponse (terminal)
    - Route exists, wrong method → MethodNotAllowedResponse (terminal)
    - Route found → ServiceAvailableState
    """

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        route_match = ctx.app._find_route(ctx.request.method, ctx.request.path)

        if route_match is None:
            # Check if ANY route exists for this path (method mismatch)
            if ctx.app._path_has_routes(ctx.request.path):
                return self._create_error_response(
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

            return self._create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

        # Route found - populate context
        ctx.route_handler, path_params = route_match
        ctx.request.path_params = path_params
        ctx.handler_dependencies = list(ctx.route_handler.param_info.keys())

        # Copy pre-resolved state callbacks
        for state_name, callback in ctx.route_handler.state_callbacks.items():
            wrapper = DependencyWrapper(callback, state_name, callback.__name__)
            ctx.dependency_callbacks[state_name] = wrapper

        # Transition to next state
        from .service import ServiceAvailableState
        return ServiceAvailableState()

    def _create_error_response(
        self, ctx: StateContext, status_code: int, message: str
    ) -> Response:
        """Create error response using existing implementation."""
        from restmachine.state_machine import RequestStateMachine as OldStateMachine

        old_sm = OldStateMachine(ctx.app)
        old_sm.request = ctx.request
        old_sm.route_handler = ctx.route_handler

        return old_sm._create_error_response(status_code, message)

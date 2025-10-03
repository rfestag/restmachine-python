"""
Resource existence states.
"""

import logging
from http import HTTPStatus
from typing import Union

from restmachine.models import Response, HTTPMethod
from ..base import State, StateContext
from .service import _get_callback, _create_error_response

logger = logging.getLogger(__name__)


class ResourceExistsState(State):
    """G7: Check if resource exists.

    This state can skip conditional request states if the route doesn't
    support conditional requests (optimization).
    """

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "resource_exists")

        if callback:
            try:
                # If wrapped as dependency callback
                if "resource_exists" in ctx.dependency_callbacks:
                    wrapper = ctx.dependency_callbacks["resource_exists"]
                    resolved_value = ctx.app._call_with_injection(
                        wrapper.func, ctx.request, ctx.route_handler
                    )
                    if resolved_value is None:
                        # Resource doesn't exist
                        if ctx.request.method == HTTPMethod.POST:
                            # POST to non-existent resource might create it
                            # Skip to content negotiation
                            from .negotiation import ContentTypesProvidedState
                            return ContentTypesProvidedState()
                        return _create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

                    # Cache resolved value
                    ctx.app._dependency_cache.set(wrapper.original_name, resolved_value)
                else:
                    # Regular callback
                    exists = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                    if not exists:
                        if ctx.request.method == HTTPMethod.POST:
                            from .negotiation import ContentTypesProvidedState
                            return ContentTypesProvidedState()
                        return _create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

            except Exception as e:
                logger.error(f"Error in resource_exists check: {e}")
                if ctx.request.method == HTTPMethod.POST:
                    from .negotiation import ContentTypesProvidedState
                    return ContentTypesProvidedState()
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.NOT_FOUND, f"Resource check failed: {str(e)}"
                )

        # OPTIMIZATION: Check if we need to process conditional states
        # Skip only if BOTH route doesn't support conditionals AND request has no conditional headers
        needs_conditional = self._needs_conditional_processing(ctx)

        if not needs_conditional:
            logger.debug("Skipping conditional states (not needed)")
            from .negotiation import ContentTypesProvidedState
            return ContentTypesProvidedState()

        # Needs conditional processing - go through conditional states
        from .conditional import IfMatchState
        return IfMatchState()

    def _needs_conditional_processing(self, ctx: StateContext) -> bool:
        """Check if conditional request processing is needed.

        Returns True if either:
        1. Route has conditional callbacks (generate_etag/last_modified), OR
        2. Request has conditional headers (If-Match/If-None-Match/If-Modified-Since/If-Unmodified-Since)
        """
        # Check if route has conditional support
        has_route_support = False
        if ctx.route_handler:
            conditional_states = {'generate_etag', 'last_modified'}
            has_route_support = bool(conditional_states & set(ctx.route_handler.state_callbacks.keys()))

        # Check if request has conditional headers
        has_conditional_headers = (
            ctx.request.headers.get('If-Match') or
            ctx.request.headers.get('If-None-Match') or
            ctx.request.headers.get('If-Modified-Since') or
            ctx.request.headers.get('If-Unmodified-Since')
        )

        return has_route_support or bool(has_conditional_headers)

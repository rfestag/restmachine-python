"""
Authorization and authentication states.
"""

from http import HTTPStatus
from typing import Union

from restmachine.models import Response
from ..base import State, StateContext
from .service import _get_callback, _create_error_response


class AuthorizedState(State):
    """B7: Check if request is authorized."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "authorized")
        if callback:
            try:
                authorized = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not authorized:
                    return _create_error_response(ctx, HTTPStatus.UNAUTHORIZED, "Unauthorized")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.UNAUTHORIZED, f"Authorization check failed: {str(e)}"
                )

        return ForbiddenState()


class ForbiddenState(State):
    """B6: Check if access is forbidden."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "forbidden")
        if callback:
            try:
                # For wrapped dependencies, check if resolved value is None (forbidden)
                if "forbidden" in ctx.dependency_callbacks:
                    wrapper = ctx.dependency_callbacks["forbidden"]
                    try:
                        resolved_value = ctx.app._call_with_injection(
                            wrapper.func, ctx.request, ctx.route_handler
                        )
                        if resolved_value is None:
                            # None indicates forbidden access
                            return _create_error_response(ctx, HTTPStatus.FORBIDDEN, "Forbidden")
                    except Exception as e:
                        ctx.app._dependency_cache.set("exception", e)
                        return _create_error_response(ctx, HTTPStatus.FORBIDDEN, "Forbidden")
                else:
                    # Use regular callback
                    forbidden = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                    if forbidden:
                        return _create_error_response(ctx, HTTPStatus.FORBIDDEN, "Forbidden")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.FORBIDDEN, f"Forbidden check failed: {str(e)}"
                )

        from .content import ContentHeadersValidState
        return ContentHeadersValidState()

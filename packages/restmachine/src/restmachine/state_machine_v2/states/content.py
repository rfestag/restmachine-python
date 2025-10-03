"""
Content header validation states.
"""

from http import HTTPStatus
from typing import Union

from restmachine.models import Response
from ..base import State, StateContext
from .service import _get_callback, _create_error_response


class ContentHeadersValidState(State):
    """B5: Check if content headers are valid."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "valid_content_headers")
        if callback:
            try:
                valid = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not valid:
                    return _create_error_response(ctx, HTTPStatus.BAD_REQUEST, "Invalid Content Headers")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.BAD_REQUEST, f"Content header validation failed: {str(e)}"
                )

        from .resource import ResourceExistsState
        return ResourceExistsState()

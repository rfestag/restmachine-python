"""
Request validation states.
"""

from http import HTTPStatus
from typing import Union

from restmachine.models import Response
from ..base import State, StateContext
from .service import _get_callback, _create_error_response


class MalformedRequestState(State):
    """B8: Check if request is malformed."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "malformed_request")
        if callback:
            try:
                malformed = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if malformed:
                    return _create_error_response(ctx, HTTPStatus.BAD_REQUEST, "Bad Request")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.BAD_REQUEST, f"Request validation failed: {str(e)}"
                )

        from .auth import AuthorizedState
        return AuthorizedState()

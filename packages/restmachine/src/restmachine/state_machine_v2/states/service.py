"""
Service-related states.
"""

import logging
from http import HTTPStatus
from typing import Union

from restmachine.models import Response, HTTPMethod
from ..base import State, StateContext

logger = logging.getLogger(__name__)


def _get_callback(ctx: StateContext, state_name: str):
    """Get callback for a state from dependency callbacks or default callbacks."""
    if state_name in ctx.dependency_callbacks:
        return ctx.dependency_callbacks[state_name].func
    return ctx.app._default_callbacks.get(state_name)


def _create_error_response(ctx: StateContext, status_code: int, message: str) -> Response:
    """Create error response using existing implementation."""
    from restmachine.state_machine import RequestStateMachine as OldStateMachine

    old_sm = OldStateMachine(ctx.app)
    old_sm.request = ctx.request
    old_sm.route_handler = ctx.route_handler

    return old_sm._create_error_response(status_code, message)


class ServiceAvailableState(State):
    """B12: Check if service is available."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "service_available")
        if callback:
            try:
                available = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not available:
                    return _create_error_response(
                        ctx, HTTPStatus.SERVICE_UNAVAILABLE, "Service Unavailable"
                    )
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.SERVICE_UNAVAILABLE, f"Service check failed: {str(e)}"
                )

        return KnownMethodState()


class KnownMethodState(State):
    """B11: Check if HTTP method is known."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "known_method")
        if callback:
            try:
                known = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not known:
                    return _create_error_response(ctx, HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.NOT_IMPLEMENTED, f"Method check failed: {str(e)}"
                )
        else:
            # Default: check against known methods
            known_methods = {
                HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT,
                HTTPMethod.DELETE, HTTPMethod.PATCH
            }
            if ctx.request.method not in known_methods:
                return _create_error_response(ctx, HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")

        return UriTooLongState()


class UriTooLongState(State):
    """B10: Check if URI is too long."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "uri_too_long")
        if callback:
            try:
                too_long = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if too_long:
                    return _create_error_response(ctx, HTTPStatus.REQUEST_URI_TOO_LONG, "URI Too Long")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.REQUEST_URI_TOO_LONG, f"URI check failed: {str(e)}"
                )

        from .service import MethodAllowedState
        return MethodAllowedState()


class MethodAllowedState(State):
    """B9: Check if method is allowed."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        callback = _get_callback(ctx, "method_allowed")
        if callback:
            try:
                allowed = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if not allowed:
                    return _create_error_response(ctx, HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed")
            except Exception as e:
                ctx.app._dependency_cache.set("exception", e)
                return _create_error_response(
                    ctx, HTTPStatus.METHOD_NOT_ALLOWED, f"Method check failed: {str(e)}"
                )

        from .request import MalformedRequestState
        return MalformedRequestState()

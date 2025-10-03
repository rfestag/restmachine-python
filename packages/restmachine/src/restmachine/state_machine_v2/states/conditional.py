"""
Conditional request states (If-Match, If-None-Match, etc.).
"""

import logging
from http import HTTPStatus
from typing import Union, Optional
from datetime import datetime

from restmachine.models import Response, HTTPMethod, etags_match
from ..base import State, StateContext
from .service import _get_callback, _create_error_response

logger = logging.getLogger(__name__)


class IfMatchState(State):
    """G3: Process If-Match header."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        if_match_etags = ctx.request.get_if_match()
        if not if_match_etags:
            return IfUnmodifiedSinceState()

        # Get current resource ETag
        current_etag = self._get_resource_etag(ctx)
        if not current_etag:
            # If resource doesn't have an ETag, If-Match fails
            return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        # Special case: If-Match: *
        if "*" in if_match_etags:
            # Resource exists (we checked earlier), so * matches
            return IfUnmodifiedSinceState()

        # Check if current ETag matches any of the requested ETags
        for requested_etag in if_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=True):
                return IfUnmodifiedSinceState()

        # No ETag matches
        return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

    def _get_resource_etag(self, ctx: StateContext) -> Optional[str]:
        """Get the current ETag for the resource."""
        callback = _get_callback(ctx, "generate_etag")
        if callback:
            try:
                etag = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if etag:
                    return f'"{etag}"' if not etag.startswith('"') and not etag.startswith('W/') else etag
            except Exception as e:
                logger.warning(f"ETag generation callback failed: {e}")
        return None


class IfUnmodifiedSinceState(State):
    """G4: Process If-Unmodified-Since header."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        if_unmodified_since = ctx.request.get_if_unmodified_since()
        if not if_unmodified_since:
            return IfNoneMatchState()

        # Get current resource last modified time
        last_modified = self._get_resource_last_modified(ctx)
        if not last_modified:
            # If resource doesn't have a Last-Modified date, precondition fails
            return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        # Check if resource was modified after the If-Unmodified-Since date
        if last_modified > if_unmodified_since:
            return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        return IfNoneMatchState()

    def _get_resource_last_modified(self, ctx: StateContext) -> Optional[datetime]:
        """Get the current Last-Modified timestamp for the resource."""
        callback = _get_callback(ctx, "last_modified")
        if callback:
            try:
                return ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
            except Exception as e:
                logger.warning(f"Last-Modified callback failed: {e}")
        return None


class IfNoneMatchState(State):
    """G5: Process If-None-Match header."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        if_none_match_etags = ctx.request.get_if_none_match()
        if not if_none_match_etags:
            return IfModifiedSinceState()

        # Get current resource ETag
        current_etag = self._get_resource_etag(ctx)

        # Special case: If-None-Match: *
        if "*" in if_none_match_etags:
            # Resource exists, so * matches - return NOT_MODIFIED for GET, PRECONDITION_FAILED for others
            if ctx.request.method in [HTTPMethod.GET]:
                return Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag} if current_etag else {})
            else:
                return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        # If resource doesn't have an ETag, If-None-Match succeeds
        if not current_etag:
            return IfModifiedSinceState()

        # Check if current ETag matches any of the requested ETags (weak comparison for If-None-Match)
        for requested_etag in if_none_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=False):
                # ETag matches - return NOT_MODIFIED for GET, PRECONDITION_FAILED for others
                if ctx.request.method in [HTTPMethod.GET]:
                    return Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag})
                else:
                    return _create_error_response(ctx, HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        # No ETag matches, continue processing
        return IfModifiedSinceState()

    def _get_resource_etag(self, ctx: StateContext) -> Optional[str]:
        """Get the current ETag for the resource."""
        callback = _get_callback(ctx, "generate_etag")
        if callback:
            try:
                etag = ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
                if etag:
                    return f'"{etag}"' if not etag.startswith('"') and not etag.startswith('W/') else etag
            except Exception as e:
                logger.warning(f"ETag generation callback failed: {e}")
        return None


class IfModifiedSinceState(State):
    """G6: Process If-Modified-Since header."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        # If-Modified-Since is only evaluated for GET requests
        if ctx.request.method != HTTPMethod.GET:
            from .negotiation import ContentTypesProvidedState
            return ContentTypesProvidedState()

        if_modified_since = ctx.request.get_if_modified_since()
        if not if_modified_since:
            from .negotiation import ContentTypesProvidedState
            return ContentTypesProvidedState()

        # Get current resource last modified time
        last_modified = self._get_resource_last_modified(ctx)
        if not last_modified:
            # If resource doesn't have a Last-Modified date, assume it's been modified
            from .negotiation import ContentTypesProvidedState
            return ContentTypesProvidedState()

        # Check if resource was modified after the If-Modified-Since date
        if last_modified <= if_modified_since:
            # Resource hasn't been modified, return NOT_MODIFIED
            return Response(HTTPStatus.NOT_MODIFIED)

        from .negotiation import ContentTypesProvidedState
        return ContentTypesProvidedState()

    def _get_resource_last_modified(self, ctx: StateContext) -> Optional[datetime]:
        """Get the current Last-Modified timestamp for the resource."""
        callback = _get_callback(ctx, "last_modified")
        if callback:
            try:
                return ctx.app._call_with_injection(callback, ctx.request, ctx.route_handler)
            except Exception as e:
                logger.warning(f"Last-Modified callback failed: {e}")
        return None

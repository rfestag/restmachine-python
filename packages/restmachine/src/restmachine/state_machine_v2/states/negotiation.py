"""
Content negotiation states.
"""

import logging
from http import HTTPStatus
from typing import Union, List

from restmachine.models import Response
from ..base import State, StateContext

logger = logging.getLogger(__name__)


class ContentTypesProvidedState(State):
    """C3: Check if acceptable content types are provided."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        # Get list of all available content types for this route
        available_types = self._get_available_content_types(ctx)

        if not available_types:
            logger.error(f"No content renderers available for {ctx.request.method.value} {ctx.request.path}")
            return Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                '{"error": "No content renderers available"}',
                content_type="application/json"
            )

        return ContentTypesAcceptedState()

    def _get_available_content_types(self, ctx: StateContext) -> List[str]:
        """Get list of all available content types for this route."""
        available_types = list(ctx.app._content_renderers.keys())

        # Add route-specific content types
        if ctx.route_handler and ctx.route_handler.content_renderers:
            available_types.extend(ctx.route_handler.content_renderers.keys())

        return list(set(available_types))  # Remove duplicates


class ContentTypesAcceptedState(State):
    """C4: Check if we can provide an acceptable content type."""

    def execute(self, ctx: StateContext) -> Union[State, Response]:
        accept_header = ctx.request.get_accept_header()

        # First try route-specific renderers
        if ctx.route_handler and ctx.route_handler.content_renderers:
            for content_type, wrapper in ctx.route_handler.content_renderers.items():
                if content_type in ctx.app._content_renderers:
                    renderer = ctx.app._content_renderers[content_type]
                    if renderer.can_render(accept_header):
                        ctx.chosen_renderer = renderer
                        from .execute import ExecuteAndRenderState
                        return ExecuteAndRenderState()

        # Fall back to global renderers
        for renderer in ctx.app._content_renderers.values():
            if renderer.can_render(accept_header):
                ctx.chosen_renderer = renderer
                from .execute import ExecuteAndRenderState
                return ExecuteAndRenderState()

        # No acceptable content type found
        available_types = list(ctx.app._content_renderers.keys())
        if ctx.route_handler and ctx.route_handler.content_renderers:
            available_types.extend(ctx.route_handler.content_renderers.keys())
        available_types = list(set(available_types))

        return Response(
            HTTPStatus.NOT_ACCEPTABLE,
            f"Not Acceptable. Available types: {', '.join(available_types)}",
            headers={"Content-Type": "text/plain"},
            request=ctx.request,
            available_content_types=available_types,
        )

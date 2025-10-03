"""
Main state machine processor.
"""

import logging
from http import HTTPStatus
from typing import Union

from restmachine.models import Request, Response
from .base import State, StateContext

logger = logging.getLogger(__name__)


class RequestStateMachine:
    """Webmachine-style state machine for processing HTTP requests.

    This processes requests by executing states until a terminal Response is returned.
    States can transition to other states or return responses directly.
    """

    def __init__(self, app):
        self.app = app

    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine.

        Args:
            request: The HTTP request to process

        Returns:
            The HTTP response

        This is the main entry point. It creates a context and executes
        states until a terminal Response is returned.
        """
        ctx = StateContext(app=self.app, request=request)
        self.app._dependency_cache.clear()

        logger.debug(f"State machine v2: {request.method.value} {request.path}")

        # Import initial state here to avoid circular imports
        from .states.route import RouteExistsState
        current_state: Union[State, Response] = RouteExistsState()

        state_count = 0
        max_states = 50  # Safety limit to prevent infinite loops

        # Execute states until we get a Response
        while not isinstance(current_state, Response):
            state_count += 1

            if state_count > max_states:
                logger.error(f"State machine exceeded max states ({max_states})")
                return self._create_error_response(
                    ctx, HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Internal error: state machine loop detected"
                )

            state_name = current_state.name
            logger.debug(f"  [{state_count}] → {state_name}")

            try:
                current_state = current_state.execute(ctx)
            except Exception as e:
                logger.error(f"Error in state {state_name}: {e}", exc_info=True)
                ctx.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    ctx, HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Internal error in {state_name}: {str(e)}"
                )

        logger.debug(f"  ✓ Complete in {state_count} states: {current_state.status_code}")
        return current_state

    def _create_error_response(
        self, ctx: StateContext, status_code: int, message: str
    ) -> Response:
        """Create an error response using the existing implementation."""
        # Reuse the existing error response creation from the old state machine
        from restmachine.state_machine import RequestStateMachine as OldStateMachine

        old_sm = OldStateMachine(ctx.app)
        old_sm.request = ctx.request
        old_sm.route_handler = ctx.route_handler

        return old_sm._create_error_response(status_code, message)

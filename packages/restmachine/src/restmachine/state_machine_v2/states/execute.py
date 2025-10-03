"""
Handler execution and response rendering state (terminal).
"""

from restmachine.models import Response
from ..base import State, StateContext


class ExecuteAndRenderState(State):
    """Execute handler and render response (terminal state).

    This is always a terminal state - it returns a Response, never another State.
    """

    def execute(self, ctx: StateContext) -> Response:
        """Execute handler and render response.

        Note: Return type is Response (not Union[State, Response]) because
        this is always a terminal state.
        """
        # Delegate to old state machine for execution
        from restmachine.state_machine import RequestStateMachine as OldSM

        old_sm = OldSM(ctx.app)
        old_sm.request = ctx.request
        old_sm.route_handler = ctx.route_handler
        old_sm.handler_dependencies = ctx.handler_dependencies
        old_sm.dependency_callbacks = ctx.dependency_callbacks

        # IMPORTANT: chosen_renderer must be set or execute_and_render will fail
        if ctx.chosen_renderer:
            old_sm.chosen_renderer = ctx.chosen_renderer
        else:
            # This should never happen if ContentTypesProvidedState ran properly
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("chosen_renderer not set in context, this is a bug!")

        return old_sm.state_execute_and_render()

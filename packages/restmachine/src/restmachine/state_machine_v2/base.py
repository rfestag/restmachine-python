"""
Base classes for the state machine pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from restmachine.models import Request, Response
    from restmachine.application import RestApplication, RouteHandler
    from restmachine.content_renderers import ContentRenderer
    from restmachine.dependencies import DependencyWrapper


@dataclass
class StateContext:
    """Shared context passed through all state transitions.

    This contains all the information needed by states to make decisions
    and perform their operations.
    """
    app: 'RestApplication'
    request: 'Request'
    route_handler: Optional['RouteHandler'] = None
    chosen_renderer: Optional['ContentRenderer'] = None
    handler_dependencies: List[str] = field(default_factory=list)
    dependency_callbacks: Dict[str, 'DependencyWrapper'] = field(default_factory=dict)
    handler_result: Any = None


class State(ABC):
    """Base class for all state machine states.

    Each state represents a decision point in the HTTP request processing flow.
    States return either the next State to transition to, or a terminal Response.
    """

    @abstractmethod
    def execute(self, ctx: StateContext) -> Union['State', 'Response']:
        """Execute this state and return next state or terminal response.

        Args:
            ctx: The shared state context

        Returns:
            Either the next State to execute, or a Response to return to the client
        """
        pass

    @property
    def name(self) -> str:
        """State name for logging and debugging."""
        return self.__class__.__name__

"""
State machine context for method-based state machine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from restmachine.models import Request
    from restmachine.application import RestApplication, RouteHandler
    from restmachine.content_renderers import ContentRenderer
    from restmachine.dependencies import DependencyWrapper


@dataclass
class StateContext:
    """Shared context for state machine execution.

    This contains all the information needed by state methods to make decisions
    and perform their operations.
    """
    app: 'RestApplication'
    request: 'Request'
    route_handler: Optional['RouteHandler'] = None
    chosen_renderer: Optional['ContentRenderer'] = None
    handler_dependencies: List[str] = field(default_factory=list)
    dependency_callbacks: Dict[str, 'DependencyWrapper'] = field(default_factory=dict)
    handler_result: Any = None

"""
Adapter interface for handling different event sources that execute the app.

Adapters convert between external platform formats (AWS Lambda, Azure Functions, etc.)
and the internal Request/Response models used by RestMachine.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import Request, Response


class Adapter(ABC):
    """Abstract base class for adapters that convert external events to app requests."""

    @abstractmethod
    def handle_event(self, event: Any, context: Optional[Any] = None) -> Any:
        """
        Handle an external event and return the appropriate response format.

        Args:
            event: The external event (e.g., AWS Lambda event)
            context: Optional context (e.g., AWS Lambda context)

        Returns:
            Response in the format expected by the external system
        """
        pass

    @abstractmethod
    def convert_to_request(self, event: Any, context: Optional[Any] = None) -> Request:
        """
        Convert an external event to a Request object.

        Args:
            event: The external event
            context: Optional context

        Returns:
            Request object that can be processed by the app
        """
        pass

    @abstractmethod
    def convert_from_response(self, response: Response, event: Any, context: Optional[Any] = None) -> Any:
        """
        Convert a Response object to the format expected by the external system.

        Args:
            response: Response from the app
            event: Original external event
            context: Optional context

        Returns:
            Response in the format expected by the external system
        """
        pass
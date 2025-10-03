"""
Method-based state machine implementation following webmachine-ruby's pattern.

Each state is a method that returns either the next method or a Response.
This eliminates object creation overhead while maintaining clean state transitions.
"""

from .base import StateContext
from .machine_methods import RequestStateMachine

__all__ = ["StateContext", "RequestStateMachine"]

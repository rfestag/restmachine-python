"""
Hook decorators for model lifecycle and query extensions.

Provides declarative way to extend models and queries via mixins.
"""

from typing import Callable, Any, TypeVar

F = TypeVar('F', bound=Callable[..., Any])


def before_save(func: F) -> F:
    """
    Decorator to mark a method as a before_save hook.

    Called before the model is saved to the backend.

    Example:
        >>> class TimestampMixin:
        ...     @before_save
        ...     def set_timestamps(self):
        ...         self.updated_at = datetime.now()
    """
    setattr(func, '_is_before_save_hook', True)  # type: ignore[attr-defined]
    return func


def after_save(func: F) -> F:
    """
    Decorator to mark a method as an after_save hook.

    Called after the model is saved to the backend.

    Example:
        >>> class NotificationMixin:
        ...     @after_save
        ...     def send_notification(self):
        ...         send_email(self.email, "Record saved")
    """
    setattr(func, '_is_after_save_hook', True)  # type: ignore[attr-defined]
    return func


def after_load(func: F) -> F:
    """
    Decorator to mark a method as an after_load hook.

    Called after data is loaded from backend and model is instantiated.

    Example:
        >>> class GeoMixin:
        ...     @after_load
        ...     def deserialize_geo(self):
        ...         if self._location_geo:
        ...             self.location = Point(self._location_geo['coordinates'])
    """
    setattr(func, '_is_after_load_hook', True)  # type: ignore[attr-defined]
    return func


def query_method(func: F) -> F:
    """
    Decorator to add a custom method to QueryBuilder.

    Example:
        >>> class GeoMixin:
        ...     @query_method
        ...     def near(query, point: Point, radius: float):
        ...         # query is the QueryBuilder instance
        ...         return query.filter(...)
    """
    setattr(func, '_is_query_method', True)  # type: ignore[attr-defined]
    setattr(func, '_query_method_name', func.__name__)  # type: ignore[attr-defined]
    return func


def query_operator_for_type(field_type: type, operator: str):
    """
    Decorator to register a query operator for a specific field type.

    Args:
        field_type: The type of field this operator applies to (e.g., Point)
        operator: The operator name (e.g., 'near', 'contains')

    Example:
        >>> @query_operator_for_type(Point, 'near')
        ... def handle_point_near(query, field_name: str, value: tuple):
        ...     point, radius = value
        ...     return query.add_result_filter(...)
    """
    def decorator(func: F) -> F:
        setattr(func, '_is_query_operator', True)  # type: ignore[attr-defined]
        setattr(func, '_operator_type', field_type)  # type: ignore[attr-defined]
        setattr(func, '_operator_name', operator)  # type: ignore[attr-defined]
        return func
    return decorator


def query_operator_for_types(field_types: list[type], operator: str):
    """
    Decorator to register a query operator for multiple field types.

    Args:
        field_types: List of types this operator applies to
        operator: The operator name

    Example:
        >>> @query_operator_for_types([Point, Polygon], 'within')
        ... def handle_geo_within(query, field_name: str, bounds: Polygon):
        ...     return query.add_result_filter(...)
    """
    def decorator(func: F) -> F:
        setattr(func, '_is_query_operator', True)  # type: ignore[attr-defined]
        setattr(func, '_operator_types', field_types)  # type: ignore[attr-defined]
        setattr(func, '_operator_name', operator)  # type: ignore[attr-defined]
        return func
    return decorator

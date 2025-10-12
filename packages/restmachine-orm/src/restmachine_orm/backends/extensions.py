"""
Backend extension system for mixins.

Extensions allow mixins to provide backend-specific behavior without backends
needing to know about specific mixins.
"""

from abc import ABC
from typing import Type, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from restmachine_orm.backends.base import Backend
    from restmachine_orm.query.base import QueryBuilder
    from restmachine_orm.models.base import Model


class BackendExtension(ABC):
    """
    Base class for backend-specific mixin extensions.

    Mixins can define inner classes that extend this to provide backend-specific
    behavior. Extensions are discovered automatically by backends and their hooks
    are called at appropriate lifecycle points.

    Example:
        >>> class MyMixin:
        ...     my_field: Optional[str] = None
        ...
        ...     class DynamoDBExtension(BackendExtension):
        ...         backend_name = 'dynamodb'
        ...
        ...         def serialize(self, data: dict) -> dict:
        ...             # Transform data before storage
        ...             return data
        ...
        ...     class MemoryExtension(BackendExtension):
        ...         backend_name = 'memory'
        ...
        ...         def serialize(self, data: dict) -> dict:
        ...             # Different transformation for memory backend
        ...             return data

    Attributes:
        backend_name: The name of the backend this extension supports.
                     Use '*' for universal extensions that work with all backends.
        mixin_class: The mixin class this extension belongs to
        backend: The backend instance
    """

    # Subclasses must define which backend this extension is for
    # Use '*' for universal extensions
    backend_name: Optional[str] = None

    def __init__(self, mixin_class: Type, backend: 'Backend'):
        """
        Initialize extension.

        Args:
            mixin_class: The mixin class this extension belongs to
            backend: The backend instance
        """
        self.mixin_class = mixin_class
        self.backend = backend

    # === Optional Hook Methods (override as needed) ===

    def serialize(self, data: dict) -> dict:
        """
        Transform data before writing to backend.

        Called by backend.create() and backend.update() before data is written.
        Allows transforming field values for backend-specific requirements.

        Args:
            data: Dictionary of field names to values

        Returns:
            Transformed data dictionary

        Example:
            >>> def serialize(self, data: dict) -> dict:
            ...     # Convert datetime to Unix timestamp for DynamoDB TTL
            ...     if 'expires_at' in data and data['expires_at']:
            ...         data['expires_at'] = int(data['expires_at'].timestamp())
            ...     return data
        """
        return data

    def deserialize(self, data: dict) -> dict:
        """
        Transform data after reading from backend.

        Called by backend.get() and query results after data is read.
        Allows converting backend-specific formats back to Python types.

        Args:
            data: Dictionary of field names to values from backend

        Returns:
            Transformed data dictionary

        Example:
            >>> def deserialize(self, data: dict) -> dict:
            ...     # Convert Unix timestamp back to datetime
            ...     if 'expires_at' in data and isinstance(data['expires_at'], int):
            ...         data['expires_at'] = datetime.fromtimestamp(data['expires_at'])
            ...     return data
        """
        return data

    def configure_backend(self, model_class: Type['Model']) -> None:
        """
        Configure backend for this mixin (called once per model).

        Called the first time a model using this mixin interacts with the backend.
        Use this to set up backend-specific features like indexes, TTL, analyzers, etc.

        Args:
            model_class: The model class using this mixin

        Example:
            >>> def configure_backend(self, model_class: Type[Model]) -> None:
            ...     # Enable TTL on DynamoDB table
            ...     self.backend.enable_ttl('expires_at')
        """
        pass

    def modify_query(self, query_builder: 'QueryBuilder') -> 'QueryBuilder':
        """
        Modify query behavior.

        Called when a query builder is created for a model using this mixin.
        Allows adding filters, changing behavior, or configuring query options.

        Args:
            query_builder: The query builder being created

        Returns:
            Modified query builder

        Example:
            >>> def modify_query(self, query_builder: 'QueryBuilder') -> 'QueryBuilder':
            ...     # Add automatic filtering for expired items
            ...     query_builder.add_result_filter(
            ...         'expiration',
            ...         lambda item: not item.is_expired()
            ...     )
            ...     return query_builder
        """
        return query_builder

    def validate(self, data: dict) -> None:
        """
        Validate data for this backend (can raise exceptions).

        Called before data is written to the backend. Allows backend-specific
        validation that goes beyond Pydantic validation.

        Args:
            data: Dictionary of field names to values

        Raises:
            ValueError: If validation fails

        Example:
            >>> def validate(self, data: dict) -> None:
            ...     # DynamoDB has a 400KB item size limit
            ...     import json
            ...     if len(json.dumps(data)) > 400_000:
            ...         raise ValueError("Item exceeds DynamoDB size limit")
        """
        pass

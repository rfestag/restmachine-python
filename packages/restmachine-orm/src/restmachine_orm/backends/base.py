"""
Base backend interface for RestMachine ORM.

Defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model
    from restmachine_orm.query.base import QueryBuilder
    from restmachine_orm.backends.adapters import ModelAdapter
    from restmachine_orm.backends.extensions import BackendExtension


class Backend(ABC):
    """
    Abstract base class for storage backends.

    All backends (DynamoDB, OpenSearch, Composite, etc.) must implement
    this interface to provide consistent CRUD operations.

    Each backend has an adapter that knows how to map models to the
    backend's native storage format.

    Backends support mixin extensions via the extension discovery system.
    Mixins can define inner classes that extend BackendExtension to provide
    backend-specific behavior.
    """

    def __init__(self, adapter: "ModelAdapter"):
        """
        Initialize backend with an adapter.

        Args:
            adapter: Adapter for mapping models to storage format
        """
        self.adapter = adapter
        self._configured_models: set[Type] = set()
        self._model_extensions: dict[Type, list['BackendExtension']] = {}

    @abstractmethod
    def create(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new record in the backend.

        Args:
            model_class: The model class being created
            data: Dictionary of field values

        Returns:
            Dictionary of created record data

        Raises:
            ValidationError: If data validation fails
            DuplicateKeyError: If unique constraint is violated
        """
        pass

    @abstractmethod
    def upsert(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create or update a record (upsert).

        If a record with the same key exists, it will be overwritten.
        Unlike create(), this does not raise DuplicateKeyError.

        Args:
            model_class: The model class being upserted
            data: Dictionary of field values

        Returns:
            Dictionary of upserted record data

        Raises:
            ValidationError: If data validation fails
        """
        pass

    @abstractmethod
    def get(self, model_class: type["Model"], **filters: Any) -> Optional[dict[str, Any]]:
        """
        Get a single record by primary key or unique field.

        Args:
            model_class: The model class to query
            **filters: Filter conditions (typically primary key)

        Returns:
            Dictionary of record data, or None if not found
        """
        pass

    @abstractmethod
    def update(
        self,
        model_class: type["Model"],
        instance: "Model"
    ) -> dict[str, Any]:
        """
        Update an existing record.

        The backend is responsible for extracting keys from the instance
        using the model's metadata (e.g., partition key, sort key decorators).

        Args:
            model_class: The model class being updated
            instance: The model instance with updated data

        Returns:
            Dictionary of updated record data

        Raises:
            NotFoundError: If record doesn't exist
            ValidationError: If update data is invalid
        """
        pass

    @abstractmethod
    def delete(self, model_class: type["Model"], instance: "Model") -> bool:
        """
        Delete a record.

        The backend is responsible for extracting keys from the instance
        using the model's metadata (e.g., partition key, sort key decorators).

        Args:
            model_class: The model class being deleted
            instance: The model instance to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def query(self, model_class: type["Model"]) -> "QueryBuilder":
        """
        Create a query builder for this backend.

        Args:
            model_class: The model class to query

        Returns:
            QueryBuilder instance for fluent query construction

        Example:
            >>> backend.query(User).filter(age__gte=18).limit(10).all()
        """
        pass

    @abstractmethod
    def count(self, model_class: type["Model"], **filters: Any) -> int:
        """
        Count records matching filters.

        Args:
            model_class: The model class to count
            **filters: Optional filter conditions

        Returns:
            Number of matching records
        """
        pass

    @abstractmethod
    def exists(self, model_class: type["Model"], **filters: Any) -> bool:
        """
        Check if a record exists.

        Args:
            model_class: The model class to check
            **filters: Filter conditions

        Returns:
            True if at least one record matches, False otherwise
        """
        pass

    def batch_create(
        self,
        model_class: type["Model"],
        items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Create multiple records in a single batch operation.

        Default implementation calls create() for each item.
        Backends should override with optimized batch operations.

        Args:
            model_class: The model class being created
            items: List of record data dictionaries

        Returns:
            List of created record data

        Raises:
            ValidationError: If any item validation fails
        """
        return [self.create(model_class, item) for item in items]

    def batch_get(
        self,
        model_class: type["Model"],
        keys: list[dict[str, Any]]
    ) -> list[Optional[dict[str, Any]]]:
        """
        Get multiple records by their keys in a single batch operation.

        Default implementation calls get() for each key.
        Backends should override with optimized batch operations.

        Args:
            model_class: The model class to query
            keys: List of key dictionaries

        Returns:
            List of record data (None for missing records)
        """
        return [self.get(model_class, **key) for key in keys]

    def initialize(self) -> None:
        """
        Initialize the backend (create tables, indexes, etc.).

        Optional method for backends that need setup.
        """
        pass

    def close(self) -> None:
        """
        Close connections and cleanup resources.

        Optional method for backends with persistent connections.
        """
        pass

    # === Extension System ===

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """
        Backend identifier (e.g., 'dynamodb', 'memory', 'opensearch').

        Used by extensions to determine if they should be activated.
        """
        raise NotImplementedError

    def _discover_extensions(self, model_class: Type["Model"]) -> list['BackendExtension']:
        """
        Discover and instantiate all backend extensions for this model.

        Walks the model's MRO looking for BackendExtension subclasses that match
        this backend's name or are universal ('*').

        Args:
            model_class: The model class to discover extensions for

        Returns:
            List of instantiated extension objects
        """
        if model_class in self._model_extensions:
            return self._model_extensions[model_class]

        from restmachine_orm.backends.extensions import BackendExtension

        extensions = []
        seen_extension_classes = set()  # Track which extension classes we've seen

        # Walk MRO to find all mixin classes
        for base in model_class.__mro__:
            # Skip Model and BaseModel classes
            if base.__name__ in ('Model', 'BaseModel'):
                continue

            # Look for nested Extension classes in this mixin
            # Only look at attributes defined directly on this class, not inherited
            for attr_name in dir(base):
                # Skip if this attribute is inherited from a parent class
                if attr_name not in base.__dict__:
                    continue

                try:
                    attr = getattr(base, attr_name)

                    # Check if it's a class (not instance) with backend_name attribute
                    # It can either inherit from BackendExtension or just have the interface
                    if (isinstance(attr, type) and
                        hasattr(attr, 'backend_name') and
                        attr.backend_name is not None):

                        # Skip the BackendExtension base class itself
                        if attr is BackendExtension:
                            continue

                        # Skip if we've already seen this extension class
                        if attr in seen_extension_classes:
                            continue

                        # Check if this extension is for our backend or universal
                        if attr.backend_name in (self.backend_name, '*'):
                            # Instantiate the extension
                            extension = attr(base, self)
                            extensions.append(extension)
                            seen_extension_classes.add(attr)

                except (AttributeError, TypeError):
                    continue

        # Cache for this model
        self._model_extensions[model_class] = extensions
        return extensions

    def _ensure_configured(self, model_class: Type["Model"]) -> None:
        """
        Ensure all extensions are configured for this model (once).

        Calls configure_backend() on each extension the first time a model
        is used with this backend.

        Args:
            model_class: The model class to configure
        """
        if model_class in self._configured_models:
            return

        extensions = self._discover_extensions(model_class)

        # Call configure_backend on all extensions
        for extension in extensions:
            if hasattr(extension, 'configure_backend') and callable(extension.configure_backend):
                extension.configure_backend(model_class)

        self._configured_models.add(model_class)

    def _call_serialize_hooks(self, model_class: Type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Call serialize hooks on all extensions.

        Args:
            model_class: The model class
            data: Data to serialize

        Returns:
            Serialized data (after all extensions have processed it)
        """
        extensions = self._discover_extensions(model_class)

        for extension in extensions:
            if hasattr(extension, 'serialize') and callable(extension.serialize):
                data = extension.serialize(data)

        return data

    def _call_deserialize_hooks(self, model_class: Type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Call deserialize hooks on all extensions.

        Args:
            model_class: The model class
            data: Data to deserialize

        Returns:
            Deserialized data (after all extensions have processed it)
        """
        extensions = self._discover_extensions(model_class)

        for extension in extensions:
            if hasattr(extension, 'deserialize') and callable(extension.deserialize):
                data = extension.deserialize(data)

        return data

    def _call_validate_hooks(self, model_class: Type["Model"], data: dict[str, Any]) -> None:
        """
        Call validate hooks on all extensions.

        Args:
            model_class: The model class
            data: Data to validate

        Raises:
            ValidationError: If any extension validation fails
        """
        extensions = self._discover_extensions(model_class)

        for extension in extensions:
            if hasattr(extension, 'validate') and callable(extension.validate):
                extension.validate(data)

    def _call_modify_query_hooks(self, model_class: Type["Model"], query_builder: "QueryBuilder") -> "QueryBuilder":
        """
        Call modify_query hooks on all extensions.

        Args:
            model_class: The model class
            query_builder: Query builder to modify

        Returns:
            Modified query builder
        """
        extensions = self._discover_extensions(model_class)

        for extension in extensions:
            if hasattr(extension, 'modify_query') and callable(extension.modify_query):
                query_builder = extension.modify_query(query_builder)

        return query_builder


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class NotFoundError(BackendError):
    """Record not found in backend."""
    pass


class DuplicateKeyError(BackendError):
    """Unique constraint violation."""
    pass


class ValidationError(BackendError):
    """Data validation failed."""
    pass

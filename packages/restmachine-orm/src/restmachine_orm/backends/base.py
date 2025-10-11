"""
Base backend interface for RestMachine ORM.

Defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model
    from restmachine_orm.query.base import QueryBuilder
    from restmachine_orm.backends.adapters import ModelAdapter


class Backend(ABC):
    """
    Abstract base class for storage backends.

    All backends (DynamoDB, OpenSearch, Composite, etc.) must implement
    this interface to provide consistent CRUD operations.

    Each backend has an adapter that knows how to map models to the
    backend's native storage format.
    """

    def __init__(self, adapter: "ModelAdapter"):
        """
        Initialize backend with an adapter.

        Args:
            adapter: Adapter for mapping models to storage format
        """
        self.adapter = adapter

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

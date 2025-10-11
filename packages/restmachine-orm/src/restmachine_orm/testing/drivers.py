"""
Driver implementations for different backend environments.

This is the third layer in Dave Farley's 4-layer testing architecture.
Drivers know how to translate DSL operations into actual backend calls.
"""

from abc import ABC, abstractmethod
from typing import Type, Optional, Any

from restmachine_orm.backends.memory import InMemoryBackend
from restmachine_orm.backends.adapters import InMemoryAdapter

from .dsl import (
    CreateOperation,
    GetOperation,
    UpdateOperation,
    DeleteOperation,
    UpsertOperation,
    QueryOperation,
    OperationResult,
)


class DriverInterface(ABC):
    """Abstract interface for all ORM test drivers."""

    @abstractmethod
    def execute_create(self, operation: CreateOperation) -> OperationResult:
        """Execute a create operation."""
        pass

    @abstractmethod
    def execute_get(self, operation: GetOperation) -> OperationResult:
        """Execute a get operation."""
        pass

    @abstractmethod
    def execute_update(self, operation: UpdateOperation) -> OperationResult:
        """Execute an update operation."""
        pass

    @abstractmethod
    def execute_delete(self, operation: DeleteOperation) -> OperationResult:
        """Execute a delete operation."""
        pass

    @abstractmethod
    def execute_upsert(self, operation: UpsertOperation) -> OperationResult:
        """Execute an upsert operation."""
        pass

    @abstractmethod
    def execute_query(self, operation: QueryOperation) -> OperationResult:
        """Execute a query operation."""
        pass

    @abstractmethod
    def count(self, model_class: Type, **filters: Any) -> int:
        """Count instances matching filters."""
        pass

    @abstractmethod
    def exists(self, model_class: Type, **filters: Any) -> bool:
        """Check if instances exist matching filters."""
        pass

    @abstractmethod
    def clear(self, model_class: Optional[Type] = None) -> None:
        """Clear storage for testing."""
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Get the name of the backend being tested."""
        pass

    @abstractmethod
    def setup_backend(self, model_class: Type) -> None:
        """Set up backend for a model class."""
        pass


class InMemoryDriver(DriverInterface):
    """
    Driver that tests against the InMemory backend.

    This is the reference implementation and tests the ORM core functionality
    without external dependencies.
    """

    def __init__(self):
        """Initialize with InMemory backend."""
        self.backend = InMemoryBackend(InMemoryAdapter())

    def execute_create(self, operation: CreateOperation) -> OperationResult:
        """Execute a create operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Create instance
            instance = operation.model_class.create(**operation.data)

            return OperationResult(
                success=True,
                instance=instance,
                data=instance.model_dump()
            )
        except Exception as e:
            if operation.should_fail and operation.expected_error:
                if isinstance(e, operation.expected_error):
                    return OperationResult(success=False, error=e)
            # Re-raise if not expected
            if not operation.should_fail:
                return OperationResult(success=False, error=e)
            raise

    def execute_get(self, operation: GetOperation) -> OperationResult:
        """Execute a get operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Get instance
            instance = operation.model_class.get(**operation.filters)

            if instance is None and operation.should_exist:
                return OperationResult(
                    success=True,
                    instance=None,
                    data=None
                )

            return OperationResult(
                success=True,
                instance=instance,
                data=instance.model_dump() if instance else None
            )
        except Exception as e:
            return OperationResult(success=False, error=e)

    def execute_update(self, operation: UpdateOperation) -> OperationResult:
        """Execute an update operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Apply changes
            for key, value in operation.changes.items():
                setattr(operation.instance, key, value)

            # Save
            operation.instance.save()

            return OperationResult(
                success=True,
                instance=operation.instance,
                data=operation.instance.model_dump()
            )
        except Exception as e:
            if operation.should_fail:
                return OperationResult(success=False, error=e)
            return OperationResult(success=False, error=e)

    def execute_delete(self, operation: DeleteOperation) -> OperationResult:
        """Execute a delete operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Delete
            success = operation.instance.delete()

            return OperationResult(
                success=success,
                data={"deleted": success}
            )
        except Exception as e:
            return OperationResult(success=False, error=e)

    def execute_upsert(self, operation: UpsertOperation) -> OperationResult:
        """Execute an upsert operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Upsert
            instance = operation.model_class.upsert(**operation.data)

            return OperationResult(
                success=True,
                instance=instance,
                data=instance.model_dump()
            )
        except Exception as e:
            if operation.should_fail:
                return OperationResult(success=False, error=e)
            return OperationResult(success=False, error=e)

    def execute_query(self, operation: QueryOperation) -> OperationResult:
        """Execute a query operation."""
        try:
            # Set backend for model
            self.setup_backend(operation.model_class)

            # Build query
            query = operation.model_class.where(**operation.filters) if operation.filters else operation.model_class.where()

            # Apply ordering
            if operation.order_by:
                for order in operation.order_by:
                    query = query.order_by(order)

            # Apply limit/offset
            if operation.limit:
                query = query.limit(operation.limit)
            if operation.offset:
                query = query.offset(operation.offset)

            # Execute
            instances = query.all()

            return OperationResult(
                success=True,
                data=instances
            )
        except Exception as e:
            return OperationResult(success=False, error=e)

    def count(self, model_class: Type, **filters: Any) -> int:
        """Count instances matching filters."""
        self.setup_backend(model_class)
        result: int = model_class.where(**filters).count() if filters else model_class.where().count()
        return result

    def exists(self, model_class: Type, **filters: Any) -> bool:
        """Check if instances exist matching filters."""
        self.setup_backend(model_class)
        result: bool = model_class.where(**filters).exists()
        return result

    def clear(self, model_class: Optional[Type] = None) -> None:
        """Clear storage for testing."""
        self.backend.clear(model_class)

    def get_backend_name(self) -> str:
        """Get the name of the backend being tested."""
        return "InMemory"

    def setup_backend(self, model_class: Type) -> None:
        """Set up backend for a model class."""
        model_class.Meta.backend = self.backend

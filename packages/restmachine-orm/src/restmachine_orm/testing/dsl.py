"""
DSL (Domain Specific Language) for ORM test actions.

This is the second layer in Dave Farley's 4-layer testing architecture:
1. Test Layer (actual test methods)
2. DSL Layer (this file) - describes what we want to do in business terms
3. Driver Layer - knows how to interact with the system
4. System Under Test (restmachine-orm library)
"""

from typing import Any, Optional, Type, List, Dict, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model
    from restmachine_orm.testing.drivers import DriverInterface


@dataclass
class ModelOperation:
    """Base class for model operations."""
    model_class: "Type[Model]"


@dataclass
class CreateOperation(ModelOperation):
    """Represents a model create operation."""
    data: Dict[str, Any]
    should_fail: bool = False
    expected_error: Optional[Type[Exception]] = None


@dataclass
class GetOperation(ModelOperation):
    """Represents a model get operation."""
    filters: Dict[str, Any]
    should_exist: bool = True


@dataclass
class UpdateOperation(ModelOperation):
    """Represents a model update operation."""
    instance: Any  # Model instance
    changes: Dict[str, Any]
    should_fail: bool = False


@dataclass
class DeleteOperation(ModelOperation):
    """Represents a model delete operation."""
    instance: Any  # Model instance
    should_succeed: bool = True


@dataclass
class UpsertOperation(ModelOperation):
    """Represents a model upsert operation."""
    data: Dict[str, Any]
    should_fail: bool = False


@dataclass
class QueryOperation(ModelOperation):
    """Represents a query operation."""
    filters: Dict[str, Any] = field(default_factory=dict)
    order_by: Optional[List[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    expected_count: Optional[int] = None


@dataclass
class OperationResult:
    """Result of an operation."""
    success: bool
    data: Any = None
    error: Optional[Exception] = None
    instance: Any = None  # Model instance if applicable


class OrmDsl:
    """
    Domain-Specific Language for ORM testing.

    This provides a high-level, business-focused way to describe ORM operations
    without knowing backend implementation details.
    """

    def __init__(self, driver: "DriverInterface"):
        """Initialize with a driver that knows how to execute operations."""
        self._driver: "DriverInterface" = driver

    @property
    def driver(self):
        """Access the underlying driver for driver-specific operations."""
        return self._driver

    # Model operations
    def create_model(self, model_class: Type, **data: Any) -> OperationResult:
        """
        Create a new model instance.

        Args:
            model_class: The model class to create
            **data: Field values for the model

        Returns:
            OperationResult with created instance
        """
        op = CreateOperation(model_class=model_class, data=data)
        return self._driver.execute_create(op)

    def get_model(self, model_class: Type, **filters: Any) -> OperationResult:
        """
        Get a model instance by filters.

        Args:
            model_class: The model class to query
            **filters: Filter conditions

        Returns:
            OperationResult with instance or None
        """
        op = GetOperation(model_class=model_class, filters=filters)
        return self._driver.execute_get(op)

    def update_model(self, instance: Any, **changes: Any) -> OperationResult:
        """
        Update a model instance.

        Args:
            instance: Model instance to update
            **changes: Fields to change

        Returns:
            OperationResult with updated instance
        """
        op = UpdateOperation(
            model_class=instance.__class__,
            instance=instance,
            changes=changes
        )
        return self._driver.execute_update(op)

    def delete_model(self, instance: Any) -> OperationResult:
        """
        Delete a model instance.

        Args:
            instance: Model instance to delete

        Returns:
            OperationResult indicating success
        """
        op = DeleteOperation(
            model_class=instance.__class__,
            instance=instance
        )
        return self._driver.execute_delete(op)

    def upsert_model(self, model_class: Type, **data: Any) -> OperationResult:
        """
        Upsert a model instance (create or update).

        Args:
            model_class: The model class to upsert
            **data: Field values for the model

        Returns:
            OperationResult with upserted instance
        """
        op = UpsertOperation(model_class=model_class, data=data)
        return self._driver.execute_upsert(op)

    def query_models(
        self,
        model_class: Type,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> OperationResult:
        """
        Query for multiple model instances.

        Args:
            model_class: The model class to query
            filters: Optional filter conditions
            order_by: Optional ordering
            limit: Optional result limit
            offset: Optional result offset

        Returns:
            OperationResult with list of instances
        """
        op = QueryOperation(
            model_class=model_class,
            filters=filters or {},
            order_by=order_by,
            limit=limit,
            offset=offset
        )
        return self._driver.execute_query(op)

    def count_models(self, model_class: Type, **filters: Any) -> int:
        """
        Count model instances matching filters.

        Args:
            model_class: The model class to count
            **filters: Filter conditions

        Returns:
            Count of matching instances
        """
        return self._driver.count(model_class, **filters)

    def model_exists(self, model_class: Type, **filters: Any) -> bool:
        """
        Check if a model instance exists.

        Args:
            model_class: The model class to check
            **filters: Filter conditions

        Returns:
            True if at least one instance matches
        """
        return self._driver.exists(model_class, **filters)

    def all_models(self, model_class: Type) -> List[Any]:
        """
        Get all instances of a model.

        Args:
            model_class: The model class to query

        Returns:
            List of all instances
        """
        result = self.query_models(model_class)
        return result.data if result.success else []

    def clear_storage(self, model_class: Optional[Type] = None) -> None:
        """
        Clear storage for testing.

        Args:
            model_class: Optional model class to clear. If None, clears all.
        """
        self._driver.clear(model_class)

    # Convenience methods for common test patterns
    def create_and_verify(self, model_class: Type, **data: Any) -> Any:
        """
        Create a model and verify it was created successfully.

        Args:
            model_class: The model class to create
            **data: Field values

        Returns:
            Created model instance

        Raises:
            AssertionError: If creation failed
        """
        result = self.create_model(model_class, **data)
        assert result.success, f"Failed to create {model_class.__name__}: {result.error}"  # nosec B101
        assert result.instance is not None, "Created instance is None"  # nosec B101

        # Verify persisted flag
        assert hasattr(result.instance, '_is_persisted'), "Instance missing _is_persisted attribute"  # nosec B101
        assert result.instance._is_persisted is True, "Instance not marked as persisted"  # nosec B101

        # Verify data
        for key, value in data.items():
            actual_value = getattr(result.instance, key, None)
            assert actual_value == value, f"Field {key}: expected {value}, got {actual_value}"  # nosec B101

        return result.instance

    def get_and_verify_exists(self, model_class: Type, **filters: Any) -> Any:
        """
        Get a model and verify it exists.

        Args:
            model_class: The model class to get
            **filters: Filter conditions

        Returns:
            Retrieved model instance

        Raises:
            AssertionError: If model doesn't exist
        """
        result = self.get_model(model_class, **filters)
        assert result.success, f"Failed to get {model_class.__name__}: {result.error}"  # nosec B101
        assert result.instance is not None, f"{model_class.__name__} not found with filters {filters}"  # nosec B101
        return result.instance

    def get_and_verify_not_exists(self, model_class: Type, **filters: Any) -> None:
        """
        Get a model and verify it doesn't exist.

        Args:
            model_class: The model class to get
            **filters: Filter conditions

        Raises:
            AssertionError: If model exists
        """
        result = self.get_model(model_class, **filters)
        assert result.instance is None, f"{model_class.__name__} unexpectedly found with filters {filters}"  # nosec B101

    def update_and_verify(self, instance: Any, **changes: Any) -> Any:
        """
        Update a model and verify the update succeeded.

        Args:
            instance: Model instance to update
            **changes: Fields to change

        Returns:
            Updated model instance

        Raises:
            AssertionError: If update failed
        """
        result = self.update_model(instance, **changes)
        assert result.success, f"Failed to update {instance.__class__.__name__}: {result.error}"  # nosec B101

        # Verify changes
        for key, value in changes.items():
            actual_value = getattr(result.instance, key, None)
            assert actual_value == value, f"Field {key}: expected {value}, got {actual_value}"  # nosec B101

        return result.instance

    def delete_and_verify(self, instance: Any) -> None:
        """
        Delete a model and verify deletion succeeded.

        Args:
            instance: Model instance to delete

        Raises:
            AssertionError: If deletion failed
        """
        result = self.delete_model(instance)
        assert result.success, f"Failed to delete {instance.__class__.__name__}: {result.error}"  # nosec B101

    def upsert_and_verify(self, model_class: Type, **data: Any) -> Any:
        """
        Upsert a model and verify it succeeded.

        Args:
            model_class: The model class to upsert
            **data: Field values

        Returns:
            Upserted model instance

        Raises:
            AssertionError: If upsert failed
        """
        result = self.upsert_model(model_class, **data)
        assert result.success, f"Failed to upsert {model_class.__name__}: {result.error}"  # nosec B101
        assert result.instance is not None, "Upserted instance is None"  # nosec B101
        assert result.instance._is_persisted is True, "Instance not marked as persisted"  # nosec B101
        return result.instance

    def query_and_verify_count(
        self,
        model_class: Type,
        expected_count: int,
        **filters: Any
    ) -> List[Any]:
        """
        Query models and verify the count matches expected.

        Args:
            model_class: The model class to query
            expected_count: Expected number of results
            **filters: Filter conditions

        Returns:
            List of retrieved instances

        Raises:
            AssertionError: If count doesn't match
        """
        result = self.query_models(model_class, filters=filters)
        assert result.success, f"Failed to query {model_class.__name__}: {result.error}"  # nosec B101

        actual_count = len(result.data) if result.data else 0
        assert actual_count == expected_count, \
            f"Expected {expected_count} instances, got {actual_count}"  # nosec B101

        return list(result.data) if result.data else []

    def expect_create_failure(
        self,
        model_class: Type,
        expected_error: Type[Exception],
        **data: Any
    ) -> None:
        """
        Expect a create operation to fail with a specific error.

        Args:
            model_class: The model class to create
            expected_error: Expected exception type
            **data: Field values

        Raises:
            AssertionError: If operation didn't fail as expected
        """
        result = self.create_model(model_class, **data)
        assert not result.success, f"Expected {model_class.__name__}.create to fail, but it succeeded"  # nosec B101
        assert result.error is not None, "Expected error but got None"  # nosec B101
        assert isinstance(result.error, expected_error), \
            f"Expected {expected_error.__name__}, got {type(result.error).__name__}"  # nosec B101

    def expect_update_failure(
        self,
        instance: Any,
        expected_error: Type[Exception],
        **changes: Any
    ) -> None:
        """
        Expect an update operation to fail with a specific error.

        Args:
            instance: Model instance to update
            expected_error: Expected exception type
            **changes: Fields to change

        Raises:
            AssertionError: If operation didn't fail as expected
        """
        result = self.update_model(instance, **changes)
        assert not result.success, "Expected update to fail, but it succeeded"  # nosec B101
        assert result.error is not None, "Expected error but got None"  # nosec B101
        assert isinstance(result.error, expected_error), \
            f"Expected {expected_error.__name__}, got {type(result.error).__name__}"  # nosec B101

    # Backend introspection
    def get_backend_name(self) -> str:
        """Get the name of the current backend."""
        return self._driver.get_backend_name()

    def is_backend(self, name: str) -> bool:
        """Check if current backend matches the given name."""
        return self._driver.get_backend_name() == name

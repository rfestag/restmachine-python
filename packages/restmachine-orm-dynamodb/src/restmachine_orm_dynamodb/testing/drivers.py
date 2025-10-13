"""
Driver implementation for DynamoDB backend testing.

This driver integrates with RestMachine ORM's testing framework.
"""

from typing import Type, Optional, Any

from restmachine_orm_testing import (  # type: ignore[import-not-found]
    DriverInterface,
    CreateOperation,
    GetOperation,
    UpdateOperation,
    DeleteOperation,
    UpsertOperation,
    QueryOperation,
    OperationResult,
)

from ..backend import DynamoDBBackend


class DynamoDBDriver(DriverInterface):
    """
    Driver that tests against the DynamoDB backend.

    This driver uses moto to mock DynamoDB for testing.
    """

    def __init__(self, table_name: str = "test-table", region_name: str = "us-east-1"):
        """
        Initialize with DynamoDB backend.

        Args:
            table_name: DynamoDB table name for testing
            region_name: AWS region name
        """
        self.backend = DynamoDBBackend(
            table_name=table_name,
            region_name=region_name
        )
        self.table_name = table_name
        self.region_name = region_name

    def execute_create(self, operation: CreateOperation) -> OperationResult:
        """Execute a create operation."""
        try:
            self.setup_backend(operation.model_class)
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
            if not operation.should_fail:
                return OperationResult(success=False, error=e)
            raise

    def execute_get(self, operation: GetOperation) -> OperationResult:
        """Execute a get operation."""
        try:
            self.setup_backend(operation.model_class)
            instance = operation.model_class.get(**operation.filters)

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
            self.setup_backend(operation.model_class)

            for key, value in operation.changes.items():
                setattr(operation.instance, key, value)

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
            self.setup_backend(operation.model_class)
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
            self.setup_backend(operation.model_class)
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
            self.setup_backend(operation.model_class)

            query = operation.model_class.where(**operation.filters) if operation.filters else operation.model_class.where()

            if operation.order_by:
                for order in operation.order_by:
                    query = query.order_by(order)

            if operation.limit:
                query = query.limit(operation.limit)
            if operation.offset:
                query = query.offset(operation.offset)

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
        """Clear storage for testing - DynamoDB requires table scan and delete."""
        # For DynamoDB, we'd need to scan and delete all items
        # This is typically not used in DynamoDB tests - tests clean up after themselves
        pass

    def get_backend_name(self) -> str:
        """Get the name of the backend being tested."""
        return "dynamodb"

    def setup_backend(self, model_class: Type) -> None:
        """Set up backend for a model class."""
        model_class.model_backend = self.backend

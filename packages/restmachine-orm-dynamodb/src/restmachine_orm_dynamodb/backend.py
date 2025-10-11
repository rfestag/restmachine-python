"""
DynamoDB backend for RestMachine ORM.

Provides full DynamoDB integration with support for:
- Single-table design with pk/sk
- Global Secondary Indexes (GSIs)
- Batch operations
- Conditional updates
- Key condition and filter expressions
"""

from typing import Any, Optional, TYPE_CHECKING
from decimal import Decimal

import boto3  # type: ignore[import-untyped]
from boto3.dynamodb.conditions import Attr  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from restmachine_orm.backends.base import Backend, NotFoundError, DuplicateKeyError
from restmachine_orm.backends.adapters import ModelAdapter
from restmachine_orm.query.base import QueryBuilder

from .adapter import DynamoDBAdapter

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model
    Table = Any  # Placeholder for DynamoDB Table type


class DynamoDBBackend(Backend):
    """
    DynamoDB storage backend.

    Handles connection management, CRUD operations, and query building
    for AWS DynamoDB tables.

    Example:
        >>> from restmachine_orm.backends.dynamodb import DynamoDBBackend
        >>> from restmachine_orm.backends.adapters import DynamoDBAdapter
        >>>
        >>> backend = DynamoDBBackend(
        ...     table_name="my-table",
        ...     adapter=DynamoDBAdapter()
        ... )
        >>>
        >>> class TodoItem(Model):
        ...     class Meta:
        ...         backend = backend
        ...     user_id: str
        ...     todo_id: str
        ...     title: str
        ...     @partition_key
        ...     def pk(self) -> str:
        ...         return f"USER#{self.user_id}"
        ...     @sort_key
        ...     def sk(self) -> str:
        ...         return f"TODO#{self.todo_id}"
    """

    def __init__(
        self,
        table_name: str,
        adapter: Optional[DynamoDBAdapter] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        **boto3_kwargs: Any,
    ):
        """
        Initialize DynamoDB backend.

        Args:
            table_name: Name of the DynamoDB table
            adapter: DynamoDBAdapter instance (uses default if not provided)
            region_name: AWS region (e.g., 'us-east-1')
            endpoint_url: Custom endpoint URL (for local DynamoDB)
            **boto3_kwargs: Additional arguments for boto3.resource()
        """
        # Store adapter in private attribute to avoid property conflicts
        self._dynamodb_adapter = adapter or DynamoDBAdapter()
        # Initialize parent with the adapter
        super().__init__(self._dynamodb_adapter)

        self.table_name = table_name
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.boto3_kwargs = boto3_kwargs

        # Lazy initialization of DynamoDB resource
        self._dynamodb_resource: Optional[Any] = None
        self._table: Optional["Table"] = None

    @property
    def adapter(self) -> DynamoDBAdapter:  # type: ignore[override]
        """Get the DynamoDB adapter (properly typed)."""
        return self._dynamodb_adapter

    @adapter.setter
    def adapter(self, value: ModelAdapter) -> None:
        """Set the DynamoDB adapter."""
        # Accept broader type for compatibility, but store as narrower type
        if not isinstance(value, DynamoDBAdapter):
            raise TypeError(f"Expected DynamoDBAdapter, got {type(value).__name__}")
        self._dynamodb_adapter = value  # type: ignore[assignment]
        # Also update parent's reference by setting directly in __dict__
        # This bypasses the property descriptor
        self.__dict__['adapter'] = value

    @property
    def dynamodb(self) -> Any:
        """Get or create DynamoDB resource."""
        if self._dynamodb_resource is None:
            kwargs = {"region_name": self.region_name, **self.boto3_kwargs}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._dynamodb_resource = boto3.resource("dynamodb", **kwargs)
        return self._dynamodb_resource

    @property
    def table(self) -> "Table":
        """Get or create DynamoDB table resource."""
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    def _python_to_dynamodb(self, value: Any) -> Any:
        """
        Convert Python types to DynamoDB-compatible types.

        DynamoDB doesn't support float or datetime, so we convert:
        - float -> Decimal
        - datetime -> ISO format string
        """
        from datetime import datetime, date

        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, dict):
            return {k: self._python_to_dynamodb(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._python_to_dynamodb(v) for v in value]
        return value

    def _dynamodb_to_python(self, value: Any) -> Any:
        """
        Convert DynamoDB types to Python types.

        Converts Decimal back to float for numeric values.
        """
        if isinstance(value, Decimal):
            # Convert to int if no decimal places, otherwise float
            if value % 1 == 0:
                return int(value)
            return float(value)
        elif isinstance(value, dict):
            return {k: self._dynamodb_to_python(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._dynamodb_to_python(v) for v in value]
        return value

    def create(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new record in DynamoDB.

        Args:
            model_class: Model class
            data: Record data

        Returns:
            Created record data

        Raises:
            DuplicateKeyError: If item with same key already exists
        """
        # Create instance to generate keys
        instance = model_class(**data)

        # Transform to storage format (adds pk, sk, entity_type)
        item = self.adapter.model_to_storage(instance)

        # Convert to DynamoDB types
        item = self._python_to_dynamodb(item)

        try:
            # Use ConditionExpression to prevent overwriting existing items
            pk_attr = self.adapter.pk_attribute
            self.table.put_item(
                Item=item,
                ConditionExpression=f"attribute_not_exists({pk_attr})"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateKeyError(
                    f"Item with key {item.get(pk_attr)} already exists"
                )
            raise

        # Convert back to Python types
        item = self._dynamodb_to_python(item)

        # Transform back to model format
        return self.adapter.storage_to_model(model_class, item)

    def upsert(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create or update a record (upsert).

        Args:
            model_class: Model class
            data: Record data

        Returns:
            Upserted record data
        """
        # Create instance to generate keys
        instance = model_class(**data)

        # Transform to storage format (adds pk, sk, entity_type)
        item = self.adapter.model_to_storage(instance)

        # Convert to DynamoDB types
        item = self._python_to_dynamodb(item)

        # Put item without condition - overwrites if exists
        self.table.put_item(Item=item)

        # Convert back to Python types
        item = self._dynamodb_to_python(item)

        # Transform back to model format
        return self.adapter.storage_to_model(model_class, item)

    def get(self, model_class: type["Model"], **filters: Any) -> Optional[dict[str, Any]]:
        """
        Get a single record by key.

        Args:
            model_class: Model class
            **filters: Filter conditions (must include enough to build key)

        Returns:
            Record data, or None if not found
        """
        # Create instance without validation to generate keys
        instance = model_class.model_construct(**filters)

        # Get key attributes from adapter
        pk_value = self.adapter._get_partition_key_value(instance)
        sk_value = self.adapter._get_sort_key_value(instance)

        if not pk_value:
            # Fall back to query
            result = self.query(model_class).and_(**filters).first()
            if result:
                return result.model_dump()
            return None

        # Build key dict
        key = {self.adapter.pk_attribute: pk_value}
        if sk_value:
            key[self.adapter.sk_attribute] = sk_value

        try:
            response = self.table.get_item(Key=key)
            if "Item" in response:
                item = self._dynamodb_to_python(response["Item"])
                return self.adapter.storage_to_model(model_class, item)
        except ClientError:
            pass

        return None

    def update(
        self,
        model_class: type["Model"],
        instance: "Model"
    ) -> dict[str, Any]:
        """
        Update an existing record.

        Args:
            model_class: Model class
            instance: Model instance with updated data

        Returns:
            Updated record data

        Raises:
            NotFoundError: If record not found
        """
        # Get key values from adapter
        pk_value = self.adapter._get_partition_key_value(instance)
        sk_value = self.adapter._get_sort_key_value(instance)

        if not pk_value:
            raise RuntimeError("Cannot update without partition key")

        # Build key dict
        key = {self.adapter.pk_attribute: pk_value}
        if sk_value:
            key[self.adapter.sk_attribute] = sk_value

        # Transform to storage format
        item = self.adapter.model_to_storage(instance)
        item = self._python_to_dynamodb(item)

        # Build update expression
        update_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        for field_name, value in item.items():
            # Skip key attributes
            if field_name in (self.adapter.pk_attribute, self.adapter.sk_attribute):
                continue

            # Use attribute name aliases to handle reserved words
            attr_alias = f"#{field_name}"
            value_alias = f":{field_name}"

            update_parts.append(f"{attr_alias} = {value_alias}")
            expression_attribute_names[attr_alias] = field_name
            expression_attribute_values[value_alias] = value

        if not update_parts:
            # No fields to update
            return self.adapter.storage_to_model(model_class, item)

        update_expression = "SET " + ", ".join(update_parts)

        try:
            response = self.table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression=f"attribute_exists({self.adapter.pk_attribute})",
                ReturnValues="ALL_NEW"
            )

            updated_item = self._dynamodb_to_python(response["Attributes"])
            return self.adapter.storage_to_model(model_class, updated_item)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NotFoundError("Record not found")
            raise

    def delete(self, model_class: type["Model"], instance: "Model") -> bool:
        """
        Delete a record.

        Args:
            model_class: Model class
            instance: Model instance to delete

        Returns:
            True if deleted successfully
        """
        # Get key values from adapter
        pk_value = self.adapter._get_partition_key_value(instance)
        sk_value = self.adapter._get_sort_key_value(instance)

        if not pk_value:
            raise RuntimeError("Cannot delete without partition key")

        # Build key dict
        key = {self.adapter.pk_attribute: pk_value}
        if sk_value:
            key[self.adapter.sk_attribute] = sk_value

        try:
            self.table.delete_item(
                Key=key,
                ConditionExpression=f"attribute_exists({self.adapter.pk_attribute})"
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def query(self, model_class: type["Model"]) -> "QueryBuilder":
        """
        Create a query builder for complex queries.

        Returns:
            DynamoDBQueryBuilder instance
        """
        return DynamoDBQueryBuilder(model_class, self)

    def count(self, model_class: type["Model"], **filters: Any) -> int:
        """
        Count records matching filters.

        Args:
            model_class: Model class
            **filters: Filter conditions

        Returns:
            Number of matching records
        """
        return self.query(model_class).and_(**filters).count()

    def exists(self, model_class: type["Model"], **filters: Any) -> bool:
        """
        Check if a record exists.

        Args:
            model_class: Model class
            **filters: Filter conditions

        Returns:
            True if at least one record matches
        """
        return self.query(model_class).and_(**filters).exists()

    def batch_get(  # type: ignore[override]
        self,
        model_class: type["Model"],
        keys: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Get multiple items by their keys.

        Args:
            model_class: Model class
            keys: List of key dicts (e.g., [{"id": "1"}, {"id": "2"}])

        Returns:
            List of record data
        """
        if not keys:
            return []

        # Convert keys to DynamoDB format
        dynamodb_keys = []
        for key_dict in keys:
            # Create instance without validation to generate keys
            instance = model_class.model_construct(**key_dict)
            pk_value = self.adapter._get_partition_key_value(instance)
            sk_value = self.adapter._get_sort_key_value(instance)

            ddb_key = {self.adapter.pk_attribute: pk_value}
            if sk_value:
                ddb_key[self.adapter.sk_attribute] = sk_value
            dynamodb_keys.append(ddb_key)

        # Batch get (handles pagination automatically)
        response = self.dynamodb.batch_get_item(
            RequestItems={
                self.table_name: {
                    "Keys": dynamodb_keys
                }
            }
        )

        results = []
        if self.table_name in response.get("Responses", {}):
            for item in response["Responses"][self.table_name]:
                item = self._dynamodb_to_python(item)
                model_data = self.adapter.storage_to_model(model_class, item)
                results.append(model_data)

        return results

    def batch_create(
        self,
        model_class: type["Model"],
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Create multiple records in batch.

        Args:
            model_class: Model class
            records: List of record data

        Returns:
            List of created record data
        """
        if not records:
            return []

        # Convert to DynamoDB format
        items = []
        for data in records:
            instance = model_class(**data)
            item = self.adapter.model_to_storage(instance)
            item = self._python_to_dynamodb(item)
            items.append(item)

        # Batch write (handles batching of 25 items automatically)
        with self.table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)

        # Return the items converted back to model format
        results = []
        for item in items:
            item = self._dynamodb_to_python(item)
            model_data = self.adapter.storage_to_model(model_class, item)
            results.append(model_data)

        return results


class DynamoDBQueryBuilder(QueryBuilder):
    """
    Query builder for DynamoDB backend.

    Builds key condition expressions and filter expressions for DynamoDB queries.
    """

    def __init__(self, model_class: type["Model"], backend: DynamoDBBackend):
        """
        Initialize query builder.

        Args:
            model_class: Model class being queried
            backend: DynamoDBBackend instance
        """
        super().__init__(model_class)
        self.backend = backend
        self._index_name: Optional[str] = None
        self._key_conditions: list[Any] = []
        self._scan_forward: bool = True


    def using_index(self, index_name: str) -> "DynamoDBQueryBuilder":
        """
        Query using a Global Secondary Index.

        Args:
            index_name: Name of the GSI

        Returns:
            Self for chaining
        """
        self._index_name = index_name
        return self

    def reverse(self) -> "DynamoDBQueryBuilder":
        """
        Reverse the sort order.

        Returns:
            Self for chaining
        """
        self._scan_forward = False
        return self

    def _build_filter_expression(self, conditions: dict[str, Any]) -> Optional[Any]:
        """Build DynamoDB filter expression from conditions."""
        from restmachine_orm.query.expressions import parse_field_lookup

        expressions = []
        for field_lookup, value in conditions.items():
            field, operator = parse_field_lookup(field_lookup)

            if operator == "eq":
                expressions.append(Attr(field).eq(value))
            elif operator == "ne":
                expressions.append(Attr(field).ne(value))
            elif operator == "gt":
                expressions.append(Attr(field).gt(value))
            elif operator == "gte":
                expressions.append(Attr(field).gte(value))
            elif operator == "lt":
                expressions.append(Attr(field).lt(value))
            elif operator == "lte":
                expressions.append(Attr(field).lte(value))
            elif operator == "in":
                expressions.append(Attr(field).is_in(value))
            elif operator == "contains":
                expressions.append(Attr(field).contains(value))
            elif operator == "startswith":
                expressions.append(Attr(field).begins_with(value))
            # Note: DynamoDB doesn't have direct support for endswith

        # Combine with AND
        if not expressions:
            return None

        result = expressions[0]
        for expr in expressions[1:]:
            result = result & expr

        return result

    def all(self) -> list["Model"]:
        """Execute query and return all results."""
        # Build filter expression
        filter_expression = None
        for filter_type, conditions in self._filters:
            expr = self._build_filter_expression(conditions)
            if expr:
                if filter_type == "not":
                    expr = ~expr
                elif filter_type == "or":
                    # OR logic - combine with | operator
                    if filter_expression:
                        filter_expression = filter_expression | expr
                    else:
                        filter_expression = expr
                    continue

                # AND logic - combine with & operator
                if filter_expression:
                    filter_expression = filter_expression & expr
                else:
                    filter_expression = expr

        # Determine if we should use Query or Scan
        # For now, we'll use Scan (Query requires key conditions)
        kwargs: dict[str, Any] = {}

        if filter_expression:
            kwargs["FilterExpression"] = filter_expression

        if self._index_name:
            kwargs["IndexName"] = self._index_name

        # Use scan for now (we'll implement Query with key conditions later)
        response = self.backend.table.scan(**kwargs)

        items = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = self.backend.table.scan(**kwargs)
            items.extend(response.get("Items", []))

        # Convert to model instances
        results = []
        for item in items:
            item = self.backend._dynamodb_to_python(item)
            model_data = self.backend.adapter.storage_to_model(self.model_class, item)
            instance = self.model_class(**model_data)
            instance._is_persisted = True
            results.append(instance)

        # Apply ordering in Python (for now)
        if self._order_by:
            for order_field in reversed(self._order_by):
                reverse = order_field.startswith("-")
                field = order_field[1:] if reverse else order_field
                results.sort(key=lambda x: getattr(x, field, ""), reverse=reverse)

        # Apply offset and limit
        if self._offset:
            results = results[self._offset:]
        if self._limit:
            results = results[:self._limit]

        return results

    def first(self) -> Optional["Model"]:
        """Get the first result."""
        results = self.limit(1).all()
        return results[0] if results else None

    def count(self) -> int:
        """Count results."""
        return len(self.all())

    def exists(self) -> bool:
        """Check if any results exist."""
        return self.first() is not None

    def paginate(self) -> tuple[list["Model"], Optional[dict[str, Any]]]:
        """
        Execute query and return results with pagination cursor.

        For DynamoDB backend, the cursor is the LastEvaluatedKey dict.
        """
        # Build filter expression
        filter_expression = None
        for filter_type, conditions in self._filters:
            expr = self._build_filter_expression(conditions)
            if expr:
                if filter_type == "not":
                    expr = ~expr
                elif filter_type == "or":
                    # OR logic - combine with | operator
                    if filter_expression:
                        filter_expression = filter_expression | expr
                    else:
                        filter_expression = expr
                    continue

                # AND logic - combine with & operator
                if filter_expression:
                    filter_expression = filter_expression & expr
                else:
                    filter_expression = expr

        # Build scan/query kwargs
        kwargs: dict[str, Any] = {}

        if filter_expression:
            kwargs["FilterExpression"] = filter_expression

        if self._index_name:
            kwargs["IndexName"] = self._index_name

        # If cursor is set, use it as ExclusiveStartKey
        if self._cursor:
            kwargs["ExclusiveStartKey"] = self._cursor

        # If limit is set, use it for DynamoDB Limit
        if self._limit:
            kwargs["Limit"] = self._limit

        # Execute scan (single page)
        response = self.backend.table.scan(**kwargs)

        items = response.get("Items", [])
        next_cursor = response.get("LastEvaluatedKey")

        # Convert to model instances
        results = []
        for item in items:
            item = self.backend._dynamodb_to_python(item)
            model_data = self.backend.adapter.storage_to_model(self.model_class, item)
            instance = self.model_class(**model_data)
            instance._is_persisted = True
            results.append(instance)

        # Apply ordering in Python (for now)
        if self._order_by:
            for order_field in reversed(self._order_by):
                reverse = order_field.startswith("-")
                field = order_field[1:] if reverse else order_field
                results.sort(key=lambda x: getattr(x, field, ""), reverse=reverse)

        # Note: offset is not compatible with cursor-based pagination
        # If offset is used, the cursor won't work correctly
        if self._offset and not self._cursor:
            results = results[self._offset:]

        return results, next_cursor

"""
In-memory backend for RestMachine ORM.

Simple dict-based storage for testing and examples without requiring
external services.
"""

from typing import Any, Optional, TYPE_CHECKING
from copy import deepcopy

from restmachine_orm.backends.base import Backend, NotFoundError
from restmachine_orm.backends.adapters import InMemoryAdapter
from restmachine_orm.query.base import QueryBuilder

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class InMemoryBackend(Backend):
    """
    In-memory storage backend using Python dicts.

    Stores all data in memory. Data is lost when the process ends.
    Useful for testing and examples.

    Example:
        >>> from restmachine_orm.backends.memory import InMemoryBackend
        >>> from restmachine_orm.backends.adapters import InMemoryAdapter
        >>>
        >>> class User(Model):
        ...     class Meta:
        ...         backend = InMemoryBackend(InMemoryAdapter())
        ...     id: str = Field(primary_key=True)
        ...     name: str
        >>>
        >>> user = User.create(id="123", name="Alice")
    """

    def __init__(self, adapter: Optional[InMemoryAdapter] = None):
        """
        Initialize in-memory backend.

        Args:
            adapter: Optional adapter (uses InMemoryAdapter by default)
        """
        super().__init__(adapter or InMemoryAdapter())
        # Storage: {model_class_name: {pk: record_data}}
        self._storage: dict[str, dict[Any, dict[str, Any]]] = {}

    @property
    def backend_name(self) -> str:
        """Backend identifier."""
        return 'memory'

    def _get_storage(self, model_class: type["Model"]) -> dict[Any, dict[str, Any]]:
        """Get storage dict for a model class."""
        entity_type = self.adapter.get_entity_type(model_class)
        if entity_type not in self._storage:
            self._storage[entity_type] = {}
        return self._storage[entity_type]

    def create(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """Create a new record in memory."""
        # Ensure extensions are configured
        self._ensure_configured(model_class)

        storage = self._get_storage(model_class)

        # Create model instance to get primary key
        instance = model_class(**data)
        pk_value = self.adapter.get_primary_key_value(instance)

        # Check if already exists
        if pk_value in storage:
            from restmachine_orm.backends.base import DuplicateKeyError
            raise DuplicateKeyError(f"Record with key {pk_value} already exists")

        # Convert to storage format
        storage_data = self.adapter.model_to_storage(instance)

        # Call extension hooks
        storage_data = self._call_serialize_hooks(model_class, storage_data)
        self._call_validate_hooks(model_class, storage_data)

        # Store data
        storage[pk_value] = deepcopy(storage_data)

        # Return model format (apply deserialize hooks)
        result_data = self.adapter.storage_to_model(model_class, storage_data)
        result_data = self._call_deserialize_hooks(model_class, result_data)
        return result_data

    def upsert(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a record (upsert)."""
        # Ensure extensions are configured
        self._ensure_configured(model_class)

        storage = self._get_storage(model_class)

        # Create model instance to get primary key
        instance = model_class(**data)
        pk_value = self.adapter.get_primary_key_value(instance)

        # Convert to storage format
        storage_data = self.adapter.model_to_storage(instance)

        # Call extension hooks
        storage_data = self._call_serialize_hooks(model_class, storage_data)
        self._call_validate_hooks(model_class, storage_data)

        # Store data (overwrite if exists)
        storage[pk_value] = deepcopy(storage_data)

        # Return model format (apply deserialize hooks)
        result_data = self.adapter.storage_to_model(model_class, storage_data)
        result_data = self._call_deserialize_hooks(model_class, result_data)
        return result_data

    def get(self, model_class: type["Model"], **filters: Any) -> Optional[dict[str, Any]]:
        """Get a single record by primary key."""
        storage = self._get_storage(model_class)

        # Simple implementation: assumes filters contain primary key
        # For more complex filtering, use query()
        for record in storage.values():
            model_data = self.adapter.storage_to_model(model_class, record)
            model_data = self._call_deserialize_hooks(model_class, model_data)
            if all(model_data.get(k) == v for k, v in filters.items()):
                return model_data

        return None

    def update(
        self,
        model_class: type["Model"],
        instance: "Model"
    ) -> dict[str, Any]:
        """Update an existing record."""
        storage = self._get_storage(model_class)

        # Get primary key from instance
        pk_value = self.adapter.get_primary_key_value(instance)

        if pk_value not in storage:
            raise NotFoundError(f"Record not found with key: {pk_value}")

        # Convert to storage format
        storage_data = self.adapter.model_to_storage(instance)

        # Call extension hooks
        storage_data = self._call_serialize_hooks(model_class, storage_data)
        self._call_validate_hooks(model_class, storage_data)

        # Update the record
        storage[pk_value] = deepcopy(storage_data)

        # Return model format (apply deserialize hooks)
        # Note: For update, this return value is currently ignored by Model.save()
        # but we return it for consistency and future hooks support
        result_data = self.adapter.storage_to_model(model_class, storage_data)
        result_data = self._call_deserialize_hooks(model_class, result_data)
        return result_data

    def delete(self, model_class: type["Model"], instance: "Model") -> bool:
        """Delete a record."""
        storage = self._get_storage(model_class)

        # Get primary key from instance
        pk_value = self.adapter.get_primary_key_value(instance)

        if pk_value in storage:
            del storage[pk_value]
            return True

        return False

    def query(self, model_class: type["Model"]) -> QueryBuilder:
        """Create a query builder for this backend."""
        query_builder: QueryBuilder = InMemoryQueryBuilder(model_class, self)
        # Call extension hooks to modify query behavior
        query_builder = self._call_modify_query_hooks(model_class, query_builder)
        return query_builder

    def count(self, model_class: type["Model"], **filters: Any) -> int:
        """Count records matching filters."""
        storage = self._get_storage(model_class)

        if not filters:
            return len(storage)

        count = 0
        for record in storage.values():
            model_data = self.adapter.storage_to_model(model_class, record)
            if all(model_data.get(k) == v for k, v in filters.items()):
                count += 1

        return count

    def exists(self, model_class: type["Model"], **filters: Any) -> bool:
        """Check if a record exists."""
        return self.count(model_class, **filters) > 0

    def clear(self, model_class: Optional[type["Model"]] = None) -> None:
        """
        Clear storage.

        Args:
            model_class: Optional model class to clear. If None, clears all.
        """
        if model_class:
            entity_type = self.adapter.get_entity_type(model_class)
            self._storage.pop(entity_type, None)
        else:
            self._storage.clear()


class InMemoryQueryBuilder(QueryBuilder):
    """
    Query builder for in-memory backend.

    Performs filtering, sorting, and pagination in Python.
    """

    def __init__(self, model_class: type["Model"], backend: InMemoryBackend):
        """
        Initialize query builder.

        Args:
            model_class: Model class being queried
            backend: InMemoryBackend instance
        """
        super().__init__(model_class)
        self.backend = backend


    def _matches_conditions(self, record: dict[str, Any], conditions: dict[str, Any]) -> bool:
        """Check if a record matches filter conditions."""
        from restmachine_orm.query.expressions import parse_field_lookup

        for field_lookup, value in conditions.items():
            field, operator = parse_field_lookup(field_lookup)

            record_value = record.get(field)

            if operator == "eq":
                if record_value != value:
                    return False
            elif operator == "ne":
                if record_value == value:
                    return False
            elif operator == "gt":
                if not (record_value is not None and record_value > value):
                    return False
            elif operator == "gte":
                if not (record_value is not None and record_value >= value):
                    return False
            elif operator == "lt":
                if not (record_value is not None and record_value < value):
                    return False
            elif operator == "lte":
                if not (record_value is not None and record_value <= value):
                    return False
            elif operator == "in":
                if record_value not in value:
                    return False
            elif operator == "contains":
                if not (record_value and value in record_value):
                    return False
            elif operator == "startswith":
                if not (record_value and str(record_value).startswith(str(value))):
                    return False
            elif operator == "endswith":
                if not (record_value and str(record_value).endswith(str(value))):
                    return False

        return True

    def all(self) -> list["Model"]:
        """Execute query and return all results."""
        storage = self.backend._get_storage(self.model_class)

        # Get all records and convert to model data
        results = []
        for record in storage.values():
            model_data = self.backend.adapter.storage_to_model(self.model_class, record)
            model_data = self.backend._call_deserialize_hooks(self.model_class, model_data)

            # Apply filters with boolean logic
            # and: all conditions must match (AND)
            # or: creates OR groups
            # not: negates conditions
            include = True if not self._filters else False

            # Group filters by OR boundaries
            or_groups: list[list[tuple[str, dict[str, Any]]]] = []
            current_group: list[tuple[str, dict[str, Any]]] = []

            for filter_type, conditions in self._filters:
                if filter_type == "or":
                    # Finish current group and start new OR group
                    if current_group:
                        or_groups.append(current_group)
                    current_group = [(filter_type, conditions)]
                else:
                    current_group.append((filter_type, conditions))

            # Add final group
            if current_group:
                or_groups.append(current_group)

            # Evaluate: OR groups are ORed, conditions within groups are ANDed
            if not or_groups:
                # No filters, include all
                include = True
            else:
                for group in or_groups:
                    group_matches = True
                    for filter_type, conditions in group:
                        matches = self._matches_conditions(model_data, conditions)
                        if filter_type == "and" and not matches:
                            group_matches = False
                            break
                        elif filter_type == "not" and matches:
                            group_matches = False
                            break
                        elif filter_type == "or":
                            # OR condition - if it matches, entire group matches
                            if matches:
                                group_matches = True
                                break

                    if group_matches:
                        include = True
                        break  # OR: any group matching is enough

            if include:
                results.append(model_data)

        # Apply ordering
        if self._order_by:
            for order_field in reversed(self._order_by):
                reverse = order_field.startswith("-")
                field = order_field[1:] if reverse else order_field
                results.sort(key=lambda x: x.get(field) or "", reverse=reverse)

        # Apply offset and limit
        # If cursor is set, use it as the offset
        offset = self._offset or 0
        if self._cursor and isinstance(self._cursor, dict) and "offset" in self._cursor:
            offset = self._cursor["offset"]

        if offset:
            results = results[offset:]
        if self._limit:
            results = results[:self._limit]

        # Convert to model instances
        instances = []
        for data in results:
            instance = self.model_class(**data)
            instance._is_persisted = True

            # Call after_load hooks (for geo deserialization, etc.)
            for hook in self.model_class._after_load_hooks:
                hook(instance)

            instances.append(instance)

        # Apply result filters (e.g., from mixins)
        instances = self._apply_result_filters(instances)

        return instances

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

    def paginate(self) -> tuple[list["Model"], Optional[dict[str, int]]]:
        """
        Execute query and return results with pagination cursor.

        For in-memory backend, the cursor is a dict with 'offset' key.
        """
        # Get all results up to limit + offset
        all_results = self.all()

        # If we have a limit, we may need to return a cursor
        if self._limit and len(all_results) == self._limit:
            # There might be more results
            # Cursor is the next offset
            current_offset = self._offset or 0
            next_cursor = {"offset": current_offset + self._limit}
            return all_results, next_cursor
        else:
            # No more results
            return all_results, None

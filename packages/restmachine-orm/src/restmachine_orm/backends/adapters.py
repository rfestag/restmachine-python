"""
Adapter interface for mapping models to storage backends.

Each backend has its own adapter that knows how to:
- Transform model data to backend-specific format
- Extract composite keys for DynamoDB
- Map fields to indexes
- Handle backend-specific metadata
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class ModelAdapter(ABC):
    """
    Abstract adapter for mapping models to storage backends.

    Each backend implements its own adapter that understands how to
    translate between the generic Model representation and the
    backend-specific storage format.
    """

    @abstractmethod
    def model_to_storage(self, instance: "Model") -> dict[str, Any]:
        """
        Transform a model instance to backend storage format.

        Args:
            instance: Model instance to transform

        Returns:
            Dictionary in backend-specific format

        Example (DynamoDB):
            >>> adapter.model_to_storage(user)
            {
                'pk': 'USER#123',
                'sk': 'METADATA',
                'entity_type': 'User',
                'id': '123',
                'email': 'alice@example.com',
                'name': 'Alice'
            }
        """
        pass

    @abstractmethod
    def storage_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Transform backend storage format to model data.

        Args:
            model_class: The model class to instantiate
            data: Data from backend storage

        Returns:
            Dictionary suitable for model instantiation

        Example (DynamoDB):
            >>> adapter.storage_to_model(User, {
            ...     'pk': 'USER#123',
            ...     'sk': 'METADATA',
            ...     'entity_type': 'User',
            ...     'id': '123',
            ...     'email': 'alice@example.com'
            ... })
            {'id': '123', 'email': 'alice@example.com'}
        """
        pass

    @abstractmethod
    def get_primary_key_value(self, instance: "Model") -> Any:
        """
        Get the primary key value for a model instance.

        For simple backends (like SQL), this is just the primary key field.
        For DynamoDB, this might be a composite key.

        Args:
            instance: Model instance

        Returns:
            Primary key value (simple or composite)

        Example:
            >>> adapter.get_primary_key_value(user)
            '123'  # Simple key
            >>> adapter.get_primary_key_value(todo)
            {'pk': 'USER#alice', 'sk': 'TODO#2025-01-15'}  # Composite
        """
        pass

    def get_index_keys(self, instance: "Model") -> dict[str, Any]:
        """
        Get secondary index keys for a model instance.

        Optional method for backends that support secondary indexes.

        Args:
            instance: Model instance

        Returns:
            Dictionary of index names to key values

        Example (DynamoDB GSIs):
            >>> adapter.get_index_keys(user)
            {
                'EmailIndex': {'gsi_pk': 'alice@example.com'},
                'TenantIndex': {'gsi_pk': 'TENANT#org-1', 'gsi_sk': '2025-01-15'}
            }
        """
        return {}

    def get_entity_type(self, model_class: type["Model"]) -> str:
        """
        Get the entity type identifier for a model.

        Used for filtering in single-table designs.

        Args:
            model_class: Model class

        Returns:
            Entity type identifier (typically the class name)
        """
        return model_class.__name__


class OpenSearchAdapter(ModelAdapter):
    """
    Adapter for OpenSearch.

    Maps models to OpenSearch documents with:
    - _id - from primary key field
    - All model fields as document fields
    - Special handling for searchable fields
    """

    def __init__(
        self,
        *,
        id_field: str = "_id",
        include_type: bool = True,
        type_field: str = "_type",
    ):
        """
        Initialize OpenSearch adapter.

        Args:
            id_field: OpenSearch document ID field
            include_type: Whether to include type field in documents
            type_field: Field name for document type
        """
        self.id_field = id_field
        self.include_type = include_type
        self.type_field = type_field

    def model_to_storage(self, instance: "Model") -> dict[str, Any]:
        """Transform model instance to OpenSearch document."""
        data = instance.model_dump()

        # Add type if configured
        if self.include_type:
            data[self.type_field] = self.get_entity_type(instance.__class__)

        return data

    def storage_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """Transform OpenSearch document to model data."""
        model_data = dict(data)

        # Remove OpenSearch-specific fields
        model_data.pop(self.type_field, None)
        model_data.pop("_score", None)
        model_data.pop("_index", None)
        model_data.pop("_source", None)

        return model_data

    def get_primary_key_value(self, instance: "Model") -> str:
        """Get document ID for OpenSearch."""
        from restmachine_orm.models.fields import get_field_orm_metadata

        # Find the primary key field
        pk_field = None
        for field_name, field_info in instance.__class__.model_fields.items():
            metadata = get_field_orm_metadata(field_info)
            if metadata.get("primary_key"):
                pk_field = field_name
                break

        if not pk_field:
            raise ValueError(
                f"No primary key field defined for {instance.__class__.__name__}"
            )
        return str(getattr(instance, pk_field))


class InMemoryAdapter(ModelAdapter):
    """
    Adapter for in-memory storage (testing and examples).

    Simple adapter that uses the primary key field as-is.
    No special transformation needed for in-memory dicts.
    """

    def model_to_storage(self, instance: "Model") -> dict[str, Any]:
        """Return model data as-is for in-memory storage."""
        return instance.model_dump()

    def storage_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return data as-is for model instantiation."""
        return dict(data)

    def get_primary_key_value(self, instance: "Model") -> Any:
        """Get primary key value."""
        from restmachine_orm.models.fields import get_field_orm_metadata

        # Find the primary key field
        pk_field = None
        for field_name, field_info in instance.__class__.model_fields.items():
            metadata = get_field_orm_metadata(field_info)
            if metadata.get("primary_key"):
                pk_field = field_name
                break

        if not pk_field:
            raise ValueError(
                f"No primary key field defined for {instance.__class__.__name__}"
            )
        return getattr(instance, pk_field)


class CompositeAdapter(ModelAdapter):
    """
    Adapter for composite backends.

    Delegates to sub-adapters based on operation type:
    - Search operations use search_adapter (e.g., OpenSearch)
    - Storage operations use storage_adapter (e.g., DynamoDB)
    """

    def __init__(
        self,
        search_adapter: ModelAdapter,
        storage_adapter: ModelAdapter,
    ):
        """
        Initialize composite adapter.

        Args:
            search_adapter: Adapter for search backend (e.g., OpenSearch)
            storage_adapter: Adapter for storage backend (e.g., DynamoDB)
        """
        self.search_adapter = search_adapter
        self.storage_adapter = storage_adapter

    def model_to_storage(self, instance: "Model") -> dict[str, Any]:
        """Use storage adapter for persistence."""
        return self.storage_adapter.model_to_storage(instance)

    def storage_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """Use storage adapter for retrieval."""
        return self.storage_adapter.storage_to_model(model_class, data)

    def get_primary_key_value(self, instance: "Model") -> Any:
        """Use storage adapter for key generation."""
        return self.storage_adapter.get_primary_key_value(instance)

    def model_to_search(self, instance: "Model") -> dict[str, Any]:
        """Transform model for search indexing."""
        return self.search_adapter.model_to_storage(instance)

    def search_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """Transform search result to model data."""
        return self.search_adapter.storage_to_model(model_class, data)

"""
DynamoDB adapter for RestMachine ORM.

Handles transformation between model instances and DynamoDB items.
"""

from typing import Any, Optional, TYPE_CHECKING

from restmachine_orm.backends.adapters import ModelAdapter

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class DynamoDBAdapter(ModelAdapter):
    """
    Adapter for DynamoDB single-table design.

    Maps models to DynamoDB items with:
    - pk (partition key) - from @partition_key method or primary key field
    - sk (sort key) - from @sort_key method or default value
    - entity_type - for filtering different entities in same table
    - All model fields as attributes
    - GSI keys from @gsi_partition_key and @gsi_sort_key methods
    """

    def __init__(
        self,
        *,
        pk_attribute: str = "pk",
        sk_attribute: str = "sk",
        entity_type_attribute: str = "entity_type",
        include_type_in_sk: bool = False,
    ):
        """
        Initialize DynamoDB adapter.

        Args:
            pk_attribute: DynamoDB attribute name for partition key
            sk_attribute: DynamoDB attribute name for sort key
            entity_type_attribute: Attribute name for entity type
            include_type_in_sk: Whether to include entity type in sort key
        """
        self.pk_attribute = pk_attribute
        self.sk_attribute = sk_attribute
        self.entity_type_attribute = entity_type_attribute
        self.include_type_in_sk = include_type_in_sk

    def _get_partition_key_method(self, model_class: type["Model"]) -> Optional[str]:
        """
        Get the partition key method name from model class.

        Args:
            model_class: Model class to inspect

        Returns:
            Name of the method decorated with @partition_key, or None
        """
        from restmachine_orm.models.decorators import is_partition_key_method

        for name in dir(model_class):
            if name.startswith("_"):
                continue
            attr = getattr(model_class, name)
            if callable(attr) and is_partition_key_method(attr):
                return name
        return None

    def _get_sort_key_method(self, model_class: type["Model"]) -> Optional[str]:
        """
        Get the sort key method name from model class.

        Args:
            model_class: Model class to inspect

        Returns:
            Name of the method decorated with @sort_key, or None
        """
        from restmachine_orm.models.decorators import is_sort_key_method

        for name in dir(model_class):
            if name.startswith("_"):
                continue
            attr = getattr(model_class, name)
            if callable(attr) and is_sort_key_method(attr):
                return name
        return None

    def _get_partition_key_value(self, instance: "Model") -> Optional[str]:
        """
        Get the partition key value for an instance.

        Args:
            instance: Model instance

        Returns:
            Partition key value, or None
        """
        method_name = self._get_partition_key_method(instance.__class__)
        if method_name:
            method = getattr(instance, method_name)
            result: str = method()
            return result
        return None

    def _get_sort_key_value(self, instance: "Model") -> Optional[str]:
        """
        Get the sort key value for an instance.

        Args:
            instance: Model instance

        Returns:
            Sort key value, or None
        """
        method_name = self._get_sort_key_method(instance.__class__)
        if method_name:
            method = getattr(instance, method_name)
            result: str = method()
            return result
        return None

    def model_to_storage(self, instance: "Model") -> dict[str, Any]:
        """Transform model instance to DynamoDB item format."""
        # Get model data
        data = instance.model_dump()

        # Generate partition key
        pk_value = self._get_partition_key_value(instance)
        if pk_value:
            data[self.pk_attribute] = pk_value
        else:
            # Fallback to primary key field
            from restmachine_orm.models.fields import get_field_orm_metadata

            pk_field = None
            for field_name, field_info in instance.__class__.model_fields.items():
                metadata = get_field_orm_metadata(field_info)
                if metadata.get("primary_key"):
                    pk_field = field_name
                    break

            if pk_field:
                data[self.pk_attribute] = f"{self.get_entity_type(instance.__class__)}#{data[pk_field]}"
            else:
                raise ValueError(
                    f"No partition key method or primary key field defined for {instance.__class__.__name__}"
                )

        # Generate sort key
        sk_value = self._get_sort_key_value(instance)
        if sk_value:
            data[self.sk_attribute] = sk_value
        else:
            # Default sort key
            if self.include_type_in_sk:
                data[self.sk_attribute] = f"{self.get_entity_type(instance.__class__)}#METADATA"
            else:
                data[self.sk_attribute] = "METADATA"

        # Add entity type for filtering
        data[self.entity_type_attribute] = self.get_entity_type(instance.__class__)

        # Add GSI keys
        gsi_keys = self._get_gsi_keys(instance)
        data.update(gsi_keys)

        return data

    def storage_to_model(
        self,
        model_class: type["Model"],
        data: dict[str, Any]
    ) -> dict[str, Any]:
        """Transform DynamoDB item to model data."""
        # Create a copy to avoid mutating original
        model_data = dict(data)

        # Remove DynamoDB-specific attributes
        model_data.pop(self.pk_attribute, None)
        model_data.pop(self.sk_attribute, None)
        model_data.pop(self.entity_type_attribute, None)

        # Remove GSI attributes
        for key in list(model_data.keys()):
            if key.startswith("gsi_"):
                model_data.pop(key)

        return model_data

    def get_primary_key_value(self, instance: "Model") -> dict[str, str]:
        """Get composite key for DynamoDB."""
        result = {}

        # Get partition key
        pk_value = self._get_partition_key_value(instance)
        if pk_value:
            result[self.pk_attribute] = pk_value
        else:
            # Fallback to primary key field
            from restmachine_orm.models.fields import get_field_orm_metadata

            pk_field = None
            for field_name, field_info in instance.__class__.model_fields.items():
                metadata = get_field_orm_metadata(field_info)
                if metadata.get("primary_key"):
                    pk_field = field_name
                    break

            if pk_field:
                result[self.pk_attribute] = f"{self.get_entity_type(instance.__class__)}#{getattr(instance, pk_field)}"

        # Get sort key
        sk_value = self._get_sort_key_value(instance)
        if sk_value:
            result[self.sk_attribute] = sk_value
        else:
            if self.include_type_in_sk:
                result[self.sk_attribute] = f"{self.get_entity_type(instance.__class__)}#METADATA"
            else:
                result[self.sk_attribute] = "METADATA"

        return result

    def _get_gsi_keys(self, instance: "Model") -> dict[str, Any]:
        """Extract GSI keys from model instance."""
        from restmachine_orm.models.decorators import (
            is_gsi_partition_key_method,
            is_gsi_sort_key_method,
        )

        gsi_keys = {}

        # Scan for GSI key methods on the class (not instance)
        for name in dir(instance.__class__):
            if name.startswith("_"):
                continue

            # Get attribute from class to avoid deprecation warning
            class_attr = getattr(instance.__class__, name, None)
            if not callable(class_attr):
                continue

            # Bind the method to the instance
            attr = getattr(instance, name)

            # Check for GSI partition key
            if is_gsi_partition_key_method(class_attr):
                gsi_name = getattr(class_attr, "_gsi_name")
                value = attr()
                gsi_keys[f"gsi_pk_{gsi_name}"] = value

            # Check for GSI sort key
            elif is_gsi_sort_key_method(class_attr):
                gsi_name = getattr(class_attr, "_gsi_name")
                value = attr()
                gsi_keys[f"gsi_sk_{gsi_name}"] = value

        return gsi_keys

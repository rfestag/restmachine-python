"""
Version registry for managing versioned models.

Uses Pydantic's discriminated unions to automatically deserialize to the correct
version class based on the _model_version field.
"""

from typing import TYPE_CHECKING, Union, cast
import logging

if TYPE_CHECKING:
    from restmachine_orm.models.versioned import VersionedModel

logger = logging.getLogger(__name__)


class VersionRegistry:
    """
    Registry for versioned models using Pydantic discriminated unions.

    Tracks all versions of each model family and builds discriminated union types
    for automatic deserialization.
    """

    def __init__(self):
        # model_name -> {
        #     "classes": [UserV1, UserV2, UserV3],
        #     "latest": UserV3,
        #     "union": Union[UserV1, UserV2, UserV3]
        # }
        self._registry: dict[str, dict] = {}

    def register(
        self,
        model_name: str,
        model_class: type["VersionedModel"],
        is_latest: bool = False
    ) -> None:
        """
        Register a versioned model class.

        Args:
            model_name: Logical model name (e.g., "User")
            model_class: The model class to register
            is_latest: Whether this is the latest version

        Raises:
            ValueError: If latest is already set for this model
        """
        if model_name not in self._registry:
            self._registry[model_name] = {
                "classes": [],
                "latest": None,
                "union": None
            }

        entry = self._registry[model_name]

        # Check if already registered
        if model_class in entry["classes"]:
            logger.debug(f"{model_class.__name__} already registered for {model_name}")
            return

        # Add to classes list
        entry["classes"].append(model_class)

        # Set as latest if specified
        if is_latest:
            if entry["latest"] is not None and entry["latest"] != model_class:
                raise ValueError(
                    f"Latest version already set for {model_name}: {entry['latest'].__name__}. "
                    f"Cannot also mark {model_class.__name__} as latest."
                )
            entry["latest"] = model_class

        # Rebuild union with all registered classes
        self._rebuild_union(model_name)

        logger.debug(
            f"Registered {model_class.__name__} for {model_name} "
            f"(latest={is_latest})"
        )

    def _rebuild_union(self, model_name: str) -> None:
        """
        Rebuild the Pydantic union type for a model family.

        Creates a discriminated union using model_version as the discriminator.
        """
        entry = self._registry[model_name]
        classes = entry["classes"]

        if not classes:
            entry["union"] = None
            return

        if len(classes) == 1:
            # Single class - union of one
            entry["union"] = classes[0]
        else:
            # Multiple classes - create Union
            # Pydantic will use _model_version field as discriminator
            entry["union"] = Union[tuple(classes)]  # type: ignore

    def get_union_type(self, model_name: str):
        """
        Get the Pydantic union type for a model family.

        This type can be used with model_validate() to automatically
        deserialize to the correct version class.

        Args:
            model_name: The logical model name

        Returns:
            Union type of all registered versions

        Raises:
            KeyError: If no versions registered for this model

        Example:
            >>> union_type = registry.get_union_type("User")
            >>> # union_type is Union[UserV1, UserV2, UserV3]
            >>> instance = union_type.model_validate(data)
            >>> # Pydantic picks the right class based on model_version
        """
        if model_name not in self._registry:
            raise KeyError(
                f"No versions registered for model: {model_name}. "
                f"Available models: {sorted(self._registry.keys())}"
            )

        union = self._registry[model_name]["union"]
        if union is None:
            raise ValueError(f"No classes registered for {model_name}")

        return union

    def get_latest_class(self, model_name: str) -> type["VersionedModel"]:
        """
        Get the latest version class for a model.

        Args:
            model_name: The logical model name

        Returns:
            The latest version class

        Raises:
            KeyError: If no versions registered
            ValueError: If no version marked as latest

        Example:
            >>> User = registry.get_latest_class("User")
            >>> # User is UserV3 (marked with latest=True)
        """
        if model_name not in self._registry:
            raise KeyError(
                f"No versions registered for model: {model_name}. "
                f"Available models: {sorted(self._registry.keys())}"
            )

        latest = self._registry[model_name]["latest"]
        if latest is None:
            classes = self._registry[model_name]["classes"]
            class_names = [cls.__name__ for cls in classes]
            raise ValueError(
                f"No version marked as latest for {model_name}. "
                f"Registered versions: {class_names}. "
                f"Mark one with @versioned_model('{model_name}', latest=True)"
            )

        return cast(type["VersionedModel"], latest)

    def get_all_classes(self, model_name: str) -> list[type["VersionedModel"]]:
        """
        Get all registered version classes for a model.

        Args:
            model_name: The logical model name

        Returns:
            List of all version classes

        Raises:
            KeyError: If no versions registered
        """
        if model_name not in self._registry:
            raise KeyError(f"No versions registered for model: {model_name}")

        return cast(list[type["VersionedModel"]], self._registry[model_name]["classes"].copy())

    def is_registered(self, model_name: str) -> bool:
        """Check if any versions are registered for a model."""
        return model_name in self._registry

    def list_models(self) -> list[str]:
        """List all registered model names."""
        return sorted(self._registry.keys())


# Global registry instance
_registry = VersionRegistry()


def versioned_model(model_name: str, latest: bool = False):
    """
    Decorator to register a versioned model.

    Args:
        model_name: Logical model name (e.g., "User") - used for table name
        latest: Whether this is the latest/current version

    Returns:
        Decorator function

    Example:
        >>> @versioned_model("User")
        >>> class UserV1(VersionedModel):
        ...     id: str
        ...     name: str
        ...
        ...     def upgrade(self):
        ...         return UserV2(id=self.id, name=self.name, age=0)
        ...
        >>> @versioned_model("User", latest=True)
        >>> class UserV2(VersionedModel):
        ...     id: str
        ...     name: str
        ...     age: int = 0
    """
    def decorator(cls):
        # Set metadata on class
        cls._model_name = model_name
        cls._is_latest = latest

        # Register in global registry
        _registry.register(model_name, cls, is_latest=latest)

        return cls

    return decorator


def get_latest_model(model_name: str) -> type["VersionedModel"]:
    """
    Get the latest version class for a model.

    Args:
        model_name: The logical model name

    Returns:
        The latest version class

    Example:
        >>> User = get_latest_model("User")
        >>> user = User.create(id="1", name="Alice", age=30)
    """
    return _registry.get_latest_class(model_name)


def get_union_type(model_name: str):
    """
    Get the Pydantic union type for deserializing any version.

    Args:
        model_name: The logical model name

    Returns:
        Union type of all versions

    Example:
        >>> union_type = get_union_type("User")
        >>> instance = union_type.model_validate(data)
        >>> # Pydantic automatically picks correct version class
    """
    return _registry.get_union_type(model_name)


def get_all_versions(model_name: str) -> list[type["VersionedModel"]]:
    """
    Get all registered version classes for a model.

    Args:
        model_name: The logical model name

    Returns:
        List of all version classes
    """
    return _registry.get_all_classes(model_name)


def is_registered(model_name: str) -> bool:
    """Check if any versions are registered for a model."""
    return _registry.is_registered(model_name)


def list_models() -> list[str]:
    """List all registered model names."""
    return _registry.list_models()


def upgrade_to_latest(instance: "VersionedModel") -> "VersionedModel":
    """
    Recursively upgrade an instance to the latest version.

    This is a helper function used by backends to chain upgrades.
    Each call to upgrade() returns the next version, and this function
    recursively calls upgrade() until reaching the latest.

    Args:
        instance: An instance of any version

    Returns:
        Instance of the latest version

    Example:
        >>> user_v1 = UserV1(id="1", name="Alice")
        >>> user_v3 = upgrade_to_latest(user_v1)
        >>> # Automatically chains: V1 → V2 → V3
    """
    next_version = instance.upgrade()

    if next_version is None:
        # No more upgrades - this is the latest
        return instance

    # Recursively upgrade the next version
    return upgrade_to_latest(next_version)


__all__ = [
    "VersionRegistry",
    "versioned_model",
    "get_latest_model",
    "get_union_type",
    "get_all_versions",
    "is_registered",
    "list_models",
    "upgrade_to_latest",
]

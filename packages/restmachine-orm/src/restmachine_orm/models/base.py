"""
Base model class for RestMachine ORM.

Provides ActiveRecord-style interface using Pydantic for validation.
"""

from typing import Any, Optional, ClassVar, Callable, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from restmachine_orm.backends.base import Backend
    from restmachine_orm.query.base import QueryBuilder

# Import descriptor classes for ignored_types
from restmachine_orm.models.decorators import BeforeSaveCallback, AfterSaveCallback


class ModelMeta:
    """
    Metadata container for Model configuration.

    Defined as an inner class in Model subclasses to configure
    backend and other model-level settings.
    """
    backend: Optional["Backend"] = None
    table_name: Optional[str] = None
    index_name: Optional[str] = None


class Model(BaseModel):
    """
    Base model class for RestMachine ORM.

    Provides ActiveRecord-style CRUD operations and integrates with
    Pydantic for validation. Models are compatible with RestMachine
    for automatic API integration.

    Example:
        >>> class User(Model):
        ...     class Meta:
        ...         backend = DynamoDBBackend(table_name="users")
        ...
        ...     id: str = Field(primary_key=True)
        ...     email: str = Field(unique=True)
        ...     name: str
        ...
        >>> user = User.create(id="123", email="alice@example.com", name="Alice")
        >>> user.name = "Alice Smith"
        >>> user.save()
    """

    # Pydantic configuration
    model_config = ConfigDict(
        validate_assignment=True,  # Validate on attribute assignment
        arbitrary_types_allowed=True,  # Allow custom types
        from_attributes=True,  # Allow ORM mode
        ignored_types=(BeforeSaveCallback, AfterSaveCallback),  # Ignore callback descriptors
    )

    # Class-level metadata
    Meta: ClassVar[type[ModelMeta]] = ModelMeta

    # Track if this is a new record or loaded from database
    _is_persisted: bool = False

    # Callback lists (populated by descriptors)
    _before_save_callbacks: ClassVar[list[Callable[["Model"], None]]] = []
    _after_save_callbacks: ClassVar[list[Callable[["Model"], None]]] = []

    @classmethod
    def _get_backend(cls) -> "Backend":
        """
        Get the backend for this model.

        Returns:
            Backend instance

        Raises:
            RuntimeError: If no backend is configured
        """
        if not hasattr(cls.Meta, "backend") or cls.Meta.backend is None:
            raise RuntimeError(
                f"No backend configured for {cls.__name__}. "
                f"Set {cls.__name__}.Meta.backend to a Backend instance."
            )
        return cls.Meta.backend



    @classmethod
    def create(cls, **kwargs: Any) -> "Model":
        """
        Create and save a new record in one operation.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created and saved model instance

        Raises:
            ValidationError: If field validation fails
            DuplicateKeyError: If unique constraint is violated

        Example:
            >>> user = User.create(id="123", email="alice@example.com", name="Alice")
        """
        instance = cls(**kwargs)
        instance.save()
        return instance

    @classmethod
    def upsert(cls, **kwargs: Any) -> "Model":
        """
        Create or update a record (upsert).

        If a record with the same key exists, it will be overwritten.
        Unlike create(), this does not raise DuplicateKeyError.

        Callbacks:
            - Calls all @before_save methods before persisting
            - Calls all @after_save methods after persisting

        Args:
            **kwargs: Field values for the record

        Returns:
            Upserted and saved model instance

        Raises:
            ValidationError: If field validation fails

        Example:
            >>> user = User.upsert(id="123", email="alice@example.com", name="Alice")
            >>> # If user with id=123 exists, it will be overwritten
        """
        instance = cls(**kwargs)

        # Call all registered before_save callbacks
        for callback in cls._before_save_callbacks:
            callback(instance)

        # Validate the model before saving
        instance.model_validate(instance.model_dump())

        backend = cls._get_backend()
        data = instance.model_dump()

        # Backend returns the data that was stored
        backend.upsert(cls, data)

        # Mark instance as persisted
        instance._is_persisted = True

        # Call all registered after_save callbacks
        for callback in cls._after_save_callbacks:
            callback(instance)

        return instance

    def save(self) -> "Model":
        """
        Validate and save this record to the database.

        Creates a new record if not persisted, otherwise updates existing.

        Callbacks:
            - Calls all @before_save methods before persisting
            - Calls all @after_save methods after persisting

        Returns:
            Self for method chaining

        Raises:
            ValidationError: If field validation fails

        Example:
            >>> user = User(id="123", name="Alice")
            >>> user.save()  # Validates and saves

            >>> user.name = "Alice Smith"
            >>> user.save()  # Validates and updates
        """
        # Call all registered before_save callbacks
        for callback in self.__class__._before_save_callbacks:
            callback(self)

        # Validate the model before saving
        # Pydantic automatically validates on construction and assignment
        # but we trigger it explicitly here to ensure consistency
        self.model_validate(self.model_dump())

        backend = self._get_backend()
        data = self.model_dump()

        if not self._is_persisted:
            # Create new record
            backend.create(self.__class__, data)
            self._is_persisted = True
        else:
            # Update existing record
            # Instance already has the correct state
            # Backend just persists what we have
            backend.update(self.__class__, self)

        # Call all registered after_save callbacks
        for callback in self.__class__._after_save_callbacks:
            callback(self)

        return self

    def delete(self) -> bool:
        """
        Delete this record from the database.

        Returns:
            True if deleted successfully

        Example:
            >>> user.delete()
        """
        backend = self._get_backend()
        # Backend handles key extraction from the model instance
        return backend.delete(self.__class__, self)

    @classmethod
    def get(cls, **filters: Any) -> Optional["Model"]:
        """
        Get a single record by primary key or filters.

        Args:
            **filters: Filter conditions (typically primary key)

        Returns:
            Model instance, or None if not found

        Example:
            >>> user = User.get(id="123")
            >>> if user:
            ...     print(user.name)
        """
        backend = cls._get_backend()
        data = backend.get(cls, **filters)
        if data:
            instance = cls(**data)
            instance._is_persisted = True
            return instance
        return None

    @classmethod
    def find_by(cls, **conditions: Any) -> Optional["Model"]:
        """
        Find the first record matching conditions (eager execution).

        This method executes immediately and returns the first matching record.
        For lazy query building, use where() instead.

        Args:
            **conditions: Filter conditions (all ANDed together)

        Returns:
            First matching model instance, or None if not found

        Examples:
            >>> # Find first user with email
            >>> user = User.find_by(email="alice@example.com")
            >>> if user:
            ...     print(user.name)

            >>> # Find first active user
            >>> user = User.find_by(status="active")
        """
        return cls.where(**conditions).first()

    @classmethod
    def where(cls, **conditions: Any) -> "QueryBuilder":
        """
        Create a lazy query builder for finding records.

        Returns a QueryBuilder that doesn't execute until results are accessed
        (via .all(), .first(), .last(), iteration, etc.)

        All conditions passed as kwargs are ANDed together.

        Args:
            **conditions: Initial filter conditions (all ANDed together)

        Returns:
            QueryBuilder instance for chaining

        Examples:
            >>> # Find all active users (conditions ANDed)
            >>> users = User.where(status="active", age__gte=18).all()

            >>> # Chain conditions
            >>> users = User.where(age__gte=18).and_(status="active").limit(10).all()

            >>> # Boolean operators
            >>> query = User.where(role="admin").or_(role="moderator")
            >>> admins_and_mods = query.all()

            >>> # Iterate over results (lazy)
            >>> for user in User.where(age__gte=18):
            ...     print(user.name)
        """
        backend = cls._get_backend()
        query = backend.query(cls)
        if conditions:
            query = query.and_(**conditions)
        return query

    @classmethod
    def all(cls) -> list["Model"]:
        """
        Get all records.

        This is a convenience method equivalent to where().all()

        Returns:
            List of all model instances

        Example:
            >>> all_users = User.all()
        """
        return cls.where().all()

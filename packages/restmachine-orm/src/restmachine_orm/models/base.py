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


class Model(BaseModel):
    """
    Base model class for RestMachine ORM.

    Provides ActiveRecord-style CRUD operations and integrates with
    Pydantic for validation. Models are compatible with RestMachine
    for automatic API integration.

    Example:
        >>> class User(Model):
        ...     model_backend: ClassVar[Backend] = InMemoryBackend()
        ...
        ...     id: str = Field(primary_key=True)
        ...     email: str = Field(unique=True)
        ...     name: str
        ...
        >>> user = User.create(id="123", email="alice@example.com", name="Alice")
        >>> user.name = "Alice Smith"
        >>> user.save()

        Alternative syntax using class parameter:
        >>> class User(Model, model_backend=InMemoryBackend()):
        ...     id: str = Field(primary_key=True)
        ...     name: str
    """

    # Pydantic configuration
    model_config = ConfigDict(
        validate_assignment=True,  # Validate on attribute assignment
        arbitrary_types_allowed=True,  # Allow custom types
        from_attributes=True,  # Allow ORM mode
        ignored_types=(BeforeSaveCallback, AfterSaveCallback),  # Ignore callback descriptors
    )

    # Backend configuration
    model_backend: ClassVar[Optional["Backend"]] = None

    # Track if this is a new record or loaded from database
    _is_persisted: bool = False

    # Callback lists (populated by descriptors)
    _before_save_callbacks: ClassVar[list[Callable[["Model"], None]]] = []
    _after_save_callbacks: ClassVar[list[Callable[["Model"], None]]] = []

    # Hook lists (populated by __init_subclass__)
    _before_save_hooks: ClassVar[list[Callable[["Model"], None]]] = []
    _after_save_hooks: ClassVar[list[Callable[["Model"], None]]] = []
    _after_load_hooks: ClassVar[list[Callable[["Model"], None]]] = []
    _query_methods: ClassVar[dict[str, Callable]] = {}
    _query_operators: ClassVar[dict[tuple[str, str], Callable]] = {}
    _auto_query_filters: ClassVar[list[Callable]] = []
    _geo_field_names: ClassVar[list[str]] = []

    def __init_subclass__(cls, model_backend: Optional["Backend"] = None, **kwargs: Any):
        """
        Collect hooks from mixins when model class is defined.

        Args:
            model_backend: Optional backend to use for this model (alternative to ClassVar)
            **kwargs: Additional arguments passed to parent
        """
        super().__init_subclass__(**kwargs)

        # Support class parameter pattern: class User(Model, model_backend=InMemoryBackend())
        if model_backend is not None:
            cls.model_backend = model_backend

        # Reset class variables for this specific subclass
        cls._before_save_hooks = []
        cls._after_save_hooks = []
        cls._after_load_hooks = []
        cls._query_methods = {}
        cls._query_operators = {}
        cls._auto_query_filters = []
        cls._geo_field_names = []

        # Collect hooks from all bases (mixins) and the current class
        for base in [cls] + list(cls.__bases__):
            # Collect hooks from mixin methods
            for attr_name in dir(base):
                # Skip special Python attributes (double underscore)
                if attr_name.startswith('__'):
                    continue
                try:
                    attr = getattr(base, attr_name)
                    if callable(attr) and getattr(attr, '_is_before_save_hook', False):
                        if attr not in cls._before_save_hooks:
                            cls._before_save_hooks.append(attr)
                    elif callable(attr) and getattr(attr, '_is_after_save_hook', False):
                        if attr not in cls._after_save_hooks:
                            cls._after_save_hooks.append(attr)
                    elif callable(attr) and getattr(attr, '_is_after_load_hook', False):
                        if attr not in cls._after_load_hooks:
                            cls._after_load_hooks.append(attr)
                    elif callable(attr) and getattr(attr, '_is_query_method', False):
                        method_name = getattr(attr, '_query_method_name', attr.__name__)
                        cls._query_methods[method_name] = attr
                    elif callable(attr) and getattr(attr, '_is_query_operator', False):
                        # Type-based operator
                        if hasattr(attr, '_operator_type'):
                            op_type = getattr(attr, '_operator_type')
                            op_name = getattr(attr, '_operator_name')
                            # We'll map this to field names after fields are set
                            if not hasattr(cls, '_type_operators'):
                                cls._type_operators = {}  # type: ignore[attr-defined]
                            cls._type_operators[(op_type, op_name)] = attr  # type: ignore[attr-defined]
                        elif hasattr(attr, '_operator_types'):
                            for op_type in getattr(attr, '_operator_types'):
                                op_name = getattr(attr, '_operator_name')
                                if not hasattr(cls, '_type_operators'):
                                    cls._type_operators = {}  # type: ignore[attr-defined]
                                cls._type_operators[(op_type, op_name)] = attr  # type: ignore[attr-defined]
                except AttributeError:
                    continue

            # Collect auto query filters (from ExpirationMixin, etc.)
            if hasattr(base, '_auto_query_filters'):
                cls._auto_query_filters.extend(base._auto_query_filters)

        # Map type-based operators to field names
        if hasattr(cls, '_type_operators') and hasattr(cls, 'model_fields'):
            cls._map_type_operators_to_fields()

    @classmethod
    def _map_type_operators_to_fields(cls) -> None:
        """Map type-based operators to actual field names."""
        from typing import get_args, Union
        import sys

        # Try importing geo types, but don't fail if they're not installed
        try:
            from shapely.geometry import Point, Polygon, MultiPolygon  # type: ignore[import-untyped]
            geo_types = (Point, Polygon, MultiPolygon)
        except ImportError:
            geo_types = ()  # type: ignore[assignment]

        if not hasattr(cls, '_type_operators'):
            return

        for field_name, field_info in cls.model_fields.items():
            # Get the actual type (handle Optional, Annotated, etc.)
            field_type = field_info.annotation

            # Handle Optional[Type] -> Union[Type, None] or Type | None
            # In Python 3.10+, Type | None creates types.UnionType
            origin = getattr(field_type, '__origin__', None)
            if origin is not None:
                # typing.Union
                if origin is Union:
                    args = get_args(field_type)
                    # Get the non-None type
                    field_type = args[0] if args and args[0] is not type(None) else args[1] if len(args) > 1 else field_type
            elif sys.version_info >= (3, 10):
                # Python 3.10+ union syntax (Type | None)
                import types
                if isinstance(field_type, types.UnionType):  # type: ignore[attr-defined]
                    args = get_args(field_type)
                    # Get the non-None type
                    field_type = args[0] if args and args[0] is not type(None) else args[1] if len(args) > 1 else field_type

            # Check if this field type has registered operators
            for (op_type, op_name), handler in cls._type_operators.items():  # type: ignore[attr-defined]
                try:
                    if field_type == op_type or (isinstance(field_type, type) and issubclass(field_type, op_type)):
                        cls._query_operators[(field_name, op_name)] = handler

                        # Track geo fields
                        if geo_types and op_type in geo_types:
                            if field_name not in cls._geo_field_names:
                                cls._geo_field_names.append(field_name)
                except TypeError:
                    # Not a class, skip
                    continue

    @classmethod
    def _get_backend(cls) -> "Backend":
        """
        Get the backend for this model.

        Returns:
            Backend instance

        Raises:
            RuntimeError: If no backend is configured
        """
        if cls.model_backend is not None:
            return cls.model_backend

        raise RuntimeError(
            f"No backend configured for {cls.__name__}. "
            f"Set {cls.__name__}.model_backend = YourBackend() or pass model_backend=YourBackend() to class definition."
        )



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

        # Call hook-based before_save methods (from mixins)
        for hook in cls._before_save_hooks:
            hook(instance)

        # Call all registered before_save callbacks
        for callback in cls._before_save_callbacks:
            callback(instance)

        # Validate the model before saving
        instance.model_validate(instance.model_dump())

        backend = cls._get_backend()
        data = instance.model_dump()

        # Backend returns the data that was stored
        result_data = backend.upsert(cls, data)

        # Update instance with any fields set by backend extensions (e.g., timestamps)
        for key, value in result_data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        # Mark instance as persisted
        instance._is_persisted = True

        # Call hook-based after_save methods (from mixins)
        for hook in cls._after_save_hooks:
            hook(instance)

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
        # Call hook-based before_save methods (from mixins)
        for hook in self.__class__._before_save_hooks:
            hook(self)

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
            result_data = backend.create(self.__class__, data)
            self._is_persisted = True
            # Update instance with any fields set by backend extensions (e.g., timestamps)
            for key, value in result_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        else:
            # Update existing record
            result_data = backend.update(self.__class__, self)
            # Update instance with any fields modified by backend extensions
            for key, value in result_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)

        # Call hook-based after_save methods (from mixins)
        for hook in self.__class__._after_save_hooks:
            hook(self)

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

            # Call after_load hooks (for geo deserialization, etc.)
            for hook in cls._after_load_hooks:
                hook(instance)

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
        # Lazy initialization of query operators (needs to happen after Pydantic sets up model_fields)
        if hasattr(cls, '_type_operators') and not cls._query_operators:
            cls._map_type_operators_to_fields()

        backend = cls._get_backend()
        query = backend.query(cls)

        # Apply auto query filters (from ExpirationMixin, etc.)
        for auto_filter in cls._auto_query_filters:
            query = auto_filter(query)

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

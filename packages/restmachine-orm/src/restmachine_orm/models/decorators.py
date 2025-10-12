"""
Decorators for RestMachine ORM.

Provides decorators for defining composite keys in DynamoDB and other
backend-specific functionality.
"""

from typing import Callable, Any, TYPE_CHECKING
from functools import wraps

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class BeforeSaveCallback:
    """Descriptor for before_save callbacks."""

    def __init__(self, func: Callable[["Model"], None]):
        self.func = func

    def __set_name__(self, owner: type, name: str):
        """Register callback when descriptor is assigned to class.

        Ensures each subclass has its own callback list (not shared with parent)
        by checking if the list exists in the class's own __dict__.
        """
        if '_before_save_callbacks' not in owner.__dict__:
            owner._before_save_callbacks = []  # type: ignore[attr-defined]
        owner._before_save_callbacks.append(self.func)  # type: ignore[attr-defined]

    def __get__(self, instance: Any, owner: type) -> Callable:
        """Return callable method."""
        # Return bound method or unbound function
        if instance is None:
            return self.func
        return lambda: self.func(instance)


class AfterSaveCallback:
    """Descriptor for after_save callbacks."""

    def __init__(self, func: Callable[["Model"], None]):
        self.func = func

    def __set_name__(self, owner: type, name: str):
        """Register callback when descriptor is assigned to class.

        Ensures each subclass has its own callback list (not shared with parent)
        by checking if the list exists in the class's own __dict__.
        """
        if '_after_save_callbacks' not in owner.__dict__:
            owner._after_save_callbacks = []  # type: ignore[attr-defined]
        owner._after_save_callbacks.append(self.func)  # type: ignore[attr-defined]

    def __get__(self, instance: Any, owner: type) -> Callable:
        """Return callable method."""
        # Return bound method or unbound function
        if instance is None:
            return self.func
        return lambda: self.func(instance)


def partition_key(func: Callable[["Model"], str]) -> Callable[["Model"], str]:
    """
    Decorator to mark a method as the partition key (hash key) generator.

    Used for DynamoDB tables to define composite partition keys.
    The decorated method should return a string that will be used as the
    partition key value.

    Args:
        func: Method that generates the partition key string

    Returns:
        Decorated method with metadata

    Example:
        >>> class TodoItem(Model):
        ...     user_id: str
        ...     todo_id: str
        ...
        ...     @partition_key
        ...     def pk(self) -> str:
        ...         return f"USER#{self.user_id}"

    Note:
        Only one method per model should be decorated with @partition_key.
        The method name is conventionally 'pk' but can be anything.
    """
    @wraps(func)
    def wrapper(self: "Model") -> str:
        return func(self)

    # Mark the function with metadata
    wrapper._is_partition_key = True  # type: ignore
    wrapper._key_name = func.__name__  # type: ignore
    return wrapper


def sort_key(func: Callable[["Model"], str]) -> Callable[["Model"], str]:
    """
    Decorator to mark a method as the sort key (range key) generator.

    Used for DynamoDB tables to define composite sort keys.
    The decorated method should return a string that will be used as the
    sort key value.

    Args:
        func: Method that generates the sort key string

    Returns:
        Decorated method with metadata

    Example:
        >>> class TodoItem(Model):
        ...     user_id: str
        ...     created_at: datetime
        ...     todo_id: str
        ...
        ...     @partition_key
        ...     def pk(self) -> str:
        ...         return f"USER#{self.user_id}"
        ...
        ...     @sort_key
        ...     def sk(self) -> str:
        ...         return f"TODO#{self.created_at.isoformat()}#{self.todo_id}"

    Note:
        Only one method per model should be decorated with @sort_key.
        The method name is conventionally 'sk' but can be anything.
    """
    @wraps(func)
    def wrapper(self: "Model") -> str:
        return func(self)

    # Mark the function with metadata
    wrapper._is_sort_key = True  # type: ignore
    wrapper._key_name = func.__name__  # type: ignore
    return wrapper


def gsi_partition_key(index_name: str):
    """
    Decorator to mark a method as a GSI partition key generator.

    Used for DynamoDB Global Secondary Indexes.

    Args:
        index_name: Name of the GSI

    Returns:
        Decorator function

    Example:
        >>> class User(Model):
        ...     id: str
        ...     email: str
        ...     tenant_id: str
        ...
        ...     @gsi_partition_key("EmailIndex")
        ...     def gsi_pk_email(self) -> str:
        ...         return self.email
        ...
        ...     @gsi_partition_key("TenantIndex")
        ...     def gsi_pk_tenant(self) -> str:
        ...         return f"TENANT#{self.tenant_id}"
    """
    def decorator(func: Callable[["Model"], str]) -> Callable[["Model"], str]:
        @wraps(func)
        def wrapper(self: "Model") -> str:
            return func(self)

        wrapper._is_gsi_partition_key = True  # type: ignore
        wrapper._gsi_name = index_name  # type: ignore
        wrapper._key_name = func.__name__  # type: ignore
        return wrapper

    return decorator


def gsi_sort_key(index_name: str):
    """
    Decorator to mark a method as a GSI sort key generator.

    Used for DynamoDB Global Secondary Indexes.

    Args:
        index_name: Name of the GSI

    Returns:
        Decorator function

    Example:
        >>> class User(Model):
        ...     id: str
        ...     created_at: datetime
        ...     email: str
        ...
        ...     @gsi_partition_key("EmailIndex")
        ...     def gsi_pk_email(self) -> str:
        ...         return self.email
        ...
        ...     @gsi_sort_key("EmailIndex")
        ...     def gsi_sk_email(self) -> str:
        ...         return self.created_at.isoformat()
    """
    def decorator(func: Callable[["Model"], str]) -> Callable[["Model"], str]:
        @wraps(func)
        def wrapper(self: "Model") -> str:
            return func(self)

        wrapper._is_gsi_sort_key = True  # type: ignore
        wrapper._gsi_name = index_name  # type: ignore
        wrapper._key_name = func.__name__  # type: ignore
        return wrapper

    return decorator


def is_partition_key_method(method: Any) -> bool:
    """Check if a method is decorated with @partition_key."""
    return hasattr(method, "_is_partition_key") and method._is_partition_key


def is_sort_key_method(method: Any) -> bool:
    """Check if a method is decorated with @sort_key."""
    return hasattr(method, "_is_sort_key") and method._is_sort_key


def is_gsi_partition_key_method(method: Any) -> bool:
    """Check if a method is decorated with @gsi_partition_key."""
    return hasattr(method, "_is_gsi_partition_key") and method._is_gsi_partition_key


def is_gsi_sort_key_method(method: Any) -> bool:
    """Check if a method is decorated with @gsi_sort_key."""
    return hasattr(method, "_is_gsi_sort_key") and method._is_gsi_sort_key


def before_save(func: Callable[["Model"], None]) -> BeforeSaveCallback:
    """
    Decorator to mark a method to be called before saving to the database.

    Methods decorated with @before_save are called before the model is
    persisted to the backend. This allows you to:
    - Automatically update fields (e.g., updated_at timestamps)
    - Perform validation
    - Normalize data
    - Set computed fields

    The method should mutate the model instance as needed. These mutations
    will be included in the persisted data.

    Args:
        func: Method to call before save

    Returns:
        Descriptor that registers the callback

    Example:
        >>> class User(Model):
        ...     id: str = Field(primary_key=True)
        ...     name: str
        ...     updated_at: Optional[datetime] = None
        ...
        ...     @before_save
        ...     def update_timestamp(self):
        ...         self.updated_at = datetime.now()

    Note:
        - Multiple @before_save methods can be defined on a model
        - They are called in the order they are defined in the class
        - Mutations made in @before_save are persisted to the database
    """
    return BeforeSaveCallback(func)


def after_save(func: Callable[["Model"], None]) -> AfterSaveCallback:
    """
    Decorator to mark a method to be called after saving to the database.

    Methods decorated with @after_save are called after the model has been
    persisted to the backend. This allows you to:
    - Send notifications (emails, webhooks, etc.)
    - Update caches
    - Trigger async jobs
    - Log audit trails
    - Perform other side effects

    The method can access the model instance to read its values, but any
    mutations will NOT be automatically persisted (save would need to be
    called again).

    Args:
        func: Method to call after save

    Returns:
        Descriptor that registers the callback

    Example:
        >>> class User(Model):
        ...     id: str = Field(primary_key=True)
        ...     email: str
        ...     name: str
        ...
        ...     @after_save
        ...     def log_save(self):
        ...         print(f"User {self.id} was saved")

    Note:
        - Multiple @after_save methods can be defined on a model
        - They are called in the order they are defined in the class
        - Mutations made in @after_save are NOT automatically persisted
        - @after_save is useful for side effects, not data mutations
    """
    return AfterSaveCallback(func)

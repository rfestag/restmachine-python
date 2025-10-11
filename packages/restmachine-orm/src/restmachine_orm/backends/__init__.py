"""Backend implementations for RestMachine ORM."""

import warnings
from restmachine_orm.backends.base import Backend
from restmachine_orm.backends.memory import InMemoryBackend
from restmachine_orm.backends.adapters import (
    ModelAdapter,
    OpenSearchAdapter,
    InMemoryAdapter,
    CompositeAdapter,
)


def __getattr__(name):
    """Provide deprecation warnings for moved DynamoDB components."""
    if name == "DynamoDBBackend":
        warnings.warn(
            "DynamoDBBackend has been moved to the restmachine-orm-dynamodb package. "
            "Please install it with 'pip install restmachine-orm-dynamodb' and import from "
            "'restmachine_orm_dynamodb' instead of 'restmachine_orm.backends'.",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            from restmachine_orm_dynamodb import DynamoDBBackend
            return DynamoDBBackend
        except ImportError:
            raise ImportError(
                "DynamoDBBackend is no longer available in restmachine-orm. "
                "Install restmachine-orm-dynamodb: pip install restmachine-orm-dynamodb"
            )
    elif name == "DynamoDBAdapter":
        warnings.warn(
            "DynamoDBAdapter has been moved to the restmachine-orm-dynamodb package. "
            "Please install it with 'pip install restmachine-orm-dynamodb' and import from "
            "'restmachine_orm_dynamodb' instead of 'restmachine_orm.backends'.",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            from restmachine_orm_dynamodb import DynamoDBAdapter
            return DynamoDBAdapter
        except ImportError:
            raise ImportError(
                "DynamoDBAdapter is no longer available in restmachine-orm. "
                "Install restmachine-orm-dynamodb: pip install restmachine-orm-dynamodb"
            )
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "Backend",
    "InMemoryBackend",
    "ModelAdapter",
    "OpenSearchAdapter",
    "InMemoryAdapter",
    "CompositeAdapter",
    # DynamoDB components moved to restmachine-orm-dynamodb
    "DynamoDBBackend",  # Deprecated - for backwards compatibility
    "DynamoDBAdapter",  # Deprecated - for backwards compatibility
]

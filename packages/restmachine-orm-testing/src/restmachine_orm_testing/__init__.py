"""
Testing framework for RestMachine ORM.

Provides DSL and drivers for backend-agnostic ORM testing.
"""

from .dsl import (
    ModelOperation,
    OrmDsl,
    CreateOperation,
    GetOperation,
    UpdateOperation,
    DeleteOperation,
    UpsertOperation,
    QueryOperation,
    OperationResult,
)
from .drivers import (
    DriverInterface,
    InMemoryDriver,
)
from .multi_backend_base import (
    MultiBackendTestBase,
    multi_backend_test_class,
    skip_backend,
    only_backends,
)

__all__ = [
    # DSL
    "ModelOperation",
    "OrmDsl",
    "CreateOperation",
    "GetOperation",
    "UpdateOperation",
    "DeleteOperation",
    "UpsertOperation",
    "QueryOperation",
    "OperationResult",
    # Drivers
    "DriverInterface",
    "InMemoryDriver",
    # Test base
    "MultiBackendTestBase",
    "multi_backend_test_class",
    "skip_backend",
    "only_backends",
]

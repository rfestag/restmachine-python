"""
Testing framework for RestMachine ORM.

DEPRECATED: This module has been moved to the restmachine-orm-testing package.
This re-export is for backward compatibility only. Please update your imports to use:

    from restmachine_orm_testing import OrmDsl, InMemoryDriver, MultiBackendTestBase

Instead of:

    from restmachine_orm.testing import OrmDsl, InMemoryDriver, MultiBackendTestBase
"""

# Re-export from the new package for backward compatibility
# Only import if the package is available
try:
    from restmachine_orm_testing import (  # type: ignore[import-not-found]  # noqa: F401
        # DSL
        ModelOperation,
        OrmDsl,
        CreateOperation,
        GetOperation,
        UpdateOperation,
        DeleteOperation,
        UpsertOperation,
        QueryOperation,
        OperationResult,
        # Drivers
        DriverInterface,
        InMemoryDriver,
        # Test base
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
except ImportError:
    # restmachine-orm-testing not installed
    __all__ = []

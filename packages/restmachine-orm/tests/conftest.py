"""
Pytest configuration for ORM tests.

Enables multi-backend testing infrastructure.
"""

import pytest
from restmachine_orm_testing import MultiBackendTestBase


def pytest_generate_tests(metafunc):
    """
    Generate tests for each enabled backend.

    This hook allows MultiBackendTestBase classes to parametrize their tests
    across multiple backends.
    """
    # Check if this is a MultiBackendTestBase subclass
    if metafunc.cls and issubclass(metafunc.cls, MultiBackendTestBase):
        if "orm" in metafunc.fixturenames:
            backends = metafunc.cls.get_available_backends()
            metafunc.parametrize("orm", backends, indirect=True, ids=backends)

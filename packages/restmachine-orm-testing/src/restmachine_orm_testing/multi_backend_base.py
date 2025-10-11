"""
Multi-backend test base for automatic backend discovery and execution.

This module provides a base class that automatically runs tests against all available backends.
Each test file should inherit from MultiBackendTestBase and define model classes for testing.
"""

import pytest
from typing import List, Type, Optional
from abc import ABC, abstractmethod

from .dsl import OrmDsl
from .drivers import DriverInterface, InMemoryDriver


class MultiBackendTestBase(ABC):
    """
    Base class for multi-backend tests.

    Automatically runs each test method against all available backends.
    Subclasses must implement get_test_models() to define models for testing.
    """

    # Override this in subclasses to control which backends to test
    ENABLED_BACKENDS = [
        'inmemory',  # InMemory backend: reference implementation
    ]

    # Optional: Override to exclude specific backends for certain test files
    EXCLUDED_BACKENDS: List[str] = []

    @abstractmethod
    def get_test_models(self) -> List[Type]:
        """
        Get list of model classes used in this test.

        This method should return a list of Model classes that will be tested.
        The backend will be configured for these models automatically.

        Returns:
            List of Model classes
        """
        pass

    @classmethod
    def get_available_backends(cls) -> List[str]:
        """Get list of available backend names for this test class."""
        available = [backend for backend in cls.ENABLED_BACKENDS
                    if backend not in cls.EXCLUDED_BACKENDS]
        return available

    @classmethod
    def create_driver(cls, backend_name: str) -> DriverInterface:
        """Create a driver instance for the given backend name."""
        driver_map = {
            'inmemory': lambda: InMemoryDriver(),
        }

        # DynamoDB backend will be added by restmachine-orm-dynamodb package
        # via conftest.py monkey-patching

        if backend_name not in driver_map:
            pytest.skip(f"Backend '{backend_name}' not available. Available: {list(driver_map.keys())}")

        return driver_map[backend_name]()

    @pytest.fixture
    def orm(self, request):
        """
        Parametrized fixture that provides ORM DSL client for each enabled backend.

        This fixture is automatically parametrized with all enabled backends.
        """
        backend_name = request.param
        driver = self.create_driver(backend_name)

        # Set up backend for all test models
        models = self.get_test_models()
        for model in models:
            driver.setup_backend(model)

        # Clear storage before test
        driver.clear()

        yield OrmDsl(driver), backend_name

        # Clear storage after test
        driver.clear()


def multi_backend_test_class(enabled_backends: Optional[List[str]] = None,
                             excluded_backends: Optional[List[str]] = None):
    """
    Class decorator to configure multi-backend testing.

    Args:
        enabled_backends: List of backend names to enable for this test class
        excluded_backends: List of backend names to exclude for this test class

    Usage:
        @multi_backend_test_class(enabled_backends=['inmemory', 'dynamodb'])
        class TestUserModel(MultiBackendTestBase):
            def get_test_models(self):
                return [User]

            def test_create_user(self, orm):
                orm_client, backend_name = orm
                # Test code here
    """
    def decorator(cls):
        if enabled_backends is not None:
            cls.ENABLED_BACKENDS = enabled_backends
        if excluded_backends is not None:
            cls.EXCLUDED_BACKENDS = excluded_backends
        return cls
    return decorator


def skip_backend(backend_name: str, reason: str = "Backend not supported for this test"):
    """
    Decorator to skip a specific test for a particular backend.

    Usage:
        @skip_backend('dynamodb', 'This test requires in-memory features')
        def test_something(self, orm):
            orm_client, backend_name = orm
            # Test code here
    """
    def decorator(func):
        def wrapper(self, orm, *args, **kwargs):
            orm_client, current_backend = orm
            if current_backend == backend_name:
                pytest.skip(reason)
            return func(self, orm, *args, **kwargs)
        return wrapper
    return decorator


def only_backends(*backend_names: str):
    """
    Decorator to run a test only on specific backends.

    Usage:
        @only_backends('inmemory', 'dynamodb')
        def test_something(self, orm):
            orm_client, backend_name = orm
            # Test code here
    """
    def decorator(func):
        def wrapper(self, orm, *args, **kwargs):
            orm_client, current_backend = orm
            if current_backend not in backend_names:
                pytest.skip(f"Test only runs on backends: {backend_names}")
            return func(self, orm, *args, **kwargs)
        return wrapper
    return decorator

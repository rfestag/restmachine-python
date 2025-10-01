"""
Multi-driver test base for automatic driver discovery and execution.

This module provides a base class that automatically runs tests against all available drivers.
Each test file should inherit from MultiDriverTestBase and define a single create_app() method.
"""

import pytest
from typing import List
from abc import ABC, abstractmethod

from restmachine import RestApplication
from .dsl import RestApiDsl
from .drivers import (
    DriverInterface,
    RestMachineDriver,
    AwsLambdaDriver,
    MockDriver
)


class MultiDriverTestBase(ABC):
    """
    Base class for multi-driver tests.

    Automatically runs each test method against all available drivers.
    Subclasses must implement create_app() to define the application under test.
    """

    # Override this in subclasses to control which drivers to test
    ENABLED_DRIVERS = [
        'direct',           # Direct driver: calls RestMachine directly
        'aws_lambda',       # AWS Lambda driver: simulates AWS API Gateway events
        'uvicorn-http1',    # HTTP/1.1 driver via Uvicorn server
        'hypercorn-http1',  # HTTP/1.1 driver via Hypercorn server
        'uvicorn-http2',    # HTTP/2 driver via Uvicorn server
        'hypercorn-http2',  # HTTP/2 driver via Hypercorn server
    ]

    # Optional: Override to exclude specific drivers for certain test files
    EXCLUDED_DRIVERS = []

    @abstractmethod
    def create_app(self) -> RestApplication:
        """
        Create and configure the application for testing.

        This method should return a fully configured RestApplication instance
        that will be tested against all enabled drivers.
        """
        pass

    @classmethod
    def get_available_drivers(cls) -> List[str]:
        """Get list of available driver names for this test class."""
        available = [driver for driver in cls.ENABLED_DRIVERS
                    if driver not in cls.EXCLUDED_DRIVERS]
        return available

    @classmethod
    def create_driver(cls, driver_name: str, app: RestApplication) -> DriverInterface:
        """Create a driver instance for the given driver name."""
        driver_map = {
            'direct': lambda app: RestMachineDriver(app),
            'aws_lambda': lambda app: AwsLambdaDriver(app),
            'aws_lambda_debug': lambda app: AwsLambdaDriver(app, enable_debugging=True),
            'mock': lambda app: MockDriver()  # Note: MockDriver doesn't use app
        }

        # Try to import HTTP drivers (may not be available)
        try:
            from .http_drivers import (
                UvicornHttp1Driver,
                UvicornHttp2Driver,
                HypercornHttp1Driver,
                HypercornHttp2Driver,
            )
            driver_map.update({
                'uvicorn-http1': lambda app: UvicornHttp1Driver(app),
                'uvicorn-http2': lambda app: UvicornHttp2Driver(app),
                'hypercorn-http1': lambda app: HypercornHttp1Driver(app),
                'hypercorn-http2': lambda app: HypercornHttp2Driver(app),
            })
        except ImportError:
            pass  # HTTP drivers not available

        if driver_name not in driver_map:
            pytest.skip(f"Driver '{driver_name}' not available. Available: {list(driver_map.keys())}")

        return driver_map[driver_name](app)

    @pytest.fixture(scope="class")
    def api(self, request):
        """
        Parametrized fixture that provides API client for each enabled driver.

        This fixture is automatically parametrized with all enabled drivers.
        Uses class scope to reuse servers across all tests in a class.
        """
        driver_name = request.param
        app = self.create_app()
        driver = self.create_driver(driver_name, app)

        # HTTP drivers need to be started/stopped with context manager
        if driver_name.startswith('uvicorn-') or driver_name.startswith('hypercorn-'):
            with driver as active_driver:
                import time
                time.sleep(0.05)  # Reduced from 0.1s - minimal time needed
                yield RestApiDsl(active_driver), driver_name
        else:
            # Direct and Lambda drivers don't need context manager
            yield RestApiDsl(driver), driver_name


def multi_driver_test_class(enabled_drivers: List[str] = None,
                           excluded_drivers: List[str] = None):
    """
    Class decorator to configure multi-driver testing.

    Args:
        enabled_drivers: List of driver names to enable for this test class
        excluded_drivers: List of driver names to exclude for this test class

    Usage:
        @multi_driver_test_class(enabled_drivers=['direct', 'aws_lambda'])
        class TestMyApi(MultiDriverTestBase):
            def create_app(self):
                return RestApplication()
    """
    def decorator(cls):
        if enabled_drivers is not None:
            cls.ENABLED_DRIVERS = enabled_drivers
        if excluded_drivers is not None:
            cls.EXCLUDED_DRIVERS = excluded_drivers
        return cls
    return decorator


def skip_driver(driver_name: str, reason: str = "Driver not supported for this test"):
    """
    Decorator to skip a specific test for a particular driver.

    Usage:
        @skip_driver('aws_lambda', 'This test requires direct access')
        def test_something(self, api):
            api_client, driver_name = api
            # Test code here
    """
    def decorator(func):
        def wrapper(self, api, *args, **kwargs):
            api_client, current_driver = api
            if current_driver == driver_name:
                pytest.skip(reason)
            return func(self, api, *args, **kwargs)
        return wrapper
    return decorator


def only_drivers(*driver_names: str):
    """
    Decorator to run a test only on specific drivers.

    Usage:
        @only_drivers('direct', 'aws_lambda')
        def test_something(self, api):
            api_client, driver_name = api
            # Test code here
    """
    def decorator(func):
        def wrapper(self, api, *args, **kwargs):
            api_client, current_driver = api
            if current_driver not in driver_names:
                pytest.skip(f"Test only runs on drivers: {driver_names}")
            return func(self, api, *args, **kwargs)
        return wrapper
    return decorator



"""
Pytest configuration for multi-driver testing.

This file sets up automatic parametrization for test classes that inherit from
MultiDriverTestBase and adds driver-specific markers.
"""

import pytest
from tests.framework.multi_driver_base import MultiDriverTestBase


def pytest_configure(config):
    """Configure pytest-anyio to use only asyncio backend (trio not installed)."""
    config.option.anyio_backends = ["asyncio"]


def pytest_generate_tests(metafunc):
    """
    Pytest hook to automatically parametrize the 'api' fixture for MultiDriverTestBase subclasses.

    This ensures every test method in classes that inherit from MultiDriverTestBase
    gets run against all enabled drivers.

    Only affects tests in the restmachine/tests directory (not adapter packages).
    """
    # Check if this is a test class that inherits from MultiDriverTestBase
    if (hasattr(metafunc, 'cls') and
        metafunc.cls is not None and
        issubclass(metafunc.cls, MultiDriverTestBase) and
        'api' in metafunc.fixturenames):

        # Only parametrize tests in this package (packages/restmachine/tests)
        # Check if the test file is in our tests directory (not imported into adapter packages)
        if "/packages/restmachine/tests/" not in metafunc.module.__file__:
            return

        # Get the available drivers for this test class
        drivers = metafunc.cls.get_available_drivers()

        # Parametrize the api fixture with all available drivers
        metafunc.parametrize(
            'api',
            drivers,
            indirect=True,
            ids=[f"driver-{d}" for d in drivers]
        )


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to add driver-specific markers to parametrized tests.

    This allows running tests for specific drivers using markers like:
        pytest -m driver_direct
        pytest -m "driver_direct or driver_aws_lambda"
        pytest -m "not driver_uvicorn_http1"
    """
    # Performance test class names - mark these wherever they appear
    performance_test_classes = {
        # State machine path performance tests
        'TestSimpleGetPath',
        'TestAuthenticatedGetPath',
        'TestConditionalGetPath',
        'TestPostCreatePath',
        'TestPutUpdatePath',
        'TestDeletePath',
        'TestErrorPaths',
        'TestCRUDCyclePath',
        # Future performance tests (placeholders)
        'TestGetRequestPerformance',
        'TestPostRequestPerformance',
        'TestPutRequestPerformance',
        'TestDeleteRequestPerformance',
        'TestMixedOperationsPerformance',
        'TestPathParameterPerformance',
        'TestQueryParameterPerformance',
        'TestComplexRoutingPerformance',
        'TestMixedParametersPerformance',
        'TestSmallPayloadPerformance',
        'TestMediumPayloadPerformance',
        'TestLargePayloadPerformance',
        'TestNestedJsonPerformance',
        'TestVariousDataTypesPerformance',
    }

    # Deselect trio tests (trio is not installed, only asyncio is supported)
    deselected = []
    remaining = []
    for item in items:
        if '[trio]' in item.nodeid:
            deselected.append(item)
        else:
            remaining.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = remaining

    for item in items:
        # Add performance marker based on test class name OR file path
        # This catches performance tests wherever they're imported
        test_class_name = item.cls.__name__ if item.cls else None
        if test_class_name in performance_test_classes or "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)

        # Check if this test has a parametrized driver (look for 'driver-' in the node id)
        if 'driver-' in item.nodeid:
            # Extract driver name from the node id (e.g., "driver-direct" -> "direct")
            parts = item.nodeid.split('[')
            if len(parts) > 1:
                param_part = parts[-1].rstrip(']')
                if param_part.startswith('driver-'):
                    driver_name = param_part.replace('driver-', '')
                    # Convert driver name to marker name (e.g., "aws_lambda" -> "driver_aws_lambda")
                    # Replace hyphens with underscores for marker names
                    marker_name = f"driver_{driver_name.replace('-', '_')}"
                    item.add_marker(getattr(pytest.mark, marker_name))
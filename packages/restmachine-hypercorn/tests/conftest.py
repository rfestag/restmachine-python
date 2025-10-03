"""
Pytest configuration for Hypercorn driver testing.

This file sets up testing to run all core RestMachine tests against the Hypercorn driver.
It imports the core test framework and configures it to use only the Hypercorn drivers.
"""

import pytest
import sys
from pathlib import Path

# Add core tests directory to path so we can import test modules
# Path structure: restmachine-python/packages/restmachine-hypercorn/tests/conftest.py
# We need: restmachine-python/packages/restmachine
core_package_dir = Path(__file__).parent.parent.parent / "restmachine"
core_tests_dir = core_package_dir / "tests"
if core_tests_dir.exists():
    sys.path.insert(0, str(core_package_dir))
else:
    raise RuntimeError(f"Cannot find core tests directory at {core_tests_dir}")

# Make sure we can import the core test framework
# The core package should be installed in editable mode
from restmachine.testing.multi_driver_base import MultiDriverTestBase  # noqa: E402

# Import our Hypercorn drivers
from restmachine_hypercorn import HypercornHttp1Driver, HypercornHttp2Driver  # noqa: E402


def pytest_generate_tests(metafunc):
    """
    Pytest hook to automatically parametrize the 'api' fixture for MultiDriverTestBase subclasses.

    This runs tests only against the Hypercorn drivers (HTTP/1.1 and HTTP/2), unlike the core package
    which tests against multiple drivers.

    Only affects tests in the restmachine-hypercorn/tests directory.
    """
    # Check if this is a test class that inherits from MultiDriverTestBase
    if (hasattr(metafunc, 'cls') and
        metafunc.cls is not None and
        issubclass(metafunc.cls, MultiDriverTestBase) and
        'api' in metafunc.fixturenames):

        # Only parametrize tests in this package (packages/restmachine-hypercorn/tests)
        # Check if the test file is in our tests directory (not core tests)
        if "/packages/restmachine-hypercorn/tests/" not in metafunc.module.__file__:
            return

        # Only use hypercorn drivers for Hypercorn package tests
        drivers = ['hypercorn-http1', 'hypercorn-http2']

        # Parametrize the api fixture with Hypercorn drivers only
        metafunc.parametrize(
            'api',
            drivers,
            indirect=True,
            ids=[f"driver-{d}" for d in drivers]
        )


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to add driver-specific markers and performance markers to tests.

    This allows running tests for specific drivers using markers.
    """
    # Performance test class names - mark these wherever they appear
    performance_test_classes = {
        'TestSimpleGetPath',
        'TestAuthenticatedGetPath',
        'TestConditionalGetPath',
        'TestPostCreatePath',
        'TestPutUpdatePath',
        'TestDeletePath',
        'TestErrorPaths',
        'TestCRUDCyclePath',
    }

    for item in items:
        # Add performance marker based on test class name OR file path
        test_class_name = item.cls.__name__ if item.cls else None
        if test_class_name in performance_test_classes or "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)

        # Check if this test has a parametrized driver (look for 'driver-' in the node id)
        if 'driver-' in item.nodeid:
            # Extract driver name from the node id (e.g., "driver-hypercorn-http1" -> "hypercorn-http1")
            parts = item.nodeid.split('[')
            if len(parts) > 1:
                param_part = parts[-1].rstrip(']')
                if param_part.startswith('driver-'):
                    driver_name = param_part.replace('driver-', '')
                    # Convert driver name to marker name (e.g., "hypercorn-http1" -> "driver_hypercorn_http1")
                    marker_name = f"driver_{driver_name.replace('-', '_')}"
                    item.add_marker(getattr(pytest.mark, marker_name))


# Override the MultiDriverTestBase.create_driver method to support Hypercorn drivers
_original_create_driver = MultiDriverTestBase.create_driver


@classmethod
def _create_driver_with_hypercorn(cls, driver_name: str, app):
    """Extended create_driver that supports Hypercorn drivers."""
    if driver_name == 'hypercorn-http1':
        return HypercornHttp1Driver(app)
    elif driver_name == 'hypercorn-http2':
        return HypercornHttp2Driver(app)
    # Fall back to original implementation for other drivers
    return _original_create_driver(driver_name, app)


# Monkey-patch the create_driver method to add Hypercorn support
MultiDriverTestBase.create_driver = _create_driver_with_hypercorn


@pytest.fixture(scope="class")
def api(self, request):
    """
    Class-scoped fixture that provides API client for hypercorn drivers.

    Optimized with fast shutdown (reduced timeouts) for better test performance.
    """
    driver_name = request.param
    app = self.create_app()
    driver = self.create_driver(driver_name, app)

    # HTTP server drivers need to be started/stopped with context manager
    if driver_name.startswith('hypercorn-') or driver_name.startswith('uvicorn-'):
        with driver as active_driver:
            from restmachine.testing.dsl import RestApiDsl
            yield RestApiDsl(active_driver), driver_name
    else:
        # Other drivers (direct, aws_lambda, etc.) don't need context manager
        from restmachine.testing.dsl import RestApiDsl
        yield RestApiDsl(driver), driver_name


# Replace the fixture
MultiDriverTestBase.api = api

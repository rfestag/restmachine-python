"""
Pytest configuration for Uvicorn driver testing.

This file sets up testing to run all core RestMachine tests against the Uvicorn driver.
It imports the core test framework and configures it to use only the Uvicorn driver.
"""

import pytest
import sys
from pathlib import Path

# Add core tests directory to path so we can import test modules
# Path structure: restmachine-python/packages/restmachine-uvicorn/tests/conftest.py
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

# Import our Uvicorn driver
from restmachine_uvicorn import UvicornHttp1Driver  # noqa: E402


def pytest_generate_tests(metafunc):
    """
    Pytest hook to automatically parametrize the 'api' fixture for MultiDriverTestBase subclasses.

    This runs tests only against the Uvicorn driver (HTTP/1.1), unlike the core package
    which tests against the direct driver only.

    Only affects tests in the restmachine-uvicorn/tests directory.
    """
    # Check if this is a test class that inherits from MultiDriverTestBase
    if (hasattr(metafunc, 'cls') and
        metafunc.cls is not None and
        issubclass(metafunc.cls, MultiDriverTestBase) and
        'api' in metafunc.fixturenames):

        # Only parametrize tests in this package (packages/restmachine-uvicorn/tests)
        # Check if the test file is in our tests directory (not core tests)
        if "/packages/restmachine-uvicorn/tests/" not in metafunc.module.__file__:
            return

        # Only use uvicorn driver for Uvicorn package tests
        drivers = ['uvicorn-http1']

        # Parametrize the api fixture with Uvicorn driver only
        metafunc.parametrize(
            'api',
            drivers,
            indirect=True,
            ids=[f"driver-{d}" for d in drivers]
        )


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to add driver-specific markers to parametrized tests.

    This allows running tests for specific drivers using markers.
    """
    for item in items:
        # Check if this test has a parametrized driver (look for 'driver-' in the node id)
        if 'driver-' in item.nodeid:
            # Extract driver name from the node id (e.g., "driver-uvicorn-http1" -> "uvicorn-http1")
            parts = item.nodeid.split('[')
            if len(parts) > 1:
                param_part = parts[-1].rstrip(']')
                if param_part.startswith('driver-'):
                    driver_name = param_part.replace('driver-', '')
                    # Convert driver name to marker name (e.g., "uvicorn-http1" -> "driver_uvicorn_http1")
                    marker_name = f"driver_{driver_name.replace('-', '_')}"
                    item.add_marker(getattr(pytest.mark, marker_name))


# Override the MultiDriverTestBase.create_driver method to support Uvicorn driver
_original_create_driver = MultiDriverTestBase.create_driver


@classmethod
def _create_driver_with_uvicorn(cls, driver_name: str, app):
    """Extended create_driver that supports Uvicorn driver."""
    if driver_name == 'uvicorn-http1':
        return UvicornHttp1Driver(app)
    # Fall back to original implementation for other drivers
    return _original_create_driver(driver_name, app)


# Monkey-patch the create_driver method to add Uvicorn support
MultiDriverTestBase.create_driver = _create_driver_with_uvicorn


@pytest.fixture(scope="class")
def api(self, request):
    """
    Class-scoped fixture that provides API client for uvicorn driver.

    Optimized with fast shutdown (reduced timeouts) for better test performance.
    """
    driver_name = request.param
    app = self.create_app()
    driver = self.create_driver(driver_name, app)

    # HTTP server drivers need to be started/stopped with context manager
    if driver_name.startswith('uvicorn-') or driver_name.startswith('hypercorn-'):
        with driver as active_driver:
            from restmachine.testing.dsl import RestApiDsl
            yield RestApiDsl(active_driver), driver_name
    else:
        # Other drivers (direct, aws_lambda, etc.) don't need context manager
        from restmachine.testing.dsl import RestApiDsl
        yield RestApiDsl(driver), driver_name


# Replace the fixture
MultiDriverTestBase.api = api

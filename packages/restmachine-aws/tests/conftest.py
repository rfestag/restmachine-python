"""
Pytest configuration for AWS Lambda driver testing.

This file sets up testing to run all core RestMachine tests against the AWS Lambda driver.
It imports the core test framework and configures it to use only the AWS Lambda driver.
"""

import pytest
import sys
from pathlib import Path
import os

# Add core tests directory to path so we can import test modules
# Path structure: restmachine-python/packages/restmachine-aws/tests/conftest.py
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

# Import our AWS Lambda driver
# Add tests directory to path for framework imports
sys.path.insert(0, os.path.dirname(__file__))
from framework.driver import AwsLambdaDriver  # noqa: E402


def pytest_generate_tests(metafunc):
    """
    Pytest hook to automatically parametrize the 'api' fixture for MultiDriverTestBase subclasses.

    This runs tests only against the AWS Lambda driver, unlike the core package which tests
    against multiple drivers.
    """
    # Check if this is a test class that inherits from MultiDriverTestBase
    if (hasattr(metafunc, 'cls') and
        metafunc.cls is not None and
        issubclass(metafunc.cls, MultiDriverTestBase) and
        'api' in metafunc.fixturenames):

        # Only use aws_lambda driver for AWS package tests
        drivers = ['aws_lambda']

        # Parametrize the api fixture with AWS driver only
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
            # Extract driver name from the node id (e.g., "driver-aws_lambda" -> "aws_lambda")
            parts = item.nodeid.split('[')
            if len(parts) > 1:
                param_part = parts[-1].rstrip(']')
                if param_part.startswith('driver-'):
                    driver_name = param_part.replace('driver-', '')
                    # Convert driver name to marker name (e.g., "aws_lambda" -> "driver_aws_lambda")
                    marker_name = f"driver_{driver_name.replace('-', '_')}"
                    item.add_marker(getattr(pytest.mark, marker_name))


# Override the MultiDriverTestBase.create_driver method to support AWS Lambda driver
_original_create_driver = MultiDriverTestBase.create_driver


@classmethod
def _create_driver_with_aws(cls, driver_name: str, app):
    """Extended create_driver that supports AWS Lambda driver."""
    if driver_name == 'aws_lambda':
        return AwsLambdaDriver(app)
    # Fall back to original implementation for other drivers
    return _original_create_driver(driver_name, app)


# Monkey-patch the create_driver method to add AWS support
MultiDriverTestBase.create_driver = _create_driver_with_aws

"""
Pytest configuration for restmachine-web tests.
"""

import pytest
from restmachine.testing import MultiDriverTestBase


def pytest_generate_tests(metafunc):
    """
    Pytest hook to automatically parametrize the 'api' fixture for MultiDriverTestBase subclasses.

    This ensures every test method in classes that inherit from MultiDriverTestBase
    gets run against all enabled drivers.
    """
    # Check if this is a test class that inherits from MultiDriverTestBase
    if (hasattr(metafunc, 'cls') and
        metafunc.cls is not None and
        issubclass(metafunc.cls, MultiDriverTestBase) and
        'api' in metafunc.fixturenames):

        # Get the available drivers for this test class
        drivers = metafunc.cls.get_available_drivers()

        # Parametrize the api fixture with all available drivers
        metafunc.parametrize(
            'api',
            drivers,
            indirect=True,
            ids=[f"driver-{d}" for d in drivers]
        )

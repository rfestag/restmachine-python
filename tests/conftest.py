"""
Pytest configuration for multi-driver testing.

This file sets up automatic parametrization for test classes that inherit from
MultiDriverTestBase.
"""

from tests.framework.multi_driver_base import MultiDriverTestBase


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
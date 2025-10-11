"""
Pytest configuration for DynamoDB backend tests.

Registers DynamoDB driver with the testing framework and sets up moto.
"""

import pytest
import boto3
from moto import mock_aws

from restmachine_orm.testing import MultiBackendTestBase
from restmachine_orm_dynamodb.testing import DynamoDBDriver


# Register DynamoDB driver with the testing framework
original_create_driver = MultiBackendTestBase.create_driver


@classmethod
def patched_create_driver(cls, backend_name: str):
    """Create driver with DynamoDB support."""
    if backend_name == 'dynamodb':
        return DynamoDBDriver(table_name="test-table", region_name="us-east-1")
    return original_create_driver(backend_name)


# Monkey-patch the create_driver method
MultiBackendTestBase.create_driver = patched_create_driver


@pytest.fixture(scope="session", autouse=True)
def setup_moto():
    """Set up moto mock for all tests."""
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_table():
    """Get the mock DynamoDB table for testing."""
    # Table is created fresh for each test within the session-level mock_aws context
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create table
    table = dynamodb.create_table(
        TableName="test-table",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Wait for table to be created
    table.meta.client.get_waiter("table_exists").wait(TableName="test-table")

    yield table

    # Clean up - delete table after test
    try:
        table.delete()
        table.meta.client.get_waiter("table_not_exists").wait(TableName="test-table")
    except Exception:
        pass  # Table might already be gone


@pytest.fixture
def backend(dynamodb_table):
    """Create DynamoDB backend for testing."""
    from restmachine_orm_dynamodb import DynamoDBBackend

    return DynamoDBBackend(
        table_name="test-table",
        region_name="us-east-1",
    )


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

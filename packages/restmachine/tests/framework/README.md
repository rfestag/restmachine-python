# Multi-Driver Testing Framework

This framework implements a new approach to testing where each test file defines a single application and automatically runs every test against all available drivers. This ensures that the library works consistently across different deployment environments.

## Overview

The new testing approach replaces the previous method where each test had to explicitly specify which driver to use. Instead, tests now:

1. **Define a single app** in the `create_app()` method
2. **Automatically run against all drivers** (direct, AWS Lambda, enhanced AWS, etc.)
3. **Provide consistent validation** that the library works across all environments

## Key Components

### MultiDriverTestBase

The base class that all test classes should inherit from:

```python
from tests.framework import MultiDriverTestBase

class TestMyApi(MultiDriverTestBase):
    def create_app(self) -> RestApplication:
        """Define your application once."""
        app = RestApplication()

        @app.get("/hello")
        def hello():
            return {"message": "Hello World"}

        return app

    def test_hello_endpoint(self, api):
        """This test runs against ALL drivers automatically."""
        api_client, driver_name = api

        response = api_client.get_resource("/hello")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"
```

### Available Drivers

The framework automatically tests against these drivers:

- **direct**: `RestMachineDriver` - Direct library execution
- **aws_lambda**: `AwsLambdaDriver` - AWS Lambda/API Gateway simulation with full binary support and debugging capabilities
- **aws_lambda_debug**: `AwsLambdaDriver` (with debugging enabled) - AWS Lambda simulation with event/response inspection

### Driver Selection

You can customize which drivers to test against:

```python
from tests.framework import MultiDriverTestBase, multi_driver_test_class

# Use decorator to specify drivers
@multi_driver_test_class(enabled_drivers=['direct', 'aws_lambda'])
class TestSpecificDrivers(MultiDriverTestBase):
    def create_app(self):
        # ... app definition

# Or set class attributes
class TestCustomDrivers(MultiDriverTestBase):
    ENABLED_DRIVERS = ['direct', 'aws_lambda_debug']
    EXCLUDED_DRIVERS = ['aws_lambda']  # Exclude specific drivers
```

### Handling Driver Limitations

In rare cases where a driver has fundamental limitations, use decorators to skip specific tests:

```python
from tests.framework import MultiDriverTestBase, skip_driver, only_drivers

class TestWithLimitations(MultiDriverTestBase):
    def create_app(self):
        # ... app definition

    @skip_driver('mock', 'Mock driver does not execute real application logic')
    def test_that_needs_real_execution(self, api):
        api_client, driver_name = api
        # This test is skipped for mock driver only

    @only_drivers('direct', 'aws_lambda')
    def test_requiring_specific_drivers(self, api):
        api_client, driver_name = api
        # This test only runs on specified drivers
        # Use sparingly - prefer fixing drivers to make tests universal
```

**Important**: Use these decorators sparingly. If you find yourself needing driver-specific logic, consider whether:
1. The driver needs to be enhanced to provide consistent behavior
2. The test should be moved to a driver-specific test file
3. The abstraction needs improvement

### Core Principle: Consistent Behavior

**The fundamental goal of multi-driver testing is to ensure your application behaves identically across all deployment environments.**

If you find yourself writing:
- `if driver_name == 'aws_lambda': ...`
- Different assertions for different drivers
- Driver-specific conditional logic

Then the abstraction is leaky and needs to be fixed at the driver layer, not in your tests.

**Good Example**: All drivers return 404 for missing resources
```python
def test_missing_resource(self, api):
    api_client, driver_name = api
    response = api_client.get_resource("/does-not-exist")
    api_client.expect_not_found(response)  # Works the same everywhere
```

**Bad Example**: Different behavior requires different assertions
```python
def test_missing_resource(self, api):
    api_client, driver_name = api
    response = api_client.get_resource("/does-not-exist")

    if driver_name == 'aws_lambda':
        assert response.status_code == 404  # AWS-specific check
    else:
        api_client.expect_not_found(response)  # Direct driver check
```

If the bad example reflects reality, fix the drivers to behave consistently!

## Migration Guide

### Before (Old Approach)

```python
class TestOldWay:
    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        driver_name = request.param
        app = RestApplication()
        # ... app setup

        if driver_name == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)
```

### After (New Approach)

```python
class TestNewWay(MultiDriverTestBase):
    def create_app(self) -> RestApplication:
        app = RestApplication()
        # ... app setup (define once)
        return app

    def test_something(self, api):
        api_client, driver_name = api
        # Test automatically runs against all drivers
```

## Benefits

1. **DRY Principle**: Define your app once, test everywhere
2. **Automatic Coverage**: Every test automatically validates all drivers
3. **Consistency**: Ensures the library works identically across environments
4. **Maintainability**: Easier to maintain and understand test structure
5. **Discovery**: Automatically tests new drivers as they're added

## Test Organization

Organize tests by isolating different configuration concerns:

```python
# Good: Each test class has a single, focused app configuration
class TestBasicCrud(MultiDriverTestBase):
    def create_app(self):
        # Basic CRUD operations

class TestAuthentication(MultiDriverTestBase):
    def create_app(self):
        # Authentication scenarios

class TestValidation(MultiDriverTestBase):
    def create_app(self):
        # Input validation scenarios

# Avoid: Multiple unrelated configurations in one app
class TestEverything(MultiDriverTestBase):  # Don't do this
    def create_app(self):
        # Authentication + validation + CRUD + errors
        # This can lead to conflicts between default callbacks
```

## Examples

See these files for complete examples:

- `tests/test_multi_driver_example.py` - Basic usage examples
- `tests/test_http_status_codes_multi_driver.py` - Refactored HTTP status code tests

## Best Practices

1. **One App Per Test Class**: Each test class should have a single, focused `create_app()` method
2. **Isolate Concerns**: Separate different app configurations into different test classes
3. **Use Descriptive Names**: Test class names should clearly indicate what they're testing
4. **Handle Driver Differences**: Use driver-specific decorators when behavior legitimately differs
5. **Test Real Scenarios**: Create apps that represent realistic use cases, not just isolated features

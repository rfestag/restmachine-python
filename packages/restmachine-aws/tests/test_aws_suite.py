"""
Import and run all core RestMachine tests against AWS Lambda driver.

This file imports all test classes from the core package and runs them
against the AWS Lambda driver only.
"""

# Import test classes from core - only those that inherit from MultiDriverTestBase
# These imports are used by pytest for test discovery, so they appear unused
# ruff: noqa: F401

from tests.test_authentication import (
    TestAuthentication,
    TestAuthenticationAndAuthorization
)

from tests.test_conditional_requests import (
    TestETagGeneration,
    TestIfNoneMatchHeaders,
    TestIfMatchHeaders,
    TestLastModifiedHeaders,
    TestCombinedConditionalHeaders,
    TestConditionalRequestsConsistency,
    TestETagAndConditionalRequests
)

from tests.test_content_negotiation import (
    TestContentNegotiationEdgeCases,
    TestResponseRendering
)

from tests.test_custom_error_handlers import (
    TestBasicErrorHandlers,
    TestContentTypeErrorHandlers,
    TestDefaultErrorHandler,
    TestExceptionDependency,
    TestErrorHandlerReturnTypes,
    TestMultipleHandlerPriority
)

from tests.test_dependency_scopes import (
    TestRequestScopeDependencies,
    TestSessionScopeDependencies,
    TestMixedScopeDependencies,
    TestScopeWithDatabaseConnection
)

from tests.test_headers import (
    TestContentLengthHandling,
    TestVaryHeaderHandling,
    TestDefaultHeaders,
    TestBasicDefaultHeaders,
    TestConditionalHeaders,
    TestHeaderReturnValues,
    TestHeaderCallPatterns,
    TestHeaderErrorHandling,
    TestHeadersWithExistingResponseHeaders,
    TestHeadersAcrossDrivers
)

from tests.test_openapi import (
    TestBasicOpenAPIGeneration,
    TestOpenAPIWithPydantic,
    TestOpenAPIFileSaving,
    TestOpenAPIEdgeCases,
    TestEmptyApplication,
    TestOpenAPIMultipleHTTPMethods,
    TestOpenAPIQueryParameters,
    TestOpenAPIValidation
)

from tests.test_request_parsing import (
    TestMultipartFormData,
    TestContentTypeWithCharset,
    TestComplexContentParsers,
    TestParserErrorHandling,
    TestBasicContentHandling
)

from tests.test_status_codes import (
    TestSuccessStatusCodes,
    TestBasicApiOperations,
    TestBadRequestErrors,
    TestResourceExists,
    TestResourceExistsConditional,
    TestMethodNotAllowed,
    TestWrongMethodOnExistingRoute,
    TestMethodAndResourceErrors,
    TestUriTooLong,
    TestServerErrors,
    TestNotImplemented
)

from tests.test_validation import (
    TestPydanticValidation,
    TestAdvancedDependencyPatterns,
    TestComplexValidationScenarios,
    TestDependencyValidationConsistency,
    TestValidationDependencies
)

# Performance benchmarks
from tests.performance.test_state_machine_paths import (
    TestSimpleGetPath,
    TestAuthenticatedGetPath,
    TestConditionalGetPath,
    TestPostCreatePath,
    TestPutUpdatePath,
    TestDeletePath,
    TestErrorPaths,
    TestCRUDCyclePath
)

# Note: We don't import tests from test_router.py, test_http_servers.py, or test_template_rendering.py
# because their test classes don't inherit from MultiDriverTestBase and won't work with the driver framework

# All classes are imported and will be discovered by pytest
# The conftest.py will ensure they run with the AWS Lambda driver only

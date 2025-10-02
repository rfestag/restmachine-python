# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Jinja2 Template Rendering Support**: Rails-like template rendering with Jinja2
  - New `render()` helper function for template rendering
  - Support for file-based templates from `views` directory
  - Support for inline template strings
  - Template inheritance and all Jinja2 features (filters, macros, includes)
  - Configurable template package/directory location
  - XSS protection with autoescape enabled by default
  - Optional `unsafe` parameter for trusted HTML content
  - Comprehensive documentation with examples
- **Example Templates**: Professional starter templates included
  - `views/base.html` - Base layout with template inheritance
  - `views/user_detail.html` - User profile template
  - `views/post_detail.html` - Blog post template
  - `views/list.html` - Generic list rendering template
  - Examples demonstrate inheritance, loops, conditionals, and filters
- **Template Testing**: Comprehensive test coverage for template rendering
  - 33 unit tests covering all rendering scenarios
  - Tests for inline and file-based templates
  - Security tests for XSS prevention
  - Integration tests with RestApplication
  - Template inheritance and Jinja2 feature tests
- **Versioning Documentation**: Complete guides for package versioning and releases
  - `docs/VERSIONING_AND_RELEASES.md` - Comprehensive versioning strategies
  - `docs/MONOREPO_VERSIONING.md` - Python monorepo versioning guide
  - `docs/VERSIONING_QUICK_START.md` - Quick start with ready-to-use examples
  - Coverage of setuptools_scm, semantic-release, and CI/CD automation
  - Tag-based, conventional commits, and manual release strategies
- **Automatic Content-Length Header Injection**: HTTP responses now automatically include Content-Length headers based on body size
  - 204 responses exclude Content-Length header (per HTTP spec)
  - 200 responses with body include correct byte length
  - 200 responses without body set Content-Length to 0
  - Proper UTF-8 encoding support for Unicode content
- **Automatic Vary Header Support**: Responses automatically include Vary headers for proper caching behavior
  - `Vary: Authorization` when request contains Authorization header
  - `Vary: Accept` when endpoint supports multiple content types
  - Combined as `Vary: Authorization, Accept` when both conditions apply
  - Integrated with existing content negotiation system
- **default_headers Decorator**: New decorator for customizing response headers with dependency injection
  - Global headers applied to all routes
  - Route-specific headers for individual endpoints
  - Full dependency injection support (request, body, query_params, etc.)
  - Headers calculated per-request with proper scoping
  - Vary header negotiated first and provided to header functions
  - Error handling ensures failed header functions don't break responses
  - Support for both in-place modification and return-based header updates
- **Adapter System**: New adapter architecture for deploying REST applications to different platforms
  - Abstract `Adapter` base class for implementing platform-specific adapters
  - `AwsApiGatewayAdapter` for AWS Lambda + API Gateway deployment
  - Automatic conversion between platform events and internal Request/Response objects
  - Support for path parameters, query parameters, headers, and request bodies
  - Base64 encoding/decoding support for binary content
  - Robust handling of platform-specific edge cases (null values, missing fields)
  - Comprehensive test coverage and example implementations

### Changed
- **Terminology Change**: Renamed "driver" to "adapter" for platform adapters (BREAKING CHANGE)
  - `Driver` class renamed to `Adapter`
  - `AwsApiGatewayDriver` renamed to `AwsApiGatewayAdapter`
  - `restmachine/drivers.py` renamed to `restmachine/adapters.py`
  - Test framework drivers retain "driver" terminology (they implement a different pattern)
  - Updated all imports, exports, and examples
  - **Migration**: Replace `AwsApiGatewayDriver` with `AwsApiGatewayAdapter` and `from restmachine.drivers` with `from restmachine.adapters`
- **HTMLRenderer**: Updated to use Jinja2 for template rendering
  - Maintains backward compatibility with pre-rendered HTML strings
  - Default templates now use Jinja2 for better structure and escaping
  - Improved HTML generation for dictionaries and lists
  - Integrated with new `render()` helper function
- **Package Configuration**: Migrated from setup.py to modern pyproject.toml (PEP 621)
  - All metadata now in declarative pyproject.toml format
  - Dependencies managed in `[project.dependencies]` and `[project.optional-dependencies]`
  - Removed setup.py (no longer needed with modern pip)
  - Updated to use SPDX license identifier ("MIT")
  - Added migration documentation in `docs/MIGRATION_TO_PYPROJECT.md`
- **Response Class Enhancement**: Enhanced Response model to support pre-calculated headers
  - Added `pre_calculated_headers` parameter for advanced header management
  - Maintains backward compatibility with existing header logic
  - Improved header precedence: pre-calculated → content-type → automatic (Content-Length, Vary)
- **State Machine Integration**: Updated request processing to handle header dependencies
  - Headers dependencies processed before main handler execution
  - Integrated with existing dependency injection and caching system
  - Consistent error handling across all dependency types
- **Enhanced Dependency Resolution**: Improved dependency injection to support individual path parameters
  - Path parameters can now be injected directly by name (e.g., `user_id` from `/users/{user_id}`)
  - Maintains backward compatibility with existing `path_params` dictionary injection
  - Automatic caching and resolution of path parameter values

### Deprecated
- Nothing yet

### Removed
- **setup.py**: Removed in favor of pyproject.toml-only configuration
  - Modern pip (>=21.3) works perfectly with just pyproject.toml
  - No functionality lost, cleaner project structure
  - See `docs/MIGRATION_TO_PYPROJECT.md` for details

### Fixed
- **Type Checking**: Fixed mypy type errors in template_helpers.py
  - Added proper type annotations for Jinja2 loaders
  - Used `Optional[BaseLoader]` for flexible loader types
  - All type checks now pass without errors
- **Security Issues**: Resolved bandit security warnings
  - Replaced broad `except Exception` with specific exceptions
  - Added `# nosec B701` comment for intentional autoescape control
  - Documented security considerations for `unsafe` parameter
  - All security scans now pass

### Security
- **Template XSS Protection**: Jinja2 templates have autoescape enabled by default
  - Prevents XSS attacks in template rendering
  - `unsafe` parameter available for trusted content only
  - Documented security best practices in template documentation
  - Comprehensive security tests validate XSS prevention

## [0.1.0] - 2025-01-21

### Added
- Initial release of REST Framework
- Core application class with route registration
- HTTP method decorators (GET, POST, PUT, DELETE, PATCH)
- Dependency injection system with automatic caching
- Webmachine-inspired state machine for request processing
- Content negotiation with JSON, HTML, and plain text renderers
- Optional Pydantic integration for request/response validation
- State machine callbacks for service availability, authorization, etc.
- Resource existence checking with automatic 404 responses
- Custom content renderers for specific routes
- Comprehensive test suite
- Documentation and examples

### Features
- **Route Handlers**: Simple decorator-based route registration
- **Dependency Injection**: pytest-style dependency injection
- **State Machine States**:
  - B13: Route exists
  - B12: Service available
  - B11: Known method
  - B10: URI too long
  - B9: Method allowed
  - B8: Malformed request
  - B7: Authorized
  - B6: Forbidden
  - B5: Content headers valid
  - G7: Resource exists
  - C3: Content types provided
  - C4: Content types accepted
- **Content Negotiation**: Automatic content type selection
- **Validation**: Automatic Pydantic model validation with 422 error responses
- **Error Handling**: Comprehensive HTTP status code handling

### Dependencies
- Jinja2 (>=3.0.0) - Required for template rendering
- Optional Pydantic dependency for validation features
- Optional server dependencies (uvicorn, hypercorn)

### Supported Python Versions
- Python 3.8+
- Python 3.9
- Python 3.10  
- Python 3.11
- Python 3.12

[Unreleased]: https://github.com/yourusername/restmachine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/restmachine/releases/tag/v0.1.0

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **ASGI Adapter Support**: Built-in ASGI 3.0 adapter for deployment with any ASGI server
  - New `ASGIAdapter` class for creating ASGI applications
  - `create_asgi_app()` convenience function
  - Full ASGI 3.0 protocol support (scope, receive, send)
  - Works with Uvicorn, Hypercorn, Daphne, and other ASGI servers
  - Proper async handling for HTTP request/response lifecycle
  - Header normalization to lowercase (ASGI standard)
  - UTF-8 with latin-1 fallback for body encoding
  - Imported directly from main package: `from restmachine import ASGIAdapter, create_asgi_app`
  - Deploy with: `uvicorn app:asgi_app` or `hypercorn app:asgi_app`
  - Production-ready with Gunicorn workers: `gunicorn app:asgi_app -k uvicorn.workers.UvicornWorker`
- **ASGI Lifespan Protocol Support**: Startup and shutdown event handlers
  - `@app.on_startup` decorator for registering startup handlers
  - `@app.on_shutdown` decorator for registering shutdown handlers
  - Support for both sync and async handlers
  - Multiple handlers can be registered and run in order
  - Automatic integration with ASGI lifespan protocol
  - Perfect for opening/closing database connections, loading models, etc.
  - Startup failures properly reported to ASGI server
  - Shutdown errors logged but don't prevent graceful shutdown
  - **Startup handlers automatically registered as session-scoped dependencies**: Return values from startup handlers can be injected into route handlers and other dependencies
  - **Shutdown handlers support dependency injection**: Shutdown handlers can inject session-scoped dependencies (like database connections from startup handlers) for proper cleanup
  - Startup dependencies are cached across all requests (session scope) for optimal performance
  - Startup handlers execute exactly once during ASGI lifespan startup, with return values immediately cached to prevent re-execution on first request
  - Multiple startup handlers fully supported (e.g., database connection + API client initialization)
- **ASGI TLS Extension Support**: Full support for TLS/SSL connection information
  - `request.tls` boolean indicating whether connection uses TLS (HTTPS)
  - `request.client_cert` dictionary containing client certificate information for mutual TLS (mTLS)
  - ASGI adapter automatically extracts TLS info from `scope["scheme"]` and `scope["extensions"]["tls"]`
  - AWS adapter always sets `tls=True` (API Gateway/ALB use HTTPS) and extracts mTLS client certificates
  - API Gateway: Extracts from `requestContext.identity.clientCert`
  - ALB: Supports both verify mode (parsed headers) and passthrough mode (PEM certificate)
  - Client certificate includes subject, issuer, serial number, and validity information
  - Perfect for implementing certificate-based authentication and authorization
  - Full ASGI 3.0 TLS extension compliance
- **AWS Application Load Balancer (ALB) Support**: Full support for ALB Lambda target groups
  - Automatic detection of ALB vs API Gateway events
  - Support for ALB multi-value headers and query parameters
  - ALB mTLS verify mode: Certificate fields in `x-amzn-mtls-clientcert-subject`, `x-amzn-mtls-clientcert-issuer`, `x-amzn-mtls-clientcert-serial-number` headers
  - ALB mTLS passthrough mode: Full PEM certificate in `x-amzn-mtls-clientcert` header
  - Single adapter (`AwsApiGatewayAdapter`) handles both API Gateway and ALB events
  - Separate internal parsing methods for clean separation of concerns
- **AWS API Gateway HTTP API (v2) Support**: Full support for both v1 (REST API) and v2 (HTTP API) payload formats
  - Single `AwsApiGatewayAdapter` handles both v1 and v2 event formats
  - Automatic version detection based on `version` field in event
  - v1 (REST API): Uses `httpMethod`, `path`, `requestContext.identity.clientCert`
  - v2 (HTTP API): Uses `requestContext.http.method`, `rawPath`, `requestContext.authentication.clientCert`, `cookies` array
  - Cookies from v2 events automatically combined into Cookie header
  - Full feature parity between v1 and v2 (path params, query params, body, mTLS)
  - Lambda Function URLs use v2 format and work seamlessly
- **AWS Lambda Startup Support**: Startup handlers now execute automatically during Lambda cold start
  - `AwsApiGatewayAdapter` automatically calls `app.startup_sync()` during initialization
  - Enables database connections, API clients, and other resources to be initialized once per container
  - Return values cached as session-scoped dependencies and reused across warm invocations
  - Added `startup_sync()` and `shutdown_sync()` methods for synchronous startup/shutdown execution
- **AWS Lambda Shutdown Support**: Ready-to-use Lambda Extension for automatic shutdown handler execution
  - `ShutdownExtension` class for creating Lambda Extensions
  - CLI command: `python -m restmachine_aws create-extension` generates ready-to-deploy extension
  - Extension automatically calls `app.shutdown_sync()` when Lambda container terminates
  - Enables proper cleanup of database connections, API clients, and other resources
  - Environment variable customization: `RESTMACHINE_HANDLER_MODULE`, `RESTMACHINE_APP_NAME`, `RESTMACHINE_LOG_LEVEL`
  - Comprehensive tests and examples included
  - Zero code changes required in handler - extension works automatically
- **Multi-Value Headers**: Full HTTP spec compliance for headers that can appear multiple times
  - New `MultiValueHeaders` class replacing `CaseInsensitiveDict`
  - Support for multiple values per header name (Set-Cookie, Accept, Vary, etc.)
  - `.add(name, value)` method to append header values
  - `.get(name)` returns first value (backward compatible)
  - `.get_all(name)` returns all values for a header
  - `.items_all()` returns all (name, value) pairs including duplicates
  - Case-insensitive header lookups per RFC 7230
  - Dict-like interface for backward compatibility
  - Proper header precedence: `.update()` replaces headers (not appends)
  - Backward compatibility alias: `CaseInsensitiveDict = MultiValueHeaders`
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
- **Dependency Scopes**: Support for request and session-scoped dependencies
  - `scope="request"` (default): Dependencies are evaluated once per request and cleared between requests
  - `scope="session"`: Dependencies are evaluated once and cached across all requests (perfect for database connections, API clients, etc.)
  - All dependency decorators now support scope parameter: `@app.dependency()`, `@app.resource_exists()`, `@app.authorized()`, `@app.validates()`, etc.
  - Separate caching for request and session scopes
  - Request cache automatically cleared between requests, session cache persists
  - Full backward compatibility - existing code uses default request scope
  - Example: `@app.dependency(name="db", scope="session")` for reusable database connections
  - Comprehensive test coverage with 20 new tests covering all scope behaviors

### Changed
- **AWS Adapter Alignment**: Updated AWS Lambda adapter to align with ASGI patterns
  - Headers normalized to lowercase (matching ASGI standard)
  - Consistent query parameter parsing with ASGI adapter
  - Improved error handling with latin-1 fallback
  - Uses `MultiValueHeaders` internally for proper multi-value header support
  - Automatic Content-Type header for JSON responses
  - No breaking changes for existing Lambda functions
- **ASGI Adapter Architecture**: Moved ASGI adapter to core package
  - `ASGIAdapter` moved from `server.py` to `adapters.py`
  - Clear separation: `Adapter` (sync for Lambda/Azure) vs `ASGIAdapter` (async for HTTP servers)
  - Backward compatibility maintained via re-exports in `server.py`
  - Updated main package exports to include `ASGIAdapter` and `create_asgi_app`
  - Comprehensive documentation in `docs/ASGI_REFACTORING.md`
- **Router Architecture**: Unified all routing through a single root router (PERFORMANCE)
  - All routes now go through `RestApplication._root_router` (previously had dual storage with `_routes` list)
  - `@app.get()`, `@app.post()`, etc. now forward to the root router transparently
  - `app.mount()` forwards to `_root_router.mount()`
  - Eliminated duplicate route storage and matching logic (~100 lines removed)
  - No breaking changes - all existing code works unchanged
- **Route Matching**: Implemented trie/tree-based routing for O(k) lookup performance (PERFORMANCE)
  - Replaced O(n) regex matching with O(k) trie lookup (k = number of path segments, typically 2-5)
  - Routes added to trie immediately during initialization (no lazy building, no runtime overhead)
  - Static path segments use dict lookup, dynamic segments (`{id}`) handled separately
  - Prioritizes static matches over parameter matches for correct precedence
  - Dramatic performance improvement for applications with many routes
  - No breaking changes - same route syntax and behavior
- **Dependency System**: Simplified to global-only dependency registration
  - All dependencies are now registered globally and injected based on parameter names
  - Removed brittle "attach to most recent route" pattern
  - Dependencies automatically resolved by inspecting route handler parameters
  - All dependency decorators (`@app.dependency`, `@app.validates`, `@app.accepts`, etc.) register globally
  - Route-specific dependency dictionaries kept for backward compatibility but unused
  - Cleaner mental model: define dependencies once, use anywhere
  - No breaking changes - existing code continues to work
- **Built-in Dependency Registration**: Refactored built-in dependencies to use the same registration mechanism as user-defined dependencies
  - Built-in dependencies (`request`, `body`, `exception`, `request_id`, `trace_id`, etc.) now registered during application initialization
  - Removed separate code paths for built-in vs. custom dependencies (~70 lines of special-case logic eliminated)
  - Simplified dependency resolution with unified handling for all dependency types
  - Makes it trivial to add new built-in dependencies (just add one line to `_register_builtin_dependencies()`)
  - No breaking changes - all existing functionality preserved
  - Improved type safety with explicit type annotations
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
- **restmachine-uvicorn and restmachine-hypercorn packages**: Removed separate server packages
  - No longer necessary with built-in ASGI adapter
  - Users should use `ASGIAdapter` directly with their preferred ASGI server
  - Simpler architecture: one core package with ASGI support built-in
  - To migrate: Replace `restmachine-uvicorn` with `restmachine` and use `ASGIAdapter(app)`
  - Deploy directly: `uvicorn app:asgi_app` or `hypercorn app:asgi_app`
  - No functionality lost - all ASGI servers still supported via the adapter
- **setup.py**: Removed in favor of pyproject.toml-only configuration
  - Modern pip (>=21.3) works perfectly with just pyproject.toml
  - No functionality lost, cleaner project structure
  - See `docs/MIGRATION_TO_PYPROJECT.md` for details

### Fixed
- **Multi-Value Headers**: Fixed HTTP spec violation where duplicate headers only kept last value
  - Previous dict-based implementation only retained last value for duplicate header names
  - Now properly supports headers that can appear multiple times per RFC 7230
  - Critical for Set-Cookie, Accept, Vary, and other multi-value headers
  - `.update()` now properly replaces headers instead of accumulating them
  - Fixed header precedence issues when merging default headers with response headers
  - All 535 tests passing with full backward compatibility
- **Type Checking**: Enhanced type safety with stricter mypy checks
  - Added `--check-untyped-defs` flag to catch more type errors
  - Fixed type annotations in error_models.py for dict construction
  - Added runtime validation for route_handler state
  - All type checks now pass with stricter validation
- **Type Checking**: Fixed mypy type errors in template_helpers.py
  - Added proper type annotations for Jinja2 loaders
  - Used `Optional[BaseLoader]` for flexible loader types
  - All type checks now pass without errors
- **Security Issues**: Resolved bandit security warnings
  - Replaced `assert` with proper `if/raise` checks (prevents removal with Python -O flag)
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
- anyio (>=3.0.0) - Required for async/sync bridge in startup/shutdown handlers
- Optional Pydantic dependency for validation features

### Supported Python Versions
- Python 3.8+
- Python 3.9
- Python 3.10  
- Python 3.11
- Python 3.12

[Unreleased]: https://github.com/yourusername/restmachine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/restmachine/releases/tag/v0.1.0

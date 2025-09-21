# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Changed
- **Response Class Enhancement**: Enhanced Response model to support pre-calculated headers
  - Added `pre_calculated_headers` parameter for advanced header management
  - Maintains backward compatibility with existing header logic
  - Improved header precedence: pre-calculated → content-type → automatic (Content-Length, Vary)
- **State Machine Integration**: Updated request processing to handle header dependencies
  - Headers dependencies processed before main handler execution
  - Integrated with existing dependency injection and caching system
  - Consistent error handling across all dependency types

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

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
- No required dependencies for core functionality
- Optional Pydantic dependency for validation features

### Supported Python Versions
- Python 3.8+
- Python 3.9
- Python 3.10  
- Python 3.11
- Python 3.12

[Unreleased]: https://github.com/yourusername/restmachine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/restmachine/releases/tag/v0.1.0

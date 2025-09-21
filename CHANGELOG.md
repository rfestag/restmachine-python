# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

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

[Unreleased]: https://github.com/yourusername/rest-framework/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/rest-framework/releases/tag/v0.1.0

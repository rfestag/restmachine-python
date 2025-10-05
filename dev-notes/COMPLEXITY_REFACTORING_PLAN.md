# Complexity Refactoring Plan

This document outlines a strategic plan to refactor high-complexity code identified by Radon analysis.

## Current High-Complexity Code

| Function | Rating | CC Score | Location | Priority |
|----------|--------|----------|----------|----------|
| `RequestStateMachine.state_execute_and_render` | F | 49 | state_machine.py:851 | HIGH |
| `RequestStateMachine.process_request` | E | 35 | state_machine.py:171 | MEDIUM |
| `RequestStateMachine._create_error_response` | D | 24 | state_machine.py:42 | LOW |
| `AwsApiGatewayAdapter._parse_alb_event` | D | 23 | adapter.py:270 | MEDIUM |
| `AwsApiGatewayAdapter._parse_apigw_v2_event` | D | 21 | adapter.py:188 | MEDIUM |

## Refactoring Strategy

### Phase 1: AWS Adapter Parsing Methods (Quick Wins)
**Timeline:** 1-2 days
**Risk:** Low (isolated changes, excellent test coverage)
**Impact:** Reduces 3 D-rated methods to B or better

#### 1.1 Extract Common Parsing Logic

**Problem:** `_parse_apigw_v1_event`, `_parse_apigw_v2_event`, and `_parse_alb_event` all have similar parsing logic with slight variations.

**Solution:** Extract common helpers:

```python
# New helper methods to extract:
def _extract_headers(self, event: Dict) -> MultiValueHeaders:
    """Extract headers from any event format."""
    # Common logic for v1, v2, and ALB

def _extract_query_params(self, event: Dict) -> Dict[str, str]:
    """Extract query parameters from any event format."""

def _extract_path_params(self, event: Dict) -> Optional[Dict[str, str]]:
    """Extract path parameters from any event format."""

def _decode_body(self, event: Dict) -> Optional[str]:
    """Decode body with base64 support."""

def _extract_client_cert_from_context(
    self,
    request_context: Dict,
    cert_path: List[str]
) -> Optional[Dict[str, Any]]:
    """Extract client certificate from request context.

    Args:
        request_context: The requestContext dict
        cert_path: Path to certificate (e.g., ["identity", "clientCert"])
    """
```

**Benefits:**
- Reduces duplication
- Each parsing method drops from D/C (19-23) to B (6-8)
- Easier to maintain and test

**Estimated Complexity Reduction:**
- `_parse_alb_event`: D (23) → B (8)
- `_parse_apigw_v2_event`: D (21) → B (7)
- `_parse_apigw_v1_event`: C (19) → B (6)

---

### Phase 2: State Machine - Process Request (Medium Effort)
**Timeline:** 2-3 days
**Risk:** Medium (core request flow, needs careful testing)
**Impact:** Reduces E-rated method to B

#### 2.1 Extract State Execution Pattern

**Problem:** `process_request` has repetitive pattern for each state transition (35 complexity).

**Current Pattern (Repetitive):**
```python
result = self.state_route_exists()
log_state_transition("route_exists", result)
if not result.continue_processing:
    return result.response or default_response

result = self.state_service_available()
log_state_transition("service_available", result)
if not result.continue_processing:
    return result.response or default_response
# ... repeated 15+ times
```

**Solution:** Create state execution helper:

```python
def _execute_state(
    self,
    state_method: Callable,
    state_name: str,
    default_response: Response
) -> Optional[Response]:
    """Execute a state and return response if processing should stop.

    Returns:
        Response if processing should stop, None to continue
    """
    result = state_method()

    status = "CONTINUE" if result.continue_processing else "STOP"
    response_code = result.response.status_code if result.response else "None"
    logger.debug(f"State {state_name}: {status} (response: {response_code})")

    if not result.continue_processing:
        return result.response or default_response

    return None

def process_request(self, request: Request) -> Response:
    """Process a request through the state machine."""
    self.request = request
    self.app._dependency_cache.clear()

    logger.debug(f"Starting state machine processing for {request.method.value} {request.path}")

    default_response = Response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        json.dumps({"error": "Unexpected error occurred."}),
        content_type="application/json",
    )

    # Define state machine flow
    states = [
        (self.state_route_exists, "route_exists"),
        (self.state_service_available, "service_available"),
        (self.state_known_method, "known_method"),
        (self.state_uri_too_long, "uri_too_long"),
        (self.state_method_allowed, "method_allowed"),
        (self.state_malformed_request, "malformed_request"),
        (self.state_authorized, "authorized"),
        (self.state_forbidden, "forbidden"),
        (self.state_content_headers_valid, "content_headers_valid"),
        (self.state_resource_exists, "resource_exists"),
        (self.state_if_match, "if_match"),
        (self.state_if_unmodified_since, "if_unmodified_since"),
        (self.state_if_none_match, "if_none_match"),
        (self.state_if_modified_since, "if_modified_since"),
        (self.state_content_types_provided, "content_types_provided"),
        (self.state_content_types_accepted, "content_types_accepted"),
    ]

    try:
        # Execute states in sequence
        for state_method, state_name in states:
            response = self._execute_state(state_method, state_name, default_response)
            if response:
                return response

        # If all states passed, execute and render
        return self.state_execute_and_render()

    except ValidationError as e:
        # ... error handling
```

**Benefits:**
- Removes repetitive code
- Clearer state machine flow
- Easier to add/remove states
- Complexity drops from E (35) to B (8-10)

**Estimated Complexity Reduction:**
- `process_request`: E (35) → B (8-10)

---

### Phase 3: State Machine - Execute and Render (High Effort)
**Timeline:** 3-5 days
**Risk:** High (critical path, complex validation logic)
**Impact:** Reduces F-rated method to C or better

#### 3.1 Extract Validation Logic

**Problem:** `state_execute_and_render` handles too many concerns (49 complexity):
1. Header processing
2. Handler execution
3. Return type validation
4. Pydantic model handling (multiple types)
5. Route-specific rendering
6. Global rendering
7. Response object handling
8. Error handling

**Solution:** Break into smaller, focused methods:

```python
# 1. Extract return type validation
def _validate_and_process_return_value(
    self,
    result: Any,
    return_annotation: Any
) -> Any:
    """Validate and process handler return value based on type annotation.

    Returns:
        Processed result (converted Pydantic models to dicts, etc.)
    """
    # Handle None annotation
    if return_annotation is None or return_annotation is type(None):
        return None

    # Handle Union types
    if self._is_union_type(return_annotation):
        return result

    # Handle list[PydanticModel]
    if self._is_pydantic_list(return_annotation):
        return self._validate_pydantic_list(result, return_annotation)

    # Handle PydanticModel
    if self._is_pydantic_model(return_annotation):
        return self._validate_pydantic_model(result, return_annotation)

    return result

# 2. Extract rendering logic
def _render_result(
    self,
    result: Any,
    processed_headers: MultiValueHeaders
) -> Response:
    """Render the handler result using appropriate renderer.

    Handles:
    - Route-specific renderers
    - Global renderers
    - Response objects
    - Fallback to plain text
    """
    # Check for route-specific renderer
    if self._has_route_specific_renderer():
        return self._render_with_route_renderer(result, processed_headers)

    # Handle Response objects
    if isinstance(result, Response):
        return self._update_response_with_headers(result, processed_headers)

    # Use global renderer
    return self._render_with_global_renderer(result, processed_headers)

# 3. Extract ETag/Last-Modified header logic
def _add_resource_metadata_headers(
    self,
    headers: MultiValueHeaders
) -> None:
    """Add ETag and Last-Modified headers if available."""
    current_etag = self._get_resource_etag()
    if current_etag:
        headers["ETag"] = current_etag

    current_last_modified = self._get_resource_last_modified()
    if current_last_modified:
        headers["Last-Modified"] = current_last_modified.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

# 4. Simplified main method
def state_execute_and_render(self) -> Response:
    """Execute the route handler and render the response."""
    if self.route_handler is None:
        raise RuntimeError("route_handler must be set before executing handler")

    processed_headers = None
    try:
        # Process headers dependencies
        processed_headers = self._process_headers_dependencies()

        # Execute handler
        main_result = self.app._call_with_injection(
            self.route_handler.handler, self.request, self.route_handler
        )

        # Handle None result
        if main_result is None:
            return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)

        # Add resource metadata headers
        self._add_resource_metadata_headers(processed_headers)

        # Validate return value if needed
        return_annotation = self.route_handler.handler_signature.return_annotation
        validated_result = self._validate_and_process_return_value(
            main_result, return_annotation
        )

        # Handle validated None
        if validated_result is None:
            return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)

        # Render result
        return self._render_result(validated_result, processed_headers)

    except ValidationError as e:
        return self._handle_validation_error(e, processed_headers)
    except AcceptsParsingError as e:
        return self._handle_accepts_parsing_error(e, processed_headers)
    except Exception as e:
        return self._handle_general_error(e, processed_headers)
```

**Benefits:**
- Each extracted method has B or better complexity
- Main method becomes readable and maintainable
- Easier to test individual concerns
- Better separation of concerns

**Estimated Complexity Reduction:**
- `state_execute_and_render`: F (49) → C (11-15)
- New helper methods: B (6-9) each

---

### Phase 4: Error Response Creation (Low Priority)
**Timeline:** 1 day
**Risk:** Low (well-tested error handling)
**Impact:** Reduces D-rated method to B

#### 4.1 Extract Custom Handler Logic

**Problem:** `_create_error_response` has complex custom handler selection logic.

**Solution:** Extract custom handler resolution:

```python
def _find_custom_error_handler(
    self,
    status_code: HTTPStatus,
    content_type: Optional[str] = None
) -> Optional[Callable]:
    """Find the appropriate custom error handler.

    Priority:
    1. Status + content-type specific
    2. Status-specific
    3. Default handler
    """
    if not self.app._error_handlers:
        return None

    # Try status + content-type
    if content_type:
        handler_key = (status_code, content_type)
        if handler_key in self.app._error_handlers:
            return self.app._error_handlers[handler_key]

    # Try status-only
    handler_key = (status_code, None)
    if handler_key in self.app._error_handlers:
        return self.app._error_handlers[handler_key]

    # Try default
    default_key = (None, None)
    if default_key in self.app._error_handlers:
        return self.app._error_handlers[default_key]

    return None

def _create_error_response(
    self,
    status_code: HTTPStatus,
    message: str,
    details: Optional[Any] = None
) -> Response:
    """Create an error response, using custom handlers if available."""
    # Find custom handler
    custom_handler = self._find_custom_error_handler(
        status_code,
        self.chosen_renderer.media_type if self.chosen_renderer else None
    )

    if custom_handler:
        return self._execute_custom_error_handler(custom_handler, status_code, message, details)

    # Default error response
    return self._create_default_error_response(status_code, message, details)
```

**Estimated Complexity Reduction:**
- `_create_error_response`: D (24) → B (8)

---

## Implementation Plan

### Step 1: AWS Adapter Refactoring (Week 1)
1. Create helper methods for common parsing logic
2. Refactor `_parse_apigw_v1_event`
3. Refactor `_parse_apigw_v2_event`
4. Refactor `_parse_alb_event`
5. Run full test suite
6. Verify complexity improvements with `tox -e complexity`

**Success Criteria:**
- All 248 AWS tests passing
- All parsing methods at B rating or better
- No functional changes (behavior identical)

### Step 2: State Machine Process Request (Week 2)
1. Create `_execute_state` helper method
2. Refactor `process_request` to use state list
3. Run full test suite (592 tests)
4. Verify complexity improvements

**Success Criteria:**
- All 592 tests passing
- `process_request` at B rating (≤10)
- State machine behavior unchanged

### Step 3: State Machine Execute and Render (Week 3-4)
1. Extract Pydantic validation helpers
2. Extract rendering logic
3. Extract header metadata logic
4. Simplify main method
5. Comprehensive testing
6. Performance benchmarking (critical path)

**Success Criteria:**
- All 592 tests passing
- `state_execute_and_render` at C rating or better (≤20)
- Performance unchanged or improved
- No regressions in validation behavior

### Step 4: Error Response Creation (Week 5)
1. Extract custom handler resolution
2. Simplify error response creation
3. Test all error scenarios

**Success Criteria:**
- All tests passing
- `_create_error_response` at B rating (≤10)

---

## Risk Mitigation

### Testing Strategy
1. **Run tests after each extraction**: Don't refactor everything at once
2. **Performance benchmarks**: Run before/after for critical paths
3. **Code coverage**: Ensure all branches are tested
4. **Integration tests**: Verify end-to-end behavior

### Rollback Strategy
1. **Git branches**: Each phase in separate branch
2. **Incremental commits**: Small, atomic changes
3. **Easy revert**: Can rollback individual phases

### Performance Monitoring
```bash
# Before refactoring
tox -e benchmark

# After refactoring
tox -e benchmark-compare
```

Should maintain or improve performance (state machine is hot path).

---

## Expected Outcomes

### Complexity Improvements
| Function | Before | After | Improvement |
|----------|--------|-------|-------------|
| `state_execute_and_render` | F (49) | C (15) | ⬇️ 34 points |
| `process_request` | E (35) | B (9) | ⬇️ 26 points |
| `_create_error_response` | D (24) | B (8) | ⬇️ 16 points |
| `_parse_alb_event` | D (23) | B (8) | ⬇️ 15 points |
| `_parse_apigw_v2_event` | D (21) | B (7) | ⬇️ 14 points |

### Maintainability Improvements
- **Testability**: Smaller methods are easier to unit test
- **Readability**: Clear separation of concerns
- **Extensibility**: Easier to add new features
- **Debugging**: Smaller methods are easier to debug

### Project Health
- **Average Complexity**: A (3.59) → A (2.8-3.0)
- **Maintainability Index**: Improved for affected files
- **Technical Debt**: Significantly reduced

---

## Alternative Approaches (Not Recommended)

### 1. Complete State Machine Rewrite
**Why Not:** High risk, large scope, would require extensive retesting. Current state machine works well, just needs refactoring.

### 2. Ignore High Complexity
**Why Not:** Technical debt accumulates. These methods are already difficult to maintain and will become worse over time.

### 3. Suppress Radon Warnings
**Why Not:** Defeats the purpose of code quality checks. Better to address root causes.

---

## Conclusion

This refactoring plan provides a **pragmatic, low-risk approach** to addressing high-complexity code:

✅ **Incremental**: Small, testable changes
✅ **Prioritized**: Quick wins first (AWS adapters)
✅ **Well-tested**: Comprehensive test coverage
✅ **Reversible**: Easy to rollback if needed
✅ **Measurable**: Clear success criteria

**Estimated Total Effort:** 3-5 weeks
**Expected Complexity Reduction:** 105 points across 5 methods
**Risk Level:** Low to Medium (manageable with proper testing)

The refactoring will significantly improve code maintainability while preserving all existing functionality and performance.

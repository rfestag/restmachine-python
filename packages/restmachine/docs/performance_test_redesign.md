# Performance Test Redesign

## Current Problems

The existing 28 performance tests have significant redundancy:

### Redundant Tests
- **JSON size variations** (small/medium/large): Measure JSON serialization, not state machine performance
- **Parameter count variations** (1/2/3 path params): All follow same routing path
- **Similar endpoint patterns**: GET/POST variations that exercise identical state paths

### Missing Coverage
- **Auth paths**: No tests for authorized/forbidden states
- **Conditional requests**: No tests for If-Match, If-None-Match, ETags
- **Error paths**: No dedicated benchmarks for 404, 405, 401, etc.
- **Content negotiation**: No tests for Accept header processing

## State Machine Paths (From Design)

Based on our state machine analysis, here are the key paths to benchmark:

| Path Type | States Traversed | Typical Status | Use Case |
|-----------|-----------------|----------------|----------|
| **Simple GET** | 7 | 200 | Public resource, no auth, no conditional |
| **GET + Auth** | 9 | 200 | Protected resource, no conditional |
| **GET + Conditional** | 12 | 200/304 | Resource with ETag/Last-Modified |
| **GET + Auth + Conditional** | 14 | 200/304 | Protected resource with conditional |
| **POST Create** | 8 | 201 | Create new resource |
| **POST + Auth** | 10 | 201 | Protected creation |
| **PUT Update** | 9 | 200 | Update existing resource |
| **DELETE** | 8 | 204 | Delete resource |
| **404 Route Not Found** | 1 | 404 | Invalid path |
| **405 Method Not Allowed** | 1 | 405 | Valid path, wrong method |
| **401 Unauthorized** | 9 | 401 | Missing/invalid auth |
| **403 Forbidden** | 10 | 403 | Valid auth, insufficient permissions |

## Proposed Test Structure

### Primary Tests (State Machine Paths)

```python
# test_state_machine_paths.py

class TestSimpleGetPath(MultiDriverTestBase):
    """Benchmark: Simple GET (7 states) - Fastest path"""

    def test_simple_get_request(self, api, benchmark):
        # No auth, no conditional, just return data
        pass

class TestAuthenticatedGetPath(MultiDriverTestBase):
    """Benchmark: GET + Auth (9 states)"""

    def test_authenticated_get_request(self, api, benchmark):
        # Add Authorization header, check authorized state
        pass

class TestConditionalGetPath(MultiDriverTestBase):
    """Benchmark: GET + Conditional (12 states)"""

    def test_conditional_get_etag_match(self, api, benchmark):
        # If-None-Match with matching ETag -> 304
        pass

    def test_conditional_get_etag_mismatch(self, api, benchmark):
        # If-None-Match with different ETag -> 200 with data
        pass

class TestFullGetPath(MultiDriverTestBase):
    """Benchmark: GET + Auth + Conditional (14 states) - Longest path"""

    def test_full_get_path(self, api, benchmark):
        # Auth + Conditional - exercises all states
        pass

class TestPostCreatePath(MultiDriverTestBase):
    """Benchmark: POST Create (8 states)"""

    def test_post_create_request(self, api, benchmark):
        # Create resource via POST
        pass

class TestErrorPaths(MultiDriverTestBase):
    """Benchmark: Error paths (1-10 states)"""

    def test_404_not_found(self, api, benchmark):
        # Route not found - 1 state
        pass

    def test_405_method_not_allowed(self, api, benchmark):
        # Wrong method - 1 state
        pass

    def test_401_unauthorized(self, api, benchmark):
        # No auth when required - 9 states
        pass

    def test_403_forbidden(self, api, benchmark):
        # Invalid permissions - 10 states
        pass
```

### Secondary Tests (Edge Cases & Optimizations)

```python
# test_optimization_scenarios.py

class TestRouteOptimizations(MultiDriverTestBase):
    """Test scenarios where state skipping helps"""

    def test_route_without_conditionals(self, api, benchmark):
        # Route with no ETag support - should skip conditional states
        pass

    def test_route_without_auth(self, api, benchmark):
        # Public route - should skip auth states
        pass

class TestContentNegotiation(MultiDriverTestBase):
    """Test content negotiation impact"""

    def test_single_content_type(self, api, benchmark):
        # Only JSON available - fast path
        pass

    def test_multiple_content_types(self, api, benchmark):
        # JSON, HTML, XML - negotiation overhead
        pass
```

### Payload Size Tests (Separate from State Machine)

```python
# test_payload_performance.py

class TestPayloadSizes(MultiDriverTestBase):
    """Benchmark serialization/deserialization (not state machine)"""

    @pytest.mark.parametrize("size", ["small", "medium", "large"])
    def test_json_serialization(self, api, benchmark, size):
        # Measure JSON handling separately
        pass
```

## Comparative Benchmarking Setup

### Fixture for Old vs New State Machine

```python
# conftest.py additions

@pytest.fixture(params=["old", "new"])
def state_machine_impl(request):
    """Run each test with both old and new state machine."""
    impl = request.param

    # Set environment variable to control which implementation
    os.environ["USE_NEW_STATE_MACHINE"] = "true" if impl == "new" else "false"

    yield impl

    # Cleanup
    del os.environ["USE_NEW_STATE_MACHINE"]

# Usage in tests:
def test_simple_get_request(self, api, benchmark, state_machine_impl):
    result = benchmark(api_client.get_resource, "/simple")
    # Results will be tagged with "old" or "new" implementation
```

### Benchmark Comparison Report

```python
# scripts/compare_benchmarks.py

def compare_implementations():
    """Compare old vs new state machine performance."""

    # Run benchmarks for old implementation
    pytest.main([
        "tests/performance",
        "-m", "performance",
        "--benchmark-only",
        "--benchmark-json=benchmarks_old.json"
    ])

    # Run benchmarks for new implementation
    os.environ["USE_NEW_STATE_MACHINE"] = "true"
    pytest.main([
        "tests/performance",
        "-m", "performance",
        "--benchmark-only",
        "--benchmark-json=benchmarks_new.json"
    ])

    # Compare and generate report
    compare_json_files("benchmarks_old.json", "benchmarks_new.json")
```

## Test File Organization

```
tests/performance/
├── __init__.py
├── conftest.py                    # Fixtures for comparative testing
├── test_state_machine_paths.py   # PRIMARY: State machine path benchmarks
├── test_optimization_scenarios.py # State skipping optimizations
├── test_error_paths.py           # Error handling performance
├── test_payload_performance.py   # JSON serialization (separate concern)
└── test_comparative.py           # Old vs new comparison tests
```

## Metrics to Track

### Per-Path Metrics
- **State count**: How many states traversed
- **Time per state**: Average time in each state
- **Total time**: End-to-end request time
- **Memory**: Peak memory usage

### Comparison Metrics
- **Speedup**: New vs old implementation
- **State reduction**: How many states skipped
- **Consistency**: Ensure same results

## Expected Results

Based on state counts:

| Path | Old States | New States | Expected Improvement |
|------|-----------|------------|---------------------|
| Simple GET | 15 | 7 | **~50% faster** |
| GET + Auth | 15 | 9 | **~40% faster** |
| GET + Conditional | 15 | 12 | **~20% faster** |
| POST Create | 15 | 8 | **~45% faster** |
| Error (404) | 1 | 1 | Same |

## Migration Strategy

1. **Keep existing tests** initially for regression checking
2. **Add new path-based tests** alongside
3. **Run both** during development
4. **Compare results** to validate correctness
5. **Remove redundant tests** after validation
6. **Keep only path-based tests** for ongoing benchmarking

## Sample Test Implementation

```python
class TestSimpleGetPath(MultiDriverTestBase):
    """Benchmark the simplest GET path (7 states)."""

    def create_app(self) -> RestApplication:
        app = RestApplication()

        # Simple endpoint - no auth, no conditional support
        @app.get("/simple")
        def get_simple():
            return {"message": "Hello", "value": 42}

        return app

    def test_simple_get_request(self, api, benchmark, state_machine_impl):
        """Benchmark simple GET request."""
        api_client, driver_name = api

        result = benchmark(api_client.get_resource, "/simple")

        data = api_client.expect_successful_retrieval(result)
        assert data["message"] == "Hello"
        assert data["value"] == 42

        # Log which implementation was used
        print(f"  Implementation: {state_machine_impl}")


class TestAuthenticatedGetPath(MultiDriverTestBase):
    """Benchmark GET with authentication (9 states)."""

    def create_app(self) -> RestApplication:
        app = RestApplication()

        # Add authentication dependency
        @app.dependency
        def current_user(request_headers):
            auth = request_headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return None
            return {"id": 1, "name": "User"}

        @app.authorized
        def check_auth(current_user):
            return current_user is not None

        # Protected endpoint
        @app.get("/protected")
        def get_protected(current_user):
            return {"user": current_user["name"], "data": "secret"}

        return app

    def test_authenticated_get_request(self, api, benchmark, state_machine_impl):
        """Benchmark GET with valid authentication."""
        api_client, driver_name = api

        def make_request():
            request = api_client.get("/protected").accepts("application/json")
            request.headers["Authorization"] = "Bearer valid-token"
            return api_client.execute(request)

        result = benchmark(make_request)

        data = api_client.expect_successful_retrieval(result)
        assert data["user"] == "User"
        assert data["data"] == "secret"
```

## Validation Approach

1. **Correctness Check**: Both implementations must return identical responses
2. **State Count Verification**: Log actual states traversed
3. **Performance Comparison**: New must be faster for optimized paths
4. **Regression Protection**: Run old tests to ensure no behavior changes

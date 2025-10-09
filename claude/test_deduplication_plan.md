# Test Suite Deduplication Plan

## Current Status
- **Unique test methods**: 206
- **Total test runs**: 944 (1027 with non-multi-driver tests)
- **Duplication factor**: 4.6x
- **Current runtime**: 30 seconds

## Problem Analysis

### 1. Duplicate Test Classes Between Files
**test_content_parsers_multi_driver.py** and **test_advanced_content_types_multi_driver.py** have 5 duplicate test classes:
- `TestMultipartFormData` (3 tests × 6 drivers = 18 runs each = **36 duplicate runs**)
- `TestContentTypeWithCharset` (4 tests × 6 drivers = 24 runs each = **48 duplicate runs**)
- `TestComplexContentParsers` (5 tests × 6 drivers = 30 runs each = **60 duplicate runs**)
- `TestParserErrorHandling` (4 tests × 6 drivers = 24 runs each = **48 duplicate runs**)
- `TestContentNegotiationEdgeCases` (6 tests × 6 drivers = 36 runs each = **72 duplicate runs**)

**Total**: 264 duplicate test runs (28% of all tests!)

### 2. Excessive Driver Coverage
Most tests run on all 6 drivers when they only need 3:
- **direct**: Core functionality, fastest, most features
- **aws_lambda**: Different event model (API Gateway)
- **uvicorn-http1** or **hypercorn-http1**: Real HTTP server behavior

Tests currently run on:
- `direct`, `aws_lambda` ✓ (needed)
- `uvicorn-http1`, `hypercorn-http1` (redundant - same HTTP/1.1 behavior)
- `uvicorn-http2`, `hypercorn-http2` (only needed for HTTP/2-specific tests)

### 3. Unnecessary HTTP Protocol Duplication
- 140 tests run on BOTH HTTP/1 and HTTP/2
- Most features work identically on both protocols
- Only a handful of tests need HTTP/2 (headers, multiplexing, etc.)

## Deduplication Strategy

### Phase 1: Remove Duplicate Test Classes (Immediate)
**Action**: Delete duplicate classes from `test_advanced_content_types_multi_driver.py`

**Classes to remove**:
- TestMultipartFormData
- TestContentTypeWithCharset
- TestComplexContentParsers
- TestParserErrorHandling
- TestContentNegotiationEdgeCases

**Impact**:
- Removes 264 duplicate test runs
- From 944 → 680 tests (28% reduction)
- Runtime: ~30s → ~22s

### Phase 2: Update Default Driver Set (Recommended)
**Action**: Change default in `MultiDriverTestBase.ENABLED_DRIVERS`

```python
ENABLED_DRIVERS = [
    'direct',           # Core functionality (fastest)
    'aws_lambda',       # Different event model
    'uvicorn-http1',    # Real HTTP server
]
```

**Impact**:
- From 680 → ~340 tests (50% reduction from current 680)
- Runtime: ~22s → ~12s
- Still tests 3 different execution models

### Phase 3: Targeted HTTP/2 Testing (Optional)
**Action**: Create a dedicated HTTP/2 test file for HTTP/2-specific features only

Keep HTTP/2 testing for:
- HTTP/2-specific header features
- Server push (if implemented)
- Request multiplexing validation

Most tests don't need HTTP/2 validation.

## Recommended Implementation

### Step 1: Merge duplicate files
```bash
# Keep test_content_parsers_multi_driver.py
# Delete the 5 duplicate classes from test_advanced_content_types_multi_driver.py
```

### Step 2: Update base class default
```python
# tests/framework/multi_driver_base.py
class MultiDriverTestBase(ABC):
    ENABLED_DRIVERS = [
        'direct',           # Direct driver: calls RestMachine directly
        'aws_lambda',       # AWS Lambda driver: simulates AWS API Gateway events
        'uvicorn-http1',    # HTTP/1.1 driver via Uvicorn server
    ]
```

### Step 3: Update specialized test files
Files that should keep broader driver coverage:
- `test_http_servers.py` - Already tests HTTP servers specifically
- Any HTTP/2-specific tests - Use `ENABLED_DRIVERS = ['hypercorn-http2']`

### Step 4: AWS-specific tests (already correct)
These files correctly limit drivers:
- `test_aws_driver_multi_driver.py` - Uses aws_lambda and aws_lambda_debug ✓
- `test_openapi_multi_driver.py` - Uses direct only ✓
- `test_detailed_conditional_requests_multi_driver.py` - Uses direct + aws_lambda ✓

## Expected Results

### After Phase 1 (Remove Duplicates):
- Tests: 944 → 680 (-28%)
- Runtime: ~30s → ~22s

### After Phase 2 (Update Drivers):
- Tests: 680 → 340 (-50% from Phase 1, -64% total)
- Runtime: ~22s → ~12s

### Final State:
- **340 total tests** (from 944)
- **~12 second runtime** (from 30s)
- **Same coverage** across execution models:
  - Direct invocation ✓
  - AWS Lambda/API Gateway ✓
  - Real HTTP server ✓

## Rationale

### Why 3 drivers is sufficient:

1. **direct**: Tests core framework logic without server overhead
2. **aws_lambda**: Tests AWS API Gateway event model (different headers, base64, etc.)
3. **uvicorn-http1**: Tests real HTTP server behavior (headers, content-type, etc.)

### What we're NOT losing:

- All unique test logic is preserved
- All execution models are covered
- HTTP/1.1 behavior is fully tested
- AWS Lambda behavior is fully tested

### What we're eliminating:

- Redundant HTTP/1 testing (uvicorn vs hypercorn - same protocol)
- Redundant HTTP/2 testing (most tests don't need it)
- Duplicate test classes in multiple files

## Implementation Priority

1. **HIGH**: Remove duplicate test classes (Phase 1)
   - Easy win, no behavior change
   - 28% reduction immediately

2. **MEDIUM**: Update default drivers (Phase 2)
   - Requires validation that behavior is truly identical
   - 50% additional reduction

3. **LOW**: HTTP/2-specific testing (Phase 3)
   - Only if HTTP/2-specific features are added
   - Currently no HTTP/2-specific tests needed

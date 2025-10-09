# Test Suite Analysis - Key Findings

## Phase 1: Deduplication (COMPLETED ✅)
- **Removed**: 132 duplicate tests (12.8% reduction)
- **Result**: 1027 → 895 tests
- **Runtime**: 30s → 27s
- **Status**: All 879 tests passing

## Skipped Tests Investigation (CRITICAL FINDING 🚨)

### Summary
- **Total skipped**: 16 tests
- **Critical bug found**: 8 tests (case-sensitive headers)
- **Expected behavior**: 4 tests (Content-Length on 204)
- **Demo tests**: 4 tests (intentional)

### CRITICAL: Case-Sensitive Header Bug 🐛

#### The Problem
**RestMachine's `request.headers.get()` uses case-sensitive lookups**, breaking on real HTTP servers:

```python
# Application code:
auth_header = request.headers.get("Authorization", "")  # ❌ Returns empty string

# HTTP server headers (lowercase):
{'authorization': 'Bearer token', ...}  # Not found!

# Direct driver headers (preserves case):
{'Authorization': 'Bearer token', ...}  # Found!
```

#### Evidence
**Test**: `test_protected_endpoint_accessible_with_auth`

| Driver | Headers Received | Lookup Result | Status |
|--------|-----------------|---------------|--------|
| Direct | `{'Authorization': 'Bearer valid_token'}` | Found ✅ | 200 OK |
| HTTP (uvicorn) | `{'authorization': 'Bearer valid_token'}` | NOT FOUND ❌ | 401 Unauthorized |

#### Impact
- **8 auth tests fail** on HTTP drivers (currently skipped)
- **Any RestMachine app** using standard headers will break on real servers
- Affects: `Authorization`, `Content-Type`, `User-Agent`, etc.

#### Root Cause
HTTP headers are case-insensitive per RFC 7230, but:
1. Direct driver preserves casing from test code
2. HTTP servers (uvicorn/hypercorn) normalize to lowercase
3. `request.headers` is a plain Python `dict` (case-sensitive)

#### Existing Workaround
RestMachine HAS helper methods that work correctly:
- `request.get_authorization_header()` ✅ (handles both cases)
- `request.get_content_type()` ✅ (handles both cases)
- `request.get_accept_header()` ✅ (handles both cases)

BUT users (and even RestMachine's own code!) use `request.headers.get()` directly.

#### Affected Code Locations
1. **Test code**: `tests/test_rest_framework_multi_driver.py:214`
   ```python
   auth_header = request.headers.get("Authorization", "")  # ❌
   ```

2. **RestMachine itself**: `restmachine/models.py:169`
   ```python
   if self.request and self.request.headers.get("Authorization"):  # ❌
   ```

### Recommended Solutions

#### Option 1: Case-Insensitive Dict (BEST)
Make `request.headers` case-insensitive throughout:

```python
# In restmachine/models.py
class CaseInsensitiveDict(dict):
    """Case-insensitive dictionary for HTTP headers."""

    def get(self, key, default=None):
        """Get value with case-insensitive key lookup."""
        key_lower = key.lower()
        for k, v in self.items():
            if k.lower() == key_lower:
                return v
        return default

    def __getitem__(self, key):
        """Support bracket notation with case-insensitive lookup."""
        key_lower = key.lower()
        for k, v in self.items():
            if k.lower() == key_lower:
                return v
        raise KeyError(key)

    def __contains__(self, key):
        """Support 'in' operator with case-insensitive lookup."""
        key_lower = key.lower()
        return any(k.lower() == key_lower for k in self.keys())

@dataclass
class Request:
    method: HTTPMethod
    path: str
    headers: CaseInsensitiveDict  # Changed type
    ...

    def __post_init__(self):
        # Ensure headers is case-insensitive
        if not isinstance(self.headers, CaseInsensitiveDict):
            self.headers = CaseInsensitiveDict(self.headers)
```

**Benefits**:
- Fixes all existing code (tests + RestMachine)
- No API changes needed
- Works with any header name
- Matches HTTP spec (RFC 7230)

#### Option 2: Update All Code (NOT RECOMMENDED)
Change all `request.headers.get()` calls to use helper methods:

```python
# Before:
auth_header = request.headers.get("Authorization", "")

# After:
auth_header = request.get_authorization_header() or ""
```

**Drawbacks**:
- Requires updating all test code
- Requires updating RestMachine internals
- Only works for headers with helper methods
- Breaks user applications using custom headers

### Next Steps

1. **Implement CaseInsensitiveDict in RestMachine** (recommended)
2. **Remove @skip_driver decorators** from auth tests
3. **Verify all 8 auth tests pass** on HTTP drivers
4. **Update documentation** to note headers are case-insensitive

---

## Other Skipped Tests (ACCEPTABLE)

### Content-Length on 204 (4 tests)
**Reason**: HTTP servers add `Content-Length: 0` to 204 responses

**Expected Behavior**:
- RFC 7230: "204 MUST NOT contain a message body"
- Servers add `Content-Length: 0` for safety
- This is server behavior, not a framework bug

**Action**: Keep skipped (acceptable difference)

### Demo Tests (4 tests)
**Reason**: Demonstrate `@only_drivers()` decorator

**Action**: No change needed (intentional)

---

## Priority

1. **HIGH**: Fix case-insensitive headers (affects production)
2. **MEDIUM**: Phase 2 deduplication (reduce 895 → 450 tests)
3. **LOW**: Content-Length tests (acceptable as-is)

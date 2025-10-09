# Skipped Tests Analysis

## Summary
Out of 895 tests, **16 are skipped**. Investigation reveals:
- **4 tests** are intentional demo tests (test_multi_driver_example.py)
- **4 tests** are expected HTTP server behavior (Content-Length on 204)
- **8 tests** reveal a **CRITICAL BUG** in RestMachine header handling

## Critical Bug Found: Case-Sensitive Header Lookups ❌

### The Problem
**8 auth tests fail on HTTP drivers** due to case-sensitive header lookups in RestMachine:

```python
# In application code:
auth_header = request.headers.get("Authorization", "")  # Capital A

# Headers received from HTTP drivers:
{'authorization': 'Bearer valid_token'}  # lowercase a ❌

# Headers received from direct driver:
{'Authorization': 'Bearer valid_token'}  # Capital A ✅
```

### Test Evidence

**Direct Driver (WORKS)**:
```
Headers: {'Authorization': 'Bearer valid_token', 'Accept': 'application/json'}
Authorization header: 'Bearer valid_token'  ✅
Status: 200
```

**HTTP Driver (FAILS)**:
```
Headers: {'authorization': 'Bearer valid_token', 'accept': 'application/json'}
Authorization header: ''  ❌ (not found due to case mismatch!)
Status: 401 Unauthorized
```

### Root Cause
HTTP headers are **case-insensitive** per RFC 7230, but:
- Direct driver preserves original casing from test code (`'Authorization'`)
- HTTP drivers (uvicorn/hypercorn) normalize headers to lowercase (`'authorization'`)
- RestMachine's `request.headers.get()` uses **case-sensitive** dictionary lookup

### Impact
**Any RestMachine application** that accesses headers with capital letters will fail when deployed to real HTTP servers:
- `request.headers.get("Authorization")` ❌ Fails on HTTP servers
- `request.headers.get("Content-Type")` ❌ Fails on HTTP servers
- `request.headers.get("User-Agent")` ❌ Fails on HTTP servers

### Affected Tests (Currently Skipped)
1. ✗ `test_protected_endpoint_accessible_with_auth` (4 HTTP drivers)
2. ✗ `test_admin_endpoint_accessible_for_admin` (4 HTTP drivers)

**Total: 8 tests skipped due to this bug**

---

## Expected Behavior: Content-Length Tests ✓

### The Issue
**4 tests skipped** because HTTP servers add `Content-Length: 0` to 204 responses:

```python
def test_no_content_length_for_204(self, api):
    response = api_client.get_resource("/none")
    assert response.get_header("Content-Length") is None  # Fails on HTTP servers
```

### Why It's Skipped
- **Direct driver**: No Content-Length header (framework behavior)
- **HTTP servers**: Add `Content-Length: 0` (server safety behavior)

### Is This a Bug?
**No** - This is expected HTTP server behavior:
- RFC 7230 says 204 "MUST NOT contain a message body"
- Servers add `Content-Length: 0` to be explicit
- This is a server implementation detail, not a framework bug

### Affected Tests
1. ✓ `test_no_content_length_for_204` (4 HTTP drivers)

**Total: 4 tests correctly skipped** (expected behavior difference)

---

## Demo Tests: Intentionally Skipped ✓

### The Tests
4 tests in `test_multi_driver_example.py` use `@only_drivers()` decorator:

```python
@only_drivers('direct', 'aws_lambda')
def test_only_certain_drivers(self, api):
    # This test demonstrates the @only_drivers decorator
    ...
```

### Why They're Skipped
These are **demonstration tests** showing how to use decorators to limit driver scope.

### Affected Tests
1. ✓ `test_only_certain_drivers` (4 HTTP drivers)

**Total: 4 tests correctly skipped** (intentional demo)

---

## Summary Table

| Category | Count | Status | Action Required |
|----------|-------|--------|----------------|
| **Auth header bug** | 8 | ❌ **BUG** | Fix case-insensitive headers |
| Content-Length 204 | 4 | ✓ Expected | No action (server behavior) |
| Demo tests | 4 | ✓ Intentional | No action (by design) |
| **TOTAL** | **16** | | |

---

## Recommended Fix

### Option 1: Fix RestMachine Framework (Recommended)
Make `request.headers` use case-insensitive lookups:

```python
# In restmachine/core/request.py or similar
class CaseInsensitiveDict(dict):
    def get(self, key, default=None):
        # Lookup with lowercase key
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default

# Use CaseInsensitiveDict for request.headers
request.headers = CaseInsensitiveDict(raw_headers)
```

### Option 2: Normalize Header Names in Tests
Change test code to use lowercase (not recommended - doesn't fix real apps):

```python
# Before (fails on HTTP servers):
auth_header = request.headers.get("Authorization", "")

# After (works but non-standard):
auth_header = request.headers.get("authorization", "")
```

### Option 3: Fix in Server Adapter Layer
Normalize headers when converting from ASGI to RestMachine request:

```python
# In server adapter
def asgi_headers_to_dict(asgi_headers):
    # Preserve original casing
    return {k.decode(): v.decode() for k, v in asgi_headers}
```

---

## Next Steps

1. **Investigate RestMachine's request.headers implementation**
   - Find where headers are stored
   - Understand why direct driver preserves casing
   - Understand why HTTP drivers use lowercase

2. **Implement case-insensitive header lookups**
   - Make `request.headers.get()` case-insensitive
   - Ensure backward compatibility

3. **Re-enable the 8 auth tests**
   - Remove `@skip_driver` decorators
   - Verify all tests pass

4. **Consider Content-Length tests**
   - Either keep skipped (acceptable)
   - Or update assertions to handle both cases:
     ```python
     # Accept both None and "0" for 204 responses
     content_length = response.get_header("Content-Length")
     assert content_length is None or content_length == "0"
     ```

---

## Conclusion

**Major Finding**: The 8 skipped auth tests reveal a **critical bug** in RestMachine's header handling that affects real-world deployments.

**Action Required**: Fix case-insensitive header lookups in RestMachine framework to match HTTP standards.

**Priority**: HIGH - This affects any application using standard HTTP headers like Authorization, Content-Type, etc.

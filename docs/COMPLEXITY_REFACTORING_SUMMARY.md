# Complexity Refactoring Summary

Quick reference for addressing high-complexity code identified by Radon.

## The Problem

5 methods have complexity ratings of D or worse (≥21):

| Method | Rating | Score | Issue |
|--------|--------|-------|-------|
| `state_execute_and_render` | **F** | 49 | Too many responsibilities |
| `process_request` | **E** | 35 | Repetitive state transitions |
| `_create_error_response` | D | 24 | Complex handler selection |
| `_parse_alb_event` | D | 23 | Multiple parsing paths |
| `_parse_apigw_v2_event` | D | 21 | Duplicated parsing logic |

## The Solution (4 Phases)

### Phase 1: AWS Adapter - Extract Common Parsing 📦
**Effort:** 1-2 days | **Risk:** Low | **Impact:** -44 complexity points

Extract shared helpers:
- `_extract_headers()`
- `_extract_query_params()`
- `_extract_path_params()`
- `_decode_body()`
- `_extract_client_cert_from_context()`

**Result:** All 3 parsing methods → B rating

---

### Phase 2: State Machine - Simplify Process Flow 🔄
**Effort:** 2-3 days | **Risk:** Medium | **Impact:** -26 complexity points

Replace repetitive pattern:
```python
# Before: 15+ copies of this
result = self.state_route_exists()
log_state_transition("route_exists", result)
if not result.continue_processing:
    return result.response or default_response
```

With clean loop:
```python
# After: Single loop over state list
states = [
    (self.state_route_exists, "route_exists"),
    (self.state_service_available, "service_available"),
    # ...
]

for state_method, state_name in states:
    response = self._execute_state(state_method, state_name, default_response)
    if response:
        return response
```

**Result:** `process_request` E (35) → B (9)

---

### Phase 3: State Machine - Break Down Execute & Render 🎨
**Effort:** 3-5 days | **Risk:** High | **Impact:** -34 complexity points

Extract 8 concerns into focused methods:
1. `_validate_and_process_return_value()` - Handle Pydantic validation
2. `_render_result()` - Rendering logic
3. `_add_resource_metadata_headers()` - ETag/Last-Modified
4. `_has_route_specific_renderer()` - Check for custom renderer
5. `_render_with_route_renderer()` - Route-specific rendering
6. `_render_with_global_renderer()` - Global rendering
7. `_update_response_with_headers()` - Response object handling
8. Error handlers for each exception type

**Result:** `state_execute_and_render` F (49) → C (15)

---

### Phase 4: Error Response - Extract Handler Resolution 🚨
**Effort:** 1 day | **Risk:** Low | **Impact:** -16 complexity points

Extract custom handler lookup:
```python
def _find_custom_error_handler(status_code, content_type):
    # Priority: status+type → status → default
    ...

def _create_error_response(status_code, message, details):
    handler = self._find_custom_error_handler(...)
    if handler:
        return self._execute_custom_error_handler(...)
    return self._create_default_error_response(...)
```

**Result:** `_create_error_response` D (24) → B (8)

---

## Implementation Timeline

```
Week 1: Phase 1 (AWS Adapters)          ✅ Low risk, quick win
Week 2: Phase 2 (Process Request)       ⚠️ Medium risk, good testing
Week 3-4: Phase 3 (Execute & Render)    ⚠️ High risk, critical path
Week 5: Phase 4 (Error Response)        ✅ Low risk, cleanup
```

## Expected Improvements

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| F-rated methods | 1 | 0 | ⬇️ 1 |
| E-rated methods | 1 | 0 | ⬇️ 1 |
| D-rated methods | 3 | 0 | ⬇️ 3 |
| C-rated methods | 9 | 10 | ⬆️ 1 |
| Average complexity | A (3.59) | A (2.8) | ⬇️ 0.8 |
| Total complexity reduction | - | - | ⬇️ 105 points |

## Testing Strategy

✅ **After each extraction:**
```bash
pytest packages/restmachine/tests packages/restmachine-aws/tests -m 'not performance' -q
```

✅ **After each phase:**
```bash
tox -e complexity  # Verify complexity improvements
tox -e benchmark   # Ensure no performance regression
```

✅ **Before merging:**
```bash
tox  # All checks must pass
```

## Success Criteria

- ✅ All 592 tests passing
- ✅ No F or E rated methods
- ✅ All refactored methods at C or better
- ✅ No performance degradation
- ✅ Code coverage maintained

## Quick Decision Guide

**Should we do this refactoring?**
- ✅ YES - Code will be more maintainable
- ✅ YES - Incremental approach is low-risk
- ✅ YES - Clear success criteria
- ✅ YES - Will prevent future technical debt

**When should we start?**
- **Now** - Phase 1 (AWS adapters) is low-risk, high-value
- **Soon** - Phase 2-4 when ready for deeper changes

**Can we skip any phases?**
- Phase 1: **No** - Quick win, reduces 3 D-rated methods
- Phase 2: **Maybe** - Current code works, but hard to maintain
- Phase 3: **Maybe** - Most complex, but biggest improvement
- Phase 4: **Yes** - D rating is borderline acceptable

---

## Next Steps

1. **Review this plan** with the team
2. **Create tracking issues** for each phase
3. **Start with Phase 1** (AWS adapters - quick win)
4. **Measure and iterate** based on results

See `COMPLEXITY_REFACTORING_PLAN.md` for detailed implementation guide.

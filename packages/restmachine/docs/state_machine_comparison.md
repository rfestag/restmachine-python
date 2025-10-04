# State Machine Pattern Comparison

## Current Implementation (Waterfall)

```python
def process_request(self, request: Request) -> Response:
    result = self.state_route_exists()
    if not result.continue_processing:
        return result.response

    result = self.state_service_available()
    if not result.continue_processing:
        return result.response

    result = self.state_known_method()
    if not result.continue_processing:
        return result.response

    # ... 12 more states ...

    return self.state_execute_and_render()
```

**Problems:**
- Every request goes through all states sequentially
- Can't skip states even when irrelevant
- Hard to see state flow
- Implicit transitions (boolean flags)
- Difficult to optimize

## Proposed Implementation (True State Machine)

```python
def process_request(self, request: Request) -> Response:
    ctx = StateContext(app=self.app, request=request)
    current_state = RouteExistsState()

    # Execute states until terminal Response
    while not isinstance(current_state, Response):
        logger.debug(f"→ {current_state.name}")
        current_state = current_state.execute(ctx)

    return current_state
```

**Benefits:**
- Explicit state transitions
- States can skip ahead to terminal responses
- Easy to visualize and debug
- Each state is self-contained
- Natural optimization points

## State Flow Diagram

```
┌─────────────────┐
│ RouteExists     │
└────────┬────────┘
         │
    ┌────┴─────┐
    │ Found?   │
    └──┬───┬───┘
       │   │
      Yes  No → [404 Response]
       │
       ↓
┌─────────────────┐
│ServiceAvailable │
└────────┬────────┘
         │
    ┌────┴──────┐
    │Available? │
    └──┬────┬───┘
       │    │
      Yes   No → [503 Response]
       │
       ↓
┌─────────────────┐
│ KnownMethod     │
└────────┬────────┘
         │
    ┌────┴─────┐
    │ Known?   │
    └──┬───┬───┘
       │   │
      Yes  No → [501 Response]
       │
       ↓
┌─────────────────┐
│ResourceExists   │────────────────┐
└────────┬────────┘                │
         │                         │
    ┌────┴─────┐                   │
    │ Exists?  │                   │
    └──┬───┬───┘                   │
       │   │                       │
      Yes  No → [POST?] ──Yes──→ [Try Create]
       │              └─No──→ [404]
       │
       ↓
┌─────────────────┐
│Has Conditional? │ ← Route Flag Optimization
└────────┬────────┘
         │
    ┌────┴─────┐
    │    No    │────────────────┐
    │          │                │
    │   Yes    │                │
    │          │                │
    ↓          ↓                ↓
[If-Match]  [Skip]    [ContentTypesProvided]
    │          │                │
    ↓          │                │
[If-None]      │                │
    │          │                │
    └──────────┴────────────────┘
              │
              ↓
    ┌─────────────────┐
    │ContentAccepted? │
    └────────┬────────┘
             │
        ┌────┴─────┐
        │Accepted? │
        └──┬───┬───┘
           │   │
          Yes  No → [406 Response]
           │
           ↓
    ┌─────────────────┐
    │ExecuteAndRender │
    └────────┬────────┘
             │
             ↓
        [Response]
```

## Performance Comparison

### Current (Waterfall)
```
Request → 15 state checks (always) → Response
Time: O(n) where n = number of states
```

### Proposed (State Machine)
```
Request → Dynamic path through states → Response
Time: O(k) where k = relevant states only

Examples:
- Simple GET: 7 states (skip auth, skip conditional)
- GET with auth: 9 states (skip conditional)
- GET with conditional: 12 states (full path)
- POST create: 8 states (different path)
```

## Migration Strategy

### Phase 1: Create State Classes
1. Create `State` base class and `StateContext`
2. Implement each state as a class
3. Keep old implementation in parallel

### Phase 2: Add Route Flags
1. Add `RouteCapabilities` to analyze routes
2. Compute flags at route registration
3. Use flags in state decisions to skip paths

### Phase 3: Optimize Hot Paths
1. Profile common request patterns
2. Identify state sequences that can be combined
3. Add fast-path shortcuts

### Phase 4: Switch Over
1. Run both implementations in parallel with tests
2. Compare outputs for correctness
3. Switch to new implementation
4. Remove old code

## Code Organization

```
restmachine/
├── state_machine/
│   ├── __init__.py
│   ├── base.py           # State, StateContext
│   ├── context.py        # StateContext utilities
│   ├── states/
│   │   ├── __init__.py
│   │   ├── route.py      # RouteExistsState
│   │   ├── service.py    # ServiceAvailableState, KnownMethodState
│   │   ├── auth.py       # AuthorizedState, ForbiddenState
│   │   ├── resource.py   # ResourceExistsState
│   │   ├── conditional.py # If-Match, If-None-Match, etc.
│   │   ├── content.py    # ContentNegotiationStates
│   │   └── execute.py    # ExecuteAndRenderState
│   └── machine.py        # RequestStateMachine
```

## Testing Strategy

Each state can be unit tested independently:

```python
def test_route_exists_state_with_valid_route():
    ctx = StateContext(app=mock_app, request=mock_request)
    state = RouteExistsState()

    next_state = state.execute(ctx)

    assert isinstance(next_state, ServiceAvailableState)
    assert ctx.route_handler is not None

def test_route_exists_state_with_invalid_route():
    ctx = StateContext(app=mock_app, request=mock_request)
    state = RouteExistsState()

    response = state.execute(ctx)

    assert isinstance(response, Response)
    assert response.status_code == 404
```

## Performance Gains

Based on typical request patterns:

| Request Type | Current States | Optimized States | Improvement |
|--------------|---------------|------------------|-------------|
| Simple GET (no auth, no conditional) | 15 | 7 | ~50% faster |
| GET with auth (no conditional) | 15 | 9 | ~40% faster |
| GET with conditional (full path) | 15 | 12 | ~20% faster |
| POST create | 15 | 8 | ~45% faster |
| 404 (route not found) | 1 | 1 | Same |

**Average improvement: 30-40% reduction in state processing**

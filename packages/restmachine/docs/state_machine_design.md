# State Machine Refactoring Design

## Architecture

### State Base Class
```python
class State(ABC):
    """Base class for all state machine states."""

    @abstractmethod
    def execute(self, ctx: StateContext) -> Union['State', Response]:
        """Execute this state and return next state or terminal response."""
        pass

    @property
    def name(self) -> str:
        """State name for logging."""
        return self.__class__.__name__
```

### State Context
```python
@dataclass
class StateContext:
    """Shared context passed through state machine."""
    app: 'RestApplication'
    request: Request
    route_handler: Optional[RouteHandler] = None
    chosen_renderer: Optional[ContentRenderer] = None
    handler_dependencies: List[str] = field(default_factory=list)
    dependency_callbacks: Dict[str, DependencyWrapper] = field(default_factory=dict)
```

### State Machine Runner
```python
class RequestStateMachine:
    def process_request(self, request: Request) -> Response:
        ctx = StateContext(app=self.app, request=request)
        self.app._dependency_cache.clear()

        # Start with initial state
        current_state: Union[State, Response] = RouteExistsState()

        # Execute states until we get a Response
        while not isinstance(current_state, Response):
            logger.debug(f"Executing state: {current_state.name}")
            current_state = current_state.execute(ctx)

        return current_state
```

## State Transition Map

```
RouteExistsState
  ├─→ NotFoundResponse (route not found)
  ├─→ MethodNotAllowedResponse (wrong method)
  └─→ ServiceAvailableState

ServiceAvailableState
  ├─→ ServiceUnavailableResponse (not available)
  └─→ KnownMethodState

KnownMethodState
  ├─→ NotImplementedResponse (unknown method)
  └─→ UriTooLongState

UriTooLongState
  ├─→ UriTooLongResponse (uri too long)
  └─→ MethodAllowedState

MethodAllowedState
  ├─→ MethodNotAllowedResponse (method not allowed)
  └─→ MalformedRequestState

MalformedRequestState
  ├─→ BadRequestResponse (malformed)
  └─→ AuthorizedState

AuthorizedState
  ├─→ UnauthorizedResponse (not authorized)
  └─→ ForbiddenState

ForbiddenState
  ├─→ ForbiddenResponse (forbidden)
  └─→ ContentHeadersValidState

ContentHeadersValidState
  ├─→ BadRequestResponse (invalid headers)
  └─→ ResourceExistsState

ResourceExistsState
  ├─→ NotFoundResponse (not found, not POST)
  ├─→ ResourceFromRequestState (not found, is POST)
  └─→ IfMatchState (exists)

IfMatchState
  ├─→ PreconditionFailedResponse (If-Match fails)
  └─→ IfUnmodifiedSinceState

IfUnmodifiedSinceState
  ├─→ PreconditionFailedResponse (If-Unmodified-Since fails)
  └─→ IfNoneMatchState

IfNoneMatchState
  ├─→ NotModifiedResponse (If-None-Match matches, GET)
  ├─→ PreconditionFailedResponse (If-None-Match matches, not GET)
  └─→ IfModifiedSinceState

IfModifiedSinceState
  ├─→ NotModifiedResponse (not modified, GET)
  └─→ ContentTypesProvidedState

ContentTypesProvidedState
  ├─→ InternalServerErrorResponse (no renderers)
  └─→ ContentTypesAcceptedState

ContentTypesAcceptedState
  ├─→ NotAcceptableResponse (no acceptable type)
  └─→ ExecuteAndRenderState

ExecuteAndRenderState
  └─→ Response (final response)
```

## Example State Implementation

```python
class RouteExistsState(State):
    def execute(self, ctx: StateContext) -> Union[State, Response]:
        route_match = ctx.app._find_route(ctx.request.method, ctx.request.path)

        if route_match is None:
            # Check if ANY route exists for this path (method mismatch)
            if ctx.app._path_has_routes(ctx.request.path):
                return create_error_response(ctx, HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed")

            # No route exists at all
            callback = ctx.app._default_callbacks.get("route_not_found")
            if callback:
                try:
                    response = ctx.app._call_with_injection(callback, ctx.request, None)
                    if isinstance(response, Response):
                        return response
                except Exception as e:
                    logger.error(f"Error in route_not_found callback: {e}")

            return create_error_response(ctx, HTTPStatus.NOT_FOUND, "Not Found")

        # Route found - set context and continue
        ctx.route_handler, path_params = route_match
        ctx.request.path_params = path_params
        ctx.handler_dependencies = list(ctx.route_handler.param_info.keys())

        # Copy pre-resolved state callbacks
        for state_name, callback in ctx.route_handler.state_callbacks.items():
            wrapper = DependencyWrapper(callback, state_name, callback.__name__)
            ctx.dependency_callbacks[state_name] = wrapper

        return ServiceAvailableState()
```

## Benefits

1. **Explicit Transitions**: Each state clearly shows where it goes next
2. **Skippable States**: States can jump directly to terminal responses
3. **Easier Testing**: Each state is a standalone class, easy to unit test
4. **Better Logging**: Clear state transitions visible in logs
5. **Extensible**: Add new states without modifying main loop
6. **Type Safe**: Type hints make transitions explicit

## Performance Improvements

- **State Skipping**: Can bypass irrelevant states entirely
- **Early Termination**: Return Response immediately instead of checking remaining states
- **Route Flags**: Use route flags to skip states (e.g., no auth check needed)

Example optimization:
```python
class ResourceExistsState(State):
    def execute(self, ctx: StateContext) -> Union[State, Response]:
        # If route has no conditional request support, skip all conditional states
        if not ctx.route_handler.supports_conditional_requests:
            return ContentTypesProvidedState()  # Skip all If-* states

        # ... rest of logic
```

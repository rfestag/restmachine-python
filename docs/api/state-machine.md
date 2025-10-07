# State Machine

## Overview

RestMachine uses a webmachine-inspired state machine to process HTTP requests. The state machine handles content negotiation, authentication, authorization, and conditional requests automatically.

## State Machine Callbacks

Customize request processing by providing state machine callbacks:

```python
@app.get('/protected')
def protected_resource(request):
    return {"data": "secret"}

# Add authentication callback
@app.state_machine_callback('is_authorized')
def check_auth(request):
    """Check if request is authorized."""
    auth_header = request.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    # Validate token...
    return True
```

## Available Callbacks

The state machine supports various callback points:

- `is_authorized` - Check authorization
- `forbidden` - Handle forbidden requests
- `malformed_request` - Validate request format
- `allowed_methods` - Specify allowed HTTP methods
- `content_types_provided` - Available response formats
- `content_types_accepted` - Accepted request formats

## See Also

- [State Machine Guide](../advanced/state-machine.md) - Complete guide with diagrams
- [Application API](application.md) - Register callbacks
- [Authentication Guide](../guide/authentication.md) - Auth patterns

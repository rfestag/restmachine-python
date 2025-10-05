# ASGI Adapter Refactoring

## Overview

The HTTP server handling has been refactored to provide a unified ASGI adapter in the core package, aligning internal application patterns with ASGI standards.

## Changes Made

### 1. ASGI Adapter Moved to Core Package

**Before:**
- ASGI adapter was in `restmachine/server.py`
- Only accessible via `create_asgi_app()` function
- Not clearly separated from server driver code

**After:**
- ASGI adapter moved to `restmachine/adapters.py`
- Can be imported directly: `from restmachine import ASGIAdapter`
- Clear separation: `Adapter` (sync) vs `ASGIAdapter` (async)
- Backward compatibility maintained via re-exports in `server.py`

### 2. AWS Adapter Aligned with ASGI Patterns

**Updated `AwsApiGatewayAdapter`:**
- Headers normalized to lowercase (matching ASGI pattern)
- Query parameter parsing aligned with ASGI
- Consistent body encoding/decoding
- Better error handling with latin-1 fallback
- Automatic Content-Type header for JSON responses

### 3. Unified Adapter Architecture

```python
# Adapters module now contains both:

class Adapter(ABC):
    """Base class for synchronous event adapters (Lambda, Azure, etc.)"""

class ASGIAdapter:
    """ASGI 3.0 adapter for async servers (Uvicorn, Hypercorn, etc.)"""
```

## Usage Examples

### ASGI Servers (Uvicorn, Hypercorn)

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello World"}

# Create ASGI application
asgi_app = ASGIAdapter(app)

# Or use convenience function
from restmachine import create_asgi_app
asgi_app = create_asgi_app(app)

# Run with any ASGI server:
# uvicorn module:asgi_app --reload
# hypercorn module:asgi_app --reload
```

### AWS Lambda

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get("/hello")
def hello():
    return {"message": "Hello from Lambda"}

# Create adapter
adapter = AwsApiGatewayAdapter(app)

# Lambda handler
def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

## Import Compatibility

The ASGI adapter can now be imported from multiple locations for convenience:

```python
# Recommended - direct import from main package
from restmachine import ASGIAdapter, create_asgi_app

# Explicit - from adapters module
from restmachine.adapters import ASGIAdapter, create_asgi_app

# Backward compatible - from server module
from restmachine.server import ASGIAdapter, create_asgi_app
```

All imports reference the same implementation.

## Benefits

1. **Clearer Architecture**: Separation between async (ASGI) and sync (Lambda) adapters
2. **Consistent Patterns**: Both adapters follow similar header/parameter handling
3. **Better Documentation**: Clear examples and docstrings
4. **Easier to Use**: Direct imports from main package
5. **Platform Alignment**: AWS adapter now aligns with ASGI patterns

## Using with ASGI Servers

Production users should use the ASGI adapter directly with their preferred ASGI server (Uvicorn, Hypercorn, Daphne, etc.).

## Testing

All existing tests pass:
- ✅ Core framework tests (313 tests)
- ✅ AWS adapter tests (207 tests)
- ✅ Import compatibility verified
- ✅ Backward compatibility maintained

## Migration Guide

### For Direct ASGI Usage

**Before:**
```python
from restmachine.server import create_asgi_app
```

**After (recommended):**
```python
from restmachine import create_asgi_app
# or
from restmachine import ASGIAdapter
```

**Note:** The old import still works for backward compatibility.

### For AWS Lambda

**No changes required** - AWS adapter continues to work as before, but now uses lowercase headers internally for consistency with ASGI patterns.

## Future Considerations

1. The server drivers (`UvicornDriver`, `HypercornDriver`) in `servers.py` can remain for convenience in local development
2. Users deploying to production should use the ASGI adapter directly with their chosen server
3. Other platform adapters (Azure, Google Cloud) should follow the same patterns as the AWS adapter

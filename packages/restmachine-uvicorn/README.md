# RestMachine Uvicorn Adapter

Uvicorn server adapter for RestMachine framework.

## Installation

```bash
pip install restmachine-uvicorn
```

For development:

```bash
# From monorepo root
pip install -e packages/restmachine[dev]
pip install -e packages/restmachine-uvicorn[dev]
```

## Usage

### HTTP/1.1 Server

```python
from restmachine import RestApplication
from restmachine.server import create_asgi_app
import uvicorn

app = RestApplication()

@app.get("/hello")
def hello():
    return {"message": "Hello from Uvicorn!"}

# Create ASGI app
asgi_app = create_asgi_app(app)

# Run with Uvicorn
uvicorn.run(asgi_app, host="0.0.0.0", port=8000)
```

## Testing

The package provides test drivers for use with the RestMachine testing framework:

```python
from restmachine import RestApplication
from restmachine_uvicorn import UvicornHttp1Driver

app = RestApplication()

# Test with HTTP/1.1
with UvicornHttp1Driver(app) as driver:
    response = driver.execute(request)
```

## Features

- HTTP/1.1 support
- ASGI 3.0 compliant
- Test drivers for integration testing
- Full RestMachine compatibility

## Testing

```bash
pytest packages/restmachine-uvicorn/tests/
```

## License

MIT

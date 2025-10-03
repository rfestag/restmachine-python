# RestMachine Hypercorn Adapter

Hypercorn server adapter for RestMachine framework.

## Installation

```bash
pip install restmachine-hypercorn
```

For development:

```bash
# From monorepo root
pip install -e packages/restmachine[dev]
pip install -e packages/restmachine-hypercorn[dev]
```

## Usage

### HTTP/1.1 Server

```python
from restmachine import RestApplication
from restmachine.server import create_asgi_app
import hypercorn.asyncio
from hypercorn import Config

app = RestApplication()

@app.get("/hello")
def hello():
    return {"message": "Hello from Hypercorn!"}

# Create ASGI app
asgi_app = create_asgi_app(app)

# Run with Hypercorn
config = Config()
config.bind = ["0.0.0.0:8000"]

import asyncio
asyncio.run(hypercorn.asyncio.serve(asgi_app, config))
```

### HTTP/2 Server

```python
from restmachine import RestApplication
from restmachine.server import create_asgi_app
import hypercorn.asyncio
from hypercorn import Config

app = RestApplication()

@app.get("/hello")
def hello():
    return {"message": "Hello from Hypercorn with HTTP/2!"}

# Create ASGI app
asgi_app = create_asgi_app(app)

# Run with Hypercorn and HTTP/2
config = Config()
config.bind = ["0.0.0.0:8000"]
config.h2 = True  # Enable HTTP/2

import asyncio
asyncio.run(hypercorn.asyncio.serve(asgi_app, config))
```

## Testing

The package provides test drivers for use with the RestMachine testing framework:

```python
from restmachine import RestApplication
from restmachine_hypercorn import HypercornHttp1Driver, HypercornHttp2Driver

app = RestApplication()

# Test with HTTP/1.1
with HypercornHttp1Driver(app) as driver:
    response = driver.execute(request)

# Test with HTTP/2
with HypercornHttp2Driver(app) as driver:
    response = driver.execute(request)
```

## Features

- HTTP/1.1 support
- HTTP/2 support
- ASGI 3.0 compliant
- Test drivers for integration testing
- Full RestMachine compatibility

## Testing

```bash
pytest packages/restmachine-hypercorn/tests/
```

## License

MIT

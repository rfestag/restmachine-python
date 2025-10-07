# ASGI Adapter

## ASGIAdapter

::: restmachine.ASGIAdapter
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## Adapter (Base Class)

::: restmachine.Adapter
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## create_asgi_app

::: restmachine.create_asgi_app
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## Overview

Adapters convert RestMachine applications to run on different platforms. The `ASGIAdapter` enables deployment on any ASGI-compatible server (Uvicorn, Hypercorn, Daphne, etc.).

## Quick Start

```python
from restmachine import RestApplication, ASGIAdapter

app = RestApplication()

@app.get('/hello')
def hello():
    return {"message": "Hello World"}

# Create ASGI app
asgi_app = ASGIAdapter(app)

# Run with uvicorn
# uvicorn myapp:asgi_app --reload
```

## See Also

- [Application API](application.md) - Main application class
- [Uvicorn Deployment Guide](../guide/deployment/uvicorn.md) - Deploy with Uvicorn
- [Hypercorn Deployment Guide](../guide/deployment/hypercorn.md) - Deploy with Hypercorn
- [AWS Lambda Adapter](../restmachine-aws/api/adapter.md) - Deploy to Lambda

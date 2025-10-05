# Installation

## Requirements

- Python 3.9 or higher
- pip (Python package installer)

## Basic Installation

Install RestMachine using pip:

```bash
pip install restmachine
```

This installs the core framework with zero required dependencies.

## Optional Dependencies

### Validation Support

For Pydantic-based request/response validation:

```bash
pip install restmachine[validation]
```

This adds:
- `pydantic>=2.0.0` - For data validation and serialization

### AWS Lambda Support

For deploying to AWS Lambda:

```bash
pip install restmachine-aws
```

This includes the AWS Lambda adapter with support for:
- API Gateway REST API (v1)
- API Gateway HTTP API (v2)
- Application Load Balancer (ALB)
- Lambda Function URLs

### ASGI Server (Development)

For running locally with an ASGI server:

=== "Uvicorn"
    ```bash
    pip install uvicorn[standard]
    ```

=== "Hypercorn"
    ```bash
    pip install hypercorn
    ```

=== "Daphne"
    ```bash
    pip install daphne
    ```

### Complete Installation

For all features:

```bash
pip install restmachine[validation] restmachine-aws uvicorn[standard]
```

## Development Installation

To contribute to RestMachine:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rfestag/restmachine-python.git
   cd restmachine-python
   ```

2. **Install in editable mode with dev dependencies:**
   ```bash
   pip install -e packages/restmachine[dev]
   pip install -e packages/restmachine-aws[dev]
   ```

3. **Run tests:**
   ```bash
   tox
   ```

## Verify Installation

Verify your installation:

```python
import restmachine
print(restmachine.__version__)
```

Or create a simple application:

```python
from restmachine import RestApplication

app = RestApplication()

@app.get('/health')
def health_check():
    return {"status": "healthy"}

# Test it
from restmachine import Request, HTTPMethod

request = Request(method=HTTPMethod.GET, path='/health')
response = app.execute(request)
print(response.body)  # {"status": "healthy"}
```

## Next Steps

- [Quick Start →](quickstart.md) - Build your first API
- [Basic Application →](../guide/basic-application.md) - Learn the fundamentals

# Restmachine

[![Build Status](https://github.com/rfestag/restmachine-python/workflows/CI/badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Coverage](https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Code Quality](https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
[![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/rfestag/restmachine-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

Build HTTP APIs that leverage the full power of HTTP standards through simple decorators and annotations. Write once, deploy anywhere—from serverless AWS Lambda to traditional ASGI servers.

## Why Restmachine?

**HTTP is powerful, but often underutilized.** Restmachine makes advanced HTTP features accessible through simple Python decorators:

- **Conditional Requests** (`@app.generate_etag`, `@app.last_modified`) - Automatic 304 Not Modified responses for efficient caching
- **Range Requests** - Partial content delivery for large files and resumable downloads
- **Content Negotiation** (`@app.provides("text/html")`) - Serve JSON, HTML, or custom formats from the same endpoint
- **CORS** (`@app.cors(origins=["..."])`) - Cross-origin requests with fine-grained control
- **Content Security Policy** (`@app.csp(...)`) - Security headers for modern web applications
- **Dependency Injection** - Share resources (database connections, auth context) across handlers with automatic lifecycle management

**Write once, deploy anywhere.** The same application code runs unchanged on:
- **AWS Lambda** (API Gateway, ALB, Function URLs)
- **ASGI servers** (Uvicorn, Hypercorn, Daphne)
- **Any Python environment** (direct request execution)

## Features

- **Simple, Decorator-Based API** - Flask-like route registration with powerful HTTP features
- **Automatic Dependency Injection** - Request context, validated inputs, and custom resources injected by name
- **Built-in Validation** - Optional Pydantic integration for request/response validation
- **Standards Compliant** - Full HTTP spec support including conditional requests, range requests, and multi-value headers
- **Universal Deployment** - Same code for AWS Lambda, ASGI servers, or direct execution
- **Zero Required Dependencies** - Lightweight core with optional extensions

## Installation

### Basic Installation

**Note:** This package has not been released to PyPI yet.

```bash
pip install restmachine
```

### With Validation Support

```bash
pip install restmachine[validation]
```

### AWS Lambda Support

```bash
pip install restmachine-aws
```

### Development Installation

```bash
git clone https://github.com/rfestag/restmachine-python.git
cd restmachine-python
pip install -e packages/restmachine[dev]
```

## Documentation

📚 **Full documentation is available at:** [https://rfestag.github.io/restmachine-python](https://rfestag.github.io/restmachine-python)

### Quick Links

- **[Getting Started Guide](https://rfestag.github.io/restmachine-python/getting-started/)** - Your first Restmachine application
- **[Dependency Injection](https://rfestag.github.io/restmachine-python/dependency-injection/)** - Learn the DI system
- **[Validation](https://rfestag.github.io/restmachine-python/validation/)** - Pydantic integration
- **[Content Negotiation](https://rfestag.github.io/restmachine-python/content-negotiation/)** - Custom renderers and parsers
- **[ASGI Deployment](https://rfestag.github.io/restmachine-python/deployment/asgi/)** - Deploy with Uvicorn, Hypercorn, etc.
- **[AWS Lambda Deployment](https://rfestag.github.io/restmachine-python/deployment/aws-lambda/)** - Serverless deployment
- **[API Reference](https://rfestag.github.io/restmachine-python/api/)** - Complete API documentation

## Example: HTTP Features Made Simple

```python
from restmachine import RestApplication
from datetime import datetime

app = RestApplication()

# Dependency injection - database connection shared across requests
@app.on_startup
def database():
    return {"users": {1: {"name": "Alice", "updated": "2024-01-01"}}}

# Conditional requests - automatic 304 responses when content hasn't changed
@app.generate_etag
def user_etag(user_id: str, database) -> str:
    user = database["users"].get(int(user_id))
    return user["updated"] if user else ""

@app.get('/users/{user_id}')
def get_user(user_id: str, database):
    user = database["users"].get(int(user_id))
    return {"id": user_id, "name": user["name"]}

# Content negotiation - same endpoint, multiple formats
@app.get('/report')
def get_report():
    return {"sales": 1000, "date": "2024-01-01"}

@app.provides("text/html")
def report_html(get_report):
    data = get_report
    return f"<h1>Sales: ${data['sales']}</h1>"

# CORS for browser APIs
@app.get('/api/data')
@app.cors(origins=["https://example.com"])
def api_data():
    return {"data": "value"}
```

**Deploy to AWS Lambda:**
```python
from restmachine_aws import AwsApiGatewayAdapter

adapter = AwsApiGatewayAdapter(app)
lambda_handler = adapter.handle_event
```

**Deploy to ASGI (Uvicorn, Hypercorn, etc.):**
```python
from restmachine import ASGIAdapter

asgi_app = ASGIAdapter(app)
# Run with: uvicorn main:asgi_app
```

For more examples, see the [examples/](examples/) directory or visit the [documentation](https://rfestag.github.io/restmachine-python).

## Code Quality

This project maintains high code quality standards:

- **Code Quality**: A (3.21) - Excellent [![Code Quality](https://raw.githubusercontent.com/rfestag/restmachine-python/main/complexity-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
- **Test Coverage**: 592 tests passing [![Coverage](https://raw.githubusercontent.com/rfestag/restmachine-python/main/coverage-badge.svg)](https://github.com/rfestag/restmachine-python/actions)
- **Type Safety**: MyPy with strict type checking
- **Security**: Bandit security scanning
- **No F or E rated methods** - All unmaintainable code eliminated ✅

```bash
# Run all quality checks
tox

# Run specific checks
tox -e lint           # Code linting
tox -e type-check     # Type checking
tox -e import-check   # Import cycle detection
tox -e security       # Security scanning
tox -e complexity     # Complexity analysis
```

## Contributing

Contributions are welcome! Please see our [contributing guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

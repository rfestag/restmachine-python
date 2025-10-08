# Metrics & Observability

RestMachine provides a lightweight, platform-agnostic metrics collection system for monitoring application performance and tracking business metrics.

## Overview

The metrics system is designed to be:

- **Platform-agnostic** - Core collection works anywhere
- **Auto-configured for AWS Lambda** - CloudWatch EMF enabled automatically when using `AwsApiGatewayAdapter`
- **Extensible** - Easy to add publishers for any metrics platform
- **Zero-overhead when disabled** - Metrics collection can be bypassed
- **Dependency-injected** - Access via standard DI pattern

### Platform Support

| Platform | Auto-Detection | Support | Documentation |
|----------|----------------|---------|---------------|
| **AWS Lambda** | ✅ **Automatic** | CloudWatch EMF enabled by default | [AWS Metrics Guide](restmachine-aws/guides/metrics.md) |
| **ASGI on AWS** | ✅ **Automatic** | CloudWatch EMF enabled when AWS detected | [ASGI Integration](#asgi-integration) |
| **ASGI (Non-AWS)** | ❌ Manual | Custom publisher required | [ASGI Integration](#asgi-integration) |
| **Other** | ❌ Manual | Custom publisher required | [Custom Publishers](#custom-publishers) |

## Quick Start

### AWS Lambda (Auto-configured)

**When running on AWS Lambda, metrics are automatically enabled and published to CloudWatch using EMF (Embedded Metric Format).** No additional configuration is required.

The `AwsApiGatewayAdapter` automatically detects that it's running in an AWS Lambda environment and:

- ✅ Creates a CloudWatch EMF publisher by default
- ✅ Configures logging to output EMF-formatted metrics
- ✅ Uses your Lambda function name as the service dimension
- ✅ Publishes metrics after each request

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get("/users/{id}")
def get_user(id: str, metrics):
    # Add custom metrics
    metrics.add_metric("users.fetched", 1, unit="Count")
    return {"user": id}

# Metrics automatically enabled with CloudWatch EMF
# No explicit configuration needed!
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

To customize the configuration or disable metrics, see [AWS CloudWatch Metrics Guide](restmachine-aws/guides/metrics.md).

### Other Platforms

For non-AWS platforms, implement a custom publisher:

```python
from restmachine import RestApplication
from restmachine.metrics import MetricsPublisher

class MyPublisher(MetricsPublisher):
    def is_enabled(self) -> bool:
        return True

    def publish(self, collector, request=None, response=None, context=None):
        # Send metrics to your platform
        for name, values in collector.metrics.items():
            for metric_value in values:
                print(f"{name}: {metric_value.value}")

# Use custom publisher
publisher = MyPublisher()
# Integration depends on platform - see Custom Publishers section
```

## Core Concepts

### MetricsCollector

The `MetricsCollector` is injected as a dependency and provides methods to record metrics:

```python
@app.get("/endpoint")
def handler(metrics):
    # Add metrics
    metrics.add_metric("requests", 1, unit="Count")

    # Add dimensions (low-cardinality grouping)
    metrics.add_dimension("environment", "production")

    # Add metadata (high-cardinality context)
    metrics.add_metadata("request_id", request_id)

    # Time operations
    metrics.start_timer("operation")
    do_work()
    metrics.stop_timer("operation")

    return {"ok": True}
```

### MetricsPublisher

The abstract base class for publishing metrics to any platform:

```python
from restmachine.metrics import MetricsPublisher

class MyPublisher(MetricsPublisher):
    def is_enabled(self) -> bool:
        """Return True if publishing is enabled."""
        return True

    def publish(self, collector, request=None, response=None, context=None):
        """Publish collected metrics."""
        # collector.metrics - Dict[str, List[MetricValue]]
        # collector.get_all_dimensions() - Dict[str, str]
        # collector.metadata - Dict[str, Any]
        pass
```

## Adding Metrics

### Basic Metrics

```python
@app.get("/orders")
def list_orders(metrics):
    # Count metrics
    metrics.add_metric("orders.listed", 1, unit="Count")

    # Value metrics
    metrics.add_metric("orders.total_value", 1250.00, unit="None")

    # Size metrics
    metrics.add_metric("response.size", 1024, unit="Bytes")

    return orders
```

### Using Timers

```python
@app.get("/data")
def fetch_data(metrics):
    metrics.start_timer("database.query")
    data = db.query("SELECT * FROM users")
    metrics.stop_timer("database.query")  # Adds metric in milliseconds

    return data
```

### Multiple Values (Aggregation)

```python
@app.get("/batch")
def process_batch(metrics):
    for item in items:
        # Each call adds to the metric
        metrics.add_metric("items.processed", 1, unit="Count")
        metrics.add_metric("processing.time", process(item), unit="Milliseconds")

    # Publisher receives all values for aggregation
    return {"processed": len(items)}
```

## Dimensions vs Metadata

**Dimensions** are for grouping/filtering (low-cardinality):

```python
# Good - few unique values
metrics.add_dimension("environment", "production")  # ~3-5 values
metrics.add_dimension("region", "us-east-1")        # ~10-20 values
metrics.add_dimension("user_type", "premium")       # ~3-10 values
```

**Metadata** is for context/debugging (high-cardinality):

```python
# Good - many unique values
metrics.add_metadata("user_id", "12345")           # Thousands of values
metrics.add_metadata("request_id", "abc-def-...")  # Unique per request
metrics.add_metadata("order_id", order_id)         # Unique identifiers
```

⚠️ Some platforms (like CloudWatch) limit dimensions (max 30). Use metadata for high-cardinality data.

## Metric Units

Available units from the `MetricUnit` enum:

```python
from restmachine.metrics import MetricUnit

# Time
MetricUnit.Seconds
MetricUnit.Milliseconds
MetricUnit.Microseconds

# Bytes
MetricUnit.Bytes
MetricUnit.Kilobytes
MetricUnit.Megabytes
MetricUnit.Gigabytes

# Count
MetricUnit.Count

# Rates
MetricUnit.CountPerSecond
MetricUnit.BytesPerSecond

# Other
MetricUnit.Percent
MetricUnit.None
```

Usage:

```python
metrics.add_metric("api.latency", 45.2, unit=MetricUnit.Milliseconds)
metrics.add_metric("requests", 1, unit=MetricUnit.Count)
metrics.add_metric("response.size", 2048, unit=MetricUnit.Bytes)
```

## Default Dimensions

Set dimensions that apply to all metrics in a request:

```python
@app.get("/endpoint")
def handler(metrics):
    # Apply to all metrics
    metrics.set_default_dimensions(
        environment="production",
        version="v2"
    )

    metrics.add_metric("requests", 1)
    # Includes: environment=production, version=v2

    return {"ok": True}
```

Clear defaults if needed:

```python
metrics.clear_default_dimensions()
```

## Isolated Metrics (Advanced)

Use `EphemeralMetrics` for isolated metric collection:

```python
from restmachine.metrics import EphemeralMetrics

@app.get("/data")
def get_data(metrics, tenant_id: str):
    # Main request metrics
    metrics.add_metric("api.requests", 1)

    # Isolated tenant metrics (no shared dimensions)
    tenant_metrics = EphemeralMetrics()
    tenant_metrics.add_dimension("tenant_id", tenant_id)
    tenant_metrics.add_metric("tenant.requests", 1)

    # EphemeralMetrics won't be auto-published
    # Use for custom processing

    return data
```

## Custom Publishers

Create publishers for any metrics platform.

### Publisher Interface

```python
from restmachine.metrics import MetricsPublisher, MetricsCollector

class MyPublisher(MetricsPublisher):
    def is_enabled(self) -> bool:
        """Return True if publishing is enabled."""
        return True

    def publish(self, collector: MetricsCollector,
               request=None, response=None, context=None):
        """Publish collected metrics.

        Args:
            collector: MetricsCollector with metrics/dimensions/metadata
            request: Optional Request object
            response: Optional Response object
            context: Optional platform context
        """
        # Access metrics
        for name, values in collector.metrics.items():
            for metric_value in values:
                # metric_value.value - The numeric value
                # metric_value.unit - MetricUnit enum
                pass

        # Access dimensions
        dimensions = collector.get_all_dimensions()

        # Access metadata
        metadata = collector.metadata
```

### Example: Datadog

```python
from restmachine.metrics import MetricsPublisher
import datadog

class DatadogPublisher(MetricsPublisher):
    def __init__(self, api_key: str):
        datadog.initialize(api_key=api_key)

    def is_enabled(self) -> bool:
        return True

    def publish(self, collector, request=None, response=None, context=None):
        dimensions = collector.get_all_dimensions()
        tags = [f"{k}:{v}" for k, v in dimensions.items()]

        for name, values in collector.metrics.items():
            for metric_value in values:
                datadog.api.Metric.send(
                    metric=name,
                    points=[(int(time.time()), metric_value.value)],
                    tags=tags
                )
```

### Example: Prometheus

```python
from restmachine.metrics import MetricsPublisher
from prometheus_client import Counter, Histogram

class PrometheusPublisher(MetricsPublisher):
    def __init__(self):
        self.counters = {}
        self.histograms = {}

    def is_enabled(self) -> bool:
        return True

    def publish(self, collector, request=None, response=None, context=None):
        dimensions = collector.get_all_dimensions()
        label_names = list(dimensions.keys())

        for name, values in collector.metrics.items():
            if 'time' in name or 'latency' in name:
                # Use Histogram for timing
                if name not in self.histograms:
                    self.histograms[name] = Histogram(
                        name.replace('.', '_'),
                        f'Metric {name}',
                        label_names
                    )
                for value in values:
                    self.histograms[name].labels(**dimensions).observe(value.value)
            else:
                # Use Counter for counts
                if name not in self.counters:
                    self.counters[name] = Counter(
                        name.replace('.', '_'),
                        f'Metric {name}',
                        label_names
                    )
                for value in values:
                    self.counters[name].labels(**dimensions).inc(value.value)
```

### Example: Multi-Publisher

Publish to multiple backends simultaneously:

```python
from restmachine.metrics import MetricsPublisher

class MultiPublisher(MetricsPublisher):
    def __init__(self, *publishers):
        self.publishers = publishers

    def is_enabled(self) -> bool:
        return any(p.is_enabled() for p in self.publishers)

    def publish(self, collector, request=None, response=None, context=None):
        for publisher in self.publishers:
            if publisher.is_enabled():
                try:
                    publisher.publish(collector, request, response, context)
                except Exception as e:
                    logging.error(f"Publisher {publisher} failed: {e}")
```

## ASGI Integration

**The ASGI adapter automatically detects AWS environments and enables CloudWatch EMF metrics!**

When the `ASGIAdapter` detects it's running on AWS (via environment variables like `AWS_REGION`, `AWS_EXECUTION_ENV`, or ECS metadata), it automatically configures CloudWatch EMF metrics - just like the Lambda adapter.

### AWS Auto-Detection (ECS, App Runner, EC2, etc.)

**If running on AWS infrastructure, metrics are automatically enabled with CloudWatch EMF:**

```python
from restmachine import RestApplication
from restmachine.adapters import create_asgi_app

app = RestApplication()

@app.get("/users/{id}")
def get_user(id: str, metrics):
    # Metrics automatically available!
    metrics.add_metric("users.fetched", 1, unit="Count")
    return {"user": id}

# Auto-detects AWS and enables CloudWatch EMF
# Works on: ECS, App Runner, EC2, Lambda (via ASGI), etc.
asgi_app = create_asgi_app(app)

# Run with uvicorn, hypercorn, etc.
# uvicorn module:asgi_app
```

**The adapter automatically detects AWS by checking for:**
- `AWS_REGION` environment variable
- `AWS_EXECUTION_ENV` environment variable (Lambda)
- `ECS_CONTAINER_METADATA_URI` (ECS/Fargate)
- `AWS_DEFAULT_REGION` environment variable

When AWS is detected:
- ✅ CloudWatch EMF publisher is automatically configured
- ✅ Metrics are published to CloudWatch via logs
- ✅ Service name defaults to `asgi-app` (customizable)
- ✅ Namespace defaults to `RestMachine` (customizable)

### Customizing AWS Configuration

```python
from restmachine.adapters import create_asgi_app

# Custom namespace and service name
asgi_app = create_asgi_app(
    app,
    namespace="MyApp/Production",
    service_name="user-api"
)

# High-resolution metrics (1-second)
asgi_app = create_asgi_app(
    app,
    namespace="MyApp/API",
    metrics_resolution=1
)
```

### Environment Variables

Configure via environment variables (useful for different environments):

| Variable | Description | Default |
|----------|-------------|---------|
| `RESTMACHINE_METRICS_ENABLED` | Force enable/disable metrics | Auto-detect AWS |
| `RESTMACHINE_METRICS_NAMESPACE` | CloudWatch namespace | `RestMachine` |
| `RESTMACHINE_SERVICE_NAME` | Service name dimension | `asgi-app` |
| `RESTMACHINE_METRICS_RESOLUTION` | Resolution (1 or 60 seconds) | `60` |

### Non-AWS Environments

**For non-AWS platforms (local dev, GCP, Azure, on-prem), provide a custom publisher:**

```python
from restmachine import RestApplication
from restmachine.adapters import create_asgi_app
from restmachine.metrics import MetricsPublisher

# Example: Prometheus publisher
class PrometheusPublisher(MetricsPublisher):
    def is_enabled(self) -> bool:
        return True

    def publish(self, collector, request=None, response=None, context=None):
        # Publish to Prometheus
        pass

# Explicit custom publisher
asgi_app = create_asgi_app(app, metrics_publisher=PrometheusPublisher())
```

### Disabling Metrics

```python
# Explicitly disable (overrides auto-detection)
asgi_app = create_asgi_app(app, enable_metrics=False)

# Or via environment variable
# RESTMACHINE_METRICS_ENABLED=false
```

### Priority Order

The adapter determines metrics configuration in this priority:

1. **Explicit `enable_metrics` parameter** - Overrides everything
2. **`RESTMACHINE_METRICS_ENABLED` env var** - Overrides auto-detection
3. **AWS auto-detection** - Enables EMF if AWS detected
4. **Default: disabled** - No metrics if not in AWS

### Using with Server Drivers

The auto-detection also works when using RestMachine's server drivers (Uvicorn, Hypercorn):

```python
from restmachine import RestApplication
from restmachine.servers import serve

app = RestApplication()

@app.get("/data")
def get_data(metrics):
    metrics.add_metric("requests", 1)
    return {"data": "value"}

# Auto-detects AWS and enables EMF
# Metrics parameters passed through to ASGIAdapter
serve(
    app,
    server="uvicorn",
    host="0.0.0.0",
    port=8000,
    namespace="MyApp/API",  # Passed to ASGIAdapter
    service_name="api-server"
)
```

## Best Practices

### 1. Use Descriptive Metric Names

```python
# Good
metrics.add_metric("users.created", 1)
metrics.add_metric("db.query.latency", query_time)

# Avoid
metrics.add_metric("count", 1)
metrics.add_metric("time", query_time)
```

### 2. Consistent Dimensions

```python
# Good - consistent dimensions across metrics
metrics.add_dimension("environment", env)
metrics.add_dimension("region", region)
```

### 3. Appropriate Units

```python
# Correct units for clarity
metrics.add_metric("api.latency", 45.2, unit=MetricUnit.Milliseconds)
metrics.add_metric("db.connections", 5, unit=MetricUnit.Count)
metrics.add_metric("response.size", 1024, unit=MetricUnit.Bytes)
```

### 4. Timer Pattern

```python
@app.get("/data")
def fetch_data(metrics):
    metrics.start_timer("operation.total")

    metrics.start_timer("operation.step1")
    step1()
    metrics.stop_timer("operation.step1")

    metrics.start_timer("operation.step2")
    step2()
    metrics.stop_timer("operation.step2")

    metrics.stop_timer("operation.total")
    return result
```

### 5. Don't Over-dimension

```python
# Avoid - too many dimensions
for key, value in request.headers.items():
    metrics.add_dimension(key, value)

# Better - selective dimensions + metadata
metrics.add_dimension("user_type", user.type)
metrics.add_metadata("user_id", user.id)
```

## Disabling Metrics

When metrics are disabled, the collector is still created but publishing is skipped:

```python
# Disable via publisher
adapter = AwsApiGatewayAdapter(app, enable_metrics=False)

# Handler code works unchanged
@app.get("/test")
def handler(metrics):
    # Metrics collected but not published
    metrics.add_metric("requests", 1)
    return {"ok": True}
```

This allows you to keep metrics in code and control publishing via configuration.

## Platform-Specific Documentation

- **[AWS CloudWatch (EMF)](restmachine-aws/guides/metrics.md)** - Auto-configured CloudWatch metrics for Lambda
- **[Logging Configuration](#logging-configuration)** - Custom logging setup
- **[Performance Optimization](advanced/performance.md)** - Metrics overhead and optimization

## Logging Configuration

Metrics use a custom `METRICS` log level (25, between INFO and WARNING).

### Custom Log Level

```python
import logging
from restmachine.metrics import METRICS

# METRICS = 25 (between INFO=20 and WARNING=30)
```

### Manual Configuration

```python
import logging
from restmachine.metrics import METRICS

# Configure metrics logger
metrics_logger = logging.getLogger("restmachine.metrics.emf")
metrics_logger.setLevel(METRICS)

# Add handler
handler = logging.StreamHandler()
handler.setLevel(METRICS)
metrics_logger.addHandler(handler)
```

### Control Metrics Output

```python
# Disable metrics logging
logging.getLogger("restmachine.metrics.emf").setLevel(logging.WARNING)

# Re-enable
logging.getLogger("restmachine.metrics.emf").setLevel(METRICS)
```

### Environment-Specific

```python
import os

if os.environ.get("ENV") == "production":
    logging.getLogger("restmachine.metrics.emf").setLevel(METRICS)
else:
    # Disable in development
    logging.getLogger("restmachine.metrics.emf").setLevel(logging.CRITICAL)
```

## Examples

### E-commerce API

```python
@app.post("/orders")
def create_order(order_data, metrics):
    # Dimensions for grouping
    metrics.add_dimension("order_type", order_data.type)
    metrics.add_dimension("payment_method", order_data.payment)

    # Time validation
    metrics.start_timer("order.validation")
    validate(order_data)
    metrics.stop_timer("order.validation")

    # Time creation
    metrics.start_timer("order.creation")
    order = db.create_order(order_data)
    metrics.stop_timer("order.creation")

    # Business metrics
    metrics.add_metric("orders.created", 1, unit=MetricUnit.Count)
    metrics.add_metric("order.total", order.total, unit=MetricUnit.None)

    # Context metadata
    metrics.add_metadata("order_id", order.id)
    metrics.add_metadata("customer_id", order.customer_id)

    return order
```

### Multi-Region API

```python
@app.get("/data")
def get_data(metrics, region: str):
    # Add region dimension
    metrics.add_dimension("region", region)

    # Track by region
    metrics.start_timer(f"data.fetch.{region}")
    data = fetch_from_region(region)
    metrics.stop_timer(f"data.fetch.{region}")

    # Count and size
    metrics.add_metric("data.fetched", len(data), unit=MetricUnit.Count)
    metrics.add_metric("data.size", sys.getsizeof(data), unit=MetricUnit.Bytes)

    return data
```

## Troubleshooting

### Metrics dependency is None

The metrics dependency is always available. If you're getting None:

1. Check that your platform adapter is properly configured
2. Verify the dependency injection is working

### Publisher not being called

1. Check `publisher.is_enabled()` returns True
2. Verify publisher is passed to adapter
3. Check logging configuration

### Performance concerns

- Metrics collection is lightweight (~0.1-0.5ms per request)
- Publishing happens after response is sent (non-blocking)
- Disable in development to reduce noise

## Related Documentation

- **[AWS CloudWatch Metrics](restmachine-aws/guides/metrics.md)** - CloudWatch EMF configuration
- **[Performance Optimization](advanced/performance.md)** - Overhead and optimization
- **[Dependency Injection](guide/dependency-injection.md)** - Understanding DI in RestMachine

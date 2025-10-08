# CloudWatch Metrics (EMF)

RestMachine AWS automatically publishes metrics to CloudWatch using Embedded Metric Format (EMF). This provides zero-latency metric publishing without additional API calls.

## Overview

When using `AwsApiGatewayAdapter`, metrics are:

- **Automatically enabled** when running in AWS Lambda
- **Published via CloudWatch Logs** using EMF format
- **Zero API calls** - metrics extracted from log JSON
- **No additional IAM permissions needed** (uses existing Lambda log permissions)

## Quick Start

### Auto-Configuration

The simplest setup - just create the adapter:

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

# Metrics automatically configured for CloudWatch EMF
adapter = AwsApiGatewayAdapter(app)

@app.get("/users/{id}")
def get_user(id: str, metrics):
    metrics.add_metric("users.fetched", 1, unit="Count")
    return {"user": id}

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

That's it! Metrics will appear in CloudWatch Logs and CloudWatch Metrics.

### How It Works

1. **Automatic Detection**: Adapter detects AWS Lambda environment
2. **EMF Configuration**: Automatically configures CloudWatch EMF publisher
3. **Log Publishing**: Metrics logged as JSON to stdout
4. **CloudWatch Extraction**: CloudWatch Logs extracts metrics from EMF JSON
5. **Metrics Available**: Metrics appear in CloudWatch Metrics (usually within 1-2 minutes)

## Configuration

### Custom Namespace

Organize metrics in CloudWatch namespaces:

```python
adapter = AwsApiGatewayAdapter(
    app,
    namespace="MyApp/Production"
)
```

Default: `RestMachine`

### Service Name Dimension

Add a service dimension to all metrics:

```python
adapter = AwsApiGatewayAdapter(
    app,
    namespace="MyApp/Production",
    service_name="user-api"
)
```

Default: AWS Lambda function name (from `AWS_LAMBDA_FUNCTION_NAME`)

### High-Resolution Metrics

Enable 1-second granularity (default is 60 seconds):

```python
adapter = AwsApiGatewayAdapter(
    app,
    metrics_resolution=1  # 1-second resolution
)
```

⚠️ High-resolution metrics cost more in CloudWatch.

### Environment Variables

Configure via environment variables (useful for different environments):

| Variable | Description | Default |
|----------|-------------|---------|
| `RESTMACHINE_METRICS_ENABLED` | Enable/disable metrics | `true` |
| `RESTMACHINE_METRICS_NAMESPACE` | CloudWatch namespace | `RestMachine` |
| `RESTMACHINE_SERVICE_NAME` | Service name dimension | Lambda function name |
| `RESTMACHINE_METRICS_RESOLUTION` | Resolution (1 or 60 seconds) | `60` |

Example Lambda environment variables:

```bash
RESTMACHINE_METRICS_NAMESPACE=MyApp/Production
RESTMACHINE_SERVICE_NAME=user-api
RESTMACHINE_METRICS_RESOLUTION=1
```

Priority order:
1. Constructor parameters (highest)
2. Environment variables
3. Defaults (lowest)

### Disabling Metrics

```python
# Via parameter
adapter = AwsApiGatewayAdapter(app, enable_metrics=False)

# Via environment variable
# RESTMACHINE_METRICS_ENABLED=false
```

## Built-in Metrics

Every request automatically includes these metrics:

| Metric | Description | Unit |
|--------|-------------|------|
| `adapter.total_time` | Total request time including conversion | Milliseconds |
| `adapter.event_to_request` | Time to convert API Gateway event to Request | Milliseconds |
| `application.execute` | Time in application/state machine | Milliseconds |
| `adapter.response_conversion` | Time to convert Response to API Gateway format | Milliseconds |
| `errors` | Count of errors (only when errors occur) | Count |

### Default Dimensions

All metrics include:

- `method` - HTTP method (GET, POST, etc.)
- `path` - Request path
- `service` - Service name (if configured)

### Metadata (Non-dimensions)

High-cardinality fields included as metadata:

- `status_code` - HTTP response status
- `error` - Error message (when error occurs)
- `error_type` - Error class name (when error occurs)

## CloudWatch EMF Format

Metrics are logged as JSON in EMF format:

```json
{
  "_aws": {
    "Timestamp": 1634567890000,
    "CloudWatchMetrics": [{
      "Namespace": "MyApp/Production",
      "Dimensions": [["method", "path", "service"]],
      "Metrics": [
        {"Name": "users.fetched", "Unit": "Count"},
        {"Name": "adapter.total_time", "Unit": "Milliseconds"}
      ]
    }]
  },
  "method": "GET",
  "path": "/users/123",
  "service": "user-api",
  "users.fetched": 1,
  "adapter.total_time": 45.2,
  "status_code": 200,
  "request_id": "abc-123"
}
```

This JSON:
- Appears in CloudWatch Logs (searchable, debuggable)
- Automatically creates CloudWatch Metrics
- No PutMetricData API calls needed
- Works within existing Lambda log permissions

## Viewing Metrics in CloudWatch

### CloudWatch Logs

1. Open CloudWatch Logs
2. Navigate to your Lambda function's log group
3. Search for EMF JSON (contains `"_aws"`)
4. View full request context and metrics

### CloudWatch Metrics

1. Open CloudWatch Metrics
2. Select "Custom Namespaces" or your namespace (e.g., "MyApp/Production")
3. Browse by dimensions (method, path, service)
4. Create dashboards and alarms

Metrics appear within 1-2 minutes of being logged.

## Custom Metrics

See the [Core Metrics Guide](../../metrics.md) for:
- Adding custom metrics
- Using timers
- Dimensions vs metadata
- Best practices
- Metric units

## Advanced Topics

### Automatic Logging Configuration

The adapter automatically configures logging:

- Logger: `restmachine.metrics.emf`
- Level: `METRICS` (25, between INFO and WARNING)
- Handler: `StreamHandler` (stdout)

To control logging manually:

```python
import logging
from restmachine.metrics import METRICS

# Disable metrics output
logging.getLogger("restmachine.metrics.emf").setLevel(logging.WARNING)

# Enable debug logging
logging.getLogger("restmachine.metrics.emf").setLevel(logging.DEBUG)
```

### CloudWatch Limits

- **Max 100 metrics per EMF object**: Automatically chunked
- **Max 30 dimensions**: Automatically truncated if exceeded
- **Use metadata for high-cardinality**: Request IDs, user IDs, etc.

### Cost Optimization

1. **Standard resolution (60s)** instead of high-resolution (1s)
2. **Selective metrics** - don't track everything
3. **Appropriate dimensions** - avoid high cardinality
4. **Disable in dev/test** via environment variable

```bash
# Development environment
RESTMACHINE_METRICS_ENABLED=false
```

### Multi-Region Deployments

Add region dimension for multi-region visibility:

```python
import os

@app.get("/data")
def get_data(metrics):
    region = os.environ.get("AWS_REGION", "unknown")
    metrics.add_dimension("region", region)

    # Your logic here
    return data
```

## Troubleshooting

### Metrics not appearing in CloudWatch

1. **Check CloudWatch Logs** - Verify EMF JSON is being logged
   ```bash
   aws logs tail /aws/lambda/your-function --follow
   ```

2. **Check namespace** - Ensure you're looking in the correct namespace

3. **Wait 1-2 minutes** - Metrics aren't instant

4. **Check IAM permissions** - Lambda needs CloudWatch Logs permissions (usually automatic)

### EMF JSON not in logs

1. **Check logging level**:
   ```python
   logging.getLogger("restmachine.metrics.emf").setLevel(METRICS)
   ```

2. **Check metrics are enabled**:
   ```python
   assert adapter.metrics_handler.publisher is not None
   ```

3. **Check environment variable**:
   ```bash
   echo $RESTMACHINE_METRICS_ENABLED  # Should be 'true' or unset
   ```

### Dimension limit errors

```python
# Too many dimensions
metrics.add_dimension("user_id", user_id)  # High cardinality!

# Use metadata instead
metrics.add_metadata("user_id", user_id)  # ✅ Correct
```

### Performance concerns

- **Minimal overhead**: ~0.1-0.5ms per request
- **Non-blocking**: Metrics published after response
- **Disable in dev**: Use environment variable

## Examples

### E-commerce API

```python
@app.post("/orders")
def create_order(order_data, metrics):
    metrics.add_dimension("order_type", order_data.type)
    metrics.add_dimension("payment_method", order_data.payment)

    metrics.start_timer("order.validation")
    validate(order_data)
    metrics.stop_timer("order.validation")

    metrics.start_timer("order.creation")
    order = db.create_order(order_data)
    metrics.stop_timer("order.creation")

    metrics.add_metric("orders.created", 1, unit="Count")
    metrics.add_metric("order.total", order.total, unit="NoUnit")

    # High cardinality - use metadata
    metrics.add_metadata("order_id", order.id)
    metrics.add_metadata("customer_id", order.customer_id)

    return order
```

### API with External Calls

```python
@app.get("/data")
def fetch_data(metrics):
    metrics.start_timer("external.api.call")

    try:
        response = external_api.fetch()
        metrics.add_metric("external.api.success", 1, unit="Count")
    except Exception as e:
        metrics.add_metric("external.api.errors", 1, unit="Count")
        metrics.add_metadata("error", str(e))
        raise
    finally:
        metrics.stop_timer("external.api.call")

    return response
```

## Related Documentation

- **[Core Metrics Guide](../../metrics.md)** - Platform-agnostic features
- **[Lambda Deployment](lambda-deployment.md)** - Deploying to Lambda
- **[Adapter API Reference](../api/adapter.md)** - AwsApiGatewayAdapter details

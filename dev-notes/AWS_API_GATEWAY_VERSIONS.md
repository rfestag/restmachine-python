# AWS API Gateway v1 vs v2 Support

RestMachine's AWS adapter supports both API Gateway payload formats through a single unified adapter.

## Supported Event Types

The `AwsApiGatewayAdapter` automatically detects and handles:

- **API Gateway REST API (v1)** - payload format 1.0
- **API Gateway HTTP API (v2)** - payload format 2.0
- **Application Load Balancer (ALB)** - ALB Lambda targets
- **Lambda Function URLs** - uses v2 format

## Automatic Version Detection

The adapter automatically detects the event type based on the event structure:

```python
# v1 detection: has httpMethod at top level, no version field
{
  "httpMethod": "GET",
  "path": "/users/123",
  "headers": {...},
  "requestContext": {
    "identity": {...}
  }
}

# v2 detection: has version field set to "2.0"
{
  "version": "2.0",
  "rawPath": "/users/123",
  "requestContext": {
    "http": {
      "method": "GET",
      ...
    }
  }
}

# ALB detection: has requestContext.elb
{
  "httpMethod": "GET",
  "path": "/users/123",
  "requestContext": {
    "elb": {
      "targetGroupArn": "..."
    }
  }
}
```

## Key Differences Between v1 and v2

### HTTP Method

**v1:** Top-level `httpMethod` field
```json
{
  "httpMethod": "GET"
}
```

**v2:** Nested in `requestContext.http.method`
```json
{
  "requestContext": {
    "http": {
      "method": "GET"
    }
  }
}
```

### Path

**v1:** Uses `path`
```json
{
  "path": "/my/path"
}
```

**v2:** Uses `rawPath`
```json
{
  "rawPath": "/my/path",
  "rawQueryString": "param=value"
}
```

### Cookies

**v1:** Cookies in `Cookie` header
```json
{
  "headers": {
    "Cookie": "session_id=abc123; user_pref=dark_mode"
  }
}
```

**v2:** Separate `cookies` array (automatically combined into Cookie header by adapter)
```json
{
  "cookies": [
    "session_id=abc123",
    "user_pref=dark_mode"
  ]
}
```

### Client Certificates (mTLS)

**v1:** In `requestContext.identity.clientCert`
```json
{
  "requestContext": {
    "identity": {
      "clientCert": {
        "subjectDN": "CN=client.example.com",
        "issuerDN": "CN=Example CA",
        "serialNumber": "A1B2C3D4E5F6",
        "validity": {
          "notBefore": "...",
          "notAfter": "..."
        }
      }
    }
  }
}
```

**v2:** In `requestContext.authentication.clientCert`
```json
{
  "requestContext": {
    "authentication": {
      "clientCert": {
        "subjectDN": "CN=client.example.com",
        "issuerDN": "CN=Example CA",
        "serialNumber": "A1B2C3D4E5F6",
        "validity": {
          "notBefore": "...",
          "notAfter": "..."
        }
      }
    }
  }
}
```

## Common Features

Both v1 and v2 support the same core features:

- ✅ Path parameters (`pathParameters`)
- ✅ Query string parameters (`queryStringParameters`)
- ✅ Request headers (`headers`)
- ✅ Request body (`body`)
- ✅ Base64 encoding (`isBase64Encoded`)
- ✅ TLS/SSL (always HTTPS)
- ✅ mTLS client certificates

## Usage

No code changes are required to support both versions - the same adapter works for both:

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get("/users/{user_id}")
def get_user(request):
    user_id = request.path_params["user_id"]
    return {"id": user_id}

# Same adapter works for v1, v2, ALB, and Function URLs
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

## Testing

The test suite includes comprehensive tests for both formats:

- `test_aws_lambda_driver.py` - v1 format tests (248 tests)
- `test_aws_apigw_v2.py` - v2 format tests (9 tests)
- `test_aws_alb.py` - ALB format tests (10 tests)

All tests verify that v1 and v2 produce identical results for the same logical request.

## Migration from v1 to v2

If you're migrating from API Gateway REST API (v1) to HTTP API (v2):

1. **No code changes needed** in your RestMachine application
2. The adapter automatically detects and handles the new format
3. All features work identically in both versions
4. Client certificates are extracted from the appropriate location
5. Cookies are properly combined from the cookies array

## Performance

Both v1 and v2 have equivalent performance characteristics:

- Version detection is a simple field check (negligible overhead)
- Parsing logic is optimized for both formats
- No observable performance difference between versions

# RestMachine AWS Adapter

AWS Lambda adapter for RestMachine framework.

## Installation

```bash
pip install restmachine-aws
```

For development:

```bash
# From monorepo root
pip install -e packages/restmachine[dev]
pip install -e packages/restmachine-aws[dev]
```

## Usage

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

app = RestApplication()

@app.get("/hello")
def hello():
    return {"message": "Hello from AWS Lambda!"}

# Create Lambda handler
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    return adapter.handle_event(event, context)
```

## Features

- AWS API Gateway Lambda proxy integration support
- Automatic conversion between API Gateway events and RestMachine requests
- Base64 encoding/decoding for binary content
- Query parameters, path parameters, and headers support
- Full request context available

## Testing

```bash
pytest packages/restmachine-aws/tests/
```

## License

MIT

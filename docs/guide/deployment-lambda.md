# AWS Lambda Deployment

Deploy RestMachine applications to AWS Lambda for serverless, scalable REST APIs. RestMachine provides seamless integration with API Gateway, Application Load Balancer (ALB), and Lambda Function URLs.

## Installation

Install RestMachine with AWS support:

```bash
pip install 'restmachine[aws]'
```

Or install separately:

```bash
pip install restmachine restmachine-aws
```

## Quick Start

Create a Lambda handler:

```python
# lambda_function.py
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

# Create application
app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello from Lambda!"}

@app.get("/users/{user_id}")
def get_user(path_params):
    return {"id": path_params['user_id']}

# Create Lambda handler
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return adapter.handle_event(event, context)
```

## API Gateway Integration

RestMachine automatically detects and handles different API Gateway event formats.

### HTTP API (v2) - Recommended

Modern, cost-effective API Gateway:

```yaml
# SAM template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RestMachineApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
```

### REST API (v1)

Traditional API Gateway:

```yaml
Events:
  RestApi:
    Type: Api  # REST API (v1)
    Properties:
      Path: /{proxy+}
      Method: ANY
```

### Lambda Function URLs

Direct HTTPS endpoint:

```yaml
FunctionUrlConfig:
  AuthType: NONE  # or AWS_IAM
```

### Application Load Balancer

ALB events are detected automatically - no special configuration needed.

## Deployment Methods

### AWS SAM (Recommended)

**template.yaml:**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  MyApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          LOG_LEVEL: INFO
      Events:
        HttpApi:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
```

**requirements.txt:**

```
restmachine[aws]
```

Deploy:

```bash
sam build
sam deploy --guided
```

### Serverless Framework

**serverless.yml:**

```yaml
service: restmachine-api

provider:
  name: aws
  runtime: python3.11
  stage: ${opt:stage, 'dev'}
  region: us-east-1

functions:
  api:
    handler: lambda_function.lambda_handler
    events:
      - httpApi:
          path: /{proxy+}
          method: ANY
```

Deploy:

```bash
serverless deploy --stage prod
```

## Lifecycle Management

### Startup Handlers

Startup handlers run once per Lambda cold start:

```python
app = RestApplication()

@app.on_startup
def database():
    """Initialize database connection (runs once per cold start)."""
    import boto3
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table('users')

@app.get("/users/{user_id}")
def get_user(path_params, database):
    """Use database connection from startup handler."""
    response = database.get_item(Key={'id': path_params['user_id']})
    return response.get('Item', {})
```

**Cold starts:** Startup handlers run once when Lambda initializes a new container.

**Warm invocations:** Subsequent requests reuse the startup handler results.

### Shutdown Handlers

For resource cleanup when Lambda containers terminate, RestMachine supports Lambda Extensions. See the AWS package documentation for advanced Lambda Extension support.

## Database Integration

### DynamoDB

```python
import boto3

@app.on_startup
def dynamodb():
    """Initialize DynamoDB client."""
    table_name = os.getenv('TABLE_NAME', 'users')
    return boto3.resource('dynamodb').Table(table_name)

@app.get("/items/{item_id}")
def get_item(path_params, dynamodb):
    response = dynamodb.get_item(Key={'id': path_params['item_id']})
    return response.get('Item', {})

@app.post("/items")
def create_item(json_body, dynamodb):
    dynamodb.put_item(Item=json_body)
    return json_body, 201
```

### RDS with Secrets Manager

```python
import boto3
import json
import psycopg2

@app.on_startup
def database():
    """Get RDS credentials and connect."""
    secrets = boto3.client('secretsmanager')
    secret = secrets.get_secret_value(SecretId='rds-credentials')
    creds = json.loads(secret['SecretString'])

    return psycopg2.connect(
        host=creds['host'],
        database=creds['database'],
        user=creds['username'],
        password=creds['password']
    )
```

## Configuration

### Environment Variables

```python
import os

TABLE_NAME = os.getenv('TABLE_NAME', 'default-table')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

@app.on_startup
def dynamodb():
    import boto3
    return boto3.resource('dynamodb').Table(TABLE_NAME)
```

**SAM template:**

```yaml
Environment:
  Variables:
    TABLE_NAME: !Ref MyDynamoDBTable
    LOG_LEVEL: INFO
```

## Local Testing

### SAM Local

Test locally with SAM CLI:

```bash
# Start local API
sam local start-api

# Test endpoint
curl http://localhost:3000/users/123
```

### Direct Invocation

```python
# test_lambda.py
from lambda_function import lambda_handler

def test_get_user():
    event = {
        "version": "2.0",
        "routeKey": "GET /users/{user_id}",
        "rawPath": "/users/123",
        "pathParameters": {"user_id": "123"},
        "requestContext": {
            "http": {"method": "GET", "path": "/users/123"}
        }
    }

    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
```

## Complete Example

```python
# lambda_function.py
import os
import logging
import boto3
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Create application
app = RestApplication()

# Startup handler
@app.on_startup
def dynamodb():
    """Initialize DynamoDB (runs once per cold start)."""
    table_name = os.getenv('TABLE_NAME', 'users')
    logger.info(f"Connecting to table: {table_name}")
    return boto3.resource('dynamodb').Table(table_name)

# Validation
class UserCreate(BaseModel):
    id: str
    name: str

@app.validates
def user_create(json_body) -> UserCreate:
    return UserCreate.model_validate(json_body)

# Routes
@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/users/{user_id}")
def get_user(path_params, dynamodb):
    try:
        response = dynamodb.get_item(Key={'id': path_params['user_id']})
        item = response.get('Item')
        if not item:
            return {"error": "User not found"}, 404
        return item
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": "Internal server error"}, 500

@app.post("/users")
def create_user(user_create: UserCreate, dynamodb):
    try:
        dynamodb.put_item(Item=user_create.model_dump())
        return user_create.model_dump(), 201
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": "Internal server error"}, 500

# Create adapter and handler
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return adapter.handle_event(event, context)
```

**Complete SAM template:**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub users-${Environment}
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH

  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          TABLE_NAME: !Ref UsersTable
          LOG_LEVEL: INFO
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref UsersTable
      Events:
        HttpApi:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY

Outputs:
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub 'https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com'
```

## Performance Optimization

### Lambda Configuration

Configure memory (more memory = more CPU):

```yaml
MemorySize: 1024  # MB (128-10240)
Timeout: 30       # seconds (1-900)
```

### Cold Start Optimization

1. **Use startup handlers** to initialize connections once
2. **Package only needed dependencies** - smaller packages load faster
3. **Use Lambda Layers** for dependencies
4. **Keep functions warm** with provisioned concurrency (for critical paths)

### Reuse Connections

```python
# Good - connection reused across invocations
@app.on_startup
def database():
    return boto3.resource('dynamodb')

# Bad - creates new connection each request
@app.get("/users")
def get_users():
    db = boto3.resource('dynamodb')  # Don't do this!
```

## Best Practices

### 1. Use Environment Variables

```python
TABLE_NAME = os.getenv('TABLE_NAME')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

### 2. Implement Health Checks

```python
@app.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}
```

### 3. Log Structured Data

```python
import json
logger.info(json.dumps({
    "event": "user_created",
    "user_id": user_id
}))
```

### 4. Handle Errors Gracefully

```python
try:
    result = database.query(...)
    return result
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    return {"error": "Internal server error"}, 500
```

### 5. Use IAM for Permissions

Grant least-privilege permissions:

```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  - Statement:
      - Effect: Allow
        Action: secretsmanager:GetSecretValue
        Resource: !Ref MySecret
```

## Monitoring

### CloudWatch Logs

Logs automatically sent to CloudWatch:

```python
import logging
logger = logging.getLogger()
logger.info("Processing request")
```

### CloudWatch Metrics

Track:
- Invocations
- Duration
- Errors
- Throttles
- Cold starts

### X-Ray Tracing

Enable in SAM:

```yaml
Tracing: Active
```

## Next Steps

- [ASGI Deployment →](deployment-asgi.md) - Deploy with ASGI servers
- [Lifecycle Management →](../advanced/lifecycle.md) - Advanced startup/shutdown patterns
- [Performance →](../advanced/performance.md) - Optimization techniques

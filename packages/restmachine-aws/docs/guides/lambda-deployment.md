# Deploying to AWS Lambda

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

### Basic Lambda Handler

Create a Lambda handler in `lambda_function.py`:

```python
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

# Create application
app = RestApplication()

@app.get("/")
def home():
    return {"message": "Hello from Lambda!"}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": f"User {user_id}"}

# Create Lambda handler
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return adapter.handle_event(event, context)
```

### Deploy with AWS SAM

**template.yaml:**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RestMachineApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Timeout: 30
      MemorySize: 512
      Events:
        ApiEvent:
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

## API Gateway Integration

RestMachine supports all API Gateway event formats automatically.

### HTTP API (v2) - Recommended

Modern, cost-effective API Gateway with payload format 2.0:

```yaml
# SAM template
Events:
  HttpApi:
    Type: HttpApi  # HTTP API (v2)
    Properties:
      Path: /{proxy+}
      Method: ANY
```

**Event structure:**

```python
{
    "version": "2.0",
    "routeKey": "GET /users/{user_id}",
    "rawPath": "/users/123",
    "headers": {"accept": "application/json"},
    "pathParameters": {"user_id": "123"},
    "requestContext": {
        "http": {
            "method": "GET",
            "path": "/users/123"
        }
    }
}
```

### REST API (v1)

Traditional API Gateway with payload format 1.0:

```yaml
# SAM template
Events:
  RestApi:
    Type: Api  # REST API (v1)
    Properties:
      Path: /{proxy+}
      Method: ANY
```

**Event structure:**

```python
{
    "httpMethod": "GET",
    "path": "/users/123",
    "headers": {"Accept": "application/json"},
    "pathParameters": {"user_id": "123"},
    "requestContext": {
        "requestId": "..."
    }
}
```

### Lambda Function URLs

Direct HTTPS endpoint for your Lambda function:

```yaml
# SAM template
FunctionUrlConfig:
  AuthType: NONE  # or AWS_IAM
```

**Function URL uses HTTP API (v2) format automatically.**

### Application Load Balancer (ALB)

Integrate with Application Load Balancer:

```yaml
# SAM template (manually configure ALB target group)
```

ALB events are detected automatically:

```python
{
    "requestContext": {
        "elb": {  # ALB indicator
            "targetGroupArn": "..."
        }
    },
    "httpMethod": "GET",
    "path": "/users/123",
    # ...
}
```

## Deployment Methods

### AWS SAM (Serverless Application Model)

**Full example with dependencies:**

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    MemorySize: 512
    Runtime: python3.11
    Environment:
      Variables:
        LOG_LEVEL: INFO

Resources:
  MyApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_function.lambda_handler
      Layers:
        - !Ref DependenciesLayer
      Events:
        HttpApi:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY

  DependenciesLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: restmachine-dependencies
      ContentUri: dependencies/
      CompatibleRuntimes:
        - python3.11
    Metadata:
      BuildMethod: python3.11
```

Build and deploy:

```bash
# Build
sam build

# Deploy
sam deploy --guided

# Test locally
sam local start-api
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
    environment:
      LOG_LEVEL: INFO

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
```

Deploy:

```bash
serverless deploy --stage prod
```

### AWS CDK (Python)

```python
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigw,
)
from constructs import Construct

class RestMachineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Lambda function
        handler = lambda_.Function(
            self, "RestMachineFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda"),
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(30),
            memory_size=512,
        )

        # HTTP API
        api = apigw.HttpApi(
            self, "RestMachineApi",
            default_integration=apigw_integrations.HttpLambdaIntegration(
                "Integration",
                handler
            )
        )
```

Deploy:

```bash
cdk deploy
```

### Manual Deployment (ZIP)

Create deployment package:

```bash
# Install dependencies
pip install -r requirements.txt -t package/

# Copy application code
cp lambda_function.py package/

# Create ZIP
cd package && zip -r ../lambda.zip . && cd ..

# Deploy
aws lambda create-function \
  --function-name restmachine-api \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT:role/lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda.zip \
  --timeout 30 \
  --memory-size 512
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
    table = dynamodb.Table('users')
    return table

@app.get("/users/{user_id}")
def get_user(user_id: str, database):
    """Use database connection from startup handler."""
    response = database.get_item(Key={'id': user_id})
    return response.get('Item', {})
```

**Cold starts:** Startup handlers run once when Lambda initializes a new container.

**Warm invocations:** Subsequent requests reuse the same startup handler results.

### Shutdown Handlers

Shutdown handlers clean up resources when the Lambda container terminates.

#### Option 1: Lambda Extension (Recommended)

Use the RestMachine Lambda Extension for automatic shutdown:

**extensions/restmachine-shutdown:**

```python
#!/usr/bin/env python3
from restmachine_aws.extension import main

if __name__ == "__main__":
    main()
```

Make it executable:

```bash
chmod +x extensions/restmachine-shutdown
```

**SAM template:**

```yaml
MyApi:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: .
    Handler: lambda_function.lambda_handler
    # Extension is automatically included from extensions/
```

The extension monitors Lambda lifecycle and calls shutdown handlers on container termination.

#### Option 2: Manual Shutdown

For simple cleanup, use context:

```python
@app.on_shutdown
def close_connections(database):
    """Called when Lambda container terminates."""
    database.close()

# The AwsApiGatewayAdapter automatically runs startup handlers
# Extensions handle shutdown automatically
```

## Database Integration

### DynamoDB

```python
import boto3

app = RestApplication()

@app.on_startup
def dynamodb():
    """Initialize DynamoDB client."""
    return boto3.resource('dynamodb').Table('MyTable')

@app.get("/items/{item_id}")
def get_item(item_id: str, dynamodb):
    response = dynamodb.get_item(Key={'id': item_id})
    return response.get('Item', {})

@app.post("/items")
def create_item(json_body: dict, dynamodb):
    dynamodb.put_item(Item=json_body)
    return json_body, 201
```

### RDS with Secret Manager

```python
import boto3
import json
import psycopg2

@app.on_startup
def database():
    """Get RDS credentials and connect."""
    # Get secret
    secrets = boto3.client('secretsmanager')
    secret = secrets.get_secret_value(SecretId='rds-credentials')
    creds = json.loads(secret['SecretString'])

    # Connect to RDS
    conn = psycopg2.connect(
        host=creds['host'],
        database=creds['database'],
        user=creds['username'],
        password=creds['password']
    )
    return conn

@app.on_shutdown
def close_database(database):
    """Close connection on shutdown."""
    database.close()
```

## Environment Configuration

### Using Environment Variables

```python
import os

app = RestApplication()

# Get config from environment
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

### Using AWS Systems Manager Parameter Store

```python
import boto3

@app.on_startup
def config():
    """Load configuration from Parameter Store."""
    ssm = boto3.client('ssm')
    params = ssm.get_parameters_by_path(
        Path='/myapp/',
        Recursive=True,
        WithDecryption=True
    )
    return {p['Name']: p['Value'] for p in params['Parameters']}
```

## Local Testing

### SAM Local

Test locally with SAM CLI:

```bash
# Start local API
sam local start-api

# Test specific endpoint
curl http://localhost:3000/users/123
```

### Direct Invocation

Test the handler directly:

```python
# test_lambda.py
from lambda_function import lambda_handler

def test_get_user():
    event = {
        "version": "2.0",
        "routeKey": "GET /users/{user_id}",
        "rawPath": "/users/123",
        "headers": {"accept": "application/json"},
        "pathParameters": {"user_id": "123"},
        "requestContext": {
            "http": {"method": "GET", "path": "/users/123"}
        }
    }

    response = lambda_handler(event, None)

    assert response['statusCode'] == 200
    import json
    body = json.loads(response['body'])
    assert body['id'] == '123'
```

Run tests:

```bash
pytest test_lambda.py
```

## Complete Production Example

```python
# lambda_function.py
import os
import logging
import boto3
from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Create application
app = RestApplication()

@app.on_startup
def dynamodb():
    """Initialize DynamoDB client (runs once per cold start)."""
    table_name = os.getenv('TABLE_NAME', 'users')
    logger.info(f"Connecting to DynamoDB table: {table_name}")
    return boto3.resource('dynamodb').Table(table_name)

@app.on_shutdown
def cleanup(dynamodb):
    """Cleanup on Lambda container termination."""
    logger.info("Shutting down Lambda container")
    # DynamoDB client doesn't need explicit cleanup
    # but you can close other connections here

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/users/{user_id}")
def get_user(user_id: str, dynamodb):
    """Get user from DynamoDB."""
    try:
        response = dynamodb.get_item(Key={'id': user_id})
        item = response.get('Item')
        if not item:
            return {"error": "User not found"}, 404
        return item
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return {"error": "Internal server error"}, 500

@app.post("/users")
def create_user(json_body: dict, dynamodb):
    """Create user in DynamoDB."""
    try:
        # Validate required fields
        if 'id' not in json_body or 'name' not in json_body:
            return {"error": "Missing required fields"}, 400

        dynamodb.put_item(Item=json_body)
        return json_body, 201
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return {"error": "Internal server error"}, 500

@app.put("/users/{user_id}")
def update_user(user_id: str, json_body: dict, dynamodb):
    """Update user in DynamoDB."""
    try:
        # Check if user exists
        response = dynamodb.get_item(Key={'id': user_id})
        if 'Item' not in response:
            return {"error": "User not found"}, 404

        # Update user
        json_body['id'] = user_id
        dynamodb.put_item(Item=json_body)
        return json_body
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return {"error": "Internal server error"}, 500

@app.delete("/users/{user_id}")
def delete_user(user_id: str, dynamodb):
    """Delete user from DynamoDB."""
    try:
        dynamodb.delete_item(Key={'id': user_id})
        return "", 204
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return {"error": "Internal server error"}, 500

# Create adapter and handler
adapter = AwsApiGatewayAdapter(app)

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    return adapter.handle_event(event, context)
```

**SAM template for production:**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Globals:
  Function:
    Timeout: 30
    MemorySize: 512
    Runtime: python3.11
    Environment:
      Variables:
        LOG_LEVEL: !If [IsProd, WARNING, INFO]

Conditions:
  IsProd: !Equals [!Ref Environment, prod]

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
      Environment:
        Variables:
          TABLE_NAME: !Ref UsersTable
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

**Memory:** More memory = more CPU:

```yaml
MemorySize: 1024  # MB (128-10240)
Timeout: 30       # seconds (1-900)
```

**Provisioned Concurrency** for consistent performance:

```yaml
ProvisionedConcurrencyConfig:
  ProvisionedConcurrentExecutions: 5
```

### Cold Start Optimization

1. **Use startup handlers** to initialize connections once
2. **Package only what you need** - smaller packages load faster
3. **Use Lambda Layers** for dependencies
4. **Keep functions warm** with scheduled pings (dev only)

### Reuse Connections

```python
# Good - reuse connection across invocations
@app.on_startup
def database():
    return boto3.resource('dynamodb')

# Bad - creates new connection each request
@app.get("/users")
def get_users():
    db = boto3.resource('dynamodb')  # Don't do this!
    # ...
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
    "user_id": user_id,
    "timestamp": datetime.now().isoformat()
}))
```

### 4. Handle Errors Gracefully

```python
@app.get("/users/{user_id}")
def get_user(user_id: str, dynamodb):
    try:
        response = dynamodb.get_item(Key={'id': user_id})
        return response.get('Item', {})
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

Logs are automatically sent to CloudWatch:

```python
import logging
logger = logging.getLogger()
logger.info("Processing request")
```

### CloudWatch Metrics

Track Lambda metrics:
- Invocations
- Duration
- Errors
- Throttles
- Cold starts

### X-Ray Tracing

Enable tracing in SAM:

```yaml
Tracing: Active
```

Add instrumentation:

```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

@app.get("/users/{user_id}")
@xray_recorder.capture('get_user')
def get_user(user_id: str, dynamodb):
    # Traced automatically
    pass
```

## Troubleshooting

### Cold Start Issues

Check initialization time:

```python
import time
start = time.time()

@app.on_startup
def database():
    # Log initialization time
    init_time = time.time() - start
    logger.info(f"Initialized in {init_time:.2f}s")
    return boto3.resource('dynamodb')
```

### Timeout Errors

Increase timeout or optimize code:

```yaml
Timeout: 60  # Increase from 30
```

### Permission Errors

Check IAM role has required permissions:

```bash
aws lambda get-function --function-name my-function
```

## Next Steps

- Learn about [Uvicorn deployment](../../guide/deployment/uvicorn.md) for local development
- Explore [Hypercorn deployment](../../guide/deployment/hypercorn.md) for HTTP/2 support
- Read about [Lifecycle Handlers](../../advanced/lifecycle.md) for advanced startup/shutdown patterns

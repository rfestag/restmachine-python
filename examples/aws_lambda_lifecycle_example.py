"""
Complete AWS Lambda example with startup and shutdown lifecycle handlers.

This example demonstrates:
- Startup handlers that run during cold start (database connection, API client)
- Shutdown handlers that run on container termination (cleanup, connection close)
- Dependency injection of startup resources into route handlers
- Lambda Extension setup for automatic shutdown handling

Directory structure for deployment:
    my-lambda/
    ├── lambda_function.py          # This file
    ├── extensions/
    │   └── restmachine-shutdown    # Generated with: python -m restmachine_aws create-extension
    └── requirements.txt
        restmachine
        restmachine-aws

Environment setup:
    Cold start → on_startup runs → cached as session dependencies
    Warm starts → reuse cached dependencies
    Shutdown → Extension calls on_shutdown → cleanup

"""

from restmachine import RestApplication
from restmachine_aws import AwsApiGatewayAdapter

# Create the REST application
app = RestApplication()


# --- Startup Handlers (Cold Start Initialization) ---

@app.on_startup
def database():
    """
    Initialize database connection during Lambda cold start.

    This runs ONCE when the container starts and the connection is reused
    across all invocations in the same container (warm starts).

    In production, replace with real database connection:
        import pymysql
        return pymysql.connect(
            host='db.example.com',
            user='lambda',
            password=os.environ['DB_PASSWORD'],
            database='myapp'
        )
    """
    print("[STARTUP] Opening database connection...")
    # Simulate database connection
    connection = {
        "type": "mock_database",
        "host": "db.example.com",
        "pool_size": 10,
        "connected": True
    }
    print(f"[STARTUP] Database connected: {connection['host']}")
    return connection


@app.on_startup
def api_client():
    """
    Initialize external API client during cold start.

    Like database connections, API clients with connection pools should
    be created once and reused across invocations.

    In production, replace with real HTTP client:
        import requests
        session = requests.Session()
        session.headers.update({'Authorization': f"Bearer {os.environ['API_KEY']}"})
        return session
    """
    print("[STARTUP] Creating API client...")
    # Simulate API client
    client = {
        "type": "mock_api_client",
        "base_url": "https://api.example.com",
        "timeout": 30,
        "retry": 3
    }
    print(f"[STARTUP] API client ready: {client['base_url']}")
    return client


# --- Shutdown Handlers (Container Termination Cleanup) ---

@app.on_shutdown
def close_database(database):
    """
    Close database connection on shutdown.

    This runs when the Lambda container is terminating. The Lambda Extension
    (extensions/restmachine-shutdown) calls app.shutdown_sync() which triggers
    this handler.

    IMPORTANT: This only runs if you deploy the Lambda Extension!

    Startup dependencies (database, api_client) can be injected into shutdown
    handlers for proper cleanup.
    """
    print("[SHUTDOWN] Closing database connection...")
    # In production:
    # database.close()
    database["connected"] = False
    print("[SHUTDOWN] Database connection closed")


@app.on_shutdown
def cleanup_api_client(api_client):
    """
    Cleanup API client on shutdown.

    Close any open connections, flush buffers, etc.
    """
    print("[SHUTDOWN] Cleaning up API client...")
    # In production:
    # api_client.close()
    print("[SHUTDOWN] API client cleaned up")


@app.on_shutdown
def final_cleanup():
    """
    Final cleanup tasks.

    Shutdown handlers run in registration order. This runs last to perform
    any final cleanup tasks that don't depend on other resources.
    """
    print("[SHUTDOWN] Final cleanup complete")


# --- Route Handlers (Injected with Startup Dependencies) ---

@app.get("/")
def health_check(database, api_client):
    """
    Health check endpoint that uses startup dependencies.

    The database and api_client parameters are automatically injected from
    the startup handlers. These are the same instances across all warm invocations.
    """
    return {
        "status": "healthy",
        "database": {
            "connected": database.get("connected"),
            "host": database.get("host")
        },
        "api_client": {
            "base_url": api_client.get("base_url"),
            "ready": True
        }
    }


@app.get("/users/{user_id}")
def get_user(user_id, database):
    """
    Get user from database.

    The database parameter is injected from the startup handler.
    """
    # In production, query the database:
    # cursor = database.cursor()
    # cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    # user = cursor.fetchone()

    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
        "source": "database"
    }


@app.get("/external/data")
def get_external_data(api_client):
    """
    Fetch data from external API.

    The api_client parameter is injected from the startup handler.
    """
    # In production, use the API client:
    # response = api_client.get('/data')
    # return response.json()

    return {
        "data": "external API data",
        "api_endpoint": api_client.get("base_url"),
        "status": "success"
    }


# --- AWS Lambda Configuration ---

# Startup handlers execute automatically when adapter is initialized (cold start)
adapter = AwsApiGatewayAdapter(app)


def lambda_handler(event, context):
    """
    AWS Lambda handler function.

    Flow:
    1. Cold start:
       - adapter = AwsApiGatewayAdapter(app) triggers startup handlers
       - database() and api_client() run, values cached
       - First request processed with injected dependencies

    2. Warm starts:
       - Cached dependencies reused (no re-execution)
       - Requests processed immediately

    3. Shutdown (with extension):
       - Lambda sends SHUTDOWN event to extension
       - Extension calls app.shutdown_sync()
       - close_database(), cleanup_api_client(), final_cleanup() run
       - Container terminates

    Args:
        event: API Gateway proxy event
        context: Lambda context object

    Returns:
        API Gateway proxy response
    """
    return adapter.handle_event(event, context)


# --- Deployment Instructions ---

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║  RestMachine AWS Lambda Lifecycle Example                                 ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    This example demonstrates complete lifecycle management with startup and
    shutdown handlers.

    📦 DEPLOYMENT STEPS:

    1. Generate the Lambda Extension:

        python -m restmachine_aws create-extension

       This creates: extensions/restmachine-shutdown

    2. Directory Structure:

        my-lambda/
        ├── lambda_function.py          # This file (renamed)
        ├── extensions/
        │   └── restmachine-shutdown    # Generated extension
        └── requirements.txt

    3. Requirements (requirements.txt):

        restmachine
        restmachine-aws

    4. Deploy to Lambda:

        # Using AWS SAM
        sam build
        sam deploy

        # Using Serverless Framework
        serverless deploy

        # Using AWS CLI
        zip -r function.zip .
        aws lambda update-function-code --function-name my-function --zip-file fileb://function.zip

    5. Verify Extension is Running:

        Check CloudWatch Logs for:
        - "[STARTUP] Opening database connection..."
        - "[SHUTDOWN] Closing database connection..."

    🔧 CUSTOMIZATION:

    If your handler module is not "lambda_function" or app variable is not "app":

        export RESTMACHINE_HANDLER_MODULE=my_module
        export RESTMACHINE_APP_NAME=application

    Or edit extensions/restmachine-shutdown to pass custom values to main().

    📚 MORE INFO:

        AWS Lambda Extensions:
        https://docs.aws.amazon.com/lambda/latest/dg/runtimes-extensions-api.html

        RestMachine Documentation:
        https://github.com/rfestag/restmachine-python

    """)

"""
AWS Lambda Extension for automatic shutdown handler execution.

This module provides a Lambda Extension that registers with the AWS Lambda Runtime
Extensions API and calls app.shutdown_sync() when the Lambda container is terminating.

Lambda Extensions are external processes that run alongside your Lambda function and
can hook into the Lambda lifecycle (INIT, INVOKE, SHUTDOWN). This extension listens
for SHUTDOWN events and ensures cleanup handlers are executed before container termination.

Example:
    Create an extension script at extensions/restmachine-shutdown:

    ```python
    #!/usr/bin/env python3
    from restmachine_aws.extension import main
    if __name__ == "__main__":
        main()
    ```

    Then make it executable and deploy with your Lambda:
    ```bash
    chmod +x extensions/restmachine-shutdown
    ```

See Also:
    AWS Lambda Extensions API:
    https://docs.aws.amazon.com/lambda/latest/dg/runtimes-extensions-api.html
"""

import json
import logging
import os
import sys
from typing import Any, Optional, cast
from urllib import request

logger = logging.getLogger(__name__)


class ShutdownExtension:
    """
    AWS Lambda Extension that executes shutdown handlers on container termination.

    This extension registers with the Lambda Runtime Extensions API, waits for
    SHUTDOWN events, and calls the RestMachine application's shutdown_sync() method.

    The extension runs as a separate process from your Lambda handler, monitoring
    the Lambda lifecycle and ensuring cleanup code runs before the container terminates.

    Example:
        ```python
        from restmachine_aws.extension import ShutdownExtension

        extension = ShutdownExtension(
            handler_module="lambda_function",
            app_name="app"
        )
        extension.run()
        ```

    Args:
        handler_module: Python module containing the Lambda handler (default: "lambda_function")
        app_name: Name of the RestApplication variable in the handler module (default: "app")
    """

    def __init__(self, handler_module: str = "lambda_function", app_name: str = "app"):
        """
        Initialize the Lambda Extension.

        Args:
            handler_module: Module name where the RestApplication is defined
            app_name: Variable name of the RestApplication instance
        """
        self.handler_module = handler_module
        self.app_name = app_name
        self.extension_id: Optional[str] = None

        # Get Lambda Runtime API endpoint from environment
        self.runtime_api = os.environ.get("AWS_LAMBDA_RUNTIME_API")
        if not self.runtime_api:
            raise RuntimeError(
                "AWS_LAMBDA_RUNTIME_API environment variable not set. "
                "This extension must be run within an AWS Lambda environment."
            )

    def register(self) -> str:
        """
        Register this extension with the Lambda Runtime Extensions API.

        Sends a POST request to the Extensions API to register for SHUTDOWN events.
        The Lambda runtime will send a SHUTDOWN event when the container is about
        to terminate, allowing cleanup handlers to execute.

        Returns:
            Extension ID assigned by the Lambda runtime

        Raises:
            RuntimeError: If registration fails
        """
        url = f"http://{self.runtime_api}/2020-01-01/extension/register"

        payload = {"events": ["SHUTDOWN"]}
        data = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url,
            data=data,
            headers={
                "Lambda-Extension-Name": "restmachine-shutdown",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            # nosec B310: Lambda Extensions API is only accessible over localhost HTTP
            with request.urlopen(req) as response:  # nosec B310
                extension_id = response.headers.get("Lambda-Extension-Identifier")
                if not extension_id:
                    raise RuntimeError("Lambda runtime did not return an Extension ID")
                self.extension_id = extension_id
                logger.info(f"Extension registered with ID: {self.extension_id}")
                return self.extension_id
        except Exception as e:
            raise RuntimeError(f"Failed to register extension: {e}") from e

    def wait_for_event(self) -> dict:
        """
        Wait for the next lifecycle event from Lambda.

        This is a blocking call that waits for the Lambda runtime to send the next
        event. For SHUTDOWN-only extensions, this will block until the container
        is terminating.

        Returns:
            Event dictionary containing eventType and other event details

        Raises:
            RuntimeError: If event retrieval fails or extension is not registered
        """
        if not self.extension_id:
            raise RuntimeError("Extension must be registered before waiting for events")

        url = f"http://{self.runtime_api}/2020-01-01/extension/event/next"

        req = request.Request(
            url,
            headers={"Lambda-Extension-Identifier": self.extension_id},
            method="GET",
        )

        try:
            # nosec B310: Lambda Extensions API is only accessible over localhost HTTP
            with request.urlopen(req) as response:  # nosec B310
                event = cast(dict[Any, Any], json.loads(response.read()))
                return event
        except Exception as e:
            raise RuntimeError(f"Failed to get next event: {e}") from e

    def load_app(self) -> Any:
        """
        Load the RestMachine application from the handler module.

        Imports the handler module and retrieves the RestApplication instance.
        The Lambda task root is added to sys.path to ensure imports work correctly.

        Returns:
            The RestMachine application instance

        Raises:
            ImportError: If the handler module or app variable cannot be found
        """
        # Add Lambda task root to Python path
        task_root = os.environ.get("LAMBDA_TASK_ROOT", ".")
        if task_root not in sys.path:
            sys.path.insert(0, task_root)

        try:
            # Import the handler module
            handler_module = __import__(self.handler_module)
            logger.info(f"Imported module: {self.handler_module}")

            # Get the app instance
            if not hasattr(handler_module, self.app_name):
                raise AttributeError(
                    f"Module '{self.handler_module}' has no attribute '{self.app_name}'. "
                    f"Available attributes: {dir(handler_module)}"
                )

            app = getattr(handler_module, self.app_name)
            logger.info(f"Loaded app from {self.handler_module}.{self.app_name}")
            return app

        except ImportError as e:
            raise ImportError(
                f"Could not import handler module '{self.handler_module}': {e}"
            ) from e

    def run(self):
        """
        Main extension loop.

        Performs the following steps:
        1. Register with Lambda Extensions API
        2. Load the RestMachine application
        3. Wait for lifecycle events
        4. On SHUTDOWN event, call app.shutdown_sync()

        This method blocks until a SHUTDOWN event is received or an error occurs.

        Raises:
            Exception: If any step in the extension lifecycle fails
        """
        try:
            # Step 1: Register extension
            logger.info("Registering extension...")
            self.register()

            # Step 2: Load application
            logger.info("Loading application...")
            app = self.load_app()

            # Verify app has shutdown_sync method
            if not hasattr(app, "shutdown_sync"):
                logger.warning(
                    f"Application {self.app_name} does not have shutdown_sync() method. "
                    "No shutdown handlers will be called."
                )
                # Still wait for SHUTDOWN to prevent extension from exiting early
                app = None

            # Step 3: Wait for events
            logger.info("Extension ready, waiting for events...")
            while True:
                event = self.wait_for_event()
                event_type = event.get("eventType")

                logger.info(f"Received event: {event_type}")

                if event_type == "SHUTDOWN":
                    # Step 4: Execute shutdown handlers
                    if app and hasattr(app, "shutdown_sync"):
                        logger.info("Executing shutdown handlers...")
                        try:
                            app.shutdown_sync()
                            logger.info("Shutdown handlers completed successfully")
                        except Exception as e:
                            logger.error(f"Error in shutdown handlers: {e}", exc_info=True)
                    else:
                        logger.info("No shutdown handlers to execute")

                    # Exit after shutdown
                    logger.info("Extension shutting down")
                    break

        except Exception as e:
            logger.error(f"Extension error: {e}", exc_info=True)
            raise


def main(handler_module: str = "lambda_function", app_name: str = "app"):
    """
    Entry point for the Lambda Extension script.

    This function configures logging and runs the extension. It's designed to be
    called from an extension script placed in the extensions/ directory.

    Args:
        handler_module: Module containing the Lambda handler (default: "lambda_function")
        app_name: Name of the RestApplication variable (default: "app")

    Example extension script (extensions/restmachine-shutdown):
        ```python
        #!/usr/bin/env python3
        from restmachine_aws.extension import main

        if __name__ == "__main__":
            main()
        ```

    Environment Variables:
        RESTMACHINE_HANDLER_MODULE: Override the handler module name
        RESTMACHINE_APP_NAME: Override the app variable name
        RESTMACHINE_LOG_LEVEL: Set logging level (default: INFO)
    """
    # Configure logging
    log_level = os.environ.get("RESTMACHINE_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="[%(name)s] %(levelname)s: %(message)s",
    )

    # Allow override via environment variables
    handler_module = os.environ.get("RESTMACHINE_HANDLER_MODULE", handler_module)
    app_name = os.environ.get("RESTMACHINE_APP_NAME", app_name)

    logger.info("Starting RestMachine shutdown extension")
    logger.info(f"Handler module: {handler_module}")
    logger.info(f"App name: {app_name}")

    # Run the extension
    extension = ShutdownExtension(handler_module=handler_module, app_name=app_name)
    extension.run()


if __name__ == "__main__":
    main()

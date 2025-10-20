"""
CLI extension plugin for AWS Lambda/API Gateway.

Provides AWS Lambda-specific commands and utilities.
"""

from typing import Optional
import click


class AwsCliExtension:
    """CLI extension plugin for AWS Lambda."""

    def get_name(self) -> str:
        """Return extension name."""
        return "aws"

    def get_generate_commands(self) -> Optional[click.Group]:
        """
        Return commands to add under 'generate'.

        Provides:
        - lambda-extension: Generate Lambda extension for shutdown handling
        """
        # Create a temporary group to hold our commands
        @click.group()
        def temp_group():
            pass

        @temp_group.command(name="lambda-extension")
        @click.option(
            "-o", "--output",
            default=None,
            help="Output path for extension script (default: extensions/restmachine-shutdown)"
        )
        def lambda_extension(output: Optional[str]):
            """
            Generate a Lambda extension script for shutdown handling.

            This extension calls app.shutdown_sync() when the Lambda container terminates.
            It runs as a separate process alongside your Lambda function and listens for
            SHUTDOWN events from the Lambda Runtime API.

            The extension will be installed in your project's extensions/ directory.

            Environment Variables (configure in Lambda):
                RESTMACHINE_HANDLER_MODULE: Module containing the handler (default: lambda_function)
                RESTMACHINE_APP_NAME: Variable name of RestApplication (default: app)
                RESTMACHINE_LOG_LEVEL: Logging level (default: INFO)

            See: https://docs.aws.amazon.com/lambda/latest/dg/runtimes-extensions-api.html
            """
            # Import here to avoid circular dependency
            from restmachine_aws.__main__ import create_extension

            # Create an args object similar to argparse.Namespace
            class Args:
                output: Optional[str]

            args = Args()
            args.output = output

            # Use the existing create_extension function
            create_extension(args)  # type: ignore[arg-type]

        return temp_group

    def get_top_level_commands(self) -> Optional[click.Group]:
        """No top-level commands for now."""
        return None

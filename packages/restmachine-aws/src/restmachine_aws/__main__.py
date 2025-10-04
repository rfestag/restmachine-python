"""
CLI entry point for restmachine-aws.

Provides commands for generating Lambda extension scripts and other utilities.
"""

import argparse
import sys
from pathlib import Path


EXTENSION_TEMPLATE = """#!/usr/bin/env python3
\"\"\"
RestMachine Lambda Extension for automatic shutdown handling.

This extension calls app.shutdown_sync() when the Lambda container terminates.
It runs as a separate process alongside your Lambda function and listens for
SHUTDOWN events from the Lambda Runtime API.

Environment Variables:
    RESTMACHINE_HANDLER_MODULE: Module containing the handler (default: lambda_function)
    RESTMACHINE_APP_NAME: Variable name of RestApplication (default: app)
    RESTMACHINE_LOG_LEVEL: Logging level (default: INFO)

See: https://docs.aws.amazon.com/lambda/latest/dg/runtimes-extensions-api.html
\"\"\"

from restmachine_aws.extension import main

if __name__ == "__main__":
    main()
"""


def create_extension(args):
    """Generate the Lambda extension script."""
    # Default to extensions/restmachine-shutdown
    output_path = Path(args.output) if args.output else Path("extensions/restmachine-shutdown")

    # Create extensions directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the extension script
    output_path.write_text(EXTENSION_TEMPLATE)

    # Make it executable
    output_path.chmod(0o755)

    print(f"✓ Created Lambda extension: {output_path}")
    print(f"✓ Made executable: chmod +x {output_path}")
    print()
    print("Next steps:")
    print("1. Deploy this file with your Lambda function")
    print("2. Ensure restmachine-aws is in your Lambda dependencies")
    print("3. The extension will automatically call shutdown handlers on container termination")
    print()
    print("Customization:")
    print("  Set RESTMACHINE_HANDLER_MODULE if your handler is not 'lambda_function'")
    print("  Set RESTMACHINE_APP_NAME if your app variable is not 'app'")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RestMachine AWS utilities",
        prog="python -m restmachine_aws"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create-extension command
    extension_parser = subparsers.add_parser(
        "create-extension",
        help="Generate a Lambda extension script for shutdown handling"
    )
    extension_parser.add_argument(
        "-o", "--output",
        help="Output path for extension script (default: extensions/restmachine-shutdown)",
        default=None
    )

    args = parser.parse_args()

    if args.command == "create-extension":
        create_extension(args)
    elif args.command is None:
        parser.print_help()
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

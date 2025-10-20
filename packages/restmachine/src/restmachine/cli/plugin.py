"""
RestMachine CLI Plugin System.

Two types of plugins:
1. DatabaseBackendPlugin - ORM/database backends (DynamoDB, PostgreSQL, etc.)
   - Provides custom field types
   - Validates field compatibility
   - Used via --backend flag

2. CliExtensionPlugin - Infrastructure/deployment extensions (AWS, Cloudflare, etc.)
   - Adds new CLI commands/subcommands
   - Extends generate command
   - No backend configuration needed
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import click


class DatabaseBackendPlugin(ABC):
    """Base class for database backend plugins (DynamoDB, PostgreSQL, etc.)."""

    @abstractmethod
    def get_name(self) -> str:
        """
        Return backend name (e.g., 'dynamodb', 'postgresql').

        This is used for:
        - Backend identification
        - --backend flag value
        - Backend selection in .restmachine.toml
        """
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """
        Return human-readable name (e.g., 'DynamoDB', 'PostgreSQL').

        Used in help text and user-facing messages.
        """
        pass

    def get_supported_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Return additional field types this backend supports.

        Format matches FIELD_TYPE_MAP:
        {
            "geo": {
                "python_type": "dict",
                "field_def": "{name}: dict  # {{'lat': float, 'lon': float}}",
                "needs_import": None,
                "fixture_example": "{{'lat': 37.7749, 'lon': -122.4194}}",
            },
            "binary": {
                "python_type": "bytes",
                "field_def": "{name}: bytes",
                "needs_import": None,
                "fixture_example": "b'binary data'",
            }
        }

        Returns:
            Dictionary mapping type names to type specifications
        """
        return {}

    def validate_field(self, field_name: str, field_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate a field for this backend.

        Allows backends to reject incompatible field types or names.
        Example: DynamoDB might reject certain reserved keywords.

        Args:
            field_name: Name of the field
            field_type: Type of the field (str, int, geo, etc.)

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if field is valid for this backend
            - error_message: Error description if invalid, None otherwise
        """
        return True, None


class CliExtensionPlugin(ABC):
    """Base class for CLI extension plugins (AWS, Cloudflare, etc.)."""

    @abstractmethod
    def get_name(self) -> str:
        """
        Return extension name (e.g., 'aws', 'cloudflare').

        This is used for plugin identification.
        """
        pass

    def get_generate_commands(self) -> Optional[click.Group]:
        """
        Return Click command group to add under 'generate' command.

        These commands will be registered as: `restmachine generate <command>`

        Example:
            @click.group()
            def aws_generate():
                pass

            @aws_generate.command(name="lambda-extension")
            def lambda_extension():
                \"\"\"Generate Lambda extension.\"\"\"
                click.echo("Generating Lambda extension...")

            return aws_generate

        Returns:
            Click Group with commands, or None if no generate commands
        """
        return None

    def get_top_level_commands(self) -> Optional[click.Group]:
        """
        Return Click command group for top-level commands.

        These commands will be registered as: `restmachine <name> <command>`

        Example:
            @click.group()
            def aws():
                \"\"\"AWS-specific commands.\"\"\"
                pass

            @aws.command()
            def deploy():
                \"\"\"Deploy to AWS.\"\"\"
                click.echo("Deploying to AWS...")

            return aws

        Returns:
            Click Group with commands, or None if no top-level commands
        """
        return None

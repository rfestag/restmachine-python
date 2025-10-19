"""
CLI backend plugin for DynamoDB.

Provides DynamoDB-specific field types and validation.
"""

from typing import Dict, Any, Optional


class DynamoDbBackendPlugin:
    """Database backend plugin for DynamoDB."""

    def get_name(self) -> str:
        """Return backend name."""
        return "dynamodb"

    def get_display_name(self) -> str:
        """Return human-readable name."""
        return "DynamoDB"

    def get_supported_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Add DynamoDB-specific types.

        Includes:
        - geo: Geographic coordinates (latitude/longitude)
        - binary: Binary data (bytes)
        - ttl: Time-to-live (Unix timestamp)
        """
        return {
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
            },
            "ttl": {
                "python_type": "int",
                "field_def": "{name}: int  # Unix timestamp for TTL",
                "needs_import": None,
                "fixture_example": "1704067200",  # 2024-01-01 00:00:00 UTC
            },
        }

    def validate_field(self, field_name: str, field_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate field for DynamoDB compatibility.

        DynamoDB has some limitations:
        - Reserved keywords cannot be used as attribute names
        - Certain naming patterns are discouraged
        """
        # DynamoDB reserved keywords (partial list of most common)
        RESERVED_KEYWORDS = {
            "name", "status", "type", "order", "data", "time", "range",
            "key", "keys", "value", "values", "hash", "connection"
        }

        if field_name.lower() in RESERVED_KEYWORDS:
            return False, (
                f"Field name '{field_name}' is a DynamoDB reserved keyword. "
                f"Consider using '{field_name}_value' or a different name."
            )

        return True, None

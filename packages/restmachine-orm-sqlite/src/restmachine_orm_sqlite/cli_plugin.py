"""
CLI backend plugin for SQLite.

Provides SQLite backend integration for RestMachine CLI.
"""

from typing import Dict, Any, Optional


class SqliteBackendPlugin:
    """Database backend plugin for SQLite."""

    def get_name(self) -> str:
        """Return backend name."""
        return "sqlite"

    def get_display_name(self) -> str:
        """Return human-readable name."""
        return "SQLite"

    def get_supported_types(self) -> Dict[str, Dict[str, Any]]:
        """
        SQLite uses the same base types as the core framework.

        No additional types needed - SQLite handles all basic types well.
        """
        return {}

    def validate_field(self, field_name: str, field_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate field for SQLite compatibility.

        SQLite is very permissive, so most fields are valid.
        """
        return True, None

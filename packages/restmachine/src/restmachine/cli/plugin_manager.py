"""
Plugin manager for RestMachine CLI.

Handles plugin discovery, loading, and registration using Python entry points.

Two types of plugins:
1. Database backends (restmachine.backends) - ORM/database backends
2. CLI extensions (restmachine.cli_extensions) - Infrastructure/deployment tools
"""

import sys
from typing import Dict, Any, Optional
from .plugin import DatabaseBackendPlugin, CliExtensionPlugin


class PluginManager:
    """Manages discovery and loading of CLI plugins."""

    def __init__(self):
        self._backend_plugins: Dict[str, DatabaseBackendPlugin] = {}
        self._extension_plugins: Dict[str, CliExtensionPlugin] = {}
        self._discover_plugins()

    def _discover_plugins(self):
        """Discover and load all registered plugins via entry points."""
        # Use importlib.metadata for Python 3.9+ compatibility
        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points
            backend_eps = entry_points(group='restmachine.backends')
            extension_eps = entry_points(group='restmachine.cli_extensions')
        else:
            # Python 3.9 compatibility
            from importlib.metadata import entry_points
            eps = entry_points()
            backend_eps = eps.get('restmachine.backends', [])
            extension_eps = eps.get('restmachine.cli_extensions', [])

        # Load database backend plugins
        for ep in backend_eps:
            try:
                plugin_class = ep.load()
                plugin = plugin_class()
                plugin_name = plugin.get_name()
                self._backend_plugins[plugin_name] = plugin
            except Exception as e:
                # Log warning but continue - don't let one bad plugin break everything
                import warnings
                warnings.warn(
                    f"Failed to load backend plugin '{ep.name}': {e}",
                    RuntimeWarning
                )

        # Load CLI extension plugins
        for ep in extension_eps:
            try:
                plugin_class = ep.load()
                plugin = plugin_class()
                plugin_name = plugin.get_name()
                self._extension_plugins[plugin_name] = plugin
            except Exception as e:
                import warnings
                warnings.warn(
                    f"Failed to load CLI extension plugin '{ep.name}': {e}",
                    RuntimeWarning
                )

    def get_backend(self, name: str) -> Optional[DatabaseBackendPlugin]:
        """
        Get database backend plugin by name.

        Args:
            name: Backend name (e.g., 'dynamodb', 'postgresql')

        Returns:
            Backend plugin instance or None if not found
        """
        return self._backend_plugins.get(name)

    def get_extension(self, name: str) -> Optional[CliExtensionPlugin]:
        """
        Get CLI extension plugin by name.

        Args:
            name: Extension name (e.g., 'aws', 'cloudflare')

        Returns:
            Extension plugin instance or None if not found
        """
        return self._extension_plugins.get(name)

    def list_backends(self) -> Dict[str, DatabaseBackendPlugin]:
        """
        List all available database backend plugins.

        Returns:
            Dictionary mapping backend names to backend plugin instances
        """
        return self._backend_plugins.copy()

    def list_extensions(self) -> Dict[str, CliExtensionPlugin]:
        """
        List all available CLI extension plugins.

        Returns:
            Dictionary mapping extension names to extension plugin instances
        """
        return self._extension_plugins.copy()

    def get_available_types(self, backend: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get all available field types.

        If backend is specified, includes backend-specific types.
        Otherwise, returns only base types.

        Args:
            backend: Backend name to get types for (optional)

        Returns:
            Dictionary mapping type names to type specifications
        """
        from .generate import FIELD_TYPE_MAP

        # Start with base types
        types = FIELD_TYPE_MAP.copy()

        # Add backend-specific types if backend specified
        if backend:
            backend_plugin = self.get_backend(backend)
            if backend_plugin:
                backend_types = backend_plugin.get_supported_types()
                types.update(backend_types)

        return types

    def validate_field(
        self,
        backend: Optional[str],
        field_name: str,
        field_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a field against backend constraints.

        Args:
            backend: Backend name (optional)
            field_name: Field name
            field_type: Field type

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not backend:
            return True, None

        backend_plugin = self.get_backend(backend)
        if not backend_plugin:
            return True, None

        return backend_plugin.validate_field(field_name, field_type)


# Singleton instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """
    Get the global plugin manager instance.

    Returns:
        Singleton PluginManager instance
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager

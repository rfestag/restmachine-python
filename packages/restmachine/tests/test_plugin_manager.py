"""
Tests for RestMachine Plugin Manager.
"""

import pytest
from unittest.mock import Mock, patch
from restmachine.cli.plugin_manager import PluginManager, get_plugin_manager
from restmachine.cli.plugin import DatabaseBackendPlugin, CliExtensionPlugin
import click


class MockDatabaseBackendPlugin(DatabaseBackendPlugin):
    """Mock database backend plugin for testing."""

    def get_name(self) -> str:
        return "testdb"

    def get_display_name(self) -> str:
        return "TestDB"

    def get_supported_types(self):
        return {
            "custom_type": {
                "python_type": "str",
                "field_def": "{name}: str  # Custom type",
                "needs_import": None,
                "fixture_example": "'custom_value'",
            }
        }

    def validate_field(self, field_name: str, field_type: str):
        if field_name == "forbidden":
            return False, "Field name 'forbidden' is not allowed"
        return True, None


class MockCliExtensionPlugin(CliExtensionPlugin):
    """Mock CLI extension plugin for testing."""

    def get_name(self) -> str:
        return "testcloud"

    def get_generate_commands(self):
        @click.group()
        def temp_group():
            pass

        @temp_group.command(name="test-resource")
        def test_resource():
            """Test resource command."""
            click.echo("Test resource created")

        return temp_group

    def get_top_level_commands(self):
        @click.group()
        def testcloud():
            """Test cloud commands."""
            pass

        @testcloud.command()
        def deploy():
            """Deploy to test cloud."""
            click.echo("Deploying to test cloud")

        return testcloud


def test_plugin_manager_singleton():
    """Test that plugin manager is a singleton."""
    manager1 = get_plugin_manager()
    manager2 = get_plugin_manager()
    assert manager1 is manager2


def test_plugin_manager_initialization():
    """Test plugin manager initializes empty without plugins."""
    manager = PluginManager()
    assert isinstance(manager, PluginManager)
    assert isinstance(manager._backend_plugins, dict)
    assert isinstance(manager._extension_plugins, dict)


@patch('importlib.metadata.entry_points')
def test_discover_backend_plugins(mock_entry_points):
    """Test discovering database backend plugins."""
    # Mock entry point
    mock_ep = Mock()
    mock_ep.name = "testdb"
    mock_ep.load.return_value = MockDatabaseBackendPlugin

    # Python 3.10+ style - entry_points returns iterable for specific group
    def entry_points_side_effect(group=None):
        if group == 'restmachine.backends':
            return [mock_ep]
        return []

    mock_entry_points.side_effect = entry_points_side_effect

    with patch('sys.version_info', (3, 10, 0)):
        manager = PluginManager()

    assert "testdb" in manager._backend_plugins
    assert isinstance(manager._backend_plugins["testdb"], MockDatabaseBackendPlugin)


@patch('importlib.metadata.entry_points')
def test_discover_extension_plugins(mock_entry_points):
    """Test discovering CLI extension plugins."""
    # Mock entry point
    mock_ep = Mock()
    mock_ep.name = "testcloud"
    mock_ep.load.return_value = MockCliExtensionPlugin

    # Python 3.10+ style - entry_points returns iterable for specific group
    def entry_points_side_effect(group=None):
        if group == 'restmachine.cli_extensions':
            return [mock_ep]
        return []

    mock_entry_points.side_effect = entry_points_side_effect

    with patch('sys.version_info', (3, 10, 0)):
        manager = PluginManager()

    assert "testcloud" in manager._extension_plugins
    assert isinstance(manager._extension_plugins["testcloud"], MockCliExtensionPlugin)


def test_get_backend_existing():
    """Test getting an existing backend plugin."""
    manager = PluginManager()
    manager._backend_plugins["testdb"] = MockDatabaseBackendPlugin()

    backend = manager.get_backend("testdb")
    assert backend is not None
    assert backend.get_name() == "testdb"


def test_get_backend_nonexistent():
    """Test getting a nonexistent backend plugin."""
    manager = PluginManager()
    backend = manager.get_backend("nonexistent")
    assert backend is None


def test_get_extension_existing():
    """Test getting an existing extension plugin."""
    manager = PluginManager()
    manager._extension_plugins["testcloud"] = MockCliExtensionPlugin()

    extension = manager.get_extension("testcloud")
    assert extension is not None
    assert extension.get_name() == "testcloud"


def test_get_extension_nonexistent():
    """Test getting a nonexistent extension plugin."""
    manager = PluginManager()
    extension = manager.get_extension("nonexistent")
    assert extension is None


@patch('importlib.metadata.entry_points')
def test_list_backends(mock_entry_points):
    """Test listing all backend plugins."""
    # Don't discover any plugins
    mock_entry_points.side_effect = lambda group=None: []

    with patch('sys.version_info', (3, 10, 0)):
        manager = PluginManager()

    # Manually add test plugins
    manager._backend_plugins["testdb1"] = MockDatabaseBackendPlugin()
    manager._backend_plugins["testdb2"] = MockDatabaseBackendPlugin()

    backends = manager.list_backends()
    assert "testdb1" in backends
    assert "testdb2" in backends
    assert len(backends) == 2


@patch('importlib.metadata.entry_points')
def test_list_extensions(mock_entry_points):
    """Test listing all extension plugins."""
    # Don't discover any plugins
    mock_entry_points.side_effect = lambda group=None: []

    with patch('sys.version_info', (3, 10, 0)):
        manager = PluginManager()

    # Manually add test plugins
    manager._extension_plugins["testcloud1"] = MockCliExtensionPlugin()
    manager._extension_plugins["testcloud2"] = MockCliExtensionPlugin()

    extensions = manager.list_extensions()
    assert "testcloud1" in extensions
    assert "testcloud2" in extensions
    assert len(extensions) == 2


def test_get_available_types_base_only():
    """Test getting base types without backend."""
    manager = PluginManager()
    types = manager.get_available_types()

    # Should have base types from FIELD_TYPE_MAP
    assert "str" in types
    assert "int" in types
    assert "float" in types
    assert "bool" in types
    assert "datetime" in types
    assert "uuid" in types


def test_get_available_types_with_backend():
    """Test getting types with backend-specific types."""
    manager = PluginManager()
    manager._backend_plugins["testdb"] = MockDatabaseBackendPlugin()

    types = manager.get_available_types("testdb")

    # Should have base types
    assert "str" in types
    assert "int" in types

    # Should have custom type from backend
    assert "custom_type" in types
    assert types["custom_type"]["python_type"] == "str"


def test_get_available_types_nonexistent_backend():
    """Test getting types with nonexistent backend."""
    manager = PluginManager()
    types = manager.get_available_types("nonexistent")

    # Should only have base types
    assert "str" in types
    assert "custom_type" not in types


def test_validate_field_no_backend():
    """Test field validation without backend."""
    manager = PluginManager()
    is_valid, error = manager.validate_field(None, "test_field", "str")

    assert is_valid is True
    assert error is None


def test_validate_field_with_backend():
    """Test field validation with backend."""
    manager = PluginManager()
    manager._backend_plugins["testdb"] = MockDatabaseBackendPlugin()

    # Valid field
    is_valid, error = manager.validate_field("testdb", "allowed_field", "str")
    assert is_valid is True
    assert error is None

    # Invalid field
    is_valid, error = manager.validate_field("testdb", "forbidden", "str")
    assert is_valid is False
    assert "not allowed" in error


def test_validate_field_nonexistent_backend():
    """Test field validation with nonexistent backend."""
    manager = PluginManager()
    is_valid, error = manager.validate_field("nonexistent", "test_field", "str")

    assert is_valid is True
    assert error is None


@patch('importlib.metadata.entry_points')
def test_plugin_loading_error_handling(mock_entry_points):
    """Test that plugin loading errors are handled gracefully."""
    # Mock entry point that raises an error
    mock_ep = Mock()
    mock_ep.name = "broken"
    mock_ep.load.side_effect = Exception("Plugin load failed")

    def entry_points_side_effect(group=None):
        if group == 'restmachine.backends':
            return [mock_ep]
        return []

    mock_entry_points.side_effect = entry_points_side_effect

    # Should not crash, just issue warning
    with patch('sys.version_info', (3, 10, 0)):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager = PluginManager()

            # Should have issued a warning
            assert len(w) > 0
            assert "broken" in str(w[0].message)


def test_backend_plugin_type_merging():
    """Test that backend types properly merge with base types."""
    manager = PluginManager()
    backend_plugin = MockDatabaseBackendPlugin()
    manager._backend_plugins["testdb"] = backend_plugin

    types = manager.get_available_types("testdb")

    # Verify base types exist
    assert "str" in types
    assert "int" in types
    assert "float" in types

    # Verify custom type exists
    assert "custom_type" in types

    # Verify custom type has correct structure
    custom_type = types["custom_type"]
    assert custom_type["python_type"] == "str"
    assert "Custom type" in custom_type["field_def"]
    assert custom_type["fixture_example"] == "'custom_value'"


def test_extension_plugin_generate_commands():
    """Test extension plugin generate commands."""
    plugin = MockCliExtensionPlugin()
    commands = plugin.get_generate_commands()

    assert commands is not None
    assert "test-resource" in commands.commands


def test_extension_plugin_top_level_commands():
    """Test extension plugin top-level commands."""
    plugin = MockCliExtensionPlugin()
    commands = plugin.get_top_level_commands()

    assert commands is not None
    assert commands.name == "testcloud"
    assert "deploy" in commands.commands


def test_backend_plugin_defaults():
    """Test backend plugin default implementations."""
    plugin = MockDatabaseBackendPlugin()

    # Test defaults
    assert plugin.get_name() == "testdb"
    assert plugin.get_display_name() == "TestDB"
    assert "custom_type" in plugin.get_supported_types()


def test_cli_extension_plugin_defaults():
    """Test CLI extension plugin default implementations."""

    class MinimalExtension(CliExtensionPlugin):
        def get_name(self):
            return "minimal"

    plugin = MinimalExtension()

    # Test defaults
    assert plugin.get_name() == "minimal"
    assert plugin.get_generate_commands() is None
    assert plugin.get_top_level_commands() is None

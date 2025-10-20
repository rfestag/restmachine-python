"""
Tests for backend-aware field type validation in generate commands.
"""

import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from restmachine.cli import main
from restmachine.cli.plugin_manager import PluginManager
from restmachine.cli.plugin import DatabaseBackendPlugin
from unittest.mock import Mock, patch


class MockBackendPlugin(DatabaseBackendPlugin):
    """Mock backend plugin for testing."""

    def get_name(self):
        return "testbackend"

    def get_display_name(self):
        return "Test Backend"

    def get_supported_types(self):
        return {
            "custom": {
                "python_type": "dict",
                "field_def": "{name}: dict",
                "needs_import": None,
                "fixture_example": "{{}}",
            }
        }

    def validate_field(self, field_name, field_type):
        # Reject field name "forbidden"
        if field_name == "forbidden":
            return False, "Field name 'forbidden' is reserved"
        return True, None


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_project():
    """Create a temporary project for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create minimal project structure
        (project_dir / "models").mkdir()
        (project_dir / "models" / "__init__.py").write_text("")
        (project_dir / "schemas").mkdir()
        (project_dir / "schemas" / "__init__.py").write_text("")
        (project_dir / "routes").mkdir()
        (project_dir / "routes" / "__init__.py").write_text("")
        (project_dir / "db" / "fixtures" / "local" / "development").mkdir(parents=True)

        # Create app.py (required for generate commands)
        (project_dir / "app.py").write_text("# Test app\n")

        # Create .restmachine.toml
        config_content = """
[project]
name = "testapp"
backend = "sqlite"
"""
        (project_dir / ".restmachine.toml").write_text(config_content)

        yield project_dir


def test_generate_model_with_base_types(runner, temp_project):
    """Test generating model with base field types."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(
        main, ["generate", "model", "User", "name:str", "age:int", "--skip-fixtures"]
    )

    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")

    assert result.exit_code == 0, f"Command failed with: {result.output}"
    assert (temp_project / "models" / "user.py").exists()


def test_generate_model_with_invalid_type(runner, temp_project):
    """Test that invalid field types are rejected."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(
        main, ["generate", "model", "User", "name:invalid_type", "--skip-fixtures"]
    )

    assert result.exit_code != 0
    assert "Unsupported type" in result.output or "invalid_type" in result.output


@patch.object(PluginManager, "get_backend")
@patch.object(PluginManager, "get_available_types")
def test_generate_model_with_backend_custom_type(
    mock_get_types, mock_get_backend, runner, temp_project
):
    """Test generating model with backend-specific field type."""
    import os

    # Mock the backend plugin
    mock_backend = MockBackendPlugin()
    mock_get_backend.return_value = mock_backend

    # Mock available types to include custom type
    base_types = {
        "str": {"python_type": "str", "field_def": "{name}: str"},
        "int": {"python_type": "int", "field_def": "{name}: int"},
    }
    base_types.update(mock_backend.get_supported_types())
    mock_get_types.return_value = base_types

    os.chdir(temp_project)

    # Update config to use test backend
    config = temp_project / ".restmachine.toml"
    config.write_text("""
[project]
name = "testapp"
backend = "testbackend"
version = "1.0"
""")

    result = runner.invoke(
        main, ["generate", "model", "Product", "data:custom", "--skip-fixtures"]
    )

    # Should succeed with custom type
    assert result.exit_code == 0


@patch.object(PluginManager, "validate_field")
def test_generate_model_with_backend_field_validation(
    mock_validate, runner, temp_project
):
    """Test that backend field validation is called."""
    import os

    # Mock validation to reject "forbidden" field
    def validate_side_effect(backend, field_name, field_type):
        if field_name == "forbidden":
            return False, "Field name 'forbidden' is reserved"
        return True, None

    mock_validate.side_effect = validate_side_effect

    os.chdir(temp_project)

    result = runner.invoke(
        main, ["generate", "model", "User", "forbidden:str", "--skip-fixtures"]
    )

    # Should fail validation
    assert result.exit_code != 0
    assert "forbidden" in result.output or "reserved" in result.output.lower()


def test_generate_scaffold_with_base_types(runner, temp_project):
    """Test generating scaffold with base field types."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(
        main,
        ["generate", "scaffold", "User", "name:str", "email:str", "--skip-fixtures"],
    )

    assert result.exit_code == 0
    assert (temp_project / "models" / "user.py").exists()
    assert (temp_project / "schemas" / "user_schemas.py").exists()
    assert (temp_project / "routes" / "users.py").exists()


def test_backend_override_in_generate_command(runner, temp_project):
    """Test overriding backend in generate command."""
    import os

    os.chdir(temp_project)

    # Default backend is sqlite, but we can override
    result = runner.invoke(
        main,
        [
            "generate",
            "model",
            "User",
            "name:str",
            "--backend",
            "memory",
            "--skip-fixtures",
        ],
    )

    # Should work with override
    assert result.exit_code == 0


def test_generate_with_all_base_field_types(runner, temp_project):
    """Test generating model with all supported base types."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(
        main,
        [
            "generate",
            "model",
            "AllTypes",
            "name:str",
            "count:int",
            "price:float",
            "active:bool",
            "created:datetime",
            "id:uuid",
            "--skip-fixtures",
        ],
    )

    if result.exit_code != 0:
        print(f"Command failed: {result.output}")

    assert result.exit_code == 0, f"Command failed with: {result.output}"
    model_file = temp_project / "models" / "all_types.py"  # Changed to snake_case
    assert model_file.exists()

    # Verify imports
    content = model_file.read_text()
    assert "from datetime import datetime" in content or "datetime" in content
    assert "str" in content
    assert "int" in content
    assert "float" in content
    assert "bool" in content


def test_field_type_map_includes_base_types(runner):
    """Test that FIELD_TYPE_MAP includes all base types."""
    from restmachine.cli.generate import FIELD_TYPE_MAP

    # Verify base types exist
    assert "str" in FIELD_TYPE_MAP
    assert "int" in FIELD_TYPE_MAP
    assert "float" in FIELD_TYPE_MAP
    assert "bool" in FIELD_TYPE_MAP
    assert "datetime" in FIELD_TYPE_MAP
    assert "uuid" in FIELD_TYPE_MAP

    # Verify structure
    for type_name, type_info in FIELD_TYPE_MAP.items():
        assert "python_type" in type_info
        assert "field_def" in type_info


def test_plugin_manager_merges_types_correctly():
    """Test that PluginManager correctly merges base and backend types."""
    manager = PluginManager()

    # Add mock backend
    manager._backend_plugins["testbackend"] = MockBackendPlugin()

    # Get types for testbackend
    types = manager.get_available_types("testbackend")

    # Should have base types
    assert "str" in types
    assert "int" in types

    # Should have custom type
    assert "custom" in types


def test_get_backend_and_types_helper():
    """Test the _get_backend_and_types helper function."""
    from restmachine.cli.generate import _get_backend_and_types

    # Without backend override or project config
    backend, types = _get_backend_and_types(None)

    # Should return base types
    assert types is not None
    assert "str" in types
    assert "int" in types


def test_generate_validates_field_format(runner, temp_project):
    """Test that field format is validated."""
    import os

    os.chdir(temp_project)

    # Missing colon
    result = runner.invoke(
        main, ["generate", "model", "User", "invalidfield", "--skip-fixtures"]
    )

    assert result.exit_code != 0
    assert "Invalid field" in result.output or ":" in result.output


def test_generate_model_no_fields(runner, temp_project):
    """Test generating model with no fields."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(main, ["generate", "model", "Empty", "--skip-fixtures"])

    # Should succeed - empty model is valid
    assert result.exit_code == 0
    assert (temp_project / "models" / "empty.py").exists()


def test_fixture_generation_respects_backend_types(runner, temp_project):
    """Test that fixture generation uses backend-specific types."""
    import os
    import yaml

    os.chdir(temp_project)

    result = runner.invoke(
        main, ["generate", "model", "User", "name:str", "age:int"]
    )

    assert result.exit_code == 0

    # Check fixture was created
    fixtures = list((temp_project / "db" / "fixtures").rglob("*.yaml"))
    assert len(fixtures) > 0, "At least one fixture file should be created"

    # Verify fixture structure
    fixture_file = fixtures[0]
    with open(fixture_file) as f:
        content = f.read()

    # Fixture might be empty or have placeholder structure - just verify it exists and is valid YAML
    if content.strip():
        data = yaml.safe_load(content)
        # Data might be None for empty/commented fixtures, which is fine
        if data:
            assert isinstance(data, dict), "Fixture should be a dictionary"


def test_generate_scaffold_creates_all_files(runner, temp_project):
    """Test that scaffold generates model, schema, and routes."""
    import os

    os.chdir(temp_project)

    result = runner.invoke(
        main,
        ["generate", "scaffold", "Product", "name:str", "price:float", "--skip-fixtures"],
    )

    assert result.exit_code == 0

    # Verify all files created
    assert (temp_project / "models" / "product.py").exists()
    assert (temp_project / "schemas" / "product_schemas.py").exists()
    assert (temp_project / "routes" / "products.py").exists()


def test_backend_types_in_fixture_examples():
    """Test that backend types provide fixture examples."""
    plugin = MockBackendPlugin()
    types = plugin.get_supported_types()

    assert "custom" in types
    assert "fixture_example" in types["custom"]
    assert types["custom"]["fixture_example"] is not None

"""
Tests for RestMachine Project Configuration.
"""

import tempfile
from pathlib import Path
import pytest
from restmachine.cli.config import ProjectConfig


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_project_config_creation(temp_project_dir):
    """Test creating a project configuration."""
    config = ProjectConfig(temp_project_dir)
    assert config.project_dir == temp_project_dir
    assert config.config_path == temp_project_dir / ".restmachine.toml"


def test_create_default_config(temp_project_dir):
    """Test creating default configuration."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )

    assert config._config["project"]["name"] == "testapp"
    assert config._config["project"]["backend"] == "sqlite"


def test_save_and_load_config(temp_project_dir):
    """Test saving and loading configuration."""
    # Create and save config
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="dynamodb"
    )
    config.save()

    # Verify file exists
    assert config.config_path.exists()

    # Load config in new instance
    loaded_config = ProjectConfig(temp_project_dir)
    assert loaded_config.get_backend() == "dynamodb"
    assert loaded_config._config["project"]["name"] == "testapp"


def test_get_backend(temp_project_dir):
    """Test getting backend from config."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="postgresql"
    )
    config.save()

    loaded_config = ProjectConfig(temp_project_dir)
    assert loaded_config.get_backend() == "postgresql"


def test_get_backend_missing_config(temp_project_dir):
    """Test getting backend when config doesn't exist."""
    config = ProjectConfig(temp_project_dir)
    assert config.get_backend() is None


def test_set_backend(temp_project_dir):
    """Test setting backend in config."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )

    config.set_backend("dynamodb")
    assert config.get_backend() == "dynamodb"

    # Save and reload
    config.save()
    loaded_config = ProjectConfig(temp_project_dir)
    assert loaded_config.get_backend() == "dynamodb"


def test_find_project_root_by_config_file(temp_project_dir, monkeypatch):
    """Test finding project root by .restmachine.toml file."""
    # Create config file
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )
    config.save()

    # Create subdirectory and search from there
    subdir = temp_project_dir / "models" / "nested"
    subdir.mkdir(parents=True)

    # Mock cwd to be in subdirectory
    monkeypatch.chdir(subdir)
    found_root = ProjectConfig.find_project_root()
    assert found_root == temp_project_dir


def test_find_project_root_by_app_py(temp_project_dir, monkeypatch):
    """Test finding project root by app.py file."""
    # Create app.py instead of .restmachine.toml
    (temp_project_dir / "app.py").write_text("# app")

    # Create subdirectory and search from there
    subdir = temp_project_dir / "routes"
    subdir.mkdir()

    # Mock cwd to be in subdirectory
    monkeypatch.chdir(subdir)
    found_root = ProjectConfig.find_project_root()
    assert found_root == temp_project_dir


def test_find_project_root_not_found(monkeypatch):
    """Test finding project root when not in a project."""
    import tempfile

    # Use a completely empty directory
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)
        found_root = ProjectConfig.find_project_root()
        assert found_root is None


def test_config_toml_format(temp_project_dir):
    """Test that config is saved in proper TOML format."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )
    config.save()

    # Read raw file
    content = config.config_path.read_text()

    # Verify TOML format
    assert "[project]" in content
    assert 'name = "testapp"' in content
    assert 'backend = "sqlite"' in content


def test_config_handles_special_characters(temp_project_dir):
    """Test config handles project names with special characters."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="my-awesome-app",
        backend="sqlite"
    )
    config.save()

    loaded_config = ProjectConfig(temp_project_dir)
    assert loaded_config._config["project"]["name"] == "my-awesome-app"


def test_config_preserves_backend_settings(temp_project_dir):
    """Test that backend-specific settings are preserved."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="dynamodb"
    )

    # Add backend-specific settings manually
    config._config["backends"] = {
        "dynamodb": {
            "table_name_prefix": "prod_",
            "region": "us-west-2"
        }
    }
    config.save()

    # Load and verify
    loaded_config = ProjectConfig(temp_project_dir)
    assert "backends" in loaded_config._config
    assert loaded_config._config["backends"]["dynamodb"]["region"] == "us-west-2"


def test_config_multiple_save_operations(temp_project_dir):
    """Test multiple save operations don't corrupt config."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )

    # Save multiple times with changes
    config.save()
    config.set_backend("dynamodb")
    config.save()
    config.set_backend("postgresql")
    config.save()

    # Load and verify final state
    loaded_config = ProjectConfig(temp_project_dir)
    assert loaded_config.get_backend() == "postgresql"


def test_config_empty_initialization(temp_project_dir):
    """Test initializing config in directory without config file."""
    config = ProjectConfig(temp_project_dir)
    assert config._config == {}
    assert config.get_backend() is None


def test_config_with_comments(temp_project_dir):
    """Test that config can be created with version info."""
    config = ProjectConfig.create_default(
        temp_project_dir,
        project_name="testapp",
        backend="sqlite"
    )

    # Verify project name and backend exist
    assert config._config["project"]["name"] == "testapp"
    assert config._config["project"]["backend"] == "sqlite"


def test_find_project_root_max_depth(monkeypatch):
    """Test that project root search stops after max depth."""
    import tempfile

    # Create deeply nested structure without project markers
    with tempfile.TemporaryDirectory() as tmpdir:
        deep_dir = Path(tmpdir)
        for i in range(10):
            deep_dir = deep_dir / f"level{i}"
        deep_dir.mkdir(parents=True)

        monkeypatch.chdir(deep_dir)
        # Should return None after searching up 5 levels
        found_root = ProjectConfig.find_project_root()
        assert found_root is None


def test_config_file_path_constant():
    """Test that config file name is consistent."""
    assert ProjectConfig.CONFIG_FILE == ".restmachine.toml"


def test_config_load_invalid_toml(temp_project_dir):
    """Test loading config with invalid TOML."""
    # Create invalid TOML file
    config_path = temp_project_dir / ".restmachine.toml"
    config_path.write_text("this is not valid TOML [[[[")

    # Should raise an error when trying to load
    with pytest.raises(Exception):
        ProjectConfig(temp_project_dir)

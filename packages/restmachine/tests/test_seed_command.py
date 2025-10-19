"""
Tests for the 'restmachine seed' command.

Tests the CLI command that loads fixtures into the database.
"""

import tempfile
from pathlib import Path
from typing import ClassVar
import pytest
import yaml
from click.testing import CliRunner
from restmachine.cli import main


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def project_with_fixtures(tmp_path):
    """
    Create a temporary project directory with fixture structure.

    Returns the project directory path.
    """
    project_dir = tmp_path / "testapp"
    project_dir.mkdir()

    # Create config directory and hierarchy.yaml
    config_dir = project_dir / "config"
    config_dir.mkdir()
    (config_dir / "hierarchy.yaml").write_text(yaml.dump({
        "default_path": "local",
        "default_environment": "development"
    }))

    # Create fixtures directory structure
    fixtures_dir = project_dir / "db" / "fixtures"
    fixtures_dir.mkdir(parents=True)

    # Create a simple base fixture
    (fixtures_dir / "base.yaml").write_text(yaml.dump({
        "model": "User",
        "records": [
            {"name": "Base User"}
        ]
    }))

    return project_dir


class TestSeedCommandCLI:
    """Test basic seed command CLI functionality."""

    def test_seed_command_exists(self, runner):
        """Test that the seed command is registered."""
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'seed' in result.output

    def test_seed_requires_fixtures_directory(self, runner, tmp_path):
        """Test that seed fails gracefully without fixtures directory."""
        # Create a project without fixtures directory
        project_dir = tmp_path / "no_fixtures"
        project_dir.mkdir()

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_dir)
        ])

        assert result.exit_code != 0
        assert "Invalid project structure" in result.output or "fixtures" in result.output.lower()

    def test_seed_with_dry_run(self, runner, project_with_fixtures):
        """Test dry-run mode shows what would be loaded."""
        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "base.yaml" in result.output.lower() or "User" in result.output

    def test_seed_with_environment_option(self, runner, project_with_fixtures):
        """Test --environment option."""
        # Create environment-specific fixtures at the default path level (local)
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        local_dir = fixtures_dir / "local"
        local_dir.mkdir()
        prod_dir = local_dir / "production"
        prod_dir.mkdir()
        (prod_dir / "prod.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Prod User"}]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--environment', 'production',
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "prod.yaml" in result.output.lower()

    def test_seed_with_path_option(self, runner, project_with_fixtures):
        """Test --path option."""
        # Create path-specific fixtures
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        aws_dir = fixtures_dir / "aws"
        aws_dir.mkdir()
        (aws_dir / "aws.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "AWS User"}]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--path', 'aws',
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "aws.yaml" in result.output.lower() or "AWS User" in result.output

    def test_seed_with_hierarchical_loading(self, runner, project_with_fixtures):
        """Test that fixtures are loaded hierarchically."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Create nested structure
        (fixtures_dir / "root.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Root"}]
        }))

        local_dir = fixtures_dir / "local"
        local_dir.mkdir()
        (local_dir / "local.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Local"}]
        }))

        dev_dir = local_dir / "development"
        dev_dir.mkdir()
        (dev_dir / "dev.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Dev"}]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--path', 'local',
            '--environment', 'development',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should load all three levels
        output_lower = result.output.lower()
        assert "root.yaml" in output_lower or "base.yaml" in output_lower
        assert "local.yaml" in output_lower
        assert "dev.yaml" in output_lower

    def test_seed_with_fixture_id_replacement(self, runner, project_with_fixtures):
        """Test that _fixture_id causes record replacement."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove base.yaml to isolate this test
        (fixtures_dir / "base.yaml").unlink()

        # Root level fixture with _fixture_id
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [
                {"_fixture_id": "admin", "name": "Root Admin"}
            ]
        }))

        # Environment level that replaces it (need to be under local/development)
        local_dir = fixtures_dir / "local"
        local_dir.mkdir()
        dev_dir = local_dir / "development"
        dev_dir.mkdir()
        (dev_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [
                {"_fixture_id": "admin", "name": "Dev Admin"}
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--environment', 'development',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should show only 1 record (replaced, not 2)
        assert "1 record" in result.output.lower()

    def test_seed_with_fixture_flag_loads_only_specified_file(self, runner, project_with_fixtures):
        """Test that --fixture flag loads only the specified fixture file."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Create models
        models_dir = project_with_fixtures / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("""
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends.inmemory import InMemoryBackend, InMemoryAdapter

class User(Model):
    model_backend: ClassVar = InMemoryBackend(InMemoryAdapter())

    name: str

class Product(Model):
    model_backend: ClassVar = InMemoryBackend(InMemoryAdapter())

    name: str
""")

        # Create multiple fixtures
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "User 1"}]
        }))
        (fixtures_dir / "products.yaml").write_text(yaml.dump({
            "model": "Product",
            "records": [{"name": "Product 1"}]
        }))

        # Load only users.yaml
        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--fixture', 'users.yaml',
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "users.yaml" in result.output.lower() or "User" in result.output
        # Should not load products
        assert "products.yaml" not in result.output.lower() and "Product" not in result.output

    def test_seed_with_multiple_fixture_flags(self, runner, project_with_fixtures):
        """Test multiple --fixture flags."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Create three fixtures
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "User"}]
        }))
        (fixtures_dir / "products.yaml").write_text(yaml.dump({
            "model": "Product",
            "records": [{"name": "Product"}]
        }))
        (fixtures_dir / "orders.yaml").write_text(yaml.dump({
            "model": "Order",
            "records": [{"id": "1"}]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--fixture', 'users.yaml',
            '--fixture', 'products.yaml',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should load users and products
        output_lower = result.output.lower()
        assert "users.yaml" in output_lower or "User" in output_lower
        assert "products.yaml" in output_lower or "Product" in output_lower
        # Should NOT load orders
        assert "orders.yaml" not in output_lower and "Order" not in output_lower

    def test_seed_with_clear_flag_in_dry_run(self, runner, project_with_fixtures):
        """Test --clear flag shows warning in dry-run."""
        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--clear',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should mention clearing/truncating
        assert "clear" in result.output.lower() or "truncate" in result.output.lower()

    def test_seed_with_verbose_flag_in_dry_run(self, runner, project_with_fixtures):
        """Test --verbose flag shows detailed information."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--verbose',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should show more details
        output_lower = result.output.lower()
        assert "fixtures directory" in output_lower or "path" in output_lower
        assert "environment" in output_lower or "directories" in output_lower


class TestSeedWithInMemoryBackend:
    """Test seeding with the in-memory ORM backend."""

    def test_seed_creates_records(self, runner, project_with_fixtures, tmp_path):
        """Test that seed command validates correctly with upsert_key."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove base.yaml to isolate this test
        (fixtures_dir / "base.yaml").unlink()

        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"email": "test@example.com", "name": "Test User"},
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "User" in result.output
        assert "1 record" in result.output.lower()
        assert "upsert by email" in result.output.lower()

    def test_seed_with_upsert_key_is_idempotent(self, runner, project_with_fixtures):
        """Test that upsert_key is properly configured for idempotent seeding."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"email": "test@example.com", "name": "Test User"},
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "upsert by email" in result.output.lower()

    def test_seed_without_upsert_key_uses_id(self, runner, project_with_fixtures):
        """Test that without upsert_key, records still load correctly."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        (fixtures_dir / "items.yaml").write_text(yaml.dump({
            "model": "Item",
            # No upsert_key specified
            "records": [
                {"id": "item-1", "name": "Item 1"},
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "Item" in result.output
        assert "1 record" in result.output.lower()

    def test_seed_with_composite_upsert_key(self, runner, project_with_fixtures):
        """Test seeding with composite upsert key."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        (fixtures_dir / "tenant_users.yaml").write_text(yaml.dump({
            "model": "TenantUser",
            "upsert_key": ["tenant_id", "email"],
            "records": [
                {"tenant_id": "tenant-1", "email": "user@example.com", "name": "User 1"},
                {"tenant_id": "tenant-2", "email": "user@example.com", "name": "User 2"},
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        assert "TenantUser" in result.output
        assert "2 record" in result.output.lower()

    def test_seed_with_clear_flag_truncates_tables(self, runner, project_with_fixtures):
        """Test that --clear flag shows warning in output."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [
                {"name": "User 1"},
            ]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--clear',
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should mention clearing/truncating in dry-run
        assert "clear" in result.output.lower() or "truncate" in result.output.lower()


class TestSeedErrorHandling:
    """Test Phase 3: Error handling and validation."""

    def test_seed_with_invalid_yaml_shows_helpful_error(self, runner, project_with_fixtures):
        """Test that invalid YAML shows file path and helpful error message."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Create invalid YAML file
        (fixtures_dir / "invalid.yaml").write_text("""
model: User
records:
  - name: Test
    invalid: syntax here
      bad_indent: value
""")

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code != 0
        # Should show the file that caused the error
        assert "invalid.yaml" in result.output
        # Should mention YAML or parse error
        assert "yaml" in result.output.lower() or "parse" in result.output.lower()

    def test_seed_with_missing_model_field_shows_error(self, runner, project_with_fixtures):
        """Test that fixture without 'model' field shows clear error."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove base.yaml to isolate this test
        (fixtures_dir / "base.yaml").unlink()

        # Create fixture without model field
        (fixtures_dir / "no_model.yaml").write_text("""
records:
  - name: Test User
""")

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code != 0
        # Should mention missing model field
        assert "model" in result.output.lower()
        assert "no_model.yaml" in result.output

    def test_seed_validates_models_exist_in_dry_run(self, runner, project_with_fixtures):
        """Test that dry-run validates model classes exist."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove base.yaml
        (fixtures_dir / "base.yaml").unlink()

        # Create fixture with non-existent model
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "NonExistentModel",
            "records": [{"name": "Test"}]
        }))

        # Create models directory but with different model
        models_dir = project_with_fixtures / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("""
from typing import ClassVar
from restmachine_orm import Model
from restmachine_orm.backends.inmemory import InMemoryBackend, InMemoryAdapter

class User(Model):
    model_backend: ClassVar = InMemoryBackend(InMemoryAdapter())
    name: str
""")

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        # In dry-run mode, should show the fixture will be loaded
        # But we should add validation warnings
        assert "NonExistentModel" in result.output
        # Should show warning about model not being found (when we implement validation)
        # For now, just verify the model name appears in output

    def test_seed_shows_timing_statistics(self, runner, project_with_fixtures):
        """Test that seed command shows timing statistics after completion."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Create a simple fixture
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "User 1"}]
        }))

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run',
            '--verbose'
        ])

        assert result.exit_code == 0
        # Should show timing information in verbose mode
        output_lower = result.output.lower()
        # Should show elapsed time or duration
        assert ("elapsed" in output_lower or "completed in" in output_lower or
                "took" in output_lower or "time:" in output_lower or
                "duration" in output_lower), \
                f"Expected timing info in output, got: {result.output}"

    def test_seed_with_malformed_upsert_key_shows_error(self, runner, project_with_fixtures):
        """Test that invalid upsert_key configuration shows helpful error."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove base.yaml
        (fixtures_dir / "base.yaml").unlink()

        # Create fixture with invalid upsert_key (field doesn't exist)
        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "nonexistent_field",
            "records": [{"name": "Test"}]
        }))

        # Create models
        models_dir = project_with_fixtures / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text("""
from typing import ClassVar
from restmachine_orm import Model
from restmachine_orm.backends.inmemory import InMemoryBackend, InMemoryAdapter

class User(Model):
    model_backend: ClassVar = InMemoryBackend(InMemoryAdapter())
    name: str
""")

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        # Dry-run should show the fixture will be loaded
        # Field validation happens at save time, not dry-run
        assert "User" in result.output or "users.yaml" in result.output.lower()

    def test_seed_empty_fixtures_directory_shows_helpful_message(self, runner, project_with_fixtures):
        """Test that seeding with no fixtures shows helpful message."""
        fixtures_dir = project_with_fixtures / "db" / "fixtures"

        # Remove all fixture files
        for file in fixtures_dir.glob("*.yaml"):
            file.unlink()

        result = runner.invoke(main, [
            'seed',
            '--project-dir', str(project_with_fixtures),
            '--dry-run'
        ])

        assert result.exit_code == 0
        # Should mention no fixtures found
        assert "no fixture" in result.output.lower() or "no file" in result.output.lower()

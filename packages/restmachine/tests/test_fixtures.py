"""
Tests for hierarchical fixture loading.

Tests the fixture loader that walks directory hierarchies and merges
fixture definitions based on config paths and environments.
"""

import tempfile
from pathlib import Path
import pytest
import yaml
from restmachine.cli.fixtures import FixtureLoader, FixtureRecord


class TestFixtureLoader:
    """Test the hierarchical fixture loader."""

    def test_load_simple_fixture(self, tmp_path):
        """Test loading a single fixture file."""
        # Create a simple fixture
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        fixture_file = fixture_dir / "users.yaml"
        fixture_file.write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"email": "user1@example.com", "name": "User 1"},
                {"email": "user2@example.com", "name": "User 2"},
            ]
        }))

        loader = FixtureLoader(fixture_dir)
        fixtures = loader.load()

        assert len(fixtures) == 1
        assert fixtures[0].model == "User"
        assert fixtures[0].upsert_key == "email"
        assert len(fixtures[0].records) == 2
        assert fixtures[0].records[0]["email"] == "user1@example.com"

    def test_load_hierarchical_fixtures(self, tmp_path):
        """Test loading fixtures from multiple levels of hierarchy."""
        fixture_dir = tmp_path / "fixtures"

        # Root level
        (fixture_dir).mkdir(parents=True)
        (fixture_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"_fixture_id": "admin", "email": "admin@example.com", "name": "Admin"},
            ]
        }))

        # Environment level
        (fixture_dir / "local" / "development").mkdir(parents=True)
        (fixture_dir / "local" / "development" / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"_fixture_id": "dev-user", "email": "dev@example.com", "name": "Dev User"},
            ]
        }))

        loader = FixtureLoader(fixture_dir, path="local", environment="development")
        fixtures = loader.load()

        # Should have one User fixture with merged records
        user_fixtures = [f for f in fixtures if f.model == "User"]
        assert len(user_fixtures) == 1

        all_records = user_fixtures[0].records
        assert len(all_records) == 2

        # Verify both records are present
        emails = [r["email"] for r in all_records]
        assert "admin@example.com" in emails
        assert "dev@example.com" in emails

    def test_fixture_id_replacement(self, tmp_path):
        """Test that _fixture_id causes record replacement at deeper levels."""
        fixture_dir = tmp_path / "fixtures"

        # Root level - base admin
        (fixture_dir).mkdir(parents=True)
        (fixture_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {
                    "_fixture_id": "admin",
                    "email": "admin@example.com",
                    "name": "Base Admin",
                    "role": "admin"
                },
            ]
        }))

        # Production level - override admin
        (fixture_dir / "aws" / "prod").mkdir(parents=True)
        (fixture_dir / "aws" / "prod" / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {
                    "_fixture_id": "admin",  # Same fixture_id
                    "email": "admin@production.com",  # Different email
                    "name": "Production Admin",
                    "role": "admin",
                    "mfa_required": True  # Additional field
                },
            ]
        }))

        loader = FixtureLoader(fixture_dir, path="aws", environment="prod")
        fixtures = loader.load()

        user_fixtures = [f for f in fixtures if f.model == "User"]
        assert len(user_fixtures) == 1

        # Should only have ONE record (replacement, not addition)
        assert len(user_fixtures[0].records) == 1

        record = user_fixtures[0].records[0]
        # Should be the production version
        assert record["email"] == "admin@production.com"
        assert record["name"] == "Production Admin"
        assert record["mfa_required"] is True
        # _fixture_id should be stripped
        assert "_fixture_id" not in record

    def test_fixture_id_stripped_from_records(self, tmp_path):
        """Test that _fixture_id is removed before returning records."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        (fixture_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"_fixture_id": "user1", "email": "user1@example.com", "name": "User 1"},
            ]
        }))

        loader = FixtureLoader(fixture_dir)
        fixtures = loader.load()

        # _fixture_id should not be in the final record
        assert "_fixture_id" not in fixtures[0].records[0]
        assert fixtures[0].records[0]["email"] == "user1@example.com"

    def test_multiple_models_in_hierarchy(self, tmp_path):
        """Test loading different models from different levels."""
        fixture_dir = tmp_path / "fixtures"

        # Root level - users
        (fixture_dir).mkdir(parents=True)
        (fixture_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"id": "user1", "name": "User 1"}]
        }))

        # Environment level - products
        (fixture_dir / "local" / "development").mkdir(parents=True)
        (fixture_dir / "local" / "development" / "products.yaml").write_text(yaml.dump({
            "model": "Product",
            "records": [{"id": "prod1", "name": "Product 1"}]
        }))

        loader = FixtureLoader(fixture_dir, path="local", environment="development")
        fixtures = loader.load()

        models = {f.model for f in fixtures}
        assert "User" in models
        assert "Product" in models

    def test_path_walking(self, tmp_path):
        """Test that loader walks entire path from root to target."""
        fixture_dir = tmp_path / "fixtures"

        # Create fixtures at each level
        levels = [
            (fixture_dir, "root.yaml", {"_fixture_id": "track", "level": "root"}),
            (fixture_dir / "aws", "aws.yaml", {"_fixture_id": "track", "level": "aws"}),
            (fixture_dir / "aws" / "123456", "account.yaml", {"_fixture_id": "track", "level": "account"}),
            (fixture_dir / "aws" / "123456" / "us-east-1", "region.yaml", {"_fixture_id": "track", "level": "region"}),
        ]

        for dir_path, filename, record in levels:
            dir_path.mkdir(parents=True, exist_ok=True)
            (dir_path / filename).write_text(yaml.dump({
                "model": "Config",
                "records": [record]
            }))

        loader = FixtureLoader(fixture_dir, path="aws/123456/us-east-1")
        fixtures = loader.load()

        config_fixtures = [f for f in fixtures if f.model == "Config"]
        assert len(config_fixtures) == 1

        # Should only have the most specific one (region) due to _fixture_id
        assert len(config_fixtures[0].records) == 1
        assert config_fixtures[0].records[0]["level"] == "region"

    def test_environment_specific_fixtures(self, tmp_path):
        """Test that environment-specific fixtures are loaded correctly."""
        fixture_dir = tmp_path / "fixtures"

        # Config-level fixtures
        (fixture_dir / "aws").mkdir(parents=True)
        (fixture_dir / "aws" / "shared.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"_fixture_id": "shared", "name": "Shared"}]
        }))

        # Development environment
        (fixture_dir / "aws" / "development").mkdir(parents=True)
        (fixture_dir / "aws" / "development" / "dev-users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"_fixture_id": "dev", "name": "Dev"}]
        }))

        # Production environment
        (fixture_dir / "aws" / "production").mkdir(parents=True)
        (fixture_dir / "aws" / "production" / "prod-users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"_fixture_id": "prod", "name": "Prod"}]
        }))

        # Load development
        loader_dev = FixtureLoader(fixture_dir, path="aws", environment="development")
        fixtures_dev = loader_dev.load()
        user_fixtures_dev = [f for f in fixtures_dev if f.model == "User"]
        names_dev = [r["name"] for r in user_fixtures_dev[0].records]
        assert "Shared" in names_dev
        assert "Dev" in names_dev
        assert "Prod" not in names_dev

        # Load production
        loader_prod = FixtureLoader(fixture_dir, path="aws", environment="production")
        fixtures_prod = loader_prod.load()
        user_fixtures_prod = [f for f in fixtures_prod if f.model == "User"]
        names_prod = [r["name"] for r in user_fixtures_prod[0].records]
        assert "Shared" in names_prod
        assert "Prod" in names_prod
        assert "Dev" not in names_prod

    def test_no_upsert_key(self, tmp_path):
        """Test that upsert_key is optional."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        (fixture_dir / "countries.yaml").write_text(yaml.dump({
            "model": "Country",
            # No upsert_key specified
            "records": [
                {"id": "US", "name": "United States"},
                {"id": "CA", "name": "Canada"},
            ]
        }))

        loader = FixtureLoader(fixture_dir)
        fixtures = loader.load()

        assert fixtures[0].upsert_key is None
        assert len(fixtures[0].records) == 2

    def test_composite_upsert_key(self, tmp_path):
        """Test that upsert_key can be a list of fields."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        (fixture_dir / "tenant_users.yaml").write_text(yaml.dump({
            "model": "TenantUser",
            "upsert_key": ["tenant_id", "email"],
            "records": [
                {"tenant_id": "t1", "email": "user@example.com", "name": "User 1"},
            ]
        }))

        loader = FixtureLoader(fixture_dir)
        fixtures = loader.load()

        assert fixtures[0].upsert_key == ["tenant_id", "email"]

    def test_empty_fixtures_directory(self, tmp_path):
        """Test that empty fixtures directory returns empty list."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        loader = FixtureLoader(fixture_dir)
        fixtures = loader.load()

        assert fixtures == []

    def test_invalid_yaml_raises_error(self, tmp_path):
        """Test that invalid YAML raises appropriate error."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        (fixture_dir / "bad.yaml").write_text("{ invalid yaml {{")

        loader = FixtureLoader(fixture_dir)
        with pytest.raises(Exception):  # Will be more specific once implemented
            loader.load()

    def test_missing_model_field_raises_error(self, tmp_path):
        """Test that fixture without 'model' field raises error."""
        fixture_dir = tmp_path / "fixtures"
        fixture_dir.mkdir()

        (fixture_dir / "bad.yaml").write_text(yaml.dump({
            # Missing 'model' field
            "records": [{"id": "1", "name": "Test"}]
        }))

        loader = FixtureLoader(fixture_dir)
        with pytest.raises(ValueError, match="missing required 'model' field"):
            loader.load()

    def test_default_path_and_environment(self, tmp_path):
        """Test that loader uses default path and environment from hierarchy.yaml."""
        fixture_dir = tmp_path / "fixtures"

        # Create a hierarchy.yaml with defaults
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "hierarchy.yaml").write_text(yaml.dump({
            "default_path": "local",
            "default_environment": "development"
        }))

        # Create local/development fixture
        (fixture_dir / "local" / "development").mkdir(parents=True)
        (fixture_dir / "local" / "development" / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Dev User"}]
        }))

        # Loader should use defaults from hierarchy.yaml
        loader = FixtureLoader(
            fixture_dir,
            hierarchy_file=config_dir / "hierarchy.yaml"
        )
        fixtures = loader.load()

        assert len(fixtures) == 1
        assert fixtures[0].records[0]["name"] == "Dev User"

    def test_environment_variables_override_defaults(self, tmp_path, monkeypatch):
        """Test that RESTMACHINE_* env vars override hierarchy.yaml defaults."""
        fixture_dir = tmp_path / "fixtures"
        config_dir = tmp_path / "config"

        # Setup hierarchy.yaml with defaults
        config_dir.mkdir()
        (config_dir / "hierarchy.yaml").write_text(yaml.dump({
            "default_path": "local",
            "default_environment": "development"
        }))

        # Create production fixtures
        (fixture_dir / "aws" / "production").mkdir(parents=True)
        (fixture_dir / "aws" / "production" / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"name": "Prod User"}]
        }))

        # Set environment variables
        monkeypatch.setenv("RESTMACHINE_CONFIG_PATH", "aws")
        monkeypatch.setenv("RESTMACHINE_ENVIRONMENT", "production")

        loader = FixtureLoader(
            fixture_dir,
            hierarchy_file=config_dir / "hierarchy.yaml"
        )
        fixtures = loader.load()

        assert fixtures[0].records[0]["name"] == "Prod User"

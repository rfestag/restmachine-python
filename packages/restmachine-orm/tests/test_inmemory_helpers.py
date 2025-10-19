"""
Tests for InMemory backend auto-seeding helper functions.

Tests the create_demo_backend() and seed_backend() helpers that enable
easy fixture loading for demo apps and testing.
"""

import pytest
import yaml
import tempfile
from pathlib import Path
from typing import ClassVar, Optional

from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.backends.memory_helpers import create_demo_backend, seed_backend


class TestCreateDemoBackend:
    """Test create_demo_backend() helper function."""

    def test_create_demo_backend_with_defaults(self):
        """Test creating demo backend with default settings."""
        backend = create_demo_backend()

        assert isinstance(backend, InMemoryBackend)
        assert backend.backend_name == "memory"
        # Should have seed config stored
        assert hasattr(backend, "_seed_config")
        assert backend._seed_config is not None

    def test_create_demo_backend_with_environment(self):
        """Test creating demo backend with specific environment."""
        backend = create_demo_backend(environment="demo")

        assert isinstance(backend, InMemoryBackend)
        assert backend._seed_config["environment"] == "demo"

    def test_create_demo_backend_with_path(self):
        """Test creating demo backend with specific path."""
        backend = create_demo_backend(path="local/testing")

        assert isinstance(backend, InMemoryBackend)
        assert backend._seed_config["path"] == "local/testing"

    def test_create_demo_backend_with_custom_fixtures_dir(self):
        """Test creating demo backend with custom fixtures directory."""
        backend = create_demo_backend(fixtures_dir="custom/fixtures")

        assert isinstance(backend, InMemoryBackend)
        assert backend._seed_config["fixtures_dir"] == Path("custom/fixtures")

    def test_create_demo_backend_stores_config_for_later_seeding(self):
        """Test that backend stores configuration for use by seed_backend()."""
        backend = create_demo_backend(
            fixtures_dir="db/fixtures",
            environment="production",
            path="aws/123456/us-east-1"
        )

        assert backend._seed_config["fixtures_dir"] == Path("db/fixtures")
        assert backend._seed_config["environment"] == "production"
        assert backend._seed_config["path"] == "aws/123456/us-east-1"


class TestSeedBackend:
    """Test seed_backend() helper function."""

    @pytest.fixture
    def temp_fixtures_dir(self):
        """Create temporary fixtures directory with test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures"
            fixtures_dir.mkdir()
            yield fixtures_dir

    @pytest.fixture
    def backend_with_fixtures(self, temp_fixtures_dir):
        """Create a demo backend configured to use temp fixtures."""
        return create_demo_backend(
            fixtures_dir=str(temp_fixtures_dir),
            environment="test"
        )

    def test_seed_backend_without_seed_config_raises_error(self):
        """Test that seeding a regular backend (not from create_demo_backend) raises error."""
        # Create a regular backend without seed config
        backend = InMemoryBackend()

        # Define a simple model
        class User(Model):
            model_backend: ClassVar = backend
            id: str = Field(primary_key=True)
            name: str

        with pytest.raises(ValueError, match="create_demo_backend"):
            seed_backend(backend, User)

    def test_seed_backend_with_no_models_returns_zero(self, backend_with_fixtures):
        """Test that seeding with no models returns 0."""
        count = seed_backend(backend_with_fixtures)
        assert count == 0

    def test_seed_backend_with_empty_fixtures_dir_returns_zero(self, backend_with_fixtures):
        """Test that seeding from empty fixtures directory returns 0."""
        # Define a model
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        count = seed_backend(backend_with_fixtures, User)
        assert count == 0

    def test_seed_backend_loads_simple_fixture(self, temp_fixtures_dir, backend_with_fixtures):
        """Test loading a simple fixture file."""
        # Create fixture file
        users_fixture = temp_fixtures_dir / "users.yaml"
        users_fixture.write_text(yaml.dump({
            "model": "User",
            "records": [
                {"id": "user-1", "name": "Alice", "email": "alice@example.com"},
                {"id": "user-2", "name": "Bob", "email": "bob@example.com"}
            ]
        }))

        # Define model
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str
            email: str

        # Seed
        count = seed_backend(backend_with_fixtures, User)

        assert count == 2
        assert len(User.all()) == 2

        # Verify data
        alice = User.get(id="user-1")
        assert alice is not None
        assert alice.name == "Alice"
        assert alice.email == "alice@example.com"

    def test_seed_backend_with_multiple_models(self, temp_fixtures_dir, backend_with_fixtures):
        """Test seeding multiple models at once."""
        # Create fixture files
        (temp_fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"id": "user-1", "name": "Alice"}]
        }))

        (temp_fixtures_dir / "products.yaml").write_text(yaml.dump({
            "model": "Product",
            "records": [
                {"id": "prod-1", "name": "Widget"},
                {"id": "prod-2", "name": "Gadget"}
            ]
        }))

        # Define models
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        class Product(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        # Seed both models
        count = seed_backend(backend_with_fixtures, User, Product)

        assert count == 3  # 1 user + 2 products
        assert len(User.all()) == 1
        assert len(Product.all()) == 2

    def test_seed_backend_with_upsert_key(self, temp_fixtures_dir, backend_with_fixtures):
        """Test seeding with upsert_key for idempotency."""
        # Create fixture file with upsert_key
        (temp_fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "upsert_key": "email",
            "records": [
                {"id": "user-1", "name": "Alice", "email": "alice@example.com"}
            ]
        }))

        # Define model
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str
            email: str

        # Seed once
        count1 = seed_backend(backend_with_fixtures, User)
        assert count1 == 1
        assert len(User.all()) == 1

        # Seed again - should update, not create duplicate
        count2 = seed_backend(backend_with_fixtures, User)
        assert count2 == 1  # Still 1 record processed
        assert len(User.all()) == 1  # Still only 1 user

    def test_seed_backend_skips_models_not_in_fixtures(self, temp_fixtures_dir, backend_with_fixtures):
        """Test that models without fixtures are skipped gracefully."""
        # Create fixture only for User
        (temp_fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [{"id": "user-1", "name": "Alice"}]
        }))

        # Define two models
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        class Product(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        # Seed both, but only User has fixtures
        count = seed_backend(backend_with_fixtures, User, Product)

        assert count == 1  # Only User record loaded
        assert len(User.all()) == 1
        assert len(Product.all()) == 0

    def test_seed_backend_with_hierarchical_fixtures(self, temp_fixtures_dir, backend_with_fixtures):
        """Test that hierarchical fixture loading works."""
        # Create root-level fixture
        (temp_fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [
                {"id": "user-1", "name": "Base User", "_fixture_id": "admin"}
            ]
        }))

        # Create environment-specific override
        # Note: backend defaults to path="local", so we need local/test/ structure
        local_test_dir = temp_fixtures_dir / "local" / "test"
        local_test_dir.mkdir(parents=True)
        (local_test_dir / "users.yaml").write_text(yaml.dump({
            "model": "User",
            "records": [
                {"id": "user-1", "name": "Test Admin", "_fixture_id": "admin"}
            ]
        }))

        # Define model
        class User(Model):
            model_backend: ClassVar = backend_with_fixtures
            id: str = Field(primary_key=True)
            name: str

        # Seed
        count = seed_backend(backend_with_fixtures, User)

        assert count == 1  # Only 1 user due to _fixture_id replacement
        user = User.get(id="user-1")
        assert user.name == "Test Admin"  # Environment override wins


class TestIntegrationExample:
    """Test complete integration example of auto-seeding for demo apps."""

    def test_demo_app_startup_pattern(self, tmp_path):
        """Test realistic demo app startup with auto-seeding."""
        # Setup fixtures directory
        fixtures_dir = tmp_path / "db" / "fixtures"
        fixtures_dir.mkdir(parents=True)

        (fixtures_dir / "users.yaml").write_text(yaml.dump({
            "model": "DemoUser",
            "upsert_key": "email",
            "records": [
                {"id": "demo-1", "email": "demo@example.com", "name": "Demo User"}
            ]
        }))

        # Create backend (would happen at app startup)
        backend = create_demo_backend(
            fixtures_dir=str(fixtures_dir),
            environment="demo"
        )

        # Define models
        class DemoUser(Model):
            model_backend: ClassVar = backend
            id: str = Field(primary_key=True)
            email: str
            name: str

        # Seed on startup (one line!)
        records_loaded = seed_backend(backend, DemoUser)

        # Verify
        assert records_loaded == 1
        demo_user = DemoUser.find_by(email="demo@example.com")
        assert demo_user is not None
        assert demo_user.name == "Demo User"

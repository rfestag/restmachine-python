"""
Tests for versioned model support.
"""

import pytest
from restmachine_orm import (
    VersionedModel,
    versioned_model,
    get_latest_model,
    get_union_type,
    upgrade_to_latest,
    Field,
)
from restmachine_orm.backends import InMemoryBackend


@pytest.fixture
def backend():
    """Create an in-memory backend for testing."""
    return InMemoryBackend()


@pytest.fixture(autouse=True)
def clear_version_registry():
    """Clear the version registry between tests to avoid conflicts."""
    from restmachine_orm.versioning import _registry
    yield
    _registry._registry.clear()


class TestVersionedModelBasics:
    """Test basic versioned model functionality."""

    def test_discriminator_field_set(self, backend):
        """Test that model_version is set to class name."""

        @versioned_model("Test")
        class TestV1(VersionedModel):
            model_backend = backend
            id: str = Field(primary_key=True)
            name: str

        instance = TestV1(id="1", name="test")
        assert instance.model_version == "TestV1"

    def test_discriminator_in_dump(self, backend):
        """Test that model_version is included in model_dump()."""

        @versioned_model("Test")
        class TestV1(VersionedModel):
            model_backend = backend
            id: str
            name: str

        instance = TestV1(id="1", name="test")
        data = instance.model_dump()

        assert "model_version" in data
        assert data["model_version"] == "TestV1"

    def test_table_name_from_model_name(self, backend):
        """Test that table name is derived from model_name."""

        @versioned_model("User")
        class UserV1(VersionedModel):
            model_backend = backend
            id: str

        @versioned_model("User")
        class UserV2(VersionedModel):
            model_backend = backend
            id: str

        # Both versions should use same table name
        assert UserV1._get_table_name() == "users"
        assert UserV2._get_table_name() == "users"


class TestVersionRegistry:
    """Test version registry functionality."""

    def test_register_single_version(self, backend):
        """Test registering a single version."""

        @versioned_model("Single", latest=True)
        class SingleV1(VersionedModel):
            model_backend = backend
            id: str

        latest = get_latest_model("Single")
        assert latest is SingleV1

    def test_register_multiple_versions(self, backend):
        """Test registering multiple versions."""

        @versioned_model("Multi")
        class MultiV1(VersionedModel):
            model_backend = backend
            id: str

        @versioned_model("Multi", latest=True)
        class MultiV2(VersionedModel):
            model_backend = backend
            id: str
            name: str

        latest = get_latest_model("Multi")
        assert latest is MultiV2

    def test_get_union_type(self, backend):
        """Test getting union type for deserialization."""

        @versioned_model("Union")
        class UnionV1(VersionedModel):
            model_backend = backend
            id: str

        @versioned_model("Union", latest=True)
        class UnionV2(VersionedModel):
            model_backend = backend
            id: str

        union = get_union_type("Union")
        assert union is not None
        # Union should contain both versions

    def test_duplicate_latest_raises_error(self, backend):
        """Test that marking two versions as latest raises error."""

        @versioned_model("Dup", latest=True)
        class DupV1(VersionedModel):
            model_backend = backend
            id: str

        with pytest.raises(ValueError, match="Latest version already set"):

            @versioned_model("Dup", latest=True)
            class DupV2(VersionedModel):
                model_backend = backend
                id: str

    def test_get_latest_without_latest_marked_raises_error(self, backend):
        """Test that get_latest_model raises error if no version marked as latest."""

        @versioned_model("NoLatest")
        class NoLatestV1(VersionedModel):
            model_backend = backend
            id: str

        with pytest.raises(ValueError, match="No version marked as latest"):
            get_latest_model("NoLatest")


class TestUpgrade:
    """Test upgrade functionality."""

    def test_single_upgrade_v1_to_v2(self, backend):
        """Test upgrading from V1 to V2."""

        @versioned_model("Upgrade")
        class UpgradeV1(VersionedModel):
            model_backend = backend
            id: str
            name: str

            def upgrade(self):
                return UpgradeV2(id=self.id, name=self.name, age=0)

        @versioned_model("Upgrade", latest=True)
        class UpgradeV2(VersionedModel):
            model_backend = backend
            id: str
            name: str
            age: int = 0

        # Create V1 instance
        v1 = UpgradeV1(id="1", name="Alice")

        # Upgrade to V2
        v2 = v1.upgrade()

        assert isinstance(v2, UpgradeV2)
        assert v2.id == "1"
        assert v2.name == "Alice"
        assert v2.age == 0
        assert v2.model_version == "UpgradeV2"

    def test_multi_hop_upgrade(self, backend):
        """Test upgrading through multiple versions V1 → V2 → V3."""

        @versioned_model("Chain")
        class ChainV1(VersionedModel):
            model_backend = backend
            id: str
            name: str

            def upgrade(self):
                return ChainV2(id=self.id, name=self.name, age=0)

        @versioned_model("Chain")
        class ChainV2(VersionedModel):
            model_backend = backend
            id: str
            name: str
            age: int = 0

            def upgrade(self):
                parts = self.name.split(" ", 1)
                return ChainV3(
                    id=self.id,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                    age=self.age
                )

        @versioned_model("Chain", latest=True)
        class ChainV3(VersionedModel):
            model_backend = backend
            id: str
            first_name: str
            last_name: str
            age: int = 0

        # Create V1 instance
        v1 = ChainV1(id="1", name="Alice Smith")

        # Upgrade to latest (V3)
        v3 = upgrade_to_latest(v1)

        assert isinstance(v3, ChainV3)
        assert v3.id == "1"
        assert v3.first_name == "Alice"
        assert v3.last_name == "Smith"
        assert v3.age == 0
        assert v3.model_version == "ChainV3"

    def test_upgrade_latest_returns_self(self, backend):
        """Test that upgrading latest version returns itself."""

        @versioned_model("Latest", latest=True)
        class LatestV1(VersionedModel):
            model_backend = backend
            id: str

        instance = LatestV1(id="1")
        upgraded = upgrade_to_latest(instance)

        assert upgraded is instance

    def test_version_skipping(self, backend):
        """Test that V1 can skip directly to V3."""

        @versioned_model("Skip")
        class SkipV1(VersionedModel):
            model_backend = backend
            id: str
            value: int

            def upgrade(self):
                # Skip V2, go directly to V3
                return SkipV3(id=self.id, value=self.value * 3)

        @versioned_model("Skip")
        class SkipV2(VersionedModel):
            model_backend = backend
            id: str
            value: int

            def upgrade(self):
                return SkipV3(id=self.id, value=self.value * 2)

        @versioned_model("Skip", latest=True)
        class SkipV3(VersionedModel):
            model_backend = backend
            id: str
            value: int

        # Create V1 and upgrade
        v1 = SkipV1(id="1", value=10)
        v3 = upgrade_to_latest(v1)

        assert isinstance(v3, SkipV3)
        assert v3.value == 30  # Multiplied by 3 (V1 → V3)

        # Create V2 and upgrade
        v2 = SkipV2(id="2", value=10)
        v3_from_v2 = upgrade_to_latest(v2)

        assert isinstance(v3_from_v2, SkipV3)
        assert v3_from_v2.value == 20  # Multiplied by 2 (V2 → V3)


class TestComplexUpgrades:
    """Test complex upgrade scenarios."""

    def test_data_transformation(self, backend):
        """Test complex data transformation during upgrade."""

        @versioned_model("Transform")
        class TransformV1(VersionedModel):
            model_backend = backend
            id: str
            full_name: str
            email: str

            def upgrade(self):
                parts = self.full_name.split(" ", 1)
                return TransformV2(
                    id=self.id,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                    email=self.email,
                    email_verified=False
                )

        @versioned_model("Transform", latest=True)
        class TransformV2(VersionedModel):
            model_backend = backend
            id: str
            first_name: str
            last_name: str
            email: str
            email_verified: bool = False

        v1 = TransformV1(id="1", full_name="Dr. Alice Jane Smith", email="alice@example.com")
        v2 = v1.upgrade()

        assert v2.first_name == "Dr."
        assert v2.last_name == "Alice Jane Smith"
        assert v2.email == "alice@example.com"
        assert v2.email_verified is False

    def test_single_name_upgrade(self, backend):
        """Test upgrading user with single-word name."""

        @versioned_model("Single")
        class SingleV1(VersionedModel):
            model_backend = backend
            id: str
            name: str

            def upgrade(self):
                parts = self.name.split(" ", 1)
                return SingleV2(
                    id=self.id,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else ""
                )

        @versioned_model("Single", latest=True)
        class SingleV2(VersionedModel):
            model_backend = backend
            id: str
            first_name: str
            last_name: str

        v1 = SingleV1(id="1", name="Madonna")
        v2 = v1.upgrade()

        assert v2.first_name == "Madonna"
        assert v2.last_name == ""

    def test_type_conversion(self, backend):
        """Test type conversion during upgrade (dollars to cents)."""

        @versioned_model("Price")
        class PriceV1(VersionedModel):
            model_backend = backend
            id: str
            price: float  # Dollars

            def upgrade(self):
                return PriceV2(
                    id=self.id,
                    price_cents=round(self.price * 100)  # Use round for float precision
                )

        @versioned_model("Price", latest=True)
        class PriceV2(VersionedModel):
            model_backend = backend
            id: str
            price_cents: int  # Cents

        v1 = PriceV1(id="1", price=19.99)
        v2 = v1.upgrade()

        assert v2.price_cents == 1999


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_optional_fields_with_defaults(self, backend):
        """Test that optional fields get proper defaults."""

        @versioned_model("Optional")
        class OptionalV1(VersionedModel):
            model_backend = backend
            id: str
            name: str

            def upgrade(self):
                return OptionalV2(
                    id=self.id,
                    name=self.name,
                    age=None,  # Optional field
                    active=True  # Field with default
                )

        @versioned_model("Optional", latest=True)
        class OptionalV2(VersionedModel):
            model_backend = backend
            id: str
            name: str
            age: int | None = None
            active: bool = True

        v1 = OptionalV1(id="1", name="Alice")
        v2 = v1.upgrade()

        assert v2.age is None
        assert v2.active is True

    def test_preserve_all_fields(self, backend):
        """Test that all existing fields are preserved during upgrade."""

        @versioned_model("Preserve")
        class PreserveV1(VersionedModel):
            model_backend = backend
            id: str
            field1: str
            field2: int
            field3: bool

            def upgrade(self):
                return PreserveV2(
                    id=self.id,
                    field1=self.field1,
                    field2=self.field2,
                    field3=self.field3,
                    field4="new"
                )

        @versioned_model("Preserve", latest=True)
        class PreserveV2(VersionedModel):
            model_backend = backend
            id: str
            field1: str
            field2: int
            field3: bool
            field4: str

        v1 = PreserveV1(id="1", field1="test", field2=42, field3=True)
        v2 = v1.upgrade()

        assert v2.id == "1"
        assert v2.field1 == "test"
        assert v2.field2 == 42
        assert v2.field3 is True
        assert v2.field4 == "new"

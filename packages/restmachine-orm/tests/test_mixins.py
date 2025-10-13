"""
Tests for built-in mixins with backend extensions.

Tests TimestampMixin, ExpirationMixin, and other provided mixins.
"""

import pytest
from datetime import datetime, timedelta
from typing import ClassVar, Optional
from time import sleep

from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Shared backend
shared_backend = InMemoryBackend(InMemoryAdapter())


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    if hasattr(shared_backend, '_model_extensions'):
        shared_backend._model_extensions.clear()
    if hasattr(shared_backend, '_configured_models'):
        shared_backend._configured_models.clear()
    yield
    shared_backend.clear()


class TestTimestampMixin:
    """Test TimestampMixin functionality."""

    def test_created_at_set_on_create(self):
        """Test that created_at is set when creating a record."""
        from restmachine_orm.mixins import TimestampMixin

        class User(TimestampMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        before_create = datetime.now()
        user = User.create(id="1", name="Alice")
        after_create = datetime.now()

        # created_at should be set
        assert user.created_at is not None
        assert before_create <= user.created_at <= after_create

    def test_updated_at_set_on_create(self):
        """Test that updated_at is set when creating a record."""
        from restmachine_orm.mixins import TimestampMixin

        class User(TimestampMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")

        # updated_at should be set
        assert user.updated_at is not None

    def test_updated_at_changes_on_update(self):
        """Test that updated_at is updated when record is modified."""
        from restmachine_orm.mixins import TimestampMixin

        class User(TimestampMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")
        first_updated = user.updated_at

        # Small delay to ensure timestamp difference
        sleep(0.01)

        # Update user
        user.name = "Alice Smith"
        user.save()

        # updated_at should change
        assert user.updated_at > first_updated

    def test_created_at_does_not_change_on_update(self):
        """Test that created_at remains unchanged on update."""
        from restmachine_orm.mixins import TimestampMixin

        class User(TimestampMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")
        original_created_at = user.created_at

        sleep(0.01)

        # Update user
        user.name = "Alice Smith"
        user.save()

        # created_at should not change
        assert user.created_at == original_created_at

    def test_timestamps_persisted(self):
        """Test that timestamps are persisted to database."""
        from restmachine_orm.mixins import TimestampMixin

        class User(TimestampMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        user = User.create(id="1", name="Alice")

        # Reload from database
        reloaded = User.get(id="1")

        assert reloaded.created_at == user.created_at
        assert reloaded.updated_at == user.updated_at


class TestExpirationMixin:
    """Test ExpirationMixin functionality."""

    def test_is_expired_returns_false_when_no_expiration(self):
        """Test is_expired() returns False when expires_at is None."""
        from restmachine_orm.mixins import ExpirationMixin

        class CacheItem(ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            data: str

        item = CacheItem.create(id="1", data="test")

        # No expiration set
        assert not item.is_expired()

    def test_is_expired_returns_false_when_not_expired(self):
        """Test is_expired() returns False when item hasn't expired yet."""
        from restmachine_orm.mixins import ExpirationMixin

        class CacheItem(ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            data: str

        # Set expiration in future
        future = datetime.now() + timedelta(hours=1)
        item = CacheItem.create(id="1", data="test", expires_at=future)

        assert not item.is_expired()

    def test_is_expired_returns_true_when_expired(self):
        """Test is_expired() returns True when item has expired."""
        from restmachine_orm.mixins import ExpirationMixin

        class CacheItem(ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            data: str

        # Set expiration in past
        past = datetime.now() - timedelta(hours=1)
        item = CacheItem.create(id="1", data="test", expires_at=past)

        assert item.is_expired()

    def test_query_filters_expired_items(self):
        """Test that queries automatically filter out expired items."""
        from restmachine_orm.mixins import ExpirationMixin

        class CacheItem(ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            data: str

        # Create non-expired item
        CacheItem.create(
            id="1",
            data="active",
            expires_at=datetime.now() + timedelta(hours=1)
        )

        # Create expired item
        CacheItem.create(
            id="2",
            data="expired",
            expires_at=datetime.now() - timedelta(hours=1)
        )

        # Create item with no expiration
        CacheItem.create(id="3", data="permanent")

        # Query should only return non-expired items
        items = CacheItem.all()

        # Should get 2 items (active and permanent, not expired)
        assert len(items) == 2
        ids = [item.id for item in items]
        assert "1" in ids
        assert "3" in ids
        assert "2" not in ids

    def test_query_can_include_expired(self):
        """Test that queries can explicitly include expired items."""
        from restmachine_orm.mixins import ExpirationMixin

        class CacheItem(ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            data: str

        # Create expired item
        CacheItem.create(
            id="1",
            data="expired",
            expires_at=datetime.now() - timedelta(hours=1)
        )

        # Normal query filters it out
        assert len(CacheItem.all()) == 0

        # Query with disabled filter includes it
        items = CacheItem.where().disable_filter('expiration').all()
        assert len(items) == 1


class TestMixinComposition:
    """Test multiple mixins working together."""

    def test_timestamp_and_expiration_mixins_together(self):
        """Test TimestampMixin and ExpirationMixin working together."""
        from restmachine_orm.mixins import TimestampMixin, ExpirationMixin

        class Session(TimestampMixin, ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            session_id: str = Field(primary_key=True)
            user_id: str

        # Create session with expiration
        session = Session.create(
            session_id="abc",
            user_id="user1",
            expires_at=datetime.now() + timedelta(hours=1)
        )

        # Both mixins should work
        assert session.created_at is not None  # From TimestampMixin
        assert session.updated_at is not None  # From TimestampMixin
        assert session.expires_at is not None  # From ExpirationMixin
        assert not session.is_expired()  # From ExpirationMixin

    def test_multiple_mixins_serialize_together(self):
        """Test that multiple mixins' extensions all serialize data."""
        from restmachine_orm.mixins import TimestampMixin, ExpirationMixin

        class CachedUser(TimestampMixin, ExpirationMixin, Model):
            model_backend: ClassVar = shared_backend

            id: str = Field(primary_key=True)
            name: str

        # Create with all fields
        user = CachedUser.create(
            id="1",
            name="Alice",
            expires_at=datetime.now() + timedelta(hours=1)
        )

        # All fields should be set and persisted
        reloaded = CachedUser.get(id="1")
        assert reloaded.created_at is not None
        assert reloaded.updated_at is not None
        assert reloaded.expires_at is not None
        assert reloaded.name == "Alice"

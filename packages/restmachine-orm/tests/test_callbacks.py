"""
Tests for model callbacks (before_save and after_save).

This test file demonstrates the callback system for models.
"""

import pytest
from datetime import datetime
from typing import Optional

from restmachine_orm import Model, Field, before_save, after_save
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Shared backend instance
shared_backend = InMemoryBackend(InMemoryAdapter())


class UserWithCallbacks(Model):
    """User model with before_save and after_save callbacks."""

    class Meta:
        backend = shared_backend

    id: str = Field(primary_key=True)
    email: str
    name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Track callback execution
    _before_save_called: int = 0
    _after_save_called: int = 0

    @before_save
    def update_timestamps(self):
        """Update timestamps before saving."""
        now = datetime.now()
        if not self._is_persisted:
            # New record - set created_at
            self.created_at = now
        # Always update updated_at
        self.updated_at = now
        self._before_save_called += 1

    @after_save
    def log_save(self):
        """Log after saving (side effect)."""
        self._after_save_called += 1


class UserWithMultipleCallbacks(Model):
    """User model with multiple callbacks of each type."""

    class Meta:
        backend = shared_backend

    id: str = Field(primary_key=True)
    name: str
    version: int = 0

    # Track callback execution order
    callback_order: list = []

    @before_save
    def first_before_save(self):
        """First before_save callback."""
        self.callback_order.append('before_1')

    @before_save
    def second_before_save(self):
        """Second before_save callback."""
        self.callback_order.append('before_2')
        self.version += 1

    @after_save
    def first_after_save(self):
        """First after_save callback."""
        self.callback_order.append('after_1')

    @after_save
    def second_after_save(self):
        """Second after_save callback."""
        self.callback_order.append('after_2')


class EmailLog:
    """Mock email log for testing side effects."""
    emails_sent: list = []

    @classmethod
    def send(cls, to: str, subject: str):
        """Mock send email."""
        cls.emails_sent.append({'to': to, 'subject': subject})

    @classmethod
    def clear(cls):
        """Clear email log."""
        cls.emails_sent.clear()


class UserWithSideEffects(Model):
    """User model with side effects in after_save."""

    class Meta:
        backend = shared_backend

    id: str = Field(primary_key=True)
    email: str
    name: str

    @after_save
    def send_notification(self):
        """Send notification after save (side effect)."""
        EmailLog.send(self.email, "User saved")


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage and email log before each test."""
    shared_backend.clear()
    EmailLog.clear()
    yield
    shared_backend.clear()
    EmailLog.clear()


class TestBeforeSaveCallback:
    """Test before_save callback functionality."""

    def test_before_save_called_on_create(self):
        """Test that before_save is called when creating a new record."""
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")
        assert user._before_save_called == 0
        assert user.created_at is None
        assert user.updated_at is None

        user.save()

        # before_save should have been called
        assert user._before_save_called == 1
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_before_save_called_on_update(self):
        """Test that before_save is called when updating a record."""
        user = UserWithCallbacks.create(id="user-1", email="alice@example.com", name="Alice")

        # Reset counter after create
        first_updated_at = user.updated_at
        initial_count = user._before_save_called

        # Update the user
        user.name = "Alice Smith"
        user.save()

        # before_save should have been called again
        assert user._before_save_called == initial_count + 1
        assert user.updated_at != first_updated_at
        assert user.updated_at > first_updated_at

    def test_before_save_mutations_persisted(self):
        """Test that mutations in before_save are persisted to database."""
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")
        user.save()

        # Reload from database
        reloaded = UserWithCallbacks.get(id="user-1")

        # Timestamps set in before_save should be persisted
        assert reloaded.created_at is not None
        assert reloaded.updated_at is not None
        assert reloaded.created_at == user.created_at
        assert reloaded.updated_at == user.updated_at

    def test_multiple_before_save_callbacks(self):
        """Test that multiple before_save callbacks are called."""
        user = UserWithMultipleCallbacks(id="user-1", name="Alice")
        user.callback_order = []

        user.save()

        # Both before_save callbacks should have been called
        assert 'before_1' in user.callback_order
        assert 'before_2' in user.callback_order

        # Version should be incremented
        assert user.version == 1

        # Verify persisted
        reloaded = UserWithMultipleCallbacks.get(id="user-1")
        assert reloaded.version == 1


class TestAfterSaveCallback:
    """Test after_save callback functionality."""

    def test_after_save_called_on_create(self):
        """Test that after_save is called when creating a new record."""
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")
        assert user._after_save_called == 0

        user.save()

        # after_save should have been called
        assert user._after_save_called == 1

    def test_after_save_called_on_update(self):
        """Test that after_save is called when updating a record."""
        user = UserWithCallbacks.create(id="user-1", email="alice@example.com", name="Alice")

        initial_count = user._after_save_called

        # Update the user
        user.name = "Alice Smith"
        user.save()

        # after_save should have been called again
        assert user._after_save_called == initial_count + 1

    def test_after_save_mutations_not_persisted(self):
        """Test that mutations in after_save are NOT persisted (it's too late)."""
        # This is more of a documentation test - showing that after_save
        # mutations don't automatically get persisted
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")

        # The _after_save_called counter is incremented in after_save
        user.save()
        assert user._after_save_called == 1

        # But reloading doesn't show the counter change (it's not a persisted field anyway)
        reloaded = UserWithCallbacks.get(id="user-1")
        assert reloaded._after_save_called == 0  # Not persisted

    def test_multiple_after_save_callbacks(self):
        """Test that multiple after_save callbacks are called."""
        user = UserWithMultipleCallbacks(id="user-1", name="Alice")
        user.callback_order = []

        user.save()

        # Both after_save callbacks should have been called
        assert 'after_1' in user.callback_order
        assert 'after_2' in user.callback_order

    def test_after_save_side_effects(self):
        """Test that after_save can trigger side effects like sending notifications."""
        user = UserWithSideEffects(id="user-1", email="alice@example.com", name="Alice")

        # No emails sent yet
        assert len(EmailLog.emails_sent) == 0

        user.save()

        # Notification should have been sent in after_save
        assert len(EmailLog.emails_sent) == 1
        assert EmailLog.emails_sent[0]['to'] == "alice@example.com"
        assert EmailLog.emails_sent[0]['subject'] == "User saved"


class TestCallbackExecutionOrder:
    """Test callback execution order."""

    def test_callback_execution_order(self):
        """Test that callbacks execute in correct order: before_save -> save -> after_save."""
        user = UserWithMultipleCallbacks(id="user-1", name="Alice")
        user.callback_order = []

        user.save()

        # Check order: all before_save callbacks, then all after_save callbacks
        assert user.callback_order == ['before_1', 'before_2', 'after_1', 'after_2']

    def test_before_save_runs_before_persistence(self):
        """Test that before_save runs before data is persisted."""
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")

        # Before save, no timestamps
        assert user.created_at is None

        user.save()

        # After save, timestamps are set and persisted
        reloaded = UserWithCallbacks.get(id="user-1")
        assert reloaded.created_at is not None
        assert reloaded.created_at == user.created_at

    def test_after_save_runs_after_persistence(self):
        """Test that after_save runs after data is persisted."""
        user = UserWithCallbacks(id="user-1", email="alice@example.com", name="Alice")

        user.save()

        # After save completes, record should be in database
        assert user._is_persisted is True
        reloaded = UserWithCallbacks.get(id="user-1")
        assert reloaded is not None

        # And after_save should have been called
        assert user._after_save_called == 1


class TestCallbackWithCreate:
    """Test callbacks work with Model.create() class method."""

    def test_callbacks_called_with_create(self):
        """Test that callbacks are called when using Model.create()."""
        user = UserWithCallbacks.create(id="user-1", email="alice@example.com", name="Alice")

        # before_save should have set timestamps
        assert user.created_at is not None
        assert user.updated_at is not None

        # after_save should have been called
        assert user._after_save_called >= 1


class TestCallbackWithUpsert:
    """Test callbacks work with Model.upsert() class method."""

    def test_callbacks_called_with_upsert(self):
        """Test that callbacks ARE called when using Model.upsert()."""
        user = UserWithCallbacks.upsert(id="user-1", email="alice@example.com", name="Alice")

        # Callbacks should have been called
        assert user._before_save_called >= 1
        assert user._after_save_called >= 1

        # And timestamps should be set by before_save
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_upsert_callbacks_on_overwrite(self):
        """Test that callbacks are called when upsert overwrites existing record."""
        # First create
        user1 = UserWithCallbacks.upsert(id="user-1", email="alice@example.com", name="Alice")
        first_updated = user1.updated_at

        # Upsert same ID (overwrite)
        user2 = UserWithCallbacks.upsert(id="user-1", email="alice@example.com", name="Alice Updated")

        # Callbacks should have been called on second upsert
        assert user2._before_save_called >= 1
        assert user2._after_save_called >= 1

        # Timestamp should be different (updated by before_save)
        assert user2.updated_at != first_updated
        assert user2.updated_at > first_updated

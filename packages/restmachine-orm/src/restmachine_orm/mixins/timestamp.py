"""
TimestampMixin for automatic created_at and updated_at tracking.

Provides automatic timestamp management for models.
"""

from datetime import datetime
from typing import Optional

from restmachine_orm.models.hooks import before_save


class TimestampMixin:
    """
    Mixin that adds automatic timestamp tracking.

    Adds created_at and updated_at fields that are automatically managed:
    - created_at: Set once when the record is created
    - updated_at: Set on creation and updated on every save

    Example:
        >>> class User(TimestampMixin, Model):
        ...     class Meta:
        ...         backend = InMemoryBackend()
        ...     id: str = Field(primary_key=True)
        ...     name: str
        >>>
        >>> user = User.create(id="1", name="Alice")
        >>> print(user.created_at)  # Automatic timestamp
        >>> user.name = "Alice Smith"
        >>> user.save()
        >>> print(user.updated_at)  # Updated timestamp
    """

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @before_save
    def _set_timestamps(self):
        """Set timestamps before saving."""
        now = datetime.now()

        # If created_at is not set, this is a new record
        if self.created_at is None:
            self.created_at = now

        # Always update updated_at
        self.updated_at = now

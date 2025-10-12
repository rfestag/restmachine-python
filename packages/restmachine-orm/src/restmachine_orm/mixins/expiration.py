"""
ExpirationMixin for automatic expiration tracking and filtering.

Provides automatic expiration management for models with TTL support.
"""

from datetime import datetime
from typing import Optional, Any



class ExpirationMixin:
    """
    Mixin that adds expiration tracking.

    Adds an expires_at field and automatic filtering of expired items.
    Items with expires_at in the past are automatically filtered out of
    query results (can be disabled with disable_filter('expiration')).

    Example:
        >>> from datetime import datetime, timedelta
        >>> class CacheItem(ExpirationMixin, Model):
        ...     class Meta:
        ...         backend = InMemoryBackend()
        ...     id: str = Field(primary_key=True)
        ...     data: str
        >>>
        >>> # Create item that expires in 1 hour
        >>> item = CacheItem.create(
        ...     id="1",
        ...     data="cached",
        ...     expires_at=datetime.now() + timedelta(hours=1)
        ... )
        >>> print(item.is_expired())  # False
        >>>
        >>> # Queries automatically filter expired items
        >>> items = CacheItem.all()  # Only returns non-expired items
        >>>
        >>> # Explicitly include expired items
        >>> all_items = CacheItem.where().disable_filter('expiration').all()
    """

    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """
        Check if this item has expired.

        Returns:
            True if expires_at is set and in the past, False otherwise
        """
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.now()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-add expiration filter when model is created."""
        super().__init_subclass__(**kwargs)

        # Register the expiration filter to be added to all queries
        if not hasattr(cls, '_auto_query_filters'):
            cls._auto_query_filters = []  # type: ignore[attr-defined]

        def add_expiration_filter(query: Any) -> Any:
            """Add automatic expiration filter."""
            def not_expired(item: Any) -> bool:
                if not hasattr(item, 'is_expired'):
                    return True
                return not item.is_expired()

            return query.add_result_filter('expiration', not_expired)

        cls._auto_query_filters.append(add_expiration_filter)  # type: ignore[attr-defined]

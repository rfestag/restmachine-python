"""
Base query builder for RestMachine ORM.

Provides a fluent interface for building database queries in a
backend-agnostic way.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class QueryBuilder(ABC):
    """
    Abstract base class for query builders.

    Provides a fluent interface for constructing queries. Each backend
    implements its own QueryBuilder that translates to backend-specific
    query language (DynamoDB expressions, OpenSearch DSL, etc.).
    """

    def __init__(self, model_class: type["Model"]):
        """
        Initialize query builder.

        Args:
            model_class: The model class being queried
        """
        self.model_class = model_class
        self._filters: list[tuple[str, dict[str, Any]]] = []  # (operator, conditions)
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._order_by: list[str] = []
        self._select_fields: Optional[list[str]] = None
        self._cursor: Optional[Any] = None  # Backend-specific pagination cursor

    def and_(self, **conditions: Any) -> "QueryBuilder":
        """
        Add AND conditions to the query.

        All conditions are ANDed together.

        Args:
            **conditions: Filter conditions to AND

        Returns:
            Self for method chaining

        Example:
            >>> query = User.where(age__gte=18).and_(status="active")
            >>> # Equivalent to: age >= 18 AND status = 'active'
        """
        if conditions:
            self._filters.append(("and", conditions))
        return self

    def or_(self, **conditions: Any) -> "QueryBuilder":
        """
        Add OR conditions to the query.

        Args:
            **conditions: Filter conditions to OR

        Returns:
            Self for method chaining

        Example:
            >>> query = User.where(role="admin").or_(role="moderator")
            >>> # Equivalent to: role = 'admin' OR role = 'moderator'
        """
        if conditions:
            self._filters.append(("or", conditions))
        return self

    def not_(self, **conditions: Any) -> "QueryBuilder":
        """
        Add NOT conditions to the query.

        Args:
            **conditions: Filter conditions to NOT

        Returns:
            Self for method chaining

        Example:
            >>> query = User.where().not_(status="deleted")
            >>> # Equivalent to: NOT (status = 'deleted')
        """
        if conditions:
            self._filters.append(("not", conditions))
        return self

    def limit(self, n: int) -> "QueryBuilder":
        """
        Limit the number of results.

        Args:
            n: Maximum number of results

        Returns:
            Self for method chaining

        Example:
            >>> query.limit(10)
        """
        self._limit = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        """
        Skip the first n results.

        Args:
            n: Number of results to skip

        Returns:
            Self for method chaining

        Example:
            >>> query.offset(20)  # Skip first 20 results
        """
        self._offset = n
        return self

    def order_by(self, *fields: str) -> "QueryBuilder":
        """
        Order results by fields.

        Use "-" prefix for descending order.

        Args:
            *fields: Field names to order by

        Returns:
            Self for method chaining

        Example:
            >>> query.order_by("-created_at", "name")  # Newest first, then by name
        """
        self._order_by.extend(fields)
        return self

    def select(self, *fields: str) -> "QueryBuilder":
        """
        Select only specific fields (projection).

        Args:
            *fields: Field names to select

        Returns:
            Self for method chaining

        Example:
            >>> query.select("id", "name", "email")
        """
        self._select_fields = list(fields)
        return self

    def cursor(self, cursor: Optional[Any]) -> "QueryBuilder":
        """
        Set a pagination cursor for continuing a previous query.

        The cursor is backend-specific and opaque. It allows the backend
        to continue fetching results from where it left off.

        Args:
            cursor: Backend-specific cursor from a previous paginate() call

        Returns:
            Self for method chaining

        Example:
            >>> results, next_cursor = User.where().limit(10).paginate()
            >>> # Get next page
            >>> more_results, cursor = User.where().limit(10).cursor(next_cursor).paginate()
        """
        self._cursor = cursor
        return self

    @abstractmethod
    def all(self) -> list["Model"]:
        """
        Execute the query and return all results.

        Returns:
            List of model instances

        Example:
            >>> users = User.query().filter(age__gte=18).all()
        """
        pass

    @abstractmethod
    def first(self) -> Optional["Model"]:
        """
        Execute the query and return the first result.

        Returns:
            First model instance, or None if no results

        Example:
            >>> user = User.where().filter(email="alice@example.com").first()
        """
        pass

    def last(self) -> Optional["Model"]:
        """
        Execute the query and return the last result.

        This is equivalent to reversing the order and returning the first element.
        If no explicit ordering is set, results in natural backend order reversed.

        Returns:
            Last model instance, or None if no results

        Example:
            >>> user = User.where().order_by("created_at").last()  # Most recent
            >>> user = User.where().order_by("-created_at").last()  # Oldest
        """
        # If no ordering specified, we can't reliably reverse
        # So we just get all results and return the last one
        if not self._order_by:
            results = self.all()
            return results[-1] if results else None

        # Reverse all order_by fields
        reversed_order = []
        for field in self._order_by:
            if field.startswith("-"):
                # Remove the minus to reverse descending -> ascending
                reversed_order.append(field[1:])
            else:
                # Add minus to reverse ascending -> descending
                reversed_order.append(f"-{field}")

        # Save current order_by and replace with reversed
        original_order_by = self._order_by
        self._order_by = reversed_order
        result = self.first()
        # Restore original order_by
        self._order_by = original_order_by
        return result

    @abstractmethod
    def count(self) -> int:
        """
        Count the number of results without fetching them.

        Returns:
            Number of matching records

        Example:
            >>> total = User.query().filter(age__gte=18).count()
        """
        pass

    @abstractmethod
    def exists(self) -> bool:
        """
        Check if any results exist without fetching them.

        Returns:
            True if at least one record matches

        Example:
            >>> if User.where().filter(email="alice@example.com").exists():
            ...     print("Email already registered")
        """
        pass

    @abstractmethod
    def paginate(self) -> tuple[list["Model"], Optional[Any]]:
        """
        Execute the query and return results with a pagination cursor.

        Returns a tuple of (results, next_cursor). The cursor is backend-specific
        and opaque. It can be passed to cursor() on a new query to continue
        fetching results from where this query left off.

        Returns:
            Tuple of (list of model instances, next cursor or None if no more results)

        Example:
            >>> # First page
            >>> results, cursor = User.where().limit(10).paginate()
            >>> print(f"Got {len(results)} results")
            >>>
            >>> # Next page
            >>> if cursor:
            ...     more_results, next_cursor = User.where().limit(10).cursor(cursor).paginate()
        """
        pass

    def get(self, **conditions: Any) -> Optional["Model"]:
        """
        Get a single record matching conditions.

        Raises an error if multiple records match.

        Args:
            **conditions: Filter conditions

        Returns:
            Model instance, or None if not found

        Raises:
            MultipleResultsError: If multiple records match

        Example:
            >>> user = User.query().get(email="alice@example.com")
        """
        results = self.and_(**conditions).limit(2).all()
        if len(results) > 1:
            raise MultipleResultsError(
                f"Expected 1 result, got {len(results)}"
            )
        return results[0] if results else None

    def __iter__(self):
        """
        Make query builder iterable.

        Example:
            >>> for user in User.query().filter(age__gte=18):
            ...     print(user.name)
        """
        return iter(self.all())

    def __len__(self):
        """
        Get count of results.

        Example:
            >>> num_users = len(User.query().filter(age__gte=18))
        """
        return self.count()

    def __bool__(self):
        """
        Check if query has results.

        Example:
            >>> if User.query().filter(email="test@example.com"):
            ...     print("User exists")
        """
        return self.exists()


class MultipleResultsError(Exception):
    """Raised when get() returns multiple results."""
    pass

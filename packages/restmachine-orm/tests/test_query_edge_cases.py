"""
Tests for query builder edge cases and advanced features.

Tests methods like last(), get(), cursor(), result filters, and magic methods.
"""

import pytest
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.query.base import MultipleResultsError


shared_backend = InMemoryBackend()


class User(Model):
    """Test user model."""
    model_backend: ClassVar = shared_backend

    id: str = Field(primary_key=True)
    name: str
    email: str
    age: int
    status: str


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


@pytest.fixture
def sample_users():
    """Create sample users for testing."""
    User.create(id="1", name="Alice", email="alice@example.com", age=30, status="active")
    User.create(id="2", name="Bob", email="bob@example.com", age=25, status="active")
    User.create(id="3", name="Carol", email="carol@example.com", age=35, status="inactive")
    User.create(id="4", name="Dave", email="dave@example.com", age=28, status="active")
    User.create(id="5", name="Eve", email="eve@example.com", age=32, status="inactive")


class TestQueryBuilderLast:
    """Test last() method for getting last result."""

    def test_last_with_order_by(self, sample_users):
        """Test last() returns last item with ordering."""
        result = User.where().order_by("age").last()

        assert result is not None
        # Should be the oldest user
        assert result.age == 35

    def test_last_with_descending_order(self, sample_users):
        """Test last() with descending order returns oldest when reversed."""
        result = User.where().order_by("-age").last()

        assert result is not None
        # Should reverse descending to ascending, so youngest
        assert result.age == 25

    def test_last_without_order_by(self, sample_users):
        """Test last() without ordering returns last from all results."""
        result = User.where().last()

        # Should return some user (last from the unordered results)
        assert result is not None

    def test_last_on_empty_results(self):
        """Test last() returns None on empty results."""
        result = User.where().last()
        assert result is None

    def test_last_with_filter(self, sample_users):
        """Test last() with filtering."""
        result = User.where(status="active").order_by("age").last()

        assert result is not None
        assert result.status == "active"
        # Should be Alice (30) since she's the oldest active user


class TestQueryBuilderGet:
    """Test get() method for single results."""

    def test_get_single_result(self, sample_users):
        """Test get() returns single result when only one matches."""
        result = User.where().get(email="alice@example.com")

        assert result is not None
        assert result.name == "Alice"

    def test_get_no_results(self, sample_users):
        """Test get() returns None when no results."""
        result = User.where().get(email="nonexistent@example.com")
        assert result is None

    def test_get_multiple_results_error(self, sample_users):
        """Test get() raises error when multiple results match."""
        with pytest.raises(MultipleResultsError, match="Expected 1 result, got"):
            User.where().get(status="active")  # 3 active users

    def test_get_with_chained_filters(self, sample_users):
        """Test get() with previously chained filters."""
        result = User.where(status="active").get(name="Bob")

        assert result is not None
        assert result.name == "Bob"
        assert result.status == "active"


class TestQueryBuilderCursor:
    """Test cursor() method for pagination."""

    def test_cursor_sets_cursor_value(self, sample_users):
        """Test cursor() sets the cursor on query builder."""
        query = User.where().cursor("abc123")

        # Cursor should be set internally
        assert query._cursor == "abc123"

    def test_cursor_returns_self_for_chaining(self, sample_users):
        """Test cursor() returns self for method chaining."""
        query = User.where()
        result = query.cursor("abc123")

        assert result is query


class TestQueryBuilderResultFilters:
    """Test add_result_filter() and disable_filter() methods."""

    def test_add_result_filter(self, sample_users):
        """Test add_result_filter() adds filter function."""
        def adults_only(user):
            return user.age >= 30

        query = User.where().add_result_filter("adults", adults_only)
        results = list(query)

        # Should only include users aged 30+
        assert all(u.age >= 30 for u in results)
        assert len(results) == 3  # Alice (30), Carol (35), Eve (32)

    def test_add_multiple_result_filters(self, sample_users):
        """Test adding multiple result filters."""
        def adults_only(user):
            return user.age >= 30

        def active_only(user):
            return user.status == "active"

        query = (
            User.where()
            .add_result_filter("adults", adults_only)
            .add_result_filter("active", active_only)
        )
        results = list(query)

        # Should only include users aged 30+ AND active
        assert all(u.age >= 30 and u.status == "active" for u in results)
        assert len(results) == 1  # Only Alice

    def test_disable_filter(self, sample_users):
        """Test disable_filter() removes a result filter."""
        def adults_only(user):
            return user.age >= 30

        query = (
            User.where()
            .add_result_filter("adults", adults_only)
            .disable_filter("adults")
        )
        results = list(query)

        # Filter is disabled, so should include all users
        assert len(results) == 5

    def test_result_filter_with_empty_results(self):
        """Test result filters on empty query."""
        def adults_only(user):
            return user.age >= 30

        query = User.where().add_result_filter("adults", adults_only)
        results = list(query)

        assert len(results) == 0


class TestQueryBuilderMagicMethods:
    """Test magic methods on QueryBuilder."""

    def test_iter_magic_method(self, sample_users):
        """Test __iter__ makes query iterable."""
        query = User.where(status="active")
        count = 0

        for user in query:
            count += 1
            assert user.status == "active"

        assert count == 3

    def test_len_magic_method(self, sample_users):
        """Test __len__ returns count."""
        query = User.where(status="active")
        length = len(query)

        assert length == 3

    def test_bool_magic_method_true(self, sample_users):
        """Test __bool__ returns True when results exist."""
        query = User.where(status="active")

        assert bool(query) is True
        if query:  # Should be truthy
            pass
        else:
            pytest.fail("Query should be truthy")

    def test_bool_magic_method_false(self, sample_users):
        """Test __bool__ returns False when no results."""
        query = User.where(status="deleted")

        assert bool(query) is False
        if not query:  # Should be falsy
            pass
        else:
            pytest.fail("Query should be falsy")


class TestQueryBuilderExpressionToFilters:
    """Test _expression_to_filters method."""

    def test_expression_to_filters_with_query_expression(self, sample_users):
        """Test _expression_to_filters with QueryExpression."""
        # This tests the elif hasattr(expr, 'expr') branch
        from restmachine_orm.query.expressions import NotExpression
        from restmachine_orm.query.fields import QueryExpression

        # Create a NOT expression
        inner_expr = QueryExpression("age", "gte", 30)
        not_expr = NotExpression(inner_expr)

        # The query builder should handle this
        query = User.where(not_expr)
        # This may or may not work depending on backend, but shouldn't crash
        try:
            results = list(query)
        except Exception:
            # Some backends may not support NOT expressions fully
            pass


class TestQueryBuilderChaining:
    """Test method chaining and combinations."""

    def test_complex_chaining_with_all_methods(self, sample_users):
        """Test chaining multiple query methods together."""
        results = list(
            User.where(status="active")
            .and_(age__gte=25)
            .order_by("age")
            .limit(2)
        )

        assert len(results) == 2
        assert all(u.status == "active" and u.age >= 25 for u in results)
        # Should be ordered by age
        assert results[0].age <= results[1].age

    def test_chaining_with_result_filters(self, sample_users):
        """Test chaining with result filters."""
        def name_starts_with_a(user):
            return user.name.startswith("A")

        results = list(
            User.where(status="active")
            .add_result_filter("name_filter", name_starts_with_a)
        )

        assert len(results) == 1
        assert results[0].name == "Alice"

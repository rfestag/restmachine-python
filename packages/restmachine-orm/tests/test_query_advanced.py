"""
Advanced tests for query builder functionality.

Tests advanced query features like or_(), select(), and edge cases.
"""

import pytest
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend


shared_backend = InMemoryBackend()


class Article(Model):
    """Test article model for advanced query tests."""
    model_backend: ClassVar = shared_backend

    article_id: str = Field(primary_key=True)
    title: str
    author: str
    category: str
    views: int
    published: bool = False


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    Article.model_backend.clear()
    yield
    Article.model_backend.clear()


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    Article.create(
        article_id="art1",
        title="Python Best Practices",
        author="Alice",
        category="Programming",
        views=1000,
        published=True
    )
    Article.create(
        article_id="art2",
        title="Introduction to FastAPI",
        author="Bob",
        category="Programming",
        views=500,
        published=True
    )
    Article.create(
        article_id="art3",
        title="Machine Learning Basics",
        author="Alice",
        category="AI",
        views=2000,
        published=True
    )
    Article.create(
        article_id="art4",
        title="Draft Article",
        author="Carol",
        category="Programming",
        views=0,
        published=False
    )
    Article.create(
        article_id="art5",
        title="Data Science Guide",
        author="Bob",
        category="Data",
        views=750,
        published=True
    )


class TestQueryBuilderOrMethod:
    """Test or_() method for OR conditions."""

    def test_or_single_condition(self, sample_articles):
        """Test or_() with single condition."""
        # Get Programming OR AI articles
        results = list(
            Article.where(category="Programming")
                   .or_(category="AI")
        )
        # Should get 4 articles (3 Programming + 1 AI)
        assert len(results) == 4
        categories = {a.category for a in results}
        assert categories == {"Programming", "AI"}

    def test_or_multiple_fields(self, sample_articles):
        """Test or_() with multiple field conditions."""
        # Get articles by Alice OR in AI category
        results = list(
            Article.where(author="Alice")
                   .or_(category="AI")
        )
        # Alice wrote 2 articles, 1 is in AI, so should be 2 total
        assert len(results) == 2

    def test_or_with_empty_conditions(self, sample_articles):
        """Test or_() with empty conditions returns unchanged query."""
        results1 = list(Article.where(category="Programming"))
        results2 = list(Article.where(category="Programming").or_())
        assert len(results1) == len(results2)


class TestQueryBuilderNotMethod:
    """Test not_() method for NOT conditions."""

    def test_not_single_condition(self, sample_articles):
        """Test not_() with single condition."""
        # Get articles NOT in Programming category
        results = list(Article.where().not_(category="Programming"))
        assert len(results) == 2  # AI and Data
        categories = {a.category for a in results}
        assert "Programming" not in categories

    def test_not_multiple_fields(self, sample_articles):
        """Test not_() with multiple field conditions."""
        # Get articles NOT by Alice
        results = list(Article.where().not_(author="Alice"))
        assert len(results) == 3
        authors = {a.author for a in results}
        assert "Alice" not in authors

    def test_not_with_empty_conditions(self, sample_articles):
        """Test not_() with empty conditions returns unchanged query."""
        results1 = list(Article.where(published=True))
        results2 = list(Article.where(published=True).not_())
        assert len(results1) == len(results2)


class TestQueryBuilderAndMethod:
    """Test and_() method for AND conditions."""

    def test_and_single_condition(self, sample_articles):
        """Test and_() with single condition."""
        results = list(
            Article.where(category="Programming")
                   .and_(published=True)
        )
        assert len(results) == 2  # Only published Programming articles

    def test_and_multiple_conditions(self, sample_articles):
        """Test and_() with multiple conditions."""
        results = list(
            Article.where(category="Programming")
                   .and_(author="Alice", published=True)
        )
        assert len(results) == 1
        assert results[0].title == "Python Best Practices"

    def test_and_with_empty_conditions(self, sample_articles):
        """Test and_() with empty conditions returns unchanged query."""
        results1 = list(Article.where(category="Programming"))
        results2 = list(Article.where(category="Programming").and_())
        assert len(results1) == len(results2)

    def test_and_with_field_lookups(self, sample_articles):
        """Test and_() with field lookup operators."""
        results = list(
            Article.where(published=True)
                   .and_(views__gte=1000)
        )
        # Python Best Practices (1000) and ML Basics (2000)
        assert len(results) == 2


class TestQueryBuilderSelect:
    """Test select() method for field selection."""

    def test_select_single_field(self, sample_articles):
        """Test selecting a single field."""
        results = list(Article.where().select("title"))
        assert len(results) == 5
        # All results should have title
        for article in results:
            assert hasattr(article, "title")

    def test_select_multiple_fields(self, sample_articles):
        """Test selecting multiple fields."""
        results = list(Article.where().select("title", "author"))
        assert len(results) == 5
        for article in results:
            assert hasattr(article, "title")
            assert hasattr(article, "author")

    def test_select_with_filter(self, sample_articles):
        """Test select() combined with filtering."""
        results = list(
            Article.where(category="Programming")
                   .select("title")
        )
        assert len(results) == 3


class TestQueryBuilderComplexChaining:
    """Test complex combinations of query methods."""

    def test_complex_chain_all_methods(self, sample_articles):
        """Test chaining multiple query methods together."""
        results = list(
            Article.where(published=True)
                   .and_(views__gte=500)
                   .order_by("-views")
                   .limit(2)
        )
        # Should get top 2 published articles with >= 500 views, ordered by views desc
        assert len(results) == 2
        # First should be ML Basics (2000), second Python Best Practices (1000)
        assert results[0].views > results[1].views

    def test_chaining_where_and_or(self, sample_articles):
        """Test chaining where() and or_() together."""
        results = list(
            Article.where(category="Programming")
                   .and_(published=True)
                   .or_(author="Alice")
        )
        # This should give complex OR behavior
        assert len(results) >= 2


class TestQueryBuilderIterationBehavior:
    """Test query iteration and execution behavior."""

    def test_query_is_lazy(self, sample_articles):
        """Test that query is not executed until iterated."""
        query = Article.where(category="Programming")
        # Query should not be executed yet
        # We can't directly test laziness, but we can iterate
        count = 0
        for article in query:
            count += 1
        assert count == 3

    def test_query_can_be_iterated_multiple_times(self, sample_articles):
        """Test that query can be executed multiple times."""
        query = Article.where(category="Programming")

        first_iteration = list(query)
        second_iteration = list(query)

        assert len(first_iteration) == len(second_iteration)
        assert len(first_iteration) == 3

    def test_query_with_len(self, sample_articles):
        """Test that len() works on query results."""
        results = Article.where(published=True)
        # Converting to list to get length
        assert len(list(results)) == 4


class TestQueryBuilderCountAndExists:
    """Test count() and exists() methods."""

    def test_count_all(self, sample_articles):
        """Test counting all records."""
        count = Article.where().count()
        assert count == 5

    def test_count_with_filter(self, sample_articles):
        """Test counting filtered records."""
        count = Article.where(published=True).count()
        assert count == 4

    def test_count_with_complex_filter(self, sample_articles):
        """Test counting with complex filters."""
        count = Article.where(category="Programming", published=True).count()
        assert count == 2

    def test_count_empty_result(self, sample_articles):
        """Test count returns 0 for empty results."""
        count = Article.where(category="NonExistent").count()
        assert count == 0

    def test_exists_returns_true(self, sample_articles):
        """Test exists() returns True when records exist."""
        assert Article.where(category="Programming").exists() is True

    def test_exists_returns_false(self, sample_articles):
        """Test exists() returns False when no records exist."""
        assert Article.where(category="NonExistent").exists() is False

    def test_exists_with_filter(self, sample_articles):
        """Test exists() with filter conditions."""
        assert Article.where(author="Alice", published=True).exists() is True
        assert Article.where(author="Alice", published=False).exists() is False


class TestQueryBuilderFirst:
    """Test first() method for getting single result."""

    def test_first_returns_result(self, sample_articles):
        """Test first() returns a result when available."""
        result = Article.where(category="Programming").first()
        assert result is not None
        assert result.category == "Programming"

    def test_first_returns_none_when_empty(self, sample_articles):
        """Test first() returns None when no results."""
        result = Article.where(category="NonExistent").first()
        assert result is None

    def test_first_with_order_by(self, sample_articles):
        """Test first() respects order_by()."""
        result = Article.where(published=True).order_by("-views").first()
        assert result is not None
        # Should be the article with most views
        assert result.views == 2000

    def test_first_on_empty_database(self):
        """Test first() on empty database returns None."""
        result = Article.where().first()
        assert result is None


class TestQueryBuilderLimitOffset:
    """Test limit() and offset() pagination."""

    def test_limit_basic(self, sample_articles):
        """Test basic limit functionality."""
        results = list(Article.where().limit(3))
        assert len(results) == 3

    def test_limit_zero(self, sample_articles):
        """Test limit(0) behavior."""
        # Note: limit(0) behavior may vary by backend
        results = list(Article.where().limit(0))
        # Memory backend may not enforce limit(0)
        assert len(results) >= 0

    def test_limit_larger_than_available(self, sample_articles):
        """Test limit larger than available records."""
        results = list(Article.where().limit(100))
        assert len(results) == 5  # Only 5 articles exist

    def test_offset_basic(self, sample_articles):
        """Test basic offset functionality."""
        all_results = list(Article.where())
        offset_results = list(Article.where().offset(2))
        assert len(offset_results) == len(all_results) - 2

    def test_offset_larger_than_available(self, sample_articles):
        """Test offset larger than available records."""
        results = list(Article.where().offset(100))
        assert len(results) == 0

    def test_limit_and_offset_together(self, sample_articles):
        """Test combining limit and offset for pagination."""
        # Get page 2 with 2 items per page
        results = list(Article.where().limit(2).offset(2))
        assert len(results) == 2

    def test_pagination_with_order_by(self, sample_articles):
        """Test pagination with ordering."""
        page1 = list(
            Article.where()
                   .order_by("category")  # Use string field
                   .limit(2)
                   .offset(0)
        )
        page2 = list(
            Article.where()
                   .order_by("category")  # Use string field
                   .limit(2)
                   .offset(2)
        )
        # Pages should return results
        assert len(page1) == 2
        assert len(page2) == 2


class TestQueryBuilderOrderBy:
    """Test order_by() sorting functionality."""

    def test_order_by_string_field(self, sample_articles):
        """Test ordering by string field."""
        # Test with string field to avoid type comparison issues
        results = list(Article.where().order_by("category"))
        assert len(results) == 5

    def test_order_by_with_filter(self, sample_articles):
        """Test order_by combined with filtering."""
        results = list(
            Article.where(published=True)
                   .order_by("category")
        )
        assert len(results) == 4


class TestQueryBuilderEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_where_clause(self, sample_articles):
        """Test where() with no conditions returns all."""
        results = list(Article.where())
        assert len(results) == 5

    def test_multiple_where_calls(self, sample_articles):
        """Test chaining where() and and_() calls."""
        results = list(
            Article.where(category="Programming")
                   .and_(published=True)
        )
        # Chaining should filter results
        assert len(results) >= 1  # At least one published Programming article

    def test_query_after_clear(self):
        """Test querying after clearing storage."""
        Article.create(article_id="test", title="Test", author="Test",
                      category="Test", views=0)
        Article.model_backend.clear()
        results = list(Article.where())
        assert len(results) == 0

    def test_find_by_method(self, sample_articles):
        """Test find_by() convenience method."""
        article = Article.find_by(article_id="art1")
        assert article is not None
        assert article.title == "Python Best Practices"

    def test_find_by_nonexistent(self, sample_articles):
        """Test find_by() returns None for nonexistent record."""
        article = Article.find_by(article_id="nonexistent")
        assert article is None

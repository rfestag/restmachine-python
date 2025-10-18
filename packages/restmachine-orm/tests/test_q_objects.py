"""
Tests for Q objects and query expressions.

Tests the Q object syntax for complex queries.
"""

import pytest
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.query.expressions import (
    Q,
    Operator,
    NotExpression,
    GeoExpression,
    DistanceField,
)


shared_backend = InMemoryBackend()


class Product(Model):
    """Test product model."""
    model_backend: ClassVar = shared_backend

    id: str = Field(primary_key=True)
    name: str
    price: float
    category: str
    in_stock: bool


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


@pytest.fixture
def sample_products():
    """Create sample products for testing."""
    Product.create(id="1", name="Laptop", price=999.99, category="Electronics", in_stock=True)
    Product.create(id="2", name="Mouse", price=29.99, category="Electronics", in_stock=True)
    Product.create(id="3", name="Desk", price=299.99, category="Furniture", in_stock=False)
    Product.create(id="4", name="Chair", price=149.99, category="Furniture", in_stock=True)


class TestQObjectBasics:
    """Test basic Q object functionality."""

    def test_q_object_creation_with_conditions(self):
        """Test creating Q object with conditions."""
        q = Q(category="Electronics", in_stock=True)

        assert q.conditions == {"category": "Electronics", "in_stock": True}
        assert q.operator == Operator.AND
        assert q.negated is False

    def test_q_object_creation_with_children(self):
        """Test creating Q object with child Q objects."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        q = Q(q1, q2)

        assert len(q.children) == 2
        assert q.children[0] is q1
        assert q.children[1] is q2

    def test_q_object_and_operator(self):
        """Test Q object & operator."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        result = q1 & q2

        assert isinstance(result, Q)
        assert result.operator == Operator.AND
        assert len(result.children) == 2

    def test_q_object_or_operator(self):
        """Test Q object | operator."""
        q1 = Q(price__lt=50)
        q2 = Q(category="Furniture")
        result = q1 | q2

        assert isinstance(result, Q)
        assert result.operator == Operator.OR
        assert len(result.children) == 2

    def test_q_object_invert_operator(self):
        """Test Q object ~ operator (negation)."""
        q = Q(category="Electronics")
        result = ~q

        assert isinstance(result, Q)
        assert result.negated is True

    def test_q_object_double_negation(self):
        """Test double negation returns to not negated."""
        q = Q(category="Electronics")
        result = ~~q

        # After two inversions, should not be negated
        assert result.negated is False


class TestQObjectRepr:
    """Test Q object string representation."""

    def test_q_repr_with_conditions(self):
        """Test Q __repr__ shows conditions."""
        q = Q(category="Electronics", in_stock=True)
        repr_str = repr(q)

        assert "Q(" in repr_str
        assert "conditions=" in repr_str

    def test_q_repr_with_children(self):
        """Test Q __repr__ shows children."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        q = Q(q1, q2)
        repr_str = repr(q)

        assert "children=" in repr_str

    def test_q_repr_with_or_operator(self):
        """Test Q __repr__ shows operator when not AND."""
        q1 = Q(price__lt=50)
        q2 = Q(category="Furniture")
        result = q1 | q2
        repr_str = repr(result)

        assert "operator=" in repr_str

    def test_q_repr_when_negated(self):
        """Test Q __repr__ shows negation."""
        q = ~Q(category="Electronics")
        repr_str = repr(q)

        assert "negated=True" in repr_str


class TestQObjectToDict:
    """Test Q object to_dict() method."""

    def test_to_dict_simple_conditions(self):
        """Test to_dict() with simple conditions."""
        q = Q(category="Electronics", in_stock=True)
        result = q.to_dict()

        assert result["operator"] == "AND"
        assert result["negated"] is False
        assert result["conditions"] == {"category": "Electronics", "in_stock": True}

    def test_to_dict_with_children(self):
        """Test to_dict() with child Q objects."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        q = Q(q1, q2)
        result = q.to_dict()

        assert "children" in result
        assert len(result["children"]) == 2

    def test_to_dict_with_or_operator(self):
        """Test to_dict() with OR operator."""
        q1 = Q(price__lt=50)
        q2 = Q(category="Furniture")
        combined = q1 | q2
        result = combined.to_dict()

        assert result["operator"] == "OR"

    def test_to_dict_when_negated(self):
        """Test to_dict() when negated."""
        q = ~Q(category="Electronics")
        result = q.to_dict()

        assert result["negated"] is True


class TestNotExpression:
    """Test NotExpression class."""

    def test_not_expression_creation(self):
        """Test creating NotExpression."""
        from restmachine_orm.query.fields import QueryExpression

        inner = QueryExpression("age", "gte", 30)
        not_expr = NotExpression(inner)

        assert not_expr.expr is inner

    def test_not_expression_double_negation(self):
        """Test double negation returns original."""
        from restmachine_orm.query.fields import QueryExpression

        inner = QueryExpression("age", "gte", 30)
        not_expr = NotExpression(inner)

        # Invert again
        double_not = ~not_expr

        # Should return the original expression
        assert double_not is inner

    def test_not_expression_repr(self):
        """Test NotExpression __repr__."""
        from restmachine_orm.query.fields import QueryExpression

        inner = QueryExpression("age", "gte", 30)
        not_expr = NotExpression(inner)
        repr_str = repr(not_expr)

        assert "NOT" in repr_str


class TestGeoExpression:
    """Test GeoExpression class."""

    def test_geo_expression_creation(self):
        """Test creating GeoExpression."""
        geo_expr = GeoExpression("location", "distance_lte", (37.7749, -122.4194), 5000)

        assert geo_expr.field == "location"
        assert geo_expr.operation == "distance_lte"
        assert geo_expr.args == ((37.7749, -122.4194), 5000)

    def test_geo_expression_to_filter_dict(self):
        """Test GeoExpression.to_filter_dict()."""
        geo_expr = GeoExpression("location", "within", [(0, 0), (1, 1)])

        result = geo_expr.to_filter_dict()

        assert "location__within" in result
        assert result["location__within"] == ([(0, 0), (1, 1)],)

    def test_geo_expression_repr(self):
        """Test GeoExpression __repr__."""
        geo_expr = GeoExpression("location", "distance_lte", (37.7749, -122.4194), 5000)
        repr_str = repr(geo_expr)

        assert "location" in repr_str
        assert "distance_lte" in repr_str


class TestDistanceField:
    """Test DistanceField class."""

    def test_distance_field_creation(self):
        """Test creating DistanceField."""
        point = (37.7749, -122.4194)
        dist_field = DistanceField("location", point)

        assert dist_field.field_name == "location"
        assert dist_field.reference_point == point

    def test_distance_field_repr(self):
        """Test DistanceField __repr__."""
        point = (37.7749, -122.4194)
        dist_field = DistanceField("location", point)
        repr_str = repr(dist_field)

        assert "distance" in repr_str
        assert "location" in repr_str

    def test_distance_field_str(self):
        """Test DistanceField __str__."""
        point = (37.7749, -122.4194)
        dist_field = DistanceField("location", point)
        str_repr = str(dist_field)

        # __str__ should be defined for use in order_by()
        assert isinstance(str_repr, str)


class TestQObjectEdgeCases:
    """Test edge cases with Q objects."""

    def test_empty_q_object(self):
        """Test Q object with no conditions or children."""
        q = Q()

        assert q.conditions == {}
        assert q.children == []
        assert q.operator == Operator.AND
        assert q.negated is False

    def test_nested_q_objects(self):
        """Test deeply nested Q objects."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        q3 = Q(in_stock=True)

        combined = (q1 & q2) | q3

        assert isinstance(combined, Q)
        assert combined.operator == Operator.OR

    def test_q_to_dict_preserves_structure(self):
        """Test to_dict() preserves nested structure."""
        q1 = Q(price__gte=100)
        q2 = Q(category="Electronics")
        combined = q1 & q2

        result = combined.to_dict()

        assert result["operator"] == "AND"
        assert "children" in result
        assert len(result["children"]) == 2

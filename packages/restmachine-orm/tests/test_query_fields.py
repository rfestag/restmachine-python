"""
Tests for QueryField class and geospatial query methods.

Tests QueryField operators and geo query methods.
"""

import pytest
from typing import ClassVar
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.query.fields import QueryField
from restmachine_orm.query.expressions import GeoExpression, DistanceField


shared_backend = InMemoryBackend()


class Location(Model):
    """Test model with fields."""
    model_backend: ClassVar = shared_backend

    id: str = Field(primary_key=True)
    name: str
    lat: float
    lng: float


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


class TestQueryFieldBasics:
    """Test QueryField basic functionality."""

    def test_query_field_creation(self):
        """Test creating a QueryField."""
        field = QueryField(Location, "name")

        assert field.model_class is Location
        assert field.field_name == "name"
        assert field.is_geo is False

    def test_query_field_repr(self):
        """Test QueryField __repr__."""
        field = QueryField(Location, "name")
        repr_str = repr(field)

        assert "QueryField" in repr_str
        assert "name" in repr_str

    def test_query_field_repr_geo(self):
        """Test QueryField __repr__ with geo field."""
        # Create a field that we'll manually mark as geo
        field = QueryField(Location, "location")
        field.is_geo = True
        repr_str = repr(field)

        assert "QueryField" in repr_str
        assert "location" in repr_str
        assert "GEO" in repr_str


class TestQueryFieldGeoMethods:
    """Test geospatial query methods on QueryField."""

    def test_distance_lte_creates_geo_expression(self):
        """Test distance_lte creates GeoExpression."""
        field = QueryField(Location, "location")
        field.is_geo = True

        point = (37.7749, -122.4194)
        distance = 5000  # meters

        result = field.distance_lte(point, distance)

        assert isinstance(result, GeoExpression)
        assert result.field == "location"
        assert result.operation == "distance_lte"
        assert result.args == (point, distance)

    def test_distance_gte_creates_geo_expression(self):
        """Test distance_gte creates GeoExpression."""
        field = QueryField(Location, "location")
        field.is_geo = True

        point = (37.7749, -122.4194)
        distance = 1000

        result = field.distance_gte(point, distance)

        assert isinstance(result, GeoExpression)
        assert result.field == "location"
        assert result.operation == "distance_gte"
        assert result.args == (point, distance)

    def test_near_creates_geo_expression(self):
        """Test near is alias for distance_lte."""
        field = QueryField(Location, "location")
        field.is_geo = True

        point = (37.7749, -122.4194)
        max_distance = 2000

        result = field.near(point, max_distance)

        assert isinstance(result, GeoExpression)
        assert result.field == "location"
        assert result.operation == "distance_lte"  # near is alias for distance_lte
        assert result.args == (point, max_distance)

    def test_within_creates_geo_expression(self):
        """Test within creates GeoExpression."""
        field = QueryField(Location, "location")
        field.is_geo = True

        # Polygon as list of coordinates
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]

        result = field.within(polygon)

        assert isinstance(result, GeoExpression)
        assert result.field == "location"
        assert result.operation == "within"
        assert result.args == (polygon,)

    def test_intersects_creates_geo_expression(self):
        """Test intersects creates GeoExpression."""
        field = QueryField(Location, "area")
        field.is_geo = True

        geometry = {"type": "Polygon", "coordinates": [[(0, 0), (1, 1)]]}

        result = field.intersects(geometry)

        assert isinstance(result, GeoExpression)
        assert result.field == "area"
        assert result.operation == "intersects"
        assert result.args == (geometry,)

    def test_geo_contains_creates_geo_expression(self):
        """Test geo_contains creates GeoExpression."""
        field = QueryField(Location, "boundary")
        field.is_geo = True

        point = (5, 5)

        result = field.geo_contains(point)

        assert isinstance(result, GeoExpression)
        assert result.field == "boundary"
        assert result.operation == "geo_contains"
        assert result.args == (point,)

    def test_bbox_creates_geo_expression(self):
        """Test bbox creates GeoExpression."""
        field = QueryField(Location, "location")
        field.is_geo = True

        min_lat, min_lng = 37.7, -122.5
        max_lat, max_lng = 37.8, -122.4

        result = field.bbox(min_lat, min_lng, max_lat, max_lng)

        assert isinstance(result, GeoExpression)
        assert result.field == "location"
        assert result.operation == "bbox"
        assert result.args == (min_lat, min_lng, max_lat, max_lng)

    def test_distance_creates_distance_field(self):
        """Test distance creates DistanceField for ordering."""
        field = QueryField(Location, "location")
        field.is_geo = True

        reference_point = (37.7749, -122.4194)

        result = field.distance(reference_point)

        assert isinstance(result, DistanceField)
        assert result.field_name == "location"
        assert result.reference_point == reference_point

    def test_distance_field_repr(self):
        """Test DistanceField __repr__."""
        point = (37.7, -122.4)
        dist_field = DistanceField("location", point)

        repr_str = repr(dist_field)
        assert "distance" in repr_str
        assert "location" in repr_str

    def test_distance_field_str(self):
        """Test DistanceField __str__ for use in order_by."""
        point = (37.7, -122.4)
        dist_field = DistanceField("location", point)

        str_repr = str(dist_field)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0


class TestGeoExpressionToFilterDict:
    """Test GeoExpression to_filter_dict method."""

    def test_geo_expression_to_filter_dict(self):
        """Test GeoExpression.to_filter_dict creates correct format."""
        geo_expr = GeoExpression("location", "within", [(0, 0), (1, 1)])

        result = geo_expr.to_filter_dict()

        assert "location__within" in result
        assert result["location__within"] == ([(0, 0), (1, 1)],)

    def test_geo_expression_repr(self):
        """Test GeoExpression __repr__."""
        geo_expr = GeoExpression("location", "distance_lte", (37.7, -122.4), 5000)

        repr_str = repr(geo_expr)
        assert "location" in repr_str
        assert "distance_lte" in repr_str

    def test_geo_expression_repr_long_geometry(self):
        """Test GeoExpression __repr__ truncates long geometries."""
        # Create expression with very long geometry
        long_coords = [(i, i) for i in range(100)]
        geo_expr = GeoExpression("area", "within", long_coords)

        repr_str = repr(geo_expr)
        # Should be truncated (max 50 chars per arg)
        assert len(repr_str) < 200


class TestQueryFieldNonGeoMethods:
    """Test QueryField methods when is_geo=False."""

    def test_non_geo_field_still_has_geo_methods(self):
        """Test non-geo fields have geo methods (they just won't work correctly)."""
        field = QueryField(Location, "name")

        # Methods exist but behavior undefined for non-geo fields
        assert hasattr(field, 'distance_lte')
        assert hasattr(field, 'within')
        assert hasattr(field, 'near')

    def test_non_geo_field_can_call_geo_methods(self):
        """Test calling geo methods on non-geo field creates expressions."""
        field = QueryField(Location, "name")
        field.is_geo = False

        # Can still call the method - creates GeoExpression
        # (Backend will handle whether this makes sense)
        result = field.distance_lte((0, 0), 100)

        assert isinstance(result, GeoExpression)

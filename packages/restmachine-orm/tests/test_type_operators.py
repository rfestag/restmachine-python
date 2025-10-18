"""
Tests for type operator mapping and query_operator_for_type decorator.

Tests the complex type operator mapping system that allows mixins to register
operators for specific field types (e.g., Point fields get 'near' operator).
"""

import pytest
import sys
from typing import ClassVar, Optional
from restmachine_orm import Model, Field
from restmachine_orm.backends import InMemoryBackend
from restmachine_orm.models.hooks import query_operator_for_type, query_operator_for_types


shared_backend = InMemoryBackend()


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test."""
    shared_backend.clear()
    yield
    shared_backend.clear()


# Custom type for testing
class CustomGeoType:
    """Custom type for testing type operators."""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class TestTypeOperatorDecorator:
    """Test query_operator_for_type decorator."""

    def test_decorator_sets_attributes(self):
        """Test decorator sets _is_query_operator, _operator_type, _operator_name."""
        @query_operator_for_type(CustomGeoType, 'nearby')
        def handle_nearby(query, field_name, value):
            return query

        assert hasattr(handle_nearby, '_is_query_operator')
        assert handle_nearby._is_query_operator is True
        assert hasattr(handle_nearby, '_operator_type')
        assert handle_nearby._operator_type is CustomGeoType
        assert hasattr(handle_nearby, '_operator_name')
        assert handle_nearby._operator_name == 'nearby'

    def test_decorator_preserves_function(self):
        """Test decorator returns the original function."""
        @query_operator_for_type(CustomGeoType, 'nearby')
        def handle_nearby(query, field_name, value):
            return query.add_result_filter('test', lambda x: True)

        # Function should still be callable
        class DummyModel(Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)

        # Use where() to get a concrete query builder
        query = DummyModel.where()
        result = handle_nearby(query, 'location', (0, 0))
        assert result is not None


class TestTypeOperatorsDecorator:
    """Test query_operator_for_types decorator for multiple types."""

    def test_decorator_sets_attributes_for_multiple_types(self):
        """Test decorator sets _operator_types with list of types."""
        class TypeA:
            pass

        class TypeB:
            pass

        @query_operator_for_types([TypeA, TypeB], 'contains')
        def handle_contains(query, field_name, value):
            return query

        assert hasattr(handle_contains, '_is_query_operator')
        assert handle_contains._is_query_operator is True
        assert hasattr(handle_contains, '_operator_types')
        assert handle_contains._operator_types == [TypeA, TypeB]
        assert hasattr(handle_contains, '_operator_name')
        assert handle_contains._operator_name == 'contains'


class TestTypeOperatorMapping:
    """Test _map_type_operators_to_fields method."""

    def test_simple_type_operator_mapping(self):
        """Test mapping operator to simple field type."""
        call_log = []

        # Define mixin with operator
        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                call_log.append(f'{field_name}__nearby')
                return query

        # Model inherits from mixin
        class Store(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            name: str
            location: CustomGeoType

        # Trigger lazy initialization of query operators
        Store.where()

        # Check that the operator was registered
        assert hasattr(Store, '_query_operators')
        assert ('location', 'nearby') in Store._query_operators

        # Verify it's the handler function
        handler = Store._query_operators[('location', 'nearby')]
        assert hasattr(handler, '_operator_type')
        assert handler._operator_type is CustomGeoType

    def test_optional_type_unwrapping(self):
        """Test mapping operator to Optional[Type] field."""
        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                return query

        class Store(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            name: str
            location: Optional[CustomGeoType] = None

        # Trigger lazy initialization
        Store.where()

        # Should unwrap Optional[CustomGeoType] -> CustomGeoType and map it
        assert hasattr(Store, '_query_operators')
        assert ('location', 'nearby') in Store._query_operators

    def test_multiple_fields_same_type(self):
        """Test mapping operator to multiple fields of same type."""
        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                return query

        class Building(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            entrance: CustomGeoType
            exit: CustomGeoType

        # Trigger lazy initialization
        Building.where()

        # Both fields should get the operator
        assert ('entrance', 'nearby') in Building._query_operators
        assert ('exit', 'nearby') in Building._query_operators

    def test_multiple_operators_for_same_type(self):
        """Test mapping multiple operators to same type."""
        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                return query

            @query_operator_for_type(CustomGeoType, 'within')
            def handle_within(query, field_name, value):
                return query

        class Store(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            location: CustomGeoType

        # Trigger lazy initialization
        Store.where()

        # Both operators should be registered for the field
        assert ('location', 'nearby') in Store._query_operators
        assert ('location', 'within') in Store._query_operators

    def test_no_type_operators_attribute(self):
        """Test _map_type_operators_to_fields when no type operators exist."""
        class SimpleModel(Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            name: str

        # Should not crash, should just return early
        SimpleModel._map_type_operators_to_fields()

        # Should not have _type_operators or it should be empty
        if hasattr(SimpleModel, '_type_operators'):
            assert len(SimpleModel._type_operators) == 0

    def test_operator_for_types_maps_to_all_matching_fields(self):
        """Test query_operator_for_types maps to all fields of any matching type."""
        class TypeA:
            pass

        class TypeB:
            pass

        class MultiTypeMixin:
            @query_operator_for_types([TypeA, TypeB], 'custom_op')
            def handle_custom(query, field_name, value):
                return query

        class MultiTypeModel(MultiTypeMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            field_a: TypeA
            field_b: TypeB
            field_a2: TypeA

        # Trigger lazy initialization
        MultiTypeModel.where()

        # All three fields should get the operator
        assert ('field_a', 'custom_op') in MultiTypeModel._query_operators
        assert ('field_b', 'custom_op') in MultiTypeModel._query_operators
        assert ('field_a2', 'custom_op') in MultiTypeModel._query_operators

    def test_type_error_handling_for_non_class_types(self):
        """Test TypeError handling when type isn't a class."""
        # This tests the except TypeError block in _map_type_operators_to_fields
        class StringMixin:
            @query_operator_for_type(str, 'custom')
            def handle_custom(query, field_name, value):
                return query

        class EdgeCaseModel(StringMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            name: str

        # Trigger lazy initialization
        EdgeCaseModel.where()

        # Should not crash, should map str fields to custom operator
        assert ('name', 'custom') in EdgeCaseModel._query_operators


class TestGeoFieldTracking:
    """Test geo field tracking in type operator mapping."""

    def test_geo_fields_tracked_when_shapely_available(self):
        """Test geo fields are tracked when Point/Polygon operators registered."""
        # Skip if shapely not installed
        try:
            from shapely.geometry import Point
        except ImportError:
            pytest.skip("Shapely not installed")

        class PointMixin:
            @query_operator_for_type(Point, 'nearby')
            def handle_nearby(query, field_name, value):
                return query

        class Store(PointMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            location: Point  # type: ignore[valid-type]

        # Trigger lazy initialization
        Store.where()

        # location should be in geo field names
        assert hasattr(Store, '_geo_field_names')
        assert 'location' in Store._geo_field_names

    def test_geo_fields_tracked_for_polygon(self):
        """Test Polygon fields are tracked as geo fields."""
        try:
            from shapely.geometry import Polygon
        except ImportError:
            pytest.skip("Shapely not installed")

        class PolygonMixin:
            @query_operator_for_type(Polygon, 'contains')
            def handle_contains(query, field_name, value):
                return query

        class Zone(PolygonMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            boundary: Polygon  # type: ignore[valid-type]

        # Trigger lazy initialization
        Zone.where()

        assert hasattr(Zone, '_geo_field_names')
        assert 'boundary' in Zone._geo_field_names

    def test_geo_fields_tracked_for_multipolygon(self):
        """Test MultiPolygon fields are tracked as geo fields."""
        try:
            from shapely.geometry import MultiPolygon
        except ImportError:
            pytest.skip("Shapely not installed")

        class MultiPolygonMixin:
            @query_operator_for_type(MultiPolygon, 'contains')
            def handle_contains(query, field_name, value):
                return query

        class Region(MultiPolygonMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            areas: MultiPolygon  # type: ignore[valid-type]

        # Trigger lazy initialization
        Region.where()

        assert hasattr(Region, '_geo_field_names')
        assert 'areas' in Region._geo_field_names

    def test_non_geo_fields_not_tracked(self):
        """Test non-geo fields are not added to _geo_field_names."""
        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                return query

        class SimpleModel(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            location: CustomGeoType

        # CustomGeoType is not a Shapely type, so shouldn't be tracked
        if hasattr(SimpleModel, '_geo_field_names'):
            assert 'location' not in SimpleModel._geo_field_names


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Python 3.10+ union syntax")
class TestPython310UnionSyntax:
    """Test type operator mapping with Python 3.10+ union syntax."""

    def test_union_syntax_type_unwrapping(self):
        """Test mapping operator to Type | None field (Python 3.10+)."""
        # Create model using union syntax
        code = '''
class UnionMixin:
    @query_operator_for_type(CustomGeoType, 'nearby')
    def handle_nearby(query, field_name, value):
        return query

class UnionModel(UnionMixin, Model):
    model_backend: ClassVar = shared_backend
    id: str = Field(primary_key=True)
    location: CustomGeoType | None = None

# Trigger lazy initialization
UnionModel.where()
'''
        namespace = {
            'Model': Model,
            'ClassVar': ClassVar,
            'shared_backend': shared_backend,
            'Field': Field,
            'CustomGeoType': CustomGeoType,
            'query_operator_for_type': query_operator_for_type,
        }
        exec(code, namespace)
        UnionModel = namespace['UnionModel']

        # Should unwrap CustomGeoType | None -> CustomGeoType and map it
        assert hasattr(UnionModel, '_query_operators')
        assert ('location', 'nearby') in UnionModel._query_operators


class TestTypeOperatorIntegration:
    """Test type operator integration with query builder."""

    def test_type_operator_can_be_invoked(self):
        """Test type operators can be invoked through query builder."""
        call_log = []

        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                call_log.append(('nearby', field_name, value))
                return query.add_result_filter('nearby_filter', lambda x: True)

        class Store(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            name: str
            location: CustomGeoType

        # Create a query that uses the operator
        query = Store.where(location__nearby=(0, 0))

        # The operator should have been called
        assert len(call_log) == 1
        assert call_log[0][0] == 'nearby'
        assert call_log[0][1] == 'location'
        assert call_log[0][2] == (0, 0)

    def test_multiple_type_operators_in_single_query(self):
        """Test using multiple type operators in one query."""
        call_log = []

        class CustomGeoMixin:
            @query_operator_for_type(CustomGeoType, 'nearby')
            def handle_nearby(query, field_name, value):
                call_log.append(('nearby', field_name))
                return query.add_result_filter(f'{field_name}_nearby', lambda x: True)

        class Building(CustomGeoMixin, Model):
            model_backend: ClassVar = shared_backend
            id: str = Field(primary_key=True)
            entrance: CustomGeoType
            exit: CustomGeoType

        # Use the operator on both fields
        query = Building.where(entrance__nearby=(0, 0)).and_(exit__nearby=(1, 1))

        # Both operators should have been called
        assert len(call_log) == 2
        field_names = [entry[1] for entry in call_log]
        assert 'entrance' in field_names
        assert 'exit' in field_names

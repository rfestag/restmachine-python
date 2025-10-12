"""
GeoMixin for geospatial operations.

Provides geospatial capabilities for Point, Polygon, and MultiPolygon fields.
Supports operations like contains, within, near, intersects, etc.

Requires: shapely, pygeohash
"""

from typing import Union, get_args, Any, TYPE_CHECKING

try:
    import pygeohash as geohash  # type: ignore[import-untyped, import-not-found]
except ImportError:
    geohash = None  # type: ignore[assignment]

try:
    from shapely.geometry import Point, Polygon, MultiPolygon, shape  # type: ignore[import-untyped, import-not-found]
except ImportError:
    Point = None  # type: ignore[assignment,misc]
    Polygon = None  # type: ignore[assignment,misc]
    MultiPolygon = None  # type: ignore[assignment,misc]
    shape = None  # type: ignore[assignment]

from restmachine_orm.models.hooks import (
    before_save,
    after_load,
    query_operator_for_type,
    query_method
)

if TYPE_CHECKING:
    from restmachine_orm.query.base import QueryBuilder


class GeoMixin:
    """
    Mixin that adds geospatial capabilities.

    Automatically handles serialization/deserialization of Point, Polygon,
    and MultiPolygon fields. Adds query operators for geo operations.

    Example:
        >>> class Store(GeoMixin, Model):
        ...     name: str = Field(primary_key=True)
        ...     location: Point  # User defines geo fields
        ...     delivery_zone: Polygon
        >>>
        >>> store = Store.create(
        ...     name="Store 1",
        ...     location=Point(-122.4, 37.8),
        ...     delivery_zone=Polygon([...])
        ... )
        >>>
        >>> # Query with geo operators
        >>> stores = Store.where(location__near=(my_point, 5)).all()
        >>> stores = Store.where(delivery_zone__contains=point).all()
    """

    @before_save
    def _serialize_geo_fields(self) -> None:
        """Convert geo objects to primitives before backend sees them."""
        for field_name, field_info in self.model_fields.items():  # type: ignore[attr-defined]
            # Get the actual type (handle Optional, Annotated, etc.)
            field_type = field_info.annotation
            if hasattr(field_type, '__origin__'):
                # Handle Optional[Point], etc.
                if field_type.__origin__ is Union:
                    args = get_args(field_type)
                    field_type = args[0] if args else field_type

            value = getattr(self, field_name, None)

            if value is None:
                continue

            # Check if this is a geo type
            if isinstance(value, (Point, Polygon, MultiPolygon)):
                # Store as GeoJSON dict (adapters already handle dicts)
                geo_dict = value.__geo_interface__
                setattr(self, f'_{field_name}_geo', geo_dict)

                # Add geohash for DynamoDB optimization
                if isinstance(value, Point):
                    # Store point geohash directly
                    setattr(self, f'_{field_name}_geohash',
                           geohash.encode(value.y, value.x, precision=7))
                elif isinstance(value, (Polygon, MultiPolygon)):
                    # Store centroid geohash for polygons
                    centroid = value.centroid
                    setattr(self, f'_{field_name}_geohash',
                           geohash.encode(centroid.y, centroid.x, precision=7))

    @after_load
    def _deserialize_geo_fields(self) -> None:
        """Reconstruct geo objects after loading from backend."""
        for field_name, field_info in self.model_fields.items():  # type: ignore[attr-defined]
            # Check if we have stored geo data
            geo_data = getattr(self, f'_{field_name}_geo', None)

            if geo_data:
                # Reconstruct geometry from GeoJSON
                geom = shape(geo_data)
                setattr(self, field_name, geom)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-add shadow fields for geo storage."""
        super().__init_subclass__(**kwargs)

        # We'll add the shadow fields dynamically in the Model metaclass
        # For now, just track which fields are geo fields
        if not hasattr(cls, '_geo_field_names'):
            cls._geo_field_names = []  # type: ignore[attr-defined]

        # This will be populated when Model processes field types

    # === Query Operators ===

    @query_operator_for_type(Point, 'near')  # type: ignore[misc]
    def _handle_point_near(query: "QueryBuilder", field_name: str, value: tuple) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle Point field with 'near' operator.

        Usage: Store.where(location__near=(point, radius_km))
        """
        point, radius = value

        # Try backend optimization (DynamoDB with geohash)
        if hasattr(query, 'backend') and query.backend.backend_name == 'dynamodb':  # type: ignore[attr-defined]
            # Calculate geohash bbox for coarse filtering
            # Reduce precision for wider area (precision 6 ≈ 1.2km × 0.6km)
            geohash_field = f'_{field_name}_geohash'
            geohash_prefix = geohash.encode(point.y, point.x, precision=6)

            # Add coarse filter using standard startswith
            query._filters.append(('and', {f'{geohash_field}__startswith': geohash_prefix}))  # type: ignore[attr-defined]

        # Always add exact Python filter
        def distance_filter(item: Any) -> bool:
            item_point = getattr(item, field_name, None)
            if not item_point:
                return False
            # Convert km to degrees (rough approximation at mid-latitudes)
            # 1 degree ≈ 111 km
            return bool(item_point.distance(point) <= (radius / 111.0))

        return query.add_result_filter(f'{field_name}_near_{id(point)}', distance_filter)

    @query_operator_for_type(Polygon, 'contains')  # type: ignore[misc]
    def _handle_polygon_contains(query: "QueryBuilder", field_name: str, point: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle Polygon field with 'contains' operator.

        Usage: DeliveryZone.where(boundary__contains=point)
        """
        def contains_filter(item: Any) -> bool:
            polygon = getattr(item, field_name, None)
            return bool(polygon and polygon.contains(point))

        return query.add_result_filter(f'{field_name}_contains_{id(point)}', contains_filter)

    @query_operator_for_type(Point, 'within')  # type: ignore[misc]
    def _handle_point_within(query: "QueryBuilder", field_name: str, bounds: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle Point field with 'within' operator.

        Usage: Store.where(location__within=polygon)
        """
        def within_filter(item: Any) -> bool:
            point = getattr(item, field_name, None)
            return bool(point and bounds.contains(point))

        return query.add_result_filter(f'{field_name}_within_{id(bounds)}', within_filter)

    @query_operator_for_type(Polygon, 'intersects')  # type: ignore[misc]
    def _handle_polygon_intersects(query: "QueryBuilder", field_name: str, other: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle Polygon field with 'intersects' operator.

        Usage: Zone.where(area__intersects=other_polygon)
        """
        def intersects_filter(item: Any) -> bool:
            polygon = getattr(item, field_name, None)
            return bool(polygon and polygon.intersects(other))

        return query.add_result_filter(f'{field_name}_intersects_{id(other)}', intersects_filter)

    @query_operator_for_type(Polygon, 'covers')  # type: ignore[misc]
    def _handle_polygon_covers(query: "QueryBuilder", field_name: str, other: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle Polygon field with 'covers' operator.

        Usage: Zone.where(area__covers=other_geometry)
        """
        def covers_filter(item: Any) -> bool:
            polygon = getattr(item, field_name, None)
            return bool(polygon and polygon.covers(other))

        return query.add_result_filter(f'{field_name}_covers_{id(other)}', covers_filter)

    @query_operator_for_type(MultiPolygon, 'contains')  # type: ignore[misc]
    def _handle_multipolygon_contains(query: "QueryBuilder", field_name: str, point: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle MultiPolygon field with 'contains' operator.

        Usage: Region.where(areas__contains=point)
        """
        def contains_filter(item: Any) -> bool:
            multipolygon = getattr(item, field_name, None)
            return bool(multipolygon and multipolygon.contains(point))

        return query.add_result_filter(f'{field_name}_contains_{id(point)}', contains_filter)

    @query_operator_for_type(MultiPolygon, 'intersects')  # type: ignore[misc]
    def _handle_multipolygon_intersects(query: "QueryBuilder", field_name: str, other: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Handle MultiPolygon field with 'intersects' operator.

        Usage: Region.where(areas__intersects=polygon)
        """
        def intersects_filter(item: Any) -> bool:
            multipolygon = getattr(item, field_name, None)
            return bool(multipolygon and multipolygon.intersects(other))

        return query.add_result_filter(f'{field_name}_intersects_{id(other)}', intersects_filter)

    # === Custom Query Methods ===

    @staticmethod  # type: ignore[misc]
    @query_method  # type: ignore[misc]
    def within_bounds(query: "QueryBuilder", bounds: Any) -> "QueryBuilder":  # type: ignore[name-defined]
        """
        Filter all geo fields to be within bounds.

        Usage: Store.where().within_bounds(city_polygon).all()
        """
        # Find all geo fields in the model
        geo_fields = getattr(query.model_class, '_geo_field_names', [])  # type: ignore[attr-defined]

        for field_name in geo_fields:
            field_info = query.model_class.model_fields.get(field_name)  # type: ignore[attr-defined]
            if field_info:
                field_type = field_info.annotation
                # Handle Optional, etc.
                origin = getattr(field_type, '__origin__', None)
                if origin is not None:
                    if origin is Union:
                        args = get_args(field_type)
                        field_type = args[0] if args else field_type

                # Add appropriate filter based on type
                if field_type == Point:
                    query = query.filter(**{f'{field_name}__within': bounds})  # type: ignore[attr-defined]
                elif field_type in (Polygon, MultiPolygon):
                    # For polygons, check if they're within bounds
                    def within_filter(item: Any) -> bool:
                        geom = getattr(item, field_name, None)
                        return bool(geom and bounds.contains(geom))
                    query = query.add_result_filter(f'{field_name}_within_bounds', within_filter)

        return query

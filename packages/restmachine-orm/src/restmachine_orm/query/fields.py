"""
QueryField class for field-based query building.

Enables SQLAlchemy-style syntax: User.age > 25
"""

from typing import Any, TYPE_CHECKING
import typing

from restmachine_orm.query.expressions import (
    QueryExpression,
    GeoExpression,
    DistanceField,
)

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


class QueryField:
    """
    Field wrapper that enables operator overloading for query building.

    Automatically detects geo fields and adds geospatial methods.
    """

    def __init__(self, model_class: type["Model"], field_name: str):
        """
        Initialize query field.

        Args:
            model_class: Model class this field belongs to
            field_name: Name of the field
        """
        self.model_class = model_class
        self.field_name = field_name

        # Detect if this is a geo field
        self.is_geo = False
        if hasattr(model_class, 'model_fields') and field_name in model_class.model_fields:
            field_info = model_class.model_fields[field_name]
            field_type = field_info.annotation

            # Check if field type is a geo type
            try:
                from shapely.geometry import Point, Polygon, MultiPolygon  # type: ignore[import-untyped]
                GEO_TYPES = (Point, Polygon, MultiPolygon)

                # Handle Optional types
                origin = typing.get_origin(field_type)
                if origin is typing.Union:
                    args = typing.get_args(field_type)
                    field_type = args[0] if args and args[0] is not type(None) else args[1] if len(args) > 1 else field_type

                if field_type in GEO_TYPES:
                    self.is_geo = True
            except ImportError:
                # Shapely not installed, no geo support
                pass

    # ========================================================================
    # Standard comparison operators
    # ========================================================================

    def __eq__(self, other: Any) -> QueryExpression:  # type: ignore[override]
        """Equal: User.age == 25"""
        return QueryExpression(self.field_name, "eq", other)

    def __ne__(self, other: Any) -> QueryExpression:  # type: ignore[override]
        """Not equal: User.age != 25"""
        return QueryExpression(self.field_name, "ne", other)

    def __gt__(self, other: Any) -> QueryExpression:
        """Greater than: User.age > 25"""
        return QueryExpression(self.field_name, "gt", other)

    def __ge__(self, other: Any) -> QueryExpression:
        """Greater than or equal: User.age >= 25"""
        return QueryExpression(self.field_name, "gte", other)

    def __lt__(self, other: Any) -> QueryExpression:
        """Less than: User.age < 25"""
        return QueryExpression(self.field_name, "lt", other)

    def __le__(self, other: Any) -> QueryExpression:
        """Less than or equal: User.age <= 25"""
        return QueryExpression(self.field_name, "lte", other)

    # ========================================================================
    # String methods
    # ========================================================================

    def contains(self, value: str) -> QueryExpression:
        """Contains substring: User.name.contains("alice")"""
        return QueryExpression(self.field_name, "contains", value)

    def startswith(self, value: str) -> QueryExpression:
        """Starts with: User.name.startswith("A")"""
        return QueryExpression(self.field_name, "startswith", value)

    def endswith(self, value: str) -> QueryExpression:
        """Ends with: User.email.endswith("@example.com")"""
        return QueryExpression(self.field_name, "endswith", value)

    def in_(self, values: list[Any]) -> QueryExpression:
        """In list: User.role.in_(["admin", "moderator"])"""
        return QueryExpression(self.field_name, "in", values)

    # ========================================================================
    # Geospatial methods (only available for geo fields)
    # ========================================================================

    def distance_lte(self, point: Any, distance: float) -> GeoExpression:
        """
        Find records within distance of a point.

        Args:
            point: Point geometry or (lat, lng) tuple
            distance: Maximum distance in meters

        Returns:
            GeoExpression for distance query

        Example:
            >>> Shop.where(Shop.location.distance_lte(user_location, 5000))
        """
        return GeoExpression(self.field_name, "distance_lte", point, distance)

    def distance_gte(self, point: Any, distance: float) -> GeoExpression:
        """Find records farther than distance from a point."""
        return GeoExpression(self.field_name, "distance_gte", point, distance)

    def near(self, point: Any, max_distance: float) -> GeoExpression:
        """
        Alias for distance_lte - find nearby records.

        Example:
            >>> Shop.where(Shop.location.near(user_location, max_distance=5000))
        """
        return self.distance_lte(point, max_distance)

    def within(self, geometry: Any) -> GeoExpression:
        """
        Find records within a geometry (polygon).

        Args:
            geometry: Polygon or MultiPolygon

        Returns:
            GeoExpression for within query

        Example:
            >>> Shop.where(Shop.location.within(delivery_area))
        """
        return GeoExpression(self.field_name, "within", geometry)

    def intersects(self, geometry: Any) -> GeoExpression:
        """
        Find records that intersect with a geometry.

        Args:
            geometry: Any geometry type

        Returns:
            GeoExpression for intersection query

        Example:
            >>> Event.where(Event.venue_location.intersects(search_area))
        """
        return GeoExpression(self.field_name, "intersects", geometry)

    def geo_contains(self, point_or_geometry: Any) -> GeoExpression:
        """
        Find records (polygons) that contain a point or geometry.

        Args:
            point_or_geometry: Point or other geometry

        Returns:
            GeoExpression for containment query

        Example:
            >>> DeliveryZone.where(DeliveryZone.boundary.geo_contains(customer_location))
        """
        return GeoExpression(self.field_name, "geo_contains", point_or_geometry)

    def bbox(self, min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> GeoExpression:
        """
        Find records within a bounding box.

        Args:
            min_lat: Minimum latitude
            min_lng: Minimum longitude
            max_lat: Maximum latitude
            max_lng: Maximum longitude

        Returns:
            GeoExpression for bounding box query

        Example:
            >>> Shop.where(Shop.location.bbox(37.7, -122.5, 37.8, -122.4))
        """
        return GeoExpression(self.field_name, "bbox", min_lat, min_lng, max_lat, max_lng)

    def distance(self, point: Any) -> DistanceField:
        """
        Calculate distance to a point (for ordering).

        Args:
            point: Point to calculate distance from

        Returns:
            DistanceField for use in order_by()

        Example:
            >>> Shop.where(...).order_by(Shop.location.distance(user_location))
        """
        return DistanceField(self.field_name, point)

    def __repr__(self) -> str:
        geo_marker = " [GEO]" if self.is_geo else ""
        return f"<QueryField: {self.field_name}{geo_marker}>"

"""
Query expression objects for complex queries.

Provides Q objects for building complex boolean expressions similar to Django ORM.
"""

from typing import Any
from enum import Enum


class Operator(str, Enum):
    """Query operators."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class Q:
    """
    Query expression object for complex boolean logic.

    Allows combining filter conditions with AND, OR, and NOT operators.

    Example:
        >>> # (age >= 18 AND status = "active") OR (role = "admin")
        >>> query = Q(age__gte=18, status="active") | Q(role="admin")
        >>>
        >>> # NOT deleted
        >>> query = ~Q(deleted=True)
        >>>
        >>> # Complex nested conditions
        >>> query = (Q(age__gte=18) & Q(status="active")) | Q(role="admin")
    """

    def __init__(self, *args: "Q", **conditions: Any):
        """
        Initialize a Q object.

        Args:
            *args: Child Q objects for complex expressions
            **conditions: Field filter conditions

        Example:
            >>> Q(age__gte=18)
            >>> Q(age__gte=18, status="active")
            >>> Q(Q(age__gte=18) | Q(role="admin"))
        """
        self.children = list(args)
        self.conditions = conditions
        self.operator = Operator.AND
        self.negated = False

    def __and__(self, other: "Q") -> "Q":
        """
        Combine with AND operator.

        Args:
            other: Another Q object

        Returns:
            New Q object with AND combination

        Example:
            >>> Q(age__gte=18) & Q(status="active")
        """
        result = Q(self, other)
        result.operator = Operator.AND
        return result

    def __or__(self, other: "Q") -> "Q":
        """
        Combine with OR operator.

        Args:
            other: Another Q object

        Returns:
            New Q object with OR combination

        Example:
            >>> Q(age__gte=18) | Q(role="admin")
        """
        result = Q(self, other)
        result.operator = Operator.OR
        return result

    def __invert__(self) -> "Q":
        """
        Negate this expression.

        Returns:
            New Q object with negation

        Example:
            >>> ~Q(deleted=True)  # NOT deleted
        """
        result = Q(self)
        result.negated = not self.negated
        return result

    def __repr__(self) -> str:
        """String representation of the Q object."""
        parts = []
        if self.conditions:
            parts.append(f"conditions={self.conditions}")
        if self.children:
            parts.append(f"children={self.children}")
        if self.operator != Operator.AND:
            parts.append(f"operator={self.operator}")
        if self.negated:
            parts.append("negated=True")
        return f"Q({', '.join(parts)})"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary representation.

        Returns:
            Dictionary representation of the query expression

        Example:
            >>> q = Q(age__gte=18) & Q(status="active")
            >>> q.to_dict()
            {
                'operator': 'AND',
                'negated': False,
                'children': [
                    {'conditions': {'age__gte': 18}},
                    {'conditions': {'status': 'active'}}
                ]
            }
        """
        result: dict[str, Any] = {
            "operator": self.operator.value,
            "negated": self.negated,
        }

        if self.conditions:
            result["conditions"] = self.conditions

        if self.children:
            result["children"] = [
                child.to_dict() if isinstance(child, Q) else child
                for child in self.children
            ]

        return result


def parse_field_lookup(field_lookup: str) -> tuple[str, str]:
    """
    Parse a field lookup string into field name and operator.

    Args:
        field_lookup: Field lookup string (e.g., "age__gte")

    Returns:
        Tuple of (field_name, operator)

    Example:
        >>> parse_field_lookup("age__gte")
        ('age', 'gte')
        >>> parse_field_lookup("name")
        ('name', 'eq')
    """
    if "__" in field_lookup:
        field, operator = field_lookup.rsplit("__", 1)
        return field, operator
    return field_lookup, "eq"


# Supported operators and their meanings
OPERATORS = {
    "eq": "equals",
    "ne": "not equals",
    "gt": "greater than",
    "gte": "greater than or equal",
    "lt": "less than",
    "lte": "less than or equal",
    "in": "in list",
    "contains": "contains",
    "startswith": "starts with",
    "endswith": "ends with",
    "icontains": "contains (case-insensitive)",
    "istartswith": "starts with (case-insensitive)",
    "iendswith": "ends with (case-insensitive)",
}


# ============================================================================
# Field-based expression classes for SQLAlchemy-style queries
# ============================================================================

class BooleanExpression:
    """Base class for boolean expressions with operator support."""

    def __and__(self, other: Any) -> "AndExpression":
        """Combine with AND: expr & other"""
        return AndExpression(self, other)

    def __or__(self, other: Any) -> "OrExpression":
        """Combine with OR: expr | other"""
        return OrExpression(self, other)

    def __invert__(self) -> "NotExpression":
        """Negate: ~expr"""
        return NotExpression(self)


class QueryExpression(BooleanExpression):
    """
    Represents a query filter expression created by field operators.

    Created by comparison operators on QueryField objects.
    Example: User.age > 25 creates QueryExpression("age", "gt", 25)
    """

    def __init__(self, field: str, operator: str, value: Any):
        """
        Initialize query expression.

        Args:
            field: Field name (e.g., "age")
            operator: Operator name (e.g., "gt", "eq", "gte")
            value: Value to compare against
        """
        self.field = field
        self.operator = operator
        self.value = value

    def to_filter_dict(self) -> dict[str, Any]:
        """
        Convert to QueryBuilder filter dict format.

        Returns:
            Dict like {"age__gte": 25} or {"name": "Alice"}
        """
        if self.operator == "eq":
            return {self.field: self.value}
        return {f"{self.field}__{self.operator}": self.value}

    def __repr__(self) -> str:
        return f"<{self.field} {self.operator} {self.value}>"


class GeoExpression(QueryExpression):
    """
    Special expression for geospatial operations.

    Stores the operation type and arguments for backend translation.
    """

    def __init__(self, field: str, operation: str, *args: Any):
        """
        Initialize geo expression.

        Args:
            field: Field name
            operation: Geo operation ('distance_lte', 'within', 'intersects', etc.)
            *args: Operation arguments (point, distance, polygon, etc.)
        """
        self.field = field
        self.operation = operation
        self.args = args

    def to_filter_dict(self) -> dict[str, Any]:
        """Translate to backend-specific filter format."""
        # Backend-specific query builders will handle GeoExpression specially
        return {f"{self.field}__{self.operation}": self.args}

    def __repr__(self) -> str:
        args_str = ", ".join(str(arg)[:50] for arg in self.args)  # Truncate long geometries
        return f"<{self.field}.{self.operation}({args_str})>"


class AndExpression(BooleanExpression):
    """Represents AND combination: (expr1) & (expr2)"""

    def __init__(self, left: Any, right: Any):
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"({self.left} AND {self.right})"


class OrExpression(BooleanExpression):
    """Represents OR combination: (expr1) | (expr2)"""

    def __init__(self, left: Any, right: Any):
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"({self.left} OR {self.right})"


class NotExpression(BooleanExpression):
    """Represents NOT: ~expr"""

    def __init__(self, expr: Any):
        self.expr = expr

    def __invert__(self) -> Any:
        """Double negation returns original: ~~a == a"""
        return self.expr

    def __repr__(self) -> str:
        return f"NOT ({self.expr})"


class DistanceField:
    """
    Represents a distance calculation for ordering.

    Used in order_by() clauses to sort by distance from a reference point.
    """

    def __init__(self, field_name: str, reference_point: Any):
        """
        Initialize distance field.

        Args:
            field_name: Name of the geo field
            reference_point: Point to calculate distance from
        """
        self.field_name = field_name
        self.reference_point = reference_point

    def __repr__(self) -> str:
        return f"distance({self.field_name}, {self.reference_point})"

    def __str__(self) -> str:
        """String representation for use in order_by()."""
        return f"{self.field_name}__distance"

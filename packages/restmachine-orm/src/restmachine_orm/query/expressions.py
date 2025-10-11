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

"""
Field definitions for RestMachine ORM.

Extends Pydantic's field system with ORM-specific metadata like primary keys,
indexes, and backend-specific options.
"""

from typing import Any, Optional, Callable
from pydantic import Field as PydanticField
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


def Field(
    default: Any = PydanticUndefined,
    *,
    # Standard Pydantic validation
    default_factory: Optional[Callable[[], Any]] = None,
    alias: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    examples: Optional[list[Any]] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
    # ORM-specific options
    primary_key: bool = False,
    unique: bool = False,
    index: bool = False,
    searchable: bool = False,  # For full-text search in OpenSearch
    auto_now: bool = False,  # Update timestamp on save
    auto_now_add: bool = False,  # Set timestamp on create
    db_column: Optional[str] = None,  # Custom database column name
    # DynamoDB-specific
    gsi_partition_key: Optional[str] = None,  # GSI partition key name
    gsi_sort_key: Optional[str] = None,  # GSI sort key name
    # OpenSearch-specific
    analyzer: Optional[str] = None,  # Text analyzer for search
    **extra: Any,
) -> FieldInfo:
    """
    Define a model field with validation and ORM metadata.

    Args:
        default: Default value for the field
        default_factory: Factory function for default values
        alias: Alternative name for the field
        title: Human-readable title
        description: Field description
        examples: Example values
        gt: Greater than validation
        ge: Greater than or equal validation
        lt: Less than validation
        le: Less than or equal validation
        min_length: Minimum string/list length
        max_length: Maximum string/list length
        pattern: Regex pattern for string validation
        primary_key: Whether this is the primary key
        unique: Whether values must be unique
        index: Whether to create a database index
        searchable: Whether to enable full-text search (OpenSearch)
        auto_now: Auto-update timestamp on save
        auto_now_add: Auto-set timestamp on create
        db_column: Custom database column name
        gsi_partition_key: DynamoDB GSI partition key name
        gsi_sort_key: DynamoDB GSI sort key name
        analyzer: OpenSearch text analyzer
        **extra: Additional Pydantic field arguments

    Returns:
        FieldInfo object with ORM metadata

    Example:
        >>> class User(Model):
        ...     id: str = Field(primary_key=True)
        ...     email: str = Field(unique=True, index=True)
        ...     name: str = Field(max_length=100, searchable=True)
        ...     age: int = Field(ge=0, le=150)
        ...     created_at: datetime = Field(auto_now_add=True)
    """
    # Build ORM-specific metadata
    json_schema_extra = extra.pop("json_schema_extra", {})
    json_schema_extra.update({
        "orm": {
            "primary_key": primary_key,
            "unique": unique,
            "index": index,
            "searchable": searchable,
            "auto_now": auto_now,
            "auto_now_add": auto_now_add,
            "db_column": db_column,
            "gsi_partition_key": gsi_partition_key,
            "gsi_sort_key": gsi_sort_key,
            "analyzer": analyzer,
        }
    })

    return PydanticField(  # type: ignore[no-any-return, call-overload, misc]
        default=default,
        default_factory=default_factory,
        alias=alias,
        title=title,
        description=description,
        examples=examples,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        json_schema_extra=json_schema_extra,
        **extra,
    )


def get_field_orm_metadata(field_info: FieldInfo) -> dict[str, Any]:
    """
    Extract ORM metadata from a FieldInfo object.

    Args:
        field_info: Pydantic FieldInfo instance

    Returns:
        Dictionary of ORM metadata

    Example:
        >>> field = Field(primary_key=True, index=True)
        >>> metadata = get_field_orm_metadata(field)
        >>> assert metadata["primary_key"] is True
    """
    if hasattr(field_info, "json_schema_extra") and field_info.json_schema_extra:
        extra = field_info.json_schema_extra
        if isinstance(extra, dict):
            orm_data = extra.get("orm", {})
            if isinstance(orm_data, dict):
                return orm_data
    return {}


def is_primary_key(field_info: FieldInfo) -> bool:
    """Check if a field is a primary key."""
    return bool(get_field_orm_metadata(field_info).get("primary_key", False))


def is_unique(field_info: FieldInfo) -> bool:
    """Check if a field has a unique constraint."""
    return bool(get_field_orm_metadata(field_info).get("unique", False))


def is_indexed(field_info: FieldInfo) -> bool:
    """Check if a field is indexed."""
    return bool(get_field_orm_metadata(field_info).get("index", False))


def is_searchable(field_info: FieldInfo) -> bool:
    """Check if a field is searchable (full-text)."""
    return bool(get_field_orm_metadata(field_info).get("searchable", False))

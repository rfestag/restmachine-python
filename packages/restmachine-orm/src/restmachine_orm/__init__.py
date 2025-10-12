"""
RestMachine ORM - ActiveRecord-style ORM/ODM for Python.

An ORM/ODM framework with support for DynamoDB, OpenSearch, and composite backends.
Designed to integrate seamlessly with RestMachine for building full-stack applications.
"""

from restmachine_orm.models.base import Model
from restmachine_orm.models.fields import Field
from restmachine_orm.models.decorators import (
    partition_key,
    sort_key,
    before_save as before_save_decorator,
    after_save as after_save_decorator,
)
from restmachine_orm.models.hooks import (
    before_save,
    after_save,
    after_load,
    query_method,
    query_operator_for_type,
    query_operator_for_types,
)
from restmachine_orm.mixins import (
    TimestampMixin,
    ExpirationMixin,
    GeoMixin,
)

__version__ = "0.1.0"

__all__ = [
    "Model",
    "Field",
    "partition_key",
    "sort_key",
    "before_save_decorator",
    "after_save_decorator",
    "before_save",
    "after_save",
    "after_load",
    "query_method",
    "query_operator_for_type",
    "query_operator_for_types",
    "TimestampMixin",
    "ExpirationMixin",
    "GeoMixin",
]

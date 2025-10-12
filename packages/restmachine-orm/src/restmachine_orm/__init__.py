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
    before_save,
    after_save,
)

__version__ = "0.1.0"

__all__ = [
    "Model",
    "Field",
    "partition_key",
    "sort_key",
    "before_save",
    "after_save",
]

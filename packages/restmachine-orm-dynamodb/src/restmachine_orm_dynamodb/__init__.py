"""
RestMachine ORM - DynamoDB Backend

Provides DynamoDB storage backend for RestMachine ORM.
"""

from .backend import DynamoDBBackend
from .adapter import DynamoDBAdapter

__all__ = [
    "DynamoDBBackend",
    "DynamoDBAdapter",
]

__version__ = "0.1.0"

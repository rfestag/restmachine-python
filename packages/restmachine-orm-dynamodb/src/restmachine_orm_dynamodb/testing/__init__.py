"""
Testing infrastructure for DynamoDB backend.

Provides driver for multi-backend testing framework.
"""

from .drivers import DynamoDBDriver

__all__ = [
    "DynamoDBDriver",
]

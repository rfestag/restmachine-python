"""
SQLite backend for RestMachine ORM.

Provides a simple file-based database for local development and testing.
"""

from .backend import SqliteBackend

__all__ = ["SqliteBackend"]
__version__ = "0.1.0"

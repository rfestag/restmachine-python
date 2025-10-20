"""
SQLite backend for RestMachine ORM.

Simple file-based storage using SQLite with JSON document storage.
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from restmachine_orm.backends.base import Backend, NotFoundError, DuplicateKeyError
from restmachine_orm.backends.adapters import InMemoryAdapter
from restmachine_orm.query.base import QueryBuilder

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


# Regex pattern for valid SQL identifiers (table/column names)
# Allows alphanumeric characters and underscores, must start with letter or underscore
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class SqliteBackend(Backend):
    """
    SQLite storage backend.

    Stores models as JSON documents in SQLite tables.
    Each model class gets its own table.

    Example:
        >>> from restmachine_orm_sqlite import SqliteBackend
        >>>
        >>> backend = SqliteBackend(database="myapp.db")
        >>>
        >>> class User(Model):
        ...     model_backend = backend
        ...     id: str
        ...     name: str
        ...     email: str
    """

    def __init__(
        self,
        database: str = "data.db",
        adapter: Optional[InMemoryAdapter] = None,
    ):
        """
        Initialize SQLite backend.

        Args:
            database: Path to SQLite database file (default: "data.db")
            adapter: Model adapter (uses InMemoryAdapter if not provided)
        """
        self._adapter = adapter or InMemoryAdapter()
        super().__init__(self._adapter)

        self.database = Path(database)
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def backend_name(self) -> str:
        """Backend identifier."""
        return 'sqlite'

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.database))
            self._connection.row_factory = sqlite3.Row
        return self._connection

    @staticmethod
    def _validate_identifier(identifier: str) -> str:
        """
        Validate that an identifier (table/column name) is safe to use in SQL.

        This prevents SQL injection by ensuring identifiers only contain
        alphanumeric characters and underscores.

        Args:
            identifier: The identifier to validate

        Returns:
            The validated identifier

        Raises:
            ValueError: If identifier contains invalid characters
        """
        if not _VALID_IDENTIFIER.match(identifier):
            raise ValueError(
                f"Invalid SQL identifier: {identifier!r}. "
                "Identifiers must start with a letter or underscore and "
                "contain only alphanumeric characters and underscores."
            )
        return identifier

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """
        Quote a SQL identifier for safe use in queries.

        Uses double quotes as per SQL standard. The identifier is validated
        first to ensure it contains only safe characters.

        Args:
            identifier: The identifier to quote

        Returns:
            Quoted identifier safe for SQL interpolation
        """
        validated = SqliteBackend._validate_identifier(identifier)
        return f'"{validated}"'

    def _get_table_name(self, model_class: type["Model"]) -> str:
        """
        Get validated table name for a model class.

        Generates table name from model class name and validates it
        to ensure it's safe for SQL queries.
        """
        table_name = model_class.__name__.lower() + "s"
        return self._validate_identifier(table_name)

    def _ensure_table(self, model_class: type["Model"]) -> None:
        """Ensure table exists for model class."""
        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        # Using validated and quoted identifier - safe from SQL injection
        self.connection.execute(f"""
            CREATE TABLE IF NOT EXISTS {quoted_table} (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)  # nosec B608 - table name validated by regex
        self.connection.commit()

    def _get_primary_key_value(self, data: dict[str, Any]) -> Optional[str]:
        """Extract primary key value from data."""
        # Look for common primary key field names
        for key_field in ['id', 'pk', 'key']:
            if key_field in data:
                value = data[key_field]
                return str(value) if value is not None else None
        return None

    def create(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new record.

        Args:
            model_class: Model class
            data: Record data

        Returns:
            Created record data

        Raises:
            DuplicateKeyError: If record with same ID already exists
        """
        self._ensure_table(model_class)
        self._ensure_configured(model_class)

        # Get primary key
        pk_value = self._get_primary_key_value(data)
        if not pk_value:
            raise ValueError("Record must have an 'id' field")

        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        # Serialize hooks
        data = self._call_serialize_hooks(model_class, data)
        self._call_validate_hooks(model_class, data)

        # Store as JSON
        json_data = json.dumps(data)

        try:
            # Using validated and quoted identifier - safe from SQL injection
            self.connection.execute(
                f"INSERT INTO {quoted_table} (id, data) VALUES (?, ?)",  # nosec B608 - table name validated by regex
                (pk_value, json_data)
            )
            self.connection.commit()
        except sqlite3.IntegrityError:
            raise DuplicateKeyError(f"Record with id '{pk_value}' already exists")

        # Deserialize hooks
        data = self._call_deserialize_hooks(model_class, data)
        return data

    def upsert(self, model_class: type["Model"], data: dict[str, Any]) -> dict[str, Any]:
        """
        Create or update a record.

        Args:
            model_class: Model class
            data: Record data

        Returns:
            Upserted record data
        """
        self._ensure_table(model_class)
        self._ensure_configured(model_class)

        # Get primary key
        pk_value = self._get_primary_key_value(data)
        if not pk_value:
            raise ValueError("Record must have an 'id' field")

        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        # Serialize hooks
        data = self._call_serialize_hooks(model_class, data)
        self._call_validate_hooks(model_class, data)

        # Store as JSON
        json_data = json.dumps(data)

        # Using validated and quoted identifier - safe from SQL injection
        self.connection.execute(
            f"INSERT OR REPLACE INTO {quoted_table} (id, data) VALUES (?, ?)",  # nosec B608 - table name validated by regex
            (pk_value, json_data)
        )
        self.connection.commit()

        # Deserialize hooks
        data = self._call_deserialize_hooks(model_class, data)
        return data

    def get(self, model_class: type["Model"], **filters: Any) -> Optional[dict[str, Any]]:
        """
        Get a single record by ID or filters.

        Args:
            model_class: Model class
            **filters: Filter conditions

        Returns:
            Record data, or None if not found
        """
        self._ensure_table(model_class)

        # Try to get by ID first
        pk_value = self._get_primary_key_value(filters)
        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        if pk_value:
            # Using validated and quoted identifier - safe from SQL injection
            cursor = self.connection.execute(
                f"SELECT data FROM {quoted_table} WHERE id = ?",  # nosec B608 - table name validated by regex
                (pk_value,)
            )
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                data = self._call_deserialize_hooks(model_class, data)
                return data

        # Fall back to query
        result = self.query(model_class).and_(**filters).first()
        if result:
            return result.model_dump()

        return None

    def update(
        self,
        model_class: type["Model"],
        instance: "Model"
    ) -> dict[str, Any]:
        """
        Update an existing record.

        Args:
            model_class: Model class
            instance: Model instance with updated data

        Returns:
            Updated record data

        Raises:
            NotFoundError: If record not found
        """
        self._ensure_table(model_class)

        # Convert instance to dict
        data = instance.model_dump()

        # Get primary key
        pk_value = self._get_primary_key_value(data)
        if not pk_value:
            raise ValueError("Record must have an 'id' field")

        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        # Serialize hooks
        data = self._call_serialize_hooks(model_class, data)
        self._call_validate_hooks(model_class, data)

        # Store as JSON
        json_data = json.dumps(data)

        # Using validated and quoted identifier - safe from SQL injection
        cursor = self.connection.execute(
            f"UPDATE {quoted_table} SET data = ? WHERE id = ?",  # nosec B608 - table name validated by regex
            (json_data, pk_value)
        )

        if cursor.rowcount == 0:
            raise NotFoundError(f"Record with id '{pk_value}' not found")

        self.connection.commit()

        # Deserialize hooks
        data = self._call_deserialize_hooks(model_class, data)
        return data

    def delete(self, model_class: type["Model"], instance: "Model") -> bool:
        """
        Delete a record.

        Args:
            model_class: Model class
            instance: Model instance to delete

        Returns:
            True if deleted successfully
        """
        self._ensure_table(model_class)

        # Convert instance to dict
        data = instance.model_dump()

        # Get primary key
        pk_value = self._get_primary_key_value(data)
        if not pk_value:
            raise ValueError("Record must have an 'id' field")

        table_name = self._get_table_name(model_class)
        quoted_table = self._quote_identifier(table_name)

        # Using validated and quoted identifier - safe from SQL injection
        cursor = self.connection.execute(
            f"DELETE FROM {quoted_table} WHERE id = ?",  # nosec B608 - table name validated by regex
            (pk_value,)
        )
        self.connection.commit()

        return cursor.rowcount > 0

    def query(self, model_class: type["Model"]) -> "QueryBuilder":
        """
        Create a query builder for complex queries.

        Returns:
            SqliteQueryBuilder instance
        """
        query_builder: QueryBuilder = SqliteQueryBuilder(model_class, self)
        query_builder = self._call_modify_query_hooks(model_class, query_builder)
        return query_builder

    def count(self, model_class: type["Model"], **filters: Any) -> int:
        """Count records matching filters."""
        return self.query(model_class).and_(**filters).count()

    def exists(self, model_class: type["Model"], **filters: Any) -> bool:
        """Check if a record exists."""
        return self.query(model_class).and_(**filters).exists()


class SqliteQueryBuilder(QueryBuilder):
    """Query builder for SQLite backend using proper SQL queries."""

    def __init__(self, model_class: type["Model"], backend: SqliteBackend):
        """Initialize query builder."""
        super().__init__(model_class)
        self.backend = backend

    def _build_where_clause(self) -> tuple[str, list[Any]]:
        """
        Build WHERE clause from filters using SQLite JSON functions.

        Returns:
            Tuple of (where_clause, params)
        """
        if not self._filters:
            return "", []

        where_parts = []
        params = []

        for filter_type, conditions in self._filters:
            for field, value in conditions.items():
                # Use json_extract to query JSON fields
                json_path = f"$.{field}"

                if filter_type == "and":
                    # For equality: json_extract(data, '$.field') = ?
                    where_parts.append("json_extract(data, ?) = ?")
                    params.extend([json_path, json.dumps(value) if not isinstance(value, (str, int, float, bool, type(None))) else value])
                elif filter_type == "not":
                    # For inequality: json_extract(data, '$.field') != ? OR json_extract(data, '$.field') IS NULL
                    where_parts.append("(json_extract(data, ?) != ? OR json_extract(data, ?) IS NULL)")
                    params.extend([json_path, json.dumps(value) if not isinstance(value, (str, int, float, bool, type(None))) else value, json_path])

        if where_parts:
            return " AND ".join(where_parts), params
        return "", []

    def _build_order_clause(self) -> str:
        """Build ORDER BY clause using SQLite JSON functions."""
        if not self._order_by:
            return ""

        order_parts = []
        for order_field in self._order_by:
            reverse = order_field.startswith("-")
            field = order_field[1:] if reverse else order_field
            direction = "DESC" if reverse else "ASC"

            # Use json_extract for ordering
            order_parts.append(f"json_extract(data, '$.{field}') {direction}")

        return " ORDER BY " + ", ".join(order_parts)

    def _build_limit_offset_clause(self) -> str:
        """Build LIMIT and OFFSET clause."""
        parts = []

        # SQLite requires LIMIT when using OFFSET
        if self._limit:
            parts.append(f"LIMIT {self._limit}")
        elif self._offset:
            # Use LIMIT -1 (no limit) when offset is specified without limit
            parts.append("LIMIT -1")

        if self._offset:
            parts.append(f"OFFSET {self._offset}")

        return " " + " ".join(parts) if parts else ""

    def all(self) -> list["Model"]:
        """Execute query and return all results using SQL."""
        self.backend._ensure_table(self.model_class)
        table_name = self.backend._get_table_name(self.model_class)
        quoted_table = self.backend._quote_identifier(table_name)

        # Build SQL query
        where_clause, params = self._build_where_clause()
        order_clause = self._build_order_clause()
        limit_offset_clause = self._build_limit_offset_clause()

        # Construct query - table name is from model class (not user input)
        sql = f"SELECT data FROM {quoted_table}"  # nosec B608 - table name validated by regex

        if where_clause:
            sql += f" WHERE {where_clause}"

        sql += order_clause
        sql += limit_offset_clause

        # Execute query with parameterized values
        cursor = self.backend.connection.execute(sql, params)

        results = []
        for row in cursor:
            data = json.loads(row[0])
            data = self.backend._call_deserialize_hooks(self.model_class, data)

            instance = self.model_class(**data)
            instance._is_persisted = True

            # Call after_load hooks
            for hook in self.model_class._after_load_hooks:
                hook(instance)

            results.append(instance)

        # Apply result filters (these are Python-level filters like permissions)
        results = self._apply_result_filters(results)

        return results

    def first(self) -> Optional["Model"]:
        """Get the first result using LIMIT 1."""
        self.backend._ensure_table(self.model_class)
        table_name = self.backend._get_table_name(self.model_class)
        quoted_table = self.backend._quote_identifier(table_name)

        # Build SQL query with LIMIT 1
        where_clause, params = self._build_where_clause()
        order_clause = self._build_order_clause()

        sql = f"SELECT data FROM {quoted_table}"  # nosec B608 - table name validated by regex

        if where_clause:
            sql += f" WHERE {where_clause}"

        sql += order_clause
        sql += " LIMIT 1"

        # Execute and fetch single row
        cursor = self.backend.connection.execute(sql, params)
        row = cursor.fetchone()

        if not row:
            return None

        # Deserialize single record
        data = json.loads(row[0])
        data = self.backend._call_deserialize_hooks(self.model_class, data)

        instance = self.model_class(**data)
        instance._is_persisted = True

        # Call after_load hooks
        for hook in self.model_class._after_load_hooks:
            hook(instance)

        # Apply result filters (permissions, etc.)
        results = self._apply_result_filters([instance])
        return results[0] if results else None

    def last(self) -> Optional["Model"]:
        """Get the last result using reversed ORDER BY and LIMIT 1."""
        self.backend._ensure_table(self.model_class)
        table_name = self.backend._get_table_name(self.model_class)
        quoted_table = self.backend._quote_identifier(table_name)

        # Build SQL query with LIMIT 1
        where_clause, params = self._build_where_clause()

        # If no ordering specified, use SQLite's implicit rowid in descending order
        if not self._order_by:
            order_clause = " ORDER BY rowid DESC"
        else:
            # Reverse all order_by fields
            reversed_order = []
            for field in self._order_by:
                if field.startswith("-"):
                    # Remove the minus to reverse descending -> ascending
                    reversed_order.append(field[1:])
                else:
                    # Add minus to reverse ascending -> descending
                    reversed_order.append(f"-{field}")

            # Build reversed order clause
            order_parts = []
            for order_field in reversed_order:
                reverse = order_field.startswith("-")
                field = order_field[1:] if reverse else order_field
                direction = "DESC" if reverse else "ASC"
                order_parts.append(f"json_extract(data, '$.{field}') {direction}")
            order_clause = " ORDER BY " + ", ".join(order_parts)

        sql = f"SELECT data FROM {quoted_table}"  # nosec B608 - table name validated by regex

        if where_clause:
            sql += f" WHERE {where_clause}"

        sql += order_clause
        sql += " LIMIT 1"

        # Execute and fetch single row
        cursor = self.backend.connection.execute(sql, params)
        row = cursor.fetchone()

        if not row:
            return None

        # Deserialize single record
        data = json.loads(row[0])
        data = self.backend._call_deserialize_hooks(self.model_class, data)

        instance = self.model_class(**data)
        instance._is_persisted = True

        # Call after_load hooks
        for hook in self.model_class._after_load_hooks:
            hook(instance)

        # Apply result filters (permissions, etc.)
        results = self._apply_result_filters([instance])
        return results[0] if results else None

    def count(self) -> int:
        """Count results using SQL COUNT()."""
        self.backend._ensure_table(self.model_class)
        table_name = self.backend._get_table_name(self.model_class)
        quoted_table = self.backend._quote_identifier(table_name)

        # Build WHERE clause
        where_clause, params = self._build_where_clause()

        # Build count query - table name is from model class (not user input)
        sql = f"SELECT COUNT(*) FROM {quoted_table}"  # nosec B608 - table name validated by regex

        if where_clause:
            sql += f" WHERE {where_clause}"

        cursor = self.backend.connection.execute(sql, params)
        result = cursor.fetchone()
        return result[0] if result else 0

    def exists(self) -> bool:
        """Check if any results exist using SQL EXISTS."""
        self.backend._ensure_table(self.model_class)
        table_name = self.backend._get_table_name(self.model_class)
        quoted_table = self.backend._quote_identifier(table_name)

        # Build WHERE clause
        where_clause, params = self._build_where_clause()

        # Build exists query - table name is from model class (not user input)
        sql = f"SELECT EXISTS(SELECT 1 FROM {quoted_table}"  # nosec B608 - table name validated by regex

        if where_clause:
            sql += f" WHERE {where_clause}"

        sql += " LIMIT 1)"

        cursor = self.backend.connection.execute(sql, params)
        result = cursor.fetchone()
        return bool(result[0]) if result else False

    def paginate(self) -> tuple[list["Model"], Optional[Any]]:
        """
        Execute query and return results with pagination cursor.

        For SQLite, we use offset-based pagination.
        The cursor is the next offset value.

        Returns:
            Tuple of (results, next_cursor or None)
        """
        results = self.all()

        # Calculate next cursor
        next_cursor = None
        if results and self._limit:
            current_offset = self._offset or 0
            if len(results) == self._limit:
                # There might be more results
                next_cursor = current_offset + self._limit

        return results, next_cursor

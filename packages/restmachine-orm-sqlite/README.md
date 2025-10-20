# restmachine-orm-sqlite

SQLite backend for RestMachine ORM.

Provides a simple file-based database for local development and testing.

## Features

- Zero configuration - uses Python's built-in sqlite3
- File-based persistence - easy to inspect and version control
- Perfect for development and testing
- Document-store style - stores models as JSON documents

## Installation

```bash
pip install restmachine-orm-sqlite
```

## Usage

```python
from restmachine_orm_sqlite import SqliteBackend

# Use default database file (data.db)
backend = SqliteBackend()

# Or specify custom file
backend = SqliteBackend(database="myapp.db")
```

## CLI Integration

When creating a new RestMachine project, SQLite is the default backend:

```bash
restmachine new myapp
# Creates project with SQLite backend (default)

restmachine new myapp --backend sqlite
# Explicitly use SQLite backend
```

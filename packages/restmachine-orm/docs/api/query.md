# Query API

RestMachine ORM provides a chainable query interface for filtering, ordering, and retrieving data.

## Starting a Query

Queries are started from model classes:

```python
# Start a query
query = User.where()

# Start with filters
query = User.where(age__gte=18)
```

## Query Methods

### Filtering

- `where(**filters)` - Start a query with filters
- `and_(**filters)` - Add AND conditions
- `not_(**filters)` - Add NOT conditions

### Comparison Operators

Use these suffixes in filter kwargs:

- `field__gt` - Greater than
- `field__gte` - Greater than or equal
- `field__lt` - Less than
- `field__lte` - Less than or equal

Example:
```python
users = User.where().and_(age__gte=18, age__lt=65).all()
```

### Ordering

- `order_by(*fields)` - Order results
  - Use `"field"` for ascending
  - Use `"-field"` for descending

Example:
```python
users = User.where().order_by("-age", "name").all()
```

### Pagination

- `limit(n)` - Limit results
- `offset(n)` - Skip n results
- `cursor(cursor_value)` - Use cursor for pagination

Example:
```python
# Offset-based
page1 = User.where().limit(10).all()
page2 = User.where().limit(10).offset(10).all()

# Cursor-based
results, cursor = User.where().limit(10).paginate()
if cursor:
    more, next_cursor = User.where().limit(10).cursor(cursor).paginate()
```

### Execution

- `all()` - Get all matching results
- `first()` - Get first result or None
- `last()` - Get last result or None
- `count()` - Count matching results
- `exists()` - Check if any match
- `paginate()` - Get results and pagination cursor

Example:
```python
# Get all
all_users = User.where().all()

# Get first
first_user = User.where().first()

# Count
total = User.where().count()

# Check existence
has_admin = User.where().and_(role="admin").exists()
```

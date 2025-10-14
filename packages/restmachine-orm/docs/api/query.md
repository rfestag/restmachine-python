# Query API

RestMachine ORM provides a chainable query interface for filtering, ordering, and retrieving data.

## Starting a Query

Queries are started from model classes:

```python
# Start a query
query = User.where()

# Start with filters (keyword style)
query = User.where(age__gte=18)

# Start with field expressions (recommended)
query = User.where(User.age >= 18)
```

## Query Syntax Styles

RestMachine ORM supports two query syntax styles:

### Field Expression Syntax (Recommended)

SQLAlchemy-style field expressions provide a Pythonic, type-safe way to build queries:

```python
# Basic comparisons
users = User.where(User.age > 25).all()
users = User.where(User.status == "active").all()

# Boolean operators
young_or_old = User.where((User.age < 18) | (User.age > 65)).all()
adults = User.where((User.age >= 18) & (User.age <= 65)).all()
not_deleted = User.where(~(User.status == "deleted")).all()

# String methods
alice_users = User.where(User.name.startswith("Alice")).all()
gmail_users = User.where(User.email.endswith("@gmail.com")).all()
search_users = User.where(User.bio.contains("python")).all()

# Mix with keyword filters
users = User.where(User.age >= 18, is_verified=True).all()
```

**Field Expression Operators:**
- `==` - Equal
- `!=` - Not equal
- `>` - Greater than
- `>=` - Greater than or equal
- `<` - Less than
- `<=` - Less than or equal
- `&` - AND (must wrap expressions in parentheses)
- `|` - OR (must wrap expressions in parentheses)
- `~` - NOT

**Field Expression Methods:**
- `.startswith(value)` - String starts with
- `.endswith(value)` - String ends with
- `.contains(value)` - String contains
- `.in_(values)` - Field in list

### Keyword Syntax (Classic)

Traditional Django-style keyword arguments are still fully supported:

```python
# Basic filters
users = User.where(age__gte=18).all()
users = User.where(status="active").all()

# Chaining with and_()
users = User.where(age__gte=18).and_(status="active").all()

# NOT conditions
users = User.where().not_(status="deleted").all()
```

## Query Methods

### Filtering

- `where(*expressions, **filters)` - Start query with expressions and/or keyword filters
- `and_(**filters)` - Add AND conditions (keyword style only)
- `not_(**filters)` - Add NOT conditions (keyword style only)

### Comparison Operators (Keyword Syntax)

Use these suffixes in filter kwargs:

- `field__gt` - Greater than
- `field__gte` - Greater than or equal
- `field__lt` - Less than
- `field__lte` - Less than or equal
- `field__ne` - Not equal
- `field__in` - In list
- `field__contains` - Contains substring
- `field__startswith` - Starts with
- `field__endswith` - Ends with

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

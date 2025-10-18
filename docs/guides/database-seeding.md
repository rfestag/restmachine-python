# Database Seeding with Hierarchical Fixtures

RestMachine provides a powerful fixture seeding system that follows the same hierarchical pattern as configuration loading. This allows you to maintain different fixtures for different environments and deployment contexts.

## Quick Start

### 1. Create Fixture Files

Create YAML fixture files in your project's `db/fixtures/` directory:

```yaml
# db/fixtures/users.yaml
model: User
upsert_key: email
records:
  - email: admin@example.com
    name: Admin User
    role: admin
```

### 2. Run the Seed Command

```bash
# Seed with defaults from config/hierarchy.yaml
restmachine seed

# Seed specific environment
restmachine seed --environment production

# Preview what would be loaded (dry-run)
restmachine seed --dry-run
```

## Fixture File Format

Fixture files use YAML format with three main keys:

```yaml
model: ModelName              # Required: ORM model class name
upsert_key: field_name        # Optional: field(s) for get-or-create
records:                      # Required: list of records to create
  - field1: value1
    field2: value2
```

### Fields

- **`model`** (required): The name of the ORM model class (e.g., `User`, `Product`)
- **`upsert_key`** (optional): Field name or list of field names to use for get-or-create logic
  - If present: existing records are updated, new ones are created
  - If absent and record has `id`: uses `id` for upsert
  - If absent and no `id`: always creates new record
- **`records`** (required): List of record dictionaries

### Special Fields

- **`_fixture_id`** (optional): Identifier for cross-level deduplication
  - Used during fixture loading to identify "same" record across hierarchy
  - Stripped before saving to database
  - Records with same `_fixture_id` at deeper levels replace shallower ones

## Hierarchical Loading

Fixtures are loaded hierarchically based on the config path and environment, following the same pattern as configuration:

### Directory Structure

```
db/fixtures/
  users.yaml                    # Root level (always loaded)
  reference-data.yaml

  local/
    development/
      dev-users.yaml           # Local development
    production/
      prod-users.yaml          # Local production

  aws/
    shared.yaml                # AWS partition

    123456789012/
      account-fixtures.yaml    # AWS account

      us-east-1/
        region-fixtures.yaml   # AWS region

        production/
          prod-data.yaml       # Environment-specific
```

### Load Order

For `RESTMACHINE_CONFIG_PATH=aws/123456789012/us-east-1` and `RESTMACHINE_ENVIRONMENT=production`:

1. `db/fixtures/*.yaml` (root level)
2. `db/fixtures/aws/*.yaml`
3. `db/fixtures/aws/123456789012/*.yaml`
4. `db/fixtures/aws/123456789012/us-east-1/*.yaml`
5. `db/fixtures/aws/123456789012/us-east-1/production/*.yaml`

### Merging Strategy

- **Files**: Additive (all applicable files are loaded)
- **Records**: Merged by `_fixture_id`
  - Records without `_fixture_id`: all kept (additive)
  - Records with same `_fixture_id`: deeper level replaces shallower

## Examples

### Basic Fixture

```yaml
# db/fixtures/users.yaml
model: User
upsert_key: email
records:
  - email: user1@example.com
    name: User 1
  - email: user2@example.com
    name: User 2
```

### Environment Override

```yaml
# db/fixtures/users.yaml (root - always loaded)
model: User
upsert_key: email
records:
  - _fixture_id: admin
    email: admin@example.com
    name: Base Admin
    role: admin
```

```yaml
# db/fixtures/aws/production/users.yaml (production override)
model: User
upsert_key: email
records:
  - _fixture_id: admin      # Same _fixture_id = replacement
    email: admin@prod.com   # Different values
    name: Production Admin
    mfa_required: true     # Additional fields
```

**Result**: In production, only the production admin record exists (complete replacement, not merge).

### Composite Upsert Key

```yaml
# db/fixtures/tenant-users.yaml
model: TenantUser
upsert_key: [tenant_id, email]
records:
  - tenant_id: tenant-1
    email: user@example.com
    name: User 1
  - tenant_id: tenant-2
    email: user@example.com
    name: User 2
```

### No Upsert Key (Always Create)

```yaml
# db/fixtures/countries.yaml
model: Country
# No upsert_key - will use 'id' field if present
records:
  - id: US
    name: United States
  - id: CA
    name: Canada
```

## CLI Command Reference

### `restmachine seed`

Load fixtures into the database.

```bash
restmachine seed [OPTIONS]
```

**Options:**

- `--project-dir PATH`: Project directory (default: current directory)
- `--environment ENV`: Environment to seed (overrides `RESTMACHINE_ENVIRONMENT`)
- `--path PATH`: Config path to use (overrides `RESTMACHINE_CONFIG_PATH`)
- `--dry-run`: Show what would be loaded without saving to database
- `--fixture FILENAME`: Load only specific fixture file(s) (can be specified multiple times)
- `--clear`: Clear/truncate tables before seeding
- `--verbose`: Show detailed loading information

**Examples:**

```bash
# Use defaults from config/hierarchy.yaml
restmachine seed

# Seed specific environment
restmachine seed --environment production

# Seed specific path and environment
restmachine seed --path aws/123456/us-east-1 --environment staging

# Preview without saving
restmachine seed --dry-run

# Specify project directory
restmachine seed --project-dir /path/to/project

# Load only specific fixture files
restmachine seed --fixture users.yaml --fixture products.yaml

# Clear tables before seeding
restmachine seed --clear

# Show detailed output
restmachine seed --verbose

# Combine options
restmachine seed --fixture users.yaml --clear --verbose
```

### Environment Variables

The seed command respects the same environment variables as config loading:

- `RESTMACHINE_CONFIG_PATH`: Default config path (e.g., `aws/123456/us-east-1`)
- `RESTMACHINE_ENVIRONMENT`: Default environment (e.g., `production`)

**Priority**: CLI options > environment variables > `hierarchy.yaml` defaults

## Programmatic Usage

You can also use the `FixtureLoader` class directly in Python:

```python
from pathlib import Path
from restmachine.cli.fixtures import FixtureLoader

# Load fixtures
loader = FixtureLoader(
    fixtures_dir=Path("db/fixtures"),
    path="aws/123456/us-east-1",
    environment="production",
    hierarchy_file=Path("config/hierarchy.yaml")
)

fixtures = loader.load()

# Process each fixture
for fixture in fixtures:
    print(f"Model: {fixture.model}")
    print(f"Upsert key: {fixture.upsert_key}")
    print(f"Records: {len(fixture.records)}")

    # Access the model class
    model_class = getattr(models, fixture.model)

    # Save records...
```

### Dry-Run Inspection

```python
# Get summary without loading
summary = loader.get_load_summary()

print(f"Fixtures directory: {summary['fixtures_dir']}")
print(f"Path: {summary['path']}")
print(f"Environment: {summary['environment']}")

for file_info in summary['yaml_files']:
    print(f"  - {file_info['file']}")
```

## Integration with `db/seeds.py`

Projects created with `restmachine new` include a `db/seeds.py` script:

```python
# db/seeds.py
from pathlib import Path
from restmachine.cli.fixtures import FixtureLoader

def seed():
    """Seed the database using hierarchical fixtures."""
    project_dir = Path(__file__).parent.parent
    fixtures_dir = project_dir / "db" / "fixtures"
    hierarchy_file = project_dir / "config" / "hierarchy.yaml"

    loader = FixtureLoader(
        fixtures_dir=fixtures_dir,
        hierarchy_file=hierarchy_file
    )

    fixtures = loader.load()

    # Import models and save fixtures...
```

Run directly: `python db/seeds.py`

## Advanced Features

### Selective Fixture Loading

Use the `--fixture` flag to load only specific fixture files instead of all fixtures:

```bash
# Load only users
restmachine seed --fixture users.yaml

# Load multiple specific fixtures
restmachine seed --fixture users.yaml --fixture products.yaml
```

This is useful when:
- You only need to update specific data
- Testing specific models during development
- Avoiding loading large fixture sets

### Clear/Truncate Tables

Use the `--clear` flag to truncate tables before seeding:

```bash
# Clear all tables then seed
restmachine seed --clear

# Clear and load only specific fixtures
restmachine seed --clear --fixture users.yaml
```

**Important**: The `--clear` flag will delete ALL existing records in the models referenced by your fixtures before loading new data. Use with caution in production!

### Verbose Output

Use the `--verbose` flag to see detailed loading information:

```bash
# See exactly what's being loaded
restmachine seed --verbose

# Combine with dry-run for maximum detail
restmachine seed --dry-run --verbose
```

Verbose mode shows:
- Full directory hierarchy being traversed
- Each fixture file with its source directory
- Record counts per model as they're created/updated

## Best Practices

1. **Use `_fixture_id` for overrides**: When you need environment-specific versions of the same logical record
2. **Keep root fixtures minimal**: Put only truly global data at the root level
3. **Use `upsert_key` for idempotency**: Makes re-running seeds safe
4. **Test with `--dry-run`**: Preview what will be loaded before committing
5. **Version control fixtures**: Treat fixtures as code - commit them to your repository
6. **Separate by concern**: Use different files for different models or logical groups

## Future Enhancements

The following enhancements are planned for future releases:

- Schema validation against ORM models
- Performance optimizations for large datasets
- Support for fixture dependencies and ordering
- Rollback/undo capabilities
- Fixture versioning and migration support

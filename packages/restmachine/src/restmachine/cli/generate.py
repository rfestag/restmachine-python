"""
Command to generate RestMachine scaffolding.

Usage:
    restmachine generate scaffold Product
    restmachine generate scaffold BlogPost --skip-tests
"""

from pathlib import Path
from typing import Dict, Any
import click
import inflection
from jinja2 import Environment, PackageLoader, select_autoescape


# Type mapping for field generation
FIELD_TYPE_MAP: Dict[str, Dict[str, Any]] = {
    "str": {
        "python_type": "str",
        "field_def": "{name}: str",
        "needs_import": None,
        "fixture_example": "example_{name}",
    },
    "int": {
        "python_type": "int",
        "field_def": "{name}: int",
        "needs_import": None,
        "fixture_example": "42",
    },
    "float": {
        "python_type": "float",
        "field_def": "{name}: float",
        "needs_import": None,
        "fixture_example": "3.14",
    },
    "bool": {
        "python_type": "bool",
        "field_def": "{name}: bool",
        "needs_import": None,
        "fixture_example": "true",
    },
    "datetime": {
        "python_type": "datetime",
        "field_def": "{name}: datetime",
        "needs_import": "datetime",
        "fixture_example": "2024-01-01T12:00:00Z",
    },
    "uuid": {
        "python_type": "str",
        "field_def": "{name}: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))",
        "needs_import": "uuid",
        "fixture_example": "550e8400-e29b-41d4-a716-446655440000",
    },
}


@click.group()
def generate():
    """Generate code scaffolding."""
    pass


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option(
    "--skip-fixtures",
    is_flag=True,
    help="Skip fixture generation"
)
def model(name: str, fields: tuple[str, ...], skip_fixtures: bool):
    """
    Generate a model with specified fields.

    Fields should be specified as name:type pairs.

    Supported types:
    - str, int, float, bool, datetime
    - uuid (auto-generates UUID if not provided)

    Examples:
        restmachine generate model User name:str email:str age:int
        restmachine generate model Product id:uuid name:str price:float is_active:bool
    """
    # Validate we're in a RestMachine project
    if not _is_restmachine_project():
        click.echo(
            click.style("Error: Not in a RestMachine project directory", fg="red"),
            err=True
        )
        click.echo("Run this command from your project root (where app.py exists)", err=True)
        raise click.Abort()

    # Generate name variations
    resource_name = inflection.camelize(name)
    resource_snake = inflection.underscore(name)

    # Parse fields
    parsed_fields = []
    needs_uuid_import = False
    needs_datetime_import = False

    for field_spec in fields:
        if ":" not in field_spec:
            click.echo(
                click.style(f"Error: Invalid field specification '{field_spec}'. Use format 'name:type'", fg="red"),
                err=True
            )
            raise click.Abort()

        field_name, field_type = field_spec.split(":", 1)

        # Validate field type
        if field_type not in FIELD_TYPE_MAP:
            valid_types = list(FIELD_TYPE_MAP.keys())
            click.echo(
                click.style(f"Error: Unsupported type '{field_type}'. Supported types: {', '.join(valid_types)}", fg="red"),
                err=True
            )
            raise click.Abort()

        # Get type mapping info
        type_info = FIELD_TYPE_MAP[field_type]

        # Track which imports we need
        if type_info["needs_import"] == "uuid":
            needs_uuid_import = True
        elif type_info["needs_import"] == "datetime":
            needs_datetime_import = True

        # Build field with all info from mapping
        parsed_fields.append({
            "name": field_name,
            "type": field_type,
            "python_type": type_info["python_type"],
            "field_def": type_info["field_def"].format(name=field_name),
            "fixture_example": type_info["fixture_example"].format(name=field_name) if "{name}" in type_info["fixture_example"] else type_info["fixture_example"],
        })

    click.echo(f"Generating model {resource_name} with {len(parsed_fields)} field(s)...")

    # Prepare context
    context = {
        "resource_name": resource_name,
        "resource_snake": resource_snake,
        "project_name": _get_project_name(),
        "fields": parsed_fields,
        "needs_uuid_import": needs_uuid_import,
        "needs_datetime_import": needs_datetime_import,
    }

    # Generate model file
    model_file = _generate_model_only(context)
    click.echo(click.style(f"  ✓ Created {model_file}", fg="green"))

    # Generate fixture (if not skipped)
    if not skip_fixtures:
        fixture_file = _generate_model_fixture(context)
        click.echo(click.style(f"  ✓ Created {fixture_file}", fg="green"))

    # Update models/__init__.py
    _update_models_init(resource_name, resource_snake)
    click.echo(click.style("  ✓ Updated models/__init__.py", fg="green"))

    click.echo()
    click.echo(click.style("✓ Model generated successfully!", fg="green", bold=True))
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review the generated model in models/{resource_snake}.py")
    click.echo("  2. Add any additional fields or methods as needed")
    if not skip_fixtures:
        click.echo(f"  3. Customize fixture data in db/fixtures/{resource_snake}.yaml")
    click.echo()


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option(
    "--skip-tests",
    is_flag=True,
    help="Skip test generation"
)
@click.option(
    "--skip-fixtures",
    is_flag=True,
    help="Skip fixture generation"
)
def scaffold(name: str, fields: tuple[str, ...], skip_tests: bool, skip_fixtures: bool):
    """
    Generate a complete CRUD resource scaffold.

    Creates model, schemas, routes, fixture template, and tests for a resource.
    Optionally specify fields as name:type pairs.

    Supported types:
    - str, int, float, bool, datetime
    - uuid (auto-generates UUID if not provided)

    Examples:
        restmachine generate scaffold Product
        restmachine generate scaffold Product name:str price:float stock:int
        restmachine generate scaffold BlogPost title:str content:str published_at:datetime --skip-tests
    """
    # Validate we're in a RestMachine project
    if not _is_restmachine_project():
        click.echo(
            click.style("Error: Not in a RestMachine project directory", fg="red"),
            err=True
        )
        click.echo("Run this command from your project root (where app.py exists)", err=True)
        raise click.Abort()

    # Generate name variations
    resource_name = inflection.camelize(name)
    resource_snake = inflection.underscore(name)
    resource_plural = inflection.pluralize(resource_snake)
    resource_singular = resource_snake
    resource_name_plural = inflection.camelize(resource_plural)

    click.echo(f"Generating scaffold for {resource_name}...")

    # Parse fields (or use default id:uuid if no fields specified)
    parsed_fields = []
    needs_uuid_import = True  # Always need UUID for id field
    needs_datetime_import = False

    # Always add id:uuid as first field
    uuid_type_info = FIELD_TYPE_MAP["uuid"]
    parsed_fields.append({
        "name": "id",
        "type": "uuid",
        "python_type": uuid_type_info["python_type"],
        "field_def": uuid_type_info["field_def"].format(name="id"),
        "fixture_example": uuid_type_info["fixture_example"],
    })

    # Parse additional fields if provided
    for field_spec in fields:
        if ":" not in field_spec:
            click.echo(
                click.style(f"Error: Invalid field specification '{field_spec}'. Use format 'name:type'", fg="red"),
                err=True
            )
            raise click.Abort()

        field_name, field_type = field_spec.split(":", 1)

        # Validate field type
        if field_type not in FIELD_TYPE_MAP:
            valid_types = list(FIELD_TYPE_MAP.keys())
            click.echo(
                click.style(f"Error: Unsupported type '{field_type}'. Supported types: {', '.join(valid_types)}", fg="red"),
                err=True
            )
            raise click.Abort()

        # Get type mapping info
        type_info = FIELD_TYPE_MAP[field_type]

        # Track which imports we need
        if type_info["needs_import"] == "datetime":
            needs_datetime_import = True

        # Build field with all info from mapping
        parsed_fields.append({
            "name": field_name,
            "type": field_type,
            "python_type": type_info["python_type"],
            "field_def": type_info["field_def"].format(name=field_name),
            "fixture_example": type_info["fixture_example"].format(name=field_name) if "{name}" in type_info["fixture_example"] else type_info["fixture_example"],
        })

    # Prepare context for model
    model_context = {
        "resource_name": resource_name,
        "resource_snake": resource_snake,
        "project_name": _get_project_name(),
        "fields": parsed_fields,
        "needs_uuid_import": needs_uuid_import,
        "needs_datetime_import": needs_datetime_import,
    }

    # Prepare context for other components
    context = {
        "resource_name": resource_name,
        "resource_snake": resource_snake,
        "resource_plural": resource_plural,
        "resource_singular": resource_singular,
        "resource_name_plural": resource_name_plural,
        "project_name": _get_project_name(),
    }

    # Generate files
    generated_files = []

    # 1. Model (using model generator for consistency)
    model_file = _generate_model_only(model_context)
    generated_files.append(model_file)

    # 2. Schemas
    schemas_file = _generate_schemas(context)
    generated_files.append(schemas_file)

    # 3. Routes
    routes_file = _generate_routes(context)
    generated_files.append(routes_file)

    # 4. Fixture (if not skipped)
    if not skip_fixtures:
        fixture_file = _generate_fixture(context)
        generated_files.append(fixture_file)

    # 5. Tests (if not skipped)
    if not skip_tests:
        test_file = _generate_integration_test(context)
        generated_files.append(test_file)

    # 6. Update __init__.py files
    _update_models_init(resource_name, resource_snake)
    _update_schemas_init(resource_name, resource_snake, resource_name_plural)

    # 7. Auto-mount to app.py
    _auto_mount_router(context)

    # Show success
    click.echo()
    for file_path in generated_files:
        click.echo(click.style(f"  ✓ Created {file_path}", fg="green"))

    click.echo(click.style("  ✓ Updated models/__init__.py", fg="green"))
    click.echo(click.style("  ✓ Updated schemas/__init__.py", fg="green"))
    click.echo(click.style("  ✓ Mounted router in app.py", fg="green"))

    click.echo()
    click.echo(click.style("✓ Scaffold generated successfully!", fg="green", bold=True))
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Add fields to models/{resource_snake}.py")
    click.echo(f"  2. Update schemas in schemas/{resource_snake}_schemas.py")
    if not skip_fixtures:
        click.echo(f"  3. Customize db/fixtures/{resource_plural}.yaml")
    if not skip_tests:
        click.echo(f"  4. Implement tests in tests/integration/test_{resource_plural}_api.py")
    click.echo(f"  5. Run tests: pytest tests/integration/test_{resource_plural}_api.py")
    click.echo()


def _is_restmachine_project() -> bool:
    """Check if current directory is a RestMachine project."""
    cwd = Path.cwd()
    # Check for app.py and models/ directory
    return (cwd / "app.py").exists() and (cwd / "models").is_dir()


def _get_project_name() -> str:
    """Get project name from current directory."""
    return Path.cwd().name


def _generate_schemas(context: dict) -> str:
    """Generate schemas file."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/schemas.py.j2")
    content = template.render(context)

    output_path = Path(f"schemas/{context['resource_snake']}_schemas.py")
    output_path.write_text(content)

    return str(output_path)


def _generate_routes(context: dict) -> str:
    """Generate routes file."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/routes.py.j2")
    content = template.render(context)

    output_path = Path(f"routes/{context['resource_plural']}.py")
    output_path.write_text(content)

    return str(output_path)


def _generate_fixture(context: dict) -> str:
    """Generate fixture template file."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/fixture.yaml.j2")
    content = template.render(context)

    output_path = Path(f"db/fixtures/{context['resource_plural']}.yaml")
    output_path.write_text(content)

    return str(output_path)


def _generate_integration_test(context: dict) -> str:
    """Generate integration test file."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/integration_test.py.j2")
    content = template.render(context)

    output_path = Path(f"tests/integration/test_{context['resource_plural']}_api.py")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    return str(output_path)


def _update_models_init(resource_name: str, resource_snake: str):
    """Update models/__init__.py to import new model."""
    init_file = Path("models/__init__.py")

    if not init_file.exists():
        return

    content = init_file.read_text()

    # Add import if not already present
    import_line = f"from models.{resource_snake} import {resource_name}"

    if import_line not in content:
        lines = content.split('\n')
        insert_index = len(lines)  # Default to end of file

        # Find where to insert the import
        # Strategy: Insert AFTER the backend initialization to avoid circular imports
        # The backend line typically looks like: backend = SomeBackend(...)
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Look for backend initialization (assignment to 'backend')
            if stripped.startswith('backend =') or stripped.startswith('backend='):
                # Insert after this line
                insert_index = i + 1
                break
        else:
            # No backend found, look for the last import statement
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (stripped.startswith('from ') or stripped.startswith('import ')) and \
                   not stripped.startswith('from models.'):
                    insert_index = i + 1

        # Skip blank lines and comments after the insertion point
        while insert_index < len(lines) and \
              (not lines[insert_index].strip() or lines[insert_index].strip().startswith('#')):
            insert_index += 1

        # Insert new import
        lines.insert(insert_index, import_line)
        init_file.write_text('\n'.join(lines))


def _update_schemas_init(resource_name: str, resource_snake: str, resource_name_plural: str):
    """Update schemas/__init__.py to import new schemas."""
    init_file = Path("schemas/__init__.py")

    if not init_file.exists():
        return

    content = init_file.read_text()

    # Add imports if not already present
    # Using new naming convention: Create{Resource}Request, Update{Resource}Request, List{Resources}Response
    import_line = f"from schemas.{resource_snake}_schemas import Create{resource_name}Request, Update{resource_name}Request, List{resource_name_plural}Response"

    if import_line not in content:
        # Append to end
        if content and not content.endswith('\n'):
            content += '\n'
        content += import_line + '\n'
        init_file.write_text(content)


def _auto_mount_router(context: dict):
    """Auto-mount the router in app.py."""
    app_file = Path("app.py")

    if not app_file.exists():
        return

    content = app_file.read_text()

    # Import statement
    import_line = f"from routes.{context['resource_plural']} import router as {context['resource_plural']}_router"

    # Mount statement
    mount_line = f"app.mount('/{context['resource_plural']}', {context['resource_plural']}_router)"

    # Check if already mounted
    if mount_line in content:
        return

    # Add import after other route imports
    if import_line not in content:
        lines = content.split('\n')
        insert_index = 0

        # Find last route import
        for i, line in enumerate(lines):
            if 'from routes.' in line and 'import router as' in line:
                insert_index = i + 1

        # If no route imports found, add after other imports
        if insert_index == 0:
            for i, line in enumerate(lines):
                if line.startswith('from ') or line.startswith('import '):
                    insert_index = i + 1

        lines.insert(insert_index, import_line)
        content = '\n'.join(lines)

    # Add mount after other mounts
    lines = content.split('\n')
    insert_index = len(lines)

    # Find last app.mount() call
    for i, line in enumerate(lines):
        if 'app.mount(' in line:
            insert_index = i + 1

    lines.insert(insert_index, mount_line)
    app_file.write_text('\n'.join(lines))


def _generate_model_only(context: dict) -> str:
    """Generate model file with specified fields."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/model_with_fields.py.j2")
    content = template.render(context)

    output_path = Path(f"models/{context['resource_snake']}.py")
    output_path.write_text(content)

    return str(output_path)


def _generate_model_fixture(context: dict) -> str:
    """Generate fixture file with example data for fields."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/model_fixture.yaml.j2")
    content = template.render(context)

    output_path = Path(f"db/fixtures/{context['resource_snake']}.yaml")
    output_path.write_text(content)

    return str(output_path)

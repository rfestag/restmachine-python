"""
Command to generate RestMachine scaffolding.

Usage:
    restmachine generate scaffold Product
    restmachine generate scaffold BlogPost --skip-tests
"""

from pathlib import Path
import click
import inflection
from jinja2 import Environment, PackageLoader, select_autoescape


@click.group()
def generate():
    """Generate code scaffolding."""
    pass


@generate.command()
@click.argument("name")
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
def scaffold(name: str, skip_tests: bool, skip_fixtures: bool):
    """
    Generate a complete CRUD resource scaffold.

    Creates model, schemas, routes, fixture template, and tests for a resource.

    Examples:
        restmachine generate scaffold Product
        restmachine generate scaffold BlogPost --skip-tests
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

    # Prepare context
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

    # 1. Model
    model_file = _generate_model(context)
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


def _generate_model(context: dict) -> str:
    """Generate model file."""
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    template = env.get_template("generate/model.py.j2")
    content = template.render(context)

    output_path = Path(f"models/{context['resource_snake']}.py")
    output_path.write_text(content)

    return str(output_path)


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
    # Using new naming convention: Create{Resource}Request, Update{Resource}Request, {Resource}Response, List{Resources}Response
    import_line = f"from schemas.{resource_snake}_schemas import Create{resource_name}Request, Update{resource_name}Request, {resource_name}Response, List{resource_name_plural}Response"

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

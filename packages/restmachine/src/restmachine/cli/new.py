"""
Command to create a new RestMachine project.

Usage:
    restmachine new myapp
    restmachine new myapp --minimal  # Minimal structure
"""

from pathlib import Path
from typing import Optional
import click
from jinja2 import Environment, PackageLoader, select_autoescape


@click.command()
@click.argument("name")
@click.option(
    "--backend",
    default="sqlite",
    help="Backend to use (sqlite, dynamodb, postgresql, etc.)"
)
@click.option(
    "--minimal",
    is_flag=True,
    help="Create minimal project structure (no examples)"
)
@click.option(
    "--directory",
    type=click.Path(),
    default=None,
    help="Directory to create project in (default: ./NAME)"
)
def new_command(name: str, backend: str, minimal: bool, directory: Optional[str]):
    """
    Create a new RestMachine project.

    Creates a default directory structure with:
    - models/         - ORM models
    - schemas/        - Pydantic validation schemas
    - routes/         - Route handlers
    - config/         - Hierarchical configuration
    - tests/          - Test suite
    - app.py          - Application definition
    - main.py         - Development server
    - .restmachine.toml - Project configuration
    """
    from restmachine.cli.plugin_manager import get_plugin_manager
    from restmachine.cli.config import ProjectConfig

    # Validate backend
    plugin_manager = get_plugin_manager()
    backend_plugin = None

    # Built-in backends don't need plugins
    built_in_backends = {"memory", "sqlite"}

    if backend not in built_in_backends:
        backend_plugin = plugin_manager.get_backend(backend)
        if not backend_plugin:
            available = list(built_in_backends) + list(plugin_manager.list_backends().keys())
            click.echo(
                click.style(f"Error: Unknown backend '{backend}'", fg="red"),
                err=True
            )
            click.echo(f"Available backends: {', '.join(sorted(available))}", err=True)
            raise click.Abort()

    # Determine target directory
    if directory:
        project_dir = Path(directory) / name
    else:
        project_dir = Path.cwd() / name

    # Check if directory already exists
    if project_dir.exists():
        click.echo(f"Error: Directory {project_dir} already exists", err=True)
        raise click.Abort()

    # Set display name for backend
    if backend_plugin:
        backend_display = backend_plugin.get_display_name()
    elif backend == "memory":
        backend_display = "Memory (in-process)"
    elif backend == "sqlite":
        backend_display = "SQLite (file-based)"
    else:
        backend_display = backend

    click.echo(f"Creating new RestMachine project: {name}")
    click.echo(f"  Location: {project_dir}")
    click.echo(f"  Backend: {backend_display}")

    # Create directory structure
    _create_directory_structure(project_dir, name, minimal)

    # Render templates
    _render_templates(project_dir, name, minimal)

    # Create .restmachine.toml configuration
    config = ProjectConfig.create_default(project_dir, name, backend)
    config.save()

    click.echo()
    click.echo(click.style("✓ Project created successfully!", fg="green", bold=True))
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  cd {name}")
    click.echo("  python -m venv .venv")
    click.echo("  source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate")
    click.echo("  pip install -e .")
    click.echo("  python main.py")
    click.echo()


def _create_directory_structure(project_dir: Path, name: str, minimal: bool):
    """Create the project directory structure."""
    directories = [
        "models",
        "schemas",
        "routes",
        "config",
        "config/local",
        "db",
        "db/fixtures",
        "db/fixtures/local",
        "db/fixtures/local/development",
        "tests",
        "tests/unit",
        "tests/unit/models",
        "tests/integration",
        "lib",
    ]

    if not minimal:
        directories.append("public")

    for directory in directories:
        (project_dir / directory).mkdir(parents=True, exist_ok=True)

    # Create .gitkeep files for empty fixture directories
    (project_dir / "db" / "fixtures" / ".gitkeep").write_text("")
    (project_dir / "db" / "fixtures" / "local" / "development" / ".gitkeep").write_text("")


def _render_templates(project_dir: Path, name: str, minimal: bool):
    """Render Jinja2 templates into the project directory."""
    # Set up Jinja2 environment
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    # Template context
    context = {
        "project_name": name,
        "minimal": minimal,
    }

    # Templates to render
    templates = [
        ("app.py.j2", "app.py"),
        ("main.py.j2", "main.py"),
        ("lambda_function.py.j2", "lambda_function.py"),
        ("Dockerfile.j2", "Dockerfile"),
        ("docker-compose.yml.j2", "docker-compose.yml"),
        (".gitignore.j2", ".gitignore"),
        (".env.example.j2", ".env.example"),
        ("pyproject.toml.j2", "pyproject.toml"),
        ("README.md.j2", "README.md"),

        # Config
        ("config/settings.py.j2", "config/settings.py"),
        ("config/__init__.py.j2", "config/__init__.py"),
        ("config/hierarchy.yaml.j2", "config/hierarchy.yaml"),
        ("config/local/development.yaml.j2", "config/local/development.yaml"),

        # Models
        ("models/__init__.py.j2", "models/__init__.py"),

        # Schemas
        ("schemas/__init__.py.j2", "schemas/__init__.py"),

        # Routes
        ("routes/__init__.py.j2", "routes/__init__.py"),
        ("routes/health.py.j2", "routes/health.py"),

        # Lib
        ("lib/__init__.py.j2", "lib/__init__.py"),

        # DB
        ("db/seeds.py.j2", "db/seeds.py"),

        # Tests
        ("tests/__init__.py.j2", "tests/__init__.py"),
        ("tests/conftest.py.j2", "tests/conftest.py"),
    ]

    # Always include dependencies file
    templates.append(("lib/dependencies.py.j2", "lib/dependencies.py"))

    # Render each template
    for template_name, output_path in templates:
        try:
            template = env.get_template(template_name)
            content = template.render(context)

            output_file = project_dir / output_path
            output_file.write_text(content)

        except Exception as e:
            click.echo(f"Warning: Could not render {template_name}: {e}", err=True)

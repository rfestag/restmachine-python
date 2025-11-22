"""
Command to generate RestMachine scaffolding.

Usage:
    restmachine generate scaffold Product
    restmachine generate scaffold BlogPost --skip-tests
    restmachine generate model User name:str email:str --backend aws
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import click
import inflection
from jinja2 import Environment, PackageLoader, select_autoescape


# ============================================================================
# Controller Action Specification
# ============================================================================

@dataclass
class ActionSpec:
    """Complete specification for a controller action."""
    name: str                      # e.g., "list", "create", "activate"
    http_method: str               # "get", "post", "put", "delete", "patch"
    path: str                      # "/", "/{id}", "/{id}/activate"
    input_schema: Optional[str]    # "CreateProductRequest", None
    output_schema: Optional[str]   # "Product", "ListProductsResponse", None
    requires_resource: bool        # True for show/update/delete (needs /{id})
    description: str               # Docstring for the action


# Standard CRUD actions with well-known HTTP methods
STANDARD_CRUD_METHODS = {
    "create": "post",
    "update": "put",
    "delete": "delete",
    # list, show, index, etc. default to GET
}


def _parse_action(action_str: str) -> Tuple[str, str]:
    """
    Parse action string like 'activate:post' or 'list'.

    Returns:
        Tuple of (action_name, http_method)

    Examples:
        "list" → ("list", "get")
        "create" → ("create", "post")
        "activate:post" → ("activate", "post")
        "approve" → ("approve", "get")  # Defaults to GET
    """
    if ":" in action_str:
        name, method = action_str.split(":", 1)
        method = method.lower()

        # Validate method
        valid_methods = ["get", "post", "put", "patch", "delete"]
        if method not in valid_methods:
            raise click.BadParameter(
                f"Invalid HTTP method '{method}' for action '{name}'. "
                f"Must be one of: {', '.join(valid_methods)}"
            )

        return name, method
    else:
        name = action_str
        # Use standard CRUD method or default to GET
        method = STANDARD_CRUD_METHODS.get(name, "get")
        return name, method


def _build_action_spec(name: str, method: str, resource_name: str,
                       resource_singular: str, has_model: bool) -> ActionSpec:
    """
    Build an ActionSpec with smart defaults based on action name and method.

    Args:
        name: Action name (e.g., "list", "create", "activate")
        method: HTTP method (e.g., "get", "post")
        resource_name: PascalCase resource name (e.g., "Product")
        resource_singular: Singular snake_case (e.g., "product")
        has_model: Whether a model exists for this resource

    Returns:
        ActionSpec with appropriate defaults
    """
    # Determine if this is a standard CRUD action
    is_member_action = name in ["show", "update", "delete"]
    is_collection_action = name in ["list", "create"]
    is_standard_crud = is_member_action or is_collection_action

    # Build path (using resource_singular for ID parameter name)
    id_param = f"{{{resource_singular}_id}}"

    if name == "list":
        path = "/"
        requires_resource = False
    elif name == "show":
        path = f"/{id_param}"
        requires_resource = True
    elif name == "create":
        path = "/"
        requires_resource = False
    elif name == "update":
        path = f"/{id_param}"
        requires_resource = True
    elif name == "delete":
        path = f"/{id_param}"
        requires_resource = True
    else:
        # Custom action - if it modifies a specific resource, use /{id}/action
        # Otherwise use /action
        if method in ["put", "patch", "delete"]:
            path = f"/{id_param}/{name}"
            requires_resource = True
        else:
            path = f"/{name}"
            requires_resource = False

    # Build schemas (only if has_model)
    input_schema = None
    output_schema = None

    if has_model:
        if name == "list":
            output_schema = f"List{inflection.pluralize(resource_name)}Response"
        elif name == "show":
            output_schema = resource_name
        elif name == "create":
            input_schema = f"Create{resource_name}Request"
            output_schema = resource_name
        elif name == "update":
            input_schema = f"Update{resource_name}Request"
            output_schema = resource_name
        # delete has no schemas

    # Build description
    if is_standard_crud:
        descriptions = {
            "list": f"List all {inflection.pluralize(resource_singular)}",
            "show": f"Get a single {resource_singular}",
            "create": f"Create a new {resource_singular}",
            "update": f"Update a {resource_singular}",
            "delete": f"Delete a {resource_singular}",
        }
        description = descriptions[name]
    else:
        description = f"{name.title()} action"

    return ActionSpec(
        name=name,
        http_method=method,
        path=path,
        input_schema=input_schema,
        output_schema=output_schema,
        requires_resource=requires_resource,
        description=description,
    )


def _build_crud_actions(resource_name: str, resource_singular: str) -> List[ActionSpec]:
    """
    Build standard REST CRUD actions for a resource.

    Returns list of ActionSpecs for: list, show, create, update, delete
    """
    actions = []
    for action_name in ["list", "show", "create", "update", "delete"]:
        method = STANDARD_CRUD_METHODS.get(action_name, "get")
        spec = _build_action_spec(action_name, method, resource_name,
                                   resource_singular, has_model=True)
        actions.append(spec)
    return actions


# ============================================================================
# Field Type Mapping (for model generation)
# ============================================================================

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


def _get_backend_and_types(backend_override: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Dict[str, Any]]]:
    """
    Get backend name and available field types.

    Args:
        backend_override: Optional backend override from command line

    Returns:
        Tuple of (backend_name, available_types)
    """
    from restmachine.cli.plugin_manager import get_plugin_manager
    from restmachine.cli.config import ProjectConfig

    backend = backend_override

    # If no override, try to load from project config
    if not backend:
        project_root = ProjectConfig.find_project_root()
        if project_root:
            config = ProjectConfig(project_root)
            backend = config.get_backend()

    # Get available types for this backend
    plugin_manager = get_plugin_manager()
    available_types = plugin_manager.get_available_types(backend)

    return backend, available_types


# ============================================================================
# Controller Context Preparation
# ============================================================================

def _path_to_resource_name(path: str) -> str:
    """
    Convert mount path to resource name for class/function naming.

    Examples:
        /health → Health
        /api/v1/metrics → ApiV1Metrics
        /admin/users → AdminUsers
    """
    # Remove leading slash and convert to PascalCase
    clean_path = path.lstrip('/')
    # Replace slashes with underscores, then split and capitalize
    parts = clean_path.replace('/', '_').split('_')
    return ''.join(word.capitalize() for word in parts if word)


def _path_to_file_name(path: str) -> str:
    """
    Convert mount path to file name.

    Examples:
        /health → health
        /api/v1/metrics → api_v1_metrics
        /admin/users → admin_users
    """
    # Remove leading slash and replace remaining slashes with underscores
    clean_path = path.lstrip('/').replace('/', '_')
    return clean_path


def _prepare_controller_context(name: str, actions: Optional[Tuple[str, ...]] = None) -> dict:
    """
    Prepare context for controller generation.

    Interprets the 'name' parameter as either:
    - A model name (e.g., "Product") if it doesn't start with /
    - A mount path (e.g., "/health") if it starts with /

    Args:
        name: Either a model name or a mount path starting with /
        actions: Optional tuple of action specifications

    Returns:
        Dictionary with context for template rendering
    """
    if name.startswith('/'):
        # Path-based controller
        mount_path = name
        resource_name = _path_to_resource_name(name)
        resource_snake = inflection.underscore(resource_name)
        resource_singular = inflection.singularize(resource_snake)
        resource_plural = inflection.pluralize(resource_snake)
        file_name = _path_to_file_name(name)
        has_model = False
        context_type = "path"

    else:
        # Model-based controller
        resource_name = inflection.camelize(name)
        resource_snake = inflection.underscore(resource_name)
        resource_singular = inflection.singularize(resource_snake)
        resource_plural = inflection.pluralize(resource_snake)
        mount_path = f"/{resource_plural}"
        file_name = resource_plural
        context_type = "model"

        # Check if model exists
        model_file = Path(f"models/{resource_snake}.py")
        has_model = model_file.exists()

    # Parse actions
    action_specs: List[ActionSpec] = []
    if actions:
        # User specified actions - parse them
        for action_str in actions:
            action_name, method = _parse_action(action_str)
            spec = _build_action_spec(action_name, method, resource_name,
                                       resource_singular, has_model)
            action_specs.append(spec)
    elif has_model:
        # No actions specified but model exists - full CRUD
        action_specs = _build_crud_actions(resource_name, resource_singular)

    return {
        "type": context_type,
        "mount_path": mount_path,
        "resource_name": resource_name,
        "resource_snake": resource_snake,
        "resource_singular": resource_singular,
        "resource_plural": resource_plural,
        "file_name": file_name,
        "has_model": has_model,
        "actions": action_specs,
        "project_name": Path.cwd().name,
    }


# ============================================================================
# CLI Commands
# ============================================================================

@click.group()
def generate():
    """Generate code scaffolding."""
    pass


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option(
    "--backend",
    default=None,
    help="Override backend for this model (uses project default if not specified)"
)
@click.option(
    "--skip-fixtures",
    is_flag=True,
    help="Skip fixture generation"
)
def model(name: str, fields: tuple[str, ...], backend: Optional[str], skip_fixtures: bool):
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

    # Get backend and available types
    effective_backend, available_types = _get_backend_and_types(backend)

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

        # Validate field type against available types (includes backend-specific types)
        if field_type not in available_types:
            valid_types = list(available_types.keys())
            click.echo(
                click.style(f"Error: Unsupported type '{field_type}'", fg="red"),
                err=True
            )
            click.echo(f"Available types: {', '.join(sorted(valid_types))}", err=True)
            if effective_backend:
                click.echo(f"(Backend: {effective_backend})", err=True)
            raise click.Abort()

        # Backend-specific validation
        if effective_backend:
            from restmachine.cli.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            is_valid, error_msg = plugin_manager.validate_field(effective_backend, field_name, field_type)
            if not is_valid:
                click.echo(
                    click.style(f"Error: {error_msg}", fg="red"),
                    err=True
                )
                raise click.Abort()

        # Get type mapping info
        type_info = available_types[field_type]

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
@click.argument("actions", nargs=-1)
@click.option(
    "--with-schemas",
    is_flag=True,
    help="Generate schema files (only applies if model exists)"
)
@click.option(
    "--skip-tests",
    is_flag=True,
    help="Skip test generation"
)
def controller(name: str, actions: Tuple[str, ...], with_schemas: bool, skip_tests: bool):
    """
    Generate a controller with specified actions.

    NAME can be either:
      - A model name (e.g., "Product", "User")
        → Mounts at pluralized path (/products, /users)
        → Uses REST conventions if model exists

      - A mount path starting with / (e.g., "/health", "/api/v1/metrics")
        → Mounts at exact path specified
        → No model assumptions

    Examples:
        # Model-based (REST conventions)
        restmachine generate controller Product
        restmachine generate controller Product list create

        # Path-based (custom endpoints)
        restmachine generate controller /health check status
        restmachine generate controller /api/v1/metrics collect:post report:get
    """
    if not _is_restmachine_project():
        click.echo(
            click.style("Error: Not in a RestMachine project directory", fg="red"),
            err=True
        )
        click.echo("Run this command from your project root (where app.py exists)", err=True)
        raise click.Abort()

    # Prepare context
    context = _prepare_controller_context(name, actions)

    # Display what we're doing
    click.echo(f"Generating controller: {context['resource_name']}")
    click.echo(f"  Mount path: {context['mount_path']}")
    click.echo(f"  File: routes/{context['file_name']}.py")

    # Warn if model doesn't exist (for model-based controllers)
    if context['type'] == 'model' and not context['has_model']:
        click.echo(click.style(
            f"  ⚠ Warning: Model {context['resource_name']} not found at models/{context['resource_snake']}.py",
            fg="yellow"
        ))
        click.echo("  Generating controller with placeholder CRUD actions")

    # Show actions
    if context['actions']:
        action_names = [f"{a.name}:{a.http_method.upper()}" for a in context['actions']]
        click.echo(f"  Actions: {', '.join(action_names)}")
    else:
        click.echo("  Actions: None (empty controller)")

    # Generate files
    files = _generate_controller_files(
        context,
        skip_schemas=not with_schemas,
        skip_tests=skip_tests
    )

    # Success message
    click.echo()
    for file_path in files:
        click.echo(click.style(f"  ✓ Created {file_path}", fg="green"))
    click.echo(click.style(f"  ✓ Mounted router at {context['mount_path']}", fg="green"))

    # Helpful next steps if model missing
    if context['type'] == 'model' and not context['has_model']:
        click.echo()
        click.echo(click.style("Next steps:", bold=True))
        click.echo(f"  1. Review generated controller at routes/{context['file_name']}.py")
        click.echo("  2. Create the model:")
        click.echo(click.style(
            f"     restmachine generate model {context['resource_name']} <fields>",
            fg="cyan"
        ))
        click.echo(f"     Example: restmachine generate model {context['resource_name']} name:str price:float")
        click.echo("\n  💡 Or use scaffold to create both at once:")
        click.echo(click.style(
            f"     restmachine generate scaffold {context['resource_name']} <fields>",
            fg="cyan"
        ))

    click.echo()
    click.echo(click.style("✓ Controller generated successfully!", fg="green", bold=True))
    click.echo()


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option(
    "--backend",
    default=None,
    help="Override backend for this scaffold (uses project default if not specified)"
)
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
def scaffold(name: str, fields: tuple[str, ...], backend: Optional[str], skip_tests: bool, skip_fixtures: bool):
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

    # Get backend and available types
    effective_backend, available_types = _get_backend_and_types(backend)

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
    uuid_type_info = available_types["uuid"]
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

        # Validate field type against available types (includes backend-specific types)
        if field_type not in available_types:
            valid_types = list(available_types.keys())
            click.echo(
                click.style(f"Error: Unsupported type '{field_type}'", fg="red"),
                err=True
            )
            click.echo(f"Available types: {', '.join(sorted(valid_types))}", err=True)
            if effective_backend:
                click.echo(f"(Backend: {effective_backend})", err=True)
            raise click.Abort()

        # Backend-specific validation
        if effective_backend:
            from restmachine.cli.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            is_valid, error_msg = plugin_manager.validate_field(effective_backend, field_name, field_type)
            if not is_valid:
                click.echo(
                    click.style(f"Error: {error_msg}", fg="red"),
                    err=True
                )
                raise click.Abort()

        # Get type mapping info
        type_info = available_types[field_type]

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

    # 2. Fixture (if not skipped)
    if not skip_fixtures:
        fixture_file = _generate_fixture(context)
        generated_files.append(fixture_file)

    # 3. Update models/__init__.py
    _update_models_init(resource_name, resource_snake)

    # 4. Controller (schemas, routes, tests) - using controller generator
    # Prepare controller context with full CRUD actions
    controller_context = _prepare_controller_context(name, None)
    # Add field information for schema generation
    controller_context['fields'] = parsed_fields
    controller_context['needs_datetime_import'] = needs_datetime_import
    controller_files = _generate_controller_files(
        controller_context,
        skip_schemas=False,  # Scaffold always generates schemas
        skip_tests=skip_tests
    )
    generated_files.extend(str(p) for p in controller_files)

    # Show success
    click.echo()
    for file_path in generated_files:
        click.echo(click.style(f"  ✓ Created {file_path}", fg="green"))

    click.echo(click.style("  ✓ Updated models/__init__.py", fg="green"))
    click.echo(click.style("  ✓ Updated schemas/__init__.py", fg="green"))
    click.echo(click.style(f"  ✓ Mounted router at /{resource_plural}", fg="green"))

    click.echo()
    click.echo(click.style("✓ Scaffold generated successfully!", fg="green", bold=True))
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Review generated files in models/, schemas/, and routes/")
    click.echo(f"  2. Add additional fields to models/{resource_snake}.py if needed")
    if not skip_fixtures:
        click.echo(f"  3. Customize db/fixtures/{resource_plural}.yaml")
    if not skip_tests:
        click.echo(f"  4. Run tests: pytest tests/integration/test_{resource_plural}_api.py")
    click.echo()


def _is_restmachine_project() -> bool:
    """Check if current directory is a RestMachine project."""
    cwd = Path.cwd()
    # Check for app.py and models/ directory
    return (cwd / "app.py").exists() and (cwd / "models").is_dir()


def _get_project_name() -> str:
    """Get project name from current directory."""
    return Path.cwd().name


def _generate_controller_files(context: dict, skip_schemas: bool = False,
                                skip_tests: bool = False) -> List[Path]:
    """
    Generate controller-related files.

    This is the internal API used by both the controller and scaffold commands.

    Args:
        context: Controller context from _prepare_controller_context()
        skip_schemas: If True, don't generate schema files
        skip_tests: If True, don't generate test files

    Returns:
        List of Path objects for created files
    """
    files = []
    env = Environment(
        loader=PackageLoader("restmachine.cli", "templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
    )

    # Add helper for schema tracking in template
    context['generate_schemas'] = not skip_schemas and context['has_model']
    context['schemas_imported'] = []  # Track imported schemas to avoid duplicates

    # 1. Controller/Routes file
    template = env.get_template("generate/controller.py.j2")
    content = template.render(context)

    output_path = Path(f"routes/{context['file_name']}.py")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    files.append(output_path)

    # 2. Schemas file (if has model and not skipped)
    if context['has_model'] and not skip_schemas:
        # Generate placeholder schemas with the standard CRUD schemas
        schema_context = {
            "resource_name": context["resource_name"],
            "resource_snake": context["resource_snake"],
            "resource_singular": context["resource_singular"],
            "resource_plural": context["resource_plural"],
            "resource_name_plural": inflection.camelize(context["resource_plural"]),
            "project_name": context["project_name"],
            "fields": context.get("fields"),  # Include fields if available (from scaffold)
            "needs_datetime_import": context.get("needs_datetime_import", False),
        }

        template = env.get_template("generate/schemas.py.j2")
        content = template.render(schema_context)

        output_path = Path(f"schemas/{context['resource_snake']}_schemas.py")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        files.append(output_path)

        # Update schemas/__init__.py
        _update_schemas_init(
            context["resource_name"],
            context["resource_snake"],
            inflection.camelize(context["resource_plural"])
        )

    # 3. Test file (if not skipped)
    if not skip_tests and context['actions']:
        test_context = {
            "resource_name": context["resource_name"],
            "resource_snake": context["resource_snake"],
            "resource_singular": context["resource_singular"],
            "resource_plural": context["resource_plural"],
            "resource_name_plural": inflection.camelize(context["resource_plural"]),
            "project_name": context["project_name"],
        }

        template = env.get_template("generate/integration_test.py.j2")
        content = template.render(test_context)

        output_path = Path(f"tests/integration/test_{context['file_name']}_api.py")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        files.append(output_path)

    # 4. Auto-mount router in app.py
    _auto_mount_router({
        "resource_plural": context["file_name"],
        "mount_path": context["mount_path"],
    })

    return files


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

    # Determine file name and mount path
    # Support both old format (resource_plural) and new format (file_name + mount_path)
    file_name = context.get('file_name', context.get('resource_plural'))
    mount_path = context.get('mount_path', f"/{context.get('resource_plural')}")

    # Import statement
    import_line = f"from routes.{file_name} import router as {file_name}_router"

    # Mount statement
    mount_line = f"app.mount('{mount_path}', {file_name}_router)"

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

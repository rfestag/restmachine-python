"""
Command to seed the database with fixtures.

Usage:
    restmachine seed
    restmachine seed --environment production
    restmachine seed --path aws/123456/us-east-1 --environment staging
    restmachine seed --dry-run
"""

import sys
from pathlib import Path
from typing import Optional, Any, Dict, Tuple
import click
from restmachine.cli.fixtures import FixtureLoader


@click.command()
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project directory (default: current directory)"
)
@click.option(
    "--environment",
    type=str,
    default=None,
    help="Environment to seed (overrides RESTMACHINE_ENVIRONMENT)"
)
@click.option(
    "--path",
    type=str,
    default=None,
    help="Config path to use (overrides RESTMACHINE_CONFIG_PATH)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be loaded without actually saving to database"
)
@click.option(
    "--fixture",
    "fixtures",
    multiple=True,
    type=str,
    help="Load only specific fixture file(s) (can be specified multiple times)"
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear/truncate tables before seeding"
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed loading information"
)
def seed_command(
    project_dir: Optional[Path],
    environment: Optional[str],
    path: Optional[str],
    dry_run: bool,
    fixtures: Tuple[str, ...],
    clear: bool,
    verbose: bool
):
    """
    Seed the database with fixtures.

    Loads fixture files from db/fixtures/ directory hierarchically,
    based on the config path and environment. Uses the same hierarchical
    pattern as configuration loading.

    The loader will walk the directory tree from root to the most specific
    level, merging fixture records. Records with the same _fixture_id at
    deeper levels will replace those at shallower levels.

    Examples:
        # Use defaults from config/hierarchy.yaml
        restmachine seed

        # Seed specific environment
        restmachine seed --environment production

        # Seed specific path and environment
        restmachine seed --path aws/123456/us-east-1 --environment staging

        # Preview what would be loaded
        restmachine seed --dry-run
    """
    # Determine project directory
    if project_dir is None:
        project_dir = Path.cwd()

    # Validate project structure
    if not _validate_project_structure(project_dir):
        click.echo(click.style("Error: Invalid project structure", fg="red"), err=True)
        click.echo("Expected to find db/fixtures/ directory", err=True)
        raise click.Abort()

    fixtures_dir = project_dir / "db" / "fixtures"
    hierarchy_file = project_dir / "config" / "hierarchy.yaml"

    # Load fixtures
    try:
        loader = FixtureLoader(
            fixtures_dir=fixtures_dir,
            path=path,
            environment=environment,
            hierarchy_file=hierarchy_file if hierarchy_file.exists() else None,
            fixture_filter=list(fixtures) if fixtures else None
        )

        if dry_run:
            _show_dry_run(loader, verbose=verbose, clear=clear)
        else:
            _perform_seed(loader, project_dir, verbose=verbose, clear=clear)

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise click.Abort()


def _validate_project_structure(project_dir: Path) -> bool:
    """
    Validate that the project has the required structure.

    Args:
        project_dir: Project root directory

    Returns:
        True if valid, False otherwise
    """
    fixtures_dir = project_dir / "db" / "fixtures"
    return fixtures_dir.exists()


def _show_dry_run(loader: FixtureLoader, verbose: bool = False, clear: bool = False):
    """
    Display what would be loaded without actually loading.

    Args:
        loader: Configured FixtureLoader instance
        verbose: Show detailed loading information
        clear: Whether tables will be cleared before seeding
    """
    click.echo(click.style("=== DRY RUN ===", fg="yellow", bold=True))
    click.echo()

    if clear:
        click.echo(click.style("⚠ Tables will be cleared/truncated before seeding", fg="yellow"))
        click.echo()

    summary = loader.get_load_summary()

    if verbose:
        click.echo(f"Fixtures directory: {summary['fixtures_dir']}")
        click.echo(f"Path: {summary['path']}")
        click.echo(f"Environment: {summary['environment']}")
        click.echo()

        click.echo("Directories to load (in order):")
        for directory in summary['directories_to_load']:
            click.echo(f"  - {directory}")
        click.echo()

    if not summary['yaml_files']:
        click.echo(click.style("No fixture files found", fg="yellow"))
        return

    # Always show fixture files (more details if verbose)
    click.echo("Fixture files that would be loaded:")
    for file_info in summary['yaml_files']:
        if verbose:
            click.echo(f"  - {file_info['file']} (from {file_info['directory']})")
        else:
            click.echo(f"  - {file_info['file']}")
    click.echo()

    # Load and show record counts
    fixtures = loader.load()

    if not fixtures:
        click.echo(click.style("No fixtures to load", fg="yellow"))
        return

    click.echo("Records that would be created/updated:")
    total_records = 0
    for fixture in fixtures:
        count = len(fixture.records)
        total_records += count
        upsert_info = f" (upsert by {fixture.upsert_key})" if fixture.upsert_key else ""
        click.echo(f"  - {fixture.model}: {count} records{upsert_info}")

    click.echo()
    click.echo(click.style(f"Total: {total_records} records would be processed", fg="cyan", bold=True))


def _perform_seed(loader: FixtureLoader, project_dir: Path, verbose: bool = False, clear: bool = False):
    """
    Actually load and save fixtures to the database.

    Args:
        loader: Configured FixtureLoader instance
        project_dir: Project root directory
        verbose: Show detailed loading information
        clear: Clear/truncate tables before seeding
    """
    if verbose:
        click.echo("Loading fixtures...")

    # Load all fixtures
    fixtures = loader.load()

    if not fixtures:
        click.echo(click.style("No fixtures found", fg="yellow"))
        return

    # Add project to sys.path so we can import models
    sys.path.insert(0, str(project_dir))

    try:
        # Import models module (assuming it exists)
        try:
            import models  # type: ignore[import-not-found]
        except ImportError:
            click.echo(click.style("Warning: Could not import models module", fg="yellow"), err=True)
            click.echo("Make sure your project has a models/ directory with __init__.py", err=True)
            raise click.Abort()

        # Clear tables if requested
        if clear:
            if verbose:
                click.echo("Clearing tables...")
            _clear_tables(fixtures, models, verbose=verbose)

        # Process each fixture
        total_created = 0
        total_updated = 0

        for fixture in fixtures:
            created, updated = _save_fixture_records(fixture, models, verbose=verbose)
            total_created += created
            total_updated += updated

        click.echo()
        click.echo(click.style("✓ Database seeded successfully!", fg="green", bold=True))
        click.echo(f"  Created: {total_created} records")
        click.echo(f"  Updated: {total_updated} records")

    finally:
        # Clean up sys.path
        sys.path.remove(str(project_dir))


def _clear_tables(fixtures, models_module, verbose: bool = False):  # type: ignore[no-untyped-def]
    """
    Clear/truncate tables for all models in fixtures.

    Args:
        fixtures: List of FixtureRecord objects
        models_module: Imported models module
        verbose: Show detailed information
    """
    models_to_clear = set()
    for fixture in fixtures:
        try:
            model_class = getattr(models_module, fixture.model)
            models_to_clear.add((fixture.model, model_class))
        except AttributeError:
            if verbose:
                click.echo(click.style(f"Warning: Model '{fixture.model}' not found", fg="yellow"), err=True)

    for model_name, model_class in models_to_clear:
        try:
            # Try to clear all records using the ORM
            if hasattr(model_class, 'query'):
                query = model_class.query()
                if hasattr(query, 'delete_all'):
                    query.delete_all()
                else:
                    # Fallback: delete records one by one
                    for record in query.all():
                        record.delete()
            if verbose:
                click.echo(f"  Cleared {model_name}")
        except Exception as e:
            if verbose:
                click.echo(click.style(f"Warning: Could not clear {model_name}: {e}", fg="yellow"), err=True)


def _save_fixture_records(fixture, models_module, verbose: bool = False) -> Tuple[int, int]:  # type: ignore[no-untyped-def]
    """
    Save records for a single fixture.

    Args:
        fixture: FixtureRecord object
        models_module: Imported models module
        verbose: Show detailed information

    Returns:
        Tuple of (created_count, updated_count)
    """
    # Get the model class
    try:
        model_class = getattr(models_module, fixture.model)
    except AttributeError:
        click.echo(click.style(f"Warning: Model '{fixture.model}' not found in models module", fg="yellow"), err=True)
        return (0, 0)

    created_count = 0
    updated_count = 0

    for record in fixture.records:
        # Determine upsert strategy
        if fixture.upsert_key:
            # Use upsert_key for get-or-create
            was_created = _upsert_record(model_class, record, fixture.upsert_key)
            if was_created:
                created_count += 1
            else:
                updated_count += 1
        elif 'id' in record:
            # Use id field for upsert
            was_created = _upsert_record(model_class, record, 'id')
            if was_created:
                created_count += 1
            else:
                updated_count += 1
        else:
            # No upsert key, just create
            instance = model_class(**record)
            instance.save()
            created_count += 1

    if verbose:
        click.echo(f"  {fixture.model}: {created_count} created, {updated_count} updated")

    return (created_count, updated_count)


def _upsert_record(model_class, record: Dict[str, Any], upsert_key) -> bool:  # type: ignore[no-untyped-def]
    """
    Get-or-create a record using the upsert key.

    Args:
        model_class: ORM model class
        record: Record data dictionary
        upsert_key: Field or list of fields to use for lookup

    Returns:
        True if created, False if updated
    """
    # Build lookup query
    if isinstance(upsert_key, list):
        # Composite key
        lookup = {key: record[key] for key in upsert_key}
    else:
        # Single key
        lookup = {upsert_key: record[upsert_key]}

    # Try to find existing record
    try:
        query = model_class.query()
        for key, value in lookup.items():
            query = query.filter(**{key: value})

        existing = query.first()

        if existing:
            # Update existing
            for key, value in record.items():
                setattr(existing, key, value)
            existing.save()
            return False
        else:
            # Create new
            instance = model_class(**record)
            instance.save()
            return True

    except AttributeError:
        # Model doesn't have query() method, fall back to simple create
        click.echo(click.style(f"Warning: {model_class.__name__} doesn't support query(), creating new record", fg="yellow"), err=True)
        instance = model_class(**record)
        instance.save()
        return True

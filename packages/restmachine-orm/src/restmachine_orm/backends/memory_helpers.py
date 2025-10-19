"""
Auto-seeding helper functions for InMemoryBackend.

Provides convenient utilities for creating demo backends with automatic
fixture loading capabilities.

Example:
    >>> from restmachine_orm.backends.memory_helpers import create_demo_backend, seed_backend
    >>>
    >>> # Create backend configured for auto-seeding
    >>> backend = create_demo_backend(environment="demo")
    >>>
    >>> # Define models
    >>> class User(Model):
    ...     model_backend: ClassVar = backend
    ...     id: str = Field(primary_key=True)
    ...     email: str
    ...     name: str
    >>>
    >>> # Seed in one line!
    >>> seed_backend(backend, User)
"""

from pathlib import Path
from typing import Union, Optional, Type, TYPE_CHECKING

from restmachine_orm.backends.memory import InMemoryBackend

if TYPE_CHECKING:
    from restmachine_orm.models.base import Model


def create_demo_backend(
    fixtures_dir: Union[str, Path] = "db/fixtures",
    environment: Optional[str] = None,
    path: Optional[str] = None
) -> InMemoryBackend:
    """
    Create an InMemoryBackend configured for auto-seeding.

    This helper creates a backend and stores configuration for later use
    by seed_backend(). It's designed for demo applications and testing
    scenarios where you want to automatically load fixtures on startup.

    The backend will use hierarchical fixture loading, following the same
    pattern as the `restmachine seed` CLI command.

    Args:
        fixtures_dir: Directory containing fixture files (default: "db/fixtures")
        environment: Environment name (e.g., "demo", "test"). If None, uses
                    RESTMACHINE_ENVIRONMENT or defaults from hierarchy.yaml
        path: Config path (e.g., "local", "aws/123456/us-east-1"). If None, uses
              RESTMACHINE_CONFIG_PATH or defaults from hierarchy.yaml

    Returns:
        InMemoryBackend instance with seed configuration attached

    Example:
        >>> backend = create_demo_backend(environment="demo")
        >>>
        >>> class User(Model):
        ...     model_backend: ClassVar = backend
        ...     email: str
        ...     name: str
        >>>
        >>> seed_backend(backend, User)

    Note:
        This is intended for development and demo scenarios. For production
        use cases, use a persistent backend like DynamoDB.
    """
    backend = InMemoryBackend()

    # Store seed configuration on the backend instance
    backend._seed_config = {  # type: ignore[attr-defined]
        "fixtures_dir": Path(fixtures_dir),
        "environment": environment,
        "path": path
    }

    return backend


def seed_backend(backend: InMemoryBackend, *models: Type["Model"]) -> int:
    """
    Seed an InMemoryBackend with fixtures for the given models.

    Loads fixtures from the directory configured in create_demo_backend(),
    using hierarchical loading based on the path and environment.

    Only models passed as arguments will be seeded. This allows you to
    control which fixtures are loaded.

    Args:
        backend: Backend created with create_demo_backend()
        *models: Model classes to seed (only these models will be loaded)

    Returns:
        Total number of records created/updated

    Raises:
        ValueError: If backend was not created with create_demo_backend()

    Example:
        >>> backend = create_demo_backend(environment="demo")
        >>>
        >>> class User(Model):
        ...     model_backend: ClassVar = backend
        ...     id: str
        ...     name: str
        >>>
        >>> class Product(Model):
        ...     model_backend: ClassVar = backend
        ...     id: str
        ...     name: str
        >>>
        >>> # Seed both models
        >>> seed_backend(backend, User, Product)
        5  # Total records loaded

    Note:
        Uses the FixtureLoader from restmachine.cli.fixtures, so it follows
        the same hierarchical loading rules as the CLI seed command.
    """
    # Validate backend has seed config
    if not hasattr(backend, "_seed_config") or backend._seed_config is None:
        raise ValueError(
            "Backend must be created with create_demo_backend() to use seed_backend(). "
            "Regular InMemoryBackend instances do not have seed configuration."
        )

    # Early return if no models provided
    if not models:
        return 0

    seed_config = backend._seed_config
    fixtures_dir = seed_config["fixtures_dir"]

    # Early return if fixtures directory doesn't exist
    if not fixtures_dir.exists():
        return 0

    # Import FixtureLoader (deferred to avoid circular dependency)
    try:
        from restmachine.cli.fixtures import FixtureLoader  # type: ignore[import-not-found]
    except ImportError:
        raise ImportError(
            "Could not import FixtureLoader. Make sure restmachine is installed."
        )

    # Determine hierarchy file location
    # Try to find hierarchy.yaml relative to fixtures_dir
    hierarchy_file = None
    if fixtures_dir.is_absolute():
        # Try fixtures_dir/../../config/hierarchy.yaml (db/fixtures -> config/hierarchy.yaml)
        potential_hierarchy = fixtures_dir.parent.parent / "config" / "hierarchy.yaml"
        if potential_hierarchy.exists():
            hierarchy_file = potential_hierarchy

    # Load fixtures
    loader = FixtureLoader(
        fixtures_dir=fixtures_dir,
        path=seed_config.get("path"),
        environment=seed_config.get("environment"),
        hierarchy_file=hierarchy_file
    )

    fixtures = loader.load()

    # Build model name lookup
    model_by_name = {model.__name__: model for model in models}

    total_records = 0

    # Process each fixture
    for fixture in fixtures:
        # Skip if model not in our list
        if fixture.model not in model_by_name:
            continue

        model_class = model_by_name[fixture.model]

        # Create/update records
        for record in fixture.records:
            # Determine upsert strategy
            if fixture.upsert_key:
                # Use upsert for idempotency
                model_class.upsert(**record)
            elif 'id' in record:
                # Use id for upsert
                model_class.upsert(**record)
            else:
                # No upsert key, just create
                model_class.create(**record)

            total_records += 1

    return total_records

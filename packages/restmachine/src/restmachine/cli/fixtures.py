"""
Hierarchical fixture loading for RestMachine.

Loads fixture files from a directory hierarchy based on config path and environment,
following the same pattern as hierarchical configuration.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import yaml  # type: ignore[import-untyped]


@dataclass
class FixtureRecord:
    """
    Represents a loaded fixture with its model and records.

    Attributes:
        model: The model class name (e.g., "User", "Product")
        upsert_key: Field(s) to use for get-or-create (str or list of str)
        records: List of record dictionaries to create/upsert
    """
    model: str
    records: List[Dict[str, Any]]
    upsert_key: Optional[Union[str, List[str]]] = None


class FixtureLoader:
    """
    Loads fixtures hierarchically from a directory structure.

    Walks the directory tree from root to the specified path + environment,
    loading all YAML fixture files and merging records by _fixture_id.

    Example directory structure:
        fixtures/
            users.yaml              # Root level, always loaded
            local/
                shared.yaml         # Loaded for path="local"
                development/
                    dev.yaml        # Loaded for environment="development"
                production/
                    prod.yaml       # Loaded for environment="production"

    Usage:
        loader = FixtureLoader(
            fixtures_dir="/path/to/db/fixtures",
            path="aws/123456/us-east-1",
            environment="production"
        )
        fixtures = loader.load()

        for fixture in fixtures:
            for record in fixture.records:
                # Save record to database using fixture.model and fixture.upsert_key
                pass
    """

    def __init__(
        self,
        fixtures_dir: Union[str, Path],
        path: Optional[str] = None,
        environment: Optional[str] = None,
        hierarchy_file: Optional[Union[str, Path]] = None,
        fixture_filter: Optional[List[str]] = None
    ):
        """
        Initialize the fixture loader.

        Args:
            fixtures_dir: Root directory containing fixtures
            path: Config path to load (e.g., "aws/123456/us-east-1")
            environment: Environment name (e.g., "production", "development")
            hierarchy_file: Path to hierarchy.yaml for defaults (optional)
            fixture_filter: List of fixture filenames to load (if None, load all)
        """
        self.fixtures_dir = Path(fixtures_dir)
        self.hierarchy_file = Path(hierarchy_file) if hierarchy_file else None
        self.fixture_filter = fixture_filter

        # Priority: constructor args > environment variables > hierarchy.yaml defaults
        # 1. First, load defaults from hierarchy.yaml
        default_path, default_env = self._load_hierarchy_defaults()

        # 2. Apply environment variables (override defaults)
        env_path, env_env = self._get_env_var_values()

        # 3. Constructor args have highest priority
        self._path = path if path is not None else (env_path if env_path is not None else default_path)
        self._environment = environment if environment is not None else (env_env if env_env is not None else default_env)

    def _load_hierarchy_defaults(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Load default path and environment from hierarchy.yaml.

        Returns:
            Tuple of (default_path, default_environment)
        """
        if not self.hierarchy_file or not self.hierarchy_file.exists():
            return ('local', 'development')

        with open(self.hierarchy_file, 'r') as f:
            hierarchy = yaml.safe_load(f)

        default_path = hierarchy.get('default_path', 'local')
        default_environment = hierarchy.get('default_environment', 'development')

        return (default_path, default_environment)

    def _get_env_var_values(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get path and environment from environment variables if set.

        Returns:
            Tuple of (env_path, env_environment) or (None, None) if not set
        """
        env_path = os.environ.get('RESTMACHINE_CONFIG_PATH')
        env_environment = os.environ.get('RESTMACHINE_ENVIRONMENT')

        return (env_path, env_environment)

    def load(self) -> List[FixtureRecord]:
        """
        Load all fixtures from the hierarchy.

        Returns:
            List of FixtureRecord objects with merged records

        Raises:
            ValueError: If fixture files are malformed
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.fixtures_dir.exists():
            return []

        # Build list of directories to load from (root to specific)
        dirs_to_load = self._get_load_order()

        # Load all fixture files from all directories
        all_fixture_data = []
        for directory in dirs_to_load:
            all_fixture_data.extend(self._load_fixtures_from_dir(directory))

        # Merge fixtures by model and _fixture_id
        merged = self._merge_fixtures(all_fixture_data)

        return merged

    def _get_load_order(self) -> List[Path]:
        """
        Get the list of directories to load, in order from root to most specific.

        Returns:
            List of Path objects to load fixtures from
        """
        directories = []

        # 1. Root level (always loaded)
        directories.append(self.fixtures_dir)

        if not self._path:
            # No path specified, just load root + environment
            if self._environment:
                env_dir = self.fixtures_dir / self._environment
                if env_dir.exists():
                    directories.append(env_dir)
            return directories

        # 2. Walk the path hierarchy
        path_parts = self._path.split('/')
        current_path = self.fixtures_dir

        for part in path_parts:
            current_path = current_path / part
            if current_path.exists():
                # Add path-level directory (e.g., fixtures/aws/)
                directories.append(current_path)

        # 3. Add environment-specific directory at the final path level
        if self._environment:
            env_dir = current_path / self._environment
            if env_dir.exists():
                directories.append(env_dir)

        return directories

    def _load_fixtures_from_dir(self, directory: Path) -> List[Dict[str, Any]]:
        """
        Load all YAML fixture files from a single directory (non-recursive).

        Args:
            directory: Directory to load fixtures from

        Returns:
            List of raw fixture data dictionaries
        """
        fixtures = []

        # Only load YAML files in this directory (not subdirectories)
        for yaml_file in directory.glob('*.yaml'):
            # Skip if fixture_filter is set and this file is not in the filter
            if self.fixture_filter and yaml_file.name not in self.fixture_filter:
                continue

            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                # Validate required fields
                if 'model' not in data:
                    raise ValueError(
                        f"{yaml_file}: Fixture file missing required 'model' field"
                    )

                if 'records' not in data:
                    data['records'] = []

                # Store metadata about where this came from
                data['_source_file'] = yaml_file
                data['_source_dir'] = directory

                fixtures.append(data)

            except yaml.YAMLError as e:
                raise Exception(f"Failed to parse {yaml_file}: {e}")

        return fixtures

    def _merge_fixtures(self, all_fixture_data: List[Dict[str, Any]]) -> List[FixtureRecord]:
        """
        Merge fixture data by model, handling _fixture_id-based replacement.

        Args:
            all_fixture_data: All loaded fixture dictionaries

        Returns:
            List of merged FixtureRecord objects
        """
        # Group by model
        by_model: Dict[str, List[Dict[str, Any]]] = {}
        for fixture_data in all_fixture_data:
            model = fixture_data['model']
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(fixture_data)

        # Merge records for each model
        merged_fixtures = []
        for model, fixture_list in by_model.items():
            merged_record = self._merge_model_fixtures(model, fixture_list)
            merged_fixtures.append(merged_record)

        return merged_fixtures

    def _merge_model_fixtures(
        self,
        model: str,
        fixture_list: List[Dict[str, Any]]
    ) -> FixtureRecord:
        """
        Merge all fixtures for a single model.

        Uses _fixture_id to identify records that should replace earlier ones.
        If no _fixture_id is present, all records are kept (additive).

        Args:
            model: The model name
            fixture_list: List of fixture dictionaries for this model

        Returns:
            Single merged FixtureRecord
        """
        # Track records by _fixture_id (if present)
        records_by_id: Dict[str, Dict[str, Any]] = {}
        records_without_id: List[Dict[str, Any]] = []

        # Use the last upsert_key found (most specific level wins)
        upsert_key = None

        for fixture_data in fixture_list:
            # Update upsert_key if present (later definitions override)
            if 'upsert_key' in fixture_data:
                upsert_key = fixture_data['upsert_key']

            for record in fixture_data.get('records', []):
                # Make a copy to avoid modifying original
                record_copy = dict(record)

                # Check for _fixture_id
                fixture_id = record_copy.pop('_fixture_id', None)

                if fixture_id:
                    # Replace any existing record with same _fixture_id
                    records_by_id[fixture_id] = record_copy
                else:
                    # No _fixture_id, just add to list
                    records_without_id.append(record_copy)

        # Combine all records
        all_records = list(records_by_id.values()) + records_without_id

        return FixtureRecord(
            model=model,
            records=all_records,
            upsert_key=upsert_key
        )

    def get_load_summary(self) -> Dict[str, Any]:
        """
        Get a summary of what would be loaded (useful for dry-run).

        Returns:
            Dictionary with loading information
        """
        dirs = self._get_load_order()

        yaml_files: List[Dict[str, str]] = []
        for directory in dirs:
            for yaml_file in directory.glob('*.yaml'):
                # Skip if fixture_filter is set and this file is not in the filter
                if self.fixture_filter and yaml_file.name not in self.fixture_filter:
                    continue

                yaml_files.append({
                    'file': str(yaml_file.relative_to(self.fixtures_dir)),
                    'directory': str(directory.relative_to(self.fixtures_dir))
                })

        summary: Dict[str, Any] = {
            'fixtures_dir': str(self.fixtures_dir),
            'path': self._path,
            'environment': self._environment,
            'directories_to_load': [str(d) for d in dirs],
            'yaml_files': yaml_files
        }

        return summary

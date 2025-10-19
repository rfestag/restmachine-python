"""
Hierarchical configuration management using OmegaConf.

Supports flexible, nested configuration hierarchies where later levels
override earlier levels. At each level, both config.yaml (defaults) and
[environment].yaml (environment-specific overrides) can be defined.

Environment variables:
    RESTMACHINE_CONFIG_PATH: Path through hierarchy (e.g., "aws/123456789012/us-east-1")
    RESTMACHINE_ENVIRONMENT: Environment name (e.g., "production", "staging", "development")

Example structure:
    config/
    ├── base.yaml
    ├── aws/
    │   ├── config.yaml              # AWS defaults (all environments)
    │   ├── production.yaml          # AWS production overrides
    │   └── 123456789012/
    │       ├── config.yaml          # Account defaults
    │       ├── production.yaml      # Account production overrides
    │       └── us-east-1/
    │           ├── config.yaml      # Region defaults
    │           └── production.yaml  # Region production overrides

Loading order for path="aws/123456789012/us-east-1" and environment="production":
    1. base.yaml
    2. aws/config.yaml + aws/production.yaml
    3. aws/123456789012/config.yaml + aws/123456789012/production.yaml
    4. aws/123456789012/us-east-1/config.yaml + aws/123456789012/us-east-1/production.yaml
"""

import os
from pathlib import Path
from typing import Any, Optional, Union

try:
    from omegaconf import OmegaConf, DictConfig  # type: ignore[import-not-found]
except ImportError:
    raise ImportError(
        "OmegaConf is required for hierarchical configuration. "
        "Install it with: pip install omegaconf"
    )


class HierarchicalSettings:
    """
    Hierarchical configuration loader with environment overlays.

    Walks down a directory hierarchy, loading both config.yaml (defaults)
    and [environment].yaml (environment-specific overrides) at each level,
    merging them in order.

    Usage:
        # In your config/settings.py
        from restmachine.config import HierarchicalSettings

        settings = HierarchicalSettings()

        # Access configuration values
        db_host = settings.get("database.host")
        debug_mode = settings.app.debug
    """

    def __init__(self, config_dir: Optional[Union[Path, str]] = None):
        """
        Initialize hierarchical settings.

        Args:
            config_dir: Path to the config directory. If None, looks for a 'config'
                       directory relative to the caller's location.
        """
        if config_dir is None:
            # Try to find config directory relative to caller
            import inspect
            caller_frame = inspect.stack()[1]
            caller_path = Path(caller_frame.filename).parent
            config_dir = caller_path

        self._config_dir = Path(config_dir)
        self._config: Optional[DictConfig] = None

    @property
    def config(self) -> DictConfig:
        """
        Get the full configuration object.

        Lazy-loads configuration on first access.
        """
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key in dot notation (e.g., "database.host")
            default: Default value to return if key doesn't exist

        Returns:
            Configuration value or default

        Example:
            >>> settings.get("database.host", "localhost")
            'localhost'
        """
        value = OmegaConf.select(self.config, key)
        return value if value is not None else default

    def __getattr__(self, name: str) -> Any:
        """
        Allow attribute access to config values.

        Example:
            >>> settings.app.name
            'myapp'
            >>> settings.database.host
            'localhost'
        """
        if name.startswith('_'):
            return super().__getattribute__(name)

        try:
            return OmegaConf.select(self.config, name)
        except Exception:
            raise AttributeError(f"Configuration has no attribute '{name}'")

    def _get_default_path(self) -> str:
        """Get default config path from hierarchy.yaml or fallback."""
        hierarchy_file = self._config_dir / "hierarchy.yaml"

        if hierarchy_file.exists():
            hierarchy = OmegaConf.load(hierarchy_file)
            if isinstance(hierarchy, DictConfig):
                return str(hierarchy.get("default_path", "local"))

        return "local"

    def _get_default_environment(self) -> str:
        """Get default environment from hierarchy.yaml or fallback."""
        hierarchy_file = self._config_dir / "hierarchy.yaml"

        if hierarchy_file.exists():
            hierarchy = OmegaConf.load(hierarchy_file)
            if isinstance(hierarchy, DictConfig):
                return str(hierarchy.get("default_environment", "development"))

        return "development"

    def _load_config(self) -> DictConfig:
        """
        Load and merge all configuration files.

        Walks the hierarchy path, loading config.yaml and [environment].yaml
        at each level, merging in order from least to most specific.

        Returns:
            Merged configuration
        """
        # Start with base config
        base_file = self._config_dir / "base.yaml"
        if base_file.exists():
            config = OmegaConf.load(base_file)
        else:
            config = OmegaConf.create({})

        # Get path and environment
        config_path = os.getenv("RESTMACHINE_CONFIG_PATH", self._get_default_path())
        environment = os.getenv("RESTMACHINE_ENVIRONMENT", self._get_default_environment())

        # Handle empty path (root-level configs only)
        if not config_path or config_path == ".":
            path_parts = []
        else:
            path_parts = config_path.split("/")

        # Walk down the path
        current_path = self._config_dir

        for part in path_parts:
            current_path = current_path / part

            # Load config.yaml (defaults for this level)
            level_config_file = current_path / "config.yaml"
            if level_config_file.exists():
                level_config = OmegaConf.load(level_config_file)
                config = OmegaConf.merge(config, level_config)

            # Load [environment].yaml (environment overrides for this level)
            env_config_file = current_path / f"{environment}.yaml"
            if env_config_file.exists():
                env_config = OmegaConf.load(env_config_file)
                config = OmegaConf.merge(config, env_config)

        # If path is empty, still try to load environment at root
        if not path_parts:
            env_config_file = self._config_dir / f"{environment}.yaml"
            if env_config_file.exists():
                env_config = OmegaConf.load(env_config_file)
                config = OmegaConf.merge(config, env_config)

        # Resolve all interpolations (${var}, ${oc.env:VAR}, etc.)
        OmegaConf.resolve(config)

        # Ensure we return a DictConfig
        if not isinstance(config, DictConfig):
            config = OmegaConf.create({})

        return config

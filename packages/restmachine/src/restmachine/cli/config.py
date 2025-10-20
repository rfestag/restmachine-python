"""
Project configuration management for RestMachine.

Handles reading and writing .restmachine.toml configuration file.
"""

from pathlib import Path
from typing import Optional, Dict, Any


class ProjectConfig:
    """Manages .restmachine.toml configuration file."""

    CONFIG_FILE = ".restmachine.toml"

    def __init__(self, project_dir: Path):
        """
        Initialize project configuration.

        Args:
            project_dir: Path to project root directory
        """
        self.project_dir = project_dir
        self.config_path = project_dir / self.CONFIG_FILE
        self._config: Dict[str, Any] = {}

        if self.config_path.exists():
            self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        try:
            import tomli  # type: ignore[import-not-found]
        except ImportError:
            # Python 3.11+ has tomllib in stdlib
            import tomllib as tomli  # type: ignore[import-not-found]

        with open(self.config_path, "rb") as f:
            self._config = tomli.load(f)

    def save(self) -> None:
        """Save configuration to file."""
        try:
            import tomli_w  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError(
                "tomli-w is required to write configuration. "
                "Install with: pip install tomli-w"
            )

        with open(self.config_path, "wb") as f:
            tomli_w.dump(self._config, f)

    def get_project_name(self) -> Optional[str]:
        """
        Get project name from config.

        Returns:
            Project name or None if not set
        """
        project = self._config.get("project", {})
        if isinstance(project, dict):
            name = project.get("name")
            return str(name) if name is not None else None
        return None

    def set_project_name(self, name: str):
        """
        Set project name in config.

        Args:
            name: Project name
        """
        if "project" not in self._config:
            self._config["project"] = {}
        self._config["project"]["name"] = name

    def get_backend(self) -> Optional[str]:
        """
        Get configured backend name.

        Returns:
            Backend name (e.g., 'memory', 'dynamodb') or None
        """
        project = self._config.get("project", {})
        if isinstance(project, dict):
            backend = project.get("backend")
            return str(backend) if backend is not None else None
        return None

    def set_backend(self, backend: str, backend_config: Optional[Dict[str, Any]] = None):
        """
        Set backend and optional backend-specific config.

        Args:
            backend: Backend name (e.g., 'memory', 'aws', 'postgresql')
            backend_config: Optional backend-specific configuration
        """
        if "project" not in self._config:
            self._config["project"] = {}

        self._config["project"]["backend"] = backend

        if backend_config:
            if "backend" not in self._config:
                self._config["backend"] = {}
            self._config["backend"][backend] = backend_config

    def get_backend_config(self, backend: str) -> Dict[str, Any]:
        """
        Get backend-specific configuration.

        Args:
            backend: Backend name

        Returns:
            Backend configuration dictionary
        """
        backend_section = self._config.get("backend", {})
        if isinstance(backend_section, dict):
            config = backend_section.get(backend, {})
            return dict(config) if isinstance(config, dict) else {}
        return {}

    def get_all_config(self) -> Dict[str, Any]:
        """
        Get entire configuration dictionary.

        Returns:
            Complete configuration
        """
        return self._config.copy()

    @classmethod
    def find_project_root(cls) -> Optional[Path]:
        """
        Find project root by looking for .restmachine.toml or app.py.

        Searches current directory and up to 5 parent directories.

        Returns:
            Path to project root or None if not found
        """
        current = Path.cwd()

        # Check up to 5 levels up
        for _ in range(5):
            # Check for .restmachine.toml first (most reliable)
            if (current / cls.CONFIG_FILE).exists():
                return current

            # Fallback: check for app.py (for older projects without config)
            if (current / "app.py").exists():
                return current

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        return None

    @classmethod
    def create_default(cls, project_dir: Path, project_name: str, backend: str = "memory") -> "ProjectConfig":
        """
        Create a new project configuration with defaults.

        Args:
            project_dir: Path to project directory
            project_name: Name of the project
            backend: Backend to use (default: "memory")

        Returns:
            New ProjectConfig instance
        """
        config = cls(project_dir)
        config.set_project_name(project_name)
        config.set_backend(backend)
        return config

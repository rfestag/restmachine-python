"""Result objects from CLI commands."""

from pathlib import Path
from typing import Optional


class CommandResult:
    """Base result from CLI command."""

    def __init__(self, exit_code: int, output: str, project_dir: Path):
        self.exit_code = exit_code
        self.output = output
        self.project_dir = project_dir
        self.success = exit_code == 0

    def assert_success(self) -> "CommandResult":
        """Chain-able assertion that command succeeded."""
        assert self.exit_code == 0, f"Command failed with exit code {self.exit_code}:\n{self.output}"
        return self


class ScaffoldResult(CommandResult):
    """Result from scaffold generation."""

    def __init__(
        self,
        exit_code: int,
        output: str,
        project_dir: Path,
        resource_snake: str,
        resource_plural: str,
        skip_tests: bool = False,
        skip_fixtures: bool = False,
    ):
        super().__init__(exit_code, output, project_dir)
        self.resource_snake = resource_snake
        self.resource_plural = resource_plural

        # File paths
        self.model_file = project_dir / "models" / f"{resource_snake}.py"
        self.schemas_file = project_dir / "schemas" / f"{resource_snake}_schemas.py"
        self.routes_file = project_dir / "routes" / f"{resource_plural}.py"
        self.test_file = (
            None if skip_tests else project_dir / "tests" / "integration" / f"test_{resource_plural}_api.py"
        )
        self.fixture_file = (
            None if skip_fixtures else project_dir / "db" / "fixtures" / f"{resource_plural}.yaml"
        )


class ModelResult(CommandResult):
    """Result from model generation."""

    def __init__(
        self,
        exit_code: int,
        output: str,
        project_dir: Path,
        resource_snake: str,
        skip_fixtures: bool = False,
    ):
        super().__init__(exit_code, output, project_dir)
        self.resource_snake = resource_snake

        # File paths
        self.model_file = project_dir / "models" / f"{resource_snake}.py"
        self.fixture_file = None if skip_fixtures else project_dir / "db" / "fixtures" / f"{resource_snake}.yaml"

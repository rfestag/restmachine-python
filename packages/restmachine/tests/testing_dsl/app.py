"""RestMachine testing DSL for CLI operations."""

import os
import sys
import importlib
from pathlib import Path
from typing import Optional, Any
from click.testing import CliRunner
import inflection

from .results import CommandResult, ScaffoldResult, ModelResult


class RestMachineApp:
    """Test DSL for RestMachine CLI operations."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.runner = CliRunner()
        self._old_cwd: Optional[str] = None
        self._in_context = False

    def create(self) -> "RestMachineApp":
        """Create basic project structure (app.py, models/, schemas/, etc.)."""
        # Create app.py
        (self.project_dir / "app.py").write_text("""from restmachine import RestMachine

app = RestMachine()

# Routes will be mounted here
""")

        # Create models/
        (self.project_dir / "models").mkdir()
        (self.project_dir / "models" / "__init__.py").write_text("""from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter
backend = InMemoryBackend(InMemoryAdapter())
# Model imports will be added below by scaffold generator
""")

        # Create schemas/
        (self.project_dir / "schemas").mkdir()
        (self.project_dir / "schemas" / "__init__.py").write_text("")

        # Create routes/
        (self.project_dir / "routes").mkdir()
        (self.project_dir / "routes" / "__init__.py").write_text("")

        # Create db/fixtures/
        (self.project_dir / "db").mkdir()
        (self.project_dir / "db" / "fixtures").mkdir()

        # Create tests/integration/
        (self.project_dir / "tests").mkdir()
        (self.project_dir / "tests" / "integration").mkdir()

        return self

    def _enter_context(self) -> None:
        """Enter project context (cd to directory, add to path)."""
        if not self._in_context:
            self._old_cwd = os.getcwd()
            os.chdir(self.project_dir)
            sys.path.insert(0, str(self.project_dir))
            self._in_context = True

    def _exit_context(self) -> None:
        """Exit project context (restore cwd, clean up imports)."""
        if self._in_context and self._old_cwd:
            os.chdir(self._old_cwd)
            if str(self.project_dir) in sys.path:
                sys.path.remove(str(self.project_dir))
            self._in_context = False

    def cleanup(self) -> None:
        """Clean up sys.path, imported modules, and database files."""
        self._exit_context()

        # Clean up all imported modules from project
        modules_to_remove = [
            key for key in sys.modules.keys() if key.startswith(("models", "schemas", "routes"))
        ]
        for module in modules_to_remove:
            del sys.modules[module]

        # Clean up database files (.db, .sqlite, .sqlite3)
        for db_file in self.project_dir.glob("*.db"):
            try:
                db_file.unlink()
            except Exception:
                pass
        for db_file in self.project_dir.glob("*.sqlite"):
            try:
                db_file.unlink()
            except Exception:
                pass
        for db_file in self.project_dir.glob("*.sqlite3"):
            try:
                db_file.unlink()
            except Exception:
                pass

    def _run_command(self, args: list[str]) -> CommandResult:
        """Run CLI command in project directory."""
        from restmachine.cli import main

        old_cwd = os.getcwd()
        try:
            os.chdir(self.project_dir)
            result = self.runner.invoke(main, args)
            return CommandResult(result.exit_code, result.output, self.project_dir)
        finally:
            os.chdir(old_cwd)

    def add_scaffold(
        self,
        name: str,
        fields: Optional[list[str]] = None,
        skip_tests: bool = False,
        skip_fixtures: bool = False,
    ) -> ScaffoldResult:
        """Generate a scaffold and return result object."""
        args = ["generate", "scaffold", name]
        if fields:
            args.extend(fields)
        if skip_tests:
            args.append("--skip-tests")
        if skip_fixtures:
            args.append("--skip-fixtures")

        from restmachine.cli import main

        old_cwd = os.getcwd()
        try:
            os.chdir(self.project_dir)
            result = self.runner.invoke(main, args)

            # Calculate resource names
            resource_snake = inflection.underscore(name)
            resource_plural = inflection.pluralize(resource_snake)

            return ScaffoldResult(
                result.exit_code,
                result.output,
                self.project_dir,
                resource_snake,
                resource_plural,
                skip_tests,
                skip_fixtures,
            )
        finally:
            os.chdir(old_cwd)

    def add_model(
        self, name: str, fields: list[str], skip_fixtures: bool = False
    ) -> ModelResult:
        """Generate a model and return result object."""
        args = ["generate", "model", name]
        args.extend(fields)
        if skip_fixtures:
            args.append("--skip-fixtures")

        from restmachine.cli import main

        old_cwd = os.getcwd()
        try:
            os.chdir(self.project_dir)
            result = self.runner.invoke(main, args)

            resource_snake = inflection.underscore(name)

            return ModelResult(
                result.exit_code, result.output, self.project_dir, resource_snake, skip_fixtures
            )
        finally:
            os.chdir(old_cwd)

    def import_model(self, name: str) -> type:
        """Import and return model class (with automatic context management)."""
        self._enter_context()
        module_name = inflection.underscore(name)
        class_name = inflection.camelize(name)

        module = importlib.import_module(f"models.{module_name}")
        return getattr(module, class_name)

    def import_schema(self, name: str) -> type:
        """Import and return schema class."""
        self._enter_context()
        module_name = inflection.underscore(name)

        module = importlib.import_module(f"schemas.{module_name}_schemas")
        return getattr(module, name)

    def import_router(self, name: str):
        """Import and return router module."""
        self._enter_context()
        resource_plural = inflection.pluralize(inflection.underscore(name))
        return importlib.import_module(f"routes.{resource_plural}")

    def read_file(self, path: str) -> str:
        """Read file content relative to project root."""
        return (self.project_dir / path).read_text()

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return (self.project_dir / path).exists()

    def get_openapi_spec(self) -> dict:
        """Import app and generate OpenAPI spec."""
        import json

        self._enter_context()

        from restmachine import RestApplication
        import importlib

        # Reload app module to get latest changes
        if "app" in sys.modules:
            del sys.modules["app"]

        app_module = importlib.import_module("app")
        app = app_module.app

        if not isinstance(app, RestApplication):
            # If it's RestMachine, we need to get the underlying app
            app = RestApplication()

            # Re-mount all routers
            # This is a simplified version - in real usage we'd track mounted routers
            pass

        spec_json = app.generate_openapi_json()
        return json.loads(spec_json)

    # Assertion Helpers
    def assert_model_has_fields(self, model: type, fields: dict[str, type]) -> None:
        """Assert model has fields with correct types."""
        annotations = model.__annotations__
        for field_name, field_type in fields.items():
            assert (
                field_name in annotations
            ), f"Model {model.__name__} missing field '{field_name}'"
            assert (
                annotations[field_name] == field_type
            ), f"Field '{field_name}' has type {annotations[field_name]}, expected {field_type}"

    def assert_inherits_from(self, cls: type, base: type) -> None:
        """Assert class inherits from base."""
        assert issubclass(cls, base), f"{cls.__name__} does not inherit from {base.__name__}"

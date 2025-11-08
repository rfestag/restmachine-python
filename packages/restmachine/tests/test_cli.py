"""
Tests for RestMachine CLI.
"""

import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from restmachine.cli import main


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test projects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert 'RestMachine' in result.output
    assert 'CLI for REST applications' in result.output


def test_cli_version(runner):
    """Test CLI version command."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0


def test_new_command_help(runner):
    """Test 'new' command help."""
    result = runner.invoke(main, ['new', '--help'])
    assert result.exit_code == 0
    assert 'Create a new RestMachine project' in result.output
    assert '--minimal' in result.output


def test_new_command_creates_project(runner, temp_dir):
    """Test creating a new project."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])

    assert result.exit_code == 0
    assert 'Project created successfully' in result.output

    # Verify directory was created
    assert project_dir.exists()
    assert project_dir.is_dir()

    # Verify core files exist
    assert (project_dir / 'app.py').exists()
    assert (project_dir / 'main.py').exists()
    assert (project_dir / 'lambda_function.py').exists()
    assert (project_dir / 'pyproject.toml').exists()
    assert (project_dir / 'README.md').exists()
    assert (project_dir / 'Dockerfile').exists()
    assert (project_dir / 'docker-compose.yml').exists()
    assert (project_dir / '.gitignore').exists()
    assert (project_dir / '.env.example').exists()


def test_new_command_creates_directory_structure(runner, temp_dir):
    """Test that new command creates proper directory structure."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Verify directories exist
    assert (project_dir / 'models').exists()
    assert (project_dir / 'schemas').exists()
    assert (project_dir / 'routes').exists()
    assert (project_dir / 'config').exists()
    assert (project_dir / 'config' / 'local').exists()
    assert (project_dir / 'db').exists()
    assert (project_dir / 'db' / 'fixtures').exists()
    assert (project_dir / 'tests').exists()
    assert (project_dir / 'tests' / 'unit').exists()
    assert (project_dir / 'tests' / 'unit' / 'models').exists()
    assert (project_dir / 'tests' / 'integration').exists()
    assert (project_dir / 'lib').exists()
    assert (project_dir / 'public').exists()


def test_new_command_creates_config_files(runner, temp_dir):
    """Test that config files are created correctly."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Verify config files (simplified structure)
    assert (project_dir / 'config' / 'settings.py').exists()
    assert (project_dir / 'config' / 'hierarchy.yaml').exists()
    assert (project_dir / 'config' / 'local' / 'development.yaml').exists()

    # Verify removed files don't exist
    assert not (project_dir / 'config' / 'base.yaml').exists()
    assert not (project_dir / 'config' / 'backends.py').exists()
    assert not (project_dir / 'config' / 'dependencies.py').exists()
    assert not (project_dir / 'config' / 'routes.py').exists()

    # Verify config content is templated
    dev_yaml = (project_dir / 'config' / 'local' / 'development.yaml').read_text()
    assert 'myapp' in dev_yaml


def test_new_command_creates_example_files(runner, temp_dir):
    """Test that example files are created (non-minimal mode)."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Verify core files exist (no user examples anymore)
    assert (project_dir / 'lib' / 'dependencies.py').exists()
    assert not (project_dir / 'models' / 'user.py').exists()
    assert not (project_dir / 'schemas' / 'user_schemas.py').exists()
    assert not (project_dir / 'routes' / 'users.py').exists()

    # Verify content is templated
    app_py = (project_dir / 'app.py').read_text()
    assert 'myapp' in app_py


def test_new_command_minimal_mode(runner, temp_dir):
    """Test creating a minimal project."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--minimal', '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Core files should exist
    assert (project_dir / 'app.py').exists()
    assert (project_dir / 'main.py').exists()

    # Example files should NOT exist in minimal mode
    assert not (project_dir / 'models' / 'user.py').exists()
    assert not (project_dir / 'schemas' / 'user_schemas.py').exists()
    assert not (project_dir / 'routes' / 'users.py').exists()

    # Health route should still exist
    assert (project_dir / 'routes' / 'health.py').exists()


def test_new_command_rejects_existing_directory(runner, temp_dir):
    """Test that new command fails if directory exists."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name
    project_dir.mkdir()

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])

    assert result.exit_code != 0
    assert 'already exists' in result.output


def test_new_command_templates_project_name(runner, temp_dir):
    """Test that project name is properly templated throughout files."""
    project_name = 'awesome-api'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Check that project name appears in various files
    files_to_check = [
        'app.py',
        'main.py',
        'config/local/development.yaml',
        'pyproject.toml',
        'README.md',
    ]

    for file_path in files_to_check:
        content = (project_dir / file_path).read_text()
        assert project_name in content, f"{project_name} not found in {file_path}"


def test_new_command_creates_health_route(runner, temp_dir):
    """Test that health check route is always created."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    # Test both minimal and non-minimal
    for minimal in [True, False]:
        # Clean up from previous iteration
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)

        args = ['new', project_name, '--directory', str(temp_dir)]
        if minimal:
            args.append('--minimal')

        result = runner.invoke(main, args)
        assert result.exit_code == 0

        # Health route should exist in both modes
        health_py = project_dir / 'routes' / 'health.py'
        assert health_py.exists()

        content = health_py.read_text()
        assert 'router = Router()' in content
        assert "@router.get('/')" in content
        assert 'health_check' in content


def test_new_command_creates_fixture_directories(runner, temp_dir):
    """Test that new command creates hierarchical fixture directory structure."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Verify fixture directory structure
    fixtures_dir = project_dir / 'db' / 'fixtures'
    assert fixtures_dir.exists()
    assert fixtures_dir.is_dir()

    # Should have local/development structure
    local_dev = fixtures_dir / 'local' / 'development'
    assert local_dev.exists()
    assert local_dev.is_dir()


def test_new_command_creates_seeds_script(runner, temp_dir):
    """Test that seeds.py script is created with fixture loading example."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Verify seeds.py exists
    seeds_py = project_dir / 'db' / 'seeds.py'
    assert seeds_py.exists()

    # Should contain fixture loading code
    content = seeds_py.read_text()
    assert 'FixtureLoader' in content or 'fixtures' in content.lower()
    assert 'def seed' in content


def test_new_command_creates_sample_fixture(runner, temp_dir):
    """Test that a sample fixture file is created."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Check for sample fixture at root level or in local/development
    fixtures_dir = project_dir / 'db' / 'fixtures'

    # Should have at least one sample fixture or .gitkeep files
    has_sample = False
    for yaml_file in fixtures_dir.rglob('*.yaml'):
        has_sample = True
        break

    has_gitkeep = False
    for gitkeep in fixtures_dir.rglob('.gitkeep'):
        has_gitkeep = True
        break

    # Should have either a sample fixture or .gitkeep files
    assert has_sample or has_gitkeep


def test_new_command_default_backend(runner, temp_dir):
    """Test that new command uses sqlite as default backend."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Check .restmachine.toml
    config_file = project_dir / '.restmachine.toml'
    assert config_file.exists()

    content = config_file.read_text()
    assert 'backend = "sqlite"' in content


def test_new_command_custom_backend(runner, temp_dir):
    """Test that new command accepts custom backend."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--backend', 'memory', '--directory', str(temp_dir)])
    assert result.exit_code == 0

    # Check .restmachine.toml
    config_file = project_dir / '.restmachine.toml'
    content = config_file.read_text()
    assert 'backend = "memory"' in content


def test_new_command_creates_restmachine_toml(runner, temp_dir):
    """Test that .restmachine.toml is created."""
    project_name = 'myapp'
    project_dir = temp_dir / project_name

    result = runner.invoke(main, ['new', project_name, '--directory', str(temp_dir)])
    assert result.exit_code == 0

    config_file = project_dir / '.restmachine.toml'
    assert config_file.exists()

    # Verify TOML structure
    content = config_file.read_text()
    assert '[project]' in content
    assert 'name = "myapp"' in content
    assert 'backend = "sqlite"' in content


def test_new_command_invalid_backend(runner, temp_dir):
    """Test that new command rejects invalid backend."""
    project_name = 'myapp'

    result = runner.invoke(main, ['new', project_name, '--backend', 'nonexistent', '--directory', str(temp_dir)])
    assert result.exit_code != 0
    assert 'Unknown backend' in result.output or 'nonexistent' in result.output


def test_new_command_backend_display_name(runner, temp_dir):
    """Test that new command shows backend display name."""
    project_name = 'myapp'

    result = runner.invoke(main, ['new', project_name, '--backend', 'sqlite', '--directory', str(temp_dir)])
    assert result.exit_code == 0
    # Should show human-readable backend name
    assert 'SQLite' in result.output or 'sqlite' in result.output


def test_generate_command_help(runner):
    """Test 'generate' command help."""
    result = runner.invoke(main, ['generate', '--help'])
    assert result.exit_code == 0
    assert 'generate' in result.output.lower()


def test_generate_scaffold_help(runner):
    """Test 'generate scaffold' command help."""
    result = runner.invoke(main, ['generate', 'scaffold', '--help'])
    assert result.exit_code == 0
    assert 'scaffold' in result.output.lower()


def test_generate_model_help(runner):
    """Test 'generate model' command help."""
    result = runner.invoke(main, ['generate', 'model', '--help'])
    assert result.exit_code == 0
    assert 'model' in result.output.lower()


def test_end_to_end_new_and_scaffold_imports(runner, temp_dir):
    """
    End-to-end test: Create a new project, generate a scaffold, and verify it works.

    This test validates the complete workflow:
    1. Create a new project with 'restmachine new'
    2. Generate a scaffold resource with fields
    3. Verify all files are created correctly
    4. Import the generated app and models successfully
    5. Verify the app can be instantiated and models work
    """
    import sys
    import json
    from restmachine.testing import RestMachineDriver, RestApiDsl

    project_name = 'test-blog'
    project_dir = temp_dir / project_name

    # Step 1: Create a new project
    result = runner.invoke(main, [
        'new', project_name,
        '--backend', 'sqlite',
        '--directory', str(temp_dir)
    ])
    assert result.exit_code == 0, f"Project creation failed: {result.output}"
    assert project_dir.exists(), "Project directory was not created"

    # Step 2: Generate a scaffold with fields
    # Note: Schemas are generated as placeholders, which is fine for testing basic CRUD
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(project_dir)
        result = runner.invoke(main, [
            'generate', 'scaffold', 'Post',
            'title:str', 'content:str', 'author:str', 'published:bool'
        ])
        assert result.exit_code == 0, f"Scaffold generation failed: {result.output}"
    finally:
        os.chdir(original_dir)

    # Step 3: Verify all files were created
    assert (project_dir / 'models' / 'post.py').exists(), "Model file not created"
    assert (project_dir / 'routes' / 'posts.py').exists(), "Routes file not created"
    assert (project_dir / 'schemas' / 'post_schemas.py').exists(), "Schemas file not created"
    assert (project_dir / 'db' / 'fixtures' / 'posts.yaml').exists(), "Fixture file not created"
    assert (project_dir / 'tests' / 'integration' / 'test_posts_api.py').exists(), "Test file not created"

    # Step 4: Verify generated code has valid Python syntax
    sys.path.insert(0, str(project_dir))
    try:
        # Import the app module
        import importlib
        app_module = importlib.import_module('app')
        app = app_module.app
        assert app is not None, "App should be created"

        # Import the Post model
        models_module = importlib.import_module('models.post')
        Post = models_module.Post
        assert Post is not None, "Post model should exist"

        # Verify model has the correct fields
        post_fields = Post.model_fields
        assert 'id' in post_fields, "Post should have 'id' field"
        assert 'title' in post_fields, "Post should have 'title' field"
        assert 'content' in post_fields, "Post should have 'content' field"
        assert 'author' in post_fields, "Post should have 'author' field"
        assert 'published' in post_fields, "Post should have 'published' field"

        # Verify the router is mounted
        routes_module = importlib.import_module('routes.posts')
        assert hasattr(routes_module, 'router'), "Routes module should have router"

        # Step 5: Verify app can be used
        # This confirms the backend is initialized and models can be used
        # (We don't test actual HTTP requests since schemas are placeholders)
        assert Post.model_backend is not None, "Model backend should be initialized"

    finally:
        # Clean up sys.path
        if str(project_dir) in sys.path:
            sys.path.remove(str(project_dir))

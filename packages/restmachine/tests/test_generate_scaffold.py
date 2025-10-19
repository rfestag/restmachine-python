"""
Tests for the generate scaffold CLI command.
"""

import pytest
import os
from pathlib import Path
from click.testing import CliRunner
from restmachine.cli import main


@pytest.fixture
def temp_project(tmp_path):
    """Create a minimal RestMachine project structure for testing."""
    # Create basic project structure
    (tmp_path / "app.py").write_text("""
from restmachine import RestMachine

app = RestMachine()

# Routes will be mounted here
""")

    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "__init__.py").write_text("""
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter

backend = InMemoryBackend(InMemoryAdapter())
""")

    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "__init__.py").write_text("")

    (tmp_path / "routes").mkdir()
    (tmp_path / "routes" / "__init__.py").write_text("")

    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "fixtures").mkdir()

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "integration").mkdir()

    return tmp_path


def run_in_dir(directory, runner, args):
    """Helper to run CLI command in a specific directory."""
    old_cwd = os.getcwd()
    try:
        os.chdir(directory)
        return runner.invoke(main, args)
    finally:
        os.chdir(old_cwd)


class TestGenerateScaffold:
    """Test generate scaffold command."""

    def test_scaffold_command_creates_all_files(self, temp_project):
        """Test that scaffold command creates all expected files."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify model file created
        model_file = temp_project / "models" / "product.py"
        assert model_file.exists()
        content = model_file.read_text()
        assert "class Product(Model):" in content
        assert "model_backend: ClassVar = backend" in content
        assert "id: str = Field(primary_key=True)" in content

        # Verify schemas file created
        schemas_file = temp_project / "schemas" / "product_schemas.py"
        assert schemas_file.exists()
        content = schemas_file.read_text()
        assert "class ProductCreate(BaseModel):" in content
        assert "class ProductUpdate(BaseModel):" in content
        assert "class ProductResponse(BaseModel):" in content
        assert "class ProductListResponse(BaseModel):" in content

        # Verify routes file created
        routes_file = temp_project / "routes" / "products.py"
        assert routes_file.exists()
        content = routes_file.read_text()
        assert "router = Router()" in content
        assert "def list_products(" in content
        assert "def get_product(" in content
        assert "def create_product(" in content
        assert "def update_product(" in content
        assert "def delete_product(" in content

        # Verify fixture file created
        fixture_file = temp_project / "db" / "fixtures" / "products.yaml"
        assert fixture_file.exists()
        content = fixture_file.read_text()
        assert "# Example fixture for Product" in content

        # Verify test file created
        test_file = temp_project / "tests" / "integration" / "test_products_api.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "class TestProductCRUD:" in content

    def test_scaffold_command_updates_models_init(self, temp_project):
        """Test that scaffold command updates models/__init__.py."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])

        assert result.exit_code == 0

        # Check models/__init__.py was updated
        init_file = temp_project / "models" / "__init__.py"
        content = init_file.read_text()
        assert "from models.product import Product" in content

    def test_scaffold_command_updates_schemas_init(self, temp_project):
        """Test that scaffold command updates schemas/__init__.py."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])

        assert result.exit_code == 0

        # Check schemas/__init__.py was updated
        init_file = temp_project / "schemas" / "__init__.py"
        content = init_file.read_text()
        assert "from schemas.product_schemas import ProductCreate, ProductUpdate, ProductResponse, ProductListResponse" in content

    def test_scaffold_command_mounts_router_in_app(self, temp_project):
        """Test that scaffold command mounts router in app.py."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])

        assert result.exit_code == 0

        # Check app.py was updated
        app_file = temp_project / "app.py"
        content = app_file.read_text()
        assert "from routes.products import router as products_router" in content
        assert "app.mount('/products', products_router)" in content

    def test_scaffold_with_skip_tests_flag(self, temp_project):
        """Test scaffold command with --skip-tests flag."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product', '--skip-tests'])

        assert result.exit_code == 0

        # Test file should not exist
        test_file = temp_project / "tests" / "integration" / "test_products_api.py"
        assert not test_file.exists()

        # Other files should still exist
        assert (temp_project / "models" / "product.py").exists()
        assert (temp_project / "routes" / "products.py").exists()

    def test_scaffold_with_skip_fixtures_flag(self, temp_project):
        """Test scaffold command with --skip-fixtures flag."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product', '--skip-fixtures'])

        assert result.exit_code == 0

        # Fixture file should not exist
        fixture_file = temp_project / "db" / "fixtures" / "products.yaml"
        assert not fixture_file.exists()

        # Other files should still exist
        assert (temp_project / "models" / "product.py").exists()
        assert (temp_project / "routes" / "products.py").exists()

    def test_scaffold_fails_outside_project(self, tmp_path):
        """Test that scaffold command fails when not in a RestMachine project."""
        runner = CliRunner()
        result = run_in_dir(tmp_path, runner, ['generate', 'scaffold', 'Product'])

        assert result.exit_code != 0
        assert "Not in a RestMachine project" in result.output

    def test_scaffold_handles_camelcase_input(self, temp_project):
        """Test scaffold with CamelCase input."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'BlogPost'])

        assert result.exit_code == 0

        # Files should use snake_case
        assert (temp_project / "models" / "blog_post.py").exists()
        assert (temp_project / "schemas" / "blog_post_schemas.py").exists()
        assert (temp_project / "routes" / "blog_posts.py").exists()

        # Content should use proper naming
        model_file = temp_project / "models" / "blog_post.py"
        content = model_file.read_text()
        assert "class BlogPost(Model):" in content

    def test_scaffold_handles_snake_case_input(self, temp_project):
        """Test scaffold with snake_case input."""
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'blog_post'])

        assert result.exit_code == 0

        # Files should use snake_case
        assert (temp_project / "models" / "blog_post.py").exists()

        # Content should use PascalCase for class
        model_file = temp_project / "models" / "blog_post.py"
        content = model_file.read_text()
        assert "class BlogPost(Model):" in content

    def test_scaffold_pluralization(self, temp_project):
        """Test that scaffold correctly pluralizes resource names."""
        runner = CliRunner()

        test_cases = [
            ('Category', 'categories'),
            ('Status', 'statuses'),
            ('Person', 'people'),
        ]

        for resource, expected_plural in test_cases:
            result = run_in_dir(temp_project, runner, ['generate', 'scaffold', resource])

            assert result.exit_code == 0

            # Routes file should use plural
            routes_file = temp_project / "routes" / f"{expected_plural}.py"
            assert routes_file.exists(), f"Expected {routes_file} for {resource}"

            # Clean up for next iteration
            routes_file.unlink()
            (temp_project / "models" / f"{resource.lower()}.py").unlink(missing_ok=True)


class TestNameHelpers:
    """Test name conversion using inflection library."""

    def test_pluralize_regular_nouns(self):
        """Test pluralization of regular nouns."""
        import inflection

        assert inflection.pluralize('user') == 'users'
        assert inflection.pluralize('product') == 'products'
        assert inflection.pluralize('item') == 'items'

    def test_pluralize_words_ending_in_y(self):
        """Test pluralization of words ending in consonant + y."""
        import inflection

        assert inflection.pluralize('category') == 'categories'
        assert inflection.pluralize('company') == 'companies'

    def test_pluralize_words_ending_in_s_x_z(self):
        """Test pluralization of words ending in s, x, z, ch, sh."""
        import inflection

        assert inflection.pluralize('status') == 'statuses'
        assert inflection.pluralize('box') == 'boxes'
        assert inflection.pluralize('search') == 'searches'

    def test_pluralize_special_cases(self):
        """Test pluralization of special irregular nouns."""
        import inflection

        assert inflection.pluralize('person') == 'people'
        assert inflection.pluralize('child') == 'children'

    def test_to_class_name(self):
        """Test conversion to PascalCase class names."""
        import inflection

        assert inflection.camelize('product') == 'Product'
        assert inflection.camelize('blog_post') == 'BlogPost'
        assert inflection.camelize('BlogPost') == 'BlogPost'

    def test_to_snake_case(self):
        """Test conversion to snake_case."""
        import inflection

        assert inflection.underscore('Product') == 'product'
        assert inflection.underscore('BlogPost') == 'blog_post'
        assert inflection.underscore('blog_post') == 'blog_post'
        assert inflection.underscore('APIKey') == 'api_key'

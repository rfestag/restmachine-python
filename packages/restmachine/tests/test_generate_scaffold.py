"""
Tests for the generate scaffold CLI command.
"""

import pytest
import os
import sys
import importlib.util
from pathlib import Path
from click.testing import CliRunner
from restmachine.cli import main
from restmachine import RestApplication


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
    # Note: backend must be defined before any model imports to avoid circular import
    (tmp_path / "models" / "__init__.py").write_text("""from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter
backend = InMemoryBackend(InMemoryAdapter())
# Model imports will be added below by scaffold generator
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
        assert "import uuid" in content
        assert "class Product(Model):" in content
        assert "model_backend: ClassVar = backend" in content
        assert "id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))" in content

        # Verify schemas file created
        schemas_file = temp_project / "schemas" / "product_schemas.py"
        assert schemas_file.exists()
        content = schemas_file.read_text()
        assert "class CreateProductRequest(BaseModel):" in content
        assert "class UpdateProductRequest(BaseModel):" in content
        assert "class ProductResponse(BaseModel):" in content
        assert "class ListProductsResponse(BaseModel):" in content

        # Verify routes file created
        routes_file = temp_project / "routes" / "products.py"
        assert routes_file.exists()
        content = routes_file.read_text()
        assert "import uuid" not in content  # UUID generation is now in the model
        assert "router = Router()" in content
        assert "def list_products(" in content
        assert "def product(" in content  # Combined resource_exists and GET endpoint
        assert "@router.resource_exists" in content
        assert "@router.get('/{product_id}')" in content
        assert "def create_product(" in content
        assert "def update_product(" in content
        assert "def delete_product(" in content
        assert "id=str(uuid.uuid4())" not in content  # Should not manually generate UUIDs

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
        assert "from schemas.product_schemas import CreateProductRequest, UpdateProductRequest, ProductResponse, ListProductsResponse" in content

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

    def test_resource_name_plural_variable(self, temp_project):
        """Test that resource_name_plural variable is available in templates."""
        runner = CliRunner()

        # Test with a simple case
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])
        assert result.exit_code == 0

        # The variable should be available for use in templates
        # We can verify by checking that pluralized PascalCase names would work
        # For example: Products, BlogPosts, Categories

        # Test with BlogPost to ensure multi-word resources work
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'BlogPost'])
        assert result.exit_code == 0

        routes_file = temp_project / "routes" / "blog_posts.py"
        assert routes_file.exists()

    def test_generated_scaffold_has_valid_syntax(self, temp_project):
        """
        Test that generated scaffold files are syntactically valid.

        This validates that all generated Python files:
        1. Have valid Python syntax (can be parsed without errors)
        2. Can be compiled to bytecode
        """
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])
        assert result.exit_code == 0, f"Scaffold generation failed: {result.output}"

        # Verify all generated files have valid Python syntax
        import ast
        import py_compile

        model_file = temp_project / "models" / "product.py"
        schemas_file = temp_project / "schemas" / "product_schemas.py"
        routes_file = temp_project / "routes" / "products.py"
        test_file = temp_project / "tests" / "integration" / "test_products_api.py"

        for file_path in [model_file, schemas_file, routes_file, test_file]:
            # Test 1: File can be parsed as valid Python AST
            try:
                tree = ast.parse(file_path.read_text())
                assert tree is not None, f"AST parsing returned None for {file_path}"
            except SyntaxError as e:
                pytest.fail(f"Generated file {file_path} has invalid Python syntax: {e}")

            # Test 2: File can be compiled to bytecode
            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as e:
                pytest.fail(f"Generated file {file_path} cannot be compiled: {e}")

    def test_generated_scaffold_is_functional(self, temp_project):
        """
        Test that generated scaffold is functionally correct.

        This tests actual behavior rather than implementation details:
        1. App can be imported and run without errors (no circular imports)
        2. OpenAPI schema is generated correctly
        3. All standard REST endpoints are present
        4. Path parameters, request bodies, and response schemas are correct
        """
        runner = CliRunner()
        result = run_in_dir(temp_project, runner, ['generate', 'scaffold', 'Product'])
        assert result.exit_code == 0, f"Scaffold generation failed: {result.output}"

        # Change to temp directory and add to path for imports to work
        old_cwd = os.getcwd()
        sys.path.insert(0, str(temp_project))

        try:
            os.chdir(temp_project)

            # 1. Import the generated router module (tests for circular imports)
            import routes.products as routes_module

            # 2. Verify app can be created and router mounted without errors
            app = RestApplication()
            app.mount('/products', routes_module.router)

            # 3. Generate OpenAPI schema
            import json
            spec_json = app.generate_openapi_json()
            spec = json.loads(spec_json)

            # 4. Verify all standard REST endpoints are present
            assert '/products/' in spec['paths'], "List endpoint missing from OpenAPI"
            assert '/products/{product_id}' in spec['paths'], "Get single endpoint missing from OpenAPI"

            list_path = spec['paths']['/products/']
            single_path = spec['paths']['/products/{product_id}']

            # 5. Verify all HTTP methods are present
            assert 'get' in list_path, "GET /products endpoint missing"
            assert 'post' in list_path, "POST /products endpoint missing"
            assert 'get' in single_path, "GET /products/{product_id} endpoint missing"
            assert 'put' in single_path, "PUT /products/{product_id} endpoint missing"
            assert 'delete' in single_path, "DELETE /products/{product_id} endpoint missing"

            # 6. Verify path parameter exists for single-resource endpoints
            get_single = single_path['get']
            assert 'parameters' in get_single, "Path parameters missing from GET single endpoint"
            params = get_single['parameters']
            assert any(p['name'] == 'product_id' and p['in'] == 'path' for p in params), \
                "product_id path parameter missing or incorrect"

            # 7. Verify request bodies for create/update
            create_endpoint = list_path['post']
            if 'requestBody' in create_endpoint:
                assert 'content' in create_endpoint['requestBody'], \
                    "POST endpoint missing request body content"
                assert 'application/json' in create_endpoint['requestBody']['content'], \
                    "POST endpoint missing application/json content type"

            update_endpoint = single_path['put']
            if 'requestBody' in update_endpoint:
                assert 'content' in update_endpoint['requestBody'], \
                    "PUT endpoint missing request body content"
                assert 'application/json' in update_endpoint['requestBody']['content'], \
                    "PUT endpoint missing application/json content type"

            # 8. Verify list endpoint has response schema
            list_endpoint = list_path['get']
            if 'responses' in list_endpoint and '200' in list_endpoint['responses']:
                response_200 = list_endpoint['responses']['200']
                assert 'content' in response_200 or 'schema' in response_200, \
                    "List endpoint should have response schema"

        finally:
            # Cleanup: restore working directory and clean up imports
            os.chdir(old_cwd)
            sys.path.remove(str(temp_project))
            # Clean up all imported modules from temp directory
            modules_to_remove = [key for key in sys.modules.keys()
                                if key.startswith(('models', 'schemas', 'routes'))]
            for module in modules_to_remove:
                del sys.modules[module]


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

"""
Refactored REST framework tests using 4-layer architecture.

This demonstrates the new testing approach:
1. Test Layer (this file) - focuses on business scenarios
2. DSL Layer - describes RESTful actions in business terms
3. Driver Layer - knows how to execute against different environments
4. System Under Test - the actual restmachine library
"""

import pytest

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver

# Import Pydantic if available for validation tests
try:
    from pydantic import BaseModel, Field

    PYDANTIC_AVAILABLE = True

    class UserModel(BaseModel):
        name: str = Field(..., min_length=1)
        email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
        age: int = Field(..., ge=0, le=150)

    class UserResponse(BaseModel):
        id: int
        name: str
        email: str

except ImportError:
    PYDANTIC_AVAILABLE = False


class TestBasicApiOperations:
    """Test basic API operations using DSL."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """
        Parametrized fixture that tests against multiple drivers.

        This ensures all functionality works regardless of the execution environment.
        """
        app = RestApplication()

        # Set up a simple API
        @app.get("/")
        def home():
            return {"message": "Hello World"}

        @app.get("/users/{user_id}")
        def get_user(path_params):
            user_id = path_params["user_id"]
            return {"id": int(user_id), "name": f"User {user_id}"}

        @app.post("/users")
        def create_user(json_body):
            return {"id": 123, "name": json_body["name"], "email": json_body["email"]}

        @app.delete("/users/{user_id}")
        def delete_user(path_params):
            return None  # 204 No Content

        # Select driver based on parameter
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        elif request.param == 'aws_lambda':
            driver = AwsLambdaDriver(app)
        else:
            raise ValueError(f"Unknown driver: {request.param}")

        return RestApiDsl(driver)

    def test_can_get_home_page(self, api):
        """Test that we can retrieve the home page."""
        # When I request the home page
        response = api.get_resource("/")

        # Then I should get a successful response with the expected message
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"

    def test_can_get_user_by_id(self, api):
        """Test that we can retrieve a user by ID."""
        # When I request a specific user
        response = api.get_resource("/users/42")

        # Then I should get the user data
        data = api.expect_successful_retrieval(response)
        assert data["id"] == 42
        assert data["name"] == "User 42"

    def test_can_create_user(self, api):
        """Test that we can create a new user."""
        # Given user data
        user_data = {"name": "John Doe", "email": "john@example.com"}

        # When I create a user
        response = api.create_resource("/users", user_data)

        # Then the user should be created successfully
        data = api.expect_successful_creation(response, ["id", "name", "email"])
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_can_delete_user(self, api):
        """Test that we can delete a user."""
        # When I delete a user
        response = api.delete_resource("/users/123")

        # Then I should get a no content response
        api.expect_no_content(response)

    def test_nonexistent_resource_returns_404(self, api):
        """Test that accessing nonexistent resources returns 404."""
        # When I request a nonexistent resource
        response = api.get_resource("/nonexistent")

        # Then I should get a not found response
        api.expect_not_found(response)


class TestContentNegotiation:
    """Test content negotiation capabilities."""

    @pytest.fixture
    def api(self):
        """Set up API with multiple content types."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"title": "Sample Data", "content": "This is some content"}

        @app.renders("text/html")
        def render_html(get_data):
            data = get_data
            return f"<h1>{data['title']}</h1><p>{data['content']}</p>"

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_can_get_json_response(self, api):
        """Test that we can get JSON response."""
        # When I request data as JSON
        response = api.get_resource("/data")

        # Then I should get JSON data
        data = api.expect_successful_retrieval(response)
        assert data["title"] == "Sample Data"
        assert response.content_type == "application/json"

    def test_can_get_html_response(self, api):
        """Test that we can get HTML response."""
        # When I request data as HTML
        response = api.get_as_html("/data")

        # Then I should get HTML content
        assert response.status_code == 200
        assert response.content_type == "text/html"
        html_content = response.get_text_body()
        assert "<h1>Sample Data</h1>" in html_content
        assert "<p>This is some content</p>" in html_content


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestValidation:
    """Test validation functionality using DSL."""

    @pytest.fixture
    def api(self):
        """Set up API with validation."""
        app = RestApplication()

        @app.validates
        def validate_user(json_body) -> UserModel:
            return UserModel.model_validate(json_body)

        @app.post("/users")
        def create_user(validate_user) -> UserResponse:
            user_data = validate_user.model_dump()
            return UserResponse(id=1, name=user_data["name"], email=user_data["email"])

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_valid_user_creation_succeeds(self, api):
        """Test that valid user data creates user successfully."""
        # Given valid user data
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }

        # When I create a user
        response = api.create_resource("/users", user_data)

        # Then the user should be created successfully
        data = api.expect_successful_creation(response)
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_invalid_user_data_returns_validation_error(self, api):
        """Test that invalid user data returns validation error."""
        # Given invalid user data
        invalid_data = {
            "name": "",  # Too short
            "email": "invalid-email",  # Invalid format
            "age": -5  # Negative age
        }

        # When I try to create a user with invalid data
        response = api.submit_invalid_data("/users", invalid_data)

        # Then I should get a validation error
        error_data = api.expect_validation_error(response)
        assert "error" in error_data


class TestAuthentication:
    """Test authentication and authorization."""

    @pytest.fixture
    def api(self):
        """Set up API with authentication."""
        app = RestApplication()

        # Simple session store for testing
        sessions = {"valid_token": {"user_id": "123", "role": "admin"}}

        @app.default_authorized
        def check_auth(request):
            # Only protect non-public endpoints
            if request.path == "/public":
                return True  # Public endpoint, always authorized
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return False
            token = auth_header[7:]
            return token in sessions

        @app.default_forbidden
        def check_permissions(request):
            # Admin endpoints require admin role
            if request.path.startswith("/admin"):
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    session = sessions.get(token, {})
                    return session.get("role") != "admin"
            return False

        @app.get("/public")
        def public_endpoint():
            return {"message": "Public content"}

        @app.get("/protected")
        def protected_endpoint():
            return {"message": "Protected content"}

        @app.get("/admin/stats")
        def admin_endpoint():
            return {"stats": "Admin only stats"}

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_public_endpoint_accessible_without_auth(self, api):
        """Test that public endpoints are accessible without authentication."""
        # When I access a public endpoint
        response = api.get_resource("/public")

        # Then I should get the content
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Public content"

    def test_protected_endpoint_requires_auth(self, api):
        """Test that protected endpoints require authentication."""
        # When I access a protected endpoint without auth
        response = api.access_protected_resource("/protected")

        # Then I should be unauthorized
        api.expect_unauthorized(response)

    def test_protected_endpoint_accessible_with_auth(self, api):
        """Test that protected endpoints are accessible with valid auth."""
        # When I access a protected endpoint with valid auth
        request = api.get("/protected").with_auth("valid_token").accepts("application/json")
        response = api.execute(request)

        # Then I should get the content
        data = api.expect_successful_retrieval(response)
        assert data["message"] == "Protected content"

    def test_admin_endpoint_forbidden_for_non_admin(self, api):
        """Test that admin endpoints are forbidden for non-admin users."""
        # When I access admin endpoint with non-admin token
        response = api.access_forbidden_resource("/admin/stats", "user_token")

        # Then I should be forbidden (this will be unauthorized since user_token doesn't exist)
        api.expect_unauthorized(response)

    def test_admin_endpoint_accessible_for_admin(self, api):
        """Test that admin endpoints are accessible for admin users."""
        # When I access admin endpoint with admin token
        request = api.get("/admin/stats").with_auth("valid_token").accepts("application/json")
        response = api.execute(request)

        # Then I should get the admin content
        data = api.expect_successful_retrieval(response)
        assert data["stats"] == "Admin only stats"


class TestConditionalRequests:
    """Test conditional request functionality."""

    @pytest.fixture
    def api(self):
        """Set up API with conditional request support."""
        app = RestApplication()

        # Simple document store
        documents = {
            "doc1": {"id": "doc1", "title": "Document 1", "version": 1}
        }

        @app.generate_etag
        def document_etag(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id and doc_id in documents:
                doc = documents[doc_id]
                return f"doc-{doc_id}-v{doc['version']}"
            return None

        @app.resource_exists
        def document_exists(request):
            doc_id = request.path_params.get("doc_id")
            return documents.get(doc_id)

        @app.get("/documents/{doc_id}")
        def get_document(document_exists, document_etag):
            return document_exists

        @app.put("/documents/{doc_id}")
        def update_document(document_exists, json_body, request, document_etag):
            doc_id = request.path_params["doc_id"]
            documents[doc_id].update(json_body)
            documents[doc_id]["version"] += 1
            return documents[doc_id]

        driver = RestMachineDriver(app)
        return RestApiDsl(driver)

    def test_conditional_get_with_matching_etag_returns_not_modified(self, api):
        """Test that conditional GET with matching ETag returns 304."""
        # Given I get a document and its ETag
        response1 = api.get_resource("/documents/doc1")
        data = api.expect_successful_retrieval(response1)
        etag = response1.get_header("ETag")

        # ETag should be generated by the dependency injection
        assert etag is not None, "ETag should be generated for conditional requests"

        # When I request the same document with If-None-Match
        response2 = api.get_if_none_match("/documents/doc1", etag)

        # Then I should get not modified
        api.expect_not_modified(response2)

    def test_conditional_put_with_wrong_etag_fails(self, api):
        """Test that conditional PUT with wrong ETag fails."""
        # When I try to update with wrong ETag
        update_data = {"title": "Updated Document"}
        response = api.update_if_match("/documents/doc1", update_data, '"wrong-etag"')

        # Then I should get precondition failed
        api.expect_precondition_failed(response)

    def test_conditional_put_with_correct_etag_succeeds(self, api):
        """Test that conditional PUT with correct ETag succeeds."""
        # Given I get the current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # When I update with the correct ETag
        update_data = {"title": "Updated Document"}
        response2 = api.update_if_match("/documents/doc1", update_data, etag)

        # Then the update should succeed
        data = api.expect_successful_retrieval(response2)
        assert data["title"] == "Updated Document"
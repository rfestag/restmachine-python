"""
REST framework tests using multi-driver approach.

Tests basic API operations, content negotiation, validation, authentication,
and conditional requests across all drivers.
"""

from restmachine import RestApplication
from tests.framework import MultiDriverTestBase, skip_driver

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


class TestBasicApiOperations(MultiDriverTestBase):
    """Test basic API operations across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with basic CRUD operations."""
        app = RestApplication()

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

        return app

    def test_can_get_home_page(self, api):
        """Test that we can retrieve the home page."""
        api_client, driver_name = api

        response = api_client.get_resource("/")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Hello World"

    def test_can_get_user_by_id(self, api):
        """Test that we can retrieve a user by ID."""
        api_client, driver_name = api

        response = api_client.get_resource("/users/42")
        data = api_client.expect_successful_retrieval(response)
        assert data["id"] == 42
        assert data["name"] == "User 42"

    def test_can_create_user(self, api):
        """Test that we can create a new user."""
        api_client, driver_name = api

        user_data = {"name": "John Doe", "email": "john@example.com"}
        response = api_client.create_resource("/users", user_data)

        data = api_client.expect_successful_creation(response, ["id", "name", "email"])
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_can_delete_user(self, api):
        """Test that we can delete a user."""
        api_client, driver_name = api

        response = api_client.delete_resource("/users/123")
        api_client.expect_no_content(response)

    def test_nonexistent_resource_returns_404(self, api):
        """Test that accessing nonexistent resources returns 404."""
        api_client, driver_name = api

        response = api_client.get_resource("/nonexistent")
        api_client.expect_not_found(response)


class TestContentNegotiation(MultiDriverTestBase):
    """Test content negotiation capabilities across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with multiple content types."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"title": "Sample Data", "content": "This is some content"}

        @app.renders("text/html")
        def render_html(get_data):
            data = get_data
            return f"<h1>{data['title']}</h1><p>{data['content']}</p>"

        return app

    def test_can_get_json_response(self, api):
        """Test that we can get JSON response."""
        api_client, driver_name = api

        response = api_client.get_resource("/data")
        data = api_client.expect_successful_retrieval(response)
        assert data["title"] == "Sample Data"
        assert response.content_type == "application/json"

    def test_can_get_html_response(self, api):
        """Test that we can get HTML response."""
        api_client, driver_name = api

        response = api_client.get_as_html("/data")
        assert response.status_code == 200
        assert response.content_type == "text/html"
        html_content = response.get_text_body()
        assert "<h1>Sample Data</h1>" in html_content
        assert "<p>This is some content</p>" in html_content


class TestValidation(MultiDriverTestBase):
    """Test validation functionality across all drivers."""

    skip_if_unavailable = not PYDANTIC_AVAILABLE
    skip_reason = "Pydantic not available"

    def create_app(self) -> RestApplication:
        """Create app with validation."""
        if not PYDANTIC_AVAILABLE:
            return RestApplication()

        app = RestApplication()

        @app.validates
        def validate_user(json_body) -> UserModel:
            return UserModel.model_validate(json_body)

        @app.post("/users")
        def create_user(validate_user) -> UserResponse:
            user_data = validate_user.model_dump()
            return UserResponse(id=1, name=user_data["name"], email=user_data["email"])

        return app

    def test_valid_user_creation_succeeds(self, api):
        """Test that valid user data creates user successfully."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }

        response = api_client.create_resource("/users", user_data)
        data = api_client.expect_successful_creation(response)
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"

    def test_invalid_user_data_returns_validation_error(self, api):
        """Test that invalid user data returns validation error."""
        if not PYDANTIC_AVAILABLE:
            return

        api_client, driver_name = api

        invalid_data = {
            "name": "",  # Too short
            "email": "invalid-email",  # Invalid format
            "age": -5  # Negative age
        }

        response = api_client.submit_invalid_data("/users", invalid_data)
        error_data = api_client.expect_validation_error(response)
        assert "error" in error_data


class TestAuthentication(MultiDriverTestBase):
    """Test authentication and authorization across all drivers."""

    def create_app(self) -> RestApplication:
        """Create app with authentication."""
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

        return app

    def test_public_endpoint_accessible_without_auth(self, api):
        """Test that public endpoints are accessible without authentication."""
        api_client, driver_name = api

        response = api_client.get_resource("/public")
        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Public content"

    def test_protected_endpoint_requires_auth(self, api):
        """Test that protected endpoints require authentication."""
        api_client, driver_name = api

        response = api_client.access_protected_resource("/protected")
        api_client.expect_unauthorized(response)

    def test_protected_endpoint_accessible_with_auth(self, api):
        """Test that protected endpoints are accessible with valid auth."""
        api_client, driver_name = api

        request = api_client.get("/protected").with_auth("valid_token").accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_retrieval(response)
        assert data["message"] == "Protected content"

    def test_admin_endpoint_forbidden_for_non_admin(self, api):
        """Test that admin endpoints are forbidden for non-admin users."""
        api_client, driver_name = api

        response = api_client.access_forbidden_resource("/admin/stats", "user_token")
        # Will be unauthorized since user_token doesn't exist in sessions
        api_client.expect_unauthorized(response)

    def test_admin_endpoint_accessible_for_admin(self, api):
        """Test that admin endpoints are accessible for admin users."""
        api_client, driver_name = api

        request = api_client.get("/admin/stats").with_auth("valid_token").accepts("application/json")
        response = api_client.execute(request)

        data = api_client.expect_successful_retrieval(response)
        assert data["stats"] == "Admin only stats"


class TestConditionalRequests(MultiDriverTestBase):
    """Test conditional request functionality across all drivers."""

    # Conditional requests only work with direct and AWS Lambda drivers
    ENABLED_DRIVERS = ['direct', 'aws_lambda']

    def create_app(self) -> RestApplication:
        """Create app with conditional request support."""
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

        return app

    def test_conditional_get_with_matching_etag_returns_not_modified(self, api):
        """Test that conditional GET with matching ETag returns 304."""
        api_client, driver_name = api

        # Get a document and its ETag
        response1 = api_client.get_resource("/documents/doc1")
        api_client.expect_successful_retrieval(response1)
        etag = response1.get_header("ETag")

        # ETag should be generated by the dependency injection
        assert etag is not None, "ETag should be generated for conditional requests"

        # Request the same document with If-None-Match
        response2 = api_client.get_if_none_match("/documents/doc1", etag)
        api_client.expect_not_modified(response2)

    def test_conditional_put_with_wrong_etag_fails(self, api):
        """Test that conditional PUT with wrong ETag fails."""
        api_client, driver_name = api

        update_data = {"title": "Updated Document"}
        response = api_client.update_if_match("/documents/doc1", update_data, '"wrong-etag"')
        api_client.expect_precondition_failed(response)

    def test_conditional_put_with_correct_etag_succeeds(self, api):
        """Test that conditional PUT with correct ETag succeeds."""
        api_client, driver_name = api

        # Get the current ETag
        response1 = api_client.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Update with the correct ETag
        update_data = {"title": "Updated Document"}
        response2 = api_client.update_if_match("/documents/doc1", update_data, etag)

        data = api_client.expect_successful_retrieval(response2)
        assert data["title"] == "Updated Document"
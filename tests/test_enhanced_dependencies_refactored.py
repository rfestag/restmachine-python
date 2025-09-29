"""
Refactored enhanced dependencies tests using 4-layer architecture.

Tests for advanced dependency injection patterns, Pydantic validation,
and complex validation scenarios.
"""

import pytest
from typing import Optional, List

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True

    # Test models for validation
    class UserCreateRequest(BaseModel):
        name: str = Field(..., min_length=1, max_length=100, description="User's full name")
        email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Valid email address")
        age: Optional[int] = Field(None, ge=0, le=150, description="User's age")
        tags: Optional[List[str]] = Field(None, description="User tags")

    class UserUpdateRequest(BaseModel):
        name: Optional[str] = Field(None, min_length=1, max_length=100)
        email: Optional[str] = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
        age: Optional[int] = Field(None, ge=0, le=150)

    class UserResponse(BaseModel):
        id: int
        name: str
        email: str
        age: Optional[int] = None
        tags: Optional[List[str]] = None

    class SearchQuery(BaseModel):
        q: Optional[str] = Field(None, description="Search query")
        limit: Optional[int] = Field(10, ge=1, le=100, description="Number of results")
        offset: Optional[int] = Field(0, ge=0, description="Offset for pagination")

except ImportError:
    PYDANTIC_AVAILABLE = False

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestPydanticValidation:
    """Test Pydantic model validation in dependency injection."""

    @pytest.fixture
    def api(self):
        """Set up API with Pydantic validation."""
        app = RestApplication()

        # In-memory user store
        users = {}
        next_id = 1

        @app.validates
        def validate_user_create(json_body) -> UserCreateRequest:
            """Validate user creation request."""
            return UserCreateRequest.model_validate(json_body)

        @app.validates
        def validate_user_update(json_body) -> UserUpdateRequest:
            """Validate user update request."""
            return UserUpdateRequest.model_validate(json_body)

        @app.validates
        def validate_search_query(query_params) -> SearchQuery:
            """Validate search query parameters."""
            return SearchQuery.model_validate(query_params or {})

        @app.post("/users")
        def create_user(validate_user_create) -> UserResponse:
            """Create a new user with validation."""
            nonlocal next_id
            user_data = validate_user_create.model_dump()
            user = UserResponse(id=next_id, **user_data)
            users[next_id] = user.model_dump()
            next_id += 1
            return user

        @app.get("/users/{user_id}")
        def get_user(path_params) -> UserResponse:
            """Get a user by ID."""
            user_id = int(path_params["user_id"])
            if user_id not in users:
                from restmachine import Response
                return Response(404, "User not found")
            return UserResponse.model_validate(users[user_id])

        @app.put("/users/{user_id}")
        def update_user(path_params, validate_user_update) -> UserResponse:
            """Update a user with validation."""
            user_id = int(path_params["user_id"])
            if user_id not in users:
                from restmachine import Response
                return Response(404, "User not found")

            # Update only provided fields
            update_data = validate_user_update.model_dump(exclude_unset=True)
            users[user_id].update(update_data)
            return UserResponse.model_validate(users[user_id])

        @app.get("/users")
        def search_users(validate_search_query):
            """Search users with query validation."""
            query = validate_search_query
            # Simple search implementation
            user_list = list(users.values())

            if query.q:
                user_list = [u for u in user_list if query.q.lower() in u["name"].lower()]

            # Apply pagination
            start = query.offset
            end = start + query.limit
            paginated_users = user_list[start:end]

            # Convert to UserResponse and return as JSON-serializable list
            return [UserResponse.model_validate(u).model_dump() for u in paginated_users]

        return RestApiDsl(RestMachineDriver(app))

    def test_valid_user_creation_with_required_fields(self, api):
        """Test creating user with valid required fields."""
        user_data = {
            "name": "John Doe",
            "email": "john@example.com"
        }

        response = api.create_resource("/users", user_data)
        data = api.expect_successful_creation(response)

        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert data["id"] == 1
        assert data["age"] is None

    def test_valid_user_creation_with_all_fields(self, api):
        """Test creating user with all fields."""
        user_data = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "age": 30,
            "tags": ["admin", "developer"]
        }

        response = api.create_resource("/users", user_data)
        data = api.expect_successful_creation(response)

        assert data["name"] == "Jane Smith"
        assert data["email"] == "jane@example.com"
        assert data["age"] == 30
        assert data["tags"] == ["admin", "developer"]

    def test_invalid_user_creation_missing_required_field(self, api):
        """Test validation error for missing required field."""
        user_data = {
            "email": "incomplete@example.com"
            # Missing required 'name' field
        }

        response = api.submit_invalid_data("/users", user_data)
        assert response.status_code in [400, 422]

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_invalid_user_creation_invalid_email(self, api):
        """Test validation error for invalid email format."""
        user_data = {
            "name": "Invalid Email User",
            "email": "not-an-email"
        }

        response = api.submit_invalid_data("/users", user_data)
        assert response.status_code in [400, 422]

        error_data = response.get_json_body()
        assert "error" in error_data

    def test_invalid_user_creation_invalid_age(self, api):
        """Test validation error for invalid age."""
        user_data = {
            "name": "Invalid Age User",
            "email": "user@example.com",
            "age": -5  # Invalid age
        }

        response = api.submit_invalid_data("/users", user_data)
        assert response.status_code in [400, 422]

    def test_invalid_user_creation_name_too_long(self, api):
        """Test validation error for name that's too long."""
        user_data = {
            "name": "A" * 101,  # Exceeds max_length of 100
            "email": "user@example.com"
        }

        response = api.submit_invalid_data("/users", user_data)
        assert response.status_code in [400, 422]

    def test_user_update_partial_fields(self, api):
        """Test updating user with partial field validation."""
        # First create a user
        create_data = {
            "name": "Original Name",
            "email": "original@example.com",
            "age": 25
        }
        create_response = api.create_resource("/users", create_data)
        created_user = api.expect_successful_creation(create_response)
        user_id = created_user["id"]

        # Update only the name
        update_data = {"name": "Updated Name"}
        update_response = api.update_resource(f"/users/{user_id}", update_data)
        updated_user = api.expect_successful_retrieval(update_response)

        assert updated_user["name"] == "Updated Name"
        assert updated_user["email"] == "original@example.com"  # Unchanged
        assert updated_user["age"] == 25  # Unchanged

    def test_user_update_invalid_partial_field(self, api):
        """Test validation error when updating with invalid partial field."""
        # First create a user
        create_data = {
            "name": "Original Name",
            "email": "original@example.com"
        }
        create_response = api.create_resource("/users", create_data)
        created_user = api.expect_successful_creation(create_response)
        user_id = created_user["id"]

        # Try to update with invalid email
        update_data = {"email": "invalid-email"}
        update_response = api.update_resource(f"/users/{user_id}", update_data)
        assert update_response.status_code in [400, 422]

    def test_query_parameter_validation(self, api):
        """Test query parameter validation."""
        # First create some users
        for i in range(5):
            user_data = {
                "name": f"User {i}",
                "email": f"user{i}@example.com"
            }
            api.create_resource("/users", user_data)

        # Test valid search query
        response = api.search_resources("/users", {"q": "User", "limit": "3", "offset": "1"})
        data = api.expect_successful_retrieval(response)

        # Should return users (exact number depends on search implementation)
        assert isinstance(data, list)

    def test_query_parameter_validation_invalid_limit(self, api):
        """Test validation error for invalid query parameter."""
        # Try to search with invalid limit
        response = api.search_resources("/users", {"limit": "1000"})  # Exceeds max limit
        assert response.status_code in [400, 422]


class TestAdvancedDependencyPatterns:
    """Test advanced dependency injection patterns."""

    @pytest.fixture
    def api(self):
        """Set up API with complex dependency patterns."""
        app = RestApplication()

        # Simulated external services
        class UserService:
            def __init__(self):
                self.users = {}
                self.next_id = 1

            def create_user(self, user_data):
                user = {"id": self.next_id, **user_data}
                self.users[self.next_id] = user
                self.next_id += 1
                return user

            def get_user(self, user_id):
                return self.users.get(user_id)

        class AuditService:
            def __init__(self):
                self.logs = []

            def log_action(self, action, user_id, details=None):
                log_entry = {
                    "action": action,
                    "user_id": user_id,
                    "details": details,
                    "timestamp": "2024-01-01T00:00:00Z"  # Fixed for testing
                }
                self.logs.append(log_entry)
                return log_entry

        # Service instances
        user_service = UserService()
        audit_service = AuditService()

        # Validation model for advanced patterns
        class UserDataRequest(BaseModel):
            name: str = Field(..., min_length=2, description="User name")
            email: str = Field(..., description="User email")

        @app.validates
        def validate_user_data(json_body) -> UserDataRequest:
            """Validate user data with custom logic."""
            if not json_body:
                raise ValueError("Request body is required")
            return UserDataRequest.model_validate(json_body)

        @app.post("/users")
        def create_user(validate_user_data):
            """Create user with service logic."""
            user_data = validate_user_data.model_dump()
            user = user_service.create_user(user_data)
            audit_service.log_action("user_created", user["id"], user)
            return user

        @app.get("/users/{user_id}")
        def get_user(path_params):
            """Get user with audit logging."""
            user_id = int(path_params["user_id"])
            user = user_service.get_user(user_id)

            if not user:
                audit_service.log_action("user_not_found", user_id)
                from restmachine import Response
                return Response(404, "User not found")

            audit_service.log_action("user_retrieved", user_id)
            return user

        @app.get("/audit/logs")
        def get_audit_logs():
            """Get audit logs."""
            return {"logs": audit_service.logs}

        return RestApiDsl(RestMachineDriver(app))

    def test_service_dependency_injection(self, api):
        """Test service dependency injection."""
        user_data = {"name": "Service User", "email": "service@example.com"}

        response = api.create_resource("/users", user_data)
        data = api.expect_successful_creation(response)

        assert data["name"] == "Service User"
        assert data["id"] == 1

    def test_chained_service_dependencies(self, api):
        """Test multiple service dependencies in one handler."""
        # Create a user (which uses both user_service and audit_service)
        user_data = {"name": "Chained User", "email": "chained@example.com"}
        create_response = api.create_resource("/users", user_data)
        created_user = api.expect_successful_creation(create_response)
        user_id = created_user["id"]

        # Get the user (which also logs the action)
        get_response = api.get_resource(f"/users/{user_id}")
        retrieved_user = api.expect_successful_retrieval(get_response)

        assert retrieved_user["name"] == "Chained User"

        # Check audit logs
        logs_response = api.get_resource("/audit/logs")
        logs_data = api.expect_successful_retrieval(logs_response)

        assert len(logs_data["logs"]) >= 2
        assert any(log["action"] == "user_created" for log in logs_data["logs"])
        assert any(log["action"] == "user_retrieved" for log in logs_data["logs"])

    def test_validation_dependency_with_custom_error(self, api):
        """Test custom validation dependency with specific error messages."""
        # Test missing name
        invalid_data = {"email": "test@example.com"}
        response = api.submit_invalid_data("/users", invalid_data)
        assert response.status_code in [400, 422]

        # Test name too short
        short_name_data = {"name": "A", "email": "test@example.com"}
        response = api.submit_invalid_data("/users", short_name_data)
        assert response.status_code in [400, 422]

    def test_service_dependency_not_found_scenario(self, api):
        """Test service dependency when resource not found."""
        # Try to get non-existent user
        response = api.get_resource("/users/999")
        api.expect_not_found(response)

        # Check that audit log was created for not found
        logs_response = api.get_resource("/audit/logs")
        logs_data = api.expect_successful_retrieval(logs_response)

        assert any(log["action"] == "user_not_found" and log["user_id"] == 999
                  for log in logs_data["logs"])


class TestComplexValidationScenarios:
    """Test complex validation scenarios."""

    @pytest.fixture
    def api(self):
        """Set up API with complex validation scenarios."""
        app = RestApplication()

        # Validation model for complex scenarios
        class CombinedValidationRequest(BaseModel):
            body_data: dict
            path_id: int
            format: str = "json"

        @app.validates
        def validate_combined_data(json_body, path_params, query_params) -> CombinedValidationRequest:
            """Validate data from multiple sources."""
            errors = []

            # Validate JSON body
            if not json_body or "data" not in json_body:
                errors.append("JSON body must contain 'data' field")

            # Validate path params
            if not path_params or "id" not in path_params:
                errors.append("Path must contain 'id' parameter")
            else:
                try:
                    path_id = int(path_params["id"])
                except ValueError:
                    errors.append("ID must be a valid integer")

            # Validate query params
            format_val = "json"
            if query_params and "format" in query_params:
                if query_params["format"] not in ["json", "xml", "csv"]:
                    errors.append("Format must be one of: json, xml, csv")
                else:
                    format_val = query_params["format"]

            if errors:
                raise ValueError("; ".join(errors))

            return CombinedValidationRequest(
                body_data=json_body,
                path_id=path_id,
                format=format_val
            )

        @app.post("/items/{id}")
        def process_item(validate_combined_data):
            """Process item with combined validation."""
            return {
                "processed": True,
                "data": validate_combined_data.body_data,
                "id": validate_combined_data.path_id,
                "format": validate_combined_data.format
            }

        return RestApiDsl(RestMachineDriver(app))

    def test_combined_validation_success(self, api):
        """Test successful combined validation."""
        data = {"data": {"name": "test item"}}

        request = api.post("/items/123").with_json_body(data).accepts("application/json")
        request.query_params = {"format": "json"}

        response = api.execute(request)
        result = api.expect_successful_creation(response)

        assert result["processed"] is True
        assert result["id"] == 123
        assert result["format"] == "json"
        assert result["data"]["data"]["name"] == "test item"

    def test_combined_validation_invalid_body(self, api):
        """Test validation error from invalid body."""
        data = {"wrong_field": "data"}  # Missing 'data' field

        request = api.post("/items/123").with_json_body(data).accepts("application/json")
        response = api.execute(request)

        assert response.status_code in [400, 422]

    def test_combined_validation_invalid_path_param(self, api):
        """Test validation error from invalid path parameter."""
        data = {"data": {"name": "test item"}}

        request = api.post("/items/not-a-number").with_json_body(data).accepts("application/json")
        response = api.execute(request)

        assert response.status_code in [400, 422]

    def test_combined_validation_invalid_query_param(self, api):
        """Test validation error from invalid query parameter."""
        data = {"data": {"name": "test item"}}

        request = api.post("/items/123").with_json_body(data).accepts("application/json")
        request.query_params = {"format": "invalid_format"}

        response = api.execute(request)
        assert response.status_code in [400, 422]


class TestDependencyInjectionAcrossDrivers:
    """Test that dependency injection works consistently across different drivers."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """Parametrized fixture for testing across drivers."""
        app = RestApplication()

        # Simple validation model for cross-driver testing
        class SimpleDataRequest(BaseModel):
            value: int = Field(..., ge=0, description="Non-negative integer")
            name: Optional[str] = Field(None, description="Optional name")

        @app.validates
        def validate_simple_data(json_body) -> SimpleDataRequest:
            """Simple validation that works across drivers."""
            if not json_body or "value" not in json_body:
                raise ValueError("Body must contain 'value' field")
            return SimpleDataRequest.model_validate(json_body)

        @app.post("/validate")
        def validate_endpoint(validate_simple_data):
            """Endpoint that uses validation dependency."""
            return {"validated": True, "data": validate_simple_data.model_dump()}

        # Select driver
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)

    def test_validation_dependency_across_drivers(self, api):
        """Test that validation works the same across drivers."""
        # Test valid data
        valid_data = {"value": 42, "name": "test"}
        response = api.create_resource("/validate", valid_data)
        data = api.expect_successful_creation(response)

        assert data["validated"] is True
        assert data["data"]["value"] == 42

        # Test invalid data
        invalid_data = {"value": -1}
        response = api.submit_invalid_data("/validate", invalid_data)
        assert response.status_code in [400, 422]

    def test_missing_field_validation_across_drivers(self, api):
        """Test missing field validation across drivers."""
        invalid_data = {"name": "test"}  # Missing 'value' field
        response = api.submit_invalid_data("/validate", invalid_data)
        assert response.status_code in [400, 422]
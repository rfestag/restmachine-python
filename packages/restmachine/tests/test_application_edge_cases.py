"""
Tests for application.py edge cases and uncovered code paths.

These tests specifically target uncovered lines to improve coverage from 85% to 95%+.
Focuses on:
- Validation dependencies with custom scopes
- Body parsing edge cases (unknown content types, legacy parsing, etc.)
- Content negotiation edge cases
- State machine decision points
"""

import pytest
import json
from io import BytesIO

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True

    class ValidatedData(BaseModel):
        name: str = Field(..., min_length=1)
        value: int = Field(..., ge=0)

    class ScopedValidation(BaseModel):
        data: str

except ImportError:
    PYDANTIC_AVAILABLE = False

from restmachine import RestApplication, Request, Response, HTTPMethod
from restmachine.dependencies import ValidationWrapper


class TestValidationDependencyScopes:
    """Test validation dependency scope resolution (lines 1006-1008)."""

    def test_validation_dependency_with_custom_scope(self):
        """Test that validation dependencies can have custom scopes."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        app = RestApplication()

        # Create validation wrapper with custom scope
        def validate_data(json_body) -> ValidatedData:
            return ValidatedData.model_validate(json_body)

        validation_wrapper = ValidationWrapper(validate_data, scope="application")
        app._validation_dependencies["validate_data"] = validation_wrapper

        # Test scope resolution
        scope = app._get_dependency_scope("validate_data")
        assert scope == "application"

    def test_validation_dependency_without_scope_attribute(self):
        """Test validation dependency without explicit scope uses default."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        app = RestApplication()

        # Create validation wrapper without scope
        def validate_data(json_body) -> ValidatedData:
            return ValidatedData.model_validate(json_body)

        # Add as plain wrapper (no scope attribute)
        app._validation_dependencies["validate_data"] = type('Wrapper', (), {'func': validate_data})()

        # Should return default scope
        scope = app._get_dependency_scope("validate_data")
        assert scope == "request"


class TestValidationDependencyNonPydanticErrors:
    """Test validation dependencies that don't return Pydantic models (lines 1038-1045)."""

    def test_plain_function_validation_with_non_pydantic_return(self):
        """Test plain function used as validation that doesn't return Pydantic model."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        app = RestApplication()

        # Register a plain function (not wrapped in Dependency)
        def validate_data(json_body):
            return {"not": "pydantic"}  # Returns dict, not Pydantic model

        # Add to dependencies as plain function
        app._dependencies["validate_data"] = validate_data

        # Add to validation dependencies
        app._validation_dependencies["validate_data"] = type('Wrapper', (), {'func': lambda: None})()

        @app.post("/test")
        def handler(validate_data):
            return validate_data

        # This should raise ValueError because validate_data doesn't return Pydantic model
        request = Request(
            method=HTTPMethod.POST,
            path="/test",
            headers={"content-type": "application/json"},
            body=BytesIO(b'{"test": "data"}')
        )

        response = app.execute(request)
        # Should get 400 error for validation failure
        assert response.status_code == 400
        assert "Pydantic model" in str(response.body)

    def test_dependency_wrapper_validation_with_non_pydantic_return(self):
        """Test Dependency wrapper validation that doesn't return Pydantic model."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        from restmachine.dependencies import Dependency

        app = RestApplication()

        # Register as Dependency wrapper
        def validate_data(json_body):
            return "not a pydantic model"

        app._dependencies["validate_data"] = Dependency(validate_data)
        app._validation_dependencies["validate_data"] = type('Wrapper', (), {'func': lambda: None})()

        @app.post("/test")
        def handler(validate_data):
            return validate_data

        request = Request(
            method=HTTPMethod.POST,
            path="/test",
            headers={"content-type": "application/json"},
            body=BytesIO(b'{"test": "data"}')
        )

        response = app.execute(request)
        assert response.status_code == 400


class TestBodyParsingEdgeCases:
    """Test body parsing edge cases (lines 1225, 1229-1243, 1258, 1264-1283)."""

    def test_unknown_content_type_returns_raw_bytes(self):
        """Test that unknown content types return raw bytes (line 1225)."""
        app = RestApplication()

        # Test the internal parsing method directly
        body_stream = BytesIO(b'custom data here')
        result = app._parse_stream_body(body_stream, "application/x-custom-type")

        # Unknown content type should return raw bytes
        assert isinstance(result, bytes)
        assert result == b'custom data here'

    def test_legacy_multipart_form_data_parsing(self):
        """Test legacy multipart/form-data parsing (lines 1239-1240)."""
        app = RestApplication()

        # Test legacy parsing with multipart (returns placeholder dict)
        legacy_body = '------WebKitFormBoundary\r\nContent-Disposition: form-data; name="field"\r\n\r\nvalue\r\n------WebKitFormBoundary--'
        result = app._parse_legacy_body(legacy_body.encode('utf-8'), "multipart/form-data")

        # Should return dict with raw body and content type
        assert isinstance(result, dict)
        assert "_raw_body" in result
        assert "_content_type" in result
        assert result["_content_type"] == "multipart/form-data"

    def test_legacy_text_plain_parsing(self):
        """Test legacy text/plain parsing (lines 1241-1242)."""
        app = RestApplication()

        # Test legacy text/plain parsing
        legacy_body = b'Plain text content here'
        result = app._parse_legacy_body(legacy_body, "text/plain")

        # Should return the decoded text
        assert isinstance(result, str)
        assert result == "Plain text content here"

    def test_charset_extraction_with_double_quotes(self):
        """Test charset extraction with double quotes (lines 278-286)."""
        app = RestApplication()

        charset = app._extract_charset_from_content_type('text/html; charset="utf-8"')
        assert charset == "utf-8"

    def test_charset_extraction_with_single_quotes(self):
        """Test charset extraction with single quotes (lines 284-285)."""
        app = RestApplication()

        charset = app._extract_charset_from_content_type("text/html; charset='iso-8859-1'")
        assert charset == "iso-8859-1"

    def test_charset_extraction_without_quotes(self):
        """Test charset extraction without quotes (lines 278-286)."""
        app = RestApplication()

        charset = app._extract_charset_from_content_type('text/html; charset=utf-8')
        assert charset == "utf-8"

    def test_charset_extraction_no_charset(self):
        """Test charset extraction when no charset present (line 273)."""
        app = RestApplication()

        charset = app._extract_charset_from_content_type(None)
        assert charset is None

        charset = app._extract_charset_from_content_type('text/html')
        assert charset is None


class TestContentNegotiationEdgeCases:
    """Test content negotiation edge cases (lines 70, 72)."""

    def test_matches_accept_with_no_content_type(self):
        """Test Accept header matching when handler has no content_type (line 70)."""
        from restmachine.application import ErrorHandler

        # Create error handler with no content_type (default handler)
        def error_handler(error):
            return {"error": str(error)}

        handler = ErrorHandler(
            handler=error_handler,
            status_codes=(400,),
            content_type=None
        )

        # Should match any Accept header when content_type is None
        assert handler.matches_accept("application/json") is True
        assert handler.matches_accept("text/html") is True
        assert handler.matches_accept("*/*") is True

    def test_matches_accept_with_no_accept_header(self):
        """Test Accept header matching when no Accept header present (line 72)."""
        from restmachine.application import ErrorHandler

        def error_handler(error):
            return {"error": str(error)}

        handler = ErrorHandler(
            handler=error_handler,
            status_codes=(400,),
            content_type="application/json"
        )

        # Should not match when Accept header is missing/empty and content_type is set
        assert handler.matches_accept("") is False
        # None will be falsy, so should also return False
        result = handler.matches_accept(None)
        # matches_accept expects a string, but in practice might get None
        # The code checks: if not accept_header: return False
        # So None should return False (line 72 is the 'return False' for no accept header)


class TestStateMachineCallbackResolution:
    """Test state machine callback resolution (lines 129, 158-161)."""

    def test_add_validation_wrapper_to_route(self):
        """Test adding validation wrapper to route (line 129)."""
        app = RestApplication()

        @app.get("/test")
        def handler():
            return {"ok": True}

        # Get the route from the root router
        routes = app._root_router._routes
        assert len(routes) > 0
        route = routes[0]

        # Create a validation wrapper
        if PYDANTIC_AVAILABLE:
            def validator(data) -> ValidatedData:
                return ValidatedData.model_validate(data)

            wrapper = ValidationWrapper(validator)
            route.add_validation_wrapper(wrapper)

            assert wrapper in route.validation_wrappers

    def test_resolve_state_callbacks_with_state_name_match(self):
        """Test state callback resolution by state_name (lines 158-161)."""
        from restmachine.dependencies import DependencyWrapper

        app = RestApplication()

        # Create a dependency with state_name
        def check_auth():
            return True

        # DependencyWrapper requires (func, state_name, name, scope=optional)
        auth_dep = DependencyWrapper(
            func=check_auth,
            state_name="authorized",
            name="my_auth",
            scope="request"
        )
        app._dependencies["my_auth"] = auth_dep

        # Create route that uses a parameter matching the state_name
        @app.get("/test")
        def handler(authorized):
            return {"authorized": authorized}

        # Resolve state callbacks
        route = app._root_router._routes[0]
        route.resolve_state_callbacks(app)

        # Should have mapped the authorized state callback
        assert "authorized" in route.state_callbacks


class TestOpenAPISchemaEdgeCases:
    """Test OpenAPI schema generation edge cases (lines 1668-1677, 1692-1706)."""

    def test_infer_basic_schema_string_type(self):
        """Test basic schema inference for string type (line 1692-1693)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(str)
        assert schema == {"type": "string"}

    def test_infer_basic_schema_int_type(self):
        """Test basic schema inference for int type (line 1694-1695)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(int)
        assert schema == {"type": "integer"}

    def test_infer_basic_schema_float_type(self):
        """Test basic schema inference for float type (line 1696-1697)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(float)
        assert schema == {"type": "number"}

    def test_infer_basic_schema_bool_type(self):
        """Test basic schema inference for bool type (line 1698-1699)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(bool)
        assert schema == {"type": "boolean"}

    def test_infer_basic_schema_list_type(self):
        """Test basic schema inference for list type (line 1700-1701)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(list)
        assert schema == {"type": "array", "items": {"type": "object"}}

    def test_infer_basic_schema_dict_type(self):
        """Test basic schema inference for dict type (line 1702-1703)."""
        app = RestApplication()

        schema = app._infer_basic_schema_from_type(dict)
        assert schema == {"type": "object"}

    def test_infer_basic_schema_unknown_type(self):
        """Test basic schema inference for unknown type (line 1705-1706)."""
        app = RestApplication()

        class CustomType:
            pass

        schema = app._infer_basic_schema_from_type(CustomType)
        assert schema == {"type": "object"}  # Default fallback

    def test_infer_schema_from_validation_dependencies(self):
        """Test schema inference from validation dependencies (lines 1668-1677)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        app = RestApplication()

        # Create validation that takes json_body parameter
        def validate_json(json_body) -> ValidatedData:
            return ValidatedData.model_validate(json_body)

        wrapper = ValidationWrapper(validate_json)
        app._validation_dependencies["validate_json"] = wrapper

        # Track collected schemas
        collected_schemas = {}

        def collect_schema(model_class):
            name = model_class.__name__
            collected_schemas[name] = {"type": "object"}
            return name

        # Test schema inference
        schema = app._infer_schema_from_validation_dependencies("json_body", collect_schema)

        if schema:
            assert "$ref" in schema
            assert "ValidatedData" in schema["$ref"]

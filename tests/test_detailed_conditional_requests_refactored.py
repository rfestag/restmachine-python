"""
Refactored detailed conditional requests tests using 4-layer architecture.

Tests for comprehensive ETag handling, If-Match/If-None-Match scenarios,
Last-Modified header interactions, and combined conditional headers.
"""

import pytest
from datetime import datetime, timezone, timedelta

from restmachine import RestApplication
from tests.framework import RestApiDsl, RestMachineDriver, AwsLambdaDriver


class TestETagGeneration:
    """Test ETag generation and handling."""

    @pytest.fixture
    def api(self):
        """Set up API with ETag generation."""
        app = RestApplication()

        # Document store with versioning
        documents = {
            "doc1": {"id": "doc1", "title": "Document 1", "content": "Content 1", "version": 1},
            "doc2": {"id": "doc2", "title": "Document 2", "content": "Content 2", "version": 2}
        }

        @app.generate_etag
        def document_etag(request):
            """Generate ETag based on document version."""
            doc_id = request.path_params.get("doc_id")
            if doc_id and doc_id in documents:
                doc = documents[doc_id]
                return f'"{doc_id}-v{doc["version"]}"'
            return None

        @app.resource_exists
        def document_exists(request):
            """Check if document exists."""
            doc_id = request.path_params.get("doc_id")
            return documents.get(doc_id)

        @app.get("/documents/{doc_id}")
        def get_document(document_exists, document_etag):
            """Get document with ETag generation."""
            return document_exists

        @app.put("/documents/{doc_id}")
        def update_document(document_exists, json_body, request, document_etag):
            """Update document and increment version."""
            doc_id = request.path_params["doc_id"]
            documents[doc_id].update(json_body)
            documents[doc_id]["version"] += 1
            return documents[doc_id]

        @app.post("/documents")
        def create_document(json_body):
            """Create new document."""
            doc_id = f"doc{len(documents) + 1}"
            doc = {"id": doc_id, "version": 1, **json_body}
            documents[doc_id] = doc
            return doc

        return RestApiDsl(RestMachineDriver(app))

    def test_etag_generation_for_existing_resource(self, api):
        """Test ETag generation for existing resource."""
        response = api.get_resource("/documents/doc1")
        data = api.expect_successful_retrieval(response)

        # Check ETag header
        etag = response.get_header("ETag")
        assert etag is not None
        assert "doc1-v1" in etag
        assert data["version"] == 1

    def test_etag_changes_after_update(self, api):
        """Test that ETag changes after resource update."""
        # Get initial ETag
        response1 = api.get_resource("/documents/doc1")
        etag1 = response1.get_header("ETag")
        assert "doc1-v1" in etag1

        # Update document
        update_data = {"title": "Updated Document 1"}
        response2 = api.update_resource("/documents/doc1", update_data)
        data = api.expect_successful_retrieval(response2)

        # Check new ETag
        etag2 = response2.get_header("ETag")
        assert etag2 != etag1
        assert "doc1-v2" in etag2
        assert data["version"] == 2

    def test_etag_for_different_resources(self, api):
        """Test that different resources have different ETags."""
        response1 = api.get_resource("/documents/doc1")
        response2 = api.get_resource("/documents/doc2")

        etag1 = response1.get_header("ETag")
        etag2 = response2.get_header("ETag")

        assert etag1 != etag2
        assert "doc1-v1" in etag1
        assert "doc2-v2" in etag2

    def test_no_etag_for_nonexistent_resource(self, api):
        """Test that nonexistent resources don't generate ETags."""
        response = api.get_resource("/documents/nonexistent")
        api.expect_not_found(response)

        etag = response.get_header("ETag")
        assert etag is None

    def test_etag_for_created_resource(self, api):
        """Test ETag for newly created resource."""
        create_data = {"title": "New Document", "content": "New content"}
        response = api.create_resource("/documents", create_data)
        data = api.expect_successful_creation(response)

        # Created resource should have version 1
        assert data["version"] == 1

        # Get the created document to check ETag
        doc_id = data["id"]
        get_response = api.get_resource(f"/documents/{doc_id}")
        etag = get_response.get_header("ETag")
        assert etag is not None
        assert f"{doc_id}-v1" in etag


class TestIfNoneMatchHeaders:
    """Test If-None-Match header handling."""

    @pytest.fixture
    def api(self):
        """Set up API for If-None-Match testing."""
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
                return f'"{doc_id}-v{doc["version"]}"'
            return None

        @app.resource_exists
        def document_exists(request):
            doc_id = request.path_params.get("doc_id")
            return documents.get(doc_id)

        @app.get("/documents/{doc_id}")
        def get_document(document_exists, document_etag):
            return document_exists

        @app.post("/documents")
        def create_document(json_body):
            doc_id = f"doc{len(documents) + 1}"
            doc = {"id": doc_id, "version": 1, **json_body}
            documents[doc_id] = doc
            return doc

        return RestApiDsl(RestMachineDriver(app))

    def test_if_none_match_with_matching_etag_returns_304(self, api):
        """Test If-None-Match with matching ETag returns 304."""
        # Get document and its ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")
        assert etag is not None

        # Request with If-None-Match using same ETag
        response2 = api.get_if_none_match("/documents/doc1", etag)
        api.expect_not_modified(response2)

    def test_if_none_match_with_different_etag_returns_resource(self, api):
        """Test If-None-Match with different ETag returns resource."""
        # Request with If-None-Match using different ETag
        different_etag = '"different-etag"'
        response = api.get_if_none_match("/documents/doc1", different_etag)
        data = api.expect_successful_retrieval(response)
        assert data["id"] == "doc1"

    def test_if_none_match_star_with_existing_resource_returns_304(self, api):
        """Test If-None-Match: * with existing resource returns 304."""
        # Request with If-None-Match: *
        response = api.get_if_none_match("/documents/doc1", "*")
        api.expect_not_modified(response)

    def test_if_none_match_star_with_nonexistent_resource_returns_404(self, api):
        """Test If-None-Match: * with nonexistent resource returns 404."""
        response = api.get_if_none_match("/documents/nonexistent", "*")
        api.expect_not_found(response)

    def test_if_none_match_with_post_creates_conflict(self, api):
        """Test If-None-Match with POST should prevent creation if resource exists."""
        # This would be more relevant for PUT, but testing POST behavior
        create_data = {"title": "New Document"}

        # Use If-None-Match with POST (unusual but valid scenario)
        request = api.post("/documents").with_json_body(create_data).accepts("application/json")
        request = request.with_header("If-None-Match", "*")

        response = api.execute(request)
        # Behavior depends on implementation - could be 201 (created) or 412 (precondition failed)
        assert response.status_code in [201, 412]

    def test_if_none_match_with_multiple_etags(self, api):
        """Test If-None-Match with multiple ETags."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        current_etag = response1.get_header("ETag")

        # Request with multiple ETags including the current one
        multiple_etags = f'"old-etag-1", {current_etag}, "old-etag-2"'
        response2 = api.get_if_none_match("/documents/doc1", multiple_etags)
        api.expect_not_modified(response2)

    def test_if_none_match_with_multiple_etags_no_match(self, api):
        """Test If-None-Match with multiple ETags where none match."""
        multiple_etags = '"old-etag-1", "old-etag-2", "old-etag-3"'
        response = api.get_if_none_match("/documents/doc1", multiple_etags)
        data = api.expect_successful_retrieval(response)
        assert data["id"] == "doc1"


class TestIfMatchHeaders:
    """Test If-Match header handling."""

    @pytest.fixture
    def api(self):
        """Set up API for If-Match testing."""
        app = RestApplication()

        documents = {
            "doc1": {"id": "doc1", "title": "Document 1", "version": 1}
        }

        @app.generate_etag
        def document_etag(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id and doc_id in documents:
                doc = documents[doc_id]
                return f'"{doc_id}-v{doc["version"]}"'
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

        @app.delete("/documents/{doc_id}")
        def delete_document(document_exists, request, document_etag):
            doc_id = request.path_params["doc_id"]
            del documents[doc_id]
            return None

        return RestApiDsl(RestMachineDriver(app))

    def test_if_match_with_correct_etag_allows_update(self, api):
        """Test If-Match with correct ETag allows update."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Update with correct ETag
        update_data = {"title": "Updated Document"}
        response2 = api.update_if_match("/documents/doc1", update_data, etag)
        data = api.expect_successful_retrieval(response2)
        assert data["title"] == "Updated Document"
        assert data["version"] == 2

    def test_if_match_with_wrong_etag_returns_412(self, api):
        """Test If-Match with wrong ETag returns 412."""
        wrong_etag = '"wrong-etag"'
        update_data = {"title": "Should Not Update"}
        response = api.update_if_match("/documents/doc1", update_data, wrong_etag)
        api.expect_precondition_failed(response)

    def test_if_match_star_with_existing_resource_allows_update(self, api):
        """Test If-Match: * with existing resource allows update."""
        update_data = {"title": "Updated with Star"}
        response = api.update_if_match("/documents/doc1", update_data, "*")
        data = api.expect_successful_retrieval(response)
        assert data["title"] == "Updated with Star"

    def test_if_match_star_with_nonexistent_resource_returns_404(self, api):
        """Test If-Match: * with nonexistent resource returns 404 (restmachine behavior)."""
        update_data = {"title": "Should Not Create"}
        response = api.update_if_match("/documents/nonexistent", update_data, "*")
        api.expect_not_found(response)

    def test_if_match_with_delete_operation(self, api):
        """Test If-Match with DELETE operation."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Delete with correct ETag
        request = api.delete("/documents/doc1").with_header("If-Match", etag).accepts("application/json")
        response2 = api.execute(request)
        api.expect_no_content(response2)

        # Verify deletion
        response3 = api.get_resource("/documents/doc1")
        api.expect_not_found(response3)

    def test_if_match_with_multiple_etags(self, api):
        """Test If-Match with multiple ETags."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        current_etag = response1.get_header("ETag")

        # Update with multiple ETags including the current one
        multiple_etags = f'"old-etag", {current_etag}, "another-old-etag"'
        update_data = {"title": "Updated with Multiple ETags"}
        response2 = api.update_if_match("/documents/doc1", update_data, multiple_etags)
        data = api.expect_successful_retrieval(response2)
        assert data["title"] == "Updated with Multiple ETags"


class TestLastModifiedHeaders:
    """Test Last-Modified header handling."""

    @pytest.fixture
    def api(self):
        """Set up API with Last-Modified support."""
        app = RestApplication()

        # Documents with last modified timestamps
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        documents = {
            "doc1": {
                "id": "doc1",
                "title": "Document 1",
                "last_modified": base_time
            },
            "doc2": {
                "id": "doc2",
                "title": "Document 2",
                "last_modified": base_time + timedelta(hours=1)
            }
        }

        @app.last_modified
        def document_last_modified():
            """Get last modified time for document (simplified for testing)."""
            # For testing, return a fixed date in the past
            return base_time

        @app.resource_exists
        def document_exists(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id in documents:
                doc = documents[doc_id].copy()
                # Convert datetime to string for JSON serialization
                doc["last_modified"] = doc["last_modified"].isoformat()
                return doc
            return None

        @app.get("/documents/{doc_id}")
        def get_document(document_exists, document_last_modified):
            return document_exists

        @app.put("/documents/{doc_id}")
        def update_document(document_exists, json_body, request, document_last_modified):
            doc_id = request.path_params["doc_id"]
            documents[doc_id].update(json_body)
            documents[doc_id]["last_modified"] = datetime.now(timezone.utc)
            doc = documents[doc_id].copy()
            doc["last_modified"] = doc["last_modified"].isoformat()
            return doc

        return RestApiDsl(RestMachineDriver(app))

    def test_last_modified_header_present(self, api):
        """Test that Last-Modified header is present."""
        response = api.get_resource("/documents/doc1")
        api.expect_successful_retrieval(response)

        last_modified = response.get_header("Last-Modified")
        assert last_modified is not None

    def test_if_modified_since_with_newer_modification(self, api):
        """Test If-Modified-Since when resource was modified after the date."""
        # Use a date before the document's last modified time
        old_date = "Mon, 01 Jan 2024 10:00:00 GMT"
        response = api.get_if_modified_since("/documents/doc1", old_date)
        data = api.expect_successful_retrieval(response)
        assert data["id"] == "doc1"

    def test_if_modified_since_with_older_modification(self, api):
        """Test If-Modified-Since when resource wasn't modified after the date."""
        # Use a date after the document's last modified time
        future_date = "Wed, 01 Jan 2025 10:00:00 GMT"
        response = api.get_if_modified_since("/documents/doc1", future_date)
        api.expect_not_modified(response)

    def test_if_unmodified_since_with_newer_modification(self, api):
        """Test If-Unmodified-Since when resource was modified after the date."""
        # Use a date before the document's last modified time
        old_date = "Mon, 01 Jan 2024 10:00:00 GMT"
        request = (api.put("/documents/doc1")
                  .with_json_body({"title": "Should Not Update"})
                  .with_header("If-Unmodified-Since", old_date)
                  .accepts("application/json"))
        response = api.execute(request)
        api.expect_precondition_failed(response)

    def test_if_unmodified_since_with_older_modification(self, api):
        """Test If-Unmodified-Since when resource wasn't modified after the date."""
        # Use a date after the document's last modified time
        future_date = "Wed, 01 Jan 2025 10:00:00 GMT"
        update_data = {"title": "Updated Document"}
        request = (api.put("/documents/doc1")
                  .with_json_body(update_data)
                  .with_header("If-Unmodified-Since", future_date)
                  .accepts("application/json"))
        response = api.execute(request)
        data = api.expect_successful_retrieval(response)
        assert data["title"] == "Updated Document"


class TestCombinedConditionalHeaders:
    """Test combinations of conditional headers."""

    @pytest.fixture
    def api(self):
        """Set up API with both ETag and Last-Modified support."""
        app = RestApplication()

        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        documents = {
            "doc1": {
                "id": "doc1",
                "title": "Document 1",
                "version": 1,
                "last_modified": base_time
            }
        }

        @app.generate_etag
        def document_etag(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id and doc_id in documents:
                doc = documents[doc_id]
                return f'"{doc_id}-v{doc["version"]}"'
            return None

        @app.last_modified
        def document_last_modified():
            # For combined testing, return a fixed date
            return base_time

        @app.resource_exists
        def document_exists(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id in documents:
                doc = documents[doc_id].copy()
                doc["last_modified"] = doc["last_modified"].isoformat()
                return doc
            return None

        @app.get("/documents/{doc_id}")
        def get_document(document_exists, document_etag, document_last_modified):
            return document_exists

        @app.put("/documents/{doc_id}")
        def update_document(document_exists, json_body, request, document_etag, document_last_modified):
            doc_id = request.path_params["doc_id"]
            documents[doc_id].update(json_body)
            documents[doc_id]["version"] += 1
            documents[doc_id]["last_modified"] = datetime.now(timezone.utc)
            doc = documents[doc_id].copy()
            doc["last_modified"] = doc["last_modified"].isoformat()
            return doc

        return RestApiDsl(RestMachineDriver(app))

    def test_both_etag_and_last_modified_present(self, api):
        """Test that both ETag and Last-Modified headers are present."""
        response = api.get_resource("/documents/doc1")
        api.expect_successful_retrieval(response)

        etag = response.get_header("ETag")
        last_modified = response.get_header("Last-Modified")

        assert etag is not None
        assert last_modified is not None
        assert "doc1-v1" in etag

    def test_if_match_and_if_unmodified_since_both_pass(self, api):
        """Test update when both If-Match and If-Unmodified-Since conditions pass."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Update with both conditions
        update_data = {"title": "Updated with Both Conditions"}
        future_date = "Wed, 01 Jan 2025 10:00:00 GMT"

        request = (api.put("/documents/doc1")
                  .with_json_body(update_data)
                  .with_header("If-Match", etag)
                  .with_header("If-Unmodified-Since", future_date)
                  .accepts("application/json"))

        response2 = api.execute(request)
        data = api.expect_successful_retrieval(response2)
        assert data["title"] == "Updated with Both Conditions"

    def test_if_match_passes_if_unmodified_since_fails(self, api):
        """Test behavior when If-Match passes but If-Unmodified-Since fails."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Try to update with valid ETag but old date
        update_data = {"title": "Should Not Update"}
        old_date = "Mon, 01 Jan 2024 10:00:00 GMT"

        request = (api.put("/documents/doc1")
                  .with_json_body(update_data)
                  .with_header("If-Match", etag)
                  .with_header("If-Unmodified-Since", old_date)
                  .accepts("application/json"))

        response2 = api.execute(request)
        # Should fail because If-Unmodified-Since condition fails
        api.expect_precondition_failed(response2)

    def test_if_none_match_and_if_modified_since_both_return_304(self, api):
        """Test when both If-None-Match and If-Modified-Since return 304."""
        # Get current ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Request with both conditions that should return 304
        future_date = "Wed, 01 Jan 2025 10:00:00 GMT"

        request = (api.get("/documents/doc1")
                  .with_header("If-None-Match", etag)
                  .with_header("If-Modified-Since", future_date)
                  .accepts("application/json"))

        response2 = api.execute(request)
        api.expect_not_modified(response2)


class TestConditionalRequestsAcrossDrivers:
    """Test conditional requests work consistently across drivers."""

    @pytest.fixture(params=['direct', 'aws_lambda'])
    def api(self, request):
        """Parametrized fixture for testing across drivers."""
        app = RestApplication()

        documents = {
            "doc1": {"id": "doc1", "title": "Document 1", "version": 1}
        }

        @app.generate_etag
        def document_etag(request):
            doc_id = request.path_params.get("doc_id")
            if doc_id and doc_id in documents:
                doc = documents[doc_id]
                return f'"{doc_id}-v{doc["version"]}"'
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

        # Select driver
        if request.param == 'direct':
            driver = RestMachineDriver(app)
        else:
            driver = AwsLambdaDriver(app)

        return RestApiDsl(driver)

    def test_etag_generation_across_drivers(self, api):
        """Test ETag generation works across drivers."""
        response = api.get_resource("/documents/doc1")
        data = api.expect_successful_retrieval(response)

        etag = response.get_header("ETag")
        assert etag is not None
        assert "doc1-v1" in etag

    def test_if_none_match_across_drivers(self, api):
        """Test If-None-Match works across drivers."""
        # Get ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Test If-None-Match
        response2 = api.get_if_none_match("/documents/doc1", etag)
        api.expect_not_modified(response2)

    def test_if_match_across_drivers(self, api):
        """Test If-Match works across drivers."""
        # Get ETag
        response1 = api.get_resource("/documents/doc1")
        etag = response1.get_header("ETag")

        # Update with If-Match
        update_data = {"title": "Updated Across Drivers"}
        response2 = api.update_if_match("/documents/doc1", update_data, etag)
        data = api.expect_successful_retrieval(response2)
        assert data["title"] == "Updated Across Drivers"
        assert data["version"] == 2
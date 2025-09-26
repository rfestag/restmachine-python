"""
Tests for conditional request headers (ETags, If-Match, If-None-Match, etc.).
Tests the webmachine-style implementation of RFC 7232 conditional requests.
"""

import json
from datetime import datetime, timezone

import pytest

from restmachine import HTTPMethod, Request, Response, RestApplication


class TestETagGeneration:
    """Test ETag generation functionality."""

    def test_response_set_etag_strong(self):
        """Test setting a strong ETag on a response."""
        response = Response(200, "test content")
        response.set_etag("abc123")

        assert response.headers["ETag"] == '"abc123"'
        assert response.etag == "abc123"

    def test_response_set_etag_weak(self):
        """Test setting a weak ETag on a response."""
        response = Response(200, "test content")
        response.set_etag("abc123", weak=True)

        assert response.headers["ETag"] == 'W/"abc123"'
        assert response.etag == "abc123"

    def test_response_generate_etag_from_content(self):
        """Test generating ETag from response content."""
        response = Response(200, "test content")
        response.generate_etag_from_content()

        assert "ETag" in response.headers
        assert response.etag is not None
        # Should generate consistent hash for same content
        response2 = Response(200, "test content")
        response2.generate_etag_from_content()
        assert response.etag == response2.etag

    def test_response_set_last_modified(self):
        """Test setting Last-Modified header."""
        response = Response(200, "test content")
        test_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        response.set_last_modified(test_time)

        assert response.headers["Last-Modified"] == "Mon, 01 Jan 2024 12:00:00 GMT"
        assert response.last_modified == test_time


class TestRequestHeaderParsing:
    """Test parsing of conditional request headers."""

    def test_parse_if_match_single(self):
        """Test parsing single ETag in If-Match header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-Match": '"abc123"'}
        )

        etags = request.get_if_match()
        assert etags == ['"abc123"']

    def test_parse_if_match_multiple(self):
        """Test parsing multiple ETags in If-Match header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-Match": '"abc123", "def456", W/"weak789"'}
        )

        etags = request.get_if_match()
        assert etags == ['"abc123"', '"def456"', 'W/"weak789"']

    def test_parse_if_match_star(self):
        """Test parsing If-Match: * header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-Match": "*"}
        )

        etags = request.get_if_match()
        assert etags == ["*"]

    def test_parse_if_none_match_single(self):
        """Test parsing single ETag in If-None-Match header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-None-Match": '"abc123"'}
        )

        etags = request.get_if_none_match()
        assert etags == ['"abc123"']

    def test_parse_if_modified_since(self):
        """Test parsing If-Modified-Since header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT"}
        )

        date = request.get_if_modified_since()
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 1

    def test_parse_if_unmodified_since(self):
        """Test parsing If-Unmodified-Since header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={"If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT"}
        )

        date = request.get_if_unmodified_since()
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 1


class TestIfMatchPrecondition:
    """Test If-Match precondition processing."""

    def test_if_match_success_with_matching_etag(self):
        """Test successful If-Match with matching ETag."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Match": '"abc123"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_match_failure_with_non_matching_etag(self):
        """Test If-Match failure with non-matching ETag."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Match": '"different"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 412
        assert "Precondition Failed" in response.body

    def test_if_match_success_with_star(self):
        """Test If-Match: * succeeds when resource exists."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Match": "*",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_match_failure_when_no_etag(self):
        """Test If-Match failure when resource has no ETag."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Match": '"abc123"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 412
        assert "Precondition Failed" in response.body


class TestIfNoneMatchPrecondition:
    """Test If-None-Match precondition processing."""

    def test_if_none_match_success_with_non_matching_etag(self):
        """Test If-None-Match success with non-matching ETag."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-None-Match": '"different"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_none_match_304_with_matching_etag_get(self):
        """Test If-None-Match returns 304 for GET with matching ETag."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-None-Match": '"abc123"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 304
        assert response.headers.get("ETag") == '"abc123"'

    def test_if_none_match_412_with_matching_etag_post(self):
        """Test If-None-Match returns 412 for POST with matching ETag."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.post("/resource")
        def create_resource(get_etag):
            return {"id": 2, "data": "created"}

        request = Request(
            method=HTTPMethod.POST,
            path="/resource",
            headers={
                "If-None-Match": '"abc123"',
                "Accept": "application/json"
            },
            body='{"data": "test"}'
        )

        response = app.execute(request)
        assert response.status_code == 412
        assert "Precondition Failed" in response.body

    def test_if_none_match_star_304_for_existing_resource(self):
        """Test If-None-Match: * returns 304 for GET when resource exists."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.get("/resource")
        def get_resource(get_etag):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-None-Match": "*",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 304

    def test_if_none_match_success_when_no_etag(self):
        """Test If-None-Match succeeds when resource has no ETag."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-None-Match": '"abc123"',
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200


class TestIfModifiedSincePrecondition:
    """Test If-Modified-Since precondition processing."""

    def test_if_modified_since_success_when_modified(self):
        """Test If-Modified-Since success when resource was modified."""
        app = RestApplication()

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)  # Modified after

        @app.get("/resource")
        def get_resource(get_last_modified):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_modified_since_304_when_not_modified(self):
        """Test If-Modified-Since returns 304 when resource wasn't modified."""
        app = RestApplication()

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # Same time

        @app.get("/resource")
        def get_resource(get_last_modified):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 304
        assert "Last-Modified" in response.headers

    def test_if_modified_since_ignored_for_post(self):
        """Test If-Modified-Since is ignored for non-GET requests."""
        app = RestApplication()

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # Same time

        @app.post("/resource")
        def create_resource(get_last_modified):
            return {"id": 2, "data": "created"}

        request = Request(
            method=HTTPMethod.POST,
            path="/resource",
            headers={
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "test"}'
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_modified_since_success_when_no_last_modified(self):
        """Test If-Modified-Since succeeds when resource has no Last-Modified."""
        app = RestApplication()

        @app.get("/resource")
        def get_resource():
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 200


class TestIfUnmodifiedSincePrecondition:
    """Test If-Unmodified-Since precondition processing."""

    def test_if_unmodified_since_success_when_not_modified(self):
        """Test If-Unmodified-Since success when resource wasn't modified."""
        app = RestApplication()

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # Modified before

        @app.put("/resource")
        def update_resource(get_last_modified):
            return {"id": 1, "data": "updated"}

        request = Request(
            method=HTTPMethod.PUT,
            path="/resource",
            headers={
                "If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "updated"}'
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_unmodified_since_412_when_modified(self):
        """Test If-Unmodified-Since returns 412 when resource was modified."""
        app = RestApplication()

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)  # Modified after

        @app.put("/resource")
        def update_resource(get_last_modified):
            return {"id": 1, "data": "updated"}

        request = Request(
            method=HTTPMethod.PUT,
            path="/resource",
            headers={
                "If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "updated"}'
        )

        response = app.execute(request)
        assert response.status_code == 412
        assert "Precondition Failed" in response.body

    def test_if_unmodified_since_412_when_no_last_modified(self):
        """Test If-Unmodified-Since fails when resource has no Last-Modified."""
        app = RestApplication()

        @app.put("/resource")
        def update_resource():
            return {"id": 1, "data": "updated"}

        request = Request(
            method=HTTPMethod.PUT,
            path="/resource",
            headers={
                "If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "updated"}'
        )

        response = app.execute(request)
        assert response.status_code == 412
        assert "Precondition Failed" in response.body


class TestCombinedConditionalHeaders:
    """Test combinations of conditional headers."""

    def test_if_match_and_if_unmodified_since_both_succeed(self):
        """Test both If-Match and If-Unmodified-Since succeed."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # Modified before

        @app.put("/resource")
        def update_resource(get_etag, get_last_modified):
            return {"id": 1, "data": "updated"}

        request = Request(
            method=HTTPMethod.PUT,
            path="/resource",
            headers={
                "If-Match": '"abc123"',
                "If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "updated"}'
        )

        response = app.execute(request)
        assert response.status_code == 200

    def test_if_match_succeeds_if_unmodified_since_fails(self):
        """Test If-Match succeeds but If-Unmodified-Since fails."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)  # Modified after

        @app.put("/resource")
        def update_resource(get_etag, get_last_modified):
            return {"id": 1, "data": "updated"}

        request = Request(
            method=HTTPMethod.PUT,
            path="/resource",
            headers={
                "If-Match": '"abc123"',
                "If-Unmodified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            },
            body='{"data": "updated"}'
        )

        response = app.execute(request)
        assert response.status_code == 412  # Should fail on If-Unmodified-Since

    def test_if_none_match_and_if_modified_since_both_return_304(self):
        """Test both If-None-Match and If-Modified-Since return 304."""
        app = RestApplication()

        @app.generate_etag
        def get_etag():
            return "abc123"

        @app.last_modified
        def get_last_modified():
            return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # Same time

        @app.get("/resource")
        def get_resource(get_etag, get_last_modified):
            return {"id": 1, "data": "test"}

        request = Request(
            method=HTTPMethod.GET,
            path="/resource",
            headers={
                "If-None-Match": '"abc123"',
                "If-Modified-Since": "Mon, 01 Jan 2024 12:00:00 GMT",
                "Accept": "application/json"
            }
        )

        response = app.execute(request)
        assert response.status_code == 304
        assert "ETag" in response.headers


class TestETagComparison:
    """Test ETag comparison functions."""

    def test_strong_etag_comparison_matching(self):
        """Test strong ETag comparison with matching ETags."""
        from restmachine.models import etags_match

        result = etags_match('"abc123"', '"abc123"', strong_comparison=True)
        assert result is True

    def test_strong_etag_comparison_non_matching(self):
        """Test strong ETag comparison with non-matching ETags."""
        from restmachine.models import etags_match

        result = etags_match('"abc123"', '"def456"', strong_comparison=True)
        assert result is False

    def test_strong_etag_comparison_with_weak_etag(self):
        """Test strong ETag comparison fails with weak ETags."""
        from restmachine.models import etags_match

        result = etags_match('W/"abc123"', '"abc123"', strong_comparison=True)
        assert result is False

    def test_weak_etag_comparison_matching(self):
        """Test weak ETag comparison with matching ETags."""
        from restmachine.models import etags_match

        result = etags_match('W/"abc123"', '"abc123"', strong_comparison=False)
        assert result is True

    def test_weak_etag_comparison_both_weak(self):
        """Test weak ETag comparison with both weak ETags."""
        from restmachine.models import etags_match

        result = etags_match('W/"abc123"', 'W/"abc123"', strong_comparison=False)
        assert result is True


class TestEndToEndScenarios:
    """Test complete end-to-end conditional request scenarios."""

    def test_api_with_etag_caching(self):
        """Test a complete API scenario with ETag-based caching."""
        app = RestApplication()

        # Simulate a simple user resource with version tracking
        users_db = {
            "1": {"id": "1", "name": "Alice", "version": 1}
        }

        @app.generate_etag
        def user_etag(request):
            user_id = request.path_params.get("user_id")
            if user_id and user_id in users_db:
                user = users_db[user_id]
                return f"user-{user_id}-v{user['version']}"
            return None

        @app.get("/users/{user_id}")
        def get_user(user_etag, request):
            user_id = request.path_params["user_id"]
            if user_id not in users_db:
                return Response(404, "User not found")
            return users_db[user_id]

        @app.put("/users/{user_id}")
        def update_user(user_etag, request):
            user_id = request.path_params["user_id"]
            if user_id not in users_db:
                return Response(404, "User not found")

            # Update user and increment version
            user_data = json.loads(request.body)
            users_db[user_id].update(user_data)
            users_db[user_id]["version"] += 1

            return users_db[user_id]

        # First request - should return 200 with ETag
        request1 = Request(
            method=HTTPMethod.GET,
            path="/users/1",
            headers={"Accept": "application/json"}
        )
        response1 = app.execute(request1)
        assert response1.status_code == 200
        etag1 = response1.headers.get("ETag")
        assert etag1 is not None

        # Second request with If-None-Match - should return 304
        request2 = Request(
            method=HTTPMethod.GET,
            path="/users/1",
            headers={
                "If-None-Match": etag1,
                "Accept": "application/json"
            }
        )
        response2 = app.execute(request2)
        assert response2.status_code == 304

        # Update request with If-Match - should succeed
        request3 = Request(
            method=HTTPMethod.PUT,
            path="/users/1",
            headers={
                "If-Match": etag1,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body='{"name": "Alice Updated"}'
        )
        response3 = app.execute(request3)
        assert response3.status_code == 200

        # New GET request should return updated data with new ETag
        request4 = Request(
            method=HTTPMethod.GET,
            path="/users/1",
            headers={"Accept": "application/json"}
        )
        response4 = app.execute(request4)
        assert response4.status_code == 200
        etag2 = response4.headers.get("ETag")
        assert etag2 != etag1  # ETag should have changed
        data = json.loads(response4.body)
        assert data["name"] == "Alice Updated"

    def test_api_with_last_modified_caching(self):
        """Test a complete API scenario with Last-Modified-based caching."""
        app = RestApplication()

        # Simulate a document with modification tracking
        document = {
            "id": "doc1",
            "content": "Original content",
            "modified": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        }

        @app.last_modified
        def doc_last_modified():
            return document["modified"]

        @app.get("/document")
        def get_document(doc_last_modified):
            return {
                "id": document["id"],
                "content": document["content"]
            }

        @app.put("/document")
        def update_document(doc_last_modified):
            # Update document and modification time
            document["content"] = "Updated content"
            document["modified"] = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
            return {
                "id": document["id"],
                "content": document["content"]
            }

        # First request - should return 200 with Last-Modified
        request1 = Request(
            method=HTTPMethod.GET,
            path="/document",
            headers={"Accept": "application/json"}
        )
        response1 = app.execute(request1)
        assert response1.status_code == 200
        last_modified = response1.headers.get("Last-Modified")
        assert last_modified is not None

        # Second request with If-Modified-Since - should return 304
        request2 = Request(
            method=HTTPMethod.GET,
            path="/document",
            headers={
                "If-Modified-Since": last_modified,
                "Accept": "application/json"
            }
        )
        response2 = app.execute(request2)
        assert response2.status_code == 304

        # Update request with If-Unmodified-Since - should succeed
        request3 = Request(
            method=HTTPMethod.PUT,
            path="/document",
            headers={
                "If-Unmodified-Since": last_modified,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body='{"content": "Updated content"}'
        )
        response3 = app.execute(request3)
        assert response3.status_code == 200

        # New GET request with old If-Modified-Since should return 200 (was modified)
        request4 = Request(
            method=HTTPMethod.GET,
            path="/document",
            headers={
                "If-Modified-Since": last_modified,
                "Accept": "application/json"
            }
        )
        response4 = app.execute(request4)
        assert response4.status_code == 200
        data = json.loads(response4.body)
        assert data["content"] == "Updated content"


if __name__ == "__main__":
    pytest.main([__file__])
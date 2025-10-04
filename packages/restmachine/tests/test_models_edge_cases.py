"""
Tests for edge cases in models.py to improve coverage.

Covers:
- CaseInsensitiveDict with non-string keys and deletion
- Request conditional header parsing (weak ETags, alternative date formats)
- Response ETag/Last-Modified methods
- Utility functions (parse_etags, etags_match)
"""

from datetime import datetime, timezone
from restmachine.models import (
    CaseInsensitiveDict,
    Request,
    Response,
    HTTPMethod,
    parse_etags,
    etags_match,
)


class TestCaseInsensitiveDictEdgeCases:
    """Test CaseInsensitiveDict with edge cases like non-string keys."""

    def test_get_with_non_string_key(self):
        """Test get() with non-string key returns default."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json'})

        # Non-string keys should use default dict behavior
        result = headers.get(123, 'default_value')
        assert result == 'default_value'

    def test_getitem_with_non_string_key(self):
        """Test __getitem__ with non-string key raises KeyError."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json'})

        try:
            _ = headers[123]
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_getitem_with_missing_string_key(self):
        """Test __getitem__ with missing string key raises KeyError."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json'})

        try:
            _ = headers['Missing-Header']
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert 'Missing-Header' in str(e)

    def test_contains_with_non_string_key(self):
        """Test __contains__ with non-string key."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json'})

        # Non-string keys should use default dict behavior
        assert 123 not in headers

    def test_delitem_with_string_key(self):
        """Test __delitem__ with case-insensitive string key."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json', 'Accept': 'text/html'})

        del headers['content-type']  # Delete using lowercase
        assert 'Content-Type' not in headers
        assert 'content-type' not in headers
        assert 'Accept' in headers

    def test_delitem_with_non_string_key(self):
        """Test __delitem__ with non-string key raises KeyError."""
        headers = CaseInsensitiveDict({'Content-Type': 'application/json'})

        try:
            del headers[123]
            assert False, "Should have raised KeyError"
        except KeyError:
            pass


class TestRequestConditionalHeaderParsing:
    """Test Request methods for parsing conditional headers."""

    def test_get_if_match_with_weak_etags(self):
        """Test parsing If-Match header with weak ETags (W/ prefix)."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Match': 'W/"weak-etag", "strong-etag"'}
        )

        etags = request.get_if_match()
        assert etags is not None
        assert len(etags) == 2
        assert 'W/"weak-etag"' in etags
        assert '"strong-etag"' in etags

    def test_get_if_none_match_with_weak_etags(self):
        """Test parsing If-None-Match header with weak ETags (W/ prefix)."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-None-Match': 'W/"weak1", "strong1", W/"weak2"'}
        )

        etags = request.get_if_none_match()
        assert etags is not None
        assert len(etags) == 3
        assert 'W/"weak1"' in etags
        assert '"strong1"' in etags
        assert 'W/"weak2"' in etags

    def test_get_if_match_with_unquoted_etag(self):
        """Test parsing If-Match header with unquoted ETag adds quotes."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Match': 'unquoted-etag'}
        )

        etags = request.get_if_match()
        assert etags is not None
        assert len(etags) == 1
        assert '"unquoted-etag"' in etags

    def test_get_if_none_match_with_unquoted_etag(self):
        """Test parsing If-None-Match header with unquoted ETag adds quotes."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-None-Match': 'unquoted-etag'}
        )

        etags = request.get_if_none_match()
        assert etags is not None
        assert len(etags) == 1
        assert '"unquoted-etag"' in etags

    def test_get_if_modified_since_with_alternative_format(self):
        """Test parsing If-Modified-Since with alternative date format (dashes)."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Modified-Since': 'Mon, 01-Jan-2024 12:00:00 GMT'}
        )

        result = request.get_if_modified_since()
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12

    def test_get_if_modified_since_with_invalid_format(self):
        """Test parsing If-Modified-Since with invalid format returns None."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Modified-Since': 'invalid-date-format'}
        )

        result = request.get_if_modified_since()
        assert result is None

    def test_get_if_unmodified_since_with_alternative_format(self):
        """Test parsing If-Unmodified-Since with alternative date format (dashes)."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Unmodified-Since': 'Mon, 01-Jan-2024 12:00:00 GMT'}
        )

        result = request.get_if_unmodified_since()
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_get_if_unmodified_since_with_invalid_format(self):
        """Test parsing If-Unmodified-Since with invalid format returns None."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'If-Unmodified-Since': 'not-a-date'}
        )

        result = request.get_if_unmodified_since()
        assert result is None


class TestResponseETagMethods:
    """Test Response methods for ETag and Last-Modified."""

    def test_set_etag_strong(self):
        """Test set_etag() with strong ETag."""
        response = Response(status_code=200, body="test")
        response.set_etag("abc123", weak=False)

        assert response.headers["ETag"] == '"abc123"'
        assert response.etag == "abc123"

    def test_set_etag_weak(self):
        """Test set_etag() with weak ETag."""
        response = Response(status_code=200, body="test")
        response.set_etag("def456", weak=True)

        assert response.headers["ETag"] == 'W/"def456"'
        assert response.etag == "def456"

    def test_set_etag_with_none_headers(self):
        """Test set_etag() initializes headers if None."""
        response = Response(status_code=200, body="test")
        # Force headers to None (shouldn't happen in practice but test the guard)
        response.headers = None
        response.set_etag("test123", weak=False)

        assert response.headers == {"ETag": '"test123"'}

    def test_set_last_modified(self):
        """Test set_last_modified() formats datetime correctly."""
        response = Response(status_code=200, body="test")
        last_mod = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        response.set_last_modified(last_mod)

        assert "Last-Modified" in response.headers
        assert response.headers["Last-Modified"] == "Mon, 15 Jan 2024 10:30:00 GMT"
        assert response.last_modified == last_mod

    def test_set_last_modified_with_none_headers(self):
        """Test set_last_modified() initializes headers if None."""
        response = Response(status_code=200, body="test")
        response.headers = None
        last_mod = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        response.set_last_modified(last_mod)

        assert "Last-Modified" in response.headers

    def test_generate_etag_from_content_strong(self):
        """Test generate_etag_from_content() with strong ETag."""
        response = Response(status_code=200, body="test content")
        response.generate_etag_from_content(weak=False)

        assert "ETag" in response.headers
        assert response.headers["ETag"].startswith('"')
        assert not response.headers["ETag"].startswith('W/"')
        assert response.etag is not None

    def test_generate_etag_from_content_weak(self):
        """Test generate_etag_from_content() with weak ETag."""
        response = Response(status_code=200, body="test content")
        response.generate_etag_from_content(weak=True)

        assert "ETag" in response.headers
        assert response.headers["ETag"].startswith('W/"')
        assert response.etag is not None

    def test_generate_etag_from_content_with_none_body(self):
        """Test generate_etag_from_content() with None body does nothing."""
        response = Response(status_code=204)  # No Content
        response.generate_etag_from_content()

        assert "ETag" not in response.headers
        assert response.etag is None

    def test_response_vary_header_with_authorization(self):
        """Test Response automatically adds Authorization to Vary header."""
        request = Request(
            method=HTTPMethod.GET,
            path="/test",
            headers={'Authorization': 'Bearer token123'}
        )

        response = Response(
            status_code=200,
            body="test",
            request=request,
            available_content_types=['application/json']
        )

        assert "Vary" in response.headers
        assert "Authorization" in response.headers["Vary"]


class TestParseETagsFunction:
    """Test parse_etags() utility function."""

    def test_parse_etags_with_empty_string(self):
        """Test parse_etags() with empty string returns empty list."""
        result = parse_etags("")
        assert result == []

    def test_parse_etags_with_none(self):
        """Test parse_etags() with None returns empty list."""
        result = parse_etags(None)
        assert result == []

    def test_parse_etags_with_star(self):
        """Test parse_etags() with star returns ['*']."""
        result = parse_etags("*")
        assert result == ["*"]

    def test_parse_etags_with_quoted_etags(self):
        """Test parse_etags() with quoted ETags."""
        result = parse_etags('"etag1", "etag2", "etag3"')
        assert len(result) == 3
        assert '"etag1"' in result
        assert '"etag2"' in result
        assert '"etag3"' in result

    def test_parse_etags_with_weak_etags(self):
        """Test parse_etags() with weak ETags (W/ prefix)."""
        result = parse_etags('W/"weak1", "strong1", W/"weak2"')
        assert len(result) == 3
        assert 'W/"weak1"' in result
        assert '"strong1"' in result
        assert 'W/"weak2"' in result

    def test_parse_etags_with_unquoted_etags(self):
        """Test parse_etags() adds quotes to unquoted ETags."""
        result = parse_etags('unquoted1, unquoted2')
        assert len(result) == 2
        assert '"unquoted1"' in result
        assert '"unquoted2"' in result


class TestETagsMatchFunction:
    """Test etags_match() utility function."""

    def test_etags_match_with_empty_etags(self):
        """Test etags_match() with empty ETags returns False."""
        assert etags_match("", '"etag1"') is False
        assert etags_match('"etag1"', "") is False
        assert etags_match("", "") is False

    def test_etags_match_strong_comparison_both_strong(self):
        """Test strong comparison with two strong ETags."""
        assert etags_match('"etag1"', '"etag1"', strong_comparison=True) is True
        assert etags_match('"etag1"', '"etag2"', strong_comparison=True) is False

    def test_etags_match_strong_comparison_one_weak(self):
        """Test strong comparison with one weak ETag returns False."""
        assert etags_match('W/"etag1"', '"etag1"', strong_comparison=True) is False
        assert etags_match('"etag1"', 'W/"etag1"', strong_comparison=True) is False

    def test_etags_match_strong_comparison_both_weak(self):
        """Test strong comparison with both weak ETags returns False."""
        assert etags_match('W/"etag1"', 'W/"etag1"', strong_comparison=True) is False

    def test_etags_match_weak_comparison(self):
        """Test weak comparison matches values regardless of weak/strong."""
        assert etags_match('"etag1"', '"etag1"', strong_comparison=False) is True
        assert etags_match('W/"etag1"', '"etag1"', strong_comparison=False) is True
        assert etags_match('"etag1"', 'W/"etag1"', strong_comparison=False) is True
        assert etags_match('W/"etag1"', 'W/"etag1"', strong_comparison=False) is True
        assert etags_match('W/"etag1"', 'W/"etag2"', strong_comparison=False) is False

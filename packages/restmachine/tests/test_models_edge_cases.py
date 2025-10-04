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
    MultiValueHeaders,
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


class TestMultiValueHeadersClass:
    """Test MultiValueHeaders class for handling multiple header values."""

    def test_add_single_header(self):
        """Test adding a single header value."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        assert headers.get("Content-Type") == "application/json"
        assert headers.get_all("Content-Type") == ["application/json"]

    def test_add_multiple_same_header(self):
        """Test adding multiple values for the same header name."""
        headers = MultiValueHeaders()
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")
        headers.add("Set-Cookie", "preferences=dark_mode")

        # get() returns first value
        assert headers.get("Set-Cookie") == "session=abc123"

        # get_all() returns all values
        all_cookies = headers.get_all("Set-Cookie")
        assert len(all_cookies) == 3
        assert "session=abc123" in all_cookies
        assert "user=john_doe" in all_cookies
        assert "preferences=dark_mode" in all_cookies

    def test_case_insensitive_lookup(self):
        """Test that header lookups are case-insensitive."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        assert headers.get("content-type") == "application/json"
        assert headers.get("CONTENT-TYPE") == "application/json"
        assert headers.get("Content-Type") == "application/json"

    def test_get_nonexistent_header(self):
        """Test getting a header that doesn't exist."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        assert headers.get("Authorization") is None
        assert headers.get("Authorization", "default") == "default"
        assert headers.get_all("Authorization") == []

    def test_set_replaces_all_values(self):
        """Test that set() replaces all values for a header."""
        headers = MultiValueHeaders()
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        # set() should replace all values
        headers.set("Set-Cookie", "new_cookie=xyz")

        assert headers.get("Set-Cookie") == "new_cookie=xyz"
        assert headers.get_all("Set-Cookie") == ["new_cookie=xyz"]

    def test_dict_like_setitem(self):
        """Test dict-like __setitem__ interface."""
        headers = MultiValueHeaders()
        headers["Content-Type"] = "application/json"

        assert headers["Content-Type"] == "application/json"

    def test_dict_like_getitem(self):
        """Test dict-like __getitem__ interface."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        assert headers["Content-Type"] == "application/json"

    def test_getitem_raises_keyerror(self):
        """Test that __getitem__ raises KeyError for missing headers."""
        headers = MultiValueHeaders()

        try:
            _ = headers["Missing-Header"]
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "Missing-Header" in str(e)

    def test_contains(self):
        """Test __contains__ for checking header existence."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        assert "Content-Type" in headers
        assert "content-type" in headers
        assert "CONTENT-TYPE" in headers
        assert "Authorization" not in headers

    def test_delitem(self):
        """Test deleting headers."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        # Delete Set-Cookie (removes all values)
        del headers["Set-Cookie"]

        assert "Set-Cookie" not in headers
        assert "Content-Type" in headers
        assert headers.get_all("Set-Cookie") == []

    def test_items_returns_first_values(self):
        """Test that items() returns first value for each header."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        items = list(headers.items())
        assert len(items) == 2

        # Check that we have both headers with first values
        items_dict = dict(items)
        assert items_dict["Content-Type"] == "application/json"
        assert items_dict["Set-Cookie"] == "session=abc123"

    def test_items_all_returns_all_values(self):
        """Test that items_all() returns all header values including duplicates."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")
        headers.add("Set-Cookie", "preferences=dark_mode")

        all_items = headers.items_all()
        assert len(all_items) == 4

        # Convert to list of (name, value) tuples
        set_cookies = [value for name, value in all_items if name == "Set-Cookie"]
        assert len(set_cookies) == 3
        assert "session=abc123" in set_cookies
        assert "user=john_doe" in set_cookies
        assert "preferences=dark_mode" in set_cookies

    def test_to_dict_conversion(self):
        """Test converting to simple dict."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        headers_dict = headers.to_dict()

        assert headers_dict["Content-Type"] == "application/json"
        assert headers_dict["Set-Cookie"] == "session=abc123"  # First value
        assert len(headers_dict) == 2

    def test_to_multidict_conversion(self):
        """Test converting to multi-value dict."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        multidict = headers.to_multidict()

        assert multidict["Content-Type"] == ["application/json"]
        assert multidict["Set-Cookie"] == ["session=abc123", "user=john_doe"]
        assert len(multidict) == 2

    def test_update_from_dict(self):
        """Test updating headers from a dict."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")

        headers.update({"Authorization": "Bearer token", "X-Custom": "value"})

        assert headers.get("Authorization") == "Bearer token"
        assert headers.get("X-Custom") == "value"
        assert headers.get("Content-Type") == "application/json"

    def test_update_from_multivalue_headers(self):
        """Test updating headers from another MultiValueHeaders instance."""
        headers1 = MultiValueHeaders()
        headers1.add("Set-Cookie", "session=abc123")
        headers1.add("X-Custom", "old_value")

        headers2 = MultiValueHeaders()
        headers2.add("Set-Cookie", "user=john_doe")
        headers2.add("Content-Type", "application/json")

        headers1.update(headers2)

        # update() should replace existing headers, not append
        # So Set-Cookie from headers2 replaces the one from headers1
        all_cookies = headers1.get_all("Set-Cookie")
        assert len(all_cookies) == 1
        assert "user=john_doe" in all_cookies
        assert headers1.get("Content-Type") == "application/json"
        # X-Custom should still be there (wasn't in headers2)
        assert headers1.get("X-Custom") == "old_value"

    def test_copy(self):
        """Test copying headers."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        headers_copy = headers.copy()

        # Verify copy has same values
        assert headers_copy.get("Content-Type") == "application/json"
        assert headers_copy.get_all("Set-Cookie") == ["session=abc123", "user=john_doe"]

        # Modify copy shouldn't affect original
        headers_copy.add("Set-Cookie", "new_cookie=xyz")
        assert len(headers.get_all("Set-Cookie")) == 2
        assert len(headers_copy.get_all("Set-Cookie")) == 3

    def test_initialization_from_dict(self):
        """Test initializing from a dict."""
        headers = MultiValueHeaders({"Content-Type": "application/json", "Authorization": "Bearer token"})

        assert headers.get("Content-Type") == "application/json"
        assert headers.get("Authorization") == "Bearer token"

    def test_initialization_from_list_of_tuples(self):
        """Test initializing from a list of tuples."""
        headers = MultiValueHeaders([
            ("Content-Type", "application/json"),
            ("Set-Cookie", "session=abc123"),
            ("Set-Cookie", "user=john_doe")
        ])

        assert headers.get("Content-Type") == "application/json"
        assert headers.get_all("Set-Cookie") == ["session=abc123", "user=john_doe"]

    def test_initialization_from_another_multivalue_headers(self):
        """Test initializing from another MultiValueHeaders instance."""
        original = MultiValueHeaders()
        original.add("Content-Type", "application/json")
        original.add("Set-Cookie", "session=abc123")

        copy = MultiValueHeaders(original)

        assert copy.get("Content-Type") == "application/json"
        assert copy.get_all("Set-Cookie") == ["session=abc123"]

    def test_len(self):
        """Test getting the number of distinct header names."""
        headers = MultiValueHeaders()
        assert len(headers) == 0

        headers.add("Content-Type", "application/json")
        assert len(headers) == 1

        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")
        assert len(headers) == 2  # Still 2 distinct header names

    def test_iter(self):
        """Test iterating over header names."""
        headers = MultiValueHeaders()
        headers.add("Content-Type", "application/json")
        headers.add("Set-Cookie", "session=abc123")
        headers.add("Set-Cookie", "user=john_doe")

        names = list(headers)
        assert len(names) == 2
        assert "Content-Type" in names
        assert "Set-Cookie" in names

    def test_backward_compatibility_alias(self):
        """Test that CaseInsensitiveDict is an alias for MultiValueHeaders."""
        headers = CaseInsensitiveDict()
        assert isinstance(headers, MultiValueHeaders)

    def test_update_replaces_not_appends(self):
        """Test that update() replaces headers rather than appending (dict-like behavior)."""
        headers = MultiValueHeaders()
        headers.add("X-Timestamp", "2024-01-01T00:00:00Z")
        headers.add("X-Custom", "value1")

        # Simulating what happens when default headers are applied to response headers
        default_headers = {"X-Timestamp": "2024-12-31T23:59:59Z", "X-New": "new_value"}
        headers.update(default_headers)

        # X-Timestamp should be replaced, not duplicated
        assert headers.get("X-Timestamp") == "2024-12-31T23:59:59Z"
        assert len(headers.get_all("X-Timestamp")) == 1

        # X-Custom should remain unchanged
        assert headers.get("X-Custom") == "value1"

        # X-New should be added
        assert headers.get("X-New") == "new_value"

    def test_update_with_multivalue_headers_preserves_multiple_values(self):
        """Test that update() preserves multi-value headers when updating from MultiValueHeaders."""
        headers1 = MultiValueHeaders()
        headers1.add("Content-Type", "application/json")

        headers2 = MultiValueHeaders()
        headers2.add("Set-Cookie", "session=abc123")
        headers2.add("Set-Cookie", "user=john_doe")
        headers2.add("Set-Cookie", "preferences=dark_mode")

        headers1.update(headers2)

        # All Set-Cookie values should be preserved
        all_cookies = headers1.get_all("Set-Cookie")
        assert len(all_cookies) == 3
        assert "session=abc123" in all_cookies
        assert "user=john_doe" in all_cookies
        assert "preferences=dark_mode" in all_cookies


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

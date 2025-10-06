"""
Basic tests for S3 static file serving functionality.

Note: These tests verify the S3 path parsing and initialization logic.
Full S3 integration tests would require moto or actual AWS credentials.
"""

import sys
import pytest
from unittest.mock import Mock, patch


class TestS3PathParsing:
    """Test S3 URI parsing logic."""

    def test_parse_s3_uri_with_prefix(self):
        """Test parsing S3 URI with bucket and prefix."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(serve="s3://my-bucket/assets/")

            assert router.is_s3 is True
            assert router.s3_bucket == "my-bucket"
            assert router.s3_prefix == "assets/"

    def test_parse_s3_uri_without_prefix(self):
        """Test parsing S3 URI with bucket only."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(serve="s3://my-bucket")

            assert router.s3_bucket == "my-bucket"
            assert router.s3_prefix == ""

    def test_parse_s3_uri_adds_trailing_slash(self):
        """Test that S3 prefix gets trailing slash if not present."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(serve="s3://my-bucket/assets")

            assert router.s3_prefix == "assets/"

    def test_parse_s3_uri_strips_leading_slash(self):
        """Test that leading slash is stripped from prefix."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(serve="s3://my-bucket//assets/")

            assert router.s3_prefix == "assets/"

    def test_s3_without_boto3_raises_import_error(self):
        """Test that S3 URI without boto3 raises ImportError."""
        from restmachine_web import StaticRouter

        with patch.dict('sys.modules', {'boto3': None}):
            with pytest.raises(ImportError, match="boto3 is required for S3 support"):
                StaticRouter(serve="s3://my-bucket/assets/")


class TestPathNormalization:
    """Test path normalization for both local and S3."""

    def test_normalize_removes_leading_slash(self, tmp_path):
        """Test that leading slash is removed."""
        from restmachine_web import StaticRouter

        router = StaticRouter(serve=str(tmp_path))
        normalized = router._normalize_path("/test/file.txt")

        assert normalized == "test/file.txt"

    def test_normalize_removes_duplicate_slashes(self, tmp_path):
        """Test that duplicate slashes are removed."""
        from restmachine_web import StaticRouter

        router = StaticRouter(serve=str(tmp_path))
        normalized = router._normalize_path("test//file///nested.txt")

        assert normalized == "test/file/nested.txt"

    def test_normalize_handles_multiple_leading_slashes(self, tmp_path):
        """Test that multiple leading slashes are handled."""
        from restmachine_web import StaticRouter

        router = StaticRouter(serve=str(tmp_path))
        normalized = router._normalize_path("///test/file.txt")

        assert normalized == "test/file.txt"


class TestRetryWithIndex:
    """Test retry_with_index parameter."""

    def test_retry_with_index_enabled(self):
        """Test that retry_with_index parameter is stored."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(
                serve="s3://my-bucket/",
                retry_with_index=True
            )

            assert router.retry_with_index is True

    def test_retry_with_index_disabled_by_default(self):
        """Test that retry_with_index is False by default."""
        from restmachine_web import StaticRouter

        mock_boto3 = Mock()
        mock_boto3.client.return_value = Mock()

        with patch.dict('sys.modules', {'boto3': mock_boto3}):
            router = StaticRouter(serve="s3://my-bucket/")

            assert router.retry_with_index is False

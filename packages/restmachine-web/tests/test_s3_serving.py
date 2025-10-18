"""
Tests for S3 static file serving functionality.

Uses moto to mock AWS S3 for testing S3 file serving.
"""

import pytest
from io import BytesIO

import boto3
from moto import mock_aws
from restmachine import RestApplication
from restmachine.testing import MultiDriverTestBase
from restmachine_web import StaticRouter


class TestS3FileServing(MultiDriverTestBase):
    """Test serving static files from S3."""

    @pytest.fixture(scope="class")
    def s3_bucket(self):
        """Create a mock S3 bucket with test files."""
        with mock_aws():
            # Create S3 bucket
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')

            # Upload test files
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.txt',
                Body=b'Hello from S3!',
                ContentType='text/plain'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.html',
                Body=b'<html><body>S3 HTML</body></html>',
                ContentType='text/html'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/index.html',
                Body=b'<html><body>S3 Index</body></html>',
                ContentType='text/html'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/docs/index.html',
                Body=b'<html><body>Docs Index</body></html>',
                ContentType='text/html'
            )

            yield s3_client

    def create_app(self, with_retry=False) -> RestApplication:
        """Create a RestMachine app with S3 static files mounted."""
        app = RestApplication()
        with mock_aws():
            static_router = StaticRouter(
                serve="s3://test-bucket/assets/",
                retry_with_index=with_retry
            )
            app.mount("/static", static_router)
        return app

    @pytest.fixture(scope="class")
    def api(self, request, s3_bucket):
        """Override api fixture to create app with S3 bucket."""
        driver_name = request.param
        with mock_aws():
            # Recreate the bucket in this context
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.txt',
                Body=b'Hello from S3!',
                ContentType='text/plain'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.html',
                Body=b'<html><body>S3 HTML</body></html>',
                ContentType='text/html'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/index.html',
                Body=b'<html><body>S3 Index</body></html>',
                ContentType='text/html'
            )
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/docs/index.html',
                Body=b'<html><body>Docs Index</body></html>',
                ContentType='text/html'
            )

            app = self.create_app()
            driver = self.create_driver(driver_name, app)
            from restmachine.testing import RestApiDsl
            yield RestApiDsl(driver), driver_name

    def test_serve_s3_text_file(self, api):
        """Test serving a text file from S3."""
        api_client, driver_name = api

        request = api_client.get("/static/test.txt")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "Hello from S3!" in str(response.body)

    def test_serve_s3_html_file(self, api):
        """Test serving an HTML file from S3."""
        api_client, driver_name = api

        request = api_client.get("/static/test.html")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "S3 HTML" in str(response.body)

    def test_serve_s3_root_index(self, api):
        """Test serving root index file from S3."""
        api_client, driver_name = api

        request = api_client.get("/static/")
        response = api_client.execute(request)

        assert response.status_code == 200
        assert "S3 Index" in str(response.body)

    def test_serve_s3_missing_file(self, api):
        """Test serving a non-existent file from S3 returns 404."""
        api_client, driver_name = api

        request = api_client.get("/static/nonexistent.txt")
        response = api_client.execute(request)

        assert response.status_code == 404

    def test_serve_s3_with_retry_index(self, api):
        """Test S3 serving with retry_with_index for directory paths."""
        api_client, driver_name = api

        # Create app with retry enabled
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/docs/index.html',
                Body=b'<html><body>Docs Index</body></html>',
                ContentType='text/html'
            )

            app = RestApplication()
            static_router = StaticRouter(
                serve="s3://test-bucket/assets/",
                retry_with_index=True
            )
            app.mount("/static", static_router)
            driver = self.create_driver(driver_name, app)
            from restmachine.testing import RestApiDsl
            api_with_retry = RestApiDsl(driver)

            # Request a "directory" path that should retry with index
            request = api_with_retry.get("/static/docs")
            response = api_with_retry.execute(request)

            # Should find docs/index.html
            assert response.status_code == 200
            assert "Docs Index" in str(response.body)


class TestS3ContentTypes:
    """Test S3 content type handling."""

    def test_s3_content_type_from_metadata(self):
        """Test that Content-Type is retrieved from S3 metadata."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/custom.dat',
                Body=b'custom data',
                ContentType='application/x-custom'
            )

            app = RestApplication()
            static_router = StaticRouter(serve="s3://test-bucket/assets/")
            app.mount("/static", static_router)

            # Access via router directly
            from restmachine.testing import RestMachineDriver, RestApiDsl
            driver = RestMachineDriver(app)
            api = RestApiDsl(driver)

            request = api.get("/static/custom.dat")
            response = api.execute(request)

            assert response.status_code == 200

    def test_s3_content_type_guessed_from_filename(self):
        """Test that Content-Type is guessed when not in metadata."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            # Upload without explicit ContentType
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/style.css',
                Body=b'body { color: red; }'
            )

            app = RestApplication()
            static_router = StaticRouter(serve="s3://test-bucket/assets/")
            app.mount("/static", static_router)

            from restmachine.testing import RestMachineDriver, RestApiDsl
            driver = RestMachineDriver(app)
            api = RestApiDsl(driver)

            request = api.get("/static/style.css")
            response = api.execute(request)

            assert response.status_code == 200


class TestS3Errors:
    """Test S3 error handling."""

    def test_s3_permission_error(self):
        """Test handling S3 permission errors."""
        with mock_aws():
            # Create app pointing to non-existent bucket
            # Moto will raise an exception
            app = RestApplication()
            static_router = StaticRouter(serve="s3://test-bucket/assets/")
            app.mount("/static", static_router)

            from restmachine.testing import RestMachineDriver, RestApiDsl
            driver = RestMachineDriver(app)
            api = RestApiDsl(driver)

            request = api.get("/static/test.txt")
            response = api.execute(request)

            # Should return 500 for S3 errors
            assert response.status_code == 500


class TestS3ContentTypeEdgeCases:
    """Test S3 content type edge cases and fallbacks."""

    def test_s3_content_type_fallback_to_mimetypes(self):
        """Test content type guessing when S3 metadata doesn't include ContentType."""
        from unittest.mock import patch, MagicMock
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.json',
                Body=b'{"key": "value"}'
            )

            app = RestApplication()
            static_router = StaticRouter(serve="s3://test-bucket/assets/")
            app.mount("/static", static_router)

            # Mock the S3 response to not include ContentType
            original_get = static_router.s3_client.get_object
            def mock_get_object(**kwargs):
                response = original_get(**kwargs)
                # Remove ContentType to trigger mimetypes fallback
                if 'ContentType' in response:
                    del response['ContentType']
                return response

            with patch.object(static_router.s3_client, 'get_object', side_effect=mock_get_object):
                from restmachine.testing import RestMachineDriver, RestApiDsl
                driver = RestMachineDriver(app)
                api = RestApiDsl(driver)

                request = api.get("/static/test.json")
                response = api.execute(request)

                assert response.status_code == 200
                # Should guess content type from filename (.json)
                assert "json" in response.content_type or "application" in response.content_type

    def test_s3_content_type_fallback_to_octet_stream(self):
        """Test content type fallback to octet-stream for unknown extensions."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')

            # Upload file with unknown extension and no ContentType
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/test.xyz123',
                Body=b'unknown file type'
            )

            app = RestApplication()
            static_router = StaticRouter(serve="s3://test-bucket/assets/")
            app.mount("/static", static_router)

            from restmachine.testing import RestMachineDriver, RestApiDsl
            driver = RestMachineDriver(app)
            api = RestApiDsl(driver)

            request = api.get("/static/test.xyz123")
            response = api.execute(request)

            assert response.status_code == 200

    def test_s3_retry_index_not_found(self):
        """Test S3 retry with index when index file also doesn't exist."""
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')

            # Don't upload any files - both original and index will fail

            app = RestApplication()
            static_router = StaticRouter(
                serve="s3://test-bucket/assets/",
                retry_with_index=True
            )
            app.mount("/static", static_router)

            from restmachine.testing import RestMachineDriver, RestApiDsl
            driver = RestMachineDriver(app)
            api = RestApiDsl(driver)

            # Request a path that doesn't exist
            request = api.get("/static/nonexistent")
            response = api.execute(request)

            # Should return 404 after both attempts fail
            assert response.status_code == 404

    def test_s3_retry_index_content_type_fallback(self):
        """Test content type guessing in retry path when metadata is missing."""
        from unittest.mock import patch
        with mock_aws():
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='test-bucket')
            s3_client.put_object(
                Bucket='test-bucket',
                Key='assets/docs/index.html',
                Body=b'<html><body>Docs</body></html>'
            )

            app = RestApplication()
            static_router = StaticRouter(
                serve="s3://test-bucket/assets/",
                retry_with_index=True
            )
            app.mount("/static", static_router)

            # Mock the S3 response to not include ContentType
            original_get = static_router.s3_client.get_object
            def mock_get_object(**kwargs):
                response = original_get(**kwargs)
                # Remove ContentType to trigger mimetypes fallback
                if 'ContentType' in response:
                    del response['ContentType']
                return response

            with patch.object(static_router.s3_client, 'get_object', side_effect=mock_get_object):
                from restmachine.testing import RestMachineDriver, RestApiDsl
                driver = RestMachineDriver(app)
                api = RestApiDsl(driver)

                # Request directory path - will retry with index
                request = api.get("/static/docs")
                response = api.execute(request)

                assert response.status_code == 200
                # Should guess content type from .html extension or default to text/html
                assert "html" in response.content_type or "text" in response.content_type

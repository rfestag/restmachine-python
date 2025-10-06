"""
Static file serving router for RestMachine framework.
"""

from pathlib import Path as PathType
from typing import Optional, Union, BinaryIO
from restmachine.router import Router
from restmachine import Response
from http import HTTPStatus
import mimetypes


class StaticRouter(Router):
    """Router for serving static files from a local directory or S3 bucket.

    This router provides a simple way to mount a directory of static files
    to a RestMachine application. It includes security features like path
    traversal protection and supports serving index files for directories.

    Supports both local filesystem and S3:
    - Local: serve="./public"
    - S3: serve="s3://bucket-name/optional-prefix/"

    Only supports GET requests - all other methods return 405 Method Not Allowed.

    Example:
        ```python
        from restmachine import RestApplication
        from restmachine_web import StaticRouter

        app = RestApplication()

        # Local filesystem
        static_router = StaticRouter(serve="./public")
        app.mount("/static", static_router)

        # S3 bucket
        s3_router = StaticRouter(
            serve="s3://my-bucket/assets/",
            retry_with_index=True
        )
        app.mount("/assets", s3_router)
        ```
    """

    def __init__(
        self,
        serve: str,
        index_file: str = "index.html",
        retry_with_index: bool = False
    ):
        """Initialize the static file router.

        Args:
            serve: Path to the directory containing static files
                  Can be local path or S3 URI (s3://bucket-name/prefix/)
            index_file: Name of the index file to serve for directory requests
                       (default: "index.html")
            retry_with_index: If True and initial S3 GetObject fails, retry with
                            index file appended (treats path as directory)

        Raises:
            ValueError: If local directory doesn't exist or is not a directory
            ImportError: If S3 path is used but boto3 is not installed
        """
        super().__init__()

        self.index_file = index_file
        self.retry_with_index = retry_with_index

        # Detect if this is an S3 path
        if serve.startswith("s3://"):
            self.is_s3 = True
            self._parse_s3_path(serve)
        else:
            self.is_s3 = False
            self.directory = PathType(serve).resolve()

            if not self.directory.exists():
                raise ValueError(f"Directory does not exist: {serve}")
            if not self.directory.is_dir():
                raise ValueError(f"Path is not a directory: {serve}")

        # Register the wildcard GET route
        self._register_routes()

    def _parse_s3_path(self, s3_uri: str):
        """Parse S3 URI into bucket and prefix.

        Args:
            s3_uri: S3 URI like s3://bucket-name/prefix/path/

        Raises:
            ImportError: If boto3 is not installed
        """
        try:
            import boto3
            self.s3_client = boto3.client('s3')
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 support. "
                "Install with: pip install restmachine-web[s3]"
            )

        # Remove s3:// prefix
        path = s3_uri[5:]

        # Split into bucket and prefix
        parts = path.split('/', 1)
        self.s3_bucket = parts[0]
        self.s3_prefix = parts[1] if len(parts) > 1 else ""

        # Ensure prefix doesn't start with / but ends with / if not empty
        self.s3_prefix = self.s3_prefix.lstrip('/')
        if self.s3_prefix and not self.s3_prefix.endswith('/'):
            self.s3_prefix += '/'

    def _register_routes(self):
        """Register the static file serving routes."""

        @self.get("/**")
        def serve_static(path: str = ""):
            """Serve a static file from the directory."""
            return self._serve_file(path)

        # For other HTTP methods, register handlers that return 405
        for method_name in ['post', 'put', 'delete', 'patch']:
            method = getattr(self, method_name)

            @method("/**")
            def method_not_allowed(path: str = ""):
                """Return 405 Method Not Allowed for non-GET requests."""
                return Response(HTTPStatus.METHOD_NOT_ALLOWED)

    def _normalize_path(self, filepath: str) -> str:
        """Normalize path by removing duplicate slashes and leading slash.

        Args:
            filepath: The requested file path

        Returns:
            Normalized path without leading slash or duplicate slashes
        """
        # Remove leading slash
        path = filepath.lstrip('/')

        # Replace multiple slashes with single slash
        while '//' in path:
            path = path.replace('//', '/')

        return path

    def _serve_file(self, filepath: str) -> Union[Response, PathType, BinaryIO]:
        """Serve a static file from the mounted directory or S3.

        Args:
            filepath: The requested file path (relative to serve directory)

        Returns:
            Response with file content or appropriate error status
        """
        # Normalize the path
        normalized_path = self._normalize_path(filepath)

        if self.is_s3:
            return self._serve_file_from_s3(normalized_path)
        else:
            return self._serve_file_from_local(normalized_path)

    def _serve_file_from_local(self, filepath: str) -> Union[Response, PathType]:
        """Serve a static file from the local filesystem.

        Args:
            filepath: The requested file path (relative to serve directory)

        Returns:
            Response with file content or appropriate error status
        """
        # Security: resolve the requested path and ensure it's within directory
        requested_path = self.directory / filepath
        try:
            resolved_path = requested_path.resolve()
        except (OSError, RuntimeError):
            # Path resolution failed (e.g., too many symlinks, invalid path)
            return Response(HTTPStatus.NOT_FOUND)

        # Security: ensure the resolved path is within our directory
        # This prevents path traversal attacks like "../../../etc/passwd"
        try:
            resolved_path.relative_to(self.directory)
        except ValueError:
            # Path is outside the allowed directory
            return Response(HTTPStatus.NOT_FOUND)

        # Check if it's a directory
        if resolved_path.is_dir():
            # Try to serve index file
            index_path = resolved_path / self.index_file
            if index_path.is_file():
                return index_path
            # No index file, return 404
            return Response(HTTPStatus.NOT_FOUND)

        # Check if file exists
        if not resolved_path.is_file():
            return Response(HTTPStatus.NOT_FOUND)

        # Return the Path object - RestMachine will handle the response
        return resolved_path

    def _serve_file_from_s3(self, filepath: str) -> Union[Response, BinaryIO]:
        """Serve a static file from S3.

        Args:
            filepath: The requested file path (relative to S3 prefix)

        Returns:
            Response with StreamingBody or appropriate error status
        """
        # If filepath is empty or just "/", use index file
        if not filepath or filepath == '/':
            filepath = self.index_file

        # Construct S3 key
        s3_key = self.s3_prefix + filepath

        try:
            # Try to get the object from S3
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )

            # Get Content-Type from S3 metadata or guess from filename
            content_type = response.get('ContentType')
            if not content_type:
                content_type, _ = mimetypes.guess_type(s3_key)
                if not content_type:
                    content_type = 'application/octet-stream'

            # Return StreamingBody wrapped in Response with Content-Type
            return Response(
                HTTPStatus.OK,
                response['Body'],
                content_type=content_type
            )

        except self.s3_client.exceptions.NoSuchKey:
            # File not found - try with index if retry_with_index is enabled
            if self.retry_with_index:
                # Append index file and try again
                index_key = s3_key.rstrip('/') + '/' + self.index_file

                try:
                    response = self.s3_client.get_object(
                        Bucket=self.s3_bucket,
                        Key=index_key
                    )

                    # Get Content-Type
                    content_type = response.get('ContentType')
                    if not content_type:
                        content_type, _ = mimetypes.guess_type(index_key)
                        if not content_type:
                            content_type = 'text/html'

                    # Return StreamingBody wrapped in Response
                    return Response(
                        HTTPStatus.OK,
                        response['Body'],
                        content_type=content_type
                    )

                except self.s3_client.exceptions.NoSuchKey:
                    # Index file also not found
                    return Response(HTTPStatus.NOT_FOUND)

            # No retry or retry failed
            return Response(HTTPStatus.NOT_FOUND)

        except Exception as e:
            # Other S3 errors (permissions, etc.)
            return Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"S3 error: {str(e)}"},
                content_type="application/json"
            )

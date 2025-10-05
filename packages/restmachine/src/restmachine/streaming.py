"""
Streaming support for request and response bodies.

This module provides file-like stream objects for handling large request and
response bodies efficiently without loading everything into memory.
"""

import io
from typing import cast


class BytesStreamBuffer(io.BytesIO):
    """
    A bytes stream buffer that can be written to asynchronously and read synchronously.

    This class extends io.BytesIO to provide a file-like interface for streaming
    request bodies. The ASGI adapter writes to this stream as body chunks arrive,
    and the application reads from it.

    Features:
    - Supports incremental writes from async sources
    - Seekable for parsers that need it
    - Tracks EOF state
    - Compatible with boto3 StreamingBody and similar interfaces

    Example:
        ```python
        # ASGI adapter creates stream and writes as chunks arrive
        stream = BytesStreamBuffer()
        async for chunk in receive_body_chunks():
            stream.write(chunk)
        stream.close_writing()

        # Application reads from stream
        data = stream.read()

        # Or for streaming parsers:
        import json
        parsed = json.load(stream)
        ```
    """

    def __init__(self):
        super().__init__()
        self._writing_finished = False
        self._read_position = 0

    def close_writing(self):
        """
        Signal that no more data will be written.

        This should be called by the ASGI adapter once all body chunks
        have been received and written to the stream.
        """
        self._writing_finished = True
        # Reset to beginning for reading
        self.seek(0)

    @property
    def writing_finished(self) -> bool:
        """Check if writing is finished and stream is ready for reading."""
        return self._writing_finished

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class FileStreamWrapper:
    """
    Wrapper for file-like objects to provide consistent interface.

    This wrapper ensures that file-like objects (such as boto3 StreamingBody)
    can be used uniformly with our streaming infrastructure.

    Example:
        ```python
        # Wrap an S3 streaming body
        import boto3
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket='my-bucket', Key='file.txt')
        stream = FileStreamWrapper(response['Body'])

        # Use in response
        return Response(200, body=stream)
        ```
    """

    def __init__(self, file_obj):
        self._file = file_obj

    def read(self, size: int = -1) -> bytes:
        """Read bytes from the underlying file object."""
        if hasattr(self._file, 'read'):
            return cast(bytes, self._file.read(size))
        raise TypeError("Wrapped object does not support read()")

    def close(self):
        """Close the underlying file object if it supports closing."""
        if hasattr(self._file, 'close'):
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __iter__(self):
        """Iterate over lines or chunks."""
        if hasattr(self._file, '__iter__'):
            return iter(self._file)
        # Default: iterate in 8KB chunks
        return self._chunk_iterator()

    def _chunk_iterator(self, chunk_size: int = 8192):
        """Iterator for reading in chunks."""
        while True:
            chunk = self.read(chunk_size)
            if not chunk:
                break
            yield chunk

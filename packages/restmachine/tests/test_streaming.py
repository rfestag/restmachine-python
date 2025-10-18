"""
Tests for streaming support for request and response bodies.

The streaming module provides file-like objects for efficiently handling
large request and response bodies without loading everything into memory.
"""

import pytest
import io
from restmachine.streaming import BytesStreamBuffer, FileStreamWrapper


class TestBytesStreamBuffer:
    """Test BytesStreamBuffer for async write / sync read."""

    def test_init(self):
        """Test initialization."""
        stream = BytesStreamBuffer()

        assert stream.writing_finished is False
        assert stream.tell() == 0

    def test_write_and_read(self):
        """Test writing data and reading it back."""
        stream = BytesStreamBuffer()

        # Write data
        stream.write(b"Hello, ")
        stream.write(b"World!")

        # Close writing
        stream.close_writing()

        # Read data back
        data = stream.read()
        assert data == b"Hello, World!"
        assert stream.writing_finished is True

    def test_close_writing_resets_position(self):
        """Test that close_writing resets position to start."""
        stream = BytesStreamBuffer()

        stream.write(b"test data")
        # Position should be at end after write
        assert stream.tell() > 0

        stream.close_writing()
        # Position should be reset to start
        assert stream.tell() == 0

    def test_multiple_reads(self):
        """Test reading data multiple times."""
        stream = BytesStreamBuffer()

        stream.write(b"Hello, World!")
        stream.close_writing()

        # First read
        data1 = stream.read()
        assert data1 == b"Hello, World!"

        # Seek back and read again
        stream.seek(0)
        data2 = stream.read()
        assert data2 == b"Hello, World!"

    def test_partial_reads(self):
        """Test reading data in chunks."""
        stream = BytesStreamBuffer()

        stream.write(b"1234567890")
        stream.close_writing()

        # Read in chunks
        chunk1 = stream.read(5)
        assert chunk1 == b"12345"

        chunk2 = stream.read(5)
        assert chunk2 == b"67890"

        # EOF
        chunk3 = stream.read(5)
        assert chunk3 == b""

    def test_seekable(self):
        """Test seeking in the stream."""
        stream = BytesStreamBuffer()

        stream.write(b"ABCDEFGHIJ")
        stream.close_writing()

        # Seek to middle
        stream.seek(5)
        data = stream.read(3)
        assert data == b"FGH"

        # Seek to beginning
        stream.seek(0)
        data = stream.read(3)
        assert data == b"ABC"

        # Seek to end
        stream.seek(0, 2)
        assert stream.tell() == 10

    def test_context_manager(self):
        """Test using as context manager."""
        with BytesStreamBuffer() as stream:
            stream.write(b"test")
            stream.close_writing()
            data = stream.read()
            assert data == b"test"

        # Stream should be closed after context
        assert stream.closed

    def test_writing_finished_property(self):
        """Test writing_finished property."""
        stream = BytesStreamBuffer()

        assert stream.writing_finished is False

        stream.write(b"data")
        assert stream.writing_finished is False

        stream.close_writing()
        assert stream.writing_finished is True

    def test_incremental_writes(self):
        """Test writing data incrementally (simulating async chunks)."""
        stream = BytesStreamBuffer()

        # Simulate receiving chunks asynchronously
        chunks = [b"chunk1", b"-", b"chunk2", b"-", b"chunk3"]
        for chunk in chunks:
            stream.write(chunk)

        stream.close_writing()

        # Read all data
        data = stream.read()
        assert data == b"chunk1-chunk2-chunk3"

    def test_empty_stream(self):
        """Test empty stream behavior."""
        stream = BytesStreamBuffer()
        stream.close_writing()

        data = stream.read()
        assert data == b""
        assert stream.writing_finished is True


class TestFileStreamWrapper:
    """Test FileStreamWrapper for consistent file-like interface."""

    def test_init(self):
        """Test initialization with file object."""
        file_obj = io.BytesIO(b"test data")
        wrapper = FileStreamWrapper(file_obj)

        assert wrapper._file is file_obj

    def test_read(self):
        """Test reading from wrapped file."""
        file_obj = io.BytesIO(b"Hello, World!")
        wrapper = FileStreamWrapper(file_obj)

        data = wrapper.read()
        assert data == b"Hello, World!"

    def test_read_with_size(self):
        """Test reading specific number of bytes."""
        file_obj = io.BytesIO(b"1234567890")
        wrapper = FileStreamWrapper(file_obj)

        chunk1 = wrapper.read(5)
        assert chunk1 == b"12345"

        chunk2 = wrapper.read(5)
        assert chunk2 == b"67890"

        # EOF
        chunk3 = wrapper.read(5)
        assert chunk3 == b""

    def test_read_without_read_method(self):
        """Test wrapping object without read method."""
        # Create object without read method
        bad_obj = object()
        wrapper = FileStreamWrapper(bad_obj)

        with pytest.raises(TypeError, match="does not support read"):
            wrapper.read()

    def test_close(self):
        """Test closing wrapped file."""
        file_obj = io.BytesIO(b"test")
        wrapper = FileStreamWrapper(file_obj)

        wrapper.close()

        # File should be closed
        assert file_obj.closed

    def test_close_without_close_method(self):
        """Test closing object without close method."""
        # Create mock object without close method
        class NoClose:
            def read(self, size=-1):
                return b"data"

        obj = NoClose()
        wrapper = FileStreamWrapper(obj)

        # Should not raise
        wrapper.close()

    def test_context_manager(self):
        """Test using wrapper as context manager."""
        file_obj = io.BytesIO(b"test data")

        with FileStreamWrapper(file_obj) as wrapper:
            data = wrapper.read()
            assert data == b"test data"

        # File should be closed after context
        assert file_obj.closed

    def test_iterate_with_iterator(self):
        """Test iteration when wrapped object has __iter__."""
        # Create file-like object with lines
        file_obj = io.BytesIO(b"line1\nline2\nline3\n")
        wrapper = FileStreamWrapper(file_obj)

        lines = list(wrapper)
        assert lines == [b"line1\n", b"line2\n", b"line3\n"]

    def test_iterate_with_chunks(self):
        """Test iteration using chunk iterator."""
        # Create object with read but no __iter__
        class ReadOnlyFile:
            def __init__(self, data):
                self.data = data
                self.pos = 0

            def read(self, size=-1):
                if size == -1:
                    result = self.data[self.pos:]
                    self.pos = len(self.data)
                    return result
                else:
                    result = self.data[self.pos:self.pos + size]
                    self.pos += len(result)
                    return result

        data = b"A" * 20000  # 20KB
        file_obj = ReadOnlyFile(data)
        wrapper = FileStreamWrapper(file_obj)

        # Iterate in chunks
        chunks = list(wrapper)

        # Should have received data in 8KB chunks
        assert len(chunks) == 3  # 8192 + 8192 + 3616 bytes
        assert b"".join(chunks) == data

    def test_chunk_iterator_directly(self):
        """Test _chunk_iterator method."""
        file_obj = io.BytesIO(b"X" * 10000)
        wrapper = FileStreamWrapper(file_obj)

        chunks = list(wrapper._chunk_iterator(chunk_size=1024))

        # Should have ~10 chunks of 1KB each
        assert len(chunks) == 10
        assert all(len(chunk) == 1024 for chunk in chunks[:-1])
        assert b"".join(chunks) == b"X" * 10000

    def test_chunk_iterator_small_data(self):
        """Test chunk iterator with data smaller than chunk size."""
        file_obj = io.BytesIO(b"small")
        wrapper = FileStreamWrapper(file_obj)

        chunks = list(wrapper._chunk_iterator(chunk_size=1024))

        assert len(chunks) == 1
        assert chunks[0] == b"small"

    def test_chunk_iterator_empty_data(self):
        """Test chunk iterator with empty data."""
        file_obj = io.BytesIO(b"")
        wrapper = FileStreamWrapper(file_obj)

        chunks = list(wrapper._chunk_iterator())

        assert len(chunks) == 0


class TestStreamingIntegration:
    """Integration tests for streaming functionality."""

    def test_bytes_stream_buffer_simulates_asgi_body(self):
        """Test BytesStreamBuffer simulating ASGI body reception."""
        # Simulate ASGI adapter receiving body chunks
        stream = BytesStreamBuffer()

        # Simulate receiving chunks from ASGI
        async def simulate_asgi_receive():
            chunks = [
                b'{"name": "',
                b'John',
                b'", "age": ',
                b'30',
                b'}'
            ]
            for chunk in chunks:
                stream.write(chunk)
            stream.close_writing()

        # Run simulation
        import asyncio
        asyncio.run(simulate_asgi_receive())

        # Application reads the body
        body = stream.read()
        assert body == b'{"name": "John", "age": 30}'

        # Can parse as JSON
        import json
        stream.seek(0)
        data = json.load(stream)
        assert data == {"name": "John", "age": 30}

    def test_file_stream_wrapper_with_real_file(self, tmp_path):
        """Test FileStreamWrapper with actual file."""
        # Create temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello from file!")

        # Wrap file
        with test_file.open('rb') as f:
            wrapper = FileStreamWrapper(f)
            data = wrapper.read()

        assert data == b"Hello from file!"

    def test_wrapping_bytes_io(self):
        """Test wrapping BytesIO object."""
        buffer = io.BytesIO(b"test data")
        wrapper = FileStreamWrapper(buffer)

        # Should work seamlessly
        data = wrapper.read()
        assert data == b"test data"

    def test_reusing_stream_after_close_writing(self):
        """Test that stream can be read multiple times after close_writing."""
        stream = BytesStreamBuffer()

        stream.write(b"reusable data")
        stream.close_writing()

        # Read once
        data1 = stream.read()
        assert data1 == b"reusable data"

        # Seek and read again
        stream.seek(0)
        data2 = stream.read()
        assert data2 == b"reusable data"

        # Partial read after seek
        stream.seek(3)
        data3 = stream.read(7)
        assert data3 == b"sable d"

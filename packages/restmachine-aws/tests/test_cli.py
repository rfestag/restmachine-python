"""
Tests for CLI commands (__main__.py).

These tests verify the CLI utilities work correctly.
"""

import pytest
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch


def test_create_extension_default_path():
    """Test creating extension with default path."""
    from restmachine_aws.__main__ import create_extension
    from argparse import Namespace
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to temp directory for this test
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            args = Namespace(output=None)
            create_extension(args)

            # Check extension was created
            extension_path = Path(tmpdir) / "extensions" / "restmachine-shutdown"
            assert extension_path.exists()
            assert extension_path.is_file()

            # Check it's executable
            assert extension_path.stat().st_mode & 0o111  # At least one execute bit

            # Check content
            content = extension_path.read_text()
            assert "from restmachine_aws.extension import main" in content
        finally:
            os.chdir(orig_cwd)


def test_create_extension_custom_path():
    """Test creating extension with custom path."""
    from restmachine_aws.__main__ import create_extension
    from argparse import Namespace

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_path = Path(tmpdir) / "custom" / "my-extension"
        args = Namespace(output=str(custom_path))
        create_extension(args)

        # Check extension was created at custom path
        assert custom_path.exists()
        assert custom_path.is_file()


def test_cli_help():
    """Test CLI help message."""
    from restmachine_aws.__main__ import main

    # Test that help exits with code 1 when no command given
    with patch('sys.argv', ['restmachine-aws']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

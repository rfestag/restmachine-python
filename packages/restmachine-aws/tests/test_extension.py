"""
Tests for AWS Lambda Extension for shutdown handling.
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from restmachine_aws.extension import ShutdownExtension, main


class TestShutdownExtension:
    """Test the ShutdownExtension class."""

    def test_initialization_requires_runtime_api(self):
        """Extension should fail if AWS_LAMBDA_RUNTIME_API is not set."""
        # Clear the environment variable if it exists
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="AWS_LAMBDA_RUNTIME_API"):
                ShutdownExtension()

    def test_initialization_with_runtime_api(self):
        """Extension should initialize successfully with runtime API set."""
        with patch.dict(os.environ, {"AWS_LAMBDA_RUNTIME_API": "localhost:9001"}):
            extension = ShutdownExtension()
            assert extension.runtime_api == "localhost:9001"
            assert extension.handler_module == "lambda_function"
            assert extension.app_name == "app"

    def test_initialization_with_custom_module_and_app(self):
        """Extension should accept custom module and app names."""
        with patch.dict(os.environ, {"AWS_LAMBDA_RUNTIME_API": "localhost:9001"}):
            extension = ShutdownExtension(handler_module="my_handler", app_name="application")
            assert extension.handler_module == "my_handler"
            assert extension.app_name == "application"

    def test_register_success(self):
        """Test successful registration with Extensions API."""
        with patch.dict(os.environ, {"AWS_LAMBDA_RUNTIME_API": "localhost:9001"}):
            extension = ShutdownExtension()

            # Mock the HTTP request
            mock_response = MagicMock()
            mock_response.headers = {"Lambda-Extension-Identifier": "test-ext-id-123"}
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)

            with patch("restmachine_aws.extension.request.urlopen", return_value=mock_response) as mock_urlopen:
                ext_id = extension.register()

                # Verify registration was called
                assert mock_urlopen.called
                assert ext_id == "test-ext-id-123"
                assert extension.extension_id == "test-ext-id-123"

                # Verify the request parameters
                call_args = mock_urlopen.call_args
                req = call_args[0][0]
                assert "2020-01-01/extension/register" in req.full_url
                assert req.get_method() == "POST"

    def test_wait_for_event_returns_shutdown(self):
        """Test waiting for and receiving a SHUTDOWN event."""
        with patch.dict(os.environ, {"AWS_LAMBDA_RUNTIME_API": "localhost:9001"}):
            extension = ShutdownExtension()
            extension.extension_id = "test-ext-id"

            # Mock the event response
            shutdown_event = {"eventType": "SHUTDOWN", "shutdownReason": "spindown"}
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(shutdown_event).encode("utf-8")
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)

            with patch("restmachine_aws.extension.request.urlopen", return_value=mock_response):
                event = extension.wait_for_event()

                assert event["eventType"] == "SHUTDOWN"
                assert event["shutdownReason"] == "spindown"

    def test_load_app_success(self):
        """Test successfully loading the application."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            extension = ShutdownExtension()

            # Create a mock module with an app
            mock_app = Mock()
            mock_module = Mock()
            mock_module.app = mock_app

            with patch("builtins.__import__", return_value=mock_module):
                app = extension.load_app()

                assert app == mock_app

    def test_load_app_module_not_found(self):
        """Test loading app when module doesn't exist."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            extension = ShutdownExtension(handler_module="nonexistent_module")

            with patch("builtins.__import__", side_effect=ImportError("No module named 'nonexistent_module'")):
                with pytest.raises(ImportError, match="Could not import handler module"):
                    extension.load_app()

    def test_load_app_missing_attribute(self):
        """Test loading app when module doesn't have the app attribute."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            extension = ShutdownExtension(app_name="missing_app")

            # Create a mock module without the app attribute
            mock_module = Mock(spec=[])  # No attributes

            with patch("builtins.__import__", return_value=mock_module):
                with pytest.raises(AttributeError, match="has no attribute 'missing_app'"):
                    extension.load_app()

    def test_run_complete_lifecycle(self):
        """Test the complete extension lifecycle."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            extension = ShutdownExtension()

            # Mock app with shutdown_sync method
            mock_app = Mock()
            mock_app.shutdown_sync = Mock()

            # Mock registration
            mock_register_response = MagicMock()
            mock_register_response.headers = {"Lambda-Extension-Identifier": "test-id"}
            mock_register_response.__enter__ = Mock(return_value=mock_register_response)
            mock_register_response.__exit__ = Mock(return_value=False)

            # Mock event response
            shutdown_event = {"eventType": "SHUTDOWN"}
            mock_event_response = MagicMock()
            mock_event_response.read.return_value = json.dumps(shutdown_event).encode("utf-8")
            mock_event_response.__enter__ = Mock(return_value=mock_event_response)
            mock_event_response.__exit__ = Mock(return_value=False)

            # Mock module import
            mock_module = Mock()
            mock_module.app = mock_app

            with patch("restmachine_aws.extension.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = [mock_register_response, mock_event_response]

                with patch("builtins.__import__", return_value=mock_module):
                    extension.run()

                    # Verify shutdown_sync was called
                    mock_app.shutdown_sync.assert_called_once()

    def test_run_without_shutdown_sync_method(self):
        """Test extension with app that doesn't have shutdown_sync."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            extension = ShutdownExtension()

            # Mock app WITHOUT shutdown_sync method
            mock_app = Mock(spec=[])  # No shutdown_sync

            # Mock registration
            mock_register_response = MagicMock()
            mock_register_response.headers = {"Lambda-Extension-Identifier": "test-id"}
            mock_register_response.__enter__ = Mock(return_value=mock_register_response)
            mock_register_response.__exit__ = Mock(return_value=False)

            # Mock event response
            shutdown_event = {"eventType": "SHUTDOWN"}
            mock_event_response = MagicMock()
            mock_event_response.read.return_value = json.dumps(shutdown_event).encode("utf-8")
            mock_event_response.__enter__ = Mock(return_value=mock_event_response)
            mock_event_response.__exit__ = Mock(return_value=False)

            # Mock module import
            mock_module = Mock()
            mock_module.app = mock_app

            with patch("restmachine_aws.extension.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = [mock_register_response, mock_event_response]

                with patch("builtins.__import__", return_value=mock_module):
                    # Should not raise an error, just log a warning
                    extension.run()


class TestExtensionMain:
    """Test the main() entry point."""

    def test_main_with_defaults(self):
        """Test main() with default parameters."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            mock_extension = Mock()

            with patch("restmachine_aws.extension.ShutdownExtension", return_value=mock_extension):
                main()

                # Verify extension was created with defaults
                assert mock_extension.run.called

    def test_main_with_environment_overrides(self):
        """Test main() with environment variable overrides."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task",
            "RESTMACHINE_HANDLER_MODULE": "custom_handler",
            "RESTMACHINE_APP_NAME": "my_app",
            "RESTMACHINE_LOG_LEVEL": "DEBUG"
        }):
            with patch("restmachine_aws.extension.ShutdownExtension") as mock_extension_class:
                mock_extension = Mock()
                mock_extension_class.return_value = mock_extension

                main()

                # Verify extension was created with environment overrides
                mock_extension_class.assert_called_once_with(
                    handler_module="custom_handler",
                    app_name="my_app"
                )
                mock_extension.run.assert_called_once()

    def test_main_with_custom_parameters(self):
        """Test main() with custom parameters passed directly."""
        with patch.dict(os.environ, {
            "AWS_LAMBDA_RUNTIME_API": "localhost:9001",
            "LAMBDA_TASK_ROOT": "/var/task"
        }):
            with patch("restmachine_aws.extension.ShutdownExtension") as mock_extension_class:
                mock_extension = Mock()
                mock_extension_class.return_value = mock_extension

                main(handler_module="my_module", app_name="application")

                # Verify extension was created with custom parameters
                mock_extension_class.assert_called_once_with(
                    handler_module="my_module",
                    app_name="application"
                )
                mock_extension.run.assert_called_once()

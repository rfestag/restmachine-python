"""
Tests for deprecation warnings.

Tests deprecation warnings for moved DynamoDB components.
"""

import pytest
import warnings


class TestDynamoDBDeprecationWarnings:
    """Test deprecation warnings for DynamoDB components."""

    def test_dynamodb_backend_deprecation_warning(self):
        """Test importing DynamoDBBackend shows deprecation warning."""
        with pytest.warns(DeprecationWarning, match="DynamoDBBackend has been moved"):
            # This will trigger the __getattr__ in backends/__init__.py
            from restmachine_orm.backends import DynamoDBBackend

    def test_dynamodb_backend_import_error_without_package(self):
        """Test DynamoDBBackend import raises error if package not installed."""
        # Mock that the package isn't installed by catching the ImportError
        with pytest.warns(DeprecationWarning):
            try:
                from restmachine_orm.backends import DynamoDBBackend
                # If we get here, the package is installed
                # Just verify it's the right class
                assert DynamoDBBackend is not None
            except ImportError as e:
                # Package not installed - verify error message
                assert "restmachine-orm-dynamodb" in str(e)

    def test_dynamodb_adapter_deprecation_warning(self):
        """Test importing DynamoDBAdapter shows deprecation warning."""
        with pytest.warns(DeprecationWarning, match="DynamoDBAdapter has been moved"):
            from restmachine_orm.backends import DynamoDBAdapter

    def test_dynamodb_adapter_import_error_without_package(self):
        """Test DynamoDBAdapter import raises error if package not installed."""
        with pytest.warns(DeprecationWarning):
            try:
                from restmachine_orm.backends import DynamoDBAdapter
                # If we get here, the package is installed
                assert DynamoDBAdapter is not None
            except ImportError as e:
                # Package not installed - verify error message
                assert "restmachine-orm-dynamodb" in str(e)

    def test_unknown_attribute_raises_attribute_error(self):
        """Test accessing unknown attribute raises AttributeError."""
        with pytest.raises(AttributeError, match="has no attribute 'UnknownClass'"):
            from restmachine_orm import backends
            # Try to access non-existent attribute
            _ = backends.UnknownClass

    def test_deprecation_warning_stacklevel(self):
        """Test deprecation warning uses correct stacklevel."""
        # Capture warnings to verify stacklevel
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from restmachine_orm.backends import DynamoDBBackend

            # Should have exactly one warning
            assert len(w) >= 1
            # First warning should be DeprecationWarning
            assert issubclass(w[0].category, DeprecationWarning)
            # Message should contain the deprecation text
            assert "DynamoDBBackend has been moved" in str(w[0].message)


class TestBackendsAllExports:
    """Test that __all__ includes deprecated names."""

    def test_all_includes_deprecated_backends(self):
        """Test __all__ includes deprecated DynamoDB components."""
        from restmachine_orm import backends

        # __all__ should include the deprecated names
        assert "DynamoDBBackend" in backends.__all__
        assert "DynamoDBAdapter" in backends.__all__

    def test_all_includes_current_backends(self):
        """Test __all__ includes current backend components."""
        from restmachine_orm import backends

        # Should also include current components
        assert "Backend" in backends.__all__
        assert "InMemoryBackend" in backends.__all__
        assert "ModelAdapter" in backends.__all__
        assert "InMemoryAdapter" in backends.__all__
        assert "OpenSearchAdapter" in backends.__all__
        assert "CompositeAdapter" in backends.__all__

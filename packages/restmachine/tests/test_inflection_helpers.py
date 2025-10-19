"""
Tests for inflection library helpers used in code generation.

These tests verify that the inflection library behaves as expected for
our naming conventions (pluralization, camelization, underscoring).
"""

import inflection


class TestNameHelpers:
    """Test name conversion using inflection library."""

    def test_pluralize_regular_nouns(self):
        """Test pluralization of regular nouns."""
        assert inflection.pluralize('user') == 'users'
        assert inflection.pluralize('product') == 'products'
        assert inflection.pluralize('item') == 'items'

    def test_pluralize_words_ending_in_y(self):
        """Test pluralization of words ending in consonant + y."""
        assert inflection.pluralize('category') == 'categories'
        assert inflection.pluralize('company') == 'companies'

    def test_pluralize_words_ending_in_s_x_z(self):
        """Test pluralization of words ending in s, x, z, ch, sh."""
        assert inflection.pluralize('status') == 'statuses'
        assert inflection.pluralize('box') == 'boxes'
        assert inflection.pluralize('search') == 'searches'

    def test_pluralize_special_cases(self):
        """Test pluralization of special irregular nouns."""
        assert inflection.pluralize('person') == 'people'
        assert inflection.pluralize('child') == 'children'

    def test_to_class_name(self):
        """Test conversion to PascalCase class names."""
        assert inflection.camelize('product') == 'Product'
        assert inflection.camelize('blog_post') == 'BlogPost'
        assert inflection.camelize('BlogPost') == 'BlogPost'

    def test_to_snake_case(self):
        """Test conversion to snake_case."""
        assert inflection.underscore('Product') == 'product'
        assert inflection.underscore('BlogPost') == 'blog_post'
        assert inflection.underscore('blog_post') == 'blog_post'
        assert inflection.underscore('APIKey') == 'api_key'

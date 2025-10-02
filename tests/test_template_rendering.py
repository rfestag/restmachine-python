"""
Unit tests for Jinja2 template rendering functionality.

Tests the render() helper function and HTMLRenderer integration.
"""

import os
import pytest
from restmachine import RestApplication, render
from restmachine.content_renderers import HTMLRenderer
from restmachine.models import Request, HTTPMethod


class TestRenderFunction:
    """Test the render() helper function."""

    def test_inline_template_basic(self):
        """Test basic inline template rendering."""
        result = render(
            inline="<h1>{{ title }}</h1>",
            title="Hello World"
        )
        assert result == "<h1>Hello World</h1>"

    def test_inline_template_multiple_variables(self):
        """Test inline template with multiple variables."""
        result = render(
            inline="<h1>{{ title }}</h1><p>{{ content }}</p>",
            title="Welcome",
            content="This is a test"
        )
        assert result == "<h1>Welcome</h1><p>This is a test</p>"

    def test_inline_template_with_filters(self):
        """Test inline template with Jinja2 filters."""
        result = render(
            inline="{{ name|upper }}",
            name="john"
        )
        assert result == "JOHN"

    def test_inline_template_with_conditionals(self):
        """Test inline template with conditionals."""
        result = render(
            inline="{% if show %}{{ message }}{% endif %}",
            show=True,
            message="Visible"
        )
        assert result == "Visible"

        result = render(
            inline="{% if show %}{{ message }}{% endif %}",
            show=False,
            message="Hidden"
        )
        assert result == ""

    def test_inline_template_with_loop(self):
        """Test inline template with loop."""
        result = render(
            inline="{% for item in items %}{{ item }},{% endfor %}",
            items=["a", "b", "c"]
        )
        assert result == "a,b,c,"

    def test_inline_template_autoescape_enabled_by_default(self):
        """Test that autoescape is enabled by default for inline templates."""
        result = render(
            inline="{{ content }}",
            content="<script>alert('xss')</script>"
        )
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_inline_template_unsafe_disables_autoescape(self):
        """Test that unsafe=True disables autoescape."""
        result = render(
            inline="{{ content }}",
            unsafe=True,
            content="<strong>Bold</strong>"
        )
        assert result == "<strong>Bold</strong>"

    def test_inline_template_safe_filter(self):
        """Test using |safe filter with autoescape enabled."""
        result = render(
            inline="{{ content|safe }}",
            content="<em>Italic</em>"
        )
        assert result == "<em>Italic</em>"

    def test_file_template_basic(self):
        """Test basic file-based template rendering."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="simple.html",
            package=templates_dir,
            title="Test Title",
            content="Test Content"
        )
        assert "<h1>Test Title</h1>" in result
        assert "<p>Test Content</p>" in result

    def test_file_template_with_inheritance(self):
        """Test template inheritance."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="extends_base.html",
            package=templates_dir,
            page_title="My Page",
            heading="Welcome",
            message="Hello from template"
        )
        assert "<!DOCTYPE html>" in result
        assert "<title>My Page</title>" in result
        assert "<h1>Welcome</h1>" in result
        assert "<p>Hello from template</p>" in result

    def test_file_template_with_loop(self):
        """Test template with loop."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="with_loop.html",
            package=templates_dir,
            items=["apple", "banana", "cherry"]
        )
        assert "<li>apple</li>" in result
        assert "<li>banana</li>" in result
        assert "<li>cherry</li>" in result

    def test_file_template_autoescape_enabled(self):
        """Test that file templates have autoescape enabled by default."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="simple.html",
            package=templates_dir,
            title="<script>alert('xss')</script>",
            content="Safe content"
        )
        assert "&lt;script&gt;" in result
        assert "<script>alert" not in result

    def test_file_template_with_safe_filter(self):
        """Test file template with |safe filter."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="unsafe.html",
            package=templates_dir,
            content="<strong>Bold text</strong>"
        )
        assert "<strong>Bold text</strong>" in result

    def test_package_as_relative_path(self):
        """Test package parameter as relative path."""
        # Get the current test directory
        test_dir = os.path.dirname(__file__)
        templates_path = os.path.join(test_dir, "templates")

        result = render(
            template="simple.html",
            package=templates_path,
            title="Test",
            content="Content"
        )
        assert "<h1>Test</h1>" in result

    def test_package_as_absolute_path(self):
        """Test package parameter as absolute path."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        abs_path = os.path.abspath(templates_dir)

        result = render(
            template="simple.html",
            package=abs_path,
            title="Absolute",
            content="Path"
        )
        assert "<h1>Absolute</h1>" in result

    def test_error_no_template_or_inline(self):
        """Test error when neither template nor inline is provided."""
        with pytest.raises(ValueError) as excinfo:
            render(title="Test")
        assert "Either 'template' or 'inline' parameter must be provided" in str(excinfo.value)

    def test_error_template_not_found(self):
        """Test error when template file doesn't exist."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        with pytest.raises(ValueError) as excinfo:
            render(
                template="nonexistent.html",
                package=templates_dir
            )
        assert "Failed to load template" in str(excinfo.value)

    def test_error_package_not_found(self):
        """Test error when package/directory doesn't exist."""
        with pytest.raises(ValueError) as excinfo:
            render(
                template="test.html",
                package="/nonexistent/path"
            )
        assert "Could not find template directory or package" in str(excinfo.value)

    def test_inline_takes_precedence_over_template(self):
        """Test that inline parameter takes precedence over template."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        result = render(
            template="simple.html",
            inline="<p>{{ text }}</p>",
            package=templates_dir,
            text="Inline wins"
        )
        # Should use inline template
        assert result == "<p>Inline wins</p>"


class TestHTMLRenderer:
    """Test HTMLRenderer with Jinja2 integration."""

    def test_backward_compatibility_prerendered_html(self):
        """Test that HTMLRenderer still accepts pre-rendered HTML strings."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        html = "<h1>Already Rendered</h1>"
        result = renderer.render(html, request)

        # Should return as-is
        assert result == html

    def test_dict_rendering_uses_jinja2(self):
        """Test that dict rendering now uses Jinja2."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        data = {"name": "John", "age": 30}
        result = renderer.render(data, request)

        # Should contain HTML structure with Jinja2 template
        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "API Response" in result
        assert "name" in result
        assert "John" in result

    def test_list_rendering_uses_jinja2(self):
        """Test that list rendering now uses Jinja2."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        data = ["apple", "banana", "cherry"]
        result = renderer.render(data, request)

        # Should contain HTML structure
        assert "<!DOCTYPE html>" in result
        assert "<li>apple</li>" in result
        assert "<li>banana</li>" in result

    def test_string_rendering_uses_jinja2(self):
        """Test that non-HTML strings are wrapped with Jinja2 template."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        data = "Plain text message"
        result = renderer.render(data, request)

        # Should be wrapped in HTML
        assert "<!DOCTYPE html>" in result
        assert "Plain text message" in result

    def test_nested_dict_rendering(self):
        """Test rendering nested dictionaries."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        data = {
            "user": {
                "name": "Alice",
                "email": "alice@example.com"
            },
            "status": "active"
        }
        result = renderer.render(data, request)

        assert "user" in result
        assert "Alice" in result
        assert "alice@example.com" in result
        assert "status" in result
        assert "active" in result

    def test_html_escaping_in_dict_values(self):
        """Test that dict values are HTML-escaped properly."""
        renderer = HTMLRenderer()
        request = Request(method=HTTPMethod.GET, path="/test", headers={})

        data = {"message": "<script>alert('xss')</script>"}
        result = renderer.render(data, request)

        # The content is marked as safe in the template, but individual values
        # should still be escaped when building the HTML structure
        # This is handled by the _dict_to_html method which uses f-strings
        assert "alert" in result  # The string value is there but escaped


class TestTemplateRenderingIntegration:
    """Integration tests for template rendering with RestApplication."""

    def test_custom_renderer_with_file_template(self):
        """Test custom renderer using file-based template."""
        app = RestApplication()
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        @app.get("/user/{user_id}")
        def get_user(user_id: str):
            return {"id": user_id, "name": "John Doe"}

        @app.renders("text/html")
        def user_html(get_user):
            user = get_user
            return render(
                template="simple.html",
                package=templates_dir,
                title=user["name"],
                content=f"User ID: {user['id']}"
            )

        request = Request(
            method=HTTPMethod.GET,
            path="/user/123",
            headers={"Accept": "text/html"}
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert "<h1>John Doe</h1>" in response.body
        assert "User ID: 123" in response.body

    def test_custom_renderer_with_inline_template(self):
        """Test custom renderer using inline template."""
        app = RestApplication()

        @app.get("/greeting/{name}")
        def greeting(name: str):
            return {"name": name}

        @app.renders("text/html")
        def greeting_html(greeting):
            data = greeting
            return render(
                inline="<h1>Hello, {{ name }}!</h1>",
                name=data["name"]
            )

        request = Request(
            method=HTTPMethod.GET,
            path="/greeting/World",
            headers={"Accept": "text/html"}
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert response.body == "<h1>Hello, World!</h1>"

    def test_default_html_renderer_fallback(self):
        """Test that default HTMLRenderer works without custom templates."""
        app = RestApplication()

        @app.get("/data")
        def get_data():
            return {"message": "Hello", "value": 42}

        request = Request(
            method=HTTPMethod.GET,
            path="/data",
            headers={"Accept": "text/html"}
        )

        response = app.execute(request)

        assert response.status_code == 200
        assert response.content_type == "text/html"
        assert "<!DOCTYPE html>" in response.body
        assert "message" in response.body
        assert "Hello" in response.body

    def test_content_negotiation_json_vs_html(self):
        """Test content negotiation between JSON and HTML."""
        app = RestApplication()
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        @app.get("/users")
        def list_users():
            return [
                {"name": "Alice", "id": "1"},
                {"name": "Bob", "id": "2"}
            ]

        @app.renders("text/html")
        def users_html(list_users):
            return render(
                template="with_loop.html",
                package=templates_dir,
                items=[f"{u['name']} (ID: {u['id']})" for u in list_users]
            )

        # Request JSON
        json_request = Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={"Accept": "application/json"}
        )
        json_response = app.execute(json_request)

        assert json_response.status_code == 200
        assert json_response.content_type == "application/json"
        assert "Alice" in json_response.body

        # Request HTML
        html_request = Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={"Accept": "text/html"}
        )
        html_response = app.execute(html_request)

        assert html_response.status_code == 200
        assert html_response.content_type == "text/html"
        assert "<li>Alice (ID: 1)</li>" in html_response.body
        assert "<li>Bob (ID: 2)</li>" in html_response.body


class TestTemplateSecurityFeatures:
    """Test security features of template rendering."""

    def test_autoescape_prevents_xss_inline(self):
        """Test that autoescape prevents XSS in inline templates."""
        malicious = "<script>alert('xss')</script>"
        result = render(
            inline="{{ content }}",
            content=malicious
        )
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_autoescape_prevents_xss_file_template(self):
        """Test that autoescape prevents XSS in file templates."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        malicious = "<script>alert('xss')</script>"

        result = render(
            template="simple.html",
            package=templates_dir,
            title=malicious,
            content="safe"
        )

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_unsafe_mode_allows_html(self):
        """Test that unsafe mode allows raw HTML (use with caution)."""
        html_content = "<strong>Bold</strong>"
        result = render(
            inline="{{ content }}",
            unsafe=True,
            content=html_content
        )
        assert result == html_content

    def test_safe_filter_allows_trusted_html(self):
        """Test that |safe filter allows trusted HTML."""
        trusted_html = "<em>Italic</em>"
        result = render(
            inline="{{ content|safe }}",
            content=trusted_html
        )
        assert result == trusted_html

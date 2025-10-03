"""
Template rendering helpers for the REST framework.
"""

import os
from typing import Any, Optional
from jinja2 import Environment, PackageLoader, FileSystemLoader, select_autoescape, Template
from jinja2.loaders import BaseLoader


def render(
    template: Optional[str] = None,
    package: str = "views",
    unsafe: bool = False,
    inline: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Render a template using Jinja2.

    This function provides Rails-like view rendering capabilities with support
    for both file-based templates and inline template strings.

    Args:
        template: Path to the template file relative to the package/views directory.
                 Ignored if `inline` is provided.
        package: Package name or directory path for templates. Defaults to "views".
                If it's a valid directory path, FileSystemLoader is used.
                Otherwise, PackageLoader is attempted.
        unsafe: If False (default), autoescape is enabled for security.
               If True, autoescape is disabled (use with caution).
        inline: Optional inline template string. If provided, this template
               will be rendered instead of loading from a file.
        **kwargs: Variables to pass to the template context for rendering.

    Returns:
        The rendered template as a string.

    Examples:
        # Render from a file
        render(template="users/show.html", user=user_obj)

        # Render inline template
        render(inline="<h1>{{ title }}</h1>", title="Welcome")

        # Custom package location
        render(template="admin/dashboard.html", package="admin_views", stats=stats)

        # Using directory path
        render(template="index.html", package="./templates", data=data)

        # Disable autoescape (use with caution)
        render(template="raw.html", unsafe=True, content=html_content)
    """
    if inline:
        # Render inline template
        template_obj = Template(
            inline,
            autoescape=not unsafe
        )
        return template_obj.render(**kwargs)

    if not template:
        raise ValueError("Either 'template' or 'inline' parameter must be provided")

    # Try to determine if package is a directory path or a package name
    loader: Optional[BaseLoader] = None

    # Check if it's a directory path (absolute or relative)
    if os.path.isdir(package):
        loader = FileSystemLoader(package)
    else:
        # Try common directory locations
        possible_paths = [
            package,  # Direct path
            os.path.join(os.getcwd(), package),  # Relative to current directory
            os.path.join(os.path.dirname(os.path.dirname(__file__)), package),  # Relative to project root
        ]

        for path in possible_paths:
            if os.path.isdir(path):
                loader = FileSystemLoader(path)
                break

        # If no directory found, try PackageLoader
        if loader is None:
            try:
                loader = PackageLoader(package)
            except (ImportError, ValueError, ModuleNotFoundError):
                # PackageLoader failed - package doesn't exist or isn't importable
                # This is expected when package is neither a directory nor a valid Python package
                pass

    if loader is None:
        raise ValueError(
            f"Could not find template directory or package '{package}'. "
            f"Tried paths: {possible_paths}"
        )

    # Create Jinja2 environment
    try:
        # Note: autoescape can be disabled via unsafe=True parameter for trusted content
        # This is intentional and controlled by the caller - see documentation
        env = Environment(  # nosec B701
            loader=loader,
            autoescape=select_autoescape() if not unsafe else False
        )
        template_obj = env.get_template(template)
        return template_obj.render(**kwargs)
    except Exception as e:
        raise ValueError(
            f"Failed to load template '{template}' from package/directory '{package}'. "
            f"Ensure the package/directory exists and contains the template file. "
            f"Original error: {str(e)}"
        )

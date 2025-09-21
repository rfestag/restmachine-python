"""
Content renderers for different media types.
"""

import json
from typing import Any

from .models import Request


class ContentRenderer:
    """Base class for content renderers."""

    def __init__(self, media_type: str):
        self.media_type = media_type

    def can_render(self, accept_header: str) -> bool:
        """Check if this renderer can handle the given Accept header."""
        if accept_header == "*/*":
            return True
        accept_types = [t.strip().split(";")[0] for t in accept_header.split(",")]
        return self.media_type in accept_types or "*/*" in accept_types

    def render(self, data: Any, request: Request) -> str:
        """Render the data as this content type."""
        raise NotImplementedError


class JSONRenderer(ContentRenderer):
    """JSON content renderer."""

    def __init__(self):
        super().__init__("application/json")

    def render(self, data: Any, request: Request) -> str:
        """Render data as JSON."""
        if isinstance(data, str):
            # If it's already a string, assume it's JSON or return as-is
            return data

        # Handle Pydantic models and lists of Pydantic models
        data = self._serialize_pydantic(data)

        try:
            return json.dumps(data, indent=2)
        except (TypeError, ValueError):
            return json.dumps({"data": str(data)})

    def _serialize_pydantic(self, data: Any) -> Any:
        """Convert Pydantic models to dictionaries for JSON serialization."""
        if hasattr(data, "model_dump"):
            # Single Pydantic model
            return data.model_dump()
        elif isinstance(data, list):
            # List that might contain Pydantic models
            return [self._serialize_pydantic(item) for item in data]
        elif isinstance(data, dict):
            # Dictionary that might contain Pydantic models
            return {key: self._serialize_pydantic(value) for key, value in data.items()}
        else:
            # Regular data, return as-is
            return data


class HTMLRenderer(ContentRenderer):
    """HTML content renderer."""

    def __init__(self):
        super().__init__("text/html")

    def render(self, data: Any, request: Request) -> str:
        """Render data as HTML."""
        if isinstance(data, str) and data.strip().startswith("<"):
            # Already HTML
            return data

        # Simple HTML wrapper for non-HTML data
        if isinstance(data, dict):
            content = self._dict_to_html(data)
        elif isinstance(data, list):
            content = self._list_to_html(data)
        else:
            content = f"<p>{str(data)}</p>"

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>API Response</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .key {{ font-weight: bold; color: #333; }}
        .value {{ margin-left: 20px; color: #666; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>API Response</h1>
    {content}
</body>
</html>"""

    def _dict_to_html(self, data: dict) -> str:
        """Convert dictionary to HTML."""
        items = []
        for key, value in data.items():
            if isinstance(value, dict):
                value_html = self._dict_to_html(value)
            elif isinstance(value, list):
                value_html = self._list_to_html(value)
            else:
                value_html = f'<span class="value">{str(value)}</span>'
            items.append(f'<li><span class="key">{key}:</span> {value_html}</li>')
        return f"<ul>{''.join(items)}</ul>"

    def _list_to_html(self, data: list) -> str:
        """Convert list to HTML."""
        items = []
        for item in data:
            if isinstance(item, dict):
                item_html = self._dict_to_html(item)
            elif isinstance(item, list):
                item_html = self._list_to_html(item)
            else:
                item_html = str(item)
            items.append(f"<li>{item_html}</li>")
        return f"<ul>{''.join(items)}</ul>"


class PlainTextRenderer(ContentRenderer):
    """Plain text content renderer."""

    def __init__(self):
        super().__init__("text/plain")

    def render(self, data: Any, request: Request) -> str:
        """Render data as plain text."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            return "\n".join(f"{k}: {v}" for k, v in data.items())
        elif isinstance(data, list):
            return "\n".join(str(item) for item in data)
        else:
            return str(data)

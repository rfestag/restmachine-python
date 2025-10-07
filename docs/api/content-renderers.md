# Content Renderers

## Built-in Renderers

::: restmachine.JSONRenderer
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

::: restmachine.HTMLRenderer
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

::: restmachine.PlainTextRenderer
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## ContentRenderer Base Class

::: restmachine.ContentRenderer
    options:
      show_root_heading: true
      heading_level: 3
      show_source: false

## Overview

Content renderers convert response data into different formats based on the client's `Accept` header. RestMachine includes built-in renderers for JSON, HTML, and plain text.

## Custom Renderers

Register custom renderers for specific content types:

```python
@app.content_renderer("application/xml")
def render_xml(data):
    """Render data as XML."""
    return f"<result>{data}</result>"

@app.get('/data')
def get_data():
    return {"key": "value"}
    # Returns JSON or XML based on Accept header
```

## See Also

- [Content Negotiation Guide](../guide/content-negotiation.md) - Complete guide
- [Application API](application.md) - Register renderers

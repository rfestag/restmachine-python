# Content Security Policy (CSP)

RestMachine provides built-in Content Security Policy support with auto-quoting, nonce generation, and flexible configuration at app, router, or route level.

## Overview

CSP is a powerful security feature that helps prevent cross-site scripting (XSS) and other code injection attacks by controlling which resources browsers can load. RestMachine handles:

- **Auto-quoting** - Keywords like `'self'` and `'unsafe-inline'` are automatically quoted
- **Nonce generation** - Unique nonces for inline scripts/styles
- **Preset policies** - Pre-configured security levels (STRICT, BASIC, RELAXED)
- **Dynamic sources** - Callable functions for runtime CSP configuration
- **Report-only mode** - Test policies without blocking resources
- **Three-tier configuration** - App-level, router-level, or route-level

## Quick Start

### Basic CSP Setup

The simplest CSP configuration - allow only resources from your own domain:

```python
from restmachine import RestApplication

app = RestApplication()

# Enable CSP - allow resources only from same origin
app.csp(default_src=["self"])

@app.get("/page")
def get_page():
    return {"page": "content"}

# Response will include: Content-Security-Policy: default-src 'self'
```

Notice how `"self"` in the code becomes `'self'` (quoted) in the header - RestMachine automatically quotes CSP keywords for you.

### Using Presets

RestMachine includes pre-configured security levels:

```python
from restmachine import RestApplication
from restmachine.csp import CSPPreset

app = RestApplication()

# STRICT: Most secure - blocks most external resources
app.csp(preset=CSPPreset.STRICT)

# BASIC: Allow only same-origin resources
app.csp(preset=CSPPreset.BASIC)

# RELAXED: Allow inline styles (common in many apps)
app.csp(preset=CSPPreset.RELAXED)

# DEVELOPMENT: Very permissive, report-only mode
app.csp(preset=CSPPreset.DEVELOPMENT)
```

## Configuration Levels

RestMachine supports CSP configuration at three levels with inheritance:

### 1. App-Level (Global)

Apply CSP to all routes in the application:

```python
app = RestApplication()

# All routes will have this CSP policy
app.csp(
    default_src=["self"],
    script_src=["self", "https://cdn.jsdelivr.net"],
    style_src=["self", "unsafe-inline"],
    img_src=["self", "data:", "https:"]
)

@app.get("/page")
def get_page():
    from restmachine import render
    return render(template="page.html", package="templates")
```

### 2. Router-Level

Apply CSP to all routes in a specific router:

```python
from restmachine import Router

app = RestApplication()

# Public pages - relaxed CSP
public_router = Router()
public_router.csp(
    default_src=["self"],
    script_src=["self", "https://cdn.example.com"],
    style_src=["self", "unsafe-inline"]
)

@public_router.get("/home")
def home():
    from restmachine import render
    return render(template="home.html", package="templates")

# Admin pages - strict CSP
admin_router = Router()
admin_router.csp(
    default_src=["self"],
    script_src=["self"],  # No CDNs
    style_src=["self"]    # No inline styles
)

@admin_router.get("/dashboard")
def dashboard():
    from restmachine import render
    return render(template="admin.html", package="templates")

app.mount("/", public_router)
app.mount("/admin", admin_router)
```

### 3. Route-Level

Override CSP for specific endpoints:

```python
app = RestApplication()

# Default CSP for all routes
app.csp(default_src=["self"])

@app.get("/page")
def get_page():
    return {"page": "basic"}

# Override for specific route
@app.get("/special")
@app.csp(
    default_src=["self"],
    script_src=["self", "https://special-cdn.com"]
)
def get_special():
    return {"page": "special"}
```

**Hierarchy**: Route-level → Router-level → App-level (most specific wins)

## Auto-Quoting

RestMachine automatically quotes CSP values based on their type:

### Keywords (Auto-Quoted)

CSP keywords are automatically quoted:

```python
app.csp(
    default_src=["self"],                    # → 'self'
    script_src=["self", "unsafe-inline"],    # → 'self' 'unsafe-inline'
    style_src=["unsafe-eval"],               # → 'unsafe-eval'
    object_src=["none"]                      # → 'none'
)

# Result: default-src 'self'; script-src 'self' 'unsafe-inline'; ...
```

**Supported keywords**: `self`, `unsafe-inline`, `unsafe-eval`, `none`, `strict-dynamic`, `unsafe-hashes`, `report-sample`, `unsafe-allow-redirects`, `wasm-unsafe-eval`

### URLs and Domains (Not Quoted)

URLs, domains, and schemes don't need quotes:

```python
app.csp(
    script_src=[
        "self",                          # → 'self'
        "https://cdn.jsdelivr.net",      # → https://cdn.jsdelivr.net
        "https://code.jquery.com"        # → https://code.jquery.com
    ],
    img_src=[
        "self",                          # → 'self'
        "data:",                         # → data:
        "*.example.com",                 # → *.example.com
        "https:"                         # → https:
    ]
)
```

### Already-Quoted Values (Preserved)

If you quote values yourself, RestMachine preserves them:

```python
app.csp(
    script_src=["'self'", "'unsafe-inline'"]  # Already quoted - preserved
)
```

### Nonces and Hashes (Auto-Quoted)

Nonces and hashes are automatically quoted:

```python
# When nonce=True, RestMachine generates: 'nonce-abc123xyz'
# When using hashes: 'sha256-...'
```

## Nonce Support

CSP nonces allow specific inline scripts/styles while blocking others - a powerful security pattern.

### Basic Nonce Usage

Enable nonces for inline scripts and styles:

```python
app = RestApplication()

@app.get("/page")
@app.csp(
    script_src=["self"],
    style_src=["self"],
    nonce=True  # Generate nonce for this route
)
def get_page(request):
    # Access the nonce in your handler
    nonce = request.csp_nonce

    return render_template(
        "page.html",
        csp_nonce=nonce  # Pass to template
    )
```

### Using Nonce in Templates

Jinja2 template example:

```html
<!DOCTYPE html>
<html>
<head>
    <!-- Inline style with nonce - allowed -->
    <style nonce="{{ csp_nonce }}">
        .special { color: red; }
    </style>

    <!-- Inline style without nonce - blocked by CSP -->
    <style>
        .blocked { color: blue; }
    </style>
</head>
<body>
    <!-- Inline script with nonce - allowed -->
    <script nonce="{{ csp_nonce }}">
        console.log("This works!");
    </script>

    <!-- Inline script without nonce - blocked by CSP -->
    <script>
        console.log("This is blocked!");
    </script>
</body>
</html>
```

### How Nonces Work

1. **Generation**: RestMachine generates a unique nonce per request (32-byte URL-safe string)
2. **Header**: Nonce is added to CSP header: `script-src 'self' 'nonce-abc123...'`
3. **Access**: Nonce is available as `request.csp_nonce` in handler
4. **Template**: Pass nonce to templates for inline script/style tags
5. **Validation**: Browser only executes inline code with matching nonce

**Security benefit**: Attackers can't guess the nonce, so injected scripts won't execute.

## Dynamic CSP with Providers

For complex scenarios where CSP needs to change per request:

```python
from restmachine import RestApplication
from restmachine.csp import CSPConfig

app = RestApplication()

@app.csp_provider
def get_csp_for_request(request):
    """Return different CSP based on request properties."""

    # Admin pages get stricter CSP
    if request.path.startswith("/admin"):
        return CSPConfig(
            default_src=["self"],
            script_src=["self"],
            style_src=["self"]
        )

    # Public pages can use CDNs
    if request.path.startswith("/public"):
        return CSPConfig(
            default_src=["self"],
            script_src=["self", "https://cdn.example.com"],
            style_src=["self", "unsafe-inline"]
        )

    # Default policy
    return CSPConfig(default_src=["self"])

@app.get("/admin/dashboard")
def admin_dashboard():
    return {"admin": True}

@app.get("/public/page")
def public_page():
    return {"public": True}
```

**Provider priority**: Provider → Route → Router → App (provider overrides all)

## Callable Sources

Sources can be callable functions for runtime determination:

```python
def get_allowed_cdns():
    """Load allowed CDNs from database or config."""
    return [
        "self",
        "https://cdn1.example.com",
        "https://cdn2.example.com"
    ]

app.csp(script_src=get_allowed_cdns)
```

The function is called when building each CSP header, allowing dynamic configuration.

## Report-Only Mode

Test CSP policies without blocking resources:

```python
app = RestApplication()

# Report violations but don't block
app.csp(
    default_src=["self"],
    script_src=["self"],
    report_only=True,              # Don't block, just report
    report_uri="/csp-violations"   # Where to send reports
)

@app.post("/csp-violations")
def handle_csp_report(body: dict):
    """Receive CSP violation reports."""
    logger.warning(f"CSP violation: {body}")
    return {"status": "received"}
```

**Use cases**:
- Testing new policies before enforcement
- Monitoring for CSP issues in production
- Gradual CSP rollout

## CSP Directives

RestMachine supports all major CSP directives:

### Fetch Directives

Control where resources can be loaded from:

```python
app.csp(
    default_src=["self"],              # Default for all fetch directives
    script_src=["self", "https://cdn.example.com"],
    style_src=["self", "unsafe-inline"],
    img_src=["self", "data:", "https:"],
    font_src=["self", "https://fonts.gstatic.com"],
    connect_src=["self", "https://api.example.com"],
    frame_src=["self", "https://www.youtube.com"],
    object_src=["none"],               # Block plugins
    media_src=["self", "https://media.example.com"],
    worker_src=["self"]                # Web workers
)
```

### Document Directives

Control document properties:

```python
app.csp(
    base_uri=["self"]  # Restrict <base> tag URLs
)
```

### Navigation Directives

Control form submissions:

```python
app.csp(
    form_action=["self", "https://external-form.com"]
)
```

## Common Patterns

### Pattern 1: Basic Security

Allow only same-origin resources:

```python
app.csp(default_src=["self"])
```

### Pattern 2: CDN Support

Allow resources from trusted CDNs:

```python
app.csp(
    default_src=["self"],
    script_src=["self", "https://cdn.jsdelivr.net"],
    style_src=["self", "https://cdn.jsdelivr.net"],
    font_src=["self", "https://fonts.gstatic.com"]
)
```

### Pattern 3: Third-Party Integrations

Allow specific third-party services:

```python
app.csp(
    default_src=["self"],
    script_src=[
        "self",
        "https://www.google-analytics.com",
        "https://www.googletagmanager.com"
    ],
    img_src=[
        "self",
        "data:",  # Data URIs for inline images
        "https://www.google-analytics.com"
    ],
    connect_src=[
        "self",
        "https://www.google-analytics.com"
    ]
)
```

### Pattern 4: Development Setup

Permissive for development with reporting:

```python
import os

app = RestApplication()

if os.getenv("ENV") == "development":
    app.csp(preset=CSPPreset.DEVELOPMENT)
else:
    app.csp(preset=CSPPreset.STRICT)
```

### Pattern 5: Inline Scripts with Nonces

Allow inline scripts safely:

```python
@app.get("/page")
@app.csp(
    script_src=["self"],
    style_src=["self"],
    nonce=True
)
def get_page(request):
    return render_template("page.html", csp_nonce=request.csp_nonce)
```

## Security Best Practices

### 1. Start Strict, Then Relax

Start with a strict policy and relax as needed:

```python
# Start with this
app.csp(default_src=["self"])

# If you need CDNs, add them specifically
app.csp(
    default_src=["self"],
    script_src=["self", "https://trusted-cdn.com"]
)
```

### 2. Avoid unsafe-inline

Use nonces instead of `unsafe-inline`:

```python
# ❌ Bad: Opens XSS vulnerabilities
app.csp(script_src=["self", "unsafe-inline"])

# ✅ Good: Use nonces
app.csp(script_src=["self"], nonce=True)
```

### 3. Test with Report-Only

Test policies before enforcement:

```python
# Phase 1: Test with report-only
app.csp(
    default_src=["self"],
    report_only=True,
    report_uri="/csp-violations"
)

# Phase 2: After testing, enforce
app.csp(default_src=["self"])
```

### 4. Block Object/Embed

Block plugins to prevent Flash/Java attacks:

```python
app.csp(
    default_src=["self"],
    object_src=["none"]  # Block plugins
)
```

### 5. Use HTTPS for CDNs

Always use HTTPS URLs for external resources:

```python
# ✅ Good
app.csp(script_src=["self", "https://cdn.example.com"])

# ❌ Bad: Allows HTTP (insecure)
app.csp(script_src=["self", "http://cdn.example.com"])
```

## Debugging CSP

### Browser Developer Tools

1. Open browser developer console
2. Look for CSP violation errors:
   ```
   Refused to load the script 'https://evil.com/script.js'
   because it violates the following Content Security Policy directive: "script-src 'self'"
   ```

### Report-Only Mode

Use report-only to see violations without blocking:

```python
app.csp(
    default_src=["self"],
    report_only=True,
    report_uri="/csp-violations"
)

@app.post("/csp-violations")
def log_violations(body: dict):
    print(f"CSP Violation: {body}")
    return {"ok": True}
```

### Common Issues

**Issue**: Inline styles/scripts blocked
**Solution**: Use nonces or move to external files

**Issue**: Third-party scripts blocked
**Solution**: Add their domain to script-src

**Issue**: Data URIs blocked
**Solution**: Add `data:` to img-src

**Issue**: WebSocket connections blocked
**Solution**: Add WebSocket URL to connect-src

## Migration from Other Frameworks

### From Flask-Talisman

```python
# Flask-Talisman
talisman = Talisman(
    app,
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", 'https://cdn.com']
    }
)

# RestMachine (no manual quoting needed!)
app.csp(
    default_src=["self"],
    script_src=["self", "https://cdn.com"]
)
```

### From Django CSP

```python
# Django settings.py
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://cdn.com")

# RestMachine
app.csp(
    default_src=["self"],
    script_src=["self", "https://cdn.com"]
)
```

## Additional Resources

- [MDN: Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [CSP Quick Reference](https://content-security-policy.com/)
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/) - Test your policies
- [Report URI](https://report-uri.com/) - CSP violation reporting service

## Summary

RestMachine's CSP support provides:

✅ **Auto-quoting** - No manual quoting of keywords
✅ **Nonce generation** - Secure inline scripts/styles
✅ **Presets** - Quick security levels
✅ **Flexible configuration** - App/router/route levels
✅ **Dynamic policies** - CSP providers and callable sources
✅ **Report-only mode** - Test before enforcing
✅ **Best practices** - Built-in security patterns

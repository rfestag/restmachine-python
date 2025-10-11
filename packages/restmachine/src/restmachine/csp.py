"""Content Security Policy (CSP) support for RestMachine.

This module provides auto-quoting CSP configuration with support for:
- Automatic quoting of CSP keywords ('self', 'unsafe-inline', etc.)
- URL and domain handling (no quotes needed)
- Nonce generation for inline scripts/styles
- Report-only mode for testing
- Pre-configured security presets
"""

from dataclasses import dataclass
from typing import List, Optional, Callable, Union


@dataclass
class CSPConfig:
    """Content Security Policy configuration with auto-quoting.

    CSP keywords (self, unsafe-inline, etc.) are automatically quoted.
    URLs and domains don't need quotes - just pass them as-is.

    Examples:
        # Simple protection
        CSPConfig(default_src=["self"])

        # CDN support (no manual quoting!)
        CSPConfig(
            script_src=["self", "https://cdn.jsdelivr.net"],
            style_src=["self", "unsafe-inline"]  # Keywords auto-quoted
        )

        # Data URIs and wildcards
        CSPConfig(
            img_src=["self", "data:", "*.example.com"],
            font_src=["self", "https://fonts.gstatic.com"]
        )

        # Block everything except self
        CSPConfig(
            default_src=["self"],
            object_src=["none"]  # Plugins blocked
        )

    Note:
        Keywords like 'self', 'unsafe-inline' are auto-quoted.
        URLs like https://cdn.com need no quotes.
        Already-quoted values are preserved.
    """

    # CSP keywords that need single quotes
    KEYWORDS = {
        'self', 'unsafe-inline', 'unsafe-eval', 'none',
        'strict-dynamic', 'unsafe-hashes', 'report-sample',
        'unsafe-allow-redirects', 'wasm-unsafe-eval'
    }

    # Fetch directives
    default_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    script_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    style_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    img_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    font_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    connect_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    frame_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    object_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    media_src: Optional[Union[List[str], Callable[[], List[str]]]] = None
    worker_src: Optional[Union[List[str], Callable[[], List[str]]]] = None

    # Document directives
    base_uri: Optional[Union[List[str], Callable[[], List[str]]]] = None

    # Navigation directives
    form_action: Optional[Union[List[str], Callable[[], List[str]]]] = None

    # Special options
    nonce: bool = False  # Auto-generate 'nonce-xxx' for script/style-src
    report_uri: Optional[str] = None  # Violation report endpoint
    report_only: bool = False  # Use Content-Security-Policy-Report-Only

    @staticmethod
    def _quote_source(source: str) -> str:
        """Auto-quote CSP sources based on type.

        Args:
            source: Raw source value from user

        Returns:
            Properly quoted CSP source

        Examples:
            >>> CSPConfig._quote_source("self")
            "'self'"
            >>> CSPConfig._quote_source("https://cdn.com")
            "https://cdn.com"
            >>> CSPConfig._quote_source("'self'")  # Already quoted
            "'self'"
        """
        # Already quoted - leave it
        if source.startswith("'") and source.endswith("'"):
            return source

        # Nonce/hash format - quote it
        if source.startswith("nonce-") or source.startswith("sha"):
            return f"'{source}'"

        # Known keyword - quote it
        if source.lower() in CSPConfig.KEYWORDS:
            return f"'{source}'"

        # URL, scheme, or domain - no quotes
        return source

    @staticmethod
    def _resolve_sources(sources: Union[List[str], Callable[[], List[str]]]) -> List[str]:
        """Resolve sources (may be callable)."""
        if callable(sources):
            return sources()
        return sources

    def _build_directive(self, name: str, sources: Union[List[str], Callable[[], List[str]]], nonce_value: Optional[str] = None) -> str:
        """Build a single CSP directive.

        Args:
            name: Directive name (e.g., "script-src")
            sources: List of source values or callable returning list
            nonce_value: Optional nonce to append

        Returns:
            Formatted directive string
        """
        resolved_sources = self._resolve_sources(sources)
        quoted_sources = [self._quote_source(s) for s in resolved_sources]

        # Add nonce if applicable and provided
        if nonce_value and name in ('script-src', 'style-src'):
            quoted_sources.append(f"'nonce-{nonce_value}'")

        return f"{name} {' '.join(quoted_sources)}"

    def build_header(self, nonce_value: Optional[str] = None) -> str:
        """Build CSP header value.

        Args:
            nonce_value: Optional nonce for inline scripts/styles

        Returns:
            Complete CSP header value
        """
        directives = []

        if self.default_src:
            directives.append(self._build_directive("default-src", self.default_src))

        if self.script_src:
            directives.append(self._build_directive("script-src", self.script_src, nonce_value if self.nonce else None))

        if self.style_src:
            directives.append(self._build_directive("style-src", self.style_src, nonce_value if self.nonce else None))

        if self.img_src:
            directives.append(self._build_directive("img-src", self.img_src))

        if self.font_src:
            directives.append(self._build_directive("font-src", self.font_src))

        if self.connect_src:
            directives.append(self._build_directive("connect-src", self.connect_src))

        if self.frame_src:
            directives.append(self._build_directive("frame-src", self.frame_src))

        if self.object_src:
            directives.append(self._build_directive("object-src", self.object_src))

        if self.media_src:
            directives.append(self._build_directive("media-src", self.media_src))

        if self.worker_src:
            directives.append(self._build_directive("worker-src", self.worker_src))

        if self.base_uri:
            directives.append(self._build_directive("base-uri", self.base_uri))

        if self.form_action:
            directives.append(self._build_directive("form-action", self.form_action))

        if self.report_uri:
            directives.append(f"report-uri {self.report_uri}")

        return "; ".join(directives)

    def header_name(self) -> str:
        """Get appropriate header name."""
        if self.report_only:
            return "Content-Security-Policy-Report-Only"
        return "Content-Security-Policy"


class CSPPreset:
    """Pre-configured CSP security presets."""

    # Strict security - blocks most external resources
    STRICT = CSPConfig(
        default_src=["self"],
        object_src=["none"],
        base_uri=["self"],
        form_action=["self"]
    )

    # Basic protection - allows self only
    BASIC = CSPConfig(
        default_src=["self"]
    )

    # Relaxed - allows inline styles (common in many apps)
    RELAXED = CSPConfig(
        default_src=["self"],
        style_src=["self", "unsafe-inline"],
        img_src=["self", "data:", "https:"]
    )

    # Development - very permissive with reporting
    DEVELOPMENT = CSPConfig(
        default_src=["self"],
        script_src=["self", "unsafe-inline", "unsafe-eval"],
        style_src=["self", "unsafe-inline"],
        report_only=True
    )

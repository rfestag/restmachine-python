"""CORS (Cross-Origin Resource Sharing) support for RestMachine.

Provides decorators and configuration for handling CORS preflight requests
and adding appropriate CORS headers to responses.

References:
- RFC 6454: The Web Origin Concept
- WHATWG Fetch Standard: https://fetch.spec.whatwg.org/
- MDN CORS: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .router import Router


@dataclass
class CORSConfig:
    """Configuration for CORS (Cross-Origin Resource Sharing).

    Attributes:
        origins: List of allowed origins or "*" for all origins.
                 Examples: ["https://app.example.com", "https://admin.example.com"]

        methods: Optional list of allowed HTTP methods. If None, auto-detects from registered routes.
                 Examples: ["GET", "POST", "PUT"] or None (auto-detect)

        allow_headers: Request headers that can be used in actual request.
                      Defaults to common headers browsers send.
                      Use ["*"] to allow all headers.

        expose_headers: Response headers that JavaScript can access.
                       Defaults to headers commonly needed by clients.

        credentials: Whether to allow credentials (cookies, authorization headers).
                    When True, origins cannot be "*" (security requirement),
                    unless reflect_any_origin is enabled.

        max_age: How long (seconds) browser can cache preflight response.
                Defaults to 24 hours (86400 seconds).

        reflect_any_origin: Allow reflecting any origin with credentials (for development).
                          When True, allows using origins="*" with credentials=True by
                          reflecting the request's Origin header in the response instead
                          of sending a literal "*". Useful for development environments
                          where you want to support credentials from any origin.
                          WARNING: Only use in development! In production, specify explicit origins.

    Examples:
        # Minimal - auto-detect methods, use defaults
        CORSConfig(origins=["https://app.example.com"])

        # Common configuration
        CORSConfig(
            origins=["https://app.example.com"],
            credentials=True,
            expose_headers=["X-Request-ID"]
        )

        # Development - allow any origin with credentials (reflects origin)
        CORSConfig(
            origins="*",
            credentials=True,
            reflect_any_origin=True  # WARNING: Development only!
        )

        # Explicit method restriction
        CORSConfig(
            origins=["*"],
            methods=["GET", "POST"],  # Only allow GET/POST
            allow_headers=["*"]
        )
    """

    origins: Union[List[str], Literal["*"]]

    # Auto-detect from routes if None
    methods: Optional[List[str]] = None

    # Smart defaults for common use cases
    # Allow common headers browsers send
    allow_headers: List[str] = field(default_factory=lambda: [
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Content-Language",
        "Authorization",
        "X-Requested-With",
    ])

    # Expose headers clients commonly need
    expose_headers: List[str] = field(default_factory=lambda: [
        "Content-Length",
        "Content-Type",
        "ETag",
        "Location",
        "X-Request-ID",
    ])

    credentials: bool = False

    # 24 hours in seconds
    max_age: int = 86400

    # Allow reflecting any origin with credentials (useful for development)
    # When True, allows origins="*" with credentials=True
    # WARNING: Only use in development! In production, specify explicit origins.
    reflect_any_origin: bool = False

    def matches_origin(self, origin: str) -> bool:
        """Check if the given origin is allowed.

        Args:
            origin: Origin header from request (e.g., "https://app.example.com")

        Returns:
            True if origin is allowed, False otherwise
        """
        if self.origins == "*":
            return True
        return origin in self.origins

    def get_allowed_methods(self, path: str, router: 'Router') -> List[str]:
        """Get allowed methods - manual override or auto-detected from routes.

        Args:
            path: Request path (e.g., "/users/123")
            router: Router instance to introspect routes

        Returns:
            List of allowed HTTP method strings (e.g., ["GET", "POST", "OPTIONS"])
        """
        if self.methods is not None:
            # User explicitly set methods - use those
            return self.methods

        # Auto-detect from registered routes
        detected_methods = router.get_methods_for_path(path)
        return [m.value for m in detected_methods]

    def validate(self) -> None:
        """Validate CORS configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        # Security: Cannot use wildcard origin with credentials
        # UNLESS reflect_any_origin is explicitly enabled
        if self.credentials and self.origins == "*" and not self.reflect_any_origin:
            raise ValueError(
                "CORS: Cannot use wildcard origin '*' with credentials=True. "
                "Specify explicit origins when allowing credentials, or set "
                "reflect_any_origin=True for development environments."
            )

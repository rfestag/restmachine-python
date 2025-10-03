"""
Error response models for the REST framework.
"""

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict  # type: ignore[import-not-found]

    PYDANTIC_AVAILABLE = True

    class ErrorResponse(BaseModel):
        """Standard error response model.

        This model represents the structure of error responses returned by the framework.
        It includes an error message, optional validation details, and tracking identifiers.
        """

        model_config = ConfigDict(
            json_schema_extra={
                "example": {
                    "error": "Validation failed",
                    "details": [
                        {
                            "type": "missing",
                            "loc": ["body", "name"],
                            "msg": "Field required",
                            "input": {}
                        }
                    ],
                    "request_id": "req-123456",
                    "trace_id": "trace-abc-def"
                }
            }
        )

        error: str = Field(
            ...,
            description="Human-readable error message describing what went wrong"
        )

        details: Optional[List[Dict[str, Any]]] = Field(
            None,
            description="Detailed validation errors following the Pydantic error schema"
        )

        request_id: Optional[str] = Field(
            None,
            description="Unique identifier for this specific request"
        )

        trace_id: Optional[str] = Field(
            None,
            description="Trace identifier for distributed tracing across services"
        )

        def model_dump_json(self, **kwargs):
            """Override to set include_url=False for validation error details by default."""
            # Ensure exclude_none is True by default for cleaner responses
            kwargs.setdefault('exclude_none', True)
            return super().model_dump_json(**kwargs)

        @classmethod
        def from_validation_error(
            cls,
            error: Any,
            message: str = "Validation failed",
            request_id: Optional[str] = None,
            trace_id: Optional[str] = None
        ) -> "ErrorResponse":
            """Create an ErrorResponse from a Pydantic ValidationError.

            Args:
                error: The Pydantic ValidationError instance
                message: Custom error message (defaults to "Validation failed")
                request_id: Optional request identifier
                trace_id: Optional trace identifier

            Returns:
                ErrorResponse instance with validation details
            """
            # Get errors with include_url=False to exclude URLs from the error details
            details = error.errors(include_url=False) if hasattr(error, 'errors') else None
            return cls(
                error=message,
                details=details,
                request_id=request_id,
                trace_id=trace_id
            )

except ImportError:
    PYDANTIC_AVAILABLE = False

    class ErrorResponse:  # type: ignore[no-redef]
        """Fallback ErrorResponse when Pydantic is not available."""

        def __init__(
            self,
            error: str,
            details: Optional[List[Dict[str, Any]]] = None,
            request_id: Optional[str] = None,
            trace_id: Optional[str] = None
        ):
            self.error = error
            self.details = details
            self.request_id = request_id
            self.trace_id = trace_id

        def model_dump_json(self, **kwargs):
            """Serialize to JSON string."""
            import json
            data: Dict[str, Any] = {"error": self.error}
            if self.details is not None:
                data["details"] = self.details
            if self.request_id is not None:
                data["request_id"] = self.request_id
            if self.trace_id is not None:
                data["trace_id"] = self.trace_id
            return json.dumps(data)

        def model_dump(self, **kwargs):
            """Serialize to dict."""
            exclude_none = kwargs.get('exclude_none', True)
            data: Dict[str, Any] = {"error": self.error}
            if self.details is not None or not exclude_none:
                if self.details is not None or not exclude_none:
                    data["details"] = self.details
            if self.request_id is not None or not exclude_none:
                if self.request_id is not None or not exclude_none:
                    data["request_id"] = self.request_id
            if self.trace_id is not None or not exclude_none:
                if self.trace_id is not None or not exclude_none:
                    data["trace_id"] = self.trace_id
            return data

        @classmethod
        def from_validation_error(
            cls,
            error: Any,
            message: str = "Validation failed",
            request_id: Optional[str] = None,
            trace_id: Optional[str] = None
        ):
            """Create an ErrorResponse from a validation error."""
            details = error.errors() if hasattr(error, 'errors') else None
            return cls(
                error=message,
                details=details,
                request_id=request_id,
                trace_id=trace_id
            )
"""
Webmachine-inspired state machine for HTTP request processing.
"""

import inspect
import json
import logging
from datetime import datetime
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional, Union, get_origin, get_args

from .content_renderers import ContentRenderer
from .dependencies import DependencyWrapper
from .error_models import ErrorResponse
from .exceptions import PYDANTIC_AVAILABLE, ValidationError, AcceptsParsingError
from .models import HTTPMethod, Request, Response, etags_match

# Set up logger for this module
logger = logging.getLogger(__name__)


class StateMachineResult:
    """Result from a state machine decision point."""

    def __init__(self, continue_processing: bool, response: Optional[Response] = None):
        self.continue_processing = continue_processing
        self.response = response


class RequestStateMachine:
    """Webmachine-like state machine for processing HTTP requests."""
    request: Request
    chosen_renderer: ContentRenderer

    def __init__(self, app):
        self.app = app
        self.route_handler = None
        self.handler_dependencies: List[str] = []
        self.dependency_callbacks: Dict[str, DependencyWrapper] = {}
        self.handler_result: Any = None

    def _create_error_response(self, status_code: int, message: str, details=None, **kwargs) -> Response:
        """Create an error response respecting content negotiation.

        Args:
            status_code: HTTP status code
            message: Error message
            details: Optional validation error details (follows Pydantic error schema)
            **kwargs: Additional Response parameters (headers, etc.)

        Returns:
            Response object formatted according to Accept header
        """
        # Check Accept header to determine response format
        accept_header = self.request.get_accept_header() if hasattr(self, 'request') else ""

        # Check if there are custom error handlers registered
        if self.app._error_handlers:
            # Find handlers that match this status code
            matching_handlers = [
                h for h in self.app._error_handlers
                if h.handles_status(status_code)
            ]

            if matching_handlers:
                # Try to find content-type-specific handler first
                content_specific = None
                default_handler = None

                for handler in matching_handlers:
                    if handler.content_type:
                        # This is a content-type-specific handler
                        if handler.matches_accept(accept_header):
                            content_specific = handler
                            break
                    else:
                        # This is a default handler (no content type specified)
                        default_handler = handler

                # Use content-specific handler if found, otherwise use default
                chosen_handler = content_specific or default_handler

                if chosen_handler:
                    try:
                        # Call the error handler with dependency injection
                        result = self.app._call_with_injection(
                            chosen_handler.handler, self.request, self.route_handler
                        )

                        # Convert result to Response if not already
                        if isinstance(result, Response):
                            return result
                        elif isinstance(result, dict):
                            # Return as JSON
                            return Response(
                                status_code,
                                json.dumps(result),
                                content_type=chosen_handler.content_type or "application/json",
                                **kwargs
                            )
                        elif isinstance(result, str):
                            # Return as text
                            return Response(
                                status_code,
                                result,
                                content_type=chosen_handler.content_type or "text/plain",
                                **kwargs
                            )
                        else:
                            # Try to serialize as JSON
                            return Response(
                                status_code,
                                json.dumps(result),
                                content_type=chosen_handler.content_type or "application/json",
                                **kwargs
                            )
                    except Exception as e:
                        # If custom handler fails, log and fall back to default
                        logger.error(f"Error in custom error handler: {e}")
                        # Fall through to default behavior

        # Default error response behavior (no custom handler or handler failed)
        # Get request_id and trace_id using dependency resolution
        request_id = None
        trace_id = None
        try:
            request_id = self.app._resolve_builtin_dependency("request_id", None, self.request, self.route_handler)
            trace_id = self.app._resolve_builtin_dependency("trace_id", None, self.request, self.route_handler)
        except Exception as e:
            # If dependency resolution fails, continue without IDs
            logger.warning(f"Failed to resolve request_id/trace_id for error response: {e}")

        # Determine if client wants JSON
        prefers_json = False
        if accept_header:
            # Simple check: if application/json is explicitly requested or */* is used
            if "application/json" in accept_header or "*/*" in accept_header:
                prefers_json = True
            elif "text/plain" in accept_header:
                prefers_json = False
            else:
                # Default to JSON for common browsers/APIs
                prefers_json = True
        else:
            # No Accept header - default to JSON for RESTful APIs
            prefers_json = True

        if prefers_json:
            # Return JSON error response using ErrorResponse model
            error_response = ErrorResponse(
                error=message,
                details=details,
                request_id=request_id,
                trace_id=trace_id
            )
            return Response(
                status_code,
                error_response.model_dump_json(),
                content_type="application/json",
                **kwargs
            )
        else:
            # Return plain text error response
            return Response(
                status_code,
                message,
                content_type="text/plain",
                **kwargs
            )

    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine."""
        self.request = request
        self.app._dependency_cache.clear()

        logger.debug(f"Starting state machine processing for {request.method.value} {request.path}")

        def log_state_transition(state_name: str, result: StateMachineResult):
            """Helper to log state transitions with debug info."""
            status = "CONTINUE" if result.continue_processing else "STOP"
            response_code = result.response.status_code if result.response else "None"
            logger.debug(f"State {state_name}: {status} (response: {response_code})")

        # This should never actually be returned, but we include it here
        # in case a bug is intorduced where we choose not to continue processing,
        # but also fail to provide a response
        default_response = Response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            json.dumps({"error": "Unexpected error occured."}),
            content_type="application/json",
        )
        try:
            # State machine flow - all wrapped in try-catch for ValidationError
            result = self.state_route_exists()
            log_state_transition("route_exists", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_service_available()
            log_state_transition("service_available", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_known_method()
            log_state_transition("known_method", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_uri_too_long()
            log_state_transition("uri_too_long", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_method_allowed()
            log_state_transition("method_allowed", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_malformed_request()
            log_state_transition("malformed_request", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_authorized()
            log_state_transition("authorized", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_forbidden()
            log_state_transition("forbidden", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_content_headers_valid()
            log_state_transition("content_headers_valid", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_resource_exists()
            log_state_transition("resource_exists", result)
            if not result.continue_processing:
                return result.response or default_response

            # Conditional request processing states
            result = self.state_if_match()
            log_state_transition("if_match", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_if_unmodified_since()
            log_state_transition("if_unmodified_since", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_if_none_match()
            log_state_transition("if_none_match", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_if_modified_since()
            log_state_transition("if_modified_since", result)
            if not result.continue_processing:
                return result.response or default_response

            # Content negotiation states
            result = self.state_content_types_provided()
            log_state_transition("content_types_provided", result)
            if not result.continue_processing:
                return result.response or default_response

            result = self.state_content_types_accepted()
            log_state_transition("content_types_accepted", result)
            if not result.continue_processing:
                return result.response or default_response

            logger.debug("All state checks passed, executing handler and rendering response")
            return self.state_execute_and_render()

        except ValidationError as e:
            logger.warning(f"Validation error in request processing: {e}")
            # Get request_id and trace_id
            request_id = None
            trace_id = None
            try:
                request_id = self.app._resolve_builtin_dependency("request_id", None, self.request, self.route_handler)
                trace_id = self.app._resolve_builtin_dependency("trace_id", None, self.request, self.route_handler)
            except Exception as dep_error:
                logger.warning(f"Failed to resolve request_id/trace_id for validation error: {dep_error}")

            error_response = ErrorResponse.from_validation_error(
                e,
                message="Validation failed",
                request_id=request_id,
                trace_id=trace_id
            )
            return Response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                error_response.model_dump_json(),
                content_type="application/json",
            )

    def state_route_exists(self) -> StateMachineResult:
        """B13: Check if route exists."""
        route_match = self.app._find_route(self.request.method, self.request.path)
        if route_match is None:
            # Check if ANY route exists for this path (regardless of method)
            if self.app._path_has_routes(self.request.path):
                # Route exists but method not allowed -> HTTPStatus.METHOD_NOT_ALLOWED
                return StateMachineResult(False, self._create_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed"))

            # No route exists at all for this path -> HTTPStatus.NOT_FOUND
            callback = self._get_callback("route_not_found")
            if callback:
                try:
                    response = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if isinstance(response, Response):
                        return StateMachineResult(False, response)
                    return StateMachineResult(
                        False, self._create_error_response(HTTPStatus.NOT_FOUND, str(response) if response else "Not Found")
                    )
                except Exception as e:
                    logger.error(f"Error in route_not_found callback for {self.request.method.value} {self.request.path}: {e}")
                    self.app._dependency_cache.set("exception", e)
                    return StateMachineResult(
                        False,
                        self._create_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error in route_not_found callback: {str(e)}"),
                    )
            return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found"))

        self.route_handler, path_params = route_match
        self.request.path_params = path_params

        # Analyze handler dependencies
        sig = inspect.signature(self.route_handler.handler)
        self.handler_dependencies = list(sig.parameters.keys())

        # Find dependency callbacks that will be used - check route-specific first, then global
        for dep_name in self.handler_dependencies:
            # Check route-specific dependencies first
            if dep_name in self.route_handler.dependencies:
                dep = self.route_handler.dependencies[dep_name]
                if isinstance(dep, DependencyWrapper):
                    self.dependency_callbacks[dep.state_name] = dep
            # Fall back to global dependencies
            elif dep_name in self.app._dependencies:
                dep = self.app._dependencies[dep_name]
                if isinstance(dep, DependencyWrapper):
                    self.dependency_callbacks[dep.state_name] = dep

        return StateMachineResult(True)

    def state_service_available(self) -> StateMachineResult:
        """B12: Check if service is available."""
        callback = self._get_callback("service_available")
        if callback:
            try:
                available = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not available:
                    return StateMachineResult(
                        False, self._create_error_response(HTTPStatus.SERVICE_UNAVAILABLE, "Service Unavailable")
                    )
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.SERVICE_UNAVAILABLE, f"Service check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_known_method(self) -> StateMachineResult:
        """B11: Check if HTTP method is known."""
        callback = self._get_callback("known_method")
        if callback:
            try:
                known = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not known:
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_IMPLEMENTED, "Not Implemented"))
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.NOT_IMPLEMENTED, f"Method check failed: {str(e)}")
                )
        else:
            # Default: check if method is in our known methods
            known_methods = {
                HTTPMethod.GET,
                HTTPMethod.POST,
                HTTPMethod.PUT,
                HTTPMethod.DELETE,
                HTTPMethod.PATCH,
            }
            if self.request.method not in known_methods:
                return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_IMPLEMENTED, "Not Implemented"))
        return StateMachineResult(True)

    def state_uri_too_long(self) -> StateMachineResult:
        """B10: Check if URI is too long."""
        callback = self._get_callback("uri_too_long")
        if callback:
            try:
                too_long = self.app._call_with_injection(callback, self.request, self.route_handler)
                if too_long:
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.REQUEST_URI_TOO_LONG, "URI Too Long"))
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.REQUEST_URI_TOO_LONG, f"URI length check failed: {str(e)}")
                )
        else:
            # Default: check if URI is longer than 2048 characters
            if len(self.request.path) > 2048:
                return StateMachineResult(False, self._create_error_response(HTTPStatus.REQUEST_URI_TOO_LONG, "URI Too Long"))
        return StateMachineResult(True)

    def state_method_allowed(self) -> StateMachineResult:
        """B9: Check if method is allowed for this resource."""
        callback = self._get_callback("method_allowed")
        if callback:
            try:
                allowed = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not allowed:
                    return StateMachineResult(
                        False, self._create_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed")
                    )
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.METHOD_NOT_ALLOWED, f"Method check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_malformed_request(self) -> StateMachineResult:
        """B8: Check if request is malformed."""
        callback = self._get_callback("malformed_request")
        if callback:
            try:
                malformed = self.app._call_with_injection(callback, self.request, self.route_handler)
                if malformed:
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.BAD_REQUEST, "Bad Request"))
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.BAD_REQUEST, f"Request validation failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_authorized(self) -> StateMachineResult:
        """B7: Check if request is authorized."""
        callback = self._get_callback("authorized")
        if callback:
            try:
                authorized = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not authorized:
                    logger.error(f"Authorization failed for {self.request.method.value} {self.request.path}")
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.UNAUTHORIZED, "Unauthorized"))
            except Exception as e:
                logger.error(f"Authorization check exception for {self.request.method.value} {self.request.path}: {e}")
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.UNAUTHORIZED, f"Authorization check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_forbidden(self) -> StateMachineResult:
        """B6: Check if request is forbidden."""
        callback = self._get_callback("forbidden")
        if callback:
            try:
                # For wrapped dependencies, we need to resolve the dependency
                # and check if it indicates forbidden access
                if "forbidden" in self.dependency_callbacks:
                    wrapper = self.dependency_callbacks["forbidden"]
                    try:
                        resolved_value = self.app._call_with_injection(
                            wrapper.func, self.request, self.route_handler
                        )
                        if resolved_value is None:
                            logger.error(f"Access forbidden for {self.request.method.value} {self.request.path}")
                            return StateMachineResult(False, self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden"))
                    except Exception as e:
                        logger.error(f"Forbidden check exception for {self.request.method.value} {self.request.path}: {e}")
                        self.app._dependency_cache.set("exception", e)
                        return StateMachineResult(False, self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden"))
                else:
                    # Use the regular callback
                    forbidden = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if forbidden:
                        logger.error(f"Access forbidden for {self.request.method.value} {self.request.path}")
                        return StateMachineResult(False, self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden"))
            except Exception as e:
                logger.error(f"Permission check exception for {self.request.method.value} {self.request.path}: {e}")
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.FORBIDDEN, f"Permission check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_content_headers_valid(self) -> StateMachineResult:
        """B5: Check if content headers are valid."""
        callback = self._get_callback("content_headers_valid")
        if callback:
            try:
                valid = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not valid:
                    return StateMachineResult(
                        False, self._create_error_response(HTTPStatus.BAD_REQUEST, "Bad Request - Invalid Headers")
                    )
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.BAD_REQUEST, f"Header validation failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_resource_exists(self) -> StateMachineResult:
        """G7: Check if resource exists."""
        callback = self._get_callback("resource_exists")
        if callback:
            try:
                # For wrapped dependencies, we need to resolve the dependency
                # and check if it returns None (indicating resource doesn't exist)
                if "resource_exists" in self.dependency_callbacks:
                    wrapper = self.dependency_callbacks["resource_exists"]
                    try:
                        resolved_value = self.app._call_with_injection(
                            wrapper.func, self.request, self.route_handler
                        )
                        if resolved_value is None:
                            # Resource doesn't exist - check if we can create it from request (for POST)
                            if self.request.method == HTTPMethod.POST:
                                return self._try_resource_from_request()
                            return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found"))
                        # Cache the resolved value for later use in the handler
                        self.app._dependency_cache.set(
                            wrapper.original_name, resolved_value
                        )
                    except Exception:
                        # Resource doesn't exist - check if we can create it from request (for POST)
                        if self.request.method == HTTPMethod.POST:
                            return self._try_resource_from_request()
                        return StateMachineResult(
                            False, self._create_error_response(HTTPStatus.NOT_FOUND, "Resource Not Found")
                        )
                else:
                    # Use the regular callback
                    exists = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if not exists:
                        # Resource doesn't exist - check if we can create it from request (for POST)
                        if self.request.method == HTTPMethod.POST:
                            return self._try_resource_from_request()
                        return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found"))
            except Exception as e:
                # Resource doesn't exist - check if we can create it from request (for POST)
                if self.request.method == HTTPMethod.POST:
                    return self._try_resource_from_request()
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.NOT_FOUND, f"Resource check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def _try_resource_from_request(self) -> StateMachineResult:
        """Try to create resource from request for POST operations."""
        # Check if there's a resource_from_request callback
        if "resource_from_request" in self.dependency_callbacks:
            wrapper = self.dependency_callbacks["resource_from_request"]
            try:
                # Call the resource_from_request function to create the resource
                resolved_value = self.app._call_with_injection(
                    wrapper.func, self.request, self.route_handler
                )
                if resolved_value is not None:
                    # Cache the created resource value for later use in the handler
                    # Use the same name as the resource_exists dependency
                    if "resource_exists" in self.dependency_callbacks:
                        resource_exists_wrapper = self.dependency_callbacks["resource_exists"]
                        self.app._dependency_cache.set(
                            resource_exists_wrapper.original_name, resolved_value
                        )
                    # Continue processing (resource now "exists" from the request)
                    return StateMachineResult(True)
                else:
                    # resource_from_request returned None, can't create resource
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.BAD_REQUEST, "Bad Request"))
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return StateMachineResult(
                    False, self._create_error_response(HTTPStatus.BAD_REQUEST, f"Resource creation failed: {str(e)}")
                )

        # No resource_from_request callback available
        return StateMachineResult(False, self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found"))

    def state_if_match(self) -> StateMachineResult:
        """Check If-Match precondition (RFC 7232)."""
        if_match_etags = self.request.get_if_match()
        if not if_match_etags:
            return StateMachineResult(True)

        # Get current resource ETag
        current_etag = self._get_resource_etag()
        if not current_etag:
            # If resource doesn't have an ETag, If-Match fails
            return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

        # Special case: If-Match: *
        if "*" in if_match_etags:
            # Resource exists (we checked earlier), so * matches
            return StateMachineResult(True)

        # Check if current ETag matches any of the requested ETags
        for requested_etag in if_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=True):
                return StateMachineResult(True)

        # No ETag matches
        return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

    def state_if_unmodified_since(self) -> StateMachineResult:
        """Check If-Unmodified-Since precondition (RFC 7232)."""
        if_unmodified_since = self.request.get_if_unmodified_since()
        if not if_unmodified_since:
            return StateMachineResult(True)

        # Get current resource last modified time
        last_modified = self._get_resource_last_modified()
        if not last_modified:
            # If resource doesn't have a Last-Modified date, precondition fails
            return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

        # Check if resource was modified after the If-Unmodified-Since date
        if last_modified > if_unmodified_since:
            return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

        return StateMachineResult(True)

    def state_if_none_match(self) -> StateMachineResult:
        """Check If-None-Match precondition (RFC 7232)."""
        if_none_match_etags = self.request.get_if_none_match()
        if not if_none_match_etags:
            return StateMachineResult(True)

        # Get current resource ETag
        current_etag = self._get_resource_etag()

        # Special case: If-None-Match: *
        if "*" in if_none_match_etags:
            # Resource exists, so * matches - return HTTPStatus.NOT_MODIFIED for GET/HEAD, HTTPStatus.PRECONDITION_FAILED for others
            if self.request.method in [HTTPMethod.GET]:
                return StateMachineResult(False, Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag} if current_etag else {}))
            else:
                return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

        # If resource doesn't have an ETag, If-None-Match succeeds
        if not current_etag:
            return StateMachineResult(True)

        # Check if current ETag matches any of the requested ETags (weak comparison for If-None-Match)
        for requested_etag in if_none_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=False):
                # ETag matches - return HTTPStatus.NOT_MODIFIED for GET/HEAD, HTTPStatus.PRECONDITION_FAILED for others
                if self.request.method in [HTTPMethod.GET]:
                    return StateMachineResult(False, Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag}))
                else:
                    return StateMachineResult(False, self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed"))

        # No ETag matches, continue processing
        return StateMachineResult(True)

    def state_if_modified_since(self) -> StateMachineResult:
        """Check If-Modified-Since precondition (RFC 7232)."""
        # If-Modified-Since is only evaluated for GET requests
        if self.request.method != HTTPMethod.GET:
            return StateMachineResult(True)

        if_modified_since = self.request.get_if_modified_since()
        if not if_modified_since:
            return StateMachineResult(True)

        # Get current resource last modified time
        last_modified = self._get_resource_last_modified()
        if not last_modified:
            # If resource doesn't have a Last-Modified date, assume it's been modified
            return StateMachineResult(True)

        # Check if resource was modified after the If-Modified-Since date
        if last_modified <= if_modified_since:
            # Resource hasn't been modified, return HTTPStatus.NOT_MODIFIED
            headers = {}
            if last_modified:
                headers["Last-Modified"] = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
            current_etag = self._get_resource_etag()
            if current_etag:
                headers["ETag"] = current_etag
            return StateMachineResult(False, Response(HTTPStatus.NOT_MODIFIED, headers=headers))

        return StateMachineResult(True)

    def _get_resource_etag(self) -> Optional[str]:
        """Get the current ETag for the resource.

        This checks for ETag callbacks or dependencies that provide the resource ETag.
        """
        # Check for ETag callback
        callback = self._get_callback("generate_etag")
        if callback:
            try:
                etag = self.app._call_with_injection(callback, self.request, self.route_handler)
                if etag:
                    return f'"{etag}"' if not etag.startswith('"') and not etag.startswith('W/') else etag
            except Exception as e:
                # ETag generation failed, continue gracefully without ETag
                logger.warning(f"ETag generation callback failed: {e}")
                pass

        # Check for ETag dependency
        if "generate_etag" in self.dependency_callbacks:
            wrapper = self.dependency_callbacks["generate_etag"]
            try:
                etag = self.app._call_with_injection(wrapper.func, self.request, self.route_handler)
                if etag:
                    return f'"{etag}"' if not etag.startswith('"') and not etag.startswith('W/') else etag
            except Exception as e:
                # ETag dependency injection failed, continue gracefully without ETag
                logger.warning(f"ETag dependency injection failed: {e}")
                pass

        return None

    def _get_resource_last_modified(self) -> Optional['datetime']:
        """Get the current Last-Modified date for the resource.

        This checks for Last-Modified callbacks or dependencies.
        """

        # Check for Last-Modified callback
        callback = self._get_callback("last_modified")
        if callback:
            try:
                last_modified = self.app._call_with_injection(callback, self.request, self.route_handler)
                if isinstance(last_modified, datetime):
                    return last_modified
                elif isinstance(last_modified, str):
                    # Try to parse as HTTP date
                    try:
                        return datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
                    except ValueError:
                        pass
            except Exception as e:
                # Last-Modified callback failed, continue gracefully without Last-Modified
                logger.warning(f"Last-Modified generation callback failed: {e}")
                pass

        # Check for Last-Modified dependency
        if "last_modified" in self.dependency_callbacks:
            wrapper = self.dependency_callbacks["last_modified"]
            try:
                last_modified = self.app._call_with_injection(wrapper.func, self.request, self.route_handler)
                if isinstance(last_modified, datetime):
                    return last_modified
                elif isinstance(last_modified, str):
                    # Try to parse as HTTP date
                    try:
                        return datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
                    except ValueError:
                        pass
            except Exception as e:
                # Last-Modified dependency injection failed, continue gracefully without Last-Modified
                logger.warning(f"Last-Modified dependency injection failed: {e}")
                pass

        return None

    def get_available_content_types(self) -> List[str]:
        """Get list of all available content types for this route."""
        available_types = list(self.app._content_renderers.keys())

        # Add route-specific content types
        if self.route_handler and self.route_handler.content_renderers:
            available_types.extend(self.route_handler.content_renderers.keys())

        return list(set(available_types))  # Remove duplicates

    def state_content_types_provided(self) -> StateMachineResult:
        """C3: Determine what content types we can provide."""
        available_types = self.get_available_content_types()

        if not available_types:
            logger.error(f"No content renderers available for {self.request.method.value} {self.request.path}")
            return StateMachineResult(
                False, self._create_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, "No content renderers available")
            )

        return StateMachineResult(True)

    def state_content_types_accepted(self) -> StateMachineResult:
        """C4: Check if we can provide an acceptable content type."""
        accept_header = self.request.get_accept_header()

        # First try route-specific renderers
        if self.route_handler and self.route_handler.content_renderers:
            for content_type, wrapper in self.route_handler.content_renderers.items():
                if content_type in self.app._content_renderers:
                    renderer = self.app._content_renderers[content_type]
                    if renderer.can_render(accept_header):
                        self.chosen_renderer = renderer
                        return StateMachineResult(True)

        # Fall back to global renderers
        for renderer in self.app._content_renderers.values():
            if renderer.can_render(accept_header):
                self.chosen_renderer = renderer
                return StateMachineResult(True)

        # No acceptable content type found
        available_types = self.get_available_content_types()

        return StateMachineResult(
            False,
            Response(
                HTTPStatus.NOT_ACCEPTABLE,
                f"Not Acceptable. Available types: {', '.join(set(available_types))}",
                headers={"Content-Type": "text/plain"},
                request=self.request,
                available_content_types=available_types,
            ),
        )

    def _process_headers_dependencies(self) -> Dict[str, str]:
        """Process all headers dependencies and return final headers."""
        # Get initial headers (includes Vary header)
        headers = self.app._dependency_cache.get("headers")
        if headers is None:
            headers = self.app._get_initial_headers(self.request, self.route_handler)
            self.app._dependency_cache.set("headers", headers)

        # Find all headers dependencies (route-specific first, then global)
        headers_deps = []

        # Collect route-specific headers dependencies
        if self.route_handler and self.route_handler.headers_dependencies:
            for dep_name, wrapper in self.route_handler.headers_dependencies.items():
                headers_deps.append((dep_name, wrapper))

        # Collect global headers dependencies
        for dep_name, wrapper in self.app._headers_dependencies.items():
            # Avoid duplicates if already added from route-specific
            if not any(dep[0] == dep_name for dep in headers_deps):
                headers_deps.append((dep_name, wrapper))

        # Process each headers dependency in order
        for dep_name, wrapper in headers_deps:
            try:
                # Call the headers function with dependency injection
                updated_headers = self.app._call_with_injection(
                    wrapper.func, self.request, self.route_handler
                )
                # If function returns headers, use them; otherwise assume headers modified in-place
                if updated_headers and isinstance(updated_headers, dict):
                    headers.update(updated_headers)
                # Update cache with current state
                self.app._dependency_cache.set("headers", headers)
            except Exception as e:
                # If headers dependency fails, continue with current headers
                logger.warning(f"Headers dependency injection failed: {e}")
                pass

        return headers

    def state_execute_and_render(self) -> Response:
        """Execute the route handler and render the response."""
        processed_headers = None
        try:
            # Process headers dependencies first to get final headers
            processed_headers = self._process_headers_dependencies()

            # Execute the main handler to get the result
            main_result = self.app._call_with_injection(
                self.route_handler.handler, self.request, self.route_handler
            )

            # Check if handler returned None (regardless of annotation) -> return HTTPStatus.NO_CONTENT No Content
            if main_result is None:
                return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)

            # Add ETag and Last-Modified to processed headers if available (after handler execution)
            current_etag = self._get_resource_etag()
            if current_etag:
                processed_headers["ETag"] = current_etag

            current_last_modified = self._get_resource_last_modified()
            if current_last_modified:
                processed_headers["Last-Modified"] = current_last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")

            # Check return type annotation for response validation
            sig = inspect.signature(self.route_handler.handler)
            return_annotation = sig.return_annotation

            # Handle different return type scenarios
            if return_annotation is None or return_annotation is type(None):
                # Explicitly annotated as None -> return HTTPStatus.NO_CONTENT No Content
                return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)
            elif return_annotation != inspect.Signature.empty and PYDANTIC_AVAILABLE:
                # Has return type annotation -> validate response
                try:
                    if (
                        hasattr(return_annotation, "__origin__")
                        and return_annotation.__origin__ is Union
                    ):
                        # Handle Optional[SomeType] or Union types
                        # For now, skip validation on Union types
                        pass
                    elif (
                        get_origin(return_annotation) is list
                        and get_args(return_annotation)
                        and hasattr(get_args(return_annotation)[0], "model_validate")
                    ):
                        # Handle list[PydanticModel] types
                        pydantic_type = get_args(return_annotation)[0]
                        if isinstance(main_result, list):
                            # Convert each item to a dict if it's a Pydantic model
                            validated_list = []
                            for item in main_result:
                                if hasattr(item, "model_dump"):
                                    validated_list.append(item.model_dump())
                                elif isinstance(item, dict):
                                    # Validate and convert
                                    validated_item = pydantic_type.model_validate(item)
                                    validated_list.append(validated_item.model_dump())
                                else:
                                    # Try to validate the raw item
                                    validated_item = pydantic_type.model_validate(item)
                                    validated_list.append(validated_item.model_dump())
                            main_result = validated_list
                    elif hasattr(return_annotation, "model_validate"):
                        # It's a Pydantic model -> validate
                        if isinstance(main_result, dict):
                            validated_response = return_annotation.model_validate(
                                main_result
                            )
                            main_result = validated_response.model_dump()
                        elif hasattr(main_result, "model_dump"):
                            # Already a Pydantic model -> convert to dict
                            main_result = main_result.model_dump()
                        else:
                            # Try to validate the raw result
                            validated_response = return_annotation.model_validate(
                                main_result
                            )
                            main_result = validated_response.model_dump()
                except ValidationError as e:
                    return Response(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        json.dumps(
                            {
                                "error": "Response validation failed",
                                "details": e.errors(),
                            }
                        ),
                        content_type="application/json",
                        pre_calculated_headers=processed_headers,
                    )
                except Exception as e:
                    # If validation fails for other reasons, log but don't crash
                    logger.warning(f"Validation dependency execution failed: {e}")
                    pass

            # Check if we should use a route-specific renderer
            if (
                self.route_handler
                and self.route_handler.content_renderers
                and self.chosen_renderer.media_type
                in self.route_handler.content_renderers
            ):
                # Use route-specific content renderer
                wrapper = self.route_handler.content_renderers[
                    self.chosen_renderer.media_type
                ]

                # Create a temporary dependency for the handler result
                handler_func_name = self.route_handler.handler.__name__
                self.app._dependency_cache.set(handler_func_name, main_result)

                # Call the renderer with dependency injection (it will receive the handler result)
                rendered_result = self.app._call_with_injection(
                    wrapper.func, self.request, self.route_handler
                )

                # If the renderer returns a Response, use it directly
                if isinstance(rendered_result, Response):
                    if not rendered_result.content_type:
                        rendered_result.content_type = self.chosen_renderer.media_type
                        rendered_result.headers = rendered_result.headers or {}
                        rendered_result.headers["Content-Type"] = (
                            self.chosen_renderer.media_type
                        )
                    return rendered_result

                # Otherwise, treat the rendered result as the body
                return Response(
                    HTTPStatus.OK,
                    str(rendered_result),
                    content_type=self.chosen_renderer.media_type,
                    pre_calculated_headers=processed_headers,
                )
            else:
                # Use regular global renderer
                result = main_result

            # If result is already a Response, update it with processed headers
            if isinstance(result, Response):
                if not result.content_type and self.chosen_renderer:
                    result.content_type = self.chosen_renderer.media_type
                    result.headers = result.headers or {}
                    result.headers["Content-Type"] = self.chosen_renderer.media_type

                # Add processed headers if not already set
                if not result.pre_calculated_headers:
                    result.pre_calculated_headers = processed_headers
                    # Re-run __post_init__ to apply processed headers
                    result.__post_init__()
                return result

            # Render the result using the chosen renderer
            if self.chosen_renderer:
                rendered_body = self.chosen_renderer.render(result, self.request)
                return Response(
                    HTTPStatus.OK,
                    rendered_body,
                    content_type=self.chosen_renderer.media_type,
                    pre_calculated_headers=processed_headers,
                )
            else:
                # Fallback to plain text
                return Response(
                    HTTPStatus.OK,
                    str(result),
                    content_type="text/plain",
                    pre_calculated_headers=processed_headers,
                )
        except ValidationError as e:
            # Set exception in cache for custom error handlers
            self.app._dependency_cache.set("exception", e)
            # Use processed headers if available, otherwise fallback to basic headers
            fallback_headers = processed_headers or {}
            # Create a custom response for validation errors with details
            response = self._create_error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Validation failed", details=e.errors(include_url=False))
            if fallback_headers:
                response.pre_calculated_headers = fallback_headers
                response.__post_init__()
            return response
        except AcceptsParsingError as e:
            # Set exception in cache for custom error handlers
            self.app._dependency_cache.set("exception", e)
            # Handle accepts parsing errors with HTTPStatus.UNPROCESSABLE_ENTITY status
            fallback_headers = processed_headers or {}
            response = self._create_error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Parsing failed")
            # If default response (not custom handler), add message
            if response.body == json.dumps({"error": "Parsing failed"}):
                response.body = json.dumps({"error": "Parsing failed", "message": e.message})
            if fallback_headers:
                response.pre_calculated_headers = fallback_headers
                response.__post_init__()
            return response
        except ValueError as e:
            # Set exception in cache for custom error handlers
            self.app._dependency_cache.set("exception", e)
            # Handle specific ValueError cases for better HTTP status codes
            error_message = str(e)
            fallback_headers = processed_headers or {}

            if "Unsupported Media Type - 415" in error_message:
                response = self._create_error_response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Unsupported Media Type")
            else:
                # Other ValueError cases return Bad Request
                response = self._create_error_response(HTTPStatus.BAD_REQUEST, f"Bad Request: {error_message}")

            if fallback_headers:
                response.pre_calculated_headers = fallback_headers
                response.__post_init__()
            return response
        except Exception as e:
            # Set exception in cache for custom error handlers
            self.app._dependency_cache.set("exception", e)
            # Use processed headers if available, otherwise fallback to basic headers
            fallback_headers = processed_headers or {}
            response = self._create_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal Server Error: {str(e)}")
            if fallback_headers:
                response.pre_calculated_headers = fallback_headers
                response.__post_init__()
            return response

    def _get_callback(self, state_name: str) -> Optional[Callable]:
        """Get callback for a state, preferring dependency callbacks over defaults."""
        # First check if we have a dependency callback for this state
        if state_name in self.dependency_callbacks:
            return self.dependency_callbacks[state_name].func

        # Fall back to default callbacks
        return self.app._default_callbacks.get(state_name)

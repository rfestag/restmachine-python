"""
Webmachine-style state machine using methods instead of objects.

Following webmachine-ruby's pattern: each state is a method that returns
either the next method to call or a Response object.
"""

import inspect
import json
import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Union, Callable, Optional, cast, Any, Dict, List, get_origin, get_args, TYPE_CHECKING
from datetime import datetime

from restmachine.models import Request, Response, HTTPMethod, etags_match, MultiValueHeaders
from restmachine.dependencies import DependencyWrapper
from restmachine.error_models import ErrorResponse
from restmachine.exceptions import PYDANTIC_AVAILABLE, ValidationError, AcceptsParsingError

if TYPE_CHECKING:
    from restmachine.application import RestApplication, RouteHandler
    from restmachine.content_renderers import ContentRenderer

logger = logging.getLogger(__name__)


@dataclass
class StateContext:
    """Shared context for state machine execution.

    This contains all the information needed by state methods to make decisions
    and perform their operations.
    """
    app: 'RestApplication'
    request: 'Request'
    route_handler: Optional['RouteHandler'] = None
    chosen_renderer: Optional['ContentRenderer'] = None
    handler_dependencies: List[str] = field(default_factory=list)
    dependency_callbacks: Dict[str, 'DependencyWrapper'] = field(default_factory=dict)
    handler_result: Any = None


class RequestStateMachine:
    """Webmachine-style state machine using methods for states.

    Each state is a method that returns either:
    - Another method (next state)
    - A Response object (terminal state)

    This eliminates all state object creation overhead.
    """

    def __init__(self, app):
        self.app = app
        # ctx is initialized in process_request before any state methods are called
        self.ctx: StateContext  # type: ignore[misc]

    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine."""
        # Initialize context
        self.ctx = StateContext(app=self.app, request=request)

        # Preserve metrics if set by platform adapter
        metrics = self.app._dependency_cache.get("metrics")
        self.app._dependency_cache.clear()
        if metrics is not None:
            self.app._dependency_cache.set("metrics", metrics)

        logger.debug(f"State machine v2: {request.method.value} {request.path}")

        # Start with first state method
        current: Union[Callable, Response] = self.state_route_exists

        state_count = 0
        max_states = 50

        # Execute state methods until we get a Response
        while not isinstance(current, Response):
            state_count += 1

            if state_count > max_states:
                logger.error(f"State machine exceeded max states ({max_states})")
                return self._create_error_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Internal error: state machine loop detected"
                )

            state_name = current.__name__
            logger.debug(f"  [{state_count}] → {state_name}")

            try:
                current = current()
            except Exception as e:
                logger.error(f"Error in state {state_name}: {e}", exc_info=True)
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Internal error in {state_name}: {str(e)}"
                )

        logger.debug(f"  ✓ Complete in {state_count} states: {current.status_code}")
        return current

    # ========================================================================
    # STATE METHODS (following webmachine pattern)
    # ========================================================================

    def state_route_exists(self) -> Union[Callable, Response]:
        """B13: Check if route exists."""
        route_match = self.app._find_route(self.ctx.request.method, self.ctx.request.path)

        if route_match is None:
            if self.app._path_has_routes(self.ctx.request.path):
                return self._create_error_response(
                    HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed"
                )

            callback = self.app._default_callbacks.get("route_not_found")
            if callback:
                try:
                    response = self.app._call_with_injection(callback, self.ctx.request, None)
                    if isinstance(response, Response):
                        return response
                except Exception as e:
                    logger.error(f"Error in route_not_found callback: {e}")

            return self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found")

        # Populate context
        self.ctx.route_handler, path_params = route_match
        self.ctx.request.path_params = path_params
        self.ctx.handler_dependencies = list(self.ctx.route_handler.param_info.keys())

        # Copy pre-resolved state callbacks
        for state_name, callback in self.ctx.route_handler.state_callbacks.items():
            wrapper = DependencyWrapper(callback, state_name, callback.__name__)
            self.ctx.dependency_callbacks[state_name] = wrapper

        return self.state_service_available

    def state_service_available(self) -> Union[Callable, Response]:
        """B12: Check if service is available."""
        callback = self._get_callback("service_available")
        if callback:
            try:
                available = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if not available:
                    return self._create_error_response(
                        HTTPStatus.SERVICE_UNAVAILABLE, "Service Unavailable"
                    )
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.SERVICE_UNAVAILABLE, f"Service check failed: {str(e)}"
                )

        return self.state_known_method

    def state_known_method(self) -> Union[Callable, Response]:
        """B11: Check if HTTP method is known."""
        callback = self._get_callback("known_method")
        if callback:
            try:
                known = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if not known:
                    return self._create_error_response(HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.NOT_IMPLEMENTED, f"Method check failed: {str(e)}"
                )
        else:
            known_methods = {
                HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT,
                HTTPMethod.DELETE, HTTPMethod.PATCH, HTTPMethod.OPTIONS
            }
            if self.ctx.request.method not in known_methods:
                return self._create_error_response(HTTPStatus.NOT_IMPLEMENTED, "Not Implemented")

        return self.state_uri_too_long

    def state_uri_too_long(self) -> Union[Callable, Response]:
        """B10: Check if URI is too long."""
        callback = self._get_callback("uri_too_long")
        if callback:
            try:
                too_long = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if too_long:
                    return self._create_error_response(HTTPStatus.REQUEST_URI_TOO_LONG, "URI Too Long")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.REQUEST_URI_TOO_LONG, f"URI check failed: {str(e)}"
                )

        return self.state_method_allowed

    def state_method_allowed(self) -> Union[Callable, Response]:
        """B9: Check if method is allowed."""
        callback = self._get_callback("method_allowed")
        if callback:
            try:
                allowed = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if not allowed:
                    return self._create_error_response(HTTPStatus.METHOD_NOT_ALLOWED, "Method Not Allowed")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.METHOD_NOT_ALLOWED, f"Method check failed: {str(e)}"
                )

        return self.state_malformed_request

    def state_malformed_request(self) -> Union[Callable, Response]:
        """B8: Check if request is malformed."""
        callback = self._get_callback("malformed_request")
        if callback:
            try:
                malformed = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if malformed:
                    return self._create_error_response(HTTPStatus.BAD_REQUEST, "Bad Request")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.BAD_REQUEST, f"Request validation failed: {str(e)}"
                )

        return self.state_authorized

    def state_authorized(self) -> Union[Callable, Response]:
        """B7: Check if request is authorized."""
        callback = self._get_callback("authorized")
        if callback:
            try:
                authorized = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if not authorized:
                    return self._create_error_response(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.UNAUTHORIZED, f"Authorization check failed: {str(e)}"
                )

        return self.state_forbidden

    def state_forbidden(self) -> Union[Callable, Response]:
        """B6: Check if access is forbidden."""
        callback = self._get_callback("forbidden")
        if callback:
            try:
                if "forbidden" in self.ctx.dependency_callbacks:
                    wrapper = self.ctx.dependency_callbacks["forbidden"]
                    try:
                        resolved_value = self.app._call_with_injection(
                            wrapper.func, self.ctx.request, self.ctx.route_handler
                        )
                        if resolved_value is None:
                            return self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden")
                    except Exception as e:
                        self.app._dependency_cache.set("exception", e)
                        return self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden")
                else:
                    forbidden = self.app._call_with_injection(
                        callback, self.ctx.request, self.ctx.route_handler
                    )
                    if forbidden:
                        return self._create_error_response(HTTPStatus.FORBIDDEN, "Forbidden")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.FORBIDDEN, f"Forbidden check failed: {str(e)}"
                )

        return self.state_content_headers_valid

    def state_content_headers_valid(self) -> Union[Callable, Response]:
        """B5: Check if content headers are valid."""
        callback = self._get_callback("valid_content_headers")
        if callback:
            try:
                valid = self.app._call_with_injection(
                    callback, self.ctx.request, self.ctx.route_handler
                )
                if not valid:
                    return self._create_error_response(HTTPStatus.BAD_REQUEST, "Invalid Content Headers")
            except Exception as e:
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.BAD_REQUEST, f"Content header validation failed: {str(e)}"
                )

        return self.state_resource_exists

    def state_resource_exists(self) -> Union[Callable, Response]:
        """G7: Check if resource exists."""
        callback = self._get_callback("resource_exists")

        if callback:
            try:
                if "resource_exists" in self.ctx.dependency_callbacks:
                    wrapper = self.ctx.dependency_callbacks["resource_exists"]
                    resolved_value = self.app._call_with_injection(
                        wrapper.func, self.ctx.request, self.ctx.route_handler
                    )
                    if resolved_value is None:
                        if self.ctx.request.method == HTTPMethod.POST:
                            return self.state_content_types_provided
                        return self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found")

                    self.app._dependency_cache.set(wrapper.original_name, resolved_value)
                else:
                    exists = self.app._call_with_injection(
                        callback, self.ctx.request, self.ctx.route_handler
                    )
                    if not exists:
                        if self.ctx.request.method == HTTPMethod.POST:
                            return self.state_content_types_provided
                        return self._create_error_response(HTTPStatus.NOT_FOUND, "Not Found")

            except Exception as e:
                logger.error(f"Error in resource_exists check: {e}")
                if self.ctx.request.method == HTTPMethod.POST:
                    return self.state_content_types_provided
                self.app._dependency_cache.set("exception", e)
                return self._create_error_response(
                    HTTPStatus.NOT_FOUND, f"Resource check failed: {str(e)}"
                )

        # Check if we need conditional processing
        if not self._needs_conditional_processing():
            logger.debug("Skipping conditional states (not needed)")
            return self.state_content_types_provided

        return self.state_if_match

    def state_if_match(self) -> Union[Callable, Response]:
        """G3: Process If-Match header."""
        if_match_etags = self.ctx.request.get_if_match()
        if not if_match_etags:
            return self.state_if_unmodified_since

        current_etag = self._get_resource_etag()
        if not current_etag:
            return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        if "*" in if_match_etags:
            return self.state_if_unmodified_since

        for requested_etag in if_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=True):
                return self.state_if_unmodified_since

        return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

    def state_if_unmodified_since(self) -> Union[Callable, Response]:
        """G4: Process If-Unmodified-Since header."""
        if_unmodified_since = self.ctx.request.get_if_unmodified_since()
        if not if_unmodified_since:
            return self.state_if_none_match

        last_modified = self._get_resource_last_modified()
        if not last_modified:
            return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        if last_modified > if_unmodified_since:
            return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        return self.state_if_none_match

    def state_if_none_match(self) -> Union[Callable, Response]:
        """G5: Process If-None-Match header."""
        if_none_match_etags = self.ctx.request.get_if_none_match()
        if not if_none_match_etags:
            return self.state_if_modified_since

        current_etag = self._get_resource_etag()

        if "*" in if_none_match_etags:
            if self.ctx.request.method in [HTTPMethod.GET]:
                return Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag} if current_etag else {})
            else:
                return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        if not current_etag:
            return self.state_if_modified_since

        for requested_etag in if_none_match_etags:
            if etags_match(current_etag, requested_etag, strong_comparison=False):
                if self.ctx.request.method in [HTTPMethod.GET]:
                    return Response(HTTPStatus.NOT_MODIFIED, headers={"ETag": current_etag})
                else:
                    return self._create_error_response(HTTPStatus.PRECONDITION_FAILED, "Precondition Failed")

        return self.state_if_modified_since

    def state_if_modified_since(self) -> Union[Callable, Response]:
        """G6: Process If-Modified-Since header."""
        if self.ctx.request.method != HTTPMethod.GET:
            return self.state_content_types_provided

        if_modified_since = self.ctx.request.get_if_modified_since()
        if not if_modified_since:
            return self.state_content_types_provided

        last_modified = self._get_resource_last_modified()
        if not last_modified:
            return self.state_content_types_provided

        if last_modified <= if_modified_since:
            return Response(HTTPStatus.NOT_MODIFIED)

        return self.state_content_types_provided

    def state_content_types_provided(self) -> Union[Callable, Response]:
        """C3: Check if acceptable content types are provided."""
        available_types = list(self.app._content_renderers.keys())

        if self.ctx.route_handler and self.ctx.route_handler.content_renderers:
            available_types.extend(self.ctx.route_handler.content_renderers.keys())
        available_types = list(set(available_types))

        if not available_types:
            logger.error(f"No content renderers available for {self.ctx.request.method.value} {self.ctx.request.path}")
            return Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                '{"error": "No content renderers available"}',
                content_type="application/json"
            )

        return self.state_content_types_accepted

    def state_content_types_accepted(self) -> Union[Callable, Response]:
        """C4: Check if we can provide an acceptable content type."""
        accept_header = self.ctx.request.get_accept_header()

        # Try route-specific renderers first
        if self.ctx.route_handler and self.ctx.route_handler.content_renderers:
            for content_type, wrapper in self.ctx.route_handler.content_renderers.items():
                if content_type in self.app._content_renderers:
                    renderer = self.app._content_renderers[content_type]
                    if renderer.can_render(accept_header):
                        self.ctx.chosen_renderer = renderer
                        return self.state_execute_and_render

        # Fall back to global renderers
        for renderer in self.app._content_renderers.values():
            if renderer.can_render(accept_header):
                self.ctx.chosen_renderer = renderer
                return self.state_execute_and_render

        # No acceptable content type found
        available_types = list(self.app._content_renderers.keys())
        if self.ctx.route_handler and self.ctx.route_handler.content_renderers:
            available_types.extend(self.ctx.route_handler.content_renderers.keys())
        available_types = list(set(available_types))

        return Response(
            HTTPStatus.NOT_ACCEPTABLE,
            f"Not Acceptable. Available types: {', '.join(available_types)}",
            headers={"Content-Type": "text/plain"},
            request=self.ctx.request,
            available_content_types=available_types,
        )

    def state_execute_and_render(self) -> Response:
        """Execute handler and render response (terminal state)."""
        if not self.ctx.route_handler:
            raise RuntimeError("route_handler must be set before executing handler")

        processed_headers: Optional[MultiValueHeaders] = None
        try:
            # Process headers dependencies first
            processed_headers = self._process_headers_dependencies()

            # Execute the main handler
            result = self.app._call_with_injection(
                self.ctx.route_handler.handler,
                self.ctx.request,
                self.ctx.route_handler
            )

            # Handle None result -> NO_CONTENT
            if result is None:
                return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)

            # Add resource metadata headers (ETag, Last-Modified)
            self._add_resource_metadata_to_headers(processed_headers)

            # Validate and process return type if Pydantic is used
            validated_result = self._validate_pydantic_return_type(result)

            # Handle validated None result
            if validated_result is None:
                return Response(HTTPStatus.NO_CONTENT, pre_calculated_headers=processed_headers)

            # Render the result
            return self._render_result(validated_result, processed_headers)

        except ValidationError as e:
            self.app._dependency_cache.set("exception", e)
            return self._handle_validation_error(e, processed_headers)
        except AcceptsParsingError as e:
            self.app._dependency_cache.set("exception", e)
            return self._handle_accepts_parsing_error(e, processed_headers)
        except ValueError as e:
            self.app._dependency_cache.set("exception", e)
            return self._handle_value_error(e, processed_headers)
        except Exception as e:
            self.app._dependency_cache.set("exception", e)
            return self._handle_general_error(e, processed_headers)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_callback(self, state_name: str):
        """Get callback for a state."""
        if state_name in self.ctx.dependency_callbacks:
            return self.ctx.dependency_callbacks[state_name].func
        return self.app._default_callbacks.get(state_name)

    def _needs_conditional_processing(self) -> bool:
        """Check if conditional request processing is needed."""
        has_route_support = False
        if self.ctx.route_handler:
            conditional_states = {'generate_etag', 'last_modified'}
            has_route_support = bool(conditional_states & set(self.ctx.route_handler.state_callbacks.keys()))

        has_conditional_headers = (
            self.ctx.request.headers.get('If-Match') or
            self.ctx.request.headers.get('If-None-Match') or
            self.ctx.request.headers.get('If-Modified-Since') or
            self.ctx.request.headers.get('If-Unmodified-Since')
        )

        return has_route_support or bool(has_conditional_headers)

    def _get_resource_etag(self) -> Optional[str]:
        """Get the current ETag for the resource."""
        callback = self._get_callback("generate_etag")
        if callback:
            try:
                etag = self.app._call_with_injection(callback, self.ctx.request, self.ctx.route_handler)
                if etag:
                    return f'"{etag}"' if not etag.startswith('"') and not etag.startswith('W/') else etag
            except Exception as e:
                logger.warning(f"ETag generation callback failed: {e}")
        return None

    def _get_resource_last_modified(self) -> Optional[datetime]:
        """Get the current Last-Modified timestamp for the resource."""
        callback = self._get_callback("last_modified")
        if callback:
            try:
                result = self.app._call_with_injection(callback, self.ctx.request, self.ctx.route_handler)
                return cast(Optional[datetime], result)
            except Exception as e:
                logger.warning(f"Last-Modified callback failed: {e}")
        return None

    def _create_error_response(self, status_code: int, message: str, details=None, **kwargs) -> Response:
        """Create an error response respecting content negotiation."""
        # Try custom error handlers first
        custom_response = self._try_custom_error_handler(status_code, message, details, **kwargs)
        if custom_response:
            return custom_response

        # Get request/trace IDs for error response
        request_id, trace_id = self._get_error_context_ids()

        # Determine response format from Accept header
        if self._prefers_json_error_response():
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
            return Response(
                status_code,
                message,
                content_type="text/plain",
                **kwargs
            )

    # ========================================================================
    # HELPER METHODS FOR state_execute_and_render
    # ========================================================================

    def _process_headers_dependencies(self) -> MultiValueHeaders:
        """Process all headers dependencies and return final headers."""
        headers = self.app._dependency_cache.get("headers")
        if headers is None:
            headers = self.app._get_initial_headers(self.ctx.request, self.ctx.route_handler)
            self.app._dependency_cache.set("headers", headers)

        # Process each headers dependency in order
        for dep_name, wrapper in self.app._headers_dependencies.items():
            try:
                updated_headers = self.app._call_with_injection(
                    wrapper.func, self.ctx.request, self.ctx.route_handler
                )
                if updated_headers and isinstance(updated_headers, dict):
                    headers.update(updated_headers)
                self.app._dependency_cache.set("headers", headers)
            except Exception as e:
                logger.warning(f"Headers dependency injection failed: {e}")

        return cast(MultiValueHeaders, headers)

    def _add_resource_metadata_to_headers(self, headers: MultiValueHeaders) -> None:
        """Add ETag and Last-Modified headers if available."""
        etag = self._get_resource_etag()
        if etag:
            headers["ETag"] = etag

        last_modified = self._get_resource_last_modified()
        if last_modified:
            headers["Last-Modified"] = last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def _validate_pydantic_return_type(self, result: Any) -> Any:
        """Validate and convert Pydantic return types. Raises ValidationError on error."""
        if not PYDANTIC_AVAILABLE or not self.ctx.route_handler:
            return result

        return_annotation = self.ctx.route_handler.handler_signature.return_annotation

        # Skip validation for types that don't need it
        if self._should_skip_pydantic_validation(return_annotation):
            return None if return_annotation is type(None) else result

        try:
            # Handle list[PydanticModel]
            if self._is_pydantic_list_type(return_annotation):
                return self._validate_pydantic_list(result, return_annotation)

            # Handle PydanticModel
            if hasattr(return_annotation, "model_validate"):
                return self._validate_pydantic_model(result, return_annotation)

        except ValidationError:
            raise  # Re-raise to be caught by state_execute_and_render
        except Exception as e:
            logger.warning(f"Validation failed: {e}")

        return result

    def _should_skip_pydantic_validation(self, annotation: Any) -> bool:
        """Check if annotation should skip Pydantic validation."""
        if annotation is None or annotation is type(None) or annotation == inspect.Signature.empty:
            return True
        if hasattr(annotation, "__origin__") and annotation.__origin__ is Union:
            return True
        return False

    def _is_pydantic_list_type(self, annotation: Any) -> bool:
        """Check if annotation is list[PydanticModel]."""
        if get_origin(annotation) is not list:
            return False
        args = get_args(annotation)
        return bool(args and hasattr(args[0], "model_validate"))

    def _validate_pydantic_list(self, result: Any, annotation: Any) -> Any:
        """Validate and convert list of Pydantic models."""
        if not isinstance(result, list):
            return result

        pydantic_type = get_args(annotation)[0]
        validated_list = []

        for item in result:
            if hasattr(item, "model_dump"):
                validated_list.append(item.model_dump())
            elif isinstance(item, dict):
                validated_item = pydantic_type.model_validate(item)
                validated_list.append(validated_item.model_dump())
            else:
                validated_item = pydantic_type.model_validate(item)
                validated_list.append(validated_item.model_dump())

        return validated_list

    def _validate_pydantic_model(self, result: Any, annotation: Any) -> Any:
        """Validate and convert Pydantic model."""
        if isinstance(result, dict):
            validated = annotation.model_validate(result)
            return validated.model_dump()
        elif hasattr(result, "model_dump"):
            return result.model_dump()
        else:
            validated = annotation.model_validate(result)
            return validated.model_dump()

    def _render_result(self, result: Any, headers: MultiValueHeaders) -> Response:
        """Render the result using appropriate renderer."""
        # Check for route-specific renderer
        if self._has_route_specific_renderer():
            return self._render_with_route_specific_renderer(result, headers)

        # Handle Response objects
        if isinstance(result, Response):
            return self._finalize_response_object(result, headers)

        # Handle Path objects - wrap in Response to preserve Path type
        from pathlib import Path
        if isinstance(result, Path):
            response = Response(HTTPStatus.OK, result)
            return self._finalize_response_object(response, headers)

        # Use global renderer
        return self._render_with_global_renderer(result, headers)

    def _has_route_specific_renderer(self) -> bool:
        """Check if route has a specific renderer for chosen media type."""
        if not self.ctx.route_handler or not self.ctx.route_handler.content_renderers:
            return False
        if not self.ctx.chosen_renderer:
            return False
        return self.ctx.chosen_renderer.media_type in self.ctx.route_handler.content_renderers

    def _render_with_route_specific_renderer(self, result: Any, headers: MultiValueHeaders) -> Response:
        """Render using route-specific content renderer."""
        # These checks are guaranteed by _has_route_specific_renderer
        if not self.ctx.route_handler or not self.ctx.chosen_renderer:
            raise RuntimeError("route_handler and chosen_renderer must be set")

        wrapper = self.ctx.route_handler.content_renderers[self.ctx.chosen_renderer.media_type]

        # Cache handler result for renderer to access
        handler_func_name = self.ctx.route_handler.handler.__name__
        self.app._dependency_cache.set(handler_func_name, result)

        # Call renderer with dependency injection
        rendered_result = self.app._call_with_injection(
            wrapper.func, self.ctx.request, self.ctx.route_handler
        )

        # Get full content type including charset if specified
        full_content_type = wrapper.get_full_content_type()

        # Handle Response from renderer
        if isinstance(rendered_result, Response):
            if not rendered_result.content_type:
                rendered_result.content_type = full_content_type
                rendered_result.headers = rendered_result.headers or {}
                rendered_result.headers["Content-Type"] = full_content_type
            return rendered_result

        # Renderer returned string/other
        return Response(
            HTTPStatus.OK,
            str(rendered_result),
            content_type=full_content_type,
            pre_calculated_headers=headers,
        )

    def _render_with_global_renderer(self, result: Any, headers: MultiValueHeaders) -> Response:
        """Render using global content renderer."""
        if self.ctx.chosen_renderer:
            rendered_body = self.ctx.chosen_renderer.render(result, self.ctx.request)
            return Response(
                HTTPStatus.OK,
                rendered_body,
                content_type=self.ctx.chosen_renderer.media_type,
                pre_calculated_headers=headers,
            )
        else:
            # Fallback to plain text
            return Response(
                HTTPStatus.OK,
                str(result),
                content_type="text/plain",
                pre_calculated_headers=headers,
            )

    def _finalize_response_object(self, response: Response, headers: MultiValueHeaders) -> Response:
        """Finalize a Response object with headers and content type."""
        from pathlib import Path

        # Validate Path objects - if path doesn't exist or isn't a file, return 404
        if isinstance(response.body, Path):
            if not response.body.exists() or not response.body.is_file():
                return Response(
                    HTTPStatus.NOT_FOUND,
                    json.dumps({"error": "Not Found", "detail": "File not found"}),
                    content_type="application/json"
                )
            # For Path responses, Content-Type is set from file extension in Response.__post_init__
        elif not response.content_type and self.ctx.chosen_renderer:
            # Not a Path response - set content type from chosen renderer
            response.content_type = self.ctx.chosen_renderer.media_type
            response.headers = response.headers or {}
            response.headers["Content-Type"] = self.ctx.chosen_renderer.media_type

        # Add processed headers if not already set
        if not response.pre_calculated_headers:
            response.pre_calculated_headers = headers
            response.__post_init__()

        # Process range requests after response is finalized
        response = self._process_range_request(response)

        return response

    def _process_range_request(self, response: Response) -> Response:
        """Process Range header and prepare response for partial content.

        RFC 9110 Section 14: Range requests allow clients to request partial
        transfer of a selected representation.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-14

        This method:
        1. Checks if response supports ranges
        2. Parses Range header if present
        3. Validates ranges
        4. Sets appropriate headers (Accept-Ranges, Content-Range, 206/416 status)
        5. Sets range_start/range_end fields for adapters to use

        Adapters are responsible for actually sending the range bytes.
        """
        from .models import parse_range_header

        # Convert strings to bytes for range processing
        # (Range requests work on byte boundaries, not character boundaries)
        if isinstance(response.body, str):
            response.body = response.body.encode('utf-8')

        # Determine if response supports range requests
        supports_ranges = self._supports_ranges(response)

        # Ensure headers exists
        if response.headers is None:
            response.headers = MultiValueHeaders()

        # Set Accept-Ranges header
        if supports_ranges:
            response.headers["Accept-Ranges"] = "bytes"
        else:
            response.headers["Accept-Ranges"] = "none"
            return response

        # Check for Range header
        range_header = self.ctx.request.headers.get("Range")
        if not range_header:
            # No range requested - return normal response
            return response

        # Get total size of content
        total_size = self._get_content_size(response)
        if total_size is None:
            # Can't determine size - can't handle ranges
            return response

        # Check If-Range precondition
        if not self._check_if_range_precondition(response):
            # Precondition failed - return full response (200)
            return response

        # Parse range specification
        ranges = parse_range_header(range_header, total_size)

        if not ranges:
            # Invalid or unsatisfiable range - return 416
            response.status_code = 416
            response.headers["Content-Range"] = f"bytes */{total_size}"
            response.body = b"Range Not Satisfiable"
            response.headers["Content-Length"] = str(len(response.body))
            return response

        # For now, only handle single range
        # TODO: Implement multipart/byteranges for multiple ranges
        start, end = ranges[0]

        # Set partial content response fields
        response.status_code = 206
        response.range_start = start
        response.range_end = end
        response.headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        response.headers["Content-Length"] = str(end - start + 1)

        return response

    def _supports_ranges(self, response: Response) -> bool:
        """Check if response supports range requests."""
        from pathlib import Path
        from .models import is_seekable_stream

        # Path objects always support ranges
        if isinstance(response.body, Path):
            return True

        # Seekable streams support ranges
        if is_seekable_stream(response.body):
            return True

        # Bytes support ranges
        if isinstance(response.body, bytes):
            return True

        return False

    def _get_content_size(self, response: Response) -> Optional[int]:
        """Get total content size in bytes."""
        from pathlib import Path
        from .models import is_seekable_stream, get_stream_size
        from typing import cast, BinaryIO

        # Check Content-Length header first
        if response.headers:
            content_length_header = response.headers.get("Content-Length")
            if content_length_header:
                try:
                    return int(content_length_header)
                except ValueError:
                    pass

        # Path object? Get file size
        if isinstance(response.body, Path):
            try:
                return response.body.stat().st_size
            except OSError:
                return None

        # Seekable stream? Get size from stream
        if is_seekable_stream(response.body):
            try:
                return get_stream_size(cast(BinaryIO, response.body))
            except Exception:
                return None

        # Bytes? Get length directly
        if isinstance(response.body, bytes):
            return len(response.body)

        return None

    def _check_if_range_precondition(self, response: Response) -> bool:
        """Check If-Range precondition header.

        RFC 9110 Section 13.1.5: If-Range allows conditional range request.
        https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5

        Returns:
            True if precondition passes or no If-Range header present.
            False if precondition fails (should send full 200 response).
        """
        if_range = self.ctx.request.headers.get("If-Range")
        if not if_range:
            return True  # No precondition

        if not response.headers:
            return False  # No headers to check against

        # Check against ETag
        current_etag = response.headers.get("ETag")
        if current_etag and if_range == current_etag:
            return True

        # Check against Last-Modified
        last_modified = response.headers.get("Last-Modified")
        if last_modified and if_range == last_modified:
            return True

        # Precondition failed
        return False

    # ========================================================================
    # ERROR HANDLING HELPERS
    # ========================================================================

    def _handle_validation_error(self, e: ValidationError, headers: Optional[MultiValueHeaders]) -> Response:
        """Handle ValidationError with proper response."""
        fallback_headers = headers or MultiValueHeaders()
        response = self._create_error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Validation failed",
            details=e.errors(include_url=False)
        )
        if fallback_headers:
            response.pre_calculated_headers = fallback_headers
            response.__post_init__()
        return response

    def _handle_accepts_parsing_error(self, e: AcceptsParsingError, headers: Optional[MultiValueHeaders]) -> Response:
        """Handle AcceptsParsingError with proper response."""
        fallback_headers = headers or MultiValueHeaders()
        response = self._create_error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Parsing failed")

        # Add error message if using default response
        if response.body == json.dumps({"error": "Parsing failed"}):
            response.body = json.dumps({"error": "Parsing failed", "message": e.message})

        if fallback_headers:
            response.pre_calculated_headers = fallback_headers
            response.__post_init__()
        return response

    def _handle_value_error(self, e: ValueError, headers: Optional[MultiValueHeaders]) -> Response:
        """Handle ValueError with appropriate HTTP status."""
        fallback_headers = headers or MultiValueHeaders()
        error_message = str(e)

        if "Unsupported Media Type - 415" in error_message:
            status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
            message = "Unsupported Media Type"
        else:
            status_code = HTTPStatus.BAD_REQUEST
            message = f"Bad Request: {error_message}"

        response = self._create_error_response(status_code, message)
        if fallback_headers:
            response.pre_calculated_headers = fallback_headers
            response.__post_init__()
        return response

    def _handle_general_error(self, e: Exception, headers: Optional[MultiValueHeaders]) -> Response:
        """Handle general exceptions."""
        fallback_headers = headers or MultiValueHeaders()
        response = self._create_error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            f"Internal Server Error: {str(e)}"
        )
        if fallback_headers:
            response.pre_calculated_headers = fallback_headers
            response.__post_init__()
        return response

    # ========================================================================
    # ERROR RESPONSE HELPERS
    # ========================================================================

    def _try_custom_error_handler(self, status_code: int, message: str, details: Any, **kwargs) -> Optional[Response]:
        """Try to use a custom error handler. Returns None if not found or failed."""
        if not self.app._error_handlers:
            return None

        # Find matching handlers
        matching_handlers = [h for h in self.app._error_handlers if h.handles_status(status_code)]
        if not matching_handlers:
            return None

        # Choose appropriate handler based on content negotiation
        accept_header = self.ctx.request.get_accept_header() if hasattr(self.ctx, 'request') else ""
        chosen_handler = self._choose_error_handler(matching_handlers, accept_header)
        if not chosen_handler:
            return None

        # Execute custom handler
        try:
            result = self.app._call_with_injection(
                chosen_handler.handler,
                self.ctx.request,
                self.ctx.route_handler
            )
            return self._convert_custom_handler_result(result, chosen_handler, status_code, **kwargs)
        except Exception as e:
            logger.error(f"Error in custom error handler: {e}")
            return None

    def _choose_error_handler(self, handlers: List[Any], accept_header: str) -> Optional[Any]:
        """Choose the best error handler based on content negotiation."""
        # Try content-specific handler first
        for handler in handlers:
            if handler.content_type and handler.matches_accept(accept_header):
                return handler

        # Fall back to default handler (no content type)
        for handler in handlers:
            if not handler.content_type:
                return handler

        return None

    def _convert_custom_handler_result(self, result: Any, handler: Any, status_code: int, **kwargs) -> Optional[Response]:
        """Convert custom error handler result to Response."""
        # Get full content type including charset if specified
        full_content_type = handler.get_full_content_type()

        if isinstance(result, Response):
            return result
        elif isinstance(result, dict):
            return Response(
                status_code,
                json.dumps(result),
                content_type=full_content_type or "application/json",
                **kwargs
            )
        elif isinstance(result, str):
            return Response(
                status_code,
                result,
                content_type=full_content_type or "text/plain",
                **kwargs
            )
        else:
            return Response(
                status_code,
                json.dumps(result),
                content_type=full_content_type or "application/json",
                **kwargs
            )

    def _get_error_context_ids(self) -> tuple[Optional[str], Optional[str]]:
        """Get request_id and trace_id for error responses."""
        request_id = None
        trace_id = None

        try:
            request_id = self.app._resolve_dependency(
                "request_id", None, self.ctx.request, self.ctx.route_handler
            )
            trace_id = self.app._resolve_dependency(
                "trace_id", None, self.ctx.request, self.ctx.route_handler
            )
        except Exception as e:
            logger.warning(f"Failed to resolve request_id/trace_id: {e}")

        return request_id, trace_id

    def _prefers_json_error_response(self) -> bool:
        """Determine if client prefers JSON error response based on Accept header."""
        accept_header = self.ctx.request.get_accept_header() if hasattr(self.ctx, 'request') else ""

        if not accept_header:
            return True  # Default to JSON for RESTful APIs

        if "application/json" in accept_header or "*/*" in accept_header:
            return True
        elif "text/plain" in accept_header:
            return False
        else:
            return True  # Default to JSON

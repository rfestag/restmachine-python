"""
Webmachine-style state machine using methods instead of objects.

Following webmachine-ruby's pattern: each state is a method that returns
either the next method to call or a Response object.
"""

import logging
from http import HTTPStatus
from typing import Union, Callable, Optional
from datetime import datetime

from restmachine.models import Request, Response, HTTPMethod, etags_match
from restmachine.dependencies import DependencyWrapper
from .base import StateContext

logger = logging.getLogger(__name__)


class RequestStateMachine:
    """Webmachine-style state machine using methods for states.

    Each state is a method that returns either:
    - Another method (next state)
    - A Response object (terminal state)

    This eliminates all state object creation overhead.
    """

    def __init__(self, app):
        self.app = app
        self.ctx: Optional[StateContext] = None

    def process_request(self, request: Request) -> Response:
        """Process a request through the state machine."""
        # Initialize context
        self.ctx = StateContext(app=self.app, request=request)
        self.app._dependency_cache.clear()

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
                HTTPMethod.DELETE, HTTPMethod.PATCH
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
        # Delegate to old state machine for now
        from restmachine.state_machine import RequestStateMachine as OldSM

        old_sm = OldSM(self.app)
        old_sm.request = self.ctx.request
        old_sm.route_handler = self.ctx.route_handler
        old_sm.handler_dependencies = self.ctx.handler_dependencies
        old_sm.dependency_callbacks = self.ctx.dependency_callbacks

        if self.ctx.chosen_renderer:
            old_sm.chosen_renderer = self.ctx.chosen_renderer
        else:
            logger.warning("chosen_renderer not set in context")

        return old_sm.state_execute_and_render()

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
                return self.app._call_with_injection(callback, self.ctx.request, self.ctx.route_handler)
            except Exception as e:
                logger.warning(f"Last-Modified callback failed: {e}")
        return None

    def _create_error_response(self, status_code: int, message: str) -> Response:
        """Create an error response."""
        from restmachine.state_machine import RequestStateMachine as OldStateMachine

        old_sm = OldStateMachine(self.app)
        old_sm.request = self.ctx.request
        old_sm.route_handler = self.ctx.route_handler

        return old_sm._create_error_response(status_code, message)

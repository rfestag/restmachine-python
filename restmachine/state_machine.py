"""
Webmachine-inspired state machine for HTTP request processing.
"""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Union, get_origin, get_args

from .content_renderers import ContentRenderer
from .dependencies import DependencyWrapper
from .exceptions import PYDANTIC_AVAILABLE, ValidationError
from .models import HTTPMethod, Request, Response


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

    def process_request(self, request: Request) -> Optional[Response]:
        """Process a request through the state machine."""
        self.request = request
        self.app._dependency_cache.clear()

        try:
            # State machine flow - all wrapped in try-catch for ValidationError
            result = self.state_route_exists()
            if not result.continue_processing:
                return result.response

            result = self.state_service_available()
            if not result.continue_processing:
                return result.response

            result = self.state_known_method()
            if not result.continue_processing:
                return result.response

            result = self.state_uri_too_long()
            if not result.continue_processing:
                return result.response

            result = self.state_method_allowed()
            if not result.continue_processing:
                return result.response

            result = self.state_malformed_request()
            if not result.continue_processing:
                return result.response

            result = self.state_authorized()
            if not result.continue_processing:
                return result.response

            result = self.state_forbidden()
            if not result.continue_processing:
                return result.response

            result = self.state_content_headers_valid()
            if not result.continue_processing:
                return result.response

            result = self.state_resource_exists()
            if not result.continue_processing:
                return result.response

            # Content negotiation states
            result = self.state_content_types_provided()
            if not result.continue_processing:
                return result.response

            result = self.state_content_types_accepted()
            if not result.continue_processing:
                return result.response

            return self.state_execute_and_render()

        except ValidationError as e:
            return Response(
                422,
                json.dumps({"error": "Validation failed", "details": e.errors()}),
                content_type="application/json",
            )

    def state_route_exists(self) -> StateMachineResult:
        """B13: Check if route exists."""
        route_match = self.app._find_route(self.request.method, self.request.path)
        if route_match is None:
            callback = self._get_callback("route_not_found")
            if callback:
                try:
                    response = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if isinstance(response, Response):
                        return StateMachineResult(False, response)
                    return StateMachineResult(
                        False, Response(404, str(response) if response else "Not Found")
                    )
                except Exception as e:
                    return StateMachineResult(
                        False,
                        Response(500, f"Error in route_not_found callback: {str(e)}"),
                    )
            return StateMachineResult(False, Response(404, "Not Found"))

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
                        False, Response(503, "Service Unavailable")
                    )
            except Exception as e:
                return StateMachineResult(
                    False, Response(503, f"Service check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_known_method(self) -> StateMachineResult:
        """B11: Check if HTTP method is known."""
        callback = self._get_callback("known_method")
        if callback:
            try:
                known = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not known:
                    return StateMachineResult(False, Response(501, "Not Implemented"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(501, f"Method check failed: {str(e)}")
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
                return StateMachineResult(False, Response(501, "Not Implemented"))
        return StateMachineResult(True)

    def state_uri_too_long(self) -> StateMachineResult:
        """B10: Check if URI is too long."""
        callback = self._get_callback("uri_too_long")
        if callback:
            try:
                too_long = self.app._call_with_injection(callback, self.request, self.route_handler)
                if too_long:
                    return StateMachineResult(False, Response(414, "URI Too Long"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(414, f"URI length check failed: {str(e)}")
                )
        else:
            # Default: check if URI is longer than 2048 characters
            if len(self.request.path) > 2048:
                return StateMachineResult(False, Response(414, "URI Too Long"))
        return StateMachineResult(True)

    def state_method_allowed(self) -> StateMachineResult:
        """B9: Check if method is allowed for this resource."""
        callback = self._get_callback("method_allowed")
        if callback:
            try:
                allowed = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not allowed:
                    return StateMachineResult(
                        False, Response(405, "Method Not Allowed")
                    )
            except Exception as e:
                return StateMachineResult(
                    False, Response(405, f"Method check failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_malformed_request(self) -> StateMachineResult:
        """B8: Check if request is malformed."""
        callback = self._get_callback("malformed_request")
        if callback:
            try:
                malformed = self.app._call_with_injection(callback, self.request, self.route_handler)
                if malformed:
                    return StateMachineResult(False, Response(400, "Bad Request"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(400, f"Request validation failed: {str(e)}")
                )
        return StateMachineResult(True)

    def state_authorized(self) -> StateMachineResult:
        """B7: Check if request is authorized."""
        callback = self._get_callback("authorized")
        if callback:
            try:
                authorized = self.app._call_with_injection(callback, self.request, self.route_handler)
                if not authorized:
                    return StateMachineResult(False, Response(401, "Unauthorized"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(401, f"Authorization check failed: {str(e)}")
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
                            return StateMachineResult(False, Response(403, "Forbidden"))
                    except Exception:
                        return StateMachineResult(False, Response(403, "Forbidden"))
                else:
                    # Use the regular callback
                    forbidden = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if forbidden:
                        return StateMachineResult(False, Response(403, "Forbidden"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(403, f"Permission check failed: {str(e)}")
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
                        False, Response(400, "Bad Request - Invalid Headers")
                    )
            except Exception as e:
                return StateMachineResult(
                    False, Response(400, f"Header validation failed: {str(e)}")
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
                            return StateMachineResult(False, Response(404, "Not Found"))
                        # Cache the resolved value for later use in the handler
                        self.app._dependency_cache.set(
                            wrapper.original_name, resolved_value
                        )
                    except Exception as e:
                        return StateMachineResult(
                            False, Response(404, "Resource Not Found")
                        )
                else:
                    # Use the regular callback
                    exists = self.app._call_with_injection(callback, self.request, self.route_handler)
                    if not exists:
                        return StateMachineResult(False, Response(404, "Not Found"))
            except Exception as e:
                return StateMachineResult(
                    False, Response(404, f"Resource check failed: {str(e)}")
                )
        return StateMachineResult(True)

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
            return StateMachineResult(
                False, Response(500, "No content renderers available")
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
                406,
                f"Not Acceptable. Available types: {', '.join(set(available_types))}",
                headers={"Content-Type": "text/plain"},
                request=self.request,
                available_content_types=available_types,
            ),
        )

    def state_execute_and_render(self) -> Response:
        """Execute the route handler and render the response."""
        try:
            # First, execute the main handler to get the result
            main_result = self.app._call_with_injection(
                self.route_handler.handler, self.request, self.route_handler
            )

            # Check return type annotation for response validation
            sig = inspect.signature(self.route_handler.handler)
            return_annotation = sig.return_annotation

            # Handle different return type scenarios
            if return_annotation is None or return_annotation is type(None):
                # Explicitly annotated as None -> return 204 No Content
                return Response(204, request=self.request, available_content_types=self.get_available_content_types())
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
                        422,
                        json.dumps(
                            {
                                "error": "Response validation failed",
                                "details": e.errors(),
                            }
                        ),
                        content_type="application/json",
                        request=self.request,
                        available_content_types=self.get_available_content_types(),
                    )
                except Exception:
                    # If validation fails for other reasons, log but don't crash
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
                    200,
                    str(rendered_result),
                    content_type=self.chosen_renderer.media_type,
                    request=self.request,
                    available_content_types=self.get_available_content_types(),
                )
            else:
                # Use regular global renderer
                result = main_result

            # If result is already a Response, update it with request info for Vary header
            if isinstance(result, Response):
                if not result.content_type and self.chosen_renderer:
                    result.content_type = self.chosen_renderer.media_type
                    result.headers = result.headers or {}
                    result.headers["Content-Type"] = self.chosen_renderer.media_type

                # Add request and content type info for Vary header if not already set
                if not result.request:
                    result.request = self.request
                if not result.available_content_types:
                    result.available_content_types = self.get_available_content_types()
                    # Re-run __post_init__ to add Vary header
                    result.__post_init__()
                return result

            # Render the result using the chosen renderer
            if self.chosen_renderer:
                rendered_body = self.chosen_renderer.render(result, self.request)
                return Response(
                    200,
                    rendered_body,
                    content_type=self.chosen_renderer.media_type,
                    request=self.request,
                    available_content_types=self.get_available_content_types(),
                )
            else:
                # Fallback to plain text
                return Response(
                    200,
                    str(result),
                    content_type="text/plain",
                    request=self.request,
                    available_content_types=self.get_available_content_types(),
                )
        except ValidationError as e:
            return Response(
                422,
                json.dumps({"error": "Validation failed", "details": e.json()}),
                content_type="application/json",
                request=self.request,
                available_content_types=self.get_available_content_types(),
            )
        except Exception as e:
            return Response(
                500,
                f"Internal Server Error: {str(e)}",
                request=self.request,
                available_content_types=self.get_available_content_types(),
            )

    def _get_callback(self, state_name: str) -> Optional[Callable]:
        """Get callback for a state, preferring dependency callbacks over defaults."""
        # First check if we have a dependency callback for this state
        if state_name in self.dependency_callbacks:
            return self.dependency_callbacks[state_name].func

        # Fall back to default callbacks
        return self.app._default_callbacks.get(state_name)

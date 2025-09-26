"""
Main application class for the REST framework.
"""

import inspect
import json
import os
import re
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from .content_renderers import (
    ContentRenderer,
    HTMLRenderer,
    JSONRenderer,
    PlainTextRenderer,
)
from .dependencies import (
    ContentNegotiationWrapper,
    DependencyCache,
    DependencyWrapper,
    HeadersWrapper,
    ValidationWrapper,
)
from .exceptions import PYDANTIC_AVAILABLE
from .models import HTTPMethod, Request, Response
from .state_machine import RequestStateMachine


class RouteHandler:
    """Represents a registered route and its handler."""

    def __init__(self, method: HTTPMethod, path: str, handler: Callable):
        self.method = method
        self.path = path
        self.handler = handler
        self.path_pattern = self._compile_path_pattern(path)
        self.content_renderers: Dict[str, ContentNegotiationWrapper] = {}
        self.validation_wrappers: List[ValidationWrapper] = []
        # Per-route dependency tracking
        self.dependencies: Dict[str, Union[Callable, DependencyWrapper]] = {}
        self.validation_dependencies: Dict[str, ValidationWrapper] = {}
        self.headers_dependencies: Dict[str, HeadersWrapper] = {}

    def _compile_path_pattern(self, path: str) -> str:
        """Convert path with {param} syntax to a pattern for matching."""
        # Replace {param} with named regex groups
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        return f"^{pattern}$"

    def matches(self, method: HTTPMethod, path: str) -> Optional[Dict[str, str]]:
        """Check if this route matches the given method and path."""
        if self.method != method:
            return None

        match = re.match(self.path_pattern, path)
        if match:
            return match.groupdict()
        return None

    def add_content_renderer(
        self, content_type: str, wrapper: ContentNegotiationWrapper
    ):
        """Add a content-specific renderer for this route."""
        self.content_renderers[content_type] = wrapper

    def add_validation_wrapper(self, wrapper: ValidationWrapper):
        self.validation_wrappers.append(wrapper)


class RestApplication:
    """Main application class for the REST framework."""

    def __init__(self):
        self._routes: List[RouteHandler] = []
        self._dependencies: Dict[str, Union[Callable, DependencyWrapper]] = {}
        self._validation_dependencies: Dict[str, ValidationWrapper] = {}
        self._headers_dependencies: Dict[str, HeadersWrapper] = {}
        self._default_callbacks: Dict[str, Callable] = {}
        self._dependency_cache = DependencyCache()
        self._content_renderers: Dict[str, ContentRenderer] = {}

        # Add default content renderers
        self.add_content_renderer(JSONRenderer())
        self.add_content_renderer(HTMLRenderer())
        self.add_content_renderer(PlainTextRenderer())

    def add_content_renderer(self, renderer: ContentRenderer):
        """Add a global content renderer."""
        self._content_renderers[renderer.media_type] = renderer

    def dependency(self, name: Optional[str] = None):
        """Decorator to register a dependency provider."""

        def decorator(func: Callable):
            dep_name = name or func.__name__
            self._dependencies[dep_name] = func
            return func

        return decorator

    # State machine callback decorators for dependencies
    def resource_exists(self, func: Callable):
        """Decorator to wrap a dependency with resource existence checking."""
        wrapper = DependencyWrapper(func, "resource_exists", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    def resource_from_request(self, func: Callable):
        """Decorator to wrap a dependency for creating resource from request (for POST)."""
        wrapper = DependencyWrapper(func, "resource_from_request", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    def forbidden(self, func: Callable):
        """Decorator to wrap a dependency with forbidden checking."""
        wrapper = DependencyWrapper(func, "forbidden", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    def authorized(self, func: Callable):
        """Decorator to wrap a dependency with authorization checking."""
        wrapper = DependencyWrapper(func, "authorized", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    def default_headers(self, func: Callable):
        """Decorator to register a headers manipulation function."""
        wrapper = HeadersWrapper(func, func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.headers_dependencies[func.__name__] = wrapper
            route.dependencies[func.__name__] = func
        else:
            self._headers_dependencies[func.__name__] = wrapper
            self._dependencies[func.__name__] = func
        return func

    def generate_etag(self, func: Callable):
        """Decorator to wrap a dependency with ETag generation for conditional requests."""
        wrapper = DependencyWrapper(func, "generate_etag", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    def last_modified(self, func: Callable):
        """Decorator to wrap a dependency with Last-Modified date for conditional requests."""
        wrapper = DependencyWrapper(func, "last_modified", func.__name__)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.dependencies[func.__name__] = wrapper
        else:
            self._dependencies[func.__name__] = wrapper
        return func

    # Content negotiation decorators
    def renders(self, content_type: str):
        """Decorator to register a content-type specific renderer for an endpoint."""

        def decorator(func: Callable):
            # Find the most recently added route (should be the one this renderer is for)
            if self._routes:
                route = self._routes[-1]
                handler_name = route.handler.__name__
                wrapper = ContentNegotiationWrapper(func, content_type, handler_name)
                route.add_content_renderer(content_type, wrapper)

                # Also register this as a dependency so it can be injected
                self._dependencies[func.__name__] = func
            return func

        return decorator

    # Simplified validation decorator - just expects Pydantic model return
    def validates(self, func: Callable):
        """Decorator to mark a function as returning a validated Pydantic model."""
        if not PYDANTIC_AVAILABLE:
            raise ImportError("Pydantic is required for validation features")

        wrapper = ValidationWrapper(func)
        # Add to most recent route if it exists, otherwise add globally
        if self._routes:
            route = self._routes[-1]
            route.validation_dependencies[func.__name__] = wrapper
            route.dependencies[func.__name__] = func
        else:
            self._validation_dependencies[func.__name__] = wrapper
            self._dependencies[func.__name__] = func
        return func

    # Default state machine callbacks
    def default_service_available(self, func: Callable):
        """Register a default service_available callback."""
        self._default_callbacks["service_available"] = func
        return func

    def default_known_method(self, func: Callable):
        """Register a default known_method callback."""
        self._default_callbacks["known_method"] = func
        return func

    def default_uri_too_long(self, func: Callable):
        """Register a default uri_too_long callback."""
        self._default_callbacks["uri_too_long"] = func
        return func

    def default_method_allowed(self, func: Callable):
        """Register a default method_allowed callback."""
        self._default_callbacks["method_allowed"] = func
        return func

    def default_malformed_request(self, func: Callable):
        """Register a default malformed_request callback."""
        self._default_callbacks["malformed_request"] = func
        return func

    def default_authorized(self, func: Callable):
        """Register a default authorized callback."""
        self._default_callbacks["authorized"] = func
        return func

    def default_forbidden(self, func: Callable):
        """Register a default forbidden callback."""
        self._default_callbacks["forbidden"] = func
        return func

    def default_content_headers_valid(self, func: Callable):
        """Register a default content_headers_valid callback."""
        self._default_callbacks["content_headers_valid"] = func
        return func

    def default_resource_exists(self, func: Callable):
        """Register a default resource_exists callback."""
        self._default_callbacks["resource_exists"] = func
        return func

    def default_route_not_found(self, func: Callable):
        """Register a default route_not_found callback."""
        self._default_callbacks["route_not_found"] = func
        return func

    # HTTP method decorators
    def get(self, path: str):
        """Decorator to register a GET route handler."""
        return self._route_decorator(HTTPMethod.GET, path)

    def post(self, path: str):
        """Decorator to register a POST route handler."""
        return self._route_decorator(HTTPMethod.POST, path)

    def put(self, path: str):
        """Decorator to register a PUT route handler."""
        return self._route_decorator(HTTPMethod.PUT, path)

    def delete(self, path: str):
        """Decorator to register a DELETE route handler."""
        return self._route_decorator(HTTPMethod.DELETE, path)

    def patch(self, path: str):
        """Decorator to register a PATCH route handler."""
        return self._route_decorator(HTTPMethod.PATCH, path)

    def _route_decorator(self, method: HTTPMethod, path: str):
        """Internal method to create route decorators."""

        def decorator(func: Callable):
            route = RouteHandler(method, path, func)
            self._routes.append(route)
            return func

        return decorator

    def _resolve_dependency(
        self, param_name: str, param_type: Optional[Type], request: Request, route: Optional[RouteHandler] = None
    ) -> Any:
        """Resolve a dependency by name and type."""
        # Check cache first
        cached_value = self._dependency_cache.get(param_name)
        if cached_value is not None:
            return cached_value

        # Built-in dependencies
        if param_name == "request" or param_type == Request:
            self._dependency_cache.set(param_name, request)
            return request
        elif param_name == "body":
            self._dependency_cache.set(param_name, request.body)
            return request.body
        elif param_name == "query_params":
            query_params = request.query_params or {}
            self._dependency_cache.set(param_name, query_params)
            return query_params
        elif param_name == "path_params":
            path_params = request.path_params or {}
            self._dependency_cache.set(param_name, path_params)
            return path_params
        elif param_name == "headers":
            # Get or create the current headers state
            headers = self._dependency_cache.get("headers")
            if headers is None:
                # Initialize headers with automatic headers already calculated
                headers = self._get_initial_headers(request, route)
                self._dependency_cache.set("headers", headers)
            return headers

        # Check if the parameter name is in path_params
        if request.path_params and param_name in request.path_params:
            path_value = request.path_params[param_name]
            self._dependency_cache.set(param_name, path_value)
            return path_value

        # Check route-specific dependencies first if route is provided
        dep_or_wrapper = None
        validation_dependency = None

        if route and param_name in route.dependencies:
            dep_or_wrapper = route.dependencies[param_name]
            if param_name in route.validation_dependencies:
                validation_dependency = route.validation_dependencies[param_name]
        elif param_name in self._dependencies:
            # Fall back to global dependencies
            dep_or_wrapper = self._dependencies[param_name]
            if param_name in self._validation_dependencies:
                validation_dependency = self._validation_dependencies[param_name]

        if dep_or_wrapper is not None:
            if isinstance(dep_or_wrapper, DependencyWrapper):
                # For wrapped dependencies, the state machine will handle the resolution
                # and early exit logic. Here we just call the function.
                resolved_value = self._call_with_injection(dep_or_wrapper.func, request, route)
                self._dependency_cache.set(param_name, resolved_value)
                return resolved_value
            else:
                # Regular dependency - check if it's a validation dependency
                if validation_dependency is not None:
                    # This is a validation function that should return a Pydantic model
                    # Call it and validate the result
                    result = self._call_with_injection(dep_or_wrapper, request, route)

                    # The function should return a Pydantic model
                    # If ValidationError occurs, it will be caught by the state machine
                    if hasattr(result, "model_validate") or hasattr(
                        result, "model_dump"
                    ):
                        # It's already a Pydantic model, cache and return
                        self._dependency_cache.set(param_name, result)
                        return result
                    else:
                        # If it's not a Pydantic model, something went wrong
                        raise ValueError(
                            f"Validation function {param_name} must return a Pydantic model"
                        )
                else:
                    # Regular dependency
                    resolved_value = self._call_with_injection(dep_or_wrapper, request, route)
                    self._dependency_cache.set(param_name, resolved_value)
                    return resolved_value

        raise ValueError(f"Unable to resolve dependency: {param_name}")

    def _call_with_injection(self, func: Callable, request: Request, route: Optional[RouteHandler] = None) -> Any:
        """Call a function with dependency injection."""
        sig = inspect.signature(func)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            param_type = (
                param.annotation
                if param.annotation != inspect.Parameter.empty
                else None
            )
            resolved_value = self._resolve_dependency(param_name, param_type, request, route)
            kwargs[param_name] = resolved_value

        return func(**kwargs)

    def _get_initial_headers(self, request: Request, route: Optional[RouteHandler]) -> Dict[str, str]:
        """Get initial headers with Vary header pre-calculated."""
        headers = {}

        # Calculate Vary header values
        vary_values = []

        # Add "Authorization" to Vary if request has Authorization header
        if request.headers.get("Authorization"):
            vary_values.append("Authorization")

        # Add "Accept" to Vary if endpoint accepts more than one content type
        available_content_types = list(self._content_renderers.keys())
        if route and route.content_renderers:
            available_content_types.extend(route.content_renderers.keys())
        available_content_types = list(set(available_content_types))  # Remove duplicates

        if len(available_content_types) > 1:
            vary_values.append("Accept")

        # Set Vary header if we have values to include
        if vary_values:
            headers["Vary"] = ", ".join(vary_values)

        return headers

    def _find_route(
        self, method: HTTPMethod, path: str
    ) -> Optional[Tuple[RouteHandler, Dict[str, str]]]:
        """Find a matching route for the given method and path."""
        for route in self._routes:
            path_params = route.matches(method, path)
            if path_params is not None:
                return route, path_params
        return None

    def execute(self, request: Request) -> Response:
        """Execute a request through the state machine."""
        # Create a new state machine for each request to avoid state pollution
        state_machine = RequestStateMachine(self)
        return state_machine.process_request(request)

    def _is_pydantic_model(self, annotation) -> bool:
        """Check if the annotation is a Pydantic model."""
        if not PYDANTIC_AVAILABLE or annotation is None:
            return False
        try:
            return hasattr(annotation, "model_fields") and hasattr(
                annotation, "model_validate"
            )
        except (TypeError, AttributeError):
            return False

    def _is_optional_type(self, annotation) -> Tuple[bool, Type]:
        """Check if type annotation is Optional and return the inner type."""
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T] which is Union[T, None]
                inner_type = args[0] if args[1] is type(None) else args[1]
                return True, inner_type
        return False, annotation

    def _get_pydantic_schema(self, model_class) -> Dict[str, Any]:
        """Extract JSON schema from Pydantic model."""
        if not self._is_pydantic_model(model_class):
            return {"type": "object"}
        try:
            return model_class.model_json_schema()
        except (AttributeError, TypeError):
            return {"type": "object"}

    def _pydantic_field_to_openapi_param(
        self, field_name: str, field_info, model_class
    ) -> Dict[str, Any]:
        """Convert a Pydantic field to OpenAPI parameter definition."""
        param = {
            "name": field_name,
            "in": "query",  # Will be overridden for path params
            "required": True,
            "schema": {"type": "string"},
        }

        try:
            # Get field info from Pydantic model
            field_annotation = model_class.model_fields.get(field_name)
            if field_annotation:
                # Check if field is optional
                is_optional, inner_type = self._is_optional_type(
                    field_annotation.annotation
                )
                param["required"] = not is_optional and field_annotation.default is None

                # Basic type mapping
                if inner_type is str:
                    param["schema"] = {"type": "string"}
                elif inner_type is int:
                    param["schema"] = {"type": "integer"}
                elif inner_type is float:
                    param["schema"] = {"type": "number"}
                elif inner_type is bool:
                    param["schema"] = {"type": "boolean"}
                else:
                    param["schema"] = {"type": "string"}

                # Add description if available
                if (
                    hasattr(field_annotation, "description")
                    and field_annotation.description
                ):
                    param["description"] = field_annotation.description

        except (AttributeError, TypeError):
            pass

        return param

    def generate_openapi_json(
        self,
        title: str = "REST API",
        version: str = "1.0.0",
        description: str = "API generated by REST Framework",
    ) -> str:
        """Generate OpenAPI 3.0 JSON specification from registered routes."""

        # Keep track of all schemas we've seen to avoid duplicates
        collected_schemas: Dict[str, Dict[str, Any]] = {}

        def _collect_schema(model_class) -> Optional[str]:
            """Collect a Pydantic model schema and return its reference name."""
            if not self._is_pydantic_model(model_class):
                return None

            schema_name = model_class.__name__
            if schema_name not in collected_schemas:
                collected_schemas[schema_name] = self._get_pydantic_schema(model_class)

            return schema_name

        def _get_schema_ref(schema_name: str) -> Dict[str, str]:
            """Get a $ref object for a schema."""
            return {"$ref": f"#/components/schemas/{schema_name}"}

        def _extract_path_parameters(
            path: str, route: RouteHandler
        ) -> List[Dict[str, Any]]:
            """Extract path parameters from a route path."""
            params = []

            # First, check if there are validation dependencies that depend on path_params
            sig = inspect.signature(route.handler)
            path_params_from_validation = []

            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a validation dependency
                if param_name in self._validation_dependencies:
                    validation_wrapper = self._validation_dependencies[param_name]

                    # Check if this validation function depends on path_params
                    if (
                        hasattr(validation_wrapper, "depends_on_path_params")
                        and validation_wrapper.depends_on_path_params
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            # Extract Pydantic model fields
                            if self._is_pydantic_model(return_annotation):
                                try:
                                    model_fields = return_annotation.model_fields
                                    for field_name, field_info in model_fields.items():
                                        param_def = (
                                            self._pydantic_field_to_openapi_param(
                                                field_name,
                                                field_info,
                                                return_annotation,
                                            )
                                        )
                                        param_def["in"] = (
                                            "path"  # Set to path instead of the default
                                        )
                                        path_params_from_validation.append(param_def)
                                except (AttributeError, TypeError):
                                    # If we can't extract fields, skip this validation function
                                    pass

            # If we found path parameters from validation dependencies, use those
            if path_params_from_validation:
                return path_params_from_validation

            # Otherwise, fall back to extracting from path pattern (assuming strings)
            pattern = re.findall(r"\{(\w+)\}", path)
            for param_name in pattern:
                params.append(
                    {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )
            return params

        def _extract_query_string_parameters(
            route: RouteHandler,
        ) -> List[Dict[str, Any]]:
            """Extract query string parameters from validation dependencies."""
            params = []

            # Look at the route handler's parameters to find validation dependencies
            sig = inspect.signature(route.handler)
            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a validation dependency
                if param_name in self._validation_dependencies:
                    validation_wrapper = self._validation_dependencies[param_name]

                    # Check if this validation function depends on query_params
                    if (
                        hasattr(validation_wrapper, "depends_on_query_params")
                        and validation_wrapper.depends_on_query_params
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            # Extract Pydantic model fields
                            if self._is_pydantic_model(return_annotation):
                                try:
                                    model_fields = return_annotation.model_fields
                                    for field_name, field_info in model_fields.items():
                                        param_def = (
                                            self._pydantic_field_to_openapi_param(
                                                field_name,
                                                field_info,
                                                return_annotation,
                                            )
                                        )
                                        param_def["in"] = (
                                            "query"  # Set to query instead of the default
                                        )
                                        params.append(param_def)
                                except (AttributeError, TypeError):
                                    # If we can't extract fields, skip this validation function
                                    pass

            return params

        def _extract_request_body_schema(
            route: RouteHandler,
        ) -> Optional[Dict[str, Any]]:
            """Extract request body schema from validation dependencies that depend on body."""
            sig = inspect.signature(route.handler)

            for param_name, param in sig.parameters.items():
                # Check if this parameter corresponds to a validation dependency
                if param_name in self._validation_dependencies:
                    validation_wrapper = self._validation_dependencies[param_name]

                    # Check if this validation function depends on body
                    if (
                        hasattr(validation_wrapper, "depends_on_body")
                        and validation_wrapper.depends_on_body
                    ):
                        # Get the return type annotation of the validation function
                        return_annotation = inspect.signature(
                            validation_wrapper.func
                        ).return_annotation
                        if (
                            return_annotation
                            and return_annotation != inspect.Parameter.empty
                        ):
                            if self._is_pydantic_model(return_annotation):
                                # Collect the schema and return a reference
                                schema_name = _collect_schema(return_annotation)
                                if schema_name:
                                    return _get_schema_ref(schema_name)

            return None

        def _extract_response_schema(route: RouteHandler) -> Optional[Dict[str, Any]]:
            """Extract response schema from handler return type annotation. Returns None if no schema should be included."""
            sig = inspect.signature(route.handler)
            return_annotation = sig.return_annotation

            # Check if return type is explicitly None
            if return_annotation is type(None):
                return None  # No schema for 204 responses

            # Check if no annotation is provided
            if return_annotation == inspect.Parameter.empty:
                return None  # No schema for unannotated handlers

            if return_annotation and return_annotation != inspect.Parameter.empty:
                # Handle Optional types
                is_optional, inner_type = self._is_optional_type(return_annotation)
                actual_type = inner_type if is_optional else return_annotation

                # Handle List types
                origin = get_origin(actual_type)
                if origin is list:
                    # This is List[SomeType]
                    args = get_args(actual_type)
                    if args and self._is_pydantic_model(args[0]):
                        schema_name = _collect_schema(args[0])
                        if schema_name:
                            return {
                                "type": "array",
                                "items": _get_schema_ref(schema_name),
                            }
                elif self._is_pydantic_model(actual_type):
                    schema_name = _collect_schema(actual_type)
                    if schema_name:
                        return _get_schema_ref(schema_name)

            # Default fallback for other annotated types
            return {"type": "object"}

        def _route_uses_validation_dependencies(route: RouteHandler) -> bool:
            """Check if a route uses any validation dependencies that return Pydantic models."""
            sig = inspect.signature(route.handler)
            for param_name, param in sig.parameters.items():
                if param_name in self._validation_dependencies:
                    return True
            return False

        def _convert_path_to_openapi(path: str) -> str:
            """Convert {param} syntax to OpenAPI {param} syntax."""
            return path

        def _get_operation_info(route: RouteHandler) -> Dict[str, Any]:
            """Extract operation information from a route handler."""
            # Extract response schema from handler return type
            response_schema = _extract_response_schema(route)

            # Check if this is a None return type (should use 204)
            sig = inspect.signature(route.handler)
            return_annotation = sig.return_annotation

            operation: Dict[str, Any] = {
                "summary": route.handler.__name__.replace("_", " ").title(),
                "responses": {},
            }

            if return_annotation is None:
                # Handler explicitly returns None -> 204 No Content
                operation["responses"]["204"] = {"description": "No Content"}
            elif response_schema is inspect.Signature.empty:
                # No annotation or no schema -> 200 without content schema
                operation["responses"]["200"] = {"description": "Successful response"}
            elif response_schema:
                # Has schema -> 200 with content
                operation["responses"]["200"] = {
                    "description": "Successful response",
                    "content": {"application/json": {"schema": response_schema}},
                }
            else:
                # Has schema -> 200 with content
                operation["responses"]["200"] = {
                    "description": "Successful response",
                }

            # Check if this route uses validation dependencies and add 422 response
            uses_validation = _route_uses_validation_dependencies(route)
            if uses_validation:
                operation["responses"]["422"] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": {"type": "string"},
                                    "details": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }

            # Add description from docstring if available
            if route.handler.__doc__:
                operation["description"] = route.handler.__doc__.strip()

            # Add path parameters
            path_params = _extract_path_parameters(route.path, route)
            # Add query string parameters
            query_params = _extract_query_string_parameters(route)

            # Combine all parameters
            all_params = path_params + query_params
            if all_params:
                operation["parameters"] = all_params

            # Add request body for POST/PUT/PATCH methods
            if route.method.value in ["POST", "PUT", "PATCH"]:
                # Try to extract request body schema from validation dependencies
                request_body_schema = _extract_request_body_schema(route)
                if request_body_schema:
                    operation["requestBody"] = {
                        "content": {"application/json": {"schema": request_body_schema}}
                    }

            return operation

        # Build the OpenAPI specification
        openapi_spec: Dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": title, "version": version, "description": description},
            "paths": {},
        }

        # Process all routes to collect schemas and build paths
        for route in self._routes:
            openapi_path = _convert_path_to_openapi(route.path)

            if openapi_path not in openapi_spec["paths"]:
                openapi_spec["paths"][openapi_path] = {}

            method_lower = route.method.value.lower()
            openapi_spec["paths"][openapi_path][method_lower] = _get_operation_info(
                route
            )

        # Add components section if we have collected schemas
        if collected_schemas:
            openapi_spec["components"] = {"schemas": collected_schemas}

        return json.dumps(openapi_spec, indent=2)

    def save_openapi_json(
        self,
        filename: str = "openapi.json",
        docs_dir: str = "docs",
        title: str = "REST API",
        version: str = "1.0.0",
        description: str = "API generated by REST Framework",
    ) -> str:
        """Generate and save OpenAPI JSON specification to a file in the docs directory."""

        # Create docs directory if it doesn't exist
        if not os.path.exists(docs_dir):
            os.makedirs(docs_dir)

        # Generate OpenAPI JSON
        openapi_json = self.generate_openapi_json(title, version, description)

        # Write to file
        file_path = os.path.join(docs_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(openapi_json)

        return file_path

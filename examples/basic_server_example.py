#!/usr/bin/env python3
"""
Basic HTTP Server Example for RestMachine

This example demonstrates how to create a simple REST API using RestMachine
and serve it with different HTTP servers (Uvicorn or Hypercorn).

Run with:
    python examples/basic_server_example.py
    python examples/basic_server_example.py --server hypercorn
    python examples/basic_server_example.py --server uvicorn --http-version http2
"""

import argparse
import sys
from typing import Dict, Any

from restmachine import RestApplication, Response


def create_todo_app() -> RestApplication:
    """Create a simple TODO application."""
    app = RestApplication()

    # In-memory storage for demo purposes
    todos: Dict[str, Dict[str, Any]] = {}
    next_id = 1

    @app.get("/")
    def home():
        """Welcome endpoint."""
        return {
            "message": "Welcome to RestMachine TODO API",
            "version": "1.0.0",
            "endpoints": {
                "GET /todos": "List all todos",
                "POST /todos": "Create a new todo",
                "GET /todos/{id}": "Get a specific todo",
                "PUT /todos/{id}": "Update a todo",
                "DELETE /todos/{id}": "Delete a todo"
            }
        }

    @app.get("/todos")
    def list_todos(query_params):
        """List all todos with optional filtering."""
        completed = query_params.get("completed")

        result = list(todos.values())

        if completed is not None:
            is_completed = completed.lower() == "true"
            result = [todo for todo in result if todo["completed"] == is_completed]

        return {
            "todos": result,
            "total": len(result)
        }

    @app.post("/todos")
    def create_todo(json_body):
        """Create a new todo item."""
        nonlocal next_id

        # Validate required fields
        if not json_body or "title" not in json_body:
            return Response(400, {"error": "Title is required"})

        todo = {
            "id": str(next_id),
            "title": json_body["title"],
            "description": json_body.get("description", ""),
            "completed": json_body.get("completed", False),
            "created_at": "2024-01-01T00:00:00Z"  # In real app, use actual timestamp
        }

        todos[str(next_id)] = todo
        next_id += 1

        return Response(201, todo)

    @app.get("/todos/{todo_id}")
    def get_todo(path_params):
        """Get a specific todo by ID."""
        todo_id = path_params["todo_id"]

        if todo_id not in todos:
            return Response(404, {"error": "Todo not found"})

        return todos[todo_id]

    @app.put("/todos/{todo_id}")
    def update_todo(path_params, json_body):
        """Update a todo item."""
        todo_id = path_params["todo_id"]

        if todo_id not in todos:
            return Response(404, {"error": "Todo not found"})

        # Update fields if provided
        todo = todos[todo_id]
        if "title" in json_body:
            todo["title"] = json_body["title"]
        if "description" in json_body:
            todo["description"] = json_body["description"]
        if "completed" in json_body:
            todo["completed"] = json_body["completed"]

        return todo

    @app.delete("/todos/{todo_id}")
    def delete_todo(path_params):
        """Delete a todo item."""
        todo_id = path_params["todo_id"]

        if todo_id not in todos:
            return Response(404, {"error": "Todo not found"})

        del todos[todo_id]
        return None  # 204 No Content

    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "todos_count": len(todos)}

    return app


def main():
    """Main function to run the server."""
    parser = argparse.ArgumentParser(description="RestMachine TODO API Server")
    parser.add_argument(
        "--server",
        choices=["uvicorn", "hypercorn"],
        default="uvicorn",
        help="HTTP server to use (default: uvicorn)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--http-version",
        choices=["http1", "http2", "http3"],
        default="http1",
        help="HTTP version to use (default: http1)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development (uvicorn only)"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level (default: info)"
    )

    args = parser.parse_args()

    # Validate HTTP version for selected server
    if args.server == "uvicorn" and args.http_version == "http3":
        print("Error: Uvicorn does not support HTTP/3. Use Hypercorn for HTTP/3.", file=sys.stderr)
        sys.exit(1)

    # Create the application
    app = create_todo_app()

    print(f"Starting {args.server} server...")
    print(f"Server: {args.server}")
    print(f"HTTP Version: {args.http_version.upper()}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"URL: http://{args.host}:{args.port}")
    print()
    print("Available endpoints:")
    print("  GET    /                - API information")
    print("  GET    /todos           - List todos")
    print("  POST   /todos           - Create todo")
    print("  GET    /todos/{id}      - Get todo")
    print("  PUT    /todos/{id}      - Update todo")
    print("  DELETE /todos/{id}      - Delete todo")
    print("  GET    /health          - Health check")
    print()

    try:
        if args.server == "uvicorn":
            from restmachine import serve_uvicorn
            serve_uvicorn(
                app,
                host=args.host,
                port=args.port,
                http_version=args.http_version,
                log_level=args.log_level,
                reload=args.reload
            )
        elif args.server == "hypercorn":
            from restmachine import serve_hypercorn
            serve_hypercorn(
                app,
                host=args.host,
                port=args.port,
                http_version=args.http_version,
                log_level=args.log_level
            )
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"Install required dependencies with: pip install 'restmachine[{args.server}]'", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()
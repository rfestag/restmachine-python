"""
Advanced usage example for the REST Framework.

This example demonstrates:
- Complex dependency chains
- State machine callbacks for security and validation
- Custom content renderers
- Resource existence checking
- Authorization and permission systems
- Error handling and custom responses
- Multiple content type support
"""

import json
import time
from typing import Dict, Optional

from restmachine import HTTPMethod, Request, Response, RestApplication

# Create the application
app = RestApplication()

# Simulated databases
users_db = {
    "1": {"id": "1", "name": "Alice", "email": "alice@example.com", "role": "admin"},
    "2": {"id": "2", "name": "Bob", "email": "bob@example.com", "role": "user"},
    "3": {"id": "3", "name": "Charlie", "email": "charlie@example.com", "role": "user"},
}

posts_db = {
    "1": {"id": "1", "title": "Hello World", "content": "First post", "author_id": "1"},
    "2": {
        "id": "2",
        "title": "Second Post",
        "content": "Another post",
        "author_id": "2",
    },
}

# Simulated session store
sessions = {}


# Complex dependency chain
@app.dependency()
def config():
    """Application configuration."""
    return {
        "max_posts_per_user": 10,
        "session_timeout": 3600,
        "admin_endpoints": ["/admin"],
        "rate_limit": 100,
    }


@app.dependency()
def database_connection(config):
    """Simulated database connection."""
    return {
        "users": users_db,
        "posts": posts_db,
        "config": config,
        "connected_at": time.time(),
    }


@app.dependency()
def user_service(database_connection):
    """User service with database access."""

    def get_user(user_id: str) -> Optional[Dict]:
        return database_connection["users"].get(user_id)

    def get_user_by_email(email: str) -> Optional[Dict]:
        for user in database_connection["users"].values():
            if user["email"] == email:
                return user
        return None

    def create_user(user_data: Dict) -> Dict:
        user_id = str(len(database_connection["users"]) + 1)
        user_data["id"] = user_id
        database_connection["users"][user_id] = user_data
        return user_data

    return {"get": get_user, "get_by_email": get_user_by_email, "create": create_user}


@app.dependency()
def post_service(database_connection, user_service):
    """Post service with user validation."""

    def get_post(post_id: str) -> Optional[Dict]:
        return database_connection["posts"].get(post_id)

    def get_posts_by_author(author_id: str) -> list:
        return [
            post
            for post in database_connection["posts"].values()
            if post["author_id"] == author_id
        ]

    def create_post(post_data: Dict, author_id: str) -> Dict:
        # Validate author exists
        if not user_service["get"](author_id):
            raise ValueError("Author not found")

        post_id = str(len(database_connection["posts"]) + 1)
        post_data.update({"id": post_id, "author_id": author_id})
        database_connection["posts"][post_id] = post_data
        return post_data

    return {
        "get": get_post,
        "get_by_author": get_posts_by_author,
        "create": create_post,
    }


# Authentication dependency
@app.dependency()
def auth_service():
    """Authentication service."""

    def create_session(user_id: str) -> str:
        session_id = f"sess_{user_id}_{int(time.time())}"
        sessions[session_id] = {"user_id": user_id, "created_at": time.time()}
        return session_id

    def get_user_from_session(session_id: str) -> Optional[str]:
        session = sessions.get(session_id)
        if not session:
            return None

        # Check if session is expired (1 hour timeout)
        if time.time() - session["created_at"] > 3600:
            del sessions[session_id]
            return None

        return session["user_id"]

    return {"create_session": create_session, "get_user": get_user_from_session}


# State machine callbacks for security
@app.default_service_available
def check_service_health(database_connection):
    """Check if our services are healthy."""
    # Simulate health check
    return time.time() - database_connection["connected_at"] < 86400  # 24 hours


@app.default_authorized
def check_authorization(request: Request, auth_service, user_service):
    """Global authorization check."""
    # Public endpoints don't need auth
    public_endpoints = ["/", "/login", "/register", "/health"]
    if request.path in public_endpoints:
        return True

    # Check for session
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    session_id = auth_header[7:]  # Remove "Bearer "
    user_id = auth_service["get_user"](session_id)

    if not user_id:
        return False

    # Store current user in request for later use
    request.current_user_id = user_id
    return True


@app.default_forbidden
def check_permissions(request: Request, user_service, config):
    """Check if user has permission for this resource."""
    # Skip if not authenticated
    if not hasattr(request, "current_user_id"):
        return False

    current_user = user_service["get"](request.current_user_id)
    if not current_user:
        return True  # Forbidden if user doesn't exist

    # Check admin endpoints
    for admin_endpoint in config["admin_endpoints"]:
        if request.path.startswith(admin_endpoint) and current_user["role"] != "admin":
            return True  # Forbidden for non-admins

    return False  # Not forbidden


# Resource existence checks
@app.resource_exists
def user_exists(request: Request, user_service):
    """Check if user exists for user-specific endpoints."""
    user_id = request.path_params.get("user_id")
    if user_id:
        return user_service["get"](user_id)
    return True  # Not a user-specific endpoint


@app.resource_exists
def post_exists(request: Request, post_service):
    """Check if post exists for post-specific endpoints."""
    post_id = request.path_params.get("post_id")
    if post_id:
        return post_service["get"](post_id)
    return True  # Not a post-specific endpoint


# Custom content renderers
@app.get("/posts/{post_id}")
def get_post_detail(post_exists, user_service):
    """Get detailed post information."""
    post = post_exists
    author = user_service["get"](post["author_id"])

    return {
        "post": post,
        "author": {"id": author["id"], "name": author["name"]},
        "metadata": {"retrieved_at": time.time()},
    }


@app.provides("text/html")
def post_html_renderer(get_post_detail):
    """Custom HTML renderer for post details."""
    data = get_post_detail
    post = data["post"]
    author = data["author"]

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{post["title"]}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .post-header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 20px; }}
            .post-content {{ line-height: 1.6; }}
            .author {{ color: #666; font-style: italic; }}
        </style>
    </head>
    <body>
        <article>
            <div class="post-header">
                <h1>{post["title"]}</h1>
                <p class="author">By {author["name"]}</p>
            </div>
            <div class="post-content">
                <p>{post["content"]}</p>
            </div>
        </article>
    </body>
    </html>
    """


# API Routes
@app.get("/")
def api_info():
    """API information endpoint."""
    return {
        "name": "Advanced REST Framework Example",
        "version": "1.0.0",
        "features": [
            "Authentication with sessions",
            "Role-based permissions",
            "Resource existence checking",
            "Custom content rendering",
            "State machine security",
            "Complex dependency injection",
        ],
        "endpoints": {
            "auth": {
                "POST /login": "Login with email/password",
                "POST /register": "Register new user",
                "POST /logout": "Logout current session",
            },
            "users": {
                "GET /users": "List users (admin only)",
                "GET /users/{id}": "Get user details",
                "POST /users": "Create user (admin only)",
            },
            "posts": {
                "GET /posts": "List all posts",
                "GET /posts/{id}": "Get post details",
                "POST /posts": "Create new post",
                "GET /users/{id}/posts": "Get user's posts",
            },
            "admin": {"GET /admin/stats": "System statistics (admin only)"},
        },
    }


@app.get("/health")
def health_check(database_connection, config):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "uptime": time.time() - database_connection["connected_at"],
        "version": "1.0.0",
    }


@app.post("/login")
def login(auth_service, user_service, json_body):
    """User login endpoint."""
    email = json_body.get("email")
    password = json_body.get("password")  # In real app, check hashed password

    if not email or not password:
        return Response(
            400,
            '{"error": "Email and password required"}',
            content_type="application/json",
        )

    user = user_service["get_by_email"](email)
    if not user:
        return Response(
            401, '{"error": "Invalid credentials"}', content_type="application/json"
        )

    session_id = auth_service["create_session"](user["id"])

    return {
        "message": "Login successful",
        "session_id": session_id,
        "user": {"id": user["id"], "name": user["name"], "role": user["role"]},
    }


@app.post("/register")
def register(user_service, json_body):
    """User registration endpoint."""
    required_fields = ["name", "email"]

    for field in required_fields:
        if field not in json_body:
            return Response(
                400,
                f'{{"error": "Missing field: {field}"}}',
                content_type="application/json",
            )

    # Check if user already exists
    if user_service["get_by_email"](json_body["email"]):
        return Response(
            409, '{"error": "User already exists"}', content_type="application/json"
        )

    # Set default role
    json_body["role"] = "user"

    user = user_service["create"](json_body)

    return Response(
        201,
        json.dumps(
            {
                "message": "User created successfully",
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"],
                },
            }
        ),
        content_type="application/json",
    )


@app.get("/users")
def list_users(user_service, request: Request):
    """List all users (admin only)."""
    # This will be blocked by forbidden check for non-admins
    users = list(user_service["get"](uid) for uid in users_db.keys())
    return {"users": users}


@app.get("/users/{user_id}")
def get_user_detail(user_exists):
    """Get user details."""
    user = user_exists
    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    }


@app.get("/users/{user_id}/posts")
def get_user_posts(user_exists, post_service):
    """Get all posts by a user."""
    user = user_exists
    posts = post_service["get_by_author"](user["id"])
    return {"user": {"id": user["id"], "name": user["name"]}, "posts": posts}


@app.get("/posts")
def list_posts(post_service, user_service):
    """List all posts with author information."""
    posts = []
    for post in posts_db.values():
        author = user_service["get"](post["author_id"])
        posts.append({**post, "author_name": author["name"] if author else "Unknown"})

    return {"posts": posts}


@app.post("/posts")
def create_post(post_service, json_body, request: Request):
    """Create a new post."""
    if "title" not in json_body or "content" not in json_body:
        return Response(
            400,
            '{"error": "Title and content required"}',
            content_type="application/json",
        )

    # Use current user as author
    author_id = request.current_user_id

    try:
        post = post_service["create"](json_body, author_id)

        return Response(
            201,
            json.dumps({"message": "Post created successfully", "post": post}),
            content_type="application/json",
        )

    except ValueError as e:
        return Response(
            400, f'{{"error": "{str(e)}"}}', content_type="application/json"
        )


@app.get("/admin/stats")
def admin_stats(database_connection, config, user_service):
    """System statistics (admin only)."""
    return {
        "statistics": {
            "total_users": len(database_connection["users"]),
            "total_posts": len(database_connection["posts"]),
            "active_sessions": len(sessions),
            "uptime": time.time() - database_connection["connected_at"],
        },
        "configuration": {
            "max_posts_per_user": config["max_posts_per_user"],
            "session_timeout": config["session_timeout"],
        },
    }


def main():
    """Demonstrate the advanced API features."""
    print("REST Framework Advanced Example")
    print("=" * 35)

    # 1. Health check (public)
    print("1. Health Check:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/health",
            headers={"Accept": "application/json"},
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # 2. Register new user
    print("2. Register new user:")
    new_user = {"name": "Dave", "email": "dave@example.com"}
    response = app.execute(
        Request(
            method=HTTPMethod.POST,
            path="/register",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(new_user),
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # 3. Login
    print("3. Login:")
    login_data = {"email": "alice@example.com", "password": "password"}
    response = app.execute(
        Request(
            method=HTTPMethod.POST,
            path="/login",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(login_data),
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")

    # Extract session for authenticated requests
    if response.status_code == 200:
        session_data = json.loads(response.body)
        session_id = session_data["session_id"]
        print(f"Session ID: {session_id}")
    print()

    # 4. Try accessing protected endpoint without auth (should fail)
    print("4. Access protected endpoint without auth:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET, path="/users", headers={"Accept": "application/json"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # 5. Access protected endpoint with auth
    print("5. Access protected endpoint with auth:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {session_id}",
            },
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()

    # 6. Get post with HTML rendering
    print("6. Get post with HTML rendering:")
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/posts/1",
            headers={"Accept": "text/html", "Authorization": f"Bearer {session_id}"},
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print("HTML content generated successfully")
    print()

    # 7. Create new post
    print("7. Create new post:")
    new_post = {"title": "My New Post", "content": "This is a great post!"}
    response = app.execute(
        Request(
            method=HTTPMethod.POST,
            path="/posts",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_id}",
            },
            body=json.dumps(new_post),
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.body}")
    print()


if __name__ == "__main__":
    main()

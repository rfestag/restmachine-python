# Authentication

Implement authentication and authorization in RestMachine using dependency injection. This guide covers API keys, JWT tokens, OAuth, and role-based access control.

## Basic Authentication

### API Key Authentication

Simple API key authentication using headers:

```python
from restmachine import RestApplication, Request, Response
import json

app = RestApplication()

# Database initialized at startup
@app.on_startup
def database():
    """Initialize API keys and user data at startup."""
    return {
        "api_keys": {
            "key_12345": {"user_id": "1", "name": "Alice"},
            "key_67890": {"user_id": "2", "name": "Bob"}
        }
    }

@app.dependency()
def api_key(request: Request) -> str:
    """Extract API key from header."""
    key = request.headers.get('x-api-key')
    if not key:
        raise ValueError("API key required")
    return key

@app.dependency()
def current_user(api_key: str, database):
    """Validate API key and get user."""
    user = database["api_keys"].get(api_key)
    if not user:
        raise ValueError("Invalid API key")
    return user

@app.get('/protected')
def protected_resource(current_user):
    return {
        "message": f"Hello, {current_user['name']}!",
        "user_id": current_user['user_id']
    }

@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    return {
        "error": "Unauthorized",
        "message": message
    }
```

### Bearer Token Authentication

Implement Bearer token authentication:

```python
@app.dependency()
def bearer_token(request: Request) -> str:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get('authorization', '')

    if not auth_header.startswith('Bearer '):
        raise ValueError("Bearer token required")

    return auth_header[7:]  # Remove 'Bearer ' prefix

@app.dependency()
def current_user(bearer_token: str):
    """Validate token and get user."""
    # In production, validate against database or cache
    user = validate_token(bearer_token)
    if not user:
        raise ValueError("Invalid or expired token")
    return user

def validate_token(token: str):
    """Validate token (implement your logic)."""
    # Simplified example
    if token == "valid_token_123":
        return {"id": "1", "name": "Alice", "role": "admin"}
    return None
```

## JWT Authentication

### JWT Token Validation

Use PyJWT for token-based authentication:

```python
import jwt
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
SECRET_KEY = "your-secret-key"  # Use environment variable in production
ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

@app.dependency()
def jwt_token(request: Request) -> str:
    """Extract JWT from Authorization header."""
    auth_header = request.headers.get('authorization', '')

    if not auth_header.startswith('Bearer '):
        raise ValueError("JWT token required")

    return auth_header[7:]

@app.dependency()
def current_user(jwt_token: str) -> Dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            jwt_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        # Check expiration
        exp = payload.get('exp')
        if exp and datetime.fromtimestamp(exp) < datetime.now():
            raise ValueError("Token expired")

        return {
            "id": payload.get('user_id'),
            "email": payload.get('email'),
            "role": payload.get('role', 'user')
        }

    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")

@app.post('/login')
def login(request: Request):
    """Generate JWT token for user."""
    import json
    data = json.loads(request.body)

    # Validate credentials (simplified)
    if data.get('email') == 'alice@example.com' and data.get('password') == 'secret':
        # Create token
        payload = {
            'user_id': '1',
            'email': 'alice@example.com',
            'role': 'admin',
            'exp': datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS),
            'iat': datetime.now()
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": TOKEN_EXPIRY_HOURS * 3600
        }

    return Response(401, json.dumps({"error": "Invalid credentials"}))

@app.get('/profile')
def get_profile(current_user):
    return {
        "user": current_user
    }
```

### Refresh Tokens

Implement refresh token pattern:

```python
from uuid import uuid4

# Store refresh tokens (use Redis in production)
REFRESH_TOKENS = {}

def create_tokens(user_id: str, email: str, role: str):
    """Create access and refresh tokens."""
    # Access token (short-lived)
    access_payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.now() + timedelta(hours=1),
        'iat': datetime.now(),
        'type': 'access'
    }
    access_token = jwt.encode(access_payload, SECRET_KEY, algorithm=ALGORITHM)

    # Refresh token (long-lived)
    refresh_token_id = str(uuid4())
    refresh_payload = {
        'token_id': refresh_token_id,
        'user_id': user_id,
        'exp': datetime.now() + timedelta(days=30),
        'iat': datetime.now(),
        'type': 'refresh'
    }
    refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm=ALGORITHM)

    # Store refresh token
    REFRESH_TOKENS[refresh_token_id] = {
        'user_id': user_id,
        'created_at': datetime.now(),
        'active': True
    }

    return access_token, refresh_token

@app.post('/login')
def login(request: Request):
    import json
    data = json.loads(request.body)

    # Validate credentials
    if data.get('email') == 'alice@example.com' and data.get('password') == 'secret':
        access_token, refresh_token = create_tokens('1', 'alice@example.com', 'admin')

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600
        }

    return Response(401, json.dumps({"error": "Invalid credentials"}))

@app.post('/refresh')
def refresh_access_token(request: Request):
    import json
    data = json.loads(request.body)
    refresh_token = data.get('refresh_token')

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # Validate refresh token
        token_id = payload.get('token_id')
        if token_id not in REFRESH_TOKENS or not REFRESH_TOKENS[token_id]['active']:
            return Response(401, json.dumps({"error": "Invalid refresh token"}))

        # Create new access token
        user_id = payload.get('user_id')
        # In production, fetch user details from database
        new_access_token = jwt.encode({
            'user_id': user_id,
            'exp': datetime.now() + timedelta(hours=1),
            'type': 'access'
        }, SECRET_KEY, algorithm=ALGORITHM)

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 3600
        }

    except jwt.InvalidTokenError:
        return Response(401, json.dumps({"error": "Invalid refresh token"}))

@app.post('/logout')
def logout(request: Request, current_user):
    """Revoke refresh tokens for user."""
    import json
    data = json.loads(request.body)
    refresh_token = data.get('refresh_token')

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        token_id = payload.get('token_id')

        if token_id in REFRESH_TOKENS:
            REFRESH_TOKENS[token_id]['active'] = False

        return {"message": "Logged out successfully"}

    except jwt.InvalidTokenError:
        return Response(400, json.dumps({"error": "Invalid token"}))
```

## Role-Based Access Control (RBAC)

### Basic RBAC

Implement role-based authorization:

```python
from typing import List

@app.dependency()
def require_role(*allowed_roles: str):
    """Create dependency that requires specific role."""
    def role_checker(current_user):
        user_role = current_user.get('role')
        if user_role not in allowed_roles:
            raise PermissionError(f"Role '{user_role}' not authorized. Required: {', '.join(allowed_roles)}")
        return current_user
    return role_checker

# Use in routes
@app.dependency()
def require_admin(current_user):
    """Require admin role."""
    if current_user.get('role') != 'admin':
        raise PermissionError("Admin access required")
    return current_user

@app.get('/admin/users')
def list_all_users(require_admin, database):
    """Admin-only endpoint."""
    return {"users": database["users"]}

@app.dependency()
def require_moderator(current_user):
    """Require moderator or admin role."""
    role = current_user.get('role')
    if role not in ['admin', 'moderator']:
        raise PermissionError("Moderator or admin access required")
    return current_user

@app.delete('/posts/{post_id}')
def delete_post(path_params, require_moderator, database):
    """Moderators and admins can delete posts."""
    post_id = path_params['post_id']
    # Delete logic
    return {"message": "Post deleted"}, 204

@app.error_handler(403)
def forbidden(request, message, **kwargs):
    return {
        "error": "Forbidden",
        "message": message
    }
```

### Permission-Based Access

Implement fine-grained permissions:

```python
from enum import Enum

class Permission(str, Enum):
    READ_USERS = "users:read"
    WRITE_USERS = "users:write"
    DELETE_USERS = "users:delete"
    READ_POSTS = "posts:read"
    WRITE_POSTS = "posts:write"
    DELETE_POSTS = "posts:delete"

ROLE_PERMISSIONS = {
    "admin": [
        Permission.READ_USERS, Permission.WRITE_USERS, Permission.DELETE_USERS,
        Permission.READ_POSTS, Permission.WRITE_POSTS, Permission.DELETE_POSTS
    ],
    "moderator": [
        Permission.READ_USERS, Permission.READ_POSTS,
        Permission.WRITE_POSTS, Permission.DELETE_POSTS
    ],
    "user": [
        Permission.READ_POSTS, Permission.WRITE_POSTS
    ]
}

@app.dependency()
def current_user_permissions(current_user) -> List[Permission]:
    """Get permissions for current user."""
    role = current_user.get('role', 'user')
    return ROLE_PERMISSIONS.get(role, [])

def require_permission(permission: Permission):
    """Create dependency that checks for specific permission."""
    @app.dependency()
    def permission_checker(current_user_permissions: List[Permission]):
        if permission not in current_user_permissions:
            raise PermissionError(f"Permission '{permission}' required")
        return True
    return permission_checker

@app.get('/users')
def list_users(require_permission(Permission.READ_USERS), database):
    return {"users": database["users"]}

@app.delete('/users/{user_id}')
def delete_user(require_permission(Permission.DELETE_USERS), path_params, database):
    user_id = path_params['user_id']
    # Delete logic
    return {"message": "User deleted"}, 204
```

## Resource-Based Authorization

### Owner-Based Access

Check if user owns the resource using `@app.resource_exists` and authorization dependencies:

```python
@app.resource_exists
def post(path_params, database):
    """Get post by ID, returns None if not found (triggers 404)."""
    post_id = path_params.get('post_id')
    return next((p for p in database["posts"] if p["id"] == post_id), None)

@app.dependency()
def authorized_post(post, current_user):
    """Require user to be post owner or admin."""
    user_role = current_user.get('role')
    user_id = current_user.get('id')

    if user_role == 'admin':
        return post  # Admins can access any post

    if post['author_id'] != user_id:
        raise PermissionError("You can only edit your own posts")

    return post

@app.put('/posts/{post_id}')
def update_post(authorized_post, json_body):
    """Update post (owner or admin only). 404 and 403 handled automatically."""
    authorized_post.update(json_body)
    return authorized_post
```

## Optional Authentication

### Public and Protected Routes

Make authentication optional for some routes:

```python
@app.dependency()
def optional_user(request: Request):
    """Get current user if authenticated, None otherwise."""
    auth_header = request.headers.get('authorization', '')

    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "id": payload.get('user_id'),
            "role": payload.get('role', 'user')
        }
    except jwt.InvalidTokenError:
        return None

@app.get('/posts')
def list_posts(optional_user, database):
    """List posts. Authenticated users see more details."""
    posts = database["posts"]

    if optional_user:
        # Authenticated: show all fields
        return {"posts": posts}
    else:
        # Anonymous: show limited fields
        return {
            "posts": [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "published": p.get("published", False)
                }
                for p in posts
                if p.get("published", False)
            ]
        }
```

## Session-Based Authentication

### Cookie-Based Sessions

Implement session-based auth with cookies:

```python
from uuid import uuid4
from datetime import datetime, timedelta

# Store sessions (use Redis in production)
SESSIONS = {}

@app.post('/login')
def login(request: Request):
    import json
    data = json.loads(request.body)

    # Validate credentials
    if data.get('email') == 'alice@example.com' and data.get('password') == 'secret':
        # Create session
        session_id = str(uuid4())
        SESSIONS[session_id] = {
            'user_id': '1',
            'email': 'alice@example.com',
            'role': 'admin',
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(days=7)
        }

        # Return session cookie
        return (
            {"message": "Logged in successfully"},
            200,
            {
                'Set-Cookie': f'session_id={session_id}; HttpOnly; SameSite=Lax; Max-Age=604800'
            }
        )

    return Response(401, json.dumps({"error": "Invalid credentials"}))

@app.dependency()
def session_id(request: Request) -> str:
    """Extract session ID from cookie."""
    cookies = request.headers.get('cookie', '')

    # Parse cookies (simplified)
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('session_id='):
            return cookie[11:]  # Remove 'session_id=' prefix

    raise ValueError("Not authenticated")

@app.dependency()
def current_user(session_id: str):
    """Get user from session."""
    session = SESSIONS.get(session_id)

    if not session:
        raise ValueError("Invalid session")

    # Check expiration
    if session['expires_at'] < datetime.now():
        del SESSIONS[session_id]
        raise ValueError("Session expired")

    return {
        'id': session['user_id'],
        'email': session['email'],
        'role': session['role']
    }

@app.post('/logout')
def logout(session_id: str):
    """Destroy session."""
    if session_id in SESSIONS:
        del SESSIONS[session_id]

    return (
        {"message": "Logged out successfully"},
        200,
        {
            'Set-Cookie': 'session_id=; HttpOnly; SameSite=Lax; Max-Age=0'
        }
    )
```

## Complete Example

Here's a complete authentication system:

```python
from restmachine import RestApplication, Request, Response
from pydantic import BaseModel, EmailStr
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json

app = RestApplication()

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"

# Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: str
    email: EmailStr
    role: str

# Database
@app.on_startup
def database():
    return {
        "users": [
            {
                "id": "1",
                "email": "alice@example.com",
                "password_hash": "hashed_password",  # Use bcrypt in production
                "role": "admin"
            },
            {
                "id": "2",
                "email": "bob@example.com",
                "password_hash": "hashed_password",
                "role": "user"
            }
        ],
        "posts": [
            {"id": "1", "title": "Post 1", "author_id": "1"},
            {"id": "2", "title": "Post 2", "author_id": "2"}
        ]
    }

# Authentication
@app.validates
def login_request(json_body) -> LoginRequest:
    return LoginRequest.model_validate(json_body)

@app.dependency()
def jwt_token(request: Request) -> str:
    auth_header = request.headers.get('authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValueError("Authentication required")
    return auth_header[7:]

@app.dependency()
def current_user(jwt_token: str, database) -> Dict[str, Any]:
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('user_id')

        user = next((u for u in database["users"] if u["id"] == user_id), None)
        if not user:
            raise ValueError("User not found")

        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"]
        }
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")

@app.dependency()
def require_admin(current_user):
    if current_user.get('role') != 'admin':
        raise PermissionError("Admin access required")
    return current_user

# Routes
@app.post('/login')
def login(login_request: LoginRequest, database):
    # Find user
    user = next(
        (u for u in database["users"] if u["email"] == login_request.email),
        None
    )

    # Verify password (use bcrypt.checkpw in production)
    if not user or user["password_hash"] != "hashed_password":
        return Response(401, json.dumps({"error": "Invalid credentials"}))

    # Create token
    payload = {
        'user_id': user['id'],
        'email': user['email'],
        'role': user['role'],
        'exp': datetime.now() + timedelta(hours=24),
        'iat': datetime.now()
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400
    }

@app.get('/profile')
def get_profile(current_user):
    return {"user": current_user}

@app.get('/admin/users')
def list_users(require_admin, database):
    return {
        "users": [
            {"id": u["id"], "email": u["email"], "role": u["role"]}
            for u in database["users"]
        ]
    }

@app.resource_exists
def post(path_params, database):
    """Get post by ID, returns None if not found (triggers 404)."""
    post_id = path_params['post_id']
    return next((p for p in database["posts"] if p["id"] == post_id), None)

@app.get('/posts/{post_id}')
def get_post(post, current_user):
    """Get post. 404 handled automatically."""
    return post

@app.dependency()
def authorized_post(post, current_user):
    """Check if user can modify post (owner or admin)."""
    if post['author_id'] != current_user['id'] and current_user['role'] != 'admin':
        raise PermissionError("Not authorized to modify this post")
    return post

@app.delete('/posts/{post_id}')
def delete_post(authorized_post, path_params, database):
    """Delete post. 404 and 403 handled automatically."""
    post_id = path_params['post_id']
    database["posts"] = [p for p in database["posts"] if p["id"] != post_id]
    return {"message": "Post deleted"}, 204

# Error handlers
@app.error_handler(401)
def unauthorized(request, message, **kwargs):
    return {"error": "Unauthorized", "message": message}

@app.error_handler(403)
def forbidden(request, message, **kwargs):
    return {"error": "Forbidden", "message": message}

# ASGI
from restmachine import ASGIAdapter
asgi_app = ASGIAdapter(app)
```

## Best Practices

### 1. Never Store Plain Text Passwords

Always hash passwords:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

### 2. Use Environment Variables

Store secrets securely:

```python
import os

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable not set")
```

### 3. Implement Rate Limiting

Prevent brute force attacks:

```python
from collections import defaultdict
from datetime import datetime, timedelta

# Simple rate limiter (use Redis in production)
login_attempts = defaultdict(list)

@app.dependency()
def rate_limit_login(request: Request):
    ip = request.headers.get('x-forwarded-for', 'unknown')

    # Clean old attempts
    cutoff = datetime.now() - timedelta(minutes=15)
    login_attempts[ip] = [t for t in login_attempts[ip] if t > cutoff]

    # Check rate limit
    if len(login_attempts[ip]) >= 5:
        raise ValueError("Too many login attempts. Try again later.")

    login_attempts[ip].append(datetime.now())
    return True

@app.post('/login')
def login(rate_limit_login, validate_login: LoginRequest, database):
    # Login logic
    ...
```

### 4. Set Token Expiration

Use short-lived access tokens:

```python
# Short access token
access_exp = datetime.now() + timedelta(hours=1)

# Long refresh token
refresh_exp = datetime.now() + timedelta(days=30)
```

### 5. Validate Token Claims

Always validate all token claims:

```python
@app.dependency()
def current_user(jwt_token: str):
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])

        # Validate token type
        if payload.get('type') != 'access':
            raise ValueError("Invalid token type")

        # Validate expiration
        exp = payload.get('exp')
        if not exp or datetime.fromtimestamp(exp) < datetime.now():
            raise ValueError("Token expired")

        # Validate issuer (if using)
        if payload.get('iss') != 'your-app':
            raise ValueError("Invalid issuer")

        return payload

    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")
```

## Next Steps

- [Error Handling →](error-handling.md) - Handle authentication errors
- [Testing →](testing.md) - Test authentication flows
- [Deployment →](deployment/uvicorn.md) - Deploy with HTTPS
- [Advanced Features →](../advanced/tls.md) - TLS client certificate authentication

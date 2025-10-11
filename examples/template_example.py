"""
Example demonstrating the new Jinja2 template rendering capabilities.

This example shows how to use the render() helper function to render
HTML templates with Rails-like view capabilities.

Note: This script can be run from any directory.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from restmachine import RestApplication, HTTPMethod, Request, render

# Get the directory where this script is located for template paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# Create the application
app = RestApplication()


# Example 1: Using inline templates
@app.get("/hello/{name}")
def hello_inline(name: str):
    """Render a greeting using an inline template."""
    return render(
        inline="<h1>Hello, {{ name }}!</h1><p>Welcome to our API.</p>",
        name=name
    )


# Example 2: Using file-based templates
@app.get("/user/{user_id}")
def get_user(user_id: str):
    """Get user details - no custom renderer needed!"""
    # This would normally fetch from a database
    user = {
        "id": user_id,
        "name": "John Doe",
        "email": "john@example.com",
        "created_at": "2024-01-01"
    }
    return user  # Will use default HTMLRenderer


# Example 3: Custom HTML renderer using templates
@app.get("/user/{user_id}/profile")
def get_user_profile(user_id: str):
    """Get user profile with custom template."""
    user = {
        "id": user_id,
        "name": "Jane Smith",
        "email": "jane@example.com",
        "created_at": "2024-02-15"
    }
    return user


@app.provides("text/html")
def user_profile_html(get_user_profile):
    """Render user profile using a Jinja2 template."""
    user = get_user_profile
    return render(
        template="user_detail.html",
        package=os.path.join(SCRIPT_DIR, "views"),
        user=user
    )


# Example 4: Blog post with author
@app.get("/posts/{post_id}")
def get_post(post_id: str):
    """Get blog post with author."""
    # Simulated data
    post = {
        "id": post_id,
        "title": "Getting Started with RestMachine",
        "content": "<p>RestMachine is a powerful REST framework...</p>",
        "created_at": "2024-03-10",
        "tags": ["python", "rest", "api"]
    }
    author = {
        "id": "1",
        "name": "Alice Developer"
    }
    return {"post": post, "author": author}


@app.provides("text/html")
def post_html(get_post):
    """Render blog post using template."""
    data = get_post
    return render(
        template="post_detail.html",
        package=os.path.join(SCRIPT_DIR, "views"),
        post=data["post"],
        author=data["author"]
    )


# Example 5: List rendering
@app.get("/users")
def list_users():
    """Get list of users."""
    users = [
        {"id": "1", "name": "John Doe", "email": "john@example.com"},
        {"id": "2", "name": "Jane Smith", "email": "jane@example.com"},
        {"id": "3", "name": "Bob Wilson", "email": "bob@example.com"}
    ]
    return {"users": users}


@app.provides("text/html")
def users_list_html(list_users):
    """Render users list using template."""
    data = list_users
    return render(
        template="list.html",
        package=os.path.join(SCRIPT_DIR, "views"),
        title="Users List",
        header="All Users",
        items=data["users"]
    )


# Example 6: Unsafe rendering (with HTML content)
@app.get("/content/{content_id}")
def get_content(content_id: str):
    """Get content with raw HTML."""
    return {
        "id": content_id,
        "title": "Rich Content Example",
        "html_content": "<div><strong>Bold text</strong> and <em>italic text</em></div>"
    }


@app.provides("text/html")
def content_html(get_content):
    """Render content with unsafe HTML (autoescape disabled)."""
    data = get_content
    # Using unsafe=True to allow raw HTML in the content
    return render(
        inline="""
        <h1>{{ title }}</h1>
        <div class="content">
            {{ html_content|safe }}
        </div>
        """,
        title=data["title"],
        html_content=data["html_content"]
    )


# Example 7: Custom package location
# If you have templates in a different package, you can specify it:
@app.get("/admin/dashboard")
def admin_dashboard():
    """Admin dashboard."""
    stats = {
        "users": 150,
        "posts": 342,
        "comments": 1205
    }
    return stats


@app.provides("text/html")
def admin_dashboard_html(admin_dashboard):
    """Render admin dashboard."""
    stats = admin_dashboard
    # This would look for templates in the 'admin_views' package
    # For this example, we'll use inline rendering
    return render(
        inline="""
        <h1>Admin Dashboard</h1>
        <div class="stats">
            <div class="stat">
                <span class="label">Users:</span>
                <span class="value">{{ users }}</span>
            </div>
            <div class="stat">
                <span class="label">Posts:</span>
                <span class="value">{{ posts }}</span>
            </div>
            <div class="stat">
                <span class="label">Comments:</span>
                <span class="value">{{ comments }}</span>
            </div>
        </div>
        """,
        users=stats["users"],
        posts=stats["posts"],
        comments=stats["comments"]
    )


if __name__ == "__main__":
    # Test the endpoints
    print("=" * 60)
    print("Jinja2 Template Rendering Examples")
    print("=" * 60)

    # Example 1: Inline template
    print("\n1. Inline Template Example:")
    print("-" * 60)
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/hello/World",
            headers={"Accept": "text/html"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print(f"Body:\n{response.body[:200]}...")

    # Example 2: File-based template
    print("\n2. File-based Template Example (User Profile):")
    print("-" * 60)
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/user/123/profile",
            headers={"Accept": "text/html"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print("Template rendered successfully!")

    # Example 3: Blog post
    print("\n3. Blog Post Template:")
    print("-" * 60)
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/posts/456",
            headers={"Accept": "text/html"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print("Template rendered successfully!")

    # Example 4: List rendering
    print("\n4. List Template:")
    print("-" * 60)
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={"Accept": "text/html"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print("Template rendered successfully!")

    # Example 5: JSON fallback
    print("\n5. JSON Response (same endpoint, different Accept header):")
    print("-" * 60)
    response = app.execute(
        Request(
            method=HTTPMethod.GET,
            path="/users",
            headers={"Accept": "application/json"}
        )
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print(f"Body:\n{response.body[:200]}...")

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
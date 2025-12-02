# Tutorial: Building a Blog API

Welcome to the RestMachine tutorial! In this hands-on guide, you'll build a complete blog application from scratch, learning all the core concepts along the way.

## What You'll Build

By the end of this tutorial, you'll have:

- A full-featured blog API with posts, authors, and comments
- Database models with relationships
- Complete CRUD operations with proper HTTP semantics
- Request validation and error handling
- Seed data for development
- A simple web interface
- Production-ready deployment

## Prerequisites

- Python 3.9 or higher
- Basic Python knowledge
- Familiarity with REST APIs (helpful but not required)

## Installation

First, install RestMachine:

=== "pip"
    ```bash
    pip install restmachine
    ```

=== "pip with validation"
    ```bash
    pip install restmachine[validation]
    ```

Verify the installation:

```bash
restmachine --version
```

## Create Your Project

Use the CLI to create a new project:

```bash
restmachine new blog-api
cd blog-api
```

This creates a complete project structure:

```
blog-api/
├── app.py              # Main application entry point
├── main.py             # Development server runner
├── models/             # Database models
│   └── __init__.py
├── schemas/            # Request/response schemas
│   └── __init__.py
├── routes/             # API routes
│   └── __init__.py
├── db/
│   └── fixtures/       # Seed data
├── tests/
│   └── integration/    # API tests
├── config/             # Environment configs
│   └── local/
│       └── development.yaml
├── .restmachine.toml   # Project configuration
└── pyproject.toml      # Python package config
```

## Explore the Generated Code

Let's look at what was created:

**app.py** - Your application:

```python
from restmachine import RestMachine

app = RestMachine()

# Routes will be mounted here
```

**main.py** - Development server:

```python
import uvicorn
from app import app
from restmachine import ASGIAdapter

asgi_app = ASGIAdapter(app)

if __name__ == "__main__":
    uvicorn.run(asgi_app, host="127.0.0.1", port=3000, reload=True)
```

## Run Your Application

Start the development server:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn app:asgi_app --reload --port 3000
```

Visit [http://localhost:3000](http://localhost:3000) - you should see a basic response (we'll add a proper home page later).

## Project Configuration

The `.restmachine.toml` file configures your project:

```toml
[project]
name = "blog-api"
backend = "sqlite"  # Default ORM backend

[database]
# SQLite configuration (automatically set up)
path = "blog.db"
```

## Next Steps

Great! You now have a working RestMachine project. In the next section, we'll create our first model and API endpoints.

[Next: Creating Models →](02-models.md)

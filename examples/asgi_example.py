"""
Example: Using RestMachine with ASGI servers directly.

This example shows how to create an ASGI application that can be used
with any ASGI-compatible server (Uvicorn, Hypercorn, Daphne, etc.).

Run with:
    uvicorn examples.asgi_example:app --reload
    # or
    hypercorn examples.asgi_example:app --reload
"""

from restmachine import RestApplication, ASGIAdapter
from pydantic import BaseModel


class Item(BaseModel):
    """Item model for demonstration."""
    name: str
    price: float
    description: str = ""


# Create the RestMachine application
rest_app = RestApplication()


@rest_app.get("/")
def home():
    """Home endpoint."""
    return {
        "message": "Welcome to RestMachine ASGI Example",
        "docs": "/docs"
    }


@rest_app.get("/items/{item_id}")
def get_item(path_params):
    """Get item by ID."""
    item_id = path_params["item_id"]
    return {
        "item_id": item_id,
        "name": f"Item {item_id}",
        "price": 29.99
    }


@rest_app.validates
def validate_item(json_body) -> Item:
    """Validate item creation request."""
    return Item.model_validate(json_body)


@rest_app.get("/items")
def list_items() -> list[Item]:
    """List item."""
    return [{
        "name": "Fake item",
        "price": 3.14,
        "description": "Pie is delicious",
    }]

@rest_app.post("/items")
def create_item(validate_item):
    """Create a new item."""
    return {
        "message": "Item created",
        "item": {
            "name": validate_item.name,
            "price": validate_item.price,
            "description": validate_item.description
        }
    }


# Create the ASGI application - this is what the ASGI server will use
app = ASGIAdapter(rest_app)

# You can also use the convenience function:
# from restmachine import create_asgi_app
# app = create_asgi_app(rest_app)

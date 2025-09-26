"""
Example demonstrating conditional request support with ETags and Last-Modified headers.

This example shows how to use:
- ETag generation for resources
- Last-Modified dates for resources
- If-Match, If-None-Match, If-Modified-Since, If-Unmodified-Since headers
- HTTP 304 (Not Modified) and 412 (Precondition Failed) responses
"""

from datetime import datetime, timezone
from restmachine import RestApplication, HTTPMethod, Request
import json

app = RestApplication()

# Simulate a simple document store with versioning
documents = {
    "doc1": {
        "id": "doc1",
        "title": "Sample Document",
        "content": "This is the original content.",
        "version": 1,
        "modified": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    }
}


@app.generate_etag
def document_etag(request):
    """Generate ETag based on document version."""
    doc_id = request.path_params.get("doc_id")
    if doc_id and doc_id in documents:
        doc = documents[doc_id]
        return f"doc-{doc_id}-v{doc['version']}"
    return None


@app.last_modified
def document_last_modified(request):
    """Get Last-Modified date for document."""
    doc_id = request.path_params.get("doc_id")
    if doc_id and doc_id in documents:
        return documents[doc_id]["modified"]
    return None


@app.resource_exists
def document(request):
    """Check if document exists."""
    doc_id = request.path_params.get("doc_id")
    if doc_id and doc_id in documents:
        return documents[doc_id]
    return None


@app.resource_from_request
def new_document(request):
    """Create new document from request data for POST operations."""
    # Parse request body
    try:
        doc_data = json.loads(request.body)
    except json.JSONDecodeError:
        return None

    # Generate a new document ID (in a real app, this might be a UUID or auto-increment)
    import uuid
    doc_id = str(uuid.uuid4())[:8]  # Short ID for demo

    # Create new document
    return {
        "id": doc_id,
        "title": doc_data.get("title", "Untitled"),
        "content": doc_data.get("content", ""),
        "version": 1,
        "modified": datetime.now(timezone.utc)
    }


@app.get("/documents")
def list_documents(request):
    """List all documents."""
    return [{"id": doc["id"], "title": doc["title"], "version": doc["version"]}
            for doc in documents.values()]


@app.post("/documents")
def create_document(new_document, request):
    """Create a new document. Uses resource_from_request to generate the document."""
    # new_document contains the created document data
    doc = new_document

    # Save the document to the store (persistence logic belongs in the handler)
    documents[doc["id"]] = doc

    # Generate ETag for the response
    from restmachine import Response
    etag = f'"doc-{doc["id"]}-v{doc["version"]}"'

    return Response(
        200,
        {
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "version": doc["version"]
        },
        headers={"ETag": etag, "Last-Modified": doc["modified"].strftime("%a, %d %b %Y %H:%M:%S GMT")}
    )


@app.get("/documents/{doc_id}")
def get_document(document, document_etag, document_last_modified, request):
    """Get a document. Supports conditional requests with ETag and Last-Modified."""
    # document contains the document data, no need for manual checks
    doc = document
    return {
        "id": doc["id"],
        "title": doc["title"],
        "content": doc["content"],
        "version": doc["version"]
    }


@app.put("/documents/{doc_id}")
def update_document(document, document_etag, document_last_modified, request):
    """Update a document. Requires If-Match or If-Unmodified-Since for safe updates."""
    # Parse request body
    try:
        update_data = json.loads(request.body)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}, 400

    # Update document and increment version
    # document contains the document data, no need for manual checks
    doc = document
    if "title" in update_data:
        doc["title"] = update_data["title"]
    if "content" in update_data:
        doc["content"] = update_data["content"]

    doc["version"] += 1
    doc["modified"] = datetime.now(timezone.utc)

    return {
        "id": doc["id"],
        "title": doc["title"],
        "content": doc["content"],
        "version": doc["version"]
    }


def demo():
    """Demonstrate conditional request scenarios."""

    print("=== Conditional Requests Demo ===\n")

    # 1. Initial GET request - should return 200 with ETag and Last-Modified
    print("1. Initial GET request")
    request = Request(
        method=HTTPMethod.GET,
        path="/documents/doc1",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code}")
    print(f"   ETag: {response.headers.get('ETag')}")
    print(f"   Last-Modified: {response.headers.get('Last-Modified')}")
    etag1 = response.headers.get('ETag')
    last_modified1 = response.headers.get('Last-Modified')
    print()

    # 2. GET with If-None-Match (same ETag) - should return 304
    print("2. GET with If-None-Match (same ETag) - expect 304")
    request = Request(
        method=HTTPMethod.GET,
        path="/documents/doc1",
        headers={
            "If-None-Match": etag1,
            "Accept": "application/json"
        }
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 304)")
    print()

    # 3. GET with If-Modified-Since (same date) - should return 304
    print("3. GET with If-Modified-Since (same date) - expect 304")
    request = Request(
        method=HTTPMethod.GET,
        path="/documents/doc1",
        headers={
            "If-Modified-Since": last_modified1,
            "Accept": "application/json"
        }
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 304)")
    print()

    # 4. PUT with If-Match (correct ETag) - should succeed
    print("4. PUT with If-Match (correct ETag) - expect 200")
    request = Request(
        method=HTTPMethod.PUT,
        path="/documents/doc1",
        headers={
            "If-Match": etag1,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body='{"title": "Updated Document", "content": "This content has been updated!"}'
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 200)")
    data = json.loads(response.body)
    print(f"   New version: {data['version']}")
    etag2 = response.headers.get('ETag')
    print(f"   New ETag: {etag2}")
    print()

    # 5. PUT with If-Match (old ETag) - should return 412
    print("5. PUT with If-Match (old ETag) - expect 412")
    request = Request(
        method=HTTPMethod.PUT,
        path="/documents/doc1",
        headers={
            "If-Match": etag1,  # Old ETag
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body='{"content": "This should fail!"}'
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 412 - Precondition Failed)")
    print()

    # 6. GET with old If-None-Match - should return 200 (ETag changed)
    print("6. GET with old If-None-Match - expect 200 (ETag changed)")
    request = Request(
        method=HTTPMethod.GET,
        path="/documents/doc1",
        headers={
            "If-None-Match": etag1,  # Old ETag
            "Accept": "application/json"
        }
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 200 - ETag changed)")
    data = json.loads(response.body)
    print(f"   Title: {data['title']}")
    print()

    # 7. GET list of documents
    print("7. GET list of all documents - expect 200")
    request = Request(
        method=HTTPMethod.GET,
        path="/documents",
        headers={"Accept": "application/json"}
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 200)")
    if response.status_code == 200:
        data = json.loads(response.body)
        print(f"   Found {len(data)} documents")
        for doc in data:
            print(f"     - {doc['id']}: {doc['title']} (v{doc['version']})")
    print()

    # 8. POST to create new document - should succeed
    print("8. POST to create new document - expect 200")
    request = Request(
        method=HTTPMethod.POST,
        path="/documents",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body='{"title": "New Document", "content": "This is a new document."}'
    )
    response = app.execute(request)
    print(f"   Status: {response.status_code} (should be 200)")
    new_doc_id = None
    if response.status_code == 200:
        # Handle both dict and string response bodies
        if isinstance(response.body, dict):
            data = response.body
        else:
            data = json.loads(response.body)
        print(f"   Created document ID: {data['id']}")
        print(f"   Title: {data['title']}")
        print(f"   Version: {data['version']}")
        print(f"   ETag: {response.headers.get('ETag')}")
        new_doc_id = data['id']
    print()

    # 9. GET the new document to verify it was created
    if new_doc_id:
        print("9. GET the newly created document - expect 200")
        request = Request(
            method=HTTPMethod.GET,
            path=f"/documents/{new_doc_id}",
            headers={"Accept": "application/json"}
        )
        response = app.execute(request)
        print(f"   Status: {response.status_code} (should be 200)")
        if response.status_code == 200:
            data = json.loads(response.body)
            print(f"   Retrieved: {data['title']}")
            print(f"   ETag: {response.headers.get('ETag')}")
        print()


if __name__ == "__main__":
    demo()

"""Check the actual HTML rendering for form issues."""
import os
import tempfile
os.environ.setdefault("SAMJON_PORTAL_USERNAME", "portal-admin")
os.environ.setdefault("SAMJON_PORTAL_PASSWORD", "portal-secret")
os.environ.setdefault("SAMJON_PORTAL_ALLOWED_ORIGINS", "http://localhost:8100,http://127.0.0.1:8100")

from samjon_memory.config import config
from samjon_memory.portal.router import _parse_origin
from fastapi.testclient import TestClient
from samjon_memory.core.main import app
from samjon_memory.core.service import CoreService

# Create temp db
with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
    db_path = f.name

svc = CoreService(database_path=db_path)
app.state.service = svc
client = TestClient(app)
client.auth = ("portal-admin", "portal-secret")

# Create a collection with 3 memories
coll = svc.create_collection({"subject": "diag", "title": "Diag", "source": "test", "expected_item_count": 3})
m1 = svc.create_memory({"subject": "A", "raw_content": "a", "source": "test"})
m2 = svc.create_memory({"subject": "B", "raw_content": "b", "source": "test"})
m3 = svc.create_memory({"subject": "C", "raw_content": "c", "source": "test"})
svc.add_memory_to_collection(coll["collection_id"], m1["memory_id"], 1)
svc.add_memory_to_collection(coll["collection_id"], m2["memory_id"], 2)
svc.add_memory_to_collection(coll["collection_id"], m3["memory_id"], 3)

# Get the collection detail page
resp = client.get(f"/portal/collections/{coll['collection_id']}")
html = resp.text

# Print the relevant part of the HTML
print("=== HTML Form Rendering (mem_rows section) ===")
print()

# Find the mem_rows section
import re
mem_rows_match = re.search(r'<tr><td>1</td>.*?</tr>', html, re.DOTALL)
if mem_rows_match:
    print(mem_rows_match.group(0))
print()

# Check the form actions and buttons for each memory
print("=== Form Actions for Each Memory ===")
for i, m in enumerate([m1, m2, m3]):
    mid = m["memory_id"]
    # Find the row for this memory
    row_pattern = f'<td>{i+1}</td><td>{m["subject"]}</td>'
    row_start = html.find(row_pattern)
    if row_start >= 0:
        row_end = html.find('</tr>', row_start)
        row = html[row_start:row_end]
        print(f"Row for {m['subject']} (seq {i+1}):")
        # Find form actions
        forms = re.findall(r'<form[^>]*method="post"[^>]*action="([^"]*)"[^>]*>', row)
        for form in forms:
            print(f"  Form: {form}")
        # Find buttons
        buttons = re.findall(r'<button[^>]*>([^<]*)</button>', row)
        for btn in buttons:
            print(f"  Button: {btn}")
        print()

# Cleanup
os.unlink(db_path)
"""Portal page renderers using HTML templates."""

from typing import Any, Optional
from samjon_memory.shared.helpers import utc_now


def escape_html(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _nav() -> str:
    return """<nav>
<a href="/portal/">Home</a> |
<a href="/portal/memories">Memories</a> |
<a href="/portal/collections">Collections</a> |
<a href="/portal/audit">Audit Log</a> |
<a href="/health">Health</a> |
<a href="/api/v1/capabilities">Capabilities</a>
</nav>"""


def _csrf_field(token: str) -> str:
    return f'<input type="hidden" name="csrf_token" value="{escape_html(token)}">'


def render_portal_index() -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Samjon Memory Core Portal</title><meta charset="utf-8">
<style>body{{font-family:sans-serif;margin:2em;}}table{{border-collapse:collapse;width:100%;}}th,td{{border:1px solid #ccc;padding:8px;text-align:left;}}th{{background:#f5f5f5;}}</style>
</head><body>
<h1>Samjon Memory Core Portal</h1>
<p>Service: Samjon Memory Core V1 | Version: 1.0.0</p>
{_nav()}
<h2>Quick Actions</h2>
<ul>
<li><a href="/portal/memories?q=">View All Memories</a></li>
<li><a href="/portal/collections?q=">View All Collections</a></li>
<li><a href="/portal/memories/create">Create Memory</a></li>
<li><a href="/portal/collections/create">Create Collection</a></li>
<li><a href="/portal/audit">Audit Log</a></li>
</ul>
</body></html>"""


def render_memory_list(memories: list, page: int = 1, q: str = "", csrf_token: str = "") -> str:
    rows = ""
    for m in memories:
        mid = escape_html(m.get("memory_id", ""))
        rows += f"<tr><td>{mid}</td><td>{escape_html(m.get('subject',''))}</td><td>{escape_html(m.get('status',''))}</td><td>{escape_html(m.get('memory_type',''))}</td><td><a href=\"/portal/memories/{mid}\">View</a> | <a href=\"/portal/memories/{mid}/edit\">Edit</a></td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Memories</title><meta charset="utf-8"></head><body>
<h1>Memories</h1>
{_nav()}
<p>Search: {escape_html(q)} | Page: {page}</p>
<table><tr><th>ID</th><th>Subject</th><th>Status</th><th>Type</th><th>Actions</th></tr>{rows}</table>
<p><a href="/portal/memories/create">Create Memory</a></p>
</body></html>"""


def render_memory_create() -> str:
    return """<!DOCTYPE html><html><head><title>Create Memory</title><meta charset="utf-8"></head><body>
<h1>Create Memory</h1>
<form method="post" action="/portal/memories/create">
<p><label>Subject: <input type="text" name="subject" required></label></p>
<p><label>Raw Content: <textarea name="raw_content" required></textarea></label></p>
<p><label>Source: <input type="text" name="source" value="portal"></label></p>
<p><button type="submit">Create</button></p>
</form>
<a href="/portal/">Back</a>
</body></html>"""


def render_memory_edit(memory: dict) -> str:
    return f"""<!DOCTYPE html><html><head><title>Edit Memory</title><meta charset="utf-8"></head><body>
<h1>Edit Memory</h1>
<p>ID: {escape_html(memory.get('memory_id',''))} | Current Version: {escape_html(str(memory.get('version','')))}</p>
<form method="post" action="/portal/memories/{escape_html(memory.get('memory_id',''))}/edit">
<p><label>Subject: <input type="text" name="subject" value="{escape_html(memory.get('subject',''))}"></label></p>
<p><label>Raw Content: <textarea name="raw_content">{escape_html(memory.get('raw_content',''))}</textarea></label></p>
<p><label>Expected Version: <input type="number" name="expected_version" value="{escape_html(str(memory.get('version','')))}" required></label></p>
<p><button type="submit">Update</button></p>
</form>
<a href="/portal/memories/{escape_html(memory.get('memory_id',''))}">Cancel</a>
</body></html>"""


def render_memory_detail(memory: dict) -> str:
    mid = escape_html(memory.get("memory_id", ""))
    return f"""<!DOCTYPE html><html><head><title>Memory {mid}</title><meta charset="utf-8"></head><body>
<h1>Memory Detail</h1>
<p>ID: {mid}</p>
<p>Subject: {escape_html(memory.get('subject',''))}</p>
<p>Type: {escape_html(memory.get('memory_type',''))}</p>
<p>Status: {escape_html(memory.get('status',''))}</p>
<p>Version: {escape_html(str(memory.get('version','')))}</p>
<p>Raw Content: {escape_html(memory.get('raw_content',''))}</p>
<p><a href="/portal/memories/{mid}/edit">Edit</a> |
<a href="/portal/memories/{mid}/supersede">Supersede</a> |
<a href="/portal/memories/{mid}/forget">Forget</a> |
<a href="/portal/">Back</a></p>
</body></html>"""


def render_collection_list(collections: list, page: int = 1, q: str = "", csrf_token: str = "") -> str:
    rows = ""
    for c in collections:
        cid = escape_html(c.get("collection_id", ""))
        rows += f"<tr><td>{cid}</td><td>{escape_html(c.get('subject',''))}</td><td>{escape_html(c.get('status',''))}</td><td>{escape_html(c.get('title',''))}</td><td><a href=\"/portal/collections/{cid}\">View</a></td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Collections</title><meta charset="utf-8"></head><body>
<h1>Collections</h1>
{_nav()}
<p>Search: {escape_html(q)} | Page: {page}</p>
<table><tr><th>ID</th><th>Subject</th><th>Status</th><th>Title</th><th>Actions</th></tr>{rows}</table>
<p><a href="/portal/collections/create">Create Collection</a></p>
</body></html>"""


def render_collection_create() -> str:
    return """<!DOCTYPE html><html><head><title>Create Collection</title><meta charset="utf-8"></head><body>
<h1>Create Collection (Draft)</h1>
<form method="post" action="/portal/collections/create">
<p><label>Subject: <input type="text" name="subject" required></label></p>
<p><label>Title: <input type="text" name="title" required></label></p>
<p><label>Source: <input type="text" name="source" value="portal"></label></p>
<p><label>Expected Item Count: <input type="number" name="expected_item_count"></label></p>
<p><button type="submit">Create Draft</button></p>
</form>
<a href="/portal/">Back</a>
</body></html>"""


def render_collection_edit(collection: dict) -> str:
    return f"""<!DOCTYPE html><html><head><title>Edit Collection</title><meta charset="utf-8"></head><body>
<h1>Edit Collection</h1>
<p>ID: {escape_html(collection.get('collection_id',''))} | Current Version: {escape_html(str(collection.get('version','')))}</p>
<form method="post" action="/portal/collections/{escape_html(collection.get('collection_id',''))}/edit">
<p><label>Subject: <input type="text" name="subject" value="{escape_html(collection.get('subject',''))}"></label></p>
<p><label>Title: <input type="text" name="title" value="{escape_html(collection.get('title',''))}"></label></p>
<p><label>Expected Version: <input type="number" name="expected_version" value="{escape_html(str(collection.get('version','')))}" required></label></p>
<p><button type="submit">Update</button></p>
</form>
<a href="/portal/collections/{escape_html(collection.get('collection_id',''))}">Cancel</a>
</body></html>"""


def render_collection_detail(collection: dict, memories: list, validation: dict, csrf_token: str = "") -> str:
    cid = escape_html(collection.get("collection_id", ""))
    mem_rows = ""
    for m in memories:
        mem_rows += f"<tr><td>{escape_html(m.get('memory_id',''))}</td><td>{escape_html(m.get('subject',''))}</td><td>{escape_html(str(m.get('sequence_number','')))}</td><td>{escape_html(m.get('status',''))}</td></tr>"
    issues = ", ".join(validation.get("issues", [])) if validation.get("issues") else "none"
    return f"""<!DOCTYPE html><html><head><title>Collection {cid}</title><meta charset="utf-8"></head><body>
<h1>Collection: {escape_html(collection.get('title',''))}</h1>
<p>ID: {cid} | Status: {escape_html(collection.get('status',''))} | Version: {escape_html(str(collection.get('version','')))}</p>
<h2>Validation</h2>
<p>Valid: {validation.get('valid')} | Issues: {escape_html(issues)} | Memories: {validation.get('memory_count',0)}</p>
<h2>Memories</h2>
<table><tr><th>ID</th><th>Subject</th><th>Seq</th><th>Status</th></tr>{mem_rows}</table>
<h2>Actions</h2>
<form method="post" action="/portal/collections/{cid}/reorder"><p>Reorder (comma-separated IDs): <input type="text" name="ordered_memory_ids" required> <button type="submit">Reorder</button></p></form>
<form method="post" action="/portal/collections/{cid}/validate"><button type="submit">Validate</button></form>
<form method="post" action="/portal/collections/{cid}/activate"><button type="submit">Activate</button></form>
<form method="post" action="/portal/collections/{cid}/edit"><button type="submit">Edit Metadata</button></form>
<a href="/portal/">Back</a>
</body></html>"""


def render_audit_log(audits: list, page: int = 1, csrf_token: str = "") -> str:
    rows = ""
    for a in audits:
        rows += f"<tr><td>{escape_html(a.get('audit_id',''))}</td><td>{escape_html(a.get('action',''))}</td><td>{escape_html(a.get('entity_id',''))}</td><td>{escape_html(str(a.get('created_at','')))}</td><td>{escape_html(a.get('actor',''))}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Audit Log</title><meta charset="utf-8"></head><body>
<h1>Audit Log</h1>
{_nav()}
<table><tr><th>ID</th><th>Action</th><th>Entity ID</th><th>Created</th><th>Actor</th></tr>{rows}</table>
</body></html>"""


def render_message(title: str, detail: str, level: str = "info") -> str:
    color = {"success": "green", "error": "red", "warning": "orange", "info": "blue"}.get(level, "black")
    return f"""<!DOCTYPE html><html><head><title>{escape_html(title)}</title><meta charset="utf-8"></head><body>
<h1 style="color:{color}">{escape_html(title)}</h1>
<p>{escape_html(detail)}</p>
<a href="/portal/">Back</a>
</body></html>"""
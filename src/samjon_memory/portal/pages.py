"""Portal page renderers using HTML templates."""

from typing import Any, Optional
from samjon_memory.shared.helpers import utc_now


def escape_html(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_portal_index() -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Samjon Memory Core Portal</title><meta charset="utf-8">
<style>body{{font-family:sans-serif;margin:2em;}}table{{border-collapse:collapse;width:100%;}}th,td{{border:1px solid #ccc;padding:8px;text-align:left;}}th{{background:#f5f5f5;}}</style>
</head><body>
<h1>Samjon Memory Core Portal</h1>
<p>Service: Samjon Memory Core V1 | Version: 1.0.0</p>
<nav>
<a href="/portal/memories">Memories</a> |
<a href="/portal/collections">Collections</a> |
<a href="/portal/audit">Audit Log</a> |
<a href="/health">Health</a> |
<a href="/api/v1/capabilities">Capabilities</a>
</nav>
<h2>Quick Actions</h2>
<ul>
<li><a href="/portal/memories?q=">View All Memories</a></li>
<li><a href="/portal/collections?q=">View All Collections</a></li>
</ul>
</body></html>"""


def render_memory_list(memories: list, page: int = 1, q: str = "") -> str:
    rows = ""
    for m in memories:
        rows += f"<tr><td>{escape_html(m.get('memory_id',''))}</td><td>{escape_html(m.get('subject',''))}</td><td>{escape_html(m.get('status',''))}</td><td>{escape_html(m.get('memory_type',''))}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Memories</title><meta charset="utf-8"></head><body>
<h1>Memories</h1>
<p>Search: {escape_html(q)} | Page: {page}</p>
<table><tr><th>ID</th><th>Subject</th><th>Status</th><th>Type</th></tr>{rows}</table>
</body></html>"""


def render_collection_list(collections: list, page: int = 1, q: str = "") -> str:
    rows = ""
    for c in collections:
        rows += f"<tr><td>{escape_html(c.get('collection_id',''))}</td><td>{escape_html(c.get('subject',''))}</td><td>{escape_html(c.get('status',''))}</td><td>{escape_html(c.get('title',''))}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Collections</title><meta charset="utf-8"></head><body>
<h1>Collections</h1>
<p>Search: {escape_html(q)} | Page: {page}</p>
<table><tr><th>ID</th><th>Subject</th><th>Status</th><th>Title</th></tr>{rows}</table>
</body></html>"""


def render_memory_detail(memory: dict) -> str:
    return f"""<!DOCTYPE html><html><head><title>Memory {escape_html(memory.get('memory_id',''))}</title><meta charset="utf-8"></head><body>
<h1>Memory Detail</h1>
<p>ID: {escape_html(memory.get('memory_id',''))}</p>
<p>Subject: {escape_html(memory.get('subject',''))}</p>
<p>Type: {escape_html(memory.get('memory_type',''))}</p>
<p>Status: {escape_html(memory.get('status',''))}</p>
<p>Version: {escape_html(str(memory.get('version','')))}</p>
<p>Raw Content: {escape_html(memory.get('raw_content',''))}</p>
<a href="/portal/">Back</a>
</body></html>"""


def render_collection_detail(collection: dict, memories: list) -> str:
    mem_rows = ""
    for m in memories:
        mem_rows += f"<tr><td>{escape_html(m.get('memory_id',''))}</td><td>{escape_html(m.get('subject',''))}</td><td>{escape_html(m.get('sequence_number',''))}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Collection {escape_html(collection.get('collection_id',''))}</title><meta charset="utf-8"></head><body>
<h1>Collection: {escape_html(collection.get('title',''))}</h1>
<p>Status: {escape_html(collection.get('status',''))} | Version: {escape_html(str(collection.get('version','')))}</p>
<h2>Memories</h2>
<table><tr><th>ID</th><th>Subject</th><th>Seq</th></tr>{mem_rows}</table>
<a href="/portal/">Back</a>
</body></html>"""


def render_audit_log(audits: list, page: int = 1) -> str:
    rows = ""
    for a in audits:
        rows += f"<tr><td>{escape_html(a.get('audit_id',''))}</td><td>{escape_html(a.get('action',''))}</td><td>{escape_html(a.get('entity_id',''))}</td><td>{escape_html(a.get('created_at',''))}</td></tr>"
    return f"""<!DOCTYPE html><html><head><title>Audit Log</title><meta charset="utf-8"></head><body>
<h1>Audit Log</h1>
<table><tr><th>ID</th><th>Action</th><th>Entity ID</th><th>Created</th></tr>{rows}</table>
</body></html>"""
"""Server-rendered HTML pages for the Core Portal. All dynamic content is XSS-escaped."""
import html as _html
from samjon_memory.constants import DEFAULT_PAGE_SIZE


def _e(text) -> str:
    return _html.escape(str(text) if text is not None else "")


def _navbar(active="") -> str:
    links = [
        ("/portal/memories", "Memories", active == "memories"),
        ("/portal/collections", "Collections", active == "collections"),
        ("/portal/audit", "Audit", active == "audit"),
    ]
    items = "".join(
        f'<a class="nav{" active" if ok else ""}" href="{_e(href)}">{_e(label)}</a>'
        for href, label, ok in links
    )
    return f'<nav class="navbar">{items}<a class="nav" href="/">Home</a></nav>'


def _banner(message: str) -> str:
    if not message:
        return ""
    msg = _e(message)
    cls = "banner error" if msg.startswith("error") else "banner success"
    return f'<div class="{cls}">{msg}</div>'


def _page(body: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
        '<title>Samjon Memory Portal</title>'
        '<link rel="stylesheet" href="/portal/static/portal.css"/>'
        '<script src="/portal/static/portal.js" defer></script>'
        '</head><body>' + body + '</body></html>'
    )


def error_page(message: str) -> str:
    return _page(
        _navbar()
        + "<h1>Error</h1>"
        + f'<div class="banner error">{_e(message)}</div>'
        + '<p><a href="/portal/memories">Back to Memories</a></p>'
    )


def memory_list(memories, subject="", status_filter="", offset=0, message="") -> str:
    rows = "".join(
        f"<tr><td><a href=\"/portal/memories/{_e(m['memory_id'])}\">{_e(m['memory_id'])}</a></td>"
        f"<td>{_e(m['subject'])}</td><td>{_e(m.get('memory_type',''))}</td>"
        f"<td>{_e(m.get('scope',''))}</td><td>{_e(m.get('status',''))}</td>"
        f"<td>{_e(m.get('version',''))}</td></tr>"
        for m in memories
    )
    sel_draft = 'selected' if status_filter == "draft" else ""
    sel_active = 'selected' if status_filter == "active" else ""
    sel_super = 'selected' if status_filter == "superseded" else ""
    sel_forgot = 'selected' if status_filter == "forgotten" else ""
    body = (
        _navbar("memories")
        + "<h1>Memories</h1>"
        + _banner(message)
        + '<a class="btn" href="/portal/memories/create">Create Memory</a>'
        + '<form method="get" class="filter"><input name="subject" value="'
        + _e(subject)
        + '" placeholder="subject"/>'
        + '<select name="status"><option value="">all</option>'
        + f'<option value="draft" {sel_draft}>draft</option>'
        + f'<option value="active" {sel_active}>active</option>'
        + f'<option value="superseded" {sel_super}>superseded</option>'
        + f'<option value="forgotten" {sel_forgot}>forgotten</option></select>'
        + '<button type="submit">Filter</button></form>'
        + "<table><thead><tr><th>ID</th><th>Subject</th><th>Type</th><th>Scope</th><th>Status</th><th>Version</th></tr></thead><tbody>"
        + rows
        + "</tbody></table>"
        + f'<p><a href="/portal/memories?offset={max(0,offset-DEFAULT_PAGE_SIZE)}">Previous</a> | <a href="/portal/memories?offset={offset+DEFAULT_PAGE_SIZE}">Next</a></p>'
        + '<p><a href="/portal/collections">Collections</a> | <a href="/portal/audit">Audit</a></p>'
    )
    return _page(body)


def memory_detail(memory, message="") -> str:
    if not memory:
        return _page('<div class="banner error">Memory not found</div>')
    fields = "".join(
        f"<dt>{_e(k)}</dt><dd><pre>{_e(memory.get(k,''))}</pre></dd>"
        for k in ["memory_id","collection_id","sequence_number","subject","memory_type",
                   "scope","title","section_path","raw_content","structured_value_json",
                   "source","language","status","version","supersedes_memory_id",
                   "content_checksum","created_at","updated_at"]
    )
    body = (
        _navbar("memories")
        + f"<h1>Memory {_e(memory['memory_id'])}</h1>"
        + _banner(message)
        + f'<dl class="detail">{fields}</dl>'
        + f'<p><a class="btn" href="/portal/memories/{_e(memory["memory_id"])}/edit">Edit</a> '
        + f'<a class="btn" href="/portal/memories/create">Create New</a> '
        + f'<a class="btn" href="/portal/memories">List</a></p>'
        + f'<h2>Supersede</h2><form method="post" action="/portal/memories/{_e(memory["memory_id"])}/supersede" onsubmit="return confirm(\'Supersede?\')">'
        + '<input name="replacement_memory_id" required placeholder="replacement memory_id"/>'
        + '<button type="submit">Supersede</button></form>'
        + f'<h2>Forget</h2><form method="post" action="/portal/memories/{_e(memory["memory_id"])}/forget" onsubmit="return confirm(\'Forget? Cannot be undone.\')">'
        + '<button type="submit" class="danger">Forget</button></form>'
        + '<p><a href="/portal/memories">Back to list</a></p>'
    )
    return _page(body)


def memory_create_form(message="", error="") -> str:
    e = error or {}
    body = (
        _navbar("memories")
        + "<h1>Create Memory</h1>"
        + _banner(message)
        + '<form method="post" action="/portal/memories">'
        + '<label>Subject <input name="subject" value="'
        + _e(e.get("subject",""))
        + '" required maxlength="500"/></label>'
        + '<label>Type <input name="memory_type" value="'
        + _e(e.get("memory_type","fact"))
        + '" maxlength="100"/></label>'
        + '<label>Scope <input name="scope" value="'
        + _e(e.get("scope","household"))
        + '" maxlength="100"/></label>'
        + '<label>Title <input name="title" value="'
        + _e(e.get("title",""))
        + '" maxlength="500"/></label>'
        + '<label>Content <textarea name="raw_content" required maxlength="16384">'
        + _e(e.get("raw_content",""))
        + '</textarea></label>'
        + '<label>Source <input name="source" value="'
        + _e(e.get("source","portal"))
        + '" maxlength="200"/></label>'
        + '<label>Language <input name="language" value="'
        + _e(e.get("language","en"))
        + '" maxlength="10"/></label>'
        + "<button type=\"submit\">Create</button></form>"
        + '<p><a href="/portal/memories">Cancel</a></p>'
    )
    return _page(body)


def memory_edit_form(memory, message="", error="") -> str:
    body = (
        _navbar("memories")
        + f"<h1>Edit Memory {_e(memory['memory_id'])}</h1>"
        + _banner(message)
        + f'<form method="post" action="/portal/memories/{_e(memory["memory_id"])}">'
        + f'<input type="hidden" name="expected_version" value="{_e(memory.get("version",""))}"/>'
        + '<label>Subject <input name="subject" value="'
        + _e(memory.get("subject",""))
        + '" required maxlength="500"/></label>'
        + '<label>Type <input name="memory_type" value="'
        + _e(memory.get("memory_type","fact"))
        + '" maxlength="100"/></label>'
        + '<label>Scope <input name="scope" value="'
        + _e(memory.get("scope","household"))
        + '" maxlength="100"/></label>'
        + '<label>Title <input name="title" value="'
        + _e(memory.get("title",""))
        + '" maxlength="500"/></label>'
        + '<label>Content <textarea name="raw_content" maxlength="16384">'
        + _e(memory.get("raw_content",""))
        + '</textarea></label>'
        + '<label>Source <input name="source" value="'
        + _e(memory.get("source",""))
        + '" maxlength="200"/></label>'
        + '<label>Language <input name="language" value="'
        + _e(memory.get("language","en"))
        + '" maxlength="10"/></label>'
        + "<button type=\"submit\">Update</button></form>"
        + f'<p><a href="/portal/memories/{_e(memory["memory_id"])}">Cancel</a></p>'
    )
    return _page(body)


def collection_list(collections, message="") -> str:
    rows = "".join(
        f"<tr><td><a href=\"/portal/collections/{_e(c['collection_id'])}\">{_e(c['collection_id'])}</a></td>"
        f"<td>{_e(c['subject'])}</td><td>{_e(c.get('collection_type',''))}</td>"
        f"<td>{_e(c.get('status',''))}</td><td>{_e(c.get('version',''))}</td></tr>"
        for c in collections
    )
    body = (
        _navbar("collections")
        + "<h1>Collections</h1>"
        + _banner(message)
        + '<a class="btn" href="/portal/collections/create">Create Collection</a>'
        + "<table><thead><tr><th>ID</th><th>Subject</th><th>Type</th><th>Status</th><th>Version</th></tr></thead><tbody>"
        + rows
        + "</tbody></table>"
        + '<p><a href="/portal/memories">Memories</a> | <a href="/portal/audit">Audit</a></p>'
    )
    return _page(body)


def collection_detail(collection, memories, validation, message="") -> str:
    if not collection:
        return _page('<div class="banner error">Collection not found</div>')
    fields = "".join(
        f"<dt>{_e(k)}</dt><dd>{_e(collection.get(k,''))}</dd>"
        for k in ["collection_id","subject","collection_type","scope","title","summary",
                   "language","source","source_reference","status","version",
                   "supersedes_collection_id","expected_item_count","content_checksum","created_at","updated_at"]
    )
    expected = collection.get("expected_item_count", 0) or 0
    current = len(memories)
    missing = expected - current
    valid = validation.get("valid", False)
    issues = validation.get("issues", [])
    mem_rows = "".join(
        f'<tr><td>{_e(m.get("sequence_number",""))}</td><td>{_e(m.get("subject",""))}</td>'
        f'<td>{_e(m.get("status",""))}</td><td>{_e(m.get("version",""))}</td>'
        f'<td><a href="/portal/memories/{_e(m["memory_id"])}">Edit</a> | '
        f'<form method="post" action="/portal/collections/{_e(collection["collection_id"])}/memories/{_e(m["memory_id"])}/move-up" style="display:inline"><button type="submit"{" disabled" if i == 0 else ""}>Up</button></form> | '
        f'<form method="post" action="/portal/collections/{_e(collection["collection_id"])}/memories/{_e(m["memory_id"])}/move-down" style="display:inline"><button type="submit"{" disabled" if i == len(memories) - 1 else ""}>Down</button></form> | '
        f'<a href="/portal/memories/{_e(m["memory_id"])}">Forget</a></td></tr>'
        for i, m in enumerate(memories)
    )
    validation_html = (
        f"<p>Expected Sections: {_e(expected)}</p>"
        f"<p>Current Sections: {_e(current)}</p>"
        f"<p>Missing Sections: {_e(missing)}</p>"
    )
    if expected > 0:
        if valid:
            validation_html += "<p>Status: Ready to activate</p>"
        else:
            validation_html += "<p>Status: Not ready to activate</p>"
            for issue in issues:
                validation_html += f"<p>Issue: {_e(issue)}</p>"
    else:
        validation_html += f"<p>Status: Valid: {_e(str(valid))} | Issues: {_e(', '.join(issues) or 'none')}</p>"
    activate_disabled = ' disabled' if not valid else ''
    body = (
        _navbar("collections")
        + f"<h1>Collection {_e(collection['collection_id'])}</h1>"
        + _banner(message)
        + '<dl class="detail">' + fields + '</dl>'
        + "<h2>Sections</h2><table><thead><tr><th>Seq</th><th>Title</th><th>Status</th><th>Version</th><th>Controls</th></tr></thead><tbody>"
        + mem_rows
        + "</tbody></table>"
        + "<h2>Validation</h2>"
        + validation_html
        + '<h2>Add Section</h2>'
        + f'<form method="post" action="/portal/collections/{_e(collection["collection_id"])}/memories">'
        + '<label>Title <input name="title" required maxlength="500"/></label>'
        + '<label>Type <input name="memory_type" value="fact" maxlength="100"/></label>'
        + '<label>Content <textarea name="raw_content" required></textarea></label>'
        + '<label>Structured Value (optional) <input name="structured_value"/></label>'
        + '<label>Language <input name="language" value="en" maxlength="10"/></label>'
        + '<label>Sequence <input name="sequence_number" type="number" value="1"/></label>'
        + '<button type="submit">Add Section</button></form>'
        + '<p class="helper">Add all required Sections, validate the Collection, then activate it.</p>'
        + f'<h2>Reorder</h2><form method="post" action="/portal/collections/{_e(collection["collection_id"])}/order">'
        + '<textarea name="ordered_memory_ids" rows="3" cols="60" placeholder="comma-separated memory_ids"></textarea>'
        + '<button type="submit">Reorder</button></form>'
        + f'<h2>Activate</h2><form method="post" action="/portal/collections/{_e(collection["collection_id"])}/activate" onsubmit="return confirm(\'Activate this collection?\')">'
        + f'<button type="submit"{activate_disabled}>Activate</button></form>'
        + f'<p><a href="/portal/collections/{_e(collection["collection_id"])}/edit">Edit</a> | <a href="/portal/collections">Back to list</a></p>'
    )
    return _page(body)


def collection_create_form(message="", error="") -> str:
    e = error or {}
    body = (
        _navbar("collections")
        + "<h1>Create Collection</h1>"
        + _banner(message)
        + '<form method="post" action="/portal/collections">'
        + '<label>Subject <input name="subject" value="'
        + _e(e.get("subject",""))
        + '" required maxlength="500"/></label>'
        + '<label>Type <input name="collection_type" value="'
        + _e(e.get("collection_type","fact"))
        + '" maxlength="100"/></label>'
        + '<label>Scope <input name="scope" value="'
        + _e(e.get("scope","household"))
        + '" maxlength="100"/></label>'
        + '<label>Title <input name="title" value="'
        + _e(e.get("title",""))
        + '" required maxlength="500"/></label>'
        + '<label>Summary <textarea name="summary" maxlength="8192">'
        + _e(e.get("summary",""))
        + '</textarea></label>'
        + '<label>Source <input name="source" value="'
        + _e(e.get("source","portal"))
        + '" maxlength="200"/></label>'
        + '<label>Language <input name="language" value="'
        + _e(e.get("language","en"))
        + '" maxlength="10"/></label>'
        + '<label>Expected Item Count <input name="expected_item_count" type="number" value="'
        + _e(e.get("expected_item_count",""))
        + '"/></label>'
        + "<button type=\"submit\">Create</button></form>"
        + '<p><a href="/portal/collections">Cancel</a></p>'
    )
    return _page(body)


def collection_edit_form(collection, message="", error="") -> str:
    body = (
        _navbar("collections")
        + f"<h1>Edit Collection {_e(collection['collection_id'])}</h1>"
        + _banner(message)
        + f'<form method="post" action="/portal/collections/{_e(collection["collection_id"])}">'
        + '<label>Subject <input name="subject" value="'
        + _e(collection.get("subject",""))
        + '" required maxlength="500"/></label>'
        + '<label>Type <input name="collection_type" value="'
        + _e(collection.get("collection_type","fact"))
        + '" maxlength="100"/></label>'
        + '<label>Scope <input name="scope" value="'
        + _e(collection.get("scope","household"))
        + '" maxlength="100"/></label>'
        + '<label>Title <input name="title" value="'
        + _e(collection.get("title",""))
        + '" required maxlength="500"/></label>'
        + '<label>Summary <textarea name="summary" maxlength="8192">'
        + _e(collection.get("summary",""))
        + '</textarea></label>'
        + '<label>Source <input name="source" value="'
        + _e(collection.get("source",""))
        + '" maxlength="200"/></label>'
        + '<label>Source Reference <input name="source_reference" value="'
        + _e(collection.get("source_reference",""))
        + '"/></label>'
        + '<label>Expected Item Count <input name="expected_item_count" type="number" value="'
        + _e(collection.get("expected_item_count",""))
        + '"/></label>'
        + "<button type=\"submit\">Update</button></form>"
        + f'<p><a href="/portal/collections/{_e(collection["collection_id"])}">Cancel</a></p>'
    )
    return _page(body)


def audit_log(records, entity_id="", entity_type="", action="", message="") -> str:
    rows = "".join(
        f"<tr><td>{_e(r.get('audit_id',''))}</td><td>{_e(r.get('entity_type',''))}</td>"
        f"<td>{_e(r.get('entity_id',''))}</td><td>{_e(r.get('action',''))}</td>"
        f"<td>{_e(r.get('actor',''))}</td><td>{_e(r.get('created_at',''))}</td></tr>"
        for r in records
    )
    body = (
        _navbar("audit")
        + "<h1>Audit Log</h1>"
        + _banner(message)
        + '<form method="get" class="filter"><input name="entity_id" value="'
        + _e(entity_id)
        + '" placeholder="entity_id"/>'
        + '<input name="entity_type" value="'
        + _e(entity_type)
        + '" placeholder="entity_type"/>'
        + '<input name="action" value="'
        + _e(action)
        + '" placeholder="action"/>'
        + '<button type="submit">Filter</button></form>'
        + "<table><thead><tr><th>ID</th><th>Entity Type</th><th>Entity ID</th><th>Action</th><th>Actor</th><th>Created</th></tr></thead><tbody>"
        + rows
        + "</tbody></table>"
        + '<p><a href="/portal/memories">Memories</a> | <a href="/portal/collections">Collections</a></p>'
    )
    return _page(body)
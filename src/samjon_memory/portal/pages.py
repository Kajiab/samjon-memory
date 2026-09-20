"""Server-rendered HTML pages for the Core Portal.

All dynamic content is XSS-escaped via ``_e``. Nothing here ever emits
credentials, audit secrets, database paths, or sensitive configuration.
This module only renders markup -- it never accesses SQLite or repositories.
"""

import html as _html

from samjon_memory.constants import DEFAULT_PAGE_SIZE


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _e(text) -> str:
    return _html.escape(str(text) if text is not None else "")


def _is_error_message(message: str) -> bool:
    if message.startswith("error"):
        return True
    head = message.split(":", 1)[0].strip()
    return bool(head) and head.isupper()


def _friendly_error(message: str) -> str:
    text = message or "Something went wrong. Please try again."
    if text.startswith("error:"):
        detail = text[len("error:"):].strip()
        return detail or text
    if ":" in text:
        head, rest = text.split(":", 1)
        if head.strip().isupper() and rest.strip():
            return rest.strip()
    return text


_MESSAGE_TEXT = {
    "created": "Created successfully.",
    "updated": "Changes saved.",
    "superseded": "Record superseded.",
    "forgotten": "Record forgotten.",
    "activated": "Collection activated.",
    "memory_activated": "Memory activated.",
    "section_added": "Section added.",
    "reordered": "Order updated.",
    "moved_up": "Section moved up.",
    "moved_down": "Section moved down.",
    "cancelled": "Action cancelled - nothing was changed.",
    "restored": "Record restored to draft.",
    "purged": "Record purged permanently.",
}


def _banner(message: str) -> str:
    if not message:
        return ""
    if _is_error_message(message):
        return ('<div class="banner error" role="alert">'
                + _e(_friendly_error(message)) + "</div>")
    text = _MESSAGE_TEXT.get(message, message)
    return f'<div class="banner success" role="status">{_e(text)}</div>'


def _error_banner(text: str) -> str:
    if not text:
        return ""
    return f'<div class="banner error" role="alert">{_e(_friendly_error(text))}</div>'


def _page(body: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
        '<meta name="color-scheme" content="light"/>'
        '<title>Samjon Memory Portal</title>'
        '<link rel="stylesheet" href="/portal/static/portal.css"/>'
        '<script src="/portal/static/portal.js" defer></script>'
        '</head><body>'
        '<a class="skip-link" href="#main">Skip to content</a>'
        '<main id="main">'
        + body
        + '</main>'
        '<footer class="footer"><p>Samjon Memory Core Portal</p></footer>'
        '</body></html>'
    )


def _navbar(active: str = "") -> str:
    links = [
        ("dashboard", "/portal/", "Dashboard"),
        ("memories", "/portal/memories", "Memories"),
        ("collections", "/portal/collections", "Collections"),
        ("admin", "/portal/admin", "Administration"),
        ("audit", "/portal/audit", "Audit"),
    ]
    items = "".join(
        f'<a class="nav{" active" if key == active else ""}" href="{_e(href)}"'
        f'{" aria-current=\"page\"" if key == active else ""}>{_e(label)}</a>'
        for key, href, label in links
    )
    return ('<header class="site-header">'
            f'<nav class="navbar" aria-label="Primary">{items}</nav></header>')


_STATUS_LABELS = {
    "draft": "Draft",
    "active": "Active",
    "superseded": "Superseded",
    "forgotten": "Forgotten",
}


def _status_badge(status: str) -> str:
    key = _e(status or "")
    label = _e(_STATUS_LABELS.get(status, status)) if status else "Unknown"
    return f'<span class="badge {key}">{label}</span>'


def _metric(href, value, label, note="") -> str:
    note_html = f'<span class="stat-note">{_e(note)}</span>' if note else ""
    return ('<a class="metric-link" href="' + _e(href) + '">'
            + f'<span class="stat-value">{_e(value)}</span>'
            + f'<span class="stat-label">{_e(label)}</span>'
            + note_html + "</a>")


def _text_field(name, label, value="", required=False, maxlen=None,
                placeholder="", helper="", type_="text") -> str:
    req = " required" if required else ""
    mark = ' <span class="req" aria-hidden="true">*</span>' if required else ""
    maxa = f' maxlength="{maxlen}"' if maxlen else ""
    ph = f' placeholder="{_e(placeholder)}"' if placeholder else ""
    helper_html = f'<span class="hint">{_e(helper)}</span>' if helper else ""
    return (f'<label class="field"><span class="field-label">{_e(label)}{mark}</span>'
            f'<input name="{_e(name)}" type="{type_}" value="{_e(value)}"{req}{maxa}{ph}/>'
            f'{helper_html}</label>')


def _textarea_field(name, label, value="", required=False, maxlen=None,
                    rows=6, helper="") -> str:
    req = " required" if required else ""
    mark = ' <span class="req" aria-hidden="true">*</span>' if required else ""
    maxa = f' maxlength="{maxlen}"' if maxlen else ""
    counter = (f'<output class="counter" data-for="{_e(name)}">'
               f'{_e(len(value or ""))}</output>') if maxlen else ""
    helper_html = f'<span class="hint">{_e(helper)}</span>' if helper else ""
    return (f'<label class="field"><span class="field-label">{_e(label)}{mark}'
            f'{counter}</span>'
            f'<textarea name="{_e(name)}" rows="{rows}"{req}{maxa}>{_e(value)}</textarea>'
            f'{helper_html}</label>')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard(stats, recent_audit, message="") -> str:
    memories = (
        _metric("/portal/memories?scope=standalone", stats["standalone_total"],
                "Standalone Memories", "Memories that are not part of any collection.")
        + _metric("/portal/memories?scope=standalone&status=draft", stats["standalone_draft"],
                  "Draft", "Standalone memories not yet activated.")
        + _metric("/portal/memories?scope=standalone&status=active", stats["standalone_active"],
                  "Active", "Standalone memories that are active.")
        + _metric("/portal/memories?scope=standalone&status=superseded", stats["standalone_superseded"],
                  "Superseded", "Standalone memories replaced by a newer one.")
        + _metric("/portal/memories?scope=standalone&status=forgotten", stats["standalone_forgotten"],
                  "Forgotten", "Standalone memories marked forgotten.")
    )
    collections = (
        _metric("/portal/collections", stats["collections_total"],
                "Total Collections", "All collections of every status.")
        + _metric("/portal/collections?status=draft", stats["collections_draft"],
                  "Draft", "Collections that are not yet activated.")
        + _metric("/portal/collections?status=active", stats["collections_active"],
                  "Active", "Collections that are activated.")
        + _metric("/portal/memories?scope=collection", stats["collection_sections_total"],
                  "Collection Sections", "Memories that belong to a collection.")
        + _metric("/portal/collections?invalid=1", stats["invalid_collections"],
                  "Invalid Collections", "Collections that fail validation: missing expected sections, duplicate order, or a forgotten section.")
    )
    system = (
        _metric("/portal/memories", stats["total_facts"],
                "Total Facts", "Standalone memories + collection sections, all statuses.")
        + _metric("/portal/memories?scope=standalone", stats["standalone_total"],
                  "Standalone Memories", "Memories that are not part of any collection.")
        + _metric("/portal/memories?scope=collection", stats["collection_sections_total"],
                  "Collection Sections", "Memories that belong to a collection.")
        + _metric("/portal/memories?scope=active_knowledge", stats["active_knowledge"],
                  "Active Knowledge", "Active standalone memories + active sections inside active collections.")
    )
    recent_rows = "".join(
        f'<li><span class="badge">{_e(r.get("action",""))}</span> '
        f'{_e(r.get("entity_type",""))} {_e(r.get("entity_id",""))}'
        f'<span class="when">{_e(r.get("created_at",""))}</span></li>'
        for r in recent_audit
    )
    if not recent_rows:
        recent_rows = '<li class="empty">No recent activity.</li>'
    body = (
        _navbar("dashboard")
        + "<h1>Overview</h1>"
        + _banner(message)
        + '<section class="card"><h2 class="metric-group-title">Memories</h2><div class="metric-grid">'
        + memories + "</div></section>"
        + '<section class="card"><h2 class="metric-group-title">Collections</h2><div class="metric-grid">'
        + collections + "</div></section>"
        + '<section class="card"><h2 class="metric-group-title">System Overview</h2><div class="metric-grid">'
        + system + "</div></section>"
        + '<section class="card"><h2>Quick actions</h2>'
        + '<div class="quick-actions">'
        + '<a class="btn" href="/portal/memories/create">Create Memory</a>'
        + '<a class="btn" href="/portal/collections/create">Create Collection</a>'
        + '<a class="btn btn-ghost" href="/portal/memories">Browse Memories</a>'
        + '<a class="btn btn-ghost" href="/portal/collections">Browse Collections</a>'
        + "</div></section>"
        + '<section class="card"><h2>Recent activity</h2>'
        + f'<ul class="audit-mini">{recent_rows}</ul></section>'
    )
    return _page(body)


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def memory_list(memories, subject="", status_filter="", scope="", offset=0, message="") -> str:
    if memories:
        rows = "".join(
            f'<tr><td><a class="mono" href="/portal/memories/{_e(m["memory_id"])}">{_e(m["memory_id"])}</a></td>'
            f"<td>{_e(m['subject'])}</td>"
            f"<td>{_status_badge(m.get('status',''))}</td>"
            f"<td>{_e(m.get('memory_type',''))}</td>"
            f"<td>{_e(m.get('scope',''))}</td>"
            f"<td>{_e(m.get('version',''))}</td></tr>"
            for m in memories
        )
    else:
        rows = ('<tr><td colspan="6"><div class="empty-state">'
                '<p>No memories found yet.</p>'
                '<p>Create your first memory to get started.</p>'
                '<p><a class="btn" href="/portal/memories/create">Create Memory</a></p>'
                '</div></td></tr>')

    status_options = [
        ("", "All statuses"),
        ("draft", "Draft"),
        ("active", "Active"),
        ("superseded", "Superseded"),
        ("forgotten", "Forgotten"),
    ]
    opts = "".join(
        f'<option value="{_e(val)}"{" selected" if status_filter == val else ""}>{_e(lbl)}</option>'
        for val, lbl in status_options
    )
    scope_options = [
        ("", "All memories"),
        ("standalone", "Standalone"),
        ("collection", "Collection sections"),
        ("active_knowledge", "Active knowledge"),
    ]
    scope_opts = "".join(
        f'<option value="{_e(val)}"{" selected" if scope == val else ""}>{_e(lbl)}</option>'
        for val, lbl in scope_options
    )
    q = f"subject={_e(subject)}&status={_e(status_filter)}&scope={_e(scope)}"
    prev_offset = max(0, offset - DEFAULT_PAGE_SIZE)
    next_offset = offset + DEFAULT_PAGE_SIZE
    prev_link = (f'<a class="btn btn-ghost" href="/portal/memories?offset={prev_offset}&{q}">Previous</a>'
                 if offset > 0 else '<span class="btn btn-ghost disabled">Previous</span>')
    pagination = (f'<nav class="pagination" aria-label="Pagination">{prev_link}'
                  f'<a class="btn btn-ghost" href="/portal/memories?offset={next_offset}&{q}">Next</a></nav>')

    body = (
        _navbar("memories")
        + "<h1>Memories</h1>"
        + _banner(message)
        + f'<p class="count">{_e(len(memories))} shown</p>'
        + '<div class="btn-row"><a class="btn" href="/portal/memories/create">Create Memory</a></div>'
        + '<form method="get" class="filter" action="/portal/memories">'
        + f'<input name="subject" value="{_e(subject)}" placeholder="Search subject"/>'
        + f'<select name="status">{opts}</select>'
        + f'<select name="scope">{scope_opts}</select>'
        + '<button type="submit" class="btn btn-ghost">Filter</button></form>'
        + '<div class="table-wrapper"><table>'
        + '<thead><tr><th>ID</th><th>Subject</th><th>Status</th><th>Type</th><th>Scope</th><th>Version</th></tr></thead>'
        + f"<tbody>{rows}</tbody></table></div>"
        + pagination
    )
    return _page(body)


_MEMORY_FIELDS = (
    ("memory_id", "Memory ID"),
    ("collection_id", "Collection ID"),
    ("sequence_number", "Sequence"),
    ("subject", "Subject"),
    ("memory_type", "Type"),
    ("scope", "Scope"),
    ("title", "Title"),
    ("section_path", "Section path"),
    ("raw_content", "Content"),
    ("structured_value_json", "Structured value"),
    ("source", "Source"),
    ("language", "Language"),
    ("status", "Status"),
    ("version", "Version"),
    ("supersedes_memory_id", "Supersedes"),
    ("content_checksum", "Checksum"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
)


def _activate_memory_section(memory) -> str:
    """Activate card for a standalone draft Memory; empty string otherwise."""
    if memory.get("status") != "draft":
        return ""
    mid = _e(memory["memory_id"])
    version = _e(memory.get("version", ""))
    return (
        '<section class="card"><h2>Activate</h2>'
        '<p class="hint">Publish this memory so it becomes active and searchable.</p>'
        + f'<form method="post" action="/portal/memories/{mid}/activate" '
        + "onsubmit=\"return confirm('Activate this memory? It becomes active.')\">"
        + f'<input type="hidden" name="expected_version" value="{version}"/>'
        + '<button type="submit" class="btn">Activate</button></form></section>'
    )


def _purged_notice() -> str:
    return ('<section class="card"><h2>Purged</h2>'
            '<p class="hint">This record was permanently purged. Its content is gone and it cannot be restored, edited, activated, or reused.</p></section>')


def _restore_purge_cards(prefix, eid, version) -> str:
    restore = (
        '<section class="card"><h2>Restore</h2>'
        '<p class="hint">Bring this record back to draft so it can be reused.</p>'
        + f'<form method="post" action="/portal/{prefix}/{eid}/restore" '
        + "onsubmit=\"return confirm('Restore this record to draft?')\">"
        + '<button type="submit" class="btn">Restore</button></form></section>'
    )
    purge = (
        '<section class="card card-danger"><h2>Purge</h2>'
        '<p class="hint">Permanently erases content. Administrator only; type PURGE to confirm.</p>'
        + f'<form method="post" action="/portal/{prefix}/{eid}/purge" '
        + "onsubmit=\"return confirm('This permanently erases the content and cannot be undone. Type PURGE to confirm.')\">"
        + f'<input type="hidden" name="expected_version" value="{_e(version)}"/>'
        + '<label class="field"><span class="field-label">Type PURGE to confirm</span>'
        + '<input name="confirmation" autocomplete="off" placeholder="PURGE" required/></label>'
        + '<button type="submit" class="btn btn-danger">Purge</button></form></section>'
    )
    return restore + purge


def _memory_btn_row(memory, mid) -> str:
    edit = (f'<a class="btn" href="/portal/memories/{mid}/edit">Edit</a>'
            if not memory.get("purged_at") else "")
    return ('<div class="btn-row">' + edit
            + '<a class="btn btn-ghost" href="/portal/memories/create">New</a>'
            + '<a class="btn btn-ghost" href="/portal/memories">List</a></div>')


def _memory_actions(memory, mid) -> str:
    if memory.get("purged_at"):
        return _purged_notice()
    if memory.get("status") == "forgotten":
        return _restore_purge_cards("memories", mid, memory.get("version", ""))
    return (
        _activate_memory_section(memory)
        + '<section class="card"><h2>Supersede</h2>'
        + '<p class="hint">Mark this memory as replaced by another, newer memory.</p>'
        + f'<form method="post" action="/portal/memories/{mid}/supersede" '
        + "onsubmit=\"return confirm('Supersede this memory with the replacement? The current version is kept as superseded.')\">"
        + '<label class="field"><span class="field-label">Replacement memory ID <span class="req" aria-hidden="true">*</span></span>'
        + '<input name="replacement_memory_id" required placeholder="e.g. mem-1234"/>'
        + '<span class="hint">Use the ID of the memory that replaces this one.</span></label>'
        + '<button type="submit" class="btn">Supersede</button></form></section>'
        + '<section class="card card-danger"><h2>Forget</h2>'
        + '<p class="hint">Forgetting removes this memory from active use. This cannot be undone.</p>'
        + f'<form method="post" action="/portal/memories/{mid}/forget" '
        + "onsubmit=\"return confirm('Forget this memory? This cannot be undone.')\">"
        + '<button type="submit" class="btn btn-danger">Forget</button></form></section>'
    )


def memory_detail(memory, message="") -> str:
    if not memory:
        return _page(_navbar("memories")
                     + '<div class="banner error" role="alert">This memory was not found.</div>'
                     + '<p><a class="btn btn-ghost" href="/portal/memories">Back to Memories</a></p>')
    fields = ""
    for key, label in _MEMORY_FIELDS:
        if key not in memory:
            continue
        if key in ("raw_content", "structured_value_json"):
            inner = f"<pre>{_e(memory.get(key, ''))}</pre>"
        else:
            inner = _e(memory.get(key, ""))
        fields += f"<dt>{_e(label)}</dt><dd>{inner}</dd>"
    mid = _e(memory["memory_id"])
    body = (
        _navbar("memories")
        + "<h1>Memory</h1>"
        + _banner(message)
        + f'<p class="subtitle">{mid} {_status_badge(memory.get("status",""))}</p>'
        + f'<dl class="detail">{fields}</dl>'
        + _memory_btn_row(memory, mid)
        + _memory_actions(memory, mid)
        + '<p><a class="btn btn-ghost" href="/portal/memories">Back to Memories</a></p>'
    )
    return _page(body)


def memory_create_form(message="", error="") -> str:
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    fields = (
        _text_field("subject", "Subject", prefill.get("subject", ""), required=True,
                    maxlen=500, placeholder="e.g. Living room lighting",
                    helper="A short, memorable name for this memory.")
        + _text_field("memory_type", "Type", prefill.get("memory_type", "fact"),
                      maxlen=100, helper="e.g. fact, note, preference.")
        + _text_field("scope", "Scope", prefill.get("scope", "household"),
                      maxlen=100, helper="Where this memory applies, e.g. household.")
        + _text_field("title", "Title", prefill.get("title", ""), maxlen=500,
                      helper="Optional short title.")
        + _textarea_field("raw_content", "Content", prefill.get("raw_content", ""),
                          required=True, maxlen=16384, rows=8,
                          helper="Required. The full text of the memory.")
        + _text_field("source", "Source", prefill.get("source", "portal"), maxlen=200)
        + _text_field("language", "Language", prefill.get("language", "en"),
                      maxlen=10, helper="Language code, e.g. en, th.")
    )
    body = (
        _navbar("memories")
        + "<h1>Create Memory</h1>"
        + _banner(message)
        + _error_banner(err_text)
        + '<form method="post" action="/portal/memories"><fieldset><legend>New memory</legend>'
        + fields
        + '<button type="submit" class="btn">Create</button></fieldset></form>'
        + '<p class="cancel"><a class="btn btn-ghost" href="/portal/memories">Cancel</a></p>'
    )
    return _page(body)


def memory_edit_form(memory, message="", error="") -> str:
    if not memory:
        return _page(_navbar("memories")
                     + '<div class="banner error" role="alert">This memory was not found.</div>')
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    mid = _e(memory["memory_id"])
    fields = (
        _text_field("subject", "Subject",
                    prefill.get("subject", memory.get("subject", "")), required=True, maxlen=500)
        + _text_field("memory_type", "Type",
                      prefill.get("memory_type", memory.get("memory_type", "fact")), maxlen=100)
        + _text_field("scope", "Scope",
                      prefill.get("scope", memory.get("scope", "household")), maxlen=100)
        + _text_field("title", "Title", prefill.get("title", memory.get("title", "")), maxlen=500)
        + _textarea_field("raw_content", "Content",
                          prefill.get("raw_content", memory.get("raw_content", "")),
                          required=True, maxlen=16384, rows=8)
        + _text_field("source", "Source", prefill.get("source", memory.get("source", "")), maxlen=200)
        + _text_field("language", "Language",
                      prefill.get("language", memory.get("language", "en")), maxlen=10)
    )
    hidden = f'<input type="hidden" name="expected_version" value="{_e(memory.get("version",""))}"/>'
    body = (
        _navbar("memories")
        + "<h1>Edit Memory</h1>"
        + _banner(message)
        + _error_banner(err_text)
        + f'<p class="subtitle">{mid}</p>'
        + f'<form method="post" action="/portal/memories/{mid}"><fieldset><legend>Edit memory</legend>'
        + hidden + fields
        + '<button type="submit" class="btn">Update</button></fieldset></form>'
        + f'<p class="cancel"><a class="btn btn-ghost" href="/portal/memories/{mid}">Cancel</a></p>'
    )
    return _page(body)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

_COLLECTION_FIELDS = (
    ("collection_id", "Collection ID"),
    ("subject", "Subject"),
    ("collection_type", "Type"),
    ("scope", "Scope"),
    ("title", "Title"),
    ("summary", "Summary"),
    ("language", "Language"),
    ("source", "Source"),
    ("source_reference", "Source reference"),
    ("status", "Status"),
    ("version", "Version"),
    ("supersedes_collection_id", "Supersedes"),
    ("expected_item_count", "Expected sections"),
    ("content_checksum", "Checksum"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
)


def _collection_filter_links(status_filter="", invalid=False) -> str:
    def _link(href, label, is_active):
        cls = "btn btn-ghost" + (" active" if is_active else "")
        current = ' aria-current="true"' if is_active else ""
        return f'<a class="{cls}" href="{_e(href)}"{current}>{_e(label)}</a>'

    return (
        '<div class="filter" role="group" aria-label="Collection filters">'
        + _link("/portal/collections", "All", (not status_filter) and not invalid)
        + _link("/portal/collections?status=draft", "Draft", status_filter == "draft" and not invalid)
        + _link("/portal/collections?status=active", "Active", status_filter == "active" and not invalid)
        + _link("/portal/collections?invalid=1", "Invalid", bool(invalid))
        + "</div>"
    )


def collection_list(collections, message="", status_filter="", invalid=False) -> str:
    if collections:
        rows = "".join(
            f'<tr><td><a class="mono" href="/portal/collections/{_e(c["collection_id"])}">{_e(c["collection_id"])}</a></td>'
            f"<td>{_e(c.get('title') or c.get('subject') or '')}</td>"
            f"<td>{_e(c.get('collection_type',''))}</td>"
            f"<td>{_status_badge(c.get('status',''))}</td>"
            f"<td>{_e(c.get('version',''))}</td></tr>"
            for c in collections
        )
    else:
        rows = ('<tr><td colspan="5"><div class="empty-state">'
                '<p>No collections yet.</p>'
                '<p>Group related memories into an ordered collection.</p>'
                '<p><a class="btn" href="/portal/collections/create">Create Collection</a></p>'
                '</div></td></tr>')
    body = (
        _navbar("collections")
        + "<h1>Collections</h1>"
        + _banner(message)
        + _collection_filter_links(status_filter, invalid)
        + (('<p class="hint">Showing collections that fail validation.</p>') if invalid else "")
        + '<div class="btn-row"><a class="btn" href="/portal/collections/create">Create Collection</a></div>'
        + '<div class="table-wrapper"><table>'
        + '<thead><tr><th>ID</th><th>Title</th><th>Type</th><th>Status</th><th>Version</th></tr></thead>'
        + f"<tbody>{rows}</tbody></table></div>"
    )
    return _page(body)


def _issues_html(issues):
    items = "".join(f'<li class="issue">{_e(i)}</li>' for i in issues)
    return f'<div class="validation-card"><h3>What to fix</h3><ul class="issue-list">{items}</ul></div>'


def _assembled_preview(memories):
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda x: x.get("sequence_number", 0))
    blocks = "".join(
        f'<article class="preview-block"><h3>{_e(m.get("subject",""))}</h3>'
        f'<pre>{_e(m.get("raw_content",""))}</pre></article>'
        for m in ordered
    )
    return ('<section class="assembled-preview"><h2>Assembled preview</h2>'
            '<p class="hint">How the collection reads when the sections are joined in order.</p>'
            + blocks + "</section>")


def _add_section_form(cid, current):
    suggested = current + 1
    fields = (
        _text_field("title", "Section title", required=True, maxlen=500,
                    placeholder="e.g. Overview")
        + _text_field("memory_type", "Type", "fact", maxlen=100)
        + _textarea_field("raw_content", "Content", required=True, maxlen=16384, rows=6)
        + _text_field("structured_value", "Structured value (optional)",
                      helper="Optional structured data, as text.")
        + _text_field("language", "Language", "en", maxlen=10)
        + _text_field("sequence_number", "Position", suggested, type_="number")
    )
    return (f'<section class="card"><h2>Add Section</h2>'
            f'<form method="post" action="/portal/collections/{cid}/memories">'
            f'<fieldset><legend>New section</legend>{fields}'
            + '<button type="submit" class="btn">Add Section</button></fieldset></form>'
            + '<p class="hint">Each section becomes an independently editable memory in this collection.</p></section>')


def collection_detail(collection, memories, validation, message="") -> str:
    if not collection:
        return _page(_navbar("collections")
                     + '<div class="banner error" role="alert">This collection was not found.</div>')
    fields = ""
    for key, label in _COLLECTION_FIELDS:
        if key not in collection:
            continue
        if key == "summary":
            inner = f"<pre>{_e(collection.get(key, ''))}</pre>"
        else:
            inner = _e(collection.get(key, ""))
        fields += f"<dt>{_e(label)}</dt><dd>{inner}</dd>"
    cid = _e(collection["collection_id"])

    expected = collection.get("expected_item_count", 0) or 0
    current = len(memories)
    missing = max(0, expected - current)
    valid = bool(validation.get("valid", False))
    issues = validation.get("issues", []) or []

    if expected == 0:
        state_line = ('<p class="progress-state is-ok">Status: Ready to activate</p>'
                      if valid else '<p class="progress-state">Status: Not ready to activate</p>')
    elif valid:
        state_line = '<p class="progress-state is-ok">Status: Ready to activate</p>'
    else:
        state_line = '<p class="progress-state">Status: Not ready to activate</p>'

    fill_class = "success" if valid else ("warning" if current > 0 else "error")
    pct = 0 if expected == 0 else min(100, int(current / expected * 100))

    progress = (
        '<section class="card"><h2>Progress</h2>'
        + f'<div class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="{expected}" aria-valuenow="{current}" aria-label="Collection progress"><div class="fill {fill_class}" style="width:{pct}%"></div></div>'
        + f'<p class="progress-label">Expected Sections: {_e(expected)} &middot; Current Sections: {_e(current)} &middot; Missing Sections: {_e(missing)}</p>'
        + state_line
        + (_issues_html(issues) if issues else "")
        + "</section>"
    )

    if memories:
        rows = []
        for i, m in enumerate(memories):
            mid = _e(m["memory_id"])
            subject = _e(m.get("subject", ""))
            seq = _e(m.get("sequence_number", ""))
            up_disabled = ' disabled' if i == 0 else ""
            down_disabled = ' disabled' if i == len(memories) - 1 else ""
            if m.get("purged_at"):
                controls = '<span class="hint">purged</span>'
            elif m.get("status") == "forgotten":
                controls = (
                    f'<form method="post" action="/portal/memories/{mid}/restore" '
                    "onsubmit=\"return confirm('Restore this section to draft?')\">"
                    f'<button type="submit" class="btn btn-xsmall">Restore</button></form>'
                )
            else:
                controls = (
                    f'<a class="btn btn-xsmall" href="/portal/memories/{mid}/edit">Edit</a>'
                    f'<form method="post" action="/portal/collections/{cid}/memories/{mid}/move-up">'
                    f'<button type="submit" class="btn btn-xsmall"{up_disabled} aria-label="Move {subject} up" title="Move up">Up</button></form>'
                    f'<form method="post" action="/portal/collections/{cid}/memories/{mid}/move-down">'
                    f'<button type="submit" class="btn btn-xsmall"{down_disabled} aria-label="Move {subject} down" title="Move down">Down</button></form>'
                    f'<form method="post" action="/portal/memories/{mid}/forget" '
                    "onsubmit=\"return confirm('Forget this section? This cannot be undone.')\">"
                    f'<button type="submit" class="btn btn-xsmall btn-danger">Forget</button></form>'
                )
            rows.append(
                f"<tr><td>{seq}</td>"
                f"<td>{subject} <span class=\"mono\">{mid}</span></td>"
                f"<td>{_status_badge(m.get('status',''))}</td>"
                f"<td>{_e(m.get('version',''))}</td>"
                f'<td class="section-controls">{controls}</td></tr>'
            )
        sections_html = "".join(rows)
    else:
        sections_html = ('<tr><td colspan="5"><div class="empty-state">'
                         '<p>No sections yet.</p><p>Add your first section below.</p></div></td></tr>')

    activate_disabled = ' disabled' if not valid else ''
    activate_note = ('<p class="hint">Add all required sections so the collection can be activated.</p>'
                     if not valid else '')
    activate_html = (
        '<section class="card"><h2>Activate</h2>'
        + f'<form method="post" action="/portal/collections/{cid}/activate" '
        + "onsubmit=\"return confirm('Publish this collection? It becomes available to search and read.')\">"
        + f'<button type="submit"{activate_disabled}>Activate</button></form>'
        + activate_note
        + "</section>"
    )

    if collection.get("purged_at"):
        lifecycle_html = _purged_notice()
        can_edit_sections = False
    elif collection.get("status") == "forgotten":
        lifecycle_html = _restore_purge_cards("collections", cid, collection.get("version", ""))
        can_edit_sections = False
    else:
        lifecycle_html = activate_html
        can_edit_sections = True

    body = (
        _navbar("collections")
        + "<h1>Collection</h1>"
        + _banner(message)
        + f'<p class="subtitle">{cid} {_status_badge(collection.get("status",""))}</p>'
        + f'<dl class="detail">{fields}</dl>'
        + '<div class="btn-row">'
        + f'<a class="btn" href="/portal/collections/{cid}/edit">Edit details</a>'
        + '<a class="btn btn-ghost" href="/portal/collections">All collections</a></div>'
        + progress
        + '<section class="card"><h2>Sections</h2>'
        + '<div class="table-wrapper"><table>'
        + '<thead><tr><th>#</th><th>Section</th><th>Status</th><th>Version</th><th>Actions</th></tr></thead>'
        + f"<tbody>{sections_html}</tbody></table></div></section>"
        + (_add_section_form(cid, current) if can_edit_sections else "")
        + _assembled_preview(memories)
        + lifecycle_html
        + '<p class="cancel"><a class="btn btn-ghost" href="/portal/collections">Back to Collections</a></p>'
    )
    return _page(body)


def collection_create_form(message="", error="") -> str:
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    fields = (
        _text_field("subject", "Subject", prefill.get("subject", ""), required=True,
                    maxlen=500, placeholder="e.g. Garden care")
        + _text_field("collection_type", "Type",
                      prefill.get("collection_type", "fact"), maxlen=100)
        + _text_field("scope", "Scope", prefill.get("scope", "household"), maxlen=100)
        + _text_field("title", "Title", prefill.get("title", ""), required=True,
                      maxlen=500, helper="A short name for the collection.")
        + _textarea_field("summary", "Summary", prefill.get("summary", ""),
                          maxlen=8192, rows=4,
                          helper="Optional overview of what the collection contains.")
        + _text_field("source", "Source", prefill.get("source", "portal"), maxlen=200)
        + _text_field("source_reference", "Source reference",
                      prefill.get("source_reference", ""),
                      helper="Optional reference, e.g. a book, page or person.")
        + _text_field("language", "Language", prefill.get("language", "en"), maxlen=10)
        + _text_field("expected_item_count", "Expected sections",
                      prefill.get("expected_item_count", ""), type_="number",
                      helper="How many sections you plan to add.")
    )
    body = (
        _navbar("collections")
        + "<h1>Create Collection</h1>"
        + _banner(message)
        + _error_banner(err_text)
        + '<form method="post" action="/portal/collections"><fieldset><legend>New collection</legend>'
        + fields
        + '<button type="submit" class="btn">Create</button></fieldset></form>'
        + '<p class="cancel"><a class="btn btn-ghost" href="/portal/collections">Cancel</a></p>'
    )
    return _page(body)


def collection_edit_form(collection, message="", error="") -> str:
    if not collection:
        return _page(_navbar("collections")
                     + '<div class="banner error" role="alert">This collection was not found.</div>')
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    cid = _e(collection["collection_id"])
    ev = _e(str(collection.get("expected_item_count") or ""))
    fields = (
        _text_field("subject", "Subject",
                    prefill.get("subject", collection.get("subject", "")), required=True, maxlen=500)
        + _text_field("collection_type", "Type",
                      prefill.get("collection_type", collection.get("collection_type", "fact")), maxlen=100)
        + _text_field("scope", "Scope",
                      prefill.get("scope", collection.get("scope", "household")), maxlen=100)
        + _text_field("title", "Title",
                      prefill.get("title", collection.get("title", "")), required=True, maxlen=500)
        + _textarea_field("summary", "Summary",
                          prefill.get("summary", collection.get("summary", "")), maxlen=8192, rows=4)
        + _text_field("source", "Source",
                      prefill.get("source", collection.get("source", "")), maxlen=200)
        + _text_field("source_reference", "Source reference",
                      prefill.get("source_reference", collection.get("source_reference", "")))
        + _text_field("language", "Language",
                      prefill.get("language", collection.get("language", "en")), maxlen=10)
        + _text_field("expected_item_count", "Expected sections",
                      prefill.get("expected_item_count", ev), type_="number")
    )
    body = (
        _navbar("collections")
        + "<h1>Edit Collection</h1>"
        + _banner(message)
        + _error_banner(err_text)
        + f'<p class="subtitle">{cid}</p>'
        + f'<form method="post" action="/portal/collections/{cid}"><fieldset><legend>Edit collection</legend>'
        + fields
        + '<button type="submit" class="btn">Update</button></fieldset></form>'
        + f'<p class="cancel"><a class="btn btn-ghost" href="/portal/collections/{cid}">Cancel</a></p>'
    )
    return _page(body)


def audit_log(records, entity_id="", entity_type="", action="", since="", until="", offset=0, page_size=20, count=0, message="", summary=None) -> str:
    if records:
        rows = "".join(
            f'<tr><td class="mono">{_e(r.get("audit_id",""))}</td>'
            f"<td>{_e(r.get('entity_type',''))}</td>"
            f'<td class="mono">{_e(r.get("entity_id",""))}</td>'
            f'<td><span class="badge">{_e(r.get("action",""))}</span></td>'
            f"<td>{_e(r.get('actor',''))}</td>"
            f"<td>{_e(r.get('created_at',''))}</td></tr>"
            for r in records
        )
    else:
        rows = ('<tr><td colspan="6"><div class="empty-state">'
                '<p>No audit records to show.</p></div></td></tr>')

    f = (f"entity_id={_e(entity_id)}&entity_type={_e(entity_type)}&action={_e(action)}"
         f"&since={_e(since)}&until={_e(until)}")
    prev_link = (f'<a class="btn btn-ghost" href="/portal/audit?offset={max(0, offset - page_size)}&{f}">Previous</a>'
                 if offset > 0 else '<span class="btn btn-ghost disabled">Previous</span>')
    next_link = (f'<a class="btn btn-ghost" href="/portal/audit?offset={offset + page_size}&{f}">Next</a>'
                 if offset + len(records) < count else '<span class="btn btn-ghost disabled">Next</span>')
    pagination = f'<nav class="pagination" aria-label="Audit pagination">{prev_link}{next_link}</nav>'

    if summary:
        stats_items = "".join(
            f'<li><span class="badge">{_e(row["action"])}</span> <strong>{_e(row["count"])}</strong></li>'
            for row in summary
        )
        stats_html = (f'<section class="card"><h2>Statistics</h2><ul class="audit-mini">{stats_items}</ul></section>'
                      if stats_items else "")
    else:
        stats_html = ""

    body = (
        _navbar("audit")
        + "<h1>Audit Log</h1>"
        + _banner(message)
        + stats_html
        + '<form method="get" class="filter" action="/portal/audit">'
        + f'<input name="entity_id" value="{_e(entity_id)}" placeholder="Entity ID"/>'
        + f'<input name="entity_type" value="{_e(entity_type)}" placeholder="Entity type"/>'
        + f'<input name="action" value="{_e(action)}" placeholder="Action"/>'
        + f'<input name="since" value="{_e(since)}" placeholder="Since (ISO)"/>'
        + f'<input name="until" value="{_e(until)}" placeholder="Until (ISO)"/>'
        + '<button type="submit" class="btn btn-ghost">Filter</button></form>'
        + '<div class="table-wrapper"><table>'
        + '<thead><tr><th>ID</th><th>Entity Type</th><th>Entity ID</th><th>Action</th><th>Actor</th><th>Created</th></tr></thead>'
        + f"<tbody>{rows}</tbody></table></div>"
        + pagination
    )
    return _page(body)


def error_page(message: str) -> str:
    body = (
        _navbar()
        + "<h1>Something went wrong</h1>"
        + f'<div class="banner error" role="alert">{_e(_friendly_error(message))}</div>'
        + '<p class="hint">If this keeps happening, contact your administrator.</p>'
        + '<p><a class="btn" href="/portal/">Back to Dashboard</a> '
        + '<a class="btn btn-ghost" href="/portal/memories">Memories</a></p>'
    )
    return _page(body)


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------

def _forgotten_table(items) -> str:
    if not items:
        return '<div class="empty-state"><p>None.</p></div>'
    rows = ""
    for it in items:
        ty = it.get("entity_type")
        prefix = "memories" if ty == "memory" else "collections"
        eid = _e(it["entity_id"])
        title = _e(it.get("title") or it.get("subject") or it["entity_id"])
        ready = it.get("purge_eligible", False)
        days = it.get("days_remaining")
        restore = (
            f'<form method="post" action="/portal/{prefix}/{it["entity_id"]}/restore" '
            "onsubmit=\"return confirm('Restore this record to draft?')\">"
            '<button type="submit" class="btn btn-xsmall">Restore</button></form>'
        )
        if ready:
            badge = '<span class="badge active">Ready</span>'
            purge = (
                f'<form method="post" action="/portal/{prefix}/{it["entity_id"]}/purge" '
                "onsubmit=\"return confirm('Type PURGE to confirm. This permanently erases content.')\">"
                f'<input type="hidden" name="expected_version" value="{_e(it.get("version",""))}"/>'
                '<input name="confirmation" placeholder="PURGE" required/>'
                '<button type="submit" class="btn btn-xsmall btn-danger">Purge</button></form>'
            )
        else:
            badge = '<span class="badge draft">Pending</span>'
            purge = '<button type="button" class="btn btn-xsmall btn-danger" disabled>Purge</button>'
        days_text = f"{_e(str(days))} days" if days not in (None, 0) else ""
        rows += (
            "<tr>"
            f"<td>{_e(ty)}</td>"
            f"<td>{title}</td>"
            f"<td>{_e(it.get('forgotten_at',''))}</td>"
            f"<td>{_e(it.get('purge_eligible_date',''))}</td>"
            f"<td>{days_text}</td>"
            f"<td>{badge}</td>"
            f'<td class="section-controls">{restore}{purge}</td>'
            "</tr>"
        )
    return ('<div class="table-wrapper"><table>'
            '<thead><tr><th>Type</th><th>Title</th><th>Forgotten at</th><th>Purge eligible</th><th>Days left</th><th>Readiness</th><th>Actions</th></tr></thead>'
            + f"<tbody>{rows}</tbody></table></div>")


def _purged_table(stats) -> str:
    items = stats.get("purged_memories", []) + stats.get("purged_collections", [])
    if not items:
        return '<div class="empty-state"><p>No purged records.</p></div>'
    rows = "".join(
        "<tr>"
        f"<td>{_e(it.get('entity_type',''))}</td>"
        f"<td>{_e(it.get('title') or it.get('subject') or it.get('entity_id',''))}</td>"
        f"<td>{_e(it.get('version',''))}</td>"
        f"<td>{_e(it.get('purged_at',''))}</td>"
        f"<td>{_e(it.get('purged_by',''))}</td>"
        "</tr>"
        for it in items
    )
    return ('<div class="table-wrapper"><table>'
            '<thead><tr><th>Type</th><th>Title</th><th>Final version</th><th>Purged at</th><th>Purged by</th></tr></thead>'
            + f"<tbody>{rows}</tbody></table></div>")


def admin_page(stats, message="") -> str:
    forgotten_memories = stats.get("forgotten_memories", [])
    forgotten_collections = stats.get("forgotten_collections", [])
    all_forgotten = forgotten_memories + forgotten_collections
    ready = [it for it in all_forgotten if it.get("purge_eligible")]
    pending = [it for it in all_forgotten if not it.get("purge_eligible")]

    cards = (
        _metric("/portal/admin", stats.get("schema_version", ""), "Core schema version", "Current schema version.")
        + _metric("/portal/admin", stats.get("database_status", "unknown"), "Database status", "Core database health.")
        + _metric("/portal/admin", stats.get("tombstone_count", 0), "Tombstones", "Purged identity records.")
        + _metric("/portal/admin", stats.get("audit_count", 0), "Audit rows", "Append-only lifecycle audit rows.")
    )

    stats_items = "".join(
        f'<li><span class="badge">{_e(row["action"])}</span> <strong>{_e(row["count"])}</strong></li>'
        for row in stats.get("audit_stats", [])
    )
    audit_stats_html = ('<section class="card"><h2>Audit statistics (by action)</h2><ul class="audit-mini">'
                        + stats_items + "</ul></section>") if stats_items else ""

    body = (
        _navbar("admin")
        + "<h1>Administration</h1>"
        + _banner(message)
        + '<div class="stat-grid">' + cards + "</div>"
        + f'<p class="count">Forgotten memories: {_e(len(forgotten_memories))} &middot; Forgotten collections: {_e(len(forgotten_collections))} &middot; Ready to purge: {_e(len(ready))} &middot; Pending retention: {_e(len(pending))}</p>'
        + audit_stats_html
        + '<section class="card"><h2>Forgotten memories</h2>' + _forgotten_table(forgotten_memories) + "</section>"
        + '<section class="card"><h2>Forgotten collections</h2>' + _forgotten_table(forgotten_collections) + "</section>"
        + '<section class="card"><h2>Ready to purge</h2>' + _forgotten_table(ready) + "</section>"
        + '<section class="card"><h2>Pending retention</h2>' + _forgotten_table(pending) + "</section>"
        + '<section class="card"><h2>Purged memories and collections</h2>' + _purged_table(stats) + "</section>"
    )
    return _page(body)
"""Server-rendered HTML pages for the Core Portal.

All dynamic content is XSS-escaped via ``_e``. Nothing here ever emits
credentials, audit secrets, database paths, or sensitive configuration.
This module only renders markup -- it never accesses SQLite or repositories.
"""

import html as _html
import re
from pathlib import Path

from samjon_memory.constants import DEFAULT_PAGE_SIZE


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _e(text) -> str:
    return _html.escape(str(text) if text is not None else "")


# ---- Media rendering helpers ------------------------------------------------
# Only media metadata (ids + validated alt/caption) is rendered - never binary
# bytes. Source URLs point at Portal-authenticated media routes.

def _media_original_url(media_id: str) -> str:
    return f"/portal/media/{media_id}/original"


def _media_thumb_url(media_id: str) -> str:
    return f"/portal/media/{media_id}/thumb"


# ---- Read-only media view models --------------------------------------------
# Presentation-ready data for the Portal. Only media_id + authenticated media
# URLs are exposed; never relative_path, thumbnail_path, or filesystem paths.

def _media_vm(m) -> dict:
    return {
        "media_id": m["media_id"],
        "thumb_url": _media_thumb_url(m["media_id"]),
        "original_url": _media_original_url(m["media_id"]),
        "alt": m.get("alt_text") or "",
        "caption": m.get("caption") or "",
        "is_cover": bool(m.get("is_cover")),
    }


def _orientation_class(width, height) -> str:
    """Return a media-orientation CSS class from numeric width/height, or ''.

    Classification: width < height -> portrait, > -> landscape, == -> square.
    Returns '' when either dimension is missing/non-numeric so callers fall
    back to the safe object-fit default (contain) instead of cropping blindly.
    """
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return ""
    if w <= 0 or h <= 0:
        return ""
    if w < h:
        return "media-orientation-portrait"
    if w > h:
        return "media-orientation-landscape"
    return "media-orientation-square"


def build_gallery_vm(media) -> list:
    """Ordered gallery view model (display_order preserved from CoreService)."""
    return [_media_vm(m) for m in (media or [])]


def build_cover_vm(media):
    """Cover view model, falling back to the first illustration when no cover set."""
    items = build_gallery_vm(media)
    if not items:
        return None
    for it in items:
        if it["is_cover"]:
            return it
    return items[0]


# ---- Library subject-domain catalog (presentation constant) ---------------
# Canonical subject domain = the prefix before ':'. Category cards group many
# individual subjects under one domain so new subject domains remain possible.

SUBJECT_CATEGORIES = [
    {"key": "people", "name": "People", "hint": "บุคคลและความชอบ", "domains": ["person"], "cover": "people.webp", "cover_alt": "People category", "cover_position": "center"},
    {"key": "household", "name": "Household", "hint": "ข้อมูลที่ใช้ร่วมกันในบ้าน", "domains": ["household"], "cover": "household.webp", "cover_alt": "Household category", "cover_position": "center"},
    {"key": "plants", "name": "Plants", "hint": "ต้นไม้และการดูแล", "domains": ["plant"], "cover": "plants.webp", "cover_alt": "Plants category", "cover_position": "center"},
    {"key": "pets", "name": "Pets", "hint": "สัตว์เลี้ยงและการดูแล", "domains": ["pet"], "cover": "pets.webp", "cover_alt": "Pets category", "cover_position": "center"},
    {"key": "devices", "name": "Devices", "hint": "อุปกรณ์และเครื่องใช้", "domains": ["device"], "cover": "devices.webp", "cover_alt": "Devices category", "cover_position": "center"},
    {"key": "equipment", "name": "Equipment", "hint": "เครื่องมือและอุปกรณ์", "domains": ["equipment"], "cover": "equipment.webp", "cover_alt": "Equipment category", "cover_position": "center"},
    {"key": "locations", "name": "Locations", "hint": "ห้องและสถานที่", "domains": ["location"], "cover": "locations.webp", "cover_alt": "Locations category", "cover_position": "center"},
    {"key": "music", "name": "Music", "hint": "เพลงและความชอบด้านเสียง", "domains": ["music", "playlist"], "cover": "music.webp", "cover_alt": "Music category", "cover_position": "center"},
    {"key": "routines", "name": "Routines", "hint": "กิจวัตรและขั้นตอน", "domains": ["routine", "activity"], "cover": "routines.webp", "cover_alt": "Routines category", "cover_position": "center"},
    {"key": "inventory", "name": "Inventory", "hint": "สิ่งของและตำแหน่งจัดเก็บ", "domains": ["inventory", "item", "supply"], "cover": "inventory.webp", "cover_alt": "Inventory category", "cover_position": "center"},
    {"key": "systems", "name": "Systems", "hint": "ระบบ บริการ และ Automation", "domains": ["system", "service", "integration", "automation"], "cover": "systems.webp", "cover_alt": "Systems category", "cover_position": "center"},
    {"key": "other", "name": "Other", "hint": "ความรู้อื่น ๆ", "domains": [], "cover": "other.webp", "cover_alt": "Other category", "cover_position": "center"},
]

_OTHER_CATEGORY = next(c for c in SUBJECT_CATEGORIES if c["key"] == "other")
_CATEGORY_BY_DOMAIN = {}
for _c in SUBJECT_CATEGORIES:
    for _d in _c["domains"]:
        _CATEGORY_BY_DOMAIN[_d] = _c


def _subject_domain(subject) -> str:
    s = str(subject or "").strip()
    if ":" in s:
        head = s.split(":", 1)[0].strip()
        return head or s
    return s


def domain_is_catalogued(domain: str) -> bool:
    return domain in _CATEGORY_BY_DOMAIN


def category_by_key(key: str):
    for c in SUBJECT_CATEGORIES:
        if c["key"] == key:
            return c
    return None


def _category_for_domain(domain: str):
    return _CATEGORY_BY_DOMAIN.get(domain, _OTHER_CATEGORY)


def _category_for_subject(subject):
    return _category_for_domain(_subject_domain(subject))


def category_model(active) -> list:
    """Build the presentation category catalog with active counts.

    ``active`` = {"collections": [...], "memories": [...]} (bounded, from
    CoreService.library_active). Counting is pure read-only presentation.
    """
    cats = {c["key"]: dict(c, memories=0, collections=0) for c in SUBJECT_CATEGORIES}

    def _bucket(subject):
        return _category_for_subject(subject)["key"]

    for m in active.get("memories", []):
        cats[_bucket(m.get("subject"))]["memories"] += 1
    for c in active.get("collections", []):
        cats[_bucket(c.get("subject"))]["collections"] += 1
    return [cats[c["key"]] for c in SUBJECT_CATEGORIES]


def _category_matches(category, subject) -> bool:
    doms = category.get("domains") or []
    if doms:
        return _subject_domain(subject) in doms
    # Other: any domain not covered by a named category.
    return not domain_is_catalogued(_subject_domain(subject))


def subject_domain(subject) -> str:
    """Public: canonical subject domain = the prefix before ':'."""
    return _subject_domain(subject)


def category_matches(category, subject) -> bool:
    """Public: does an entity's subject belong to the given category?"""
    return _category_matches(category, subject)


def cover_thumb(media) -> str:
    """Return a cover thumbnail or a placeholder for a media list."""
    if not media:
        return '<div class="media-cover placeholder" aria-hidden="true">No cover</div>'
    cover = next((m for m in media if m.get("is_cover")), media[0])
    alt = _e(cover.get("alt_text") or cover.get("caption") or "Cover image")
    return f'<img class="media-cover" src="{_media_thumb_url(cover["media_id"])}" alt="{alt}">'


def _media_section(media, entity_type: str = "", entity_id: str = "",
                   admin: bool = False, back_target: str = "") -> str:
    """Render a media gallery. Read-only when ``admin`` is False.

    ``back_target`` (optional) is an internal Portal path embedded as a hidden
    ``back`` field on every admin mutation form, so inline Section media controls
    redirect back to the Collection detail page after a mutation.
    """
    media = media or []
    hidden_back = ('<input type="hidden" name="back" value="' + _e(back_target) + '">') \
        if (admin and back_target) else ""
    if not media:
        items = '<div class="empty-state"><p>No images yet.</p></div>'
    else:
        cards = []
        for idx, m in enumerate(media):
            mid = m["media_id"]
            alt = _e(m.get("alt_text") or "")
            cap = _e(m.get("caption") or "")
            cover_badge = '<span class="badge active">Cover</span>' if m.get("is_cover") else ""
            caption_bits = []
            if cap:
                caption_bits.append('<span class="cap">' + cap + "</span>")
            if alt:
                caption_bits.append('<span class="alt">[alt: ' + alt + " ]</span>")
            img = ('<img src="' + _media_thumb_url(mid) + '" alt="' + alt + '">')
            item = '<figure class="media-item">' + img + "".join(caption_bits) + cover_badge
            if admin:
                disabled = ' disabled' if m.get("is_cover") else ""
                left_dis = ' disabled' if idx == 0 else ""
                right_dis = ' disabled' if idx == len(media) - 1 else ""
                item += (
                    '<figcaption class="media-controls">'
                    '<form method="post" action="/portal/media/' + mid + '/cover">'
                    + hidden_back
                    + '<button type="submit" class="btn btn-xsmall"' + disabled + '>Cover</button></form>'
                    '<form method="post" action="/portal/media/' + mid + '/move-left">'
                    + hidden_back
                    + '<button type="submit" class="btn btn-xsmall"' + left_dis + '>&larr;</button></form>'
                    '<form method="post" action="/portal/media/' + mid + '/move-right">'
                    + hidden_back
                    + '<button type="submit" class="btn btn-xsmall"' + right_dis + '>&rarr;</button></form>'
                    '<form method="post" action="/portal/media/' + mid + '/remove" '
                    "onsubmit=\"return window.confirm('Remove this image?')\">"
                    + hidden_back
                    + '<button type="submit" class="btn btn-xsmall btn-danger">Remove</button></form>'
                    '<details class="media-edit"><summary>Edit</summary>'
                    '<form method="post" action="/portal/media/' + mid + '/metadata">'
                    + hidden_back
                    + '<label>Alt text<input name="alt_text" value="' + alt + '" maxlength="500" title="Short image description shown when the image cannot load (accessibility)."></label>'
                    '<label>Caption<input name="caption" value="' + cap + '" maxlength="2000" title="Optional caption displayed under the image."></label>'
                    '<button type="submit" class="btn btn-xsmall">Save</button></form>'
                    '<form method="post" action="/portal/media/' + mid + '/replace" '
                    'enctype="multipart/form-data">'
                    + hidden_back
                    + '<label>Replace<input type="file" name="file" '
                    'accept="image/jpeg,image/png,image/webp"></label>'
                    '<button type="submit" class="btn btn-xsmall">Replace</button></form>'
                    "</details></figcaption>"
                )
            cards.append(item + "</figure>")
        items = '<div class="media-gallery">' + "".join(cards) + "</div>"
    upload = ""
    if admin:
        upload = (
            '<form method="post" action="/portal/media/upload" '
            'enctype="multipart/form-data" class="media-upload">'
            + hidden_back
            + '<input type="hidden" name="entity_type" value="' + _e(entity_type) + '">'
            '<input type="hidden" name="entity_id" value="' + _e(entity_id) + '">'
            '<input type="file" name="file" accept="image/jpeg,image/png,image/webp" required>'
            '<input name="alt_text" placeholder="Alt text" maxlength="500" title="Short image description for accessibility.">'
            '<input name="caption" placeholder="Caption" maxlength="2000" title="Optional caption shown under the image.">'
            '<button type="submit" class="btn">Upload image</button></form>'
        )
    return '<section class="card media-section"><h2>Images</h2>' + upload + items + "</section>"


def _section_media_manager(section, cid) -> str:
    """Expandable inline Section media manager for the Collection Admin detail."""
    mid = section["memory_id"]
    media = section.get("media") or []
    back = "/portal/collections/" + _e(cid) + "#section-" + _e(mid)
    return (
        '<details class="section-media" data-section-media="1">'
        '<summary>จัดการรูปภาพของบท</summary>'
        + _media_section(media, "memory", mid, admin=True, back_target=back)
        + '<p><a class="btn btn-xsmall btn-ghost" href="/portal/memories/' + _e(mid)
        + '">Open full Section page</a></p>'
        + "</details>"
    )


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
    "resolver_rebuilt": "Rebuild complete. The search index was updated.",
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


def _brand_mark() -> str:
    """Drawn SVG book-spine mark (geometric, decorative, hidden from AT)."""
    return ('<svg class="nav-brand-mark" width="20" height="20" viewBox="0 0 20 20" '
            'aria-hidden="true" focusable="false">'
            '<rect x="3" y="3" width="14" height="14" rx="2" fill="currentColor"/>'
            '<line x1="6" y1="6" x2="6" y2="15" stroke="currentColor" stroke-opacity="0.7" stroke-width="1.6"/>'
            '<line x1="10" y1="6" x2="10" y2="15" stroke="currentColor" stroke-opacity="0.7" stroke-width="1.6"/>'
            '<line x1="14" y1="6" x2="14" y2="15" stroke="currentColor" stroke-opacity="0.7" stroke-width="1.6"/>'
            '</svg>')


def _navbar(active: str = "") -> str:
    user_links = [
        ("library", "/portal/", "Library"),
        ("memories", "/portal/memories", "Memories"),
        ("collections", "/portal/collections", "Collections"),
        ("status", "/portal/status", "Status"),
    ]
    admin_links = [
        ("admin", "/portal/admin", "Administration"),
        ("audit", "/portal/audit", "Audit"),
        ("resolver", "/portal/resolver/", "Resolver Debug"),
    ]

    def _item(key, href, label):
        cls = "nav" + (" active" if key == active else "")
        current = ' aria-current="page"' if key == active else ""
        return f'<a class="{cls}" href="{_e(href)}"{current}>{_e(label)}</a>'

    user_items = "".join(_item(k, h, l) for k, h, l in user_links)
    admin_items = "".join(_item(k, h, l) for k, h, l in admin_links)
    return ('<header class="site-header">'
            f'<nav class="navbar" aria-label="Primary">'
            f'<a class="nav-brand" href="/portal/">{_brand_mark()}<span>Samjon Memory</span></a>'
            f'<div class="nav-user">{user_items}</div>'
            '<span class="nav-sep" aria-hidden="true">|</span>'
            f'<div class="nav-admin">{admin_items}</div>'
            '</nav></header>')


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


def _readonly_field(label, value, helper="") -> str:
    helper_html = f'<span class="hint">{_e(helper)}</span>' if helper else ""
    return ('<div class="field"><span class="field-label">' + _e(label) + '</span>'
            + f'<p class="readonly-value">{_e(value or "")}</p>'
            + helper_html + '</div>')


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
        _navbar("status")
        + "<h1>System Status</h1>"
        + '<p class="section-hint">สถานะ Core, Library และดัชนีการค้นหา</p>'
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
            f'<td><a class="cell-primary-link" href="/portal/memories/{_e(m["memory_id"])}">{_e(m.get("title") or m.get("subject") or "")}</a></td>'
            f'<td class="cell-subject" title="{_e(m.get("subject") or "")}">{_e(m.get("subject") or "")}</td>'
            f"<td>{_status_badge(m.get('status',''))}</td>"
            f"<td>{_e(m.get('memory_type',''))}</td>"
            f"<td>{_e(m.get('scope',''))}</td>"
            f"<td>{_e(m.get('version',''))}</td></tr>"
            for m in memories
        )
    else:
        rows = ('<tr><td colspan="7"><div class="empty-state">'
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
        + '<thead><tr><th>ID</th><th>Title</th><th>Subject</th><th>Status</th><th>Type</th><th>Scope</th><th>Version</th></tr></thead>'
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


def memory_detail(memory, message="", media=None) -> str:
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
    gallery = _media_section(media, "memory", memory["memory_id"], admin=True)
    body = (
        _navbar("memories")
        + "<h1>Memory</h1>"
        + _banner(message)
        + f'<p class="subtitle">{mid} {_status_badge(memory.get("status",""))}</p>'
        + f'<dl class="detail">{fields}</dl>'
        + gallery
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
    is_section = bool(memory.get("collection_id"))
    if is_section:
        subject_block = _readonly_field(
            "Subject", memory.get("subject", ""),
            "Inherited from the Collection; cannot be changed.")
        scope_block = _readonly_field(
            "Scope", memory.get("scope", ""),
            "Inherited from the Collection; cannot be changed.")
    else:
        subject_block = _text_field("subject", "Subject",
                                    prefill.get("subject", memory.get("subject", "")), required=True, maxlen=500)
        scope_block = _text_field("scope", "Scope",
                                  prefill.get("scope", memory.get("scope", "household")), maxlen=100)
    fields = (
        subject_block
        + _text_field("memory_type", "Type",
                      prefill.get("memory_type", memory.get("memory_type", "fact")), maxlen=100)
        + scope_block
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
            f'<td>{_e(c.get("title") or c.get("subject") or "")}</td>'
            f'<td class="cell-subject" title="{_e(c.get("subject") or "")}">{_e(c.get("subject") or "")}</td>'
            f"<td>{_e(c.get('collection_type',''))}</td>"
            f"<td>{_status_badge(c.get('status',''))}</td>"
            f"<td>{_e(c.get('version',''))}</td></tr>"
            for c in collections
        )
    else:
        rows = ('<tr><td colspan="6"><div class="empty-state">'
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
        + '<thead><tr><th>ID</th><th>Title</th><th>Subject</th><th>Type</th><th>Status</th><th>Version</th></tr></thead>'
        + f"<tbody>{rows}</tbody></table></div>"
    )
    return _page(body)


def _issues_html(issues):
    items = "".join(f'<li class="issue">{_e(i)}</li>' for i in issues)
    return f'<div class="validation-card"><h3>What to fix</h3><ul class="issue-list">{items}</ul></div>'


def _assembled_preview(memories):
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda x: (x.get("sequence_number") is None, x.get("sequence_number") or 0))
    blocks = "".join(
        f'<article class="preview-block"><h3>{_e(m.get("title") or m.get("subject") or "")}</h3>'
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


def _reopen_banner() -> str:
    return ('<div class="banner warning" role="status">'
            'This Collection was reopened for editing. Validate it again, then Activate to republish.</div>')


def collection_detail(collection, memories, validation, message="", reopened=False, media=None) -> str:
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
            raw_mid = m["memory_id"]
            mid = _e(raw_mid)
            label = _e(m.get("title") or m.get("subject") or "")
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
                    f'<button type="submit" class="btn btn-xsmall"{up_disabled} aria-label="Move {label} up" title="Move up">Up</button></form>'
                    f'<form method="post" action="/portal/collections/{cid}/memories/{mid}/move-down">'
                    f'<button type="submit" class="btn btn-xsmall"{down_disabled} aria-label="Move {label} down" title="Move down">Down</button></form>'
                    f'<form method="post" action="/portal/memories/{mid}/forget" '
                    "onsubmit=\"return confirm('Forget this section? This cannot be undone.')\">"
                    f'<button type="submit" class="btn btn-xsmall btn-danger">Forget</button></form>'
                )
            main_row = (
                f"<tr><td>{seq}</td>"
                f"<td>{label} <span class=\"mono\">{mid}</span></td>"
                f"<td>{_status_badge(m.get('status',''))}</td>"
                f"<td>{_e(m.get('version',''))}</td>"
                f'<td class="section-controls">{controls}</td></tr>'
            )
            rows.append(main_row)
            if "media" in m:
                rows.append(
                    f'<tr id="section-{_e(raw_mid)}" class="section-media-row">'
                    f'<td colspan="5">{_section_media_manager(m, collection["collection_id"])}</td></tr>'
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
        + (_reopen_banner() if (reopened and collection.get("status") == "draft") else "")
        + f'<p class="subtitle">{cid} {_status_badge(collection.get("status",""))}</p>'
        + f'<dl class="detail">{fields}</dl>'
        + _media_section(media, "collection", collection["collection_id"], admin=True)
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
# Search (user-facing)
# ---------------------------------------------------------------------------

def _research_nav_removed():
    pass  # unified navigation is provided by _navbar


def _technical_details(entry) -> str:
    entity_id = entry.get("entity_id") or entry.get("memory_id") or entry.get("collection_id")
    rows = [
        ("ID", entity_id),
        ("Score", entry.get("score")),
        ("Match reasons", ", ".join(entry.get("match_reasons") or [])),
        ("Freshness", entry.get("projection_freshness")),
        ("Projected version", entry.get("projected_core_version") or entry.get("core_version")),
        ("Checksum", entry.get("checksum")),
    ]
    inner = "".join(
        f"<dt>{_e(label)}</dt><dd class=\"mono\">{_e(value)}</dd>"
        for label, value in rows if value not in (None, "")
    )
    return ('<details class="technical result-action technical-action">'
            '<summary>รายละเอียดทางเทคนิค</summary>'
            f"<dl>{inner}</dl></details>")


def _selected_sections(entry) -> str:
    secs = entry.get("selected_sections") or []
    if not secs:
        return ""
    items = "".join(
        f'<li><a href="/portal/memories/{_e(s.get("memory_id"))}">'
        f'{_e(s.get("title") or s.get("section_path") or s.get("memory_id"))}</a></li>'
        for s in secs
    )
    return f'<ul class="selected-sections">{items}</ul>'


_RESULT_LABELS = {
    "memory": "บันทึกความรู้",
    "collection": "ชุดความรู้",
    "section": "บทภายในชุด",
}


def _empty_cover(seed_text="") -> str:
    """Decorative 3:4 placeholder cover: drawn book mark + Thai label.

    aria-hidden (purely decorative). Exposes no filesystem path or binary data.
    The first non-space character of the title is shown subtly.
    """
    seed = (seed_text or "").strip()
    initial = _e(seed[:1]) if seed else "?"
    return ('<div class="lib-cover lib-cover-placeholder" aria-hidden="true">'
            '<span class="lib-cover-glyph" aria-hidden="true">'
            '<svg class="lib-cover-book" width="34" height="40" viewBox="0 0 34 40" focusable="false">'
            '<rect x="4" y="4" width="26" height="32" rx="3" fill="none" '
            'stroke="currentColor" stroke-width="1.5"/>'
            '<line x1="11" y1="14" x2="11" y2="30" stroke="currentColor" stroke-width="1.5"/>'
            '<line x1="16" y1="14" x2="16" y2="30" stroke="currentColor" stroke-width="1.5"/>'
            '<line x1="21" y1="14" x2="21" y2="30" stroke="currentColor" stroke-width="1.5"/>'
            '</svg></span>'
            + f'<span class="lib-cover-initial">{initial}</span>'
            + '<span class="lib-cover-none">ยังไม่มีภาพปก</span>'
            + "</div>")


def _card_cover(entry) -> str:
    """Cover thumbnail (authenticated URL) or a 3:4 placeholder."""
    thumb = entry.get("cover_thumb_url")
    title = (entry.get("title") or entry.get("subject")
             or entry.get("collection_title") or "")
    alt = _e(entry.get("cover_alt") or title)
    if thumb:
        orient = _orientation_class(entry.get("cover_width"), entry.get("cover_height"))
        wrapper = ("lib-cover media-frame media-frame-cover"
                   + (" " + orient if orient else ""))
        return (f'<div class="{wrapper}">'
                + f'<img class="lib-cover-img" src="{_e(thumb)}" alt="{alt}" loading="lazy">'
                + "</div>")
    return _empty_cover(title)


def _result_card(entry, kind) -> str:
    kind_label = _RESULT_LABELS.get(kind, kind)
    primary = ""
    secondary = ""
    count_html = ""
    if kind == "section":
        ctitle = entry.get("collection_title") or ""
        title = (f'{_e(ctitle)} › {_e(entry.get("title") or entry.get("subject") or "")}'
                 if ctitle else _e(entry.get("title") or entry.get("subject") or ""))
        primary = (f'<a class="btn result-action result-action-primary result-open" '
                   f'href="/portal/library/memories/{_e(entry.get("memory_id"))}">อ่านบทนี้</a>')
        secondary = (f'<a class="btn btn-ghost result-action result-action-secondary result-open" '
                     f'href="/portal/library/collections/{_e(entry.get("collection_id"))}">เปิดทั้งชุด</a>')
    elif kind == "collection":
        title = _e(entry.get("title") or entry.get("subject") or "")
        n = len(entry.get("selected_sections") or [])
        if n:
            count_html = f'<p class="lib-chapter-count">จำนวนบท {_e(n)}</p>'
        primary = (f'<a class="btn result-action result-action-primary result-open" '
                   f'href="/portal/library/collections/{_e(entry.get("collection_id"))}">เปิดชุดความรู้</a>')
    else:
        title = _e(entry.get("title") or entry.get("subject") or "")
        primary = (f'<a class="btn result-action result-action-primary result-open" '
                   f'href="/portal/library/memories/{_e(entry.get("memory_id"))}">อ่านบันทึก</a>')
    excerpt = _e(entry.get("excerpt") or "")
    excerpt_html = f'<p class="result-excerpt lib-excerpt">{excerpt}</p>' if excerpt else ""
    selected = (_selected_sections(entry)
                if kind == "collection" and entry.get("selected_sections") else "")
    status_html = _status_badge(entry.get("status")) if entry.get("status") else ""
    actions = f'<div class="result-actions">{primary}{secondary}{_technical_details(entry)}</div>'
    return (
        '<article class="lib-card">'
        + _card_cover(entry)
        + '<div class="lib-body">'
        + f'<span class="result-kind">{_e(kind_label)}</span>'
        + f'<h3 class="lib-title">{title}</h3>'
        + status_html
        + excerpt_html
        + count_html
        + selected
        + "</div>"
        + actions
        + "</article>"
    )


def _result_group(label, items, kind) -> str:
    cards = "".join(_result_card(it, kind) for it in items)
    return ('<section class="result-group"><h2>' + _e(label) + "</h2>"
            + f'<div class="result-list">{cards}</div></section>')


def _no_results_html(q, suggestion) -> str:
    return ('<div class="empty-state no-results">'
            + f"<p>ไม่พบผลลัพธ์สำหรับ \u201c{_e(q)}\u201d.</p>"
            + "<p>ลองพิมพ์คำอื่นหรือใช้คำค้นที่สั้นกว่า</p>"
            + (f'<p class="hint">คำแนะนำ: {_e(suggestion)}</p>' if suggestion else "")
            + "</div>")


def search_page(q="", memories=None, collections=None, sections=None,
                stale=False, error="", total=0, suggestion="") -> str:
    memories = memories or []
    collections = collections or []
    sections = sections or []
    nav = _navbar("library")
    hero = (
        '<section class="search-hero"><h1>ค้นหาในคลังความรู้</h1>'
        '<p class="search-hint">พิมพ์คำหรือหัวข้อที่ต้องการค้นหา</p>'
        '<form method="post" action="/portal/search" class="search-form">'
        '<input type="hidden" name="target" value="auto"/>'
        f'<input class="search-input" id="lib-search-q" name="q" value="{_e(q)}" aria-label="Search the knowledge library" '
        'placeholder="เช่น วิธีรดน้ำต้นไม้, การดูแลสวน" autofocus/>'
        '<button type="submit" class="btn search-btn">ค้นหา</button>'
        "</form>"
        '<p class="search-target">ค้นหาทั้งบันทึกและชุดความรู้</p>'
        "</section>"
    )
    stale_html = ('<div class="banner warning" role="status">'
                  "ผลการค้นหาอาจล้าสมัย (ยังไม่ได้สร้างดัชนีใหม่) "
                  "เปิดดูรายการเพื่อดูเวอร์ชันปัจจุบัน หรือขอให้ผู้ดูแลสร้างดัชนีใหม่"
                  if stale else "")
    error_html = f'<div class="banner error" role="alert">{_e(error)}</div>' if error else ""
    if not q:
        return _page(nav + hero + '<div class="empty-state"><p>พิมพ์คำค้นด้านบนเพื่อเริ่มค้นหา</p></div>')
    if total == 0:
        return _page(nav + hero + stale_html + error_html + _no_results_html(q, suggestion))
    groups = ""
    if memories:
        groups += _result_group("บันทึกความรู้", memories, "memory")
    if collections:
        groups += _result_group("ชุดความรู้", collections, "collection")
    if sections:
        groups += _result_group("บทภายในชุด", sections, "section")
    return _page(nav + hero + stale_html + error_html
                 + f'<p class="count">พบ {_e(total)} รายการ</p>' + groups)


# ---------------------------------------------------------------------------
# Library Reader (read-only)
# ---------------------------------------------------------------------------

def _library_hero(q="") -> str:
    return (
        '<section class="search-hero"><h1>Search the knowledge library</h1>'
        '<p class="search-hint">ค้นหาความรู้ที่บันทึกไว้ในบ้าน</p>'
        '<form method="post" action="/portal/search" class="search-form">'
        '<input type="hidden" name="target" value="auto"/>'
        f'<input class="search-input" id="lib-search-q" name="q" value="{_e(q)}" aria-label="Search the knowledge library" '
        'placeholder="เช่น วิธีรดน้ำต้นไม้, การดูแลสวน" autofocus/>'
        '<button type="submit" class="btn search-btn">ค้นหา</button>'
        "</form>"
        '<p class="search-target">ค้นหาทั้งบันทึกความรู้ ชุดความรู้ และบทภายในชุด</p>'
        "</section>"
    )


def _cat_counts(cat) -> str:
    # "\u0e0a\u0e38\u0e14" = collection count label, "\u0e1b\u0e31\u0e19\u0e17\u0e36\u0e01" = memory count label
    return (f'{_e(cat.get("collections", 0))} \u0e0a\u0e38\u0e14 \xb7 '
            f'{_e(cat.get("memories", 0))} \u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01')


# ---------------------------------------------------------------------------
# Configurable category covers (presentation-only).
#
# Category cards resolve a representative cover via a safe fallback chain:
#   1. an explicitly configured category cover (static asset, if present)
#   2. an active Collection cover (attached to the category by the router)
#   3. an active standalone Memory cover (attached by the router)
#   4. the standard Library placeholder
#
# Configured covers are static assets under ``portal/static/category-covers/``.
# They are NOT stored in Core, Resolver, or the Media metadata table, and
# categories are presentation concepts -- no Category entity is created.
# ---------------------------------------------------------------------------

CATEGORY_COVER_SUBDIR = "category-covers"


def _category_covers_dir() -> Path:
    """Directory holding configured category-cover assets (override in tests)."""
    return Path(__file__).resolve().parent / "static" / CATEGORY_COVER_SUBDIR


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _safe_cover_name(name) -> str:
    """Return the configured filename only when it is a safe basename (no path)."""
    if not name or not isinstance(name, str):
        return ""
    name = name.strip()
    if "/" in name or "\\" in name or name in (".", ".."):
        return ""
    if not _SAFE_NAME_RE.fullmatch(name):
        return ""
    return name


_ALLOWED_COVER_EXTS = {".webp", ".jpg", ".jpeg", ".png"}
"""Enabled configured-cover image extensions (case-insensitive).

SVG/other formats, remote URLs, absolute paths, traversal, and base64 are all
rejected earlier by ``_safe_cover_name`` + this allowlist; assets still come only
from ``portal/static/category-covers/``.
"""


def _safe_cover_position(position: str) -> str:
    allowed = {"center", "top", "bottom", "left", "right",
               "top left", "top right", "bottom left", "bottom right"}
    p = (position or "center").strip().lower()
    return p if p in allowed else "center"


def _configured_category_cover(cat) -> dict:
    """Configured category-cover view model, or {} when none is active.

    A configured cover is active only when it names a safe basename whose asset
    exists in the category-covers directory; otherwise the chain falls through.
    """
    raw = cat.get("cover") or ""
    safe = _safe_cover_name(raw)
    if not safe:
        return {}
    # Case-insensitive extension allowlist: .webp/.jpg/.jpeg/.png only.
    if not any(safe.lower().endswith(ext) for ext in _ALLOWED_COVER_EXTS):
        return {}
    if not (_category_covers_dir() / safe).is_file():
        return {}
    alt = cat.get("cover_alt") or ((cat.get("name") or "Category") + " category")
    return {
        "url": f"/portal/static/{CATEGORY_COVER_SUBDIR}/{safe}",
        "alt": alt,
        "position": _safe_cover_position(cat.get("cover_position")),
    }


def _category_cover(cat) -> str:
    """Render the best category cover for the fallback chain (module note).

    ``entity_cover`` is already collection-preferred by the router: only set
    when the category has no active configured cover.
    """
    conf = _configured_category_cover(cat)
    if conf:
        style = (f' style="object-position: {_e(conf["position"])};"'
                 if conf["position"] != "center" else "")
        # Configured covers are static assets without stored width/height, so
        # they default to object-fit: contain (never cropped to a slim strip).
        return ('<div class="lib-cat-cover media-frame media-frame-cover media-fit-contain">'
                '<img class="lib-cat-cover-img" '
                f'src="{_e(conf["url"])}" alt="{_e(conf["alt"])}" loading="lazy"{style}></div>')
    cov = cat.get("entity_cover")
    if cov and cov.get("media_id"):
        alt = _e(cov.get("alt_text") or cov.get("caption") or "")
        orient = _orientation_class(cov.get("width"), cov.get("height"))
        wrapper = ("lib-cat-cover media-frame media-frame-cover"
                   + (" " + orient if orient else ""))
        return (f'<div class="{wrapper}"><img class="lib-cat-cover-img" '
                f'src="{_media_thumb_url(cov["media_id"])}" alt="{alt}" loading="lazy"></div>')
    return _empty_cover(cat.get("name") or "")


def _category_card(cat) -> str:
    """Thin wrapper: render the shared category-card component (single impl)."""
    from samjon_memory.portal import templating, viewmodels
    return templating.render_partial(
        "components/category_card.html", cat=viewmodels.category_card_vm(cat))




def _category_section(categories) -> str:
    cards = "".join(_category_card(c) for c in categories)
    return ('<section class="lib-section"><h2>Browse by Subject</h2>'
            '<p class="section-hint">เรียกดูตามหมวดหมู่ของหัวข้อ</p>'
            f'<div class="lib-cat-grid">{cards}</div></section>')


def _entity_cover(entity) -> str:
    cov = entity.get("cover")
    if cov and cov.get("media_id"):
        alt = _e(cov.get("alt_text") or cov.get("caption") or "")
        orient = _orientation_class(cov.get("width"), cov.get("height"))
        wrapper = ("lib-cover media-frame media-frame-cover"
                   + (" " + orient if orient else ""))
        return (f'<div class="{wrapper}"><img class="lib-cover-img" '
                f'src="{_media_thumb_url(cov["media_id"])}" alt="{alt}" loading="lazy"></div>')
    title = entity.get("title") or entity.get("subject") or ""
    initial = _e(title[:1]) if title else "?"
    return ('<div class="lib-cover lib-cover-placeholder" aria-hidden="true">'
            f'<span class="lib-cover-initial">{initial}</span>'
            '<span class="lib-cover-none">ยังไม่มีภาพปก</span></div>')


def library_card(entity, entity_type) -> str:
    """Cover-first library card. entity_type in ('memory','collection')."""
    if entity_type == "collection":
        label = "ชุดความรู้"
        title = entity.get("title") or entity.get("subject") or ""
        excerpt = (entity.get("summary") or "")[:160]
        link = f"/portal/library/collections/{_e(entity.get('collection_id'))}"
        button = "เปิดชุดความรู้"
    else:
        label = "บันทึกความรู้"
        title = entity.get("title") or entity.get("subject") or ""
        excerpt = (entity.get("raw_content") or "")[:160]
        link = f"/portal/library/memories/{_e(entity.get('memory_id'))}"
        button = "อ่านบันทึก"
    cat_name = _e(_category_for_subject(entity.get("subject")).get("name") or "")
    return (
        '<article class="lib-card">'
        + _entity_cover(entity)
        + '<div class="lib-body">'
        + f'<span class="result-kind">{_e(label)}</span>'
        + f'<h3 class="lib-title">{_e(title)}</h3>'
        + f'<span class="lib-subject">{cat_name}</span>'
        + (f'<p class="result-excerpt lib-excerpt">{_e(excerpt)}</p>' if excerpt else "")
        + "</div>"
        + f'<div class="lib-actions"><a class="btn" href="{link}">{_e(button)}</a></div>'
        + "</article>"
    )


def _discover_section(entities) -> str:
    grid = "".join(library_card(e, e.get("_type", "memory")) for e in entities)
    if not grid:
        grid = '<div class="empty-state"><p class="section-hint">ลองเปิดดู</p></div>'
    return ('<section class="lib-section"><h2>Discover</h2>'
            '<p class="section-hint">ลองเปิดดู</p>'
            f'<div class="lib-card-grid">{grid}</div></section>')


def _recent_section(entities) -> str:
    grid = "".join(library_card(e, e.get("_type", "memory")) for e in entities)
    if not grid:
        grid = '<div class="empty-state"><p class="section-hint">รายการที่อัปเดตล่าสุด</p></div>'
    return ('<section class="lib-section"><h2>Recently Updated</h2>'
            '<p class="section-hint">รายการที่อัปเดตล่าสุด</p>'
            f'<div class="lib-card-grid">{grid}</div></section>')


def library_home(categories, discover, recent, q="") -> str:
    nav = _navbar("library")
    body = (nav + _library_hero(q) + _category_section(categories)
            + _discover_section(discover) + _recent_section(recent))
    return _page(body)


def _pager(offset, page_size, total, base_url) -> str:
    if total <= page_size:
        return ""
    prev = (f'<a class="btn btn-xsmall btn-ghost" href="{_e(base_url)}&offset={offset - page_size}">'
            "&larr; ก่อนหน้า</a>") if offset > 0 else ""
    nxt = (f'<a class="btn btn-xsmall btn-ghost" href="{_e(base_url)}&offset={offset + page_size}">'
           "ถัดไป &rarr;</a>") if offset + page_size < total else ""
    return (f'<nav class="pager" aria-label="Pagination"><span>หน้า {_e((offset // page_size) + 1)}</span>'
            f"{prev}{nxt}</nav>")


def category_page(category, collections, memories, offset=0, total=0, page_size=20) -> str:
    nav = _navbar("library")
    name = _e(category.get("name") or "")
    hint = _e(category.get("hint") or "")
    breadcrumb = f'<p class="breadcrumb"><a href="/portal/">Library</a> › <span>{name}</span></p>'
    blocks = ""
    if collections:
        blocks += ('<h2 class="lib-cat-sub">ชุดความรู้</h2><div class="lib-card-grid">'
                   + "".join(library_card(c, "collection") for c in collections) + "</div>")
    if memories:
        blocks += ('<h2 class="lib-cat-sub">บันทึกความรู้</h2><div class="lib-card-grid">'
                   + "".join(library_card(m, "memory") for m in memories) + "</div>")
    if not blocks:
        blocks = '<div class="empty-state"><p>ยังไม่มีรายการในหมวดนี้</p></div>'
    url = f"/portal/library/subjects/{_e(category.get('key'))}?offset=0"
    body = (nav + breadcrumb + f"<h1>{name}</h1>"
            + f'<p class="section-hint">{hint}</p>'
            + blocks + _pager(offset, page_size, total, url))
    return _page(body)


def library_memory(memory, back="/portal/search", collection_title="", media=None) -> str:
    nav = _navbar("library")
    mid = memory["memory_id"]
    heading = memory.get("title") or memory.get("subject") or "Memory"
    status_html = _status_badge(memory.get("status", ""))
    cat = _category_for_subject(memory.get("subject"))
    cat_name = cat.get("name") or ""

    meta = ""
    for label, value, href in (
        ("Subject", memory.get("subject") or "", ""),
        ("Category", cat_name, ""),
        ("Type", memory.get("memory_type") or "", ""),
        ("Status", memory.get("status") or "", ""),
        ("Language", memory.get("language") or "", ""),
    ):
        if not value:
            continue
        if href:
            meta += ('<li class="reader-meta-item"><span class="reader-meta-k">'
                     + _e(label) + '</span><span class="reader-meta-v"><a href="'
                     + _e(href) + '">' + _e(value) + "</a></span></li>")
        else:
            meta += ('<li class="reader-meta-item"><span class="reader-meta-k">'
                     + _e(label) + '</span><span class="reader-meta-v">'
                     + _e(value) + "</span></li>")
    if collection_title and memory.get("collection_id"):
        parent_url = f"/portal/library/collections/{_e(memory.get('collection_id'))}"
        meta += ('<li class="reader-meta-item"><span class="reader-meta-k">Collection</span>'
                 f'<span class="reader-meta-v"><a href="{_e(parent_url)}">{_e(collection_title)}</a></span></li>')
    meta_html = f'<ul class="reader-meta">{meta}</ul>' if meta else ""

    cover_vm = build_cover_vm(media)
    if cover_vm:
        hero_cover = ('<div class="reader-hero-cover"><img class="reader-cover" '
                      f'src="{_media_thumb_url(cover_vm["media_id"])}" alt="{_e(cover_vm.get("alt") or "")}" loading="lazy"></div>')
    else:
        hero_cover = _empty_cover(heading)
    gallery = _media_section(media) if media else ""
    tech = (
        '<details class="technical"><summary>Technical details</summary>'
        f"<dl><dt>ID</dt><dd class='mono'>{_e(mid)}</dd>"
        f"<dt>Status</dt><dd>{_e(memory.get('status'))}</dd>"
        f"<dt>Version</dt><dd>{_e(memory.get('version'))}</dd>"
        f"<dt>Checksum</dt><dd class='mono'>{_e(memory.get('content_checksum'))}</dd></dl></details>"
    )
    edit_btn = f'<a class="btn btn-xsmall btn-ghost" href="/portal/memories/{_e(mid)}/edit">Edit</a>'
    back_btn = f'<a class="btn btn-ghost" href="{_e(back)}">Back to results</a>'
    body = (
        nav
        + '<div class="reader-hero">' + hero_cover
        + '<div class="reader-hero-body">'
        + f'<h1>{_e(heading)}</h1>' + status_html
        + meta_html
        + "</div></div>"
        + ('<section class="card reader-content"><h2 class="visually-hidden">Content</h2>'
           f'<pre class="reader-text">{_e(memory.get("raw_content", ""))}</pre></section>')
        + gallery
        + tech
        + f'<div class="btn-row reader-actions">{back_btn}{edit_btn}</div>'
    )
    return _page(body)


def _reader_chapter(sec, index) -> str:
    """Read-only chapter block: number, title, cover, ordered illustration gallery."""
    mid = sec.get("memory_id")
    title = sec.get("title") or sec.get("subject") or f"Chapter {index}"
    reader_link = f"/portal/library/memories/{_e(mid)}"
    media = sec.get("media") or []
    cover = next((m for m in media if m.get("is_cover")), (media[0] if media else None))
    parts = []
    if cover:
        parts.append('<div class="chapter-cover-wrap"><img class="chapter-cover" src="'
                     + _media_thumb_url(cover["media_id"])
                     + '" alt="' + _e(cover.get("alt_text") or "") + '" loading="lazy"></div>')
    figs = []
    for m in media:
        alt = _e(m.get("alt_text") or "")
        fig = ('<figure class="reader-figure"><img src="' + _media_thumb_url(m["media_id"])
               + '" alt="' + alt + '" loading="lazy">')
        if m.get("caption"):
            fig += '<figcaption>' + _e(m.get("caption")) + "</figcaption>"
        fig += "</figure>"
        figs.append(fig)
    if figs:
        parts.append('<div class="chapter-gallery" aria-label="Section images">'
                     + "".join(figs) + "</div>")
    parts.append('<div class="chapter-text"><pre>' + _e(sec.get("raw_content", "")) + "</pre></div>")
    parts.append('<p class="back-to-contents"><a href="#chapters">Back to contents</a></p>')
    return ('<article class="chapter" id="chapter-' + _e(str(index)) + '">'
            + f'<h3><span class="chapter-number">{index}.</span> <a href="{reader_link}">{_e(title)}</a></h3>'
            + "".join(parts) + "</article>")


def library_collection(collection, sections, back="/portal/search", media=None) -> str:
    nav = _navbar("library")
    cid = collection["collection_id"]
    title = collection.get("title") or collection.get("subject") or "Collection"
    status_html = _status_badge(collection.get("status", ""))
    sections = list(sections or [])
    ordered = sorted(sections, key=lambda s: s.get("sequence_number") or 0)

    # Table of contents: ordered chapter anchors + small thumbnails.
    toc_items = []
    for i, sec in enumerate(ordered, start=1):
        stitle = sec.get("title") or sec.get("subject") or f"Chapter {i}"
        thumb = ""
        smedia = sec.get("media") or []
        scover = next((m for m in smedia if m.get("is_cover")), (smedia[0] if smedia else None))
        if scover:
            thumb = ('<img class="toc-thumb" src="' + _media_thumb_url(scover["media_id"])
                     + '" alt="" loading="lazy">')
        toc_items.append(
            f'<li class="toc-item"><a href="#chapter-{i}">{thumb}'
            f'<span class="toc-number">{i}.</span> {_e(stitle)}</a></li>')
    toc_html = ('<ol class="toc">' + "".join(toc_items) + "</ol>") if toc_items else ""
    chapters = "".join(_reader_chapter(sec, i) for i, sec in enumerate(ordered, start=1))
    if not ordered:
        chapters = '<div class="empty-state"><p>No chapters yet.</p></div>'

    # Hero: 3:4 cover, title, summary, type/status/language/chapter count, actions.
    cover_vm = build_cover_vm(media)
    if cover_vm:
        hero_cover = ('<div class="reader-hero-cover"><img class="reader-cover" '
                      f'src="{_media_thumb_url(cover_vm["media_id"])}" alt="{_e(cover_vm.get("alt") or "")}" loading="lazy"></div>')
    else:
        hero_cover = _empty_cover(title)
    summary_html = (f'<p class="reader-summary">{_e(collection.get("summary") or "")}</p>'
                    if collection.get("summary") else "")
    meta = (
        '<ul class="reader-meta">'
        f'<li class="reader-meta-item"><span class="reader-meta-k">Subject</span><span class="reader-meta-v">{_e(collection.get("subject"))}</span></li>'
        f'<li class="reader-meta-item"><span class="reader-meta-k">Type</span><span class="reader-meta-v">{_e(collection.get("collection_type") or "")}</span></li>'
        f'<li class="reader-meta-item"><span class="reader-meta-k">Status</span><span class="reader-meta-v">{_e(collection.get("status"))}</span></li>'
        f'<li class="reader-meta-item"><span class="reader-meta-k">Language</span><span class="reader-meta-v">{_e(collection.get("language") or "")}</span></li>'
        f'<li class="reader-meta-item"><span class="reader-meta-k">Chapters</span><span class="reader-meta-v">{len(ordered)}</span></li>'
        '</ul>'
    )
    actions = (
        '<div class="reader-actions">'
        + (f'<a class="btn" href="#chapter-1">เริ่มอ่าน</a>' if ordered else "")
        + '<a class="btn btn-ghost" href="#chapters">Contents</a>'
        + f'<a class="btn btn-ghost" href="{_e(back)}">Back to results</a>'
        + "</div>"
    )
    tech = (
        '<details class="technical"><summary>Technical details</summary>'
        f"<dl><dt>ID</dt><dd class='mono'>{_e(cid)}</dd>"
        f"<dt>Status</dt><dd>{_e(collection.get('status'))}</dd>"
        f"<dt>Version</dt><dd>{_e(collection.get('version'))}</dd>"
        f"<dt>Checksum</dt><dd class='mono'>{_e(collection.get('content_checksum'))}</dd></dl></details>"
    )
    edit_btn = f'<a class="btn btn-xsmall btn-ghost" href="/portal/collections/{_e(cid)}/edit">Edit</a>'
    body = (
        nav
        + '<div class="reader-hero">' + hero_cover
        + '<div class="reader-hero-body">'
        + f'<h1>{_e(title)}</h1>' + status_html + summary_html + meta + actions
        + "</div></div>"
        + ('<section class="reader-toc" id="chapters" aria-label="Table of contents">'
           '<h2>Chapters</h2>' + toc_html + "</section>")
        + f'<section class="reader-content"><h2 class="visually-hidden">Chapters</h2>{chapters}</section>'
        + tech
        + f'<div class="btn-row reader-actions">{edit_btn}</div>'
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


def _resolver_controls(resolver) -> str:
    if not resolver:
        return ""
    readiness = resolver.get("readiness") or {}
    state = readiness.get("status", "not_ready")
    ready_badge = ('<span class="badge active">ready</span>' if state == "ok"
                   else '<span class="badge draft">not ready</span>')
    fs = resolver.get("freshness_summary") or {}
    counts = resolver.get("counts") or {}
    last_build = resolver.get("last_full_build_id") or "-"
    projected_at = resolver.get("projected_at") or "-"
    checksum = resolver.get("snapshot_checksum") or ""
    checksum_short = checksum[:12] if checksum else "-"
    rows = (
        f"<li>Status: {ready_badge} ({_e(state)})</li>"
        f'<li>Fresh: {_e(fs.get("fresh",0))} &middot; Stale: {_e(fs.get("stale",0))} &middot; '
        f'Missing: {_e(fs.get("missing",0))} &middot; Orphaned: {_e(fs.get("orphaned",0))}</li>'
        f'<li>Projection: collections {_e(counts.get("collections",0))} &middot; '
        f'memories {_e(counts.get("memories",0))} &middot; sections {_e(counts.get("sections",0))}</li>'
        f"<li>Last rebuild: {_e(projected_at)}</li>"
        f'<li>Active build ID: <span class="mono">{_e(last_build)}</span></li>'
        f'<li>Snapshot checksum: <span class="mono">{_e(checksum_short)}</span></li>'
    )
    guidance = (
        '<h3>Guidance</h3><ul class="issue-list">'
        "<li>Changed one record - use Selective Rebuild (specify entity type + ID)</li>"
        "<li>Changed several records or you are not sure - use Full Rebuild</li>"
        "<li>The index is not refreshed automatically after Core edits - rebuild it manually</li>"
        "</ul>"
    )
    full_form = (
        '<form method="post" action="/portal/admin/resolver/rebuild">'
        '<label class="field"><span class="field-label">Type REBUILD to confirm</span>'
        '<input name="confirmation" placeholder="REBUILD" required/></label>'
        '<button type="submit" class="btn">Full Rebuild</button></form>'
    )
    sel_form = (
        '<form method="post" action="/portal/admin/resolver/rebuild/selective">'
        '<label class="field"><span class="field-label">Entity type</span>'
        '<input name="entity_type" placeholder="memory or collection" required/></label>'
        '<label class="field"><span class="field-label">Entity ID</span>'
        '<input name="entity_id" placeholder="entity ID" required/></label>'
        '<label class="field"><span class="field-label">Type REBUILD to confirm</span>'
        '<input name="confirmation" placeholder="REBUILD" required/></label>'
        '<button type="submit" class="btn">Selective Rebuild</button></form>'
    )
    debug_link = '<a class="btn btn-ghost" href="/portal/resolver/">Open Resolver Debug</a>'
    return (
        '<section class="card"><h2>Search index (Resolver)</h2>'
        + f'<ul class="audit-mini">{rows}</ul>'
        + guidance
        + '<div class="btn-row">' + full_form + sel_form + debug_link + "</div>"
        + "</section>"
    )


def admin_page(stats, message="", resolver=None) -> str:
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
        + _resolver_controls(resolver)
        + '<section class="card"><h2>Forgotten memories</h2>' + _forgotten_table(forgotten_memories) + "</section>"
        + '<section class="card"><h2>Forgotten collections</h2>' + _forgotten_table(forgotten_collections) + "</section>"
        + '<section class="card"><h2>Ready to purge</h2>' + _forgotten_table(ready) + "</section>"
        + '<section class="card"><h2>Pending retention</h2>' + _forgotten_table(pending) + "</section>"
        + '<section class="card"><h2>Purged memories and collections</h2>' + _purged_table(stats) + "</section>"
    )
    return _page(body)

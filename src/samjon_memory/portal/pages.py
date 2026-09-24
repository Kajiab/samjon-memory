"""Portal presentation helpers: category catalog, cover policy, and view-model
building blocks for the Core Portal.

All rendering is delegated to Jinja2 templates (``portal/templating.py`` +
``portal/templates``). This module only supplies pure logic and small
presentation-ready helpers -- it never renders full pages and never touches
SQLite, repositories, CoreService, or the filesystem (other than the
``category-covers`` asset directory used for configured cover discovery).
"""
from __future__ import annotations

import html as _html
import os
import re
from pathlib import Path

from samjon_memory.config import config
from samjon_memory.constants import DEFAULT_PAGE_SIZE


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _e(text) -> str:
    return _html.escape(str(text) if text is not None else "")


# ---- Media rendering helpers ------------------------------------------------
# Only media metadata (ids + validated alt/caption) is exposed - never binary
# bytes or filesystem paths. URLs point at Portal-authenticated media routes.

def _media_original_url(media_id: str) -> str:
    return f"/portal/media/{media_id}/original"


def _media_thumb_url(media_id: str) -> str:
    return f"/portal/media/{media_id}/thumb"


# ---- Read-only media view models ----------------------------------------------

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


# ---- Message / status helpers (used by view models) -------------------------

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

_STATUS_LABELS = {
    "draft": "Draft",
    "active": "Active",
    "superseded": "Superseded",
    "forgotten": "Forgotten",
}

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

_RESULT_LABELS = {
    "memory": "บันทึกความรู้",
    "collection": "ชุดความรู้",
    "section": "บทภายในชุด",
}


def _cat_counts(cat) -> str:
    # Thai labels: "ชุด" (collections) and "บันทึก" (memories).
    return (f'{_e(cat.get("collections", 0))} ชุด · '
            f'{_e(cat.get("memories", 0))} บันทึก')


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
    """Directory holding configured category-cover assets (override in tests).

    Uses the external ``SAMJON_CATEGORY_COVERS_ROOT`` (a Docker bind mount) when
    configured, otherwise the packaged ``portal/static/category-covers`` dir.
    """
    root = os.environ.get("SAMJON_CATEGORY_COVERS_ROOT", "") or config.category_covers_root
    if root:
        return Path(root)
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


def _category_card(cat) -> str:
    """Thin wrapper: render the shared category-card component (single impl)."""
    from samjon_memory.portal import templating, viewmodels
    return templating.render_partial(
        "components/category_card.html", cat=viewmodels.category_card_vm(cat))
"""Presentation-ready view models for the Jinja2 Core Portal templates.

This module only shapes data for rendering -- it never touches CoreService,
ResolverService, repositories, SQLite, the filesystem, or process environment.
All escaping happens in the templates via Jinja autoescape; values here are raw.
Helpers required by a migrated page are adopted here (from ``pages``) as they
become needed; leftover legacy renderers in ``pages`` are removed at the end.
"""
from __future__ import annotations

import samjon_memory.portal.pages as pages


# ---- Small shared view models -----------------------------------------------

def status_badge_vm(status) -> dict | None:
    """Status badge data; None when no status is supplied."""
    if not status:
        return None
    return {
        "status": status or "",
        "label": pages._STATUS_LABELS.get(status, status),
    }


def banner_vm(message: str) -> dict | None:
    """Success/error banner data; None when there is nothing to render."""
    if not message:
        return None
    if pages._is_error_message(message):
        return {"text": pages._friendly_error(message), "kind": "error", "role": "alert"}
    text = pages._MESSAGE_TEXT.get(message, message)
    return {"text": text, "kind": "success", "role": "status"}


# ---- Cover view models ------------------------------------------------------

def media_frame_vm(*, wrapper, img_class, src, alt, pos=None) -> dict:
    """A cover frame backed by an image (or a placeholder when ``src`` is empty)."""
    return {
        "wrapper": wrapper,
        "img_class": img_class,
        "src": src or "",
        "alt": alt or "",
        "pos": pos if pos and pos != "center" else None,
        "glyph": False,
        "initial": "",
    }


def empty_cover_vm(seed_text: str = "", *, glyph: bool = False) -> dict:
    seed = (seed_text or "").strip()
    return {
        "wrapper": "lib-cover lib-cover-placeholder",
        "img_class": "lib-cover-img",
        "src": "",
        "alt": "",
        "pos": None,
        "glyph": glyph,
        "initial": seed[:1] if seed else "?",
    }


def entity_cover_vm(entity) -> dict:
    """Library-card cover (media frame or simple placeholder)."""
    cov = entity.get("cover")
    if cov and cov.get("media_id"):
        orient = pages._orientation_class(cov.get("width"), cov.get("height"))
        wrapper = "lib-cover media-frame media-frame-cover" + (" " + orient if orient else "")
        return media_frame_vm(
            wrapper=wrapper,
            img_class="lib-cover-img",
            src=pages._media_thumb_url(cov["media_id"]),
            alt=cov.get("alt_text") or cov.get("caption") or "",
        )
    title = entity.get("title") or entity.get("subject") or ""
    return empty_cover_vm(title)


# -- end of part 1 --


def card_cover_vm(entry) -> dict:
    """Search-result/library cover from an enriched result entry."""
    thumb = entry.get("cover_thumb_url")
    title = (entry.get("title") or entry.get("subject")
             or entry.get("collection_title") or "")
    if thumb:
        orient = pages._orientation_class(entry.get("cover_width"), entry.get("cover_height"))
        wrapper = "lib-cover media-frame media-frame-cover" + (" " + orient if orient else "")
        return media_frame_vm(
            wrapper=wrapper,
            img_class="lib-cover-img",
            src=thumb,
            alt=entry.get("cover_alt") or title,
        )
    return empty_cover_vm(title, glyph=True)


def category_cover_vm(cat) -> dict:
    """Category card cover honoring the configured->entity->placeholder chain."""
    conf = pages._configured_category_cover(cat)
    if conf:
        return media_frame_vm(
            wrapper="lib-cat-cover media-frame media-frame-cover media-fit-contain",
            img_class="lib-cat-cover-img",
            src=conf["url"],
            alt=conf["alt"],
            pos=conf["position"],
        )
    cov = cat.get("entity_cover")
    if cov and cov.get("media_id"):
        orient = pages._orientation_class(cov.get("width"), cov.get("height"))
        wrapper = "lib-cat-cover media-frame media-frame-cover" + (" " + orient if orient else "")
        return media_frame_vm(
            wrapper=wrapper,
            img_class="lib-cat-cover-img",
            src=pages._media_thumb_url(cov["media_id"]),
            alt=cov.get("alt_text") or cov.get("caption") or "",
        )
    return empty_cover_vm(cat.get("name") or "", glyph=True)


# ---- Card view models -------------------------------------------------------

def category_card_vm(cat) -> dict:
    key = cat.get("key") or ""
    return {
        "key": key,
        "name": cat.get("name") or "",
        "hint": cat.get("hint") or "",
        "counts": pages._cat_counts(cat),  # plain numeric label string
        "href": f"/portal/library/subjects/{key}",
        "cover": category_cover_vm(cat),
    }


def library_card_vm(entity, entity_type: str) -> dict:
    """Cover-first library card. entity_type in ('memory', 'collection')."""
    if entity_type == "collection":
        label, button = "ชุดความรู้", "เปิดชุดความรู้"
        title = entity.get("title") or entity.get("subject") or ""
        excerpt = (entity.get("summary") or "")[:160]
        link = f"/portal/library/collections/{entity.get('collection_id')}"
    else:
        label, button = "บันทึกความรู้", "อ่านบันทึก"
        title = entity.get("title") or entity.get("subject") or ""
        excerpt = (entity.get("raw_content") or "")[:160]
        link = f"/portal/library/memories/{entity.get('memory_id')}"
    cat_name = pages._category_for_subject(entity.get("subject")).get("name") or ""
    return {
        "label": label,
        "title": title,
        "subject": cat_name,
        "excerpt": excerpt,
        "link": link,
        "button": button,
        "cover": entity_cover_vm(entity),
    }


# -- end of part 2 --


def technical_details_vm(entry) -> dict:
    entity_id = (entry.get("entity_id") or entry.get("memory_id") or entry.get("collection_id"))
    candidates = [
        ("ID", entity_id),
        ("Score", entry.get("score")),
        ("Match reasons", ", ".join(entry.get("match_reasons") or [])),
        ("Freshness", entry.get("projection_freshness")),
        ("Projected version", entry.get("projected_core_version") or entry.get("core_version")),
        ("Checksum", entry.get("checksum")),
    ]
    rows = [{"label": label, "value": value} for label, value in candidates
            if value not in (None, "")]
    return {"rows": rows}


def result_card_vm(entry, kind: str) -> dict:
    kind_label = pages._RESULT_LABELS.get(kind, kind)
    actions, count, selected = [], None, []
    if kind == "section":
        ctitle = entry.get("collection_title") or ""
        subt = entry.get("title") or entry.get("subject") or ""
        title = f"{ctitle} › {subt}" if ctitle else subt
        actions.append({
            "action": "link", "label": "อ่านบทนี้",
            "href": f"/portal/library/memories/{entry.get('memory_id')}", "secondary": False,
        })
        actions.append({
            "action": "link", "label": "เปิดทั้งชุด",
            "href": f"/portal/library/collections/{entry.get('collection_id')}", "secondary": True,
        })
    elif kind == "collection":
        title = entry.get("title") or entry.get("subject") or ""
        n = len(entry.get("selected_sections") or [])
        count = n or None
        actions.append({
            "action": "link", "label": "เปิดชุดความรู้",
            "href": f"/portal/library/collections/{entry.get('collection_id')}", "secondary": False,
        })
        if entry.get("selected_sections"):
            selected = [
                {"memory_id": s.get("memory_id"),
                 "title": s.get("title") or s.get("section_path") or s.get("memory_id")}
                for s in entry["selected_sections"]
            ]
    else:
        title = entry.get("title") or entry.get("subject") or ""
        actions.append({
            "action": "link", "label": "อ่านบันทึก",
            "href": f"/portal/library/memories/{entry.get('memory_id')}", "secondary": False,
        })
    actions.append({"action": "technical", "label": "รายละเอียดทางเทคนิค"})
    badge = status_badge_vm(entry.get("status")) if entry.get("status") else None
    return {
        "kind_label": kind_label,
        "title": title,
        "excerpt": entry.get("excerpt") or "",
        "cover": card_cover_vm(entry),
        "badge": badge,
        "count": count,
        "selected": selected,
        "actions": actions,
        "tech_rows": technical_details_vm(entry)["rows"],
    }


# ---- Pagination -------------------------------------------------------------

def pager_vm(offset, page_size, total, base_url) -> dict | None:
    if total <= page_size:
        return None
    return {
        "page": (offset // page_size) + 1,
        "prev": f"{base_url}&offset={offset - page_size}" if offset > 0 else None,
        "next": (f"{base_url}&offset={offset + page_size}"
                 if offset + page_size < total else None),
    }


# ---- Page-level view models -------------------------------------------------

def library_home_vm(categories, discover, recent, q="") -> dict:
    return {
        "hero": {
            "title": "Search the knowledge library",
            "hint": "ค้นหาความรู้ที่บันทึกไว้ในบ้าน",
            "target": "ค้นหาทั้งบันทึกความรู้ ชุดความรู้ และบทภายในชุด",
            "q": q,
        },
        "categories": [category_card_vm(c) for c in categories],
        "discover": [library_card_vm(e, e.get("_type") or "memory") for e in discover],
        "recent": [library_card_vm(e, e.get("_type") or "memory") for e in recent],
    }


def category_page_vm(category, collections, memories, offset=0, total=0, page_size=20) -> dict:
    key = category.get("key") or ""
    base_url = f"/portal/library/subjects/{key}?offset=0"
    return {
        "category": {"name": category.get("name") or "", "hint": category.get("hint") or ""},
        "collections": [library_card_vm(c, "collection") for c in collections],
        "memories": [library_card_vm(m, "memory") for m in memories],
        "pager": pager_vm(offset, page_size, total, base_url),
    }


def search_vm(q, memories, collections, sections, stale=False, error="",
              total=0, suggestion="") -> dict:
    groups = []
    if memories:
        groups.append({"label": "บันทึกความรู้",
                       "cards": [result_card_vm(e, "memory") for e in memories]})
    if collections:
        groups.append({"label": "ชุดความรู้",
                       "cards": [result_card_vm(e, "collection") for e in collections]})
    if sections:
        groups.append({"label": "บทภายในชุด",
                       "cards": [result_card_vm(e, "section") for e in sections]})
    return {
        "hero": {
            "title": "ค้นหาในคลังความรู้",
            "hint": "พิมพ์คำหรือหัวข้อที่ต้องการค้นหา",
            "target": "ค้นหาทั้งบันทึกและชุดความรู้",
            "q": q,
        },
        "q": q,
        "total": total,
        "stale": stale,
        "error": error,
        "groups": groups,
        "suggestion": suggestion,
    }
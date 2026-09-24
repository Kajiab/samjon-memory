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


# ---- Reader view models -----------------------------------------------------

def media_item_vm(m) -> dict:
    """Read-only/media-admin item: id + authenticated thumb URL + safe text."""
    return {
        "media_id": m["media_id"],
        "thumb_url": pages._media_thumb_url(m["media_id"]),
        "alt": m.get("alt_text") or "",
        "caption": m.get("caption") or "",
        "is_cover": bool(m.get("is_cover")),
    }


def media_gallery_vm(media) -> list:
    return [media_item_vm(m) for m in (media or [])]


def reader_hero_cover_vm(media, fallback: str) -> dict:
    """Reader hero cover frame (image) or an empty-cover placeholder."""
    cov = pages.build_cover_vm(media)
    if cov:
        return media_frame_vm(wrapper="reader-hero-cover", img_class="reader-cover",
                              src=cov["thumb_url"], alt=cov["alt"])
    return empty_cover_vm(fallback, glyph=True)


def _meta_item(label, value, href=None) -> dict:
    return {"label": label, "value": value, "href": href or None}


def memory_reader_vm(memory, back=None, collection_title="", media=None) -> dict:
    mid = memory["memory_id"]
    heading = memory.get("title") or memory.get("subject") or "Memory"
    cat_name = pages._category_for_subject(memory.get("subject")).get("name") or ""
    meta = []
    for label, value in (("Subject", memory.get("subject") or ""),
                         ("Category", cat_name),
                         ("Type", memory.get("memory_type") or ""),
                         ("Status", memory.get("status") or ""),
                         ("Language", memory.get("language") or "")):
        if value:
            meta.append(_meta_item(label, value))
    if collection_title and memory.get("collection_id"):
        meta.append(_meta_item("Collection", collection_title,
                               f"/portal/library/collections/{memory.get('collection_id')}"))
    return {
        "heading": heading,
        "badge": status_badge_vm(memory.get("status") or ""),
        "meta": meta,
        "hero_cover": reader_hero_cover_vm(media, heading),
        "raw_content": memory.get("raw_content", ""),
        "media": media_gallery_vm(media),
        "tech": [
            {"label": "ID", "value": mid, "mono": True},
            {"label": "Status", "value": memory.get("status") or "", "mono": False},
            {"label": "Version", "value": memory.get("version") or "", "mono": False},
            {"label": "Checksum", "value": memory.get("content_checksum") or "", "mono": True},
        ],
        "back": back,
        "edit_link": f"/portal/memories/{mid}/edit",
    }


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


def _chapter_vm(sec, index: int) -> dict:
    """One Collection Reader chapter (ordered section)."""
    reader_link = f"/portal/library/memories/{sec.get('memory_id')}"
    title = sec.get("title") or sec.get("subject") or f"Chapter {index}"
    media = sec.get("media") or []
    cover = next((m for m in media if m.get("is_cover")), (media[0] if media else None))
    figures = [
        {"src": pages._media_thumb_url(m["media_id"]), "alt": m.get("alt_text") or "",
         "caption": m.get("caption") or ""}
        for m in media
    ]
    return {
        "id": f"chapter-{index}",
        "number": index,
        "title": title,
        "reader_link": reader_link,
        "cover": ({"src": pages._media_thumb_url(cover["media_id"]),
                   "alt": cover.get("alt_text") or ""} if cover else None),
        "figures": figures,
        "raw_content": sec.get("raw_content", ""),
    }


def collection_reader_vm(collection, sections, back=None, media=None) -> dict:
    cid = collection["collection_id"]
    title = collection.get("title") or collection.get("subject") or "Collection"
    ordered = sorted(sections or [], key=lambda s: s.get("sequence_number") or 0)
    meta = []
    if collection.get("subject"):
        meta.append(_meta_item("Subject", collection["subject"]))
    if collection.get("collection_type"):
        meta.append(_meta_item("Type", collection["collection_type"]))
    if collection.get("status"):
        meta.append(_meta_item("Status", collection["status"]))
    if collection.get("language"):
        meta.append(_meta_item("Language", collection["language"]))
    meta.append(_meta_item("Chapters", len(ordered)))
    toc = []
    for i, sec in enumerate(ordered, start=1):
        smedia = sec.get("media") or []
        scover = next((m for m in smedia if m.get("is_cover")), (smedia[0] if smedia else None))
        toc.append({
            "index": i,
            "id": f"chapter-{i}",
            "title": sec.get("title") or sec.get("subject") or f"Chapter {i}",
            "thumb": pages._media_thumb_url(scover["media_id"]) if scover else None,
        })
    return {
        "title": title,
        "badge": status_badge_vm(collection.get("status") or ""),
        "summary": collection.get("summary") or "",
        "meta": meta,
        "hero_cover": reader_hero_cover_vm(media, title),
        "start_read": bool(ordered),
        "back": back,
        "toc": toc,
        "chapters": [_chapter_vm(sec, i) for i, sec in enumerate(ordered, start=1)],
        "has_chapters": bool(ordered),
        "tech": [
            {"label": "ID", "value": cid, "mono": True},
            {"label": "Status", "value": collection.get("status") or "", "mono": False},
            {"label": "Version", "value": collection.get("version") or "", "mono": False},
            {"label": "Checksum", "value": collection.get("content_checksum") or "", "mono": True},
        ],
        "edit_link": f"/portal/collections/{cid}/edit",
    }


# ---- Admin: field view models ----------------------------------------------

def text_field_vm(name, label, value="", required=False, maxlen=None, placeholder="",
                  helper="", type_="text") -> dict:
    return {"kind": "text", "name": name, "label": label, "value": value,
            "required": bool(required), "maxlen": maxlen,
            "placeholder": placeholder, "helper": helper, "type": type_}


def textarea_field_vm(name, label, value="", required=False, maxlen=None, rows=6,
                      helper="") -> dict:
    return {"kind": "textarea", "name": name, "label": label, "value": value,
            "required": bool(required), "maxlen": maxlen, "rows": rows,
            "helper": helper}


def readonly_field_vm(label, value, helper="") -> dict:
    return {"kind": "readonly", "label": label, "value": value, "helper": helper}


# ---- Admin media -------------------------------------------------------------

def media_admin_vm(media, entity_type, entity_id, back_target="") -> dict:
    """Admin media-management area (gallery + upload form)."""
    items = []
    total = len(media or [])
    for idx, m in enumerate(media or []):
        items.append({
            **media_item_vm(m),
            "disabled_cover": bool(m.get("is_cover")),
            "disabled_left": idx == 0,
            "disabled_right": idx == total - 1,
        })
    return {
        "cards": items,
        "has_items": bool(items),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "back_target": back_target,
        "has_back": bool(back_target),
    }


def section_media_manager_vm(section, cid) -> dict:
    mid = section["memory_id"]
    back = f"/portal/collections/{cid}#section-{mid}"
    return {
        "mid": mid,
        "back": back,
        "admin": media_admin_vm(section.get("media") or [], "memory", mid, back),
    }


# ---- Admin: Memory pages ----------------------------------------------------

def memory_list_vm(memories, subject="", status_filter="", scope="", offset=0,
                   message="") -> dict:
    status_opts = [{"value": v, "label": l, "selected": status_filter == v}
                   for v, l in [("", "All statuses"), ("draft", "Draft"),
                                ("active", "Active"), ("superseded", "Superseded"),
                                ("forgotten", "Forgotten")]]
    scope_opts = [{"value": v, "label": l, "selected": scope == v}
                  for v, l in [("", "All memories"), ("standalone", "Standalone"),
                               ("collection", "Collection sections"),
                               ("active_knowledge", "Active knowledge")]]
    q = f"subject={subject}&status={status_filter}&scope={scope}"
    prev_offset = max(0, offset - pages.DEFAULT_PAGE_SIZE)
    next_offset = offset + pages.DEFAULT_PAGE_SIZE
    rows = [{
        "memory_id": m["memory_id"],
        "title": m.get("title") or m.get("subject") or "",
        "subject": m.get("subject") or "",
        "badge": status_badge_vm(m.get("status", "")),
        "memory_type": m.get("memory_type", ""),
        "scope": m.get("scope", ""),
        "version": m.get("version", ""),
    } for m in memories]
    return {
        "banner": banner_vm(message),
        "count": len(memories),
        "subject": subject, "status_opts": status_opts, "scope_opts": scope_opts,
        "rows": rows,
        "prev_href": f"/portal/memories?offset={prev_offset}&{q}" if offset > 0 else None,
        "next_href": f"/portal/memories?offset={next_offset}&{q}",
    }


def memory_detail_vm(memory, message="", media=None) -> dict:
    if not memory:
        return {"not_found": True}
    mid = memory["memory_id"]
    fields = [{"label": label, "value": memory.get(key, ""),
               "pre": key in ("raw_content", "structured_value_json")}
              for key, label in pages._MEMORY_FIELDS if key in memory]
    status = memory.get("status", "")
    return {
        "not_found": False,
        "banner": banner_vm(message),
        "subtitle": mid,
        "badge": status_badge_vm(status),
        "fields": fields,
        "media": media_admin_vm(media, "memory", mid, ""),
        "edit_enabled": not memory.get("purged_at"),
        "is_purged": bool(memory.get("purged_at")),
        "is_forgotten": status == "forgotten",
        "show_activate": (not memory.get("purged_at")) and status != "forgotten" and status == "draft",
        "show_supersede": (not memory.get("purged_at")) and status != "forgotten",
        "show_forget": (not memory.get("purged_at")) and status != "forgotten",
        "version": memory.get("version", ""),
        "restore_action": f"/portal/memories/{mid}/restore",
        "purge_action": f"/portal/memories/{mid}/purge",
        "supersede_action": f"/portal/memories/{mid}/supersede",
        "forget_action": f"/portal/memories/{mid}/forget",
        "activate_action": f"/portal/memories/{mid}/activate",
        "edit_path": f"/portal/memories/{mid}/edit",
        "new_path": "/portal/memories/create",
        "list_path": "/portal/memories",
    }


# -- ADMIN A --


def memory_create_vm(message="", error="") -> dict:
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    fields = [
        text_field_vm("subject", "Subject", prefill.get("subject", ""), required=True,
                      maxlen=500, placeholder="e.g. Living room lighting",
                      helper="A short, memorable name for this memory."),
        text_field_vm("memory_type", "Type", prefill.get("memory_type", "fact"),
                      maxlen=100, helper="e.g. fact, note, preference."),
        text_field_vm("scope", "Scope", prefill.get("scope", "household"), maxlen=100,
                      helper="Where this memory applies, e.g. household."),
        text_field_vm("title", "Title", prefill.get("title", ""), maxlen=500,
                      helper="Optional short title."),
        textarea_field_vm("raw_content", "Content", prefill.get("raw_content", ""),
                          required=True, maxlen=16384, rows=8,
                          helper="Required. The full text of the memory."),
        text_field_vm("source", "Source", prefill.get("source", "portal"), maxlen=200),
        text_field_vm("language", "Language", prefill.get("language", "en"),
                      maxlen=10, helper="Language code, e.g. en, th."),
    ]
    return {
        "banner": banner_vm(message),
        "error_text": pages._friendly_error(err_text) if err_text else "",
        "fields": fields,
        "form_action": "/portal/memories",
        "cancel_path": "/portal/memories",
    }


def memory_edit_vm(memory, message="", error="") -> dict:
    if not memory:
        return {"not_found": True}
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    mid = memory["memory_id"]
    is_section = bool(memory.get("collection_id"))
    fields = []
    if is_section:
        fields.append(readonly_field_vm("Subject", memory.get("subject", ""),
                                        "Inherited from the Collection; cannot be changed."))
        fields.append(text_field_vm("memory_type", "Type",
                                    prefill.get("memory_type", memory.get("memory_type", "fact")), maxlen=100))
        fields.append(readonly_field_vm("Scope", memory.get("scope", ""),
                                        "Inherited from the Collection; cannot be changed."))
    else:
        fields.append(text_field_vm("subject", "Subject",
                                    prefill.get("subject", memory.get("subject", "")), required=True, maxlen=500))
        fields.append(text_field_vm("memory_type", "Type",
                                    prefill.get("memory_type", memory.get("memory_type", "fact")), maxlen=100))
        fields.append(text_field_vm("scope", "Scope",
                                    prefill.get("scope", memory.get("scope", "household")), maxlen=100))
    fields += [
        text_field_vm("title", "Title", prefill.get("title", memory.get("title", "")), maxlen=500),
        textarea_field_vm("raw_content", "Content",
                          prefill.get("raw_content", memory.get("raw_content", "")),
                          required=True, maxlen=16384, rows=8),
        text_field_vm("source", "Source", prefill.get("source", memory.get("source", "")), maxlen=200),
        text_field_vm("language", "Language",
                      prefill.get("language", memory.get("language", "en")), maxlen=10),
    ]
    return {
        "not_found": False,
        "banner": banner_vm(message),
        "error_text": pages._friendly_error(err_text) if err_text else "",
        "fields": fields,
        "subtitle": mid,
        "expected_version": memory.get("version", ""),
        "form_action": f"/portal/memories/{mid}",
        "cancel_path": f"/portal/memories/{mid}",
    }


# ---- Admin: Collection pages ------------------------------------------------

def collection_list_vm(collections, message="", status_filter="", invalid=False) -> dict:
    rows = [{
        "collection_id": c["collection_id"],
        "title": c.get("title") or c.get("subject") or "",
        "subject": c.get("subject") or "",
        "collection_type": c.get("collection_type", ""),
        "badge": status_badge_vm(c.get("status", "")),
        "version": c.get("version", ""),
    } for c in collections]
    filters = [
        {"href": "/portal/collections", "label": "All",
         "active": (not status_filter) and not invalid},
        {"href": "/portal/collections?status=draft", "label": "Draft",
         "active": status_filter == "draft" and not invalid},
        {"href": "/portal/collections?status=active", "label": "Active",
         "active": status_filter == "active" and not invalid},
        {"href": "/portal/collections?invalid=1", "label": "Invalid",
         "active": bool(invalid)},
    ]
    return {"banner": banner_vm(message), "rows": rows, "filters": filters,
            "invalid": bool(invalid), "has_rows": bool(collections)}


def collection_create_vm(message="", error="") -> dict:
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    fields = [
        text_field_vm("subject", "Subject", prefill.get("subject", ""), required=True,
                      maxlen=500, placeholder="e.g. Garden care"),
        text_field_vm("collection_type", "Type", prefill.get("collection_type", "fact"),
                      maxlen=100),
        text_field_vm("scope", "Scope", prefill.get("scope", "household"), maxlen=100),
        text_field_vm("title", "Title", prefill.get("title", ""), required=True,
                      maxlen=500, helper="A short name for the collection."),
        textarea_field_vm("summary", "Summary", prefill.get("summary", ""), maxlen=8192,
                          rows=4, helper="Optional overview of what the collection contains."),
        text_field_vm("source", "Source", prefill.get("source", "portal"), maxlen=200),
        text_field_vm("source_reference", "Source reference",
                      prefill.get("source_reference", ""),
                      helper="Optional reference, e.g. a book, page or person."),
        text_field_vm("language", "Language", prefill.get("language", "en"), maxlen=10),
        text_field_vm("expected_item_count", "Expected sections",
                      prefill.get("expected_item_count", ""), type_="number",
                      helper="How many sections you plan to add."),
    ]
    return {
        "banner": banner_vm(message),
        "error_text": pages._friendly_error(err_text) if err_text else "",
        "fields": fields,
        "form_action": "/portal/collections",
        "cancel_path": "/portal/collections",
    }


def collection_edit_vm(collection, message="", error="") -> dict:
    if not collection:
        return {"not_found": True}
    prefill = error if isinstance(error, dict) else {}
    err_text = error if isinstance(error, str) else ""
    cid = collection["collection_id"]
    ev = str(collection.get("expected_item_count") or "")
    fields = [
        text_field_vm("subject", "Subject",
                      prefill.get("subject", collection.get("subject", "")), required=True, maxlen=500),
        text_field_vm("collection_type", "Type",
                      prefill.get("collection_type", collection.get("collection_type", "fact")), maxlen=100),
        text_field_vm("scope", "Scope",
                      prefill.get("scope", collection.get("scope", "household")), maxlen=100),
        text_field_vm("title", "Title",
                      prefill.get("title", collection.get("title", "")), required=True, maxlen=500),
        textarea_field_vm("summary", "Summary",
                          prefill.get("summary", collection.get("summary", "")), maxlen=8192, rows=4),
        text_field_vm("source", "Source",
                      prefill.get("source", collection.get("source", "")), maxlen=200),
        text_field_vm("source_reference", "Source reference",
                      prefill.get("source_reference", collection.get("source_reference", ""))),
        text_field_vm("language", "Language",
                      prefill.get("language", collection.get("language", "en")), maxlen=10),
        text_field_vm("expected_item_count", "Expected sections",
                      prefill.get("expected_item_count", ev), type_="number"),
    ]
    return {
        "not_found": False,
        "banner": banner_vm(message),
        "error_text": pages._friendly_error(err_text) if err_text else "",
        "fields": fields,
        "subtitle": cid,
        "form_action": f"/portal/collections/{cid}",
        "cancel_path": f"/portal/collections/{cid}",
    }


def collection_detail_vm(collection, memories, validation, message="", reopened=False,
                         media=None) -> dict:
    if not collection:
        return {"not_found": True}
    cid = collection["collection_id"]
    fields = [{"label": label, "value": collection.get(key, ""),
               "pre": key == "summary"}
              for key, label in pages._COLLECTION_FIELDS if key in collection]
    expected = collection.get("expected_item_count", 0) or 0
    memories = memories or []
    current = len(memories)
    missing = max(0, expected - current)
    valid = bool(validation.get("valid", False))
    issues = validation.get("issues", []) or []
    fill_class = "success" if valid else ("warning" if current > 0 else "error")
    pct = 0 if expected == 0 else min(100, int(current / expected * 100))
    sections = []
    for i, m in enumerate(memories):
        raw_mid = m["memory_id"]
        label = m.get("title") or m.get("subject") or ""
        up_disabled = i == 0
        down_disabled = i == len(memories) - 1
        if m.get("purged_at"):
            controls = {"kind": "purged"}
        elif m.get("status") == "forgotten":
            controls = {"kind": "restore", "action": f"/portal/memories/{raw_mid}/restore"}
        else:
            controls = {
                "kind": "edit",
                "edit_href": f"/portal/memories/{raw_mid}/edit",
                "up_action": f"/portal/collections/{cid}/memories/{raw_mid}/move-up",
                "down_action": f"/portal/collections/{cid}/memories/{raw_mid}/move-down",
                "forget_action": f"/portal/memories/{raw_mid}/forget",
                "up_disabled": up_disabled, "down_disabled": down_disabled,
                "aria_label": label,
            }
        sections.append({
            "mid": raw_mid, "label": label, "seq": m.get("sequence_number", ""),
            "badge": status_badge_vm(m.get("status", "")), "version": m.get("version", ""),
            "controls": controls,
            "has_media": "media" in m,
            "manager": section_media_manager_vm(m, cid) if "media" in m else None,
        })
    status = collection.get("status", "")
    is_purged = bool(collection.get("purged_at"))
    is_forgotten = status == "forgotten"
    can_edit_sections = not is_purged and not is_forgotten
    add_section_fields = [
        text_field_vm("title", "Section title", "", required=True, maxlen=500,
                      placeholder="e.g. Overview"),
        text_field_vm("memory_type", "Type", "fact", maxlen=100),
        textarea_field_vm("raw_content", "Content", "", required=True, maxlen=16384, rows=6),
        text_field_vm("structured_value", "Structured value (optional)",
                      helper="Optional structured data, as text."),
        text_field_vm("language", "Language", "en", maxlen=10),
        text_field_vm("sequence_number", "Position", current + 1, type_="number"),
    ]
    ordered = sorted(memories, key=lambda x: (x.get("sequence_number") is None,
                                              x.get("sequence_number") or 0))
    assembled = [{"title": m.get("title") or m.get("subject") or "",
                  "raw_content": m.get("raw_content", ""),
                  "seq": m.get("sequence_number")} for m in ordered]
    return {
        "not_found": False,
        "banner": banner_vm(message),
        "reopen_banner": bool(reopened) and status == "draft",
        "subtitle": cid,
        "badge": status_badge_vm(status),
        "fields": fields,
        "media": media_admin_vm(media, "collection", cid, ""),
        "edit_path": f"/portal/collections/{cid}/edit",
        "list_path": "/portal/collections",
        "expected": expected, "current": current, "missing": missing,
        "valid": valid, "issues": issues, "fill_class": fill_class, "pct": pct,
        "sections": sections, "has_sections": bool(sections),
        "can_edit_sections": can_edit_sections,
        "add_section_fields": add_section_fields,
        "add_section_action": f"/portal/collections/{cid}/memories",
        "assembled": assembled,
        "activate_disabled": not valid,
        "activate_action": f"/portal/collections/{cid}/activate",
        "is_purged": is_purged,
        "is_forgotten": is_forgotten,
        "restore_action": f"/portal/collections/{cid}/restore",
        "purge_action": f"/portal/collections/{cid}/purge",
        "version": collection.get("version", ""),
    }
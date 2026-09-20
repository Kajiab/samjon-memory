"""Project a Core active-knowledge snapshot into Resolver documents.

The data here is derived and rebuildable. Resolver content is never treated as
authoritative; authoritative facts always live in Core.
"""

import hashlib
import json
from datetime import datetime, timezone

from samjon_memory.resolver.constants import (
    ENTITY_COLLECTION,
    ENTITY_COLLECTION_MEMORY,
    ENTITY_STANDALONE_MEMORY,
)
from samjon_memory.resolver.normalize import (
    normalize_text,
    safe_override_searchable,
)


def utc_now():
    """UTC timestamp string (deterministic format)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _aliases_for(core, subject):
    if not subject:
        return []
    return [
        normalize_text(a.get("alias"))
        for a in core.get("aliases", [])
        if a.get("subject") == subject and a.get("alias")
    ]


def _tags_for(core, subject):
    if not subject:
        return []
    return [
        normalize_text(t.get("tag"))
        for t in core.get("user_tags", [])
        if t.get("subject") == subject and t.get("tag")
    ]


def _doc_normalized(doc, core):
    parts = [
        normalize_text(doc.get("subject")),
        normalize_text(doc.get("title")),
        normalize_text(doc.get("section_path")),
        normalize_text(doc.get("raw_content")),
    ]
    parts.extend(_aliases_for(core, doc.get("subject")))
    parts.extend(_tags_for(core, doc.get("subject")))
    return " ".join(part for part in parts if part)


def _match_scope_key(entity_type):
    return "memory" if entity_type == ENTITY_STANDALONE_MEMORY else "collection"


def build_documents(core, projected_at):
    """Return documents in a deterministic order.

    Collections and standalone Memories first; Sections are appended per
    Collection ordered by (sequence_number ASC, memory_id ASC). Section subject
    and scope always equal the parent Collection.
    """
    documents = []
    collection_meta = {}
    collection_sections = {}

    for coll in core.get("collections", []):
        cid = coll["collection_id"]
        collection_meta[cid] = coll
        doc = {
            "entity_type": ENTITY_COLLECTION,
            "entity_id": cid,
            "collection_id": cid,
            "sequence_number": None,
            "subject": coll.get("subject"),
            "scope": coll.get("scope"),
            "title": coll.get("title"),
            "section_path": None,
            "raw_content": coll.get("summary") or "",
            "source": coll.get("source"),
            "language": coll.get("language", "en"),
            "core_version": coll.get("version"),
            "core_checksum": coll.get("content_checksum"),
            "projected_at": projected_at,
        }
        doc["match_scope_key"] = _match_scope_key(ENTITY_COLLECTION)
        doc["normalized_text"] = _doc_normalized(doc, core)
        documents.append(doc)

    for mem in core.get("memories", []):
        cid = mem.get("collection_id")
        if cid and cid in collection_meta:
            parent = collection_meta[cid]
            base = {
                "entity_type": ENTITY_COLLECTION_MEMORY,
                "entity_id": mem["memory_id"],
                "collection_id": cid,
                "sequence_number": mem.get("sequence_number"),
                "subject": parent.get("subject"),
                "scope": parent.get("scope"),
                "title": mem.get("title"),
                "section_path": mem.get("section_path"),
                "raw_content": mem.get("raw_content") or "",
                "source": mem.get("source"),
                "language": mem.get("language", "en"),
                "core_version": mem.get("version"),
                "core_checksum": mem.get("content_checksum"),
                "projected_at": projected_at,
            }
            base["match_scope_key"] = _match_scope_key(ENTITY_COLLECTION_MEMORY)
            base["normalized_text"] = _doc_normalized(base, core)
            collection_sections.setdefault(cid, []).append(base)
        else:
            base = {
                "entity_type": ENTITY_STANDALONE_MEMORY,
                "entity_id": mem["memory_id"],
                "collection_id": None,
                "sequence_number": mem.get("sequence_number"),
                "subject": mem.get("subject"),
                "scope": mem.get("scope"),
                "title": mem.get("title"),
                "section_path": mem.get("section_path"),
                "raw_content": mem.get("raw_content") or "",
                "source": mem.get("source"),
                "language": mem.get("language", "en"),
                "core_version": mem.get("version"),
                "core_checksum": mem.get("content_checksum"),
                "projected_at": projected_at,
            }
            base["match_scope_key"] = _match_scope_key(ENTITY_STANDALONE_MEMORY)
            base["normalized_text"] = _doc_normalized(base, core)
            documents.append(base)

    for cid in sorted(collection_sections.keys()):
        ordered = sorted(
            collection_sections[cid],
            key=lambda d: (
                d["sequence_number"] is None,
                d["sequence_number"] if d.get("sequence_number") is not None else 0,
                d["entity_id"],
            ),
        )
        documents.extend(ordered)

    return documents

def counts(documents):
    """Return projected entity counts (collections / standalone / sections)."""
    n_collections = sum(1 for d in documents if d["entity_type"] == ENTITY_COLLECTION)
    n_standalone = sum(
        1 for d in documents if d["entity_type"] == ENTITY_STANDALONE_MEMORY
    )
    n_sections = sum(
        1 for d in documents if d["entity_type"] == ENTITY_COLLECTION_MEMORY
    )
    return {
        "collections": n_collections,
        "memories": n_standalone,
        "sections": n_sections,
    }


def snapshot_checksum(documents):
    """Deterministic checksum over the projected content (order-independent)."""
    payload = []
    for d in sorted(documents, key=lambda x: (x["entity_type"], x["entity_id"] or "")):
        payload.append(
            {
                "entity_type": d["entity_type"],
                "entity_id": d["entity_id"],
                "collection_id": d.get("collection_id"),
                "sequence_number": d.get("sequence_number"),
                "subject": d.get("subject"),
                "scope": d.get("scope"),
                "title": d.get("title"),
                "section_path": d.get("section_path"),
                "raw_content": d.get("raw_content"),
                "normalized_text": d.get("normalized_text"),
                "core_version": d.get("core_version"),
                "core_checksum": d.get("core_checksum"),
            }
        )
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def expansion_maps(core, projected_at):
    """Derive expansion entries from active durable metadata."""
    aliases = [
        {
            "alias_id": a["alias_id"],
            "alias_term": a.get("alias"),
            "subject": a.get("subject"),
            "language": a.get("language", "en"),
            "source": a.get("source"),
            "core_version": a.get("version"),
            "core_checksum": a.get("content_checksum"),
            "projected_at": projected_at,
        }
        for a in core.get("aliases", [])
    ]
    vocabulary = [
        {
            "vocabulary_id": v["vocabulary_id"],
            "term": v.get("term"),
            "definition_norm": normalize_text(v.get("definition")),
            "language": v.get("language", "en"),
            "source": v.get("source"),
            "core_version": v.get("version"),
            "core_checksum": v.get("content_checksum"),
            "projected_at": projected_at,
        }
        for v in core.get("vocabulary", [])
    ]
    user_tags = [
        {
            "tag_id": t["tag_id"],
            "subject": t.get("subject"),
            "tag": t.get("tag"),
            "language": t.get("language", "en"),
            "source": t.get("source"),
            "core_version": t.get("version"),
            "core_checksum": t.get("content_checksum"),
            "projected_at": projected_at,
        }
        for t in core.get("user_tags", [])
    ]
    overrides = [
        {
            "override_id": o["override_id"],
            "subject": o.get("subject"),
            "scope": o.get("scope"),
            "key": normalize_text(o.get("key")),
            "value_snippet": safe_override_searchable(o.get("key"), o.get("value_json")),
            "core_version": o.get("version"),
            "core_checksum": o.get("content_checksum"),
            "projected_at": projected_at,
        }
        for o in core.get("overrides", [])
    ]
    return {
        "aliases": aliases,
        "vocabulary": vocabulary,
        "user_tags": user_tags,
        "overrides": overrides,
    }

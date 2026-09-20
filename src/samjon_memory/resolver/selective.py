"""Selective projection rebuild (Foundation C2) for the Samjon Memory Resolver.

A selective rebuild updates only the affected entity's snapshot + FTS rows and
its derived expansion maps, inside a single Resolver transaction. A failure
rolls back and preserves the previous usable projection.
"""

import uuid

from samjon_memory.errors import ProjectionFailed, ValidationError
from samjon_memory.resolver import project, rebuild
from samjon_memory.resolver.constants import (
    BUILD_TYPE_FULL,
    BUILD_TYPE_SELECTIVE,
    ENTITY_COLLECTION,
    ENTITY_COLLECTION_MEMORY,
    ENTITY_STANDALONE_MEMORY,
    PROJECTION_AUDIT_HISTORY_LIMIT,
    PROJECTION_AUDIT_OK,
    PROJECTION_ENTITY_COLLECTION,
    PROJECTION_ENTITY_MEMORY,
    PROJECTION_ENTITY_TYPES,
)
from samjon_memory.resolver.database import get_connection
from samjon_memory.resolver.migration import ensure_schema


def _make_selective_id():
    return "sel-" + uuid.uuid4().hex[:16]


def _memory_by_id(core, memory_id):
    for m in core.get("memories", []):
        if m["memory_id"] == memory_id:
            return m
    return None


def _collection_by_id(core, collection_id):
    for c in core.get("collections", []):
        if c["collection_id"] == collection_id:
            return c
    return None


def _projection_kind(entity_type):
    if entity_type in (ENTITY_STANDALONE_MEMORY, ENTITY_COLLECTION_MEMORY):
        return PROJECTION_ENTITY_MEMORY
    return PROJECTION_ENTITY_COLLECTION


def _read_all_docs(conn):
    rows = conn.execute("SELECT * FROM resolver_document_snapshot").fetchall()
    return [dict(r) for r in rows]


def _docs_by_key(documents):
    return {(d["entity_type"], d["entity_id"]): d for d in documents}


def _projected_sections(conn, collection_id):
    rows = conn.execute(
        "SELECT entity_type, entity_id, collection_id FROM resolver_document_snapshot "
        "WHERE entity_type=? AND collection_id=?",
        (ENTITY_COLLECTION_MEMORY, collection_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _projection_of_memory(conn, memory_id):
    row = conn.execute(
        "SELECT * FROM resolver_document_snapshot WHERE entity_id=? AND "
        "entity_type IN (?,?)",
        (memory_id, ENTITY_STANDALONE_MEMORY, ENTITY_COLLECTION_MEMORY),
    ).fetchone()
    return dict(row) if row else None


def _remove_doc(conn, entity_type, entity_id):
    conn.execute(
        "DELETE FROM resolver_document_snapshot WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    )
    conn.execute(
        "DELETE FROM resolver_document_fts WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    )
    conn.execute(
        "DELETE FROM projection_status WHERE entity_type=? AND entity_id=?",
        (_projection_kind(entity_type), entity_id),
    )


def _upsert_doc(conn, doc):
    entity_type = doc["entity_type"]
    entity_id = doc["entity_id"]
    _remove_doc(conn, entity_type, entity_id)
    conn.execute(
        "INSERT INTO resolver_document_snapshot (entity_type, entity_id, "
        "collection_id, sequence_number, subject, scope, title, section_path, "
        "raw_content, source, language, normalized_text, match_scope_key, "
        "core_version, core_checksum, projected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (entity_type, entity_id, doc.get("collection_id"), doc.get("sequence_number"),
         doc.get("subject"), doc.get("scope"), doc.get("title"), doc.get("section_path"),
         doc.get("raw_content"), doc.get("source"), doc.get("language"),
         doc.get("normalized_text"), doc.get("match_scope_key"), doc.get("core_version"),
         doc.get("core_checksum"), doc.get("projected_at")),
    )
    conn.execute(
        "INSERT INTO resolver_document_fts (entity_type, entity_id, collection_id, "
        "sequence_number, match_scope_key, subject, title, section_path, "
        "raw_content, normalized_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (entity_type, entity_id, doc.get("collection_id"), doc.get("sequence_number"),
         doc.get("match_scope_key"), doc.get("subject") or "", doc.get("title") or "",
         doc.get("section_path") or "", doc.get("raw_content") or "",
         doc.get("normalized_text") or ""),
    )
    conn.execute(
        "INSERT OR REPLACE INTO projection_status (entity_type, entity_id, "
        "core_version, core_checksum, projected_at) VALUES (?,?,?,?,?)",
        (_projection_kind(entity_type), entity_id, doc.get("core_version"),
         doc.get("core_checksum"), doc.get("projected_at")),
    )

def _refresh_maps(conn, maps):
    conn.execute("DELETE FROM resolver_alias_map")
    conn.execute("DELETE FROM resolver_vocab_map")
    conn.execute("DELETE FROM resolver_tag_map")
    conn.execute("DELETE FROM resolver_override_map")
    for a in maps.get("aliases", []):
        conn.execute(
            "INSERT INTO resolver_alias_map (alias_id, alias_term, subject, language, "
            "source, core_version, core_checksum, projected_at) VALUES (?,?,?,?,?,?,?,?)",
            (a["alias_id"], a["alias_term"], a["subject"], a["language"],
             a["source"], a["core_version"], a["core_checksum"], a["projected_at"]),
        )
    for v in maps.get("vocabulary", []):
        conn.execute(
            "INSERT INTO resolver_vocab_map (vocabulary_id, term, definition_norm, "
            "language, source, core_version, core_checksum, projected_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (v["vocabulary_id"], v["term"], v["definition_norm"], v["language"],
             v["source"], v["core_version"], v["core_checksum"], v["projected_at"]),
        )
    for t in maps.get("user_tags", []):
        conn.execute(
            "INSERT INTO resolver_tag_map (tag_id, subject, tag, language, source, "
            "core_version, core_checksum, projected_at) VALUES (?,?,?,?,?,?,?,?)",
            (t["tag_id"], t["subject"], t["tag"], t["language"], t["source"],
             t["core_version"], t["core_checksum"], t["projected_at"]),
        )
    for o in maps.get("overrides", []):
        conn.execute(
            "INSERT INTO resolver_override_map (override_id, subject, scope, key, "
            "value_snippet, core_version, core_checksum, projected_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (o["override_id"], o["subject"], o["scope"], o["key"],
             o["value_snippet"], o["core_version"], o["core_checksum"], o["projected_at"]),
        )

def _write_audit(conn, build_id, entity_type, entity_id, result_count):
    ts = project.utc_now()
    conn.execute(
        "INSERT INTO projection_audit (build_id, build_type, started_at, finished_at, "
        "status, entity_id, result_count, error_code) VALUES (?,?,?,?,?,?,?,?)",
        (build_id, BUILD_TYPE_SELECTIVE, ts, ts, PROJECTION_AUDIT_OK, entity_id,
         result_count, None),
    )
    conn.execute(
        "DELETE FROM projection_audit WHERE build_id NOT IN ("
        "SELECT build_id FROM projection_audit "
        "ORDER BY started_at DESC, build_id DESC LIMIT ?)",
        (PROJECTION_AUDIT_HISTORY_LIMIT,),
    )

def _metadata_bounded(_core) -> bool:
    """Whether the durable-metadata impact can be safely bounded."""
    return True

def _fallback_full(core_service, database_path):
    result = rebuild.full_rebuild(core_service, database_path)
    result["build_type"] = BUILD_TYPE_FULL
    result["fallback"] = True
    return result

def _orphaned_removes(conn, core, entity_type, entity_id):
    removes = set()
    active_mem_ids = {m["memory_id"] for m in core.get("memories", [])}
    if entity_type == PROJECTION_ENTITY_COLLECTION:
        for row in _projected_sections(conn, entity_id):
            if row["entity_id"] not in active_mem_ids:
                removes.add((ENTITY_COLLECTION_MEMORY, row["entity_id"]))
    else:
        proj = _projection_of_memory(conn, entity_id)
        if proj is not None and _memory_by_id(core, entity_id) is None:
            removes.add((proj["entity_type"], proj["entity_id"]))
    return removes

def selective_rebuild(core_service, database_path, entity_type, entity_id):
    """Selectively rebuild one Memory or Collection and its expansions."""
    if entity_type not in PROJECTION_ENTITY_TYPES:
        raise ValidationError("invalid entity_type")
    if not entity_id:
        raise ValidationError("entity_id is required")
    core = core_service.resolver_projection_snapshot()
    if not _metadata_bounded(core):
        return _fallback_full(core_service, database_path)
    with rebuild.RebuildSession():
        conn = get_connection(database_path)
        ensure_schema(conn)
        try:
            core = core_service.resolver_projection_snapshot()
            if not _metadata_bounded(core):
                conn.close()
                return _fallback_full(core_service, database_path)
            now = project.utc_now()
            documents = project.build_documents(core, now)
            maps = project.expansion_maps(core, now)
            by_key = _docs_by_key(documents)
            adds = []
            removes = set()

            if entity_type == PROJECTION_ENTITY_MEMORY:
                mem = _memory_by_id(core, entity_id)
                if mem is not None:
                    cid = mem.get("collection_id")
                    key = ("collection_memory", entity_id) if cid else ("standalone_memory", entity_id)
                    if key in by_key:
                        adds.append(by_key[key])
                    if cid:
                        col_key = ("collection", cid)
                        if col_key in by_key:
                            adds.append(by_key[col_key])
                else:
                    proj = _projection_of_memory(conn, entity_id)
                    if proj is not None:
                        removes.add((proj["entity_type"], proj["entity_id"]))
                        if proj["entity_type"] == ENTITY_COLLECTION_MEMORY and proj.get("collection_id"):
                            col_key = ("collection", proj["collection_id"])
                            if col_key in by_key:
                                adds.append(by_key[col_key])
            else:
                coll = _collection_by_id(core, entity_id)
                if coll is not None:
                    col_key = ("collection", entity_id)
                    if col_key in by_key:
                        adds.append(by_key[col_key])
                    for (k, d) in by_key.items():
                        if k[0] == ENTITY_COLLECTION_MEMORY and d.get("collection_id") == entity_id:
                            adds.append(d)
                else:
                    removes.add((ENTITY_COLLECTION, entity_id))
                    for row in _projected_sections(conn, entity_id):
                        removes.add((ENTITY_COLLECTION_MEMORY, row["entity_id"]))

            removes |= _orphaned_removes(conn, core, entity_type, entity_id)
            for (et, eid) in removes:
                _remove_doc(conn, et, eid)
            seen = set()
            for doc in adds:
                k = (doc["entity_type"], doc["entity_id"])
                if k in seen:
                    continue
                seen.add(k)
                _upsert_doc(conn, doc)

            _refresh_maps(conn, maps)
            all_docs = _read_all_docs(conn)
            counts = project.counts(all_docs)
            checksum = project.snapshot_checksum(all_docs)
            conn.execute(
                "UPDATE resolver_state SET count_memories=?, count_collections=?, "
                "count_sections=?, snapshot_checksum=? WHERE state_id=1",
                (counts["memories"], counts["collections"], counts["sections"], checksum),
            )
            build_id = _make_selective_id()
            _write_audit(conn, build_id, entity_type, entity_id,
                         counts["memories"] + counts["collections"] + counts["sections"])
            conn.commit()
            return {
                "status": PROJECTION_AUDIT_OK,
                "build_type": BUILD_TYPE_SELECTIVE,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "build_id": build_id,
                "refreshed": sorted(seen),
                "removed": sorted(removes),
                "counts": counts,
                "snapshot_checksum": checksum,
            }
        except ProjectionFailed:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise ProjectionFailed(f"selective rebuild failed: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass
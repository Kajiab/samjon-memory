"""Atomic full projection rebuild for the Samjon Memory Resolver.

Build plan (per the approved Resolver plan):
temporary Resolver DB -> migration -> populate snapshots -> populate FTS5 ->
validate -> checkpoint and close -> rename current DB to .prev -> rename
temporary DB to active path -> reopen and verify.
"""

import os
import sqlite3
import threading
import uuid
from pathlib import Path

from samjon_memory.constants import CORE_SCHEMA_VERSION
from samjon_memory.errors import ProjectionFailed, RebuildInProgress
from samjon_memory.resolver import project
from samjon_memory.resolver.constants import (
    BUILD_TYPE_FULL,
    ENTITY_COLLECTION_MEMORY,
    ENTITY_STANDALONE_MEMORY,
    PROJECTION_AUDIT_FAILED,
    PROJECTION_AUDIT_HISTORY_LIMIT,
    PROJECTION_AUDIT_OK,
    PROJECTION_AUDIT_ROLLED_BACK,
    RESOLVER_SCHEMA_VERSION,
    RESOLVER_SQLITE_PRAGMAS,
)
from samjon_memory.resolver.migration import run_migrations
from samjon_memory.resolver.normalize import is_sensitive_text

_lock = threading.Lock()


class RebuildSession:
    """Context manager enforcing a single-process rebuild lock."""

    def __enter__(self):
        if not _lock.acquire(blocking=False):
            raise RebuildInProgress()
        return self

    def __exit__(self, *_):
        _lock.release()


def rebuild_in_progress() -> bool:
    return _lock.locked()


def make_build_id() -> str:
    return "full-" + uuid.uuid4().hex[:16]


def _paths(database_path):
    active = Path(database_path)
    tmp = Path(str(active) + ".tmp")
    prev = Path(str(active) + ".prev")
    return active, tmp, prev


def _force_remove(path: Path) -> None:
    try:
        if path.exists():
            os.remove(str(path))
    except OSError:
        pass


def _force_remove_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        _force_remove(Path(str(path) + suffix))


def _rename(src: Path, dst: Path) -> None:
    os.replace(str(src), str(dst))


def _checkpoint_and_close_path(path: Path) -> None:
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


def _create_and_migrate(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    for pragma in RESOLVER_SQLITE_PRAGMAS:
        conn.execute(pragma)
    run_migrations(conn)
    return conn


def _read_recent_audits(active: Path, limit: int):
    if not active.exists():
        return []
    conn = None
    try:
        conn = sqlite3.connect(str(active))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT build_id, build_type, started_at, finished_at, status, "
            "entity_id, result_count, error_code FROM projection_audit "
            "ORDER BY started_at ASC, build_id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()


def _write_audit_history(conn, build_id, projected_at, prev_audits, status):
    conn.execute("DELETE FROM projection_audit")
    for r in prev_audits:
        conn.execute(
            "INSERT INTO projection_audit (build_id, build_type, started_at, "
            "finished_at, status, entity_id, result_count, error_code) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (r["build_id"], r["build_type"], r["started_at"], r["finished_at"],
             r["status"], r["entity_id"], r["result_count"], r["error_code"]),
        )
    conn.execute(
        "INSERT INTO projection_audit (build_id, build_type, started_at, "
        "finished_at, status, entity_id, result_count, error_code) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (build_id, BUILD_TYPE_FULL, projected_at, projected_at, status,
         None, None, None),
    )
    conn.execute(
        "DELETE FROM projection_audit WHERE build_id NOT IN ("
        "SELECT build_id FROM projection_audit "
        "ORDER BY started_at DESC, build_id DESC LIMIT ?)",
        (PROJECTION_AUDIT_HISTORY_LIMIT,),
    )

def _populate(conn, documents, maps, build_id, checksum, counts, projected_at,
              core_schema_projected, prev_audits):
    cur = conn.cursor()
    for d in documents:
        cur.execute(
            "INSERT INTO resolver_document_snapshot (entity_type, entity_id, "
            "collection_id, sequence_number, subject, scope, title, "
            "section_path, raw_content, source, language, normalized_text, "
            "match_scope_key, core_version, core_checksum, projected_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["entity_type"], d["entity_id"], d.get("collection_id"),
             d.get("sequence_number"), d.get("subject"), d.get("scope"),
             d.get("title"), d.get("section_path"), d.get("raw_content"),
             d.get("source"), d.get("language"), d.get("normalized_text"),
             d.get("match_scope_key"), d.get("core_version"),
             d.get("core_checksum"), projected_at),
        )
        cur.execute(
            "INSERT INTO resolver_document_fts (entity_type, entity_id, "
            "collection_id, sequence_number, match_scope_key, subject, title, "
            "section_path, raw_content, normalized_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (d["entity_type"], d["entity_id"], d.get("collection_id"),
             d.get("sequence_number"), d.get("match_scope_key"),
             d.get("subject") or "", d.get("title") or "",
             d.get("section_path") or "", d.get("raw_content") or "",
             d.get("normalized_text") or ""),
        )
    for a in maps.get("aliases", []):
        cur.execute(
            "INSERT INTO resolver_alias_map (alias_id, alias_term, subject, "
            "language, source, core_version, core_checksum, projected_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (a["alias_id"], a["alias_term"], a["subject"], a["language"],
             a["source"], a["core_version"], a["core_checksum"], a["projected_at"]),
        )
    for v in maps.get("vocabulary", []):
        cur.execute(
            "INSERT INTO resolver_vocab_map (vocabulary_id, term, "
            "definition_norm, language, source, core_version, core_checksum, "
            "projected_at) VALUES (?,?,?,?,?,?,?,?)",
            (v["vocabulary_id"], v["term"], v["definition_norm"], v["language"],
             v["source"], v["core_version"], v["core_checksum"], v["projected_at"]),
        )
    for t in maps.get("user_tags", []):
        cur.execute(
            "INSERT INTO resolver_tag_map (tag_id, subject, tag, language, "
            "source, core_version, core_checksum, projected_at) VALUES (?,?,?,?,?,?,?,?)",
            (t["tag_id"], t["subject"], t["tag"], t["language"], t["source"],
             t["core_version"], t["core_checksum"], t["projected_at"]),
        )
    for o in maps.get("overrides", []):
        cur.execute(
            "INSERT INTO resolver_override_map (override_id, subject, scope, "
            "key, value_snippet, core_version, core_checksum, projected_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (o["override_id"], o["subject"], o["scope"], o["key"],
             o["value_snippet"], o["core_version"], o["core_checksum"], o["projected_at"]),
        )
    for d in documents:
        etype = (
            "memory"
            if d["entity_type"] in (ENTITY_STANDALONE_MEMORY, ENTITY_COLLECTION_MEMORY)
            else "collection"
        )
        cur.execute(
            "INSERT OR REPLACE INTO projection_status (entity_type, entity_id, "
            "core_version, core_checksum, projected_at) VALUES (?,?,?,?,?)",
            (etype, d["entity_id"], d.get("core_version"), d.get("core_checksum"),
             projected_at),
        )
    if conn.execute("SELECT COUNT(*) FROM resolver_state WHERE state_id=1").fetchone()[0] == 0:
        conn.execute("INSERT OR IGNORE INTO resolver_state (state_id) VALUES (1)")
    conn.execute(
        "UPDATE resolver_state SET last_full_build_id=?, projected_at=?, "
        "core_schema_projected=?, resolver_schema_version=?, count_memories=?, "
        "count_collections=?, count_sections=?, snapshot_checksum=? "
        "WHERE state_id=1",
        (build_id, projected_at, core_schema_projected, RESOLVER_SCHEMA_VERSION,
         counts["memories"], counts["collections"], counts["sections"], checksum),
    )
    _write_audit_history(conn, build_id, projected_at, prev_audits, PROJECTION_AUDIT_OK)
    conn.commit()
    conn.execute("INSERT INTO resolver_document_fts(resolver_document_fts) VALUES('optimize')")
    conn.commit()


def _validate(conn, documents, maps):
    n_docs = conn.execute("SELECT COUNT(*) FROM resolver_document_snapshot").fetchone()[0]
    n_fts = conn.execute("SELECT COUNT(*) FROM resolver_document_fts").fetchone()[0]
    if n_docs != len(documents) or n_fts != len(documents):
        raise ProjectionFailed("projection count mismatch (snapshot/fts)")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ProjectionFailed("resolver integrity check failed")
    rows = conn.execute(
        "SELECT value_snippet FROM resolver_override_map "
        "WHERE value_snippet IS NOT NULL AND value_snippet != ''"
    ).fetchall()
    for row in rows:
        if is_sensitive_text(row[0]):
            raise ProjectionFailed("sensitive override content would be indexed")
    n_overrides = conn.execute("SELECT COUNT(*) FROM resolver_override_map").fetchone()[0]
    if n_overrides != len(maps.get("overrides", [])):
        raise ProjectionFailed("override map count mismatch")


def _verify_active(active_path):
    if not Path(active_path).exists():
        raise ProjectionFailed("active resolver db missing after swap")
    conn = sqlite3.connect(str(active_path))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT value FROM schema_metadata WHERE key='resolver_schema_version'"
        ).fetchone()
        if not row or row["value"] != RESOLVER_SCHEMA_VERSION:
            raise ProjectionFailed("resolver schema version mismatch after swap")
        state = conn.execute(
            "SELECT last_full_build_id FROM resolver_state WHERE state_id=1"
        ).fetchone()
        if not state or not state["last_full_build_id"]:
            raise ProjectionFailed("no build recorded after swap")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ProjectionFailed("resolver integrity check failed after swap")
    finally:
        conn.close()


def _swap(active, tmp, prev):
    _checkpoint_and_close_path(tmp)
    _force_remove_sidecars(tmp)
    if active.exists():
        _checkpoint_and_close_path(active)
        _force_remove_sidecars(active)
        _rename(active, prev)
    _rename(tmp, active)
    _force_remove_sidecars(active)


def _rollback(active, tmp, prev):
    if active.exists():
        _force_remove(active)
    if prev.exists():
        _rename(prev, active)
    if tmp.exists():
        _force_remove(tmp)
    _force_remove_sidecars(active)
def _record_audit(database_path, build_id, status, error_code=None):
    if not Path(database_path).exists():
        return
    conn = None
    try:
        conn = sqlite3.connect(str(database_path))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO projection_audit (build_id, build_type, started_at, "
            "finished_at, status, entity_id, result_count, error_code) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (build_id, BUILD_TYPE_FULL, "", "", status, None, None, error_code),
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()


def recover_interrupted_swap(database_path):
    """Complete or roll back an interrupted swap deterministically on startup."""
    active, tmp, prev = _paths(database_path)

    if active.exists() and prev.exists() and not tmp.exists():
        try:
            _verify_active(active)
            _force_remove(prev)
        except ProjectionFailed:
            _rollback(active, tmp, prev)
        return

    if not active.exists():
        if prev.exists() and tmp.exists():
            _rename(tmp, active)
            try:
                _verify_active(active)
                _force_remove(prev)
            except ProjectionFailed:
                _force_remove(active)
                _rename(prev, active)
        elif tmp.exists():
            _force_remove(tmp)
        elif prev.exists():
            _rename(prev, active)

    _force_remove_sidecars(active)


def full_rebuild(core_service, database_path, projected_at=None):
    """Run an atomic full projection rebuild. Returns a summary dict."""
    with RebuildSession():
        active, tmp, prev = _paths(database_path)
        active.parent.mkdir(parents=True, exist_ok=True)

        recover_interrupted_swap(database_path)

        core = core_service.resolver_projection_snapshot()
        if projected_at is None:
            projected_at = project.utc_now()
        documents = project.build_documents(core, projected_at)
        counts = project.counts(documents)
        checksum = project.snapshot_checksum(documents)
        maps = project.expansion_maps(core, projected_at)
        core_schema_projected = CORE_SCHEMA_VERSION

        prev_audits = _read_recent_audits(active, PROJECTION_AUDIT_HISTORY_LIMIT)
        build_id = make_build_id()

        try:
            _force_remove(tmp)
            tmp_conn = _create_and_migrate(tmp)
            try:
                _populate(tmp_conn, documents, maps, build_id, checksum, counts,
                          projected_at, core_schema_projected, prev_audits)
                _validate(tmp_conn, documents, maps)
            finally:
                tmp_conn.close()
        except Exception as exc:
            _force_remove(tmp)
            _record_audit(active, build_id, PROJECTION_AUDIT_FAILED, error_code=_code(exc))
            raise ProjectionFailed(f"projection build failed: {exc}") from exc

        try:
            _swap(active, tmp, prev)
            _verify_active(active)
        except Exception as exc:
            _rollback(active, tmp, prev)
            _record_audit(active, build_id, PROJECTION_AUDIT_ROLLED_BACK, error_code=_code(exc))
            raise ProjectionFailed(f"projection activation failed: {exc}") from exc

        if prev.exists():
            _force_remove(prev)

        return {
            "status": PROJECTION_AUDIT_OK,
            "build_id": build_id,
            "projected_at": projected_at,
            "snapshot_checksum": checksum,
            "counts": counts,
        }


def _code(exc):
    return getattr(exc, "code", "PROJECTION_FAILED")
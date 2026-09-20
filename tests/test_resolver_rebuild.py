"""Resolver V1 Foundation B tests: Full Projection Build.

Covers projection of active facts, exclusion of inactive facts, sensitive-data
handling, atomic rebuild with rollback, interrupted-swap recovery, the rebuild
lock, readiness, Core preservation, and API auth.
"""

import hashlib
import os
import shutil
import sqlite3
import tempfile

import pytest

from samjon_memory.core.service import CoreService
from samjon_memory.errors import ProjectionFailed, RebuildInProgress
from samjon_memory.resolver import rebuild as rb
from samjon_memory.resolver.migration import RESOLVER_SCHEMA_VERSION
from samjon_memory.resolver.service import ResolverService
from samjon_memory.shared.helpers import utc_now


CORE_FACT_TABLES = {
    "memory",
    "memory_collection",
    "durable_alias",
    "durable_vocabulary",
    "durable_user_tag",
    "manual_override",
    "audit_log",
    "lifecycle_tombstone",
    "idempotency_record",
}
RESOLVER_SPECIFIC_TABLES = {
    "resolver_state",
    "projection_audit",
    "projection_status",
    "resolver_document_snapshot",
    "resolver_document_fts",
    "resolver_alias_map",
    "resolver_vocab_map",
    "resolver_tag_map",
    "resolver_override_map",
}


@pytest.fixture
def temp_resolver_db():
    fd, path = tempfile.mkstemp(suffix="-resolver.sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


def _make_core(temp_db):
    """Seed a Core database with a representative mix of facts."""
    core = CoreService(database_path=temp_db)

    # Standalone ACTIVE.
    m_standalone = core.create_memory(
        {"subject": "plants", "raw_content": "basil grows fast in sun",
         "source": "t", "memory_type": "fact", "scope": "household"}
    )
    core.activate_memory(m_standalone["memory_id"])

    # DRAFT (excluded).
    core.create_memory(
        {"subject": "draft-topic", "raw_content": "draft content alpha beta",
         "source": "t", "scope": "household"}
    )

    # SUPERSEDED + its draft replacement (excluded).
    m_old = core.create_memory(
        {"subject": "legacy", "raw_content": "legacy old value", "source": "t",
         "scope": "household"}
    )
    core.activate_memory(m_old["memory_id"])
    m_repl = core.create_memory(
        {"subject": "legacy", "raw_content": "legacy new value", "source": "t",
         "scope": "household"}
    )
    core.supersede_memory(m_old["memory_id"], m_repl["memory_id"])

    # FORGOTTEN (excluded).
    m_forg = core.create_memory(
        {"subject": "obsolete", "raw_content": "forgotten content", "source": "t",
         "scope": "household"}
    )
    core.forget_memory(m_forg["memory_id"])

    # PURGED (excluded) - forget then flag purged_at directly.
    m_purge = core.create_memory(
        {"subject": "sensitive", "raw_content": "SHOULD-NOT-BE-INDEXED purge payload",
         "source": "t", "scope": "household"}
    )
    core.forget_memory(m_purge["memory_id"])
    core.conn.execute(
        "UPDATE memory SET purged_at=?, purged_by='admin' WHERE memory_id=?",
        (utc_now(), m_purge["memory_id"]),
    )
    core.conn.commit()

    # ACTIVE collection with sections (subject/scope must match parent).
    col = core.create_collection(
        {"subject": "recipes", "collection_type": "fact", "scope": "household",
         "title": "Cooking Notes", "summary": "favorite recipes summary",
         "language": "en", "source": "t"}
    )
    sec1 = core.create_memory(
        {"subject": "recipes", "raw_content": "soup recipe details", "source": "t",
         "scope": "household"}
    )
    sec2 = core.create_memory(
        {"subject": "recipes", "raw_content": "curry recipe details", "source": "t",
         "scope": "household"}
    )
    core.add_memory_to_collection(col["collection_id"], sec1["memory_id"], 2)
    core.add_memory_to_collection(col["collection_id"], sec2["memory_id"], 1)
    core.activate_memory(sec1["memory_id"])
    core.activate_memory(sec2["memory_id"])
    core.activate_collection(col["collection_id"])

    # DRAFT collection (excluded).
    core.create_collection(
        {"subject": "draft-col", "title": "Draft Collection", "source": "t"}
    )

    # Active durable metadata.
    core.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source) "
        "VALUES (?,?,?,?,?)",
        ("alias-1", "plants", "greens", "en", "t"),
    )
    core.conn.execute(
        "INSERT INTO durable_vocabulary (vocabulary_id, term, definition, "
        "language, source) VALUES (?,?,?,?,?)",
        ("vocab-1", "basil", "a leafy herb", "en", "t"),
    )
    core.conn.execute(
        "INSERT INTO durable_user_tag (tag_id, subject, tag, language, source) "
        "VALUES (?,?,?,?,?)",
        ("tag-1", "plants", "garden", "en", "t"),
    )
    core.conn.execute(
        "INSERT INTO manual_override (override_id, subject, scope, key, "
        "value_json, source) VALUES (?,?,?,?,?,?)",
        ("ovr-safe", "plants", "household", "light_pref", '{"light":"bright"}', "t"),
    )
    core.conn.execute(
        "INSERT INTO manual_override (override_id, subject, scope, key, "
        "value_json, source) VALUES (?,?,?,?,?,?)",
        ("ovr-secret", "plants", "household", "access_token",
         '{"token":"sk-12345-secret"}', "t"),
    )
    # NON-ACTIVE alias (excluded).
    core.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source, "
        "status) VALUES (?,?,?,?,?,?)",
        ("alias-old", "plants", "OLDALIAS", "en", "t", "superseded"),
    )
    core.conn.commit()
    return core


def _build(core, resolver_path):
    svc = ResolverService(database_path=resolver_path)
    svc.full_rebuild(core)
    return svc


def _build_closed(core, resolver_path):
    svc = ResolverService(database_path=resolver_path)
    svc.full_rebuild(core)
    svc._close_conn()


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tables(conn):
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' OR type='view'"
        ).fetchall()
    }


# ---- Projection of active facts ------------------------------------------


def test_standalone_memory_projected(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    row = r.conn.execute(
        "SELECT entity_type, normalized_text FROM resolver_document_snapshot "
        "WHERE entity_type='standalone_memory' AND normalized_text LIKE '%basil%'"
    ).fetchone()
    assert row is not None
    assert row["entity_type"] == "standalone_memory"


def test_collection_projected(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    n = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_snapshot WHERE entity_type='collection'"
    ).fetchone()[0]
    assert n == 1


def test_sections_in_active_collection_projected(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    n = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_snapshot "
        "WHERE entity_type='collection_memory'"
    ).fetchone()[0]
    assert n == 2


def test_sections_ordered_by_sequence_number_asc(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    rows = r.conn.execute(
        "SELECT sequence_number FROM resolver_document_snapshot "
        "WHERE entity_type='collection_memory' ORDER BY sequence_number ASC"
    ).fetchall()
    assert [row[0] for row in rows] == [1, 2]


def test_section_subject_scope_match_collection(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    col = r.conn.execute(
        "SELECT subject, scope FROM resolver_document_snapshot "
        "WHERE entity_type='collection' LIMIT 1"
    ).fetchone()
    assert col["subject"] == "recipes"
    assert col["scope"] == "household"
    rows = r.conn.execute(
        "SELECT subject, scope FROM resolver_document_snapshot "
        "WHERE entity_type='collection_memory'"
    ).fetchall()
    for row in rows:
        assert row["subject"] == col["subject"]
        assert row["scope"] == col["scope"]

# ---- Exclusion of inactive facts ------------------------------------------


def test_inactive_statuses_excluded(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    markers = [
        "draft content",
        "legacy old",
        "legacy new",
        "forgotten content",
        "SHOULD-NOT-BE-INDEXED",
        "Draft Collection",
    ]
    for marker in markers:
        n = r.conn.execute(
            "SELECT COUNT(*) FROM resolver_document_snapshot "
            "WHERE normalized_text LIKE ? COLLATE NOCASE",
            (f"%{marker}%",),
        ).fetchone()[0]
        assert n == 0, f"expected {marker!r} to be excluded"


# ---- Expansion maps -------------------------------------------------------


def test_aliases_vocab_tags_projected(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    aliases = [row["alias_term"] for row in r.conn.execute(
        "SELECT alias_term FROM resolver_alias_map").fetchall()]
    assert "greens" in aliases
    assert "OLDALIAS" not in aliases
    vocab = [row["term"] for row in r.conn.execute(
        "SELECT term FROM resolver_vocab_map").fetchall()]
    assert "basil" in vocab
    tags = [row["tag"] for row in r.conn.execute(
        "SELECT tag FROM resolver_tag_map").fetchall()]
    assert "garden" in tags


# ---- Sensitive data -------------------------------------------------------


def test_sensitive_override_content_not_indexed(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    rows = r.conn.execute(
        "SELECT override_id, value_snippet FROM resolver_override_map "
        "ORDER BY override_id").fetchall()
    snippets = {row["override_id"]: row["value_snippet"] for row in rows}
    assert "ovr-secret" in snippets
    assert "sk-12345" not in snippets["ovr-secret"]
    assert "token" not in snippets["ovr-secret"].split()
    assert "ovr-safe" in snippets
    assert "light" in snippets["ovr-safe"]
    for snippet in snippets.values():
        assert "sk-12345-secret" not in snippet
    n = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_snapshot "
        "WHERE normalized_text LIKE '%sk-12345%' OR raw_content LIKE '%sk-12345%'",
    ).fetchone()[0]
    assert n == 0


# ---- Counts / checksum / FTS ---------------------------------------------


def test_snapshot_counts_correct(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    state = r.state()
    assert state["count_memories"] == 1
    assert state["count_collections"] == 1
    assert state["count_sections"] == 2


def test_checksum_deterministic_and_rebuild_equivalent(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    first_checksum = r.state()["snapshot_checksum"]
    first_counts = (r.state()["count_memories"], r.state()["count_collections"],
                    r.state()["count_sections"])
    r.full_rebuild(core)
    assert r.state()["snapshot_checksum"] == first_checksum
    second_counts = (r.state()["count_memories"], r.state()["count_collections"],
                     r.state()["count_sections"])
    assert second_counts == first_counts


def test_fts_rows_match_snapshot_rows(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    n_snapshot = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_snapshot").fetchone()[0]
    n_fts = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_fts").fetchone()[0]
    assert n_fts == n_snapshot
    assert n_snapshot == 4


# ---- Database isolation ---------------------------------------------------


def test_resolver_db_has_no_core_tables(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    tables = _tables(r.conn)
    assert CORE_FACT_TABLES.isdisjoint(tables)


def test_core_db_has_no_resolver_tables(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    _build(core, temp_resolver_db)
    conn = sqlite3.connect(temp_db)
    tables = _tables(conn)
    conn.close()
    assert RESOLVER_SPECIFIC_TABLES.isdisjoint(tables)
    assert not any(t.lower().startswith("resolver") for t in tables)


# ---- Core preservation ---------------------------------------------------


def test_rebuild_creates_no_core_audit_and_core_unchanged(temp_db, temp_resolver_db):
    core = _make_core(temp_db)

    def core_snapshot():
        memories = {
            r["memory_id"]: (r["version"], r["content_checksum"], r["updated_at"],
                             r["raw_content"], r["status"])
            for r in core.query_memories(status=None, limit=10000)
        }
        collections = {
            c["collection_id"]: (c["version"], c["content_checksum"], c["updated_at"],
                                 c["title"], c["status"])
            for c in core.list_collections(limit=10000)
        }
        schema = core.conn.execute(
            "SELECT value FROM schema_metadata WHERE key='core_schema_version'"
        ).fetchone()["value"]
        audit = len(core.get_audit_records(limit=100000))
        return memories, collections, schema, audit

    before_snapshot = core_snapshot()
    before_hash = _sha(temp_db)

    _build(core, temp_resolver_db)

    after_snapshot = core_snapshot()
    after_hash = _sha(temp_db)

    assert before_snapshot == after_snapshot
    assert before_hash == after_hash
# ---- Rebuild lifecycle ---------------------------------------------------


def test_successful_rebuild_atomically_replaces_active(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)
    assert os.path.exists(temp_resolver_db)
    assert not os.path.exists(temp_resolver_db + ".tmp")
    assert not os.path.exists(temp_resolver_db + ".prev")
    assert r.state()["last_full_build_id"]
    assert r.state()["count_memories"] == 1


def test_failed_rebuild_preserves_previous_active(temp_db, temp_resolver_db, monkeypatch):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)  # state A
    old_build_id = r.state()["last_full_build_id"]
    old_counts = (r.state()["count_memories"], r.state()["count_collections"],
                  r.state()["count_sections"])

    def _boom(conn, documents, maps):
        raise ProjectionFailed("injected failure during validate")

    monkeypatch.setattr(rb, "_validate", _boom)
    with pytest.raises(ProjectionFailed):
        r.full_rebuild(core)

    assert r.state()["last_full_build_id"] == old_build_id
    assert (r.state()["count_memories"], r.state()["count_collections"],
            r.state()["count_sections"]) == old_counts
    assert not os.path.exists(temp_resolver_db + ".tmp")


def test_failed_post_swap_verification_restores_prev(temp_db, temp_resolver_db, monkeypatch):
    core = _make_core(temp_db)
    r = _build(core, temp_resolver_db)  # state A
    old_build_id = r.state()["last_full_build_id"]
    old_counts = (r.state()["count_memories"], r.state()["count_collections"],
                  r.state()["count_sections"])
    new_mem = core.create_memory(
        {"subject": "extra", "raw_content": "extra item", "source": "t",
         "scope": "household"})
    core.activate_memory(new_mem["memory_id"])

    def _bad_verify(_path):
        raise ProjectionFailed("injected post-swap verification failure")

    monkeypatch.setattr(rb, "_verify_active", _bad_verify)
    with pytest.raises(ProjectionFailed):
        r.full_rebuild(core)

    assert r.state()["last_full_build_id"] == old_build_id
    assert (r.state()["count_memories"], r.state()["count_collections"],
            r.state()["count_sections"]) == old_counts
    assert not os.path.exists(temp_resolver_db + ".prev")
    assert not os.path.exists(temp_resolver_db + ".tmp")


def test_interrupted_swap_recovery():
    d = tempfile.mkdtemp()
    core_path = os.path.join(d, "core.sqlite")
    resolver_path = os.path.join(d, "resolver.sqlite")
    p_old = os.path.join(d, "old-resolver.sqlite")
    p_new = os.path.join(d, "new-resolver.sqlite")

    core = CoreService(database_path=core_path)
    m1 = core.create_memory({"subject": "s1", "raw_content": "one", "source": "t",
                             "scope": "household"})
    core.activate_memory(m1["memory_id"])
    _build_closed(core, p_old)  # S1: count_memories == 1

    m2 = core.create_memory({"subject": "s2", "raw_content": "two", "source": "t",
                             "scope": "household"})
    core.activate_memory(m2["memory_id"])
    _build_closed(core, p_new)  # S2: count_memories == 2

    shutil.copyfile(p_old, resolver_path + ".prev")
    shutil.copyfile(p_new, resolver_path + ".tmp")

    rb.recover_interrupted_swap(resolver_path)

    assert os.path.exists(resolver_path)
    assert not os.path.exists(resolver_path + ".prev")
    assert not os.path.exists(resolver_path + ".tmp")
    conn = sqlite3.connect(resolver_path)
    n = conn.execute("SELECT count_memories FROM resolver_state WHERE state_id=1").fetchone()[0]
    conn.close()
    assert n == 2


def test_interrupted_swap_recovery_keeps_committed_active():
    d = tempfile.mkdtemp()
    core_path = os.path.join(d, "core.sqlite")
    resolver_path = os.path.join(d, "resolver.sqlite")

    core = CoreService(database_path=core_path)
    m1 = core.create_memory({"subject": "s1", "raw_content": "one", "source": "t",
                             "scope": "household"})
    core.activate_memory(m1["memory_id"])
    _build_closed(core, resolver_path)  # active S1
    shutil.copyfile(resolver_path, resolver_path + ".prev")

    rb.recover_interrupted_swap(resolver_path)

    assert os.path.exists(resolver_path)
    assert not os.path.exists(resolver_path + ".prev")
    conn = sqlite3.connect(resolver_path)
    n = conn.execute("SELECT count_memories FROM resolver_state WHERE state_id=1").fetchone()[0]
    conn.close()
    assert n == 1


def test_rebuild_lock_returns_rebuild_in_progress(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    with rb.RebuildSession():
        with pytest.raises(RebuildInProgress) as excinfo:
            rb.full_rebuild(core, temp_resolver_db)
        assert excinfo.value.code == "REBUILD_IN_PROGRESS"


# ---- Readiness ------------------------------------------------------------


def test_resolver_readiness_changes_and_core_unaffected(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = ResolverService(database_path=temp_resolver_db)
    assert r.readiness()["resolver"]["projection_built"] is False
    r.full_rebuild(core)
    rd = r.readiness()["resolver"]
    assert rd["projection_built"] is True
    assert rd["projection_freshness"] == "fresh"
    assert rd["counts"]["memories"] == 1
    assert core.health()["status"] == "ok"
# ---- API auth and routes -------------------------------------------------


class _FakeAuthConfig:
    has_auth = True
    service_token = "svc-tok"
    admin_token = "adm-tok"
    read_token = "rd-tok"


def test_rebuild_requires_admin_token(temp_db, temp_resolver_db, monkeypatch):
    import samjon_memory.security.auth as auth_mod
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(auth_mod, "config", _FakeAuthConfig())
    app.state.service = _make_core(temp_db)
    app.state.resolver_service = ResolverService(database_path=temp_resolver_db)
    client = TestClient(app)

    assert client.post("/api/v1/resolver/rebuild").status_code == 403
    assert client.post("/api/v1/resolver/rebuild",
                       headers={"X-Admin-Token": "wrong"}).status_code == 403
    ok = client.post("/api/v1/resolver/rebuild",
                     headers={"X-Admin-Token": "adm-tok"})
    assert ok.status_code == 200


def test_status_requires_read_token(temp_db, temp_resolver_db, monkeypatch):
    import samjon_memory.security.auth as auth_mod
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(auth_mod, "config", _FakeAuthConfig())
    app.state.service = _make_core(temp_db)
    app.state.resolver_service = ResolverService(database_path=temp_resolver_db)
    client = TestClient(app)

    assert client.get("/api/v1/resolver/projection/status").status_code == 401
    assert client.get("/api/v1/resolver/rebuild/status").status_code == 401
    assert client.get("/api/v1/resolver/projection/status",
                      headers={"X-Service-Token": "svc-tok"}).status_code == 200
    assert client.get("/api/v1/resolver/rebuild/status",
                      headers={"X-Service-Token": "svc-tok"}).status_code == 200


def test_resolver_routes_registered_in_openapi():
    from samjon_memory.core.main import app
    paths = app.openapi().get("paths", {})
    for route in [
        "/resolver/ready",
        "/api/v1/resolver/rebuild",
        "/api/v1/resolver/rebuild/status",
        "/api/v1/resolver/projection/status",
    ]:
        assert route in paths
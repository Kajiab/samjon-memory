"""Resolver V1 Foundation C2 tests: Selective Rebuild and Bounded Context."""

import hashlib
import os
import sqlite3
import tempfile

import pytest

from samjon_memory.errors import ProjectionFailed, RebuildInProgress
from samjon_memory.resolver import project, rebuild, selective
from samjon_memory.resolver.service import ResolverService
from test_resolver_rebuild import _build, _make_core


@pytest.fixture
def temp_resolver_db():
    fd, path = tempfile.mkstemp(suffix="-resolver.sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


def _seed(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)
    return core, r


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_row(conn, entity_type, entity_id):
    return conn.execute(
        "SELECT * FROM resolver_document_snapshot WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    ).fetchone()


def _fts_count(conn):
    return conn.execute("SELECT COUNT(*) FROM resolver_document_fts").fetchone()[0]


def _snapshot_has(conn, entity_type, entity_id):
    return _snapshot_row(conn, entity_type, entity_id) is not None


def _notebook(core):
    coll = core.create_collection(
        {"subject": "notebook", "title": "Notebook", "source": "t", "scope": "household"})
    sec_ids = {}
    for seq in range(1, 6):
        m = core.create_memory({"subject": "notebook", "raw_content": f"c{seq}",
                                "source": "t", "scope": "household"})
        core.add_memory_to_collection(coll["collection_id"], m["memory_id"], seq)
        core.activate_memory(m["memory_id"])
        sec_ids[f"c{seq}"] = m["memory_id"]
    core.activate_collection(coll["collection_id"])
    return coll, sec_ids


# ---- Selective Memory rebuild ---------------------------------------------


def test_selective_standalone_memory_rebuild(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    coll_row_before = _snapshot_row(r.conn, "collection",
                                    core.query_memories(subject="recipes")[0].get("collection_id"))
    # unrelated - capture a section of the recipes collection
    sec_before = None
    for m in core.query_memories(collection_id=core.query_memories(subject="recipes")[0]["collection_id"]):
        pass
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    sec_rows_before = [dict(_snapshot_row(r.conn, "collection_memory", m["memory_id"]))
                       for m in core.query_memories(collection_id=recipes["collection_id"])]

    core.update_memory(plants["memory_id"], {"raw_content": "basil v2 grows fast"}, actor="system")
    result = r.selective_rebuild(core, "memory", plants["memory_id"])
    assert result["build_type"] == "selective"
    new_row = _snapshot_row(r.conn, "standalone_memory", plants["memory_id"])
    assert new_row["core_version"] == core.query_memories(subject="plants")[0]["version"]
    assert "basil v2" in new_row["normalized_text"]
    # unrelated projections unchanged
    sec_rows_after = [dict(_snapshot_row(r.conn, "collection_memory", m["memory_id"]))
                      for m in core.query_memories(collection_id=recipes["collection_id"])]
    assert len(sec_rows_after) == len(sec_rows_before)
    for before, after in zip(sec_rows_before, sec_rows_after):
        assert before == after


def test_selective_section_rebuild_refreshes_collection(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    sec1 = core.query_memories(collection_id=recipes["collection_id"], limit=100)[0]
    seq_before = _snapshot_row(r.conn, "collection_memory", sec1["memory_id"])["sequence_number"]
    core.update_memory(sec1["memory_id"], {"raw_content": "soup v2 recipe"}, actor="system")
    r.selective_rebuild(core, "memory", sec1["memory_id"])
    row = _snapshot_row(r.conn, "collection_memory", sec1["memory_id"])
    assert row["core_version"] == core.get_memory(sec1["memory_id"])["version"]
    assert row["sequence_number"] == seq_before
    assert "soup v2" in row["normalized_text"]
    # containing Collection projection still present (refreshed)
    assert _snapshot_has(r.conn, "collection", recipes["collection_id"])


def test_selective_collection_rebuild_refreshes_all_sections(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    sec1 = core.query_memories(collection_id=recipes["collection_id"], limit=100)[0]
    core.update_memory(sec1["memory_id"], {"raw_content": "soup v2 recipe"}, actor="system")
    r.selective_rebuild(core, "collection", recipes["collection_id"])
    assert _snapshot_has(r.conn, "collection", recipes["collection_id"])
    count = r.conn.execute(
        "SELECT COUNT(*) FROM resolver_document_snapshot WHERE entity_type='collection_memory' "
        "AND collection_id=?", (recipes["collection_id"],)).fetchone()[0]
    assert count >= 2
    row1 = _snapshot_row(r.conn, "collection_memory", sec1["memory_id"])
    assert row1["core_version"] == core.get_memory(sec1["memory_id"])["version"]


def test_inactive_memory_projection_removed(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    core.forget_memory(plants["memory_id"])
    r.selective_rebuild(core, "memory", plants["memory_id"])
    assert not _snapshot_has(r.conn, "standalone_memory", plants["memory_id"])
    res = r.search(core, "basil", target="memory", allow_stale=False)
    assert res["result_type"] == "no_match"


def test_inactive_collection_and_sections_removed(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    sec_ids = [m["memory_id"] for m in core.query_memories(collection_id=recipes["collection_id"], limit=100)]
    core.forget_collection(recipes["collection_id"])
    r.selective_rebuild(core, "collection", recipes["collection_id"])
    assert not _snapshot_has(r.conn, "collection", recipes["collection_id"])
    for sid in sec_ids:
        assert not _snapshot_has(r.conn, "collection_memory", sid)
    res = r.search(core, "soup", target="auto", allow_stale=False)
    assert res["result_type"] == "no_match"


def test_orphaned_projection_cleaned(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    secs = core.query_memories(collection_id=recipes["collection_id"], limit=100)
    forgotten = secs[0]
    kept = secs[1]
    core.forget_memory(forgotten["memory_id"])
    r.selective_rebuild(core, "collection", recipes["collection_id"])
    assert not _snapshot_has(r.conn, "collection_memory", forgotten["memory_id"])
    assert _snapshot_has(r.conn, "collection_memory", kept["memory_id"])


def test_fts_and_snapshot_consistent(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    core.update_memory(plants["memory_id"], {"raw_content": "basil v2 grows fast"}, actor="system")
    r.selective_rebuild(core, "memory", plants["memory_id"])
    recipes = [c for c in core.list_collections() if c["subject"] == "recipes"][0]
    r.selective_rebuild(core, "collection", recipes["collection_id"])
    snap_count = r.conn.execute("SELECT COUNT(*) FROM resolver_document_snapshot").fetchone()[0]
    assert _fts_count(r.conn) == snap_count

# ---- Expansion refresh ----------------------------------------------------


def test_aliases_and_vocabulary_refresh_affected_results(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    core.conn.execute(
        "INSERT INTO durable_alias (alias_id, subject, alias, language, source) "
        "VALUES (?,?,?,?,?)", ("alias-flora", "plants", "flora", "en", "t"))
    core.conn.execute(
        "INSERT INTO durable_vocabulary (vocabulary_id, term, definition, "
        "language, source) VALUES (?,?,?,?,?)", ("vocab-2", "verte", "a plant", "en", "t"))
    core.conn.commit()

    before = r.search(core, "flora", target="memory", allow_stale=False)
    assert before["result_type"] == "no_match"

    r.selective_rebuild(core, "memory", plants["memory_id"])

    after = r.search(core, "flora", target="memory", allow_stale=False)
    assert after["result_type"] == "standalone_memory"
    assert any("alias_match" in e["match_reasons"] for e in after["results"])
    terms = [row["term"] for row in r.conn.execute("SELECT term FROM resolver_vocab_map").fetchall()]
    assert "verte" in terms


def test_unsafe_metadata_impact_falls_back_to_full_rebuild(temp_db, temp_resolver_db, monkeypatch):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    monkeypatch.setattr(selective, "_metadata_bounded", lambda _core: False)
    r._close_conn()
    result = r.selective_rebuild(core, "memory", plants["memory_id"])
    assert result.get("fallback") is True
    assert result.get("build_type") == "full"
    assert result["build_id"].startswith("full-")


def test_selective_failure_rolls_back(temp_db, temp_resolver_db, monkeypatch):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    before = dict(_snapshot_row(r.conn, "standalone_memory", plants["memory_id"]))

    def _boom(core_, projected_at):
        raise ProjectionFailed("injected failure")

    monkeypatch.setattr(project, "build_documents", _boom)
    with pytest.raises(ProjectionFailed):
        r.selective_rebuild(core, "memory", plants["memory_id"])
    after = dict(_snapshot_row(r.conn, "standalone_memory", plants["memory_id"]))
    assert after == before


def test_concurrent_rebuild_returns_rebuild_in_progress(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    plants = core.query_memories(subject="plants")[0]
    with rebuild.RebuildSession():
        with pytest.raises(RebuildInProgress) as excinfo:
            r.selective_rebuild(core, "memory", plants["memory_id"])
        assert excinfo.value.code == "REBUILD_IN_PROGRESS"
# ---- Bounded context expansion -------------------------------------------


def test_context_returns_previous_and_next_sections(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    coll, sec_ids = _notebook(core)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    result = r.search(core, "c3", target="memory", neighbor_items=2)
    section = [e for e in result["results"] if e.get("memory_id") == sec_ids["c3"]]
    assert section
    ctx = section[0]["context"]
    selected = {s["memory_id"]: s for s in ctx["selected_sections"]}
    assert sec_ids["c2"] in selected and selected[sec_ids["c2"]]["inclusion_reason"] == "previous_neighbor"
    assert sec_ids["c4"] in selected and selected[sec_ids["c4"]]["inclusion_reason"] == "next_neighbor"


def test_context_never_crosses_collection_boundary(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    coll, sec_ids = _notebook(core)
    other = core.create_collection(
        {"subject": "other", "title": "Other", "source": "t", "scope": "household"})
    om = core.create_memory({"subject": "other", "raw_content": "c3", "source": "t",
                             "scope": "household"})
    core.add_memory_to_collection(other["collection_id"], om["memory_id"], 1)
    core.activate_memory(om["memory_id"])
    core.activate_collection(other["collection_id"])
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    result = r.search(core, "c3", target="memory", neighbor_items=2, allow_stale=False)
    for entry in result["results"]:
        if entry["result_type"] == "collection_memory" and entry.get("memory_id") == sec_ids["c3"]:
            ctx = entry["context"]
            assert all(s["memory_id"] in sec_ids.values() for s in ctx["selected_sections"])


def test_context_excludes_inactive_sections(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    coll, sec_ids = _notebook(core)
    core.forget_memory(sec_ids["c2"])
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    result = r.search(core, "c3", target="memory", neighbor_items=2)
    section = [e for e in result["results"] if e.get("memory_id") == sec_ids["c3"]][0]
    selected_ids = [s["memory_id"] for s in section["context"]["selected_sections"]]
    assert sec_ids["c2"] not in selected_ids


def test_context_budget_enforced_and_truncated(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    coll, sec_ids = _notebook(core)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    result = r.search(core, "c3", target="memory", neighbor_items=2, context_budget=2)
    section = [e for e in result["results"] if e.get("memory_id") == sec_ids["c3"]][0]
    ctx = section["context"]
    assert ctx["truncated"] is True
    assert len(ctx["selected_sections"]) <= 1
    assert ctx["context_budget_used"] <= 2


def test_context_deterministic_ordering(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    coll, sec_ids = _notebook(core)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    a = r.search(core, "c3", target="memory", neighbor_items=2)
    b = r.search(core, "c3", target="memory", neighbor_items=2)
    assert a == b
    sec = [e for e in a["results"] if e.get("memory_id") == sec_ids["c3"]][0]
    seqs = sec["context"]["sequence_numbers"]
    assert seqs == sorted(seqs)
# ---- Core unchanged + admin token ----------------------------------------


def test_core_hash_versions_audit_unchanged(temp_db, temp_resolver_db):
    core, r = _seed(temp_db, temp_resolver_db)
    before_hash = _sha(temp_db)
    before_audit = len(core.get_audit_records(limit=100000))
    before_versions = {
        m["memory_id"]: (m["version"], m["content_checksum"], m["status"])
        for m in core.query_memories(status=None, limit=10000)
    }
    plants = core.query_memories(subject="plants")[0]
    r.selective_rebuild(core, "memory", plants["memory_id"])
    r.search(core, "basil", target="memory")  # read-only path
    assert _sha(temp_db) == before_hash
    assert len(core.get_audit_records(limit=100000)) == before_audit
    after_versions = {
        m["memory_id"]: (m["version"], m["content_checksum"], m["status"])
        for m in core.query_memories(status=None, limit=10000)
    }
    assert after_versions == before_versions


class _FakeAuthConfig:
    has_auth = True
    service_token = "svc-tok"
    admin_token = "adm-tok"
    read_token = "rd-tok"


def test_selective_rebuild_requires_admin_token(temp_db, temp_resolver_db, monkeypatch):
    import samjon_memory.security.auth as auth_mod
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(auth_mod, "config", _FakeAuthConfig())
    app.state.service = _make_core(temp_db)
    app.state.resolver_service = ResolverService(database_path=temp_resolver_db)
    client = TestClient(app)

    assert client.post("/api/v1/resolver/rebuild/selective",
                       json={"entity_type": "memory",
                             "entity_id": "mem-1"}).status_code == 403
    resp = client.post("/api/v1/resolver/rebuild/selective",
                       json={"entity_type": "collection", "entity_id": "no-such"},
                       headers={"X-Admin-Token": "adm-tok"})
    assert resp.status_code == 200


def test_selective_route_registered_in_openapi():
    from samjon_memory.core.main import app
    paths = app.openapi().get("paths", {})
    assert "/api/v1/resolver/rebuild/selective" in paths
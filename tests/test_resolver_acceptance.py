"""Resolver V1 Foundation D: Portal + acceptance tests on a synthetic dataset."""

import hashlib
import os
import tempfile

import pytest

from acceptance_dataset import seed_and_build_resolver
from samjon_memory.errors import ProjectionStale


@pytest.fixture
def temp_resolver_db():
    fd, path = tempfile.mkstemp(suffix="-resolver.sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


@pytest.fixture
def acceptance(temp_db, temp_resolver_db):
    core, rsvc = seed_and_build_resolver(temp_db, temp_resolver_db)
    return core, rsvc


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- Search acceptance ---------------------------------------------------


def test_thai_standalone_search(acceptance):
    core, r = acceptance
    result = r.search(core, "โหระพา", target="memory", allow_stale=False)
    assert result["result_type"] == "standalone_memory"
    assert result["count"] >= 1
    assert any("vocabulary_match" in e["match_reasons"] for e in result["results"])


def test_collection_level_search(acceptance):
    core, r = acceptance
    result = r.search(core, "recipes", target="collection", allow_stale=False)
    assert result["result_type"] == "collection"


def test_section_level_search(acceptance):
    core, r = acceptance
    result = r.search(core, "curry", target="memory", allow_stale=False)
    assert result["count"] >= 1
    assert any(e["result_type"] == "collection_memory" for e in result["results"])


def test_alias_and_vocabulary_matching(acceptance):
    core, r = acceptance
    alias = r.search(core, "greens", target="memory", allow_stale=False)
    assert alias["result_type"] == "standalone_memory"
    assert any("alias_match" in e["match_reasons"] for e in alias["results"])
    vocab = r.search(core, "โหระพา", target="memory", allow_stale=False)
    assert any("vocabulary_match" in e["match_reasons"] for e in vocab["results"])


def test_target_filtering(acceptance):
    core, r = acceptance
    m = r.search(core, "curry", target="memory", allow_stale=False)
    assert {e["result_type"] for e in m["results"]} <= {
        "standalone_memory", "collection_memory"}
    c = r.search(core, "curry", target="collection", allow_stale=False)
    assert {e["result_type"] for e in c["results"]} <= {
        "collection", "collection_with_selected_memories"}


def test_selected_neighbor_context(acceptance):
    core, r = acceptance
    result = r.search(core, "curry", target="memory", neighbor_items=2, allow_stale=False)
    section = [e for e in result["results"] if e["result_type"] == "collection_memory"]
    assert section
    ctx = section[0]["context"]
    selected = {s["inclusion_reason"]: s for s in ctx["selected_sections"]}
    assert "previous_neighbor" in selected
    assert "next_neighbor" in selected
    seqs = ctx["sequence_numbers"]
    assert seqs == sorted(seqs)


def test_stale_and_allow_stale(acceptance):
    core, r = acceptance
    plants = core.query_memories(subject="plants")[0]
    core.update_memory(plants["memory_id"], {"raw_content": "basil sprouted faster"}, actor="system")
    with pytest.raises(ProjectionStale) as excinfo:
        r.search(core, "basil", target="memory", allow_stale=False)
    assert excinfo.value.code == "PROJECTION_STALE"
    stale = r.search(core, "basil", target="memory", allow_stale=True)
    assert stale["incomplete"] is True
    assert stale["projection_freshness"] == "stale"


def test_superseded_draft_forgotten_purged_excluded(acceptance):
    core, r = acceptance
    for term in ("draft alpha", "superseded old", "forgotten content", "PURGED-SECRET-CONTENT"):
        res = r.search(core, term, target="auto", allow_stale=False)
        assert res["result_type"] == "no_match", term


def test_deterministic_repeated_results(acceptance):
    core, r = acceptance
    first = r.search(core, "recipes", target="auto", allow_stale=False)
    for _ in range(3):
        assert r.search(core, "recipes", target="auto", allow_stale=False) == first
def test_ambiguous_query(acceptance):
    core, r = acceptance
    # A genuine tie under prefix semantics: the query term appears only in the
    # subject of both entities and never in title/content, so neither entity
    # gains an extra prefix/exact-content boost that would break the tie.
    m = core.create_memory({"subject": "tieword", "raw_content": "alpha beta",
                            "source": "t", "scope": "household"})
    core.activate_memory(m["memory_id"])
    c = core.create_collection({"subject": "tieword", "title": "Tater",
                                "source": "t", "scope": "household"})
    core.activate_collection(c["collection_id"])
    r.full_rebuild(core)
    result = r.search(core, "tieword", target="auto", allow_stale=False)
    assert result["result_type"] == "ambiguous"


def test_no_match_query(acceptance):
    core, r = acceptance
    result = r.search(core, "zzzznone", target="auto", allow_stale=False)
    assert result["result_type"] == "no_match"


# ---- Resolver Portal ------------------------------------------------------


def _portal_client(core, rsvc):
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    app.state.service = core
    app.state.resolver_service = rsvc
    return TestClient(app)


def test_portal_authentication(acceptance):
    core, r = acceptance
    client = _portal_client(core, r)
    assert client.get("/portal/resolver/").status_code == 401
    for path in ("/portal/resolver/query", "/portal/resolver/projection",
                 "/portal/resolver/rebuild"):
        assert client.get(path).status_code == 401
    ok = client.get("/portal/resolver/", auth=("portal-admin", "portal-secret"))
    assert ok.status_code == 200
    assert "portal-secret" not in ok.text
    assert "schema version" in ok.text or "Resolver Dashboard" in ok.text


def test_portal_origin_validation_for_rebuild(acceptance):
    core, r = acceptance
    client = _portal_client(core, r)
    before = r.state()["last_full_build_id"]
    bad = client.post("/portal/resolver/rebuild", data={"confirmation": "rebuild"},
                      headers={"Origin": "http://evil.example"},
                      auth=("portal-admin", "portal-secret"))
    assert bad.status_code == 403
    assert r.state()["last_full_build_id"] == before
    good = client.post("/portal/resolver/rebuild", data={"confirmation": "rebuild"},
                       headers={"Origin": "http://localhost:8100"},
                       auth=("portal-admin", "portal-secret"))
    assert good.status_code in (200, 303)
    assert r.state()["last_full_build_id"]


def test_portal_cancel_no_side_effect(acceptance):
    core, r = acceptance
    client = _portal_client(core, r)
    before = r.state()["last_full_build_id"]
    page = client.get("/portal/resolver/rebuild", auth=("portal-admin", "portal-secret"))
    assert page.status_code == 200
    assert "Cancel" in page.text and "/portal/resolver/rebuild" in page.text
    assert r.state()["last_full_build_id"] == before
    # POST without the required confirmation text performs no mutation
    resp = client.post("/portal/resolver/rebuild", data={},
                       headers={"Origin": "http://localhost:8100"},
                       auth=("portal-admin", "portal-secret"))
    assert resp.status_code in (200, 303)
    assert r.state()["last_full_build_id"] == before


def test_core_preservation_after_portal(temp_db, temp_resolver_db):
    core, r = seed_and_build_resolver(temp_db, temp_resolver_db)
    before_hash = _sha(temp_db)
    before_audit = len(core.get_audit_records(limit=100000))
    before_versions = {
        m["memory_id"]: (m["version"], m["content_checksum"], m["status"])
        for m in core.query_memories(status=None, limit=10000)
    }
    client = _portal_client(core, r)
    client.get("/portal/resolver/", auth=("portal-admin", "portal-secret"))
    client.get("/portal/resolver/query?query=basil", auth=("portal-admin", "portal-secret"))
    client.get("/portal/resolver/projection", auth=("portal-admin", "portal-secret"))
    client.post("/portal/resolver/rebuild", data={"confirmation": "rebuild"},
                headers={"Origin": "http://localhost:8100"},
                auth=("portal-admin", "portal-secret"))
    assert _sha(temp_db) == before_hash
    assert len(core.get_audit_records(limit=100000)) == before_audit
    after_versions = {
        m["memory_id"]: (m["version"], m["content_checksum"], m["status"])
        for m in core.query_memories(status=None, limit=10000)
    }
    assert after_versions == before_versions


def test_resolver_portal_routes_in_openapi():
    from samjon_memory.core.main import app
    paths = app.openapi().get("paths", {})
    for route in ("/portal/resolver/", "/portal/resolver/query",
                  "/portal/resolver/projection", "/portal/resolver/rebuild",
                  "/portal/resolver/rebuild/selective", "/portal/resolver/evidence"):
        assert route in paths
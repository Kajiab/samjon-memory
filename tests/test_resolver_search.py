"""Resolver V1 Foundation C1 tests: Search, Ranking, and Freshness."""

import hashlib
import os
import sqlite3
import tempfile

import pytest

from samjon_memory.errors import ProjectionStale, ValidationError
from samjon_memory.resolver import freshness as freshness_mod
from samjon_memory.resolver import query as query_mod
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


def _seed_temp(path):
    return _build(_make_core(path), _gap_temp())


@pytest.fixture
def seed(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)
    return core, r


def _gap_temp():
    return None  # placeholder; real resolver path is passed explicitly


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- Safe FTS5 query parsing ---------------------------------------------


def test_parse_empty_query():
    matcher, tokens, reason = query_mod.parse_query("   ")
    assert matcher is None
    assert tokens == []
    assert reason in ("empty", "empty_after_normalize")


def test_parse_missing_query_rejected():
    with pytest.raises(ValidationError):
        query_mod.parse_query(None)


def test_parse_oversized_query_rejected():
    with pytest.raises(ValidationError):
        query_mod.parse_query("x" * 5000)


def test_parse_neutralizes_punctuation_and_operators():
    matcher, tokens, reason = query_mod.parse_query(
        'basil OR "curry" (soup) -mint:extra* AND NOT'
    )
    assert reason == "ok"
    assert set(tokens) == {"basil", "or", "curry", "soup", "mint", "extra", "and", "not"}
    assert matcher.startswith("\"basil\"")
    # No raw FTS operator or punctuation reaches the MATCH expression directly.
    assert " OR " not in matcher
    assert "(" not in matcher and ")" not in matcher
    assert "-" not in matcher and ":" not in matcher and "*" not in matcher
    # Every entity is a double-quoted token (safe phrase), not raw syntax.
    for token in tokens:
        assert f'"{token}"' in matcher


def test_parse_handles_thai_text_and_punctuation():
    matcher, tokens, _reason = query_mod.parse_query("basil\u0e01\u0e31\u0e1a curry\uff0e\uff01")
    assert any("\u0e01\u0e31\u0e1a" in t for t in tokens)
    assert "\uff0e" not in matcher
    assert "\uff01" not in matcher


def test_parse_punctuation_only_yields_empty():
    matcher, tokens, _reason = query_mod.parse_query("***((( )))---::")
    assert matcher is None
    assert tokens == []


def test_parse_bounds_token_count():
    _matcher, tokens, _reason = query_mod.parse_query(" ".join(["tok"] * 500))
    assert len(tokens) == query_mod.MAX_QUERY_TOKENS


def test_safe_match_expr():
    assert query_mod.safe_match_expr("") == ""
    assert query_mod.safe_match_expr("basil") == '"basil"'

# ---- Search + ranking ----------------------------------------------------


def test_standalone_memory_match(seed):
    core, r = seed
    result = r.search(core, "basil", target="memory")
    assert result["result_type"] == "standalone_memory"
    assert result["count"] >= 1
    top = result["results"][0]
    assert top["result_type"] == "standalone_memory"
    assert top["match_reasons"] == ["token_match", "vocabulary_match"]


def test_collection_section_match(seed):
    core, r = seed
    result = r.search(core, "soup", target="memory")
    assert result["count"] >= 1
    assert any(entry["result_type"] == "collection_memory" for entry in result["results"])


def test_collection_match(seed):
    core, r = seed
    result = r.search(core, "recipes", target="collection")
    assert result["result_type"] == "collection"


def test_target_filtering_memory(seed):
    core, r = seed
    result = r.search(core, "soup", target="memory")
    types = {entry["result_type"] for entry in result["results"]}
    assert types <= {"standalone_memory", "collection_memory"}


def test_target_filtering_collection(seed):
    core, r = seed
    result = r.search(core, "soup", target="collection")
    types = {entry["result_type"] for entry in result["results"]}
    assert types <= {"collection", "collection_with_selected_memories"}


def test_target_filtering_auto(seed):
    core, r = seed
    result = r.search(core, "soup", target="auto")
    types = {entry["result_type"] for entry in result["results"]}
    assert "collection_memory" in types
    assert "collection_with_selected_memories" in types


def test_alias_match(seed):
    core, r = seed
    result = r.search(core, "greens", target="memory", allow_stale=False)
    assert result["count"] >= 1
    assert any("alias_match" in e["match_reasons"] for e in result["results"])


def test_vocabulary_match(seed):
    core, r = seed
    result = r.search(core, "basil", target="memory")
    assert any("vocabulary_match" in e["match_reasons"] for e in result["results"])


def test_tag_match(seed):
    core, r = seed
    result = r.search(core, "garden", target="memory")
    assert result["count"] >= 1
    assert any("tag_match" in e["match_reasons"] for e in result["results"])


def test_no_match(seed):
    core, r = seed
    result = r.search(core, "zzzznope", target="auto")
    assert result["result_type"] == "no_match"
    assert result["count"] == 0


def test_deterministic_repeated_results(seed):
    core, r = seed
    first = r.search(core, "recipes", target="auto")
    for _ in range(3):
        assert r.search(core, "recipes", target="auto") == first


def test_deterministic_tie_break(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    a = core.create_memory({"subject": "dup", "raw_content": "dupdata", "source": "t",
                            "scope": "household"})
    b = core.create_memory({"subject": "dup", "raw_content": "dupdata", "source": "t",
                            "scope": "household"})
    core.activate_memory(a["memory_id"])
    core.activate_memory(b["memory_id"])
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)
    result = r.search(core, "dupdata", target="memory")
    ids = [e["identity"]["memory_id"] for e in result["results"] if e["result_type"] == "standalone_memory"]
    assert ids == sorted(ids)
    assert len(ids) >= 2


def test_ambiguous_result(seed):
    core, r = seed
    col = core.create_collection(
        {"subject": "plants", "title": "Alpha Catalog", "source": "t"})
    core.activate_collection(col["collection_id"])
    r.full_rebuild(core)
    result = r.search(core, "plants", target="auto", allow_stale=False)
    assert result["result_type"] == "ambiguous"
    assert result["count"] == 2
    types = {e["result_type"] for e in result["results"]}
    assert types == {"standalone_memory", "collection"}
# ---- Bounding -------------------------------------------------------------


def test_bounded_limit_and_offset(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    for i in range(5):
        m = core.create_memory({"subject": "wiki", "raw_content": f"wiki {i}",
                                "source": "t", "scope": "household"})
        core.activate_memory(m["memory_id"])
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    all_results = r.search(core, "wiki", target="memory")
    assert all_results["total"] == 5

    page1 = r.search(core, "wiki", target="memory", limit=2, offset=0)
    assert len(page1["results"]) == 2
    page2 = r.search(core, "wiki", target="memory", limit=2, offset=2)
    assert len(page2["results"]) == 2
    page3 = r.search(core, "wiki", target="memory", limit=2, offset=4)
    assert len(page3["results"]) == 1
    p1_ids = [e["identity"]["memory_id"] for e in page1["results"]]
    p2_ids = [e["identity"]["memory_id"] for e in page2["results"]]
    assert not (set(p1_ids) & set(p2_ids))


def test_draft_superseded_forgotten_purged_never_returned(seed):
    core, r = seed
    result = r.search(core, "draft content", target="auto")
    assert result["result_type"] == "no_match"
    result = r.search(core, "legacy", target="auto")
    assert result["result_type"] == "no_match"
    result = r.search(core, "forgotten content", target="auto")
    assert result["result_type"] == "no_match"
    result = r.search(core, "SHOULD-NOT-BE-INDEXED", target="auto")
    assert result["result_type"] == "no_match"


# ---- Freshness ------------------------------------------------------------


def test_fresh_projection(seed):
    core, r = seed
    result = r.search(core, "basil", target="auto", allow_stale=False)
    assert result["projection_freshness"] == "fresh"
    assert result["incomplete"] is False
    for entry in result["results"]:
        assert entry["projection_freshness"] == "fresh"


def test_stale_allow_stale_false_raises(seed):
    core, r = seed
    mem = core.query_memories(subject="plants")[0]
    core.update_memory(mem["memory_id"], {"raw_content": "basil updated xyz"}, actor="system")
    with pytest.raises(ProjectionStale) as excinfo:
        r.search(core, "basil", target="auto", allow_stale=False)
    assert excinfo.value.code == "PROJECTION_STALE"


def test_stale_allow_stale_true_returns_evidence(seed):
    core, r = seed
    mem = core.query_memories(subject="plants")[0]
    core.update_memory(mem["memory_id"], {"raw_content": "basil updated xyz"}, actor="system")
    result = r.search(core, "basil", target="auto", allow_stale=True)
    assert result["incomplete"] is True
    assert result["projection_freshness"] == "stale"
    plants = [e for e in result["results"] if e.get("memory_id") == mem["memory_id"]]
    assert plants and plants[0]["projection_freshness"] == "stale"


def test_missing_and_orphaned_freshness(seed):
    core, r = seed
    added = core.create_memory({"subject": "newwiki", "raw_content": "newwiki token",
                                "source": "t", "scope": "household"})
    core.activate_memory(added["memory_id"])
    core.forget_memory(core.query_memories(subject="plants")[0]["memory_id"])
    mapping = freshness_mod.compute(r.conn, core)
    assert mapping[("memory", added["memory_id"])] == "missing"
    orphaned_ids = [k[1] for k, v in mapping.items() if v == "orphaned"]
    assert orphaned_ids
    # Orphaned entity is still searchable but marked orphaned (allow_stale True).
    res = r.search(core, "basil", target="memory", allow_stale=True)
    assert res["incomplete"] is True


# ---- Core unchanged -------------------------------------------------------


def test_search_leaves_core_unchanged(temp_db, temp_resolver_db):
    core = _make_core(temp_db)
    r = ResolverService(database_path=temp_resolver_db)
    r.full_rebuild(core)

    before_hash = _sha(temp_db)
    before_audit = len(core.get_audit_records(limit=100000))
    r.search(core, "basil", target="auto")
    r.search(core, "recipes", target="collection")
    r.search(core, "soup", target="memory")
    after_hash = _sha(temp_db)
    after_audit = len(core.get_audit_records(limit=100000))
    assert before_hash == after_hash
    assert before_audit == after_audit


# ---- API auth + OpenAPI ---------------------------------------------------


class _FakeAuthConfig:
    has_auth = True
    service_token = "svc-tok"
    admin_token = "adm-tok"
    read_token = "rd-tok"


def test_query_requires_read_token(temp_db, temp_resolver_db, monkeypatch):
    import samjon_memory.security.auth as auth_mod
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(auth_mod, "config", _FakeAuthConfig())
    app.state.service = _make_core(temp_db)
    app.state.resolver_service = ResolverService(database_path=temp_resolver_db)
    client = TestClient(app)

    assert client.post("/api/v1/resolver/query",
                       json={"query": "basil"}).status_code == 401
    resp = client.post("/api/v1/resolver/query",
                       json={"query": "basil"},
                       headers={"X-Service-Token": "svc-tok"})
    assert resp.status_code == 200
    assert resp.json()["result_type"] in ("standalone_memory", "no_match")


def test_query_route_registered_in_openapi():
    from samjon_memory.core.main import app
    paths = app.openapi().get("paths", {})
    assert "/api/v1/resolver/query" in paths
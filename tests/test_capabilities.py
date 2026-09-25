"""Capabilities manifest accuracy tests.

Verify the ``/api/v1/capabilities`` response reports the current executable
reality: Resolver implemented, FTS5, exact/prefix/Thai-infix search, freshness
evidence, and bounded Collection context. All version values are asserted
against the authoritative constants so a version bump cannot silently drift.
"""

from fastapi.testclient import TestClient


def _client():
    from samjon_memory.core.main import app
    return TestClient(app)


def _capabilities():
    resp = _client().get("/api/v1/capabilities")
    assert resp.status_code == 200
    return resp.json()


def test_reports_core_schema_version_from_constant():
    from samjon_memory.constants import CORE_SCHEMA_VERSION
    data = _capabilities()
    assert data["core_schema_version"] == CORE_SCHEMA_VERSION


def test_reports_resolver_schema_version_from_constant():
    from samjon_memory.resolver.constants import RESOLVER_SCHEMA_VERSION
    data = _capabilities()
    assert data["resolver_schema_version"] == RESOLVER_SCHEMA_VERSION


def test_resolver_implemented():
    data = _capabilities()
    resolver = data["features"]["resolver"]
    assert resolver["implemented"] is True
    assert resolver["database"] == "samjon_resolver.sqlite"


def test_resolver_database_not_stale():
    """The stale 'resolver_database'/'fts5' top-level flags are gone."""
    data = _capabilities()
    features = data["features"]
    assert "resolver_database" not in features
    assert "fts5" not in features
    assert "resolver" in features


def test_fts5_available():
    data = _capabilities()
    fts5 = data["features"]["resolver"]["fts5"]
    assert fts5["implemented"] is True
    assert fts5["required"] is True


def test_search_exact_prefix_thai_infix():
    data = _capabilities()
    search = data["features"]["resolver"]["search"]
    assert search["exact"] is True
    assert search["prefix"] is True
    assert search["thai_infix"] is True


def test_freshness_evidence():
    data = _capabilities()
    freshness = data["features"]["resolver"]["freshness_evidence"]
    assert freshness["implemented"] is True
    assert freshness["allow_stale"] is True


def test_bounded_context():
    data = _capabilities()
    ctx = data["features"]["resolver"]["bounded_context"]
    assert ctx["implemented"] is True
    assert ctx["max_neighbors"] > 0
    assert ctx["max_query_tokens"] > 0
    assert ctx["max_query_limit"] > 0


def test_resolver_routes_listed():
    data = _capabilities()
    routes = data["routes"]
    assert "GET /resolver/ready" in routes
    assert "POST /api/v1/resolver/query" in routes
    assert "POST /api/v1/resolver/rebuild" in routes
    assert "POST /api/v1/resolver/rebuild/selective" in routes
    assert "GET /api/v1/resolver/projection/status" in routes
    assert "GET /api/v1/resolver/rebuild/status" in routes
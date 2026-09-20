"""Resolver V1 Foundation A tests.

Covers: migrations, schema metadata, resolver database isolation from Core,
Core isolation from Resolver, initialization side-effect-freedom on Core,
FTS5 fail-fast with the approved stable error, and readiness independence.
"""

import hashlib
import os
import sqlite3
import tempfile

import pytest

from samjon_memory.errors import ResolverDatabaseUnavailable
from samjon_memory.resolver.migration import (
    RESOLVER_SCHEMA_VERSION,
    ensure_schema,
    get_schema_version,
    run_migrations,
)
from samjon_memory.resolver.service import ResolverService
from samjon_memory.core.service import CoreService


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
RESOLVER_TABLES = {
    "schema_metadata",
    "resolver_state",
    "projection_audit",
    "projection_status",
}
# Tables that exist only in the Resolver database. Core also has its own
# generic `schema_metadata`, so it is excluded from the Core-side isolation
# assertion (resolver-specific tables must never appear in Core).
RESOLVER_SPECIFIC_TABLES = RESOLVER_TABLES - {"schema_metadata"}


@pytest.fixture
def temp_resolver_db():
    fd, path = tempfile.mkstemp(suffix="-resolver.sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


def _tables(conn):
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


# ---- Migration -----------------------------------------------------------


def test_resolver_initial_migration(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    applied = run_migrations(conn)
    assert "1.0.0" in applied
    assert get_schema_version(conn) == RESOLVER_SCHEMA_VERSION
    conn.close()


def test_resolver_migration_idempotent(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    ensure_schema(conn)
    applied = run_migrations(conn)
    assert applied == []
    conn.close()


def test_resolver_schema_version(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    ensure_schema(conn)
    assert get_schema_version(conn) == RESOLVER_SCHEMA_VERSION
    conn.close()


# ---- Schema metadata / foundation tables ---------------------------------


def test_resolver_state_single_row_foundation(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM resolver_state").fetchall()
    assert len(rows) == 1
    assert rows[0]["state_id"] == 1
    conn.close()


def test_projection_foundation_tables(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    ensure_schema(conn)
    pa = {r[1] for r in conn.execute("PRAGMA table_info(projection_audit)").fetchall()}
    assert {
        "build_id",
        "build_type",
        "started_at",
        "finished_at",
        "status",
        "entity_id",
        "result_count",
        "error_code",
    } <= pa
    ps = {r[1] for r in conn.execute("PRAGMA table_info(projection_status)").fetchall()}
    assert {"entity_type", "entity_id", "core_version", "core_checksum", "projected_at"} <= ps
    conn.close()


# ---- Database isolation --------------------------------------------------


def test_resolver_database_has_no_core_fact_tables(temp_resolver_db):
    conn = sqlite3.connect(temp_resolver_db)
    ensure_schema(conn)
    tables = _tables(conn)
    assert CORE_FACT_TABLES.isdisjoint(tables)
    assert RESOLVER_TABLES.issubset(tables)
    conn.close()


def test_core_database_has_no_resolver_tables(temp_db):
    from samjon_memory.core.migration import ensure_schema as ensure_core_schema

    conn = sqlite3.connect(temp_db)
    ensure_core_schema(conn)
    tables = _tables(conn)
    assert RESOLVER_SPECIFIC_TABLES.isdisjoint(tables)
    conn.close()


def test_resolver_initialization_does_not_change_core(temp_db, temp_resolver_db):
    core = CoreService(database_path=temp_db)
    mem = core.create_memory(
        {"subject": "topic", "raw_content": "hello world", "source": "t"}
    )
    core.activate_memory(mem["memory_id"])

    def core_snapshot():
        rows = core.query_memories(status=None, limit=100)
        memories = {
            r["memory_id"]: (
                r["version"],
                r["content_checksum"],
                r["status"],
                r["updated_at"],
            )
            for r in rows
        }
        schema = core.conn.execute(
            "SELECT value FROM schema_metadata WHERE key='core_schema_version'"
        ).fetchone()["value"]
        audit = len(core.get_audit_records(limit=1000))
        return memories, schema, audit

    def file_sha(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    before_snapshot = core_snapshot()
    before_hash = file_sha(temp_db)

    # Initialize Resolver Foundation A. Must not touch Core.
    ResolverService(database_path=temp_resolver_db)

    after_snapshot = core_snapshot()
    after_hash = file_sha(temp_db)

    assert before_snapshot == after_snapshot
    assert before_hash == after_hash


# ---- FTS5 fail-fast ------------------------------------------------------


def test_fts5_missing_fails_with_stable_error(temp_resolver_db, monkeypatch):
    import samjon_memory.resolver.database as rdb

    conn = sqlite3.connect(temp_resolver_db)
    monkeypatch.setattr(rdb, "fts5_available", lambda _conn: False)
    with pytest.raises(ResolverDatabaseUnavailable) as excinfo:
        ensure_schema(conn)
    assert excinfo.value.code == "RESOLVER_DATABASE_UNAVAILABLE"
    conn.close()


def test_resolver_service_fts5_fail_fast(temp_resolver_db, monkeypatch):
    import samjon_memory.resolver.database as rdb

    monkeypatch.setattr(rdb, "fts5_available", lambda _conn: False)
    with pytest.raises(ResolverDatabaseUnavailable) as excinfo:
        ResolverService(database_path=temp_resolver_db)
    assert excinfo.value.code == "RESOLVER_DATABASE_UNAVAILABLE"


# ---- Readiness independence ----------------------------------------------


def test_core_readiness_independent_of_resolver_readiness(temp_db, temp_resolver_db):
    core = CoreService(database_path=temp_db)
    rsvc = ResolverService(database_path=temp_resolver_db)

    assert core.health()["status"] == "ok"
    assert rsvc.readiness()["resolver"]["status"] == "ok"

    # Degrade the Resolver without touching Core.
    rsvc.conn.close()
    assert rsvc.readiness()["resolver"]["status"] == "degraded"
    assert rsvc.readiness()["resolver"]["database_available"] is False
    assert core.health()["status"] == "ok"


def test_resolver_ready_endpoint(temp_resolver_db):
    from samjon_memory.core.main import app
    from fastapi.testclient import TestClient

    app.state.resolver_service = ResolverService(database_path=temp_resolver_db)
    client = TestClient(app)
    response = client.get("/resolver/ready")
    assert response.status_code == 200
    data = response.json()["resolver"]
    assert data["status"] == "ok"
    assert data["database_available"] is True
    assert data["schema_version"] == RESOLVER_SCHEMA_VERSION
    assert data["fts5_available"] is True
    assert data["projection_built"] is False
